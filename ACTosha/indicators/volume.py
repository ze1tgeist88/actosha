"""Volume indicators: OBV, VWAP, Volume Profile."""

from __future__ import annotations

import pandas as pd
import numpy as np


def compute_obv(df: pd.DataFrame, col: str = "close") -> pd.DataFrame:
    """On-Balance Volume.

    Running total of volume where the bar is added if close > prev_close,
    subtracted if close < prev_close, unchanged if equal.

    Adds column: obv
    """
    result = df.copy()

    direction = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (direction * df["volume"]).cumsum()
    # First bar: no diff, so just use volume with positive sign
    obv.iloc[0] = df["volume"].iloc[0] if df["volume"].iloc[0] > 0 else 0

    result["obv"] = obv
    return result


def compute_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Volume-Weighted Average Price.

    VWAP = cumsum(typical_price * volume) / cumsum(volume)
    typical_price = (high + low + close) / 3

    Resets each day (assumes DataFrame index is DatetimeIndex).

    Adds column: vwap
    """
    result = df.copy()

    if not isinstance(df.index, pd.DatetimeIndex):
        # Fallback: use DatetimeIndex from timestamp column if present
        if "timestamp" in df.columns:
            result.index = pd.to_datetime(df["timestamp"], utc=True)
        else:
            result["vwap"] = (df["high"] + df["low"] + df["close"]) / 3
            return result

    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_pv = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()

    result["vwap"] = cum_pv / cum_vol.replace(0, np.nan)
    result["vwap"] = result["vwap"].fillna(typical_price)

    return result


def compute_volume_profile(
    df: pd.DataFrame, bins: int = 50
) -> pd.DataFrame:
    """Volume Profile (price distribution by volume).

    Divides price range into `bins` bins and computes volume traded in each.
    Adds columns:
        vpoc — Volume POC (price level with highest volume)
        vp_delta — Net buying pressure (up volume - down volume)
        vp_imbalance — Ratio of buying to total volume

    POC: highest volume bin price
    Delta: sum(positive_close_bars_vol) - sum(negative_close_bars_vol)
    Imbalance: delta / total_volume (0 = neutral, 1 = pure buying, -1 = pure selling)
    """
    result = df.copy()

    low_price = df["low"].min()
    high_price = df["high"].max()
    if high_price == low_price:
        high_price = low_price + 1

    bin_edges = np.linspace(low_price, high_price, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    price_range = high_price - low_price
    bin_size = price_range / bins

    # Assign each bar to a bin based on close price
    bin_indices = ((df["close"] - low_price) / bin_size).clip(0, bins - 1).astype(int)

    profile = pd.Series(0.0, index=range(bins))
    up_volume = pd.Series(0.0, index=range(bins))
    down_volume = pd.Series(0.0, index=range(bins))

    for i, bin_idx in enumerate(bin_indices.values):
        vol = df["volume"].iloc[i]
        profile.iloc[bin_idx] += vol
        if df["close"].iloc[i] >= df["open"].iloc[i]:
            up_volume.iloc[bin_idx] += vol
        else:
            down_volume.iloc[bin_idx] += vol

    # POC: bin with maximum volume
    poc_bin = profile.idxmax()
    result["vpoc"] = bin_centers[poc_bin]
    result["vp_delta"] = (up_volume - down_volume).sum()
    result["vp_imbalance"] = result["vp_delta"] / max(profile.sum(), 1)

    # Add per-row VP values (rolling, last N bins aggregated)
    # For efficiency: compute running VP delta and imbalance
    result["vp_delta"] = (
        (df["close"] > df["open"]).astype(float) * 2 - 1
    ) * df["volume"]
    result["vp_delta"] = result["vp_delta"].rolling(window=20, min_periods=1).sum()
    result["vp_imbalance"] = (
        (df["close"] > df["open"]).astype(float) * df["volume"]
    ) / df["volume"].replace(0, 1).rolling(window=20, min_periods=1).mean()
    result["vp_imbalance"] = result["vp_imbalance"].fillna(0).clip(-1, 1)

    return result