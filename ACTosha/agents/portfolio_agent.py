"""PortfolioAgent — capital allocation, correlation tracking, and rebalancing."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ACTosha.agents.base import TradingAgent
from ACTosha.agents.message_bus import AgentMessage, AgentMessageBus
from ACTosha.agents.state import AgentAction, AgentEvent, AgentState


# ------------------------------------------------------------------
# PortfolioConfig
# ------------------------------------------------------------------

@dataclass
class PortfolioConfig:
    """Configuration for PortfolioAgent.

    Attributes
    ----------
    total_capital : float
        Total available capital across all strategies. Default: 50 000.
    max_strategies : int
        Maximum number of concurrently active strategy slots. Default: 3.
    rebalance_threshold : float
        Trigger rebalancing when any strategy's weight deviates by more
        than this fraction from its target weight. Default: 0.1 (10%).
    correlation_window : int
        Number of periods for rolling correlation calculation. Default: 50.
    max_correlation : float
        Maximum allowed correlation between any two strategy returns.
        Strategies exceeding this threshold are flagged for review.
        Default: 0.85.
    drawdown_limit : float
        Portfolio-level max drawdown (as fraction). If breached, reduce
        exposure. Default: 0.15 (15%).
    min_opportunity_strength : float
        Minimum opportunity strength to consider for allocation.
        Default: 0.65.
    """

    total_capital: float = 50_000.0
    max_strategies: int = 3
    rebalance_threshold: float = 0.1
    correlation_window: int = 50
    max_correlation: float = 0.85
    drawdown_limit: float = 0.15
    min_opportunity_strength: float = 0.65


# ------------------------------------------------------------------
# StrategySlot
# ------------------------------------------------------------------

@dataclass
class StrategySlot:
    """Represents a capital allocation slot for a strategy in the portfolio.

    Attributes
    ----------
    strategy_id : str
        Unique identifier for this strategy slot.
    strategy_name : str
        Human-readable strategy name.
    allocated_capital : float
        Capital currently allocated to this strategy.
    target_weight : float
        Target weight as fraction of total portfolio (0.0–1.0).
    returns_history : pd.Series
        Rolling series of period returns for this strategy.
    is_active : bool
        Whether this slot is actively being traded.
    """

    strategy_id: str
    strategy_name: str
    allocated_capital: float = 0.0
    target_weight: float = 0.0
    returns_history: pd.Series = field(
        default_factory=lambda: pd.Series(dtype=float)
    )
    is_active: bool = True

    @property
    def current_weight(self) -> float:
        """Current weight in the portfolio based on allocated_capital."""
        return self.allocated_capital

    def update_return(self, ret: float) -> None:
        """Append a period return to the history."""
        ts = datetime.utcnow()
        new = pd.Series({ts: ret})
        if self.returns_history.empty:
            self.returns_history = new
        else:
            self.returns_history = pd.concat(
                [self.returns_history, new]
            )


# ------------------------------------------------------------------
# PortfolioAgent
# ------------------------------------------------------------------

class PortfolioAgent(TradingAgent):
    """Autonomous portfolio management agent.

    PortfolioAgent subscribes to ``market.opportunity`` and
    ``backtest.completed`` topics from the :class:`AgentMessageBus`.
    It allocates capital across strategy slots, tracks correlations,
    and triggers rebalancing when allocation thresholds are breached.

    Parameters
    ----------
    config : PortfolioConfig | None
        Portfolio configuration. Uses defaults if None.
    message_bus : AgentMessageBus | None
        Message bus. Uses singleton if None.
    """

    def __init__(
        self,
        config: PortfolioConfig | None = None,
        message_bus: AgentMessageBus | None = None,
    ) -> None:
        self.config = config or PortfolioConfig()
        self._bus = message_bus or AgentMessageBus()
        self._slots: dict[str, StrategySlot] = {}
        self._opportunity_queue: list[dict] = []
        self._backtest_results: list[dict] = []
        self._equity_history: list[float] = []
        self._lock = threading.RLock()
        self._slot_counter = 0

        # Correlation matrix (strategy_id -> {strategy_id -> correlation})
        self._correlation_matrix: dict[str, dict[str, float]] = defaultdict(dict)

        # Register subscriptions
        self._bus.subscribe("market.opportunity", self._on_opportunity)
        self._bus.subscribe("backtest.completed", self._on_backtest_completed)

    # ------------------------------------------------------------------
    # TradingAgent interface
    # ------------------------------------------------------------------

    @property
    def agent_id(self) -> str:
        return "portfolio"

    @property
    def role(self) -> str:
        return "portfolio"

    def step(self, state: AgentState) -> AgentAction:
        """Evaluate the portfolio state and decide on rebalancing.

        Parameters
        ----------
        state : AgentState
            Current portfolio state snapshot.

        Returns
        -------
        AgentAction
            action_type="rebalance" if rebalancing is triggered,
            "hold" otherwise. Payload includes allocation table and alerts.
        """
        with self._lock:
            # Update equity history from state
            if state.portfolio_value > 0:
                self._equity_history.append(state.portfolio_value)

            # Check drawdown limit
            drawdown_alert = self._check_drawdown()

            # Check rebalancing need
            needs_rebalance, rebalance_reason = self._check_rebalance()

            # Check correlations
            high_corr_alerts = self._check_correlations()

            # Process queued opportunities — allocate if promising
            allocation_decisions = self._process_opportunities()

            actions: list[str] = []
            if drawdown_alert:
                actions.append("reduce_exposure")
            if needs_rebalance:
                actions.append("rebalance")
            if high_corr_alerts:
                actions.append("correlation_alert")

            if not actions:
                return AgentAction(
                    action_type="hold",
                    payload=self._build_status_payload(state),
                    confidence=0.0,
                )

            action_type = actions[0] if len(actions) == 1 else "rebalance"

            return AgentAction(
                action_type=action_type,
                payload={
                    **self._build_status_payload(state),
                    "rebalance_reason": rebalance_reason if needs_rebalance else None,
                    "drawdown_alert": drawdown_alert,
                    "correlation_alerts": high_corr_alerts,
                    "allocation_decisions": allocation_decisions,
                    "actions_taken": actions,
                },
                confidence=0.9,
            )

    def receive_signal(self, event: AgentEvent) -> None:
        """Route incoming events to internal handlers.

        Events on subscribed topics (``market.opportunity``,
        ``backtest.completed``) are handled automatically by the
        registered callbacks; this method handles ad-hoc signals
        from other agents.
        """
        if event.topic == "portfolio.rebalance":
            self._log_rebalance_decision(
                event.data.get("reason", "manual_request")
            )
        elif event.topic == "portfolio.allocate":
            self._handle_allocation_request(event.data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_strategy_slot(
        self,
        strategy_name: str,
        target_weight: float,
        initial_capital: float | None = None,
    ) -> str:
        """Add a new strategy slot to the portfolio.

        Parameters
        ----------
        strategy_name : str
            Human-readable name for the strategy.
        target_weight : float
            Target weight as fraction of total capital (0.0–1.0).
        initial_capital : float | None
            Initial capital allocation. If None, computed from target_weight
            and total_capital.

        Returns
        -------
        str
            The assigned strategy_id for this slot.
        """
        with self._lock:
            self._slot_counter += 1
            strategy_id = f"slot_{self._slot_counter}"

            if initial_capital is None:
                initial_capital = self.config.total_capital * target_weight

            slot = StrategySlot(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                allocated_capital=initial_capital,
                target_weight=target_weight,
            )
            self._slots[strategy_id] = slot
            return strategy_id

    def remove_strategy_slot(self, strategy_id: str) -> bool:
        """Remove a strategy slot and return its capital to unallocated."""
        with self._lock:
            if strategy_id not in self._slots:
                return False
            del self._slots[strategy_id]
            return True

    def set_target_weight(self, strategy_id: str, weight: float) -> None:
        """Update the target weight for a strategy slot."""
        with self._lock:
            if strategy_id in self._slots:
                self._slots[strategy_id].target_weight = max(0.0, min(1.0, weight))

    def get_allocation_table(self) -> pd.DataFrame:
        """Return a DataFrame with current allocation per strategy slot."""
        with self._lock:
            total = self.config.total_capital
            rows = []
            for slot in self._slots.values():
                rows.append(
                    {
                        "strategy_id": slot.strategy_id,
                        "strategy_name": slot.strategy_name,
                        "allocated_capital": slot.allocated_capital,
                        "target_weight": slot.target_weight,
                        "current_weight": (
                            slot.allocated_capital / total
                            if total > 0
                            else 0.0
                        ),
                        "weight_deviation": (
                            slot.allocated_capital / total - slot.target_weight
                            if total > 0
                            else 0.0
                        ),
                        "is_active": slot.is_active,
                    }
                )
            return pd.DataFrame(rows)

    def get_correlation_matrix(self) -> pd.DataFrame:
        """Return the rolling correlation matrix between strategy returns."""
        with self._lock:
            strategy_ids = list(self._slots.keys())
            if len(strategy_ids) < 2:
                return pd.DataFrame()

            matrix = np.zeros((len(strategy_ids), len(strategy_ids)))
            for i, sid_i in enumerate(strategy_ids):
                for j, sid_j in enumerate(strategy_ids):
                    if i == j:
                        matrix[i, j] = 1.0
                    else:
                        corr = self._correlation_matrix.get(sid_i, {}).get(
                            sid_j, 0.0
                        )
                        matrix[i, j] = corr

            df = pd.DataFrame(
                matrix,
                index=strategy_ids,
                columns=strategy_ids,
            )
            return df

    # ------------------------------------------------------------------
    # Internal: event handlers
    # ------------------------------------------------------------------

    def _on_opportunity(self, msg: AgentMessage) -> None:
        """Callback for market.opportunity events."""
        opp_data = msg.data
        strength = opp_data.get("strength", 0.0)
        if strength >= self.config.min_opportunity_strength:
            with self._lock:
                self._opportunity_queue.append(opp_data)

    def _on_backtest_completed(self, msg: AgentMessage) -> None:
        """Callback for backtest.completed events."""
        with self._lock:
            self._backtest_results.append(msg.data)

    def _handle_allocation_request(self, data: dict[str, Any]) -> None:
        """Handle a portfolio.allocate request from another agent."""
        strategy_id = data.get("strategy_id")
        new_capital = data.get("capital")
        if strategy_id and new_capital is not None:
            with self._lock:
                if strategy_id in self._slots:
                    self._slots[strategy_id].allocated_capital = float(new_capital)

    # ------------------------------------------------------------------
    # Internal: checks
    # ------------------------------------------------------------------

    def _check_drawdown(self) -> dict[str, Any] | None:
        """Check if portfolio drawdown exceeds the configured limit."""
        if len(self._equity_history) < 2:
            return None

        peak = max(self._equity_history)
        current = self._equity_history[-1]

        if peak <= 0:
            return None

        drawdown = (peak - current) / peak
        if drawdown > self.config.drawdown_limit:
            return {
                "peak_equity": peak,
                "current_equity": current,
                "drawdown_pct": round(drawdown * 100, 2),
                "limit_pct": round(self.config.drawdown_limit * 100, 2),
            }
        return None

    def _check_rebalance(self) -> tuple[bool, str | None]:
        """Check if any slot has drifted beyond its rebalance threshold.

        Returns
        -------
        (needs_rebalance, reason)
        """
        total = self.config.total_capital
        if total <= 0:
            return False, None

        for slot in self._slots.values():
            current_w = slot.allocated_capital / total
            deviation = abs(current_w - slot.target_weight)
            if deviation > self.config.rebalance_threshold:
                return True, (
                    f"Slot '{slot.strategy_name}' drifted "
                    f"{deviation:.1%} from target {slot.target_weight:.1%}"
                )
        return False, None

    def _check_correlations(self) -> list[dict[str, Any]]:
        """Check inter-strategy correlations and return high-correlation alerts."""
        alerts: list[dict[str, Any]] = []
        if len(self._slots) < 2:
            return alerts

        strategy_ids = list(self._slots.keys())
        for i, sid_i in enumerate(strategy_ids):
            for sid_j in strategy_ids[i + 1 :]:
                corr = self._correlation_matrix.get(sid_i, {}).get(sid_j, 0.0)
                if abs(corr) >= self.config.max_correlation:
                    alerts.append(
                        {
                            "strategy_a": sid_i,
                            "strategy_b": sid_j,
                            "correlation": round(corr, 4),
                            "threshold": self.config.max_correlation,
                        }
                    )
        return alerts

    def _process_opportunities(self) -> list[dict[str, Any]]:
        """Process queued opportunities and make allocation decisions.

        Returns
        -------
        list of decisions taken
        """
        decisions: list[dict[str, Any]] = []
        to_remove: list[int] = []

        with self._lock:
            active_slots = [
                s for s in self._slots.values() if s.is_active
            ]
            available_capital = (
                self.config.total_capital
                - sum(s.allocated_capital for s in active_slots)
            )

        for i, opp in enumerate(self._opportunity_queue):
            strength = opp.get("strength", 0.0)
            symbol = opp.get("symbol", "unknown")
            pattern = opp.get("pattern", "unknown")

            # Only act on high-conviction opportunities
            if strength < self.config.min_opportunity_strength:
                continue

            if available_capital < self.config.total_capital * 0.05:
                # Not enough free capital — defer
                continue

            # Find the least-allocated active slot
            if not active_slots:
                continue

            target_slot = min(
                active_slots,
                key=lambda s: s.allocated_capital,
            )

            # Allocate a portion of capital to this opportunity
            allocation = available_capital * min(strength, 0.3)
            target_slot.allocated_capital += allocation
            available_capital -= allocation

            decisions.append(
                {
                    "opportunity_symbol": symbol,
                    "pattern": pattern,
                    "strength": strength,
                    "allocated_to": target_slot.strategy_name,
                    "capital_allocated": round(allocation, 2),
                }
            )
            to_remove.append(i)

        # Remove processed opportunities
        for i in reversed(to_remove):
            self._opportunity_queue.pop(i)

        # Update correlation matrix if we have enough history
        self._update_correlations()

        return decisions

    def _update_correlations(self) -> None:
        """Recompute rolling correlations between all strategy slot returns."""
        slot_list = list(self._slots.values())
        if len(slot_list) < 2:
            return

        window = self.config.correlation_window

        for i, slot_i in enumerate(slot_list):
            for j, slot_j in enumerate(slot_list):
                if i >= j:
                    continue

                hist_i = slot_i.returns_history
                hist_j = slot_j.returns_history

                if len(hist_i) < 10 or len(hist_j) < 10:
                    continue

                # Align by index (timestamp)
                aligned_i, aligned_j = hist_i.align(hist_j, join="inner")
                if len(aligned_i) < 10:
                    continue

                # Rolling correlation over window
                if len(aligned_i) >= window:
                    rolls = (
                        aligned_i.rolling(window)
                        .corr(aligned_j)
                        .dropna()
                    )
                    corr = float(rolls.iloc[-1]) if len(rolls) > 0 else 0.0
                else:
                    corr = float(aligned_i.corr(aligned_j))

                self._correlation_matrix[slot_i.strategy_id][
                    slot_j.strategy_id
                ] = corr
                self._correlation_matrix[slot_j.strategy_id][
                    slot_i.strategy_id
                ] = corr

    def _log_rebalance_decision(self, reason: str) -> None:
        """Record a rebalance decision for audit / history."""
        # Future: persist to audit log
        pass

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _rebalance(self) -> None:
        """Execute a rebalancing pass: restore each slot to its target weight."""
        total = self.config.total_capital
        if total <= 0:
            return

        for slot in self._slots.values():
            target_capital = total * slot.target_weight
            slot.allocated_capital = target_capital

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
            "num_queued_opportunities": len(self._opportunity_queue),
            "num_pending_backtests": len(self._backtest_results),
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
    "PortfolioAgent",
    "PortfolioConfig",
    "StrategySlot",
]
