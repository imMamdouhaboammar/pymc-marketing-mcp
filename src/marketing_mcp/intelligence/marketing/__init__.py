"""Marketing domain intelligence modules."""

from .lifecycle import analyze_channel_lifecycles
from .market_structure import analyze_market_structure
from .tracking_quality import analyze_tracking_quality

__all__ = [
    "analyze_channel_lifecycles",
    "analyze_market_structure",
    "analyze_tracking_quality",
]
