"""PROVISIONAL Learned Model — grading engine trained on flush outcomes.

Additive artifact: writes results/learned_model.pkl; changes nothing else.
Rollback = delete that file. The Rulebook (framework/reversal_low_scanner.md)
remains the official grader.

Inputs per flush (all knowable at the flush bar close):
  anatomy z (offset 0): clv, lower_wick_frac, body_frac, volume_z
  tail: tail_atr, tail_frac
  OI (per user request, despite weak standalone result): oi_chg_1h/4h/8h
  HTF (per user request, despite weak standalone result): pos_90d,
      time_at_price, is_90d_low, daily_trend, btc_ret_4h, btc_ret_24h,
      btc_above_ema

Protocol: train 2024-2025, exam on unseen 2026; then refit on all data for
live use. HistGradientBoosting (handles missing values natively).
"""
import os
import pickle
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "breakout_precursors"))
from config import KLINES_DIR                    # noqa: E402
from deleveraging import days_for, metric_series  # noqa: E402

RESULTS = os.path.join(HERE, "results")

ANAT = ["clv", "lower_wick_frac", "body_frac", "volume_z"]
FEATURES = ["z_clv", "z_wick", "z_body", "z_vol", "tail_atr", "tail_frac",
            "oi_chg_1h", "oi_chg_4h", "oi_chg_8h",
            "pos_90d", "time_at_price", "is_90d_low", "daily_trend",
            "btc_ret_4h", "btc_ret_24h", "btc_above_ema"]


def main():
    with open(os.path.join(RESULTS, "windows.pkl"), "rb") as f:
        W = pickle.load(f)
    meta = W["meta"].reset_index(drop=True)
    oz = {o: i for i, o in enumerate(W["offsets"])}
    base = meta[["symbol", "t_open_ms", "label", "low", "atr"]].copy()
    for col, feat in zip(["z_clv", "z_wick", "z_body", "z_vol"], ANAT):
        base[col] = W["z"][feat][:, oz[0]]

    # tail features from raw klines
    tails = {}
    for sym in base["symbol"].unique():
        df = pd.read_pickle(os.path.join(KLINES_DIR, f"{sym}_15m.pkl"))
        o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
        idx = pd.Series(np.arange(len(df)), index=df["open_time"].values)
        for _, r in base[base.symbol == sym].iterrows():
            t = idx.get(r["t_open_ms"])
            if t is None:
                continue
            rng = h[t] - l[t]
            tail = min(o[t], c[t]) - l[t]
            tails[(sym, r["t_open_ms"])] = (tail / r["atr"],
                                            tail / (rng + 1e-12))
    base["tail_atr"] = [tails.get(k, (np.nan,) * 2)[0]
                        for k in zip(base.symbol, base.t_open_ms)]
    base["tail_frac"] = [tails.get(k, (np.nan,) * 2)[1]
                         for k in zip(base.symbol, base.t_open_ms)]
    print("tail features done", flush=True)

    # OI features from cached metrics
    oi_rows = {}
    for sym, grp in base.groupby("symbol"):
        days = sorted({d for t in grp.t_open_ms for d in days_for(t)})
        m = metric_series(sym, days)
        if m is None:
            continue
        oi = m["sum_open_interest"].astype(float)
        for t in grp.t_open_ms:
            ts = pd.Timestamp(t, unit="ms", tz="UTC")

            def at(k):
                return oi.get(ts + pd.Timedelta(minutes=15 * k), np.nan)

            o0 = at(0)
            if not np.isfinite(o0) or o0 <= 0:
                continue
            vals = []
            for k in (-4, -16, -32):
                p = at(k)
                vals.append(o0 / p - 1 if np.isfinite(p) and p > 0 else np.nan)
            oi_rows[(sym, t)] = vals
        print(f"oi {sym}", flush=True)
    for j, col in enumerate(["oi_chg_1h", "oi_chg_4h", "oi_chg_8h"]):
        base[col] = [oi_rows.get(k, (np.nan,) * 3)[j]
                     for k in zip(base.symbol, base.t_open_ms)]

    # HTF features
    htf = pd.read_pickle(os.path.join(RESULTS, "htf_context.pkl"))
    htf = htf.drop(columns=["label"])
    htf["is_90d_low"] = htf["is_90d_low"].astype(float)
    htf["btc_above_ema"] = htf["btc_above_ema"].astype("boolean") \
        .astype("Float64").to_numpy(dtype=float, na_value=np.nan)
    df = base.merge(htf, on=["symbol", "t_open_ms"], how="left")

    y = (df["label"] == "durable").astype(int).values
    year = pd.to_datetime(df["t_open_ms"], unit="ms").dt.year.values
    X = df[FEATURES].values.astype(float)
    tr, te = year <= 2025, year == 2026
    print(f"\ntrain {tr.sum()} (2024-25), exam {te.sum()} (2026)")

    mdl = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=200, l2_regularization=1.0,
        early_stopping=True, validation_fraction=0.15, random_state=7)
    mdl.fit(X[tr], y[tr])
    p_te = mdl.predict_proba(X[te])[:, 1]
    auc_learned = roc_auc_score(y[te], p_te)

    # Rulebook-style baseline: mean of the four anatomy z's (continuous)
    rb = np.nanmean(df[["z_clv", "z_wick", "z_body", "z_vol"]].values
                    * np.array([1, 1, -1, 1]), axis=1)
    ok = np.isfinite(rb) & te
    auc_rulebook = roc_auc_score(y[ok], rb[ok])
    print(f"2026 exam: Learned AUC = {auc_learned:.3f}   "
          f"Rulebook-score AUC = {auc_rulebook:.3f}")

    print("\n2026 calibration (predicted decile -> actual durable rate):")
    q = pd.qcut(p_te, 10, duplicates="drop")
    cal = pd.DataFrame({"pred": p_te, "y": y[te]}).groupby(q, observed=True)
    for interval, g in cal:
        print(f"  pred {g['pred'].mean():.0%}  actual {g['y'].mean():.0%}  "
              f"(n={len(g)})")

    from sklearn.inspection import permutation_importance
    sub = np.random.default_rng(7).choice(np.nonzero(te)[0], 4000,
                                          replace=False)
    imp = permutation_importance(mdl, X[sub], y[sub], n_repeats=3,
                                 random_state=7)
    order = np.argsort(-imp.importances_mean)
    print("\ntop feature importances (2026 exam):")
    for i in order[:8]:
        print(f"  {FEATURES[i]:16} {imp.importances_mean[i]:+.4f}")

    # refit on everything for live use
    mdl_full = HistGradientBoostingClassifier(
        max_iter=mdl.n_iter_, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=200, l2_regularization=1.0, random_state=7)
    mdl_full.fit(X, y)
    out = {"model": mdl_full, "features": FEATURES,
           "status": "PROVISIONAL — shadow/test use only",
           "trained_on": "flushes 2024-01..2026-06 (n=%d)" % len(df),
           "exam_2026_auc": float(auc_learned),
           "rulebook_2026_auc": float(auc_rulebook)}
    with open(os.path.join(RESULTS, "learned_model.pkl"), "wb") as f:
        pickle.dump(out, f)
    print("\nsaved results/learned_model.pkl (PROVISIONAL)")


if __name__ == "__main__":
    main()
