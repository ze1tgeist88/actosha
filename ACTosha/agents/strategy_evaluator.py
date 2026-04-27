"""StrategyEvaluator — scores, ranks, and advises on strategy replacement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ------------------------------------------------------------------
# Score components
# ------------------------------------------------------------------

@dataclass
class StrategyScore:
    """Composite score for a single strategy with breakdown."""

    strategy_id: str
    strategy_name: str
    overall_score: float  # 0.0–1.0

    # Component scores (0.0–1.0)
    sharpe_score: float
    win_rate_score: float
    drawdown_score: float  # 1.0 = no drawdown, 0.0 = at/max threshold
    consistency_score: float  # how stable are returns

    # Raw metrics
    sharpe_ratio: float
    win_rate: float
    max_drawdown_pct: float
    total_return_pct: float
    num_trades: int

    # Flags
    is_flagged: bool = False
    flag_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "overall_score": round(self.overall_score, 4),
            "sharpe_score": round(self.sharpe_score, 4),
            "win_rate_score": round(self.win_rate_score, 4),
            "drawdown_score": round(self.drawdown_score, 4),
            "consistency_score": round(self.consistency_score, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "win_rate": round(self.win_rate, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_return_pct": round(self.total_return_pct, 4),
            "num_trades": self.num_trades,
            "is_flagged": self.is_flagged,
            "flag_reason": self.flag_reason,
        }


@dataclass
class ReplacementAdvice:
    """Advice on which strategy to replace and with what."""

    should_replace: bool
    victim_id: str | None
    victim_name: str | None
    reason: str
    candidate_id: str | None
    confidence: float = 0.0


# ------------------------------------------------------------------
# StrategyEvaluator
# ------------------------------------------------------------------

class StrategyEvaluator:
    """Evaluates strategy performance and provides ranking / replacement advice.

    Parameters
    ----------
    max_drawdown_threshold : float
        Drawdown (as fraction) above which drawdown_score → 0. Default: 0.20.
    win_rate_threshold : float
        Win rate (as fraction) below which strategy is flagged. Default: 0.40.
    sharpe_flag_threshold : float
        Sharpe ratio below which strategy is flagged for review. Default: 0.0.
    min_trades_for_score : int
        Minimum trades required for a reliable score. Default: 10.
    benchmark_sharpe : float
        Benchmark Sharpe to compare against. Default: 1.0.
    """

    def __init__(
        self,
        max_drawdown_threshold: float = 0.20,
        win_rate_threshold: float = 0.40,
        sharpe_flag_threshold: float = 0.0,
        min_trades_for_score: int = 10,
        benchmark_sharpe: float = 1.0,
    ) -> None:
        self.max_drawdown_threshold = max_drawdown_threshold
        self.win_rate_threshold = win_rate_threshold
        self.sharpe_flag_threshold = sharpe_flag_threshold
        self.min_trades_for_score = min_trades_for_score
        self.benchmark_sharpe = benchmark_sharpe

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_strategy(self, result: Any, strategy_id: str = "", strategy_name: str = "") -> StrategyScore:
        """Score a strategy from its BacktestResult.

        Parameters
        ----------
        result : BacktestResult or dict
            Backtest result object or dict with `metrics` and `trades`.
        strategy_id : str
            Unique identifier for this strategy slot.
        strategy_name : str
            Human-readable strategy name.

        Returns
        -------
        StrategyScore
        """
        if isinstance(result, dict):
            metrics = result.get("metrics", {})
            trades_df = result.get("trades")
            num_trades = result.get("num_trades", len(trades_df) if trades_df is not None else 0)
        else:
            metrics = getattr(result, "metrics", {})
            trades_df = getattr(result, "trades", None)
            num_trades = len(trades_df) if trades_df is not None else 0

        sharpe_ratio = float(metrics.get("sharpe_ratio") or 0.0)
        win_rate = float(metrics.get("win_rate") or 0.0)
        max_dd_pct = float(metrics.get("max_drawdown_pct") or 0.0)
        total_return = float(metrics.get("total_return_pct") or 0.0)

        # Component scores
        sharpe_score = self._sharpe_score(sharpe_ratio)
        win_rate_score = self._win_rate_score(win_rate)
        drawdown_score = self._drawdown_score(max_dd_pct)
        consistency_score = self._consistency_score(trades_df)

        # Overall = weighted average
        overall_score = (
            0.35 * sharpe_score
            + 0.25 * win_rate_score
            + 0.25 * drawdown_score
            + 0.15 * consistency_score
        )

        # Flags
        is_flagged = False
        flag_reason = ""
        if sharpe_ratio < self.sharpe_flag_threshold:
            is_flagged = True
            flag_reason = f"Sharpe {sharpe_ratio:.2f} < threshold {self.sharpe_flag_threshold:.2f}"
        elif win_rate < self.win_rate_threshold:
            is_flagged = True
            flag_reason = f"WinRate {win_rate:.1%} < threshold {self.win_rate_threshold:.1%}"
        elif max_dd_pct / 100.0 > self.max_drawdown_threshold:
            is_flagged = True
            flag_reason = f"MaxDD {max_dd_pct:.1f}% > threshold {self.max_drawdown_threshold * 100:.1f}%"

        return StrategyScore(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            overall_score=overall_score,
            sharpe_score=sharpe_score,
            win_rate_score=win_rate_score,
            drawdown_score=drawdown_score,
            consistency_score=consistency_score,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            max_drawdown_pct=max_dd_pct,
            total_return_pct=total_return,
            num_trades=num_trades,
            is_flagged=is_flagged,
            flag_reason=flag_reason,
        )

    def compare_with_benchmark(
        self,
        scores: list[StrategyScore],
    ) -> list[StrategyScore]:
        """Rank strategies by overall_score descending.

        Parameters
        ----------
        scores : list[StrategyScore]
            List of scored strategies.

        Returns
        -------
        list[StrategyScore]
            Sorted descending by overall_score.
        """
        return sorted(scores, key=lambda s: s.overall_score, reverse=True)

    def recommend_replacement(
        self,
        active_scores: list[StrategyScore],
        candidate_scores: list[StrategyScore] | None = None,
        top_n: int = 3,
    ) -> ReplacementAdvice:
        """Recommend whether to replace a strategy and which one.

        Parameters
        ----------
        active_scores : list[StrategyScore]
            Currently active strategies with their scores.
        candidate_scores : list[StrategyScore] | None
            Candidate strategies from backtests (optional).
        top_n : int
            How many bottom performers to consider for replacement.

        Returns
        -------
        ReplacementAdvice
        """
        if not active_scores:
            return ReplacementAdvice(
                should_replace=False,
                victim_id=None,
                victim_name=None,
                reason="No active strategies to evaluate.",
                candidate_id=None,
                confidence=0.0,
            )

        # Always sort active scores
        ranked = self.compare_with_benchmark(active_scores)

        # Find bottom performers
        bottom = ranked[-(min(top_n, len(ranked))) :]

        # Check circuit-breaker flags first
        for score in ranked:
            if score.max_drawdown_pct / 100.0 > self.max_drawdown_threshold:
                return ReplacementAdvice(
                    should_replace=True,
                    victim_id=score.strategy_id,
                    victim_name=score.strategy_name,
                    reason=f"CIRCUIT BREAKER: MaxDD {score.max_drawdown_pct:.1f}% exceeds threshold",
                    candidate_id=None,
                    confidence=1.0,
                )

        # Check if any active strategy is flagged
        for score in ranked:
            if score.is_flagged:
                # Try to find a better candidate
                candidate_id = None
                if candidate_scores:
                    candidate_ranked = self.compare_with_benchmark(candidate_scores)
                    if candidate_ranked and candidate_ranked[0].overall_score > score.overall_score:
                        candidate_id = candidate_ranked[0].strategy_id

                return ReplacementAdvice(
                    should_replace=True,
                    victim_id=score.strategy_id,
                    victim_name=score.strategy_name,
                    reason=f"Flagged for review: {score.flag_reason}",
                    candidate_id=candidate_id,
                    confidence=0.85,
                )

        # No clear replacement needed
        return ReplacementAdvice(
            should_replace=False,
            victim_id=None,
            victim_name=None,
            reason="All active strategies within acceptable parameters.",
            candidate_id=None,
            confidence=0.5,
        )

    # ------------------------------------------------------------------
    # Internal scoring helpers
    # ------------------------------------------------------------------

    def _sharpe_score(self, sharpe: float) -> float:
        """Score Sharpe ratio 0–1. Benchmark = self.benchmark_sharpe."""
        if sharpe <= self.sharpe_flag_threshold:
            return 0.0
        # Normalise against benchmark: 0 → 0, benchmark → 0.7, 3×benchmark → 1.0
        ratio = sharpe / self.benchmark_sharpe
        capped = min(ratio, 3.0)
        return float(max(0.0, min(1.0, 0.7 * capped / 3.0 + 0.3 * (1 - max(0, (1 - capped)) / 1))))

    def _win_rate_score(self, win_rate: float) -> float:
        """Score win rate 0–1. Below 40% → 0, above 60% → 1."""
        if win_rate <= 0.0:
            return 0.0
        score = (win_rate - 0.40) / (0.60 - 0.40)  # linear map 0.40→0.0, 0.60→1.0
        return float(max(0.0, min(1.0, score)))

    def _drawdown_score(self, max_dd_pct: float) -> float:
        """Score drawdown 0–1. At 0% → 1.0, at threshold → 0.0."""
        threshold_pct = self.max_drawdown_threshold * 100.0
        if max_dd_pct <= 0.0:
            return 1.0
        score = 1.0 - (max_dd_pct / threshold_pct)
        return float(max(0.0, min(1.0, score)))

    def _consistency_score(self, trades_df: Any) -> float:
        """Score return consistency from trades DataFrame."""
        if trades_df is None or (hasattr(trades_df, "empty") and trades_df.empty):
            return 0.5  # no data → neutral
        try:
            pnls = trades_df["pnl_pct"].values
            if len(pnls) < 3:
                return 0.5
            # CV of PnL: lower CV = more consistent = higher score
            mean = np.mean(pnls)
            std = np.std(pnls)
            if mean <= 0:
                return 0.3
            cv = std / mean
            # Map CV: 0 → 1.0, 2+ → 0.0
            score = max(0.0, min(1.0, 1.0 - cv / 2.0))
            return float(score)
        except Exception:
            return 0.5


__all__ = [
    "StrategyEvaluator",
    "StrategyScore",
    "ReplacementAdvice",
]
