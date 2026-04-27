"""RiskManager — position limits, drawdown checks, and position sizing validation."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ACTosha.executor.paper import PaperExecutor


@dataclass
class RiskLimits:
    """Configurable risk limits for a trading account.

    Parameters
    ----------
    max_position_size_usd : float
        Maximum position size in USD per symbol.
    max_total_position_usd : float
        Maximum total exposure across all positions.
    max_leverage : float
        Maximum allowed leverage (e.g. 3.0 = 3x).
    max_drawdown_pct : float
        Max drawdown percentage that triggers a full stop (e.g. 0.20 = 20%).
    max_daily_loss_usd : float | None
        Maximum loss allowed per calendar day. None = no limit.
    min_trade_size_usd : float
        Minimum trade size in USD (skip if below).
    """

    max_position_size_usd: float = 1_000.0
    max_total_position_usd: float = 5_000.0
    max_leverage: float = 3.0
    max_drawdown_pct: float = 0.20
    max_daily_loss_usd: float | None = None
    min_trade_size_usd: float = 10.0


@dataclass
class RiskCheckResult:
    """Result of a risk check."""

    passed: bool
    reason: str = ""
    suggested_size: float | None = None


@dataclass
class AccountRiskSnapshot:
    """Current account-level risk metrics."""

    total_exposure_usd: float
    largest_position_usd: float
    position_count: int
    current_drawdown_pct: float
    peak_equity_usd: float
    current_equity_usd: float
    daily_pnl_usd: float
    leverage: float


class RiskManager:
    """Risk management and validation for trading executions.

    The RiskManager checks orders and positions against configured limits
    before they are submitted. It also tracks equity, drawdown, and
    exposes account-level risk metrics.

    Parameters
    ----------
    limits : RiskLimits
        Risk limit configuration.
    executor : PaperExecutor | None
        Reference to the executor for reading current state.
        Can be set later via ``set_executor``.
    initial_capital : float
        Initial capital for drawdown calculation (if no executor provided).
    """

    def __init__(
        self,
        limits: RiskLimits | None = None,
        executor: "PaperExecutor | None" = None,
        initial_capital: float = 10_000.0,
    ) -> None:
        self._limits = limits or RiskLimits()
        self._executor = executor
        self._peak_equity = initial_capital
        self._daily_loss = 0.0
        self._daily_reset_ts: str | None = None  # YYYY-MM-DD

    def set_executor(self, executor: "PaperExecutor") -> None:
        """Attach an executor for live state reads."""
        self._executor = executor

    def set_limits(self, **kwargs) -> None:
        """Update risk limits by keyword argument."""
        for key, value in kwargs.items():
            if hasattr(self._limits, key):
                setattr(self._limits, key, value)

    # ------------------------------------------------------------------
    # Pre-trade validation
    # ------------------------------------------------------------------

    def validate_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
    ) -> RiskCheckResult:
        """Validate a proposed order against all risk limits.

        Parameters
        ----------
        symbol : str
            Trading symbol (e.g. "BTC").
        side : str
            "buy" or "sell".
        size : float
            Order size in base currency.
        price : float
            Reference price for USD conversion.

        Returns
        -------
        RiskCheckResult
        """
        notional_usd = size * price

        # 1. Minimum trade size
        if notional_usd < self._limits.min_trade_size_usd:
            return RiskCheckResult(
                passed=False,
                reason=f"Notional ${notional_usd:.2f} below minimum ${self._limits.min_trade_size_usd:.2f}",
            )

        # 2. Position size limit
        if notional_usd > self._limits.max_position_size_usd:
            suggested = self._limits.max_position_size_usd / price
            return RiskCheckResult(
                passed=False,
                reason=f"Position ${notional_usd:.2f} exceeds max ${self._limits.max_position_size_usd:.2f}",
                suggested_size=suggested,
            )

        # 3. Total exposure
        current_exposure = self._current_exposure()
        if current_exposure + notional_usd > self._limits.max_total_position_usd:
            remaining = self._limits.max_total_position_usd - current_exposure
            if remaining <= 0:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Total exposure cap reached (${current_exposure:.2f}/${self._limits.max_total_position_usd:.2f})",
                )
            suggested = remaining / price
            return RiskCheckResult(
                passed=False,
                reason=f"Would exceed total exposure: ${current_exposure + notional_usd:.2f} > ${self._limits.max_total_position_usd:.2f}",
                suggested_size=suggested,
            )

        # 4. Max leverage check
        equity = self._current_equity()
        if equity > 0:
            leverage = notional_usd / equity
            if leverage > self._limits.max_leverage:
                max_size = (equity * self._limits.max_leverage) / price
                return RiskCheckResult(
                    passed=False,
                    reason=f"Leverage {leverage:.1f}x exceeds max {self._limits.max_leverage:.1f}x",
                    suggested_size=max_size,
                )

        # 5. Max drawdown stop
        snapshot = self.get_snapshot()
        if snapshot.current_drawdown_pct >= self._limits.max_drawdown_pct:
            return RiskCheckResult(
                passed=False,
                reason=f"Max drawdown {snapshot.current_drawdown_pct:.1%} ≥ {self._limits.max_drawdown_pct:.1%} — trading halted",
            )

        # 6. Daily loss check
        self._check_daily_reset()
        if (
            self._limits.max_daily_loss_usd is not None
            and -self._daily_loss >= self._limits.max_daily_loss_usd
        ):
            return RiskCheckResult(
                passed=False,
                reason=f"Daily loss ${self._daily_loss:.2f} ≥ limit ${self._limits.max_daily_loss_usd:.2f}",
            )

        return RiskCheckResult(passed=True)

    def validate_size(
        self,
        size: float,
        price: float,
        side: str = "buy",
    ) -> float:
        """Validate and optionally clamp order size to risk limits.

        Returns the allowed size (may be smaller than input if limits exceeded).
        Raises ValueError if order would violate drawdown or daily loss.
        """
        check = self.validate_order(symbol="", side=side, size=size, price=price)
        if not check.passed:
            if "trading halted" in check.reason or "Daily loss" in check.reason:
                raise ValueError(check.reason)
            # Return suggested size for soft limit violations
            if check.suggested_size is not None:
                return max(check.suggested_size, 0.0)
            return 0.0
        return size

    def get_snapshot(self) -> AccountRiskSnapshot:
        """Return current account risk snapshot."""
        equity = self._current_equity()
        self._peak_equity = max(self._peak_equity, equity)
        dd_pct = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0.0

        positions = self._get_positions()
        total_exposure = sum(abs(p.size * p.entry_price) for p in positions)
        largest = max((abs(p.size * p.entry_price) for p in positions), default=0.0)
        leverage = total_exposure / equity if equity > 0 else 0.0

        self._check_daily_reset()
        return AccountRiskSnapshot(
            total_exposure_usd=total_exposure,
            largest_position_usd=largest,
            position_count=len(positions),
            current_drawdown_pct=dd_pct,
            peak_equity_usd=self._peak_equity,
            current_equity_usd=equity,
            daily_pnl_usd=self._daily_loss,
            leverage=leverage,
        )

    def update_daily_pnl(self, pnl_delta: float) -> None:
        """Update daily PnL tracker (call after each trade)."""
        self._check_daily_reset()
        self._daily_loss += pnl_delta

    def reset_daily(self) -> None:
        """Manually reset daily PnL tracker."""
        from datetime import datetime
        self._daily_loss = 0.0
        self._daily_reset_ts = datetime.utcnow().strftime("%Y-%m-%d")

    def reset_peak(self) -> None:
        """Reset peak equity to current equity (call after a profitable period)."""
        self._peak_equity = self._current_equity()

    # ------------------------------------------------------------------
    # Kelly criterion position sizing
    # ------------------------------------------------------------------

    def kelly_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        price: float,
        fraction: float = 0.25,
    ) -> float:
        """Calculate position size using the Kelly criterion (fractional).

        Kelly % = W - (1-W)/RR
        where W = win rate, RR = avg_win / avg_loss

        Parameters
        ----------
        win_rate : float
            Historical win rate (0.0–1.0).
        avg_win : float
            Average winning trade in USD.
        avg_loss : float
            Average losing trade in USD (positive number).
        price : float
            Entry price for converting to base size.
        fraction : float
            Kelly fraction to use (default 0.25 = quarter Kelly).

        Returns
        -------
        float
            Position size in base currency.
        """
        if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        rr = avg_win / avg_loss
        kelly_pct = win_rate - (1 - win_rate) / rr
        if kelly_pct <= 0:
            return 0.0

        equity = self._current_equity()
        kelly_dollars = equity * kelly_pct * fraction
        size = kelly_dollars / price

        # Clamp to risk limits
        max_by_pos = self._limits.max_position_size_usd / price
        max_by_exposure = (self._limits.max_total_position_usd - self._current_exposure()) / price
        max_size = min(max_by_pos, max_by_exposure, equity * self._limits.max_leverage / price)
        return max(min(size, max_size), 0.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_exposure(self) -> float:
        """Sum of absolute USD notional of all open positions."""
        positions = self._get_positions()
        return sum(abs(p.size * p.entry_price) for p in positions)

    def _current_equity(self) -> float:
        """Current total equity."""
        if self._executor is not None:
            return self._executor.get_equity()
        return self._peak_equity * (1 - self.get_snapshot().current_drawdown_pct)

    def _get_positions(self):
        """Get current positions from executor or empty list."""
        if self._executor is not None:
            return self._executor.get_positions()
        return []

    def _check_daily_reset(self) -> None:
        """Reset daily PnL tracker if a new day has started."""
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self._daily_reset_ts != today:
            self._daily_loss = 0.0
            self._daily_reset_ts = today


__all__ = ["RiskManager", "RiskLimits", "RiskCheckResult", "AccountRiskSnapshot"]
