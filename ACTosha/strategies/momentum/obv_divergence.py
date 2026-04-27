"""Momentum strategy: OBV Divergence."""

from __future__ import annotations

from typing import Literal

import pandas as pd
import numpy as np

from ACTosha.indicators.volume import compute_obv
from ACTosha.indicators.volatility import compute_atr
from ACTosha.strategies.base import BaseStrategy, SignalBundle


class OBVDivergenceStrategy(BaseStrategy):
    """OBV (On-Balance Volume) divergence momentum strategy.

    Signal Logic
    ------------
    Bullish divergence (LONG):
      - Price makes a lower low (new local minimum)
      - OBV makes a higher low (rejecting the lower low)
      → Price is being supported by volume despite weakness

    Bearish divergence (SHORT):
      - Price makes a higher high (new local maximum)
      - OBV makes a lower high (rejecting the higher high)
      → Price rising without volume confirmation (distribution)

    Volume confirmation required: volume > SMA(volume, 20).

    Parameters
    ----------
    obv_ema_period : int
        EMA period to smooth OBV. Default: 21.
    price_lookback : int
        Lookback for price swing detection. Default: 5.
    divergence_lookback : int
        Number of bars to look back for divergence confirmation. Default: 50.
    min_volume_mult : float
        Minimum volume vs 20-bar SMA for confirmation. Default: 1.0.
    require_exact_swing : bool
        Require price to hit exact swing low/high. Default: False (use near).
    swing_tolerance : float
        Tolerance for "near" swing detection (as fraction of range). Default: 0.05.
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
        obv_ema_period: int = 21,
        price_lookback: int = 5,
        divergence_lookback: int = 50,
        min_volume_mult: float = 1.0,
        require_exact_swing: bool = False,
        swing_tolerance: float = 0.05,
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
        self._obv_ema_period = obv_ema_period
        self._price_lookback = price_lookback
        self._divergence_lookback = divergence_lookback
        self._min_volume_mult = min_volume_mult
        self._require_exact_swing = require_exact_swing
        self._swing_tolerance = swing_tolerance
        self._use_atr_sl = use_atr_sl
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._risk_reward = risk_reward

    @property
    def name(self) -> str:
        return f"OBVDiv_O{self._obv_ema_period}_L{self._divergence_lookback}"

    @property
    def timeframe(self) -> str:
        return "1h"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update(
            {
                "obv_ema_period": self._obv_ema_period,
                "price_lookback": self._price_lookback,
                "divergence_lookback": self._divergence_lookback,
                "min_volume_mult": self._min_volume_mult,
                "require_exact_swing": self._require_exact_swing,
                "swing_tolerance": self._swing_tolerance,
                "use_atr_sl": self._use_atr_sl,
                "atr_period": self._atr_period,
                "atr_multiplier": self._atr_multiplier,
                "risk_reward": self._risk_reward,
            }
        )
        return base

    def _detect_swing_extrema(
        self, series: pd.Series, lookback: int
    ) -> pd.DataFrame:
        """Detect local swing highs and lows.

        Returns DataFrame with columns:
          - is_swing_low: bool
          - is_swing_high: bool
        """
        result = pd.DataFrame(index=series.index)
        result["is_swing_low"] = False
        result["is_swing_high"] = False

        for i in range(lookback, len(series) - lookback):
            window = series.iloc[i - lookback : i + lookback + 1]
            val = series.iloc[i]
            if val == window.min():
                result.iloc[i, result.columns.get_loc("is_swing_low")] = True
            if val == window.max():
                result.iloc[i, result.columns.get_loc("is_swing_high")] = True

        return result

    def _find_divergence(
        self,
        price: pd.Series,
        obv: pd.Series,
        idx,
        direction: Literal["long", "short"],
    ) -> bool:
        """Check if there's a divergence at the given index."""
        lookback = self._divergence_lookback
        if idx < lookback:
            return False

        window_price = price.iloc[max(0, idx - lookback) : idx + 1]
        window_obv = obv.iloc[max(0, idx - lookback) : idx + 1]

        if direction == "long":
            # Find last two swing lows in price
            price_swing_mask = window_price[
                (window_price.shift(1) > window_price)
                & (window_price.shift(-1) > window_price)
            ]
            if len(price_swing_mask) < 2:
                return False

            price_vals = price_swing_mask.values
            obv_vals = obv.loc[price_swing_mask.index].values

            # Bullish: price makes lower low, OBV makes higher low
            price_lower = price_vals[-1] < price_vals[-2]
            obv_higher = obv_vals[-1] > obv_vals[-2]

            return price_lower and obv_higher

        else:  # short
            price_swing_mask = window_price[
                (window_price.shift(1) < window_price)
                & (window_price.shift(-1) < window_price)
            ]
            if len(price_swing_mask) < 2:
                return False

            price_vals = price_swing_mask.values
            obv_vals = obv.loc[price_swing_mask.index].values

            # Bearish: price makes higher high, OBV makes lower high
            price_higher = price_vals[-1] > price_vals[-2]
            obv_lower = obv_vals[-1] < obv_vals[-2]

            return price_higher and obv_lower

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate OBV divergence signals from OHLCV data."""
        self.validate_df(df)

        # Compute OBV and smoothed OBV
        data = compute_obv(df)
        data[f"obv_ema"] = data["obv"].ewm(
            span=self._obv_ema_period, adjust=False, min_periods=self._obv_ema_period
        ).mean()

        if self._use_atr_sl:
            data = compute_atr(data, period=self._atr_period)

        close = data["close"]
        obv = data[f"obv_ema"]
        volume = data["volume"]

        # Volume confirmation
        vol_sma = volume.rolling(20, min_periods=1).mean()
        vol_confirm = volume >= vol_sma * self._min_volume_mult

        # Detect swing extrema
        swings = self._detect_swing_extrema(close, self._price_lookback)
        data = pd.concat([data, swings], axis=1)

        # Find divergences at each swing point
        long_div = pd.Series(False, index=data.index)
        short_div = pd.Series(False, index=data.index)

        for i in range(self._divergence_lookback, len(data)):
            if swings.iloc[i]["is_swing_low"]:
                long_div.iloc[i] = self._find_divergence(
                    close, obv, i, "long"
                )
            if swings.iloc[i]["is_swing_high"]:
                short_div.iloc[i] = self._find_divergence(
                    close, obv, i, "short"
                )

        # Require volume confirmation at divergence bar
        long_cond = long_div & vol_confirm
        short_cond = short_div & vol_confirm

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_cond] = "long"
        sides[short_cond] = "short"

        # Strength: based on OBV slope and volume ratio
        obv_slope = obv.diff(10) / close.diff(10).replace(0, np.nan)
        obv_slope_norm = (obv_slope / obv_slope.abs().rolling(50, min_periods=10).mean().replace(0, np.nan)).clip(-1, 1).fillna(0)
        vol_score = (volume / vol_sma.replace(0, 1)).clip(0, 2).fillna(1.0) / 2.0
        strength = ((obv_slope_norm.abs() * 0.5 + vol_score * 0.5)).clip(0, 1).fillna(0.5)

        signals = pd.DataFrame({"side": sides, "strength": strength})
        signals["entry_price"] = close
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(signals)

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
                "obv_slope": round(float(obv_slope.loc[idx]) if not pd.isna(obv_slope.loc[idx]) else 0.0, 6),
                "volume_ratio": round(float(volume.loc[idx] / vol_sma.loc[idx]), 4)
                if vol_sma.loc[idx] > 0 else 1.0,
                "divergence_type": "bullish" if side == "long" else "bearish",
            }

        meta = {"strategy": self.name, "params": self.get_params()}
        return SignalBundle(signals=signals, metadata=meta)


__all__ = ["OBVDivergenceStrategy"]
