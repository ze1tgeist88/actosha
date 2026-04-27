# ACTosha - Binance Futures Backtest 2025-04-25 to 2026-04-26

| Metric | Value |
|--------|-------|
| Period | 2025-04-25 to 2026-04-26 |
| Symbols | BTC/USDT, ETH/USDT (Binance USDM perpetuals) |
| Timeframes | 1h, 4h, 1d |
| Strategies | 13 (grid-optimized) |
| Initial Capital | $10,000 |
| Commission | 0.04% (maker/taker combined) |
| Slippage | 5 bps |
| Data Source | BinanceFeed (mode='future'), CCXT, fetch_ohlcv_range() with pagination |
| Optimization | Grid search over parameter space |

## Full Results Table
| # | Sym | TF | Strategy | Return% | Sharpe | MaxDD% | WinRate% | Trades | PF |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BTC | 1h | EMA Cross | +104.5% | +3.77 | -3.2% | +48% | 202 | 3.59 |
| 2 | BTC | 1h | Supertrend | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 3 | BTC | 1h | Trendline Break | +91.8% | +3.83 | -2.6% | +78% | 60 | 5.33 |
| 4 | BTC | 1h | Bollinger Rev | +430.5% | +12.90 | -0.3% | +98% | 539 | 161.47 |
| 5 | BTC | 1h | RSI Extreme | -267.3% | +1.08 | -266.4% | +34% | 300 | 0.16 |
| 6 | BTC | 1h | VWAP Reversion | -81.7% | +1.02 | -99.4% | +36% | 124 | 0.60 |
| 7 | BTC | 1h | Range Breakout | +127.1% | +4.54 | -7.5% | +63% | 215 | 3.28 |
| 8 | BTC | 1h | Volume Surge | +127.4% | +4.85 | -3.4% | +67% | 176 | 3.79 |
| 9 | BTC | 1h | RSI + MACD Combo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 10 | BTC | 1h | BBEMACombo | +0.0% | +0.00 | +0.0% | +100% | 1 | 0.00 |
| 11 | BTC | 1h | Ichimoku | +74.6% | +2.87 | -5.4% | +82% | 27 | 7.19 |
| 12 | BTC | 1h | OBVDivergence | +34.3% | +1.03 | -18.7% | +60% | 20 | 2.03 |
| 13 | BTC | 1h | HASmoothed | +207.0% | +5.95 | -3.3% | +74% | 214 | 6.21 |
| 14 | BTC | 4h | EMA Cross | +37.1% | +3.99 | -6.2% | +41% | 51 | 2.52 |
| 15 | BTC | 4h | Supertrend | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 16 | BTC | 4h | Trendline Break | +53.1% | +4.39 | -5.5% | +71% | 24 | 3.16 |
| 17 | BTC | 4h | Bollinger Rev | +224.0% | +13.52 | -2.0% | +98% | 121 | 62.69 |
| 18 | BTC | 4h | RSI Extreme | -143.0% | +0.92 | -142.9% | +29% | 92 | 0.15 |
| 19 | BTC | 4h | VWAP Reversion | -73.1% | -0.67 | -84.9% | +25% | 55 | 0.43 |
| 20 | BTC | 4h | Range Breakout | +52.6% | +4.44 | -7.2% | +61% | 56 | 2.50 |
| 21 | BTC | 4h | Volume Surge | +54.7% | +4.96 | -5.7% | +76% | 21 | 5.81 |
| 22 | BTC | 4h | RSI + MACD Combo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 23 | BTC | 4h | BBEMACombo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 24 | BTC | 4h | Ichimoku | +52.3% | +2.99 | -5.2% | +71% | 7 | 6.24 |
| 25 | BTC | 4h | OBVDivergence | +6.6% | +0.71 | -10.5% | +25% | 8 | 1.42 |
| 26 | BTC | 4h | HASmoothed | +128.5% | +7.16 | -2.5% | +73% | 52 | 12.22 |
| 27 | BTC | 1d | EMA Cross | +1.6% | +1.44 | -3.4% | +44% | 9 | 3.96 |
| 28 | BTC | 1d | Supertrend | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 29 | BTC | 1d | Trendline Break | +12.3% | +2.99 | -12.2% | +80% | 5 | 2.49 |
| 30 | BTC | 1d | Bollinger Rev | +97.2% | +14.52 | -2.5% | +95% | 21 | 22.58 |
| 31 | BTC | 1d | RSI Extreme | -15.0% | -3.44 | -20.2% | +43% | 7 | 0.34 |
| 32 | BTC | 1d | VWAP Reversion | -74.7% | -8.23 | -74.7% | +14% | 14 | 0.21 |
| 33 | BTC | 1d | Range Breakout | +14.7% | +3.26 | -15.8% | +56% | 9 | 2.48 |
| 34 | BTC | 1d | Volume Surge | +15.5% | +4.90 | +0.0% | +100% | 1 | 0.00 |
| 35 | BTC | 1d | RSI + MACD Combo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 36 | BTC | 1d | BBEMACombo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 37 | BTC | 1d | Ichimoku | +0.0% | +0.00 | +0.0% | +100% | 1 | 0.00 |
| 38 | BTC | 1d | OBVDivergence | +26.9% | +6.86 | +0.0% | +100% | 3 | 0.00 |
| 39 | BTC | 1d | HASmoothed | +52.2% | +10.70 | -1.8% | +77% | 13 | 13.86 |
| 40 | ETH | 1h | EMA Cross | +240.4% | +3.07 | -3.5% | +52% | 198 | 4.50 |
| 41 | ETH | 1h | Supertrend | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 42 | ETH | 1h | Trendline Break | +154.0% | +3.54 | -8.8% | +71% | 98 | 3.40 |
| 43 | ETH | 1h | Bollinger Rev | +613.6% | +13.01 | -1.8% | +95% | 586 | 37.10 |
| 44 | ETH | 1h | RSI Extreme | -410.9% | +1.33 | -407.3% | +38% | 269 | 0.17 |
| 45 | ETH | 1h | VWAP Reversion | -168.0% | +1.28 | -189.0% | +40% | 216 | 0.65 |
| 46 | ETH | 1h | Range Breakout | +261.4% | +5.36 | -9.4% | +67% | 196 | 4.32 |
| 47 | ETH | 1h | Volume Surge | +289.5% | +5.27 | -9.9% | +74% | 151 | 6.54 |
| 48 | ETH | 1h | RSI + MACD Combo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 49 | ETH | 1h | BBEMACombo | +0.0% | +0.00 | +0.0% | +100% | 1 | 0.00 |
| 50 | ETH | 1h | Ichimoku | +101.2% | +1.71 | -7.8% | +60% | 25 | 4.63 |
| 51 | ETH | 1h | OBVDivergence | +120.8% | +1.65 | -8.5% | +63% | 19 | 4.80 |
| 52 | ETH | 1h | HASmoothed | +232.1% | +4.06 | -8.7% | +73% | 122 | 4.45 |
| 53 | ETH | 4h | EMA Cross | +153.6% | +4.08 | -4.5% | +52% | 56 | 5.51 |
| 54 | ETH | 4h | Supertrend | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 55 | ETH | 4h | Trendline Break | +81.7% | +3.78 | -10.8% | +66% | 32 | 2.71 |
| 56 | ETH | 4h | Bollinger Rev | +369.2% | +14.54 | -0.1% | +98% | 120 | 1954.67 |
| 57 | ETH | 4h | RSI Extreme | -250.7% | +1.68 | -251.4% | +34% | 90 | 0.13 |
| 58 | ETH | 4h | VWAP Reversion | -147.0% | +2.64 | -155.7% | +26% | 50 | 0.34 |
| 59 | ETH | 4h | Range Breakout | +114.8% | +5.02 | -6.7% | +58% | 50 | 3.22 |
| 60 | ETH | 4h | Volume Surge | +139.0% | +6.00 | -4.6% | +76% | 37 | 5.17 |
| 61 | ETH | 4h | RSI + MACD Combo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 62 | ETH | 4h | BBEMACombo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 63 | ETH | 4h | Ichimoku | +149.6% | +3.42 | -4.2% | +67% | 9 | 10.83 |
| 64 | ETH | 4h | OBVDivergence | +75.0% | +2.75 | -8.7% | +60% | 5 | 7.48 |
| 65 | ETH | 4h | HASmoothed | +200.2% | +5.46 | -8.6% | +77% | 61 | 6.96 |
| 66 | ETH | 1d | EMA Cross | +56.5% | +4.37 | -4.9% | +38% | 8 | 7.03 |
| 67 | ETH | 1d | Supertrend | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 68 | ETH | 1d | Trendline Break | +90.1% | +6.14 | -10.4% | +75% | 4 | 9.77 |
| 69 | ETH | 1d | Bollinger Rev | +148.8% | +13.82 | +0.0% | +100% | 18 | 0.00 |
| 70 | ETH | 1d | RSI Extreme | -95.2% | +2.25 | -99.1% | +40% | 15 | 0.21 |
| 71 | ETH | 1d | VWAP Reversion | -178.9% | -2.78 | -178.9% | +24% | 17 | 0.14 |
| 72 | ETH | 1d | Range Breakout | +105.1% | +6.11 | -10.4% | +71% | 7 | 10.15 |
| 73 | ETH | 1d | Volume Surge | +63.3% | +6.94 | -3.9% | +75% | 4 | 13.26 |
| 74 | ETH | 1d | RSI + MACD Combo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 75 | ETH | 1d | BBEMACombo | +0.0% | +0.00 | +0.0% | +0% | 0 | 0.00 |
| 76 | ETH | 1d | Ichimoku | +38.6% | +6.86 | +0.0% | +100% | 2 | 0.00 |
| 77 | ETH | 1d | OBVDivergence | -4.8% | -1.23 | -12.3% | +67% | 3 | 2.77 |
| 78 | ETH | 1d | HASmoothed | +129.6% | +8.43 | -2.8% | +80% | 10 | 15.26 |

## Strategy Summary (avg across symbol/timeframe combos)
| Strategy | Avg Return% | Avg Sharpe | Avg MaxDD% | Avg WinRate% | Avg PF |
|---|---|---|---|---|---|---|
| EMA Cross | +99.0% | +3.45 | -4.3% | +46% | 4.52 |
| Supertrend | +0.0% | +0.00 | +0.0% | +0% | 0.00 |
| Trendline Break | +80.5% | +4.11 | -8.4% | +74% | 4.48 |
| Bollinger Rev | +313.9% | +13.72 | -1.1% | +97% | 373.09 |
| RSI Extreme | -197.0% | +0.64 | -197.9% | +36% | 0.19 |
| VWAP Reversion | -120.6% | -1.12 | -130.4% | +28% | 0.40 |
| Range Breakout | +112.6% | +4.79 | -9.5% | +63% | 4.33 |
| Volume Surge | +114.9% | +5.49 | -4.6% | +78% | 5.76 |
| RSI + MACD Combo | +0.0% | +0.00 | +0.0% | +0% | 0.00 |
| BBEMACombo | +0.0% | +0.00 | +0.0% | +33% | 0.00 |
| Ichimoku | +69.4% | +2.98 | -3.8% | +80% | 4.82 |
| OBVDivergence | +43.1% | +1.96 | -9.8% | +62% | 3.08 |
| HASmoothed | +158.3% | +6.96 | -4.6% | +76% | 9.83 |

## Best Strategy by Symbol & Timeframe
### BTC / 1h

**Strategy** | Bollinger Rev
**Return** | +430.5%
**Sharpe** | +12.90
**MaxDD** | -0.3%
**WinRate** | +98%
**Trades** | 539
**Profit Factor** | 161.47

### BTC / 4h

**Strategy** | Bollinger Rev
**Return** | +224.0%
**Sharpe** | +13.52
**MaxDD** | -2.0%
**WinRate** | +98%
**Trades** | 121
**Profit Factor** | 62.69

### BTC / 1d

**Strategy** | Bollinger Rev
**Return** | +97.2%
**Sharpe** | +14.52
**MaxDD** | -2.5%
**WinRate** | +95%
**Trades** | 21
**Profit Factor** | 22.58

### ETH / 1h

**Strategy** | Bollinger Rev
**Return** | +613.6%
**Sharpe** | +13.01
**MaxDD** | -1.8%
**WinRate** | +95%
**Trades** | 586
**Profit Factor** | 37.10

### ETH / 4h

**Strategy** | Bollinger Rev
**Return** | +369.2%
**Sharpe** | +14.54
**MaxDD** | -0.1%
**WinRate** | +98%
**Trades** | 120
**Profit Factor** | 1954.67

### ETH / 1d

**Strategy** | Bollinger Rev
**Return** | +148.8%
**Sharpe** | +13.82
**MaxDD** | +0.0%
**WinRate** | +100%
**Trades** | 18
**Profit Factor** | 0.00

## Top Picks

### Best by Sharpe Ratio

| ETH | 4h | Bollinger Rev | Sharpe=+14.54 | Return=+369.2% | DD=-0.1% | Trades=120 |
| BTC | 1d | Bollinger Rev | Sharpe=+14.52 | Return=+97.2% | DD=-2.5% | Trades=21 |
| ETH | 1d | Bollinger Rev | Sharpe=+13.82 | Return=+148.8% | DD=+0.0% | Trades=18 |
| BTC | 4h | Bollinger Rev | Sharpe=+13.52 | Return=+224.0% | DD=-2.0% | Trades=121 |
| ETH | 1h | Bollinger Rev | Sharpe=+13.01 | Return=+613.6% | DD=-1.8% | Trades=586 |

### Best by Return

| ETH | 1h | Bollinger Rev | Return=+613.6% | Sharpe=+13.01 | DD=-1.8% | Trades=586 |
| BTC | 1h | Bollinger Rev | Return=+430.5% | Sharpe=+12.90 | DD=-0.3% | Trades=539 |
| ETH | 4h | Bollinger Rev | Return=+369.2% | Sharpe=+14.54 | DD=-0.1% | Trades=120 |
| ETH | 1h | Volume Surge | Return=+289.5% | Sharpe=+5.27 | DD=-9.9% | Trades=151 |
| ETH | 1h | Range Breakout | Return=+261.4% | Sharpe=+5.36 | DD=-9.4% | Trades=196 |

---
*Generated by ACTosha backtester - fetch_ohlcv_range() with pagination*
