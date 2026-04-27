"""DataFeeder module — OHLCV data loading via CCXT.

Public API
----------
AbstractExchangeFeed  : abstract base class
BinanceFeed           : Binance spot + USDM-futures data feeder (PRIMARY)
HyperliquidFeed       : Hyperliquid perpetual data feeder
UnifiedOHLCVSchema    : normalize raw exchange data to unified schema
DataFeeder             : default alias → BinanceFeed (mode='future' perpetuals)
"""

from ACTosha.datafeeder.base import AbstractExchangeFeed
from ACTosha.datafeeder.normalizer import UnifiedOHLCVSchema

try:
    from ACTosha.datafeeder.binance import BinanceFeed

    # PRIMARY default — use BinanceFeed for perpetuals with mode='future'
    DataFeeder = BinanceFeed

    __all__ = [
        "AbstractExchangeFeed",
        "BinanceFeed",
        "HyperliquidFeed",
        "DataFeeder",
        "UnifiedOHLCVSchema",
    ]
except ImportError:
    # ccxt not installed
    __all__ = [
        "AbstractExchangeFeed",
        "UnifiedOHLCVSchema",
    ]
    DataFeeder = None  # type: ignore[assignment]

try:
    from ACTosha.datafeeder.hyperliquid import HyperliquidFeed

    if "BinanceFeed" not in dir():
        __all__.append("HyperliquidFeed")
        DataFeeder = HyperliquidFeed
    else:
        __all__.append("HyperliquidFeed")
except ImportError:
    pass