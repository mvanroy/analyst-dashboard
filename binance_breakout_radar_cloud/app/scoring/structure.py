from __future__ import annotations

import pandas as pd

from app.scoring.base import EngineResult, average, metric


def score(df: pd.DataFrame, config: dict) -> EngineResult:
    params = config.get("structure", {})
    lookback = int(params.get("lookback_bars", 100))
    near_resistance_pct = float(params.get("near_resistance_pct", 1.0))
    near_support_pct = float(params.get("near_support_pct", 1.0))
    min_gap = int(params.get("distinct_test_min_gap_bars", 8))
    coil_bars = max(5, int(params.get("coil_recent_bars", 12)))
    exclude_recent = max(1, int(params.get("resistance_exclude_recent_bars", 1)))
    prior_end = max(lookback, len(df) - exclude_recent)
    prior_start = max(0, prior_end - lookback)
    look = df.iloc[prior_start:prior_end]
    price = float(df["close"].iloc[-1])
    swing_lows = _swing_lows(df, params)
    swing_highs = _swing_highs(df, params)
    resistance, resistance_source = _select_resistance(
        price=price,
        swing_highs=[(idx, value) for idx, value in swing_highs if prior_start <= idx < prior_end],
        fallback_high=float(look["high"].max()),
        near_pct=near_resistance_pct,
        max_distance_pct=float(params.get("breakout_distance_weak_pct", 10)),
        min_gap=min_gap,
    )
    support = float(look["low"].min())
    distance = (resistance - price) / resistance * 100 if resistance else 999.0
    recent_base = df.iloc[-coil_bars:]
    atr = float(df["atr14"].iloc[-1]) if "atr14" in df.columns and pd.notna(df["atr14"].iloc[-1]) else 0.0
    base_range = float(recent_base["high"].max() - recent_base["low"].min())
    base_tight_atr = base_range / atr if atr else None
    base_extension_atr = (price - float(recent_base["low"].min())) / atr if atr else None
    body_overlap = _body_overlap_ratio(recent_base)
    volume_dryup = _volume_dryup_ratio(df, coil_bars)
    higher_lows = sum(1 for left, right in zip(swing_lows[-5:], swing_lows[-4:]) if right[1] > left[1])
    resistance_tests = _distinct_level_touches(
        [
            (idx, value)
            for idx, value in swing_highs
            if prior_start <= idx < prior_end and _within_pct(value, resistance, near_resistance_pct)
        ],
        min_gap,
    )
    recent_closes = df["close"].iloc[-30:]
    near_resistance = float(
        (
            (recent_closes >= resistance * (1 - near_resistance_pct / 100))
            & (recent_closes <= resistance * (1 + near_resistance_pct / 100))
        ).mean()
        * 100
    )
    first_range = look.iloc[:30]["high"].max() - look.iloc[:30]["low"].min()
    last_range = look.iloc[-30:]["high"].max() - look.iloc[-30:]["low"].min()
    contraction = float((first_range - last_range) / first_range * 100) if first_range else 0.0
    support_holds = _distinct_level_touches(
        [(idx, value) for idx, value in swing_lows if idx >= len(df) - lookback and value <= support * (1 + near_support_pct / 100)],
        min_gap,
    )
    near_support = look[look["low"] <= support * (1 + near_support_pct / 100)]
    wick = 0.0
    if not near_support.empty:
        candle_range = (near_support["high"] - near_support["low"]).replace(0, pd.NA)
        wick = float(((near_support[["open", "close"]].min(axis=1) - near_support["low"]) / candle_range * 100).max())

    metrics = {
        "Higher Lows Count": metric(higher_lows, 100 if higher_lows >= 3 else 75 if higher_lows == 2 else 50 if higher_lows == 1 else 0, "higher lows"),
        "Resistance Test Count": metric(resistance_tests, 100 if resistance_tests >= 3 else 75 if resistance_tests == 2 else 50 if resistance_tests == 1 else 0, "tests"),
        "Time Near Resistance": metric(near_resistance, 100 if near_resistance >= 30 else 75 if near_resistance >= 20 else 50 if near_resistance >= 10 else 0, "near resistance"),
        "Triangle / Trendline Convergence": metric(contraction, 100 if contraction >= 30 else 75 if contraction >= 15 else 50 if contraction >= 0 else 0, "range contraction"),
        "Support Holds": metric(support_holds, 100 if support_holds >= 3 else 75 if support_holds == 2 else 50 if support_holds == 1 else 0, "holds"),
        "Lower Wick Rejection": metric(wick, 100 if wick >= 40 else 75 if wick >= 25 else 50 if wick >= 10 else 0, "lower wick"),
        "Breakout Level Distance": metric(distance, _distance_score(distance, near_resistance_pct), "distance"),
        "Base Tightness ATR": metric(base_tight_atr, _base_tightness_score(base_tight_atr, params), "recent range / ATR"),
        "Base Extension ATR": metric(base_extension_atr, _base_extension_score(base_extension_atr, params), "price from base low / ATR"),
        "Body Overlap Tightness": metric(body_overlap, _body_overlap_score(body_overlap, params), "body overlap"),
        "Volume Dry-Up Into Base": metric(volume_dryup, _volume_dryup_score(volume_dryup, params), "recent volume / prior volume"),
        "_resistance": resistance,
        "_resistance_source": resistance_source,
        "_resistance_excluded_recent_bars": exclude_recent,
        "_coil_recent_bars": coil_bars,
        "_support": support,
    }
    uncapped_score = round(average([v["score"] for k, v in metrics.items() if not k.startswith("_")]), 2)
    cap_above = float(params.get("cap_score_if_distance_above_pct", 6))
    cap_score = float(params.get("capped_structure_score", 50))
    was_capped = distance > cap_above and uncapped_score > cap_score
    if was_capped:
        metrics["_uncapped_score"] = uncapped_score
        metrics["_distance_cap_applied"] = True
        metrics["Breakout Level Distance"]["bucket"] = "distance cap applied"
        scored_score = cap_score
    else:
        scored_score = uncapped_score
    if base_extension_atr is not None and base_extension_atr > float(params.get("max_base_extension_atr_for_coil", 3.5)):
        scored_score = min(scored_score, float(params.get("base_extension_cap_score", 55)))
        metrics["_base_extension_cap_applied"] = True
    if body_overlap < float(params.get("body_overlap_weak", 0.25)):
        scored_score = min(scored_score, float(params.get("body_overlap_fail_cap_score", 55)))
        metrics["_body_overlap_cap_applied"] = True
    scored = [v["score"] for k, v in metrics.items() if not k.startswith("_")]
    evidence = [f"Price is {distance:.2f}% below resistance"] if 0 <= distance <= 3 else []
    if -near_resistance_pct <= distance < 0:
        evidence.append(f"Price is {abs(distance):.2f}% above prior resistance")
    if contraction >= 30:
        evidence.append(f"Range contraction is {contraction:.1f}%")
    if base_tight_atr is not None and base_tight_atr <= float(params.get("base_tight_atr_moderate", 3.0)):
        evidence.append(f"Recent base is tight at {base_tight_atr:.2f} ATR")
    if body_overlap >= float(params.get("body_overlap_moderate", 0.40)):
        evidence.append(f"Recent candle bodies overlap tightly ({body_overlap:.2f})")
    if volume_dryup is not None and volume_dryup <= float(params.get("volume_dryup_moderate", 0.90)):
        evidence.append(f"Volume has dried into the base ({volume_dryup:.2f}x prior)")
    missing = []
    if distance > 6:
        missing.append(f"Price is {distance:.2f}% below resistance")
    if distance < -near_resistance_pct:
        missing.append(f"Price is already {abs(distance):.2f}% above prior resistance")
    if near_resistance < 10:
        missing.append("Not enough closes near resistance")
    if base_tight_atr is not None and base_tight_atr > float(params.get("base_tight_atr_weak", 4.0)):
        missing.append(f"Recent base is too loose at {base_tight_atr:.2f} ATR")
    if base_extension_atr is not None and base_extension_atr > float(params.get("max_base_extension_atr_for_coil", 3.5)):
        missing.append(f"Price has already travelled {base_extension_atr:.2f} ATR from the base low")
    if body_overlap < float(params.get("body_overlap_weak", 0.25)):
        missing.append(f"Recent candle bodies are not overlapping tightly ({body_overlap:.2f})")
    if volume_dryup is not None and volume_dryup > float(params.get("volume_dryup_weak", 1.10)):
        missing.append(f"Volume is not drying into the base ({volume_dryup:.2f}x prior)")
    if was_capped:
        missing.append(f"Structure capped because price is {distance:.2f}% from resistance")
    return EngineResult("Structural Pressure", round(scored_score, 2), metrics, evidence, missing)


def _swing_lows(df: pd.DataFrame, params: dict) -> list[tuple[int, float]]:
    lows = []
    reset = df.reset_index(drop=True)
    left = int(params.get("swing_left_bars", 2))
    right = int(params.get("swing_right_bars", 2))
    for idx in range(left, len(reset) - right):
        if reset["low"].iloc[idx] < reset["low"].iloc[idx - left : idx].min() and reset["low"].iloc[idx] <= reset["low"].iloc[idx + 1 : idx + 1 + right].min():
            lows.append((idx, float(reset["low"].iloc[idx])))
    return lows


def _swing_highs(df: pd.DataFrame, params: dict) -> list[tuple[int, float]]:
    highs = []
    reset = df.reset_index(drop=True)
    left = int(params.get("swing_left_bars", 2))
    right = int(params.get("swing_right_bars", 2))
    for idx in range(left, len(reset) - right):
        if reset["high"].iloc[idx] > reset["high"].iloc[idx - left : idx].max() and reset["high"].iloc[idx] >= reset["high"].iloc[idx + 1 : idx + 1 + right].max():
            highs.append((idx, float(reset["high"].iloc[idx])))
    return highs


def _distinct_level_touches(points: list[tuple[int, float]], min_gap: int) -> int:
    count = 0
    last_idx = -10_000
    for idx, _ in sorted(points):
        if idx - last_idx >= min_gap:
            count += 1
            last_idx = idx
    return count


def _select_resistance(
    price: float,
    swing_highs: list[tuple[int, float]],
    fallback_high: float,
    near_pct: float,
    max_distance_pct: float,
    min_gap: int,
) -> tuple[float, str]:
    if not swing_highs:
        return fallback_high, "prior_window_high"

    candidates = []
    for idx, level in swing_highs:
        distance = (level - price) / level * 100 if level else 999.0
        if distance > max_distance_pct or distance < -near_pct:
            continue
        touches = _distinct_level_touches(
            [(touch_idx, value) for touch_idx, value in swing_highs if _within_pct(value, level, near_pct)],
            min_gap,
        )
        candidates.append(
            {
                "level": level,
                "touches": touches,
                "abs_distance": abs(distance),
                "idx": idx,
            }
        )
    if not candidates:
        return fallback_high, "prior_window_high"
    selected = sorted(candidates, key=lambda item: (-item["touches"], item["abs_distance"], -item["idx"]))[0]
    return float(selected["level"]), "prior_swing_high_cluster"


def _within_pct(value: float, level: float, pct: float) -> bool:
    if not level:
        return False
    return abs(value / level - 1) * 100 <= pct


def _distance_score(distance: float, near_pct: float) -> int:
    if -near_pct <= distance <= 3:
        return 100
    if -near_pct * 1.5 <= distance <= 6:
        return 75
    if -near_pct * 2 <= distance <= 10:
        return 50
    return 0


def _base_tightness_score(value: float | None, params: dict) -> int | None:
    if value is None:
        return None
    if value <= float(params.get("base_tight_atr_strong", 2.0)):
        return 100
    if value <= float(params.get("base_tight_atr_moderate", 3.0)):
        return 75
    if value <= float(params.get("base_tight_atr_weak", 4.0)):
        return 50
    return 0


def _base_extension_score(value: float | None, params: dict) -> int | None:
    if value is None:
        return None
    max_extension = float(params.get("max_base_extension_atr_for_coil", 3.5))
    if value <= max_extension * 0.45:
        return 100
    if value <= max_extension * 0.70:
        return 75
    if value <= max_extension:
        return 50
    return 0


def _body_overlap_score(value: float, params: dict) -> int:
    if value >= float(params.get("body_overlap_strong", 0.55)):
        return 100
    if value >= float(params.get("body_overlap_moderate", 0.40)):
        return 75
    if value >= float(params.get("body_overlap_weak", 0.25)):
        return 50
    return 0


def _volume_dryup_score(value: float | None, params: dict) -> int | None:
    if value is None:
        return None
    if value <= float(params.get("volume_dryup_strong", 0.70)):
        return 100
    if value <= float(params.get("volume_dryup_moderate", 0.90)):
        return 75
    if value <= float(params.get("volume_dryup_weak", 1.10)):
        return 50
    return 0


def _body_overlap_ratio(df: pd.DataFrame) -> float:
    if len(df) < 2:
        return 0.0
    bodies = pd.DataFrame(
        {
            "low": df[["open", "close"]].min(axis=1),
            "high": df[["open", "close"]].max(axis=1),
        }
    ).reset_index(drop=True)
    overlaps = []
    for idx in range(1, len(bodies)):
        current_low = float(bodies["low"].iloc[idx])
        current_high = float(bodies["high"].iloc[idx])
        prior_low = float(bodies["low"].iloc[idx - 1])
        prior_high = float(bodies["high"].iloc[idx - 1])
        union = max(current_high, prior_high) - min(current_low, prior_low)
        overlap = min(current_high, prior_high) - max(current_low, prior_low)
        overlaps.append(max(0.0, overlap) / union if union else 1.0)
    return float(sum(overlaps) / len(overlaps)) if overlaps else 0.0


def _volume_dryup_ratio(df: pd.DataFrame, recent_bars: int) -> float | None:
    prior_start = max(0, len(df) - recent_bars - 20)
    prior_end = max(0, len(df) - recent_bars)
    prior = df["volume"].iloc[prior_start:prior_end].mean()
    recent = df["volume"].iloc[-recent_bars:].mean()
    if pd.isna(prior) or not prior:
        return None
    return float(recent / prior)
