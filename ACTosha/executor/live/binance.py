"""BinanceExecutor — live execution on Binance (spot + USD-M futures) via CCXT."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

import ccxt

from ACTosha.executor.base import AbstractExecutor, ExecutionResult, Order, Position


log = logging.getLogger(__name__)

# Commission rates
BINANCE_SPOT_MAKER_FEE = 0.001    # 0.1%
BINANCE_SPOT_TAKER_FEE = 0.001    # 0.1%
BINANCE_PERP_MAKER_FEE = 0.0002   # 0.02%
BINANCE_PERP_TAKER_FEE = 0.0004  # 0.04%


class BinanceExecutor(AbstractExecutor):
    """Live order execution on Binance (spot + USD-M futures) via CCXT.

    Supports: Market, Limit, Stop, and Take-Profit orders.
    Tracks positions and balance via the Binance API.

    Parameters
    ----------
    api_key : str | None
        Binance API key. If None, only public endpoints are accessible.
    api_secret : str | None
        Binance API secret.
    spot : bool
        If True, trade spot market. If False, trade USD-M perpetuals (default: False).
    testnet : bool
        Use Binance testnet (default: False).
    margin_mode : Literal["cross", "isolated"]
        Margin mode for futures trading (default: "cross").
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        spot: bool = False,
        testnet: bool = False,
        margin_mode: Literal["cross", "isolated"] = "cross",
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._spot = spot
        self._testnet = testnet
        self._margin_mode = margin_mode

        self._ccxt: ccxt.binance = self._init_ccxt()
        self._position_cache: list[Position] = []
        self._balance_cache: dict[str, float] = {}
        self._open_orders_cache: list[dict] = []

    def _init_ccxt(self) -> ccxt.binance:
        """Initialise the CCXT Binance exchange."""
        exchange_config: dict[str, Any] = {
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot" if self._spot else "future",
                "marginMode": self._margin_mode,
            },
        }

        if self._api_key and self._api_secret:
            exchange_config["apiKey"] = self._api_key
            exchange_config["secret"] = self._api_secret

        if self._testnet:
            exchange_config["testnet"] = True

        exchange = ccxt.binance(exchange_config)
        return exchange

    def _to_position(self, raw: dict) -> Position:
        """Convert a CCXT position dict to our Position dataclass."""
        size = float(raw.get("size", raw.get("contracts", 0)) or 0)
        entry_price = float(raw.get("entryPrice", raw.get("entry price", 0) or 0)
                            or float(raw.get("info", {}).get("entryPrice", 0) or 0))
        unrealized_pnl = float(raw.get("unrealizedPnl", raw.get("unrealized profit", 0) or 0)
                               or float(raw.get("info", {}).get("unrealizedProfit", 0) or 0))
        symbol = raw.get("symbol", raw.get("info", {}).get("symbol", ""))
        side = raw.get("side", raw.get("info", {}).get("side", ""))
        if not side:
            side = "long" if size > 0 else "short"
        return Position(
            symbol=symbol,
            side=side if isinstance(side, str) else "long",
            size=abs(size),
            entry_price=entry_price,
            unrealized_pnl=unrealized_pnl,
            opened_at=datetime.utcnow(),
        )

    def _symbol_for_ccxt(self, symbol: str) -> str:
        """Normalize symbol to CCXT format (e.g. 'BTCUSDT' → 'BTC/USDT')."""
        if "/" in symbol:
            return symbol
        if self._spot:
            # Binance spot uses BTCUSDT format
            if symbol.endswith("USDT"):
                return f"{symbol[:-4]}/USDT"
            if symbol.endswith("BUSD"):
                return f"{symbol[:-4]}/BUSD"
            if symbol.endswith("BTC"):
                return f"{symbol[:-3]}/BTC"
            return f"{symbol}/USDT"
        else:
            # USD-M futures
            if symbol.endswith("USDT"):
                return f"{symbol[:-4]}/USDT:USDT"
            return f"{symbol}/USDT:USDT"

    def _ccxt_order_type(self, order_type: str) -> str:
        """Map our order_type string to CCXT format."""
        mapping = {
            "market": "market",
            "limit": "limit",
            "stop": "stop",
            "take_profit": "take_profit",
            "stop_loss_limit": "stop_loss_limit",
            "stop_market": "stop_market",
            "take_profit_market": "take_profit_market",
        }
        return mapping.get(order_type, order_type)

    # ------------------------------------------------------------------
    # AbstractExecutor interface
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> ExecutionResult:
        """Submit an order to Binance.

        Parameters
        ----------
        order : Order
            Order with symbol, side, order_type, size, price, stop_price.

        Returns
        -------
        ExecutionResult
        """
        try:
            ccxt_symbol = self._symbol_for_ccxt(order.symbol)
            ccxt_type = self._ccxt_order_type(order.order_type)

            ccxt_order: dict[str, Any] = {
                "symbol": ccxt_symbol,
                "side": order.side,  # 'buy' or 'sell'
                "type": ccxt_type,
                "amount": order.size,
            }

            if order.order_type in ("limit", "stop", "take_profit", "stop_loss_limit"):
                if order.price is not None:
                    ccxt_order["price"] = order.price
                else:
                    return ExecutionResult(
                        success=False,
                        order_id=order.order_id,
                        message=f"{order.order_type} order requires a price",
                    )

            if order.order_type in ("stop", "take_profit", "stop_market", "take_profit_market"):
                if order.stop_price is not None:
                    ccxt_order["stopPrice"] = order.stop_price
                elif order.price is not None:
                    ccxt_order["stopPrice"] = order.price

            raw = self._ccxt.create_order(**ccxt_order)

            order_id = str(raw.get("id", order.order_id or ""))
            filled_price = float(raw.get("average", raw.get("price", 0) or 0))
            filled_size = float(raw.get("filled", raw.get("amount", 0) or 0))
            commission = self._calc_commission(filled_price, filled_size, order.order_type)

            self.refresh_state()

            return ExecutionResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price if filled_price > 0 else None,
                filled_size=filled_size if filled_size > 0 else None,
                commission=commission,
                message=f"Order {order_id} submitted successfully",
            )

        except ccxt.BaseError as e:
            log.error("Binance submit_order failed", extra={"error": str(e)})
            return ExecutionResult(
                success=False,
                order_id=order.order_id,
                message=f"CCXT error: {e}",
            )

    def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        """Cancel a pending order by ID.

        Parameters
        ----------
        order_id : str
            The exchange order ID to cancel.
        symbol : str
            Symbol for the order (required by some endpoints).

        Returns
        -------
        bool
            True if cancelled, False otherwise.
        """
        try:
            if symbol:
                ccxt_symbol = self._symbol_for_ccxt(symbol)
            else:
                found = next(
                    (o for o in self._open_orders_cache if str(o.get("id")) == str(order_id)),
                    None,
                )
                if found:
                    ccxt_symbol = found["symbol"]
                else:
                    log.warning("cancel_order: symbol required when not in cache")
                    return False

            self._ccxt.cancel_order(order_id, ccxt_symbol)
            self.refresh_state()
            return True

        except ccxt.BaseError as e:
            log.error("Binance cancel_order failed", extra={"order_id": order_id, "error": str(e)})
            return False

    def get_positions(self) -> list[Position]:
        """Return current open positions from Binance."""
        if self._spot:
            # Spot doesn't have positions in the same sense — return empty
            self._position_cache = []
            return self._position_cache

        try:
            raw = self._ccxt.fetch_positions()
            self._position_cache = [
                self._to_position(p) for p in raw
                if float(p.get("size", p.get("contracts", 0) or 0)) != 0
            ]
            return self._position_cache
        except ccxt.BaseError as e:
            log.error("Binance get_positions failed", extra={"error": str(e)})
            return self._position_cache

    def get_balance(self) -> dict[str, float]:
        """Return account balance from Binance.

        For spot: available balance per asset.
        For futures: USDT cross/isolated balance.
        """
        try:
            raw = self._ccxt.fetch_balance()
            if self._spot:
                # Filter out zero balances for readability
                self._balance_cache = {
                    asset: {
                        "free": float(info.get("free", 0)),
                        "total": float(info.get("total", info.get("free", 0) + info.get("locked", 0))),
                        "used": float(info.get("locked", 0)),
                    }
                    for asset, info in raw.items()
                    if isinstance(info, dict) and float(info.get("free", 0) + info.get("locked", 0)) > 0
                }
            else:
                usdt = raw.get("USDT", raw.get("info", {}).get("USDT", {}))
                if isinstance(usdt, dict):
                    self._balance_cache = {
                        "free": float(usdt.get("free", 0)),
                        "total": float(usdt.get("total", usdt.get("available", 0))),
                        "used": float(usdt.get("used", usdt.get("initialMargin", 0))),
                    }
                else:
                    self._balance_cache = {"free": 0.0, "total": 0.0, "used": 0.0}
            return self._balance_cache
        except ccxt.BaseError as e:
            log.error("Binance get_balance failed", extra={"error": str(e)})
            return self._balance_cache

    # ------------------------------------------------------------------
    # Extended API
    # ------------------------------------------------------------------

    def refresh_state(self) -> None:
        """Refresh cached positions, open orders, and balance in one call."""
        _ = self.get_balance()
        _ = self.get_positions()
        _ = self.get_open_orders()

    def get_open_orders(self, symbol: str = "") -> list[dict]:
        """Return currently open (pending) orders."""
        try:
            if symbol:
                ccxt_symbol = self._symbol_for_ccxt(symbol)
                orders = self._ccxt.fetch_open_orders(ccxt_symbol)
            else:
                orders = self._ccxt.fetch_open_orders()
            self._open_orders_cache = orders
            return orders
        except ccxt.BaseError as e:
            log.error("Binance get_open_orders failed", extra={"error": str(e)})
            return self._open_orders_cache

    def get_fills(self, symbol: str = "", limit: int = 50) -> list[dict]:
        """Return recent trade fills."""
        try:
            if symbol:
                ccxt_symbol = self._symbol_for_ccxt(symbol)
                return self._ccxt.fetch_my_trades(ccxt_symbol, limit=limit)
            return self._ccxt.fetch_my_trades(limit=limit)
        except ccxt.BaseError as e:
            log.error("Binance get_fills failed", extra={"error": str(e)})
            return []

    def get_ticker(self, symbol: str) -> dict | None:
        """Return current ticker for a symbol."""
        try:
            ccxt_symbol = self._symbol_for_ccxt(symbol)
            ticker = self._ccxt.fetch_ticker(ccxt_symbol)
            return {
                "symbol": symbol,
                "last": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume": ticker.get("baseVolume"),
                "timestamp": ticker.get("timestamp"),
            }
        except ccxt.BaseError as e:
            log.error("Binance get_ticker failed", extra={"symbol": symbol, "error": str(e)})
            return None

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict | None:
        """Return orderbook for a symbol."""
        try:
            ccxt_symbol = self._symbol_for_ccxt(symbol)
            return self._ccxt.fetch_order_book(ccxt_symbol, limit=limit)
        except ccxt.BaseError as e:
            log.error("Binance get_orderbook failed", extra={"symbol": symbol, "error": str(e)})
            return None

    def set_leverage(self, leverage: int, symbol: str = "") -> dict:
        """Set leverage for a USD-M futures symbol."""
        if self._spot:
            return {"error": "Cannot set leverage on spot market"}
        try:
            ccxt_symbol = self._symbol_for_ccxt(symbol) if symbol else None
            if ccxt_symbol:
                return self._ccxt.set_leverage(leverage, ccxt_symbol)
            return {"error": "symbol required for leverage setting"}
        except ccxt.BaseError as e:
            log.error("Binance set_leverage failed", extra={"leverage": leverage, "error": str(e)})
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calc_commission(
        self,
        price: float,
        size: float,
        order_type: str,
    ) -> float:
        """Calculate commission for a fill."""
        if self._spot:
            rate = BINANCE_SPOT_MAKER_FEE if order_type in ("limit",) else BINANCE_SPOT_TAKER_FEE
        else:
            rate = BINANCE_PERP_MAKER_FEE if order_type in ("limit",) else BINANCE_PERP_TAKER_FEE
        return price * size * rate


__all__ = ["BinanceExecutor"]
