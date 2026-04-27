"""Trend strategy: Ichimoku Cloud."""

from __future__ import annotations

from typing import Literal

import pandas as pd
import numpy as np

from ACTosha.indicators.volatility import compute_atr
from ACTosha.strategies.base import BaseStrategy, SignalBundle


class IchimokuStrategy(BaseStrategy):
    """Ichimoku Cloud trend-following strategy.

    Components
    ----------
    Tenkan-sen (Conversion Line) : (9-period HH + 9-period LL) / 2
    Kijun-sen (Base Line)        : (26-period HH + 26-period LL) / 2
    Senkou Span A (Lead 1)       : (Tenkan + Kijun) / 2, plotted 26 ahead
    Senkou Span B (Lead 2)       : (52-period HH + 52-period LL) / 2, plotted 26 ahead
    Chikou Span (Lagging Span)  : close, plotted 26 behind

    Signal Logic
    ------------
    Long:
      - Tenkan crosses above Kijun (bullish TK cross)
      - Price is above the Cloud (above both Lead A and Lead B)
      - Cloud is green (Lead A > Lead B) → bullish cloud
      - Chikou confirms: Chikou is above price from the past (price > lagged price)
    Short:
      - Tenkan crosses below Kijun (bearish TK cross)
      - Price is below the Cloud
      - Cloud is red (Lead A < Lead B)
      - Chikou confirms: Chikou is below price from the past

    Parameters
    ----------
    tenkan_period : int
        Tenkan-sen lookback period. Default: 9.
    kijun_period : int
        Kijun-sen lookback period. Default: 26.
    senkou_b_period : int
        Senkou Span B lookback period. Default: 52.
    cloud_shift : int
        Forward shift for cloud spans. Default: 26.
    chikou_confirm : bool
        Require Chikou span confirmation. Default: True.
    cloud_thickness_filter : bool
        Reject signals when cloud is very thick (high volatility). Default: False.
    max_cloud_width : float
        Max cloud width (Lead B - Lead A) / price * 100. Default: 5.0.
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
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        cloud_shift: int = 26,
        chikou_confirm: bool = True,
        cloud_thickness_filter: bool = False,
        max_cloud_width: float = 5.0,
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
        self._tenkan_period = tenkan_period
        self._kijun_period = kijun_period
        self._senkou_b_period = senkou_b_period
        self._cloud_shift = cloud_shift
        self._chikou_confirm = chikou_confirm
        self._cloud_thickness_filter = cloud_thickness_filter
        self._max_cloud_width = max_cloud_width
        self._use_atr_sl = use_atr_sl
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._risk_reward = risk_reward

    @property
    def name(self) -> str:
        return (
            f"Ichimoku_T{self._tenkan_period}_K{self._kijun_period}"
            f"_S{self._senkou_b_period}"
        )

    @property
    def timeframe(self) -> str:
        return "1h"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update(
            {
                "tenkan_period": self._tenkan_period,
                "kijun_period": self._kijun_period,
                "senkou_b_period": self._senkou_b_period,
                "cloud_shift": self._cloud_shift,
                "chikou_confirm": self._chikou_confirm,
                "cloud_thickness_filter": self._cloud_thickness_filter,
                "max_cloud_width": self._max_cloud_width,
                "use_atr_sl": self._use_atr_sl,
                "atr_period": self._atr_period,
                "atr_multiplier": self._atr_multiplier,
                "risk_reward": self._risk_reward,
            }
        )
        return base

    def _compute_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all Ichimoku components."""
        result = df.copy()

        # Tenkan-sen
        tenkan_hh = df["high"].rolling(self._tenkan_period, min_periods=self._tenkan_period).max()
        tenkan_ll = df["low"].rolling(self._tenkan_period, min_periods=self._tenkan_period).min()
        result["tenkan"] = (tenkan_hh + tenkan_ll) / 2

        # Kijun-sen
        kijun_hh = df["high"].rolling(self._kijun_period, min_periods=self._kijun_period).max()
        kijun_ll = df["low"].rolling(self._kijun_period, min_periods=self._kijun_period).min()
        result["kijun"] = (kijun_hh + kijun_ll) / 2

        # Senkou Span A (Lead 1) — shifted forward
        lead_a = (result["tenkan"] + result["kijun"]) / 2
        result["lead_a"] = lead_a.shift(self._cloud_shift)

        # Senkou Span B (Lead 2) — shifted forward
        senkou_b_hh = df["high"].rolling(self._senkou_b_period, min_periods=self._senkou_b_period).max()
        senkou_b_ll = df["low"].rolling(self._senkou_b_period, min_periods=self._senkou_b_period).min()
        lead_b = (senkou_b_hh + senkou_b_ll) / 2
        result["lead_b"] = lead_b.shift(self._cloud_shift)

        # Chikou Span — current close, plotted 26 behind
        result["chikou"] = df["close"].shift(-self._cloud_shift)

        # Cloud: top = max(lead_a, lead_b), bottom = min(lead_a, lead_b)
        result["cloud_top"] = result[["lead_a", "lead_b"]].max(axis=1)
        result["cloud_bottom"] = result[["lead_a", "lead_b"]].min(axis=1)

        # Cloud color: green when lead_a > lead_b
        result["cloud_bull"] = result["lead_a"] > result["lead_b"]

        # Cloud width as % of price
        cloud_range = result["cloud_top"] - result["cloud_bottom"]
        result["cloud_width_pct"] = (cloud_range / df["close"].replace(0, np.nan)) * 100

        return result

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate Ichimoku cloud signals from OHLCV data."""
        self.validate_df(df)

        data = self._compute_ichimoku(df)
        if self._use_atr_sl:
            from ACTosha.indicators.volatility import compute_atr

            data = compute_atr(data, period=self._atr_period)

        tenkan = data["tenkan"]
        kijun = data["kijun"]
        close = data["close"]
        high = data["high"]
        low = data["low"]

        # TK cross detection
        tk_above = tenkan > kijun
        tk_cross_up = tk_above & ~tk_above.shift(1).fillna(False)
        tk_cross_down = (~tk_above) & tk_above.shift(1).fillna(False)

        # Price vs cloud
        cloud_top = data["cloud_top"]
        cloud_bottom = data["cloud_bottom"]
        price_above_cloud = close > cloud_top
        price_below_cloud = close < cloud_bottom

        # Cloud bullish (green)
        cloud_bull = data["cloud_bull"]
        cloud_bear = ~cloud_bull

        # Chikou confirmation: Chikou above lagged price (for current bar look back)
        # Chikou = close shifted -26; so at bar t, chikou represents bar t-26 price
        # Confirm: current close > close 26 bars ago (bullish)
        lagged_close = close.shift(self._cloud_shift)
        chikou_bull_confirm = data["chikou"] > lagged_close
        chikou_bear_confirm = data["chikou"] < lagged_close

        # Cloud thickness filter
        if self._cloud_thickness_filter:
            thick_cloud = data["cloud_width_pct"] > self._max_cloud_width
        else:
            thick_cloud = pd.Series(False, index=data.index)

        # Volume confirmation (20-period SMA)
        vol_sma = data["volume"].rolling(20, min_periods=1).mean()
        vol_confirm = data["volume"] >= vol_sma

        # Long signal
        long_cond = (
            tk_cross_up
            & price_above_cloud
            & cloud_bull
            & (~thick_cloud)
            & (
                not self._chikou_confirm
                or chikou_bull_confirm
            )
        )

        # Short signal
        short_cond = (
            tk_cross_down
            & price_below_cloud
            & cloud_bear
            & (~thick_cloud)
            & (
                not self._chikou_confirm
                or chikou_bear_confirm
            )
        )

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_cond] = "long"
        sides[short_cond] = "short"

        # Strength based on cloud width (thinner = stronger trend)
        cloud_width_inv = 1.0 - (data["cloud_width_pct"].fillna(0) / self._max_cloud_width).clip(0, 1)
        vol_score = (data["volume"] / vol_sma.replace(0, 1)).clip(0, 2).fillna(1.0) / 2.0
        strength = (cloud_width_inv * 0.5 + vol_score * 0.5).clip(0, 1).fillna(0.5)

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
                "tk_cross": "up" if tk_cross_up.loc[idx] else "down",
                "cloud_bull": bool(cloud_bull.loc[idx]),
                "cloud_width_pct": round(float(data["cloud_width_pct"].loc[idx]), 4),
            }

        meta = {"strategy": self.name, "params": self.get_params()}
        return SignalBundle(signals=signals, metadata=meta)


__all__ = ["IchimokuStrategy"]
