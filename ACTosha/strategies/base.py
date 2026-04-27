"""Base strategy class, SignalBundle dataclass, and common risk utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import pandas as pd


# ------------------------------------------------------------------
# SignalBundle — container for strategy-generated signals
# ------------------------------------------------------------------

@dataclass
class SignalBundle:
    """Container for strategy-generated trading signals.

    Attributes
    ----------
    signals : pd.DataFrame
        DataFrame with one row per bar. Columns:
            - side:       "long" | "short" | "close" | "none"
            - strength:   float 0.0–1.0
            - entry_price: float | None
            - stop_loss:   float | None
            - take_profit: float | None
            - metadata:    dict (per-row extra info)
    metadata : dict
        Strategy-level info: name, params, created_at, etc.

    The underlying DataFrame index must be a DatetimeIndex (UTC).
    """

    signals: pd.DataFrame = field(default_factory=lambda: _empty_signals())
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metadata.setdefault("created_at", datetime.utcnow())

    @property
    def is_empty(self) -> bool:
        return self.signals.empty or (self.signals["side"] == "none").all()

    def filter_side(self, side: str) -> pd.DataFrame:
        return self.signals[self.signals["side"] == side].copy()


def _empty_signals() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["side", "strength", "entry_price", "stop_loss", "take_profit"]
    ).astype({
        "side": "string",
        "strength": "float64",
        "entry_price": "float64",
        "stop_loss": "float64",
        "take_profit": "float64",
    })


# ------------------------------------------------------------------
# Strategy — abstract base class
# ------------------------------------------------------------------

class Strategy(ABC):
    """Abstract base class for all trading strategies.

    Concrete strategies must implement:
        name property
        generate_signals()

    The strategy operates on OHLCV DataFrames with columns:
        timestamp (DatetimeIndex UTC), open, high, low, close, volume
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""
        ...

    @property
    def symbols(self) -> list[str]:
        """List of symbols this strategy trades."""
        return []

    @property
    def timeframe(self) -> str:
        """Primary timeframe for this strategy."""
        return "1h"

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate trading signals from OHLCV data.

        Args:
            df: OHLCV DataFrame with columns: timestamp (index),
                open, high, low, close, volume

        Returns:
            SignalBundle with signals DataFrame and metadata.
        """
        ...

    def get_params(self) -> dict:
        """Return strategy parameters as a dict."""
        return {}

    def validate_df(self, df: pd.DataFrame) -> None:
        """Validate that df has required OHLCV columns."""
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise KeyError(
                f"{self.name}: DataFrame missing required columns: {missing}"
            )


# ------------------------------------------------------------------
# BaseStrategy — base implementation with common position & risk helpers
# ------------------------------------------------------------------

class BaseStrategy(Strategy):
    """Base implementation with common position sizing and risk management.

    Subclasses should call _init_base() in __init__ and use inherited helpers.
    """

    def __init__(
        self,
        initial_capital: float = 10_000.0,
        risk_per_trade: float = 0.02,
        max_positions: int = 1,
    ) -> None:
        self._initial_capital = initial_capital
        self._risk_per_trade = risk_per_trade
        self._max_positions = max_positions

    def get_params(self) -> dict:
        return {
            "initial_capital": self._initial_capital,
            "risk_per_trade": self._risk_per_trade,
            "max_positions": self._max_positions,
        }

    # ------------------------------------------------------------------
    # Position sizing helpers
    # ------------------------------------------------------------------

    def calc_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        capital: float | None = None,
    ) -> float:
        """Calculate position size (in quote currency) based on risk.

        Uses ATR or fixed stop distance. Falls back to 2% of capital.
        """
        if capital is None:
            capital = self._initial_capital

        risk_amount = capital * self._risk_per_trade

        if stop_loss and stop_loss != entry_price:
            stop_distance = abs(entry_price - stop_loss)
            size = risk_amount / stop_distance
            return round(size, 4)

        # Fallback: use 2% of capital / entry_price
        return round(capital * 0.02 / entry_price, 4)

    def calc_stop_loss(
        self,
        entry_price: float,
        direction: Literal["long", "short"],
        atr_value: float | None = None,
        multiplier: float = 2.0,
    ) -> float:
        """Calculate a stop-loss price from entry and ATR."""
        if atr_value:
            distance = atr_value * multiplier
        else:
            distance = entry_price * 0.02  # 2% fallback

        if direction == "long":
            return round(entry_price - distance, 4)
        else:
            return round(entry_price + distance, 4)

    def calc_take_profit(
        self,
        entry_price: float,
        direction: Literal["long", "short"],
        stop_loss: float | None = None,
        risk_reward: float = 2.0,
    ) -> float:
        """Calculate take-profit price from entry, stop-loss, and R:R ratio."""
        if stop_loss:
            risk = abs(entry_price - stop_loss)
            reward = risk * risk_reward
        else:
            reward = entry_price * 0.04  # 4% fallback

        if direction == "long":
            return round(entry_price + reward, 4)
        else:
            return round(entry_price - reward, 4)

    # ------------------------------------------------------------------
    # Signal building helpers
    # ------------------------------------------------------------------

    def _build_signal_row(
        self,
        timestamp,
        side: str,
        strength: float,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Build a single signal row dict."""
        return {
            "side": side,
            "strength": round(float(strength), 4),
            "entry_price": float(entry_price) if entry_price is not None else None,
            "stop_loss": float(stop_loss) if stop_loss is not None else None,
            "take_profit": float(take_profit) if take_profit is not None else None,
            "metadata": metadata or {},
        }

    def _signals_from_crossover(
        self,
        df: pd.DataFrame,
        fast_col: str,
        slow_col: str,
        direction: Literal["long", "short"],
    ) -> pd.DataFrame:
        """Generate signals from column crossover (e.g. EMA 9 crosses EMA 21).

        long  = fast crosses above slow
        short = fast crosses below slow
        close = reverse cross
        """
        fast = df[fast_col]
        slow = df[slow_col]

        above = fast > slow
        cross_up = above & ~above.shift(1).fillna(False)
        cross_down = (~above) & above.shift(1).fillna(False)
        cross_reverse = cross_up | cross_down

        sides = pd.Series("none", index=df.index)
        sides[cross_up] = "long"
        sides[cross_down] = "short"
        # Close on reverse cross (optional — subclasses override if needed)
        # sides[cross_reverse] = "close"

        # Strength based on how far apart the lines are (volatility proxy)
        spread = (fast - slow).abs()
        spread_ma = spread.rolling(20, min_periods=1).mean()
        strength = (spread / spread_ma.replace(0, 1)).clip(0, 1)

        signals = pd.DataFrame(
            {"side": sides, "strength": strength.fillna(0.5)}
        )
        signals["entry_price"] = None
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(signals)

        return signals


__all__ = ["Strategy", "BaseStrategy", "SignalBundle"]