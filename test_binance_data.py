#!/usr/bin/env python3
"""Test Binance data feed to verify 2024 historical data is valid."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from ACTosha.datafeeder import BinanceFeed

def test_binance_feed():
    print("=== BinanceFeed Test ===\n")

    # Test in 'future' mode (perpetuals)
    bn = BinanceFeed(mode='future')
    print(f"BinanceFeed mode: future")
    print(f"  Symbol resolution BTC -> {bn._resolve_symbol('BTC')}")
    print(f"  Symbol resolution BTC/USDT -> {bn._resolve_symbol('BTC/USDT')}")
    print(f"  Symbol resolution BTC/USDT:USDT -> {bn._resolve_symbol('BTC/USDT:USDT')}")
    print(f"  Symbol resolution ETH -> {bn._resolve_symbol('ETH')}")

    print("\n--- Fetching BTC/USDT 1h data from 2024-01-01 ---")
    try:
        since_ms = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
        df = bn.fetch_ohlcv_range("BTC", timeframe="1h", since=since_ms, limit=1000)
        print(f"  Fetched {len(df)} bars")
        if not df.empty:
            print(f"  First:  {df.index[0]}  O={df['open'].iloc[0]:.2f} C={df['close'].iloc[0]:.2f}")
            print(f"  Last:   {df.index[-1]}  O={df['open'].iloc[-1]:.2f} C={df['close'].iloc[-1]:.2f}")
            # Check if data contains varied prices (not fake)
            price_std = df['close'].std()
            price_range = df['close'].max() - df['close'].min()
            print(f"  Price std: {price_std:.2f}, range: {price_range:.2f}")
            # BTC 2024 range should be > $1000
            if price_range < 1000:
                print("  ⚠ WARNING: price range suspiciously low — may be fake data")
            else:
                print("  ✓ Price range looks valid")
        else:
            print("  ⚠ No data returned!")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- Fetching ETH/USDT 1h data from 2024-01-01 ---")
    try:
        since_ms = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
        df_eth = bn.fetch_ohlcv_range("ETH", timeframe="1h", since=since_ms, limit=1000)
        print(f"  Fetched {len(df_eth)} bars")
        if not df_eth.empty:
            print(f"  First:  {df_eth.index[0]}  O={df_eth['open'].iloc[0]:.2f} C={df_eth['close'].iloc[0]:.2f}")
            print(f"  Last:   {df_eth.index[-1]}  O={df_eth['open'].iloc[-1]:.2f} C={df_eth['close'].iloc[-1]:.2f}")
        else:
            print("  ⚠ No data returned!")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- Spot mode test (BTC/USDT spot) ---")
    try:
        bn_spot = BinanceFeed(mode='spot')
        df_spot = bn_spot.fetch_ohlcv("BTC", timeframe="1h", limit=100)
        print(f"  Fetched {len(df_spot)} bars (spot)")
        if not df_spot.empty:
            print(f"  Last: {df_spot.index[-1]}  C={df_spot['close'].iloc[-1]:.2f}")
        else:
            print("  ⚠ No data returned!")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n=== Done ===")

if __name__ == "__main__":
    test_binance_feed()