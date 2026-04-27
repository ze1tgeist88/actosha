"""IndicatorEngine — compute technical indicators on OHLCV DataFrames."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import numpy as np

from ACTosha.indicators.moving_averages import (
    compute_sma,
    compute_ema,
    compute_wma,
)
from ACTosha.indicators.momentum import (
    compute_rsi,
    compute_macd,
    compute_stochastic,
)
from ACTosha.indicators.volatility import (
    compute_bollinger_bands,
    compute_atr,
    compute_keltner_channels,
)
from ACTosha.indicators.volume import (
    compute_obv,
    compute_vwap,
    compute_volume_profile,
)


# Signature for all indicator functions:
#   (df: pd.DataFrame, **params) -> pd.DataFrame
IndicatorFn = Callable[..., pd.DataFrame]


class IndicatorEngine:
    """Compute technical indicators on OHLCV data.

    Supports the following built-in indicators:

    Moving Averages
        sma(period)         Simple moving average
        ema(period)         Exponential moving average
        wma(period)         Weighted moving average

    Momentum
        rsi(period=14)      Relative Strength Index
        macd(fast=12, slow=26, signal=9)
        stochastic(k_period=14, d_period=3)

    Volatility
        bollinger_bands(period=20, std_dev=2)
        atr(period=14)       Average True Range
        keltner_channels(period=20, atr_period=10, multiplier=2)

    Volume
        obv()               On-Balance Volume
        vwap()              Volume-Weighted Average Price
        volume_profile(bins=50)

    Each computed indicator adds its columns to the returned DataFrame.
    The input OHLCV DataFrame must contain: open, high, low, close, volume.
    """

    BUILT_IN: dict[str, IndicatorFn] = {
        # Moving averages
        "sma":            compute_sma,
        "ema":            compute_ema,
        "wma":            compute_wma,
        # Momentum
        "rsi":            compute_rsi,
        "macd":           compute_macd,
        "stochastic":     compute_stochastic,
        # Volatility
        "bollinger_bands": compute_bollinger_bands,
        "atr":             compute_atr,
        "keltner_channels": compute_keltner_channels,
        # Volume
        "obv":            compute_obv,
        "vwap":           compute_vwap,
        "volume_profile": compute_volume_profile,
    }

    def __init__(self) -> None:
        """Initialize IndicatorEngine with registered indicator functions."""
        self._indicators: dict[str, IndicatorFn] = dict(self.BUILT_IN)
        self._custom: dict[str, IndicatorFn] = {}

    def compute(
        self,
        indicator_name: str,
        df: pd.DataFrame,
        **params: Any,
    ) -> pd.DataFrame:
        """Compute a named indicator on the input DataFrame.

        Args:
            indicator_name: Name of indicator (e.g. "sma", "rsi", "macd")
            df:             OHLCV DataFrame with columns: open, high, low, close, volume
            **params:       Indicator-specific parameters (passed to the indicator function)

        Returns:
            DataFrame with added indicator columns.

        Raises:
            ValueError: If indicator_name is not registered.
            KeyError: If required column is missing from df.
        """
        indicator_name = indicator_name.lower()
        fn = self._indicators.get(indicator_name)

        if fn is None:
            fn = self._custom.get(indicator_name)
            if fn is None:
                available = self.list_available()
                raise ValueError(
                    f"Unknown indicator '{indicator_name}'. "
                    f"Available: {available}"
                )

        # Validate required columns
        required_cols = {"close"}
        if indicator_name in {"rsi", "macd", "bollinger_bands", "atr"}:
            required_cols.update({"high", "low"})
        if indicator_name in {"atr", "keltner_channels"}:
            required_cols.add("open")
        if indicator_name in {"obv", "vwap", "volume_profile"}:
            required_cols.add("volume")

        missing = required_cols - set(df.columns)
        if missing:
            raise KeyError(
                f"DataFrame missing required columns for '{indicator_name}': {missing}"
            )

        result_df = fn(df, **params)
        return result_df

    def compute_indicator_set(
        self,
        indicators: list[str],
        df: pd.DataFrame,
        **global_params: Any,
    ) -> pd.DataFrame:
        """Compute multiple indicators in one call.

        Args:
            indicators:  List of indicator names to compute.
            df:           OHLCV DataFrame.
            **global_params: Parameters shared across all indicators.

        Returns:
            DataFrame with all computed indicators added as columns.
        """
        result = df.copy()
        for name in indicators:
            result = self.compute(name, result, **global_params)
        return result

    def register(self, name: str, fn: IndicatorFn) -> None:
        """Register a custom indicator function.

        Args:
            name: Lowercase identifier for the indicator.
            fn:   Callable(df, **params) → pd.DataFrame.
        """
        self._custom[name.lower()] = fn
        self._indicators[name.lower()] = fn

    def list_available(self) -> list[str]:
        """Return alphabetically sorted list of available indicator names."""
        return sorted(self._indicators.keys())

    # ------------------------------------------------------------------
    # Convenience methods for common indicator subsets
    # ------------------------------------------------------------------

    def compute_all_ma(self, df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
        """Compute SMA and EMA for a list of periods."""
        if periods is None:
            periods = [9, 21, 50, 200]
        result = df.copy()
        for p in periods:
            for ma in ("sma", "ema"):
                result = self.compute(ma, result, period=p)
        return result

    def compute_momentum_set(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute RSI, MACD, Stochastic with default parameters."""
        result = df.copy()
        result = self.compute("rsi", result, period=14)
        result = self.compute("macd", result, fast=12, slow=26, signal=9)
        result = self.compute("stochastic", result, k_period=14, d_period=3)
        return result

    def compute_volatility_set(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute Bollinger Bands, ATR, Keltner Channels with defaults."""
        result = df.copy()
        result = self.compute("bollinger_bands", result, period=20, std_dev=2)
        result = self.compute("atr", result, period=14)
        result = self.compute("keltner_channels", result, period=20, atr_period=10, multiplier=2)
        return result


__all__ = ["IndicatorEngine"]