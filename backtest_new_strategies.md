# ACTosha New Strategies Backtest
**Setup:** BTC/USDC 1h | 2025-04-25 → 2026-04-25 | Initial $10,000
**Commission:** 0.04% | **Slippage:** 5 bps | **Optimization:** Grid
**Data:** 8782 hourly bars from Binance

=== BBEMACombo ===
Return: 19.69%
Sharpe: 1.81
MaxDD: 0.0%
WinRate: 100.0%
Trades: 6
Best params: {'ema_period': 21, 'bb_period': 15, 'bb_std': 1.5, 'bb_extreme_threshold': 0.85, 'min_volume_mult': 1.0, 'use_atr_sl': True, 'atr_period': 14, 'atr_multiplier': 2.0, 'risk_reward': 1.5}
Profit Factor: 0

=== Ichimoku ===
Return: 85.66%
Sharpe: 2.65
MaxDD: -3.13%
WinRate: 76.0%
Trades: 25
Best params: {'tenkan_period': 7, 'kijun_period': 30, 'senkou_b_period': 44, 'cloud_shift': 26, 'chikou_confirm': True, 'cloud_thickness_filter': False, 'max_cloud_width': 4.0, 'use_atr_sl': True, 'atr_period': 14, 'atr_multiplier': 2.0, 'risk_reward': 1.5}
Profit Factor: 10.76

=== OBVDivergence ===
Return: 53.41%
Sharpe: 1.42
MaxDD: -15.72%
WinRate: 71.9%
Trades: 32
Best params: {'obv_ema_period': 21, 'price_lookback': 7, 'divergence_lookback': 50, 'min_volume_mult': 1.0, 'require_exact_swing': False, 'swing_tolerance': 0.05, 'use_atr_sl': True, 'atr_period': 14, 'atr_multiplier': 2.0, 'risk_reward': 1.5}
Profit Factor: 2.36

=== HASmoothed ===
Return: 161.68%
Sharpe: 5.13
MaxDD: -3.04%
WinRate: 66.1%
Trades: 192
Best params: {'ha_smooth_ema': 5, 'consecutive_bars': 5, 'volume_ma_period': 20, 'min_volume_mult': 1.0, 'trailing_mode': True, 'use_atr_sl': True, 'atr_period': 14, 'atr_multiplier': 2.0, 'risk_reward': 1.5}
Profit Factor: 4.33

## Summary Table

| Strategy | Return | Sharpe | MaxDD | WinRate | Trades | PF |
|---|---|---|---|---|---|---|
| BBEMACombo | 19.69% | 1.81 | 0.0% | 100.0% | 6 | 0 || Ichimoku | 85.66% | 2.65 | -3.13% | 76.0% | 25 | 10.76 || OBVDivergence | 53.41% | 1.42 | -15.72% | 71.9% | 32 | 2.36 || HASmoothed | 161.68% | 5.13 | -3.04% | 66.1% | 192 | 4.33 |
## vs Bollinger Reversion (492.91%, Sharpe 14.36)

| Strategy | Return | Sharpe | MaxDD | WinRate | Trades | PF |
|---|---|---|---|---|---|---|
| **Bollinger Reversion** (benchmark) | **492.91%** | **14.36** | **-0.34%** | **96.0%** | **883** | **32.31** |
| BBEMACombo | 19.69% | 1.81 | 0.0% | 100.0% | 6 | 0 || Ichimoku | 85.66% | 2.65 | -3.13% | 76.0% | 25 | 10.76 || OBVDivergence | 53.41% | 1.42 | -15.72% | 71.9% | 32 | 2.36 || HASmoothed | 161.68% | 5.13 | -3.04% | 66.1% | 192 | 4.33 |
## Ranking by Sharpe

1. **HASmoothed** — Sharpe 5.13, Return 161.68%, MaxDD -3.04%, PF 4.33
2. **Ichimoku** — Sharpe 2.65, Return 85.66%, MaxDD -3.13%, PF 10.76
3. **BBEMACombo** — Sharpe 1.81, Return 19.69%, MaxDD 0.0%, PF 0
4. **OBVDivergence** — Sharpe 1.42, Return 53.41%, MaxDD -15.72%, PF 2.36

**Best:** HASmoothed (Sharpe 5.13, Return 161.68%)
