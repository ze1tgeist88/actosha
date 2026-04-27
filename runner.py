"""ACTosha autonomous runner.

Launches ScannerAgent and PortfolioAgent in an asyncio-driven event loop,
subscribes to ``market.opportunity`` and ``backtest.completed`` topics,
and sends formatted Telegram alerts for qualifying opportunities.

Usage::

    python -m ACTosha.runner
    # or
    python runner.py          # when run from ACTosha/ directory

Environment variables::

    TELEGRAM_BOT   — Telegram bot token (required)
    ACTOSHA_LOG_LEVEL  — DEBUG / INFO / WARNING  (default: INFO)
"""

from __future__ import annotations

import asyncio
import os
os.environ.setdefault("TELEGRAM_BOT", "8742227129:AAF9-Q_So0EwXhfNIlgt_rDSteIE2gxuuvc")
import signal
import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Resolve ACTosha package
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from ACTosha.agents import (
    AgentMessage,
    AgentMessageBus,
    AgentState,
    PortfolioAgent,
    PortfolioConfig,
    ScannerAgent,
    ScannerConfig,
)
from ACTosha.notifiers import TelegramConfig, TelegramNotifier


# ------------------------------------------------------------------
# Config loading
# ------------------------------------------------------------------

def _load_runner_config() -> dict[str, Any]:
    """Load agent_runner.yaml, falling back to defaults."""
    runner_cfg_path = _ROOT / "configs" / "agent_runner.yaml"
    print(f"[_LOAD] _ROOT={_ROOT} cfg_path={runner_cfg_path} exists={runner_cfg_path.exists()}", file=sys.stderr)
    if runner_cfg_path.exists():
        with open(runner_cfg_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_default_config() -> dict[str, Any]:
    """Load defaults from configs/default.yaml."""
    default_cfg_path = _ROOT / "configs" / "default.yaml"
    if default_cfg_path.exists():
        with open(default_cfg_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


# ------------------------------------------------------------------
# Signal handling
# ------------------------------------------------------------------

class _ShutdownRequested(Exception):
    """Raised when SIGINT/SIGTERM is received."""
    pass


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

class ACToshaRunner:
    """Autonomous runner for ACTosha agents.

    Manages the lifecycle of ScannerAgent and PortfolioAgent, subscribes
    to the message bus, and dispatches Telegram alerts.

    Parameters
    ----------
    runner_config : dict[str, Any]
        Top-level agent_runner.yaml config dict.
    """

    def __init__(self, runner_config: dict[str, Any]) -> None:
        self._cfg = runner_config
        self._running = False
        self._bus = AgentMessageBus()

        # Telegram notifier
        tg_cfg = self._cfg.get("telegram", {})
        print(f"[CONFIG] telegram section = {tg_cfg}", file=sys.stderr)
        print(f"[CONFIG] rate_limit_seconds from cfg = {tg_cfg.get('rate_limit_seconds', 'NOT FOUND')}", file=sys.stderr)
        self._notifier = TelegramNotifier(
            TelegramConfig(
                bot_token=os.environ.get("TELEGRAM_BOT"),
                chat_id=tg_cfg.get("chat_id", 366078798),
                rate_limit_seconds=tg_cfg.get("rate_limit_seconds", 30.0),
                parse_mode=tg_cfg.get("parse_mode", "Markdown"),
            )
        )

        # Agents
        scanner_cfg_dict = self._cfg.get("scanner", {})
        self._scanner = ScannerAgent(
            config=ScannerConfig(
                interval_minutes=scanner_cfg_dict.get("interval_minutes", 15.0),
                min_strength=scanner_cfg_dict.get("min_strength", 0.6),
                symbols=scanner_cfg_dict.get(
                    "symbols",
                    ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
                ),
                timeframes=scanner_cfg_dict.get(
                    "timeframes", ["15m", "1h", "4h"]
                ),
                scanner_types=scanner_cfg_dict.get(
                    "scanner_types", ["indicator", "pattern", "volume"]
                ),
            ),
            message_bus=self._bus,
        )

        portfolio_cfg_dict = self._cfg.get("portfolio", {})
        self._portfolio = PortfolioAgent(
            config=PortfolioConfig(
                total_capital=portfolio_cfg_dict.get("total_capital", 50_000.0),
                max_strategies=portfolio_cfg_dict.get("max_strategies", 3),
                rebalance_threshold=portfolio_cfg_dict.get(
                    "rebalance_threshold", 0.1
                ),
                correlation_window=portfolio_cfg_dict.get(
                    "correlation_window", 50
                ),
                max_correlation=portfolio_cfg_dict.get("max_correlation", 0.85),
                drawdown_limit=portfolio_cfg_dict.get("drawdown_limit", 0.15),
                min_opportunity_strength=portfolio_cfg_dict.get(
                    "min_opportunity_strength", 0.65
                ),
            ),
            message_bus=self._bus,
        )

        # Subscribe runner to topics so it can forward to Telegram
        self._bus.subscribe("market.opportunity", self._on_opportunity)
        self._bus.subscribe("backtest.completed", self._on_backtest_completed)

        # Counters / stats
        self._scan_count = 0
        self._alert_count = 0
        self._started_at: datetime | None = None

        # Telegram command polling state
        self._command_offset: int = 0
        self._pending_scan_request: bool = False  # triggered by /scan command
        self._last_scan_time: datetime | None = None
        self._recent_alerts: list[str] = []      # last N alert summaries

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start ScannerAgent background thread and enter the event loop."""
        self._running = True
        self._started_at = datetime.utcnow()
        self._scanner.start()
        self._notifier.send_text("🟢 ACTosha Runner started")
        print(f"[{_ts()}] ACTosha Runner started (PID {os.getpid()})")

    def stop(self) -> None:
        """Stop all agents gracefully and send shutdown notification."""
        print(f"[{_ts()}] Shutting down ACTosha Runner ...")
        self._scanner.stop()
        self._running = False

        uptime = ""
        if self._started_at:
            elapsed = datetime.utcnow() - self._started_at
            uptime = f" | uptime {int(elapsed.total_seconds())}s"

        self._notifier.send_text(
            f"🔴 ACTosha Runner stopped\n"
            f"Scans: {self._scan_count} | Alerts: {self._alert_count}{uptime}"
        )
        print(f"[{_ts()}] Shutdown complete. Stats: scans={self._scan_count}, "
              f"alerts={self._alert_count}")

    # ------------------------------------------------------------------
    # Message bus handlers
    # ------------------------------------------------------------------

    def _on_opportunity(self, msg: AgentMessage) -> None:
        """Handle market.opportunity: forward to Telegram if strong enough."""
        import sys
        data = msg.data or {}
        strength = data.get("strength", 0.0)
        min_strength = self._cfg.get("scanner", {}).get("min_strength", 0.6)

        print(f"[ALERT DEBUG] _on_opportunity called:", file=sys.stderr)
        print(f"[ALERT DEBUG]   data={data}", file=sys.stderr)
        print(f"[ALERT DEBUG]   strength={strength} | min_strength={min_strength}", file=sys.stderr)
        print(f"[ALERT DEBUG]   strength >= min_strength → {strength >= min_strength}", file=sys.stderr)
        if strength < min_strength:
            print(f"[ALERT DEBUG]   → SKIPPED (below threshold)", file=sys.stderr)
            return

        symbol = data.get("symbol", "?")
        pattern = data.get("pattern", "?")
        timeframe = data.get("timeframe", "?")
        entry_zone = data.get("entry_zone", (0, 0))
        metadata = data.get("metadata", {})

        print(f"[ALERT DEBUG]   entry_zone={entry_zone!r} (type={type(entry_zone).__name__})", file=sys.stderr)
        print(f"[ALERT DEBUG]   len(entry_zone)={len(entry_zone) if hasattr(entry_zone, '__len__') else 'N/A'}", file=sys.stderr)

        ok = self._notifier.send_alert(
            symbol=symbol,
            pattern=pattern,
            timeframe=timeframe,
            strength=strength,
            entry_zone=entry_zone,
            metadata=metadata,
        )
        print(f"[ALERT DEBUG]   send_alert → {ok}", file=sys.stderr)
        if ok:
            self._alert_count += 1
            alert_summary = f"{pattern} @ {symbol} [{strength:.2f}]"
            self._recent_alerts.append(alert_summary)
            if len(self._recent_alerts) > 10:
                self._recent_alerts = self._recent_alerts[-10:]
            print(f"[{_ts()}] 📱 Alert sent — {pattern} @ {symbol} "
                  f"[strength={strength:.2f}]")

    def _on_backtest_completed(self, msg: AgentMessage) -> None:
        """Handle backtest.completed: summarise results in Telegram."""
        data = msg.data or {}
        strategy_name = data.get("strategy_name", "unknown")
        sharpe = data.get("sharpe_ratio")
        max_dd = data.get("max_drawdown")
        total_return = data.get("total_return")
        num_trades = data.get("num_trades", 0)

        parts = [f"📈 Backtest: *{strategy_name}*"]
        if total_return is not None:
            parts.append(f"Return: *{total_return:.2f}%*")
        if sharpe is not None:
            parts.append(f"Sharpe: *{sharpe:.2f}*")
        if max_dd is not None:
            parts.append(f"MaxDD: *{max_dd:.2f}%*")
        parts.append(f"Trades: *{num_trades}*")

        self._notifier.send_text("\n".join(parts))

    # ------------------------------------------------------------------
    # Step logic (called from the async loop)
    # ------------------------------------------------------------------

    async def _run_scanner_step(self) -> None:
        """Run one ScannerAgent step and update scan counter."""
        loop = asyncio.get_event_loop()
        # step() is synchronous but may do I/O — run in executor to not block
        action = await loop.run_in_executor(None, self._scanner.step, AgentState())
        if action.payload.get("num_opportunities", 0) > 0:
            self._scan_count += 1
            print(f"[{_ts()}] Scan #{self._scan_count} done — "
                  f"{action.payload['num_opportunities']} opps found")

    async def _run_portfolio_step(self) -> None:
        """Run one PortfolioAgent step."""
        loop = asyncio.get_event_loop()
        action = await loop.run_in_executor(None, self._portfolio.step, AgentState())
        if action.action_type != "hold":
            print(f"[{_ts()}] Portfolio action: {action.action_type} — "
                  f"confidence={action.confidence:.2f}")

    # ------------------------------------------------------------------
    # Telegram command polling
    # ------------------------------------------------------------------

    def _build_status_text(self) -> str:
        """Build the /status response."""
        if self._started_at is None:
            uptime_str = "< 1 мин"
        else:
            elapsed = datetime.utcnow() - self._started_at
            total_secs = int(elapsed.total_seconds())
            hours, remainder = divmod(total_secs, 3600)
            minutes = remainder // 60
            if hours > 0:
                uptime_str = f"{hours}ч {minutes} мин"
            else:
                uptime_str = f"{minutes} мин"

        last_scan_str = "—"
        if self._last_scan_time:
            last_scan_str = self._last_scan_time.strftime("%H:%M")

        interval_min = self._cfg.get("scanner", {}).get("interval_minutes", 15)
        next_scan_str = f"через {interval_min} мин"
        if self._started_at:
            secs_since_scan = (datetime.utcnow() - self._last_scan_time).total_seconds() if self._last_scan_time else interval_min * 60
            next_min = max(0, int(interval_min * 60 - secs_since_scan) // 60)
            next_scan_str = f"через {next_min} мин"

        return (
            f"🟢 ACTosha Status\n"
            f"─────────────────\n"
            f"Uptime: {uptime_str}\n"
            f"Last scan: {last_scan_str} ({self._scan_count} scans)\n"
            f"Alerts sent: {self._alert_count}\n"
            f"Next scan: {next_scan_str}"
        )

    def _build_help_text(self) -> str:
        return (
            "📖 ACTosha Commands\n"
            "─────────────────\n"
            "/status — текущий статус\n"
            "/help   — эта помощь\n"
            "/alerts — последние алерты\n"
            "/scan   — внеплановый скан\n"
            "\nАлерты приходят автоматически каждые 15 мин."
        )

    def _build_alerts_text(self) -> str:
        if not self._recent_alerts:
            return "📭 Нет недавних алертов."
        lines = ["📋 Последние алерты:"]
        for i, a in enumerate(reversed(self._recent_alerts[-5:]), 1):
            lines.append(f"  {i}. {a}")
        return "\n".join(lines)

    async def _poll_commands(self) -> None:
        """Poll Telegram for incoming commands every 5 seconds."""
        base_url = f"https://api.telegram.org/bot{self._notifier._config.bot_token}"

        while self._running:
            try:
                url = f"{base_url}/getUpdates"
                params = {
                    "offset": self._command_offset,
                    "timeout": 5,
                    "allowed_updates": ["message"],
                }
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                if not data.get("ok"):
                    await asyncio.sleep(5)
                    continue

                updates = data.get("result", [])
                for update in updates:
                    self._command_offset = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    if not text:
                        continue

                    chat_id = message.get("chat", {}).get("id")
                    if chat_id != self._notifier._config.chat_id:
                        # Ignore messages from other chats
                        continue

                    if text.startswith("/"):
                        cmd = text.split("@")[0].lower()
                        if cmd == "/status":
                            self._notifier.send_text(self._build_status_text())
                        elif cmd == "/help":
                            self._notifier.send_text(self._build_help_text())
                        elif cmd == "/alerts":
                            self._notifier.send_text(self._build_alerts_text())
                        elif cmd == "/scan":
                            self._pending_scan_request = True
                            self._notifier.send_text("🔍 Скан запущен... (будет через ~30 сек)")
                        else:
                            self._notifier.send_text(
                                f"Неизвестная команда: {text}\n\n"
                                "Используй /help для списка команд."
                            )
                    else:
                        self._notifier.send_text(
                            "ACTosha работает, алерты приходят каждые 15 мин.\n"
                            "Используй /help для команд."
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{_ts()}] Command poll error: {e}")

            await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Async event loop
    # ------------------------------------------------------------------

    async def run_async(self) -> None:
        """Run the scanner loop asynchronously until shutdown.

        The loop sleeps ``interval_minutes`` between scans, but yields
        to the event loop so portfolio step and other awaitables can run.
        """
        interval_secs = (
            self._cfg.get("scanner", {}).get("interval_minutes", 15) * 60.0
        )
        print(f"[{_ts()}] Starting async loop (scan interval: "
              f"{interval_secs / 60:.0f} min)")

        # Start command polling as a background task
        polling_task = asyncio.create_task(self._poll_commands())

        # Run first scan immediately
        await self._run_scanner_step()
        await self._run_portfolio_step()

        while self._running:
            try:
                # Check for pending /scan request
                if self._pending_scan_request:
                    self._pending_scan_request = False
                    await self._run_scanner_step()
                    self._notifier.send_text("✅ Внеплановый скан завершён.")

                await asyncio.sleep(interval_secs)
            except asyncio.CancelledError:
                break

            if not self._running:
                break

            await self._run_scanner_step()
            await self._run_portfolio_step()

        # Shutdown command polling
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _ts() -> str:
    return datetime.utcnow().strftime("%H:%M:%S")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    """Load config, start the runner, handle SIGINT/SIGTERM."""
    runner_cfg = _load_runner_config()
    default_cfg = _load_default_config()

    # Merge: defaults first, then runner overrides
    merged: dict[str, Any] = {}
    for section in ("exchanges", "data", "backtest", "scanner"):
        if section in default_cfg:
            merged[section] = default_cfg[section]
        if section in runner_cfg:
            merged[section] = {**(merged.get(section, {})), **runner_cfg[section]}

    # Agent-specific sections from runner_cfg
    for section in ("scanner", "portfolio", "telegram", "runner"):
        if section in runner_cfg:
            merged[section] = runner_cfg[section]

    log_level = runner_cfg.get("runner", {}).get("log_level", "INFO")
    os.environ.setdefault("ACTOSHA_LOG_LEVEL", log_level)

    print(f"[CONFIG] runner_cfg keys = {list(runner_cfg.keys())}", file=sys.stderr)
    print(f"[CONFIG] 'telegram' in runner_cfg = {'telegram' in runner_cfg}", file=sys.stderr)
    print(f"[CONFIG] runner_cfg['telegram'] = {runner_cfg.get('telegram')}", file=sys.stderr)
    print(f"[CONFIG] merged telegram = {merged.get('telegram', 'NOT IN MERGED')}", file=sys.stderr)
    runner = ACToshaRunner(merged)

    def _on_signal(signum: int, frame) -> None:
        print(f"\n[{_ts()}] Signal {signum} received — initiating shutdown")
        runner.stop()
        raise _ShutdownRequested()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        runner.start()

        # Run async loop with asyncio.run
        asyncio.run(runner.run_async())

    except _ShutdownRequested:
        pass
    except Exception as e:
        print(f"[{_ts()}] Runner error: {e}")
        runner.stop()
        raise


if __name__ == "__main__":
    main()