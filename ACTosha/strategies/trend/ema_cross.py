"""Trend following strategy: EMA 9/21 crossover."""

from __future__ import annotations

from typing import Literal

import pandas as pd

from ACTosha.indicators.moving_averages import compute_ema
from ACTosha.strategies.base import BaseStrategy, SignalBundle


class EMACrossStrategy(BaseStrategy):
    """EMA crossover trend-following strategy.

    Generates:
        - long  signal when fast EMA crosses above slow EMA
        - short signal when fast EMA crosses below slow EMA
        - close signal on reverse cross (optional, disabled by default)

    Parameters
    ----------
    fast_period : int
        Fast EMA period. Default: 9.
    slow_period : int
        Slow EMA period. Default: 21.
    close_on_reverse : bool
        If True, generate a "close" signal on reverse crossover. Default: False.
    min_strength : float
        Minimum signal strength (0–1) to emit a signal. Default: 0.0 (emit all).
    use_atr_sl : bool
        If True, compute stop-loss from ATR. Default: True.
    atr_period : int
        ATR period for stop-loss calculation. Default: 14.
    atr_multiplier : float
        ATR multiplier for stop-loss distance. Default: 2.0.
    risk_reward : float
        Take-profit distance as multiple of risk (stop-loss distance). Default: 2.0.
    """

    def __init__(
        self,
        fast_period: int = 9,
        slow_period: int = 21,
        close_on_reverse: bool = False,
        min_strength: float = 0.0,
        use_atr_sl: bool = True,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        risk_reward: float = 2.0,
        initial_capital: float = 10_000.0,
        risk_per_trade: float = 0.02,
        max_positions: int = 1,
    ) -> None:
        super().__init__(
            initial_capital=initial_capital,
            risk_per_trade=risk_per_trade,
            max_positions=max_positions,
        )
        if fast_period >= slow_period:
            raise ValueError(
                f"fast_period ({fast_period}) must be < slow_period ({slow_period})"
            )
        self._fast = fast_period
        self._slow = slow_period
        self._close_on_reverse = close_on_reverse
        self._min_strength = min_strength
        self._use_atr_sl = use_atr_sl
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._risk_reward = risk_reward

        # Columns names for the EMAs
        self._fast_col = f"ema_{fast_period}"
        self._slow_col = f"ema_{slow_period}"
        self._atr_col = f"atr_{atr_period}"

    @property
    def name(self) -> str:
        return f"EMACross_{self._fast}_{self._slow}"

    @property
    def timeframe(self) -> str:
        return "1h"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update(
            {
                "fast_period": self._fast,
                "slow_period": self._slow,
                "close_on_reverse": self._close_on_reverse,
                "min_strength": self._min_strength,
                "use_atr_sl": self._use_atr_sl,
                "atr_period": self._atr_period,
                "atr_multiplier": self._atr_multiplier,
                "risk_reward": self._risk_reward,
            }
        )
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate EMA crossover signals from OHLCV data.

        Args:
            df: OHLCV DataFrame with columns: open, high, low, close, volume

        Returns:
            SignalBundle with side, strength, entry_price, stop_loss, take_profit.
        """
        self.validate_df(df)

        # Compute EMAs
        data = compute_ema(df, period=self._fast)
        data = compute_ema(data, period=self._slow)

        # Compute ATR if using for stop-loss
        if self._use_atr_sl:
            from ACTosha.indicators.volatility import compute_atr

            data = compute_atr(data, period=self._atr_period)

        fast = data[self._fast_col]
        slow = data[self._slow_col]

        # Detect crossovers
        above = fast > slow
        cross_up = above & ~above.shift(1).fillna(False)
        cross_down = (~above) & above.shift(1).fillna(False)

        # Optional: close on reverse
        cross_reverse = cross_up | cross_down

        # Strength: normalized spread (how far apart the EMAs are)
        spread = (fast - slow).abs()
        spread_ma = spread.rolling(20, min_periods=1).mean()
        strength = (spread / spread_ma.replace(0, 1)).clip(0, 1).fillna(0.5)

        # Build sides series
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[cross_up] = "long"
        sides[cross_down] = "short"
        if self._close_on_reverse:
            sides[cross_reverse] = "close"

        # Build signals DataFrame
        signals = pd.DataFrame(
            {"side": sides, "strength": strength}
        )
        signals["entry_price"] = data["close"]
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(signals)

        # Compute SL/TP for crossover bars
        if self._use_atr_sl and self._atr_col in data.columns:
            atr = data[self._atr_col]
        else:
            atr = None

        for idx in data.index:
            bar = data.loc[idx]
            side = signals.loc[idx, "side"]

            if side in ("long", "short") and bar[self._fast_col] is not None:
                entry = bar["close"]
                direction: Literal["long", "short"] = side  # type: ignore[assignment]

                # Stop loss
                if atr is not None and bar[self._atr_col] > 0:
                    sl = self.calc_stop_loss(
                        entry,
                        direction,
                        atr_value=bar[self._atr_col],
                        multiplier=self._atr_multiplier,
                    )
                else:
                    sl = self.calc_stop_loss(entry, direction, atr_value=None)

                # Take profit
                tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=self._risk_reward)

                signals.at[idx, "stop_loss"] = sl
                signals.at[idx, "take_profit"] = tp

        # Filter by min_strength
        if self._min_strength > 0:
            mask = (signals["side"] == "none") | (signals["strength"] >= self._min_strength)
            signals.loc[~mask & signals["side"].isin(["long", "short"]), "side"] = "none"

        # Metadata
        meta = {
            "strategy": self.name,
            "params": self.get_params(),
            "fast_col": self._fast_col,
            "slow_col": self._slow_col,
        }

        return SignalBundle(signals=signals, metadata=meta)


__all__ = ["EMACrossStrategy"]