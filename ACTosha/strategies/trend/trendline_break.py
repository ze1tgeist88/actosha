"""Trend following strategy: Trendline break + retest."""

from __future__ import annotations

import pandas as pd

from ACTosha.strategies.base import SignalBundle, Strategy


class TrendlineBreakStrategy(Strategy):
    """Trendline break and retest strategy.

    Identifies diagonal support/resistance trendlines, waits for a break,
    then enters on a retest of the broken trendline.

    Parameters
    ----------
    lookback : int
        Number of bars to use for trendline construction. Default: 50.
    retest_tolerance : float
        Tolerance (fraction of price) for considering a retest valid.
        Default: 0.005.
    """

    def __init__(self, lookback: int = 50, retest_tolerance: float = 0.005) -> None:
        self._lookback = lookback
        self._retest_tolerance = retest_tolerance

    @property
    def name(self) -> str:
        return "TrendlineBreak"

    def get_params(self) -> dict:
        return {"lookback": self._lookback, "retest_tolerance": self._retest_tolerance}

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        raise NotImplementedError(f"{self.name}.generate_signals() not yet implemented")