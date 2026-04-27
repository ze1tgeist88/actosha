# ACTosha Backtest Results
**Symbol:** BTC/USDC (Binance Spot)
**Timeframe:** 1h
**Period:** 2025-04-25 → 2026-04-25
**Bars:** 11544
**Initial Capital:** $10,000
**Commission:** 0.04% | **Slippage:** 5 bps
**Optimization:** Grid search

## EMA Cross
| Metric | Value |
|---|---|
| Return | 366.54% |
| Sharpe | 5.69 |
| MaxDD | -1.14% |
| WinRate | 66.7% |
| Trades | 342 |
| Profit Factor | 13.66 |
| Best params | {'fast_period': 5, 'slow_period': 21, 'atr_multiplier': 1.5, 'risk_reward': 1.5} |

## Supertrend
| Metric | Value |
|---|---|
| Return | 201.15% |
| Sharpe | 3.73 |
| MaxDD | -6.98% |
| WinRate | 73.5% |
| Trades | 68 |
| Profit Factor | 7.67 |
| Best params | {'period': 20, 'multiplier': 2.0} |

## Trendline Break
| Metric | Value |
|---|---|
| Return | 108.77% |
| Sharpe | 2.81 |
| MaxDD | -4.02% |
| WinRate | 61.9% |
| Trades | 105 |
| Profit Factor | 2.34 |
| Best params | {'lookback': 30, 'retest_tolerance': 0.005} |

## Bollinger Reversion
| Metric | Value |
|---|---|
| Return | 679.64% |
| Sharpe | 12.04 |
| MaxDD | -0.34% |
| WinRate | 96.0% |
| Trades | 883 |
| Profit Factor | 32.31 |
| Best params | {'bb_period': 15, 'bb_std': 1.5, 'atr_multiplier': 2.0, 'risk_reward': 1.5} |

## RSI Extreme
| Metric | Value |
|---|---|
| Return | -431.36% |
| Sharpe | 1.37 |
| MaxDD | -432.64% |
| WinRate | 34.8% |
| Trades | 339 |
| Profit Factor | 0.16 |
| Best params | {'rsi_period': 20, 'oversold': 35, 'overbought': 65} |

## VWAP Reversion
| Metric | Value |
|---|---|
| Return | -163.91% |
| Sharpe | 1.41 |
| MaxDD | -185.72% |
| WinRate | 30.2% |
| Trades | 192 |
| Profit Factor | 0.55 |
| Best params | {'band_threshold': 0.003, 'exit_threshold': 0.002, 'max_position_duration': 100} |

## Range Breakout
| Metric | Value |
|---|---|
| Return | 259.27% |
| Sharpe | 6.05 |
| MaxDD | -1.89% |
| WinRate | 67.7% |
| Trades | 350 |
| Profit Factor | 3.69 |
| Best params | {'lookback': 15, 'confirmation_bars': 1, 'atr_multiplier': 2.0, 'risk_reward': 1.5} |

## Volume Surge
| Metric | Value |
|---|---|
| Return | 211.54% |
| Sharpe | 5.23 |
| MaxDD | -3.38% |
| WinRate | 65.3% |
| Trades | 228 |
| Profit Factor | 3.79 |
| Best params | {'lookback': 20, 'volume_multiplier': 1.5} |

## RSI + MACD Combo
| Metric | Value |
|---|---|
| Return | 346.38% |
| Sharpe | 7.03 |
| MaxDD | -0.9% |
| WinRate | 87.8% |
| Trades | 262 |
| Profit Factor | 55.66 |
| Best params | {'rsi_period': 10, 'macd_fast': 10, 'macd_slow': 24, 'macd_signal': 7} |

## Summary Table

| Strategy | Return | Sharpe | MaxDD% | WinRate% | Trades | ProfitFactor |
|---|---|---|---|---|---|---|---|
| EMA Cross | 366.54% | 5.69 | -1.14% | 66.7% | 342 | 13.66 || Supertrend | 201.15% | 3.73 | -6.98% | 73.5% | 68 | 7.67 || Trendline Break | 108.77% | 2.81 | -4.02% | 61.9% | 105 | 2.34 || Bollinger Reversion | 679.64% | 12.04 | -0.34% | 96.0% | 883 | 32.31 || RSI Extreme | -431.36% | 1.37 | -432.64% | 34.8% | 339 | 0.16 || VWAP Reversion | -163.91% | 1.41 | -185.72% | 30.2% | 192 | 0.55 || Range Breakout | 259.27% | 6.05 | -1.89% | 67.7% | 350 | 3.69 || Volume Surge | 211.54% | 5.23 | -3.38% | 65.3% | 228 | 3.79 || RSI + MACD Combo | 346.38% | 7.03 | -0.9% | 87.8% | 262 | 55.66 |
## Recommendation

**Best strategy:** Bollinger Reversion

| Metric | Value |
|---|---|
| Sharpe | 12.04 |
| Return | 679.64% |
| Max Drawdown | -0.34% |
| WinRate | 96.0% |
| Trades | 883 |
| Profit Factor | 32.31 |
| Best params | {'bb_period': 15, 'bb_std': 1.5, 'atr_multiplier': 2.0, 'risk_reward': 1.5} |

### Full Ranking (by Sharpe)

1. **Bollinger Reversion** — Sharpe 12.04, Return 679.64%, MaxDD -0.34%, PF 32.31
2. **RSI + MACD Combo** — Sharpe 7.03, Return 346.38%, MaxDD -0.9%, PF 55.66
3. **Range Breakout** — Sharpe 6.05, Return 259.27%, MaxDD -1.89%, PF 3.69
4. **EMA Cross** — Sharpe 5.69, Return 366.54%, MaxDD -1.14%, PF 13.66
5. **Volume Surge** — Sharpe 5.23, Return 211.54%, MaxDD -3.38%, PF 3.79
6. **Supertrend** — Sharpe 3.73, Return 201.15%, MaxDD -6.98%, PF 7.67
7. **Trendline Break** — Sharpe 2.81, Return 108.77%, MaxDD -4.02%, PF 2.34
8. **VWAP Reversion** — Sharpe 1.41, Return -163.91%, MaxDD -185.72%, PF 0.55
9. **RSI Extreme** — Sharpe 1.37, Return -431.36%, MaxDD -432.64%, PF 0.16
