"""Backtest confirmation triggers after candidate lows.

For each candidate low bar t (raw 15m OHLCV), scan bars j = t+1 .. t+12.
A rule 'fires' at the first j where its condition holds, PROVIDED the stop
(L - 0.75*ATR) has not been breached at any bar in t+1..j (knife already
falling = no entry). Entry = close[j]. Then from bar j+1 (or the remainder of
the trade horizon), outcome = target (L + 3*ATR) before stop, same-bar both ->
loss (conservative). R multiple: win = (target - entry)/(entry - stop),
loss = -1. Horizon for everything: 48 bars from t.

Rules:
  T0 flush_close   enter at close[t] immediately (no confirmation baseline)
  T1 reclaim_high  close[j] > high[t]
  T2 reclaim_open  close[j] > open[t]
  T3 reclaim_vol   close[j] > open[t] AND volume_z[j] >= 1
  T4 two_higher    close[j] > close[j-1] > close[j-2] AND CLV[j] >= 0.5
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "breakout_precursors"))
from config import KLINES_DIR  # noqa: E402

RESULTS = os.path.join(HERE, "results")
HORIZON = 48
MAX_TRIG = 12
STOP_ATR = 0.75
TARGET_ATR = 3.0
EPS = 1e-12


def simulate(sym, recs, df):
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    v = df["volume"].values
    vmean = pd.Series(v).rolling(96, min_periods=48).mean().values
    vstd = pd.Series(v).rolling(96, min_periods=48).std().values
    vz = (v - vmean) / (vstd + EPS)
    rng = h - l
    clv = ((c - l) - (h - c)) / (rng + EPS)
    idx_of = pd.Series(np.arange(len(df)), index=df["open_time"].values)

    out = []
    for r in recs:
        t = idx_of.get(r["t_open_ms"])
        if t is None or t + HORIZON >= len(df):
            continue
        L, A = r["low"], r["atr"]
        stop, target = L - STOP_ATR * A, L + TARGET_ATR * A
        rules = {}

        def outcome(entry_j):
            entry = c[entry_j]
            if entry <= stop or entry >= target:
                return None
            risk = entry - stop
            end = t + 1 + HORIZON
            # MFE before stop-hit: how far the trade runs if not capped at target
            mfe = 0.0
            res = None
            for j in range(entry_j + 1, end):
                hit_s, hit_t = l[j] <= stop, h[j] >= target
                if hit_s:
                    mfe = max(mfe, (h[j] - entry) / risk)
                    if res is None:
                        res = {"win": False, "r": -1.0}
                    break
                mfe = max(mfe, (h[j] - entry) / risk)
                if hit_t and res is None:
                    res = {"win": True, "r": (target - entry) / risk}
            if res is None:
                res = {"win": None, "r": (c[end - 1] - entry) / risk}
            res.update({"giveback": (entry - L) / A,
                        "bars_after_low": entry_j - t, "mfe_r": mfe})
            return res

        rules["T0_flush_close"] = outcome(t)

        stopped = False
        fired = {k: False for k in ("T1_reclaim_high", "T2_reclaim_open",
                                    "T3_reclaim_vol", "T4_two_higher")}
        for j in range(t + 1, t + 1 + MAX_TRIG):
            if l[j] <= stop:
                stopped = True
                break
            conds = {
                "T1_reclaim_high": c[j] > h[t],
                "T2_reclaim_open": c[j] > o[t],
                "T3_reclaim_vol": c[j] > o[t] and vz[j] >= 1,
                "T4_two_higher": (c[j] > c[j - 1] > c[j - 2]
                                  and clv[j] >= 0.5),
            }
            for k, cond in conds.items():
                if cond and not fired[k]:
                    fired[k] = True
                    rules[k] = outcome(j)
            if all(fired.values()):
                break
        for k in fired:
            if k not in rules:
                rules[k] = "stopped_first" if stopped else "no_trigger"
        out.append({"label": r["label"], "rules": rules})
    return out


def main():
    cands = json.load(open(os.path.join(RESULTS, "candidates.json")))
    cands = [x for x in cands if x["label"] in ("durable", "knife")]
    by_sym = {}
    for x in cands:
        by_sym.setdefault(x["symbol"], []).append(x)
    sims = []
    for sym, recs in sorted(by_sym.items()):
        df = pd.read_pickle(os.path.join(KLINES_DIR, f"{sym}_15m.pkl"))
        sims += simulate(sym, recs, df)
    print(f"{len(sims)} candidates simulated\n")

    names = ["T0_flush_close", "T1_reclaim_high", "T2_reclaim_open",
             "T3_reclaim_vol", "T4_two_higher"]
    rows = []
    for name in names:
        entered = [s for s in sims if isinstance(s["rules"].get(name), dict)]
        ent_d = [s for s in entered if s["label"] == "durable"]
        ent_k = [s for s in entered if s["label"] == "knife"]
        res = [s["rules"][name] for s in entered]
        decided = [x for x in res if x["win"] is not None]
        wins = [x for x in decided if x["win"]]
        n_d = sum(1 for s in sims if s["label"] == "durable")
        n_k = sum(1 for s in sims if s["label"] == "knife")
        exp = (np.mean([x["r"] for x in decided]) if decided else np.nan)
        rows.append({
            "rule": name,
            "entries": len(entered),
            "pct_durables_entered": len(ent_d) / n_d,
            "pct_knives_entered": len(ent_k) / n_k,
            "win_rate": len(wins) / len(decided) if decided else np.nan,
            "expectancy_R": exp,
            "med_giveback_atr": float(np.median([x["giveback"]
                                                 for x in res])),
            "med_bars_after_low": float(np.median([x["bars_after_low"]
                                                   for x in res])),
            "med_mfe_R": float(np.median([x["mfe_r"] for x in res])),
            "p75_mfe_R": float(np.percentile([x["mfe_r"] for x in res], 75)),
            "med_mfe_R_durable": float(np.median(
                [s["rules"][name]["mfe_r"] for s in ent_d])),
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS, "trigger_stats.csv"), index=False)
    with pd.option_context("display.width", 200):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
