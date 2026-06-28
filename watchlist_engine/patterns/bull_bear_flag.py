"""
Pattern: Bull & Bear Flags
===========================
Detects: Strong impulse (flagpole) → tight consolidation (flag) → continuation break

Bull Flag: impulse up → consolidation → break above = long (but short setup)
Bear Flag: impulse down → consolidation → break below = short

Scoring:
  - Flagpole strength (size + speed of impulse)
  - Flag tightness (retrace depth, candle compression)
  - OI/volume confirmation
"""
import numpy as np
from typing import Dict, Any, Optional

from ..config import FLAG_PATTERNS as CFG
from ..indicators import ema, atr


def detect(
    ohlcv_4h: Optional[Dict],
    ohlcv_1h: Optional[Dict],
    oi: Optional[float],
    oi_history: Optional[Dict],
    funding: Optional[float],
    ticker: Optional[Dict],
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Detect both bull and bear flags. Returns the stronger one if found."""
    if ohlcv_4h is None:
        return None

    df4h = ohlcv_4h
    if len(df4h) < 40:
        return None

    close4h = df4h['close'].values
    high4h = df4h['high'].values
    low4h = df4h['low'].values
    last_price = float(close4h[-1])

    result = detect_flag(close4h, high4h, low4h, last_price, "bull", oi, oi_history, funding)
    if result:
        return result

    result = detect_flag(close4h, high4h, low4h, last_price, "bear", oi, oi_history, funding)
    return result


def detect_flag(close, high, low, last_price, direction, oi, oi_history, funding):
    """
    Detect a flag pattern in the given direction.
    direction: 'bull' (flagpole up) or 'bear' (flagpole down)
    """
    is_bull = direction == "bull"
    lookback = min(CFG["lookback_candles"], len(close))
    window = lookback

    # ─── 1. Find the flagpole ────────────────────────────────────────
    # Look for the strongest N-candle move in the lookback window
    if is_bull:
        # Flagpole up: find max rise over 5-8 candles
        pole_window = min(8, window // 2)
        best_rise = 0
        best_start = 0
        for i in range(window - pole_window):
            rise = (close[i + pole_window] - close[i]) / close[i] * 100
            if rise > best_rise:
                best_rise = rise
                best_start = i
        pole_end = best_start + pole_window
        pole_high = float(np.max(high[best_start:pole_end + 1]))
        pole_low = float(np.min(low[best_start:pole_end + 1]))
        pole_mid = (pole_high + pole_low) / 2
    else:
        # Flagpole down: find max drop
        pole_window = min(8, window // 2)
        best_drop = 0
        best_start = 0
        for i in range(window - pole_window):
            drop = (close[i] - close[i + pole_window]) / close[i] * 100
            if drop > best_drop:
                best_drop = drop
                best_start = i
        pole_end = best_start + pole_window
        pole_high = float(np.max(high[best_start:pole_end + 1]))
        pole_low = float(np.min(low[best_start:pole_end + 1]))
        pole_mid = (pole_high + pole_low) / 2

    pole_size_pct = best_rise if is_bull else best_drop
    if pole_size_pct < CFG["min_flagpole_pct"]:
        return None  # Not enough impulse

    # ─── 2. Check for consolidation (the flag) ───────────────────────
    # After the pole, price should consolidate/pull back
    flag_start = pole_end
    flag_candles = close[flag_start:]
    flag_highs = high[flag_start:]
    flag_lows = low[flag_start:]

    if len(flag_candles) < CFG["min_flag_candles"]:
        return None

    flag_low_val = float(np.min(flag_lows))
    flag_high_val = float(np.max(flag_highs))
    flag_range_pct = (flag_high_val - flag_low_val) / flag_low_val * 100

    # For bull flag: consolidation should retrace < 50% of the pole
    # For bear flag: consolidation should retrace < 50% of the pole (bounce up)
    if is_bull:
        retrace_from_pole = (pole_high - flag_low_val) / (pole_high - pole_low) * 100
        broken_out = last_price > flag_high_val * 1.005
        near_break = flag_high_val - last_price < (flag_high_val - flag_low_val) * 0.2
    else:
        retrace_from_pole = (flag_high_val - pole_low) / (pole_high - pole_low) * 100
        broken_out = last_price < flag_low_val * 0.995
        near_break = last_price - flag_low_val < (flag_high_val - flag_low_val) * 0.2

    if retrace_from_pole > CFG["max_retrace_pct"]:
        return None  # Too much retrace — not a flag, more like a V reversal

    # ─── Scoring ─────────────────────────────────────────────────────
    score = 0
    evidence = []
    missing = []
    warnings = []

    # Pole strength (max 3 pts)
    if pole_size_pct >= CFG["strong_pole_pct"]:
        score += 3
    elif pole_size_pct >= CFG["min_flagpole_pct"] * 1.5:
        score += 2
    else:
        score += 1
    evidence.append(f"Flagpole: {pole_size_pct:.1f}% {'rise' if is_bull else 'drop'}")

    # Flag tightness (max 3 pts)
    if flag_range_pct <= CFG["tight_flag_pct"]:
        score += 3
    elif flag_range_pct <= CFG["tight_flag_pct"] * 2:
        score += 2
    else:
        score += 1
    evidence.append(f"Flag range: {flag_range_pct:.1f}% tight")

    # Retrace quality (max 2 pts)
    if retrace_from_pole <= CFG["good_retrace_pct"]:
        score += 2
    else:
        score += 1
        warnings.append(f"Flag retrace {retrace_from_pole:.0f}% — somewhat deep")
    evidence.append(f"Retrace: {retrace_from_pole:.0f}% of pole")

    # OI (max 1 pt)
    oi_change = 0
    oi_confirms = False
    if oi_history is not None and len(oi_history) > 1:
        oi_change = float(oi_history['openInterestAmount'].pct_change().iloc[-1] * 100)
    if oi is not None:
        if is_bull and oi_change > 0:
            oi_confirms = True
            score += 1
            evidence.append(f"OI rising ({oi_change:+.1f}%) — supports flag breakout")
        elif not is_bull and oi_change < 0:
            oi_confirms = True
            score += 1
            evidence.append(f"OI declining ({oi_change:+.1f}%) — supports breakdown")
        else:
            evidence.append(f"OI neutral ({oi_change:+.1f}%)")
    else:
        missing.append("OI data unavailable")

    # ─── Maturity ────────────────────────────────────────────────────
    ready_threshold = CFG["score_ready"]
    forming_threshold = CFG["score_forming"]

    if broken_out and score >= ready_threshold:
        maturity = "Ready"
    elif near_break and score >= ready_threshold:
        maturity = "Ready"
    elif score >= forming_threshold:
        maturity = "Forming"
    elif score >= CFG["score_nascent"]:
        maturity = "Nascent"
    else:
        return None

    # ─── Entry Construction ──────────────────────────────────────────
    direction_text = "long" if is_bull else "short"
    pattern_name = f"{'Bull' if is_bull else 'Bear'} Flag Continuation"

    if is_bull:
        entry_low = flag_high_val * 1.005
        entry_high = flag_high_val * 1.03
        stop_price = flag_low_val * 0.995
    else:
        entry_low = flag_low_val * 0.995
        entry_high = flag_low_val * 1.005
        stop_price = flag_high_val * 1.005

    atr14 = atr(high, low, close)
    if not np.isnan(atr14[-1]):
        atr_val = float(atr14[-1])
        if is_bull:
            t1 = entry_low + atr_val * 1.0
            t2 = entry_low + atr_val * 2.0
        else:
            t1 = entry_low - atr_val * 1.0
            t2 = entry_low - atr_val * 2.0
    else:
        pole_size = pole_size_pct / 100 * last_price
        if is_bull:
            t1 = entry_high + pole_size * 0.5
            t2 = entry_high + pole_size * 1.0
        else:
            t1 = entry_low - pole_size * 0.5
            t2 = entry_low - pole_size * 1.0

    risk_per_unit = abs(stop_price - entry_low)
    if risk_per_unit > 0:
        rr1 = abs(t1 - entry_low) / risk_per_unit
        rr2 = abs(t2 - entry_low) / risk_per_unit
    else:
        rr1 = rr2 = 0

    # Grade
    grade = "A" if score >= 7 else "B" if score >= 5 else "C"
    strength = "STRONG" if score >= 7 else "MODERATE" if score >= 5 else "WEAK"

    # Debug info
    debug_info = {
        "flagpole": {"score": min(pole_size_pct / 5, 3), "max": 3, "pass": pole_size_pct >= CFG["strong_pole_pct"],
                     "text": f"Flagpole: {pole_size_pct:.1f}% {'rise' if is_bull else 'drop'}"},
        "flag": {"score": min(3, 4 - int(flag_range_pct / 2)), "max": 3, "pass": flag_range_pct <= CFG["tight_flag_pct"],
                 "text": f"Flag range: {flag_range_pct:.1f}% tightness"},
        "retrace": {"score": 2 if retrace_from_pole <= CFG["good_retrace_pct"] else 1, "max": 2,
                    "pass": retrace_from_pole <= CFG["good_retrace_pct"],
                    "text": f"Retrace: {retrace_from_pole:.0f}% of pole"},
        "oi": {"score": 1 if oi_confirms else 0, "max": 1, "pass": oi_confirms,
               "text": f"OI {oi_change:+.1f}% {'confirms' if oi_confirms else 'neutral'}" if oi is not None else "No OI data"},
        "total": {"score": score, "max": 9},
    }

    return {
        "pattern": "flag",
        "name": pattern_name,
        "direction": direction_text,
        "maturity": maturity,
        "grade": grade,
        "score": score,
        "max_score": 9,
        "debug": debug_info,
        "success_likelihood": {
            "percent": int(50 + (score / 9) * 30),
            "reason": f"Flagpole + tight consolidation{' + OI confirming' if oi_confirms else ''}",
        },
        "entry": {
            "direction": direction_text,
            "zone": {"low": round(entry_low, 4), "high": round(entry_high, 4),
                     "label": f"${entry_low:.4f} – ${entry_high:.4f}"},
            "stop": {"value": round(stop_price, 4), "label": f"${stop_price:.4f}",
                     "note": "Below flag low" if is_bull else "Above flag high"},
            "risk": round(risk_per_unit, 4),
            "t1": {"value": round(t1, 4), "label": f"${t1:.4f}", "rr": f"~1 : {rr1:.1f}"},
            "t2": {"value": round(t2, 4), "label": f"${t2:.4f}", "rr": f"~1 : {rr2:.1f}"},
        },
        "confluence": {"strength": strength, "checks": evidence[:4], "warnings": warnings[:3]},
        "evidence": evidence[:5],
        "missing": missing[:3],
        "price": last_price,
        "oi": oi,
        "funding": funding,
    }