"""ScannerAgent — periodic market scanning and opportunity alerts."""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

import pandas as pd

from ACTosha.agents.base import TradingAgent
from ACTosha.agents.message_bus import AgentMessage, AgentMessageBus
from ACTosha.agents.state import AgentAction, AgentEvent, AgentState
from ACTosha.scanner import (
    IndicatorScanner,
    MarketScanner,
    Opportunity,
    PatternScanner,
    VolumeScanner,
)
from ACTosha.datafeeder import DataFeeder


# ------------------------------------------------------------------
# ScannerAgent configuration
# ------------------------------------------------------------------

@dataclass
class ScannerConfig:
    """Configuration for ScannerAgent.

    Attributes
    ----------
    interval_minutes : float
        How often to run a scan cycle, in minutes. Default: 15.
    min_strength : float
        Minimum opportunity strength to publish. Default: 0.6.
    symbols : list[str]
        List of symbols to scan. Default: major perps.
    timeframes : list[str]
        OHLCV timeframes to scan. Default: ["15m", "1h", "4h"].
    scanner_types : list[str]
        Which scanner types to run. Options: indicator, pattern, volume.
        Default: ["indicator", "pattern", "volume"].
    """

    interval_minutes: float = 15.0
    min_strength: float = 0.6
    symbols: list[str] = field(
        default_factory=lambda: ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    )
    timeframes: list[str] = field(default_factory=lambda: ["15m", "1h", "4h"])
    scanner_types: list[str] = field(
        default_factory=lambda: ["indicator", "pattern", "volume"]
    )


# ------------------------------------------------------------------
# ScannerAgent
# ------------------------------------------------------------------

class ScannerAgent(TradingAgent):
    """Autonomous market scanner agent.

    ScannerAgent periodically scans configured markets for trading
    opportunities and publishes any qualifying ``Opportunity`` objects
    to the ``market.opportunity`` topic on the :class:`AgentMessageBus`.

    Parameters
    ----------
    config : ScannerConfig
        Scanner configuration.
    data_feeder : DataFeeder | None
        DataFeeder instance for loading OHLCV data. If None, a default
        DataFeeder is constructed.
    message_bus : AgentMessageBus | None
        Message bus instance. Uses the singleton if None.

    Example
    -------
    >>> config = ScannerConfig(interval_minutes=15.0, min_strength=0.7)
    >>> agent = ScannerAgent(config=config)
    >>> agent.start()
    >>> # ... agent runs periodic scans in background thread ...
    >>> agent.stop()
    """

    def __init__(
        self,
        config: ScannerConfig | None = None,
        data_feeder: DataFeeder | None = None,
        message_bus: AgentMessageBus | None = None,
    ) -> None:
        self.config = config or ScannerConfig()
        self._data_feeder = data_feeder
        self._bus = message_bus or AgentMessageBus()
        self._running = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_scan_time: datetime | None = None
        self._last_opportunities: list[Opportunity] = []
        self._scan_count = 0

        # Lazy-initialised scanners (created on first step to allow
        # DataFeeder to be set first)
        self._scanners: dict[str, MarketScanner] = {}
        self._data_feeder_initialized = False

    # ------------------------------------------------------------------
    # TradingAgent interface
    # ------------------------------------------------------------------

    @property
    def agent_id(self) -> str:
        return "scanner"

    @property
    def role(self) -> str:
        return "scanner"

    def step(self, state: AgentState) -> AgentAction:
        """Run a scan cycle and publish any detected opportunities.

        Parameters
        ----------
        state : AgentState
            Current agent state (used for context; scanner is read-only).

        Returns
        -------
        AgentAction
            action_type="scan" with payload containing:
            - opportunities: list of Opportunity dicts
            - scan_count: total scans run
            - scan_time: timestamp of this scan
        """
        with self._lock:
            if not self._data_feeder_initialized:
                self._init_data_feeder()
                self._data_feeder_initialized = True

            opportunities = self._run_scan_cycle()
            self._last_opportunities = opportunities
            self._last_scan_time = datetime.utcnow()
            self._scan_count += 1

        # Publish each opportunity to the bus
        for opp in opportunities:
            msg = AgentMessage(
                topic="market.opportunity",
                source=self.agent_id,
                data=self._opp_to_dict(opp),
            )
            self._bus.publish("market.opportunity", msg)

        return AgentAction(
            action_type="scan",
            payload={
                "opportunities": [self._opp_to_dict(o) for o in opportunities],
                "scan_count": self._scan_count,
                "scan_time": self._last_scan_time.isoformat()
                if self._last_scan_time
                else None,
                "num_opportunities": len(opportunities),
            },
            confidence=(
                float(len(opportunities) > 0)
                if opportunities
                else 0.0
            ),
        )

    def receive_signal(self, event: AgentEvent) -> None:
        """Handle incoming events — currently a no-op for ScannerAgent.

        ScannerAgent operates on its own schedule; external signals can
        trigger an ad-hoc scan by calling ``step()`` directly.
        """
        pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scanning thread.

        Does nothing if already running.
        """
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._background_loop,
                name="ScannerAgent-loop",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the background scanning thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._thread is not None:
                self._thread.join(timeout=5.0)
                self._thread = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_data_feeder(self) -> None:
        """Lazily initialise the DataFeeder if one wasn't provided."""
        if self._data_feeder is None:
            # Import here to avoid circular imports at module level
            from ACTosha.datafeeder import DataFeeder

            self._data_feeder = DataFeeder(mode="future")

    def _background_loop(self) -> None:
        """Continuously scan on the configured interval until stop()."""
        interval_secs = self.config.interval_minutes * 60.0
        while True:
            with self._lock:
                if not self._running:
                    break

            # Run one scan cycle
            try:
                self.step(AgentState())
            except Exception as e:
                logger.error("[ScannerAgent] scan error: %s", e)

            # Sleep in small increments so stop() is responsive
            slept = 0.0
            while slept < interval_secs:
                time.sleep(1.0)
                slept += 1.0
                with self._lock:
                    if not self._running:
                        break

    def _run_scan_cycle(self) -> list[Opportunity]:
        """Run all configured scanners across all symbols and timeframes.

        Returns
        -------
        list[Opportunity]
            All opportunities with strength >= min_strength.
        """
        all_opportunities: list[Opportunity] = []

        for timeframe in self.config.timeframes:
            for symbol in self.config.symbols:
                opportunities = self._scan_symbol(symbol, timeframe)
                all_opportunities.extend(opportunities)

        # Filter by strength threshold
        filtered = [
            o
            for o in all_opportunities
            if o.strength >= self.config.min_strength
        ]

        # Sort by strength descending
        filtered.sort(key=lambda o: o.strength, reverse=True)
        return filtered

    def _scan_symbol(
        self, symbol: str, timeframe: str
    ) -> list[Opportunity]:
        """Scan a single symbol+timeframe across all enabled scanner types.

        Returns
        -------
        list[Opportunity]
        """
        opportunities: list[Opportunity] = []

        # Load data
        df = self._load_ohlcv(symbol, timeframe)
        if df is None or len(df) < 50:
            return []

        # --- Indicator scanner ---
        if "indicator" in self.config.scanner_types:
            scanner = self._get_scanner("indicator", timeframe)
            try:
                opps = scanner.scan_all([symbol], {symbol: df})
                opportunities.extend(opps)
            except Exception:
                pass

        # --- Pattern scanner ---
        if "pattern" in self.config.scanner_types:
            scanner = self._get_scanner("pattern", timeframe)
            try:
                opps = scanner.scan_all([symbol], {symbol: df})
                opportunities.extend(opps)
            except Exception:
                pass

        # --- Volume scanner ---
        if "volume" in self.config.scanner_types:
            scanner = self._get_scanner("volume", timeframe)
            try:
                opps = scanner.scan_all([symbol], {symbol: df})
                opportunities.extend(opps)
            except Exception:
                pass

        return opportunities

    def _get_scanner(
        self, scanner_type: str, timeframe: str
    ) -> MarketScanner:
        """Return or create a cached scanner instance for a type+timeframe."""
        key = f"{scanner_type}:{timeframe}"
        if key not in self._scanners:
            min_str = self.config.min_strength
            if scanner_type == "indicator":
                self._scanners[key] = IndicatorScanner(
                    timeframe=timeframe, min_strength=min_str
                )
            elif scanner_type == "pattern":
                self._scanners[key] = PatternScanner(
                    timeframe=timeframe, min_strength=min_str
                )
            elif scanner_type == "volume":
                self._scanners[key] = VolumeScanner(
                    timeframe=timeframe, min_strength=min_str
                )
            else:
                raise ValueError(f"Unknown scanner type: {scanner_type}")
        return self._scanners[key]

    def _load_ohlcv(
        self, symbol: str, timeframe: str
    ) -> pd.DataFrame | None:
        """Load OHLCV data for a symbol+timeframe via the data feeder.

        Returns None on failure.
        """
        try:
            # Last 500 bars of 15m ≈ 5 days; 7 days safety margin
            import pandas as pd
            since_ms = int((pd.Timestamp.utcnow() - pd.Timedelta(days=7)).timestamp() * 1000)
            df = self._data_feeder.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since_ms,
                limit=500,
            )
            return df
        except Exception:
            return None

    @staticmethod
    def _opp_to_dict(opp: Opportunity) -> dict[str, Any]:
        """Convert an Opportunity to a dict for message bus transport."""
        return {
            "symbol": opp.symbol,
            "pattern": opp.pattern,
            "timeframe": opp.timeframe,
            "strength": opp.strength,
            "entry_zone": opp.entry_zone,
            "metadata": opp.metadata,
        }


__all__ = ["ScannerAgent", "ScannerConfig"]
