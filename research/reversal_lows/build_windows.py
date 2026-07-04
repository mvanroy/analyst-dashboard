"""Feature windows around candidate lows: offsets -32..+16, z vs -128..-33."""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "breakout_precursors"))
from config import KLINES_DIR              # noqa: E402
from features import compute_features     # noqa: E402

RESULTS = os.path.join(HERE, "results")
OFFSETS = list(range(-32, 17))
B0, B1 = -128, -33
EPS = 1e-12


def main():
    cands = json.load(open(os.path.join(RESULTS, "candidates.json")))
    cands = [c for c in cands if c["label"] in ("durable", "knife")]
    by_sym = {}
    for c in cands:
        by_sym.setdefault(c["symbol"], []).append(c)

    offsets = np.array(OFFSETS)
    base_off = np.arange(B0, B1 + 1)
    metas, mats = [], {}
    for sym, recs in sorted(by_sym.items()):
        df = pd.read_pickle(os.path.join(KLINES_DIR, f"{sym}_15m.pkl"))
        F = compute_features(df)
        idx_of = pd.Series(np.arange(len(df)), index=df["open_time"].values)
        rows, kept = [], []
        for k, r in enumerate(recs):
            i0 = idx_of.get(r["t_open_ms"])
            if i0 is None or i0 + B0 < 0 or i0 + OFFSETS[-1] >= len(df):
                continue
            rows.append(i0)
            kept.append(k)
        if not rows:
            continue
        rows = np.array(rows)
        ev_idx = rows[:, None] + offsets[None, :]
        b_idx = rows[:, None] + base_off[None, :]
        vals = F.values
        for j, name in enumerate(F.columns):
            col = vals[:, j]
            m = col[ev_idx]
            b = col[b_idx]
            med = np.nanmedian(b, axis=1, keepdims=True)
            mad = np.nanmedian(np.abs(b - med), axis=1, keepdims=True)
            scale = 1.4826 * mad
            std = np.nanstd(b, axis=1, keepdims=True)
            scale = np.where(scale < EPS, std, scale)
            z = np.clip((m - med) / np.where(scale < EPS, np.nan, scale),
                        -10, 10).astype(np.float32)
            mats.setdefault(name, []).append(z)
        metas += [recs[k] for k in kept]
        print(f"{sym}: {len(kept)}", flush=True)

    out = {"features": list(mats.keys()), "offsets": OFFSETS,
           "meta": pd.DataFrame(metas),
           "z": {k: np.vstack(v) for k, v in mats.items()}}
    with open(os.path.join(RESULTS, "windows.pkl"), "wb") as f:
        pickle.dump(out, f)
    print(f"\nDONE: {len(metas)} aligned "
          f"({(out['meta']['label'] == 'durable').mean():.1%} durable)")


if __name__ == "__main__":
    main()
