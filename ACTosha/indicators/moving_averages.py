"""Moving averages: SMA, EMA, WMA."""

from __future__ import annotations

import pandas as pd
import numpy as np


def compute_sma(df: pd.DataFrame, period: int = 20, col: str = "close") -> pd.DataFrame:
    """Simple Moving Average.

    Adds column: sma_{period}
    """
    result = df.copy()
    result[f"sma_{period}"] = df[col].rolling(window=period, min_periods=period).mean()
    return result


def compute_ema(df: pd.DataFrame, period: int = 20, col: str = "close") -> pd.DataFrame:
    """Exponential Moving Average.

    Adds column: ema_{period}
    """
    result = df.copy()
    result[f"ema_{period}"] = df[col].ewm(
        span=period, adjust=False, min_periods=period
    ).mean()
    return result


def compute_wma(df: pd.DataFrame, period: int = 20, col: str = "close") -> pd.DataFrame:
    """Weighted Moving Average.

    Uses linear weights: WMA = sum(price_i * i) / sum(i) for i=1..period
    Adds column: wma_{period}
    """
    result = df.copy()
    prices = df[col]

    def weighted_mean(series: pd.Series) -> float:
        values = series.values
        if len(values) < period:
            return np.nan
        weights = np.arange(1, len(values) + 1)
        return np.dot(values, weights) / weights.sum()

    result[f"wma_{period}"] = (
        prices.rolling(window=period, min_periods=period)
        .apply(weighted_mean, raw=True)
    )
    return result


def compute_sma_multi(
    df: pd.DataFrame, periods: list[int], col: str = "close"
) -> pd.DataFrame:
    """Compute multiple SMAs at once. Adds sma_{period} for each period."""
    result = df.copy()
    for p in periods:
        result[f"sma_{p}"] = df[col].rolling(window=p, min_periods=p).mean()
    return result


def compute_ema_multi(
    df: pd.DataFrame, periods: list[int], col: str = "close"
) -> pd.DataFrame:
    """Compute multiple EMAs at once. Adds ema_{period} for each period."""
    result = df.copy()
    for p in periods:
        result[f"ema_{p}"] = (
            df[col].ewm(span=p, adjust=False, min_periods=p).mean()
        )
    return result