"""Pattern scanner: chart patterns and candlestick pattern detection."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from ACTosha.scanner.base import MarketScanner, Opportunity


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _local_extrema(series: pd.Series, order: int = 3) -> pd.Series:
    """Return a boolean Series that is True at local maxima/minima.

    Parameters
    ----------
    series : pd.Series
        Price series.
    order : int
        Number of bars on each side required for an extremum.

    Returns
    -------
    pd.Series (bool)
        True where the point is an extremum.
    """
    shifted_up = series.shift(-order)
    shifted_down = series.shift(order)
    is_max = (series >= shifted_up) & (series >= shifted_down)
    is_min = (series <= shifted_up) & (series <= shifted_down)
    return is_max | is_min


def _swing_highs_lows(
    df: pd.DataFrame, lookback: int = 5
) -> tuple[pd.Series, pd.Series]:
    """Identify swing highs and swing lows.

    Returns
    -------
    swing_highs : pd.Series (bool) — True where a bar is a swing high
    swing_lows  : pd.Series (bool) — True where a bar is a swing low
    """
    highs = df["high"]
    lows = df["low"]

    swing_highs = pd.Series(False, index=df.index)
    swing_lows = pd.Series(False, index=df.index)

    for i in range(lookback, len(df) - lookback):
        is_high = True
        is_low = True
        for j in range(1, lookback + 1):
            if highs.iloc[i] <= highs.iloc[i - j]:
                is_high = False
            if lows.iloc[i] >= lows.iloc[i - j]:
                is_low = False
        swing_highs.iloc[i] = is_high
        swing_lows.iloc[i] = is_low

    return swing_highs, swing_lows


# ---------------------------------------------------------------------------
# Chart pattern detection
# ---------------------------------------------------------------------------

def _detect_double_top(
    df: pd.DataFrame, tolerance: float = 0.01
) -> Optional[tuple[float, float, float]]:
    """Detect double top pattern.

    Returns
    -------
    tuple (neck_level, top1_price, top2_price) or None.
    """
    swing_highs, _ = _swing_highs(df, lookback=5)
    high_indices = df.index[swing_highs].tolist()

    for i in range(len(high_indices) - 1):
        idx1 = high_indices[i]
        idx2 = high_indices[i + 1]
        price1 = df.loc[idx1, "high"]
        price2 = df.loc[idx2, "high"]

        if abs(price1 - price2) / price1 <= tolerance:
            # Found two equal highs — neck is the lower low between them
            between = df.loc[idx1:idx2]
            neck = between["low"].min()
            return (neck, price1, price2)
    return None


def _detect_double_bottom(
    df: pd.DataFrame, tolerance: float = 0.01
) -> Optional[tuple[float, float, float]]:
    """Detect double bottom pattern.

    Returns
    -------
    tuple (neck_level, bot1_price, bot2_price) or None.
    """
    _, swing_lows = _swing_highs(df, lookback=5)
    low_indices = df.index[swing_lows].tolist()

    for i in range(len(low_indices) - 1):
        idx1 = low_indices[i]
        idx2 = low_indices[i + 1]
        price1 = df.loc[idx1, "low"]
        price2 = df.loc[idx2, "low"]

        if abs(price1 - price2) / price1 <= tolerance:
            between = df.loc[idx1:idx2]
            neck = between["high"].max()
            return (neck, price1, price2)
    return None


def _swing_highs(df: pd.DataFrame, lookback: int = 5) -> tuple[pd.Series, pd.Series]:
    """Return (swing_highs, swing_lows) boolean Series."""
    return _swing_highs_lows(df, lookback=lookback)


def _detect_head_shoulders(
    df: pd.DataFrame, tolerance: float = 0.015
) -> Optional[dict]:
    """Detect head-and-shoulders pattern (regular and inverse).

    Returns
    -------
    dict with keys: pattern_type, neck, head_price, shoulders_prices, strength
    or None if not detected.
    """
    swing_highs, swing_lows = _swing_highs(df, lookback=5)
    high_idx = df.index[swing_highs].tolist()
    low_idx = df.index[swing_lows].tolist()

    if len(high_idx) < 3 or len(low_idx) < 2:
        return None

    # --- Regular H&S: left_shoulder < head > right_shoulder, neck breaks ---
    for i in range(len(high_idx) - 2):
        ls_idx, head_idx, rs_idx = high_idx[i], high_idx[i + 1], high_idx[i + 2]
        ls_price = df.loc[ls_idx, "high"]
        head_price = df.loc[head_idx, "high"]
        rs_price = df.loc[rs_idx, "high"]

        if (
            ls_price < head_price
            and rs_price < head_price
            and abs(ls_price - rs_price) / ls_price <= tolerance
        ):
            # Neck: the lower low between head and each shoulder
            between1 = df.loc[ls_idx:head_idx, "low"].min()
            between2 = df.loc[head_idx:rs_idx, "low"].min()
            neck = min(between1, between2)

            # Check if price broke below neck (confirmation)
            post_shoulder = df.loc[rs_idx:].head(10)
            if len(post_shoulder) < 2:
                continue
            close_after = post_shoulder["close"].iloc[-1]
            strength = max(0, 1 - abs(close_after - neck) / (head_price - neck))

            return {
                "pattern_type": "head_shoulders",
                "neck": neck,
                "head_price": head_price,
                "left_shoulder_price": ls_price,
                "right_shoulder_price": rs_price,
                "strength": min(strength + 0.5, 1.0),
            }

    # --- Inverse H&S ---
    for i in range(len(low_idx) - 2):
        ls_idx, head_idx, rs_idx = low_idx[i], low_idx[i + 1], low_idx[i + 2]
        ls_price = df.loc[ls_idx, "low"]
        head_price = df.loc[head_idx, "low"]
        rs_price = df.loc[rs_idx, "low"]

        if (
            ls_price > head_price
            and rs_price > head_price
            and abs(ls_price - rs_price) / ls_price <= tolerance
        ):
            between1 = df.loc[ls_idx:head_idx, "high"].max()
            between2 = df.loc[head_idx:rs_idx, "high"].max()
            neck = max(between1, between2)

            post_shoulder = df.loc[rs_idx:].head(10)
            if len(post_shoulder) < 2:
                continue
            close_after = post_shoulder["close"].iloc[-1]
            strength = max(0, 1 - abs(close_after - neck) / (neck - head_price))

            return {
                "pattern_type": "inverse_head_shoulders",
                "neck": neck,
                "head_price": head_price,
                "left_shoulder_price": ls_price,
                "right_shoulder_price": rs_price,
                "strength": min(strength + 0.5, 1.0),
            }

    return None


def _detect_triangle(
    df: pd.DataFrame, lookback: int = 50
) -> Optional[dict]:
    """Detect ascending, descending, and symmetric triangle patterns.

    Returns
    -------
    dict with pattern_type, resistance, support, break_direction, strength
    or None.
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    highs = recent["high"]
    lows = recent["low"]

    # Linear regression slopes
    x = np.arange(len(highs))
    high_slope = np.polyfit(x, highs.values, 1)[0]
    low_slope = np.polyfit(x, lows.values, 1)[0]

    # Determine triangle type from slope convergence
    recent_high = highs.iloc[-1]
    recent_low = lows.iloc[-1]
    earlier_high = highs.iloc[0]
    earlier_low = lows.iloc[0]

    resistance = recent_high
    support = recent_low
    pattern_type = "symmetric_triangle"
    break_direction = "break_up"

    slope_thresh = (recent_high - earlier_high) / lookback * 0.3

    if high_slope > -slope_thresh and low_slope > slope_thresh:
        pattern_type = "ascending_triangle"
        support = recent_low
        break_direction = "break_up"
    elif high_slope < slope_thresh and low_slope < -slope_thresh:
        pattern_type = "descending_triangle"
        resistance = recent_high
        break_direction = "break_down"
    elif high_slope < 0 and low_slope > 0:
        pattern_type = "symmetric_triangle"
        break_direction = "break_up" if highs.iloc[-1] > lows.iloc[-1] else "break_down"
    else:
        return None

    # Estimate strength based on how tight the wedge is
    range_early = earlier_high - earlier_low
    range_recent = recent_high - recent_low
    squeeze = 1 - (range_recent / max(range_early, 1e-9))
    strength = max(0.5, min(squeeze + 0.4, 0.95))

    return {
        "pattern_type": pattern_type,
        "resistance": resistance,
        "support": support,
        "break_direction": break_direction,
        "strength": strength,
    }


def _detect_wedge(
    df: pd.DataFrame, lookback: int = 40
) -> Optional[dict]:
    """Detect rising and falling wedge patterns.

    Returns
    -------
    dict with pattern_type, resistance, support, break_direction, strength
    or None.
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    highs = recent["high"]
    lows = recent["low"]

    x = np.arange(len(highs))
    high_slope = np.polyfit(x, highs.values, 1)[0]
    low_slope = np.polyfit(x, lows.values, 1)[0]

    slope_thresh = abs((highs.iloc[-1] - highs.iloc[0]) / lookback) * 0.3

    if high_slope > 0 and low_slope > 0 and abs(high_slope - low_slope) < slope_thresh:
        return None  # Parallel channels, not a wedge

    # Rising wedge: both slopes positive (converging upward)
    if high_slope > slope_thresh and low_slope > 0:
        return {
            "pattern_type": "rising_wedge",
            "resistance": highs.iloc[-1],
            "support": lows.iloc[-1],
            "break_direction": "break_down",
            "strength": 0.7,
        }
    # Falling wedge: both slopes negative (converging downward)
    elif low_slope < -slope_thresh and high_slope < 0:
        return {
            "pattern_type": "falling_wedge",
            "resistance": highs.iloc[-1],
            "support": lows.iloc[-1],
            "break_direction": "break_up",
            "strength": 0.7,
        }

    return None


# ---------------------------------------------------------------------------
# Candlestick pattern detection
# ---------------------------------------------------------------------------

def _detect_engulfing(df: pd.DataFrame) -> Optional[dict]:
    """Detect bullish and bearish engulfing patterns.

    Returns
    -------
    dict with pattern_type, strength, last_close, or None.
    """
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    body_curr = abs(curr["close"] - curr["open"])
    body_prev = abs(prev["close"] - prev["open"])

    # Bearish engulfing: prev is bullish, curr is bearish, curr body engulfs prev
    if (
        prev["close"] > prev["open"]
        and curr["close"] < curr["open"]
        and curr["high"] > prev["high"]
        and curr["low"] < prev["low"]
        and body_curr > body_prev
    ):
        return {
            "pattern_type": "bearish_engulfing",
            "strength": min(body_curr / body_prev * 0.6, 0.95),
            "last_close": curr["close"],
            "last_open": curr["open"],
        }

    # Bullish engulfing: prev is bearish, curr is bullish, curr body engulfs prev
    if (
        prev["close"] < prev["open"]
        and curr["close"] > curr["open"]
        and curr["high"] > prev["high"]
        and curr["low"] < prev["low"]
        and body_curr > body_prev
    ):
        return {
            "pattern_type": "bullish_engulfing",
            "strength": min(body_curr / body_prev * 0.6, 0.95),
            "last_close": curr["close"],
            "last_open": curr["open"],
        }

    return None


def _detect_hammer(df: pd.DataFrame) -> Optional[dict]:
    """Detect hammer and inverted hammer candlestick patterns.

    Returns
    -------
    dict with pattern_type, strength, or None.
    """
    if len(df) < 1:
        return None

    curr = df.iloc[-1]
    open_, high, low, close = curr["open"], curr["high"], curr["low"], curr["close"]

    body = abs(close - open_)
    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low

    # Hammer: small body at top, long lower shadow (> 2x body)
    if lower_shadow > 2 * body and upper_shadow < body * 0.3:
        strength = min(lower_shadow / (high - low) * 1.5, 0.95)
        return {
            "pattern_type": "hammer",
            "strength": max(strength, 0.55),
            "last_close": close,
        }

    # Inverted hammer: small body at bottom, long upper shadow
    if upper_shadow > 2 * body and lower_shadow < body * 0.3:
        strength = min(upper_shadow / (high - low) * 1.5, 0.95)
        return {
            "pattern_type": "inverted_hammer",
            "strength": max(strength, 0.55),
            "last_close": close,
        }

    return None


def _detect_doji(df: pd.DataFrame, threshold: float = 0.05) -> Optional[dict]:
    """Detect doji (indecision) candlestick.

    Returns
    -------
    dict with pattern_type, strength, or None.
    """
    if len(df) < 1:
        return None

    curr = df.iloc[-1]
    open_, high, low, close = curr["open"], curr["high"], curr["low"], curr["close"]

    body = abs(close - open_)
    candle_range = high - low

    if candle_range < 1e-9:
        return None

    if body / candle_range <= threshold:
        # Doji strength inversely proportional to body size
        strength = 1 - (body / candle_range)
        return {
            "pattern_type": "doji",
            "strength": max(strength, 0.5),
            "last_close": close,
        }

    return None


def _detect_morning_star(
    df: pd.DataFrame, lookback: int = 3
) -> Optional[dict]:
    """Detect morning star (3-bar bullish reversal) pattern.

    Returns
    -------
    dict with pattern_type, strength, or None.
    """
    if len(df) < lookback:
        return None

    bar1 = df.iloc[-3]
    bar2 = df.iloc[-2]
    bar3 = df.iloc[-1]

    # Bar 1: long bearish body
    body1 = abs(bar1["close"] - bar1["open"])
    range1 = bar1["high"] - bar1["low"]
    is_bearish1 = bar1["close"] < bar1["open"] and body1 > range1 * 0.6

    # Bar 2: small body (star), gap down from bar1
    body2 = abs(bar2["close"] - bar2["open"])
    is_small_body2 = body2 < body1 * 0.3

    # Bar 3: long bullish body, closes above midpoint of bar1
    body3 = abs(bar3["close"] - bar3["open"])
    range3 = bar3["high"] - bar3["low"]
    is_bullish3 = bar3["close"] > bar3["open"] and body3 > range3 * 0.6
    closes_above_mid = bar3["close"] > (bar1["open"] + bar1["close"]) / 2

    if is_bearish1 and is_small_body2 and is_bullish3 and closes_above_mid:
        return {
            "pattern_type": "morning_star",
            "strength": 0.75,
            "last_close": bar3["close"],
        }

    # Evening star (bearish reversal)
    is_bullish1 = bar1["close"] > bar1["open"] and body1 > range1 * 0.6
    is_bearish3 = bar3["close"] < bar3["open"] and body3 > range3 * 0.6
    closes_below_mid = bar3["close"] < (bar1["open"] + bar1["close"]) / 2

    if is_bullish1 and is_small_body2 and is_bearish3 and closes_below_mid:
        return {
            "pattern_type": "evening_star",
            "strength": 0.75,
            "last_close": bar3["close"],
        }

    return None


# ---------------------------------------------------------------------------
# PatternScanner
# ---------------------------------------------------------------------------

class PatternScanner(MarketScanner):
    """Scan for chart patterns and candlestick patterns.

    Chart patterns detected
        - double_top
        - double_bottom
        - head_shoulders / inverse_head_shoulders
        - ascending_triangle / descending_triangle / symmetric_triangle
        - rising_wedge / falling_wedge

    Candlestick patterns detected
        - bullish_engulfing / bearish_engulfing
        - hammer / inverted_hammer
        - doji
        - morning_star / evening_star
    """

    PATTERNS = [
        # Chart patterns
        "double_top",
        "double_bottom",
        "head_shoulders",
        "inverse_head_shoulders",
        "ascending_triangle",
        "descending_triangle",
        "symmetric_triangle",
        "rising_wedge",
        "falling_wedge",
        # Candlestick patterns
        "bullish_engulfing",
        "bearish_engulfing",
        "hammer",
        "inverted_hammer",
        "doji",
        "morning_star",
        "evening_star",
    ]

    def __init__(
        self,
        timeframe: str = "1h",
        min_strength: float = 0.5,
        lookback: int = 100,
    ) -> None:
        """
        Parameters
        ----------
        timeframe : str
            OHLCV timeframe label.
        min_strength : float
            Minimum confidence to return an opportunity.
        lookback : int
            Number of bars to use for chart pattern detection.
        """
        super().__init__(timeframe=timeframe, min_strength=min_strength)
        self.lookback = lookback

    def _scan_symbol(
        self, symbol: str, df: pd.DataFrame
    ) -> list[Opportunity]:
        opps: list[Opportunity] = []

        # ---- Chart patterns ----
        opps.extend(self._scan_chart_patterns(symbol, df))
        # ---- Candlestick patterns ----
        opps.extend(self._scan_candlestick(symbol, df))

        return opps

    def _scan_chart_patterns(
        self, symbol: str, df: pd.DataFrame
    ) -> list[Opportunity]:
        opps: list[Opportunity] = []
        recent = df.tail(self.lookback).copy()

        # Double top
        result = _detect_double_top(recent)
        if result:
            neck, top1, top2 = result
            close = recent["close"].iloc[-1]
            entry_zone: tuple[float, float] = (neck * 0.995, neck * 1.005)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="double_top",
                    timeframe=self.timeframe,
                    strength=0.70,
                    entry_zone=entry_zone,
                    metadata={
                        "neck": neck,
                        "top1": top1,
                        "top2": top2,
                        "break_confirmation": "close_below_neck",
                    },
                )
            )

        # Double bottom
        result = _detect_double_bottom(recent)
        if result:
            neck, bot1, bot2 = result
            entry_zone = (neck * 0.995, neck * 1.005)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="double_bottom",
                    timeframe=self.timeframe,
                    strength=0.70,
                    entry_zone=entry_zone,
                    metadata={
                        "neck": neck,
                        "bottom1": bot1,
                        "bottom2": bot2,
                        "break_confirmation": "close_above_neck",
                    },
                )
            )

        # Head and shoulders
        result = _detect_head_shoulders(recent)
        if result:
            entry_zone = (result["neck"] * 0.995, result["neck"] * 1.005)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern=result["pattern_type"],
                    timeframe=self.timeframe,
                    strength=result["strength"],
                    entry_zone=entry_zone,
                    metadata={
                        "neck": result["neck"],
                        "head_price": result["head_price"],
                    },
                )
            )

        # Triangle
        result = _detect_triangle(recent)
        if result:
            entry_zone = (
                min(result["resistance"], result["support"]),
                max(result["resistance"], result["support"]),
            )
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern=result["pattern_type"],
                    timeframe=self.timeframe,
                    strength=result["strength"],
                    entry_zone=entry_zone,
                    metadata={
                        "resistance": result["resistance"],
                        "support": result["support"],
                        "break_direction": result["break_direction"],
                    },
                )
            )

        # Wedge
        result = _detect_wedge(recent)
        if result:
            entry_zone = (
                min(result["resistance"], result["support"]),
                max(result["resistance"], result["support"]),
            )
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern=result["pattern_type"],
                    timeframe=self.timeframe,
                    strength=result["strength"],
                    entry_zone=entry_zone,
                    metadata={
                        "resistance": result["resistance"],
                        "support": result["support"],
                        "break_direction": result["break_direction"],
                    },
                )
            )

        return opps

    def _scan_candlestick(
        self, symbol: str, df: pd.DataFrame
    ) -> list[Opportunity]:
        opps: list[Opportunity] = []
        recent = df.tail(5).copy()

        # Engulfing
        result = _detect_engulfing(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            entry_zone: tuple[float, float] = (close - spread, close + spread)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern=result["pattern_type"],
                    timeframe=self.timeframe,
                    strength=result["strength"],
                    entry_zone=entry_zone,
                    metadata={"last_close": result["last_close"]},
                )
            )

        # Hammer
        result = _detect_hammer(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            entry_zone = (close - spread, close + spread)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern=result["pattern_type"],
                    timeframe=self.timeframe,
                    strength=result["strength"],
                    entry_zone=entry_zone,
                    metadata={"last_close": result["last_close"]},
                )
            )

        # Doji
        result = _detect_doji(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            entry_zone = (close - spread, close + spread)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern=result["pattern_type"],
                    timeframe=self.timeframe,
                    strength=result["strength"],
                    entry_zone=entry_zone,
                    metadata={"last_close": result["last_close"]},
                )
            )

        # Morning / Evening star
        result = _detect_morning_star(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            entry_zone = (close - spread, close + spread)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern=result["pattern_type"],
                    timeframe=self.timeframe,
                    strength=result["strength"],
                    entry_zone=entry_zone,
                    metadata={"last_close": result["last_close"]},
                )
            )

        return opps


__all__ = ["PatternScanner"]
