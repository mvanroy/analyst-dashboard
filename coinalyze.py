from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx

BASE_URL = "https://api.coinalyze.net/v1"
ROOT = Path(__file__).resolve().parent
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
CACHE_PATH = ROOT / "runtime" / "coinalyze_markets.json"
MARKET_CACHE_SECONDS = 24 * 60 * 60
EXCHANGE_NAMES = {
    "6": "Bybit",
    "A": "Binance",
    "3": "OKX",
    "4": "Bitget",
    "K": "Kraken",
    "C": "Coinbase",
}
FUTURE_EXCHANGE_PREF = ("6", "A", "3", "4")
SPOT_EXCHANGE_PREF = ("A", "6", "3", "4", "C", "K")


def _secret(name: str) -> str:
    value = os.environ.get(name.upper()) or os.environ.get(name.lower())
    if value:
        return value.strip()
    try:
        text = SECRETS_PATH.read_text()
    except OSError:
        return ""
    pattern = rf'(?m)^\s*{re.escape(name)}\s*=\s*["\']([^"\']+)["\']\s*$'
    match = re.search(pattern, text, re.I)
    return (match.group(1).strip() if match else "")


def _api_key() -> str:
    return _secret("coinalyze_api_key")


def _get(path: str, params: dict | None = None):
    key = _api_key()
    if not key:
        raise RuntimeError("Coinalyze API key is not configured.")
    params = dict(params or {})
    params["api_key"] = key
    response = httpx.get(BASE_URL + path, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def _markets():
    now = time.time()
    try:
        cached = json.loads(CACHE_PATH.read_text())
        if now - float(cached.get("ts") or 0) < MARKET_CACHE_SECONDS:
            return cached.get("future") or [], cached.get("spot") or []
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass

    future = _get("/future-markets")
    spot = _get("/spot-markets")
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps({"ts": now, "future": future, "spot": spot}))
    return future, spot


def _norm(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _pick_future(symbol: str, markets: list[dict]):
    target = _norm(symbol)
    matches = []
    for market in markets:
        if not market.get("is_perpetual"):
            continue
        if (market.get("quote_asset") or "").upper() != "USDT":
            continue
        if _norm(market.get("symbol_on_exchange")) != target:
            continue
        matches.append(market)
    return sorted(matches, key=lambda m: FUTURE_EXCHANGE_PREF.index((m.get("exchange") or "").upper()) if (m.get("exchange") or "").upper() in FUTURE_EXCHANGE_PREF else 99)[0] if matches else None


def _pick_spot(symbol: str, markets: list[dict]):
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    matches = []
    for market in markets:
        if (market.get("base_asset") or "").upper() != base.upper():
            continue
        if (market.get("quote_asset") or "").upper() != "USDT":
            continue
        if not market.get("has_buy_sell_data"):
            continue
        matches.append(market)
    return sorted(matches, key=lambda m: SPOT_EXCHANGE_PREF.index((m.get("exchange") or "").upper()) if (m.get("exchange") or "").upper() in SPOT_EXCHANGE_PREF else 99)[0] if matches else None


def _history(path: str, market_symbol: str, interval="15min", hours=4, **extra):
    now = int(time.time())
    params = {
        "symbols": market_symbol,
        "interval": interval,
        "from": now - hours * 60 * 60,
        "to": now,
        **extra,
    }
    data = _get(path, params)
    if not data:
        return []
    return (data[0] or {}).get("history") or []


def _sum(rows, key):
    return sum(float(row.get(key) or 0) for row in rows)


def _flow_summary(rows):
    volume = _sum(rows, "v")
    buy = _sum(rows, "bv")
    sell = max(volume - buy, 0)
    delta = buy - sell
    delta_pct = (delta / volume * 100) if volume else None
    return {
        "volume": round(volume, 4),
        "buy_volume": round(buy, 4),
        "sell_volume": round(sell, 4),
        "delta": round(delta, 4),
        "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
    }


def _liquidation_summary(rows):
    long_liq = _sum(rows, "l")
    short_liq = _sum(rows, "s")
    total = long_liq + short_liq
    if not total:
        read = "Mixed: no meaningful liquidation pressure in sample."
    elif long_liq > short_liq * 1.5:
        read = "Mixed: longs recently flushed; bounce risk rises after downside."
    elif short_liq > long_liq * 1.5:
        read = "Mixed: shorts recently flushed; chase-long risk rises."
    else:
        read = "Mixed: liquidations balanced; no clear edge."
    return {
        "long_liquidations": round(long_liq, 4),
        "short_liquidations": round(short_liq, 4),
        "read": read,
    }


def liquidation_map(symbol: str = "BTCUSDT", hours: int = 24, interval: str = "1hour") -> dict:
    """Hourly USD liquidation buckets for a futures symbol.

    Coinalyze returns long liquidations in `l` and short liquidations in `s`.
    """
    try:
        future_markets, _ = _markets()
        future = _pick_future(symbol, future_markets)
        if not future:
            return {"available": False, "error": "No Coinalyze futures market match."}
        rows = _history(
            "/liquidation-history",
            future.get("symbol"),
            interval=interval,
            hours=hours,
            convert_to_usd="true",
        )
        buckets = []
        for row in rows:
            long_liq = float(row.get("l") or 0)
            short_liq = float(row.get("s") or 0)
            buckets.append(
                {
                    "ts": row.get("t"),
                    "long": long_liq,
                    "short": short_liq,
                    "total": long_liq + short_liq,
                }
            )
        long_total = sum(row["long"] for row in buckets)
        short_total = sum(row["short"] for row in buckets)
        return {
            "available": True,
            "source": "Coinalyze",
            "future_symbol": future.get("symbol"),
            "future_exchange": EXCHANGE_NAMES.get(future.get("exchange"), future.get("exchange")),
            "hours": hours,
            "interval": interval,
            "long_liquidations": long_total,
            "short_liquidations": short_total,
            "total_liquidations": long_total + short_total,
            "buckets": buckets,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def _spot_perp_read(spot_flow, perp_flow):
    sd = spot_flow.get("delta_pct")
    pd = perp_flow.get("delta_pct")
    if sd is None or pd is None:
        return "Mixed: spot/perp buy-sell data unavailable."
    if sd > 3 and pd > 3:
        return "Strengthens: spot and perp buying align."
    if pd > 3 and sd <= 0:
        return "Weakens: perp-led buying lacks spot support."
    if sd > 3 and pd <= 0:
        return "Strengthens: spot buying leads leveraged flow."
    if sd < -3 and pd < -3:
        return "Strengthens short: spot and perp selling align."
    if pd < -3 and sd >= 0:
        return "Weakens short: perp selling lacks spot support."
    return "Mixed: spot/perp flow not decisive."


def enhanced_positioning(symbol: str) -> dict:
    try:
        future_markets, spot_markets = _markets()
        future = _pick_future(symbol, future_markets)
        if not future:
            return {"available": False, "error": "No Coinalyze futures market match."}
        spot = _pick_spot(symbol, spot_markets)

        future_symbol = future.get("symbol")
        liq_rows = _history("/liquidation-history", future_symbol, convert_to_usd="true")
        perp_rows = _history("/ohlcv-history", future_symbol)
        spot_rows = _history("/ohlcv-history", spot.get("symbol")) if spot else []

        liq = _liquidation_summary(liq_rows)
        perp_flow = _flow_summary(perp_rows)
        spot_flow = _flow_summary(spot_rows) if spot_rows else {}
        return {
            "available": True,
            "source": "Coinalyze",
            "future_symbol": future_symbol,
            "future_exchange": EXCHANGE_NAMES.get(future.get("exchange"), future.get("exchange")),
            "spot_symbol": spot.get("symbol") if spot else None,
            "spot_exchange": EXCHANGE_NAMES.get(spot.get("exchange"), spot.get("exchange")) if spot else None,
            "liquidations": liq,
            "perp_flow": perp_flow,
            "spot_flow": spot_flow,
            "spot_perp_cvd": {
                "read": _spot_perp_read(spot_flow, perp_flow),
                "spot_delta_pct": spot_flow.get("delta_pct"),
                "perp_delta_pct": perp_flow.get("delta_pct"),
            },
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}
