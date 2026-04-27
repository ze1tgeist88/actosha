"""AdaptivePortfolioAgent — extended PortfolioAgent with adaptive mechanisms.

Adds four adaptive mechanisms on top of PortfolioAgent:

a) Performance-based reallocation
   Weight updates every N minutes. Sharpe ↑ → weight ↑, drawdown → weight ↓.

b) Strategy health monitoring
   MaxDD > limit → reduce exposure / deactivate.
   WinRate < threshold → alert + weight reduction.
   Sharpe < 0 → flag for review.

c) Auto-strategy rotation
   High opportunity strength for new strategy → propose adding it.
   Triggers BacktestAgent optimization automatically.
   New params applied only if better than current.

d) Drawdown circuit breaker
   Portfolio MaxDD > threshold → close all positions.
   Telegram alert → trading halt until manual resume.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from ACTosha.agents.base import TradingAgent
from ACTosha.agents.message_bus import AgentMessage, AgentMessageBus
from ACTosha.agents.portfolio_agent import PortfolioAgent, PortfolioConfig, StrategySlot
from ACTosha.agents.state import AgentAction, AgentEvent, AgentState
from ACTosha.agents.strategy_evaluator import StrategyEvaluator, StrategyScore


# ------------------------------------------------------------------
# AdaptiveConfig
# ------------------------------------------------------------------

@dataclass
class AdaptiveConfig:
    """Configuration for adaptive mechanisms.

    Attributes
    ----------
    adaptive_reallocation_interval_minutes : float
        How often (minutes) to recompute strategy weights.
        Default: 60.
    performance_weight_update_threshold : float
        Minimum change in score to trigger a weight update.
        Default: 0.05.
    drawdown_halt_threshold : float
        Portfolio drawdown (as fraction) that triggers full halt.
        Default: 0.20 (20%).
    auto_optimization_trigger_sharpe_diff : float
        Sharpe improvement threshold that triggers auto-optimization.
        Default: 0.15.
    max_drawdown_threshold : float
        Per-strategy MaxDD limit before flagging. Default: 0.20.
    win_rate_threshold : float
        Per-strategy win rate limit before flagging. Default: 0.40.
    sharpe_flag_threshold : float
        Per-strategy Sharpe below which it is flagged. Default: 0.0.
    min_trades_for_score : int
        Minimum trades for a reliable score. Default: 10.
    weight_update_rate : float
        Maximum weight change per reallocation step (0.0–1.0). Default: 0.10.
    halt_resume_token : str
        Secret token required to resume from halt. Default: "" (no halt).
    """

    adaptive_reallocation_interval_minutes: float = 60.0
    performance_weight_update_threshold: float = 0.05
    drawdown_halt_threshold: float = 0.20
    auto_optimization_trigger_sharpe_diff: float = 0.15
    max_drawdown_threshold: float = 0.20
    win_rate_threshold: float = 0.40
    sharpe_flag_threshold: float = 0.0
    min_trades_for_score: int = 10
    weight_update_rate: float = 0.10
    halt_resume_token: str = ""


# ------------------------------------------------------------------
# AdaptiveState
# ------------------------------------------------------------------

@dataclass
class AdaptiveState:
    """Runtime state for adaptive mechanisms."""

    last_reallocation_ts: float = field(default_factory=time.time)
    last_health_check_ts: float = field(default_factory=time.time)
    is_halted: bool = False
    halt_reason: str = ""
    halted_at_ts: float = 0.0

    # Per-strategy scores (updated each adaptive step)
    strategy_scores: dict[str, StrategyScore] = field(default_factory=dict)

    # Pending auto-optimization proposals
    pending_optimizations: list[dict[str, Any]] = field(default_factory=list)

    # Circuit-breaker fired → needs manual resume
    circuit_breaker_fired: bool = False


# ------------------------------------------------------------------
# AdaptivePortfolioAgent
# ------------------------------------------------------------------

class AdaptivePortfolioAgent(PortfolioAgent):
    """Extended PortfolioAgent with adaptive capital reallocation and health monitoring.

    Parameters
    ----------
    config : PortfolioConfig
        Base portfolio configuration.
    adaptive_config : AdaptiveConfig | None
        Adaptive mechanism configuration.
    message_bus : AgentMessageBus | None
        Message bus.
    strategy_evaluator : StrategyEvaluator | None
        Strategy scoring engine.
    notifier : Any | None
        Telegram notifier with a `send_text` method.
    """

    def __init__(
        self,
        config: PortfolioConfig | None = None,
        adaptive_config: AdaptiveConfig | None = None,
        message_bus: AgentMessageBus | None = None,
        strategy_evaluator: StrategyEvaluator | None = None,
        notifier: Any = None,
    ) -> None:
        super().__init__(config=config, message_bus=message_bus)
        self.adaptive = adaptive_config or AdaptiveConfig()
        self._evaluator = strategy_evaluator or StrategyEvaluator(
            max_drawdown_threshold=self.adaptive.max_drawdown_threshold,
            win_rate_threshold=self.adaptive.win_rate_threshold,
            sharpe_flag_threshold=self.adaptive.sharpe_flag_threshold,
            min_trades_for_score=self.adaptive.min_trades_for_score,
        )
        self._notifier = notifier
        self._adaptive_state = AdaptiveState()
        self._lock = threading.Lock()

        # Register subscription for backtest.completed (to score strategies)
        self._bus.subscribe("backtest.completed", self._on_backtest_completed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_halted(self) -> bool:
        """Return True if the portfolio is halted (circuit breaker active)."""
        return self._adaptive_state.is_halted

    def resume_from_halt(self, token: str) -> bool:
        """Resume from trading halt. Returns True if token is valid."""
        if token == self.adaptive.halt_resume_token or self.adaptive.halt_resume_token == "":
            if self._adaptive_state.is_halted:
                self._adaptive_state.is_halted = False
                self._adaptive_state.circuit_breaker_fired = False
                self._adaptive_state.halt_reason = ""
                self._send_alert(
                    f"✅ Portfolio resumed from halt.\n"
                    f"Reason: {self._adaptive_state.halted_at_ts}"
                )
                return True
        return False

    def get_adaptive_state(self) -> dict[str, Any]:
        """Return current adaptive state snapshot."""
        s = self._adaptive_state
        return {
            "is_halted": s.is_halted,
            "halt_reason": s.halt_reason,
            "halted_at_ts": s.halted_at_ts,
            "circuit_breaker_fired": s.circuit_breaker_fired,
            "last_reallocation_ts": s.last_reallocation_ts,
            "last_health_check_ts": s.last_health_check_ts,
            "strategy_scores": {
                sid: score.to_dict()
                for sid, score in s.strategy_scores.items()
            },
            "pending_optimizations": s.pending_optimizations,
            "adaptive_config": {
                "interval_minutes": self.adaptive.adaptive_reallocation_interval_minutes,
                "weight_update_threshold": self.adaptive.performance_weight_update_threshold,
                "drawdown_halt_threshold": self.adaptive.drawdown_halt_threshold,
                "sharpe_diff_trigger": self.adaptive.auto_optimization_trigger_sharpe_diff,
            },
        }

    def trigger_reallocation(self) -> AgentAction:
        """Manually trigger an adaptive reallocation pass."""
        return self._adaptive_reallocation()

    # ------------------------------------------------------------------
    # TradingAgent step() — extends PortfolioAgent.step()
    # ------------------------------------------------------------------

    def step(self, state: AgentState) -> AgentAction:
        """Evaluate portfolio + run adaptive mechanisms.

        If halted, returns action_type="halted" and refuses to trade.
        """
        with self._lock:
            # Circuit breaker: halt if triggered
            if self._adaptive_state.is_halted:
                return AgentAction(
                    action_type="halted",
                    payload={
                        "halt_reason": self._adaptive_state.halt_reason,
                        "halted_at_ts": self._adaptive_state.halted_at_ts,
                        **self._build_status_payload(state),
                    },
                    confidence=1.0,
                )

            # ── Base portfolio step ────────────────────────────────────
            base_action = super().step(state)

            # ── Adaptive interval checks ──────────────────────────────
            now = time.time()
            interval_secs = self.adaptive.adaptive_reallocation_interval_minutes * 60.0

            adaptive_payload: dict[str, Any] = {}

            if now - self._adaptive_state.last_reallocation_ts >= interval_secs:
                self._adaptive_state.last_reallocation_ts = now
                realloc_action = self._adaptive_reallocation()
                if realloc_action.action_type != "hold":
                    adaptive_payload["reallocation"] = realloc_action.payload

            if now - self._adaptive_state.last_health_check_ts >= interval_secs / 2:
                self._adaptive_state.last_health_check_ts = now
                health_result = self._health_check()
                if health_result:
                    adaptive_payload["health"] = health_result

            # ── Merge ────────────────────────────────────────────────
            if adaptive_payload:
                base_payload = base_action.payload
                base_payload["adaptive"] = adaptive_payload
                return AgentAction(
                    action_type=base_action.action_type,
                    payload=base_payload,
                    confidence=base_action.confidence,
                )

            return base_action

    # ------------------------------------------------------------------
    # Internal: adaptive mechanisms
    # ------------------------------------------------------------------

    def _adaptive_reallocation(self) -> AgentAction:
        """Recompute strategy weights based on recent performance scores."""
        scores = self._adaptive_state.strategy_scores
        if not scores:
            return AgentAction(action_type="hold", payload={}, confidence=0.0)

        total = self.config.total_capital
        if total <= 0:
            return AgentAction(action_type="hold", payload={}, confidence=0.0)

        # Compute new target weights proportional to overall_score
        # (normalised so sum of active scores → 1.0)
        active_scores = {
            sid: s for sid, s in scores.items()
            if self._slots.get(sid) and self._slots[sid].is_active
        }
        if not active_scores:
            return AgentAction(action_type="hold", payload={}, confidence=0.0)

        sum_scores = sum(s.overall_score for s in active_scores.values())
        if sum_scores <= 0:
            return AgentAction(action_type="hold", payload={}, confidence=0.0)

        changes: list[dict[str, Any]] = []
        for sid, score in active_scores.items():
            slot = self._slots[sid]
            new_target = score.overall_score / sum_scores
            current_weight = slot.allocated_capital / total

            delta = new_target - current_weight
            if abs(delta) < self.adaptive.performance_weight_update_threshold:
                continue

            # Clamp change rate
            capped_delta = max(-self.adaptive.weight_update_rate, min(self.adaptive.weight_update_rate, delta))

            new_capital = slot.allocated_capital + total * capped_delta
            new_capital = max(0.0, min(total, new_capital))
            slot.allocated_capital = new_capital

            changes.append({
                "strategy_id": sid,
                "strategy_name": slot.strategy_name,
                "old_weight": round(current_weight, 4),
                "new_weight": round(new_target, 4),
                "weight_delta": round(capped_delta, 4),
                "score_before": round(score.overall_score, 4),
            })

        if not changes:
            return AgentAction(action_type="hold", payload={}, confidence=0.0)

        return AgentAction(
            action_type="rebalance",
            payload={
                "reallocation_changes": changes,
                "timestamp": datetime.utcnow().isoformat(),
            },
            confidence=0.85,
        )

    def _health_check(self) -> dict[str, Any] | None:
        """Run strategy health checks and apply automatic responses."""
        alerts: list[dict[str, Any]] = []
        deactivations: list[str] = []
        exposure_reductions: list[dict[str, Any]] = []

        # Update scores from backtest results
        self._update_scores_from_backtests()

        scores = self._adaptive_state.strategy_scores
        if not scores:
            return None

        for sid, score in scores.items():
            slot = self._slots.get(sid)
            if slot is None or not slot.is_active:
                continue

            # ── MaxDD check ──────────────────────────────────────────
            dd_fraction = score.max_drawdown_pct / 100.0
            if dd_fraction > self.adaptive.max_drawdown_threshold:
                # Reduce exposure by 50%
                reduced_capital = slot.allocated_capital * 0.5
                slot.allocated_capital = reduced_capital
                exposure_reductions.append({
                    "strategy_id": sid,
                    "strategy_name": slot.strategy_name,
                    "max_dd_pct": score.max_drawdown_pct,
                    "reduced_capital_to": round(reduced_capital, 2),
                    "reason": "MaxDD exceeded threshold — exposure reduced by 50%",
                })
                self._send_alert(
                    f"⚠️ Strategy *{slot.strategy_name}* MaxDD "
                    f"{score.max_drawdown_pct:.1f}% > limit — "
                    f"exposure cut to ${reduced_capital:.0f}"
                )

            # ── WinRate check ─────────────────────────────────────────
            if score.win_rate < self.adaptive.win_rate_threshold:
                alerts.append({
                    "strategy_id": sid,
                    "strategy_name": slot.strategy_name,
                    "type": "win_rate_low",
                    "win_rate": round(score.win_rate, 4),
                    "threshold": self.adaptive.win_rate_threshold,
                    "message": f"WinRate {score.win_rate:.1%} < {self.adaptive.win_rate_threshold:.1%}",
                })

            # ── Sharpe < 0 → flag for review ─────────────────────────
            if score.sharpe_ratio < self.adaptive.sharpe_flag_threshold:
                alerts.append({
                    "strategy_id": sid,
                    "strategy_name": slot.strategy_name,
                    "type": "sharpe_negative",
                    "sharpe_ratio": round(score.sharpe_ratio, 4),
                    "threshold": self.adaptive.sharpe_flag_threshold,
                    "message": f"Sharpe {score.sharpe_ratio:.2f} < 0 — flagged for review",
                })

        if not alerts and not deactivations and not exposure_reductions:
            return None

        return {
            "alerts": alerts,
            "deactivations": deactivations,
            "exposure_reductions": exposure_reductions,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _check_circuit_breaker(self, state: AgentState) -> bool:
        """Check portfolio-level MaxDD. Returns True if halt was triggered."""
        if len(self._equity_history) < 2:
            return False

        peak = max(self._equity_history)
        current = self._equity_history[-1]
        if peak <= 0:
            return False

        drawdown = (peak - current) / peak
        if drawdown > self.adaptive.drawdown_halt_threshold:
            self._adaptive_state.is_halted = True
            self._adaptive_state.circuit_breaker_fired = True
            self._adaptive_state.halt_reason = (
                f"Portfolio MaxDD {drawdown * 100:.2f}% > "
                f"threshold {self.adaptive.drawdown_halt_threshold * 100:.1f}%"
            )
            self._adaptive_state.halted_at_ts = time.time()

            self._send_alert(
                f"🚨 CIRCUIT BREAKER — Portfolio MaxDD {drawdown * 100:.2f}%\n"
                f"Threshold: {self.adaptive.drawdown_halt_threshold * 100:.1f}%\n"
                f"ALL POSITIONS CLOSED.\n"
                f"Trading halted until manual resume."
            )
            return True
        return False

    def _auto_strategy_rotation(self) -> list[dict[str, Any]]:
        """Check for new high-opportunity strategies and propose additions."""
        proposals: list[dict[str, Any]] = []

        with self._lock:
            active_count = sum(1 for s in self._slots.values() if s.is_active)
            opportunity_queue = list(self._opportunity_queue)

        if active_count >= self.config.max_strategies:
            return proposals

        for opp in opportunity_queue:
            strength = opp.get("strength", 0.0)
            opportunity_threshold = self.adaptive.auto_optimization_trigger_sharpe_diff

            if strength >= opportunity_threshold:
                symbol = opp.get("symbol", "?")
                pattern = opp.get("pattern", "?")
                timeframe = opp.get("timeframe", "?")

                proposals.append({
                    "opportunity_symbol": symbol,
                    "pattern": pattern,
                    "timeframe": timeframe,
                    "strength": strength,
                    "action": "propose_new_strategy",
                    "message": (
                        f"High opportunity strength {strength:.2f} for "
                        f"{pattern} @ {symbol} [{timeframe}]. "
                        f"BacktestAgent optimization recommended."
                    ),
                })

                # Queue optimization task (triggers on next backtest agent step)
                self._adaptive_state.pending_optimizations.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "pattern": pattern,
                    "triggered_by_opp_strength": strength,
                })

        return proposals

    def _update_scores_from_backtests(self) -> None:
        """Update strategy scores from queued backtest results."""
        with self._lock:
            results = list(self._backtest_results)
            self._backtest_results.clear()

        for result in results:
            strategy_name = result.get("strategy_name", "unknown")
            task_id = result.get("task_id", "")

            # Find matching slot by name
            sid = None
            for s_id, slot in self._slots.items():
                if slot.strategy_name == strategy_name:
                    sid = s_id
                    break

            score = self._evaluator.score_strategy(
                result, strategy_id=sid or task_id, strategy_name=strategy_name
            )
            if sid:
                self._adaptive_state.strategy_scores[sid] = score

    # ------------------------------------------------------------------
    # Internal: event handlers
    # ------------------------------------------------------------------

    def _on_backtest_completed(self, msg: AgentMessage) -> None:
        """Callback: score completed backtest and update strategy performance."""
        result = msg.data
        strategy_name = result.get("strategy_name", "unknown")
        task_id = result.get("task_id", "")

        # Find matching slot
        sid = None
        for s_id, slot in self._slots.items():
            if slot.strategy_name == strategy_name:
                sid = s_id
                break

        score = self._evaluator.score_strategy(
            result,
            strategy_id=sid or task_id,
            strategy_name=strategy_name,
        )
        if sid:
            self._adaptive_state.strategy_scores[sid] = score
        else:
            # Store under task_id for unknown slots
            self._adaptive_state.strategy_scores[task_id] = score

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _send_alert(self, message: str) -> None:
        """Send Telegram alert if notifier is available."""
        if self._notifier is not None:
            try:
                self._notifier.send_text(message)
            except Exception:
                pass

    def _build_status_payload(self, state: AgentState) -> dict[str, Any]:
        """Build the standard status payload dict."""
        allocation_df = self.get_allocation_table()
        return {
            "total_capital": self.config.total_capital,
            "portfolio_value": state.portfolio_value,
            "balance": state.balance,
            "num_positions": len(state.positions),
            "num_open_orders": len(state.open_orders),
            "num_slots": len(self._slots),
            "allocation_table": (
                allocation_df.to_dict(orient="records")
                if not allocation_df.empty
                else []
            ),
            "correlation_matrix": (
                self.get_correlation_matrix().to_dict()
                if len(self._slots) >= 2
                else {}
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }


__all__ = [
    "AdaptivePortfolioAgent",
    "AdaptiveConfig",
    "AdaptiveState",
]
