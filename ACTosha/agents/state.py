"""Agent state, action, and event dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ACTosha.executor.base import Order, Position


@dataclass
class AgentState:
    """Current state of the trading system, observed by agents.

    Attributes
    ----------
    positions : list[Position]
        Open positions tracked by the executor.
    balance : float
        Available cash balance in quote currency.
    portfolio_value : float
        Total portfolio value (balance + open position values).
    open_orders : list[Order]
        Pending (unfilled or partially filled) orders.
    timestamp : datetime
        Snapshot timestamp.
    """

    positions: list[Position] = field(default_factory=list)
    balance: float = 0.0
    portfolio_value: float = 0.0
    open_orders: list[Order] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_exposure(self) -> float:
        """Sum of notional value of all open positions."""
        return sum(
            pos.size * pos.entry_price
            for pos in self.positions
            if pos.size > 0 and pos.entry_price > 0
        )

    def position_for_symbol(self, symbol: str) -> Position | None:
        """Return the open position for ``symbol`` or None."""
        for pos in self.positions:
            if pos.symbol == symbol:
                return pos
        return None


@dataclass
class AgentAction:
    """Action produced by an agent after step().

    Attributes
    ----------
    action_type : str
        One of: scan | backtest | trade | rebalance | alert | hold
    payload : dict[str, Any]
        Action-specific data (e.g. {"opportunities": [...]} for scan).
    confidence : float
        Confidence in the action, in [0.0, 1.0].
    """

    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    @property
    def is_noop(self) -> bool:
        return self.action_type == "hold" or self.confidence <= 0.0


@dataclass
class AgentEvent:
    """Event received by an agent from the message bus.

    Attributes
    ----------
    topic : str
        Message bus topic, e.g. "market.opportunity".
    source : str
        Agent ID that published this event.
    data : dict[str, Any]
        Event payload.
    timestamp : datetime
        When the event was published.
    """

    topic: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


__all__ = ["AgentState", "AgentAction", "AgentEvent"]
