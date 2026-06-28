"""
Pattern: Breakout with OI Confirmation
========================================
Detects: Price breaking a key resistance level + OI rising alongside = conviction

Key differentiator from Pullback Short: OI should be RISING, not declining.
Rising OI on a breakout means new money entering the move = sustainable.

Can detect both upside breakouts (long) and downside breakdowns (short).
"""
import numpy as np
from typing import Dict, Any, Optional

from ..config import BREAKOUT_OI as CFG
from ..indicators import find_pivot_highs, find_pivot_lows, atr


def detect(
    ohlcv_4h: Optional[Dict],
    ohlcv_1h: Optional[Dict],
    oi: Optional[float],
    oi_history: Optional[Dict],
    funding: Optional[float],
    ticker: Optional[Dict],
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Detect breakout with OI confirmation."""
    if ohlcv_4h is None or ohlcv_1h is None:
        return None

    df4h = ohlcv_4h
    df1h = ohlcv_1h
    if len(df4h) < 40 or len(df1h) < 30:
        return None

    close4h = df4h['close'].values
    high4h = df4h['high'].values
    low4h = df4h['low'].values
    close1h = df1h['close'].values
    high1h = df1h['high'].values
    low1h = df1h['low'].values

    last_price = float(close4h[-1])
    last_1h_close = float(close1h[-1])

    score = 0
    evidence = []
    missing = []
    warnings = []

    # ─── 1. Find key level (max 2 pts) ──────────────────────────────
    # Find the most significant resistance and support nearby
    pivots_h = find_pivot_highs(high4h, window=3)
    pivots_l = find_pivot_lows(low4h, window=3)

    # Nearest resistance above
    resistance = None
    for idx, val in reversed(pivots_h):
        if val > last_price * 0.98:
            resistance = val
            break

    # Nearest support below
    support = None
    for idx, val in reversed(pivots_l):
        if val < last_price * 1.02:
            support = val
            break

    # Check for upside breakout
    upside_break = False
    break_level = None
    if resistance is not None:
        dist_to_res = (resistance - last_price) / resistance * 100
        if last_price > resistance * 1.005:  # Already broke
            upside_break = True
            break_level = resistance
            score += 2
            evidence.append(f"Broke resistance ${resistance:.4f} (${last_price:.4f} above)")
        elif dist_to_res < CFG["break_proximity_pct"]:
            score += 1
            evidence.append(f"Approaching resistance ${resistance:.4f} ({dist_to_res:.1f}% below)")

    # Check for downside breakdown
    downside_break = False
    if support is not None:
        dist_to_sup = (last_price - support) / support * 100
        if last_price < support * 0.995:
            downside_break = True
            break_level = support
            score += 2
            evidence.append(f"Broke support ${support:.4f} (${last_price:.4f} below)")
        elif dist_to_sup < CFG["break_proximity_pct"]:
            score += 1
            evidence.append(f"Approaching support ${support:.4f} ({dist_to_sup:.1f}% above)")

    if not upside_break and not downside_break and score < 1:
        return None  # No breakout setup

    # ─── 2. OI Confirmation (max 3 pts) ──────────────────────────────
    oi_change = 0
    if oi_history is not None and len(oi_history) > 1:
        oi_change = float(oi_history['openInterestAmount'].pct_change().iloc[-1] * 100)

    if oi is not None:
        # For upside break: OI should be rising (new longs entering)
        # For downside break: OI could rise (new shorts) or fall (liquidation cascade)
        if upside_break and oi_change > CFG["oi_rise_threshold"]:
            score += 3
            evidence.append(f"OI rising ({oi_change:+.1f}%) — confirms breakout conviction")
        elif downside_break and oi_change < 0:
            score += 2
            evidence.append(f"OI declining ({oi_change:.1f}%) — liquidation cascade potential")
        elif downside_break and oi_change > CFG["oi_rise_threshold"]:
            score += 3
            evidence.append(f"OI rising ({oi_change:+.1f}%) — new shorts entering, trend follow")
        elif abs(oi_change) < CFG["oi_rise_threshold"]:
            score += 1
            evidence.append(f"OI flat ({oi_change:+.1f}%) — mixed signal")
        else:
            score += 1
            evidence.append(f"OI available ({oi_change:+.1f}%)")
    else:
        missing.append("OI unavailable for confirmation")

    # ─── 3. Volume / Momentum check (max 2 pts) ──────────────────────
    vol4h = df4h['volume'].values
    if len(vol4h) > 10:
        recent_vol = float(np.mean(vol4h[-3:]))
        prior_vol = float(np.mean(vol4h[-10:-3]))
        if prior_vol > 0 and recent_vol / prior_vol > CFG["volume_surge_multiple"]:
            score += 2
            evidence.append(f"Volume surge ({recent_vol/prior_vol:.1f}x normal)")
        elif prior_vol > 0 and recent_vol > prior_vol:
            score += 1
            evidence.append(f"Volume above average ({recent_vol/prior_vol:.1f}x)")
        else:
            warnings.append("Volume not confirming")
    else:
        missing.append("Volume data unavailable")

    # ─── 4. Funding check (max 1 pt) ────────────────────────────────
    if funding is not None:
        if upside_break and funding < 0:
            score += 1
            evidence.append(f"Negative funding ({funding:.4f}%) — shorts squeezed")
        elif downside_break and funding > 0:
            score += 1
            evidence.append(f"Positive funding ({funding:+.4f}%) — long squeeze")
        elif upside_break and funding > 0:
            evidence.append(f"Positive funding ({funding:+.4f}%) — longs paying but breaking out")

    # ─── Maturity ────────────────────────────────────────────────────
    if upside_break or downside_break:
        # Already broken — Ready if score is decent
        if score >= CFG["score_ready"]:
            maturity = "Ready"
        elif score >= CFG["score_forming"]:
            # Broken but lacking confirmation
            maturity = "Ready"  # The break happened — actionable even with moderate score
        else:
            return None
    else:
        # Approaching break — Forming
        if score >= CFG["score_forming"]:
            maturity = "Forming"
        elif score >= CFG["score_nascent"]:
            maturity = "Nascent"
        else:
            return None

    direction = "long" if upside_break else "short"
    pattern_name = f"{'Upside Breakout' if upside_break else 'Downside Breakdown'}"
    grade = "A" if score >= 7 else "B" if score >= 5 else "C"
    strength = "STRONG" if score >= 7 else "MODERATE" if score >= 5 else "WEAK"

    # ─── Entry ───────────────────────────────────────────────────────
    atr14 = atr(high4h, low4h, close4h)
    atr_val = float(atr14[-1]) if not np.isnan(atr14[-1]) else last_price * 0.02

    if upside_break:
        entry_low = break_level * 1.002 if break_level else last_price * 0.995
        entry_high = last_price * 1.02
        stop_price = break_level * 0.985 if break_level else last_price * 0.97
        t1 = entry_high + atr_val * 1.0
        t2 = entry_high + atr_val * 2.0
    else:
        entry_low = last_price * 0.98
        entry_high = break_level * 0.998 if break_level else last_price * 1.005
        stop_price = break_level * 1.015 if break_level else last_price * 1.03
        t1 = entry_low - atr_val * 1.0
        t2 = entry_low - atr_val * 2.0

    risk = abs(stop_price - entry_low)
    rr1 = abs(t1 - entry_low) / risk if risk > 0 else 0
    rr2 = abs(t2 - entry_low) / risk if risk > 0 else 0

    debug_info = {
        "breakout": {"score": 2 if (upside_break or downside_break) else 1, "max": 2,
                     "pass": upside_break or downside_break,
                     "text": f"{'Broke' if upside_break or downside_break else 'Approaching'} ${break_level:.4f} ({'resistance' if upside_break else 'support'})" if break_level else "No clear level"},
        "oi_confirmation": {"score": min(3, score - (2 if upside_break or downside_break else 1)), "max": 3,
                            "pass": oi_change > CFG["oi_rise_threshold"] if upside_break else oi_change < 0,
                            "text": f"OI {oi_change:+.1f}% — {'confirms' if oi is not None else 'N/A'}"},
        "volume": {"score": 2 if prior_vol > 0 and recent_vol/prior_vol > CFG["volume_surge_multiple"] else 1 if prior_vol > 0 and recent_vol > prior_vol else 0,
                   "max": 2, "pass": prior_vol > 0 and recent_vol > prior_vol,
                   "text": f"Volume {recent_vol/prior_vol:.1f}x avg" if prior_vol > 0 else "Vol N/A"},
        "funding": {"score": 1 if funding is not None and ((upside_break and funding < 0) or (downside_break and funding > 0)) else 0,
                    "max": 1, "pass": False,  # Funding is a bonus, not required
                    "text": f"Funding {funding:+.4f}%" if funding is not None else "N/A"},
        "total": {"score": score, "max": 8},
    }

    return {
        "pattern": "breakout_oi",
        "name": pattern_name,
        "direction": direction,
        "maturity": maturity,
        "grade": grade,
        "score": score,
        "max_score": 8,
        "debug": debug_info,
        "success_likelihood": {"percent": int(50 + (score / 8) * 30), "reason": f"Breakout{' + OI confirmation' if oi is not None and oi_change > 0 else ''}"},
        "entry": {
            "direction": direction,
            "zone": {"low": round(entry_low, 4), "high": round(entry_high, 4), "label": f"${entry_low:.4f} – ${entry_high:.4f}"},
            "stop": {"value": round(stop_price, 4), "label": f"${stop_price:.4f}", "note": "Below breakout level" if upside_break else "Above breakdown level"},
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