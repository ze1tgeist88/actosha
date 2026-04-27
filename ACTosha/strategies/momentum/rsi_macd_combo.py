"""Momentum strategy: RSI + MACD confluence."""

from __future__ import annotations

import pandas as pd

from ACTosha.strategies.base import SignalBundle, Strategy


class RSIMACDComboStrategy(Strategy):
    """RSI + MACD confluence momentum strategy.

    Generates signals only when both RSI and MACD agree on direction.
    Long: RSI crosses above 50 AND MACD line crosses above signal line.
    Short: RSI crosses below 50 AND MACD line crosses below signal line.

    Parameters
    ----------
    rsi_period : int
        RSI period. Default: 14.
    macd_fast : int
        MACD fast EMA period. Default: 12.
    macd_slow : int
        MACD slow EMA period. Default: 26.
    macd_signal : int
        MACD signal line period. Default: 9.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
    ) -> None:
        self._rsi_period = rsi_period
        self._macd_fast = macd_fast
        self._macd_slow = macd_slow
        self._macd_signal = macd_signal

    @property
    def name(self) -> str:
        return "RSIMACDCombo"

    def get_params(self) -> dict:
        return {
            "rsi_period": self._rsi_period,
            "macd_fast": self._macd_fast,
            "macd_slow": self._macd_slow,
            "macd_signal": self._macd_signal,
        }

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        raise NotImplementedError(f"{self.name}.generate_signals() not yet implemented")