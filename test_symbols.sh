#!/bin/bash
cd /Users/seed1nvestor/.openclaw/workspace/ACTosha
source .venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, '.')
import ccxt
hl = ccxt.hyperliquid()
markets = hl.load_markets()
perp = [s for s in markets.keys() if 'USD' in s and ':' in s]
print('Hyperliquid perpetuals:', perp[:20])
" 2>&1