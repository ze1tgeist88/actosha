"""DataFeeder: Hyperliquid feed submodule — CCXT wrapper for Hyperliquid perpetuals."""

from __future__ import annotations

import time
from typing import AsyncIterator

import pandas as pd

from ACTosha.datafeeder.base import AbstractExchangeFeed
from ACTosha.datafeeder.normalizer import UnifiedOHLCVSchema

try:
    import ccxt
except ImportError as e:
    raise ImportError(
        "ccxt is required for HyperliquidFeed: pip install ccxt>=4.0"
    ) from e


class HyperliquidFeed(AbstractExchangeFeed):
    """Hyperliquid perpetual futures data feeder via CCXT.

    Hyperliquid uses unified symbol format "BTC/USDT:USDT" for perpetuals.
    All data is normalized to UnifiedOHLCVSchema.

    API Reference: https://hyperliquid.gitbook.io/hyperliquid-docs/
    CCXT: https://docs.ccxt.com/#/exchanges/hyperliquid
    """

    MAX_LIMIT_PER_REQUEST = 500  # Hyperliquid max candles per request

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        testnet: bool = False,
        request_timeout: float = 30.0,
    ) -> None:
        """Initialize Hyperliquid exchange feed.

        Args:
            api_key:        Hyperliquid API key (optional for public market data)
            api_secret:     Hyperliquid API secret (optional for public market data)
            testnet:        Use testnet (info.hyperliquid-testnet.xyz)
            request_timeout: Timeout for HTTP requests in seconds.
        """
        self._testnet = testnet
        self._exchange = ccxt.hyperliquid(
            {
                "apiKey": api_key or "",
                "secret": api_secret or "",
                "enableRateLimit": True,
                "timeout": int(request_timeout * 1000),
                "options": {
                    "defaultType": "swap",
                    "defaultMarginMode": "cross",
                },
            }
        )
        # Override testnet endpoint if requested
        if testnet:
            self._exchange.set_sandbox_mode(True)  # CCXT uses sandbox for testnet

        self._schema = UnifiedOHLCVSchema()

    def _resolve_symbol(self, symbol: str) -> str:
        """Convert user-friendly symbol to CCXT format.

        Handles: "BTC", "BTC/USDT", "BTC/USDT:USDT" → "BTC/USDT:USDT"
        """
        # Strip any trailing margin coin
        if ":" in symbol:
            return symbol
        # Already in canonical format (e.g. from CCXT fetch_markets)
        if "/" in symbol:
            # Assume USDT perpetuals on Hyperliquid
            if "USDT" not in symbol:
                return symbol
            return f"{symbol}:USDT" if ":" not in symbol else symbol
        # Bare ticker → assume USDT perpetual
        return f"{symbol}/USDT:USDT"

    def _fetch_page(
        self, symbol: str, timeframe: str, since: int, limit: int
    ) -> list:
        """Fetch a single page of OHLCV data."""
        return self._exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            since=since,
            limit=limit,
        )

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a single Hyperliquid perpetual.

        Args:
            symbol:     Trading pair. Accepts "BTC", "BTC/USDT", "BTC/USDT:USDT".
            timeframe:  Timeframe string (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            since:      Unix timestamp in ms. If None, fetches most recent `limit` bars.
            limit:      Max candles to return (Hyperliquid max: 500 per request).

        Returns:
            DataFrame with columns: timestamp (DatetimeIndex UTC),
            open, high, low, close, volume (all float64).
        """
        if limit > self.MAX_LIMIT_PER_REQUEST:
            limit = self.MAX_LIMIT_PER_REQUEST

        ccxt_symbol = self._resolve_symbol(symbol)

        if since is None:
            since = 0  # CCXT fetches from beginning if since=0

        raw = self._fetch_page(ccxt_symbol, timeframe, since, limit)

        if not raw:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], name="timestamp", tz="UTC"),
            ).astype({"open": "float64", "high": "float64", "low": "float64",
                       "close": "float64", "volume": "float64"})

        df = self._schema.normalize(raw, source="hyperliquid")

        # Sort by timestamp ascending
        df = df.sort_index()
        return df

    def fetch_ohlcv_batch(
        self,
        symbols: list[str],
        timeframe: str = "1h",
        limit: int = 1000,
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for multiple symbols.

        Args:
            symbols:    List of trading pairs.
            timeframe:  Timeframe string.
            limit:      Max candles per symbol.

        Returns:
            Dict mapping symbol → DataFrame.
        """
        results: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            try:
                results[sym] = self.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
            except Exception as e:
                # Log and skip individual symbol failures
                import warnings
                warnings.warn(f"Failed to fetch {sym}: {e}")
                results[sym] = pd.DataFrame(
                    columns=["open", "high", "low", "close", "volume"],
                    index=pd.DatetimeIndex([], name="timestamp", tz="UTC"),
                ).astype({"open": "float64", "high": "float64", "low": "float64",
                          "close": "float64", "volume": "float64"})
        return results

    def stream_ohlcv(
        self, symbol: str, timeframe: str = "1h"
    ) -> AsyncIterator[pd.DataFrame]:
        """Poll-based streaming (no WebSocket on Hyperliquid).

        Yields a new DataFrame each poll cycle.
        """
        import asyncio
        last_ts = 0
        while True:
            try:
                df = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
                if not df.empty and (last_ts == 0 or df.index[-1] > pd.Timestamp(last_ts, tz="UTC")):
                    if last_ts == 0:
                        last_ts = df.index[0].value
                    # Yield only new candles
                    new_candles = df[df.index > pd.Timestamp(last_ts, tz="UTC")]
                    if not new_candles.empty:
                        last_ts = new_candles.index[-1].value
                        yield new_candles
                else:
                    # Emit empty frame with current timestamp to keep alive
                    yield pd.DataFrame(
                        columns=["open", "high", "low", "close", "volume"],
                        index=pd.DatetimeIndex([], name="timestamp", tz="UTC"),
                    ).astype({"open": "float64", "high": "float64", "low": "float64",
                              "close": "float64", "volume": "float64"})
            except Exception as e:
                import warnings
                warnings.warn(f"Stream error for {symbol}: {e}")
                yield pd.DataFrame(
                    columns=["open", "high", "low", "close", "volume"],
                    index=pd.DatetimeIndex([], name="timestamp", tz="UTC"),
                ).astype({"open": "float64", "high": "float64", "low": "float64",
                          "close": "float64", "volume": "float64"})
            # Sleep between polls (configurable via timeframe)
            sleep_secs = self._timeframe_to_seconds(timeframe) // 2 or 30
            time.sleep(sleep_secs)

    @staticmethod
    def _timeframe_to_seconds(tf: str) -> int:
        """Convert CCXT timeframe string to seconds."""
        mapping = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
            "6h": 21600, "12h": 43200, "1d": 86400, "3d": 259200,
            "1w": 604800, "1M": 2592000,
        }
        return mapping.get(tf, 3600)

    def fetch_funding_rate(self, symbol: str) -> dict | None:
        """Fetch current funding rate for a perpetual.

        Returns dict with 'funding_rate', 'next_funding_time', or None.
        """
        ccxt_symbol = self._resolve_symbol(symbol)
        try:
            markets = self._exchange.fetch_markets(params={"type": "swap"})
            # Use public ticker
            ticker = self._exchange.fetch_ticker(ccxt_symbol)
            return {
                "symbol": symbol,
                "funding_rate": ticker.get("fundingRate"),
                "mark_price": ticker.get("mark"),
                "index_price": ticker.get("index"),
                "timestamp": ticker.get("timestamp"),
            }
        except Exception:
            return None

    def get_available_symbols(self) -> list[str]:
        """Return list of available Hyperliquid perpetual symbols."""
        try:
            markets = self._exchange.fetch_markets()
            return [
                m["symbol"]
                for m in markets
                if m.get("type") == "swap" and m.get("quote") == "USDT"
            ]
        except Exception:
            return []


__all__ = ["HyperliquidFeed"]