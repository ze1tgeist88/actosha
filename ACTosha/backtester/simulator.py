"""OrderSimulator — fill model, slippage, commission, and funding rates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import pandas as pd


# ------------------------------------------------------------------
# Enums & Dataclasses
# ------------------------------------------------------------------

class OrderSide(Enum):
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


class FillMode(Enum):
    """Bar execution model."""

    NEXT_OPEN = "next_open"       # conservative: fill at next bar open
    HIGH_LOW = "high_low"          # aggressive: long at high, short at low


@dataclass
class FundingRate:
    """Funding rate record for a perpetual futures position."""

    rate: float          # e.g. 0.0001 for 0.01% per funding interval
    interval_hours: float = 8.0   # funding settles every N hours


@dataclass
class Order:
    """An order to be simulated."""

    side: OrderSide
    price: float          # reference price at time of signal
    size: float           # notional size in quote currency
    timestamp: pd.Timestamp


@dataclass
class Fill:
    """A filled order with realized execution details."""

    side: OrderSide
    price: float          # actual filled price (after slippage)
    size: float
    commission: float
    slippage_cost: float
    timestamp: pd.Timestamp
    bar_timestamp: pd.Timestamp   # the bar where fill occurred


@dataclass
class FundingPayment:
    """A funding rate payment accrued during a position."""

    timestamp: pd.Timestamp
    rate: float
    position_notional: float
    payment: float        # signed: positive = pay, negative = receive


# ------------------------------------------------------------------
# Exchange Configurations
# ------------------------------------------------------------------

EXCHANGE_FUNDING: dict[str, FundingRate] = {
    "hyperliquid": FundingRate(rate=0.00027, interval_hours=1.0),   # ~0.027% / hour ≈ 0.065%/8h (typical)
    "binance_perp": FundingRate(rate=0.0001, interval_hours=8.0),    # ~0.01% per 8h
}


# ------------------------------------------------------------------
# OrderSimulator
# ------------------------------------------------------------------

class OrderSimulator:
    """Simulate order execution with fill model, slippage, and fees.

    Parameters
    ----------
    commission : float
        Commission rate as a fraction per trade (e.g. 0.0004 = 0.04%).
    slippage_bps : float
        Slippage in basis points (e.g. 5 bps = 0.0005).
    fill_mode : FillMode
        Whether to fill at next bar open (conservative) or high/low (aggressive).
    exchange : str
        Exchange name for funding rate lookup. Pass None to disable funding.
    """

    def __init__(
        self,
        commission: float = 0.0004,
        slippage_bps: float = 5.0,
        fill_mode: FillMode = FillMode.NEXT_OPEN,
        exchange: str | None = None,
    ) -> None:
        self.commission = commission
        self.slippage_bps = slippage_bps
        self.fill_mode = fill_mode
        self.exchange = exchange
        self._funding_rate: FundingRate | None = (
            EXCHANGE_FUNDING.get(exchange) if exchange else None
        )

    # ------------------------------------------------------------------
    # Slippage model
    # ------------------------------------------------------------------

    def _slippage_price(
        self,
        bar: pd.Series,
        side: OrderSide,
        reference_price: float,
    ) -> float:
        """Compute execution price after slippage.

        For NEXT_OPEN: use next bar open ± slippage.
        For HIGH_LOW:  long fills at bar high, short fills at bar low.
        """
        if self.fill_mode == FillMode.NEXT_OPEN:
            exec_price = bar["open"]
        else:  # FillMode.HIGH_LOW
            exec_price = bar["high"] if side == OrderSide.LONG else bar["low"]

        # Slippage in bps; always against the taker (worse fill)
        bps = self.slippage_bps / 10_000.0
        if side == OrderSide.LONG:
            slippage_cost = exec_price * bps
            return exec_price + slippage_cost
        else:
            slippage_cost = exec_price * bps
            return exec_price - slippage_cost

    # ------------------------------------------------------------------
    # Commission model
    # ------------------------------------------------------------------

    def _calc_commission(self, fill_price: float, size: float) -> float:
        """Commission for a fill."""
        return fill_price * size * self.commission

    # ------------------------------------------------------------------
    # Funding rate model (perpetual futures)
    # ------------------------------------------------------------------

    def _calc_funding_payment(
        self,
        position_notional: float,
        entry_price: float,
        current_price: float,
        bar_timestamp: pd.Timestamp,
        prev_bar_timestamp: pd.Timestamp,
    ) -> list[FundingPayment]:
        """Accrue funding payments proportional to time in position.

        Funding is paid every `interval_hours`. We linearly interpolate
        based on elapsed time between bars.
        """
        if self._funding_rate is None:
            return []

        fr = self._funding_rate
        elapsed_hours = (bar_timestamp - prev_bar_timestamp).total_seconds() / 3600.0
        if elapsed_hours <= 0:
            return []

        funding_count = int(elapsed_hours / fr.interval_hours)
        if funding_count == 0:
            return []

        # Mark-to-market: position notional changes with price
        current_notional = position_notional  # simplified (use size * current_price if needed)
        payments = []
        payment_per_interval = current_notional * fr.rate

        for _ in range(funding_count):
            payments.append(
                FundingPayment(
                    timestamp=bar_timestamp,
                    rate=fr.rate,
                    position_notional=current_notional,
                    payment=payment_per_interval,  # positive = pay (long), negative would be receive
                )
            )
        return payments

    # ------------------------------------------------------------------
    # Main fill interface
    # ------------------------------------------------------------------

    def fill_order(
        self,
        order: Order,
        next_bar: pd.Series,
        bar_timestamp: pd.Timestamp,
        prev_timestamp: pd.Timestamp,
    ) -> Fill:
        """Execute an order on the next bar and return fill details.

        Parameters
        ----------
        order : Order
            The order to fill.
        next_bar : pd.Series
            The bar (row) at which the order is filled.
            Must contain: open, high, low (for HIGH_LOW mode).
        bar_timestamp : pd.Timestamp
            Timestamp of the fill bar.
        prev_timestamp : pd.Timestamp
            Timestamp of the previous bar (for funding calculation).

        Returns
        -------
        Fill
        """
        exec_price = self._slippage_price(next_bar, order.side, order.price)
        commission = self._calc_commission(exec_price, order.size)

        # Slippage cost in quote currency
        bps = self.slippage_bps / 10_000.0
        slippage_cost = abs(exec_price - next_bar["open"]) * order.size

        return Fill(
            side=order.side,
            price=exec_price,
            size=order.size,
            commission=commission,
            slippage_cost=slippage_cost,
            timestamp=order.timestamp,
            bar_timestamp=bar_timestamp,
        )

    def calc_funding_for_position(
        self,
        position_notional: float,
        entry_price: float,
        current_price: float,
        bar_timestamp: pd.Timestamp,
        prev_timestamp: pd.Timestamp,
    ) -> list[FundingPayment]:
        """Calculate funding payments accrued while holding a position.

        Call this each bar while a position is open.
        """
        return self._calc_funding_payment(
            position_notional, entry_price, current_price,
            bar_timestamp, prev_timestamp,
        )


__all__ = [
    "OrderSimulator",
    "Order",
    "Fill",
    "FillMode",
    "FundingPayment",
    "FundingRate",
    "OrderSide",
    "EXCHANGE_FUNDING",
]
