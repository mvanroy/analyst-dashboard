from __future__ import annotations

import pandas as pd

from app.indicators import percentile_rank, slope
from app.scoring.base import EngineResult, average, high_percentile_score, metric


def score(df: pd.DataFrame, config: dict, structure_metrics: dict | None = None) -> EngineResult:
    params = config.get("participation", {})
    last = df.iloc[-1]
    vol20 = df["volume"].rolling(20).mean().iloc[-1]
    volstd20 = df["volume"].rolling(20).std().iloc[-1]
    rel_volume = float(last["volume"] / vol20) if vol20 else 0.0
    z_score = float((last["volume"] - vol20) / volstd20) if volstd20 else 0.0
    volume_pct = percentile_rank(df["volume"], int(config["scan"].get("percentile_lookback", 100)))
    volume_trend = float(df["volume"].rolling(5).mean().iloc[-1] / vol20) if vol20 else 0.0
    obv_slope = slope(df["obv"], 20)
    obv_slope_5 = slope(df["obv"], 5)
    cmf = float(last["cmf20"]) if pd.notna(last["cmf20"]) else 0.0
    vwap_slope = slope(df["vwap"], 5)
    price = float(last["close"])
    vwap = float(last["vwap"])
    candle_range = float(last["high"] - last["low"])
    close_position = ((last["close"] - last["low"]) / candle_range * 100) if candle_range else 0.0
    upper_wick = ((last["high"] - max(last["open"], last["close"])) / candle_range * 100) if candle_range else 0.0
    vwap_distance = (price / vwap - 1) if vwap else 0.0
    vwap_near_pct = float(params.get("vwap_near_pct", 0.005))
    reclaim_close_position = float(params.get("vwap_reclaim_close_position_pct", 65))

    items = {}
    items["Relative Volume"] = _band(rel_volume, [(1.5, 100, "strong"), (1.2, 75, "moderate"), (0.8, 50, "weak")], "negative")
    items["Volume Z Score"] = _band(z_score, [(2.0, 100, "strong"), (1.0, 75, "moderate"), (-0.5, 50, "weak")], "negative")
    pscore, pbucket = high_percentile_score(volume_pct)
    items["Volume Percentile"] = metric(volume_pct, pscore, pbucket)
    items["Volume Trend 5/20"] = _band(volume_trend, [(1.25, 100, "strong"), (1.10, 75, "moderate"), (0.90, 50, "weak")], "negative")
    coil_context = _coil_context(structure_metrics, params)
    items["Coil RVOL Context"] = metric(
        {
            "relative_volume": rel_volume,
            "coil_quality_good": coil_context["good"],
            "coil_checks": coil_context["checks"],
        },
        _coil_rvol_score(rel_volume, coil_context["good"], params),
        _coil_rvol_bucket(rel_volume, coil_context["good"], params),
    )
    if obv_slope > 0 and obv_slope_5 > obv_slope:
        items["OBV Trend"] = metric(obv_slope, 100, "positive and rising")
    elif obv_slope > 0:
        items["OBV Trend"] = metric(obv_slope, 75, "positive but flat")
    elif abs(obv_slope) < df["volume"].mean() * 0.05:
        items["OBV Trend"] = metric(obv_slope, 50, "neutral")
    else:
        items["OBV Trend"] = metric(obv_slope, 0, "falling")
    if cmf >= 0.10:
        items["Chaikin Money Flow"] = metric(cmf, 100, "strong")
    elif cmf >= 0:
        items["Chaikin Money Flow"] = metric(cmf, 75, "moderate")
    elif cmf >= -0.05:
        items["Chaikin Money Flow"] = metric(cmf, 50, "weak")
    else:
        items["Chaikin Money Flow"] = metric(cmf, 0, "negative")
    if price > vwap and vwap_slope > 0:
        items["VWAP Relationship"] = metric({"price": price, "vwap": vwap, "vwap_slope": vwap_slope, "distance": vwap_distance}, 100, "above VWAP and rising")
    elif price > vwap:
        items["VWAP Relationship"] = metric({"price": price, "vwap": vwap, "vwap_slope": vwap_slope, "distance": vwap_distance}, 75, "above VWAP")
    elif abs(vwap_distance) <= vwap_near_pct and (vwap_slope > 0 or close_position >= reclaim_close_position):
        items["VWAP Relationship"] = metric(
            {"price": price, "vwap": vwap, "vwap_slope": vwap_slope, "distance": vwap_distance},
            75,
            "near VWAP with reclaim behaviour",
        )
    elif abs(vwap_distance) <= vwap_near_pct:
        items["VWAP Relationship"] = metric({"price": price, "vwap": vwap, "vwap_slope": vwap_slope, "distance": vwap_distance}, 50, "near VWAP")
    else:
        items["VWAP Relationship"] = metric({"price": price, "vwap": vwap, "vwap_slope": vwap_slope, "distance": vwap_distance}, 0, "below VWAP")

    raw_score = round(average([v["score"] for v in items.values()]), 2)
    final_score = raw_score
    constructive = sum(1 for v in items.values() if v["score"] and v["score"] >= float(params.get("constructive_score", 75)))
    min_constructive = int(params.get("min_constructive_metrics", 3))
    evidence = [f"{k}: {v['bucket']}" for k, v in items.items() if v["score"] and v["score"] >= 75]
    missing = [f"{k}: {v['bucket']}" for k, v in items.items() if v["score"] == 0]
    if constructive < min_constructive:
        final_score = min(final_score, float(params.get("constructive_miss_cap_score", 55)))
        missing.append(f"Only {constructive} participation metrics are constructive; need {min_constructive}")
    hard_below_vwap = vwap_distance < -vwap_near_pct and vwap_slope <= 0 and close_position < reclaim_close_position
    if hard_below_vwap:
        final_score = min(final_score, float(params.get("vwap_below_cap_score", 45)))
        missing.append("Price is meaningfully below VWAP without reclaim behaviour")
    deep_negative_cmf = cmf < float(params.get("cmf_deep_negative_threshold", -0.10))
    if deep_negative_cmf:
        final_score = min(final_score, float(params.get("cmf_deep_negative_cap_score", 45)))
        missing.append("CMF is deeply negative, so volume is not proving accumulation")
    has_volume_spike = rel_volume >= 1.2 or z_score >= 1.0 or (volume_pct is not None and volume_pct >= 60)
    rejection = upper_wick > float(params.get("rejection_upper_wick_pct", 45)) or close_position < float(params.get("rejection_close_position_pct", 50))
    if has_volume_spike and rejection:
        final_score = min(final_score, float(params.get("volume_spike_rejection_cap_score", 50)))
        missing.append("Volume is paired with candle rejection, not constructive entry")
    items["_raw_average_score"] = raw_score
    items["_constructive_count"] = constructive
    items["_close_position_pct"] = close_position
    items["_upper_wick_pct"] = upper_wick
    items["_vwap_distance_pct"] = vwap_distance * 100
    items["_hard_below_vwap_cap_applied"] = hard_below_vwap
    items["_deep_negative_cmf_cap_applied"] = deep_negative_cmf
    return EngineResult("Participation", round(final_score, 2), items, evidence, missing)


def _band(value: float, bands: list[tuple[float, int, str]], negative_label: str) -> dict:
    for threshold, points, label in bands:
        if value >= threshold:
            return metric(value, points, label)
    return metric(value, 0, negative_label)


def _coil_context(structure_metrics: dict | None, params: dict) -> dict:
    if not structure_metrics:
        return {"good": False, "checks": {"structure_metrics": "missing"}}

    checks = {
        "base_tightness": _metric_score(structure_metrics, "Base Tightness ATR")
        >= float(params.get("coil_context_min_base_tightness_score", 75)),
        "base_extension": _metric_score(structure_metrics, "Base Extension ATR")
        >= float(params.get("coil_context_min_base_extension_score", 50)),
        "body_overlap": _metric_score(structure_metrics, "Body Overlap Tightness")
        >= float(params.get("coil_context_min_body_overlap_score", 50)),
        "near_trigger_resistance": _metric_score(structure_metrics, "Breakout Level Distance")
        >= float(params.get("coil_context_min_distance_score", 75)),
        "resistance_pressure": max(
            _metric_score(structure_metrics, "Resistance Test Count"),
            _metric_score(structure_metrics, "Time Near Resistance"),
        )
        >= float(params.get("coil_context_min_resistance_pressure_score", 50)),
        "not_distance_capped": not bool(structure_metrics.get("_distance_cap_applied")),
        "not_extension_capped": not bool(structure_metrics.get("_base_extension_cap_applied")),
        "not_body_overlap_capped": not bool(structure_metrics.get("_body_overlap_cap_applied")),
    }
    return {"good": all(checks.values()), "checks": checks}


def _coil_rvol_score(rel_volume: float, coil_quality_good: bool, params: dict) -> int | None:
    if not coil_quality_good:
        return None
    if rel_volume >= float(params.get("coil_context_strong_rvol_threshold", 1.5)):
        return 100
    if rel_volume >= float(params.get("coil_context_rvol_threshold", 1.3)):
        return int(params.get("coil_context_rvol_score", 75))
    if rel_volume >= 1.0:
        return 50
    return 0


def _coil_rvol_bucket(rel_volume: float, coil_quality_good: bool, params: dict) -> str:
    if not coil_quality_good:
        return "ignored without valid coil context"
    if rel_volume >= float(params.get("coil_context_strong_rvol_threshold", 1.5)):
        return "strong participation inside valid coil"
    if rel_volume >= float(params.get("coil_context_rvol_threshold", 1.3)):
        return "participation beginning inside valid coil"
    if rel_volume >= 1.0:
        return "early but not constructive"
    return "no constructive participation"


def _metric_score(metrics: dict, name: str) -> float:
    value = metrics.get(name, {})
    score = value.get("score") if isinstance(value, dict) else None
    return float(score) if score is not None else 0.0
