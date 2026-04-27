"""HyperliquidExecutor — live execution on Hyperliquid perpetuals via CCXT."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

import ccxt

from ACTosha.executor.base import AbstractExecutor, ExecutionResult, Order, Position


log = logging.getLogger(__name__)


# Commission rates for Hyperliquid (approximate, verify with official docs)
HYPERLIQUID_TAKER_FEE = 0.0005   # 0.05%
HYPERLIQUID_MAKER_FEE = 0.00035  # 0.035%


class HyperliquidExecutor(AbstractExecutor):
    """Live order execution on Hyperliquid perpetuals via CCXT.

    Supports: Market, Limit, Stop, and Take-Profit orders.
    Tracks positions and balance via the Hyperliquid API.

    Parameters
    ----------
    api_key : str | None
        Hyperliquid API key. If None, only public endpoints are accessible.
    api_secret : str | None
        Hyperliquid API secret.
    testnet : bool
        Use the Hyperliquid testnet (default: False).
        Testnet endpoint: https://api.hyperliquid-testnet.xyz
    wallet_address : str | None
        Wallet address for perpertual accounts (required for trading).
    skip_order_padding : bool
        Skip order-size padding (default: False).
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        testnet: bool = False,
        wallet_address: str | None = None,
        skip_order_padding: bool = False,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._wallet_address = wallet_address or api_key
        self._skip_order_padding = skip_order_padding

        self._ccxt: ccxt.Hyperliquid = self._init_ccxt()
        self._position_cache: list[Position] = []
        self._balance_cache: dict[str, float] = {}
        self._open_orders_cache: list[dict] = []

    def _init_ccxt(self) -> ccxt.Hyperliquid:
        """Initialise the CCXT Hyperliquid exchange."""
        exchange_config: dict[str, Any] = {
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "settlementMode": "inverse",  # USD-M perpetuals
            },
        }

        if self._api_key and self._api_secret:
            exchange_config["apiKey"] = self._api_key
            exchange_config["secret"] = self._api_secret

        if self._testnet:
            exchange_config["testnet"] = True
            exchange_config["options"]["endpoint"] = "https://api.hyperliquid-testnet.xyz"

        exchange = ccxt.hyperliquid(exchange_config)
        return exchange

    def _to_position(self, raw: dict) -> Position:
        """Convert a CCXT position dict to our Position dataclass."""
        size = float(raw.get("size", 0))
        entry_price = float(raw.get("entryPrice", 0) or 0)
        unrealized_pnl = float(raw.get("unrealizedPnl", 0) or 0)
        return Position(
            symbol=raw.get("symbol", raw.get("info", {}).get("coin", "")),
            side="long" if size > 0 else "short",
            size=abs(size),
            entry_price=entry_price,
            unrealized_pnl=unrealized_pnl,
            opened_at=datetime.utcnow(),
        )

    def _symbol_for_ccxt(self, symbol: str) -> str:
        """Normalize symbol to CCXT format (e.g. 'BTC' → 'BTC/USDC:USDC')."""
        if "/" in symbol:
            return symbol
        return f"{symbol}/USDC:USDC"

    # ------------------------------------------------------------------
    # AbstractExecutor interface
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> ExecutionResult:
        """Submit an order to Hyperliquid.

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
            order_type = order.order_type.upper()
            if order_type == "MARKET":
                order_type = "market"
            elif order_type == "LIMIT":
                order_type = "limit"
            elif order_type == "STOP":
                order_type = "stop"
            elif order_type == "TAKE_PROFIT":
                order_type = "takeProfit"

            params: dict[str, Any] = {}

            # Build CCXT order params
            ccxt_order: dict[str, Any] = {
                "symbol": ccxt_symbol,
                "side": order.side,  # 'buy' or 'sell'
                "type": order_type,
                "amount": order.size,
            }

            if order.order_type in ("limit", "stop", "take_profit"):
                if order.price is not None:
                    ccxt_order["price"] = order.price
                else:
                    return ExecutionResult(
                        success=False,
                        order_id=order.order_id,
                        message=f"{order.order_type} order requires a price",
                    )

            if order.order_type in ("stop", "take_profit"):
                if order.stop_price is not None:
                    params["stopPrice"] = order.stop_price
                elif order.price is not None:
                    params["stopPrice"] = order.price

            if order.order_type == "stop":
                params["triggerPrice"] = order.stop_price or order.price
                params["stopLossPrice"] = order.stop_price

            if params:
                ccxt_order["params"] = params

            raw = self._ccxt.create_order(**ccxt_order)

            order_id = str(raw.get("id", order.order_id or ""))
            filled_price = float(raw.get("average", raw.get("price", 0) or 0))
            filled_size = float(raw.get("filled", raw.get("amount", 0) or 0))
            commission = self._calc_commission(filled_price, filled_size, order.order_type)

            # Refresh positions after order
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
            log.error("Hyperliquid submit_order failed", extra={"error": str(e)})
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
            Symbol for the order (required by some exchanges).

        Returns
        -------
        bool
            True if cancelled, False otherwise.
        """
        try:
            if symbol:
                ccxt_symbol = self._symbol_for_ccxt(symbol)
            else:
                # Try to find the order's symbol from open orders cache
                found = next(
                    (o for o in self._open_orders_cache if o.get("id") == order_id),
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
            log.error("Hyperliquid cancel_order failed", extra={"order_id": order_id, "error": str(e)})
            return False

    def get_positions(self) -> list[Position]:
        """Return current open positions from Hyperliquid."""
        try:
            raw_positions = self._ccxt.fetch_positions()
            self._position_cache = [
                self._to_position(p) for p in raw_positions
                if float(p.get("size", 0)) != 0
            ]
            return self._position_cache
        except ccxt.BaseError as e:
            log.error("Hyperliquid get_positions failed", extra={"error": str(e)})
            return self._position_cache

    def get_balance(self) -> dict[str, float]:
        """Return account balance from Hyperliquid.

        Returns dict with keys: free, total, used, in USD.
        """
        try:
            raw = self._ccxt.fetch_balance()
            usdc = raw.get("USDC", raw.get("USD", {}))
            self._balance_cache = {
                "free": float(usdc.get("free", 0)),
                "total": float(usdc.get("total", 0)),
                "used": float(usdc.get("used", 0)),
            }
            return self._balance_cache
        except ccxt.BaseError as e:
            log.error("Hyperliquid get_balance failed", extra={"error": str(e)})
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
        """Return currently open (pending) orders.

        Parameters
        ----------
        symbol : str
            Filter by symbol. If empty, returns all open orders.

        Returns
        -------
        list[dict]
            List of CCXT order dicts.
        """
        try:
            if symbol:
                ccxt_symbol = self._symbol_for_ccxt(symbol)
                orders = self._ccxt.fetch_open_orders(ccxt_symbol)
            else:
                orders = self._ccxt.fetch_open_orders()
            self._open_orders_cache = orders
            return orders
        except ccxt.BaseError as e:
            log.error("Hyperliquid get_open_orders failed", extra={"error": str(e)})
            return self._open_orders_cache

    def get_fills(self, symbol: str = "", limit: int = 50) -> list[dict]:
        """Return recent trade fills.

        Parameters
        ----------
        symbol : str
            Filter by symbol.
        limit : int
            Maximum number of recent fills (default: 50).

        Returns
        -------
        list[dict]
            List of CCXT trade dicts.
        """
        try:
            if symbol:
                ccxt_symbol = self._symbol_for_ccxt(symbol)
                return self._ccxt.fetch_my_trades(ccxt_symbol, limit=limit)
            return self._ccxt.fetch_my_trades(limit=limit)
        except ccxt.BaseError as e:
            log.error("Hyperliquid get_fills failed", extra={"error": str(e)})
            return []

    def get_ticker(self, symbol: str) -> dict | None:
        """Return current ticker (last price, bid, ask, volume) for a symbol."""
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
            log.error("Hyperliquid get_ticker failed", extra={"symbol": symbol, "error": str(e)})
            return None

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict | None:
        """Return orderbook for a symbol."""
        try:
            ccxt_symbol = self._symbol_for_ccxt(symbol)
            return self._ccxt.fetch_order_book(ccxt_symbol, limit=limit)
        except ccxt.BaseError as e:
            log.error("Hyperliquid get_orderbook failed", extra={"symbol": symbol, "error": str(e)})
            return None

    def set_leverage(self, leverage: int, symbol: str = "BTC/USDC:USDC") -> dict:
        """Set leverage for a symbol.

        Parameters
        ----------
        leverage : int
            Target leverage (e.g. 3 for 3x).
        symbol : str
            Symbol to set leverage for.

        Returns
        -------
        dict
            Exchange response.
        """
        try:
            ccxt_symbol = self._symbol_for_ccxt(symbol)
            return self._ccxt.set_leverage(leverage, ccxt_symbol)
        except ccxt.BaseError as e:
            log.error("Hyperliquid set_leverage failed", extra={"leverage": leverage, "error": str(e)})
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
        rate = HYPERLIQUID_MAKER_FEE if order_type in ("limit", "stop", "take_profit") else HYPERLIQUID_TAKER_FEE
        return price * size * rate


__all__ = ["HyperliquidExecutor"]
