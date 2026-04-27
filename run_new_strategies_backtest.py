#!/usr/bin/env python3
"""Backtest for 4 new ACTosha strategies: 2025-04-25 → 2026-04-25."""
import sys, os, signal, warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from itertools import product

from ACTosha.backtester.engine import BacktestEngine
from ACTosha.backtester.simulator import FillMode
from ACTosha.datafeeder.binance import BinanceFeed
from ACTosha.indicators.volatility import compute_atr
from ACTosha.strategies.base import SignalBundle, BaseStrategy

# Import new strategies
from ACTosha.strategies.trend.bb_ema_combo import BBEMAComboStrategy
from ACTosha.strategies.trend.ichimoku_strategy import IchimokuStrategy
from ACTosha.strategies.momentum.obv_divergence import OBVDivergenceStrategy
from ACTosha.strategies.trend.ha_smoothed import HASmoothedStrategy


# ─────────────────────────────────────────────────────────────────────────────
# Grid parameter definitions
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_GRIDS = {
    "BBEMACombo": {
        "factory": lambda p: BBEMAComboStrategy(
            ema_period=p["ema_period"],
            bb_period=p["bb_period"],
            bb_std=p["bb_std"],
            bb_extreme_threshold=p["bb_extreme_threshold"],
            min_volume_mult=p["min_volume_mult"],
            use_atr_sl=p["use_atr_sl"],
            atr_period=p["atr_period"],
            atr_multiplier=p["atr_multiplier"],
            risk_reward=p["risk_reward"],
        ),
        "params": {
            "ema_period": [14, 21, 30],
            "bb_period": [15, 20, 25],
            "bb_std": [1.5, 2.0, 2.5],
            "bb_extreme_threshold": [0.85, 0.90, 0.95],
            "min_volume_mult": [1.0, 1.5],
            "use_atr_sl": [True],
            "atr_period": [14],
            "atr_multiplier": [2.0],
            "risk_reward": [1.5, 2.0],
        },
    },
    "Ichimoku": {
        "factory": lambda p: IchimokuStrategy(
            tenkan_period=p["tenkan_period"],
            kijun_period=p["kijun_period"],
            senkou_b_period=p["senkou_b_period"],
            cloud_shift=p["cloud_shift"],
            chikou_confirm=p["chikou_confirm"],
            cloud_thickness_filter=p["cloud_thickness_filter"],
            max_cloud_width=p["max_cloud_width"],
            use_atr_sl=p["use_atr_sl"],
            atr_period=p["atr_period"],
            atr_multiplier=p["atr_multiplier"],
            risk_reward=p["risk_reward"],
        ),
        "params": {
            "tenkan_period": [7, 9, 12],
            "kijun_period": [22, 26, 30],
            "senkou_b_period": [44, 52, 65],
            "cloud_shift": [26],
            "chikou_confirm": [True, False],
            "cloud_thickness_filter": [False],
            "max_cloud_width": [4.0, 5.0, 6.0],
            "use_atr_sl": [True],
            "atr_period": [14],
            "atr_multiplier": [2.0],
            "risk_reward": [1.5, 2.0],
        },
    },
    "OBVDivergence": {
        "factory": lambda p: OBVDivergenceStrategy(
            obv_ema_period=p["obv_ema_period"],
            price_lookback=p["price_lookback"],
            divergence_lookback=p["divergence_lookback"],
            min_volume_mult=p["min_volume_mult"],
            require_exact_swing=p["require_exact_swing"],
            swing_tolerance=p["swing_tolerance"],
            use_atr_sl=p["use_atr_sl"],
            atr_period=p["atr_period"],
            atr_multiplier=p["atr_multiplier"],
            risk_reward=p["risk_reward"],
        ),
        "params": {
            "obv_ema_period": [14, 21, 30],
            "price_lookback": [3, 5, 7],
            "divergence_lookback": [30, 50],
            "min_volume_mult": [1.0, 1.5],
            "require_exact_swing": [False],
            "swing_tolerance": [0.05],
            "use_atr_sl": [True],
            "atr_period": [14],
            "atr_multiplier": [2.0],
            "risk_reward": [1.5, 2.0],
        },
    },
    "HASmoothed": {
        "factory": lambda p: HASmoothedStrategy(
            ha_smooth_ema=p["ha_smooth_ema"],
            consecutive_bars=p["consecutive_bars"],
            volume_ma_period=p["volume_ma_period"],
            min_volume_mult=p["min_volume_mult"],
            trailing_mode=p["trailing_mode"],
            use_atr_sl=p["use_atr_sl"],
            atr_period=p["atr_period"],
            atr_multiplier=p["atr_multiplier"],
            risk_reward=p["risk_reward"],
        ),
        "params": {
            "ha_smooth_ema": [3, 5, 7],
            "consecutive_bars": [5, 7, 10],
            "volume_ma_period": [20],
            "min_volume_mult": [1.0, 1.5],
            "trailing_mode": [True],
            "use_atr_sl": [True],
            "atr_period": [14],
            "atr_multiplier": [2.0],
            "risk_reward": [1.5, 2.0],
        },
    },
}


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


# ─────────────────────────────────────────────────────────────────────────────
# Main execution
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Fetching BTC/USDC 1h data from Binance (2025-04-25 → 2026-04-25)...", flush=True)

    feed = BinanceFeed(mode="spot", testnet=False)
    since_ms = int(pd.Timestamp("2025-04-25", tz="UTC").timestamp() * 1000)
    until_ms = int(pd.Timestamp("2026-04-26", tz="UTC").timestamp() * 1000)
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
    SLIPPAGE_BPS = 0.0005  # 5 bps

    results = {}
    strategy_order = ["BBEMACombo", "Ichimoku", "OBVDivergence", "HASmoothed"]

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
    report_lines = []
    report_lines.append("# ACTosha New Strategies Backtest\n")
    report_lines.append(f"**Setup:** BTC/USDC 1h | 2025-04-25 → 2026-04-25 | Initial $10,000\n")
    report_lines.append(f"**Commission:** 0.04% | **Slippage:** 5 bps | **Optimization:** Grid\n")
    report_lines.append(f"**Data:** {len(df)} hourly bars from Binance\n")

    # Individual strategy results
    for strategy_name in strategy_order:
        data = results.get(strategy_name)
        if data is None:
            report_lines.append(f"\n=== {strategy_name} ===\n")
            report_lines.append("⚠ No valid results.\n")
            continue

        m = data["metrics"]
        p = data["params"]
        report_lines.append(f"\n=== {strategy_name} ===\n")
        report_lines.append(f"Return: {m['return_pct']}%\n")
        report_lines.append(f"Sharpe: {m['sharpe']}\n")
        report_lines.append(f"MaxDD: {m['maxdd_pct']}%\n")
        report_lines.append(f"WinRate: {m['winrate']}%\n")
        report_lines.append(f"Trades: {m['trades']}\n")
        report_lines.append(f"Best params: {p}\n")
        report_lines.append(f"Profit Factor: {m['profit_factor']}\n")

    # Summary table
    report_lines.append("\n## Summary Table\n\n")
    report_lines.append("| Strategy | Return | Sharpe | MaxDD | WinRate | Trades | PF |\n")
    report_lines.append("|---|---|---|---|---|---|---|\n")
    for strategy_name in strategy_order:
        data = results.get(strategy_name)
        if data is None:
            report_lines.append(f"| {strategy_name} | N/A | N/A | N/A | N/A | N/A | N/A |")
        else:
            m = data["metrics"]
            report_lines.append(f"| {strategy_name} | {m['return_pct']}% | {m['sharpe']} | {m['maxdd_pct']}% | {m['winrate']}% | {m['trades']} | {m['profit_factor']} |")

    # Benchmark comparison
    report_lines.append("\n## vs Bollinger Reversion (492.91%, Sharpe 14.36)\n\n")
    report_lines.append("| Strategy | Return | Sharpe | MaxDD | WinRate | Trades | PF |\n")
    report_lines.append("|---|---|---|---|---|---|---|\n")
    # Benchmark row
    report_lines.append(f"| **Bollinger Reversion** (benchmark) | **492.91%** | **14.36** | **-0.34%** | **96.0%** | **883** | **32.31** |\n")
    for strategy_name in strategy_order:
        data = results.get(strategy_name)
        if data is None:
            report_lines.append(f"| {strategy_name} | N/A | N/A | N/A | N/A | N/A | N/A |")
        else:
            m = data["metrics"]
            report_lines.append(f"| {strategy_name} | {m['return_pct']}% | {m['sharpe']} | {m['maxdd_pct']}% | {m['winrate']}% | {m['trades']} | {m['profit_factor']} |")

    # Ranking by Sharpe
    valid_results = [(n, d) for n, d in results.items() if d is not None]
    if valid_results:
        ranked = sorted(valid_results, key=lambda x: (x[1]["metrics"]["sharpe"], x[1]["metrics"]["return_pct"]), reverse=True)
        report_lines.append("\n## Ranking by Sharpe\n\n")
        for i, (name, data) in enumerate(ranked, 1):
            m = data["metrics"]
            report_lines.append(f"{i}. **{name}** — Sharpe {m['sharpe']}, Return {m['return_pct']}%, MaxDD {m['maxdd_pct']}%, PF {m['profit_factor']}\n")

        best_strategy = ranked[0][0]
        best_metrics = ranked[0][1]["metrics"]
        best_params = ranked[0][1]["params"]
        report_lines.append(f"\n**Best:** {best_strategy} (Sharpe {best_metrics['sharpe']}, Return {best_metrics['return_pct']}%)\n")

    report = "".join(report_lines)

    output_path = "/Users/seed1nvestor/.openclaw/workspace/ACTosha/backtest_new_strategies.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"\n✅ Report saved to {output_path}", flush=True)


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *args: (print("TIMEOUT", flush=True), sys.exit(1)))
    signal.alarm(2400)  # 40 min timeout
    main()
    signal.alarm(0)