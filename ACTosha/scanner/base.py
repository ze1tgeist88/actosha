"""Scanner base class and Opportunity dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class Opportunity:
    """Represents a detected trading opportunity.

    Attributes
    ----------
    symbol : str
        Trading pair symbol, e.g. "BTC/USDT".
    pattern : str
        Human-readable pattern name, e.g. "double_bottom", "rsi_oversold".
    timeframe : str
        OHLCV timeframe the opportunity was detected on, e.g. "1h", "4h".
    strength : float
        Confidence score in range [0.0, 1.0].
    entry_zone : tuple[float, float]
        (lower_bound, upper_bound) price zone for potential entry.
    metadata : dict[str, Any]
        Additional context (indicator values, pattern details, etc.).
    """

    symbol: str
    pattern: str
    timeframe: str
    strength: float
    entry_zone: tuple[float, float]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0, 1], got {self.strength}")
        if self.entry_zone[0] > self.entry_zone[1]:
            raise ValueError(
                f"entry_zone lower > upper: {self.entry_zone}"
            )


class MarketScanner:
    """Base class for all market scanners.

    Subclasses must implement ``_scan_symbol`` which receives a single
    symbol's pre-processed DataFrame and returns a list of Opportunities.

    Parameters
    ----------
    timeframe : str
        OHLCV timeframe to scan (e.g. "1m", "5m", "1h", "4h", "1d").
    min_strength : float
        Minimum ``strength`` required to include an opportunity in results.
        Default: 0.5.
    """

    # Override in subclass with the concrete pattern names this scanner detects.
    PATTERNS: list[str] = []

    def __init__(self, timeframe: str = "1h", min_strength: float = 0.5) -> None:
        self.timeframe = timeframe
        self.min_strength = min_strength

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_all(self, symbols: list[str], data_map: dict[str, pd.DataFrame]) -> list[Opportunity]:
        """Scan all symbols for any detectable opportunity.

        Parameters
        ----------
        symbols : list[str]
            List of trading pair symbols to scan.
        data_map : dict[str, pd.DataFrame]
            Map of symbol → OHLCV DataFrame. Each DataFrame must contain
            columns: timestamp, open, high, low, close, volume.

        Returns
        -------
        list[Opportunity]
            All opportunities across symbols with ``strength >= min_strength``.
        """
        opportunities: list[Opportunity] = []
        for symbol in symbols:
            df = data_map.get(symbol)
            if df is None or len(df) < 20:
                continue
            opportunities.extend(self._scan_symbol(symbol, df))
        return [o for o in opportunities if o.strength >= self.min_strength]

    def scan_for_pattern(
        self,
        pattern: str,
        symbols: list[str],
        data_map: dict[str, pd.DataFrame],
    ) -> list[Opportunity]:
        """Scan for a specific pattern type.

        Raises ValueError if ``pattern`` is not in ``PATTERNS``.
        """
        if pattern not in self.PATTERNS:
            raise ValueError(
                f"Pattern '{pattern}' not supported by {self.__class__.__name__}. "
                f"Supported: {self.PATTERNS}"
            )
        all_opps = self.scan_all(symbols, data_map)
        return [o for o in all_opps if o.pattern == pattern]

    # ------------------------------------------------------------------
    # Abstract interface — override in subclasses
    # ------------------------------------------------------------------

    def _scan_symbol(self, symbol: str, df: pd.DataFrame) -> list[Opportunity]:
        """Scan a single symbol's DataFrame for opportunities.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        df : pd.DataFrame
            Pre-processed OHLCV DataFrame (at least 20 rows).

        Returns
        -------
        list[Opportunity]
            Zero or more detected opportunities.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}._scan_symbol() not implemented"
        )


__all__ = ["MarketScanner", "Opportunity"]
