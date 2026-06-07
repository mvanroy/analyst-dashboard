"""Deterministic rules engine: shortlist + breakout/reversal regime.

Mirrors the manual Market Scanner workflow:
  1. rank by TRD (5M), excluding majors for the altcoin shortlist
  2. drop anything under the volume floor, backfill from next-highest TRD
  3. narrow to the biggest movers by |Change 1D|
The regime read scores the breakout vs reversal matrix on what a single
snapshot can actually measure (baseline-dependent signals are skipped).
"""
from __future__ import annotations

MAJORS = {"BTCUSDT", "ETHUSDT", "BTCUSDC", "ETHUSDC"}


def build_shortlist(df, min_vol=500_000, top_n=10, pick=6, exclude_majors=True):
    if df.empty:
        return df
    d = df.copy()
    if exclude_majors:
        d = d[~d["symbol"].isin(MAJORS)]
    d = d.sort_values("trd5m", ascending=False)
    passing = d[d["vol5m"] >= min_vol].head(top_n)
    if passing.empty:
        return passing
    passing = passing.assign(_mag=passing["chg1d"].abs())
    return (
        passing.sort_values("_mag", ascending=False)
        .head(pick)
        .drop(columns="_mag")
        .reset_index(drop=True)
    )


def detect_regime(df, min_vol=500_000):
    liquid = df[df["vol5m"] >= min_vol]
    alts = liquid[~liquid["symbol"].isin(MAJORS)].dropna(subset=["chg1d"])
    if alts.empty:
        return {
            "regime": "Unknown",
            "breakout_score": 0,
            "reversal_score": 0,
            "reasons": ["No liquid altcoins above the volume floor."],
        }

    top_gain = alts["chg1d"].max()
    top_loss = alts["chg1d"].min()
    extreme = int((alts["chg1d"] >= 15).sum())
    directional_5m = int((alts["chg5m"].abs() >= 1).sum())
    pct_green = float((alts["chg1d"] > 0).mean())
    vol_breadth = int((alts["vol5m"] >= 2_000_000).sum())
    spike_rev = int(((alts["chg1d"] >= 15) & (alts["chg5m"] < 0)).sum())

    b = 0
    r = 0
    reasons = []

    # --- breakout signals ---
    if extreme >= 2:
        b += 1
        reasons.append(f"Breakout: {extreme} coins up >=15% on the day (extreme gainers).")
    if directional_5m >= max(3, int(0.15 * len(alts))):
        b += 1
        reasons.append(f"Breakout: {directional_5m} coins with clean >=1% 5M moves.")
    if vol_breadth >= 8:
        b += 1
        reasons.append(f"Breakout: broad volume ({vol_breadth} coins > $2M / 5M).")

    # --- reversal signals ---
    if 0.35 <= pct_green <= 0.65:
        r += 1
        reasons.append(
            f"Reversal: mixed tape ({pct_green*100:.0f}% green / {(1-pct_green)*100:.0f}% red)."
        )
    if top_gain < 8 and top_loss > -8:
        r += 1
        reasons.append(
            f"Reversal: low magnitude (top gainer +{top_gain:.1f}%, top loser {top_loss:.1f}%)."
        )
    if spike_rev >= 1:
        r += 1
        reasons.append(
            f"Reversal: {spike_rev} parabolic gainer(s) now red on 5M (spike & stall)."
        )

    if b > r:
        regime = "Breakout"
    elif r > b:
        regime = "Reversal"
    else:
        regime = "Mixed"

    reasons.append(
        "Note: 'TRD vs recent sessions' not scored — a single snapshot has no baseline."
    )
    return {
        "regime": regime,
        "breakout_score": b,
        "reversal_score": r,
        "reasons": reasons,
    }
