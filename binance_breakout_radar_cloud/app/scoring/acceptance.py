from __future__ import annotations

import pandas as pd

from app.scoring.base import EngineResult, average, metric


def score(df: pd.DataFrame, resistance: float, config: dict) -> EngineResult:
    params = config.get("acceptance", {})
    last = df.iloc[-1]
    candle_range = float(last["high"] - last["low"])
    close_pos = ((last["close"] - last["low"]) / candle_range * 100) if candle_range else 0.0
    body = (abs(last["close"] - last["open"]) / candle_range * 100) if candle_range else 0.0
    upper = ((last["high"] - max(last["open"], last["close"])) / candle_range * 100) if candle_range else 0.0
    near_closes = int((df["close"].iloc[-10:] >= resistance * 0.98).sum()) if resistance else 0
    prior_range_high = float(df["high"].iloc[-120:-20].max())
    outside = int((df["close"].iloc[-10:] > prior_range_high).sum())
    above_vwap_run = 0
    for above in (df["close"].iloc[::-1] > df["vwap"].iloc[::-1]):
        if above:
            above_vwap_run += 1
        else:
            break

    metrics = {
        "Candle Close Position": metric(close_pos, 100 if close_pos >= 80 else 75 if close_pos >= 65 else 50 if close_pos >= 35 else 0, "close position"),
        "Candle Body %": metric(body, 100 if body >= 60 else 75 if body >= 45 else 50 if body >= 25 else 0, "body"),
        "Upper Wick %": metric(upper, 100 if upper <= 20 else 75 if upper <= 35 else 50 if upper <= 45 else 0, "upper wick"),
        "Consecutive Closes Near Resistance": metric(near_closes, 100 if near_closes >= 3 else 75 if near_closes == 2 else 50 if near_closes == 1 else 0, "near resistance"),
        "Close Outside Range": metric(outside, 100 if outside >= 2 else 75 if outside == 1 else 0, "outside range"),
        "Retest Quality": metric(None, 50, "no retest modelled yet"),
        "VWAP Acceptance": metric(above_vwap_run, 100 if above_vwap_run >= 5 else 75 if above_vwap_run >= 2 else 50 if above_vwap_run >= 1 else 0, "above VWAP run"),
    }
    controlled_candle = close_pos >= 65 and body >= 45 and upper <= 35
    if params.get("near_resistance_requires_controlled_candle", True) and near_closes > 0 and not controlled_candle:
        original = metrics["Consecutive Closes Near Resistance"]["score"]
        metrics["Consecutive Closes Near Resistance"]["score"] = min(original, 50)
        metrics["Consecutive Closes Near Resistance"]["bucket"] = "near resistance without controlled candle"
    raw_score = round(average([v["score"] for v in metrics.values()]), 2)
    final_score = raw_score
    controlled_count = sum(1 for v in metrics.values() if v["score"] and v["score"] >= float(params.get("controlled_score", 75)))
    evidence = [f"{k}: {v['bucket']}" for k, v in metrics.items() if v["score"] and v["score"] >= 75]
    missing = [f"{k}: {v['bucket']}" for k, v in metrics.items() if v["score"] == 0]
    min_controlled = int(params.get("min_controlled_metrics", 4))
    if controlled_count < min_controlled:
        final_score = min(final_score, float(params.get("controlled_miss_cap_score", 60)))
        missing.append(f"Only {controlled_count} acceptance metrics are controlled; need {min_controlled}")
    if upper > 45:
        final_score = min(final_score, float(params.get("upper_wick_rejection_cap_score", 45)))
        missing.append(f"Upper wick rejection is too large at {upper:.1f}%")
    if body < 25:
        final_score = min(final_score, float(params.get("weak_body_cap_score", 55)))
        missing.append(f"Candle body is too weak at {body:.1f}%")
    if params.get("require_vwap_hold_for_valid", True) and above_vwap_run == 0:
        final_score = min(final_score, float(params.get("vwap_fail_cap_score", 50)))
        missing.append("No current VWAP acceptance")
    metrics["_raw_average_score"] = raw_score
    metrics["_controlled_count"] = controlled_count
    metrics["_controlled_candle"] = controlled_candle
    return EngineResult("Price Acceptance", round(final_score, 2), metrics, evidence, missing)
