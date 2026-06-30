from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path


def write_json(rows, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as f:
        json.dump([asdict(row) for row in rows], f, indent=2, default=str)


def write_csv(rows, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank",
        "symbol",
        "current_price",
        "overall_score_display",
        "classification",
        "compression_score_display",
        "structural_pressure_score_display",
        "participation_score_display",
        "momentum_score_display",
        "smart_money_score_display",
        "price_acceptance_score_display",
        "magnitude_score_display",
        "strongest_engine",
        "weakest_engine",
        "breakout_level_resistance",
        "invalidated_below",
        "distance_to_resistance_pct",
        "quote_volume_24h",
        "key_evidence",
        "missing_evidence",
        "notes",
        "scanned_at",
    ]
    with target.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            data = asdict(row)
            data["key_evidence"] = " | ".join(row.key_evidence)
            data["missing_evidence"] = " | ".join(row.missing_evidence)
            writer.writerow({field: data.get(field) for field in fields})


def print_summary(rows) -> None:
    if not rows:
        print("No radar rows produced.")
        return
    print(f"{'#':>3} {'Symbol':<14} {'Overall':>12} {'Class':<24} {'Strongest':<20} {'Weakest':<20}")
    for row in rows:
        print(
            f"{row.rank:>3} {row.symbol:<14} {row.overall_score_display:>12} "
            f"{row.classification:<24} {row.strongest_engine:<20} {row.weakest_engine:<20}"
        )
