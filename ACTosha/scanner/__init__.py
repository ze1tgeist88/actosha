"""Scanner module — market scanning for trading opportunities.

Public API
----------
MarketScanner : base scanner class
Opportunity   : detected opportunity dataclass
PatternScanner  : chart patterns + candlestick detection
IndicatorScanner : RSI, Bollinger, MACD, Stochastic signals
VolumeScanner   : volume anomalies and surges
"""

from ACTosha.scanner.base import MarketScanner, Opportunity
from ACTosha.scanner.pattern_scanner import PatternScanner
from ACTosha.scanner.indicator_scanner import IndicatorScanner
from ACTosha.scanner.volume_scanner import VolumeScanner, scan_volume_surge

__all__ = [
    "MarketScanner",
    "Opportunity",
    "PatternScanner",
    "IndicatorScanner",
    "VolumeScanner",
    "scan_volume_surge",
]
