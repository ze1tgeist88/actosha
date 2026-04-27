"""TradingAgent abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ACTosha.agents.state import AgentAction, AgentEvent, AgentState


class TradingAgent(ABC):
    """Abstract base class for all trading agents.

    Agents operate autonomously, receiving signals and producing actions.
    Communication happens via :class:`AgentMessageBus
    <ACTosha.agents.message_bus.AgentMessageBus>`.

    Each agent has a fixed ``role`` that classifies its primary responsibility:

    ===============  ========================================================
    Role            Description
    ===============  ========================================================
    ``scanner``     Monitors markets and emits opportunity alerts
    ``backtest``    Runs backtests and returns results
    ``portfolio``   Manages capital allocation and rebalancing
    ===============  ========================================================

    Lifecycle
    ----------
    1. Agent is instantiated with its configuration.
    2. Agent registers its subscriptions on the message bus (optional).
    3. Caller invokes ``step(state)`` in a loop or on a schedule.
    4. Incoming messages from other agents are delivered via
       ``receive_signal(event)``.
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique agent identifier within the system."""
        ...

    @property
    def role(self) -> str:
        """Agent role: scanner | backtest | portfolio.

        Override in subclass if the default "unknown" is incorrect.
        """
        return "unknown"

    @abstractmethod
    def step(self, state: "AgentState") -> "AgentAction":
        """Execute one agent step given the current state.

        This is the primary entry point for agent execution. Implementations
        should be idempotent — calling ``step`` multiple times with the same
        ``state`` should not produce duplicate side effects.

        Parameters
        ----------
        state : AgentState
            Current state snapshot from the executor.

        Returns
        -------
        AgentAction
            The action the agent wants to perform. The caller is responsible
            for routing this action appropriately (e.g. to the executor or
            back to the message bus).
        """
        ...

    def receive_signal(self, event: "AgentEvent") -> None:
        """Handle an incoming agent event / signal from the message bus.

        Default implementation accepts the event and updates internal state.
        Subclasses can override to implement custom event handling.

        Parameters
        ----------
        event : AgentEvent
            Incoming event published on a subscribed topic.
        """
        pass

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"agent_id={self.agent_id!r} role={self.role!r}>"
        )


__all__ = ["TradingAgent"]
