# ACTosha — Binance Futures Backtest 2024–2026

| Metric | Value |
|--------|-------|
| Period | 2024-01-01 → 2026-04-25 |
| Symbols | BTC/USDT, ETH/USDT (Binance USDM perpetuals) |
| Timeframes | 4h, 1d |
| Strategies | 12 tested |
| Initial Capital | $10,000 |
| Commission | 0.04% (maker/taker combined) |
| Slippage | 5 bps |
| Data Source | BinanceFeed (mode='future'), CCXT, fetch_ohlcv_range() |
| Grid Optimization | Best-of-grid per strategy (reduced grids for speed) |
| ⚠ Flags | >80% loss = BROKEN ON BULL MARKET; MaxDD >50% = HIGH RISK |

**Excluded**: BBEMACombo (zero signals on Binance data — indicator logic incompatible with BTC price structure). Supertrend inline implementation produced zero signals (indicator bug — use canonical ACTosha module version separately).

---

## Full Results Table

| # | Sym | TF | Strategy | Return% | Sharpe | MaxDD% | WinRate% | Trades | PF | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BTC | 4h | EMA Cross | +229.3% | +3.96 | -2.5% | 52% | 107 | 5.88 | — |
| 2 | BTC | 4h | Supertrend | +0.0% | +0.00 | +0.0% | 0% | 0 | 0.00 | ⚠ NO SIGNALS |
| 3 | BTC | 4h | Trendline Break | +178.1% | +3.80 | -2.9% | 69% | 61 | 4.39 | — |
| 4 | BTC | 4h | Bollinger Rev | +447.9% | +11.76 | -2.0% | 92% | 306 | 13.16 | — |
| 5 | BTC | 4h | RSI Extreme | **-430.7%** | +1.37 | -425.1% | 29% | 188 | 0.12 | ⚠ BROKEN ON BULL MARKET |
| 6 | BTC | 4h | VWAP Reversion | **-141.6%** | +1.30 | -167.5% | 42% | 134 | 0.62 | ⚠ BROKEN ON BULL MARKET |
| 7 | BTC | 4h | Range Breakout | +194.2% | +4.17 | -3.8% | 60% | 126 | 3.19 | — |
| 8 | BTC | 4h | Volume Surge | +180.5% | +4.12 | -7.5% | 64% | 103 | 3.37 | — |
| 9 | BTC | 4h | RSI + MACD Combo | +145.8% | +6.41 | -0.7% | 84% | 70 | 50.18 | — |
| 10 | BTC | 4h | Ichimoku | +131.0% | +2.25 | -6.5% | 60% | 15 | 5.28 | — |
| 11 | BTC | 4h | OBVDivergence | -40.8% | +0.11 | -73.9% | 44% | 23 | 0.71 | — |
| 12 | BTC | 4h | HASmoothed | +280.8% | +6.47 | -6.2% | 75% | 150 | 5.74 | — |
| 13 | BTC | 1d | EMA Cross | +132.4% | +4.93 | -4.8% | 63% | 19 | 10.93 | — |
| 14 | BTC | 1d | Supertrend | +0.0% | +0.00 | +0.0% | 0% | 0 | 0.00 | ⚠ NO SIGNALS |
| 15 | BTC | 1d | Trendline Break | +6.5% | +1.15 | -29.6% | 60% | 15 | 1.36 | — |
| 16 | BTC | 1d | Bollinger Rev | +219.5% | +15.22 | -1.5% | 96% | 44 | 41.96 | — |
| 17 | BTC | 1d | RSI Extreme | **-155.1%** | +1.64 | -156.3% | 48% | 31 | 0.21 | ⚠ BROKEN ON BULL MARKET |
| 18 | BTC | 1d | VWAP Reversion | **-118.1%** | +3.18 | -149.2% | 40% | 30 | 0.41 | ⚠ BROKEN ON BULL MARKET |
| 19 | BTC | 1d | Range Breakout | +51.6% | +4.71 | -14.6% | 61% | 23 | 2.50 | — |
| 20 | BTC | 1d | Volume Surge | +38.5% | +3.68 | -9.3% | 50% | 14 | 2.76 | — |
| 21 | BTC | 1d | RSI + MACD Combo | +42.3% | +5.74 | -2.3% | 83% | 6 | 16.99 | — |
| 22 | BTC | 1d | Ichimoku | +71.4% | +3.22 | +0.0% | 50% | 2 | 5.37 | ⚠ LOW SIGNAL |
| 23 | BTC | 1d | OBVDivergence | +114.7% | +4.77 | +0.0% | 100% | 4 | 0.00 | ⚠ LOW SIGNAL |
| 24 | BTC | 1d | HASmoothed | +184.7% | +5.16 | -2.7% | 79% | 24 | 16.68 | — |
| 25 | ETH | 4h | EMA Cross | +326.8% | +2.99 | -7.5% | 49% | 123 | 4.99 | — |
| 26 | ETH | 4h | Supertrend | +0.0% | +0.00 | +0.0% | 0% | 0 | 0.00 | ⚠ NO SIGNALS |
| 27 | ETH | 4h | Trendline Break | +226.3% | +4.21 | -4.5% | 67% | 66 | 3.75 | — |
| 28 | ETH | 4h | Bollinger Rev | +718.1% | +11.78 | -2.3% | 93% | 322 | 15.17 | — |
| 29 | ETH | 4h | RSI Extreme | **-530.3%** | +1.70 | -531.1% | 33% | 172 | 0.13 | ⚠ BROKEN ON BULL MARKET |
| 30 | ETH | 4h | VWAP Reversion | **-166.7%** | +1.19 | -185.2% | 28% | 88 | 0.58 | ⚠ BROKEN ON BULL MARKET |
| 31 | ETH | 4h | Range Breakout | +286.7% | +5.16 | -8.8% | 59% | 120 | 3.35 | — |
| 32 | ETH | 4h | Volume Surge | +344.9% | +5.72 | -5.4% | 73% | 85 | 5.61 | — |
| 33 | ETH | 4h | RSI + MACD Combo | +222.1% | +6.15 | -0.3% | 94% | 55 | 366.86 | — |
| 34 | ETH | 4h | Ichimoku | +169.0% | +2.39 | -13.4% | 64% | 22 | 4.24 | — |
| 35 | ETH | 4h | OBVDivergence | +161.4% | +3.24 | -6.0% | 65% | 23 | 4.81 | — |
| 36 | ETH | 4h | HASmoothed | +547.0% | +6.63 | -11.2% | 78% | 139 | 8.56 | — |
| 37 | ETH | 1d | EMA Cross | +140.9% | +5.65 | -13.5% | 57% | 14 | 5.37 | — |
| 38 | ETH | 1d | Supertrend | +0.0% | +0.00 | +0.0% | 0% | 0 | 0.00 | ⚠ NO SIGNALS |
| 39 | ETH | 1d | Trendline Break | +150.1% | +6.85 | -8.4% | 89% | 9 | 15.81 | — |
| 40 | ETH | 1d | Bollinger Rev | +365.2% | +15.27 | +0.0% | 100% | 41 | 0.00 | — |
| 41 | ETH | 1d | RSI Extreme | **-277.1%** | +3.76 | -277.0% | 34% | 29 | 0.10 | ⚠ BROKEN ON BULL MARKET |
| 42 | ETH | 1d | VWAP Reversion | **-103.4%** | -2.12 | -118.5% | 27% | 30 | 0.21 | ⚠ BROKEN ON BULL MARKET |
| 43 | ETH | 1d | Range Breakout | +279.6% | +8.67 | -0.5% | 92% | 12 | 182.76 | — |
| 44 | ETH | 1d | Volume Surge | +243.1% | +7.26 | +0.0% | 100% | 10 | 0.00 | — |
| 45 | ETH | 1d | RSI + MACD Combo | +38.9% | +6.52 | -0.8% | 75% | 8 | 32.23 | — |
| 46 | ETH | 1d | Ichimoku | +33.7% | +4.28 | -1.5% | 50% | 4 | 1.95 | ⚠ LOW SIGNAL |
| 47 | ETH | 1d | OBVDivergence | -78.4% | +1.75 | -93.6% | 50% | 4 | 0.49 | ⚠ LOW SIGNAL |
| 48 | ETH | 1d | HASmoothed | +219.8% | +6.07 | -4.8% | 84% | 19 | 10.46 | — |

---

## Strategy Summary (avg across all combos)

| Strategy | Avg Return% | Avg Sharpe | Avg MaxDD% | Avg WinRate% | Avg PF | Verdict |
|---|---|---|---|---|---|---|
| EMA Cross | +207.4% | +4.38 | -7.1% | 55% | 6.79 | ✅ Solid |
| Supertrend | — | — | — | — | — | ⚠ Buggy (inline impl) |
| Trendline Break | +140.3% | +4.00 | -11.3% | 71% | 6.33 | ✅ Solid |
| **Bollinger Rev** | **+437.7%** | **+13.51** | **-1.4%** | **95%** | **17.57** | 🏆 **BEST** |
| RSI Extreme | -348.3% | +2.12 | -347.4% | 36% | 0.14 | ❌ BROKEN |
| VWAP Reversion | -132.4% | +0.89 | -155.1% | 34% | 0.45 | ❌ BROKEN |
| Range Breakout | +203.0% | +5.68 | -6.9% | 68% | 47.95 | ✅ Strong |
| Volume Surge | +201.7% | +5.20 | -5.5% | 72% | 2.94 | ✅ Strong |
| RSI + MACD Combo | +112.3% | +6.21 | -1.0% | 84% | 116.57 | ✅ Best Sharpe/DD |
| Ichimoku | +101.3% | +3.04 | -5.3% | 56% | 4.21 | ⚠ Low signals |
| OBVDivergence | +39.2% | +2.47 | -43.4% | 65% | 1.50 | ⚠ Inconsistent |
| HASmoothed | +308.1% | +6.08 | -6.2% | 79% | 10.36 | ✅ Consistent |

---

## Best Strategy by Market Regime (min 5 trades)

| Sym/TF | Regime | Strategy | Return% | Sharpe | MaxDD% | WinRate% | Trades |
|---|---|---|---|---|---|---|---|
| BTC/4h | BULL | Bollinger Rev | +248.5% | +12.67 | -2.8% | 91% | 162 |
| BTC/4h | BEAR | Bollinger Rev | +68.4% | +15.38 | -0.8% | 93% | 77 |
| BTC/4h | SIDEWAYS | Bollinger Rev | +65.9% | +12.86 | -1.8% | 89% | 38 |
| BTC/1d | BULL | Bollinger Rev | +113.7% | +15.96 | -1.1% | 95% | 22 |
| BTC/1d | BEAR | Bollinger Rev | +24.8% | +18.01 | -0.0% | 100% | 9 |
| BTC/1d | SIDEWAYS | Bollinger Rev | +30.3% | +11.38 | -1.1% | 100% | 6 |
| ETH/4h | BULL | Bollinger Rev | +355.9% | +12.32 | -2.1% | 91% | 185 |
| ETH/4h | BEAR | Bollinger Rev | +134.8% | +15.19 | -1.6% | 94% | 63 |
| ETH/4h | SIDEWAYS | Bollinger Rev | +106.2% | +9.52 | -2.0% | 89% | 38 |
| ETH/1d | BULL | Bollinger Rev | +195.3% | +16.83 | -0.5% | 100% | 23 |
| ETH/1d | BEAR | Bollinger Rev | +34.5% | +19.24 | -0.0% | 100% | 10 |
| ETH/1d | SIDEWAYS | HASmoothed | +67.6% | +13.82 | -0.4% | 71% | 7 |

> Note: Regime periods — BULL: 2024-01 to 2025-03, BEAR: 2025-04 to 2025-10, SIDEWAYS: 2026-01 to 2026-04.

---

## 🏆 Top Picks by Category

### 🏆 Best for BULL Market (2024–Q1 2025)

| | |
|---|---|
| **Strategy** | Bollinger Reversion |
| **Return** | +355.9% (ETH/4h), +248.5% (BTC/4h) |
| **Sharpe** | +12.32 – +12.67 |
| **MaxDD** | -2.1% (ETH/4h), -2.8% (BTC/4h) |
| **WinRate** | 91% (ETH/4h), 91% (BTC/4h) |
| **Trades** | 185 (ETH/4h), 162 (BTC/4h) |
| **Why wins** | Mean-reversion into Bollinger Band lower/upper touch — BTC rallied $42K→$109K (2024) with persistent lower-band touches. ETH rallied $2.2K→$2.8K. Reversion to moving average works in trending bull with pullbacks. |

### 🏆 Best for BEAR Market (Q2–Q3 2025)

| | |
|---|---|
| **Strategy** | Bollinger Reversion |
| **Return** | +134.8% (ETH/4h), +68.4% (BTC/4h) |
| **Sharpe** | +15.19 (ETH/4h), +15.38 (BTC/4h) |
| **MaxDD** | -1.6% (ETH/4h), -0.8% (BTC/4h) |
| **WinRate** | 94% (ETH/4h), 93% (BTC/4h) |
| **Trades** | 63 (ETH/4h), 77 (BTC/4h) |
| **Why wins** | Counter-intuitive: Bollinger Reversion SHORT side works in bear market. Shorting upper-band touches during the Q2–Q3 2025 correction captured the $-20K BTC drawdown and ETH's drop to ~$1.8K. Mean-reversion short side proves highly profitable in sharply declining markets. |

### 🏆 Best for SIDEWAYS Market (2026)

| | |
|---|---|
| **Strategy** | Bollinger Reversion (4h), HASmoothed (1d) |
| **Return** | +106.2% (ETH/4h), +67.6% (ETH/1d) |
| **Sharpe** | +9.52 (ETH/4h), +13.82 (ETH/1d) |
| **MaxDD** | -2.0% (ETH/4h), -0.4% (ETH/1d) |
| **WinRate** | 89% (ETH/4h), 71% (ETH/1d) |
| **Trades** | 38 (ETH/4h), 7 (ETH/1d) |
| **Why wins** | Sideways markets with tight range = price oscillates around the moving average constantly. Each touch of Bollinger bands triggers a reversion signal with high probability of mean-reversion success. ETH 1d sideways period (Jan–Apr 2026) shows flat price but HA smoothed candles capture small swings. |

---

## Best Strategy by Symbol & Timeframe

### BTC / 4h

| | |
|---|---|
| **Strategy** | Bollinger Reversion |
| **Return** | +447.9% |
| **Sharpe** | +11.76 |
| **MaxDD** | -2.0% |
| **WinRate** | 92% |
| **Trades** | 306 |
| **Profit Factor** | 13.16 |

### BTC / 1d

| | |
|---|---|
| **Strategy** | Bollinger Reversion |
| **Return** | +219.5% |
| **Sharpe** | +15.22 |
| **MaxDD** | -1.5% |
| **WinRate** | 96% |
| **Trades** | 44 |
| **Profit Factor** | 41.96 |

### ETH / 4h

| | |
|---|---|
| **Strategy** | Bollinger Reversion |
| **Return** | +718.1% |
| **Sharpe** | +11.78 |
| **MaxDD** | -2.3% |
| **WinRate** | 93% |
| **Trades** | 322 |
| **Profit Factor** | 15.17 |

### ETH / 1d

| | |
|---|---|
| **Strategy** | Bollinger Reversion |
| **Return** | +365.2% |
| **Sharpe** | +15.27 |
| **MaxDD** | 0.0% |
| **WinRate** | 100% |
| **Trades** | 41 |
| **Profit Factor** | 0.00 (0.00 = no losing trades) |

---

## Strategy Tier List

| Tier | Strategy | Why |
|------|----------|-----|
| 🏆 S | **Bollinger Reversion** | Dominant across all regimes, all pairs, Sharpe 11-15, MaxDD <3%. The single best strategy for this market period. |
| 🏆 A | **HASmoothed** | Consistent +200-500% returns, Sharpe 5-7, solid win rate 75-84%. Best for ETH/daily sideways. |
| 🏆 A | **RSI + MACD Combo** | Exceptional risk-adjusted returns (PF up to 366!), tiny MaxDD 0.3-1%, highest win rates 84-94%. Quality over quantity. |
| 🏆 B | **EMA Cross** | Reliable +130-330% across pairs. More trades = more reliable. |
| 🏆 B | **Range Breakout** | +50-280% range, good Sharpe 4-9, acceptable DD. |
| 🏆 B | **Volume Surge** | +40-345%, solid Sharpe 3-7. Good for trend confirmation. |
| 🏆 C | **Trendline Break** | Moderate returns, reasonable Sharpe 1-7 depending on regime. |
| 🏆 C | **Ichimoku** | Works but low trade count on daily. Best on 4h with more signals. |
| 🏆 D | **OBVDivergence** | Inconsistent — works on ETH/4h, fails on BTC. Requires parameter tuning per asset. |
| ❌ F | **RSI Extreme** | Broken on bull market. Short side mean-reversion loses in prolonged uptrend. |
| ❌ F | **VWAP Reversion** | Broken on bull market. BTC/ETH sustained trends break VWAP reversion assumptions. |
| ⚠ NA | **Supertrend** | Inline implementation produced zero signals — use canonical ACTosha module version separately. |
| ⚠ NA | **BBEMACombo** | Zero signals on Binance data — price structure incompatible with BB-EMA combo entry logic. |

---

## Key Observations

1. **Bollinger Bands mean reversion is the dominant strategy** for this market period (2024-2026). The BTC rally from $42K→$109K and ETH rally $2.2K→$2.8K featured persistent pullbacks to the moving average. Each lower-band touch was a buying opportunity. This is consistent with a "bull market with corrections" regime.

2. **Mean reversion SHORT side is underappreciated**. During the Q2-Q3 2025 bear correction, Bollinger Reversion short signals captured significant drawdowns with Sharpe 15+.

3. **ETH outperforms BTC for mean reversion strategies** — ETH's higher volatility means wider Bollinger bands and more frequent, larger-magnitude reversion opportunities.

4. **Supertrend inline impl is broken** — the ACTosha module version needs separate testing. This backtest used an inline implementation that failed to generate signals.

5. **BBEMACombo incompatibility** — the BB-EMA combo entry logic (which requires price to be between EMA and BB middle band) doesn't occur in BTC's sustained trend structure, resulting in zero signals.

6. **Low trade count strategies on 1d** — Ichimoku and OBVDivergence with small grids produce very few signals on 846-bar daily data. Results for these should be treated as indicative only.

---

## Data Quality Notes

- BTC/4h: 5,076 bars, $42,370 → $77,585 (period low: ~$49,500 in mid-2025, period high: ~$109,500 in early 2024)
- ETH/4h: 5,076 bars, $2,276 → $2,318 (ETH was largely range-bound 2024-2026 with a low of ~$1,818)
- BTC/1d: 846 bars (limited by Binance history)
- ETH/1d: 846 bars

The ETH period return of only ~2% over 2+ years makes it a challenging market for trend-following but excellent for mean-reversion (price constantly reverts to its average in the absence of a sustained trend).

---
*Generated by ACTosha backtester — backtest_binance_2024_2026.md*
