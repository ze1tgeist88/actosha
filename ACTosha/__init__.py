"""ACTosha — Autonomous Crypto Trading Agent."""

__version__ = "0.1.0"

from ACTosha.datafeeder import HyperliquidFeed, BinanceFeed, AbstractExchangeFeed
from ACTosha.cache import DataCache
from ACTosha.indicators import IndicatorEngine
from ACTosha.strategies import Strategy, SignalBundle
from ACTosha.backtester import BacktestEngine, BacktestResult
from ACTosha.executor import (
    AbstractExecutor,
    ExecutionResult,
    Order,
    Position,
    PaperExecutor,
    RiskManager,
    RiskLimits,
    HyperliquidExecutor,
    BinanceExecutor,
)
from ACTosha.scanner import MarketScanner, Opportunity
from ACTosha.agents import TradingAgent, AgentState

__all__ = [
    "__version__",
    # datafeeder
    "HyperliquidFeed",
    "BinanceFeed",
    "AbstractExchangeFeed",
    # cache
    "DataCache",
    # indicators
    "IndicatorEngine",
    # strategies
    "Strategy",
    "SignalBundle",
    # backtester
    "BacktestEngine",
    "BacktestResult",
    # executor
    "AbstractExecutor",
    "ExecutionResult",
    "Order",
    "Position",
    "PaperExecutor",
    "RiskManager",
    "RiskLimits",
    "HyperliquidExecutor",
    "BinanceExecutor",
    # scanner
    "MarketScanner",
    "Opportunity",
    # agents
    "TradingAgent",
    "AgentState",
]
