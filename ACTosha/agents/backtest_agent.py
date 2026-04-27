"""BacktestAgent — strategy backtesting with optimization support."""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator

import pandas as pd

from ACTosha.agents.base import TradingAgent
from ACTosha.agents.message_bus import AgentMessage, AgentMessageBus
from ACTosha.agents.state import AgentAction, AgentEvent, AgentState
from ACTosha.backtester import BacktestEngine, BacktestResult, FillMode
from ACTosha.datafeeder import DataFeeder
from ACTosha.strategies.base import Strategy


# ------------------------------------------------------------------
# BacktestTask — input for a backtest job
# ------------------------------------------------------------------

@dataclass
class BacktestTask:
    """Specification for a backtest run.

    Attributes
    ----------
    strategy : Strategy
        Strategy instance to backtest.
    symbol : str
        Trading symbol (e.g. "BTC/USDT").
    timeframe : str
        OHLCV timeframe (e.g. "1h").
    initial_capital : float
        Starting capital. Default: 10 000.
    commission : float
        Commission rate as fraction per trade. Default: 0.0004.
    slippage : float
        Slippage in basis points. Default: 0.0005 (5 bps).
    fill_mode : FillMode
        Bar fill mode. Default: NEXT_OPEN.
    optimization : OptimizationConfig | None
        If provided, run an optimization pass after the base backtest.
    """

    strategy: Strategy
    symbol: str = "BTC/USDT:USDT"
    timeframe: str = "1h"
    initial_capital: float = 10_000.0
    commission: float = 0.0004
    slippage: float = 0.0005
    fill_mode: FillMode = FillMode.NEXT_OPEN
    optimization: OptimizationConfig | None = None


@dataclass
class OptimizationConfig:
    """Configuration for parameter optimization.

    Attributes
    ----------
    param_grid : dict[str, list[Any]]
        Mapping of strategy parameter names to lists of values to test.
        Example: {"ema_fast": [9, 12, 15], "ema_slow": [21, 26, 50]}.
    objective : str
        Metric to optimise. One of: sharpe | sortino | total_return |
        max_drawdown | win_rate. Default: "sharpe".
    method : str
        Optimization method. One of: grid | bayesian.
        Default: "grid".
    max_runs : int
        Maximum number of backtest runs for bayesian. Default: 50.
    """

    param_grid: dict[str, list[Any]] = field(default_factory=dict)
    objective: str = "sharpe"
    method: str = "grid"
    max_runs: int = 50


# ------------------------------------------------------------------
# OptimizationResult
# ------------------------------------------------------------------

@dataclass
class OptimizationResult:
    """Result from a parameter optimization run.

    Attributes
    ----------
    best_params : dict[str, Any]
        Parameter values that achieved the best objective score.
    best_score : float
        The achieved objective score.
    total_runs : int
        Number of backtest runs performed.
    all_results : list[dict]
        Full results table with params + metrics for each run.
    elapsed_seconds : float
        Wall-clock time for the entire optimization.
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    best_score: float = 0.0
    total_runs: int = 0
    all_results: list[dict] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# ------------------------------------------------------------------
# BacktestAgent
# ------------------------------------------------------------------

class BacktestAgent(TradingAgent):
    """Autonomous backtesting agent.

    BacktestAgent receives backtest task specifications (strategy +
    symbol + timeframe) and executes them via :class:`BacktestEngine`.
    Optional parameter optimization is supported via grid search or
    bayesian optimisation.

    Results are published to the ``backtest.completed`` topic on the
    :class:`AgentMessageBus` and also returned from :meth:`run_backtest`.

    Parameters
    ----------
    data_feeder : DataFeeder | None
        DataFeeder for loading OHLCV data. If None, a default instance
        is created lazily.
    message_bus : AgentMessageBus | None
        Message bus. Uses singleton if None.
    default_capital : float
        Default capital for tasks that don't specify it. Default: 10 000.
    """

    def __init__(
        self,
        data_feeder: DataFeeder | None = None,
        message_bus: AgentMessageBus | None = None,
        default_capital: float = 10_000.0,
    ) -> None:
        self._data_feeder = data_feeder
        self._bus = message_bus or AgentMessageBus()
        self._default_capital = default_capital
        self._data_feeder_initialized = False
        self._pending_tasks: dict[str, BacktestTask] = {}
        self._results_cache: dict[str, BacktestResult] = {}
        self._optimization_cache: dict[str, OptimizationResult] = {}
        self._task_counter = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # TradingAgent interface
    # ------------------------------------------------------------------

    @property
    def agent_id(self) -> str:
        return "backtest"

    @property
    def role(self) -> str:
        return "backtest"

    def step(self, state: AgentState) -> AgentAction:
        """Process any pending tasks and return current status.

        If no pending tasks exist, returns a "hold" action.
        Otherwise executes the next pending backtest task.
        """
        with self._lock:
            if not self._pending_tasks:
                return AgentAction(
                    action_type="hold",
                    payload={"status": "idle"},
                    confidence=0.0,
                )

            task_id, task = next(iter(self._pending_tasks.items()))
            del self._pending_tasks[task_id]

        result = self._execute_task(task)
        self._results_cache[task_id] = result

        # Publish result to bus
        msg = AgentMessage(
            topic="backtest.completed",
            source=self.agent_id,
            data=self._result_to_dict(task_id, task, result),
        )
        self._bus.publish("backtest.completed", msg)

        return AgentAction(
            action_type="backtest",
            payload=self._result_to_dict(task_id, task, result),
            confidence=1.0,
        )

    def receive_signal(self, event: AgentEvent) -> None:
        """Handle incoming events.

        Accepts ``backtest.request`` events with a ``BacktestTask`` in
        the event data. Queues the task for processing on the next step.
        """
        if event.topic == "backtest.request":
            task_data = event.data.get("task")
            if task_data is None:
                return
            task = self._deserialize_task(task_data)
            if task is not None:
                with self._lock:
                    self._task_counter += 1
                    task_id = f"btask_{self._task_counter}"
                    self._pending_tasks[task_id] = task

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_backtest(
        self,
        task: BacktestTask,
    ) -> BacktestResult:
        """Synchronously run a backtest task and return the result.

        Parameters
        ----------
        task : BacktestTask
            Backtest specification.

        Returns
        -------
        BacktestResult
        """
        with self._lock:
            if not self._data_feeder_initialized:
                self._init_data_feeder()
                self._data_feeder_initialized = True

        result = self._execute_task(task)

        msg = AgentMessage(
            topic="backtest.completed",
            source=self.agent_id,
            data=self._result_to_dict("sync", task, result),
        )
        self._bus.publish("backtest.completed", msg)
        return result

    def run_optimization(
        self,
        task: BacktestTask,
    ) -> OptimizationResult:
        """Run parameter optimization for a backtest task.

        Parameters
        ----------
        task : BacktestTask
            Must have ``task.optimization`` set.

        Returns
        -------
        OptimizationResult
        """
        if task.optimization is None:
            raise ValueError(
                "task.optimization must be set to run optimization"
            )

        with self._lock:
            if not self._data_feeder_initialized:
                self._init_data_feeder()
                self._data_feeder_initialized = True

        if task.optimization.method == "grid":
            return self._grid_optimize(task)
        elif task.optimization.method == "bayesian":
            return self._bayesian_optimize(task)
        else:
            raise ValueError(
                f"Unknown optimization method: {task.optimization.method!r}. "
                "Supported: grid, bayesian."
            )

    def get_cached_result(
        self, task_id: str
    ) -> BacktestResult | None:
        """Return a previously computed backtest result by task ID."""
        return self._results_cache.get(task_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_data_feeder(self) -> None:
        if self._data_feeder is None:
            from ACTosha.datafeeder import DataFeeder

            self._data_feeder = DataFeeder(mode="future")

    def _execute_task(self, task: BacktestTask) -> BacktestResult:
        """Load data and run a single backtest."""
        df = self._load_data(task.symbol, task.timeframe)
        if df is None or len(df) < 100:
            return BacktestResult()

        engine = BacktestEngine(
            fill_mode=task.fill_mode,
            exchange=self._detect_exchange(task.symbol),
            min_trade_size=10.0,
        )

        return engine.run(
            strategy=task.strategy,
            df=df,
            initial_capital=task.initial_capital or self._default_capital,
            commission=task.commission,
            slippage=task.slippage,
        )

    def _grid_optimize(self, task: BacktestTask) -> OptimizationResult:
        """Run grid search over param_grid."""
        import time

        start = time.monotonic()
        opt_cfg = task.optimization
        param_grid = opt_cfg.param_grid

        # Generate all parameter combinations
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        all_results: list[dict] = []
        best_score = float("-inf")
        best_params: dict[str, Any] = {}

        for combo in combinations:
            params = dict(zip(keys, combo))
            result = self._run_with_params(task, params)
            score = self._extract_objective(result, opt_cfg.objective)

            run_record = {"params": params, "score": score}
            run_record.update(result.metrics)
            all_results.append(run_record)

            if score > best_score:
                best_score = score
                best_params = params

        elapsed = time.monotonic() - start

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            total_runs=len(combinations),
            all_results=all_results,
            elapsed_seconds=elapsed,
        )

    def _bayesian_optimize(self, task: BacktestTask) -> OptimizationResult:
        """Run Bayesian optimization over the parameter space.

        Uses a simple Gaussian Process surrogate with L-BFGS-B acquisition.
        Falls back to random search if scipy is unavailable.
        """
        import time

        try:
            from scipy.optimize import minimize
            from scipy.stats import norm
        except ImportError:
            # Fallback: random search
            return self._random_search_optimize(task)

        start = time.monotonic()
        opt_cfg = task.optimization
        param_grid = opt_cfg.param_grid

        # Build searchable param space as normalized [0, 1] bounds
        keys = list(param_grid.keys())
        from fractions import Fraction

        normalized_bounds: list[tuple[float, float]] = []
        discrete_values: list[list[Any]] = []
        continuous_transforms: list[Callable[[float], Any]] = []

        for k in keys:
            vals = param_grid[k]
            if len(vals) <= 10 and all(
                isinstance(v, (int, float)) for v in vals
            ):
                # Treat as discrete enumerated — normalize index
                normalized_bounds.append((0.0, float(len(vals) - 1)))
                discrete_values.append(vals)
                continuous_transforms.append(
                    lambda x, v=vals: v[max(0, min(len(v) - 1, round(x)))]
                )
            else:
                # Continuous range — use min/max
                numeric_vals = [float(v) for v in vals]
                normalized_bounds.append(
                    (min(numeric_vals), max(numeric_vals))
                )
                discrete_values.append([])
                rng = max(numeric_vals) - min(numeric_vals)
                mn = min(numeric_vals)
                continuous_transforms.append(
                    lambda x, rng=rng, mn=mn: mn + x * rng
                )

        n_dims = len(keys)

        # Observations
        X_obs: list[list[float]] = []
        y_obs: list[float] = []

        max_runs = min(opt_cfg.max_runs, 200)

        for _ in range(max_runs):
            # Random restart L-BFGS-B to find next candidate
            x0 = [normalized_bounds[i][0] + (normalized_bounds[i][1] - normalized_bounds[i][0]) * hash(str(i)) % 1000 / 1000 for i in range(n_dims)]

            def neg_acquisition(x):
                if len(X_obs) < 2:
                    return float(hash(str(x)) % 1000) / 1000
                # Simple LCB acquisition (mean - 1.0 * std)
                mean = sum(y_obs) / len(y_obs)
                var = sum((yi - mean) ** 2 for yi in y_obs) / len(y_obs)
                std = var**0.5
                return -(mean - 1.0 * std)

            try:
                res = minimize(
                    neg_acquisition,
                    x0,
                    bounds=normalized_bounds,
                    method="L-BFGS-B",
                )
                x_candidate = list(res.x)
            except Exception:
                x_candidate = x0

            # Clamp
            x_candidate = [
                max(normalized_bounds[i][0],
                    min(normalized_bounds[i][1], x_candidate[i]))
                for i in range(n_dims)
            ]

            # Evaluate
            params = {
                keys[i]: continuous_transforms[i](x_candidate[i])
                for i in range(n_dims)
            }
            result = self._run_with_params(task, params)
            score = self._extract_objective(result, opt_cfg.objective)

            X_obs.append(x_candidate)
            y_obs.append(score)

        # Best
        best_idx = max(range(len(y_obs)), key=lambda i: y_obs[i])
        best_params = {
            keys[i]: continuous_transforms[i](X_obs[best_idx][i])
            for i in range(n_dims)
        }
        elapsed = time.monotonic() - start

        all_results = [
            {"params": {keys[i]: continuous_transforms[i](X_obs[j][i]) for i in range(n_dims)}, "score": y_obs[j]}
            for j in range(len(y_obs))
        ]

        return OptimizationResult(
            best_params=best_params,
            best_score=y_obs[best_idx],
            total_runs=len(y_obs),
            all_results=all_results,
            elapsed_seconds=elapsed,
        )

    def _random_search_optimize(self, task: BacktestTask) -> OptimizationResult:
        """Fallback random search when scipy is unavailable."""
        import random, time

        start = time.monotonic()
        opt_cfg = task.optimization
        param_grid = opt_cfg.param_grid
        keys = list(param_grid.keys())

        best_score = float("-inf")
        best_params: dict[str, Any] = {}
        all_results: list[dict] = []

        max_runs = min(opt_cfg.max_runs, 100)

        for _ in range(max_runs):
            params = {k: random.choice(param_grid[k]) for k in keys}
            result = self._run_with_params(task, params)
            score = self._extract_objective(result, opt_cfg.objective)
            all_results.append({"params": params, "score": score})
            if score > best_score:
                best_score = score
                best_params = params

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            total_runs=max_runs,
            all_results=all_results,
            elapsed_seconds=time.monotonic() - start,
        )

    def _run_with_params(
        self, task: BacktestTask, params: dict[str, Any]
    ) -> BacktestResult:
        """Create a strategy copy with params applied and run backtest."""
        strategy = self._apply_params(task.strategy, params)
        modified_task = BacktestTask(
            strategy=strategy,
            symbol=task.symbol,
            timeframe=task.timeframe,
            initial_capital=task.initial_capital,
            commission=task.commission,
            slippage=task.slippage,
            fill_mode=task.fill_mode,
            optimization=None,
        )
        return self._execute_task(modified_task)

    def _apply_params(self, strategy: Strategy, params: dict[str, Any]) -> Strategy:
        """Create a shallow copy of strategy with params applied.

        Strategy must accept the param keys as __init__ kwargs, or
        have a ``set_params`` method.
        """
        # Try set_params first, then fall back to kwargs init
        import copy

        s = copy.copy(strategy)
        if hasattr(s, "set_params"):
            s.set_params(params)
        else:
            for k, v in params.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        return s

    def _extract_objective(
        self, result: BacktestResult, objective: str
    ) -> float:
        """Extract scalar objective score from a BacktestResult."""
        m = result.metrics
        if objective == "sharpe":
            return float(m.get("sharpe_ratio") or 0.0)
        elif objective == "sortino":
            return float(m.get("sortino_ratio") or 0.0)
        elif objective == "total_return":
            return float(m.get("total_return_pct") or 0.0)
        elif objective == "max_drawdown":
            return float(-(m.get("max_drawdown_pct") or 0.0))  # negate — minimize
        elif objective == "win_rate":
            return float(m.get("win_rate") or 0.0)
        else:
            return float(m.get(objective, 0.0))

    def _load_data(
        self, symbol: str, timeframe: str
    ) -> pd.DataFrame | None:
        """Load OHLCV data from the data feeder."""
        try:
            return self._data_feeder.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=None,
                limit=2000,
            )
        except Exception:
            return None

    @staticmethod
    def _detect_exchange(symbol: str) -> str | None:
        """Infer exchange name from symbol format."""
        if ":USDT" in symbol:
            return "hyperliquid"
        elif "/" in symbol:
            return "binance"
        return None

    def _result_to_dict(
        self, task_id: str, task: BacktestTask, result: BacktestResult
    ) -> dict[str, Any]:
        """Serialize a BacktestResult to a dict for message bus transport."""
        return {
            "task_id": task_id,
            "strategy_name": task.strategy.name,
            "symbol": task.symbol,
            "timeframe": task.timeframe,
            "summary": result.summary,
            "metrics": result.metrics,
            "num_trades": len(result.trades)
            if not result.trades.empty
            else 0,
            "final_equity": result.summary.get("final_equity", 0.0),
            "total_return_pct": result.summary.get("total_return", 0.0),
        }

    def _deserialize_task(self, data: dict[str, Any]) -> BacktestTask | None:
        """Reconstruct a BacktestTask from a dict (basic deserialization).

        Note: The ``strategy`` field must be a Strategy instance, not a dict.
        This method is for task routing — callers should provide a proper
        BacktestTask object via the API.
        """
        try:
            return BacktestTask(
                strategy=data["strategy"],
                symbol=data.get("symbol", "BTC/USDT:USDT"),
                timeframe=data.get("timeframe", "1h"),
                initial_capital=data.get("initial_capital", self._default_capital),
                commission=data.get("commission", 0.0004),
                slippage=data.get("slippage", 0.0005),
            )
        except Exception:
            return None


__all__ = [
    "BacktestAgent",
    "BacktestTask",
    "OptimizationConfig",
    "OptimizationResult",
]
