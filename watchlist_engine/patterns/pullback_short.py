"""
Pattern: Pullback Short into Supply
====================================
Detects: Strong downtrend → price bounces modestly → stalls under supply zone
         → OI declining confirms bounce is weak → ready to short

Maps to user's A-grade "4H Pullback short into 0.44 supply" setup.
"""
import numpy as np
from typing import Dict, Any, Optional

from ..config import PULLBACK_SHORT as CFG
from ..indicators import (
    ema, rsi, atr, find_pivot_highs, find_pivot_lows,
    nearest_resistance_above, nearest_support_below
)


def detect(
    ohlcv_4h: Optional[Dict],
    ohlcv_1h: Optional[Dict],
    oi: Optional[float],
    oi_history: Optional[Dict],
    funding: Optional[float],
    ticker: Optional[Dict],
    cvd: Optional[Dict] = None,
    order_book: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    """Run the pullback short pattern detector."""
    if ohlcv_4h is None or ohlcv_1h is None:
        return None

    df4h = ohlcv_4h
    if len(df4h) < 60:
        return None

    close4h = df4h['close'].values
    high4h = df4h['high'].values
    low4h = df4h['low'].values

    last_price = float(close4h[-1])

    # ─── Compute Indicators ──────────────────────────────────────────
    ema20 = ema(close4h, CFG["ema_periods"][0])
    ema50 = ema(close4h, CFG["ema_periods"][1])
    atr14 = atr(high4h, low4h, close4h)

    # ─── Per-category scores ─────────────────────────────────────────
    trend_score = 0
    trend_max = 3
    retrace_score = 0
    retrace_max = 2
    supply_score = 0
    supply_max = 2
    oi_score = 0
    oi_max = 2
    funding_score = 0
    funding_max = 2

    evidence = []
    missing = []
    warnings = []
    debug_checks = {}

    # ─── 1. DOWNTREAD (max 3) ──────────────────────────────────────
    trend_checks = []
    
    c1 = {"pass": bool(not np.isnan(ema20[-1]) and last_price < ema20[-1]),
          "text": f"Price below EMA20 (${ema20[-1]:.4f})" if not np.isnan(ema20[-1]) else "EMA20 not available"}
    trend_checks.append(c1)
    if c1["pass"]:
        trend_score += 1
        evidence.append(c1["text"])
    else:
        missing.append("Price needs to be below 4H EMA20")
        warnings.append("Not below 4H EMA20 — trend may not be bearish")

    c2 = {"pass": bool(not np.isnan(ema50[-1]) and last_price < ema50[-1]),
          "text": f"Price below EMA50 (${ema50[-1]:.4f})" if not np.isnan(ema50[-1]) else "EMA50 not available"}
    trend_checks.append(c2)
    if c2["pass"]:
        trend_score += 1
        evidence.append(c2["text"])
    else:
        missing.append("Price needs to be below 4H EMA50")

    c3 = {"pass": bool(not np.isnan(ema20[-1]) and not np.isnan(ema50[-1]) and ema20[-1] < ema50[-1]),
          "text": "EMA20 < EMA50 (bearish alignment)"}
    trend_checks.append(c3)
    if c3["pass"]:
        trend_score += 1
        evidence.append(c3["text"])
    else:
        missing.append("EMA20/EMA50 not in bearish alignment")
        warnings.append("Bearish EMA cross needed for trend confirmation")

    debug_checks["trend"] = {"score": trend_score, "max": trend_max, "checks": trend_checks}

    # ─── 2. RETRACEMENT (max 2) ─────────────────────────────────────
    lookback = min(20, len(low4h))
    recent_low = float(np.min(low4h[-lookback:]))
    retrace_pct = (last_price - recent_low) / recent_low

    in_range = CFG["retrace_min_pct"] <= retrace_pct <= CFG["retrace_max_pct"]
    if in_range:
        retrace_score = 2
        evidence.append(f"Retrace from low: {retrace_pct*100:.1f}% bounce")
    elif retrace_pct < CFG["retrace_min_pct"]:
        missing.append(f"Retrace too small ({retrace_pct*100:.1f}%, need >{CFG['retrace_min_pct']*100:.1f}%)")
    else:
        missing.append(f"Retrace too large ({retrace_pct*100:.1f}%, need <{CFG['retrace_max_pct']*100:.1f}%) — may be a reversal")
        warnings.append(f"Large retrace ({retrace_pct*100:.1f}%) — bounce may be turning into reversal")

    debug_checks["retracement"] = {
        "score": retrace_score, "max": retrace_max, "pass": in_range,
        "text": f"Retrace {retrace_pct*100:.1f}% {'inside' if in_range else 'outside'} "
                f"range [{CFG['retrace_min_pct']*100:.1f}%–{CFG['retrace_max_pct']*100:.1f}%]",
    }

    # ─── 3. SUPPLY ZONE (max 2) ────────────────────────────────────
    pivots_4h = find_pivot_highs(high4h, window=3)
    nearest_res = nearest_resistance_above(last_price, pivots_4h)
    ticker_high = ticker.get('high') if ticker else None

    supply_candidates = []
    if nearest_res is not None:
        supply_candidates.append(nearest_res)
    if ticker_high is not None:
        supply_candidates.append(ticker_high)

    best_supply = min(supply_candidates) if supply_candidates else None
    entry_low = None
    entry_high = None
    supply_dist = None

    if best_supply is not None:
        supply_dist = (best_supply - last_price) / last_price
        if supply_dist <= CFG["supply_zone_distance_pct"]:
            supply_score = 2
            entry_low = last_price * 0.998
            entry_high = best_supply
            evidence.append(f"Supply overhead at ${best_supply:.4f} ({supply_dist*100:.2f}% away)")
        elif supply_dist <= CFG["supply_zone_distance_pct"] * 2:
            supply_score = 1
            entry_low = last_price * 0.998
            entry_high = best_supply
            evidence.append(f"Supply overhead at ${best_supply:.4f} ({supply_dist*100:.2f}% away — moderate distance)")
        else:
            missing.append(f"Supply too far (${best_supply:.4f}, {supply_dist*100:.1f}% above)")
    else:
        missing.append("No clear supply zone detected above price")

    sup_text = f"Nearest supply ${best_supply:.4f} ({supply_dist*100:.1f}% above)" if best_supply and supply_dist is not None else "No supply zone found"
    debug_checks["supply"] = {"score": supply_score, "max": supply_max, "pass": supply_score > 0, "text": sup_text}

    # ─── 4. OI CONFIRMATION (max 2) ─────────────────────────────────
    oi_change = 0
    if oi is not None:
        if oi_history is not None and len(oi_history) > 1:
            oi_change = float(oi_history['openInterestAmount'].pct_change().iloc[-1] * 100)

        if oi_change < CFG["oi_decline_threshold_pct"]:
            oi_score = 2
            evidence.append(f"OI declining ({oi_change:.1f}%) — weak bounce confirmation")
        elif oi_change < 0:
            oi_score = 1
            evidence.append(f"OI slightly negative ({oi_change:.1f}%)")
        else:
            oi_score = 1
            evidence.append(f"OI mostly flat/positive ({oi_change:.1f}% change)")
    else:
        missing.append("OI data unavailable")

    oi_text = f"OI {'declining' if oi_change < 0 else 'flat/rising'} ({oi_change:+.1f}%)" if oi is not None else "No OI data"
    debug_checks["oi"] = {"score": oi_score, "max": oi_max, "pass": oi_score >= 2, "text": oi_text}

    # ─── 5. FUNDING (max 2) ────────────────────────────────────────
    if funding is not None:
        if funding > 0:
            funding_score += 1
            evidence.append(f"Funding positive ({funding:.4f}%) — shorts paid to hold")
        elif funding < 0:
            evidence.append(f"Funding negative ({funding:.4f}%) — shorts pay")
        if funding > 0.005:
            funding_score += 1

    fund_text = f"Funding {funding:+.4f}% — {'shorts paid' if funding is not None and funding > 0 else 'shorts pay' if funding is not None and funding < 0 else 'neutral'}" if funding is not None else "No funding data"
    debug_checks["funding"] = {"score": funding_score, "max": funding_max, "pass": funding_score >= 2, "text": fund_text}

    # ─── TOTAL ──────────────────────────────────────────────────────
    total_score = trend_score + retrace_score + supply_score + oi_score + funding_score
    total_max = trend_max + retrace_max + supply_max + oi_max + funding_max
    max_score = CFG["score_max"]

    # ─── Maturity ──────────────────────────────────────────────────
    maturity = None
    if total_score >= CFG["score_ready"]:
        maturity = "Ready"
    elif total_score >= CFG["score_forming"]:
        maturity = "Forming"
    elif total_score >= CFG["score_nascent"]:
        maturity = "Nascent"
    else:
        return None

    # ─── Guard: need entry zone ─────────────────────────────────────
    if entry_low is None or entry_high is None:
        return None

    # ─── Stop & Targets ────────────────────────────────────────────
    stop_price = entry_high * 1.012
    risk_per_unit = stop_price - entry_low

    if not np.isnan(atr14[-1]):
        atr_val = float(atr14[-1])
        t1 = entry_low - atr_val * 1.0
        t2 = entry_low - atr_val * 2.0
    else:
        t1 = entry_low * 0.985
        t2 = entry_low * 0.975

    if risk_per_unit > 0:
        rr1 = (entry_low - t1) / risk_per_unit
        rr2 = (entry_low - t2) / risk_per_unit
    else:
        rr1 = rr2 = 0

    # Confluence assessment
    confluence_checks = [e for e in evidence if any(k in e for k in ["Funding positive", "OI declining", "bearish alignment", "EMA20 below"])]
    confluence_warnings = list(warnings)
    for m in missing[:2]:
        if "Retrace too large" in m:
            confluence_warnings.append(m)

    strength = "STRONG" if total_score >= 7 else "MODERATE" if total_score >= 5 else "WEAK"

    # ─── Debug info ────────────────────────────────────────────────
    debug_info = debug_checks.copy()
    debug_info["total"] = {"score": total_score, "max": total_max}

    return {
        "pattern": "pullback_short",
        "name": "4H Pullback Short into Supply",
        "direction": "short",
        "maturity": maturity,
        "grade": "A" if total_score >= 7 else "B" if total_score >= 5 else "C",
        "score": min(total_score, max_score),
        "max_score": max_score,
        "debug": debug_info,
        "success_likelihood": {
            "percent": int(50 + (total_score / total_max) * 30),
            "reason": f"Downtrend + retracement + OI confirmation" if oi_score >= 1 else "Downtrend + retracement",
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
                "note": "Above supply zone / nearest resistance",
            },
            "risk": round(risk_per_unit, 4),
            "t1": {
                "value": round(t1, 4),
                "label": f"${t1:.4f}",
                "rr": f"~1 : {rr1:.1f}",
                "note": "ATR-based first target",
            },
            "t2": {
                "value": round(t2, 4),
                "label": f"${t2:.4f}",
                "rr": f"~1 : {rr2:.1f}",
                "note": "ATR-based extension target",
            },
        },
        "confluence": {
            "strength": strength,
            "checks": confluence_checks[:5],
            "warnings": confluence_warnings[:3],
        },
        "evidence": evidence[:6],
        "missing": missing[:3],
        "price": last_price,
        "retrace_pct": round(retrace_pct * 100, 2),
        "oi": oi,
        "funding": funding,
    }
