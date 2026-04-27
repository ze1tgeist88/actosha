#!/usr/bin/env python3
"""Minimal test to confirm BacktestEngine works at all."""
import sys, os, signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run():
    import pandas as pd
    import numpy as np
    from ACTosha.backtester.simulator import FillMode
    from ACTosha.strategies.base import SignalBundle, Strategy
    from ACTosha.backtester.engine import BacktestEngine

    # Create synthetic dataset
    n = 100
    dates = pd.date_range('2024-01-01', periods=n, freq='h', tz='UTC')
    closes = np.linspace(43000, 45000, n)
    df = pd.DataFrame({
        'open': closes - 50,
        'high': closes + 100,
        'low': closes - 150,
        'close': closes,
        'volume': np.full(n, 100.0),
    }, index=dates)

    class ToyStrategy(Strategy):
        @property
        def name(self):
            return "ToyStrategy"
        def generate_signals(self, df):
            n = len(df)
            sides = pd.Series('none', index=df.index, dtype='string')
            sides.iloc[10] = 'long'
            if n > 20:
                sides.iloc[20] = 'close'
            strength = pd.Series(1.0, index=df.index)
            signals = pd.DataFrame({
                'side': sides,
                'strength': strength,
                'entry_price': df['close'].copy(),
                'stop_loss': df['close'] * 0.98,
                'take_profit': df['close'] * 1.04,
            })
            signals['metadata'] = [{}] * len(signals)
            return SignalBundle(signals=signals, metadata={'strategy': 'ToyStrategy'})

    toy = ToyStrategy()
    engine = BacktestEngine(fill_mode=FillMode.NEXT_OPEN, exchange=None, min_trade_size=10.0)
    result = engine.run(toy, df, initial_capital=10_000.0, commission=0.0004, slippage=0.0005)

    print(f"Trades: {len(result.trades)}", flush=True)
    if not result.trades.empty:
        print(result.trades[['timestamp_open', 'timestamp_close', 'side', 'entry_price', 'exit_price', 'pnl']], flush=True)
    else:
        print("ERROR: No trades even though ToyStrategy should produce 1 trade", flush=True)
        bundle = toy.generate_signals(df)
        print(f"Non-none signals:\n{bundle.signals[bundle.signals['side'] != 'none']}", flush=True)

if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *args: (print("TIMEOUT", flush=True), sys.exit(1)))
    signal.alarm(30)
    run()
    signal.alarm(0)