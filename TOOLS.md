# TOOLS.md
# ACTosha — Tool Registry, Access Rules & Execution Protocols
# Priority Level: 6 (resource layer)
# Version: 1.0.0
# Last_Updated: 2026-04-27

═══════════════════════════════════════════════════════════
PURPOSE
═══════════════════════════════════════════════════════════

TOOLS.md — реестр инструментов ACTosha.
Определяет: какие tools агент использует для trading operations.

ACTosha использует:
 — Python modules (CCXT, pandas, numpy, vectorbt)
 — File operations (state, cache)
 — Internal agents (ScannerAgent, BacktestAgent, PortfolioAgent)

NOT доступно:
 — shell_execute (риск необратимых операций)
 — order_execute (только через PaperExecutor/LiveExecutor)

═══════════════════════════════════════════════════════════
SECTION 1 — TOOL REGISTRY
═══════════════════════════════════════════════════════════

1.1 Категории инструментов

 ──────────────────────────────────────────────────────
 CATEGORY       │ ОПИСАНИЕ
 ──────────────────────────────────────────────────────
 DATA_OPS        │ Fetch, cache, normalize OHLCV data
 INDICATOR_OPS   │ Technical indicators computation
 STRATEGY_OPS   │ Signal generation, strategy execution
 BACKTEST_OPS   │ Backtesting via BacktestEngine
 EXECUTOR_OPS   │ Paper/Live order execution
 SCANNER_OPS    │ Market scanning and opportunity detection
 STATE_OPS      │ Portfolio and state management
 REPORTING_OPS  │ Metrics calculation, reporting
 ──────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: DATA_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: data_fetch
TOOL_NAME: OHLCV Data Fetch
DESCRIPTION: Загрузка OHLCV данных с бирж через CCXT
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 100 req/min per exchange
TIMEOUT_SEC: 30
INPUT_PARAMS:
  symbols: [list[str]]
  timeframe: [str] — 1m, 5m, 15m, 1h, 4h, 1d, 1w
  since: [timestamp | null]
  limit: [int, default: 1000]
  exchange: [hyperliquid | binance]
OUTPUT_SCHEMA:
  { symbols_count, bars_loaded, duration_ms, errors }
SIDE_EFFECTS: writes to cache (Parquet)
USE_WHEN: Scanner cycle, Backtest cycle, Strategy run
────────────────────────────────────────────────────────

TOOL_ID: data_cache_load
TOOL_NAME: Cache Loader
DESCRIPTION: Загрузка OHLCV из локального кэша
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: unlimited
TIMEOUT_SEC: 10
INPUT_PARAMS:
  symbol: [str]
  timeframe: [str]
  since: [timestamp | null]
  until: [timestamp | null]
OUTPUT_SCHEMA:
  { hit: bool, rows: int, path: str | null }
SIDE_EFFECTS: read-only
USE_WHEN: Data already cached, faster than fetch
────────────────────────────────────────────────────────

TOOL_ID: data_normalize
TOOL_NAME: Data Normalizer
DESCRIPTION: Нормализация OHLCV в единый формат
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: unlimited
TIMEOUT_SEC: 5
INPUT_PARAMS:
  df: [pd.DataFrame] — raw OHLCV
  source: [str] — exchange name
OUTPUT_SCHEMA:
  { columns: [timestamp, open, high, low, close, volume],
    rows: int, timezone: "UTC" }
SIDE_EFFECTS: returns normalized DataFrame
USE_WHEN: After data_fetch, before indicators
────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: INDICATOR_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: indicators_compute
TOOL_NAME: Indicator Engine
DESCRIPTION: Вычисление технических индикаторов
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: unlimited
TIMEOUT_SEC: 10
INPUT_PARAMS:
  df: [pd.DataFrame] — normalized OHLCV
  indicators: [list[str]] — [RSI, EMA, MACD, BB, ATR, ...]
  params: [dict] — indicator-specific params
OUTPUT_SCHEMA:
  { df: pd.DataFrame with added indicator columns,
    computed: [list of computed indicators],
    errors: [list of failed indicators] }
SIDE_EFFECTS: read-only operation
USE_WHEN: Before strategy signal generation
BUILT_IN_INDICATORS:
 — Moving averages: SMA, EMA, WMA
 — Momentum: RSI, MACD, Stochastic
 — Volatility: Bollinger Bands, ATR, Keltner
 — Volume: OBV, Volume Profile, VWAP
 — Custom: Supertrend, Ichimoku, ADX
────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: STRATEGY_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: strategy_generate_signals
TOOL_NAME: Signal Generator
DESCRIPTION: Генерация торговых сигналов из стратегии
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: unlimited
TIMEOUT_SEC: 10
INPUT_PARAMS:
  strategy: [Strategy] — initialized strategy instance
  df: [pd.DataFrame] — OHLCV with indicators
OUTPUT_SCHEMA:
  { signals: pd.DataFrame,
    metadata: { strategy_name, params, created_at },
    signal_count: int }
SIDE_EFFECTS: read-only
USE_WHEN: After indicators computed
SUPPORTED_STRATEGIES:
 — TrendFollowing: ema_cross, supertrend, trendline_break
 — MeanReversion: bollinger_rev, rsi_extreme, vwap_rev
 — Breakout: range_break, volume_surge
 — Momentum: rsi_macd_combo
────────────────────────────────────────────────────────

TOOL_ID: strategy_validate
TOOL_NAME: Strategy Validator
DESCRIPTION: Валидация params перед бэктестом
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: unlimited
TIMEOUT_SEC: 5
INPUT_PARAMS:
  strategy_name: [str]
  params: [dict]
  symbol: [str]
OUTPUT_SCHEMA:
  { valid: bool, errors: [str], warnings: [str] }
USE_WHEN: Before backtest run
────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: BACKTEST_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: backtest_run
TOOL_NAME: Backtest Engine
DESCRIPTION: Запуск бэктеста стратегии
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 10 concurrent
TIMEOUT_SEC: 300
INPUT_PARAMS:
  strategy: [Strategy]
  df: [pd.DataFrame]
  initial_capital: [float, default: 10000]
  commission: [float] — per-trade commission rate
  slippage_bps: [float, default: 5]
OUTPUT_SCHEMA:
  { equity_curve: pd.Series,
    trades: pd.DataFrame,
    metrics: {
      sharpe_ratio: float,
      sortino_ratio: float,
      max_drawdown: float,
      max_drawdown_duration: int,
      win_rate: float,
      profit_factor: float,
      calmar_ratio: float,
      total_trades: int,
      avg_trade_duration: int,
      exposure_time: float
    },
    summary: dict }
SIDE_EFFECTS: writes results to state
USE_WHEN: Strategy validation, optimization
────────────────────────────────────────────────────────

TOOL_ID: backtest_optimize
TOOL_NAME: Parameter Optimizer
DESCRIPTION: Оптимизация параметров стратегии (grid search)
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 3 concurrent
TIMEOUT_SEC: 1800
INPUT_PARAMS:
  strategy: [Strategy]
  df: [pd.DataFrame]
  param_space: [dict] — {param_name: [list of values]}
  metric: [str] — "sharpe_ratio" | "sortino_ratio"
  direction: ["maximize" | "minimize"]
OUTPUT_SCHEMA:
  { best_params: dict,
    best_metrics: dict,
    trials: int }
USE_WHEN: Nightly optimization, strategy tuning
────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: EXECUTOR_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: executor_submit
TOOL_NAME: Order Submitter
DESCRIPTION: Отправка ордера через PaperExecutor
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 10 orders/min
TIMEOUT_SEC: 5
INPUT_PARAMS:
  order: [Order] — {symbol, side, order_type, price, size}
  executor: [PaperExecutor | LiveExecutor]
OUTPUT_SCHEMA:
  { order_id: str,
    status: "FILLED" | "PENDING" | "REJECTED",
    fill_price: float,
    fill_time: timestamp }
RISK_CHECKS:
 — Position size ≤ 5% portfolio
 — Max 3 simultaneous positions
 — Max drawdown not breached
SIDE_EFFECTS: writes to portfolio state
USE_WHEN: Signal triggered, risk checks passed
────────────────────────────────────────────────────────

TOOL_ID: executor_cancel
TOOL_NAME: Order Canceller
DESCRIPTION: Отмена отложенного ордера
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 10 orders/min
TIMEOUT_SEC: 5
INPUT_PARAMS:
  order_id: [str]
  executor: [PaperExecutor | LiveExecutor]
OUTPUT_SCHEMA:
  { success: bool, cancelled_at: timestamp }
USE_WHEN: Signal cancelled, TP/SL hit, manual cancel
────────────────────────────────────────────────────────

TOOL_ID: executor_get_positions
TOOL_NAME: Positions Reader
DESCRIPTION: Получение открытых позиций
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 30 req/min
TIMEOUT_SEC: 3
INPUT_PARAMS:
  executor: [PaperExecutor | LiveExecutor]
OUTPUT_SCHEMA:
  { positions: [list of Position],
    count: int }
USE_WHEN: Portfolio check, risk monitoring
────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: SCANNER_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: scanner_pattern
TOOL_NAME: Pattern Scanner
DESCRIPTION: Поиск chart patterns и candlestick patterns
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 20 runs/min
TIMEOUT_SEC: 30
INPUT_PARAMS:
  symbols: [list[str]]
  timeframe: [str]
  min_strength: [float, default: 0.65]
OUTPUT_SCHEMA:
  { opportunities: [Opportunity],
    scanned_count: int,
    found_count: int }
USE_WHEN: Scheduled scan cycle
PATTERNS_DETECTED:
 — Chart: double top/bottom, H&S, triangles, wedges, channels
 — Candlestick: Engulfing, Hammer, Doji, Morning Star, Pin Bar
────────────────────────────────────────────────────────

TOOL_ID: scanner_indicator
TOOL_NAME: Indicator Scanner
DESCRIPTION: Поиск extreme indicator values
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 20 runs/min
TIMEOUT_SEC: 30
INPUT_PARAMS:
  symbols: [list[str]]
  timeframe: [str]
  conditions: [dict] — e.g., {"RSI": {"<": 30}}
OUTPUT_SCHEMA:
  { opportunities: [Opportunity],
    found_count: int }
USE_WHEN: Scheduled scan cycle
────────────────────────────────────────────────────────

TOOL_ID: scanner_volume
TOOL_NAME: Volume Scanner
DESCRIPTION: Поиск аномалий объёма
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 20 runs/min
TIMEOUT_SEC: 30
INPUT_PARAMS:
  symbols: [list[str]]
  timeframe: [str]
  volume_threshold: [float, default: 2.0] — x20 avg
OUTPUT_SCHEMA:
  { opportunities: [Opportunity],
    found_count: int }
USE_WHEN: Scheduled scan cycle
────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: STATE_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: state_save
TOOL_NAME: State Saver
DESCRIPTION: Сохранение состояния портфеля
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 60 writes/min
TIMEOUT_SEC: 5
INPUT_PARAMS:
  state_type: [portfolio | scanner | backtest | strategy]
  data: [dict]
OUTPUT_SCHEMA:
  { saved: bool, path: str, backed_up: bool }
SIDE_EFFECTS: writes JSON to state/ directory
USE_WHEN: After every completed cycle
────────────────────────────────────────────────────────

TOOL_ID: state_load
TOOL_NAME: State Loader
DESCRIPTION: Загрузка состояния портфеля
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 60 reads/min
TIMEOUT_SEC: 5
INPUT_PARAMS:
  state_type: [portfolio | scanner | backtest | strategy]
OUTPUT_SCHEMA:
  { loaded: bool, data: dict | null, path: str }
USE_WHEN: Session boot, recovery
────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY: REPORTING_OPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_ID: metrics_calculate
TOOL_NAME: Metrics Calculator
DESCRIPTION: Расчёт performance metrics
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: unlimited
TIMEOUT_SEC: 10
INPUT_PARAMS:
  equity_curve: [pd.Series]
  trades: [pd.DataFrame]
  initial_capital: [float]
OUTPUT_SCHEMA:
  { metrics: PerformanceMetrics,
    summary: dict }
CALCULATED:
 — Sharpe ratio (annualized)
 — Sortino ratio (annualized)
 — Maximum drawdown (% and duration)
 — Win rate
 — Profit factor
 — Calmar ratio
 — Total return
 — Trade count / avg duration
 — Exposure time
────────────────────────────────────────────────────────

TOOL_ID: report_generate
TOOL_NAME: Report Generator
DESCRIPTION: Генерация отчётов
STATUS: ACTIVE
REQUIRES_CONFIRM: NO
RATE_LIMIT: 10 reports/min
TIMEOUT_SEC: 30
INPUT_PARAMS:
  report_type: [daily | weekly | performance | trade_summary]
  period: [dict] — {since, until}
  format: [json | markdown | table]
OUTPUT_SCHEMA:
  { report: str | dict,
    generated_at: timestamp }
USE_WHEN: Scheduled reporting, on-demand request
────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════
SECTION 2 — TOOL EXECUTION RULES
═══════════════════════════════════════════════════════════

2.1 Общие правила

 RULE T-1: DATA BEFORE ACTION
 Всегда fetch/cache data перед indicators/strategy.

 RULE T-2: RISK CHECK BEFORE EXECUTE
 executor_submit требует risk check:
 — Position size ≤ 5%
 — Max 3 positions
 — Max drawdown not breached

 RULE T-3: CACHE BEFORE FETCH
 Проверить cache перед fetch с биржи.
 Использовать cached data если свежее.

 RULE T-4: VALIDATE BEFORE BACKTEST
 strategy_validate перед backtest_run.
 Проверить params на validity.

 RULE T-5: CONFIDENCE GATING
 Scanner output фильтруется по strength ≥ 0.65.

2.2 Цепочка вызова

 SCAN CYCLE:
 1. data_fetch → symbols OHLCV
 2. data_normalize → unified schema
 3. indicators_compute → df + indicators
 4. scanner_pattern + scanner_indicator + scanner_volume
 5. Filter by strength
 6. state_save (scanner_state)
 7. report_generate (if needed)

 BACKTEST CYCLE:
 1. data_cache_load or data_fetch
 2. data_normalize
 3. strategy_validate
 4. backtest_run
 5. metrics_calculate
 6. state_save (backtest_state)
 7. report_generate

 PAPER TRADE CYCLE:
 1. strategy_generate_signals
 2. Risk check
 3. executor_submit
 4. executor_get_positions
 5. state_save (portfolio_state)
 6. report_generate (trade_summary)

═══════════════════════════════════════════════════════════
SECTION 3 — DISABLED TOOLS (NOT AVAILABLE)
═══════════════════════════════════════════════════════════

Следующие инструменты НЕ доступны ACTosha:

 TOOL            │ ПРИЧИНА
 ────────────────┼────────────────────────────────────────
 shell_execute   │ Риск необратимых shell операций
 order_execute   │ Только через PaperExecutor/LiveExecutor
 database_write  │ Нет DB, только Parquet cache + JSON state
 webhook_call    │ Нет external HTTP calls
 telegram_send   │ Через J.A.R.V.I.S только
 wallet_access   │ Не в domain ACTosha

═══════════════════════════════════════════════════════════
SECTION 4 — ERROR HANDLING
═══════════════════════════════════════════════════════════

API_ERROR:
 — data_fetch → retry 3x с exponential backoff
 — Если fails → use cached data if available
 — Если нет cache → skip symbol, continue

VALIDATION_ERROR:
 — strategy_validate → return errors, don't run backtest
 — Backtest rejected if params invalid

RISK_REJECTED:
 — executor_submit → reject order, log reason
 — Continue without position

SCANNER_LOOP:
 — Track results hash per cycle
 — >5 same results → pause scanning
 — Alert J.A.R.V.I.S

═══════════════════════════════════════════════════════════
SECTION 5 — INTERACTION MODEL WITH OTHER DOCUMENTS
═══════════════════════════════════════════════════════════

TOOLS.md → SOUL.md
 SOUL P-2 (Risk First) реализуется через RISK_CHECKS в executor_submit.
 SOUL P-3 (Evidence Over Narrative) реализуется через metrics_calculate.

TOOLS.md → IDENTITY.md
 ACTosha trading domain определяет tool scope.

TOOLS.md → HEARTBEAT.md
 SCAN_CYCLE, BACKTEST_CYCLE используют tool chains из Section 2.

TOOLS.md → MEMORY.md
 state_save/state_load используют STATE_DIR.
 Memory persistence через state files.

═══════════════════════════════════════════════════════════
VERSION & AUDIT
═══════════════════════════════════════════════════════════

v1.0.0 — 2026-04-27 — Mr.Agent (Architect) created ACTosha tools.
Based on: ACTosha ARCHITECTURE.md + OpenClaw TOOLS template.
