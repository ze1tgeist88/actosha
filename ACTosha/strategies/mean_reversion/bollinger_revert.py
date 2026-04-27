"""Mean reversion strategy: Bollinger Bands reversion."""

from __future__ import annotations

import pandas as pd

from ACTosha.indicators.volatility import compute_bollinger_bands
from ACTosha.strategies.base import BaseStrategy, SignalBundle


class BollingerRevertStrategy(BaseStrategy):
    """Bollinger Bands mean reversion strategy.

    Goes long when price touches the lower Bollinger Band (oversold),
    goes short when price touches the upper Bollinger Band (overbought).
    Exits when price reverts to the middle band or crosses the opposite band.

    Parameters
    ----------
    bb_period : int
        Period for Bollinger Bands SMA. Default: 20.
    bb_std : float
        Number of standard deviations for bands. Default: 2.0.
    exit_at_middle : bool
        If True, exit when price crosses the middle band. Default: True.
    min_reversion_pct : float
        Minimum % distance from middle band to trigger signal. Default: 0.0.
    use_atr_sl : bool
        Use ATR-based stop-loss. Default: True.
    atr_multiplier : float
        ATR multiplier for stop-loss. Default: 2.0.
    risk_reward : float
        Take-profit risk:reward ratio. Default: 2.0.
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        exit_at_middle: bool = True,
        min_reversion_pct: float = 0.0,
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
        self._bb_period = bb_period
        self._bb_std = bb_std
        self._exit_at_middle = exit_at_middle
        self._min_reversion_pct = min_reversion_pct
        self._use_atr_sl = use_atr_sl
        self._atr_multiplier = atr_multiplier
        self._risk_reward = risk_reward

    @property
    def name(self) -> str:
        return f"BollingerRevert_{self._bb_period}_{self._bb_std}"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update(
            {
                "bb_period": self._bb_period,
                "bb_std": self._bb_std,
                "exit_at_middle": self._exit_at_middle,
                "min_reversion_pct": self._min_reversion_pct,
                "use_atr_sl": self._use_atr_sl,
                "atr_multiplier": self._atr_multiplier,
                "risk_reward": self._risk_reward,
            }
        )
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate Bollinger Bands mean reversion signals."""
        self.validate_df(df)

        data = compute_bollinger_bands(df, period=self._bb_period, std_dev=self._bb_std)

        close = data["close"]
        bb_mid = data["bb_middle"]
        bb_upper = data["bb_upper"]
        bb_lower = data["bb_lower"]
        bb_width = data["bb_width"]

        # Distance from middle band as % of middle
        upper_dist = (bb_upper - bb_mid) / bb_mid.replace(0, 1)
        lower_dist = (bb_mid - bb_lower) / bb_mid.replace(0, 1)

        # Signal conditions
        at_upper = close >= bb_upper
        at_lower = close <= bb_lower
        at_middle_long = close <= bb_mid  # for long exit
        at_middle_short = close >= bb_mid  # for short exit

        # Reversion signal direction
        near_lower = (bb_lower - close) / bb_lower.replace(0, 1) < 0.01  # within 1% of lower
        near_upper = (close - bb_upper) / bb_upper.replace(0, 1) < 0.01  # within 1% of upper

        long_signal = near_lower | at_lower
        short_signal = near_upper | at_upper

        # Close signals
        close_long = at_middle_long if self._exit_at_middle else pd.Series(False, index=data.index)
        close_short = at_middle_short if self._exit_at_middle else pd.Series(False, index=data.index)

        # Strength: how extreme is the deviation from middle
        mid_distance = ((close - bb_mid).abs() / bb_mid.replace(0, 1)).clip(0, 1)
        strength = mid_distance.rolling(5, min_periods=1).mean().fillna(0.5)

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_signal] = "long"
        sides[short_signal] = "short"
        sides[close_long & (sides == "long")] = "close"
        sides[close_short & (sides == "short")] = "close"

        # Filter by min_reversion_pct
        if self._min_reversion_pct > 0:
            min_dist = self._min_reversion_pct / 100
            is_significant = mid_distance >= min_dist
            sides[is_significant & (sides == "long")] = "none"
            sides[is_significant & (sides == "short")] = "none"

        signals = pd.DataFrame({"side": sides, "strength": strength})
        signals["entry_price"] = close
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(signals)

        # Compute SL/TP for active signal bars
        from ACTosha.indicators.volatility import compute_atr
        if self._use_atr_sl:
            data = compute_atr(data, period=14)
            atr = data["atr_14"]
        else:
            atr = None

        for idx in data.index:
            bar = data.loc[idx]
            side = signals.loc[idx, "side"]
            if side not in ("long", "short"):
                continue

            entry = bar["close"]
            direction = side  # type: ignore[assignment]

            if atr is not None and bar["atr_14"] > 0:
                sl = self.calc_stop_loss(entry, direction, atr_value=bar["atr_14"],
                                          multiplier=self._atr_multiplier)
            else:
                sl = self.calc_stop_loss(entry, direction, atr_value=None)

            tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=self._risk_reward)

            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp

        meta = {
            "strategy": self.name,
            "params": self.get_params(),
            "bb_period": self._bb_period,
            "bb_std": self._bb_std,
        }

        return SignalBundle(signals=signals, metadata=meta)


__all__ = ["BollingerRevertStrategy"]