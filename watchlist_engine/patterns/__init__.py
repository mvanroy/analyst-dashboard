"""
Pattern Registry
=================
All pattern detectors register here. Add new patterns by:
1. Creating a file like patterns/my_pattern.py with a detect() function
2. Importing it and adding to the PATTERNS list below
"""
from . import pullback_short
from . import breakdown_continuation
from . import bull_bear_flag
from . import oi_divergence
from . import mean_reversion
from . import breakout_oi
from . import rsi_divergence
from . import cvd_divergence

PATTERNS = [
    {"id": "pullback_short", "name": "Pullback Short into Supply", "detect": pullback_short.detect, "version": "1.0"},
    {"id": "breakdown_continuation", "name": "Breakdown Continuation", "detect": breakdown_continuation.detect, "version": "1.0"},
    {"id": "flag", "name": "Bull/Bear Flag", "detect": bull_bear_flag.detect, "version": "1.0"},
    {"id": "oi_divergence", "name": "OI Divergence", "detect": oi_divergence.detect, "version": "1.0"},
    {"id": "mean_reversion", "name": "Mean Reversion Long", "detect": mean_reversion.detect, "version": "1.0"},
    {"id": "breakout_oi", "name": "Breakout w/ OI Confirmation", "detect": breakout_oi.detect, "version": "1.0"},
    {"id": "rsi_divergence", "name": "RSI Divergence", "detect": rsi_divergence.detect, "version": "1.0"},
    {"id": "cvd_divergence", "name": "CVD Divergence", "detect": cvd_divergence.detect, "version": "1.0"},
]


def detect_all(data: dict) -> list:
    """Run all pattern detectors against a coin's data. Returns list of detected setups."""
    setups = []
    for pattern in PATTERNS:
        try:
            result = pattern["detect"](
                ohlcv_4h=data.get("ohlcv_4h"),
                ohlcv_1h=data.get("ohlcv_1h"),
                oi=data.get("oi"),
                oi_history=data.get("oi_history"),
                funding=data.get("funding"),
                ticker=data.get("ticker"),
                cvd=data.get("cvd"),
                order_book=data.get("order_book"),
            )
            if result is not None:
                result["pattern_id"] = pattern["id"]
                setups.append(result)
        except Exception as e:
            print(f"[ERROR] Pattern {pattern['id']}: {e}", flush=True)
            import traceback
            traceback.print_exc()
    return setups