"""PaperExecutor — simulated order execution without real API calls."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import pandas as pd

from ACTosha.executor.base import AbstractExecutor, ExecutionResult, Order, Position


@dataclass
class _OrderRecord:
    """Internal record for tracking pending and filled orders."""

    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop", "take_profit"]
    size: float
    price: float | None
    stop_price: float | None
    created_at: datetime
    status: Literal["pending", "filled", "cancelled"] = "pending"
    filled_price: float | None = None
    filled_at: datetime | None = None
    commission: float = 0.0


@dataclass
class PaperExecutorState:
    """Mutable state for PaperExecutor (separated for testability)."""

    balance: float = 10_000.0
    positions: list[Position] = field(default_factory=list)
    orders: dict[str, _OrderRecord] = field(default_factory=dict)
    order_history: list[ExecutionResult] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    peak_equity: float = 10_000.0
    trades: list[dict] = field(default_factory=list)
    _trade_counter: int = 0


class PaperExecutor(AbstractExecutor):
    """Paper (simulated) order executor.

    Tracks positions, PnL, margin state, and order history locally.
    No real API calls are made.

    Parameters
    ----------
    initial_balance : float
        Starting balance in quote currency (default: 10_000).
    commission : float
        Commission rate as a fraction per trade (default: 0.0004 = 0.04%).
    slippage_bps : float
        Slippage in basis points for market orders (default: 5 bps).
    maker_fee : float
        Maker fee rate (default: 0.0002 = 0.02%).
    taker_fee : float
        Taker fee rate (default: 0.0004 = 0.04%).
    funding_rate : float | None
        Hourly funding rate for long positions on perpetuals (default: None).
        Example: 0.00027 for 0.027% per hour on Hyperliquid.
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        commission: float = 0.0004,
        slippage_bps: float = 5.0,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0004,
        funding_rate: float | None = None,
    ) -> None:
        self._state = PaperExecutorState(balance=initial_balance)
        self._commission = commission
        self._slippage_bps = slippage_bps
        self._maker_fee = maker_fee
        self._taker_fee = taker_fee
        self._funding_rate = funding_rate
        self._last_equity_ts: datetime | None = None

    # ------------------------------------------------------------------
    # AbstractExecutor interface
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> ExecutionResult:
        """Submit a paper order.

        For market orders — fills immediately at simulated price.
        For limit/stop orders — stored as pending, can be triggered
        by calling ``trigger_order`` or ``trigger_all_pending``.
        """
        order_id = order.order_id or uuid.uuid4().hex[:12]
        record = _OrderRecord(
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            size=order.size,
            price=order.price,
            stop_price=order.stop_price,
            created_at=order.created_at or datetime.utcnow(),
        )

        if order.order_type == "market":
            return self._fill_market_order(record)
        else:
            self._state.orders[order_id] = record
            return ExecutionResult(
                success=True,
                order_id=order_id,
                message=f"Order {order_id} stored as pending ({order.order_type})",
            )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        record = self._state.orders.get(order_id)
        if record is None:
            return False
        if record.status != "pending":
            return False
        record.status = "cancelled"
        return True

    def get_positions(self) -> list[Position]:
        """Return current open positions."""
        return [p for p in self._state.positions if p.size != 0]

    def get_balance(self) -> dict[str, float]:
        """Return account balance."""
        return {"free": self._state.balance, "total": self._total_equity()}

    # ------------------------------------------------------------------
    # Paper-only extended API
    # ------------------------------------------------------------------

    def get_position(self, symbol: str) -> Position | None:
        """Return position for a symbol or None."""
        for p in self._state.positions:
            if p.symbol == symbol:
                return p
        return None

    def get_order(self, order_id: str) -> _OrderRecord | None:
        """Return order record by ID."""
        return self._state.orders.get(order_id)

    def get_pending_orders(self, symbol: str | None = None) -> list[_OrderRecord]:
        """Return pending orders, optionally filtered by symbol."""
        pending = [o for o in self._state.orders.values() if o.status == "pending"]
        if symbol:
            pending = [o for o in pending if o.symbol == symbol]
        return pending

    def trigger_order(
        self,
        order_id: str,
        current_price: float,
        high: float | None = None,
        low: float | None = None,
    ) -> ExecutionResult:
        """Trigger a pending limit/stop/take_profit order at current price.

        Parameters
        ----------
        order_id : str
            ID of the pending order.
        current_price : float
            Current market price of the symbol.
        high : float | None
            Current bar high (used for limit order fill modeling).
        low : float | None
            Current bar low (used for limit order fill modeling).

        Returns
        -------
        ExecutionResult
        """
        record = self._state.orders.get(order_id)
        if record is None or record.status != "pending":
            return ExecutionResult(
                success=False,
                order_id=order_id,
                message="Order not found or not pending",
            )

        if record.order_type == "limit":
            # Fill if price condition met
            filled = self._limit_would_fill(record, current_price, high, low)
            if not filled:
                return ExecutionResult(
                    success=False,
                    order_id=order_id,
                    message="Limit price not yet reached",
                )
        elif record.order_type == "stop":
            triggered = (
                (record.side == "buy" and current_price >= (record.stop_price or 0))
                or (record.side == "sell" and current_price <= (record.stop_price or float("inf")))
            )
            if not triggered:
                return ExecutionResult(
                    success=False,
                    order_id=order_id,
                    message="Stop price not yet triggered",
                )
            # Stop becomes market order — fill immediately
            record.order_type = "market"
        elif record.order_type == "take_profit":
            triggered = (
                (record.side == "sell" and current_price <= (record.stop_price or float("inf")))
                or (record.side == "buy" and current_price >= (record.stop_price or 0))
            )
            if not triggered:
                return ExecutionResult(
                    success=False,
                    order_id=order_id,
                    message="Take-profit price not yet triggered",
                )
            record.order_type = "market"

        return self._fill_market_order(record)

    def trigger_all_pending(
        self,
        symbol: str,
        current_price: float,
        high: float | None = None,
        low: float | None = None,
    ) -> list[ExecutionResult]:
        """Trigger all pending orders for a symbol at current price."""
        pending = self.get_pending_orders(symbol)
        results = []
        for record in pending:
            result = self.trigger_order(record.order_id, current_price, high, low)
            results.append(result)
        return results

    def set_market_price(self, symbol: str, price: float) -> None:
        """Set the current market price for a symbol (used for margin/PnL calc)."""
        for p in self._state.positions:
            if p.symbol == symbol:
                p.unrealized_pnl = self._calc_unrealized_pnl(p, price)

    def apply_bar_close(
        self,
        symbol: str,
        close_price: float,
        open_price: float,
        high_price: float,
        low_price: float,
        timestamp: pd.Timestamp,
    ) -> list[ExecutionResult]:
        """Apply end-of-bar updates: trigger pending orders, update PnL.

        This is the main entry point for backtesting loops.

        Parameters
        ----------
        symbol : str
            Trading symbol.
        close_price : float
            Closing price of the bar.
        open_price : float
            Opening price of the bar.
        high_price : float
            High price of the bar.
        low_price : float
            Low price of the bar.
        timestamp : pd.Timestamp
            Bar timestamp.

        Returns
        -------
        list[ExecutionResult]
            Results from any triggered orders.
        """
        self.set_market_price(symbol, close_price)
        # Funding for open positions
        self._apply_funding(symbol, close_price, timestamp)
        # Trigger pending orders
        return self.trigger_all_pending(symbol, close_price, high_price, low_price)

    def get_equity(self) -> float:
        """Current total equity (balance + net unrealized PnL)."""
        return self._total_equity()

    def get_equity_curve(self) -> list[float]:
        """Historical equity values."""
        return self._state.equity_curve.copy()

    def get_trades(self) -> list[dict]:
        """Closed trade history."""
        return self._state.trades.copy()

    def snapshot_equity(self, timestamp: datetime | None = None) -> None:
        """Record current equity in the equity curve."""
        self._state.equity_curve.append(self._total_equity())
        if self._state.equity_curve[-1] > self._state.peak_equity:
            self._state.peak_equity = self._state.equity_curve[-1]

    def reset(self, initial_balance: float = 10_000.0) -> None:
        """Reset all state to initial conditions."""
        self._state = PaperExecutorState(balance=initial_balance)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fill_market_order(self, record: _OrderRecord) -> ExecutionResult:
        """Fill a market order at a simulated price."""
        price = record.price or 0.0
        if price <= 0:
            return ExecutionResult(
                success=False,
                order_id=record.order_id,
                message="No reference price for market order",
            )

        # Apply slippage
        bps = self._slippage_bps / 10_000.0
        if record.side == "buy":
            fill_price = price * (1 + bps)
        else:
            fill_price = price * (1 - bps)

        commission = fill_price * record.size * self._taker_fee
        total_cost = fill_price * record.size + commission if record.side == "buy" else fill_price * record.size - commission

        if record.side == "buy":
            if total_cost > self._state.balance:
                return ExecutionResult(
                    success=False,
                    order_id=record.order_id,
                    message=f"Insufficient balance: required {total_cost:.2f}, available {self._state.balance:.2f}",
                )
            self._state.balance -= total_cost
        else:  # sell
            self._state.balance += fill_price * record.size - commission

        # Update or create position
        self._update_position(record, fill_price, commission)

        record.status = "filled"
        record.filled_price = fill_price
        record.filled_at = datetime.utcnow()
        record.commission = commission
        self._state.orders[record.order_id] = record

        result = ExecutionResult(
            success=True,
            order_id=record.order_id,
            filled_price=fill_price,
            filled_size=record.size,
            commission=commission,
            message=f"Filled {record.side} {record.size} {record.symbol} @ {fill_price:.4f}",
        )
        self._state.order_history.append(result)
        self._record_trade(record, fill_price, commission)
        return result

    def _update_position(
        self,
        record: _OrderRecord,
        fill_price: float,
        commission: float,
    ) -> None:
        """Update position after a fill."""
        existing = self.get_position(record.symbol)

        if record.side == "buy":
            if existing is None or existing.size == 0:
                new_pos = Position(
                    symbol=record.symbol,
                    side="long",
                    size=record.size,
                    entry_price=fill_price,
                    unrealized_pnl=0.0,
                )
                self._state.positions.append(new_pos)
            else:
                # Add to long position — weighted average entry
                total_size = existing.size + record.size
                existing.entry_price = (
                    (existing.entry_price * existing.size + fill_price * record.size) / total_size
                )
                existing.size = total_size
        else:  # sell
            if existing is None or existing.size == 0:
                new_pos = Position(
                    symbol=record.symbol,
                    side="short",
                    size=record.size,
                    entry_price=fill_price,
                    unrealized_pnl=0.0,
                )
                self._state.positions.append(new_pos)
            else:
                if existing.side == "long":
                    # Flatten long position
                    if record.size >= existing.size:
                        # Close long, open short
                        remaining = record.size - existing.size
                        existing.size = remaining
                        existing.side = "short"
                        existing.entry_price = fill_price
                        existing.unrealized_pnl = 0.0
                    else:
                        # Partial close of long
                        existing.size -= record.size
                        existing.unrealized_pnl = 0.0
                else:
                    # Add to short
                    total_size = existing.size + record.size
                    existing.entry_price = (
                        (existing.entry_price * existing.size + fill_price * record.size) / total_size
                    )
                    existing.size = total_size

    def _calc_unrealized_pnl(self, position: Position, current_price: float) -> float:
        """Calculate unrealized PnL for a position at current price."""
        if position.size == 0:
            return 0.0
        if position.side == "long":
            return (current_price - position.entry_price) * position.size
        else:
            return (position.entry_price - current_price) * position.size

    def _total_equity(self) -> float:
        """Total equity = balance + sum(unrealized PnL)."""
        unrealized = sum(
            self._calc_unrealized_pnl(p, p.entry_price) for p in self._state.positions
        )
        # Use entry_price as proxy for current when no market price set
        unrealized = sum(p.unrealized_pnl for p in self._state.positions)
        return self._state.balance + unrealized

    def _limit_would_fill(
        self,
        record: _OrderRecord,
        current_price: float,
        high: float | None,
        low: float | None,
    ) -> bool:
        """Determine if a limit order would fill at current price."""
        if record.side == "buy":
            # Buy limit fills if price dipped to or below limit
            return (low is not None and low <= (record.price or float("inf"))) or current_price <= (record.price or float("inf"))
        else:
            # Sell limit fills if price rose to or above limit
            return (high is not None and high >= record.price) or current_price >= (record.price or 0.0)

    def _apply_funding(self, symbol: str, current_price: float, timestamp: pd.Timestamp) -> None:
        """Accrue funding payment on open perpetual positions."""
        if self._funding_rate is None:
            return
        pos = self.get_position(symbol)
        if pos is None or pos.size == 0:
            return
        notional = pos.size * current_price
        # Simplified: funding per hour; assume 1h bars
        payment = notional * self._funding_rate
        if pos.side == "long":
            self._state.balance -= payment
        else:
            self._state.balance += payment

    def _record_trade(
        self,
        record: _OrderRecord,
        fill_price: float,
        commission: float,
    ) -> None:
        """Append a closed trade to history."""
        self._state._trade_counter += 1
        self._state.trades.append(
            {
                "trade_id": f"paper_{self._state._trade_counter}",
                "order_id": record.order_id,
                "symbol": record.symbol,
                "side": record.side,
                "size": record.size,
                "price": fill_price,
                "commission": commission,
                "timestamp": record.filled_at or datetime.utcnow(),
            }
        )


# Re-export OrderSide for compatibility with backtester
from ACTosha.backtester.simulator import OrderSide  # noqa: E402, F401

__all__ = ["PaperExecutor", "PaperExecutorState"]
