"""Derivatives features (open interest, long/short ratios, funding) for the
event/control windows.

Sources:
  * data.binance.vision daily *metrics* files (5-min granularity):
      sum_open_interest, sum_toptrader_long_short_ratio,
      count_long_short_ratio, sum_taker_long_short_vol_ratio
    Only the calendar days each event/control window spans are downloaded.
  * fapi /fapi/v1/fundingRate for full funding history per symbol.

Liquidation volume is NOT reproducible historically from public Binance data
(the forceOrders stream is real-time only and data.binance.vision has no
liquidation archive) — documented as unavailable in the report.

Output: results/deriv_windows.pkl with the same (meta rows, offsets) shape
as windows.pkl, z-scored per event against its own -128..-33 baseline.
"""
import io
import json
import os
import pickle
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests

from config import (BASELINE_OFFSETS, EVENT_OFFSETS, FUNDING_DIR, METRICS_DIR,
                    RESULTS_DIR)

EPS = 1e-12
MET_BASE = "https://data.binance.vision/data/futures/um/daily/metrics"
DERIV_FEATURES = ["oi_change_1h", "oi_change_4h", "toptrader_ls_change_4h",
                  "global_ls_change_4h", "taker_ls_vol_ratio",
                  "funding_rate", "funding_change_24h"]


def fetch_metrics_day(symbol, day):
    path = os.path.join(METRICS_DIR, f"{symbol}_{day}.pkl")
    if os.path.exists(path):
        return path
    url = f"{MET_BASE}/{symbol}/{symbol}-metrics-{day}.zip"
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 404:
            pd.DataFrame().to_pickle(path)
            return path
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            df = pd.read_csv(io.BytesIO(zf.read(zf.namelist()[0])))
        df.to_pickle(path)
    except Exception:
        return None
    return path


def fetch_funding(symbol):
    path = os.path.join(FUNDING_DIR, f"{symbol}.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    out, start = [], 1
    t = 1700000000000  # late 2023, before study window
    while True:
        r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate",
                         params={"symbol": symbol, "startTime": t,
                                 "limit": 1000}, timeout=30)
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            break
        out += rows
        if len(rows) < 1000:
            break
        t = rows[-1]["fundingTime"] + 1
    df = pd.DataFrame(out)
    if len(df):
        df["fundingTime"] = df["fundingTime"].astype("int64")
        df["fundingRate"] = df["fundingRate"].astype(float)
        df = df.sort_values("fundingTime").reset_index(drop=True)
    df.to_pickle(path)
    return df


def days_for(t_open_ms):
    """Calendar days spanned by [t_open - 32h, t_open + 1h]."""
    t0 = pd.Timestamp(t_open_ms, unit="ms", tz="UTC") - pd.Timedelta(hours=33)
    t1 = pd.Timestamp(t_open_ms, unit="ms", tz="UTC") + pd.Timedelta(hours=1)
    return [d.strftime("%Y-%m-%d") for d in
            pd.date_range(t0.floor("D"), t1.floor("D"), freq="D")]


def build_metric_series(symbol, days):
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
    df = df.drop_duplicates("ts").set_index("ts").sort_index()
    m = df.resample("15min").last()
    oi = m["sum_open_interest"].astype(float)
    out = pd.DataFrame(index=m.index)
    out["oi_change_1h"] = oi.pct_change(4)
    out["oi_change_4h"] = oi.pct_change(16)
    out["toptrader_ls_change_4h"] = (
        m["sum_toptrader_long_short_ratio"].astype(float).pct_change(16))
    out["global_ls_change_4h"] = (
        m["count_long_short_ratio"].astype(float).pct_change(16))
    out["taker_ls_vol_ratio"] = m["sum_taker_long_short_vol_ratio"] \
        .astype(float)
    return out


def robust_z(mat_ev, mat_base):
    med = np.nanmedian(mat_base, axis=1, keepdims=True)
    mad = np.nanmedian(np.abs(mat_base - med), axis=1, keepdims=True)
    scale = 1.4826 * mad
    std = np.nanstd(mat_base, axis=1, keepdims=True)
    scale = np.where(scale < EPS, std, scale)
    return np.clip((mat_ev - med) / np.where(scale < EPS, np.nan, scale),
                   -10, 10)


def collect(records, funding_cache):
    offsets = np.array(EVENT_OFFSETS)
    b0, b1 = BASELINE_OFFSETS
    base_off = np.arange(b0, b1 + 1)
    n = len(records)
    mats = {f: np.full((n, len(offsets)), np.nan) for f in DERIV_FEATURES}
    bases = {f: np.full((n, len(base_off)), np.nan) for f in DERIV_FEATURES}

    by_sym = {}
    for i, r in enumerate(records):
        by_sym.setdefault(r["symbol"], []).append(i)

    for sym, idxs in sorted(by_sym.items()):
        fund = funding_cache.get(sym)
        for i in idxs:
            t = records[i]["t_open_ms"]
            days = days_for(t)
            ms = build_metric_series(sym, days)
            t0 = pd.Timestamp(t, unit="ms", tz="UTC")
            ev_times = t0 + pd.to_timedelta(offsets * 15, unit="m")
            base_times = t0 + pd.to_timedelta(base_off * 15, unit="m")
            if ms is not None:
                for f in ["oi_change_1h", "oi_change_4h",
                          "toptrader_ls_change_4h", "global_ls_change_4h",
                          "taker_ls_vol_ratio"]:
                    s = ms[f]
                    mats[f][i] = s.reindex(ev_times).values
                    bases[f][i] = s.reindex(base_times).values
            if fund is not None and len(fund):
                ft = fund["fundingTime"].values
                fr = fund["fundingRate"].values

                def rate_at(ts_arr):
                    pos = np.searchsorted(ft, ts_arr.asi8 // 10**6,
                                          side="right") - 1
                    ok = pos >= 0
                    out = np.full(len(ts_arr), np.nan)
                    out[ok] = fr[pos[ok]]
                    return out

                r_ev = rate_at(ev_times)
                r_base = rate_at(base_times)
                mats["funding_rate"][i] = r_ev
                bases["funding_rate"][i] = r_base
                r_ev24 = rate_at(ev_times - pd.Timedelta(hours=24))
                r_b24 = rate_at(base_times - pd.Timedelta(hours=24))
                mats["funding_change_24h"][i] = r_ev - r_ev24
                bases["funding_change_24h"][i] = r_base - r_b24
        print(f"deriv {sym}: {len(idxs)} windows", flush=True)

    z = {f: robust_z(mats[f], bases[f]) for f in DERIV_FEATURES}
    return mats, z


def main():
    os.makedirs(METRICS_DIR, exist_ok=True)
    os.makedirs(FUNDING_DIR, exist_ok=True)
    events = json.load(open(os.path.join(RESULTS_DIR, "events.json")))
    controls = json.load(open(os.path.join(RESULTS_DIR, "controls.json")))

    # 1) download all needed daily metrics files + funding histories
    need = set()
    for r in events + controls:
        for d in days_for(r["t_open_ms"]):
            need.add((r["symbol"], d))
    symbols = sorted({r["symbol"] for r in events})
    print(f"{len(need)} symbol-days of metrics, {len(symbols)} funding "
          f"histories", flush=True)
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(fetch_metrics_day, s, d) for s, d in sorted(need)]
        done = 0
        for _ in as_completed(futs):
            done += 1
            if done % 500 == 0:
                print(f"metrics {done}/{len(need)}", flush=True)
    funding_cache = {}
    for s in symbols:
        funding_cache[s] = fetch_funding(s)
    print("downloads complete", flush=True)

    # 2) build windows
    ev_raw, ev_z = collect(events, funding_cache)
    ct_raw, ct_z = collect(controls, funding_cache)
    out = {"features": DERIV_FEATURES, "offsets": EVENT_OFFSETS,
           "ev_meta": pd.DataFrame(events), "ev_z": ev_z, "ev_raw": ev_raw,
           "ct_meta": pd.DataFrame(controls), "ct_z": ct_z, "ct_raw": ct_raw}
    with open(os.path.join(RESULTS_DIR, "deriv_windows.pkl"), "wb") as f:
        pickle.dump(out, f)
    print("DERIVATIVES DONE")


if __name__ == "__main__":
    main()
