"""Agents: AgentMessageBus — topic-based publish/subscribe message bus."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from ACTosha.agents.state import AgentEvent


@dataclass
class AgentMessage:
    """Message published on the agent message bus."""

    topic: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AgentMessageBus:
    """Thread-safe topic-based publish/subscribe message bus.

    Topics:
        market.opportunity   — ScannerAgent → PortfolioAgent
        backtest.completed    — BacktestAgent → PortfolioAgent
        trade.executed        — Executor → PortfolioAgent
        portfolio.rebalance   — PortfolioAgent → Executor
        alert.signal          — any → TelegramNotifier
    """

    _instance: AgentMessageBus | None = None
    _lock = threading.Lock()

    def __new__(cls) -> AgentMessageBus:
        # Singleton per process
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._subscribers: dict[str, list[Callable[[AgentMessage], None]]] = (
            defaultdict(list)
        )
        self._history: dict[str, list[AgentMessage]] = defaultdict(list)
        self._history_lock = threading.Lock()
        self._sub_lock = threading.Lock()

    def publish(self, topic: str, message: AgentMessage) -> None:
        """Publish a message to all subscribers of the topic.

        Args:
            topic:   Topic name (e.g. "market.opportunity")
            message: AgentMessage to deliver
        """
        with self._sub_lock:
            callbacks = list(self._subscribers.get(topic, []))
        import sys
        print(f"[BUS DEBUG] publish topic={topic!r} msg.source={message.source!r} n_subs={len(callbacks)}", file=sys.stderr)

        for callback in callbacks:
            try:
                callback(message)
            except Exception as e:
                print(f"[BUS DEBUG] callback {callback!r} raised {e}", file=sys.stderr)
                pass  # Swallow callback errors

        with self._history_lock:
            self._history[topic].append(message)

    def subscribe(
        self, topic: str, callback: Callable[[AgentMessage], None]
    ) -> None:
        """Subscribe a callback to a topic.

        Args:
            topic:    Topic name to subscribe to.
            callback: Callable that receives AgentMessage.
        """
        with self._sub_lock:
            self._subscribers[topic].append(callback)

    def unsubscribe(
        self, topic: str, callback: Callable[[AgentMessage], None]
    ) -> None:
        """Remove a callback from a topic."""
        with self._sub_lock:
            if topic in self._subscribers:
                self._subscribers[topic] = [
                    cb for cb in self._subscribers[topic] if cb != callback
                ]

    def get_history(
        self, topic: str, limit: int = 100
    ) -> list[AgentMessage]:
        """Return recent messages for a topic.

        Args:
            topic:  Topic name.
            limit: Maximum number of messages to return. Default: 100.

        Returns:
            List of recent AgentMessage objects (most recent last).
        """
        with self._history_lock:
            return list(self._history.get(topic, [])[-limit:])


__all__ = ["AgentMessageBus", "AgentMessage"]