"""
Pattern: OI Divergence
=======================
Detects divergence between price and Open Interest.

Bullish OI Divergence: Price making lower lows, but OI declining (shorts losing conviction)
  → Potential squeeze / trend reversal up

Bearish OI Divergence: Price making higher highs, but OI declining (longs exiting)
  → Potential trend weakening / reversal down

This is one of the most reliable non-price signals in crypto futures.
"""
import numpy as np
from typing import Dict, Any, Optional

from ..config import OI_DIVERGENCE as CFG
from ..indicators import find_pivot_highs, find_pivot_lows


def detect(
    ohlcv_4h: Optional[Dict],
    ohlcv_1h: Optional[Dict],
    oi: Optional[float],
    oi_history: Optional[Dict],
    funding: Optional[float],
    ticker: Optional[Dict],
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Detect OI divergence (bullish or bearish)."""
    if ohlcv_4h is None or oi_history is None or len(oi_history) < 20:
        return None

    df4h = ohlcv_4h
    if len(df4h) < 40:
        return None

    close4h = df4h['close'].values
    high4h = df4h['high'].values
    low4h = df4h['low'].values
    last_price = float(close4h[-1])

    oi_values = oi_history['openInterestAmount'].values
    current_oi = oi

    if len(oi_values) < 10:
        return None

    # ─── Find pivots in price ────────────────────────────────────────
    pivots_h = find_pivot_highs(high4h, window=3)
    pivots_l = find_pivot_lows(low4h, window=3)

    if len(pivots_h) < 2 or len(pivots_l) < 2:
        return None

    # ─── Map price pivots to OI values ───────────────────────────────
    # We find OI values at the same timestamp indices as price pivots
    # Since OI history may have different length, we map by position ratio

    # Take last 2 swing highs and lows
    last_2h = pivots_h[-2:]
    last_2l = pivots_l[-2:]

    oi_mapped_h = []
    for idx, val in last_2h:
        # Map pivot index to OI history position
        oi_idx = min(int(idx / len(close4h) * len(oi_values)), len(oi_values) - 1)
        oi_mapped_h.append(float(oi_values[oi_idx]))

    oi_mapped_l = []
    for idx, val in last_2l:
        oi_idx = min(int(idx / len(close4h) * len(oi_values)), len(oi_values) - 1)
        oi_mapped_l.append(float(oi_values[oi_idx]))

    # ─── Check Bearish Divergence ────────────────────────────────────
    # Price making higher high, OI making lower high
    bearish_div = False
    bearish_score = 0
    bearish_evidence = []
    bearish_warnings = []

    if len(last_2h) >= 2 and len(oi_mapped_h) >= 2:
        price_higher = last_2h[-1][1] > last_2h[-2][1]
        oi_lower = oi_mapped_h[-1] < oi_mapped_h[-2]
        oi_change_pct = (oi_mapped_h[-1] - oi_mapped_h[-2]) / oi_mapped_h[-2] * 100

        if price_higher and oi_lower:
            bearish_div = True
            bearish_score += 3
            bearish_evidence.append(f"Price HH ${last_2h[-1][1]:.4f} > ${last_2h[-2][1]:.4f}")
            bearish_evidence.append(f"OI LH ({oi_change_pct:+.1f}%) — longs exiting")

            # Magnitude bonus
            price_gap = (last_2h[-1][1] - last_2h[-2][1]) / last_2h[-2][1] * 100
            oi_gap = abs(oi_change_pct)
            if price_gap > 3 and oi_gap > 5:
                bearish_score += 2
                bearish_evidence.append(f"Strong divergence ({price_gap:.1f}% price vs {oi_gap:.1f}% OI)")
            elif price_gap > 1 and oi_gap > 2:
                bearish_score += 1
                bearish_evidence.append(f"Moderate divergence")
        else:
            bearish_warnings.append("No bearish OI divergence detected")

    # ─── Check Bullish Divergence ────────────────────────────────────
    # Price making lower low, OI making higher low (or declining less)
    bullish_div = False
    bullish_score = 0
    bullish_evidence = []
    bullish_warnings = []

    if len(last_2l) >= 2 and len(oi_mapped_l) >= 2:
        price_lower = last_2l[-1][1] < last_2l[-2][1]
        oi_higher = oi_mapped_l[-1] > oi_mapped_l[-2]
        oi_change_pct = (oi_mapped_l[-1] - oi_mapped_l[-2]) / oi_mapped_l[-2] * 100

        if price_lower and oi_higher:
            bullish_div = True
            bullish_score += 3
            bullish_evidence.append(f"Price LL ${last_2l[-1][1]:.4f} < ${last_2l[-2][1]:.4f}")
            bullish_evidence.append(f"OI HL ({oi_change_pct:+.1f}%) — accumulation during dip")

            price_gap = (last_2l[-2][1] - last_2l[-1][1]) / last_2l[-1][1] * 100
            oi_gap = abs(oi_change_pct)
            if price_gap > 3 and oi_gap > 5:
                bullish_score += 2
                bullish_evidence.append(f"Strong divergence ({price_gap:.1f}% price vs {oi_gap:.1f}% OI)")
            elif price_gap > 1 and oi_gap > 2:
                bullish_score += 1
        else:
            bullish_warnings.append("No bullish OI divergence detected")

    # ─── Also check current OI trend as confirmation ─────────────────
    oi_trend = 0
    if len(oi_values) > 5:
        oi_trend = float((oi_values[-1] / oi_values[-5] - 1) * 100)

    # ─── Pick the stronger divergence ────────────────────────────────
    if not bearish_div and not bullish_div:
        return None

    if bearish_div and bearish_score >= bullish_score:
        is_bullish = False
        score = bearish_score
        evidence = bearish_evidence
        warnings = bearish_warnings
        if oi_trend < -1:
            score += 1
            evidence.append(f"OI trending down ({oi_trend:.1f}%) — confirms bearish")
    elif bullish_div:
        is_bullish = True
        score = bullish_score
        evidence = bullish_evidence
        warnings = bullish_warnings
        if oi_trend > 1:
            score += 1
            evidence.append(f"OI trending up ({oi_trend:+.1f}%) — confirms accumulation")
    else:
        return None

    # ─── Funding check (max 1 pt) ────────────────────────────────────
    if funding is not None:
        if is_bullish and funding < -0.005:
            score += 1
            evidence.append(f"Negative funding ({funding:.4f}%) — shorts paying, squeeze potential")
        elif not is_bullish and funding > 0.005:
            score += 1
            evidence.append(f"Positive funding ({funding:+.4f}%) — longs paying, potential top")

    # ─── Current price relative to divergence point ──────────────────
    has_reversal = False
    if is_bullish and len(last_2l) >= 2:
        # Price should be above the second low to confirm reversal forming
        has_reversal = last_price > last_2l[-1][1] * 1.01
    elif not is_bullish and len(last_2h) >= 2:
        has_reversal = last_price < last_2h[-1][1] * 0.99

    # ─── Maturity ────────────────────────────────────────────────────
    ready_threshold = CFG["score_ready"]
    if score >= ready_threshold and has_reversal:
        maturity = "Ready"
    elif score >= ready_threshold:
        maturity = "Forming"
    elif score >= CFG["score_forming"]:
        maturity = "Forming"
    elif score >= CFG["score_nascent"]:
        maturity = "Nascent"
    else:
        return None

    direction = "long" if is_bullish else "short"
    pattern_name = f"{'Bullish' if is_bullish else 'Bearish'} OI Divergence"
    grade = "A" if score >= 7 else "B" if score >= 5 else "C"
    strength = "STRONG" if score >= 7 else "MODERATE" if score >= 5 else "WEAK"

    # ─── Entry ───────────────────────────────────────────────────────
    if is_bullish:
        entry_low = last_price * 0.995
        entry_high = last_price * 1.02
        stop_price = min(last_price * 0.97, last_2l[-1][1] * 0.98) if len(last_2l) >= 2 else last_price * 0.97
        t1 = last_price * 1.05
        t2 = last_price * 1.10
    else:
        entry_low = last_price * 0.98
        entry_high = last_price * 1.005
        stop_price = max(last_price * 1.03, last_2h[-1][1] * 1.02) if len(last_2h) >= 2 else last_price * 1.03
        t1 = last_price * 0.95
        t2 = last_price * 0.90

    risk = abs(stop_price - entry_low)
    rr1 = abs(t1 - entry_low) / risk if risk > 0 else 0
    rr2 = abs(t2 - entry_low) / risk if risk > 0 else 0

    # Debug
    debug_info = {
        "divergence": {"score": 3, "max": 3, "pass": True,
                       "text": f"{'Bullish' if is_bullish else 'Bearish'} OI divergence detected"},
        "magnitude": {"score": score - 3, "max": 3,
                      "pass": score - 3 >= 2,
                      "text": f"Divergence magnitude score: {score - 3}/3"},
        "oi_trend": {"score": 1 if (is_bullish and oi_trend > 1) or (not is_bullish and oi_trend < -1) else 0,
                     "max": 1, "pass": bool((is_bullish and oi_trend > 1) or (not is_bullish and oi_trend < -1)),
                     "text": f"OI {'trending up' if oi_trend > 0 else 'down'} ({oi_trend:+.1f}%)"},
        "funding": {"score": 1 if funding is not None and ((is_bullish and funding < -0.005) or (not is_bullish and funding > 0.005)) else 0,
                    "max": 1, "pass": bool(funding is not None and abs(funding) > 0.005),
                    "text": f"Funding {funding:+.4f}% — {'confirms' if funding is not None and abs(funding) > 0.005 else 'neutral'}" if funding is not None else "No data"},
        "total": {"score": score, "max": 10},
    }

    return {
        "pattern": "oi_divergence",
        "name": pattern_name,
        "direction": direction,
        "maturity": maturity,
        "grade": grade,
        "score": score,
        "max_score": 10,
        "debug": debug_info,
        "success_likelihood": {"percent": int(50 + (score / 10) * 30), "reason": f"OI divergence + {'funding confirming' if funding is not None else 'structure'}"},
        "entry": {
            "direction": direction,
            "zone": {"low": round(entry_low, 4), "high": round(entry_high, 4), "label": f"${entry_low:.4f} – ${entry_high:.4f}"},
            "stop": {"value": round(stop_price, 4), "label": f"${stop_price:.4f}", "note": "Below divergence low" if is_bullish else "Above divergence high"},
            "risk": round(risk, 4),
            "t1": {"value": round(t1, 4), "label": f"${t1:.4f}", "rr": f"~1 : {rr1:.1f}"},
            "t2": {"value": round(t2, 4), "label": f"${t2:.4f}", "rr": f"~1 : {rr2:.1f}"},
        },
        "confluence": {"strength": strength, "checks": evidence[:4], "warnings": warnings[:3]},
        "evidence": evidence[:5],
        "missing": [],
        "price": last_price,
        "oi": oi,
        "funding": funding,
    }