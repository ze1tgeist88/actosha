#!/bin/bash
cd /Users/seed1nvestor/.openclaw/workspace/ACTosha
source .venv/bin/activate
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from ACTosha.datafeeder import HyperliquidFeed
from ACTosha.scanner import IndicatorScanner, PatternScanner, VolumeScanner

feed = HyperliquidFeed()
symbols = ['BTC/USDC:USDC', 'ETH/USDC:USDC', 'SOL/USDC:USDC']
timeframe = '1h'

data = {}
for sym in symbols:
    try:
        df = feed.fetch_ohlcv(sym, timeframe, limit=200)
        data[sym] = df
    except Exception as e:
        print(f'ERROR {sym}: {e}')

print('=== ALL OPPORTUNITIES (any strength) ===')
for name, scanner_cls in [
    ('Indicator', IndicatorScanner),
    ('Volume', VolumeScanner),
]:
    scanner = scanner_cls()
    opps = scanner.scan_all(symbols, data)
    print(f'\n{name} Scanner: {len(opps)} found')
    for o in sorted(opps, key=lambda x: -x.strength)[:10]:
        marker = '🔔' if o.strength >= 0.6 else '  '
        print(f'  {marker} {o.symbol} {o.pattern} @ {o.strength:.2f}')
EOF