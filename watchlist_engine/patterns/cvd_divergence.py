"""
CVD Divergence Pattern
=======================
Detects divergences between Cumulative Volume Delta (CVD) and price.

Key relationships:
- Bullish divergence: price makes lower low, CVD makes higher low → accumulation
- Bearish divergence: price makes higher high, CVD makes lower high → distribution
- CVD trending up >20% → aggressive buying pressure
- CVD trending down >20% → aggressive selling pressure

If CVD confirms the price move (e.g., price up + CVD up), it's NOT a divergence
— that's just healthy trend continuation, handled by other patterns.
"""
import numpy as np
from typing import Optional, Dict, Any


def detect(ohlcv_4h=None, ohlcv_1h=None, oi=None, oi_history=None,
           funding=None, ticker=None, cvd=None, order_book=None,
           **kwargs) -> Optional[Dict[str, Any]]:

    from ..book_cvd import compute_cvd_from_ohlcv

    if ohlcv_4h is None or len(ohlcv_4h) < 20:
        return None

    # Compute per-candle CVD and detect divergences
    cvd_analysis = compute_cvd_from_ohlcv(ohlcv_4h, ohlcv_1h)

    if not cvd_analysis["detected"]:
        # If no divergence, check if strong CVD trend exists
        trend = cvd_analysis.get("cvd_trend_pct", 0)
        if abs(trend) < 20:
            return None

    close = ohlcv_4h['close'].values
    last_price = float(close[-1])

    signal = cvd_analysis.get("signal", "neutral")
    note = cvd_analysis.get("analysis_note", "")

    if signal == "bullish_divergence":
        direction = "long"
        grade = "B"
        score = 6
        max_score = 9
        maturity = "Ready"
        confidence_pct = 65
        verdict_note = "Bullish CVD divergence — accumulation detected"
        warnings = []
        evidence = [note]

        # Stop below the recent low
        recent_low = float(np.min(close[-20:]))
        stop = recent_low * 0.985

        # Entry zone: near current price
        entry_low = last_price * 0.995
        entry_high = last_price * 1.005

        # TP based on ATR or recent high
        recent_high = float(np.max(close[-10:]))
        t1 = entry_low + (entry_high - stop) * 1.5
        t2 = entry_low + (entry_high - stop) * 3.0

    elif signal == "bearish_divergence":
        direction = "short"
        grade = "B"
        score = 6
        max_score = 9
        maturity = "Ready"
        confidence_pct = 65
        verdict_note = "Bearish CVD divergence — distribution detected"
        warnings = []
        evidence = [note]

        recent_high = float(np.max(close[-20:]))
        stop = recent_high * 1.015
        entry_low = last_price * 0.995
        entry_high = last_price * 1.005
        t1 = entry_high - (stop - entry_low) * 1.5
        t2 = entry_high - (stop - entry_low) * 3.0

    elif signal == "bullish":
        direction = "long"
        grade = "C"
        score = 4
        max_score = 9
        maturity = "Forming"
        confidence_pct = 55
        verdict_note = note
        warnings = ["Aggressive CVD without divergence — confirm with price action"]
        evidence = [note]
        recent_low = float(np.min(close[-10:]))
        stop = recent_low * 0.97
        entry_low = last_price * 0.99
        entry_high = last_price * 1.01
        t1 = entry_low + (entry_high - stop) * 1.5
        t2 = entry_low + (entry_high - stop) * 3.0

    elif signal == "bearish":
        direction = "short"
        grade = "C"
        score = 4
        max_score = 9
        maturity = "Forming"
        confidence_pct = 55
        verdict_note = note
        warnings = ["Aggressive CVD without divergence — confirm with price action"]
        evidence = [note]
        recent_high = float(np.max(close[-10:]))
        stop = recent_high * 1.03
        entry_low = last_price * 0.99
        entry_high = last_price * 1.01
        t1 = entry_high - (stop - entry_low) * 1.5
        t2 = entry_high - (stop - entry_low) * 3.0

    else:
        return None

    # Grade boost if divergence AND the aggregate CVD confirms
    if "divergence" in signal:
        trend = cvd_analysis.get("cvd_trend_pct", 0)
        if (direction == "long" and trend > 10) or (direction == "short" and trend < -10):
            grade = "A"
            score = 8
            confidence_pct = 75

    rr1 = abs((t1 - last_price) / (stop - last_price)) if abs(stop - last_price) > 0.001 else 0
    rr2 = abs((t2 - last_price) / (stop - last_price)) if abs(stop - last_price) > 0.001 else 0

    return {
        "pattern": "cvd_divergence",
        "name": "CVD Divergence",
        "direction": direction,
        "maturity": maturity,
        "grade": grade,
        "score": score,
        "max_score": max_score,
        "success_likelihood": {
            "percent": confidence_pct,
            "reason": verdict_note,
        },
        "entry": {
            "direction": direction,
            "zone": {
                "low": round(entry_low, 6),
                "high": round(entry_high, 6),
                "label": f"${entry_low:.4f} – ${entry_high:.4f}",
            },
            "stop": {
                "value": round(stop, 6),
                "label": f"${stop:.4f}",
                "note": "Below recent swing" if direction == "long" else "Above recent swing",
            },
            "risk": round(abs(stop - last_price), 6),
            "t1": {
                "value": round(t1, 6),
                "label": f"${t1:.4f}",
                "rr": f"~1 : {rr1:.1f}",
                "note": "CVD-based extension",
            },
            "t2": {
                "value": round(t2, 6),
                "label": f"${t2:.4f}",
                "rr": f"~1 : {rr2:.1f}",
                "note": "CVD-based extension",
            },
        },
        "confluence": {
            "strength": "STRONG" if grade == "A" else "MODERATE",
            "checks": evidence,
            "warnings": warnings,
        },
        "evidence": evidence,
        "missing": ["Confirm with structure/level"],
        "price": round(last_price, 6),
        "cvd_analysis": {
            "detected": cvd_analysis.get("detected", False),
            "signal": signal,
            "net_cvd": cvd_analysis.get("net_cvd_12_candles", 0),
            "cvd_trend_pct": cvd_analysis.get("cvd_trend_pct", 0),
            "note": note,
        },
    }