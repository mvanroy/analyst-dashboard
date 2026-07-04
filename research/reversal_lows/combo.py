"""Does flush-quality (at-the-low composite) stack with the reclaim trigger?

Out-of-fold composite probability per candidate (GroupKFold by symbol, offset-0
features), then T1/T3 trigger outcomes split by score tercile.
"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "breakout_precursors"))
from config import KLINES_DIR  # noqa: E402
from triggers import simulate  # noqa: E402

RESULTS = os.path.join(HERE, "results")


def main():
    with open(os.path.join(RESULTS, "windows.pkl"), "rb") as f:
        W = pickle.load(f)
    meta = W["meta"].reset_index(drop=True)
    oi = {o: i for i, o in enumerate(W["offsets"])}
    y = (meta["label"] == "durable").astype(int).values
    X = np.column_stack([W["z"][f][:, oi[0]] for f in W["features"]])
    ok = np.isfinite(X).all(axis=1)
    prob = np.full(len(meta), np.nan)
    Xo, yo, go = X[ok], y[ok], meta["symbol"].values[ok]
    oof = np.full(len(Xo), np.nan)
    for tr, te in GroupKFold(5).split(Xo, yo, go):
        m = LogisticRegression(max_iter=2000, C=0.5)
        m.fit(Xo[tr], yo[tr])
        oof[te] = m.predict_proba(Xo[te])[:, 1]
    prob[ok] = oof
    meta["score"] = prob

    # trigger simulation joined by (symbol, t_open_ms)
    cands = json.load(open(os.path.join(RESULTS, "candidates.json")))
    cands = [x for x in cands if x["label"] in ("durable", "knife")]
    by_sym = {}
    for x in cands:
        by_sym.setdefault(x["symbol"], []).append(x)
    sims = {}
    for sym, recs in sorted(by_sym.items()):
        df = pd.read_pickle(os.path.join(KLINES_DIR, f"{sym}_15m.pkl"))
        res = simulate(sym, recs, df)
        kept = [r for r in recs
                if r["t_open_ms"] is not None]
        # simulate() preserves order of recs it could align; rebuild keys
        k = 0
        idx_of = pd.Series(np.arange(len(df)), index=df["open_time"].values)
        for r in recs:
            t = idx_of.get(r["t_open_ms"])
            if t is None or t + 48 >= len(df):
                continue
            sims[(sym, r["t_open_ms"])] = res[k]
            k += 1

    meta["key"] = list(zip(meta["symbol"], meta["t_open_ms"]))
    q1, q2 = np.nanpercentile(meta["score"], [33.3, 66.7])
    print(f"score terciles: <{q1:.3f} / {q1:.3f}-{q2:.3f} / >{q2:.3f}")
    for rule in ["T1_reclaim_high", "T3_reclaim_vol"]:
        print(f"\n=== {rule} by flush-quality tercile ===")
        for name, lo, hi in [("low", -1, q1), ("mid", q1, q2),
                             ("high", q2, 2)]:
            sub = meta[(meta["score"] > lo) & (meta["score"] <= hi)]
            outs = []
            for key in sub["key"]:
                s = sims.get(key)
                if s and isinstance(s["rules"].get(rule), dict):
                    outs.append(s["rules"][rule])
            decided = [x for x in outs if x["win"] is not None]
            if not decided:
                continue
            wr = np.mean([x["win"] for x in decided])
            exp = np.mean([x["r"] for x in decided])
            mfe = np.median([x["mfe_r"] for x in outs])
            print(f"  {name:4} n={len(outs):5}  win={wr:.1%}  "
                  f"expectancy={exp:+.3f}R  medMFE={mfe:.2f}R")


if __name__ == "__main__":
    main()
