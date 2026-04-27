"""Mean reversion strategy: RSI extreme levels (< 30 / > 70)."""

from __future__ import annotations

import pandas as pd

from ACTosha.strategies.base import SignalBundle, Strategy


class RSIExtremeStrategy(Strategy):
    """RSI-based mean reversion strategy.

    Goes long when RSI drops below oversold threshold (<30),
    goes short when RSI rises above overbought threshold (>70).
    Exits when RSI returns to neutral territory.

    Parameters
    ----------
    rsi_period : int
        Period for RSI calculation. Default: 14.
    oversold : float
        RSI level below which a long signal is generated. Default: 30.
    overbought : float
        RSI level above which a short signal is generated. Default: 70.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        self._rsi_period = rsi_period
        self._oversold = oversold
        self._overbought = overbought

    @property
    def name(self) -> str:
        return "RSIExtreme"

    def get_params(self) -> dict:
        return {
            "rsi_period": self._rsi_period,
            "oversold": self._oversold,
            "overbought": self._overbought,
        }

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        raise NotImplementedError(f"{self.name}.generate_signals() not yet implemented")