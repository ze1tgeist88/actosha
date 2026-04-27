"""BacktestEngine — single strategy backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from ACTosha.backtester.simulator import (
    EXCHANGE_FUNDING,
    Fill,
    FillMode,
    FundingPayment,
    Order,
    OrderSide,
    OrderSimulator,
)
from ACTosha.strategies.base import SignalBundle, Strategy


# ------------------------------------------------------------------
# BacktestResult
# ------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Results from a BacktestEngine run.

    Attributes
    ----------
    equity_curve : pd.Series
        Equity (portfolio value) at each timestamp, starting at initial_capital.
    trades : pd.DataFrame
        One row per completed trade. Columns:
        trade_id, timestamp_open, timestamp_close, side, entry_price,
        exit_price, size, pnl, pnl_pct, commission, slippage_cost,
        duration_bars, exit_reason, metadata.
    metrics : dict
        Performance metrics computed by PerformanceMetricsCalculator.
    summary : dict
        High-level backtest summary.
    funding_payments : list[FundingPayment]
        All funding rate payments accrued during the backtest.
    """

    equity_curve: pd.Series = field(default_factory=pd.Series)
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    metrics: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    funding_payments: list[FundingPayment] = field(default_factory=list)


# ------------------------------------------------------------------
# Trade State (internal use)
# ------------------------------------------------------------------

@dataclass
class _Position:
    """Internal position state during backtest."""

    side: Literal["long", "short"]
    entry_price: float
    size: float
    timestamp_open: pd.Timestamp
    trade_id: int


# ------------------------------------------------------------------
# BacktestEngine
# ------------------------------------------------------------------

class BacktestEngine:
    """Backtest a single strategy on historical OHLCV data.

    Parameters
    ----------
    fill_mode : FillMode
        Bar execution model (NEXT_OPEN or HIGH_LOW).
    exchange : str | None
        Exchange name for funding rate lookups (hyperliquid | binance_perp).
        Pass None to disable funding.
    min_trade_size : float
        Minimum notional trade size (in quote currency). Trades below this
        are skipped.
    """

    def __init__(
        self,
        fill_mode: FillMode = FillMode.NEXT_OPEN,
        exchange: str | None = None,
        min_trade_size: float = 10.0,
    ) -> None:
        self.fill_mode = fill_mode
        self.exchange = exchange
        self.min_trade_size = min_trade_size

    def run(
        self,
        strategy: Strategy,
        df: pd.DataFrame,
        initial_capital: float = 10_000.0,
        commission: float = 0.0004,
        slippage: float = 0.0005,
    ) -> BacktestResult:
        """Run a backtest for a single strategy.

        Parameters
        ----------
        strategy : Strategy
            Strategy instance that produces signals via generate_signals().
        df : pd.DataFrame
            OHLCV DataFrame. Must have DatetimeIndex and columns:
            open, high, low, close, volume, timestamp (as index or column).
        initial_capital : float
            Starting capital in quote currency.
        commission : float
            Commission rate as a fraction per trade.
        slippage : float
            Slippage in basis points (e.g. 5 bps = 0.0005).

        Returns
        -------
        BacktestResult
        """
        # --- Validate inputs ---
        if df.empty:
            raise ValueError("OHLCV DataFrame is empty.")
        if len(df) < 2:
            raise ValueError("Need at least 2 bars to run backtest.")

        # Normalize: ensure timestamp is index
        df = _normalize_df(df.copy())

        strategy.validate_df(df)
        signals_bundle = strategy.generate_signals(df)

        # Build a signals lookup keyed by timestamp
        signals_df = signals_bundle.signals
        if signals_df.empty:
            signals_df = _empty_signals_df(df.index)

        # Index alignment
        if not signals_df.index.equals(df.index):
            signals_df = signals_df.reindex(df.index)

        # --- Initialize simulator ---
        slippage_bps = slippage * 10_000.0
        simulator = OrderSimulator(
            commission=commission,
            slippage_bps=slippage_bps,
            fill_mode=self.fill_mode,
            exchange=self.exchange,
        )

        # --- Backtest state ---
        equity = initial_capital
        equity_curve: list[float] = []
        position: _Position | None = None
        trade_id = 0
        trades: list[dict] = []
        funding_payments: list[FundingPayment] = []

        # We iterate from bar 1 (first bar is bar 0 — no trading on first signal)
        bar_times = df.index.tolist()
        bar_values = df.values
        cols = list(df.columns)

        for i in range(len(df)):
            ts = bar_times[i]
            bar = pd.Series(dict(zip(cols, bar_values[i])), index=df.columns)
            prev_ts = bar_times[i - 1] if i > 0 else ts

            # --- Funding while in position ---
            if position is not None:
                funding = simulator.calc_funding_for_position(
                    position_notional=position.size * bar["close"],
                    entry_price=position.entry_price,
                    current_price=bar["close"],
                    bar_timestamp=ts,
                    prev_timestamp=prev_ts,
                )
                funding_payments.extend(funding)
                # Funding cost reduces equity
                for fp in funding:
                    equity -= fp.payment

            # --- Check signal ---
            signal_row = signals_df.iloc[i]
            side = signal_row["side"]
            signal_strength = float(signal_row.get("strength", 0.0))

            if position is None:
                # --- No position — check for entry ---
                if side in ("long", "short") and signal_strength > 0:
                    entry_price = bar["open"]  # placeholder; simulator overrides
                    size = _calc_size_from_signal(
                        entry_price, initial_capital, self.min_trade_size
                    )
                    if size * entry_price < self.min_trade_size:
                        equity_curve.append(equity)
                        continue

                    order = Order(
                        side=OrderSide.LONG if side == "long" else OrderSide.SHORT,
                        price=entry_price,
                        size=size,
                        timestamp=ts,
                    )
                    fill = simulator.fill_order(
                        order, bar, ts, prev_ts
                    )
                    position = _Position(
                        side=side,
                        entry_price=fill.price,
                        size=fill.size,
                        timestamp_open=ts,
                        trade_id=trade_id,
                    )
                    trade_id += 1

            else:
                # --- In position — check for close ---
                close_reason: str | None = None
                should_close = False

                # Manual close signal
                if side == "close":
                    should_close = True
                    close_reason = "signal_close"

                # Stop-loss
                sl = signal_row.get("stop_loss")
                if sl is not None and not pd.isna(sl):
                    if position.side == "long" and bar["low"] <= sl:
                        should_close = True
                        close_reason = "stop_loss"
                    elif position.side == "short" and bar["high"] >= sl:
                        should_close = True
                        close_reason = "stop_loss"

                # Take-profit
                tp = signal_row.get("take_profit")
                if tp is not None and not pd.isna(tp):
                    if position.side == "long" and bar["high"] >= tp:
                        should_close = True
                        close_reason = "take_profit"
                    elif position.side == "short" and bar["low"] <= tp:
                        should_close = True
                        close_reason = "take_profit"

                if should_close:
                    order = Order(
                        side=OrderSide.CLOSE,
                        price=bar["open"],
                        size=position.size,
                        timestamp=ts,
                    )
                    fill = simulator.fill_order(order, bar, ts, prev_ts)

                    pnl = _calc_pnl(position.side, position.entry_price, fill.price, position.size)
                    commission_total = position.size * position.entry_price * commission + fill.commission

                    equity += pnl - commission_total

                    trades.append({
                        "trade_id": position.trade_id,
                        "timestamp_open": position.timestamp_open,
                        "timestamp_close": ts,
                        "side": position.side,
                        "entry_price": position.entry_price,
                        "exit_price": fill.price,
                        "size": position.size,
                        "pnl": pnl,
                        "pnl_pct": pnl / (position.entry_price * position.size) if position.entry_price * position.size > 0 else 0.0,
                        "commission": commission_total,
                        "slippage_cost": fill.slippage_cost,
                        "duration_bars": i - bar_times.index(position.timestamp_open),
                        "exit_reason": close_reason or "unknown",
                        "metadata": {},
                    })
                    position = None

            equity_curve.append(equity)

        # --- Close any residual position at end ---
        if position is not None:
            last_ts = bar_times[-1]
            last_bar = pd.Series(dict(zip(cols, bar_values[-1])), index=df.columns)
            order = Order(
                side=OrderSide.CLOSE,
                price=last_bar["open"],
                size=position.size,
                timestamp=last_ts,
            )
            fill = simulator.fill_order(order, last_bar, last_ts, bar_times[-2])
            pnl = _calc_pnl(position.side, position.entry_price, fill.price, position.size)
            commission_total = position.size * position.entry_price * commission + fill.commission
            equity += pnl - commission_total

            trades.append({
                "trade_id": position.trade_id,
                "timestamp_open": position.timestamp_open,
                "timestamp_close": last_ts,
                "side": position.side,
                "entry_price": position.entry_price,
                "exit_price": fill.price,
                "size": position.size,
                "pnl": pnl,
                "pnl_pct": pnl / (position.entry_price * position.size) if position.entry_price * position.size > 0 else 0.0,
                "commission": commission_total,
                "slippage_cost": fill.slippage_cost,
                "duration_bars": len(df) - 1 - bar_times.index(position.timestamp_open),
                "exit_reason": "end_of_backtest",
                "metadata": {},
            })

        equity_curve.append(equity)

        # --- Build outputs ---
        equity_series = pd.Series(
            equity_curve[: len(df)],
            index=df.index[: len(df)],
            name="equity",
        )

        trades_df = pd.DataFrame(trades) if trades else _empty_trades_df()

        # --- Compute metrics ---
        from ACTosha.backtester.metrics import PerformanceMetricsCalculator
        calc = PerformanceMetricsCalculator()
        metrics = calc.calculate(
            equity_curve=equity_series,
            trades=trades_df,
            initial_capital=initial_capital,
            commission_total=sum(t["commission"] for t in trades) if trades else 0.0,
        )

        summary: dict[str, Any] = {
            "strategy_name": strategy.name,
            "symbol": (strategy.symbols[0] if strategy.symbols else "unknown"),
            "timeframe": strategy.timeframe,
            "start_date": str(df.index[0]) if len(df) > 0 else None,
            "end_date": str(df.index[-1]) if len(df) > 0 else None,
            "num_bars": len(df),
            "num_trades": len(trades),
            "final_equity": round(equity, 2),
            "total_return": round((equity / initial_capital - 1) * 100, 2) if initial_capital > 0 else 0.0,
        }

        return BacktestResult(
            equity_curve=equity_series,
            trades=trades_df,
            metrics=metrics,
            summary=summary,
            funding_payments=funding_payments,
        )


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure df has a proper DatetimeIndex and OHLCV columns."""
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    # Ensure required columns exist
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"DataFrame missing required columns: {missing}")
    return df


def _empty_signals_df(index) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "side": "none",
            "strength": 0.0,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
        },
        index=index,
    )


def _empty_trades_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "trade_id", "timestamp_open", "timestamp_close", "side",
            "entry_price", "exit_price", "size", "pnl", "pnl_pct",
            "commission", "slippage_cost", "duration_bars", "exit_reason",
            "metadata",
        ]
    )


def _calc_size_from_signal(
    entry_price: float,
    capital: float,
    min_size: float,
    risk_fraction: float = 0.02,
) -> float:
    """Calculate notional size based on risk fraction of capital."""
    risk_amount = capital * risk_fraction
    # Assume 2% stop distance
    stop_distance = entry_price * 0.02
    size = risk_amount / stop_distance if stop_distance > 0 else 0.0
    notional = size * entry_price
    if notional < min_size:
        # Use min_size directly (minimal trade)
        size = min_size / entry_price if entry_price > 0 else 0.0
    return max(size, 0.0)


def _calc_pnl(
    side: Literal["long", "short"],
    entry_price: float,
    exit_price: float,
    size: float,
) -> float:
    """PnL for a long or short position."""
    if side == "long":
        return (exit_price - entry_price) * size
    else:
        return (entry_price - exit_price) * size


__all__ = ["BacktestEngine", "BacktestResult"]
