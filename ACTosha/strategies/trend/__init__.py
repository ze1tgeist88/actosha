"""Strategies: Trend following submodule."""

from ACTosha.strategies.trend.ema_cross import EMACrossStrategy
from ACTosha.strategies.trend.supertrend import SupertrendStrategy
from ACTosha.strategies.trend.trendline_break import TrendlineBreakStrategy

__all__ = ["EMACrossStrategy", "SupertrendStrategy", "TrendlineBreakStrategy"]