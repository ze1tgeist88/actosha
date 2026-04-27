"""Backtester: multi-strategy portfolio backtesting."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ACTosha.backtester.engine import BacktestEngine, BacktestResult
from ACTosha.strategies.base import Strategy


class CombinedResult:
    """Aggregated results from a multi-strategy backtest."""

    def __init__(
        self,
        strategy_results: dict[str, BacktestResult],
        combined_equity: pd.Series,
        total_metrics: dict[str, Any],
    ) -> None:
        self.strategy_results = strategy_results
        self.combined_equity = combined_equity
        self.total_metrics = total_metrics


class PortfolioBacktester:
    """Run backtests across multiple strategies and aggregate results.

    Each strategy receives its own capital allocation and operates independently.
    Final equity is the sum of all strategy equities.
    """

    def __init__(self) -> None:
        self._engine = BacktestEngine()

    def run_multi_strategy(
        self,
        strategies: list[Strategy],
        df_map: dict[str, pd.DataFrame],
        capital_per_strategy: float = 10_000.0,
        commission: float = 0.0004,
        slippage: float = 0.0005,
    ) -> CombinedResult:
        """Run backtests for multiple strategies.

        Args:
            strategies:         List of strategy instances.
            df_map:             Dict mapping symbol → OHLCV DataFrame.
            capital_per_strategy: Initial capital allocated to each strategy.
            commission:         Commission rate per trade.
            slippage:           Slippage in basis points.

        Returns:
            CombinedResult with per-strategy results and aggregated equity.
        """
        strategy_results: dict[str, BacktestResult] = {}
        equity_curves: list[pd.Series] = []

        for strategy in strategies:
            symbol = strategy.symbols[0] if strategy.symbols else list(df_map.keys())[0]
            df = df_map.get(symbol)
            if df is None:
                continue

            result = self._engine.run(
                strategy=strategy,
                df=df,
                initial_capital=capital_per_strategy,
                commission=commission,
                slippage=slippage,
            )
            strategy_results[strategy.name] = result
            equity_curves.append(result.equity_curve)

        # Combine equity curves (aligned by index)
        combined = pd.concat(equity_curves, axis=1).sum(axis=1)
        combined.name = "combined_equity"

        # Aggregate metrics across strategies
        total_return = (
            combined.iloc[-1] / combined.iloc[0] - 1 if len(combined) > 1 else 0.0
        )
        total_trades = sum(
            len(r.trades) for r in strategy_results.values() if not r.trades.empty
        )
        avg_sharpe = sum(
            r.metrics.get("sharpe_ratio", 0) for r in strategy_results.values()
        ) / max(len(strategy_results), 1)

        total_metrics: dict[str, Any] = {
            "total_return": total_return,
            "total_trades": total_trades,
            "avg_sharpe_ratio": avg_sharpe,
            "num_strategies": len(strategy_results),
        }

        return CombinedResult(
            strategy_results=strategy_results,
            combined_equity=combined,
            total_metrics=total_metrics,
        )


__all__ = ["PortfolioBacktester", "CombinedResult"]