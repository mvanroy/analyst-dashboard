"""
Pattern: Mean Reversion Long
=============================
Detects: Oversold RSI + price at structure support + stabilization = bounce trade

Matches user's C-grade setup from the MNT JSON.
Counter-trend by nature — only taken when confluence is strong.

Signals:
  - RSI < 30 on 4H or daily (oversold)
  - Price testing or near a key support level (pivot low or range low)
  - Candles stabilizing (smaller bodies, long wicks = absorption)
  - Funding negative (shorts paying, squeeze potential)
"""
import numpy as np
from typing import Dict, Any, Optional

from ..config import MEAN_REVERSION as CFG
from ..indicators import rsi, ema, atr, find_pivot_lows, nearest_support_below


def detect(
    ohlcv_4h: Optional[Dict],
    ohlcv_1h: Optional[Dict],
    oi: Optional[float],
    oi_history: Optional[Dict],
    funding: Optional[float],
    ticker: Optional[Dict],
    cvd: Optional[Dict] = None,
    order_book: Optional[Dict] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Detect mean reversion long setups."""
    if ohlcv_4h is None:
        return None

    df4h = ohlcv_4h
    df1h = ohlcv_1h
    if len(df4h) < 50:
        return None

    close4h = df4h['close'].values
    high4h = df4h['high'].values
    low4h = df4h['low'].values
    close1h = df1h['close'].values if df1h is not None else close4h
    high1h = df1h['high'].values if df1h is not None else high4h
    low1h = df1h['low'].values if df1h is not None else low4h

    last_price = float(close4h[-1])
    score = 0
    evidence = []
    missing = []
    warnings = []

    # ─── 1. RSI Oversold (max 3 pts) ────────────────────────────────
    rsi14 = rsi(close4h)
    rsi_1h = rsi(close1h, 14) if df1h is not None else rsi14

    if not np.isnan(rsi14[-1]):
        current_rsi = float(rsi14[-1])
        if current_rsi < CFG["deep_oversold_rsi"]:
            score += 3
            evidence.append(f"4H RSI {current_rsi:.0f} — deeply oversold")
        elif current_rsi < CFG["oversold_rsi"]:
            score += 2
            evidence.append(f"4H RSI {current_rsi:.0f} — oversold")
        elif current_rsi < CFG["near_oversold_rsi"]:
            score += 1
            evidence.append(f"4H RSI {current_rsi:.0f} — near oversold")
        else:
            missing.append(f"RSI {current_rsi:.0f} — not oversold (need <{CFG['oversold_rsi']})")
    else:
        missing.append("RSI data unavailable")

    # ─── 2. Structure Support (max 3 pts) ────────────────────────────
    pivots_l = find_pivot_lows(low4h, window=3)
    support = nearest_support_below(last_price, pivots_l)

    if support is not None:
        support_dist = (last_price - support) / support * 100
        if support_dist < CFG["tight_support_pct"]:
            score += 3
            evidence.append(f"Price at support ${support:.4f} ({support_dist:.1f}% above)")
        elif support_dist < CFG["near_support_pct"]:
            score += 2
            evidence.append(f"Near support ${support:.4f} ({support_dist:.1f}% above)")
        else:
            score += 1
            evidence.append(f"Approaching support ${support:.4f}")
    else:
        # Use recent low as support proxy
        recent_low = float(np.min(low4h[-20:]))
        dist = (last_price - recent_low) / recent_low * 100
        if dist < CFG["tight_support_pct"]:
            score += 2
            evidence.append(f"Near recent low ${recent_low:.4f} ({dist:.1f}% above)")
        else:
            missing.append("No clear support level identified")
        support = recent_low

    # ─── 3. Stabilization / Absorption (max 2 pts) ───────────────────
    recent_candles = min(10, len(close4h))
    recent_highs = high4h[-recent_candles:]
    recent_lows = low4h[-recent_candles:]
    recent_closes = close4h[-recent_candles:]

    avg_body_pct = np.mean([abs(recent_closes[i] - recent_closes[i-1]) / recent_closes[i-1] * 100
                            for i in range(1, len(recent_closes))])
    avg_range_pct = np.mean([(recent_highs[i] - recent_lows[i]) / recent_lows[i] * 100
                             for i in range(len(recent_highs))])

    # Smaller candles after the selloff = stabilization
    if avg_range_pct < CFG["tight_candle_range"]:
        score += 2
        evidence.append(f"Candles tightening ({avg_range_pct:.2f}% avg range) — absorption")
    elif avg_range_pct < CFG["moderate_candle_range"]:
        score += 1
        evidence.append(f"Candles moderating ({avg_range_pct:.2f}% avg range)")
    else:
        warnings.append(f"High volatility ({avg_range_pct:.2f}% range) — no stabilization yet")
        missing.append("Candles not stabilizing")

    # ─── 4. Funding (max 1 pt) ──────────────────────────────────────
    if funding is not None:
        if funding < -0.005:
            score += 1
            evidence.append(f"Negative funding ({funding:.4f}%) — shorts squeeze potential")
        elif funding < 0:
            evidence.append(f"Funding slightly negative ({funding:.4f}%)")
        else:
            warnings.append(f"Positive funding ({funding:+.4f}%) — longs paying, less squeeze potential")
    else:
        missing.append("Funding data unavailable")

    # ─── 5. OI confirmation (max 1 pt) ───────────────────────────────
    oi_change = 0
    if oi_history is not None and len(oi_history) > 1:
        oi_change = float(oi_history['openInterestAmount'].pct_change().iloc[-1] * 100)
        if oi is not None:
            if oi_change > 0:
                score += 1
                evidence.append(f"OI rising ({oi_change:+.1f}%) — possible accumulation")
            elif oi_change < -1:
                evidence.append(f"OI declining ({oi_change:.1f}%) — deleveraging")

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

    # ─── Entry ───────────────────────────────────────────────────
    atr14 = atr(high4h, low4h, close4h)
    atr_val = float(atr14[-1]) if not np.isnan(atr14[-1]) else last_price * 0.03

    entry_low = support * 0.995
    entry_high = support * 1.015
    stop_price = support * 0.97
    risk = stop_price - entry_low

    t1 = entry_high + atr_val * 1.0
    t2 = entry_high + atr_val * 2.0
    rr1 = (t1 - entry_low) / risk if risk > 0 else 0
    rr2 = (t2 - entry_low) / risk if risk > 0 else 0

    debug_info = {
        "rsi": {
            "score": 3 if not np.isnan(rsi14[-1]) and rsi14[-1] < CFG["deep_oversold_rsi"]
            else 2 if not np.isnan(rsi14[-1]) and rsi14[-1] < CFG["oversold_rsi"]
            else 0,
            "max": 3,
            "pass": bool(not np.isnan(rsi14[-1]) and rsi14[-1] < CFG["oversold_rsi"]),
            "text": f"4H RSI {float(rsi14[-1]):.0f} — {'oversold' if float(rsi14[-1]) < CFG['oversold_rsi'] else 'not oversold'}"
            if not np.isnan(rsi14[-1]) else "RSI N/A",
        },
        "support": {
            "score": min(3, int(support_dist / 2) + 1) if support is not None else 0,
            "max": 3,
            "pass": support is not None and support_dist < CFG["near_support_pct"],
            "text": f"Support ${support:.4f} ({support_dist:.1f}% below)" if support is not None else "No clear support",
        },
        "stabilization": {
            "score": 2 if avg_range_pct < CFG["tight_candle_range"] else 1 if avg_range_pct < CFG["moderate_candle_range"] else 0,
            "max": 2,
            "pass": avg_range_pct < CFG["moderate_candle_range"],
            "text": f"Candles {'stabilizing' if avg_range_pct < CFG['moderate_candle_range'] else 'volatile'} ({avg_range_pct:.2f}% range)",
        },
        "funding_oi": {
            "score": score - (3 if not np.isnan(rsi14[-1]) and rsi14[-1] < CFG["deep_oversold_rsi"] else 2) - (3 if support is not None else 0),
            "max": 2,
            "pass": bool(funding is not None and funding < -0.005),
            "text": f"Funding {funding:+.4f}% — {'squeeze setup' if funding is not None and funding < -0.005 else 'neutral'}"
            if funding is not None else "No funding data",
        },
        "total": {"score": score, "max": 10},
    }

    return {
        "pattern": "mean_reversion",
        "name": "Mean Reversion Long from Support",
        "direction": "long",
        "maturity": maturity,
        "grade": grade,
        "score": score,
        "max_score": 10,
        "debug": debug_info,
        "success_likelihood": {
            "percent": int(40 + (score / 10) * 25),
            "reason": f"Oversold RSI + support{' + squeeze setup' if funding is not None and funding < -0.005 else ''}",
        },
        "entry": {
            "direction": "long",
            "zone": {"low": round(entry_low, 4), "high": round(entry_high, 4), "label": f"${entry_low:.4f} – ${entry_high:.4f}"},
            "stop": {"value": round(stop_price, 4), "label": f"${stop_price:.4f}", "note": "Below support"},
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
