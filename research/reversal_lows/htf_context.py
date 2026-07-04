"""HTF-context conditioning: does the higher-timeframe situation at the flush
change the durable rate? (The conditional-odds table for the scanner.)

Context per flush, all computable from the 15m data already on disk:
  pos_90d        – flush low's position in the trailing 90-day range (0 = at the
                   bottom, 1 = at the top)
  time_at_price  – fraction of the prior 90 daily bars whose range contains the
                   flush low: high = landing in prior congestion ("support"),
                   low = mid-air / fresh territory
  is_90d_low     – flush low undercuts everything in the prior 90 days
  daily_trend    – (prev daily close − daily EMA50) / daily ATR14
  btc_ret_4h/24h – BTC return into the same moment
  btc_trend_4h   – BTC close vs EMA50 on 4H at the same moment

Outputs: AUC per context feature, durable-rate bucket tables, the combined
conditional-odds table, and incremental value over anatomy (grouped CV).
"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "breakout_precursors"))
from config import KLINES_DIR  # noqa: E402

RESULTS = os.path.join(HERE, "results")
EPS = 1e-12


def daily_frame(df15):
    d = df15.set_index("ts").resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    pc = d["close"].shift(1)
    tr = np.maximum(d["high"] - d["low"],
                    np.maximum((d["high"] - pc).abs(), (d["low"] - pc).abs()))
    d["atr"] = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    d["ema50"] = d["close"].ewm(span=50, min_periods=30, adjust=False).mean()
    return d


def main():
    cands = [c for c in json.load(open(os.path.join(RESULTS,
                                                    "candidates.json")))
             if c["label"] in ("durable", "knife")]
    by_sym = {}
    for c in cands:
        by_sym.setdefault(c["symbol"], []).append(c)

    btc15 = pd.read_pickle(os.path.join(KLINES_DIR, "BTCUSDT_15m.pkl"))
    btc_close = pd.Series(btc15["close"].values, index=btc15["open_time"].values)
    btc4h = btc15.set_index("ts")["close"].resample("4h").last()
    btc4h_ema = btc4h.ewm(span=50, min_periods=30, adjust=False).mean()

    rows = []
    for sym, recs in sorted(by_sym.items()):
        df = pd.read_pickle(os.path.join(KLINES_DIR, f"{sym}_15m.pkl"))
        d = daily_frame(df)
        dl, dh = d["low"].values, d["high"].values
        didx = d.index
        for r in recs:
            t = pd.Timestamp(r["t_open_ms"], unit="ms", tz="UTC")
            L = r["low"]
            day_i = didx.searchsorted(t.floor("D"))
            if day_i < 60 or day_i >= len(d):
                continue
            w_lo, w_hi = dl[day_i - 90:day_i], dh[day_i - 90:day_i]
            w_lo = w_lo[np.isfinite(w_lo)]
            w_hi = w_hi[:len(w_lo)]
            if len(w_lo) < 30:
                continue
            rng_lo, rng_hi = w_lo.min(), w_hi.max()
            prev = d.iloc[day_i - 1]
            row = {
                "symbol": sym, "t_open_ms": r["t_open_ms"],
                "label": r["label"],
                "pos_90d": (L - rng_lo) / max(rng_hi - rng_lo, EPS),
                "time_at_price": float(np.mean((w_lo <= L) & (L <= w_hi))),
                "is_90d_low": bool(L < rng_lo),
                "daily_trend": (prev["close"] - prev["ema50"])
                               / max(prev["atr"], EPS)
                               if np.isfinite(prev["ema50"])
                               and np.isfinite(prev["atr"]) else np.nan,
            }
            b0 = btc_close.get(r["t_open_ms"], np.nan)
            b4 = btc_close.get(r["t_open_ms"] - 16 * 900000, np.nan)
            b24 = btc_close.get(r["t_open_ms"] - 96 * 900000, np.nan)
            row["btc_ret_4h"] = b0 / b4 - 1 if np.isfinite(b0) and \
                np.isfinite(b4) else np.nan
            row["btc_ret_24h"] = b0 / b24 - 1 if np.isfinite(b0) and \
                np.isfinite(b24) else np.nan
            k = btc4h.index.searchsorted(t) - 1
            row["btc_above_ema"] = bool(btc4h.iloc[k] > btc4h_ema.iloc[k]) \
                if 0 <= k < len(btc4h) and np.isfinite(btc4h_ema.iloc[k]) \
                else None
            rows.append(row)
        print(f"{sym}: done", flush=True)

    df = pd.DataFrame(rows)
    df.to_pickle(os.path.join(RESULTS, "htf_context.pkl"))
    dur = (df["label"] == "durable").values
    print(f"\n{len(df)} flushes with HTF context ({dur.mean():.1%} durable)\n")

    print("AUC durable vs knife:")
    for col in ["pos_90d", "time_at_price", "daily_trend", "btc_ret_4h",
                "btc_ret_24h"]:
        x = df[col].values
        a, b = x[dur & np.isfinite(x)], x[~dur & np.isfinite(x)]
        u, p = mannwhitneyu(a, b)
        print(f"  {col:14} AUC={u / (len(a) * len(b)):.3f}  p={p:.1e}")

    def rate(mask):
        return f"{dur[mask].mean():.1%} (n={mask.sum()})"

    print("\nDurable rate by bucket:")
    for col, edges in [("time_at_price", [0, 0.05, 0.2, 0.5, 1.01]),
                       ("pos_90d", [-9, 0.02, 0.15, 0.4, 9]),
                       ("daily_trend", [-99, -3, -1, 0, 99]),
                       ("btc_ret_4h", [-9, -0.01, 0, 0.01, 9])]:
        x = df[col].values
        print(f"  {col}:")
        for i in range(len(edges) - 1):
            m = np.isfinite(x) & (x >= edges[i]) & (x < edges[i + 1])
            if m.sum() > 100:
                print(f"    [{edges[i]:>5} .. {edges[i + 1]:<5}): {rate(m)}")
    m = df["is_90d_low"].values.astype(bool)
    print(f"  fresh 90-day low: {rate(m)}   vs not: {rate(~m)}")
    mb = df["btc_above_ema"].astype("boolean")
    print(f"  BTC 4H above EMA50: {rate((mb == True).values)}   "
          f"below: {rate((mb == False).values)}")

    print("\nCombined conditional-odds table "
          "(congestion = time_at_price >= 0.2):")
    cong = np.isfinite(df["time_at_price"].values) & \
        (df["time_at_price"].values >= 0.2)
    btc_up = (mb == True).values
    for name, m in [("congestion + BTC up", cong & btc_up),
                    ("congestion + BTC down", cong & ~btc_up),
                    ("mid-air + BTC up", ~cong & btc_up),
                    ("mid-air + BTC down", ~cong & ~btc_up)]:
        print(f"  {name:24} {rate(m)}")

    # incremental over anatomy
    with open(os.path.join(RESULTS, "windows.pkl"), "rb") as f:
        W = pickle.load(f)
    meta = W["meta"].reset_index(drop=True)
    oz = {o: i for i, o in enumerate(W["offsets"])}
    merged = meta.merge(df, on=["symbol", "t_open_ms"], how="inner",
                        suffixes=("", "_h"))
    sel = meta.set_index(["symbol", "t_open_ms"]).index.get_indexer(
        merged.set_index(["symbol", "t_open_ms"]).index)
    anat = ["clv", "lower_wick_frac", "body_frac", "volume_z"]
    Xa = np.column_stack([W["z"][f][sel, oz[0]] for f in anat])
    Xh = merged[["pos_90d", "time_at_price", "daily_trend", "btc_ret_4h",
                 "btc_ret_24h"]].values
    Xh = np.column_stack([Xh, merged["is_90d_low"].astype(float).values,
                          merged["btc_above_ema"].astype("boolean")
                          .astype("Float64").to_numpy(dtype=float,
                                                      na_value=np.nan)])
    yb = (merged["label"] == "durable").astype(int).values
    g = merged["symbol"].values
    for name, X in [("anatomy only", Xa), ("HTF only", Xh),
                    ("anatomy + HTF", np.column_stack([Xa, Xh]))]:
        okm = np.isfinite(X).all(axis=1)
        aucs = []
        for tr, te in GroupKFold(5).split(X[okm], yb[okm], g[okm]):
            mdl = LogisticRegression(max_iter=2000, C=0.5)
            mdl.fit(X[okm][tr], yb[okm][tr])
            aucs.append(roc_auc_score(yb[okm][te],
                                      mdl.predict_proba(X[okm][te])[:, 1]))
        print(f"{name:14}: grouped-CV AUC = {np.mean(aucs):.3f} "
              f"+/- {np.std(aucs):.3f} (n={okm.sum()})")


if __name__ == "__main__":
    main()
