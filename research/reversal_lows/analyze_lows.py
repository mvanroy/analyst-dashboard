"""Which features, knowable AT the candidate low, separate durable lows from
knives? (Post-low offsets are confirmation, not prediction — the trigger
backtest covers those; here we focus on offsets -8..0 plus event-level extras.)
"""
import os
import pickle

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
PRE_OFFSETS = list(range(-8, 1))


def bh_fdr(p):
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    q = np.full_like(p, np.nan)
    ps = p[ok]
    n = len(ps)
    order = np.argsort(ps)
    r = ps[order] * n / (np.arange(n) + 1)
    r = np.minimum.accumulate(r[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(r, 0, 1)
    q[ok] = out
    return q


def auc(a, b):
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 10 or len(b) < 10:
        return np.nan, np.nan
    u, p = mannwhitneyu(a, b, alternative="two-sided")
    return u / (len(a) * len(b)), p


def main():
    with open(os.path.join(RESULTS, "windows.pkl"), "rb") as f:
        W = pickle.load(f)
    meta = W["meta"]
    oi = {o: i for i, o in enumerate(W["offsets"])}
    dur = (meta["label"] == "durable").values
    print(f"{len(meta)} candidates, {dur.mean():.1%} durable\n")

    rows, ps = [], []
    for feat in W["features"]:
        Z = W["z"][feat]
        for o in PRE_OFFSETS:
            a, p = auc(Z[dur, oi[o]], Z[~dur, oi[o]])
            rows.append({"feature": feat, "offset": o, "auc": a, "p": p})
            ps.append(p)
    odf = pd.DataFrame(rows)
    odf["q"] = bh_fdr(ps)
    odf.to_csv(os.path.join(RESULTS, "offset_stats.csv"), index=False)

    at_low = odf[odf.offset == 0].copy()
    at_low["signed_auc"] = np.abs(at_low["auc"] - 0.5) + 0.5

    # symbol consistency at offset 0 for each feature
    sym = meta["symbol"].values
    cons = {}
    for feat in W["features"]:
        Z = W["z"][feat][:, oi[0]]
        gl, _ = auc(Z[dur], Z[~dur])
        agree = total = 0
        for s in np.unique(sym):
            m = sym == s
            if (m & dur).sum() < 30 or (m & ~dur).sum() < 30:
                continue
            a_s, _ = auc(Z[m & dur], Z[m & ~dur])
            if np.isnan(a_s):
                continue
            total += 1
            agree += (a_s - 0.5) * (gl - 0.5) > 0
        cons[feat] = agree / total if total else np.nan
    at_low["consistency"] = at_low["feature"].map(cons)
    at_low = at_low.sort_values("signed_auc", ascending=False)
    print("=== At the low bar (offset 0), durable vs knife ===")
    print(at_low[["feature", "auc", "q", "consistency"]]
          .to_string(index=False))

    # event-level extras
    print("\n=== Event-level extras ===")
    for col in ["rsi", "rsi_div", "decline_96_atr"]:
        x = meta[col].astype(float).values
        a, p = auc(x[dur], x[~dur])
        print(f"{col:16} AUC={a:.3f}  p={p:.2e}  n={np.isfinite(x).sum()}")

    # composite at offset 0, grouped CV by symbol
    X = np.column_stack([W["z"][f][:, oi[0]] for f in W["features"]])
    ok = np.isfinite(X).all(axis=1)
    Xo, yo, go = X[ok], dur[ok].astype(int), sym[ok]
    aucs = []
    coef = np.zeros(Xo.shape[1])
    for tr, te in GroupKFold(5).split(Xo, yo, go):
        m = LogisticRegression(max_iter=2000, C=0.5)
        m.fit(Xo[tr], yo[tr])
        aucs.append(roc_auc_score(yo[te], m.predict_proba(Xo[te])[:, 1]))
        coef += m.coef_[0]
    print(f"\nComposite AUC at the low (grouped 5-fold): "
          f"{np.mean(aucs):.3f} +/- {np.std(aucs):.3f} (n={ok.sum()})")
    top = np.argsort(-np.abs(coef))[:10]
    feats = W["features"]
    print("top weights:", ", ".join(f"{feats[i]}({coef[i] / 5:+.2f})"
                                    for i in top))


if __name__ == "__main__":
    main()
