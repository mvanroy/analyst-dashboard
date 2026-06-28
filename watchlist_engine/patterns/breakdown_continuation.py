"""
Pattern: Breakdown Continuation
=================================
Detects: Downtrend → range consolidation → price breaks below range low
         → OI decline/volume confirms breakdown → ready to short

Maps to user's B-grade "4H breakdown continuation" setup.
"""
import numpy as np
from typing import Dict, Any, Optional

from ..config import BREAKDOWN_CONTINUATION as CFG
from ..indicators import ema, atr, find_pivot_lows, find_pivot_highs


def detect(
    ohlcv_4h: Optional[Dict],
    ohlcv_1h: Optional[Dict],
    oi: Optional[float],
    oi_history: Optional[Dict],
    funding: Optional[float],
    ticker: Optional[Dict],
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Run the breakdown continuation pattern detector."""
    if ohlcv_4h is None or ohlcv_1h is None:
        return None

    df4h = ohlcv_4h
    df1h = ohlcv_1h
    
    if len(df4h) < 40 or len(df1h) < 40:
        return None

    close4h = df4h['close'].values
    high4h = df4h['high'].values
    low4h = df4h['low'].values
    close1h = df1h['close'].values
    high1h = df1h['high'].values
    low1h = df1h['low'].values

    last_price = float(close4h[-1])
    last_1h_price = float(close1h[-1])
    last_1h_high = float(high1h[-1])

    # ─── Indicators ──────────────────────────────────────────────────
    ema20 = ema(close4h, 20)
    ema50 = ema(close4h, 50)
    atr14 = atr(high4h, low4h, close4h)

    score = 0
    evidence = []
    missing = []
    warnings = []

    # --- Condition 1: Pre-existing downtrend (max 2 pts) ---
    if not np.isnan(ema20[-1]) and not np.isnan(ema50[-1]):
        if last_price < ema20[-1]:
            score += 1
            evidence.append(f"Price below 4H EMA20 (${ema20[-1]:.4f})")
        if ema20[-1] < ema50[-1]:
            score += 1
            evidence.append("Bearish EMA alignment (20 < 50)")
        if last_price >= ema20[-1]:
            missing.append("Not below 4H EMA20 — questionable downtrend")

    # --- Condition 2: Recent range / consolidation (max 2 pts) ---
    lookback = CFG["range_lookback_candles"]
    recent_high = float(np.max(high4h[-lookback:]))
    recent_low = float(np.min(low4h[-lookback:]))
    range_size = (recent_high - recent_low) / recent_low * 100

    # Range should be tight enough to be a consolidation
    if 1.0 <= range_size <= 6.0:
        score += 2
        evidence.append(f"Range formed: {range_size:.1f}% wide over {lookback} candles")
    elif range_size < 1.0:
        score += 1
        evidence.append(f"Very tight range: {range_size:.1f}%")
    else:
        missing.append(f"Range too wide ({range_size:.1f}%) for consolidation")
        warnings.append("Wide range may be a continuation pattern itself, not a consolidation")

    # --- Condition 3: Price near/breaking range low (max 3 pts) ---
    # The range low is the recent support
    support = recent_low
    
    dist_from_support = (last_price - support) / support * 100

    if last_price < support * 0.998:  # Already broken below
        score += 3
        evidence.append(f"Price below range low ${support:.4f} (breakdown in progress)")
    elif dist_from_support < 2.0:  # Near support, watching for break
        score += 2
        evidence.append(f"Price near range low ${support:.4f} ({dist_from_support:.1f}% above)")
        # Check 1H for closer view
        if last_1h_price < support * 0.998:
            score += 1
            evidence.append("1H has already broken below support")
    else:
        missing.append(f"Price too far from support ({dist_from_support:.1f}%)")
        return None  # Can't be a breakdown setup if price is mid-range

    # --- Condition 4: OI confirmation (max 2 pts) ---
    if oi is not None:
        oi_change = 0
        if oi_history is not None and len(oi_history) > 1:
            oi_change = float(oi_history['openInterestAmount'].pct_change().iloc[-1] * 100)
        
        if oi_change < CFG["oi_decline_threshold_pct"]:
            score += 2
            evidence.append(f"OI declining ({oi_change:.1f}%) — confirms breakdown")
        elif oi_change < 0:
            score += 1
            evidence.append(f"OI slightly negative ({oi_change:.1f}%)")
        else:
            evidence.append(f"OI flat/rising ({oi_change:.1f}%) — may not confirm")
    else:
        missing.append("OI data unavailable")

    # --- Maturity ---
    max_score = CFG["score_max"]
    maturity = None
    
    if score >= CFG["score_ready"]:
        maturity = "Ready"
    elif score >= CFG["score_forming"]:
        maturity = "Forming"
    elif score >= CFG["score_nascent"]:
        maturity = "Nascent"
    else:
        return None

    # --- Build Setup ---
    # Entry zone: just below support (if broken) or at support (if approaching)
    if last_price < support:
        # Already broken — entry is current area
        entry_low = last_price * 0.995
        entry_high = min(last_price * 1.005, support * 1.002)
    else:
        # Approaching — entry is at support break
        entry_low = support * 0.995
        entry_high = support * 1.002

    # Stop: just above the range midpoint or the recent high
    stop_price = recent_high + (range_size * 0.001 * recent_high)
    risk_per_unit = stop_price - entry_low

    # Targets
    if not np.isnan(atr14[-1]):
        atr_val = float(atr14[-1])
        t1 = entry_low - atr_val * 0.8
        t2 = entry_low - atr_val * 1.5
    else:
        t1 = support * 0.97
        t2 = support * 0.94

    if risk_per_unit > 0:
        rr1 = (entry_low - t1) / risk_per_unit
        rr2 = (entry_low - t2) / risk_per_unit
    else:
        rr1 = rr2 = 0

    strength = "STRONG" if score >= 6 else "MODERATE" if score >= 4 else "WEAK"

    return {
        "pattern": "breakdown_continuation",
        "name": "Breakdown Continuation below Support",
        "direction": "short",
        "maturity": maturity,
        "grade": "A" if score >= 7 else "B" if score >= 5 else "C",
        "score": score,
        "max_score": max_score,
        "success_likelihood": {
            "percent": int(45 + (score / max_score) * 30),
            "reason": "Support breakdown + " + ("OI confirming" if score >= 5 else "structure-based"),
        },
        "entry": {
            "direction": "short",
            "zone": {
                "low": round(entry_low, 4),
                "high": round(entry_high, 4),
                "label": f"${entry_low:.4f} – ${entry_high:.4f}",
            },
            "stop": {
                "value": round(stop_price, 4),
                "label": f"${stop_price:.4f}",
                "note": "Above range high / consolidation top",
            },
            "risk": round(risk_per_unit, 4),
            "t1": {
                "value": round(t1, 4),
                "label": f"${t1:.4f}",
                "rr": f"~1 : {rr1:.1f}",
            },
            "t2": {
                "value": round(t2, 4),
                "label": f"${t2:.4f}",
                "rr": f"~1 : {rr2:.1f}",
            },
        },
        "confluence": {
            "strength": strength,
            "checks": evidence[:4],
            "warnings": warnings[:3],
        },
        "evidence": evidence[:6],
        "missing": missing[:3],
        "price": last_price,
        "support": round(support, 4),
        "oi": oi,
    }