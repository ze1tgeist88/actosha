"""Volume scanner: volume surge detection and volume anomaly signals."""

from __future__ import annotations

import pandas as pd
import numpy as np

from ACTosha.scanner.base import MarketScanner, Opportunity


# ---------------------------------------------------------------------------
# Volume computation helpers
# ---------------------------------------------------------------------------

def _rolling_avg_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Simple moving average of volume over ``period`` bars."""
    return volume.rolling(window=period, min_periods=period).mean()


def _volume_surge_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Return the ratio of current volume to its ``period``-bar average."""
    avg = _rolling_avg_volume(volume, period)
    return volume / avg.replace(0, np.nan)


def _volume_spike_direction(df: pd.DataFrame) -> pd.Series:
    """Return 1 if bar closed higher than open (up), -1 if down."""
    direction = (df["close"] > df["open"]).astype(int) * 2 - 1
    return direction  # 1 = buy volume, -1 = sell volume


def _detect_consecutive_surge(
    surge_ratio: pd.Series, threshold: float = 2.0, consecutive: int = 2
) -> pd.Series:
    """Return True where ``consecutive`` bars in a row exceed ``threshold``."""
    above = surge_ratio >= threshold
    # Count consecutive True values ending at each position
    count = above.astype(int)
    for i in range(1, consecutive):
        count = count + above.shift(i).fillna(0).astype(int)
    return count >= consecutive


def _detect_volume_clamp(
    volume: pd.Series, period: int = 20, z_threshold: float = 3.0
) -> pd.Series:
    """Return True where volume is a statistical outlier (Z-score > z_threshold)."""
    avg = volume.rolling(window=period, min_periods=period).mean()
    std = volume.rolling(window=period, min_periods=period).std()
    z = (volume - avg) / std.replace(0, np.nan)
    return z > z_threshold


def _detect_volume_divergence(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Detect price-volume divergence.

    Returns 1 where price rose but volume fell (bearish divergence),
    -1 where price fell but volume rose (bullish divergence),
    0 otherwise.
    """
    price_change = df["close"].diff()
    vol_change = df["volume"].diff()

    bullish_div = (price_change < 0) & (vol_change > 0)  # price down, vol up
    bearish_div = (price_change > 0) & (vol_change < 0)  # price up, vol down

    result = pd.Series(0, index=df.index)
    result[bullish_div] = -1
    result[bearish_div] = 1
    return result


# ---------------------------------------------------------------------------
# VolumeScanner
# ---------------------------------------------------------------------------

class VolumeScanner(MarketScanner):
    """Scan for volume-based anomalies and signals.

    Signals detected
        - volume_surge          : current volume > surge_multiplier × 20-bar avg
        - volume_surge_consecutive : 2+ consecutive bars with volume surge
        - volume_clamp           : volume Z-score > z_threshold (statistical outlier)
        - volume_divergence_bull : price fell but volume rose
        - volume_divergence_bear : price rose but volume fell
    """

    PATTERNS = [
        "volume_surge",
        "volume_surge_consecutive",
        "volume_clamp",
        "volume_divergence_bull",
        "volume_divergence_bear",
    ]

    def __init__(
        self,
        timeframe: str = "1h",
        min_strength: float = 0.5,
        surge_multiplier: float = 2.0,
        avg_period: int = 20,
        consecutive_bars: int = 2,
        z_threshold: float = 3.0,
    ) -> None:
        """
        Parameters
        ----------
        timeframe : str
            OHLCV timeframe label.
        min_strength : float
            Minimum confidence to return an opportunity.
        surge_multiplier : float
            Multiplier applied to the average volume to define a surge.
        avg_period : int
            Number of bars for the rolling average volume baseline.
        consecutive_bars : int
            Number of consecutive bars that must exceed the surge threshold.
        z_threshold : float
            Z-score threshold for statistical outlier (volume_clamp).
        """
        super().__init__(timeframe=timeframe, min_strength=min_strength)
        self.surge_multiplier = surge_multiplier
        self.avg_period = avg_period
        self.consecutive_bars = consecutive_bars
        self.z_threshold = z_threshold

    def _scan_symbol(
        self, symbol: str, df: pd.DataFrame
    ) -> list[Opportunity]:
        opps: list[Opportunity] = []

        if len(df) < self.avg_period + 5:
            return opps

        volume = df["volume"]
        close = df["close"]

        # Rolling average baseline
        avg_vol = _rolling_avg_volume(volume, self.avg_period)
        surge_ratio = _volume_surge_ratio(volume, self.avg_period)

        # ---- Single-bar volume surge ----
        surge_last = surge_ratio.iloc[-1]
        if surge_last >= self.surge_multiplier:
            # Strength proportional to surge magnitude, capped at 0.95
            strength = min(surge_last / (self.surge_multiplier * 3), 0.95)
            entry_zone = self._entry_zone(close.iloc[-1])
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="volume_surge",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "surge_ratio": round(float(surge_last), 2),
                        "volume_current": round(float(volume.iloc[-1]), 2),
                        "volume_avg": round(float(avg_vol.iloc[-1]), 2),
                        "price": round(float(close.iloc[-1]), 4),
                    },
                )
            )

        # ---- Consecutive volume surges ----
        consecutive_surge = _detect_consecutive_surge(
            surge_ratio, threshold=self.surge_multiplier,
            consecutive=self.consecutive_bars
        )
        if consecutive_surge.iloc[-1]:
            # Average surge over the consecutive bars
            window_surges = surge_ratio.iloc[-(self.consecutive_bars):]
            avg_surge = float(window_surges.mean())
            strength = min(avg_surge / (self.surge_multiplier * 2), 0.95)
            entry_zone = self._entry_zone(close.iloc[-1])
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="volume_surge_consecutive",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.6),
                    entry_zone=entry_zone,
                    metadata={
                        "consecutive_bars": self.consecutive_bars,
                        "avg_surge_ratio": round(avg_surge, 2),
                        "surge_ratios": [round(float(v), 2) for v in window_surges.values],
                        "price": round(float(close.iloc[-1]), 4),
                    },
                )
            )

        # ---- Volume clamp (statistical outlier) ----
        clamp = _detect_volume_clamp(volume, period=self.avg_period, z_threshold=self.z_threshold)
        if clamp.iloc[-1]:
            entry_zone = self._entry_zone(close.iloc[-1])
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="volume_clamp",
                    timeframe=self.timeframe,
                    strength=0.7,
                    entry_zone=entry_zone,
                    metadata={
                        "volume_current": round(float(volume.iloc[-1]), 2),
                        "volume_avg": round(float(avg_vol.iloc[-1]), 2),
                        "z_threshold": self.z_threshold,
                        "price": round(float(close.iloc[-1]), 4),
                    },
                )
            )

        # ---- Price-volume divergence ----
        if len(df) >= self.avg_period + 2:
            divergence = _detect_volume_divergence(df, period=self.avg_period)
            div_last = divergence.iloc[-1]

            if div_last == -1:  # Bullish divergence: price down, volume up
                vol_current = volume.iloc[-1]
                vol_avg = avg_vol.iloc[-1]
                strength = min((vol_current / vol_avg - 1) * 0.5 + 0.5, 0.9)
                entry_zone = self._entry_zone(close.iloc[-1])
                opps.append(
                    Opportunity(
                        symbol=symbol,
                        pattern="volume_divergence_bull",
                        timeframe=self.timeframe,
                        strength=max(float(strength), 0.55),
                        entry_zone=entry_zone,
                        metadata={
                            "volume_current": round(float(vol_current), 2),
                            "volume_avg": round(float(vol_avg), 2),
                            "price": round(float(close.iloc[-1]), 4),
                        },
                    )
                )

            elif div_last == 1:  # Bearish divergence: price up, volume down
                vol_current = volume.iloc[-1]
                vol_avg = avg_vol.iloc[-1]
                strength = min((1 - vol_current / vol_avg) * 0.5 + 0.5, 0.9)
                entry_zone = self._entry_zone(close.iloc[-1])
                opps.append(
                    Opportunity(
                        symbol=symbol,
                        pattern="volume_divergence_bear",
                        timeframe=self.timeframe,
                        strength=max(float(strength), 0.55),
                        entry_zone=entry_zone,
                        metadata={
                            "volume_current": round(float(vol_current), 2),
                            "volume_avg": round(float(vol_avg), 2),
                            "price": round(float(close.iloc[-1]), 4),
                        },
                    )
                )

        return opps

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _entry_zone(price: float, spread_pct: float = 0.002) -> tuple[float, float]:
        """Return a tight entry zone around current price."""
        return (float(price * (1 - spread_pct)), float(price * (1 + spread_pct)))


# ---------------------------------------------------------------------------
# Convenience factory function
# ---------------------------------------------------------------------------

def scan_volume_surge(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str = "1h",
    multiplier: float = 2.0,
    period: int = 20,
) -> list[Opportunity]:
    """Convenience function: scan a single DataFrame for volume surges.

    Equivalent to constructing a ``VolumeScanner`` and calling
    ``scanner.scan_all([symbol], {symbol: df})``.
    """
    scanner = VolumeScanner(
        timeframe=timeframe,
        min_strength=0.5,
        surge_multiplier=multiplier,
        avg_period=period,
    )
    return scanner._scan_symbol(symbol, df)


__all__ = ["VolumeScanner", "scan_volume_surge"]
