"""Executor base class and order/position dataclasses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class Order:
    """Represents a trading order."""

    order_id: str = ""
    symbol: str = ""
    side: Literal["buy", "sell"] = "buy"
    order_type: Literal["market", "limit", "stop", "take_profit"] = "market"
    size: float = 0.0
    price: float | None = None
    stop_price: float | None = None
    created_at: datetime = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class Position:
    """Represents an open position."""

    symbol: str = ""
    side: Literal["long", "short"] = "long"
    size: float = 0.0
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    opened_at: datetime = None

    def __post_init__(self) -> None:
        if self.opened_at is None:
            self.opened_at = datetime.utcnow()


@dataclass
class ExecutionResult:
    """Result of an order execution attempt."""

    success: bool
    order_id: str
    filled_price: float | None = None
    filled_size: float | None = None
    commission: float = 0.0
    message: str = ""


class AbstractExecutor(ABC):
    """Abstract base class for order execution engines."""

    @abstractmethod
    def submit_order(self, order: Order) -> ExecutionResult:
        """Submit an order for execution."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order by ID."""
        ...

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return current open positions."""
        ...

    @abstractmethod
    def get_balance(self) -> dict[str, float]:
        """Return current account balance by asset."""
        ...


__all__ = ["AbstractExecutor", "Order", "Position", "ExecutionResult"]