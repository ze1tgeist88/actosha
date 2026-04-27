"""Backtester module — backtesting engine, portfolio, simulator, and metrics."""

from ACTosha.backtester.engine import BacktestEngine, BacktestResult
from ACTosha.backtester.metrics import PerformanceMetricsCalculator
from ACTosha.backtester.portfolio import CombinedResult, PortfolioBacktester
from ACTosha.backtester.simulator import (
    EXCHANGE_FUNDING,
    Fill,
    FillMode,
    FundingPayment,
    FundingRate,
    Order,
    OrderSide,
    OrderSimulator,
)

__all__ = [
    # Engine
    "BacktestEngine",
    "BacktestResult",
    # Portfolio
    "PortfolioBacktester",
    "CombinedResult",
    # Simulator
    "OrderSimulator",
    "Order",
    "Fill",
    "FillMode",
    "FundingPayment",
    "FundingRate",
    "OrderSide",
    "EXCHANGE_FUNDING",
    # Metrics
    "PerformanceMetricsCalculator",
]
