"""Deleveraging at the flush: does open interest behaviour separate durable
lows from knives?

Hypothesis: durable lows are liquidation-driven — OI is forcibly flushed into
the low (the selling is involuntary and finite). Knives are voluntary selling —
OI stays comparatively intact and the decline continues.

Features per flush (5-min metrics resampled to 15m, OI as-of each bar close):
  oi_chg_1h / _4h / _8h  – % change in OI into the flush bar
  oi_chg_post_2h         – % change in the 2h after the low (rebuild vs unwind)
  ttls_chg_4h            – top-trader long/short ratio change into the low
  gls_chg_4h             – global (count) long/short ratio change into the low
  taker_ls               – taker buy/sell vol ratio at the low (z vs baseline)

Output: AUC durable-vs-knife per feature, durable-rate by OI-flush quartile,
and incremental value over the flush-anatomy trio (grouped-CV logistic).
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "breakout_precursors"))
from config import METRICS_DIR              # noqa: E402
from derivatives import fetch_metrics_day   # noqa: E402

RESULTS = os.path.join(HERE, "results")
EPS = 1e-12


def days_for(t_open_ms):
    t0 = pd.Timestamp(t_open_ms, unit="ms", tz="UTC")
    return [d.strftime("%Y-%m-%d") for d in
            pd.date_range((t0 - pd.Timedelta(hours=34)).floor("D"),
                          (t0 + pd.Timedelta(hours=14)).floor("D"), freq="D")]


def metric_series(symbol, days):
    frames = []
    for d in days:
        p = os.path.join(METRICS_DIR, f"{symbol}_{d}.pkl")
        if os.path.exists(p):
            df = pd.read_pickle(p)
            if len(df):
                frames.append(df)
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df["create_time"], utc=True, format="mixed")
    m = df.drop_duplicates("ts").set_index("ts").sort_index() \
          .resample("15min").last()
    return m


def main():
    cands = [c for c in json.load(open(os.path.join(RESULTS,
                                                    "candidates.json")))
             if c["label"] in ("durable", "knife")]

    # ---- phase 1: download missing metric days ----
    need = set()
    for r in cands:
        for d in days_for(r["t_open_ms"]):
            need.add((r["symbol"], d))
    missing = [(s, d) for s, d in sorted(need)
               if not os.path.exists(os.path.join(METRICS_DIR,
                                                  f"{s}_{d}.pkl"))]
    print(f"{len(cands)} flushes, {len(need)} symbol-days, "
          f"{len(missing)} to download", flush=True)
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(fetch_metrics_day, s, d) for s, d in missing]
        for k, _ in enumerate(as_completed(futs)):
            if (k + 1) % 1000 == 0:
                print(f"downloaded {k + 1}/{len(missing)}", flush=True)
    print("download phase complete", flush=True)

    # ---- phase 2: features per flush ----
    by_sym = {}
    for r in cands:
        by_sym.setdefault(r["symbol"], []).append(r)
    rows = []
    for sym, recs in sorted(by_sym.items()):
        all_days = sorted({d for r in recs for d in days_for(r["t_open_ms"])})
        m = metric_series(sym, all_days)
        if m is None:
            continue
        oi = m["sum_open_interest"].astype(float)
        ttls = m["sum_toptrader_long_short_ratio"].astype(float)
        gls = m["count_long_short_ratio"].astype(float)
        tls = m["sum_taker_long_short_vol_ratio"].astype(float)
        for r in recs:
            t = pd.Timestamp(r["t_open_ms"], unit="ms", tz="UTC")

            def at(s, k):          # value as-of k bars from flush bar
                return s.get(t + pd.Timedelta(minutes=15 * k), np.nan)

            o0 = at(oi, 0)
            if not np.isfinite(o0) or o0 <= 0:
                continue
            row = {"label": r["label"], "symbol": sym}
            for name, k in [("oi_chg_1h", -4), ("oi_chg_4h", -16),
                            ("oi_chg_8h", -32)]:
                prev = at(oi, k)
                row[name] = o0 / prev - 1 if np.isfinite(prev) and prev > 0 \
                    else np.nan
            post = at(oi, 8)
            row["oi_chg_post_2h"] = post / o0 - 1 \
                if np.isfinite(post) and post > 0 else np.nan
            t0v, t4v = at(ttls, 0), at(ttls, -16)
            row["ttls_chg_4h"] = t0v / t4v - 1 \
                if np.isfinite(t0v) and np.isfinite(t4v) and t4v > 0 else np.nan
            g0, g4 = at(gls, 0), at(gls, -16)
            row["gls_chg_4h"] = g0 / g4 - 1 \
                if np.isfinite(g0) and np.isfinite(g4) and g4 > 0 else np.nan
            row["taker_ls"] = at(tls, 0)
            rows.append(row)
        print(f"{sym}: {len(recs)} flushes", flush=True)

    df = pd.DataFrame(rows)
    df.to_pickle(os.path.join(RESULTS, "deleveraging.pkl"))
    print(f"\n{len(df)} flushes with OI data "
          f"({(df.label == 'durable').mean():.1%} durable)", flush=True)

    # ---- phase 3: analysis ----
    from scipy.stats import mannwhitneyu
    dur = (df["label"] == "durable").values
    print("\nAUC durable vs knife (>0.5 = higher value -> more durable):")
    for col in ["oi_chg_1h", "oi_chg_4h", "oi_chg_8h", "oi_chg_post_2h",
                "ttls_chg_4h", "gls_chg_4h", "taker_ls"]:
        x = df[col].values
        a = x[dur & np.isfinite(x)]
        b = x[~dur & np.isfinite(x)]
        if len(a) < 100 or len(b) < 100:
            continue
        u, p = mannwhitneyu(a, b)
        print(f"  {col:16} AUC={u / (len(a) * len(b)):.3f}  p={p:.1e}  "
              f"n={len(a) + len(b)}")

    print("\nDurable rate by OI-flush quartile (oi_chg_4h, most negative "
          "= biggest deleveraging):")
    x = df["oi_chg_4h"]
    ok = np.isfinite(x)
    q = pd.qcut(x[ok], 4, labels=["Q1 biggest OI dump", "Q2", "Q3",
                                  "Q4 OI intact/rising"])
    for lab in q.cat.categories:
        m = q == lab
        print(f"  {lab:20} durable rate = "
              f"{dur[ok.values][m.values].mean():.1%}  (n={m.sum()})")

    # incremental value over anatomy (needs windows.pkl z at offset 0)
    import pickle
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    with open(os.path.join(RESULTS, "windows.pkl"), "rb") as f:
        W = pickle.load(f)
    meta = W["meta"].reset_index(drop=True)
    oi_idx = {o: i for i, o in enumerate(W["offsets"])}
    # rebuild t_open_ms per row (rows were appended in the same per-symbol
    # record order, with the same finite-OI filter)
    t_ms = []
    for sym, recs in sorted(by_sym.items()):
        m = metric_series(sym, sorted({d for r in recs
                                       for d in days_for(r["t_open_ms"])}))
        if m is None:
            continue
        oi_s = m["sum_open_interest"].astype(float)
        for r in recs:
            t = pd.Timestamp(r["t_open_ms"], unit="ms", tz="UTC")
            v = oi_s.get(t, np.nan)
            if np.isfinite(v) and v > 0:
                t_ms.append((sym, r["t_open_ms"]))
    df["t_open_ms"] = [k[1] for k in t_ms]
    merged = meta.merge(df, on=["symbol", "t_open_ms"], how="inner",
                        suffixes=("", "_d"))
    anat = ["clv", "lower_wick_frac", "body_frac", "volume_z"]
    rowsel = meta.set_index(["symbol", "t_open_ms"]).index \
        .get_indexer(merged.set_index(["symbol", "t_open_ms"]).index)
    Xa = np.column_stack([W["z"][f][rowsel, oi_idx[0]] for f in anat])
    Xoi = merged[["oi_chg_1h", "oi_chg_4h", "oi_chg_post_2h"]].values
    yb = (merged["label"] == "durable").astype(int).values
    g = merged["symbol"].values
    for name, X in [("anatomy only", Xa),
                    ("anatomy + OI", np.column_stack([Xa, Xoi]))]:
        okm = np.isfinite(X).all(axis=1)
        aucs = []
        for tr, te in GroupKFold(5).split(X[okm], yb[okm], g[okm]):
            mdl = LogisticRegression(max_iter=2000, C=0.5)
            mdl.fit(X[okm][tr], yb[okm][tr])
            aucs.append(roc_auc_score(yb[okm][te],
                                      mdl.predict_proba(X[okm][te])[:, 1]))
        print(f"\n{name}: grouped-CV AUC = {np.mean(aucs):.3f} "
              f"+/- {np.std(aucs):.3f} (n={okm.sum()})")


if __name__ == "__main__":
    main()
