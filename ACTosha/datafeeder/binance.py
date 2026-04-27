"""DataFeeder: Binance feed submodule — Spot + USDM-futures via CCXT."""

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
        "ccxt is required for BinanceFeed: pip install ccxt>=4.0"
    ) from e


class BinanceFeed(AbstractExchangeFeed):
    """Binance spot + USDM-futures data feeder via CCXT.

    Supports both spot markets and USD-Margined perpetual futures.
    All data is normalized to UnifiedOHLCVSchema.

    API Reference: https://developers.binance.com/
    CCXT: https://docs.ccxt.com/#/exchanges/binance
    """

    MAX_LIMIT_PER_REQUEST = 1000  # Binance max candles per request

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        mode: str = "spot",
        testnet: bool = False,
        request_timeout: float = 30.0,
    ) -> None:
        """Initialize Binance exchange feed.

        Args:
            api_key:     Binance API key (optional for public market data)
            api_secret:  Binance API secret (optional for public market data)
            mode:        "spot" or "future" (USDM perpetual)
            testnet:     Use Binance testnet (testnet.binance.vision)
            request_timeout: Timeout for HTTP requests in seconds.
        """
        if mode not in ("spot", "future"):
            raise ValueError(f"mode must be 'spot' or 'future', got '{mode}'")

        self._mode = mode
        self._testnet = testnet

        # CCXT sandbox maps to testnet URLs
        config: dict = {
            "apiKey": api_key or "",
            "secret": api_secret or "",
            "enableRateLimit": True,
            "timeout": int(request_timeout * 1000),
            "options": {
                "defaultType": mode,
            },
        }
        if testnet:
            config["testnet"] = True

        self._exchange = ccxt.binance(config)
        self._schema = UnifiedOHLCVSchema()

    def _resolve_symbol(self, symbol: str) -> str:
        """Convert user-friendly symbol to CCXT format.

        Handles: "BTC", "BTCUSDT" → "BTC/USDT" (spot) or "BTC/USDT:USDT" (perp)
                 "BTC/USDT" → "BTC/USDT" (spot) or "BTC/USDT:USDT" (perp)
                 "BTC/USDT:USDT" → unchanged
        """
        if ":" in symbol:
            return symbol
        # Extract base currency (e.g., "BTC" from "BTC", "BTCUSDT", "BTC/USDT")
        base = symbol.replace("/USDT", "").replace("USDT", "").replace("/", "").replace("-", "")
        if self._mode == "future":
            return f"{base}/USDT:USDT"
        else:
            return f"{base}/USDT"

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
        """Fetch OHLCV data for a single Binance market.

        Args:
            symbol:     Trading pair. Accepts "BTC", "BTCUSDT", "BTC/USDT".
            timeframe:  Timeframe string (1m, 3m, 5m, 15m, 30m, 1h, 2h,
                        4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
            since:       Unix timestamp in ms. If None, fetches most recent `limit` bars.
            limit:       Max candles (max 1000 per request on Binance).

        Returns:
            DataFrame with columns: timestamp (DatetimeIndex UTC),
            open, high, low, close, volume (all float64).
        """
        if limit > self.MAX_LIMIT_PER_REQUEST:
            limit = self.MAX_LIMIT_PER_REQUEST

        ccxt_symbol = self._resolve_symbol(symbol)

        # If since is None, let CCXT fetch the most recent bars
        raw = self._fetch_page(ccxt_symbol, timeframe, since, limit)

        if not raw:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], name="timestamp", tz="UTC"),
            ).astype({"open": "float64", "high": "float64", "low": "float64",
                       "close": "float64", "volume": "float64"})

        df = self._schema.normalize(raw, source="binance")

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
                import warnings
                warnings.warn(f"Failed to fetch {sym}: {e}")
                results[sym] = pd.DataFrame(
                    columns=["open", "high", "low", "close", "volume"],
                    index=pd.DatetimeIndex([], name="timestamp", tz="UTC"),
                ).astype({"open": "float64", "high": "float64", "low": "float64",
                          "close": "float64", "volume": "float64"})
        return results

    def fetch_ohlcv_range(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        until: int | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch OHLCV data within a time range, auto-paginating.

        Binance rate limits: 1200 requests/min weighted, 6000 weight/min.
        This method respects those limits and paginates automatically.

        Args:
            symbol:     Trading pair.
            timeframe: Timeframe string.
            since:     Start time in Unix ms.
            until:     End time in Unix ms (default: now).
            limit:     Max candles per single request.

        Returns:
            DataFrame covering the full range.
        """
        ccxt_symbol = self._resolve_symbol(symbol)
        # Allow caller to override via function args; default to 2024-01-01 → 2025-04-25
        if since is None:
            since_ms = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
        else:
            since_ms = since
        if until is None:
            until_ms = int(pd.Timestamp("2025-04-26", tz="UTC").timestamp() * 1000)
        else:
            until_ms = until
        current_ts = since_ms
        timeframe_ms = self._timeframe_to_ms(timeframe)  # 3600000 for 1h

        # Binance pagination: fetch in chunks of 1000 candles
        all_candles: list = []
        while current_ts < until_ms:
            remaining = (until_ms - current_ts) // timeframe_ms
            batch_limit = min(limit, max(1, int(remaining)))
            if batch_limit > 1000:
                batch_limit = 1000

            raw = self._fetch_page(ccxt_symbol, timeframe, current_ts, batch_limit)
            if not raw:
                break

            all_candles.extend(raw)
            last_ts = raw[-1][0]
            # Move to next batch: use last timestamp + 1 timeframe to avoid duplicate
            current_ts = last_ts + timeframe_ms

            # Binance rate limit: gentle sleep
            time.sleep(0.3)

            # Safety: avoid infinite loop (max 20000 candles)
            if len(all_candles) > 20000:
                break

        if not all_candles:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], name="timestamp", tz="UTC"),
            ).astype({"open": "float64", "high": "float64", "low": "float64",
                       "close": "float64", "volume": "float64"})

        df = self._schema.normalize(all_candles, source="binance")
        df = df.sort_index()

        if until:
            df = df[df.index < pd.Timestamp(until, unit="ms", tz="UTC")]

        return df

    def stream_ohlcv(
        self, symbol: str, timeframe: str = "1h"
    ) -> AsyncIterator[pd.DataFrame]:
        """Polling-based streaming (Binance does not have public WebSocket for OHLCV in CCXT).

        Yields a DataFrame each poll cycle with new candles.
        """
        last_ts = 0
        while True:
            try:
                df = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
                if not df.empty:
                    if last_ts == 0:
                        last_ts = df.index[0].value
                    new_candles = df[df.index > pd.Timestamp(last_ts, tz="UTC")]
                    if not new_candles.empty:
                        last_ts = new_candles.index[-1].value
                        yield new_candles
                else:
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
            sleep_secs = self._timeframe_to_seconds(timeframe) // 2 or 30
            time.sleep(sleep_secs)

    @staticmethod
    def _timeframe_to_seconds(tf: str) -> int:
        """Convert CCXT timeframe string to seconds."""
        mapping = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
            "6h": 21600, "8h": 28800, "12h": 43200,
            "1d": 86400, "3d": 259200, "1w": 604800, "1M": 2592000,
        }
        return mapping.get(tf, 3600)

    @staticmethod
    def _timeframe_to_ms(tf: str) -> int:
        """Convert CCXT timeframe string to milliseconds."""
        return BinanceFeed._timeframe_to_seconds(tf) * 1000

    def fetch_ticker(self, symbol: str) -> dict | None:
        """Fetch current ticker for a symbol."""
        ccxt_symbol = self._resolve_symbol(symbol)
        try:
            t = self._exchange.fetch_ticker(ccxt_symbol)
            return {
                "symbol": symbol,
                "last": t.get("last"),
                "bid": t.get("bid"),
                "ask": t.get("ask"),
                "volume": t.get("baseVolume"),
                "quote_volume": t.get("quoteVolume"),
                "timestamp": t.get("timestamp"),
            }
        except Exception:
            return None

    def get_available_symbols(self, filters: list[str] | None = None) -> list[str]:
        """Return list of available symbols filtered by type.

        Args:
            filters: list of quote assets, e.g. ["USDT", "BTC"]
        """
        try:
            markets = self._exchange.fetch_markets()
            result = []
            for m in markets:
                if self._mode == "future":
                    if m.get("type") != "future":
                        continue
                    if m.get("quote") != "USDT":
                        continue
                else:
                    if m.get("type") != "spot":
                        continue
                sym = m["symbol"].replace("/USDT:USDT", "").replace("/USDT", "")
                if filters:
                    quote = m.get("quote", "")
                    if any(f in quote for f in filters):
                        result.append(sym)
                else:
                    result.append(sym)
            return result
        except Exception:
            return []


__all__ = ["BinanceFeed"]