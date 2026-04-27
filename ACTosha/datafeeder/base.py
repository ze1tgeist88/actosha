"""Abstract base class for exchange data feeds."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

import pandas as pd


class AbstractExchangeFeed(ABC):
    """Abstract base class for exchange data feeders.

    All concrete feed implementations (Hyperliquid, Binance) inherit from this.
    """

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a single symbol.

        Args:
            symbol:     Trading pair symbol (e.g. "BTC/USDT")
            timeframe:  Timeframe string (e.g. "1m", "1h", "1d")
            since:      Unix timestamp in ms, fetch from this point
            limit:      Max number of candles to fetch

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            Index is DatetimeIndex (UTC).
        """
        ...

    @abstractmethod
    def fetch_ohlcv_batch(
        self,
        symbols: list[str],
        timeframe: str = "1h",
        limit: int = 1000,
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for multiple symbols.

        Returns:
            Dict mapping symbol → DataFrame
        """
        ...

    def stream_ohlcv(
        self, symbol: str, timeframe: str = "1h"
    ) -> AsyncIterator[pd.DataFrame]:
        """Stream OHLCV data as an async iterator.

        Default implementation uses polling. Exchanges that support WebSocket
        should override this.
        """
        raise NotImplementedError("Streaming not implemented for this exchange.")