"""Agents module — agent-based orchestration layer for ACTosha.

The agent layer provides autonomous agents that communicate via a
topic-based publish/subscribe message bus.

Public API
----------
TradingAgent      : abstract base class for all agents
AgentState        : snapshot of positions, balance, portfolio value
AgentAction       : action produced by an agent after step()
AgentEvent        : event received from the message bus
AgentMessage      : message published on the message bus
AgentMessageBus   : thread-safe topic-based pub/sub bus

Specialized agents
------------------
ScannerAgent      : periodic market scanning, publishes market.opportunity
BacktestAgent     : runs backtests + parameter optimization
PortfolioAgent    : capital allocation, correlation tracking, rebalancing

Message Bus Topics
------------------
market.opportunity     — ScannerAgent → PortfolioAgent
backtest.completed     — BacktestAgent → PortfolioAgent / Caller
trade.executed         — Executor → PortfolioAgent
portfolio.rebalance    — PortfolioAgent → Executor
alert.signal           — any → Notifier
backtest.request       — Caller → BacktestAgent
"""

from ACTosha.agents.base import TradingAgent
from ACTosha.agents.message_bus import AgentMessage, AgentMessageBus
from ACTosha.agents.state import AgentAction, AgentEvent, AgentState

# Specialized agents
from ACTosha.agents.scanner_agent import ScannerAgent, ScannerConfig
from ACTosha.agents.backtest_agent import (
    BacktestAgent,
    BacktestTask,
    OptimizationConfig,
    OptimizationResult,
)
from ACTosha.agents.portfolio_agent import (
    PortfolioAgent,
    PortfolioConfig,
    StrategySlot,
)

__all__ = [
    # Core
    "TradingAgent",
    "AgentState",
    "AgentAction",
    "AgentEvent",
    "AgentMessage",
    "AgentMessageBus",
    # Scanner
    "ScannerAgent",
    "ScannerConfig",
    # Backtest
    "BacktestAgent",
    "BacktestTask",
    "OptimizationConfig",
    "OptimizationResult",
    # Portfolio
    "PortfolioAgent",
    "PortfolioConfig",
    "StrategySlot",
]
