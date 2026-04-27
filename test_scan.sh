#!/bin/bash
cd /Users/seed1nvestor/.openclaw/workspace/ACTosha
source .venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, '.')
from ACTosha.datafeeder import HyperliquidFeed
from ACTosha.scanner import IndicatorScanner

feed = HyperliquidFeed()
symbols = ['BTC/USDC:USDC', 'ETH/USDC:USDC', 'SOL/USDC:USDC']
timeframe = '1h'

# Build data map
data = {}
for sym in symbols:
    try:
        df = feed.fetch_ohlcv(sym, timeframe, limit=200)
        data[sym] = df
        print(f'{sym}: {len(df)} bars loaded')
    except Exception as e:
        print(f'ERROR {sym}: {e}')

print()
scanner = IndicatorScanner()
opps = scanner.scan_all(symbols, data)
print(f'Opportunities: {len(opps)}')
for o in opps:
    print(f'  {o.symbol} {o.pattern} @ {o.strength:.2f}')
    print(f'    entry_zone: {o.entry_zone}')
    print(f'    metadata: {o.metadata}')
" 2>&1