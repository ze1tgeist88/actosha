#!/bin/bash
cd /Users/seed1nvestor/.openclaw/workspace/ACTosha
source .venv/bin/activate
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from ACTosha.datafeeder import HyperliquidFeed
from ACTosha.scanner import IndicatorScanner, VolumeScanner

feed = HyperliquidFeed()
symbols = ['BTC/USDC:USDC', 'ETH/USDC:USDC', 'SOL/USDC:USDC']

for sym in symbols:
    try:
        df = feed.fetch_ohlcv(sym, '1h', limit=200)
        print(f'\n=== {sym} ===')
        print(f'Last price: {df["close"].iloc[-1]:.2f}')
        
        ind = IndicatorScanner()
        opps = ind.scan_all([sym], {sym: df})
        
        for o in sorted(opps, key=lambda x: -x.strength):
            marker = '🔔' if o.strength >= 0.6 else '  '
            print(f'{marker} {o.pattern} @ {o.strength:.2f} | zone: {o.entry_zone}')
    except Exception as e:
        print(f'ERROR {sym}: {e}')
EOF