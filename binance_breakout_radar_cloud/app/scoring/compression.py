from __future__ import annotations

import pandas as pd

from app.indicators import percentile_rank
from app.scoring.base import EngineResult, average, low_percentile_score, metric


def score(df: pd.DataFrame, config: dict) -> EngineResult:
    lookback = int(config["scan"].get("percentile_lookback", 100))
    params = config.get("compression", {})
    metrics = {}
    checks = [
        ("ATR Percentile", "atr14", 20, 35, 60, 70),
        ("Bollinger Band Width Percentile", "bb_width", 20, 35, 60, 70),
        ("Historical Volatility Percentile", "hv20", 25, 40, 60, 75),
        ("Donchian Width Percentile", "donchian_width", 25, 40, 60, 75),
        ("Keltner Width Percentile", "keltner_width", 25, 40, 60, 75),
        ("Standard Deviation Percentile", "std_pct", 25, 40, 60, 75),
    ]
    scores = []
    evidence = []
    missing = []
    for label, column, strong, moderate, weak, fakeout in checks:
        raw = percentile_rank(df[column], lookback)
        points, bucket = low_percentile_score(raw, strong, moderate, weak, fakeout)
        metrics[label] = metric(raw, points, bucket)
        scores.append(points)
        if bucket in {"strong", "moderate"}:
            evidence.append(f"{label} is {raw:.1f} percentile ({bucket})")
        elif bucket in {"fakeout/already expanded", "elevated"}:
            missing.append(f"{label} is elevated at {raw:.1f} percentile")

    prior = df["range20"].iloc[-120:-20].median()
    current = df["range20"].iloc[-1]
    ratio = float(current / prior) if prior else None
    if ratio is None:
        points, bucket = None, "missing"
    elif ratio <= 0.60:
        points, bucket = 100, "strong"
    elif ratio <= 0.80:
        points, bucket = 75, "moderate"
    elif ratio <= 1.10:
        points, bucket = 50, "weak"
    elif ratio > 1.25:
        points, bucket = 0, "already expanded"
    else:
        points, bucket = 25, "elevated"
    metrics["Range Compression Ratio"] = metric(ratio, points, bucket)
    scores.append(points)
    if bucket in {"strong", "moderate"}:
        evidence.append(f"Range compression ratio is {ratio:.2f}")
    elif bucket in {"already expanded", "elevated"}:
        missing.append(f"Range compression ratio is {ratio:.2f}")

    raw_score = round(average(scores), 2)
    strong_or_moderate = sum(
        1 for item in metrics.values()
        if item["score"] is not None and item["score"] >= 75
    )
    strong_count = sum(
        1 for item in metrics.values()
        if item["score"] is not None and item["score"] >= 100
    )
    final_score = raw_score
    min_agree = int(params.get("min_strong_or_moderate_metrics", 4))
    if strong_or_moderate < min_agree:
        final_score = min(final_score, 50)
        missing.append(f"Only {strong_or_moderate} compression metrics are strong/moderate; need {min_agree}")
    atr_pct = metrics["ATR Percentile"]["raw"]
    bb_pct = metrics["Bollinger Band Width Percentile"]["raw"]
    expanded_cap = float(params.get("expanded_cap_score", 45))
    if atr_pct is not None and atr_pct > float(params.get("cap_score_if_atr_percentile_above", 70)):
        final_score = min(final_score, expanded_cap)
        missing.append(f"ATR percentile already expanded at {atr_pct:.1f}")
    if bb_pct is not None and bb_pct > float(params.get("cap_score_if_bb_width_percentile_above", 70)):
        final_score = min(final_score, expanded_cap)
        missing.append(f"BB width percentile already expanded at {bb_pct:.1f}")
    if ratio is not None and ratio > float(params.get("require_range_ratio_below", 1.10)):
        final_score = min(final_score, float(params.get("range_fail_cap_score", 55)))
        missing.append(f"Range ratio {ratio:.2f} does not prove compression")
    metrics["_raw_average_score"] = raw_score
    metrics["_strong_or_moderate_count"] = strong_or_moderate
    metrics["_strong_count"] = strong_count
    return EngineResult("Compression", round(final_score, 2), metrics, evidence, missing)
