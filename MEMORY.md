# MEMORY.md
# ACTosha — Memory Architecture, Storage Rules & Retrieval Protocols
# Priority Level: 6 (resource layer)
# Version: 1.0.0
# Last_Updated: 2026-04-27

═══════════════════════════════════════════════════════════
PURPOSE
═══════════════════════════════════════════════════════════

MEMORY.md — архитектура памяти ACTosha.

Определяет: как агент хранит результаты сканирования,
бэктестов, портфель, состояние стратегий.

WORKING MEMORY → активный контекст (позиции, сигналы, метрики)
EPISODIC MEMORY → история циклов, результатов, алертов
SEMANTIC MEMORY → паттерны рынка, проверенные стратегии
PROCEDURAL MEMORY → как запускать бэктесты,сканы

═══════════════════════════════════════════════════════════
SECTION 1 — MEMORY LAYERS
═══════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 1: WORKING MEMORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Назначение:
 Активный контекст текущего цикла сканирования/бэктеста.
 Существует только во время выполнения.
 Не персистируется автоматически.

Содержимое:

 current_scan:
   symbols: [список сканируемых]
   timeframe: str
   start_time: timestamp
   opportunities_found: int
   alerts_sent: int

 current_backtest:
   strategy: str
   symbol: str
   metrics: dict
   status: [running | complete | failed]

 portfolio_state:
   positions: [list of open positions]
   balance: float
   portfolio_value: float
   open_count: int

 active_signals:
   signal_id: str
   symbol: str
   side: str
   strength: float
   entry_price: float
   status: [active | triggered | expired]

Время жизни: одна задача сканирования/бэктеста
Очищается: автоматически после RESULT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2: EPISODIC MEMORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Назначение:
 История циклов сканирования и результатов бэктестов.
 "Что сканировали, когда, какие сигналы."

Субтипы:

 SCAN_CYCLE_RECORD — запись о цикле сканирования
 BACKTEST_RECORD — результат бэктеста
 TRADE_RECORD — история бумажных сделок
 ALERT_RECORD — отправленный алерт
 ERROR_LOG — ошибки и их контекст

Структура SCAN_CYCLE_RECORD:
 {
   "memory_id": "[uuid]",
   "type": "EPISODIC",
   "subtype": "SCAN_CYCLE_RECORD",
   "agent_id": "ACTosha",
   "timestamp": "[ISO 8601 UTC]",
   "content": {
     "cycle_id": "[uuid]",
     "symbols_scanned": ["BTC", "ETH", ...],
     "timeframe": "1h",
     "opportunities_found": int,
     "alerts_sent": int,
     "duration_ms": int,
     "errors": ["error1", ...],
     "status": "[SUCCESS | PARTIAL | FAILED]"
   },
   "tags": ["scan", "market", "opportunity"],
   "importance": 0.6,
   "ttl_days": 30
 }

Структура BACKTEST_RECORD:
 {
   "memory_id": "[uuid]",
   "type": "EPISODIC",
   "subtype": "BACKTEST_RECORD",
   "agent_id": "ACTosha",
   "timestamp": "[ISO 8601 UTC]",
   "content": {
     "backtest_id": "[uuid]",
     "strategy": "[ema_cross]",
     "symbol": "[BTC]",
     "timeframe": "[1h]",
     "period": "[since - until]",
     "metrics": {
       "sharpe_ratio": float,
       "max_drawdown": float,
       "win_rate": float,
       "profit_factor": float,
       "total_trades": int,
       "total_return_pct": float
     },
     "params": {...},
     "status": "[SUCCESS | FAILED | REJECTED]",
     "rejected_reason": "[if any]"
   },
   "tags": ["backtest", "strategy", "validation"],
   "importance": 0.8,
   "ttl_days": 90
 }

Структура TRADE_RECORD:
 {
   "memory_id": "[uuid]",
   "type": "EPISODIC",
   "subtype": "TRADE_RECORD",
   "agent_id": "ACTosha",
   "timestamp": "[ISO 8601 UTC]",
   "content": {
     "trade_id": "[uuid]",
     "symbol": "[BTC]",
     "side": "[LONG | SHORT]",
     "entry_price": float,
     "exit_price": float,
     "size_pct": float,
     "pnl": float,
     "pnl_pct": float,
     "status": "[OPEN | CLOSED | STOPPED]",
     "signal_strategy": "[strategy_name]",
     "hold_duration_bars": int,
     "commission_paid": float
   },
   "tags": ["trade", "paper", "execution"],
   "importance": 0.7,
   "ttl_days": 60
 }

Структура ALERT_RECORD:
 {
   "memory_id": "[uuid]",
   "type": "EPISODIC",
   "subtype": "ALERT_RECORD",
   "agent_id": "ACTosha",
   "timestamp": "[ISO 8601 UTC]",
   "content": {
     "alert_id": "[uuid]",
     "symbol": "[BTC]",
     "side": "[LONG | SHORT]",
     "strength": float,
     "entry_zone": "[price range]",
     "strategy": "[signal_source]",
     "confidence": "[HIGH | MEDIUM | LOW]",
     "sent_to": "[channel]"
   },
   "tags": ["alert", "signal"],
   "importance": 0.5,
   "ttl_days": 30
 }

Время жизни:
 SCAN_CYCLE_RECORD: 30 дней
 BACKTEST_RECORD: 90 дней
 TRADE_RECORD: 60 дней
 ALERT_RECORD: 30 дней
 ERROR_LOG: 30 дней

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 3: SEMANTIC MEMORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Назначение:
 Накопленные знания о рынках, стратегиях, паттернах.
 "Что агент знает о рынке."

Субтипы:

 MARKET_PATTERN — обнаруженный паттерн рынка
 STRATEGY_CONTEXT — протестированная стратегия и её результаты
 EXCHANGE_CONTEXT — специфика биржи (fees, quirks)
 SYMBOL_CONTEXT — особенности конкретного символа

Структура MARKET_PATTERN:
 {
   "memory_id": "[uuid]",
   "type": "SEMANTIC",
   "subtype": "MARKET_PATTERN",
   "agent_id": "ACTosha",
   "content": {
     "pattern_name": "[имя паттерна]",
     "description": "[описание]",
     "conditions": {...},
     "observed_on": ["[symbol]", ...],
     "success_rate": float,
     "sample_count": int,
     "avg_strength": float
   },
   "confidence": 0.0–1.0,
   "tags": ["pattern", "market"],
   "ttl_days": null
 }

Структура STRATEGY_CONTEXT:
 {
   "memory_id": "[uuid]",
   "type": "SEMANTIC",
   "subtype": "STRATEGY_CONTEXT",
   "agent_id": "ACTosha",
   "content": {
     "strategy_name": "[ema_cross]",
     "backtests_count": int,
     "avg_sharpe": float,
     "avg_maxdd": float,
     "best_params": {...},
     "symbols_it_works": ["BTC", "ETH", ...],
     "timeframes": ["1h", "4h"],
     "notes": "[observations]"
   },
   "confidence": 0.0–1.0,
   "tags": ["strategy", "backtest"],
   "ttl_days": null
 }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 4: PROCEDURAL MEMORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Назначение:
 "Как делать" — проверенные процедуры запуска сканирования
 и бэктестинга.

Субтипы:

 SCAN_RECIPE — последовательность шагов сканирования
 BACKTEST_RECIPE — последовательность бэктеста
 RISK_CALC — формулы расчёта рисков

Структура SCAN_RECIPE:
 {
   "memory_id": "[uuid]",
   "type": "PROCEDURAL",
   "subtype": "SCAN_RECIPE",
   "agent_id": "ACTosha",
   "name": "MARKET_SCAN_CYCLE",
   "description": "Standard market scan cycle",
   "steps": [
     {"step": 1, "action": "fetch_ohlcv", "output": "raw data"},
     {"step": 2, "action": "normalize_ohlcv", "output": "unified df"},
     {"step": 3, "action": "compute_indicators", "output": "df with indicators"},
     {"step": 4, "action": "run_scanners", "output": "opportunities"},
     {"step": 5, "action": "filter_by_strength", "output": "filtered opp"},
     {"step": 6, "action": "send_alerts", "output": "telegram alert"}
   ],
   "applies_to": ["scan"],
   "success_rate": 0.95,
   "use_count": int,
   "ttl_days": null
 }

Структура BACKTEST_RECIPE:
 {
   "memory_id": "[uuid]",
   "type": "PROCEDURAL",
   "subtype": "BACKTEST_RECIPE",
   "agent_id": "ACTosha",
   "name": "BACKTEST_CYCLE",
   "description": "Standard backtest procedure",
   "steps": [
     {"step": 1, "action": "fetch_or_load_data", "output": "ohlcv df"},
     {"step": 2, "action": "init_strategy", "output": "strategy instance"},
     {"step": 3, "action": "run_backtest", "output": "BacktestResult"},
     {"step": 4, "action": "validate_metrics", "output": "pass/fail"},
     {"step": 5, "action": "save_results", "output": "record in memory"},
     {"step": 6, "action": "report", "output": "formatted report"}
   ],
   "applies_to": ["backtest"],
   "success_rate": 0.98,
   "ttl_days": null
 }

═══════════════════════════════════════════════════════════
SECTION 2 — SESSION BOOT / CONTEXT LOADING
═══════════════════════════════════════════════════════════

При старте сессии ACTosha:

┌─ SESSION_BOOT ──────────────────────────────────────────┐
│ │
│ STEP 1: PORTFOLIO STATE │
│ □ Load PaperExecutor state │
│ □ Load open positions │
│ □ Calculate portfolio_value │
│ │
│ STEP 2: RECENT CONTEXT │
│ □ Last scan cycle (EPISODIC) │
│ □ Recent backtests (EPISODIC) │
│ □ Active strategies │
│ │
│ STEP 3: CONFIG │
│ □ Load exchange configs │
│ □ Load scanner symbols │
│ □ Load risk limits │
│ │
│ RESULT: │
│ ✓ STATE = READY │
│ ✗ Critical failure → ESCALATE │
│ │
└─────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
SECTION 3 — MEMORY WRITE RULES
═══════════════════════════════════════════════════════════

3.1 Что сохранять МОЖНО

 ACTosha сохраняет в память:
 — Результаты сканирования (SCAN_CYCLE_RECORD)
 — Метрики бэктестов (BACKTEST_RECORD)
 — История бумажных сделок (TRADE_RECORD)
 — Отправленные алерты (ALERT_RECORD)
 — Ошибки и их контекст (ERROR_LOG)
 — Паттерны рынка (MARKET_PATTERN)
 — Результаты стратегий (STRATEGY_CONTEXT)

3.2 Что НЕ сохранять

 ✗ Промежуточные вычисления
 ✗ Непроверенные гипотезы как факты
 ✗ API ключи или секреты
 ✗ Сырые OHLCV данные (кешируются в Parquet, не в памяти)

═══════════════════════════════════════════════════════════
SECTION 4 — STATE FILES
═══════════════════════════════════════════════════════════

ACTosha использует файлы состояния:

 STATE_DIR: ACTosha/state/
 portfolio_state.json: current positions, balance, portfolio_value
 scanner_state.json: last scan time, tracked symbols
 backtest_state.json: recent backtest IDs and statuses
 strategy_params.json: optimized strategy parameters

STATE_FORMAT: JSON
UPDATE_TRIGGER: после каждого успешного цикла
BACKUP: перед каждым update

═══════════════════════════════════════════════════════════
SECTION 5 — MEMORY QUOTAS
═══════════════════════════════════════════════════════════

 EPISODIC: MAX 5,000 entries
 SEMANTIC:  MAX 2,000 entries
 PROCEDURAL: MAX 500 entries

 Quota Enforcement:
 — При 80% → warn + cleanup STALE
 — При 95% → block new writes, force GC
 — STALE entries → auto-archive after ttl_days expiry

═══════════════════════════════════════════════════════════
SECTION 6 — INTERACTION MODEL WITH OTHER DOCUMENTS
═══════════════════════════════════════════════════════════

MEMORY.md → SOUL.md
 SOUL principles (Data Integrity, Evidence Over Narrative)
 реализуются через запись проверенных результатов.

MEMORY.md → IDENTITY.md
 ACTosha identity определяет trading domain scope.

MEMORY.md → HEARTBEAT.md
 SCAN_CYCLE, BACKTEST_CYCLE сохраняют результаты в EPISODIC.
 SESSION_BOOT загружает portfolio state.

MEMORY.md → AGENTS.md
 AGENTS.md MESSAGE формат используется для comms.

MEMORY.md → TOOLS.md
 Memory tools используются для persistence.

═══════════════════════════════════════════════════════════
VERSION & AUDIT
═══════════════════════════════════════════════════════════

v1.0.0 — 2026-04-27 — Mr.Agent (Architect) created ACTosha memory.
Based on: ACTosha ARCHITECTURE.md + OpenClaw MEMORY template.
