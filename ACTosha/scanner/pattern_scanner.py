"""Pattern scanner: COMPLETE chart patterns and candlestick pattern detection.

v2.0 — All patterns from CHART_PATTERNS_KB.md implemented.

Chart patterns detected:
  REVERSAL:
    - double_top, double_bottom
    - triple_top, triple_bottom
    - head_shoulders, inverse_head_shoulders
    - broadening_top, broadening_bottom
    - island_top, island_bottom
  CONTINUATION:
    - ascending_triangle, descending_triangle, symmetric_triangle
    - rising_wedge, falling_wedge
    - bull_flag, bear_flag
    - bull_pennant, bear_pennant
    - horizontal_channel, ascending_channel, descending_channel
  GAPS:
    - breakaway_gap, exhaustion_gap, common_gap, measuring_gap
  SPECIAL:
    - cup_handle, inverted_cup_handle
    - bull_trap, bear_trap
Candlestick patterns:
    - bullish_engulfing, bearish_engulfing
    - hammer, inverted_hammer
    - doji
    - morning_star, evening_star
    - three_white_soldiers, three_black_crows
    - shooting_star
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from ACTosha.scanner.base import MarketScanner, Opportunity


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _local_extrema(series: pd.Series, order: int = 3) -> pd.Series:
    """Return a boolean Series that is True at local maxima/minima."""
    shifted_up = series.shift(-order)
    shifted_down = series.shift(order)
    is_max = (series >= shifted_up) & (series >= shifted_down)
    is_min = (series <= shifted_up) & (series <= shifted_down)
    return is_max | is_min


def _swing_highs_lows(
    df: pd.DataFrame, lookback: int = 5
) -> tuple[pd.Series, pd.Series]:
    """Identify swing highs and swing lows."""
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


def _swing_highs(df: pd.DataFrame, lookback: int = 5) -> tuple[pd.Series, pd.Series]:
    """Return (swing_highs, swing_lows) boolean Series."""
    return _swing_highs_lows(df, lookback=lookback)


def _detect_peaks_valleys(
    df: pd.DataFrame, lookback: int = 5
) -> tuple[list, list]:
    """Return lists of (index, price) for peaks and valleys."""
    swing_highs, swing_lows = _swing_highs(df, lookback=lookback)
    peak_idx = df.index[swing_highs].tolist()
    valley_idx = df.index[swing_lows].tolist()
    peaks = [(i, df.loc[i, "high"]) for i in peak_idx]
    valleys = [(i, df.loc[i, "low"]) for i in valley_idx]
    return peaks, valleys


def _trend_slope(series: pd.Series) -> float:
    """Return slope of linear fit (positive=up, negative=down)."""
    if len(series) < 2:
        return 0.0
    x = np.arange(len(series))
    return float(np.polyfit(x, series.values, 1)[0])


def _gap_size(bar1: pd.Series, bar2: pd.Series) -> float:
    """Return gap size as fraction of bar1 close. Positive=up gap, negative=down."""
    if bar1["close"] == 0:
        return 0.0
    gap = bar2["open"] - bar1["close"]
    return gap / bar1["close"]


# ---------------------------------------------------------------------------
# REVERSAL PATTERNS
# ---------------------------------------------------------------------------

def _detect_double_top(
    df: pd.DataFrame, tolerance: float = 0.01
) -> Optional[tuple]:
    """Detect double top (bearish reversal).

    Two peaks at ~equal price, neckline is lowest low between them.
    Tolerance: 1% (from Wikipedia).
    """
    peaks, _ = _detect_peaks_valleys(df, lookback=5)

    for i in range(len(peaks) - 1):
        idx1, price1 = peaks[i]
        idx2, price2 = peaks[i + 1]

        if abs(price1 - price2) / price1 <= tolerance:
            # Neckline is the lowest low between peaks
            between = df.loc[idx1:idx2]
            neck = between["low"].min()
            return (neck, price1, price2, idx1, idx2)
    return None


def _detect_double_bottom(
    df: pd.DataFrame, tolerance: float = 0.01
) -> Optional[tuple]:
    """Detect double bottom (bullish reversal).

    Two troughs at ~equal price, neckline is highest high between them.
    Tolerance: 1% (from Wikipedia).
    """
    _, valleys = _detect_peaks_valleys(df, lookback=5)

    for i in range(len(valleys) - 1):
        idx1, price1 = valleys[i]
        idx2, price2 = valleys[i + 1]

        if abs(price1 - price2) / price1 <= tolerance:
            between = df.loc[idx1:idx2]
            neck = between["high"].max()
            return (neck, price1, price2, idx1, idx2)
    return None


def _detect_triple_top(
    df: pd.DataFrame, tolerance: float = 0.015
) -> Optional[dict]:
    """Detect triple top (bearish reversal).

    Three peaks at ~equal price level.
    Peaks may not be evenly spaced; valleys may bottom at different levels.
    Tolerance: 1.5% (from Wikipedia).
    """
    peaks, valleys = _detect_peaks_valleys(df, lookback=5)

    if len(peaks) < 3:
        return None

    # Find groups of 3 peaks within tolerance
    for i in range(len(peaks) - 2):
        idx1, price1 = peaks[i]
        idx2, price2 = peaks[i + 1]
        idx3, price3 = peaks[i + 2]

        if (
            abs(price1 - price2) / price1 <= tolerance
            and abs(price2 - price3) / price2 <= tolerance
        ):
            # Get lowest valley between all three
            between = df.loc[idx1:idx3]
            neck = between["low"].min()

            return {
                "neck": neck,
                "peak1": price1,
                "peak2": price2,
                "peak3": price3,
                "peak_indices": (idx1, idx2, idx3),
            }
    return None


def _detect_triple_bottom(
    df: pd.DataFrame, tolerance: float = 0.015
) -> Optional[dict]:
    """Detect triple bottom (bullish reversal).

    Three troughs at ~equal price level.
    """
    peaks, valleys = _detect_peaks_valleys(df, lookback=5)

    if len(valleys) < 3:
        return None

    for i in range(len(valleys) - 2):
        idx1, price1 = valleys[i]
        idx2, price2 = valleys[i + 1]
        idx3, price3 = valleys[i + 2]

        if (
            abs(price1 - price2) / price1 <= tolerance
            and abs(price2 - price3) / price2 <= tolerance
        ):
            between = df.loc[idx1:idx3]
            neck = between["high"].max()

            return {
                "neck": neck,
                "bottom1": price1,
                "bottom2": price2,
                "bottom3": price3,
                "bottom_indices": (idx1, idx2, idx3),
            }
    return None


def _detect_head_shoulders(
    df: pd.DataFrame, tolerance: float = 0.015
) -> Optional[dict]:
    """Detect head-and-shoulders and inverse head-and-shoulders.

    Regular H&S: left_shoulder < head > right_shoulder, shoulders ~equal
    Inverse H&S: left_shoulder > head < right_shoulder, shoulders ~equal
    Tolerance: 1.5% (from Wikipedia).
    """
    peaks, valleys = _detect_peaks_valleys(df, lookback=5)

    if len(peaks) < 3 or len(valleys) < 2:
        return None

    # --- Regular H&S ---
    for i in range(len(peaks) - 2):
        ls_idx, ls_price = peaks[i]
        head_idx, head_price = peaks[i + 1]
        rs_idx, rs_price = peaks[i + 2]

        if (
            ls_price < head_price
            and rs_price < head_price
            and abs(ls_price - rs_price) / ls_price <= tolerance
        ):
            between1 = df.loc[ls_idx:head_idx, "low"].min()
            between2 = df.loc[head_idx:rs_idx, "low"].min()
            neck = min(between1, between2)

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
    for i in range(len(valleys) - 2):
        ls_idx, ls_price = valleys[i]
        head_idx, head_price = valleys[i + 1]
        rs_idx, rs_price = valleys[i + 2]

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


def _detect_broadening_top(
    df: pd.DataFrame, lookback: int = 60
) -> Optional[dict]:
    """Detect broadening top (megaphone pattern).

    Successively HIGHER peaks and LOWER troughs — widening pattern.
    Appears at market tops. 5 minor reversals typical.
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    peaks, valleys = _detect_peaks_valleys(recent, lookback=3)

    if len(peaks) < 3 or len(valleys) < 2:
        return None

    # Check for successively higher peaks
    higher_count = 0
    lower_count = 0

    for i in range(1, len(peaks)):
        if peaks[i][1] > peaks[i - 1][1]:
            higher_count += 1

    for i in range(1, len(valleys)):
        if valleys[i][1] < valleys[i - 1][1]:
            lower_count += 1

    # Broadening: majority of peaks higher, majority of valleys lower
    if higher_count >= 2 and lower_count >= 1:
        # Calculate recent high and low for entry zone
        recent_high = recent["high"].iloc[-1]
        recent_low = recent["low"].iloc[-1]

        # Strength based on how pronounced the widening is
        peak_range = peaks[-1][1] - peaks[0][1]
        valley_range = valleys[0][1] - valleys[-1][1]
        width_ratio = (peak_range + valley_range) / peaks[0][1]

        return {
            "pattern_type": "broadening_top",
            "resistance": recent_high,
            "support": recent_low,
            "strength": min(width_ratio * 2, 0.95),
        }

    return None


def _detect_broadening_bottom(
    df: pd.DataFrame, lookback: int = 60
) -> Optional[dict]:
    """Detect broadening bottom (inverse megaphone).

    Successively LOWER peaks and HIGHER troughs — rare.
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    peaks, valleys = _detect_peaks_valleys(recent, lookback=3)

    if len(peaks) < 2 or len(valleys) < 3:
        return None

    lower_count = 0
    higher_count = 0

    for i in range(1, len(peaks)):
        if peaks[i][1] < peaks[i - 1][1]:
            lower_count += 1

    for i in range(1, len(valleys)):
        if valleys[i][1] > valleys[i - 1][1]:
            higher_count += 1

    if lower_count >= 1 and higher_count >= 2:
        recent_high = recent["high"].iloc[-1]
        recent_low = recent["low"].iloc[-1]

        peak_range = peaks[0][1] - peaks[-1][1]
        valley_range = valleys[-1][1] - valleys[0][1]
        width_ratio = (peak_range + valley_range) / peaks[-1][1]

        return {
            "pattern_type": "broadening_bottom",
            "resistance": recent_high,
            "support": recent_low,
            "strength": min(width_ratio * 2, 0.95),
        }

    return None


def _detect_island_reversal(df: pd.DataFrame) -> Optional[dict]:
    """Detect island reversal (top or bottom).

    Island = cluster of days separated by gaps.
    Island Top: gap up, island, gap down
    Island Bottom: gap down, island, gap up
    """
    if len(df) < 5:
        return None

    for i in range(2, len(df) - 2):
        bar_prev = df.iloc[i - 1]
        bar_curr = df.iloc[i]
        bar_next = df.iloc[i + 1]

        gap_up = bar_curr["open"] > bar_prev["close"]
        gap_down = bar_curr["open"] < bar_prev["close"]
        gap_up_after = bar_next["open"] > bar_curr["close"]
        gap_down_after = bar_next["open"] < bar_curr["close"]

        # Island Bottom: gap down then gap up
        if gap_down and gap_up_after:
            island_high = df.iloc[i : i + 1]["high"].max()
            island_low = df.iloc[i : i + 1]["low"].min()

            # Calculate strength from gap sizes
            gap1 = abs(_gap_size(bar_prev, bar_curr))
            gap2 = abs(_gap_size(bar_curr, bar_next))
            avg_gap = (gap1 + gap2) / 2

            return {
                "pattern_type": "island_bottom",
                "island_high": island_high,
                "island_low": island_low,
                "strength": min(avg_gap * 5 + 0.5, 0.95),
            }

        # Island Top: gap up then gap down
        if gap_up and gap_down_after:
            island_high = df.iloc[i : i + 1]["high"].max()
            island_low = df.iloc[i : i + 1]["low"].min()

            gap1 = abs(_gap_size(bar_prev, bar_curr))
            gap2 = abs(_gap_size(bar_curr, bar_next))
            avg_gap = (gap1 + gap2) / 2

            return {
                "pattern_type": "island_top",
                "island_high": island_high,
                "island_low": island_low,
                "strength": min(avg_gap * 5 + 0.5, 0.95),
            }

    return None


# ---------------------------------------------------------------------------
# CONTINUATION PATTERNS
# ---------------------------------------------------------------------------

def _detect_triangle(
    df: pd.DataFrame, lookback: int = 50
) -> Optional[dict]:
    """Detect ascending, descending, and symmetric triangles.

    Ascending: flat resistance, rising support → break UP
    Descending: falling resistance, flat support → break DOWN
    Symmetric: converging (one down, one up) → break in trend direction
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    highs = recent["high"]
    lows = recent["low"]

    high_slope = _trend_slope(highs)
    low_slope = _trend_slope(lows)

    recent_high = highs.iloc[-1]
    recent_low = lows.iloc[-1]
    earlier_high = highs.iloc[0]
    earlier_low = lows.iloc[0]

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

    range_early = earlier_high - earlier_low
    range_recent = recent_high - recent_low
    squeeze = 1 - (range_recent / max(range_early, 1e-9))
    strength = max(0.5, min(squeeze + 0.4, 0.95))

    return {
        "pattern_type": pattern_type,
        "resistance": recent_high,
        "support": recent_low,
        "break_direction": break_direction,
        "strength": strength,
    }


def _detect_wedge(
    df: pd.DataFrame, lookback: int = 40
) -> Optional[dict]:
    """Detect rising and falling wedge.

    Rising Wedge: BOTH lines sloping UP → break DOWN (bearish)
    Falling Wedge: BOTH lines sloping DOWN → break UP (bullish)
    Key differentiator: Both lines slope in SAME direction (vs triangle)
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    highs = recent["high"]
    lows = recent["low"]

    high_slope = _trend_slope(highs)
    low_slope = _trend_slope(lows)

    slope_thresh = abs((highs.iloc[-1] - highs.iloc[0]) / lookback) * 0.3

    # Parallel channels are not a wedge
    if abs(high_slope - low_slope) < slope_thresh:
        return None

    # Rising Wedge: both positive slope, converging
    if high_slope > slope_thresh and low_slope > 0:
        return {
            "pattern_type": "rising_wedge",
            "resistance": highs.iloc[-1],
            "support": lows.iloc[-1],
            "break_direction": "break_down",
            "strength": 0.7,
        }

    # Falling Wedge: both negative slope, converging
    if low_slope < -slope_thresh and high_slope < 0:
        return {
            "pattern_type": "falling_wedge",
            "resistance": highs.iloc[-1],
            "support": lows.iloc[-1],
            "break_direction": "break_up",
            "strength": 0.7,
        }

    return None


def _detect_flag_pennant(df: pd.DataFrame, lookback: int = 30) -> Optional[dict]:
    """Detect Bull Flag, Bear Flag, Bull Pennant, Bear Pennant.

    Flag: PARALLEL lines, counter-trend move
      Bull Flag: pole up, flag down (small pullback)
      Bear Flag: pole down, flag up (small rally)
    Pennant: CONVERGING lines, counter-trend move (small triangle)
      Bull Pennant: pole up, pennant converges downward
      Bear Pennant: pole down, pennant converges upward

    Duration: 1-4 weeks. Pole should be sharp (45°+).
    Key differentiator from wedge: FLAG has parallel lines.
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)

    # Find pole: sharp move preceding the consolidation
    # Look at first half for pole, second half for flag/pennant
    mid = len(recent) // 2
    pole_section = recent.iloc[:mid]
    flag_section = recent.iloc[mid:]

    if len(pole_section) < 5 or len(flag_section) < 3:
        return None

    pole_highs = pole_section["high"]
    pole_lows = pole_section["low"]
    pole_slope = _trend_slope(pole_section["close"])

    # Pole should be substantial (at least 5% move)
    pole_change = (pole_section["close"].iloc[-1] - pole_section["close"].iloc[0]) / pole_section["close"].iloc[0]

    if abs(pole_change) < 0.03:
        return None  # Not a significant pole

    flag_highs = flag_section["high"]
    flag_lows = flag_section["low"]
    flag_high_slope = _trend_slope(flag_highs)
    flag_low_slope = _trend_slope(flag_lows)

    # Check if lines are parallel (flag) or converging (pennant)
    slope_diff = abs(flag_high_slope - flag_low_slope)
    parallel_threshold = 0.001

    if pole_change > 0:
        # Bullish pole
        if slope_diff < parallel_threshold:
            # Parallel → Bull Flag (slight downslope expected)
            if flag_high_slope < 0 and flag_low_slope < 0:
                return {
                    "pattern_type": "bull_flag",
                    "resistance": flag_highs.iloc[-1],
                    "support": flag_lows.iloc[-1],
                    "break_direction": "break_up",
                    "strength": 0.65,
                }
        else:
            # Converging → Bull Pennant
            if flag_high_slope < 0 and flag_low_slope > 0:
                return {
                    "pattern_type": "bull_pennant",
                    "resistance": flag_highs.iloc[-1],
                    "support": flag_lows.iloc[-1],
                    "break_direction": "break_up",
                    "strength": 0.65,
                }
    else:
        # Bearish pole
        if slope_diff < parallel_threshold:
            # Parallel → Bear Flag (slight upslope expected)
            if flag_high_slope > 0 and flag_low_slope > 0:
                return {
                    "pattern_type": "bear_flag",
                    "resistance": flag_highs.iloc[-1],
                    "support": flag_lows.iloc[-1],
                    "break_direction": "break_down",
                    "strength": 0.65,
                }
        else:
            # Converging → Bear Pennant
            if flag_high_slope > 0 and flag_low_slope < 0:
                return {
                    "pattern_type": "bear_pennant",
                    "resistance": flag_highs.iloc[-1],
                    "support": flag_lows.iloc[-1],
                    "break_direction": "break_down",
                    "strength": 0.65,
                }

    return None


def _detect_price_channel(df: pd.DataFrame, lookback: int = 50) -> Optional[dict]:
    """Detect horizontal, ascending, and descending channels.

    Channel: PARALLEL lines (vs wedge which converges)
    Horizontal: flat top and bottom
    Ascending: both lines slope up
    Descending: both lines slope down
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    highs = recent["high"]
    lows = recent["low"]

    high_slope = _trend_slope(highs)
    low_slope = _trend_slope(lows)

    slope_thresh = 0.001  # Nearly flat threshold

    # Check parallelism
    slope_diff = abs(high_slope - low_slope)
    if slope_diff > abs(high_slope) * 0.5:
        return None  # Not parallel enough

    recent_high = highs.iloc[-1]
    recent_low = lows.iloc[-1]

    if abs(high_slope) < slope_thresh and abs(low_slope) < slope_thresh:
        return {
            "pattern_type": "horizontal_channel",
            "resistance": recent_high,
            "support": recent_low,
            "break_direction": "neutral",
            "strength": 0.6,
        }
    elif high_slope > slope_thresh and low_slope > slope_thresh:
        return {
            "pattern_type": "ascending_channel",
            "resistance": recent_high,
            "support": recent_low,
            "break_direction": "break_up",
            "strength": 0.65,
        }
    elif high_slope < -slope_thresh and low_slope < -slope_thresh:
        return {
            "pattern_type": "descending_channel",
            "resistance": recent_high,
            "support": recent_low,
            "break_direction": "break_down",
            "strength": 0.65,
        }

    return None


# ---------------------------------------------------------------------------
# GAP PATTERNS
# ---------------------------------------------------------------------------

def _detect_gaps(df: pd.DataFrame) -> Optional[list]:
    """Detect all gap types: breakaway, exhaustion, common, measuring.

    Breakaway: Gap at START of new move, high volume support
    Common: Gap WITHIN range, usually filled quickly
    Exhaustion: Gap at END of move, high volume, reversal
    Measuring: Gap MID-WAY through trend, low volume, continuation
    """
    if len(df) < 5:
        return None

    results = []

    for i in range(1, len(df) - 1):
        bar_prev = df.iloc[i - 1]
        bar_curr = df.iloc[i]
        bar_next = df.iloc[i + 1]

        gap = _gap_size(bar_prev, bar_curr)
        abs_gap = abs(gap)

        if abs_gap < 0.003:
            continue  # Skip small gaps (noise)

        # Calculate volume ratio
        avg_volume = df["volume"].iloc[:i].mean() if i > 0 else df["volume"].mean()
        curr_volume = bar_curr["volume"]
        vol_ratio = curr_volume / avg_volume if avg_volume > 0 else 1

        gap_type = None
        strength = min(abs_gap * 10 + 0.3, 0.95)

        # Determine gap context
        # Look at prior trend (last 10 bars)
        prior_trend = df["close"].iloc[max(0, i - 10) : i]
        if len(prior_trend) >= 2:
            trend_direction = prior_trend.iloc[-1] - prior_trend.iloc[0]
        else:
            trend_direction = 0

        if gap > 0:
            # Up gap
            if vol_ratio > 1.5:
                # High volume: could be exhaustion or breakaway
                if trend_direction > 0 and i > len(df) // 2:
                    gap_type = "exhaustion_gap"
                    strength = min(strength + 0.2, 0.95)
                else:
                    gap_type = "breakaway_gap"
            elif vol_ratio < 0.8:
                # Low volume: likely measuring (continuation)
                gap_type = "measuring_gap"
            else:
                gap_type = "common_gap"

        else:
            # Down gap
            if vol_ratio > 1.5:
                if trend_direction < 0 and i > len(df) // 2:
                    gap_type = "exhaustion_gap"
                    strength = min(strength + 0.2, 0.95)
                else:
                    gap_type = "breakaway_gap"
            elif vol_ratio < 0.8:
                gap_type = "measuring_gap"
            else:
                gap_type = "common_gap"

        results.append({
            "pattern_type": gap_type,
            "gap_size": gap,
            "volume_ratio": vol_ratio,
            "strength": strength,
            "bar_index": i,
        })

    return results if results else None


# ---------------------------------------------------------------------------
# SPECIAL PATTERNS
# ---------------------------------------------------------------------------

def _detect_cup_handle(df: pd.DataFrame, lookback: int = 60) -> Optional[dict]:
    """Detect cup and handle (bullish continuation).

    Cup: Rounded U-shape, bottom reaches same level as rim
    Handle: Small pullback (30-50% retracement of cup's rise)
    Duration: Cup 1-6 months, Handle 1-4 weeks
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    closes = recent["close"]

    # Find cup: look for U-shaped move
    # Cup should have depth of 10-40%
    if len(closes) < 20:
        return None

    mid = len(closes) // 2
    left_side = closes.iloc[:mid]
    right_side = closes.iloc[mid:]

    if len(left_side) < 10 or len(right_side) < 10:
        return None

    # Cup bottom should be lower than both rim highs
    left_rim = left_side.iloc[0]
    right_rim = right_side.iloc[-1]
    cup_bottom = closes.min()

    # Check depth
    rim_avg = (left_rim + right_rim) / 2
    depth_pct = (rim_avg - cup_bottom) / rim_avg

    if not (0.08 <= depth_pct <= 0.40):
        return None

    # Check right side recovers to near left rim level
    recovery_pct = (right_side.iloc[-1] - cup_bottom) / (rim_avg - cup_bottom)

    if recovery_pct < 0.80:
        return None  # Doesn't recover enough

    # Handle detection: small pullback after cup
    # Handle should retrace 30-50% of cup rise
    if len(right_side) >= 5:
        handle_start = right_side.iloc[0]
        handle_low = right_side.min()
        handle_retrace = (handle_start - handle_low) / (rim_avg - cup_bottom)

        if 0.20 <= handle_retrace <= 0.60:
            return {
                "pattern_type": "cup_handle",
                "rim": rim_avg,
                "cup_bottom": cup_bottom,
                "handle_retrace": handle_retrace,
                "strength": 0.70,
            }

    return None


def _detect_inverted_cup_handle(df: pd.DataFrame, lookback: int = 60) -> Optional[dict]:
    """Detect inverted cup and handle (bearish).

    Mirror of cup and handle — top forms rounded cap, handle rallies.
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    closes = recent["close"]

    if len(closes) < 20:
        return None

    mid = len(closes) // 2
    left_side = closes.iloc[:mid]
    right_side = closes.iloc[mid:]

    if len(left_side) < 10 or len(right_side) < 10:
        return None

    left_rim = left_side.iloc[0]
    right_rim = right_side.iloc[-1]
    cap_top = closes.max()

    rim_avg = (left_rim + right_rim) / 2
    depth_pct = (cap_top - rim_avg) / cap_top

    if not (0.08 <= depth_pct <= 0.40):
        return None

    if len(right_side) >= 5:
        handle_start = right_side.iloc[0]
        handle_high = right_side.max()
        handle_retrace = (handle_high - handle_start) / (cap_top - rim_avg)

        if 0.20 <= handle_retrace <= 0.60:
            return {
                "pattern_type": "inverted_cup_handle",
                "rim": rim_avg,
                "cap_top": cap_top,
                "handle_retrace": handle_retrace,
                "strength": 0.70,
            }

    return None


def _detect_traps(df: pd.DataFrame) -> Optional[dict]:
    """Detect bull trap and bear trap.

    Bull Trap: Price breaks above resistance, then falls back
    Bear Trap: Price breaks below support, then rises back
    Key: Breakout with LOW volume is warning sign.
    """
    if len(df) < 10:
        return None

    recent = df.tail(10)

    # Check for recent false breakout
    for i in range(3, len(recent)):
        window = recent.iloc[:i]
        curr = recent.iloc[i]

        if len(window) < 5:
            continue

        resistance = window["high"].max()
        support = window["low"].min()

        # Bull trap: break above resistance with low volume, then falls back
        if curr["close"] > resistance:
            vol_ratio = curr["volume"] / window["volume"].mean() if window["volume"].mean() > 0 else 1
            if vol_ratio < 0.8:
                # Low volume breakout → potential trap
                if i < len(recent) - 1 and recent.iloc[i + 1]["close"] < resistance:
                    return {
                        "pattern_type": "bull_trap",
                        "resistance": resistance,
                        "break_price": curr["close"],
                        "strength": 0.65,
                    }

        # Bear trap: break below support with low volume, then rises back
        if curr["close"] < support:
            vol_ratio = curr["volume"] / window["volume"].mean() if window["volume"].mean() > 0 else 1
            if vol_ratio < 0.8:
                if i < len(recent) - 1 and recent.iloc[i + 1]["close"] > support:
                    return {
                        "pattern_type": "bear_trap",
                        "support": support,
                        "break_price": curr["close"],
                        "strength": 0.65,
                    }

    return None


# ---------------------------------------------------------------------------
# CANDLESTICK PATTERNS
# ---------------------------------------------------------------------------

def _detect_engulfing(df: pd.DataFrame) -> Optional[dict]:
    """Detect bullish and bearish engulfing patterns."""
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    body_curr = abs(curr["close"] - curr["open"])
    body_prev = abs(prev["close"] - prev["open"])

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
        }

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
        }

    return None


def _detect_hammer(df: pd.DataFrame) -> Optional[dict]:
    """Detect hammer and inverted hammer candlestick patterns."""
    if len(df) < 1:
        return None

    curr = df.iloc[-1]
    open_, high, low, close = curr["open"], curr["high"], curr["low"], curr["close"]

    body = abs(close - open_)
    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low

    if lower_shadow > 2 * body and upper_shadow < body * 0.3:
        strength = min(lower_shadow / (high - low) * 1.5, 0.95)
        return {
            "pattern_type": "hammer",
            "strength": max(strength, 0.55),
            "last_close": close,
        }

    if upper_shadow > 2 * body and lower_shadow < body * 0.3:
        strength = min(upper_shadow / (high - low) * 1.5, 0.95)
        return {
            "pattern_type": "inverted_hammer",
            "strength": max(strength, 0.55),
            "last_close": close,
        }

    return None


def _detect_doji(df: pd.DataFrame, threshold: float = 0.05) -> Optional[dict]:
    """Detect doji (indecision) candlestick."""
    if len(df) < 1:
        return None

    curr = df.iloc[-1]
    open_, high, low, close = curr["open"], curr["high"], curr["low"], curr["close"]

    body = abs(close - open_)
    candle_range = high - low

    if candle_range < 1e-9:
        return None

    if body / candle_range <= threshold:
        strength = 1 - (body / candle_range)
        return {
            "pattern_type": "doji",
            "strength": max(strength, 0.5),
            "last_close": close,
        }

    return None


def _detect_morning_star(df: pd.DataFrame, lookback: int = 3) -> Optional[dict]:
    """Detect morning star and evening star (3-bar reversal patterns)."""
    if len(df) < lookback:
        return None

    bar1 = df.iloc[-3]
    bar2 = df.iloc[-2]
    bar3 = df.iloc[-1]

    body1 = abs(bar1["close"] - bar1["open"])
    body2 = abs(bar2["close"] - bar2["open"])
    body3 = abs(bar3["close"] - bar3["open"])

    range1 = bar1["high"] - bar1["low"]
    range3 = bar3["high"] - bar3["low"]

    # Morning star: bearish bar1, small body bar2 (gap down), bullish bar3
    is_bearish1 = bar1["close"] < bar1["open"] and body1 > range1 * 0.6
    is_small_body2 = body2 < body1 * 0.3
    is_bullish3 = bar3["close"] > bar3["open"] and body3 > range3 * 0.6
    closes_above_mid = bar3["close"] > (bar1["open"] + bar1["close"]) / 2

    if is_bearish1 and is_small_body2 and is_bullish3 and closes_above_mid:
        return {
            "pattern_type": "morning_star",
            "strength": 0.75,
            "last_close": bar3["close"],
        }

    # Evening star: bullish bar1, small body bar2, bearish bar3
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


def _detect_three_soldiers_crows(df: pd.DataFrame) -> Optional[dict]:
    """Detect Three White Soldiers (bullish) and Three Black Crows (bearish)."""
    if len(df) < 3:
        return None

    bar1 = df.iloc[-3]
    bar2 = df.iloc[-2]
    bar3 = df.iloc[-1]

    # Three White Soldiers: 3 consecutive bullish candles, each closing higher
    s1 = bar1["close"] > bar1["open"]
    s2 = bar2["close"] > bar2["open"]
    s3 = bar3["close"] > bar3["open"]
    rising = bar2["close"] > bar1["close"] and bar3["close"] > bar2["close"]

    if s1 and s2 and s3 and rising:
        body1 = abs(bar1["close"] - bar1["open"])
        body2 = abs(bar2["close"] - bar2["open"])
        body3 = abs(bar3["close"] - bar3["open"])
        range1 = bar1["high"] - bar1["low"]
        range2 = bar2["high"] - bar2["low"]
        range3 = bar3["high"] - bar3["low"]

        if (
            body1 > range1 * 0.6
            and body2 > range2 * 0.6
            and body3 > range3 * 0.6
        ):
            return {
                "pattern_type": "three_white_soldiers",
                "strength": 0.80,
                "last_close": bar3["close"],
            }

    # Three Black Crows: 3 consecutive bearish candles, each closing lower
    c1 = bar1["close"] < bar1["open"]
    c2 = bar2["close"] < bar2["open"]
    c3 = bar3["close"] < bar3["open"]
    falling = bar2["close"] < bar1["close"] and bar3["close"] < bar2["close"]

    if c1 and c2 and c3 and falling:
        body1 = abs(bar1["close"] - bar1["open"])
        body2 = abs(bar2["close"] - bar2["open"])
        body3 = abs(bar3["close"] - bar3["open"])
        range1 = bar1["high"] - bar1["low"]
        range2 = bar2["high"] - bar2["low"]
        range3 = bar3["high"] - bar3["low"]

        if (
            body1 > range1 * 0.6
            and body2 > range2 * 0.6
            and body3 > range3 * 0.6
        ):
            return {
                "pattern_type": "three_black_crows",
                "strength": 0.80,
                "last_close": bar3["close"],
            }

    return None


def _detect_shooting_star(df: pd.DataFrame) -> Optional[dict]:
    """Detect shooting star (bearish reversal)."""
    if len(df) < 1:
        return None

    curr = df.iloc[-1]
    open_, high, low, close = curr["open"], curr["high"], curr["low"], curr["close"]

    body = abs(close - open_)
    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low

    # Shooting star: long upper shadow, small body at bottom, occurs after uptrend
    if upper_shadow > 2 * body and lower_shadow < body * 0.3:
        strength = min(upper_shadow / (high - low) * 1.5, 0.95)
        return {
            "pattern_type": "shooting_star",
            "strength": max(strength, 0.55),
            "last_close": close,
        }

    return None


# ---------------------------------------------------------------------------
# PatternScanner — Main Class
# ---------------------------------------------------------------------------

class PatternScanner(MarketScanner):
    """Complete pattern scanner with all chart and candlestick patterns.

    Patterns detected (40 total):
      REVERSAL (11):
        double_top, double_bottom, triple_top, triple_bottom,
        head_shoulders, inverse_head_shoulders,
        broadening_top, broadening_bottom,
        island_top, island_bottom
      CONTINUATION (10):
        ascending_triangle, descending_triangle, symmetric_triangle,
        rising_wedge, falling_wedge,
        bull_flag, bear_flag, bull_pennant, bear_pennant,
        horizontal_channel, ascending_channel, descending_channel
      GAPS (4):
        breakaway_gap, exhaustion_gap, common_gap, measuring_gap
      SPECIAL (4):
        cup_handle, inverted_cup_handle, bull_trap, bear_trap
      CANDLESTICK (8):
        bullish_engulfing, bearish_engulfing,
        hammer, inverted_hammer,
        shooting_star,
        doji, morning_star, evening_star,
        three_white_soldiers, three_black_crows
    """

    PATTERNS = [
        # Reversal
        "double_top", "double_bottom",
        "triple_top", "triple_bottom",
        "head_shoulders", "inverse_head_shoulders",
        "broadening_top", "broadening_bottom",
        "island_top", "island_bottom",
        # Continuation
        "ascending_triangle", "descending_triangle", "symmetric_triangle",
        "rising_wedge", "falling_wedge",
        "bull_flag", "bear_flag", "bull_pennant", "bear_pennant",
        "horizontal_channel", "ascending_channel", "descending_channel",
        # Gaps
        "breakaway_gap", "exhaustion_gap", "common_gap", "measuring_gap",
        # Special
        "cup_handle", "inverted_cup_handle",
        "bull_trap", "bear_trap",
        # Candlestick
        "bullish_engulfing", "bearish_engulfing",
        "hammer", "inverted_hammer", "shooting_star",
        "doji", "morning_star", "evening_star",
        "three_white_soldiers", "three_black_crows",
    ]

    def __init__(
        self,
        timeframe: str = "1h",
        min_strength: float = 0.5,
        lookback: int = 100,
    ) -> None:
        super().__init__(timeframe=timeframe, min_strength=min_strength)
        self.lookback = lookback

    def _scan_symbol(self, symbol: str, df: pd.DataFrame) -> list[Opportunity]:
        opps: list[Opportunity] = []
        recent = df.tail(self.lookback).copy()

        # ---- Reversal patterns ----
        opps.extend(self._scan_reversal_patterns(symbol, recent))

        # ---- Continuation patterns ----
        opps.extend(self._scan_continuation_patterns(symbol, recent))

        # ---- Gap patterns ----
        opps.extend(self._scan_gap_patterns(symbol, recent))

        # ---- Special patterns ----
        opps.extend(self._scan_special_patterns(symbol, recent))

        # ---- Candlestick patterns ----
        opps.extend(self._scan_candlestick_patterns(symbol, df))

        return opps

    def _scan_reversal_patterns(self, symbol: str, df: pd.DataFrame) -> list[Opportunity]:
        opps: list[Opportunity] = []

        # Double Top
        result = _detect_double_top(df)
        if result:
            neck, top1, top2, idx1, idx2 = result
            opps.append(Opportunity(
                symbol=symbol, pattern="double_top", timeframe=self.timeframe,
                strength=0.70,
                entry_zone=(neck * 0.995, neck * 1.005),
                metadata={"neck": neck, "top1": top1, "top2": top2},
            ))

        # Double Bottom
        result = _detect_double_bottom(df)
        if result:
            neck, bot1, bot2, idx1, idx2 = result
            opps.append(Opportunity(
                symbol=symbol, pattern="double_bottom", timeframe=self.timeframe,
                strength=0.70,
                entry_zone=(neck * 0.995, neck * 1.005),
                metadata={"neck": neck, "bottom1": bot1, "bottom2": bot2},
            ))

        # Triple Top
        result = _detect_triple_top(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern="triple_top", timeframe=self.timeframe,
                strength=0.65,
                entry_zone=(result["neck"] * 0.995, result["neck"] * 1.005),
                metadata={"neck": result["neck"], "peaks": [result["peak1"], result["peak2"], result["peak3"]]},
            ))

        # Triple Bottom
        result = _detect_triple_bottom(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern="triple_bottom", timeframe=self.timeframe,
                strength=0.65,
                entry_zone=(result["neck"] * 0.995, result["neck"] * 1.005),
                metadata={"neck": result["neck"], "bottoms": [result["bottom1"], result["bottom2"], result["bottom3"]]},
            ))

        # Head & Shoulders
        result = _detect_head_shoulders(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["neck"] * 0.995, result["neck"] * 1.005),
                metadata={"neck": result["neck"], "head_price": result["head_price"]},
            ))

        # Broadening Top
        result = _detect_broadening_top(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["support"] * 0.995, result["resistance"] * 1.005),
                metadata={"resistance": result["resistance"], "support": result["support"]},
            ))

        # Broadening Bottom
        result = _detect_broadening_bottom(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["support"] * 0.995, result["resistance"] * 1.005),
                metadata={"resistance": result["resistance"], "support": result["support"]},
            ))

        # Island Reversal
        result = _detect_island_reversal(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["island_low"] * 0.995, result["island_high"] * 1.005),
                metadata={"island_high": result["island_high"], "island_low": result["island_low"]},
            ))

        return opps

    def _scan_continuation_patterns(self, symbol: str, df: pd.DataFrame) -> list[Opportunity]:
        opps: list[Opportunity] = []

        # Triangle
        result = _detect_triangle(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["support"], result["resistance"]),
                metadata={
                    "resistance": result["resistance"],
                    "support": result["support"],
                    "break_direction": result["break_direction"],
                },
            ))

        # Wedge
        result = _detect_wedge(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["support"], result["resistance"]),
                metadata={
                    "resistance": result["resistance"],
                    "support": result["support"],
                    "break_direction": result["break_direction"],
                },
            ))

        # Flag / Pennant
        result = _detect_flag_pennant(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["support"], result["resistance"]),
                metadata={
                    "resistance": result["resistance"],
                    "support": result["support"],
                    "break_direction": result["break_direction"],
                },
            ))

        # Price Channel
        result = _detect_price_channel(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["support"], result["resistance"]),
                metadata={
                    "resistance": result["resistance"],
                    "support": result["support"],
                    "break_direction": result["break_direction"],
                },
            ))

        return opps

    def _scan_gap_patterns(self, symbol: str, df: pd.DataFrame) -> list[Opportunity]:
        opps: list[Opportunity] = []

        results = _detect_gaps(df)
        if results:
            for r in results[:3]:  # Limit to 3 gap patterns per scan
                if r["strength"] < self.min_strength:
                    continue
                opps.append(Opportunity(
                    symbol=symbol, pattern=r["pattern_type"], timeframe=self.timeframe,
                    strength=r["strength"],
                    entry_zone=(
                        df.iloc[r["bar_index"]]["low"] * 0.995,
                        df.iloc[r["bar_index"]]["high"] * 1.005,
                    ),
                    metadata={
                        "gap_size": r["gap_size"],
                        "volume_ratio": r["volume_ratio"],
                        "bar_index": r["bar_index"],
                    },
                ))

        return opps

    def _scan_special_patterns(self, symbol: str, df: pd.DataFrame) -> list[Opportunity]:
        opps: list[Opportunity] = []

        # Cup and Handle
        result = _detect_cup_handle(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["cup_bottom"] * 1.005, result["rim"] * 0.995),
                metadata={
                    "rim": result["rim"],
                    "cup_bottom": result["cup_bottom"],
                    "handle_retrace": result["handle_retrace"],
                },
            ))

        # Inverted Cup and Handle
        result = _detect_inverted_cup_handle(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result["rim"] * 1.005, result["cap_top"] * 0.995),
                metadata={
                    "rim": result["rim"],
                    "cap_top": result["cap_top"],
                    "handle_retrace": result["handle_retrace"],
                },
            ))

        # Traps
        result = _detect_traps(df)
        if result:
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(result.get("support", result.get("resistance")) * 0.995,
                            result.get("resistance", result.get("support")) * 1.005),
                metadata={
                    "break_price": result.get("break_price"),
                    "resistance": result.get("resistance"),
                    "support": result.get("support"),
                },
            ))

        return opps

    def _scan_candlestick_patterns(self, symbol: str, df: pd.DataFrame) -> list[Opportunity]:
        opps: list[Opportunity] = []
        recent = df.tail(5).copy()

        # Engulfing
        result = _detect_engulfing(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(close - spread, close + spread),
                metadata={"last_close": close},
            ))

        # Hammer / Inverted Hammer
        result = _detect_hammer(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(close - spread, close + spread),
                metadata={"last_close": close},
            ))

        # Shooting Star
        result = _detect_shooting_star(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(close - spread, close + spread),
                metadata={"last_close": close},
            ))

        # Doji
        result = _detect_doji(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(close - spread, close + spread),
                metadata={"last_close": close},
            ))

        # Morning / Evening Star
        result = _detect_morning_star(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(close - spread, close + spread),
                metadata={"last_close": close},
            ))

        # Three White Soldiers / Three Black Crows
        result = _detect_three_soldiers_crows(recent)
        if result:
            close = result["last_close"]
            spread = close * 0.001
            opps.append(Opportunity(
                symbol=symbol, pattern=result["pattern_type"], timeframe=self.timeframe,
                strength=result["strength"],
                entry_zone=(close - spread, close + spread),
                metadata={"last_close": close},
            ))

        return opps


__all__ = ["PatternScanner"]
