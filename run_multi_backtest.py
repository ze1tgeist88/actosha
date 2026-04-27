#!/usr/bin/env python3
"""
ACTosha Multi-Symbol Multi-Timeframe Backtest
=============================================
Symbols  : BTC/USDC:USDC, ETH/USDC:USDC (Hyperliquid)
Timeframes: 1h, 4h, 1d
Period  : 2025-04-25 → 2026-04-25
Strategies: 13 (all from run_backtest.py + run_new_strategies_backtest.py)
Setup   : $10,000 initial | 0.04% commission | 5 bps slippage | Grid optimization
Output  : backtest_multi.tf.md
"""

import sys, os, signal, warnings, traceback
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from ACTosha.backtester.engine import BacktestEngine
from ACTosha.backtester.simulator import FillMode
from ACTosha.datafeeder.hyperliquid import HyperliquidFeed
from ACTosha.indicators.momentum import compute_rsi, compute_macd
from ACTosha.indicators.volatility import compute_atr, compute_bollinger_bands
from ACTosha.indicators.moving_averages import compute_ema
from ACTosha.strategies.base import SignalBundle, BaseStrategy
from ACTosha.strategies.trend.ema_cross import EMACrossStrategy
from ACTosha.strategies.breakout.range_breakout import RangeBreakoutStrategy
from ACTosha.strategies.mean_reversion.bollinger_revert import BollingerRevertStrategy
from ACTosha.strategies.mean_reversion.vwap_revert import VWAPRevertStrategy
from ACTosha.strategies.trend.bb_ema_combo import BBEMAComboStrategy
from ACTosha.strategies.trend.ichimoku_strategy import IchimokuStrategy
from ACTosha.strategies.momentum.obv_divergence import OBVDivergenceStrategy
from ACTosha.strategies.trend.ha_smoothed import HASmoothedStrategy

# ─────────────────────────────────────────────────────────────────────────────
# Strategy implementations (inline for non-implemented strategies)
# ─────────────────────────────────────────────────────────────────────────────

class SupertrendStrategy(BaseStrategy):
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
        close = data["close"]
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[cross_up] = "long"
        sides[cross_down] = "short"
        spread = data[atr_col] * self._multiplier
        spread_ma = spread.rolling(20, min_periods=1).mean()
        strength = (spread / spread_ma.replace(0, 1)).clip(0, 1).fillna(0.5)
        signals = pd.DataFrame({"side": sides, "strength": strength, "entry_price": close,
                               "stop_loss": None, "take_profit": None,
                               "metadata": [{}] * len(data)})
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
        roll_max = high.rolling(self._lookback, min_periods=self._lookback).max().shift(1)
        roll_min = low.rolling(self._lookback, min_periods=self._lookback).min().shift(1)
        breakout_up = close > roll_max * (1 + self._retest_tolerance)
        breakout_down = close < roll_min * (1 - self._retest_tolerance)
        confirm_up = breakout_up & (slope_up > 0)
        confirm_down = breakout_down & (slope_up < 0)
        sides = pd.Series("none", index=df.index, dtype="string")
        sides[confirm_up] = "long"
        sides[confirm_down] = "short"
        strength_arr = (close - roll_max).where(confirm_up, 0) + (roll_min - close).where(confirm_down, 0)
        strengths = strength_arr.clip(0, 1).fillna(0.5)
        signals = pd.DataFrame({"side": sides, "strength": strengths, "entry_price": close,
                               "stop_loss": None, "take_profit": None,
                               "metadata": [{}] * len(df)})
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
        signals = pd.DataFrame({"side": sides, "strength": strength, "entry_price": close,
                               "stop_loss": None, "take_profit": None,
                               "metadata": [{}] * len(df)})
        data = compute_atr(data, period=14)
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


class RSIMACDComboStrategy(BaseStrategy):
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
        macd_signal_col = data["macd_signal"]
        rsi_above50 = rsi > 50
        prev_rsi_above50 = rsi_above50.shift(1).fillna(False)
        macd_above_signal = macd > macd_signal_col
        prev_macd_above_signal = macd_above_signal.shift(1).fillna(False)
        rsi_cross_up = rsi_above50 & ~prev_rsi_above50
        macd_cross_up = macd_above_signal & ~prev_macd_above_signal
        rsi_below50 = rsi < 50
        prev_rsi_below50 = rsi_below50.shift(1).fillna(False)
        macd_cross_down = (~macd_above_signal) & prev_macd_above_signal
        rsi_cross_down = rsi_below50 & ~prev_rsi_below50
        long_confluence = rsi_cross_up & macd_cross_up
        short_confluence = rsi_cross_down & macd_cross_down
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_confluence] = "long"
        sides[short_confluence] = "short"
        long_exit = rsi_cross_up & ~macd_cross_up
        short_exit = rsi_cross_down & ~macd_cross_down
        sides[long_exit | short_exit] = "close"
        rsi_dist = (rsi - 50).abs() / 50
        macd_abs_ma = macd.abs().rolling(50, min_periods=1).mean().replace(0, 1)
        macd_dist = macd.abs() / macd_abs_ma
        strength = (rsi_dist + macd_dist.clip(0, 1)) / 2
        strength = strength.fillna(0.5).clip(0, 1)
        signals = pd.DataFrame({"side": sides, "strength": strength, "entry_price": close,
                               "stop_loss": None, "take_profit": None,
                               "metadata": [{}] * len(df)})
        data = compute_atr(data, period=14)
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


class VolumeSurgeStrategy(BaseStrategy):
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
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[long_signal] = "long"
        sides[short_signal] = "short"
        vol_ratio = data["volume"] / avg_volume.replace(0, 1)
        range_width = roll_high - roll_low
        price_break = (data["close"] - roll_low).where(long_signal, 0) + \
                      (roll_high - data["close"]).where(short_signal, 0)
        strength = ((vol_ratio / self._volume_multiplier) + (price_break / range_width.replace(0, 1))) / 2
        strength = strength.fillna(0.5).clip(0, 1)
        signals = pd.DataFrame({"side": sides, "strength": strength, "entry_price": data["close"],
                               "stop_loss": None, "take_profit": None,
                               "metadata": [{}] * len(df)})
        data = compute_atr(data, period=14)
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


# ─────────────────────────────────────────────────────────────────────────────
# Strategy grids (13 strategies)
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
    "BBEMACombo": {
        "factory": lambda p: BBEMAComboStrategy(
            ema_period=p["ema_period"], bb_period=p["bb_period"], bb_std=p["bb_std"],
            bb_extreme_threshold=p["bb_extreme_threshold"], min_volume_mult=p["min_volume_mult"],
            use_atr_sl=True, atr_period=14, atr_multiplier=2.0, risk_reward=p["risk_reward"],
        ),
        "params": {
            "ema_period": [14, 21, 30],
            "bb_period": [15, 20, 25],
            "bb_std": [1.5, 2.0, 2.5],
            "bb_extreme_threshold": [0.85, 0.90, 0.95],
            "min_volume_mult": [1.0, 1.5],
            "risk_reward": [1.5, 2.0],
        },
    },
    "Ichimoku": {
        "factory": lambda p: IchimokuStrategy(
            tenkan_period=p["tenkan_period"], kijun_period=p["kijun_period"],
            senkou_b_period=p["senkou_b_period"], cloud_shift=26,
            chikou_confirm=p["chikou_confirm"], cloud_thickness_filter=False,
            max_cloud_width=p["max_cloud_width"], use_atr_sl=True, atr_period=14,
            atr_multiplier=2.0, risk_reward=p["risk_reward"],
        ),
        "params": {
            "tenkan_period": [7, 9, 12],
            "kijun_period": [22, 26, 30],
            "senkou_b_period": [44, 52, 65],
            "chikou_confirm": [True, False],
            "max_cloud_width": [4.0, 5.0, 6.0],
            "risk_reward": [1.5, 2.0],
        },
    },
    "OBVDivergence": {
        "factory": lambda p: OBVDivergenceStrategy(
            obv_ema_period=p["obv_ema_period"], price_lookback=p["price_lookback"],
            divergence_lookback=p["divergence_lookback"], min_volume_mult=p["min_volume_mult"],
            require_exact_swing=False, swing_tolerance=0.05,
            use_atr_sl=True, atr_period=14, atr_multiplier=2.0, risk_reward=p["risk_reward"],
        ),
        "params": {
            "obv_ema_period": [14, 21, 30],
            "price_lookback": [3, 5, 7],
            "divergence_lookback": [30, 50],
            "min_volume_mult": [1.0, 1.5],
            "risk_reward": [1.5, 2.0],
        },
    },
    "HASmoothed": {
        "factory": lambda p: HASmoothedStrategy(
            ha_smooth_ema=p["ha_smooth_ema"], consecutive_bars=p["consecutive_bars"],
            volume_ma_period=20, min_volume_mult=p["min_volume_mult"],
            trailing_mode=True, use_atr_sl=True, atr_period=14, atr_multiplier=2.0,
            risk_reward=p["risk_reward"],
        ),
        "params": {
            "ha_smooth_ema": [3, 5, 7],
            "consecutive_bars": [5, 7, 10],
            "min_volume_mult": [1.0, 1.5],
            "risk_reward": [1.5, 2.0],
        },
    },
}

STRATEGY_ORDER = list(STRATEGY_GRIDS.keys())

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def grid_combinations(params_dict: dict):
    keys = list(params_dict.keys())
    for combo in product(*params_dict.values()):
        yield dict(zip(keys, combo))


def run_single_backtest(factory, params, df, initial_capital, commission, slippage_bps):
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


def best_of_strategy(strategy_name, entry, df, initial_capital, commission, slippage_bps, max_retries=3):
    """Run full grid for one strategy, return best result + params."""
    factory = entry["factory"]
    param_grid = entry["params"]

    best_result = None
    best_params = None
    best_score = -np.inf
    total_combos = 0
    total_valid = 0

    for params in grid_combinations(param_grid):
        result, err = run_single_backtest(factory, params, df,
                                          initial_capital, commission, slippage_bps)
        total_combos += 1
        if err or result is None:
            continue
        total_valid += 1
        sharpe = result.metrics.get("sharpe_ratio") or 0
        total_ret = result.metrics.get("total_return", 0)
        score = sharpe + 0.01 * total_ret
        if score > best_score:
            best_score = score
            best_result = result
            best_params = params

    return {
        "result": best_result,
        "params": best_params,
        "metrics": format_metrics(best_result),
        "total_combos": total_combos,
        "total_valid": total_valid,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data fetching
# ─────────────────────────────────────────────────────────────────────────────

def fetch_data_for_combination(symbol, timeframe, since_ms, until_ms, max_retries=3):
    """Fetch OHLCV from Hyperliquid with retries. Returns (df, error)."""
    feed = HyperliquidFeed(testnet=False)
    ccxt_symbol = f"{symbol}/USDC:USDC" if ":" not in symbol else symbol

    for attempt in range(max_retries):
        try:
            # For 1d, need to fetch more bars (limit per page 500 for Hyperliquid)
            if timeframe == "1d":
                limit = 400  # ~400 days needed
            elif timeframe == "4h":
                limit = 500  # ~833 days, but HL limit is 500
            else:
                limit = 500  # ~21 days, need multiple pages for 1 year

            all_bars = []
            current_since = since_ms

            while len(all_bars) < 9000:  # arbitrary upper bound
                batch = feed._fetch_page(ccxt_symbol, timeframe, current_since, limit)
                if not batch:
                    break
                all_bars.extend(batch)
                if len(batch) < limit:
                    break
                # Move forward
                last_ts = batch[-1][0]
                current_since = last_ts + 1
                if current_since >= until_ms:
                    break

            if not all_bars:
                return None, "No data returned"

            # Normalize
            raw_df = pd.DataFrame(all_bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
            raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"], unit="ms", utc=True)
            raw_df.set_index("timestamp", inplace=True)
            raw_df = raw_df.sort_index()
            raw_df = raw_df[["open", "high", "low", "close", "volume"]].copy()
            raw_df = raw_df.astype({"open": "float64", "high": "float64", "low": "float64",
                                     "close": "float64", "volume": "float64"})

            # Filter to period
            start_dt = pd.Timestamp("2025-04-25", tz="UTC")
            end_dt = pd.Timestamp("2026-04-26", tz="UTC")
            raw_df = raw_df[raw_df.index >= start_dt]
            raw_df = raw_df[raw_df.index < end_dt]

            if len(raw_df) < 30:
                return None, f"Only {len(raw_df)} bars after period filter"

            return raw_df, None

        except Exception as e:
            if attempt == max_retries - 1:
                return None, str(e)
            import time
            time.sleep(2 ** attempt)

    return None, "Max retries exceeded"


# ─────────────────────────────────────────────────────────────────────────────
# Worker for parallel execution
# ─────────────────────────────────────────────────────────────────────────────

def run_strategy_worker(args):
    """Worker: run one strategy on one df. Returns (strategy_name, metrics_dict)."""
    strategy_name, entry, df_json_path, initial_capital, commission, slippage_bps = args

    # Load df from temporary CSV to avoid pickling DataFrames
    try:
        df = pd.read_pickle(df_json_path)
    except Exception:
        return strategy_name, None, None, 0, 0, f"Failed to load df"

    result_data = best_of_strategy(strategy_name, entry, df, initial_capital, commission, slippage_bps)
    return (strategy_name, result_data["result"], result_data["params"],
            result_data["metrics"], result_data["total_combos"], result_data["total_valid"], None)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    INITIAL_CAPITAL = 10_000.0
    COMMISSION = 0.0004
    SLIPPAGE_BPS = 0.0005  # 5 bps

    SYMBOLS = ["BTC", "ETH"]
    TIMEFRAMES = ["1h", "4h", "1d"]
    SINCE_MS = int(pd.Timestamp("2025-04-25", tz="UTC").timestamp() * 1000)
    UNTIL_MS = int(pd.Timestamp("2026-04-26", tz="UTC").timestamp() * 1000)

    # Phase 1: Fetch all data for all symbol+timeframe combinations
    print("=" * 70)
    print("PHASE 1: Data Fetching")
    print("=" * 70)

    data_cache = {}
    cache_dir = "/tmp/ACTosha_bt_cache"
    os.makedirs(cache_dir, exist_ok=True)

    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            key = f"{symbol}_{tf}"
            cache_path = f"{cache_dir}/{key}.pkl"
            print(f"\n[{symbol}] [{tf}] Fetching...", flush=True)

            # Check cache
            if os.path.exists(cache_path):
                try:
                    df = pd.read_pickle(cache_path)
                    print(f"  ✓ Loaded from cache: {len(df)} bars")
                    data_cache[key] = (df, None)
                    continue
                except Exception:
                    pass

            df, err = fetch_data_for_combination(symbol, tf, SINCE_MS, UNTIL_MS)
            if err:
                print(f"  ⚠ Failed: {err}", flush=True)
                data_cache[key] = (None, err)
            else:
                df.to_pickle(cache_path)
                print(f"  ✓ {len(df)} bars: {df.index[0]} → {df.index[-1]}", flush=True)
                data_cache[key] = (df, None)

    # Phase 2: Run all strategies for each combination
    print("\n" + "=" * 70)
    print("PHASE 2: Strategy Backtesting")
    print("=" * 70)

    all_results = {}  # symbol → tf → strategy_name → metrics

    for symbol in SYMBOLS:
        all_results[symbol] = {}

        for tf in TIMEFRAMES:
            key = f"{symbol}_{tf}"
            df, err = data_cache[key]

            if err or df is None:
                print(f"\n=== {symbol} {tf} === ⚠ DATA UNAVAILABLE: {err}")
                all_results[symbol][tf] = {}
                for sname in STRATEGY_ORDER:
                    all_results[symbol][tf][sname] = None
                continue

            cache_path = f"{cache_dir}/{key}.pkl"
            if not os.path.exists(cache_path):
                df.to_pickle(cache_path)

            print(f"\n=== {symbol} {tf} === {len(df)} bars, running 13 strategies...", flush=True)

            strategy_results = {}

            for sname in STRATEGY_ORDER:
                entry = STRATEGY_GRIDS[sname]
                print(f"  {sname}...", end=" ", flush=True)

                result_data = best_of_strategy(sname, entry, df,
                                               INITIAL_CAPITAL, COMMISSION, SLIPPAGE_BPS)
                fm = result_data["metrics"]
                trades = fm.get("trades", 0) if fm else 0

                if result_data["result"] is None or trades == 0:
                    print(f"⚠ 0 trades", flush=True)
                    strategy_results[sname] = None
                else:
                    print(f"Sharpe={fm['sharpe']}, Ret={fm['return_pct']}%, "
                          f"MaxDD={fm['maxdd_pct']}%, Trades={trades}, "
                          f"WR={fm['winrate']}%, PF={fm['profit_factor']} "
                          f"[{result_data['total_valid']}/{result_data['total_combos']}]",
                          flush=True)
                    strategy_results[sname] = {
                        "metrics": fm,
                        "params": result_data["params"],
                    }

            all_results[symbol][tf] = strategy_results

    # Phase 3: Generate report
    print("\n" + "=" * 70)
    print("PHASE 3: Report Generation")
    print("=" * 70)

    lines = []
    lines.append("# ACTosha Multi-Strategy Backtest\n")
    lines.append("| Setting | Value |\n")
    lines.append("|---|---|\n")
    lines.append("| **Symbols** | BTC/USDC:USDC, ETH/USDC:USDC (Hyperliquid) |\n")
    lines.append("| **Timeframes** | 1h, 4h, 1d |\n")
    lines.append("| **Period** | 2025-04-25 → 2026-04-26 |\n")
    lines.append("| **Initial Capital** | $10,000 |\n")
    lines.append("| **Commission** | 0.04% (Maker) |\n")
    lines.append("| **Slippage** | 5 bps |\n")
    lines.append("| **Optimization** | Grid search |\n")
    lines.append("| **Strategies** | 13 |\n")

    # Per-combination tables
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            key = f"{symbol}_{tf}"
            df, err = data_cache[key]

            lines.append(f"\n=== {symbol} {tf} ===\n")

            if err or df is None:
                lines.append("⚠ **Data unavailable**\n")
                continue

            lines.append(f"| Strategy | Return | Sharpe | MaxDD% | WinRate% | Trades | PF |\n")
            lines.append("|---|---|---|---|---|---|---|\n")

            no_data = True
            for sname in STRATEGY_ORDER:
                res = all_results[symbol][tf].get(sname)
                if res is None:
                    lines.append(f"| {sname} | ⚠ N/A | ⚠ N/A | ⚠ N/A | ⚠ N/A | ⚠ N/A | ⚠ N/A |\n")
                else:
                    m = res["metrics"]
                    lines.append(f"| {sname} | {m['return_pct']}% | {m['sharpe']} | "
                                 f"{m['maxdd_pct']}% | {m['winrate']}% | {m['trades']} | {m['profit_factor']} |\n")
                    no_data = False

    # Symbol summaries
    for symbol in SYMBOLS:
        lines.append(f"\n=== {symbol} Summary (all timeframes) ===\n")

        best_by_sharpe = {}
        best_by_return = {}
        best_by_maxdd = {}

        for tf in TIMEFRAMES:
            tf_results = all_results[symbol][tf]
            valid_strategies = [(s, tf_results[s]["metrics"]) for s in STRATEGY_ORDER if tf_results.get(s) is not None]

            if not valid_strategies:
                continue

            by_sharpe = sorted(valid_strategies, key=lambda x: x[1]["sharpe"], reverse=True)
            by_return = sorted(valid_strategies, key=lambda x: x[1]["return_pct"], reverse=True)
            by_maxdd = sorted(valid_strategies, key=lambda x: x[1]["maxdd_pct"])

            if tf not in best_by_sharpe:
                best_by_sharpe[tf] = by_sharpe[0][0] if by_sharpe else None
                best_by_return[tf] = by_return[0][0] if by_return else None
                best_by_maxdd[tf] = by_maxdd[0][0] if by_maxdd else None

        for metric_name, metric_dict in [("Best by Sharpe", best_by_sharpe),
                                          ("Best by Return", best_by_return),
                                          ("Best by MaxDD", best_by_maxdd)]:
            lines.append(f"**{metric_name}:**\n")
            for tf in TIMEFRAMES:
                s = metric_dict.get(tf)
                if s:
                    m = all_results[symbol][tf][s]["metrics"]
                    lines.append(f"- {tf}: **{s}** (Sharpe={m['sharpe']}, Ret={m['return_pct']}%, MaxDD={m['maxdd_pct']}%)\n")

    # Cross-symbol best
    lines.append("\n=== Cross-Symbol Best (all timeframes) ===\n")
    for metric, key_func in [
        ("Sharpe", lambda m: m["sharpe"]),
        ("Return", lambda m: m["return_pct"]),
        ("MaxDD", lambda m: m["maxdd_pct"]),
    ]:
        all_valid = []
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                for sname in STRATEGY_ORDER:
                    res = all_results.get(symbol, {}).get(tf, {}).get(sname)
                    if res is not None:
                        all_valid.append((symbol, tf, sname, res["metrics"]))

        ranked = sorted(all_valid, key=lambda x: key_func(x[3]), reverse=(key_func.__name__ != "maxdd_pct"))
        top5 = ranked[:5]
        lines.append(f"**Best by {metric}:**\n")
        for symbol, tf, sname, m in top5:
            lines.append(f"- [{symbol}] [{tf}] **{sname}** (Sharpe={m['sharpe']}, Ret={m['return_pct']}%, MaxDD={m['maxdd_pct']}%, WR={m['winrate']}%, PF={m['profit_factor']}, Trades={m['trades']})\n")

    report = "".join(lines)

    output_path = "/Users/seed1nvestor/.openclaw/workspace/ACTosha/backtest_multi.tf.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"\n✅ Report saved to {output_path}")


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *args: (print("TIMEOUT", flush=True), sys.exit(1)))
    signal.alarm(7200)  # 2 hour timeout
    try:
        main()
    finally:
        signal.alarm(0)