from __future__ import annotations

import pandas as pd

from app.data_loader import DerivativesData
from app.indicators import slope
from app.scoring.base import EngineResult, average, metric


def score(df: pd.DataFrame, derivatives: DerivativesData, config: dict) -> EngineResult | None:
    if not derivatives.available:
        return None
    metrics = {}
    if derivatives.oi_hist and len(derivatives.oi_hist) >= 2:
        prev = float(derivatives.oi_hist[-2]["sumOpenInterest"])
        current = float(derivatives.oi_hist[-1]["sumOpenInterest"])
        change = (current / prev - 1) * 100 if prev else 0.0
        metrics["Open Interest Change 1H"] = metric(change, 100 if change >= 5 else 75 if change >= 2 else 50 if change >= -1 else 0, "oi change")
        price_change = (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100
        metrics["Price + OI Relationship"] = metric(
            {"price_change_pct": float(price_change), "oi_change_pct": change},
            100 if price_change > 0 and change > 0 else 75 if abs(price_change) < 0.15 and change > 0 else 50 if price_change > 0 and abs(change) < 1 else 0,
            "relationship",
        )
    if derivatives.funding_rate is not None:
        funding_pct = derivatives.funding_rate * 100
        metrics["Funding Rate"] = metric(
            funding_pct,
            100 if 0 <= funding_pct <= 0.03 else 75 if 0.03 < funding_pct <= 0.06 else 50 if funding_pct < 0 else 0,
            "funding",
        )
    cvd = (df["taker_buy_base"] - (df["volume"] - df["taker_buy_base"])).cumsum()
    cvd_slope = slope(cvd, 20)
    new_high = bool(cvd.iloc[-1] >= cvd.iloc[-20:].max())
    metrics["CVD Trend"] = metric({"slope20": cvd_slope, "new_20bar_high": new_high}, 100 if new_high else 75 if cvd_slope > 0 else 50 if abs(cvd_slope) < df["volume"].mean() * 0.05 else 0, "cvd")
    if derivatives.taker_ratio:
        ratio = float(derivatives.taker_ratio[-1]["buySellRatio"])
        buy_pct = ratio / (1 + ratio) * 100
        metrics["Taker Buy Ratio"] = metric(buy_pct, 100 if buy_pct >= 55 else 75 if buy_pct >= 52 else 50 if buy_pct >= 48 else 0, "taker buy")
    if derivatives.long_short_ratio:
        ratio = float(derivatives.long_short_ratio[-1]["longShortRatio"])
        metrics["Long / Short Ratio"] = metric(ratio, 100 if 0.9 <= ratio <= 1.3 else 75 if 0.8 <= ratio < 0.9 or 1.3 < ratio <= 1.6 else 0 if ratio > 1.8 else 50, "long short")
    metrics["Liquidation Context"] = metric(None, None, "unavailable from public endpoints")
    evidence = [f"{k}: {v['bucket']}" for k, v in metrics.items() if v["score"] and v["score"] >= 75]
    missing = [f"{k}: {v['bucket']}" for k, v in metrics.items() if v["score"] == 0]
    return EngineResult("Smart Money", round(average([v["score"] for v in metrics.values()]), 2), metrics, evidence, missing)
