from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.alerts.rules import format_alert
from app.alerts.telegram import send_message


def main() -> None:
    row = SimpleNamespace(
        symbol="HMSTRUSDT",
        classification="Developing Setup",
        overall_score=68.4,
        current_price=0.00474,
        compression_score=78,
        structural_pressure_score=72,
        participation_score=64,
        momentum_score=58,
        price_acceptance_score=52,
        breakout_level_resistance=0.00482,
        invalidated_below=0.00451,
        distance_to_resistance_pct=1.2,
        raw_metrics={
            "magnitude": {"ATR": {"raw": 0.00022}, "Realistic Target": {"raw": 0.00542}},
            "structural_pressure": {"Time Near Resistance": {"raw": 24.0}},
            "participation": {"Relative Volume": {"raw": 1.31}},
            "smart_money": {"Taker Buy Ratio": {"raw": 53.1}, "Open Interest Change 1H": {"raw": 2.4}},
            "market_context": {"correlation_1h": 0.72, "benchmark_change_pct": -0.84, "relationship": "btc drag risk"},
        },
    )
    result = send_message(format_alert(row))
    print(result)


if __name__ == "__main__":
    main()
