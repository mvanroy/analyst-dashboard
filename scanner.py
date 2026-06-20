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

import httpx
import pandas as pd

BASE = "https://fapi.binance.com"


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
