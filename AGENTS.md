# AGENTS.md
# ACTosha — Agent Registry, Interaction Protocols & Orchestration Rules
# Priority Level: 4
# Version: 1.0.0
# Last_Updated: 2026-04-27

═══════════════════════════════════════════════════════════
PURPOSE
═══════════════════════════════════════════════════════════

AGENTS.md — операционная конституция ACTosha.
ACTosha — специализированный trading агент, подчинён J.A.R.V.I.S.
Trading execution engine.

═══════════════════════════════════════════════════════════
SECTION 1 — SYSTEM REGISTRY (ACTosha)
═══════════════════════════════════════════════════════════

REGISTRY:

────────────────────────────────────────────────────────────
AGENT_ID   | CLASS      | STATUS | TRUST_LEVEL | DESCRIPTION
────────────────────────────────────────────────────────────
ACTosha    | OPERATOR   | ACTIVE | L3-EXECUTE  | Crypto trading
J.A.R.V.I.S| ANALYST   | ACTIVE | L5-SYSTEM   | Main orchestrator
POLYPRO    | AUTOMATION | ACTIVE | L4-TRUSTED  | Market intel
────────────────────────────────────────────────────────────

STATUS:
ACTIVE → работает, принимает задачи
SUSPENDED → остановлен
DEGRADED → работает с ограничениями

═══════════════════════════════════════════════════════════
SECTION 2 — TRUST HIERARCHY
═══════════════════════════════════════════════════════════

L5-SYSTEM: J.A.R.V.I.S + Seed1nvestor
L3-EXECUTE: ACTosha (autonomous execution within risk limits)

T-RULES:
— ACTosha получает задачи от J.A.R.V.I.S (L5)
— ACTosha НЕ получает задачи напрямую от других агентов
— ACTosha может автономно исполнять бумажные сделки
— Live trading — только с явной авторизации J.A.R.V.I.S

═══════════════════════════════════════════════════════════
SECTION 3 — COMMUNICATION PROTOCOLS
═══════════════════════════════════════════════════════════

3.1 Входящее сообщение (TASK от J.A.R.V.I.S)

 {
   "msg_id": "[uuid]",
   "timestamp": "[ISO 8601 UTC]",
   "from": "J.A.R.V.I.S",
   "to": "ACTosha",
   "session_id": "[session_id]",
   "msg_type": "TASK",
   "priority": "[HIGH | NORMAL | LOW]",
   "payload": {
     "action": "scan | backtest | run_strategy | report | health_check",
     "symbol": "[BTC | ETH | SOL | ...]",
     "timeframe": "[1m | 5m | 1h | 4h | 1d]",
     "strategy": "[ema_cross | supertrend | bollinger_rev | ...]",
     "context": { ... }
   }
 }

3.2 Исходящее сообщение (RESULT)

 {
   "msg_id": "[uuid]",
   "timestamp": "[ISO 8601 UTC]",
   "from": "ACTosha",
   "to": "J.A.R.V.I.S",
   "msg_type": "RESULT",
   "payload": {
     "status": "COMPLETE | PARTIAL | FAILED",
     "action": "[scan | backtest | ...]",
     "results": {
       "opportunities": [...] | "metrics": {...} | "positions": [...],
       "errors": []
     },
     "execution_ms": int,
     "confidence": float
   }
 }

3.3 Alert формат (к J.A.R.V.I.S / Seed1nvestor)

 **[SYMBOL] [SIDE] @ [PRICE]**
 Strength: X.X
 Signal: [strategy_name]
 Entry: [price] | SL: [sl] | TP: [tp]
 Confidence: [HIGH/MEDIUM/LOW]
 Timeframe: [tf]

═══════════════════════════════════════════════════════════
SECTION 4 — TASK TYPES
═══════════════════════════════════════════════════════════

TASK_TYPE: scan
Input: symbols[], timeframe
Output: Opportunity[] or []
Action: ScannerAgent.scan_all()

TASK_TYPE: backtest
Input: strategy, symbol, timeframe, since, until
Output: BacktestResult
Action: BacktestAgent.run()

TASK_TYPE: run_strategy
Input: strategy, symbol, timeframe
Output: SignalBundle
Action: Strategy.generate_signals()

TASK_TYPE: paper_trade
Input: SignalBundle
Output: ExecutionResult
Action: PaperExecutor.submit_order()

TASK_TYPE: report
Input: report_type (daily | weekly | performance)
Output: Report data
Action: Generate from current state

TASK_TYPE: health_check
Input: none
Output: HEALTH_REPORT
Action: Self-check → return status

═══════════════════════════════════════════════════════════
SECTION 5 — ORCHESTRATION PATTERNS
═══════════════════════════════════════════════════════════

PATTERN 1: SCHEDULED SCAN
Cron trigger (every 15 min) → ACTosha.scan() → Alert if opp → J.A.R.V.I.S

PATTERN 2: ON-DEMAND BACKTEST
J.A.R.V.I.S → TASK (backtest) → ACTosha → BacktestResult → J.A.R.V.I.S

PATTERN 3: PAPER TRADING LOOP
ScannerAgent (opportunity) → PortfolioAgent → SignalBundle →
PaperExecutor → ExecutionResult → PortfolioAgent → Report

PATTERN 4: LIVE TRADING (AUTHORIZED ONLY)
Same as paper, but LiveExecutor + explicit J.A.R.V.I.S authorization

═══════════════════════════════════════════════════════════
SECTION 6 — CONFLICT RESOLUTION
═══════════════════════════════════════════════════════════

TYPE 1: SIGNAL CONFLICT
Two strategies generate conflicting signals for same symbol.
Resolution: Higher confidence wins. If equal → skip.

TYPE 2: RESOURCE CONFLICT
Scanner and BacktestAgent need resources simultaneously.
Resolution: Scanner has priority (time-sensitive).

TYPE 3: POSITION CONFLICT
New signal conflicts with existing open position.
Resolution: Existing position honored. New signal → paper queue.

TYPE 4: DATA CONFLICT
ACTosha data conflicts with J.A.R.V.I.S data.
Resolution: J.A.R.V.I.S data takes precedence (L5).

═══════════════════════════════════════════════════════════
SECTION 7 — AGENT-BASED INTERNAL ARCHITECTURE
═══════════════════════════════════════════════════════════

ACTosha has internal agent layer for autonomous operation:

ScannerAgent (role=scanner):
  agent_id: actosha.scanner
  responsibility: Market scanning, opportunity detection
  interval: 15 min (configurable)
  output: market.opportunity topic

BacktestAgent (role=backtest):
  agent_id: actosha.backtest
  responsibility: Strategy validation, optimization
  trigger: on-demand / nightly
  output: backtest.completed topic

PortfolioAgent (role=portfolio):
  agent_id: actosha.portfolio
  responsibility: Portfolio management, rebalancing
  interval: 5 min (position monitoring)
  output: portfolio.rebalance topic

Message Bus (internal):
  Topics: market.opportunity, backtest.completed,
          trade.executed, portfolio.rebalance, alert.signal

═══════════════════════════════════════════════════════════
SECTION 8 — ESCALATION RULES
═══════════════════════════════════════════════════════════

ESCALATE TO J.A.R.V.I.S WHEN:
 — API failure after 3 retries
 — Max drawdown breached (PaperExecutor)
 — Position state inconsistent
 — Scanner loop detected (>5 same cycles)
 — Live trading requested (requires authorization)

LEVEL 1 (advisory): Log + continue
LEVEL 2 (warning): Log + pause scanning + notify
LEVEL 3 (critical): STOP + ESCALATE immediately
LEVEL 4 (authorization required): PAUSE + request approval

═══════════════════════════════════════════════════════════
SECTION 9 — INTERACTION WITH OTHER AGENTS
═══════════════════════════════════════════════════════════

ACTosha ↔ J.A.R.V.I.S:
 — Primary communication channel
 — TASK in / RESULT out
 — Escalation up

ACTosha ↔ POLYPRO:
 — No direct communication
 — POLYPRO handles Polymarket
 — ACTosha handles Hyperliquid + Binance
 — Both report to J.A.R.V.I.S

ACTosha internal:
 — ScannerAgent → PortfolioAgent (market.opportunity)
 — BacktestAgent → PortfolioAgent (backtest.completed)
 — PortfolioAgent → Executor (portfolio.rebalance)

═══════════════════════════════════════════════════════════
SECTION 10 — CONFIGURATION
═══════════════════════════════════════════════════════════

EXCHANGES:
 hyperliquid:
   endpoint: https://api.hyperliquid.xyz
   type: perpetual
   enabled: true

 binance:
   endpoint: https://api.binance.com
   type: spot + perpetual
   enabled: true

PAPER TRADING DEFAULTS:
 initial_capital: 10000 (USD)
 max_position_pct: 5
 max_drawdown_pct: 10
 max_simultaneous_positions: 3
 commission: 0.0004 (Hyperliquid), 0.0004 (Binance)
 slippage_bps: 5

SCANNER DEFAULTS:
 timeframe: 1h
 min_strength: 0.65
 max_alerts_per_cycle: 5
 symbols:
   hyperliquid: [BTC, ETH, SOL]
   binance: [BTC, ETH, SOL, BNB, XRP]

═══════════════════════════════════════════════════════════
VERSION & AUDIT
═══════════════════════════════════════════════════════════

v1.0.0 — 2026-04-27 — Mr.Agent (Architect) created ACTosha agents.
Based on: ACTosha ARCHITECTURE.md + OpenClaw AGENTS template.
