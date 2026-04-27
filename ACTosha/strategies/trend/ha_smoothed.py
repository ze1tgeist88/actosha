"""Trend strategy: Heikin Ashi Smoothed."""

from __future__ import annotations

from typing import Literal

import pandas as pd
import numpy as np

from ACTosha.indicators.moving_averages import compute_ema
from ACTosha.indicators.volatility import compute_atr
from ACTosha.strategies.base import BaseStrategy, SignalBundle


class HASmoothedStrategy(BaseStrategy):
    """Heikin Ashi Smoothed trend-following strategy.

    Heikin Ashi (HA) candles smooth price noise by averaging OHLC data:
      HA_Close = (open + high + low + close) / 4
      HA_Open  = (prev_HA_open + prev_HA_close) / 2
      HA_High  = max(high, HA_Open, HA_Close)
      HA_Low   = min(low, HA_Open, HA_Close)

    Then apply EMA smoothing to HA values for smoother trend detection.

    Signal Logic
    ------------
    Trend: 7+ consecutive same-color HA candles → directional bias
    Entry: HA candle color change (from red to green or vice versa)
           with volume confirmation
    Exit / SL: Trailing stop based on HA low (for longs) / HA high (for shorts)

    Parameters
    ----------
    ha_smooth_ema : int
        EMA period to smooth HA values. Default: 5.
    consecutive_bars : int
        Number of consecutive HA candles for trend confirmation. Default: 7.
    volume_ma_period : int
        Period for volume moving average. Default: 20.
    min_volume_mult : float
        Minimum volume vs volume MA for signal confirmation. Default: 1.0.
    trailing_mode : bool
        Use HA-based trailing stop. Default: True.
    use_atr_sl : bool
        Use ATR-based stop-loss as fallback. Default: True.
    atr_period : int
        ATR period. Default: 14.
    atr_multiplier : float
        ATR multiplier for stop-loss. Default: 2.0.
    risk_reward : float
        Risk:reward ratio for take-profit. Default: 2.0.
    """

    def __init__(
        self,
        ha_smooth_ema: int = 5,
        consecutive_bars: int = 7,
        volume_ma_period: int = 20,
        min_volume_mult: float = 1.0,
        trailing_mode: bool = True,
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
        self._ha_smooth_ema = ha_smooth_ema
        self._consecutive_bars = consecutive_bars
        self._volume_ma_period = volume_ma_period
        self._min_volume_mult = min_volume_mult
        self._trailing_mode = trailing_mode
        self._use_atr_sl = use_atr_sl
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._risk_reward = risk_reward

    @property
    def name(self) -> str:
        return (
            f"HASmoothed_E{self._ha_smooth_ema}_C{self._consecutive_bars}"
        )

    @property
    def timeframe(self) -> str:
        return "1h"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update(
            {
                "ha_smooth_ema": self._ha_smooth_ema,
                "consecutive_bars": self._consecutive_bars,
                "volume_ma_period": self._volume_ma_period,
                "min_volume_mult": self._min_volume_mult,
                "trailing_mode": self._trailing_mode,
                "use_atr_sl": self._use_atr_sl,
                "atr_period": self._atr_period,
                "atr_multiplier": self._atr_multiplier,
                "risk_reward": self._risk_reward,
            }
        )
        return base

    def _compute_heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute Heikin Ashi candles."""
        result = df.copy()

        ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

        ha_open = pd.Series(np.nan, index=df.index, dtype=float)
        ha_open.iloc[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2

        ha_high = pd.Series(np.nan, index=df.index, dtype=float)
        ha_low = pd.Series(np.nan, index=df.index, dtype=float)

        for i in range(1, len(df)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2
            ha_high.iloc[i] = max(
                df["high"].iloc[i], ha_open.iloc[i], ha_close.iloc[i]
            )
            ha_low.iloc[i] = min(
                df["low"].iloc[i], ha_open.iloc[i], ha_close.iloc[i]
            )

        result["ha_close"] = ha_close
        result["ha_open"] = ha_open
        result["ha_high"] = ha_high
        result["ha_low"] = ha_low

        # HA color: bullish if ha_close > ha_open
        result["ha_bull"] = ha_close > ha_open

        # Smoothed HA
        result["ha_close_smooth"] = compute_ema(
            result, period=self._ha_smooth_ema, col="ha_close"
        )[f"ema_{self._ha_smooth_ema}"]
        result["ha_open_smooth"] = compute_ema(
            result, period=self._ha_smooth_ema, col="ha_open"
        )[f"ema_{self._ha_smooth_ema}"]
        result["ha_high_smooth"] = compute_ema(
            result, period=self._ha_smooth_ema, col="ha_high"
        )[f"ema_{self._ha_smooth_ema}"]
        result["ha_low_smooth"] = compute_ema(
            result, period=self._ha_smooth_ema, col="ha_low"
        )[f"ema_{self._ha_smooth_ema}"]

        # Smoothed HA color
        result["ha_bull_smooth"] = result["ha_close_smooth"] > result["ha_open_smooth"]

        # Count consecutive same-color bars
        consecutive = 0
        consecutive_arr = []
        for i in range(len(result)):
            if i == 0:
                consecutive = 1
            else:
                if result["ha_bull_smooth"].iloc[i] == result["ha_bull_smooth"].iloc[i - 1]:
                    consecutive += 1
                else:
                    consecutive = 1
            consecutive_arr.append(consecutive)
        result["ha_consecutive"] = consecutive_arr

        return result

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate Heikin Ashi Smoothed signals from OHLCV data."""
        self.validate_df(df)

        data = self._compute_heikin_ashi(df)
        if self._use_atr_sl:
            data = compute_atr(data, period=self._atr_period)

        ha_bull = data["ha_bull_smooth"]
        ha_consecutive = data["ha_consecutive"]
        ha_close = data["ha_close"]
        ha_low = data["ha_low_smooth"]
        ha_high = data["ha_high_smooth"]
        close = data["close"]
        volume = data["volume"]

        # Volume confirmation
        vol_sma = volume.rolling(self._volume_ma_period, min_periods=1).mean()
        vol_confirm = volume >= vol_sma * self._min_volume_mult

        # Trend: N consecutive same-color bars
        in_bull_trend = ha_consecutive >= self._consecutive_bars
        bull_trend = ha_bull & in_bull_trend
        bear_trend = (~ha_bull) & in_bull_trend

        # Entry signals on color change, with volume confirmation
        # prev_bear: previous bar was bearish, current bar is bullish (color flip up)
        # prev_bull: previous bar was bullish, current bar is bearish (color flip down)
        prev_bear = (~data["ha_bull_smooth"].shift(1).fillna(False)) & data["ha_bull_smooth"]
        prev_bull = data["ha_bull_smooth"].shift(1).fillna(False) & (~data["ha_bull_smooth"])

        # Entry at color change with volume confirmation
        long_cond = prev_bear & vol_confirm
        short_cond = prev_bull & vol_confirm

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_cond] = "long"
        sides[short_cond] = "short"

        # Strength based on consecutive count (more = stronger)
        strength = (
            (ha_consecutive / self._consecutive_bars).clip(0, 1) * 0.5
            + (volume / vol_sma.replace(0, 1)).clip(0, 2).fillna(1.0) * 0.5
        ).clip(0, 1).fillna(0.5)

        signals = pd.DataFrame({"side": sides, "strength": strength})
        signals["entry_price"] = ha_close
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(signals)

        atr_col = f"atr_{self._atr_period}"
        has_atr = self._use_atr_sl and atr_col in data.columns

        for idx in data.index:
            side = signals.at[idx, "side"]
            if side not in ("long", "short"):
                continue

            entry = float(ha_close.loc[idx])
            direction: Literal["long", "short"] = side  # type: ignore[assignment]

            # Trailing stop: HA low (for long) or HA high (for short)
            if self._trailing_mode:
                if direction == "long":
                    trailing_sl = float(ha_low.loc[idx])
                else:
                    trailing_sl = float(ha_high.loc[idx])
                # Combine with ATR: tighter of the two
                if has_atr and float(data[atr_col].loc[idx]) > 0:
                    atr_sl = self.calc_stop_loss(
                        entry,
                        direction,
                        atr_value=float(data[atr_col].loc[idx]),
                        multiplier=self._atr_multiplier,
                    )
                    sl = max(trailing_sl, atr_sl) if direction == "long" else min(trailing_sl, atr_sl)
                else:
                    sl = trailing_sl
            else:
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
                "ha_trend": "bull" if ha_bull.loc[idx] else "bear",
                "ha_consecutive": int(ha_consecutive.loc[idx]),
                "volume_ratio": round(float(volume.loc[idx] / vol_sma.loc[idx]), 4)
                if vol_sma.loc[idx] > 0 else 1.0,
                "trailing_sl_used": self._trailing_mode,
            }

        meta = {"strategy": self.name, "params": self.get_params()}
        return SignalBundle(signals=signals, metadata=meta)


__all__ = ["HASmoothedStrategy"]
