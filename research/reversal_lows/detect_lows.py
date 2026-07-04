"""Detect capitulation-low candidates on 15m and label durable-low vs knife.

Candidate bar t (all conditions, completed 15m bars):
  * new-low:   low[t] = min(low[t-95 .. t])          (fresh 24h low)
  * decline:   96-bar high -> low[t] drop >= 8 x ATR14[t]
  * leg:       32-bar high -> low[t] drop >= 4 x ATR14[t]   (active leg, not drift)
  * warm-up:   >= 176 prior bars; dedup: >= 16 bars since previous candidate
    (successive new lows in one decline create successive candidates — deliberate:
     each was a catchable-looking low in real time)

Label from L = low[t], A = ATR14[t], within the next 48 bars (12h):
  * DURABLE: high reaches L + 3A before low reaches L - 0.75A
  * KNIFE:   low reaches L - 0.75A first (incl. same-bar ambiguity -> KNIFE)
  * UNDECIDED: neither within horizon -> dropped (counted)

Event-level extras captured at t:
  * rsi_div: RSI14[t] - RSI14[prev candidate in the same 96-bar window] (NaN if none)
  * flush metrics come from the feature windows at offset 0 (volume z, wick, CLV...)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "breakout_precursors"))
from config import KLINES_DIR  # noqa: E402

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

RALLY_ATR = 3.0
STOP_ATR = 0.75
HORIZON = 48
DECLINE_96_ATR = 8.0
DECLINE_32_ATR = 4.0
DEDUP = 16
WARMUP = 176


def atr14(df):
    pc = df["close"].shift(1)
    tr = np.maximum(df["high"] - df["low"],
                    np.maximum((df["high"] - pc).abs(),
                               (df["low"] - pc).abs()))
    return tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()


def rsi14(close):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14,
                                adjust=False).mean()
    return 100 - 100 / (1 + up / (dn + 1e-12))


def detect_symbol(sym, df):
    h, l = df["high"].values, df["low"].values
    n = len(df)
    a = atr14(df).values
    rsi = rsi14(df["close"]).values
    low96 = pd.Series(l).rolling(96).min().values
    hi96 = pd.Series(h).rolling(96).max().values
    hi32 = pd.Series(h).rolling(32).max().values

    out = []
    last_cand = -10**9
    prev_cands = []          # (index, rsi) of recent candidates
    for t in range(WARMUP, n - 1):
        A = a[t]
        if not np.isfinite(A) or A <= 0 or not np.isfinite(low96[t]):
            continue
        if l[t] > low96[t] + 1e-15:
            continue                          # not a fresh 96-bar low
        if (hi96[t] - l[t]) < DECLINE_96_ATR * A:
            continue
        if (hi32[t] - l[t]) < DECLINE_32_ATR * A:
            continue
        if t - last_cand < DEDUP:
            continue
        last_cand = t

        L = l[t]
        target, stop = L + RALLY_ATR * A, L - STOP_ATR * A
        label = None
        for j in range(t + 1, min(n, t + 1 + HORIZON)):
            hit_t, hit_s = h[j] >= target, l[j] <= stop
            if hit_s:                          # ambiguity -> KNIFE (conservative)
                label = "knife"
                break
            if hit_t:
                label = "durable"
                break
        if label is None:
            label = "undecided"

        prev = [(i, r) for i, r in prev_cands if t - i <= 96]
        rsi_div = float(rsi[t] - prev[-1][1]) if prev else np.nan
        prev_cands = prev + [(t, rsi[t])]

        out.append({
            "symbol": sym,
            "t_open_ms": int(df["open_time"].iloc[t]),
            "low": float(L), "atr": float(A), "label": label,
            "rsi": float(rsi[t]) if np.isfinite(rsi[t]) else None,
            "rsi_div": None if np.isnan(rsi_div) else rsi_div,
            "decline_96_atr": float((hi96[t] - L) / A),
        })
    return out


def main():
    os.makedirs(RESULTS, exist_ok=True)
    all_c = []
    for f in sorted(os.listdir(KLINES_DIR)):
        if not f.endswith("_15m.pkl"):
            continue
        sym = f.replace("_15m.pkl", "")
        df = pd.read_pickle(os.path.join(KLINES_DIR, f))
        c = detect_symbol(sym, df)
        all_c += c
        counts = pd.Series([x["label"] for x in c]).value_counts().to_dict()
        print(f"{sym}: {len(c)} candidates {counts}", flush=True)
    json.dump(all_c, open(os.path.join(RESULTS, "candidates.json"), "w"))
    s = pd.Series([x["label"] for x in all_c]).value_counts()
    print(f"\nTOTAL {len(all_c)} candidates: {s.to_dict()}")
    dk = s.get("durable", 0) + s.get("knife", 0)
    print(f"base rate durable among decided: {s.get('durable', 0) / dk:.1%}")


if __name__ == "__main__":
    main()
