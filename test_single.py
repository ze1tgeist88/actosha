#!/usr/bin/env python3
"""Instrumented BacktestEngine for debugging."""
import sys, os, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run():
    import pandas as pd
    import numpy as np

    from ACTosha.datafeeder.binance import BinanceFeed
    from ACTosha.backtester.engine import BacktestEngine
    from ACTosha.backtester.simulator import OrderSimulator, Order, OrderSide, FillMode
    from ACTosha.strategies.trend.ema_cross import EMACrossStrategy
    from ACTosha.strategies.base import SignalBundle

    # Fetch data
    feed = BinanceFeed(mode='spot', testnet=False)
    df = feed.fetch_ohlcv_range('BTC', timeframe='1h', limit=1000)
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

    print(f"Loaded {len(df)} bars", flush=True)

    strategy = EMACrossStrategy(fast_period=9, slow_period=21, atr_multiplier=2.0, risk_reward=2.0)
    strategy.validate_df(df)
    bundle = strategy.generate_signals(df)
    signals_df = bundle.signals

    print(f"Signals shape: {signals_df.shape}", flush=True)
    print(f"Signals index matches df: {signals_df.index.equals(df.index)}", flush=True)
    print(f"Long signals: {(signals_df['side']=='long').sum()}", flush=True)

    # Reindex check
    if not signals_df.index.equals(df.index):
        signals_df = signals_df.reindex(df.index)
        print("Reindexed signals", flush=True)

    INITIAL_CAPITAL = 10_000.0
    COMMISSION = 0.0004
    SLIPPAGE_BPS = 0.0005 * 10_000.0

    engine = BacktestEngine(fill_mode=FillMode.NEXT_OPEN, exchange=None, min_trade_size=10.0)
    sim = OrderSimulator(commission=COMMISSION, slippage_bps=SLIPPAGE_BPS,
                         fill_mode=FillMode.NEXT_OPEN, exchange=None)

    equity = INITIAL_CAPITAL
    equity_curve = []
    position = None
    trade_id = 0
    trades = []

    bar_times = df.index.tolist()
    bar_values = df.values
    cols = list(df.columns)

    print(f"\nStarting backtest loop over {len(df)} bars...", flush=True)

    for i in range(len(df)):
        ts = bar_times[i]
        bar = pd.Series(dict(zip(cols, bar_values[i])), index=df.columns)
        prev_ts = bar_times[i - 1] if i > 0 else ts

        signal_row = signals_df.iloc[i]
        side = signal_row["side"]
        signal_strength = float(signal_row.get("strength", 0.0))

        # Debug first 3 non-none signals
        if side in ("long", "short") and signal_strength > 0 and i < 15:
            print(f"  i={i} ts={ts} side={side} str={signal_strength:.4f} bar_close={bar['close']:.2f}", flush=True)
            entry_price = bar["open"]  # what engine uses
            size = equity * 0.02 / (bar["close"] * 0.02)  # rough size calc
            if size * entry_price < 10.0:
                print(f"    → SKIP: notional {size*entry_price:.2f} < 10", flush=True)
                equity_curve.append(equity)
                continue
            print(f"    → would enter: notional={size*entry_price:.2f} equity={equity:.2f}", flush=True)

        if position is None:
            if side in ("long", "short") and signal_strength > 0:
                entry_price = bar["open"]
                risk_amount = equity * 0.02
                stop_distance = entry_price * 0.02
                size = risk_amount / stop_distance if stop_distance > 0 else 0.0
                notional = size * entry_price
                if notional < 10.0:
                    equity_curve.append(equity)
                    continue
                order = Order(side=OrderSide.LONG if side == "long" else OrderSide.SHORT,
                              price=entry_price, size=size, timestamp=ts)
                fill = sim.fill_order(order, bar, ts, prev_ts)
                if i < 5:
                    print(f"  FILLED i={i}: price={fill.price} size={fill.size} notional={fill.price*fill.size:.2f}", flush=True)
                position = {"side": side, "entry_price": fill.price, "size": fill.size,
                            "timestamp_open": ts, "trade_id": trade_id}
                trade_id += 1
        else:
            close_reason = None
            should_close = False
            sl = signal_row.get("stop_loss")
            tp = signal_row.get("take_profit")
            if sl is not None and not pd.isna(sl):
                if position["side"] == "long" and bar["low"] <= sl:
                    should_close = True; close_reason = "stop_loss"
                elif position["side"] == "short" and bar["high"] >= sl:
                    should_close = True; close_reason = "stop_loss"
            if tp is not None and not pd.isna(tp):
                if position["side"] == "long" and bar["high"] >= tp:
                    should_close = True; close_reason = "take_profit"
                elif position["side"] == "short" and bar["low"] <= tp:
                    should_close = True; close_reason = "take_profit"
            if side == "close":
                should_close = True; close_reason = "signal_close"
            if should_close:
                order = Order(side=OrderSide.CLOSE, price=bar["open"], size=position["size"], timestamp=ts)
                fill = sim.fill_order(order, bar, ts, prev_ts)
                pnl = (fill.price - position["entry_price"]) * position["size"] if position["side"] == "long" \
                      else (position["entry_price"] - fill.price) * position["size"]
                equity += pnl
                trades.append({"trade_id": position["trade_id"], "entry": position["entry_price"],
                               "exit": fill.price, "pnl": pnl, "reason": close_reason})
                if len(trades) <= 3:
                    print(f"  CLOSED i={i}: {position['side']} {position['entry_price']:.2f} → {fill.price:.2f} pnl={pnl:.2f} ({close_reason})", flush=True)
                position = None

        equity_curve.append(equity)

    print(f"\nBacktest complete: {len(trades)} trades, final equity={equity:.2f}", flush=True)
    print(f"Return: {(equity/INITIAL_CAPITAL-1)*100:.2f}%", flush=True)
    if trades:
        print("First 5 trades:", flush=True)
        for t in trades[:5]:
            print(f"  {t}", flush=True)

if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *args: (print("TIMEOUT", flush=True), sys.exit(1)))
    signal.alarm(120)
    run()
    signal.alarm(0)