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
    release_score, release_bucket, release_checks = _release_energy_score(metrics, ratio, df, params)
    metrics["Release Energy"] = metric(release_checks, release_score, release_bucket)
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
    if release_score >= float(params.get("release_energy_min_score", 75)):
        release_floor = float(params.get("release_energy_floor_score", 60))
        if final_score < release_floor:
            final_score = release_floor
        evidence.append("Compression has started releasing with constructive expansion")
    elif release_score >= 50:
        evidence.append("Compression release is starting, but confirmation is incomplete")
    metrics["_raw_average_score"] = raw_score
    metrics["_strong_or_moderate_count"] = strong_or_moderate
    metrics["_strong_count"] = strong_count
    return EngineResult("Compression", round(final_score, 2), metrics, evidence, missing)


def _release_energy_score(metrics: dict, ratio: float | None, df: pd.DataFrame, params: dict) -> tuple[int, str, dict]:
    recent = df.iloc[-1]
    prior = df.iloc[-4:-1]
    close = float(recent["close"])
    open_price = float(recent["open"])
    high = float(recent["high"])
    low = float(recent["low"])
    candle_range = high - low
    close_pos = (close - low) / candle_range * 100 if candle_range else 0.0
    body_pct = abs(close - open_price) / candle_range * 100 if candle_range else 0.0
    vol20 = df["volume"].rolling(20).mean().iloc[-1]
    rel_volume = float(recent["volume"] / vol20) if vol20 else 0.0
    prior_low_vol = any(
        (metrics.get(name, {}).get("raw") is not None and metrics[name]["raw"] <= float(params.get("release_recent_compression_percentile", 45)))
        for name in ["Bollinger Band Width Percentile", "Donchian Width Percentile", "Keltner Width Percentile", "Standard Deviation Percentile"]
    )
    atr_expanding = _metric_raw(metrics, "ATR Percentile") >= float(params.get("release_expansion_percentile", 60))
    width_expanding = any(
        _metric_raw(metrics, name) >= float(params.get("release_expansion_percentile", 60))
        for name in ["Bollinger Band Width Percentile", "Donchian Width Percentile", "Keltner Width Percentile"]
    )
    range_expanding = ratio is not None and ratio >= float(params.get("release_range_ratio_min", 1.05))
    closes_up = int((prior["close"] < close).sum()) if not prior.empty else 0
    constructive_candle = close_pos >= float(params.get("release_close_position_pct", 60)) and body_pct >= float(params.get("release_body_pct", 35))
    volume_confirming = rel_volume >= float(params.get("release_rel_volume_min", 1.0))
    checks = {
        "recent_compression_present": prior_low_vol,
        "atr_expanding": atr_expanding,
        "width_expanding": width_expanding,
        "range_expanding": range_expanding,
        "constructive_candle": constructive_candle,
        "volume_confirming": volume_confirming,
        "closes_up_count": closes_up,
        "close_position_pct": round(close_pos, 2),
        "body_pct": round(body_pct, 2),
        "relative_volume": round(rel_volume, 2),
    }
    passed = sum(1 for key in ["recent_compression_present", "atr_expanding", "width_expanding", "range_expanding", "constructive_candle", "volume_confirming"] if checks[key])
    if passed >= 5:
        return 100, "release confirmed", checks
    if passed >= 4:
        return 75, "release building", checks
    if passed >= 3:
        return 50, "release early", checks
    return 0, "no release proof", checks


def _metric_raw(metrics: dict, name: str) -> float:
    raw = metrics.get(name, {}).get("raw")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0
