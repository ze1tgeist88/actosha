"""Breakout strategy: N-period range breakout."""

from __future__ import annotations

import pandas as pd

from ACTosha.strategies.base import BaseStrategy, SignalBundle


class RangeBreakoutStrategy(BaseStrategy):
    """N-period range breakout strategy.

    Goes long when price breaks above the highest high of the last N bars,
    goes short when price breaks below the lowest low of the last N bars.
    Exits on opposite breakout or on trailing stop.

    Parameters
    ----------
    lookback : int
        Number of bars to define the range (highest high / lowest low).
        Default: 20.
    confirmation_bars : int
        Number of consecutive bars price must hold above/below the range.
        Default: 1.
    breakout_threshold_pct : float
        Price must exceed range by this % to confirm breakout.
        Default: 0.0 (any break counts).
    trail_by : float
        Trail stop distance as % below/above breakout price.
        Default: 0.5 (0.5%).
    use_atr_sl : bool
        Use ATR-based stop-loss. Default: True.
    atr_multiplier : float
        ATR multiplier for stop-loss. Default: 2.0.
    risk_reward : float
        Take-profit risk:reward ratio. Default: 2.0.
    """

    def __init__(
        self,
        lookback: int = 20,
        confirmation_bars: int = 1,
        breakout_threshold_pct: float = 0.0,
        trail_by: float = 0.5,
        use_atr_sl: bool = True,
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
        if lookback < confirmation_bars:
            raise ValueError(f"lookback ({lookback}) must be >= confirmation_bars ({confirmation_bars})")
        self._lookback = lookback
        self._conf_bars = confirmation_bars
        self._threshold_pct = breakout_threshold_pct / 100  # convert to fraction
        self._trail_pct = trail_by / 100
        self._use_atr_sl = use_atr_sl
        self._atr_multiplier = atr_multiplier
        self._risk_reward = risk_reward

    @property
    def name(self) -> str:
        return f"RangeBreakout_{self._lookback}_{self._conf_bars}"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update(
            {
                "lookback": self._lookback,
                "confirmation_bars": self._conf_bars,
                "breakout_threshold_pct": self._threshold_pct * 100,
                "trail_by_pct": self._trail_pct * 100,
                "use_atr_sl": self._use_atr_sl,
                "atr_multiplier": self._atr_multiplier,
                "risk_reward": self._risk_reward,
            }
        )
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate range breakout signals."""
        self.validate_df(df)

        data = df.copy()

        # Compute rolling range
        highest_high = data["high"].rolling(window=self._lookback, min_periods=self._lookback).max()
        lowest_low = data["low"].rolling(window=self._lookback, min_periods=self._lookback).min()
        data["hh"] = highest_high
        data["ll"] = lowest_low

        # Breakout detection
        close = data["close"]
        break_up = close > highest_high.shift(1)
        break_down = close < lowest_low.shift(1)

        # Optional threshold filter
        if self._threshold_pct > 0:
            range_size = highest_high - lowest_low
            threshold = range_size * self._threshold_pct
            break_up = break_up & (close - highest_high.shift(1) >= threshold)
            break_down = break_down & (lowest_low.shift(1) - close >= threshold)

        # Require consecutive confirmation bars
        break_up_confirmed = break_up.rolling(self._conf_bars, min_periods=self._conf_bars).min()
        break_down_confirmed = break_down.rolling(self._conf_bars, min_periods=self._conf_bars).min()

        break_up_confirmed = break_up_confirmed.astype(bool)
        break_down_confirmed = break_down_confirmed.astype(bool)

        # Opposite breakout closes positions
        opposite_break = break_up_confirmed | break_down_confirmed

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[break_up_confirmed & ~break_down_confirmed] = "long"
        sides[break_down_confirmed & ~break_up_confirmed] = "short"
        # Close on simultaneous breakouts (both directions at once = uncertainty)
        sides[break_up_confirmed & break_down_confirmed] = "close"

        # Strength: size of the breakout relative to the range
        range_width = (highest_high - lowest_low).replace(0, 1)
        breakout_size = (
            (close - lowest_low).where(break_up_confirmed, 0)
            + (highest_high - close).where(break_down_confirmed, 0)
        )
        strength = (breakout_size / range_width).clip(0, 1).fillna(0.5)

        signals = pd.DataFrame({"side": sides, "strength": strength})
        signals["entry_price"] = close
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(signals)

        # SL/TP
        if self._use_atr_sl:
            from ACTosha.indicators.volatility import compute_atr
            data = compute_atr(data, period=14)
            has_atr = True
        else:
            has_atr = False

        for idx in data.index:
            side = signals.loc[idx, "side"]
            if side not in ("long", "short"):
                continue

            entry = data.loc[idx, "close"]
            direction = side  # type: ignore[assignment]

            if has_atr:
                atr_val = data.loc[idx, "atr_14"]
                if atr_val > 0:
                    sl = self.calc_stop_loss(entry, direction, atr_value=atr_val,
                                              multiplier=self._atr_multiplier)
                else:
                    sl = self.calc_stop_loss(entry, direction, atr_value=None)
            else:
                sl = self.calc_stop_loss(entry, direction, atr_value=None)

            tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=self._risk_reward)
            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp

        meta = {
            "strategy": self.name,
            "params": self.get_params(),
            "lookback": self._lookback,
            "confirmation_bars": self._conf_bars,
        }

        return SignalBundle(signals=signals, metadata=meta)


__all__ = ["RangeBreakoutStrategy"]