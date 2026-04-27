"""Local Parquet cache for OHLCV data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import pandas as pd


class DataCache:
    """Parquet-based OHLCV cache for repeated fast access.

    Storage layout:
        {cache_dir}/{exchange}/{symbol}/{timeframe}.parquet
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = os.environ.get("ACTOSHA_CACHE_DIR", "ACTosha/data/cache")
        self.cache_dir = Path(cache_dir)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def save(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        exchange: str = "unknown",
    ) -> None:
        """Save OHLCV DataFrame to parquet cache.

        Args:
            symbol:     Trading pair symbol (e.g. "BTC/USDT")
            timeframe:  Timeframe string (e.g. "1h")
            df:         DataFrame with timestamp index
            exchange:   Exchange name for directory structure
        """
        path = self._path(exchange, symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, engine="pyarrow", compression="snappy")

    def load(
        self,
        symbol: str,
        timeframe: str,
        exchange: str = "unknown",
        since: pd.Timestamp | None = None,
        until: pd.Timestamp | None = None,
    ) -> pd.DataFrame | None:
        """Load OHLCV DataFrame from cache.

        Args:
            symbol:     Trading pair symbol
            timeframe:  Timeframe string
            exchange:   Exchange name
            since:      Optional start timestamp filter
            until:      Optional end timestamp filter

        Returns:
            DataFrame or None if cache miss
        """
        path = self._path(exchange, symbol, timeframe)
        if not path.exists():
            return None

        df = pd.read_parquet(path)
        df = df.set_index("timestamp")

        if since is not None:
            df = df[df.index >= since]
        if until is not None:
            df = df[df.index <= until]

        return df

    def exists(
        self,
        symbol: str,
        timeframe: str,
        exchange: str = "unknown",
        since: int | None = None,
        until: int | None = None,
    ) -> bool:
        """Check if cached data covers the requested time range."""
        df = self.load(symbol, timeframe, exchange)
        if df is None:
            return False

        if since is not None:
            ts = pd.Timestamp(since, unit="ms", tz="UTC")
            if df.index.min() > ts:
                return False
        if until is not None:
            ts = pd.Timestamp(until, unit="ms", tz="UTC")
            if df.index.max() < ts:
                return False

        return True

    def prune(self, older_than_days: int) -> int:
        """Delete parquet files older than specified days.

        Returns:
            Number of files deleted.
        """
        count = 0
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=older_than_days)
        for path in self.cache_dir.rglob("*.parquet"):
            mtime = pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC")
            if mtime < cutoff:
                path.unlink()
                count += 1
        return count

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------

    def _path(
        self, exchange: str, symbol: str, timeframe: str
    ) -> Path:
        # Normalize symbol for filesystem: BTC/USDT → BTC_USDT
        safe_symbol = symbol.replace("/", "_")
        return self.cache_dir / exchange / safe_symbol / f"{timeframe}.parquet"


__all__ = ["DataCache"]