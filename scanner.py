"""Async scanner for Binance USDⓈ-M perpetual futures.

Pulls the full perpetual universe and, for each symbol, the metrics that mirror
Orion's screener columns:
    TRD 5M  -> numberOfTrades on the last closed 5m candle
    VOL 5M  -> quoteAssetVolume on the last closed 5m candle (USDT ~ $)
    CHG 5M  -> (close-open)/open on the last closed 5m candle
    CHG 1D  -> priceChangePercent from the 24h ticker
"""
from __future__ import annotations

import asyncio
import math

import httpx
import pandas as pd

BASE = "https://fapi.binance.com"
BYBIT_BASE = "https://api.bybit.com"


async def _get_json(client, url, params=None, retries=3):
    last_exc = None
    for attempt in range(retries):
        try:
            r = await client.get(url, params=params, timeout=15)
            if r.status_code in (429, 418):  # rate limited / banned -> back off
                await asyncio.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            last_exc = exc
            await asyncio.sleep(1 + attempt)
    if last_exc:
        raise last_exc
    return None


async def fetch_universe(client):
    data = await _get_json(client, BASE + "/fapi/v1/exchangeInfo")
    out = []
    for s in data.get("symbols", []):
        if s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING":
            out.append(s["symbol"])
    return out


async def fetch_24hr(client):
    data = await _get_json(client, BASE + "/fapi/v1/ticker/24hr")
    out = {}
    for d in data:
        try:
            out[d["symbol"]] = float(d["priceChangePercent"])
        except (KeyError, ValueError, TypeError):
            continue
    return out


# how many recent 5m candles to pull. 14 -> 13 closed + 1 forming, so the 13
# closed candles span 12 intervals = a clean 60 min (used for CHG 1H and the
# BTC-correlation window).
COR_LOOKBACK = 14


async def fetch_kline_5m(client, sem, symbol):
    async with sem:
        try:
            data = await _get_json(
                client,
                BASE + "/fapi/v1/klines",
                params={"symbol": symbol, "interval": "5m", "limit": COR_LOOKBACK},
            )
        except httpx.HTTPError:
            return None
    if not data or len(data) < 2:
        return None
    k = data[-2]  # last fully-closed candle
    try:
        o = float(k[1])
        c = float(k[4])
        qv = float(k[7])
        trades = int(k[8])
    except (ValueError, TypeError, IndexError):
        return None
    chg5m = (c - o) / o * 100 if o else 0.0
    closes = []
    for kk in data[:-1]:  # closed candles only (drop the still-forming last one)
        try:
            closes.append(float(kk[4]))
        except (ValueError, TypeError, IndexError):
            pass
    # CHG 1H: close of the most recent closed candle vs ~60 min earlier
    chg1h = (
        (closes[-1] - closes[0]) / closes[0] * 100
        if len(closes) >= 2 and closes[0]
        else float("nan")
    )
    return {
        "symbol": symbol,
        "trd5m": trades,
        "vol5m": qv,
        "chg5m": chg5m,
        "chg1h": chg1h,
        "closes": closes,
    }


def _returns(closes):
    out = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev:
            out.append((closes[i] - prev) / prev)
    return out


def _pearson(a, b):
    n = min(len(a), len(b))
    if n < 3:
        return float("nan")
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return float("nan")
    return cov / ((va * vb) ** 0.5)


async def _scan(concurrency=20):
    async with httpx.AsyncClient(headers={"User-Agent": "orion-lite/1.0"}) as client:
        universe, chg1d = await asyncio.gather(fetch_universe(client), fetch_24hr(client))
        sem = asyncio.Semaphore(concurrency)
        tasks = [fetch_kline_5m(client, sem, s) for s in universe]
        rows = await asyncio.gather(*tasks, return_exceptions=True)

    by_symbol = {r["symbol"]: r for r in rows if isinstance(r, dict)}
    btc = by_symbol.get("BTCUSDT")
    btc_ret = _returns(btc["closes"]) if btc and btc.get("closes") else []

    records = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ret = _returns(r.get("closes", []))
        cor = _pearson(ret, btc_ret) if btc_ret else float("nan")
        chg1h = r.get("chg1h", float("nan"))
        records.append(
            {
                "symbol": r["symbol"],
                "trd5m": r["trd5m"],
                "chg5m": round(r["chg5m"], 2),
                "chg1h": round(chg1h, 2) if chg1h == chg1h else float("nan"),
                "chg1d": round(chg1d.get(r["symbol"], float("nan")), 2),
                "vol5m": r["vol5m"],
                "cor5m": round(cor, 2) if cor == cor else float("nan"),
            }
        )
    return pd.DataFrame.from_records(
        records,
        columns=["symbol", "trd5m", "chg5m", "chg1h", "chg1d", "vol5m", "cor5m"],
    )


def scan():
    """Run one full scan synchronously. Returns a pandas DataFrame."""
    return asyncio.run(_scan())


# ---------------- Bybit watchlist universes ----------------
async def _fetch_bybit_tickers(client):
    data = await _get_json(
        client,
        BYBIT_BASE + "/v5/market/tickers",
        params={"category": "linear"},
    )
    if data.get("retCode") not in (0, "0"):
        return []
    return (data.get("result") or {}).get("list") or []


async def _fetch_bybit_instruments(client, symbol_type=None):
    cursor = None
    rows = []
    while True:
        params = {"category": "linear", "limit": "1000"}
        if symbol_type:
            params["symbolType"] = symbol_type
        if cursor:
            params["cursor"] = cursor
        data = await _get_json(client, BYBIT_BASE + "/v5/market/instruments-info", params=params)
        if data.get("retCode") not in (0, "0"):
            break
        result = data.get("result") or {}
        rows.extend(result.get("list") or [])
        cursor = result.get("nextPageCursor")
        if not cursor:
            break
    return rows


def _to_float(value, default=float("nan")):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bybit_watchlist_frame(tickers, instruments, mode):
    instrument_map = {item.get("symbol"): item for item in instruments if item.get("symbol")}
    records = []
    for ticker in tickers:
        symbol = ticker.get("symbol")
        instrument = instrument_map.get(symbol, {})
        if (
            not symbol
            or instrument.get("status") != "Trading"
            or instrument.get("contractType") != "LinearPerpetual"
        ):
            continue
        symbol_type = instrument.get("symbolType") or ""
        records.append(
            {
                "symbol": symbol,
                "symbol_type": symbol_type,
                "contract_type": instrument.get("contractType") or "",
                "last_price": _to_float(ticker.get("lastPrice")),
                "high24h": _to_float(ticker.get("highPrice24h")),
                "low24h": _to_float(ticker.get("lowPrice24h")),
                "turnover24h": _to_float(ticker.get("turnover24h")),
                "volume24h": _to_float(ticker.get("volume24h")),
                "price24h_pct": _to_float(ticker.get("price24hPcnt")) * 100,
                "launch_time": _to_float(instrument.get("launchTime"), 0),
            }
        )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(records)
    crypto = df[~df["symbol_type"].isin(["stock", "commodity"])].copy()
    stocks = df[df["symbol_type"].eq("stock")].copy()

    if mode == "tradfi_stocks":
        out = stocks.copy()
    elif mode == "new":
        out = crypto.copy()
    else:
        out = crypto.copy()

    return out


def _rank_watchlist_frame(df, mode):
    if df.empty:
        return df
    out = df.copy()
    out["volume_rank"] = out["turnover24h"].rank(pct=True)
    out["gain_rank"] = out["price24h_pct"].rank(pct=True)
    out["positive"] = out["price24h_pct"] > 0

    if mode == "tradfi_stocks":
        out["triage_score"] = out["volume_rank"] * 0.55 + out["gain_rank"] * 0.35 + out["positive"].astype(float) * 0.10
        return out.sort_values(["triage_score", "turnover24h"], ascending=[False, False])
    if mode == "new":
        out["new_rank"] = out["launch_time"].rank(pct=True)
        out["triage_score"] = out["new_rank"] * 0.55 + out["volume_rank"] * 0.25 + out["gain_rank"] * 0.20
        return out.sort_values(["triage_score", "launch_time"], ascending=[False, False])
    if mode == "gainers":
        floor = max(5_000_000, out["turnover24h"].quantile(0.35))
        pool = out[(out["price24h_pct"] > 0) & (out["turnover24h"] >= floor)].copy()
        pool["triage_score"] = pool["gain_rank"] * 0.65 + pool["volume_rank"] * 0.35
        return pool.sort_values(["triage_score", "price24h_pct"], ascending=[False, False])
    if mode == "change_24h":
        out["triage_score"] = out["gain_rank"] * 0.85 + out["volume_rank"] * 0.15
        return out.sort_values(["price24h_pct", "turnover24h"], ascending=[False, False])
    if mode == "low_cap_impulse":
        floor = max(50_000, out["turnover24h"].quantile(0.05))
        ceiling = out["turnover24h"].quantile(0.75)
        pool = out[
            (out["price24h_pct"] >= 3)
            & (out["turnover24h"] >= floor)
            & (out["turnover24h"] <= ceiling)
        ].copy()
        if pool.empty:
            pool = out[(out["price24h_pct"] > 0) & (out["turnover24h"] >= floor)].copy()
        pool["triage_score"] = (
            pool["price24h_pct"].rank(pct=True) * 0.55
            + (1 - pool["turnover24h"].rank(pct=True)) * 0.25
            + pool["turnover24h"].rank(pct=True) * 0.20
        )
        return pool.sort_values(["triage_score", "price24h_pct"], ascending=[False, False])

    out["triage_score"] = out["volume_rank"] * 0.70 + out["gain_rank"] * 0.30
    return out.sort_values(["turnover24h", "price24h_pct"], ascending=[False, False])


async def _bybit_watchlist_universe(mode, limit=30):
    async with httpx.AsyncClient(headers={"User-Agent": "orion-lite/1.0"}) as client:
        tickers, instruments = await asyncio.gather(
            _fetch_bybit_tickers(client),
            _fetch_bybit_instruments(client),
        )
    out = _rank_watchlist_frame(_bybit_watchlist_frame(tickers, instruments, mode), mode)

    return out["symbol"].head(limit).tolist()


def bybit_watchlist_universe(mode="top_volume", limit=30):
    """Symbols for the Entry Zone Watchlist category selector.

    The modes are intentionally scanner universes only; saved A/B analyses still
    decide whether a symbol has a valid waiting entry-zone setup.
    """
    return asyncio.run(_bybit_watchlist_universe(mode, limit))


async def _bybit_watchlist_triage(mode, limit=8):
    async with httpx.AsyncClient(headers={"User-Agent": "orion-lite/1.0"}) as client:
        tickers, instruments = await asyncio.gather(
            _fetch_bybit_tickers(client),
            _fetch_bybit_instruments(client),
        )
    frame = _bybit_watchlist_frame(tickers, instruments, mode)
    ranked = _rank_watchlist_frame(frame, mode)
    symbols = ranked["symbol"].head(limit).tolist() if not ranked.empty else []
    return {
        "symbols": symbols,
        "universe_count": int(len(frame)),
        "qualified_count": int(len(ranked)),
    }


def bybit_watchlist_triage(mode="top_volume", limit=8):
    """Cheap first pass over the whole selected Bybit universe.

    Returns the best symbols for full OpenAI analysis plus counts for UI status.
    """
    return asyncio.run(_bybit_watchlist_triage(mode, limit))


async def _fetch_bybit_kline(client, sem, symbol, interval="240", limit=90):
    async with sem:
        try:
            data = await _get_json(
                client,
                BYBIT_BASE + "/v5/market/kline",
                params={"category": "linear", "symbol": symbol, "interval": interval, "limit": limit},
            )
        except httpx.HTTPError:
            return symbol, []
    if data.get("retCode") not in (0, "0"):
        return symbol, []
    rows = []
    for raw in reversed((data.get("result") or {}).get("list") or []):
        try:
            rows.append(
                {
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": float(raw[5]),
                    "turnover": float(raw[6]),
                }
            )
        except (TypeError, ValueError, IndexError):
            continue
    return symbol, rows


def _series_ema(values, period):
    values = [float(v) for v in values if v == v]
    if not values:
        return float("nan")
    k = 2 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = value * k + ema * (1 - k)
    return ema


def _series_atr(candles, period=14):
    if len(candles) <= 1:
        return float("nan")
    trs = []
    for idx in range(1, len(candles)):
        c = candles[idx]
        prev = candles[idx - 1]["close"]
        trs.append(max(c["high"] - c["low"], abs(c["high"] - prev), abs(c["low"] - prev)))
    vals = trs[-period:]
    return sum(vals) / len(vals) if vals else float("nan")


def _fmt_watch_price(value):
    if value is None or not math.isfinite(float(value)):
        return "—"
    value = float(value)
    if value >= 1:
        return f"${value:,.2f}"
    if value >= 0.01:
        return f"${value:.4f}"
    return f"${value:.6f}"


def _entry_position(current, low, high):
    if low <= current <= high:
        return "Price in zone", 0.0, "In zone", "Active now", "At Zone"
    if current < low:
        gap = low - current
        distance = gap / current * 100 if current else 0.0
        return (
            "Price below zone",
            distance,
            f"{distance:.2f}%",
            f"{_fmt_watch_price(gap)} from zone",
            "Approaching" if distance <= 1.5 else "Waiting",
        )
    gap = current - high
    distance = gap / current * 100 if current else 0.0
    return (
        "Price above zone",
        distance,
        f"{distance:.2f}%",
        f"{_fmt_watch_price(gap)} from zone",
        "Approaching" if distance <= 1.5 else "Waiting",
    )


def _free_watchlist_row(record, candles, mode):
    if len(candles) < 30:
        return None
    symbol = record.get("symbol")
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    current = float(record.get("last_price") or closes[-1])
    ema20 = _series_ema(closes[-30:], 20)
    ema50 = _series_ema(closes[-70:], 50)
    atr = _series_atr(candles[-30:], 14)
    if not all(math.isfinite(v) and v > 0 for v in [current, ema20, atr]):
        return None

    change = float(record.get("price24h_pct") or 0)
    volume_rank = float(record.get("volume_rank") or 0)
    gain_rank = float(record.get("gain_rank") or 0)

    long_bias = current >= ema20 or change > 4 or mode in {"gainers", "change_24h", "low_cap_impulse"}
    short_bias = current < ema20 and (not math.isfinite(ema50) or ema20 <= ema50) and change < -1

    if short_bias and mode in {"top_volume", "tradfi_stocks"}:
        direction = "short"
        zone_mid = max(ema20, current + 0.45 * atr)
        low = zone_mid - 0.15 * atr
        high = zone_mid + 0.35 * atr
        setup = "4H Pullback Rejection"
        trigger = (
            f"Watch a push into {_fmt_watch_price(low)}–{_fmt_watch_price(high)} followed by rejection; "
            f"invalidation is acceptance back above the zone."
        )
    elif long_bias:
        direction = "long"
        pullback_mid = min(ema20, current - 0.45 * atr)
        low = pullback_mid - 0.35 * atr
        high = pullback_mid + 0.15 * atr
        setup = "4H Pullback Retest"
        if mode == "low_cap_impulse":
            setup = "Tactical Impulse Pullback"
        trigger = (
            f"Watch a pullback into {_fmt_watch_price(low)}–{_fmt_watch_price(high)}; "
            f"confirmation improves if buyers defend the zone instead of chasing the impulse."
        )
    else:
        return None

    if low <= 0 or high <= 0:
        return None
    if low > high:
        low, high = high, low

    position, distance, distance_label, distance_detail, status = _entry_position(current, low, high)
    if status == "At Zone":
        return None
    max_distance = 12.0 if mode == "low_cap_impulse" else 8.0
    if distance > max_distance:
        return None

    trend_score = 0.0
    if direction == "long":
        trend_score += 0.25 if current > ema20 else 0.08
        trend_score += 0.20 if math.isfinite(ema50) and ema20 > ema50 else 0.08
        trend_score += min(max(change, 0), 20) / 100
    else:
        trend_score += 0.25 if current < ema20 else 0.08
        trend_score += 0.20 if math.isfinite(ema50) and ema20 < ema50 else 0.08
        trend_score += min(abs(min(change, 0)), 15) / 100
    proximity_score = max(0.0, 1 - distance / max_distance) * 0.25
    liquidity_score = volume_rank * 0.15
    impulse_score = gain_rank * 0.15
    score = trend_score + proximity_score + liquidity_score + impulse_score

    if mode == "low_cap_impulse" and score < 0.72:
        grade = "C"
    elif score >= 0.78 and distance <= 4.0:
        grade = "A"
    else:
        grade = "B"

    if grade == "C" and mode != "low_cap_impulse":
        return None

    return {
        "symbol": symbol,
        "grade": grade,
        "direction": direction,
        "setup": setup,
        "status": status,
        "position": position,
        "entry": f"{_fmt_watch_price(low)} – {_fmt_watch_price(high)}",
        "current": _fmt_watch_price(current),
        "distance": distance,
        "distance_label": distance_label,
        "distance_detail": distance_detail,
        "trigger": trigger,
        "score": score,
        "change_24h": change,
        "turnover24h": float(record.get("turnover24h") or 0),
    }


async def _bybit_free_entry_watchlist(mode="top_volume", universe_limit=30, row_limit=12):
    async with httpx.AsyncClient(headers={"User-Agent": "orion-lite/1.0"}) as client:
        tickers, instruments = await asyncio.gather(
            _fetch_bybit_tickers(client),
            _fetch_bybit_instruments(client),
        )
        frame = _bybit_watchlist_frame(tickers, instruments, mode)
        ranked = _rank_watchlist_frame(frame, mode)
        if ranked.empty:
            return {"rows": [], "universe_count": int(len(frame)), "qualified_count": 0}
        scan_frame = ranked.head(universe_limit).copy()
        sem = asyncio.Semaphore(10)
        kline_pairs = await asyncio.gather(
            *(_fetch_bybit_kline(client, sem, symbol, interval="240", limit=90) for symbol in scan_frame["symbol"])
        )
    candles_by_symbol = dict(kline_pairs)
    rows = []
    for record in scan_frame.to_dict("records"):
        row = _free_watchlist_row(record, candles_by_symbol.get(record["symbol"], []), mode)
        if row:
            rows.append(row)
    rows.sort(
        key=lambda row: (
            {"A": 0, "B": 1, "C": 2}.get(row["grade"], 3),
            row["distance"],
            -row["score"],
        )
    )
    return {
        "rows": rows[:row_limit],
        "universe_count": int(len(frame)),
        "qualified_count": int(len(ranked)),
    }


def bybit_free_entry_watchlist(mode="top_volume", universe_limit=30, row_limit=12):
    """Free Bybit-only Entry Zone Watchlist.

    This deliberately does not call OpenAI. It uses the selected Bybit universe,
    4H candles, EMA/ATR proximity, 24h movement, and liquidity ranking to surface
    entry zones that have not yet been hit.
    """
    return asyncio.run(_bybit_free_entry_watchlist(mode, universe_limit, row_limit))


# ---------------- open-interest change (fetched on demand, e.g. shortlist) ----------------
_OI_NAN = {"oi5m": float("nan"), "oi1h": float("nan")}


async def _fetch_oi(client, sem, symbol):
    # 13 points of 5m OI -> latest vs 1-back = 5m change; latest vs 12-back (~60 min) = 1h change
    async with sem:
        try:
            data = await _get_json(
                client,
                BASE + "/futures/data/openInterestHist",
                params={"symbol": symbol, "period": "5m", "limit": 13},
            )
        except httpx.HTTPError:
            return symbol, dict(_OI_NAN)
    if not data or len(data) < 2:
        return symbol, dict(_OI_NAN)

    def _val(i):
        try:
            return float(data[i]["sumOpenInterest"])
        except (KeyError, ValueError, TypeError, IndexError):
            return None

    cur, prev5, prev1h = _val(-1), _val(-2), _val(0)
    oi5m = (cur - prev5) / prev5 * 100 if cur is not None and prev5 else float("nan")
    oi1h = (cur - prev1h) / prev1h * 100 if cur is not None and prev1h else float("nan")
    return symbol, {"oi5m": oi5m, "oi1h": oi1h}


async def _scan_oi(symbols, concurrency=10):
    async with httpx.AsyncClient(headers={"User-Agent": "orion-lite/1.0"}) as client:
        sem = asyncio.Semaphore(concurrency)
        res = await asyncio.gather(*(_fetch_oi(client, sem, s) for s in symbols))
    return {s: p for s, p in res}


def oi_change_pct(symbols):
    """Open-interest % change for each symbol over 5m and ~1h.

    Returns {symbol: {"oi5m": pct, "oi1h": pct}}.
    """
    symbols = list(symbols)
    if not symbols:
        return {}
    return asyncio.run(_scan_oi(symbols))


# ---------------- funding rate + tag relative to the coin's own recent normal ----------------
FUNDING_LOOKBACK = 22  # ~7 days of 8h settlements (current + ~21 of history)


def _zscore_tag(cur, hist):
    """Tag funding by how stretched it is vs the coin's OWN recent normal.

    Direction always follows the raw sign (+ = long side, - = short side); the
    relative z-score only sets how extreme it must be to count as crowded. So a
    coin that is merely *less negative* than usual reads "Normal", not "Long".
    """
    vals = [h for h in hist if h == h]  # drop NaN
    if len(vals) < 5:  # not enough history to judge "normal" for this coin
        return "—"
    mean = sum(vals) / len(vals)
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    if std <= 0:
        return "Normal"
    z = (cur - mean) / std
    if cur > 0:  # longs are the paying/crowded side
        if z > 2:
            return "Crowded long"
        if z > 1:
            return "Long tilt"
        return "Normal"
    if cur < 0:  # shorts are the paying/crowded side
        if z < -2:
            return "Crowded short"
        if z < -1:
            return "Short tilt"
        return "Normal"
    return "Normal"


async def _fetch_funding_hist(client, sem, symbol):
    async with sem:
        try:
            data = await _get_json(
                client,
                BASE + "/fapi/v1/fundingRate",
                params={"symbol": symbol, "limit": FUNDING_LOOKBACK},
            )
        except httpx.HTTPError:
            return symbol, {"rate": float("nan"), "tag": "—"}
    rates = []
    for d in data or []:
        try:
            rates.append(float(d["fundingRate"]) * 100)  # decimal -> %
        except (KeyError, ValueError, TypeError):
            pass
    if not rates:
        return symbol, {"rate": float("nan"), "tag": "—"}
    cur = rates[-1]          # most recent settled funding = "current"
    tag = _zscore_tag(cur, rates[:-1])  # compare against the coin's own prior normal
    return symbol, {"rate": cur, "tag": tag}


async def _scan_funding(symbols, concurrency=10):
    async with httpx.AsyncClient(headers={"User-Agent": "orion-lite/1.0"}) as client:
        sem = asyncio.Semaphore(concurrency)
        res = await asyncio.gather(*(_fetch_funding_hist(client, sem, s) for s in symbols))
    return {s: v for s, v in res}


def funding_relative(symbols):
    """Current funding (%, per 8h) + a tag relative to each coin's own normal.

    Returns {symbol: {"rate": pct, "tag": str}}. Tag is one of
    Crowded long / Long tilt / Normal / Short tilt / Crowded short, or '—'
    when there isn't enough history to judge.
    """
    symbols = list(symbols)
    if not symbols:
        return {}
    return asyncio.run(_scan_funding(symbols))


# ---------------- taker buy/sell (aggressor flow) over the last 1h ----------------
async def _fetch_taker(client, sem, symbol):
    async with sem:
        try:
            data = await _get_json(
                client,
                BASE + "/futures/data/takerlongshortRatio",
                params={"symbol": symbol, "period": "5m", "limit": 1},
            )
        except httpx.HTTPError:
            return symbol, float("nan")
    if not data:
        return symbol, float("nan")
    try:
        last = data[-1]
        bv, sv = float(last["buyVol"]), float(last["sellVol"])
    except (KeyError, ValueError, TypeError, IndexError):
        return symbol, float("nan")
    tot = bv + sv
    return symbol, (bv / tot * 100 if tot else float("nan"))


async def _scan_taker(symbols, concurrency=10):
    async with httpx.AsyncClient(headers={"User-Agent": "orion-lite/1.0"}) as client:
        sem = asyncio.Semaphore(concurrency)
        res = await asyncio.gather(*(_fetch_taker(client, sem, s) for s in symbols))
    return {s: p for s, p in res}


def taker_ratio(symbols):
    """Taker BUY share (% of aggressor volume) over the last 5m. {symbol: pct}."""
    symbols = list(symbols)
    if not symbols:
        return {}
    return asyncio.run(_scan_taker(symbols))


# ---------------- single-symbol live ticker (Binance USDⓈ-M futures) ----------
def live_ticker(symbol):
    """Live 24h ticker for one Binance perp. Returns {"last": float,
    "pct": float, "high": float, "low": float} or None on any failure.
    Used to surface a frequently-updating mark price (not the static value
    baked into an analysis JSON)."""
    try:
        r = httpx.get(
            BASE + "/fapi/v1/ticker/24hr",
            params={"symbol": symbol.upper()},
            headers={"User-Agent": "orion-lite/1.0"},
            timeout=6,
        )
        r.raise_for_status()
        d = r.json()
        return {
            "last": float(d["lastPrice"]),
            "pct": float(d["priceChangePercent"]),
            "high": float(d["highPrice"]),
            "low": float(d["lowPrice"]),
            "vol": float(d["volume"]),  # 24h base-asset volume (in coins)
        }
    except Exception:
        return None


def live_bybit_ticker(symbol):
    """Live 24h ticker for one Bybit linear perp."""
    try:
        r = httpx.get(
            BYBIT_BASE + "/v5/market/tickers",
            params={"category": "linear", "symbol": symbol.upper()},
            headers={"User-Agent": "orion-lite/1.0"},
            timeout=6,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("retCode") not in (0, "0"):
            return None
        items = (data.get("result") or {}).get("list") or []
        if not items:
            return None
        item = items[0]
        return {
            "last": float(item["lastPrice"]),
            "pct": float(item.get("price24hPcnt") or 0) * 100,
            "high": float(item.get("highPrice24h") or 0),
            "low": float(item.get("lowPrice24h") or 0),
            "vol": float(item.get("volume24h") or 0),
        }
    except Exception:
        return None


def live_bybit_derivatives(symbol):
    """Current Bybit funding and open interest for one linear perp.

    Returns {"funding": pct, "open_interest": float} or None on failure.
    """
    try:
        r = httpx.get(
            BYBIT_BASE + "/v5/market/tickers",
            params={"category": "linear", "symbol": symbol.upper()},
            headers={"User-Agent": "orion-lite/1.0"},
            timeout=6,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("retCode") not in (0, "0"):
            return None
        items = (data.get("result") or {}).get("list") or []
        if not items:
            return None
        item = items[0]
        return {
            "funding": float(item.get("fundingRate") or 0) * 100,
            "open_interest": float(item.get("openInterest") or 0),
        }
    except Exception:
        return None


# ---------------- S&P 500 futures sentiment (Yahoo Finance) ----------------
def sp500_futures():
    """Day change for E-mini S&P 500 futures (ES=F) from Yahoo Finance.

    Returns {"price": float, "pct": float} or None on any failure.
    `pct` is the % change vs the prior session close (drives the green/red dot).
    """
    try:
        r = httpx.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/ES=F",
            params={"range": "1d", "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        prev = float(prev)
        pct = (price - prev) / prev * 100 if prev else None
        return {"price": price, "pct": pct}
    except Exception:
        return None
