"""DataFeeder: UnifiedOHLCVSchema — normalize CCXT data to a common DataFrame format."""

from __future__ import annotations

from datetime import datetime

import pandas as pd


class UnifiedOHLCVSchema:
    """Normalize raw exchange OHLCV data into the unified ACTosha schema.

    Unified schema columns:
        timestamp (UTC) — int64 (Unix ms)
        open  — float64
        high  — float64
        low    — float64
        close — float64
        volume — float64

    Index: timestamp (DatetimeIndex UTC)

    All timeframes normalized to same schema regardless of source exchange.
    """

    @staticmethod
    def normalize(
        raw: list | pd.DataFrame,
        source: str = "unknown",
    ) -> pd.DataFrame:
        """Normalize raw CCXT-style OHLCV data to unified schema.

        Args:
            raw:    Raw OHLCV data as list of lists [[ts,o,h,l,c,v], ...]
                    or a DataFrame with columns [0..5] or named columns.
            source: Exchange name for logging/debugging.

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            Index is DatetimeIndex (UTC).
        """
        if isinstance(raw, pd.DataFrame):
            df = raw.copy()
        else:
            df = pd.DataFrame(
                raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        # Handle named columns from different exchanges
        rename_map = {
            "date": "timestamp",
            "Date": "timestamp",
            "datetime": "timestamp",
            "DateTime": "timestamp",
            "unix": "timestamp",
        }
        df = df.rename(columns=rename_map)

        # Ensure numeric types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Convert timestamp to Unix ms if needed
        if not pd.api.types.is_integer_dtype(df["timestamp"]):
            ts = pd.to_datetime(df["timestamp"], errors="coerce")
            df["timestamp"] = ts.view("int64") // 1_000_000  # ms
        else:
            # If already integer but maybe seconds not ms
            if df["timestamp"].max() < 1e12:
                df["timestamp"] = df["timestamp"] * 1000

        # Drop rows with NaN critical values
        df = df.dropna(subset=["timestamp", "close"])

        # Set timestamp index
        df = df.set_index("timestamp")
        df.index = pd.to_datetime(df.index, unit="ms", utc=True)
        df.index.name = "timestamp"

        # Ensure correct column order and types
        df = df[["open", "high", "low", "close", "volume"]].astype("float64")

        return df


__all__ = ["UnifiedOHLCVSchema"]