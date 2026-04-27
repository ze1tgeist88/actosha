"""Trend strategy: Bollinger Bands + EMA combo.

Trend defined by EMA direction; entry on BB bounce in direction of trend.
- EMA above price  = long bias (don't short)
- EMA below price  = short bias (don't long)
- Entry: price touches/rebounds from BB outer band in trend direction
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

from ACTosha.indicators.moving_averages import compute_ema
from ACTosha.indicators.volatility import compute_bollinger_bands, compute_atr
from ACTosha.strategies.base import BaseStrategy, SignalBundle


class BBEMAComboStrategy(BaseStrategy):
    """BB + EMA combo trend-following strategy.

    Logic
    -----
    1. EMA(21) defines trend direction:
       - price > EMA  → long bias
       - price < EMA  → short bias
    2. Entry zone: price at/near BB outer band (upper for longs, lower for shorts)
    3. Signal triggers when:
       - Trend matches direction AND
       - Price is at BB extreme (bb_percent near 1.0 or 0.0) AND
       - Price shows rejection (wick or close reversal)

    Parameters
    ----------
    ema_period : int
        EMA period for trend detection. Default: 21.
    bb_period : int
        Bollinger Bands period. Default: 20.
    bb_std : float
        Bollinger Bands standard deviations. Default: 2.0.
    bb_extreme_threshold : float
        bb_percent value considered extreme (0.0–1.0). Default: 0.90.
    min_volume : float
        Minimum average volume multiplier for signal confirmation. Default: 1.0.
    use_atr_sl : bool
        Use ATR-based stop-loss. Default: True.
    atr_period : int
        ATR period. Default: 14.
    atr_multiplier : float
        ATR multiplier for stop-loss. Default: 2.0.
    risk_reward : float
        Risk:reward ratio for take-profit. Default: 2.0.
    """

    def __init__(
        self,
        ema_period: int = 21,
        bb_period: int = 20,
        bb_std: float = 2.0,
        bb_extreme_threshold: float = 0.90,
        min_volume_mult: float = 1.0,
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
        self._ema_period = ema_period
        self._bb_period = bb_period
        self._bb_std = bb_std
        self._bb_extreme_threshold = bb_extreme_threshold
        self._min_volume_mult = min_volume_mult
        self._use_atr_sl = use_atr_sl
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._risk_reward = risk_reward

    @property
    def name(self) -> str:
        return f"BBEMACombo_E{self._ema_period}_BB{self._bb_period}"

    @property
    def timeframe(self) -> str:
        return "1h"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update(
            {
                "ema_period": self._ema_period,
                "bb_period": self._bb_period,
                "bb_std": self._bb_std,
                "bb_extreme_threshold": self._bb_extreme_threshold,
                "min_volume_mult": self._min_volume_mult,
                "use_atr_sl": self._use_atr_sl,
                "atr_period": self._atr_period,
                "atr_multiplier": self._atr_multiplier,
                "risk_reward": self._risk_reward,
            }
        )
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate BB+EMA combo signals from OHLCV data."""
        self.validate_df(df)

        # Compute indicators
        data = compute_ema(df, period=self._ema_period)
        data = compute_bollinger_bands(
            data, period=self._bb_period, std_dev=self._bb_std
        )
        if self._use_atr_sl:
            data = compute_atr(data, period=self._atr_period)

        ema_col = f"ema_{self._ema_period}"
        bb_upper = "bb_upper"
        bb_lower = "bb_lower"
        bb_pct = "bb_percent"

        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]

        # Trend: price above EMA = long bias, below = short bias
        trend_bull = close > data[ema_col]
        trend_bear = close < data[ema_col]

        # Volume confirmation: current volume > SMA(volume, 20)
        vol_sma = volume.rolling(20, min_periods=1).mean()
        vol_confirm = volume >= vol_sma * self._min_volume_mult

        # BB extreme: price near outer bands
        # Long entry: bb_percent > threshold (near upper band)
        # Short entry: bb_percent < (1 - threshold) (near lower band)
        bb_extreme_long = data[bb_pct] > self._bb_extreme_threshold
        bb_extreme_short = data[bb_pct] < (1.0 - self._bb_extreme_threshold)

        # Rejection candle: close reverses from BB touch
        # Long: price touched lower band and closed higher (wick rejected)
        # Short: price touched upper band and closed lower
        prev_close = close.shift(1)
        lower_touch = prev_close <= data[bb_lower].shift(1)
        upper_touch = prev_close >= data[bb_upper].shift(1)

        long_rejection = lower_touch & (close > prev_close)
        short_rejection = upper_touch & (close < prev_close)

        # Signal conditions
        long_cond = trend_bull & bb_extreme_long & long_rejection & vol_confirm
        short_cond = trend_bear & bb_extreme_short & short_rejection & vol_confirm

        # Build sides
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_cond] = "long"
        sides[short_cond] = "short"

        # Strength based on BB extreme level + volume
        bb_extreme_score = data[bb_pct].where(trend_bull, 1.0 - data[bb_pct]).fillna(0.5)
        vol_score = (volume / vol_sma.replace(0, 1)).clip(0, 2).fillna(1.0) / 2.0
        strength = (bb_extreme_score * 0.6 + vol_score * 0.4).clip(0, 1).fillna(0.5)

        signals = pd.DataFrame(
            {"side": sides, "strength": strength}
        )
        signals["entry_price"] = close
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(signals)

        # SL/TP per signal bar
        atr_col = f"atr_{self._atr_period}"
        has_atr = self._use_atr_sl and atr_col in data.columns

        for idx in data.index:
            side = signals.at[idx, "side"]
            if side not in ("long", "short"):
                continue

            entry = float(close.loc[idx])
            direction: Literal["long", "short"] = side  # type: ignore[assignment]

            if has_atr and float(data[atr_col].loc[idx]) > 0:
                sl = self.calc_stop_loss(
                    entry,
                    direction,
                    atr_value=float(data[atr_col].loc[idx]),
                    multiplier=self._atr_multiplier,
                )
            else:
                sl = self.calc_stop_loss(entry, direction, atr_value=None)

            tp = self.calc_take_profit(
                entry, direction, stop_loss=sl, risk_reward=self._risk_reward
            )

            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp
            signals.at[idx, "metadata"] = {
                "ema_trend": "bull" if trend_bull.loc[idx] else "bear",
                "bb_percent": round(float(data[bb_pct].loc[idx]), 4),
                "volume_ratio": round(float(volume.loc[idx] / vol_sma.loc[idx]), 4)
                if vol_sma.loc[idx] > 0 else 1.0,
            }

        meta = {
            "strategy": self.name,
            "params": self.get_params(),
        }
        return SignalBundle(signals=signals, metadata=meta)


__all__ = ["BBEMAComboStrategy"]
