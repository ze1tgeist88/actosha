"""Mean reversion strategy: VWAP deviation bands reversion."""

from __future__ import annotations

import pandas as pd

from ACTosha.strategies.base import SignalBundle, Strategy


class VWAPRevertStrategy(Strategy):
    """Mean reversion strategy based on VWAP deviation bands.

    Enters a long position when price deviates below the VWAP lower band
    by a configurable threshold, expecting a reversion to VWAP.
    Short entries work inversely when price exceeds the upper band.

    Parameters
    ----------
    band_threshold : float
        Deviation from VWAP (as fraction of VWAP) to trigger signal.
        Default: 0.005 (0.5%).
    exit_threshold : float
        Deviation at which to close position (closer to VWAP).
        Default: 0.001 (0.1%).
    max_position_duration : int
        Max bars to hold before forcing exit. Default: 50.
    """

    def __init__(
        self,
        band_threshold: float = 0.005,
        exit_threshold: float = 0.001,
        max_position_duration: int = 50,
    ) -> None:
        self._band_threshold = band_threshold
        self._exit_threshold = exit_threshold
        self._max_position_duration = max_position_duration

    @property
    def name(self) -> str:
        return "VWAPRevert"

    def get_params(self) -> dict:
        return {
            "band_threshold": self._band_threshold,
            "exit_threshold": self._exit_threshold,
            "max_position_duration": self._max_position_duration,
        }

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        """Generate VWAP deviation reversion signals."""
        if "vwap" not in df.columns:
            df = df.copy()
            df["vwap"] = self._compute_vwap(df)

        signals = pd.DataFrame(index=df.index)
        signals["side"] = "none"
        signals["strength"] = 0.0
        signals["entry_price"] = None
        signals["stop_loss"] = None
        signals["take_profit"] = None
        signals["metadata"] = [{}] * len(df)

        position_open = False
        position_side = None
        entry_idx = 0  # use integer index for bar counting

        for i, row in df.iterrows():
            # Get integer position
            idx_pos = df.index.get_loc(i)

            if not position_open:
                deviation = (row["close"] - row["vwap"]) / row["vwap"]

                if deviation < -self._band_threshold:
                    signals.at[i, "side"] = "long"
                    signals.at[i, "strength"] = min(abs(deviation) / self._band_threshold, 1.0)
                    signals.at[i, "entry_price"] = row["close"]
                    signals.at[i, "stop_loss"] = row["close"] * (1 - 2 * self._band_threshold)
                    signals.at[i, "take_profit"] = row["vwap"]
                    position_open = True
                    position_side = "long"
                    entry_idx = idx_pos

                elif deviation > self._band_threshold:
                    signals.at[i, "side"] = "short"
                    signals.at[i, "strength"] = min(abs(deviation) / self._band_threshold, 1.0)
                    signals.at[i, "entry_price"] = row["close"]
                    signals.at[i, "stop_loss"] = row["close"] * (1 + 2 * self._band_threshold)
                    signals.at[i, "take_profit"] = row["vwap"]
                    position_open = True
                    position_side = "short"
                    entry_idx = idx_pos

            else:
                deviation = (row["close"] - row["vwap"]) / row["vwap"]
                bars_held = idx_pos - entry_idx

                should_exit = False

                if position_side == "long":
                    if deviation >= -self._exit_threshold:
                        should_exit = True
                    elif bars_held >= self._max_position_duration:
                        should_exit = True
                else:
                    if deviation <= self._exit_threshold:
                        should_exit = True
                    elif bars_held >= self._max_position_duration:
                        should_exit = True

                if should_exit:
                    signals.at[i, "side"] = "close"
                    signals.at[i, "strength"] = 0.5
                    position_open = False
                    position_side = None

        metadata = {
            "strategy": self.name,
            "params": self.get_params(),
            "created_at": pd.Timestamp.utcnow(),
        }
        return SignalBundle(signals=signals, metadata=metadata)

    @staticmethod
    def _compute_vwap(df: pd.DataFrame) -> pd.Series:
        """Compute VWAP from OHLCV data."""
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
        cumulative_vol = df["volume"].cumsum()
        return cumulative_tp_vol / cumulative_vol


__all__ = ["VWAPRevertStrategy"]