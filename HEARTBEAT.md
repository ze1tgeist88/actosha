# HEARTBEAT.md
# ACTosha — Operational Rhythm & Health Protocols
# Priority Level: 5 (operational layer)
# Version: 1.0.0
# Last_Updated: 2026-04-27

═══════════════════════════════════════════════════════════
PURPOSE
═══════════════════════════════════════════════════════════

HEARTBEAT.md определяет операционный ритм ACTosha.
КАК и КОГДА выполняет работу.

ACTosha — trading агент.
Его задачи: сканирование рынков, анализ, бэктестинг, симуляция.

HEARTBEAT адаптирован для trading workflow:
scan → analyze → signal → backtest → report → alert.

═══════════════════════════════════════════════════════════
SECTION 1 — OPERATIONAL MODEL
═══════════════════════════════════════════════════════════

1.1 Режим работы

 OPERATIONAL_MODE: SCHEDULED + EVENT-DRIVEN
 ACTIVATION_TRIGGER: Cron schedule / TASK от ORCH
 DEACTIVATION: RESULT отправлен / ESCALATED / TIMEOUT

 SCHEDULE OPTIONS:
 — ScannerAgent: каждые 15 min (configurable)
 — BacktestAgent: по запросу / nightly optimization
 — PortfolioAgent: каждые 5 min (position monitoring)

 НЕТ:
 — Постоянного polling без необходимости
 — Автономных действий без входящей задачи или расписания
 — Live trading без авторизации

 ЕСТЬ:
 — SELF-CHECK при старте сессии
 — SCAN-CYCLE при cron trigger
 — BACKTEST-CYCLE при запросе
 — HEALTH-REPORT по запросу ORCH

1.2 Жизненный цикл одной задачи

 ┌──────────────────────────────────────────────────────┐
 │ │
 │ [TRIGGER: cron / TASK RECEIVED] │
 │ ↓ │
 │ [HEALTH CHECK] ← проверка readiness │
 │ ↓ │
 │ [PHASE 1: DATA FETCH] │
 │ ↓ │
 │ [PHASE 2: INDICATORS] │
 │ ↓ │
 │ [PHASE 3: SIGNAL GENERATION] │
 │ ↓ │
 │ [PHASE 4: OPPORTUNITY DETECTION] │
 │ ↓ │
 │ [PHASE 5: ALERT / REPORT] │
 │ ↓ │
 │ [RESULT] │
 │ │
 └──────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
SECTION 2 — SESSION LIFECYCLE
═══════════════════════════════════════════════════════════

2.1 SESSION START — чеклист при старте

 Выполняется один раз при инициализации сессии.

 ┌─ SESSION_START_CHECK ───────────────────────────────┐
 │ │
 │ CONTEXT LOADING: │
 │ □ Загрузить IDENTITY.md │
 │ □ Загрузить USER.md │
 │ □ Проверить configs (exchanges, API status) │
 │ │
 │ TOOLS CHECK: │
 │ □ Проверить Python environment │
 │ □ Проверить CCXT availability │
 │ □ Проверить cache directory │
 │ □ Проверить ACTosha modules │
 │ │
 │ STATE CHECK: │
 │ □ Проверить last scan time │
 │ □ Проверить open positions (PaperExecutor) │
 │ □ Проверить portfolio value │
 │ │
 │ RESULT: │
 │ ✓ Все ОК → STATE = READY → готов │
 │ ✗ Critical failure → ESCALATE → ждать ORCH │
 │ │
 └─────────────────────────────────────────────────────┘

2.2 SESSION END — чеклист при завершении

 ┌─ SESSION_END_CHECK ─────────────────────────────────┐
 │ │
 │ TASK COMPLETION: │
 │ □ Все задачи завершены или ESCALATED │
 │ □ Нет зависших позиций │
 │ │
 │ STATE SAVE: │
 │ □ Сохранить portfolio state │
 │ □ Обновить scan results │
 │ □ Логировать результаты │
 │ │
 │ METRICS FLUSH: │
 │ □ Сохранить session metrics │
 │ │
 └─────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
SECTION 3 — SCAN CYCLE
═══════════════════════════════════════════════════════════

Scan cycle запускается по cron (default: каждые 15 min).

 ┌─ SCAN_CYCLE ─────────────────────────────────────────┐
 │ │
 │ STEP 1: FETCH │
 │ □ symbols = configured list │
 │ □ timeframe = scan_timeframe │
 │ □ fetch via DataFeeder │
 │ □ normalize to unified OHLCV │
 │ │
 │ STEP 2: INDICATORS │
 │ □ compute for each symbol │
 │ □ indicators = [RSI, EMA, MACD, BB, Volume] │
 │ │
 │ STEP 3: SCAN │
 │ □ pattern_scanner.run() │
 │ □ indicator_scanner.run() │
 │ □ volume_scanner.run() │
 │ □ arbitrage_scanner.run() │
 │ │
 │ STEP 4: FILTER │
 │ □ strength ≥ threshold (default 0.65) │
 │ □ remove duplicates │
 │ □ sort by strength desc │
 │ │
 │ STEP 5: ALERT │
 │ □ if opportunities found → Telegram │
 │ □ log to scanner results │
 │ │
 └─────────────────────────────────────────────────────┘

3.1 Scan Configuration

 SCAN_TIMEFRAME: 1h (configurable)
 MIN_STRENGTH: 0.65
 MAX_ALERTS_PER_CYCLE: 5
 SCAN_SYMBOLS: configurable list

DEFAULT SCAN SYMBOLS:
 Hyperliquid: BTC, ETH, SOL perp
 Binance: BTC, ETH, SOL, BNB, XRP (spot + perp)

═══════════════════════════════════════════════════════════
SECTION 4 — BACKTEST CYCLE
═══════════════════════════════════════════════════════════

Backtest cycle запускается по запросу или nightly.

 ┌─ BACKTEST_CYCLE ─────────────────────────────────────┐
 │ │
 │ STEP 1: PREPARE │
 │ □ strategy = specified │
 │ □ symbol = specified │
 │ □ timeframe = specified │
 │ □ fetch/cached OHLCV │
 │ │
 │ STEP 2: RUN │
 │ □ BacktestEngine.run() │
 │ □ params = strategy.get_params() │
 │ □ initial_capital = configured │
 │ │
 │ STEP 3: VALIDATE │
 │ □ metrics = BacktestResult.metrics │
 │ □ check against thresholds │
 │ □ Sharpe > 1.0? │
 │ □ MaxDD < 15%? │
 │ □ WinRate > 50%? │
 │ │
 │ STEP 4: REPORT │
 │ □ format results │
 │ □ save to backtest_results/ │
 │ □ if requested → optimize params │
 │ │
 └─────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
SECTION 5 — HEALTH MONITORING
═══════════════════════════════════════════════════════════

5.1 Индикаторы здоровья ACTosha

 HEALTH_INDICATORS:

 GREEN (нормальная работа):
 — Scan cycles completing successfully
 — No API errors
 — Paper positions tracked correctly
 — Alerts sent properly

 YELLOW (деградация, мониторинг):
 — API rate limiting detected
 — Partial data fetched
 — > 2 failed scan cycles in row
 — Cache miss > 30%

 RED (требует вмешательства):
 — CCXT API failure
 — Position state inconsistent
 — Max drawdown breached (PaperExecutor)
 — Scanner loop detected

5.2 HEALTH-REPORT

 {
   "message_type": "HEALTH_REPORT",
   "agent": "ACTosha",
   "state": "[IDLE | SCANNING | BACKTESTING | ERROR]",
   "health": "[GREEN | YELLOW | RED]",
   "current_task": "[task_id | none]",
   "last_scan": "[timestamp | none]",
   "open_positions": [int],
   "portfolio_value": float,
   "alerts_sent_today": [int],
   "errors_today": [int],
   "timestamp": "[ISO 8601 UTC]"
 }

═══════════════════════════════════════════════════════════
SECTION 6 — METRICS & OBSERVABILITY
═══════════════════════════════════════════════════════════

PER SCAN CYCLE:
 — symbols_scanned: int
 — opportunities_found: int
 — alerts_sent: int
 — scan_duration_ms: int
 — errors: int

PER BACKTEST:
 — strategy_name: str
 — symbol: str
 — timeframe: str
 — sharpe_ratio: float
 — max_drawdown: float
 — win_rate: float
 — trades: int
 — duration_ms: int

PER PAPER TRADE:
 — signal_side: str
 — entry_price: float
 — exit_price: float
 — pnl: float
 — pnl_pct: float
 — hold_duration: int (bars)
 — status: [open | closed | stopped]

═══════════════════════════════════════════════════════════
SECTION 7 — ERROR RECOVERY
═══════════════════════════════════════════════════════════

API_ERROR:
 — Логировать error
 — Retry с exponential backoff (3 attempts)
 — Если fails → skip cycle, не блокировать

DATA_MISSING:
 — Cache hit miss → fetch from exchange
 — Rate limited → use cached data if available
 — No data → skip symbol, continue

POSITION_INCONSISTENCY:
 — Check PaperExecutor state
 — Rebuild from logs if needed
 — Alert J.A.R.V.I.S if unrecoverable

SCANNER_LOOP:
 — Track results per cycle
 — >5 same results → pause scanning
 — Alert J.A.R.V.I.S
 — Resume after manual check

═══════════════════════════════════════════════════════════
SECTION 8 — INTERACTION MODEL WITH OTHER DOCUMENTS
═══════════════════════════════════════════════════════════

HEARTBEAT.md → SOUL.md
 SOUL principles (Risk First, Evidence Over Narrative) реализуются
 через PHASE checks и RISK MANAGEMENT в каждом цикле.

HEARTBEAT.md → IDENTITY.md
 ACTosha identity (OPERATOR, trading specialist) определяет
 task types и operational modes.

HEARTBEAT.md → AGENTS.md
 AGENTS.md agent registry используется для reporting.
 TASK формат из AGENTS.md.

HEARTBEAT.md → TOOLS.md
 TOOLS.md определяет какие tools ACTosha использует.

═══════════════════════════════════════════════════════════
VERSION & AUDIT
═══════════════════════════════════════════════════════════

v1.0.0 — 2026-04-27 — Mr.Agent (Architect) created ACTosha heartbeat.
Based on: ACTosha ARCHITECTURE.md + OpenClaw HEARTBEAT template.
