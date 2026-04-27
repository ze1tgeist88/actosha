"""PerformanceMetricsCalculator — Sharpe, Sortino, MaxDD, WinRate, Calmar, etc."""

from __future__ import annotations

from typing import Any

import pandas as pd
import numpy as np


class PerformanceMetricsCalculator:
    """Calculate performance metrics from backtest results.

    Usage
    -----
    calc = PerformanceMetricsCalculator()
    metrics = calc.calculate(
        equity_curve=equity_series,
        trades=trades_df,
        initial_capital=10_000.0,
        commission_total=0.0,
    )
    """

    def __init__(self, periods_per_year: int = 365 * 24) -> None:
        """Initialize calculator.

        Parameters
        ----------
        periods_per_year : int
            Number of periods in a year for annualization.
            Default 365*24 assumes hourly bars.
            Use 252*24*60 for minute bars, 252 for daily bars, etc.
        """
        self.periods_per_year = periods_per_year

    def calculate(
        self,
        equity_curve: pd.Series,
        trades: pd.DataFrame,
        initial_capital: float = 10_000.0,
        commission_total: float = 0.0,
    ) -> dict[str, Any]:
        """Calculate all performance metrics.

        Parameters
        ----------
        equity_curve : pd.Series
            Portfolio equity over time (DatetimeIndex).
        trades : pd.DataFrame
            DataFrame of closed trades (from BacktestResult.trades).
        initial_capital : float
            Starting capital.
        commission_total : float
            Total commissions paid (for net return calc).

        Returns
        -------
        dict
            All computed metrics.
        """
        if equity_curve.empty or len(equity_curve) < 2:
            return _empty_metrics()

        returns = equity_curve.pct_change().dropna()

        total_return = equity_curve.iloc[-1] / initial_capital - 1 if initial_capital > 0 else 0.0
        net_return = total_return - commission_total / initial_capital if initial_capital > 0 else total_return

        # --- Equity-based metrics ---
        sharpe = self._sharpe_ratio(returns)
        sortino = self._sortino_ratio(returns)
        max_dd, max_dd_pct, dd_duration_bars, dd_duration_days = self._max_drawdown(equity_curve)
        calmar = self._calmar_ratio(total_return, max_dd_pct, equity_curve)
        exposure_pct = self._exposure_time(trades, len(equity_curve))

        # --- Trade-based metrics ---
        win_rate = self._win_rate(trades)
        profit_factor = self._profit_factor(trades)
        avg_trade_pnl = self._avg_trade_pnl(trades)
        avg_trade_duration = self._avg_trade_duration(trades)
        trade_count = len(trades)

        # --- Return series metrics ---
        annual_return = self._annual_return(returns)
        volatility = self._volatility(returns)

        metrics: dict[str, Any] = {
            # ---- Return metrics ----
            "total_return": round(float(total_return), 6),
            "net_return": round(float(net_return), 6),
            "annual_return": round(float(annual_return), 6),
            # ---- Risk-adjusted ----
            "sharpe_ratio": round(float(sharpe), 4) if np.isfinite(sharpe) else None,
            "sortino_ratio": round(float(sortino), 4) if np.isfinite(sortino) else None,
            "calmar_ratio": round(float(calmar), 4) if np.isfinite(calmar) else None,
            "max_drawdown": round(float(max_dd), 2),
            "max_drawdown_pct": round(float(max_dd_pct) * 100, 2),
            "max_drawdown_duration_bars": int(dd_duration_bars),
            "max_drawdown_duration_days": round(float(dd_duration_days), 1)
            if dd_duration_days is not None else None,
            "volatility_annual": round(float(volatility), 4) if np.isfinite(volatility) else None,
            # ---- Trade metrics ----
            "trade_count": trade_count,
            "win_rate": round(float(win_rate), 4) if np.isfinite(win_rate) else None,
            "profit_factor": round(float(profit_factor), 4) if np.isfinite(profit_factor) else None,
            "avg_trade_pnl": round(float(avg_trade_pnl), 2) if np.isfinite(avg_trade_pnl) else None,
            "avg_trade_duration_bars": round(float(avg_trade_duration), 2)
            if np.isfinite(avg_trade_duration) else None,
            "total_commission": round(float(commission_total), 2),
            # ---- Exposure ----
            "exposure_time_pct": round(float(exposure_pct) * 100, 2),
        }
        return metrics

    # ------------------------------------------------------------------
    # Individual metric methods
    # ------------------------------------------------------------------

    def _sharpe_ratio(self, returns: pd.Series) -> float:
        """Annualized Sharpe ratio: (mean return / std) * sqrt(periods/year)."""
        if returns.empty or returns.std() == 0:
            return 0.0
        mean_ret = returns.mean()
        std_ret = returns.std()
        return (mean_ret / std_ret) * np.sqrt(self.periods_per_year)

    def _sortino_ratio(self, returns: pd.Series) -> float:
        """Annualized Sortino ratio: (mean return / downside_std) * sqrt(periods/year)."""
        if returns.empty:
            return 0.0
        mean_ret = returns.mean()
        downside = returns[returns < 0]
        if downside.empty or downside.std() == 0:
            return 0.0
        downside_std = downside.std()
        return (mean_ret / downside_std) * np.sqrt(self.periods_per_year)

    def _max_drawdown(self, equity: pd.Series) -> tuple[float, float, int, float | None]:
        """Compute peak, max drawdown in currency, max drawdown %, duration."""
        if equity.empty:
            return 0.0, 0.0, 0, None

        running_max = equity.cummax()
        drawdown = equity - running_max
        max_dd = drawdown.min()  # negative value

        # Max drawdown %
        peak = running_max.loc[drawdown.idxmin()] if drawdown.idxmin() is not None else running_max.iloc[0]
        max_dd_pct = max_dd / peak if peak != 0 else 0.0

        # Duration: longest streak of drawdown
        in_dd = drawdown < 0
        if not in_dd.any():
            return float(max_dd), float(max_dd_pct), 0, 0.0

        max_dd_bars = 0
        current_dd_bars = 0
        for val in in_dd:
            if val:
                current_dd_bars += 1
                max_dd_bars = max(max_dd_bars, current_dd_bars)
            else:
                current_dd_bars = 0

        # Estimate days: assume hourly bars → / 24
        max_dd_days = max_dd_bars / 24.0 if max_dd_bars > 0 else None
        return float(max_dd), float(max_dd_pct), int(max_dd_bars), max_dd_days

    def _calmar_ratio(
        self,
        total_return: float,
        max_dd_pct: float,
        equity: pd.Series,
    ) -> float:
        """Calmar = annualized return / |max drawdown %|."""
        if max_dd_pct == 0:
            return 0.0
        # Annualize the total return based on the equity series length
        n_years = len(equity) / self.periods_per_year if self.periods_per_year > 0 else 1.0
        n_years = max(n_years, 1e-6)
        annualized = (1 + total_return) ** (1.0 / n_years) - 1
        return annualized / abs(max_dd_pct)

    def _win_rate(self, trades: pd.DataFrame) -> float:
        """Fraction of profitable trades."""
        if trades.empty:
            return 0.0
        return (trades["pnl"] > 0).sum() / len(trades)

    def _profit_factor(self, trades: pd.DataFrame) -> float:
        """Gross profit / gross loss absolute value."""
        if trades.empty:
            return 0.0
        gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()
        gross_loss = abs(trades.loc[trades["pnl"] < 0, "pnl"].sum())
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def _avg_trade_pnl(self, trades: pd.DataFrame) -> float:
        """Average PnL per trade."""
        if trades.empty:
            return 0.0
        return trades["pnl"].mean()

    def _avg_trade_duration(self, trades: pd.DataFrame) -> float:
        """Average duration in bars."""
        if trades.empty:
            return 0.0
        if "duration_bars" not in trades.columns:
            return 0.0
        return trades["duration_bars"].mean()

    def _annual_return(self, returns: pd.Series) -> float:
        """Annualized return based on mean period return."""
        if returns.empty:
            return 0.0
        return ((1 + returns.mean()) ** self.periods_per_year) - 1

    def _volatility(self, returns: pd.Series) -> float:
        """Annualized volatility of returns."""
        if returns.empty:
            return 0.0
        return returns.std() * np.sqrt(self.periods_per_year)

    def _exposure_time(self, trades: pd.DataFrame, total_bars: int) -> float:
        """Fraction of bars with an open position."""
        if trades.empty or total_bars == 0:
            return 0.0
        total_exposure = trades["duration_bars"].sum() if "duration_bars" in trades.columns else 0
        return min(total_exposure / total_bars, 1.0)


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_return": 0.0,
        "net_return": 0.0,
        "annual_return": 0.0,
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "calmar_ratio": None,
        "max_drawdown": 0.0,
        "max_drawdown_pct": 0.0,
        "max_drawdown_duration_bars": 0,
        "max_drawdown_duration_days": None,
        "volatility_annual": None,
        "trade_count": 0,
        "win_rate": None,
        "profit_factor": None,
        "avg_trade_pnl": None,
        "avg_trade_duration_bars": None,
        "total_commission": 0.0,
        "exposure_time_pct": 0.0,
    }


__all__ = ["PerformanceMetricsCalculator"]
