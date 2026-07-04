"""Build event-aligned 15m feature windows for events and controls.

Output: results/windows.pkl with
  features   – ordered feature names
  offsets    – EVENT_OFFSETS
  ev_meta    – DataFrame (symbol, t_open_ms, success, mfe_atr_24h)
  ev_z/ev_raw    – dict feature -> (n_events, n_offsets)
  ct_meta, ct_z, ct_raw – same for controls
"""
import json
import os
import pickle

import numpy as np
import pandas as pd

from config import EVENT_OFFSETS, KLINES_DIR, RESULTS_DIR
from features import compute_features, extract_windows


def collect(records, kind):
    by_sym = {}
    for r in records:
        by_sym.setdefault(r["symbol"], []).append(r)

    metas, mats_z, mats_raw = [], {}, {}
    for sym, recs in sorted(by_sym.items()):
        path = os.path.join(KLINES_DIR, f"{sym}_15m.pkl")
        if not os.path.exists(path):
            continue
        df = pd.read_pickle(path)
        F = compute_features(df)
        opens = [r["t_open_ms"] for r in recs]
        raw, z, kept = extract_windows(F, df["open_time"].values, opens)
        if not kept:
            continue
        for k in kept:
            metas.append(recs[k])
        for name in z:
            mats_z.setdefault(name, []).append(z[name])
            mats_raw.setdefault(name, []).append(raw[name])
        print(f"{kind} {sym}: {len(kept)}/{len(recs)} aligned", flush=True)

    meta = pd.DataFrame(metas)
    z = {k: np.vstack(v) for k, v in mats_z.items()}
    raw = {k: np.vstack(v) for k, v in mats_raw.items()}
    return meta, z, raw


def main():
    events = json.load(open(os.path.join(RESULTS_DIR, "events.json")))
    controls = json.load(open(os.path.join(RESULTS_DIR, "controls.json")))
    ev_meta, ev_z, ev_raw = collect(events, "event")
    ct_meta, ct_z, ct_raw = collect(controls, "control")
    out = {
        "features": list(ev_z.keys()),
        "offsets": EVENT_OFFSETS,
        "ev_meta": ev_meta, "ev_z": ev_z, "ev_raw": ev_raw,
        "ct_meta": ct_meta, "ct_z": ct_z, "ct_raw": ct_raw,
    }
    with open(os.path.join(RESULTS_DIR, "windows.pkl"), "wb") as f:
        pickle.dump(out, f)
    print(f"\nDONE: {len(ev_meta)} events "
          f"({ev_meta['success'].mean():.0%} successful), "
          f"{len(ct_meta)} controls, {len(ev_z)} features")


if __name__ == "__main__":
    main()
