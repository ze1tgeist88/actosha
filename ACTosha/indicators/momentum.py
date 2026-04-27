"""Momentum indicators: RSI, MACD, Stochastic."""

from __future__ import annotations

import pandas as pd
import numpy as np


def _change(series: pd.Series, period: int = 1) -> pd.Series:
    return series.diff(period)


def compute_rsi(df: pd.DataFrame, period: int = 14, col: str = "close") -> pd.DataFrame:
    """Relative Strength Index.

    Uses the standard Wilder smoothing (EMA of gains / EMA of losses).
    Adds columns: rsi_{period}
    """
    result = df.copy()
    delta = df[col].diff()

    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # First value: simple average over period
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder smoothing: RSI = 100 - 100 / (1 + RS)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result[f"rsi_{period}"] = 100 - (100 / (1 + rs))
    result[f"rsi_{period}"] = result[f"rsi_{period}"].fillna(50.0)

    return result


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    col: str = "close",
) -> pd.DataFrame:
    """MACD (Moving Average Convergence Divergence).

    MACD Line  = EMA(fast) - EMA(slow)
    Signal Line = EMA(macd_line, signal_period)
    Histogram   = MACD Line - Signal Line

    Adds columns: macd, macd_signal, macd_hist
    """
    result = df.copy()

    ema_fast = df[col].ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False, min_periods=slow).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line

    result["macd"] = macd_line
    result["macd_signal"] = signal_line
    result["macd_hist"] = histogram

    return result


def compute_stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> pd.DataFrame:
    """Stochastic Oscillator (%K and %D).

    %K = 100 * (close - lowest_low) / (highest_high - lowest_low)
    %D = SMA(%K, d_period)

    Adds columns: stoch_k, stoch_d
    """
    result = df.copy()

    lowest_low = df["low"].rolling(window=k_period, min_periods=k_period).min()
    highest_high = df["high"].rolling(window=k_period, min_periods=k_period).max()

    # Avoid division by zero
    range_hl = highest_high - lowest_low
    range_hl = range_hl.replace(0, np.nan)

    k_raw = 100 * (df["close"] - lowest_low) / range_hl

    result["stoch_k"] = k_raw
    result["stoch_d"] = k_raw.rolling(window=d_period, min_periods=d_period).mean()

    # Fill NaN with 50 (neutral)
    result["stoch_k"] = result["stoch_k"].fillna(50.0)
    result["stoch_d"] = result["stoch_d"].fillna(50.0)

    return result