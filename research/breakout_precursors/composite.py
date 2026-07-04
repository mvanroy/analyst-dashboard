"""Composite early-detection model.

Two questions:
  1. Discrimination: with features summarised over a pre-breakout band, how
     well can successful breakouts be separated from compression controls?
     Logistic regression, GroupKFold(5) grouped by symbol (no symbol leaks
     between train and test). Run per band: late (-4..-1), early (-16..-9),
     very early (-32..-17) -> shows how much signal exists at each horizon.
  2. Sequential detection: a walk-forward composite score per 15m bar
     (mean signed z of the KEEP features), thresholded at 10% control FPR.
     Reports hit rate and the distribution of detection lead times vs the
     1H breakout close.
"""
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from config import RESULTS_DIR

BANDS = {"late_-4..-1": range(-4, 0), "early_-16..-9": range(-16, -8),
         "veryearly_-32..-17": range(-32, -16)}


def main():
    with open(os.path.join(RESULTS_DIR, "windows.pkl"), "rb") as f:
        W = pickle.load(f)
    offsets = list(W["offsets"])
    oi = {o: i for i, o in enumerate(offsets)}
    succ = W["ev_meta"]["success"].values.astype(bool)
    feats = W["features"]

    stats = pd.read_csv(os.path.join(RESULTS_DIR, "feature_stats.csv"))
    dirs = dict(zip(stats.feature, np.where(stats.direction == "+", 1, -1)))
    keep = [f for f in stats[stats.recommendation == "KEEP"].feature
            if f in feats]
    print(f"KEEP features: {keep}\n")

    # ---- 1) band-level discrimination, grouped CV --------------------------
    groups_e = W["ev_meta"].loc[succ, "symbol"].values
    groups_c = W["ct_meta"]["symbol"].values
    print("Composite logistic regression (successful events vs controls):")
    for band, rng in BANDS.items():
        cols = [oi[o] for o in rng]
        X_parts, names = [], []
        for f in feats:
            E = W["ev_z"][f][succ][:, cols]
            C = W["ct_z"][f][:, cols]
            X_parts.append((np.nanmean(E, axis=1), np.nanmean(C, axis=1)))
            names.append(f)
        Xe = np.column_stack([a for a, _ in X_parts])
        Xc = np.column_stack([b for _, b in X_parts])
        X = np.vstack([Xe, Xc])
        y = np.r_[np.ones(len(Xe)), np.zeros(len(Xc))]
        g = np.r_[groups_e, groups_c]
        ok = np.isfinite(X).all(axis=1)
        X, y, g = X[ok], y[ok], g[ok]
        aucs, coef_sum = [], np.zeros(X.shape[1])
        for tr, te in GroupKFold(n_splits=5).split(X, y, g):
            m = LogisticRegression(max_iter=2000, C=0.5)
            m.fit(X[tr], y[tr])
            aucs.append(roc_auc_score(y[te], m.predict_proba(X[te])[:, 1]))
            coef_sum += m.coef_[0]
        print(f"  {band:>22}: AUC = {np.mean(aucs):.3f} "
              f"+/- {np.std(aucs):.3f}  (n={len(X)})")
        top = np.argsort(-np.abs(coef_sum))[:8]
        print("     top weights:", ", ".join(
            f"{names[i]}({coef_sum[i] / 5:+.2f})" for i in top))

    # ---- 2) sequential composite detector ----------------------------------
    pre = [o for o in offsets if o <= -1]
    pre_idx = [oi[o] for o in pre]

    ev_meta_s = W["ev_meta"][succ].reset_index(drop=True)

    def score(zdict, mask=None):
        parts = []
        for f in keep:
            M = zdict[f] if mask is None else zdict[f][mask]
            parts.append(dirs[f] * M[:, pre_idx])
        return np.nanmean(parts, axis=0)          # (n, n_pre)

    S_e = score(W["ev_z"], succ)
    S_c = score(W["ct_z"])
    Sp_e = np.fmin(S_e, np.roll(S_e, 1, axis=1))
    Sp_e[:, 0] = np.nan
    Sp_c = np.fmin(S_c, np.roll(S_c, 1, axis=1))
    Sp_c[:, 0] = np.nan
    stat_c = np.nanmax(Sp_c, axis=1)
    for fpr_target in (0.05, 0.10, 0.20):
        thr = np.nanpercentile(stat_c[np.isfinite(stat_c)],
                               100 * (1 - fpr_target))
        cross = Sp_e >= thr
        hit = cross.any(axis=1)
        first = np.argmax(cross, axis=1)
        leads = np.array([45 - 15 * pre[i] for i in first[hit]])
        print(f"\nSequential detector @ {fpr_target:.0%} control FPR "
              f"(threshold {thr:.2f}):")
        print(f"  hit rate on successful breakouts: {hit.mean():.1%}")
        if hit.any():
            q = np.percentile(leads, [25, 50, 75])
            print(f"  detection lead vs 1H close: median {q[1]:.0f} min "
                  f"(IQR {q[0]:.0f}-{q[2]:.0f}), "
                  f">=2h early: {(leads >= 120).mean():.0%}, "
                  f">=4h early: {(leads >= 240).mean():.0%}")
        if abs(fpr_target - 0.10) < 1e-9 and hit.any():
            # price head start: close at detection bar vs 1H breakout close
            import pandas as _pd
            from config import KLINES_DIR as _K
            heads = []
            hits_meta = ev_meta_s[hit].copy()
            hits_meta["trig_off"] = [pre[i] for i in first[hit]]
            for sym, grp in hits_meta.groupby("symbol"):
                px = _pd.read_pickle(os.path.join(_K, f"{sym}_15m.pkl"))
                lookup = _pd.Series(px["close"].values,
                                    index=px["open_time"].values)
                for _, r in grp.iterrows():
                    t_trig = r["t_open_ms"] + int(r["trig_off"]) * 900000
                    c_trig = lookup.get(t_trig)
                    if c_trig is not None and np.isfinite(c_trig):
                        heads.append((r["close_at_break"] - c_trig)
                                     / r["atr_1h"])
            heads = np.array(heads)
            print(f"  price head start vs entering at 1H close: "
                  f"median {np.median(heads):+.2f} ATR "
                  f"(IQR {np.percentile(heads, 25):+.2f}"
                  f"..{np.percentile(heads, 75):+.2f}, n={len(heads)}); "
                  f"median 24h MFE from breakout level: "
                  f"{ev_meta_s['mfe_atr_24h'].median():.2f} ATR")


if __name__ == "__main__":
    main()
