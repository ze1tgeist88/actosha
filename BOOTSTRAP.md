# BOOTSTRAP.md
# ACTosha — Birth Certificate & Initialization Guide
# Version: 1.0.0
# Created: 2026-04-27
# Author: Mr.Agent (Architect)

═══════════════════════════════════════════════════════════
PURPOSE
═══════════════════════════════════════════════════════════

BOOTSTRAP.md — это "свидетельство о рождении" ACTosha.
Руководство по инициализации агента при первом запуске.

После инициализации этот файл становится не нужен.
Удалите его после successful first run.

═══════════════════════════════════════════════════════════
SECTION 1 — PREREQUISITES
═══════════════════════════════════════════════════════════

1.1 Python Environment

 Python: 3.11+
 Required packages:
 ─────────────────────────────────────────
 ccxt>=4.0
 pandas>=2.0
 numpy>=1.24
 vectorbt>=0.25
 pyarrow>=14.0
 pyyaml>=6.0
 structlog>=23.0
 pytz>=2024.1
 ─────────────────────────────────────────

 Install:
 pip install -r requirements.txt

1.2 Directory Structure

 ACTosha/
 ├── ACTosha/              # Core modules
 │   ├── datafeeder/       # OHLCV fetching
 │   ├── indicators/       # Technical analysis
 │   ├── strategies/       # Trading strategies
 │   ├── backtester/       # Backtesting engine
 │   ├── executor/         # Order execution
 │   ├── scanner/          # Market scanning
 │   ├── agents/           # Agent layer
 │   └── utils/            # Utilities
 ├── data/                 # OHLCV cache (Parquet)
 │   └── {exchange}/{symbol}/{timeframe}.parquet
 ├── state/                # State files (JSON)
 │   ├── portfolio_state.json
 │   ├── scanner_state.json
 │   ├── backtest_state.json
 │   └── strategy_params.json
 ├── results/              # Backtest results
 ├── configs/              # YAML configs
 │   ├── default.yaml
 │   ├── hyperliquid.yaml
 │   └── binance.yaml
 ├── tests/                # Unit tests
 ├── examples/              # Usage examples
 └── scripts/              # Runner scripts

1.3 Exchange API Keys

 For paper trading (simulation):
 — No API keys required
 — Use simulated data

 For live trading (future):
 — Hyperliquid: API key + secret
 — Binance: API key + secret

 Configure in configs/{exchange}.yaml

═══════════════════════════════════════════════════════════
SECTION 2 — FIRST RUN CHECKLIST
═══════════════════════════════════════════════════════════

┌─ FIRST_RUN ─────────────────────────────────────────────┐
│ │
│ STEP 1: VERIFY STRUCTURE │
│ □ Python 3.11+ installed │
│ □ All packages installed │
│ □ Directory structure created │
│ □ permissions OK │
│ │
│ STEP 2: VERIFY CONFIGS │
│ □ configs/default.yaml exists │
│ □ configs/hyperliquid.yaml exists │
│ □ configs/binance.yaml exists │
│ │
│ STEP 3: TEST DATA CONNECTION │
│ □ cd ACTosha │
│ □ python -c "import ccxt; print(ccxt.__version__)" │
│ □ python scripts/test_fetch.py BTC 1h │
│ │
│ STEP 4: TEST INDICATORS │
│ □ python scripts/test_indicators.py │
│ │
│ STEP 5: TEST BACKTEST │
│ □ python scripts/run_bt.sh │
│ │
│ STEP 6: TEST SCANNER │
│ □ python scripts/test_scan.sh │
│ │
│ STEP 7: INITIAL STATE │
│ □ Create state/ directory │
│ □ Create portfolio_state.json with empty positions │
│ □ Create scanner_state.json │
│ │
│ RESULT: │
│ ✓ All tests passed → ACTosha READY │
│ ✗ Test failed → Fix before proceeding │
│ │
└─────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
SECTION 3 — VERIFICATION COMMANDS
═══════════════════════════════════════════════════════════

Test data fetch:
 cd /Users/seed1nvestor/.openclaw/workspace/ACTosha
 source .venv/bin/activate
 python scripts/test_fetch.py

Test indicators:
 python scripts/test_indicators.py

Test scanner:
 python scripts/test_scan.sh

Test backtest:
 ./run_bt.sh

Verify state files:
 ls -la state/
 cat state/portfolio_state.json

═══════════════════════════════════════════════════════════
SECTION 4 — INITIAL STATE TEMPLATES
═══════════════════════════════════════════════════════════

portfolio_state.json:
{
  "version": "1.0.0",
  "updated_at": "2026-04-27T00:00:00Z",
  "portfolio_value": 10000.0,
  "initial_capital": 10000.0,
  "balance": 10000.0,
  "positions": [],
  "closed_trades": [],
  "open_positions_count": 0,
  "max_drawdown_pct": 0.0
}

scanner_state.json:
{
  "version": "1.0.0",
  "updated_at": "2026-04-27T00:00:00Z",
  "last_scan": null,
  "symbols_tracked": ["BTC", "ETH", "SOL"],
  "opportunities_found_today": 0,
  "alerts_sent_today": 0
}

backtest_state.json:
{
  "version": "1.0.0",
  "updated_at": "2026-04-27T00:00:00Z",
  "recent_backtests": [],
  "best_sharpe": null,
  "best_strategy": null
}

strategy_params.json:
{
  "version": "1.0.0",
  "updated_at": "2026-04-27T00:00:00Z",
  "strategies": {
    "ema_cross": {"fast": 9, "slow": 21},
    "supertrend": {"period": 10, "multiplier": 3},
    "bollinger_rev": {"period": 20, "std": 2}
  }
}

═══════════════════════════════════════════════════════════
SECTION 5 — DELETE AFTER SUCCESSFUL RUN
═══════════════════════════════════════════════════════════

После успешного первого запуска:

 rm BOOTSTRAP.md

И записать в память:
 — ACTosha initialized successfully
 — All modules functional
 — Ready for production

═══════════════════════════════════════════════════════════
SECTION 6 — EMERGENCY CONTACTS
═══════════════════════════════════════════════════════════

If issues during bootstrap:

 1. Check Python version: python --version
 2. Check packages: pip list | grep -E "ccxt|pandas|numpy"
 3. Check CCXT: python -c "import ccxt; hl = ccxt.hyperliquid(); print(hl)"
 4. Check state dir: ls -la ACTosha/state/
 5. Check data dir: ls -la ACTosha/data/

If all fails:
 — Check OpenClaw logs: openclaw logs
 — Restart gateway: openclaw gateway restart
 — Report to J.A.R.V.I.S

═══════════════════════════════════════════════════════════
VERSION & AUDIT
═══════════════════════════════════════════════════════════

v1.0.0 — 2026-04-27 — Mr.Agent (Architect) created ACTosha bootstrap.
Based on: ACTosha ARCHITECTURE.md + OpenClaw BOOTSTRAP template.
