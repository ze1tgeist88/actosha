#!/usr/bin/env python3
"""ACTosha Binance Futures Backtest 2025-04-25 → 2026-04-26 — FINAL"""
import sys, os, time, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from itertools import product

from ACTosha.backtester.engine import BacktestEngine
from ACTosha.backtester.simulator import FillMode
from ACTosha.datafeeder.binance import BinanceFeed
from ACTosha.indicators.momentum import compute_rsi, compute_macd
from ACTosha.indicators.volatility import compute_atr
from ACTosha.strategies.base import SignalBundle, BaseStrategy
from ACTosha.strategies.trend.ema_cross import EMACrossStrategy
from ACTosha.strategies.breakout.range_breakout import RangeBreakoutStrategy
from ACTosha.strategies.mean_reversion.bollinger_revert import BollingerRevertStrategy
from ACTosha.strategies.trend.ichimoku_strategy import IchimokuStrategy
from ACTosha.strategies.momentum.obv_divergence import OBVDivergenceStrategy
from ACTosha.strategies.trend.ha_smoothed import HASmoothedStrategy
from ACTosha.strategies.trend.bb_ema_combo import BBEMAComboStrategy
from ACTosha.strategies.momentum.rsi_macd_combo import RSIMACDComboStrategy


# ── Inline strategies ────────────────────────────────────────────────────────────
class SupertrendStrategy(BaseStrategy):
    def __init__(self, period=10, multiplier=3.0, initial_capital=10_000.0, risk_per_trade=0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._p = period; self._m = multiplier
    @property
    def name(self): return f"Supertrend_{self._p}_{self._m}"
    def get_params(self): return {**super().get_params(), "period": self._p, "multiplier": self._m}
    def generate_signals(self, df):
        self.validate_df(df)
        data = compute_atr(df.copy(), period=self._p)
        ac = f"atr_{self._p}"; hl2 = (data["high"] + data["low"]) / 2
        ub = hl2 + self._m * data[ac]; lb = hl2 - self._m * data[ac]
        in_up = pd.Series(True, index=data.index)
        for i in range(1, len(data)):
            cc = data["close"].iloc[i]
            pu = ub.iloc[i-1]; pl = lb.iloc[i-1]
            in_up.iloc[i] = (True if cc > pu else False) if cc < pl else (False if cc < pl else in_up.iloc[i-1])
        pu = in_up.shift(1).fillna(True); cu = in_up & ~pu; cd = (~in_up) & pu
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[cu] = "long"; sides[cd] = "short"
        spr = data[ac] * self._m; sma = spr.rolling(20, min_periods=1).mean()
        strength = (spr / sma.replace(0, 1)).clip(0, 1).fillna(0.5)
        sigs = pd.DataFrame({"side": sides, "strength": strength, "entry_price": data["close"],
                              "stop_loss": None, "take_profit": None, "metadata": [{}] * len(data)}, index=data.index)
        for idx in data.index:
            s = sigs.loc[idx, "side"]
            if s not in ("long", "short"): continue
            e = data.loc[idx, "close"]; d = s; av = data.loc[idx, ac]
            sigs.at[idx, "stop_loss"] = self.calc_stop_loss(e, d, atr_value=av, multiplier=2.0)
            sigs.at[idx, "take_profit"] = self.calc_take_profit(e, d, stop_loss=sigs.loc[idx, "stop_loss"], risk_reward=2.0)
        return SignalBundle(signals=sigs, metadata={"strategy": self.name, "params": self.get_params()})


class TrendlineBreakStrategy(BaseStrategy):
    def __init__(self, lookback=50, retest_tolerance=0.005, initial_capital=10_000.0, risk_per_trade=0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._lb = lookback; self._rt = retest_tolerance
    @property
    def name(self): return f"TrendlineBreak_{self._lb}"
    def get_params(self): return {**super().get_params(), "lookback": self._lb, "retest_tolerance": self._rt}
    def generate_signals(self, df):
        self.validate_df(df); cl = df["close"]; hi = df["high"]; lo = df["low"]
        slope = cl.rolling(self._lb, min_periods=self._lb).apply(
            lambda x: np.polyfit(np.arange(len(x)), x, 1)[0] if len(x) >= 5 else 0, raw=True)
        in_up = slope > 0
        rm = hi.rolling(self._lb, min_periods=self._lb).max().shift(1)
        rn = lo.rolling(self._lb, min_periods=self._lb).min().shift(1)
        bu = cl > rm * (1 + self._rt); bd = cl < rn * (1 - self._rt)
        cu = bu & (slope > 0); cd = bd & (slope < 0)
        sides = pd.Series("none", index=df.index, dtype="string")
        sides[cu] = "long"; sides[cd] = "short"
        sa = (cl - rm).where(cu, 0) + (rn - cl).where(cd, 0); strength = sa.clip(0, 1).fillna(0.5)
        sigs = pd.DataFrame({"side": sides, "strength": strength, "entry_price": cl,
                              "stop_loss": None, "take_profit": None, "metadata": [{}] * len(df)}, index=df.index)
        data = compute_atr(df.copy(), 14)
        for idx in data.index:
            s = sigs.loc[idx, "side"]
            if s not in ("long", "short"): continue
            e = data.loc[idx, "close"]; d = s; av = data.loc[idx, "atr_14"]
            sigs.at[idx, "stop_loss"] = self.calc_stop_loss(e, d, atr_value=av, multiplier=2.0)
            sigs.at[idx, "take_profit"] = self.calc_take_profit(e, d, stop_loss=sigs.loc[idx, "stop_loss"], risk_reward=2.0)
        return SignalBundle(signals=sigs, metadata={"strategy": self.name, "params": self.get_params()})


class RSIExtremeStrategy(BaseStrategy):
    def __init__(self, rsi_period=14, oversold=30.0, overbought=70.0, initial_capital=10_000.0, risk_per_trade=0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._rp = rsi_period; self._os = oversold; self._ob = overbought
    @property
    def name(self): return f"RSIExtreme_{self._rp}_{self._os}_{self._ob}"
    def get_params(self): return {**super().get_params(), "rsi_period": self._rp, "oversold": self._os, "overbought": self._ob}
    def generate_signals(self, df):
        self.validate_df(df)
        data = compute_rsi(df.copy(), self._rp)
        data = compute_atr(data, 14)
        rc = f"rsi_{self._rp}"; cl = data["close"]; rs = data[rc]
        blo = rs < self._os; abo = rs > self._ob
        wbl = blo.shift(1).fillna(False); wab = abo.shift(1).fillna(False)
        el = blo & ~wbl; es = abo & ~wab
        le = (rs > 50) & (rs.shift(1) <= 50); se = (rs < 50) & (rs.shift(1) >= 50)
        sides = pd.Series("none", index=data.index, dtype="string")
        sides[el] = "long"; sides[es] = "short"
        sides[le & ~el] = "close"; sides[se & ~es] = "close"
        strength = ((self._os - rs).clip(0, self._os) / self._os +
                    (rs - self._ob).clip(0, 100 - self._ob) / (100 - self._ob)).fillna(0.5).clip(0, 1)
        sigs = pd.DataFrame({"side": sides, "strength": strength, "entry_price": cl,
                              "stop_loss": None, "take_profit": None, "metadata": [{}] * len(data)}, index=data.index)
        for idx in data.index:
            s = sigs.loc[idx, "side"]
            if s not in ("long", "short"): continue
            e = data.loc[idx, "close"]; d = s; av = data.loc[idx, "atr_14"]
            sigs.at[idx, "stop_loss"] = self.calc_stop_loss(e, d, atr_value=av, multiplier=2.0)
            sigs.at[idx, "take_profit"] = self.calc_take_profit(e, d, stop_loss=sigs.loc[idx, "stop_loss"], risk_reward=2.0)
        return SignalBundle(signals=sigs, metadata={"strategy": self.name, "params": self.get_params()})


class VWAPRevertStrategy(BaseStrategy):
    def __init__(self, band_threshold=0.005, exit_threshold=0.001, max_position_duration=50,
                 initial_capital=10_000.0, risk_per_trade=0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._bt = band_threshold; self._et = exit_threshold; self._mpd = max_position_duration
    @property
    def name(self): return f"VWAPRevert_{self._bt}"
    def get_params(self): return {**super().get_params(), "band_threshold": self._bt, "exit_threshold": self._et, "max_position_duration": self._mpd}
    def generate_signals(self, df):
        self.validate_df(df); data = df.copy()
        tp = (data["high"] + data["low"] + data["close"]) / 3
        data["vwap"] = (tp * data["volume"]).cumsum() / data["volume"].cumsum()
        sigs = pd.DataFrame({"side": "none", "strength": 0.0, "entry_price": data["close"],
                              "stop_loss": None, "take_profit": None, "metadata": [{}] * len(data)}, index=data.index)
        po = False; ps = None; ei = 0
        for i, idx in enumerate(data.index):
            if not po:
                dev = (data.loc[idx, "close"] - data.loc[idx, "vwap"]) / data.loc[idx, "vwap"]
                if dev < -self._bt:
                    sigs.at[idx, "side"] = "long"; sigs.at[idx, "strength"] = min(abs(dev) / self._bt, 1.0)
                    sigs.at[idx, "stop_loss"] = data.loc[idx, "close"] * (1 - 2 * self._bt)
                    sigs.at[idx, "take_profit"] = data.loc[idx, "vwap"]
                    po = True; ps = "long"; ei = i
                elif dev > self._bt:
                    sigs.at[idx, "side"] = "short"; sigs.at[idx, "strength"] = min(abs(dev) / self._bt, 1.0)
                    sigs.at[idx, "stop_loss"] = data.loc[idx, "close"] * (1 + 2 * self._bt)
                    sigs.at[idx, "take_profit"] = data.loc[idx, "vwap"]
                    po = True; ps = "short"; ei = i
            else:
                dev = (data.loc[idx, "close"] - data.loc[idx, "vwap"]) / data.loc[idx, "vwap"]
                bh = i - ei; se = False
                if ps == "long":
                    if dev >= -self._et or bh >= self._mpd: se = True
                else:
                    if dev <= self._et or bh >= self._mpd: se = True
                if se:
                    sigs.at[idx, "side"] = "close"; sigs.at[idx, "strength"] = 0.5; po = False; ps = None
        return SignalBundle(signals=sigs, metadata={"strategy": self.name, "params": self.get_params()})


class VolumeSurgeStrategy(BaseStrategy):
    def __init__(self, lookback=20, volume_multiplier=2.0, price_lookback=20,
                 initial_capital=10_000.0, risk_per_trade=0.02):
        super().__init__(initial_capital=initial_capital, risk_per_trade=risk_per_trade)
        self._lb = lookback; self._vm = volume_multiplier; self._pl = price_lookback
    @property
    def name(self): return f"VolumeSurge_{self._lb}_{self._vm}"
    def get_params(self): return {**super().get_params(), "lookback": self._lb, "volume_multiplier": self._vm, "price_lookback": self._pl}
    def generate_signals(self, df):
        self.validate_df(df); data = df.copy()
        av = data["volume"].rolling(self._lb, min_periods=self._lb).mean()
        vs = data["volume"] > av * self._vm
        rh = data["high"].rolling(self._pl, min_periods=self._pl).max()
        rl = data["low"].rolling(self._pl, min_periods=self._pl).min()
        bu = data["close"] > rh.shift(1); bd = data["close"] < rl.shift(1)
        ls = bu & vs; ss = bd & vs
        sides = pd.Series("none", index=df.index, dtype="string")
        sides[ls] = "long"; sides[ss] = "short"
        vr = data["volume"] / av.replace(0, 1); rw = rh - rl
        pb = (data["close"] - rl).where(ls, 0) + (rh - data["close"]).where(ss, 0)
        strength = ((vr / self._vm) + pb / rw.replace(0, 1)).clip(0, 1).fillna(0.5) / 2
        sigs = pd.DataFrame({"side": sides, "strength": strength, "entry_price": data["close"],
                              "stop_loss": None, "take_profit": None, "metadata": [{}] * len(df)}, index=df.index)
        data = compute_atr(data, 14)
        for idx in data.index:
            s = sigs.loc[idx, "side"]
            if s not in ("long", "short"): continue
            e = data.loc[idx, "close"]; d = s; av = data.loc[idx, "atr_14"]
            sigs.at[idx, "stop_loss"] = self.calc_stop_loss(e, d, atr_value=av, multiplier=2.0)
            sigs.at[idx, "take_profit"] = self.calc_take_profit(e, d, stop_loss=sigs.loc[idx, "stop_loss"], risk_reward=2.0)
        return SignalBundle(signals=sigs, metadata={"strategy": self.name, "params": self.get_params()})


# ── Strategy grids ──────────────────────────────────────────────────────────────
GRIDS = {
    "EMA Cross":        {"f": lambda p: EMACrossStrategy(fast_period=p["fp"], slow_period=p["sp"],
                                                          atr_multiplier=p["am"], risk_reward=p["rr"]),
                         "p": {"fp": [9, 12], "sp": [21, 30], "am": [2.0, 3.0], "rr": [1.5, 2.0]}},
    "Supertrend":       {"f": lambda p: SupertrendStrategy(period=p["p"], multiplier=p["m"]),
                         "p": {"p": [10, 14], "m": [2.0, 3.0, 4.0]}},
    "Trendline Break":  {"f": lambda p: TrendlineBreakStrategy(lookback=p["lb"], retest_tolerance=p["rt"]),
                         "p": {"lb": [30, 50], "rt": [0.003, 0.005]}},
    "Bollinger Rev":    {"f": lambda p: BollingerRevertStrategy(bb_period=p["bp"], bb_std=p["bs"],
                                                                 atr_multiplier=p["am"], risk_reward=p["rr"]),
                         "p": {"bp": [20, 25], "bs": [2.0, 2.5], "am": [2.0, 3.0], "rr": [1.5, 2.0]}},
    "RSI Extreme":      {"f": lambda p: RSIExtremeStrategy(rsi_period=p["rp"], oversold=p["os"], overbought=p["ob"]),
                         "p": {"rp": [14, 20], "os": [25, 30], "ob": [65, 70]}},
    "VWAP Reversion":  {"f": lambda p: VWAPRevertStrategy(band_threshold=p["bt"], exit_threshold=p["et"],
                                                           max_position_duration=p["md"]),
                         "p": {"bt": [0.003, 0.005], "et": [0.001, 0.002], "md": [50, 100]}},
    "Range Breakout":   {"f": lambda p: RangeBreakoutStrategy(lookback=p["lb"], confirmation_bars=p["cb"],
                                                              atr_multiplier=p["am"], risk_reward=p["rr"]),
                         "p": {"lb": [20, 30], "cb": [1, 2], "am": [2.0], "rr": [1.5, 2.0]}},
    "Volume Surge":     {"f": lambda p: VolumeSurgeStrategy(lookback=p["lb"], volume_multiplier=p["vm"]),
                         "p": {"lb": [20, 30], "vm": [1.5, 2.0, 2.5]}},
    "RSI + MACD Combo": {"f": lambda p: RSIMACDComboStrategy(rsi_period=p["rp"], macd_fast=p["mf"],
                                                              macd_slow=p["ms"], macd_signal=p["mg"]),
                         "p": {"rp": [14, 20], "mf": [12], "ms": [24, 26], "mg": [7, 9]}},
    "BBEMACombo":       {"f": lambda p: BBEMAComboStrategy(bb_period=p["bp"], bb_std=p["bs"],
                                                           ema_period=p["ep"], atr_multiplier=p["am"],
                                                           risk_reward=p["rr"], initial_capital=10_000.0,
                                                           risk_per_trade=0.02),
                         "p": {"bp": [20, 25], "bs": [2.0, 2.5], "ep": [50, 100], "am": [2.0, 3.0], "rr": [1.5, 2.0]}},
    "Ichimoku":         {"f": lambda p: IchimokuStrategy(tenkan_period=p["tp"], kijun_period=p["kp"],
                                                          senkou_b_period=p["sb"], cloud_shift=26,
                                                          chikou_confirm=p["cc"], cloud_thickness_filter=False,
                                                          max_cloud_width=p["mw"], use_atr_sl=True,
                                                          atr_period=14, atr_multiplier=2.0, risk_reward=p["rr"]),
                         "p": {"tp": [7, 9], "kp": [22, 26], "sb": [44, 52], "cc": [True, False],
                               "mw": [4.0, 5.0], "rr": [1.5, 2.0]}},
    "OBVDivergence":   {"f": lambda p: OBVDivergenceStrategy(obv_ema_period=p["op"], price_lookback=p["pl"],
                                                               divergence_lookback=p["dl"],
                                                               min_volume_mult=p["mv"], require_exact_swing=False,
                                                               swing_tolerance=0.05, use_atr_sl=True,
                                                               atr_period=14, atr_multiplier=2.0, risk_reward=p["rr"]),
                         "p": {"op": [14, 21], "pl": [3, 5], "dl": [30, 50], "mv": [1.0, 1.5], "rr": [1.5, 2.0]}},
    "HASmoothed":      {"f": lambda p: HASmoothedStrategy(ha_smooth_ema=p["he"], consecutive_bars=p["cb"],
                                                           volume_ma_period=20, min_volume_mult=p["mv"],
                                                           trailing_mode=True, use_atr_sl=True,
                                                           atr_period=14, atr_multiplier=2.0, risk_reward=p["rr"]),
                         "p": {"he": [3, 5, 7], "cb": [5, 7, 10], "mv": [1.0, 1.5], "rr": [1.5, 2.0]}},
}
ORDER = list(GRIDS.keys())


def combos(d):
    ks = list(d.keys())
    for c in product(*d.values()):
        yield dict(zip(ks, c))


def run_one(factory, params, df, ic, comm, slip):
    try:
        s = factory(params)
    except Exception:
        return None
    e = BacktestEngine(fill_mode=FillMode.NEXT_OPEN, exchange=None, min_trade_size=10.0)
    try:
        r = e.run(s, df, initial_capic=ic, commission=comm, slippage=slip)
        return r
    except Exception:
        return None


def best_of(entry, df, ic, comm, slip):
    f = entry["f"]; pg = entry["p"]
    best = None; bp = None; bs = -np.inf
    for params in combos(pg):
        r = run_one(f, params, df, ic, comm, slip)
        if r is None:
            continue
        sk = r.metrics.get("sharpe_ratio") or 0
        tr = r.metrics.get("total_return", 0)
        sc = sk + 0.01 * tr
        if sc > bs:
            bs = sc; best = r; bp = params
    return {"result": best, "params": bp}


def fm(r):
    if r is None:
        return {}
    m = r.metrics
    return {
        "ret": round(m.get("total_return", 0) * 100, 2),
        "shr": round(m.metrics.get("sharpe_ratio") or 0, 2),
        "dd": round(m.get("max_drawdown_pct", 0), 2),
        "wr": round((m.get("win_rate") or 0) * 100, 1),
        "tr": m.get("trade_count", 0),
        "pf": round(m.get("profit_factor") or 0, 2)
    }


def build_md(table):
    lines = []
    lines.append("# ACTosha — Binance Futures Backtest 2025-04-25 → 2026-04-26\n\n")
    lines.append("| Metric | Value |\n")
    lines.append("|--------|-------|\n")
    lines.append("| Period | 2025-04-25 → 2026-04-26 |\n")
    lines.append("| Symbols | BTC/USDT, ETH/USDT (Binance USDM perpetuals) |\n")
    lines.append("| Timeframes | 1h, 4h, 1d |\n")
    lines.append("| Strategies | 13 (grid-optimized) |\n")
    lines.append("| Initial Capital | $10,000 |\n")
    lines.append("| Commission | 0.04% (maker/taker combined) |\n")
    lines.append("| Slippage | 5 bps |\n")
    lines.append("| Data Source | BinanceFeed (mode='future'), CCXT, fetch_ohlcv_range() with pagination |\n")
    lines.append("| Optimization | Grid search over parameter space |\n\n")

    lines.append("## Full Results Table\n")
    lines.append("| # | Sym | TF | Strategy | Return% | Sharpe | MaxDD% | WinRate% | Trades | PF |\n")
    lines.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for i, r in enumerate(table, 1):
        lines.append(f"| {i} | {r['sym']} | {r['tf']} | {r['strat']} | {r['ret']:+.1f}% | {r['shr']:+.2f} | {r['dd']:+.1f}% | {r['wr']:+.0f}% | {r['tr']} | {r['pf']:.2f} |\n")

    lines.append("\n## Strategy Summary (avg across symbol/timeframe combos)\n")
    ss = {}
    for r in table:
        sn = r["strat"]
        if sn not in ss:
            ss[sn] = []
        ss[sn].append(r)
    lines.append("| Strategy | Avg Return% | Avg Sharpe | Avg MaxDD% | Avg WinRate% | Avg PF |\n")
    lines.append("|---|---|---|---|---|---|\n")
    for sn in ORDER:
        if sn not in ss:
            continue
        rs = ss[sn]
        avg_ret = np.mean([r["ret"] for r in rs])
        avg_shr = np.mean([r["shr"] for r in rs])
        avg_dd = np.mean([r["dd"] for r in rs])
        avg_wr = np.mean([r["wr"] for r in rs])
        avg_pf = np.mean([r["pf"] for r in rs])
        lines.append(f"| {sn} | {avg_ret:+.1f}% | {avg_shr:+.2f} | {avg_dd:+.1f}% | {avg_wr:+.0f}% | {avg_pf:.2f} |\n")

    lines.append("\n## Best Strategy by Symbol & Timeframe\n")
    for sym in ["BTC", "ETH"]:
        for tf in ["1h", "4h", "1d"]:
            sub = [r for r in table if r["sym"] == sym and r["tf"] == tf]
            if not sub:
                continue
            best = max(sub, key=lambda r: r["shr"] + 0.01 * r["ret"])
            lines.append(f"### {sym} / {tf}\n\n")
            for row in [
                ("**Strategy**", best["strat"]),
                ("**Return**", f"{best['ret']:+.1f}%"),
                ("**Sharpe**", f"{best['shr']:+.2f}"),
                ("**MaxDD**", f"{best['dd']:+.1f}%"),
                ("**WinRate**", f"{best['wr']:+.0f}%"),
                ("**Trades**", str(best["tr"])),
                ("**Profit Factor**", f"{best['pf']:.2f}"),
            ]:
                lines.append(f"{row[0]} | {row[1]}\n")
            lines.append("\n")

    lines.append("## 🏆 Top Picks\n\n")
    all_results = [r for r in table if r["ret"] != 0]
    if all_results:
        by_sharpe = sorted(all_results, key=lambda r: r["shr"], reverse=True)
        by_return = sorted(all_results, key=lambda r: r["ret"], reverse=True)
        lines.append("### Best by Sharpe Ratio\n\n")
        for r in by_sharpe[:5]:
            lines.append(f"| {r['sym']} | {r['tf']} | {r['strat']} | Sharpe={r['shr']:+.2f} | Return={r['ret']:+.1f}% | DD={r['dd']:+.1f}% | Trades={r['tr']} |\n")
        lines.append("\n### Best by Return\n\n")
        for r in by_return[:5]:
            lines.append(f"| {r['sym']} | {r['tf']} | {r['strat']} | Return={r['ret']:+.1f}% | Sharpe={r['shr']:+.2f} | DD={r['dd']:+.1f}% | Trades={r['tr']} |\n")

    lines.append("\n---\n*Generated by ACTosha backtester — fetch_ohlcv_range() with pagination*\n")
    return "".join(lines)


def main():
    since = int(pd.Timestamp("2025-04-25", tz="UTC").timestamp() * 1000)
    until = int(pd.Timestamp("2026-04-26", tz="UTC").timestamp() * 1000)
    ic = 10_000.0; comm = 0.0004; slip = 0.0005
    syms = ["BTC/USDT", "ETH/USDT"]
    tfs = ["1h", "4h", "1d"]

    print("ACTosha — Binance Futures Backtest 2025-04-25 → 2026-04-26")
    print("=" * 60)

    print("\n[1/3] Fetching data with pagination...")
    cache = {}
    feed = BinanceFeed(mode="future")
    for sym in syms:
        cache[sym] = {}
        for tf in tfs:
            t0 = time.time()
            df = feed.fetch_ohlcv_range(sym, timeframe=tf, since=since, until=until, limit=1000)
            elapsed = time.time() - t0
            cache[sym][tf] = df
            price_from = df["close"].iloc[0] if not df.empty else 0
            price_to = df["close"].iloc[-1] if not df.empty else 0
            sym_label = sym.replace("/USDT", "")
            print(f"  {sym_label}/{tf}: {len(df)} bars | {price_from:.1f} → {price_to:.1f} | ({elapsed:.1f}s)")

    print("\n[2/3] Running backtests...")
    table = []

    for sym in syms:
        for tf in tfs:
            df = cache[sym][tf]
            if df.empty:
                continue
            sym_label = sym.replace("/USDT", "")
            print(f"\n  === {sym_label}/{tf} ({len(df)} bars) ===")
            for name in ORDER:
                entry = GRIDS[name]
                t0 = time.time()
                best = best_of(entry, df, ic, comm, slip)
                elapsed = time.time() - t0
                m = fm(best["result"])
                if not m:
                    print(f"  {name}: ERROR (no result) ({elapsed:.1f}s)")
                    table.append({
                        "sym": sym_label, "tf": tf, "strat": name,
                        "ret": 0.0, "shr": 0.0, "dd": 0.0, "wr": 0.0, "tr": 0, "pf": 0.0,
                        "params": best["params"], "error": True
                    })
                    continue
                print(f"  {name}: R={m.get('ret', 0):+.1f}% S={m.get('shr', 0):+.2f} DD={m.get('dd', 0):+.1f}% "
                      f"W={m.get('wr', 0):+.0f}% #{m.get('tr', 0)} pf={m.get('pf', 0):.2f} ({elapsed:.1f}s)")
                table.append({
                    "sym": sym_label, "tf": tf, "strat": name,
                    "ret": m.get("ret", 0), "shr": m.get("shr", 0),
                    "invoke name="fm(r):
    if r is None:
        return {}
    m = r.metrics
    return {
        "ret": round(m.get("total_return", 0) * 100, 2),
        "shr": round(m.get("sharpe_ratio") or 0, 2),
        "dd": round(m.get("max_drawdown_pct", 0), 2),
        "wr": round((m.get("win_rate") or 0) * 100, 1),
        "tr": m.get("trade_count", 0),
        "pf": round(m.get("profit_factor") or 0, 2)
    }
}
```

Fixing a critical bug in the metrics extraction—I'm incorrectly accessing `m.sharpe_ratio` when it should be `m.get("sharpe_ratio")`, and I need to ensure all metrics are properly rounded and returned as a clean dictionary.
</think>

I caught two bugs in the existing script. Let me fix them quickly:
<minimax:tool_call>
<invoke name="edit">
<parameter name="edits">[{"newText": "        \"ret\": round(m.get(\"total_return\", 0) * 100, 2),\n        \"shr\": round(m.get(\"sharpe_ratio\") or 0, 2),", "oldText": "        \"ret\": round(m.get(\"total_return\", 0) * 100, 2),\n        \"shr\": round(m.metrics.get(\"sharpe_ratio\") or 0, 2),"}]