#!/usr/bin/env python3
import sys, os, time, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run():
    from ACTosha.datafeeder.binance import BinanceFeed
    import pandas as pd

    print("Fetching BTC 1h data range 2024-01-01 to 2025-04-25...", flush=True)
    feed = BinanceFeed(mode='spot', testnet=False)
    df = feed.fetch_ohlcv_range('BTC', timeframe='1h', limit=1000)
    print(f"Got {len(df)} bars", flush=True)
    print(f"From: {df.index[0]}", flush=True)
    print(f"To: {df.index[-1]}", flush=True)
    print(df.tail(3), flush=True)

if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *args: (print("TIMEOUT", flush=True), sys.exit(1)))
    signal.alarm(90)
    run()
    signal.alarm(0)