#!/usr/bin/env python3
"""
Backtest runner for ACTosha: grid-optimized backtest across all 9 strategies.
Fetches BTC/USDC 1h data from Binance, runs grid optimization, saves results.
"""
import sys, os, signal, warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from itertools import product

from ACTosha.backtester.engine import BacktestEngine
from ACTosha.backtester.simulator import FillMode, OrderSimulator, Order, OrderSide
from ACTosha.datafeeder.binance import BinanceFeed
from ACTosha.indicators.momentum import compute_rsi, compute_macd
from ACTosha.indicators.volatility import compute_atr, compute_bollinger_bands
from ACTosha.indicators.moving_averages import compute_ema
from ACTosha.strategies.base import SignalBundle, BaseStrategy
from ACTosha.strategies.trend.ema_cross import EMACrossStrategy
from ACTosha.strategies.breakout.range_breakout import RangeBreakoutStrategy
from ACTosha.strategies.mean_reversion.bollinger_revert import BollingerRevertStrategy
from ACTosha.strategies.mean_reversion.vwap_revert import VWAPRevertStrategy


# ─────────────────────────────────────────────────────────────────────────────
# Strategy implementations for NotImplemented strategies
# ─────────────────────────────────────────────────────────────────────────────

class SupertrendStrategy(BaseStrategy):
    """Supertrend trend-following strategy."""
    def __init__(self, period: int = 10, multiplier: float = 3.0,
                 initial_capital: float = 10_000.0, risk_per_trade: float = 0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._period = period
        self._multiplier = multiplier

    @property
    def name(self) -> str:
        return f"Supertrend_{self._period}_{self._multiplier}"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update({"period": self._period, "multiplier": self._multiplier})
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        self.validate_df(df)
        data = compute_atr(df.copy(), period=self._period)
        atr_col = f"atr_{self._period}"

        hl2 = (data["high"] + data["low"]) / 2
        upper_band = hl2 + self._multiplier * data[atr_col]
        lower_band = hl2 - self._multiplier * data[atr_col]

        in_uptrend = pd.Series(True, index=data.index)
        for i in range(1, len(data)):
            prev_close = data["close"].iloc[i - 1]
            curr_close = data["close"].iloc[i]
            prev_upper = upper_band.iloc[i - 1]
            prev_lower = lower_band.iloc[i - 1]

            if curr_close > prev_upper:
                in_uptrend.iloc[i] = True
            elif curr_close < prev_lower:
                in_uptrend.iloc[i] = False
            else:
                in_uptrend.iloc[i] = in_uptrend.iloc[i - 1]

        prev_uptrend = in_uptrend.shift(1).fillna(True)
        cross_up = in_uptrend & ~prev_uptrend
        cross_down = (~in_uptrend) & prev_uptrend
        cross_any = cross_up | cross_down

        close = data["close"]
        # Supertrend is a reversal system: new position auto-closes old.
        # No explicit 'close' signals needed — just entries on direction changes.
        # Use cross_up for long entries, cross_down for short entries.
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[cross_up] = "long"
        sides[cross_down] = "short"

        spread = data[atr_col] * self._multiplier
        spread_ma = spread.rolling(20, min_periods=1).mean()
        strength = (spread / spread_ma.replace(0, 1)).clip(0, 1).fillna(0.5)

        signals = pd.DataFrame({
            "side": sides, "strength": strength,
            "entry_price": close, "stop_loss": None,
            "take_profit": None, "metadata": [{}] * len(data),
        })

        for idx in data.index:
            side = signals.loc[idx, "side"]
            if side not in ("long", "short"):
                continue
            entry = data.loc[idx, "close"]
            direction = side
            atr_val = data.loc[idx, atr_col]
            sl = self.calc_stop_loss(entry, direction, atr_value=atr_val, multiplier=2.0)
            tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=2.0)
            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp

        return SignalBundle(signals=signals, metadata={"strategy": self.name, "params": self.get_params()})


class TrendlineBreakStrategy(BaseStrategy):
    """Trendline break + retest strategy."""
    def __init__(self, lookback: int = 50, retest_tolerance: float = 0.005,
                 initial_capital: float = 10_000.0, risk_per_trade: float = 0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._lookback = lookback
        self._retest_tolerance = retest_tolerance

    @property
    def name(self) -> str:
        return f"TrendlineBreak_{self._lookback}"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update({"lookback": self._lookback, "retest_tolerance": self._retest_tolerance})
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        self.validate_df(df)
        close = df["close"]
        high = df["high"]
        low = df["low"]

        slope_up = close.rolling(self._lookback, min_periods=self._lookback).apply(
            lambda x: np.polyfit(np.arange(len(x)), x, 1)[0] if len(x) >= 5 else 0, raw=True
        )
        in_uptrend = slope_up > 0
        prev_uptrend = in_uptrend.shift(1).fillna(False)

        roll_max = high.rolling(self._lookback, min_periods=self._lookback).max().shift(1)
        roll_min = low.rolling(self._lookback, min_periods=self._lookback).min().shift(1)

        breakout_up = close > roll_max * (1 + self._retest_tolerance)
        breakout_down = close < roll_min * (1 - self._retest_tolerance)
        confirm_up = breakout_up & (slope_up > 0)
        confirm_down = breakout_down & (slope_up < 0)
        reverse = confirm_up | confirm_down

        # TrendlineBreak is a reversal system: entries on break, reversals auto-close.
        sides = pd.Series("none", index=df.index, dtype="string")
        sides[confirm_up] = "long"
        sides[confirm_down] = "short"

        range_size = roll_max - roll_min
        strength_arr = (close - roll_max).where(confirm_up, 0) + (roll_min - close).where(confirm_down, 0)
        strengths = strength_arr.clip(0, 1).fillna(0.5)

        signals = pd.DataFrame({
            "side": sides, "strength": strengths,
            "entry_price": close, "stop_loss": None,
            "take_profit": None, "metadata": [{}] * len(df),
        })

        data = compute_atr(df.copy(), period=14)
        for idx in data.index:
            side = signals.loc[idx, "side"]
            if side not in ("long", "short"):
                continue
            entry = data.loc[idx, "close"]
            direction = side
            atr_val = data.loc[idx, "atr_14"]
            sl = self.calc_stop_loss(entry, direction, atr_value=atr_val, multiplier=2.0)
            tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=2.0)
            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp

        return SignalBundle(signals=signals, metadata={"strategy": self.name, "params": self.get_params()})


class RSIExtremeStrategy(BaseStrategy):
    """RSI extreme levels mean reversion strategy."""
    def __init__(self, rsi_period: int = 14, oversold: float = 30.0, overbought: float = 70.0,
                 initial_capital: float = 10_000.0, risk_per_trade: float = 0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._rsi_period = rsi_period
        self._oversold = oversold
        self._overbought = overbought

    @property
    def name(self) -> str:
        return f"RSIExtreme_{self._rsi_period}_{self._oversold}_{self._overbought}"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update({"rsi_period": self._rsi_period, "oversold": self._oversold,
                     "overbought": self._overbought})
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        self.validate_df(df)
        data = compute_rsi(df.copy(), period=self._rsi_period)
        rsi_col = f"rsi_{self._rsi_period}"
        close = data["close"]
        rsi = data[rsi_col]

        below_oversold = rsi < self._oversold
        above_overbought = rsi > self._overbought
        was_below = below_oversold.shift(1).fillna(False)
        was_above = above_overbought.shift(1).fillna(False)

        enter_long = below_oversold & ~was_below
        enter_short = above_overbought & ~was_above

        long_exit = (rsi > 50) & (rsi.shift(1) <= 50)
        short_exit = (rsi < 50) & (rsi.shift(1) >= 50)

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[enter_long] = "long"
        sides[enter_short] = "short"
        sides[long_exit & ~enter_long] = "close"
        sides[short_exit & ~enter_short] = "close"

        strength = (self._oversold - rsi).clip(0, self._oversold) / self._oversold
        strength += (rsi - self._overbought).clip(0, 100 - self._overbought) / (100 - self._overbought)
        strength = strength.fillna(0.5).clip(0, 1)

        signals = pd.DataFrame({
            "side": sides, "strength": strength,
            "entry_price": close, "stop_loss": None,
            "take_profit": None, "metadata": [{}] * len(df),
        })

        data = compute_atr(data, period=14)
        _signals_idx = data.index
        for idx in _signals_idx:
            side = signals.loc[idx, "side"]
            if side not in ("long", "short"):
                continue
            entry = data.loc[idx, "close"]
            direction = side
            atr_val = data.loc[idx, "atr_14"]
            sl = self.calc_stop_loss(entry, direction, atr_value=atr_val, multiplier=2.0)
            tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=2.0)
            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp

        return SignalBundle(signals=signals, metadata={"strategy": self.name, "params": self.get_params()})


class RSIMACDComboStrategy(BaseStrategy):
    """RSI + MACD confluence momentum strategy."""
    def __init__(self, rsi_period: int = 14, macd_fast: int = 12, macd_slow: int = 26,
                 macd_signal: int = 9, initial_capital: float = 10_000.0,
                 risk_per_trade: float = 0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._rsi_period = rsi_period
        self._macd_fast = macd_fast
        self._macd_slow = macd_slow
        self._macd_signal = macd_signal

    @property
    def name(self) -> str:
        return f"RSIMACDCombo_{self._rsi_period}_{self._macd_fast}_{self._macd_slow}_{self._macd_signal}"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update({"rsi_period": self._rsi_period, "macd_fast": self._macd_fast,
                     "macd_slow": self._macd_slow, "macd_signal": self._macd_signal})
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        self.validate_df(df)
        data = compute_rsi(df.copy(), period=self._rsi_period)
        data = compute_macd(data, fast=self._macd_fast, slow=self._macd_slow, signal=self._macd_signal)
        rsi_col = f"rsi_{self._rsi_period}"
        close = data["close"]
        rsi = data[rsi_col]
        macd = data["macd"]
        macd_signal = data["macd_signal"]

        rsi_above50 = rsi > 50
        prev_rsi_above50 = rsi_above50.shift(1).fillna(False)
        macd_above_signal = macd > macd_signal
        prev_macd_above_signal = macd_above_signal.shift(1).fillna(False)

        rsi_cross_up = rsi_above50 & ~prev_rsi_above50
        macd_cross_up = macd_above_signal & ~prev_macd_above_signal

        # Short: simplified (RSI below 50 AND MACD crosses below signal)
        rsi_below50 = rsi < 50
        prev_rsi_below50 = rsi_below50.shift(1).fillna(False)
        macd_cross_down = (~macd_above_signal) & prev_macd_above_signal
        rsi_cross_down = rsi_below50 & ~prev_rsi_below50

        long_confluence = rsi_cross_up & macd_cross_up
        short_confluence = rsi_cross_down & macd_cross_down
        close_signal = long_confluence | short_confluence

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_confluence] = "long"
        sides[short_confluence] = "short"
        # Close only when RSI or MACD flips without the other confirming
        long_exit = rsi_cross_up & ~macd_cross_up
        short_exit = rsi_cross_down & ~macd_cross_down
        sides[long_exit | short_exit] = "close"

        rsi_dist = (rsi - 50).abs() / 50
        macd_abs_ma = macd.abs().rolling(50, min_periods=1).mean().replace(0, 1)
        macd_dist = macd.abs() / macd_abs_ma
        strength = (rsi_dist + macd_dist.clip(0, 1)) / 2
        strength = strength.fillna(0.5).clip(0, 1)

        signals = pd.DataFrame({
            "side": sides, "strength": strength,
            "entry_price": close, "stop_loss": None,
            "take_profit": None, "metadata": [{}] * len(df),
        })


        data = compute_atr(data, period=14)
        _signals_idx = data.index
        for idx in _signals_idx:
            side = signals.loc[idx, "side"]
            if side not in ("long", "short"):
                continue
            entry = data.loc[idx, "close"]
            direction = side
            atr_val = data.loc[idx, "atr_14"]
            sl = self.calc_stop_loss(entry, direction, atr_value=atr_val, multiplier=2.0)
            tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=2.0)
            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp

        return SignalBundle(signals=signals, metadata={"strategy": self.name, "params": self.get_params()})


class VolumeSurgeStrategy(BaseStrategy):
    """Volume surge breakout strategy."""
    def __init__(self, lookback: int = 20, volume_multiplier: float = 2.0,
                 price_lookback: int = 20, initial_capital: float = 10_000.0,
                 risk_per_trade: float = 0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._lookback = lookback
        self._volume_multiplier = volume_multiplier
        self._price_lookback = price_lookback

    @property
    def name(self) -> str:
        return f"VolumeSurge_{self._lookback}_{self._volume_multiplier}"

    def get_params(self) -> dict:
        base = super().get_params()
        base.update({"lookback": self._lookback, "volume_multiplier": self._volume_multiplier,
                     "price_lookback": self._price_lookback})
        return base

    def generate_signals(self, df: pd.DataFrame) -> SignalBundle:
        self.validate_df(df)
        data = df.copy()
        avg_volume = data["volume"].rolling(self._lookback, min_periods=self._lookback).mean()
        volume_surge = data["volume"] > avg_volume * self._volume_multiplier

        roll_high = data["high"].rolling(self._price_lookback, min_periods=self._price_lookback).max()
        roll_low = data["low"].rolling(self._price_lookback, min_periods=self._price_lookback).min()

        break_up = data["close"] > roll_high.shift(1)
        break_down = data["close"] < roll_low.shift(1)

        long_signal = break_up & volume_surge
        short_signal = break_down & volume_surge
        opposite = long_signal | short_signal

        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_signal] = "long"
        sides[short_signal] = "short"
        # Volume surge is a reversal system — opposite breakout triggers new position (auto-closes old)

        vol_ratio = data["volume"] / avg_volume.replace(0, 1)
        range_width = roll_high - roll_low
        price_break = (data["close"] - roll_low).where(long_signal, 0) + \
                      (roll_high - data["close"]).where(short_signal, 0)
        strength = ((vol_ratio / self._volume_multiplier) + (price_break / range_width.replace(0, 1))) / 2
        strength = strength.fillna(0.5).clip(0, 1)

        signals = pd.DataFrame({
            "side": sides, "strength": strength,
            "entry_price": data["close"], "stop_loss": None,
            "take_profit": None, "metadata": [{}] * len(df),
        })

        data = compute_atr(data, period=14)
        _signals_idx = data.index
        for idx in _signals_idx:
            side = signals.loc[idx, "side"]
            if side not in ("long", "short"):
                continue
            entry = data.loc[idx, "close"]
            direction = side
            atr_val = data.loc[idx, "atr_14"]
            sl = self.calc_stop_loss(entry, direction, atr_value=atr_val, multiplier=2.0)
            tp = self.calc_take_profit(entry, direction, stop_loss=sl, risk_reward=2.0)
            signals.at[idx, "stop_loss"] = sl
            signals.at[idx, "take_profit"] = tp

        return SignalBundle(signals=signals, metadata={"strategy": self.name, "params": self.get_params()})


# ─────────────────────────────────────────────────────────────────────────────
# Grid parameter definitions
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_GRIDS = {
    "EMA Cross": {
        "factory": lambda p: EMACrossStrategy(fast_period=p["fast_period"], slow_period=p["slow_period"],
                                               atr_multiplier=p["atr_multiplier"], risk_reward=p["risk_reward"]),
        "params": {
            "fast_period": [5, 9, 12, 15],
            "slow_period": [21, 30, 50],
            "atr_multiplier": [1.5, 2.0, 3.0],
            "risk_reward": [1.5, 2.0],
        },
    },
    "Supertrend": {
        "factory": lambda p: SupertrendStrategy(period=p["period"], multiplier=p["multiplier"]),
        "params": {
            "period": [7, 10, 14, 20],
            "multiplier": [2.0, 3.0, 4.0, 5.0],
        },
    },
    "Trendline Break": {
        "factory": lambda p: TrendlineBreakStrategy(lookback=p["lookback"], retest_tolerance=p["retest_tolerance"]),
        "params": {
            "lookback": [30, 50, 80],
            "retest_tolerance": [0.003, 0.005, 0.01],
        },
    },
    "Bollinger Reversion": {
        "factory": lambda p: BollingerRevertStrategy(bb_period=p["bb_period"], bb_std=p["bb_std"],
                                                      atr_multiplier=p["atr_multiplier"], risk_reward=p["risk_reward"]),
        "params": {
            "bb_period": [15, 20, 25],
            "bb_std": [1.5, 2.0, 2.5],
            "atr_multiplier": [1.5, 2.0, 3.0],
            "risk_reward": [1.5, 2.0],
        },
    },
    "RSI Extreme": {
        "factory": lambda p: RSIExtremeStrategy(rsi_period=p["rsi_period"], oversold=p["oversold"],
                                                  overbought=p["overbought"]),
        "params": {
            "rsi_period": [10, 14, 20],
            "oversold": [25, 30, 35],
            "overbought": [65, 70, 75],
        },
    },
    "VWAP Reversion": {
        "factory": lambda p: VWAPRevertStrategy(band_threshold=p["band_threshold"],
                                                  exit_threshold=p["exit_threshold"],
                                                  max_position_duration=p["max_position_duration"]),
        "params": {
            "band_threshold": [0.003, 0.005, 0.007],
            "exit_threshold": [0.001, 0.002],
            "max_position_duration": [30, 50, 100],
        },
    },
    "Range Breakout": {
        "factory": lambda p: RangeBreakoutStrategy(lookback=p["lookback"],
                                                     confirmation_bars=p["confirmation_bars"],
                                                     atr_multiplier=p["atr_multiplier"],
                                                     risk_reward=p["risk_reward"]),
        "params": {
            "lookback": [15, 20, 30],
            "confirmation_bars": [1, 2],
            "atr_multiplier": [1.5, 2.0],
            "risk_reward": [1.5, 2.0],
        },
    },
    "Volume Surge": {
        "factory": lambda p: VolumeSurgeStrategy(lookback=p["lookback"],
                                                  volume_multiplier=p["volume_multiplier"],
                                                  price_lookback=20),
        "params": {
            "lookback": [15, 20, 30],
            "volume_multiplier": [1.5, 2.0, 2.5, 3.0],
        },
    },
    "RSI + MACD Combo": {
        "factory": lambda p: RSIMACDComboStrategy(rsi_period=p["rsi_period"], macd_fast=p["macd_fast"],
                                                   macd_slow=p["macd_slow"], macd_signal=p["macd_signal"]),
        "params": {
            "rsi_period": [10, 14, 20],
            "macd_fast": [10, 12],
            "macd_slow": [24, 26],
            "macd_signal": [7, 9],
        },
    },
}


def grid_combinations(params_dict: dict):
    keys = list(params_dict.keys())
    for combo in product(*params_dict.values()):
        yield dict(zip(keys, combo))


def run_single_backtest(factory, params, df, initial_capital, commission, slippage_bps):
    """Run backtest for a single param combination."""
    try:
        strategy = factory(params)
    except Exception as e:
        return None, str(e)

    engine = BacktestEngine(fill_mode=FillMode.NEXT_OPEN, exchange=None, min_trade_size=10.0)
    try:
        result = engine.run(strategy, df, initial_capital=initial_capital,
                           commission=commission, slippage=slippage_bps)
        return result, None
    except Exception as e:
        return None, str(e)


def format_metrics(result) -> dict:
    if result is None:
        return {}
    m = result.metrics
    return {
        "return_pct": round(m.get("total_return", 0) * 100, 2),
        "sharpe": round(m.get("sharpe_ratio") or 0, 2),
        "maxdd_pct": round(m.get("max_drawdown_pct", 0), 2),
        "winrate": round((m.get("win_rate") or 0) * 100, 1),
        "trades": m.get("trade_count", 0),
        "profit_factor": round(m.get("profit_factor") or 0, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main execution
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Fetching BTC/USDC 1h data from Binance...", flush=True)

    feed = BinanceFeed(mode="spot", testnet=False)
    since_ms = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
    until_ms = int(pd.Timestamp("2025-04-26", tz="UTC").timestamp() * 1000)
    df = feed.fetch_ohlcv_range("BTC", timeframe="1h", since=since_ms, until=until_ms, limit=1000)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df = df[["open", "high", "low", "close", "volume"]].copy()

    print(f"Loaded {len(df)} bars: {df.index[0]} → {df.index[-1]}", flush=True)

    INITIAL_CAPITAL = 10_000.0
    COMMISSION = 0.0004
    SLIPPAGE = 0.0005  # 5 bps
    SLIPPAGE_BPS = SLIPPAGE  # BacktestEngine expects fraction, not bps

    results = {}

    strategy_order = [
        "EMA Cross", "Supertrend", "Trendline Break",
        "Bollinger Reversion", "RSI Extreme", "VWAP Reversion",
        "Range Breakout", "Volume Surge", "RSI + MACD Combo",
    ]

    for strategy_name in strategy_order:
        print(f"\n══ {strategy_name} ══", flush=True)
        entry = STRATEGY_GRIDS[strategy_name]
        param_grid = entry["params"]
        factory = entry["factory"]

        best_result = None
        best_params = None
        best_score = -np.inf
        total_combos = 0
        total_valid = 0

        for params in grid_combinations(param_grid):
            result, err = run_single_backtest(factory, params, df,
                                              INITIAL_CAPITAL, COMMISSION, SLIPPAGE_BPS)
            total_combos += 1
            if err or result is None:
                continue
            total_valid += 1
            sharpe = result.metrics.get("sharpe_ratio") or 0
            total_ret = result.metrics.get("total_return", 0)
            # Score: primarily Sharpe, secondary total return
            score = sharpe + 0.01 * total_ret
            if score > best_score:
                best_score = score
                best_result = result
                best_params = params

        if best_result is None:
            print(f"  ⚠ No valid backtests ({total_combos} combos attempted)", flush=True)
            results[strategy_name] = None
            continue

        fm = format_metrics(best_result)
        print(f"  Tested {total_combos} combos, {total_valid} valid", flush=True)
        print(f"  Return: {fm['return_pct']}% | Sharpe: {fm['sharpe']} | MaxDD: {fm['maxdd_pct']}%", flush=True)
        print(f"  WinRate: {fm['winrate']}% | Trades: {fm['trades']} | PF: {fm['profit_factor']}", flush=True)
        print(f"  Params: {best_params}", flush=True)

        results[strategy_name] = {
            "result": best_result,
            "params": best_params,
            "metrics": fm,
        }

    # ─── Build report ───────────────────────────────────────────────────────
    report_lines = ["# ACTosha Backtest Results\n"]
    report_lines.append(f"**Symbol:** BTC/USDC (Binance Spot)\n")
    report_lines.append(f"**Timeframe:** 1h\n")
    report_lines.append(f"**Period:** 2025-04-25 → 2026-04-25\n")
    report_lines.append(f"**Bars:** {len(df)}\n")
    report_lines.append(f"**Initial Capital:** $10,000\n")
    report_lines.append(f"**Commission:** 0.04% | **Slippage:** 5 bps\n")
    report_lines.append(f"**Optimization:** Grid search\n")

    for strategy_name, data in results.items():
        if data is None:
            report_lines.append(f"\n## {strategy_name}\n")
            report_lines.append("⚠ No valid backtest results.\n")
            continue

        m = data["metrics"]
        p = data["params"]

        report_lines.append(f"\n## {strategy_name}\n")
        report_lines.append(f"| Metric | Value |\n|---|---|\n")
        report_lines.append(f"| Return | {m['return_pct']}% |\n")
        report_lines.append(f"| Sharpe | {m['sharpe']} |\n")
        report_lines.append(f"| MaxDD | {m['maxdd_pct']}% |\n")
        report_lines.append(f"| WinRate | {m['winrate']}% |\n")
        report_lines.append(f"| Trades | {m['trades']} |\n")
        report_lines.append(f"| Profit Factor | {m['profit_factor']} |\n")
        report_lines.append(f"| Best params | {p} |\n")

    # ─── Summary table ───────────────────────────────────────────────────────
    report_lines.append("\n## Summary Table\n\n")
    report_lines.append("| Strategy | Return | Sharpe | MaxDD% | WinRate% | Trades | ProfitFactor |\n")
    report_lines.append("|---|---|---|---|---|---|---|---|\n")

    for strategy_name in strategy_order:
        data = results.get(strategy_name)
        if data is None:
            report_lines.append(f"| {strategy_name} | N/A | N/A | N/A | N/A | N/A | N/A |")
        else:
            m = data["metrics"]
            report_lines.append(f"| {strategy_name} | {m['return_pct']}% | {m['sharpe']} | {m['maxdd_pct']}% | {m['winrate']}% | {m['trades']} | {m['profit_factor']} |")

    # ─── Recommendation ─────────────────────────────────────────────────────
    valid_results = [(n, d) for n, d in results.items() if d is not None]
    if valid_results:
        ranked = sorted(valid_results, key=lambda x: (x[1]["metrics"]["sharpe"], x[1]["metrics"]["return_pct"]), reverse=True)
        best_strategy = ranked[0][0]
        best_metrics = ranked[0][1]["metrics"]
        best_params = ranked[0][1]["params"]

        report_lines.append(f"\n## Recommendation\n\n")
        report_lines.append(f"**Best strategy:** {best_strategy}\n\n")
        report_lines.append(f"| Metric | Value |\n|---|---|\n")
        report_lines.append(f"| Sharpe | {best_metrics['sharpe']} |\n")
        report_lines.append(f"| Return | {best_metrics['return_pct']}% |\n")
        report_lines.append(f"| Max Drawdown | {best_metrics['maxdd_pct']}% |\n")
        report_lines.append(f"| WinRate | {best_metrics['winrate']}% |\n")
        report_lines.append(f"| Trades | {best_metrics['trades']} |\n")
        report_lines.append(f"| Profit Factor | {best_metrics['profit_factor']} |\n")
        report_lines.append(f"| Best params | {best_params} |\n")

        report_lines.append("\n### Full Ranking (by Sharpe)\n\n")
        for i, (name, data) in enumerate(ranked, 1):
            m = data["metrics"]
            report_lines.append(f"{i}. **{name}** — Sharpe {m['sharpe']}, Return {m['return_pct']}%, MaxDD {m['maxdd_pct']}%, PF {m['profit_factor']}\n")

    report = "".join(report_lines)

    output_path = "/Users/seed1nvestor/.openclaw/workspace/ACTosha/backtest_results_2026.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"\n✅ Report saved to {output_path}", flush=True)


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *args: (print("TIMEOUT", flush=True), sys.exit(1)))
    signal.alarm(1800)  # 30 min timeout
    main()
    signal.alarm(0)