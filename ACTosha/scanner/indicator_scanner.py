"""Indicator scanner: RSI extremes, Bollinger squeeze, and indicator signals."""

from __future__ import annotations

import pandas as pd
import numpy as np

from ACTosha.scanner.base import MarketScanner, Opportunity


# ---------------------------------------------------------------------------
# Indicator computation helpers (inline, no external dependency cycle)
# ---------------------------------------------------------------------------

def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI with Wilder smoothing. Returns Series of same length."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _compute_bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Compute Bollinger Bands. Returns (middle, upper, lower, bandwidth)."""
    middle = close.rolling(window=period, min_periods=period).mean()
    rolling_std = close.rolling(window=period, min_periods=period).std()
    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std
    bandwidth = (upper - lower) / middle
    return middle, upper, lower, bandwidth


def _compute_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD. Returns (macd_line, signal_line, histogram)."""
    ema_fast = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _compute_stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14
) -> tuple[pd.Series, pd.Series]:
    """Compute Stochastic %K and %D. Returns (k, d)."""
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()
    range_hl = (highest_high - lowest_low).replace(0, np.nan)
    k = 100 * (close - lowest_low) / range_hl
    d = k.rolling(window=3, min_periods=1).mean()
    return k.fillna(50.0), d.fillna(50.0)


def _compute_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Compute Average True Range."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return atr.fillna(0.0)


# ---------------------------------------------------------------------------
# Indicator Scanner
# ---------------------------------------------------------------------------

class IndicatorScanner(MarketScanner):
    """Scan for indicator-based signals.

    Signals detected
        - rsi_oversold    : RSI < rsi_oversold_threshold (default 30)
        - rsi_overbought  : RSI > rsi_overbought_threshold (default 70)
        - bb_squeeze      : Bollinger bandwidth < squeeze_threshold (default 0.1)
        - bb_breakout_up  : price closes above upper Bollinger band
        - bb_breakout_down: price closes below lower Bollinger band
        - macd_cross_up   : MACD line crosses above signal line
        - macd_cross_down : MACD line crosses below signal line
        - stoch_oversold  : Stochastic %K < 20
        - stoch_overbought: Stochastic %K > 80
    """

    PATTERNS = [
        "rsi_oversold",
        "rsi_overbought",
        "bb_squeeze",
        "bb_breakout_up",
        "bb_breakout_down",
        "macd_cross_up",
        "macd_cross_down",
        "stoch_oversold",
        "stoch_overbought",
    ]

    def __init__(
        self,
        timeframe: str = "1h",
        min_strength: float = 0.5,
        rsi_period: int = 14,
        rsi_oversold_threshold: float = 30.0,
        rsi_overbought_threshold: float = 70.0,
        bb_period: int = 20,
        bb_std: float = 2.0,
        bb_squeeze_threshold: float = 0.1,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        stoch_period: int = 14,
    ) -> None:
        """
        Parameters
        ----------
        timeframe : str
            OHLCV timeframe label.
        min_strength : float
            Minimum confidence to return an opportunity.
        rsi_period : int
            RSI lookback period.
        rsi_oversold_threshold : float
            RSI level below which a bar is flagged as oversold.
        rsi_overbought_threshold : float
            RSI level above which a bar is flagged as overbought.
        bb_period : int
            Bollinger Bands lookback period.
        bb_std : float
            Bollinger Bands standard deviation multiplier.
        bb_squeeze_threshold : float
            Bollinger bandwidth below which a squeeze is flagged.
        macd_fast, macd_slow, macd_signal : int
            MACD parameters.
        stoch_period : int
            Stochastic %K period.
        """
        super().__init__(timeframe=timeframe, min_strength=min_strength)
        self.rsi_period = rsi_period
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.bb_squeeze_threshold = bb_squeeze_threshold
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.stoch_period = stoch_period

    def _scan_symbol(
        self, symbol: str, df: pd.DataFrame
    ) -> list[Opportunity]:
        opps: list[Opportunity] = []

        # Ensure enough data
        min_bars = max(self.rsi_period, self.bb_period, self.macd_slow, self.stoch_period)
        if len(df) < min_bars + 5:
            return opps

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # ---- RSI ----
        rsi = _compute_rsi(close, self.rsi_period)
        rsi_last = rsi.iloc[-1]

        if rsi_last < self.rsi_oversold_threshold:
            strength = (self.rsi_oversold_threshold - rsi_last) / self.rsi_oversold_threshold
            entry_zone = self._entry_zone(close.iloc[-1])
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="rsi_oversold",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={"rsi": round(float(rsi_last), 2)},
                )
            )

        if rsi_last > self.rsi_overbought_threshold:
            strength = (rsi_last - self.rsi_overbought_threshold) / (100 - self.rsi_overbought_threshold)
            entry_zone = self._entry_zone(close.iloc[-1])
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="rsi_overbought",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={"rsi": round(float(rsi_last), 2)},
                )
            )

        # ---- Bollinger Bands ----
        bb_mid, bb_upper, bb_lower, bb_bw = _compute_bollinger_bands(
            close, self.bb_period, self.bb_std
        )
        bb_bw_last = bb_bw.iloc[-1]
        price = close.iloc[-1]
        bb_upper_last = bb_upper.iloc[-1]
        bb_lower_last = bb_lower.iloc[-1]

        # Squeeze detection
        if bb_bw_last < self.bb_squeeze_threshold:
            # Squeeze is building — momentum may be compressing
            # Strength inversely proportional to bandwidth
            strength = 1.0 - (bb_bw_last / self.bb_squeeze_threshold)
            entry_zone = self._entry_zone(price)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="bb_squeeze",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "bb_bandwidth": round(float(bb_bw_last), 6),
                        "bb_upper": round(float(bb_upper_last), 4),
                        "bb_lower": round(float(bb_lower_last), 4),
                    },
                )
            )

        # Bollinger breakout
        if price > bb_upper_last:
            # %B > 1 — price above upper band
            strength = min((price - bb_upper_last) / bb_upper_last * 10 + 0.5, 0.95)
            entry_zone: tuple[float, float] = (
                float(bb_upper_last),
                float(bb_upper_last * 1.005),
            )
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="bb_breakout_up",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "bb_percent": round(float((price - bb_lower_last) / (bb_upper_last - bb_lower_last)), 4),
                        "bb_upper": round(float(bb_upper_last), 4),
                    },
                )
            )

        if price < bb_lower_last:
            strength = min((bb_lower_last - price) / bb_lower_last * 10 + 0.5, 0.95)
            entry_zone = (
                float(bb_lower_last * 0.995),
                float(bb_lower_last),
            )
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="bb_breakout_down",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "bb_percent": round(float((price - bb_lower_last) / (bb_upper_last - bb_lower_last)), 4),
                        "bb_lower": round(float(bb_lower_last), 4),
                    },
                )
            )

        # ---- MACD crossover ----
        macd_line, macd_signal_line, macd_hist = _compute_macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )
        macd_curr = macd_line.iloc[-1]
        macd_signal_curr = macd_signal_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        macd_signal_prev = macd_signal_line.iloc[-2]

        # Cross up
        if macd_prev <= macd_signal_prev and macd_curr > macd_signal_curr:
            strength = min(abs(macd_hist.iloc[-1]) / (abs(macd_curr) + 1e-9), 0.95)
            entry_zone = self._entry_zone(price)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="macd_cross_up",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "macd": round(float(macd_curr), 6),
                        "macd_signal": round(float(macd_signal_curr), 6),
                        "macd_hist": round(float(macd_hist.iloc[-1]), 6),
                    },
                )
            )

        # Cross down
        if macd_prev >= macd_signal_prev and macd_curr < macd_signal_curr:
            strength = min(abs(macd_hist.iloc[-1]) / (abs(macd_curr) + 1e-9), 0.95)
            entry_zone = self._entry_zone(price)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="macd_cross_down",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "macd": round(float(macd_curr), 6),
                        "macd_signal": round(float(macd_signal_curr), 6),
                        "macd_hist": round(float(macd_hist.iloc[-1]), 6),
                    },
                )
            )

        # ---- Stochastic ----
        stoch_k, stoch_d = _compute_stochastic(high, low, close, self.stoch_period)
        stoch_k_last = stoch_k.iloc[-1]

        if stoch_k_last < 20:
            strength = (20 - stoch_k_last) / 20
            entry_zone = self._entry_zone(price)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="stoch_oversold",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "stoch_k": round(float(stoch_k_last), 2),
                        "stoch_d": round(float(stoch_d.iloc[-1]), 2),
                    },
                )
            )

        if stoch_k_last > 80:
            strength = (stoch_k_last - 80) / 20
            entry_zone = self._entry_zone(price)
            opps.append(
                Opportunity(
                    symbol=symbol,
                    pattern="stoch_overbought",
                    timeframe=self.timeframe,
                    strength=max(float(strength), 0.55),
                    entry_zone=entry_zone,
                    metadata={
                        "stoch_k": round(float(stoch_k_last), 2),
                        "stoch_d": round(float(stoch_d.iloc[-1]), 2),
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


__all__ = ["IndicatorScanner"]
