"""Volatility indicators: Bollinger Bands, ATR, Keltner Channels."""

from __future__ import annotations

import pandas as pd
import numpy as np


def compute_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, col: str = "close"
) -> pd.DataFrame:
    """Bollinger Bands.

    Middle Band = SMA(close, period)
    Upper Band  = SMA + (std_dev * rolling_std)
    Lower Band  = SMA - (std_dev * rolling_std)

    Adds columns: bb_middle, bb_upper, bb_lower, bb_width, bb_percent
    """
    result = df.copy()

    sma = df[col].rolling(window=period, min_periods=period).mean()
    rolling_std = df[col].rolling(window=period, min_periods=period).std()

    result["bb_middle"] = sma
    result["bb_upper"] = sma + (std_dev * rolling_std)
    result["bb_lower"] = sma - (std_dev * rolling_std)

    # Bandwidth: (upper - lower) / middle
    bandwidth = (result["bb_upper"] - result["bb_lower"]) / sma
    result["bb_width"] = bandwidth.fillna(0)

    # %B (position within bands): (close - lower) / (upper - lower)
    range_ = result["bb_upper"] - result["bb_lower"]
    result["bb_percent"] = (df[col] - result["bb_lower"]) / range_.replace(0, np.nan)
    result["bb_percent"] = result["bb_percent"].fillna(0.5)

    return result


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Average True Range.

    TR = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = Wilder EMA of TR over `period`

    Adds column: atr_{period}
    """
    result = df.copy()

    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder smoothing: first value = simple mean, then EMA-like
    atr_sma = true_range.rolling(window=period, min_periods=period).mean()
    # Subsequent: (prev_atr * (period-1) + current_tr) / period
    # Equivalent to EMA with alpha = 1/period
    result[f"atr_{period}"] = atr_sma
    # Fill remaining NaN using Wilder EMA
    for i in range(period, len(true_range)):
        if pd.isna(result[f"atr_{period}"].iloc[i]):
            pass  # already filled by SMA fallback
        elif i > period:
            prev = result[f"atr_{period}"].iloc[i - 1]
            curr = true_range.iloc[i]
            result[f"atr_{period}"].iloc[i] = (prev * (period - 1) + curr) / period

    result[f"atr_{period}"] = result[f"atr_{period}"].fillna(0)
    return result


def compute_keltner_channels(
    df: pd.DataFrame, period: int = 20, atr_period: int = 10, multiplier: float = 2.0
) -> pd.DataFrame:
    """Keltner Channels.

    Middle = EMA(close, period)
    Upper  = Middle + (multiplier * ATR)
    Lower  = Middle - (multiplier * ATR)

    Uses compute_atr internally.

    Adds columns: kc_middle, kc_upper, kc_lower
    """
    result = df.copy()

    ema = df["close"].ewm(span=period, adjust=False, min_periods=period).mean()
    result["kc_middle"] = ema

    # Compute ATR using the module's logic
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(span=atr_period, adjust=False, min_periods=atr_period).mean()

    result["kc_upper"] = ema + multiplier * atr
    result["kc_lower"] = ema - multiplier * atr

    return result