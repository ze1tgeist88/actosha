"""Trend following strategy: Supertrend breakout."""

from __future__ import annotations

import pandas as pd

from ACTosha.strategies.base import SignalBundle, Strategy


class SupertrendStrategy(Strategy):
    """Supertrend trend-following strategy.

    Goes long when price breaks above the Supertrend line (uptrend),
    goes short on breakdown (downtrend).

    Parameters
    ----------
    period : int
        ATR period. Default: 10.
    multiplier : float
        ATR multiplier for the Supertrend band. Default: 3.0.
    """

    def __init__(self, period: int = 10, multiplier: float = 3.0) -> None:
        self._period = period
        self._multiplier = multiplier

    @property
    def name(self) -> str:
        return "Supertrend"

    def get_params(self) -> dict:
        return {"period": self._period, "multiplier": self._multiplier}

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        raise NotImplementedError(f"{self.name}.generate_signals() not yet implemented")