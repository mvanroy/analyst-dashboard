from __future__ import annotations

import pandas as pd

from app.scoring.base import EngineResult, average, metric


def score(df: pd.DataFrame, config: dict) -> EngineResult:
    params = config.get("momentum", {})
    last = df.iloc[-1]
    rsi = float(last["rsi14"])
    rsi_slope = float(df["rsi14"].iloc[-1] - df["rsi14"].iloc[-6])
    adx = float(last["adx14"])
    adx_slope = float(df["adx14"].iloc[-1] - df["adx14"].iloc[-6])
    macd = float(last["macd_hist"])
    macd_prev = float(df["macd_hist"].iloc[-2])
    roc = float(last["roc10"])
    mfi = float(last["mfi20"])

    metrics = {
        "RSI 14": metric(rsi, _range_score(rsi, [(60, 70, 100), (55, 59.999, 75), (45, 54.999, 50)]), "threshold"),
        "RSI Slope 5": metric(rsi_slope, 100 if rsi_slope >= 5 else 75 if rsi_slope >= 2 else 50 if rsi_slope >= 0 else 0, "slope"),
        "ADX 14": metric(adx, 100 if adx >= 25 and adx_slope > 0 else 75 if 20 <= adx < 25 and adx_slope > 0 else 50 if 15 <= adx < 20 else 0, "trend strength"),
        "ADX Slope 5": metric(adx_slope, 100 if adx_slope >= 3 else 75 if adx_slope >= 1 else 50 if adx_slope >= 0 else 0, "slope"),
        "MACD Histogram": metric(macd, 100 if macd > 0 and macd > macd_prev else 75 if macd > 0 else 50 if abs(macd) < 0.00005 else 0, "histogram"),
        "Rate of Change 10": metric(roc, 100 if roc >= 3 else 75 if roc >= 1 else 50 if roc >= -1 else 0, "roc"),
        "Money Flow Index": metric(mfi, _range_score(mfi, [(55, 70, 100), (50, 54.999, 75), (40, 49.999, 50)]), "threshold"),
    }
    raw_score = round(average([v["score"] for v in metrics.values()]), 2)
    final_score = raw_score
    improving = sum(1 for v in metrics.values() if v["score"] and v["score"] >= float(params.get("improving_score", 75)))
    min_improving = int(params.get("min_improving_metrics", 4))
    evidence = [f"{k}: {v['raw']:.2f}" for k, v in metrics.items() if v["score"] and v["score"] >= 75]
    missing = [f"{k} is weak/negative" for k, v in metrics.items() if v["score"] == 0]
    if improving < min_improving:
        final_score = min(final_score, float(params.get("improving_miss_cap_score", 60)))
        missing.append(f"Only {improving} momentum metrics are improving; need {min_improving}")
    if params.get("require_rsi_slope_positive", True) and rsi_slope <= 0:
        final_score = min(final_score, float(params.get("rsi_slope_cap_score", 55)))
        missing.append(f"RSI slope is not improving ({rsi_slope:.2f})")
    if params.get("require_adx_slope_positive", True) and adx_slope <= 0:
        final_score = min(final_score, float(params.get("adx_slope_cap_score", 55)))
        missing.append(f"ADX slope is not improving ({adx_slope:.2f})")
    if macd < macd_prev:
        final_score = min(final_score, float(params.get("falling_macd_cap_score", 50)))
        missing.append("MACD histogram is deteriorating")
    if rsi > config.get("risk_filters", {}).get("reject_if_rsi_above", 75):
        final_score = min(final_score, float(params.get("overheated_cap_score", 45)))
        missing.append(f"RSI overheated at {rsi:.2f}")
    if mfi > config.get("risk_filters", {}).get("reject_if_mfi_above", 80):
        final_score = min(final_score, float(params.get("overheated_cap_score", 45)))
        missing.append(f"MFI overheated at {mfi:.2f}")
    metrics["_raw_average_score"] = raw_score
    metrics["_improving_count"] = improving
    return EngineResult("Momentum", round(final_score, 2), metrics, evidence, missing)


def _range_score(value: float, ranges: list[tuple[float, float, int]]) -> int:
    for low, high, points in ranges:
        if low <= value <= high:
            return points
    return 0
