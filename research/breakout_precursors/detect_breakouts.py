"""Detect 1H long breakout events and matched non-breakout control windows.

Event definition (all on completed 1H bars, per symbol):
  * breakout bar t: close[t] > max(high[t-48 .. t-1])   (Donchian 48 break)
  * compression:    high/low range of bars [t-24 .. t-1] <= 4 * ATR14[t-1]
  * warm-up:        at least 176 prior 1H bars (feature baseline coverage)
  * dedup:          skip events within 48 bars of the previous event

Timestamps recorded:
  * t_open  – open time of the breakout 1H bar
  * t_close – close of that bar = the moment the breakout is confirmed/visible
              on the 1H chart
  * t_touch – open time of the first 15m-aligned hour segment isn't needed;
              intrabar touch is derived later from 15m data if wanted

Success label: from breakout level B = prior 48-bar high, within the next
24 1H bars the high reaches B + 2*ATR14[t] BEFORE the low reaches
B - 1*ATR14[t].  Ambiguous bars (both hit in the same bar) count as failure
(conservative).

Controls: bars where the same compression filter passes, no Donchian-48 break
occurs at that bar or in the following 24 bars, sampled per symbol at
CONTROLS_PER_EVENT x the symbol's event count, with the same dedup spacing.
"""
import json
import os

import numpy as np
import pandas as pd

from config import (ATR_LEN_1H, COMPRESSION_LOOKBACK_1H,
                    COMPRESSION_MAX_RANGE_ATR, CONTROLS_PER_EVENT,
                    DEDUP_BARS_1H, DONCHIAN_LOOKBACK_1H, KLINES_DIR,
                    RESULTS_DIR, RANDOM_SEED, SUCCESS_HORIZON_1H,
                    SUCCESS_STOP_ATR, SUCCESS_TARGET_ATR)

WARMUP_1H = 176  # 128 x 15m baseline (32h) + Donchian lookback headroom


def atr(df, n):
    prev_close = df["close"].shift(1)
    tr = np.maximum(df["high"] - df["low"],
                    np.maximum((df["high"] - prev_close).abs(),
                               (df["low"] - prev_close).abs()))
    return tr.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()


def detect_symbol(sym, df):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    a = atr(df, ATR_LEN_1H).values

    prior_high = (pd.Series(h).shift(1)
                  .rolling(DONCHIAN_LOOKBACK_1H).max().values)
    rng_hi = (pd.Series(h).shift(1)
              .rolling(COMPRESSION_LOOKBACK_1H).max().values)
    rng_lo = (pd.Series(l).shift(1)
              .rolling(COMPRESSION_LOOKBACK_1H).min().values)
    atr_prev = np.roll(a, 1)
    atr_prev[0] = np.nan

    compressed = (rng_hi - rng_lo) <= COMPRESSION_MAX_RANGE_ATR * atr_prev
    breakout = c > prior_high
    valid = ~np.isnan(prior_high) & ~np.isnan(atr_prev) & (atr_prev > 0)
    valid[:WARMUP_1H] = False

    events, controls = [], []
    last_event = -10**9
    for t in np.nonzero(breakout & compressed & valid)[0]:
        if t - last_event < DEDUP_BARS_1H:
            continue
        last_event = t
        B, A = prior_high[t], a[t]
        if not np.isfinite(A) or A <= 0:
            continue
        target, stop = B + SUCCESS_TARGET_ATR * A, B - SUCCESS_STOP_ATR * A
        success, resolved = False, False
        end = min(n, t + 1 + SUCCESS_HORIZON_1H)
        for j in range(t + 1, end):
            hit_t, hit_s = h[j] >= target, l[j] <= stop
            if hit_t and not hit_s:
                success, resolved = True, True
                break
            if hit_s:
                resolved = True
                break
        if end < t + 1 + SUCCESS_HORIZON_1H and not resolved:
            continue  # truncated by end of data and unresolved -> drop
        mfe = (np.max(h[t + 1:end]) - B) / A if end > t + 1 else 0.0
        events.append({
            "symbol": sym,
            "t_open_ms": int(df["open_time"].iloc[t]),
            "breakout_level": float(B),
            "atr_1h": float(A),
            "close_at_break": float(c[t]),
            "success": bool(success),
            "mfe_atr_24h": float(mfe),
        })

    # control candidates: compressed, valid, no breakout now or in next 24 bars
    fwd_break = np.zeros(n, dtype=bool)
    bk = breakout.astype(bool)
    for k in range(0, SUCCESS_HORIZON_1H + 1):
        shifted = np.roll(bk, -k)
        shifted[n - k:] = False
        fwd_break |= shifted
    cand = np.nonzero(compressed & valid & ~fwd_break)[0]
    rng = np.random.default_rng(RANDOM_SEED + hash(sym) % 1000)
    rng.shuffle(cand)
    want = CONTROLS_PER_EVENT * len(events)
    chosen = []
    for t in cand:
        if len(chosen) >= want:
            break
        if all(abs(t - u) >= DEDUP_BARS_1H for u in chosen):
            chosen.append(t)
    for t in chosen:
        controls.append({
            "symbol": sym,
            "t_open_ms": int(df["open_time"].iloc[t]),
            "breakout_level": float(prior_high[t]),
            "atr_1h": float(a[t]),
        })
    return events, controls


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    all_events, all_controls = [], []
    files = sorted(f for f in os.listdir(KLINES_DIR) if f.endswith("_1h.pkl"))
    for f in files:
        sym = f.replace("_1h.pkl", "")
        df = pd.read_pickle(os.path.join(KLINES_DIR, f))
        ev, ct = detect_symbol(sym, df)
        all_events += ev
        all_controls += ct
        print(f"{sym}: {len(ev)} events ({sum(e['success'] for e in ev)} "
              f"successful), {len(ct)} controls", flush=True)
    json.dump(all_events, open(os.path.join(RESULTS_DIR, "events.json"), "w"))
    json.dump(all_controls,
              open(os.path.join(RESULTS_DIR, "controls.json"), "w"))
    ns = sum(e["success"] for e in all_events)
    print(f"\nTOTAL: {len(all_events)} events ({ns} successful, "
          f"{ns / max(1, len(all_events)):.0%}), {len(all_controls)} controls")


if __name__ == "__main__":
    main()
