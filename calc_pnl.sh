#!/bin/bash
cd /Users/seed1nvestor/.openclaw/workspace/ACTosha
source .venv/bin/activate
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from ACTosha.datafeeder import BinanceFeed
from ACTosha.strategies.mean_reversion import BollingerRevertStrategy
from ACTosha.backtester import BacktestEngine

feed = BinanceFeed(mode='future')
df = feed.fetch_ohlcv('BTC/USDT:USDT', '1h', since='2025-04-25')
print(f"Bars: {len(df)}")

strategy = BollingerRevertStrategy(
    symbols=['BTC/USDT:USDT'],
    timeframe='1h',
    bb_period=15,
    bb_std=1.5,
    atr_multiplier=3.0,
    risk_reward=1.5
)

result = BacktestEngine().run(
    strategy=strategy,
    df=df,
    initial_capital=10_000,
    commission=0.0004,
    slippage=5
)

trades = result.trades
print(f"\n=== BOLLINGER REVERSION (Binance BTC/USDT USDM-futures) ===")
print(f"Total trades: {len(trades)}")
wins = len(trades[trades['pnl'] > 0])
losses = len(trades[trades['pnl'] <= 0])
print(f"Wins: {wins}, Losses: {losses}")
print(f"WinRate: {wins / len(trades) * 100:.1f}%")
print()
print(f"Avg PnL per trade: ${trades['pnl'].mean():.2f}")
print(f"Avg winner: ${trades[trades['pnl'] > 0]['pnl'].mean():.2f}")
print(f"Avg loser: ${trades[trades['pnl'] <= 0]['pnl'].mean():.2f}")
print()
print(f"Total return: {result.summary['total_return_pct']:.2f}%")
print(f"Profit Factor: {result.metrics.get('profit_factor', 'N/A')}")
print()
print(f"Min PnL: ${trades['pnl'].min():.2f}")
print(f"Max PnL: ${trades['pnl'].max():.2f}")
print(f"Median PnL: ${trades['pnl'].median():.2f}")

if 'exit_reason' in trades.columns:
    print(f"\n--- PnL by exit_reason ---")
    grouped = trades.groupby('exit_reason')['pnl'].agg(['count', 'mean', 'sum'])
    print(grouped.to_string())
EOF