"""Reversal-Low watchlist engine — backend for pages/2_Reversal_Watch_List.py.

Scans all Bybit USDT perps for capitulation flushes (framework/
reversal_low_scanner.md), grades each with the Rulebook (anatomy-gated tiers)
and, when available, the PROVISIONAL Learned Model
(research/reversal_lows/results/learned_model.pkl). Returns rows in the same
schema the Watch List front end consumes.

Standalone module on purpose: no imports from watchlist_engine/ (Codex's
territory) or pages/. Public entry point: run_scan().
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

BASE = "https://api.bybit.com"
STABLES = {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "DAIUSDT", "USDEUSDT",
           "BUSDUSDT", "USTCUSDT", "EURUSDT", "USD1USDT"}
EPS = 1e-12
SCAN_BARS = 24
DECLINE_96, DECLINE_32 = 8.0, 4.0
STOP_ATR = 0.75
STALE_BARS = 12
MICROCAP_USD = 3_000_000
MIN_TAIL_ATR = 1.0      # board admission: the wick must be the story (55%+ class)
THRILLING_TAIL_ATR = 2.0  # 88%-class wicks get top billing

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(ROOT, "research", "reversal_lows", "results",
                          "learned_model.pkl")

# in-study durable rates by tail bucket — Learned-Model fallback + evidence
TAIL_CLASS = [(2.0, 88), (1.0, 55), (0.5, 38), (0.25, 29), (0.0, 24)]


def _get(path, **params):
    for a in range(3):
        try:
            j = requests.get(BASE + path, params=params, timeout=20).json()
            if j.get("retCode") == 0:
                return j["result"]
        except Exception:
            pass
        time.sleep(1 + a)
    return None


def _klines(symbol, interval="15", limit=1000):
    res = _get("/v5/market/kline", category="linear", symbol=symbol,
               interval=interval, limit=limit)
    if not res or not res.get("list"):
        return None
    rows = list(reversed(res["list"]))[:-1]
    return pd.DataFrame(rows, columns=["start", "open", "high", "low",
                                       "close", "volume", "turnover"]) \
        .astype(float)


def _atr14(df):
    pc = df["close"].shift(1)
    tr = np.maximum(df["high"] - df["low"],
                    np.maximum((df["high"] - pc).abs(),
                               (df["low"] - pc).abs()))
    return tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()


def _robust_z_at(series, i):
    base = series.iloc[i - 128:i - 32].values
    base = base[np.isfinite(base)]
    x = series.iloc[i]
    if len(base) < 48 or not np.isfinite(x):
        return np.nan
    med = np.median(base)
    mad = np.median(np.abs(base - med))
    scale = 1.4826 * mad if mad > EPS else np.std(base)
    return float(np.clip((x - med) / scale, -10, 10)) if scale > EPS \
        else np.nan


def _load_model():
    try:
        import pickle
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _tail_class(tail_atr):
    for cut, rate in TAIL_CLASS:
        if tail_atr >= cut:
            return rate
    return 24


def _daily_context(sym, t_open_ms, low):
    res = _get("/v5/market/kline", category="linear", symbol=sym,
               interval="D", limit=200)
    if not res or not res.get("list"):
        return {}
    rows = list(reversed(res["list"]))
    d = pd.DataFrame(rows, columns=["start", "open", "high", "low", "close",
                                    "volume", "turnover"]).astype(float)
    prior = d[d["start"] < (t_open_ms // 86400000) * 86400000]
    if len(prior) < 30:
        return {}
    w = prior.tail(90)
    lo, hi = w["low"].values, w["high"].values
    out = {"pos_90d": (low - lo.min()) / max(hi.max() - lo.min(), EPS),
           "time_at_price": float(np.mean((lo <= low) & (low <= hi))),
           "is_90d_low": float(low < lo.min())}
    pc = prior["close"].shift(1)
    tr = np.maximum(prior["high"] - prior["low"],
                    np.maximum((prior["high"] - pc).abs(),
                               (prior["low"] - pc).abs()))
    atr_d = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean().iloc[-1]
    ema50 = prior["close"].ewm(span=50, min_periods=30,
                               adjust=False).mean().iloc[-1]
    if np.isfinite(atr_d) and atr_d > 0 and np.isfinite(ema50):
        out["daily_trend"] = float((prior["close"].iloc[-1] - ema50) / atr_d)
    return out


def _oi_changes(sym, t_open_ms):
    res = _get("/v5/market/open-interest", category="linear", symbol=sym,
               intervalTime="15min", limit=200)
    if not res or not res.get("list"):
        return {}
    s = pd.Series({int(r["timestamp"]): float(r["openInterest"])
                   for r in res["list"]}).sort_index()

    def asof(ms):
        i = s.index.searchsorted(ms, side="right") - 1
        return s.iloc[i] if i >= 0 else np.nan

    o0 = asof(t_open_ms + 900000)
    out = {}
    if np.isfinite(o0) and o0 > 0:
        for name, k in [("oi_chg_1h", 4), ("oi_chg_4h", 16),
                        ("oi_chg_8h", 32)]:
            p = asof(t_open_ms + 900000 - k * 900000)
            out[name] = o0 / p - 1 if np.isfinite(p) and p > 0 else np.nan
    return out


def _btc_context():
    b15 = _klines("BTCUSDT")
    closes = (pd.Series(b15["close"].values,
                        index=b15["start"].astype("int64"))
              if b15 is not None else None)
    res = _get("/v5/market/kline", category="linear", symbol="BTCUSDT",
               interval="240", limit=200)
    b4 = ema = None
    if res and res.get("list"):
        rows = list(reversed(res["list"]))[:-1]
        b4 = pd.DataFrame(rows, columns=["start", "o", "h", "l", "c", "v",
                                         "to"]).astype(float)
        ema = b4["c"].ewm(span=50, min_periods=30, adjust=False).mean()

    def feats(t_open_ms):
        out = {}
        if closes is not None:
            i = closes.index.searchsorted(t_open_ms, side="right") - 1
            if i >= 96:
                c0 = closes.iloc[i]
                out["btc_ret_4h"] = float(c0 / closes.iloc[i - 16] - 1)
                out["btc_ret_24h"] = float(c0 / closes.iloc[i - 96] - 1)
        if b4 is not None:
            k = b4["start"].searchsorted(t_open_ms, side="right") - 1
            if k >= 0 and np.isfinite(ema.iloc[k]):
                out["btc_above_ema"] = float(b4["c"].iloc[k] > ema.iloc[k])
        return out

    return feats


def _scan_symbol(sym):
    """Detect flush candidates and grade with the Rulebook. Returns list of
    internal candidate dicts (may be empty)."""
    df = _klines(sym)
    if df is None or len(df) < 240:
        return []
    o, h, l, c, v = (df[k] for k in ("open", "high", "low", "close",
                                     "volume"))
    n = len(df)
    a = _atr14(df)
    rng = (h - l)
    clv = ((c - l) - (h - c)) / (rng + EPS)
    lwick = (np.minimum(o, c) - l) / (rng + EPS)
    bodyf = (c - o).abs() / (rng + EPS)
    vz = (v - v.rolling(96, min_periods=48).mean()) / \
         (v.rolling(96, min_periods=48).std() + EPS)
    roc8 = (c - c.shift(8)) / (a + EPS)
    low96 = l.rolling(96).min()
    hi96 = h.rolling(96).max()
    hi32 = h.rolling(32).max()

    cands = []
    for t in range(max(128, n - SCAN_BARS), n):
        A = a.iloc[t]
        if not np.isfinite(A) or A <= 0:
            continue
        if l.iloc[t] > low96.iloc[t] + 1e-15:
            continue
        if (hi96.iloc[t] - l.iloc[t]) < DECLINE_96 * A:
            continue
        if (hi32.iloc[t] - l.iloc[t]) < DECLINE_32 * A:
            continue
        if cands and t - cands[-1] < 16:
            continue
        cands.append(t)

    out = []
    for t in cands:
        L, A = float(l.iloc[t]), float(a.iloc[t])
        stop = L - STOP_ATR * A
        reclaim = max(float(h.iloc[t]), L + 1.0 * A)
        z_clv, z_wick = _robust_z_at(clv, t), _robust_z_at(lwick, t)
        z_body, z_vol = _robust_z_at(bodyf, t), _robust_z_at(vz, t)
        parts = [z_clv, z_wick, -z_body if np.isfinite(z_body) else np.nan,
                 z_vol]
        quality = float(np.nanmean(parts))
        if not np.isfinite(z_clv) or z_clv < 0:
            tier = "C*"
        elif quality >= 1.0 and z_clv >= 0.5 and np.isfinite(z_wick) \
                and z_wick >= 0:
            tier = "A"
        elif quality >= 0.3:
            tier = "B"
        else:
            tier = "C"

        state, grade, health = "AWAITING", "", ""
        rec_j = None
        for j in range(t + 1, n):
            if l.iloc[j] <= stop:
                state = "INVALIDATED"
                break
            if rec_j is None and c.iloc[j] > reclaim:
                rec_j = j
        if state != "INVALIDATED":
            if rec_j is not None:
                state = "CONFIRMED"
                lat = rec_j - t
                grade = ("volume" if vz.iloc[rec_j] >= 1 else
                         ("base" if lat >= 2 else "instant-V"))
                post = list(range(rec_j + 1, n))
                if len(post) >= 2:
                    checks = int(np.nanmean(clv.iloc[post]) > 0) \
                        + int(vz.iloc[n - 1] < vz.iloc[rec_j]) \
                        + int(roc8.iloc[n - 1] > roc8.iloc[rec_j])
                    health = "healthy" if checks >= 2 else "suspect"
                else:
                    health = "fresh"
            elif n - 1 - t > STALE_BARS:
                state = "STALE"
        if state == "INVALIDATED":
            continue
        tail = float(min(o.iloc[t], c.iloc[t]) - l.iloc[t])
        if tail / A < MIN_TAIL_ATR:
            continue          # only wicks worth watching make the board
        out.append({
            "sym": sym, "t_open_ms": int(df["start"].iloc[t]),
            "low": L, "atr": A, "stop": stop, "reclaim": reclaim,
            "state": state, "grade": grade, "health": health, "tier": tier,
            "quality": quality, "tail_atr": tail / A,
            "tail_frac": tail / max(float(rng.iloc[t]), EPS),
            "z_clv": z_clv, "z_wick": z_wick, "z_body": z_body,
            "z_vol": z_vol, "bars_since_low": n - 1 - t,
            "price": float(c.iloc[n - 1]),
        })
    return out


def _zn(x, d=2):
    return round(x, d) if x is not None and np.isfinite(x) else None


def _build_row(cand, ticker, learned):
    L, A = cand["low"], cand["atr"]
    entry_lo, entry_hi = cand["reclaim"], cand["reclaim"] + 0.25 * A
    entry_mid = (entry_lo + entry_hi) / 2
    stop = cand["stop"]
    t1, t2 = L + 3.0 * A, L + 6.75 * A
    risk = max(entry_mid - stop, EPS)
    tail_rate = _tail_class(cand["tail_atr"])
    score = int(round(learned * 100)) if learned is not None else tail_rate

    state = cand["state"].capitalize()          # Confirmed / Awaiting / Stale
    turnover = float(ticker.get("turnover24h") or 0)
    base = cand["sym"].replace("USDT", "")
    conf_bits = []
    if cand["state"] == "CONFIRMED":
        conf_bits.append(f"reclaim ({cand['grade']}, {cand['health']})")
    elif cand["state"] == "AWAITING":
        conf_bits.append(f"awaiting reclaim @ {cand['reclaim']:.6g}")
    else:
        conf_bits.append("no reclaim in 12 bars")
    wick_word = ("THRILLING wick" if cand["tail_atr"] >= THRILLING_TAIL_ATR
                 else "Long wick")
    pattern = (f"{wick_word} {cand['tail_atr']:.1f} ATR · "
               + conf_bits[0])

    evidence, missing, warnings = [], [], []
    evidence.append(f"Tail {cand['tail_atr']:.2f} ATR — "
                    f"{tail_rate}% class in study")
    if np.isfinite(cand["z_clv"]) and cand["z_clv"] >= 0.5:
        evidence.append(f"Strong close location (z {cand['z_clv']:.1f})")
    if np.isfinite(cand["z_vol"]) and cand["z_vol"] >= 1:
        evidence.append(f"Capitulation volume (z {cand['z_vol']:.1f})")
    if cand["state"] == "CONFIRMED":
        evidence.append(f"Reclaim confirmed — {cand['grade']} variant, "
                        f"{cand['health']}")
    else:
        missing.append(f"Reclaim close above {cand['reclaim']:.6g} "
                       f"({12 - cand['bars_since_low']} bars before stale)")
    if cand["tier"] == "C*":
        warnings.append("Weak anatomy — volume-driven score (Rulebook gate)")
    if turnover and turnover < MICROCAP_USD:
        warnings.append(f"Micro-cap: ${turnover / 1e6:.1f}M 24h turnover — "
                        "outside study calibration")
    gb = (cand["price"] - L) / A
    if gb > 2.5:
        warnings.append(f"Price already {gb:.1f} ATR off the low — "
                        "entry economics degraded")
    if learned is not None:
        warnings.append("Learned Model score is PROVISIONAL (trial period; "
                        "Rulebook remains the official grade)")
    else:
        warnings.append("Learned Model unavailable — score falls back to "
                        "tail-bucket class rate")

    def chk(text, ok):
        return {"text": text, "pass": bool(ok)}

    breakdown = [
        {"label": "Flush Anatomy (Rulebook)", "pass": cand["tier"] in
         ("A", "B"), "score": {"A": 2, "B": 1}.get(cand["tier"], 0),
         "max": 2, "text": f"Tier {cand['tier']} (quality z "
         f"{cand['quality']:.2f})",
         "checks": [
             chk(f"Close-location z {_zn(cand['z_clv'])}",
                 np.isfinite(cand["z_clv"]) and cand["z_clv"] >= 0),
             chk(f"Lower-wick z {_zn(cand['z_wick'])}",
                 np.isfinite(cand["z_wick"]) and cand["z_wick"] >= 0),
             chk(f"Volume z {_zn(cand['z_vol'])}",
                 np.isfinite(cand["z_vol"]) and cand["z_vol"] >= 1),
         ]},
        {"label": "Tail Length", "pass": cand["tail_atr"] >= 1.0,
         "score": min(2, int(cand["tail_atr"])), "max": 2,
         "text": f"{cand['tail_atr']:.2f} ATR -> {tail_rate}% class"},
        {"label": "Confirmation", "pass": cand["state"] == "CONFIRMED",
         "score": 1 if cand["state"] == "CONFIRMED" else 0, "max": 1,
         "text": pattern.split("·")[-1].strip()},
    ]
    if learned is not None:
        breakdown.append({"label": "Learned Model (provisional)",
                          "pass": learned >= 0.5,
                          "score": int(round(learned * 100)), "max": 100,
                          "text": f"{learned:.0%} class — sorted 0.654 vs "
                          "Rulebook 0.627 on 2026 exam"})

    return {
        "symbol": f"{base}/USDT", "coin": base,
        "price": cand["price"], "pattern": pattern, "direction": "long",
        "maturity": state, "grade": cand["tier"],
        "score": score, "max_score": 100, "confidence": score,
        "rr": f"1:{(t1 - entry_mid) / risk:.1f}",
        "entry_low": entry_lo, "entry_high": entry_hi,
        "stop": stop, "t1": t1, "t2": t2,
        "t1_rr": f"({(t1 - entry_mid) / risk:.1f}R)",
        "t2_rr": f"({(t2 - entry_mid) / risk:.1f}R)",
        "risk": risk,
        "funding": (float(ticker["fundingRate"]) * 100
                    if ticker.get("fundingRate") else None),
        "oi": float(ticker.get("openInterestValue") or 0),
        "low24h": float(ticker.get("lowPrice24h") or 0),
        "high24h": float(ticker.get("highPrice24h") or 0),
        "cvd": None, "order_book": None,
        "score_breakdown": breakdown,
        "evidence": evidence, "missing": missing, "warnings": warnings,
        # stable identity + lifecycle info for the alert worker (page ignores)
        "meta": {"t_open_ms": cand["t_open_ms"],
                 "bars_since_low": cand["bars_since_low"],
                 "tail_atr": round(cand["tail_atr"], 2),
                 "state": cand["state"], "grade": cand["grade"],
                 "health": cand["health"], "low": cand["low"],
                 "atr": cand["atr"], "reclaim": cand["reclaim"],
                 "stop": cand["stop"], "turnover_usd": turnover},
        "_state_order": {"Confirmed": 0, "Awaiting": 1, "Stale": 2}[state],
        "_tail": cand["tail_atr"],
    }


def run_scan():
    """Entry point for the Reversal Watch List page."""
    tk = _get("/v5/market/tickers", category="linear")
    if not tk:
        return {"rows": [], "errors": [{"coin": "Bybit",
                                        "error": "ticker fetch failed"}],
                "generated_at": time.time()}
    tickers = {t["symbol"]: t for t in tk["list"]
               if t["symbol"].endswith("USDT")
               and t["symbol"] not in STABLES}

    cands, errors = [], []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for res in ex.map(_scan_symbol, list(tickers)):
            cands += res

    model = _load_model()
    btc = _btc_context() if model else None
    rows = []
    for cand in cands:
        learned = None
        if model is not None:
            feats = {"z_clv": cand["z_clv"], "z_wick": cand["z_wick"],
                     "z_body": cand["z_body"], "z_vol": cand["z_vol"],
                     "tail_atr": cand["tail_atr"],
                     "tail_frac": cand["tail_frac"]}
            feats.update(_daily_context(cand["sym"], cand["t_open_ms"],
                                        cand["low"]))
            feats.update(_oi_changes(cand["sym"], cand["t_open_ms"]))
            feats.update(btc(cand["t_open_ms"]))
            X = np.array([[feats.get(f, np.nan)
                           for f in model["features"]]])
            try:
                learned = float(model["model"].predict_proba(X)[0, 1])
            except Exception:
                learned = None
        rows.append(_build_row(cand, tickers.get(cand["sym"], {}), learned))

    # board order: biggest wick first, full stop (user preference)
    rows.sort(key=lambda r: (-(r.get("_tail") or 0), r["_state_order"],
                             -(r["score"] or 0)))
    for r in rows:
        r.pop("_state_order", None)
        r.pop("_tail", None)
    return {"rows": rows, "errors": errors, "generated_at": time.time(),
            "total_coins": len(tickers)}
