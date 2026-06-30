from __future__ import annotations

import pandas as pd

from app.scoring.base import EngineResult, average, metric


def score(df: pd.DataFrame, trigger_resistance: float | None, invalidation: float | None, config: dict) -> EngineResult:
    params = config.get("magnitude", {})
    if not params.get("enabled", True):
        return EngineResult("Magnitude", 0.0, {}, [], ["Magnitude disabled"])
    price = float(df["close"].iloc[-1])
    atr = float(df["atr14"].iloc[-1]) if pd.notna(df["atr14"].iloc[-1]) else 0.0
    lookback = int(params.get("base_lookback_bars", 100))
    recent = int(params.get("base_recent_bars", 30))
    base = df.iloc[-lookback:]
    recent_base = df.iloc[-recent:]
    base_height = float(base["high"].max() - base["low"].min())
    recent_height = float(recent_base["high"].max() - recent_base["low"].min())
    base_height_atr = base_height / atr if atr else 0.0
    recent_height_atr = recent_height / atr if atr else 0.0
    expected_mid_atr = (float(params.get("expected_range_atr_min", 3.5)) + float(params.get("expected_range_atr_max", 6.1))) / 2
    directional_fraction = float(params.get("directional_target_fraction", 0.55))
    atr_target_move = expected_mid_atr * directional_fraction * atr
    measured_move = min(base_height, atr_target_move) if atr_target_move else base_height
    expansion_move = max(
        measured_move,
        recent_height * float(params.get("recent_range_target_fraction", 0.80)),
        atr * float(params.get("min_tp2_atr_multiple", 2.2)),
    )
    raw_target = price + measured_move
    expansion_target = price + expansion_move
    prior_supply = df.iloc[-lookback:-recent]
    overhead_floor = max(price, trigger_resistance or price)
    overhead = prior_supply[prior_supply["high"] > overhead_floor]["high"].sort_values()
    nearest_supply = float(overhead.iloc[0]) if not overhead.empty else None
    conservative_target = min(raw_target, nearest_supply) if nearest_supply else raw_target
    realistic_target = max(expansion_target, conservative_target)
    air_above_pct = (realistic_target / price - 1) * 100 if price else 0.0
    risk_pct = ((price - invalidation) / price * 100) if invalidation and invalidation < price else None
    reward_pct = (realistic_target / price - 1) * 100 if realistic_target else 0.0
    reward_risk = reward_pct / risk_pct if risk_pct and risk_pct > 0 else None
    nearby_supply = nearest_supply is not None and nearest_supply < expansion_target

    base_score = _base_score(base_height_atr, params)
    air_score = 100 if air_above_pct >= float(params.get("air_above_good_pct", 6)) else 75 if air_above_pct >= float(params.get("air_above_min_pct", 3)) else 0
    rr_score = 100 if reward_risk is not None and reward_risk >= float(params.get("reward_risk_good", 2.5)) else 75 if reward_risk is not None and reward_risk >= float(params.get("reward_risk_min", 1.5)) else 0
    supply_score = 75 if nearby_supply else 100
    metrics = {
        "ATR": metric(atr, None, "scale input"),
        "Expected Range ATR": metric(expected_mid_atr, None, "scale input"),
        "Trigger Resistance": metric(trigger_resistance, None, "local trigger"),
        "Base Height ATR": metric(base_height_atr, base_score, "base height"),
        "Recent Base Height ATR": metric(recent_height_atr, None, "context"),
        "Raw ATR/Base Target": metric(raw_target, None, "measured target"),
        "Expansion Target": metric(expansion_target, None, "release target"),
        "Nearest Supply Target": metric(nearest_supply, None, "structure context"),
        "Conservative Target": metric(conservative_target, None, "tp1 context"),
        "Realistic Target": metric(realistic_target, None, "tp2 expansion target"),
        "Air Above %": metric(air_above_pct, air_score, "air above"),
        "Reward To Invalidation": metric(reward_risk, rr_score, "reward/risk"),
        "Nearby Supply": metric(nearby_supply, supply_score, "nearby supply noted" if nearby_supply else "clear expansion target"),
    }
    scored = [base_score, air_score, rr_score, supply_score]
    evidence = []
    missing = []
    if base_score >= 75:
        evidence.append(f"Base height is {base_height_atr:.2f} ATR")
    else:
        missing.append(f"Base height is only {base_height_atr:.2f} ATR")
    if air_score >= 75:
        evidence.append(f"Air above is {air_above_pct:.2f}%")
    else:
        missing.append(f"Air above is only {air_above_pct:.2f}%")
    if rr_score >= 75:
        evidence.append(f"Reward to invalidation is {reward_risk:.2f}R")
    else:
        missing.append("Reward to invalidation is below threshold")
    if nearby_supply:
        evidence.append("Nearby supply noted, but TP2 uses expansion runway")
    return EngineResult("Magnitude", round(average(scored), 2), metrics, evidence, missing)


def _base_score(base_height_atr: float, params: dict) -> int:
    if base_height_atr >= float(params.get("large_base_atr", 3.5)):
        return 100
    if base_height_atr >= float(params.get("moderate_base_atr", 2.5)):
        return 75
    if base_height_atr >= float(params.get("small_base_atr", 1.5)):
        return 50
    return 0
