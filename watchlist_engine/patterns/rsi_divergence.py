"""
Pattern: RSI Divergence
========================
Detects hidden and regular RSI divergences.

Bullish RSI Divergence (regular):
  - Price makes lower low, RSI makes higher low
  - Indicates bearish momentum fading → potential reversal up

Bearish RSI Divergence (regular):
  - Price makes higher high, RSI makes lower high
  - Indicates bullish momentum fading → potential reversal down

Hidden divergences (for trend continuation) are not detected here.
"""
import numpy as np
from typing import Dict, Any, Optional

from ..config import RSI_DIVERGENCE as CFG
from ..indicators import rsi, find_pivot_highs, find_pivot_lows, atr


def detect(
    ohlcv_4h: Optional[Dict],
    ohlcv_1h: Optional[Dict],
    oi: Optional[float],
    oi_history: Optional[Dict],
    funding: Optional[float],
    ticker: Optional[Dict],
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Detect RSI divergence on 4H timeframe."""
    if ohlcv_4h is None:
        return None

    df4h = ohlcv_4h
    if len(df4h) < 50:
        return None

    close4h = df4h['close'].values
    high4h = df4h['high'].values
    low4h = df4h['low'].values
    last_price = float(close4h[-1])

    # ─── RSI ─────────────────────────────────────────────────────────
    rsi14 = rsi(close4h, 14)
    if np.isnan(rsi14[-1]):
        return None

    # ─── Price pivots ────────────────────────────────────────────────
    pivots_h = find_pivot_highs(high4h, window=3)
    pivots_l = find_pivot_lows(low4h, window=3)

    # ─── Compute RSI values at pivot points ─────────────────────────
    def rsi_at(idx):
        if idx < len(rsi14) and not np.isnan(rsi14[idx]):
            return float(rsi14[idx])
        return None

    score = 0
    evidence = []
    missing = []
    warnings = []

    direction = None
    pattern_name = None
    is_bullish = False

    # ─── Bullish Divergence Check ────────────────────────────────────
    if len(pivots_l) >= 2:
        idx1, low1 = pivots_l[-2]
        idx2, low2 = pivots_l[-1]

        rsi1 = rsi_at(idx1)
        rsi2 = rsi_at(idx2)

        if rsi1 is not None and rsi2 is not None:
            price_lower = low2 < low1  # Price making lower low
            rsi_higher = rsi2 > rsi1  # RSI making higher low

            if price_lower and rsi_higher:
                is_bullish = True
                direction = "long"
                pattern_name = "Bullish RSI Divergence"
                score += 4
                evidence.append(f"Bullish divergence: price LL ${low2:.4f} < ${low1:.4f} vs RSI HL {rsi2:.0f} > {rsi1:.0f}")

                # Magnitude bonus
                price_diff_pct = (low1 - low2) / low2 * 100
                rsi_diff = rsi2 - rsi1
                if rsi_diff > 10:
                    score += 2
                    evidence.append(f"Strong RSI divergence ({rsi_diff:.0f} point RSI gap)")
                elif rsi_diff > 5:
                    score += 1
                    evidence.append(f"Moderate RSI divergence ({rsi_diff:.0f} point gap)")

                # Check if price is above the second low (reversal forming)
                if last_price > low2 * 1.02:
                    score += 1
                    evidence.append(f"Price bouncing from low (+{((last_price/low2)-1)*100:.1f}%)")

    # ─── Bearish Divergence Check ────────────────────────────────────
    if direction is None and len(pivots_h) >= 2:
        idx1, high1 = pivots_h[-2]
        idx2, high2 = pivots_h[-1]

        rsi1 = rsi_at(idx1)
        rsi2 = rsi_at(idx2)

        if rsi1 is not None and rsi2 is not None:
            price_higher = high2 > high1
            rsi_lower = rsi2 < rsi1

            if price_higher and rsi_lower:
                is_bullish = False
                direction = "short"
                pattern_name = "Bearish RSI Divergence"
                score += 4
                evidence.append(f"Bearish divergence: price HH ${high2:.4f} > ${high1:.4f} vs RSI LH {rsi2:.0f} < {rsi1:.0f}")

                rsi_diff = rsi1 - rsi2
                if rsi_diff > 10:
                    score += 2
                    evidence.append(f"Strong RSI divergence ({rsi_diff:.0f} point gap)")
                elif rsi_diff > 5:
                    score += 1
                    evidence.append(f"Moderate RSI divergence ({rsi_diff:.0f} point gap)")

                if last_price < high2 * 0.98:
                    score += 1
                    evidence.append(f"Price pulling back from high (-{((1-last_price/high2)*100):.1f}%)")

    if direction is None:
        return None

    # ─── OI / Funding / Volume Confluence (max 2 pts) ────────────────
    oi_change = 0
    if oi_history is not None and len(oi_history) > 1:
        oi_change = float(oi_history['openInterestAmount'].pct_change().iloc[-1] * 100)

    if oi is not None:
        if is_bullish and oi_change > 0:
            score += 1
            evidence.append(f"OI rising ({oi_change:+.1f}%) — accumulation aligns with bullish div")
        elif not is_bullish and oi_change < 0:
            score += 1
            evidence.append(f"OI declining ({oi_change:.1f}%) — distribution aligns with bearish div")

    if funding is not None:
        if is_bullish and funding < -0.003:
            score += 1
            evidence.append(f"Negative funding ({funding:.4f}%) — squeeze potential")
        elif not is_bullish and funding > 0.003:
            score += 1
            evidence.append(f"Positive funding ({funding:+.4f}%) — longs crowded")

    # ─── Current RSI for maturity context ────────────────────────────
    current_rsi = float(rsi14[-1])

    # ─── Maturity ────────────────────────────────────────────────────
    maturity = None
    if score >= CFG["score_ready"]:
        maturity = "Ready"
    elif score >= CFG["score_forming"]:
        maturity = "Forming"
    elif score >= CFG["score_nascent"]:
        maturity = "Nascent"
    else:
        return None

    grade = "A" if score >= 7 else "B" if score >= 5 else "C"
    strength = "STRONG" if score >= 7 else "MODERATE" if score >= 5 else "WEAK"

    # ─── Entry ───────────────────────────────────────────────────────
    atr14 = atr(high4h, low4h, close4h)
    atr_val = float(atr14[-1]) if not np.isnan(atr14[-1]) else last_price * 0.025

    if is_bullish:
        entry_low = last_price * 0.99
        entry_high = last_price * 1.02
        stop_price = min(low2, low4h[-1]) * 0.97 if len(pivots_l) >= 2 else last_price * 0.95
        t1 = entry_high + atr_val * 1.0
        t2 = entry_high + atr_val * 2.0
    else:
        entry_low = last_price * 0.98
        entry_high = last_price * 1.01
        stop_price = max(high2, high4h[-1]) * 1.03 if len(pivots_h) >= 2 else last_price * 1.05
        t1 = entry_low - atr_val * 1.0
        t2 = entry_low - atr_val * 2.0

    risk = abs(stop_price - entry_low)
    rr1 = abs(t1 - entry_low) / risk if risk > 0 else 0
    rr2 = abs(t2 - entry_low) / risk if risk > 0 else 0

    debug_info = {
        "divergence": {"score": 4, "max": 4, "pass": True,
                       "text": f"{'Bullish' if is_bullish else 'Bearish'} RSI divergence confirmed"},
        "magnitude": {"score": score - 4, "max": 5,
                      "pass": score - 4 >= 3,
                      "text": f"Divergence magnitude: {score - 4}/5 — RSI gap + price action + confirmation"},
        "confluence": {"score": min(2, score - 4), "max": 2,
                       "pass": score - 4 >= 2,
                       "text": f"OI/Funding confirmation: {min(2, score - 4)}/2"},
        "total": {"score": score, "max": 11},
    }

    return {
        "pattern": "rsi_divergence",
        "name": pattern_name,
        "direction": direction,
        "maturity": maturity,
        "grade": grade,
        "score": score,
        "max_score": 11,
        "debug": debug_info,
        "success_likelihood": {"percent": int(45 + (score / 11) * 30), "reason": f"RSI divergence + {'momentum' if score >= 6 else 'structure'}"},
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
        "missing": missing[:3],
        "price": last_price,
        "oi": oi,
        "funding": funding,
    }