"""Breakout strategy: Volume + price confirmation breakout."""

from __future__ import annotations

import pandas as pd

from ACTosha.strategies.base import SignalBundle, Strategy


class VolumeSurgeStrategy(Strategy):
    """Volume surge breakout strategy.

    Enters when price breaks a key level AND volume surges above
    a multiple of the average volume over a lookback period.

    Parameters
    ----------
    lookback : int
        Number of bars to compute average volume. Default: 20.
    volume_multiplier : float
        Multiplier of average volume required for confirmation. Default: 2.0.
    price_lookback : int
        Number of bars to define the price range. Default: 20.
    """

    def __init__(
        self,
        lookback: int = 20,
        volume_multiplier: float = 2.0,
        price_lookback: int = 20,
    ) -> None:
        self._lookback = lookback
        self._volume_multiplier = volume_multiplier
        self._price_lookback = price_lookback

    @property
    def name(self) -> str:
        return "VolumeSurge"

    def get_params(self) -> dict:
        return {
            "lookback": self._lookback,
            "volume_multiplier": self._volume_multiplier,
            "price_lookback": self._price_lookback,
        }

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        raise NotImplementedError(f"{self.name}.generate_signals() not yet implemented")