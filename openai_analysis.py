"""OpenAI analysis action prototype for the Trade Dashboard.

This module intentionally keeps the first integration thin: gather a compact
Bybit evidence pack, send it with the user's framework prompt to OpenAI, and
return the model's prose-first analysis for inspection before mapping it into
the finished dashboard cards.
"""
from __future__ import annotations

import math
import os
import re
import json
import time
import base64
import glob
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

import coinalyze
import scanner

BYBIT_BASE = "https://api.bybit.com"
OPENAI_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.2"
TRADINGVIEW_CAPTURE_DIR = os.environ.get("TRADINGVIEW_CAPTURE_DIR", "/private/tmp/tradingview-captures")
OPENAI_PRICING_USD_PER_1M = {
    # Estimate used for dashboard receipts. Update this map if the configured
    # model changes or OpenAI publishes a different rate for this account.
    "gpt-5.2": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
}
CANDLE_WINDOWS = {
    "1D": 90,
    "4H": 90,
    "1H": 72,
    "15M": 36,
}
EXECUTION_HIGHLIGHT_CANDLES = 18

_ROOT = os.path.dirname(os.path.abspath(__file__))
_FRAMEWORK_PROMPT_PATH = os.path.join(_ROOT, "framework", "openai_trade_action_prompt.txt")
_ANALYSES_DIR = os.path.join(_ROOT, "analyses")


def normalise_symbol(value: str) -> str:
    symbol = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    if symbol and not symbol.endswith(("USDT", "PERP")):
        symbol += "USDT"
    return symbol


def _get_json(client: httpx.Client, path: str, params: dict):
    response = client.get(BYBIT_BASE + path, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    if data.get("retCode") not in (0, "0"):
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    return data.get("result") or {}


def _klines(client: httpx.Client, symbol: str, interval: str, limit: int = 180):
    result = _get_json(
        client,
        "/v5/market/kline",
        {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit},
    )
    rows = []
    for raw in reversed(result.get("list") or []):
        try:
            rows.append(
                {
                    "ts": int(raw[0]),
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
    return rows


def _open_interest_history(client: httpx.Client, symbol: str, interval: str, limit: int = 24):
    result = _get_json(
        client,
        "/v5/market/open-interest",
        {"category": "linear", "symbol": symbol, "intervalTime": interval, "limit": limit},
    )
    rows = []
    for raw in result.get("list") or []:
        try:
            rows.append(
                {
                    "ts": int(raw["timestamp"]),
                    "open_interest": float(raw["openInterest"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(rows, key=lambda row: row["ts"])


def _funding_history(client: httpx.Client, symbol: str, limit: int = 24):
    result = _get_json(
        client,
        "/v5/market/funding/history",
        {"category": "linear", "symbol": symbol, "limit": limit},
    )
    rows = []
    for raw in result.get("list") or []:
        try:
            rows.append(
                {
                    "ts": int(raw["fundingRateTimestamp"]),
                    "funding_rate_pct": float(raw["fundingRate"]) * 100,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(rows, key=lambda row: row["ts"])


def _ticker(client: httpx.Client, symbol: str):
    result = _get_json(
        client,
        "/v5/market/tickers",
        {"category": "linear", "symbol": symbol},
    )
    items = result.get("list") or []
    if not items:
        raise RuntimeError(f"{symbol} was not found on Bybit linear perps.")
    item = items[0]

    def num(key):
        try:
            return float(item.get(key))
        except (TypeError, ValueError):
            return None

    return {
        "symbol": item.get("symbol", symbol),
        "last": num("lastPrice"),
        "mark": num("markPrice"),
        "index": num("indexPrice"),
        "bid1": num("bid1Price"),
        "ask1": num("ask1Price"),
        "change_24h_pct": (num("price24hPcnt") or 0.0) * 100,
        "high_24h": num("highPrice24h"),
        "low_24h": num("lowPrice24h"),
        "turnover_24h": num("turnover24h"),
        "volume_24h": num("volume24h"),
        "funding_rate_pct": (num("fundingRate") or 0.0) * 100,
        "next_funding_time_ms": num("nextFundingTime"),
        "funding_interval_hours": num("fundingIntervalHour"),
        "open_interest": num("openInterest"),
    }


def _orderbook(client: httpx.Client, symbol: str, limit: int = 200):
    result = _get_json(
        client,
        "/v5/market/orderbook",
        {"category": "linear", "symbol": symbol, "limit": limit},
    )

    def rows(side):
        out = []
        for raw in result.get(side) or []:
            try:
                price = float(raw[0])
                size = float(raw[1])
                out.append({"price": price, "size": size, "notional": price * size})
            except (TypeError, ValueError, IndexError):
                continue
        return out

    return {"bids": rows("b"), "asks": rows("a"), "ts": int(result.get("ts") or 0)}


def _returns(candles):
    closes = [c["close"] for c in candles if c.get("close")]
    return [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]


def _round(value, digits=4):
    if value is None:
        return None
    try:
        if math.isnan(value):
            return None
    except TypeError:
        pass
    return round(float(value), digits)


def _pct_change(current, previous):
    try:
        if previous in (None, 0):
            return None
        return (float(current) - float(previous)) / float(previous) * 100
    except (TypeError, ValueError):
        return None


def _ema(values, period: int):
    values = [float(v) for v in values if v is not None]
    if not values:
        return None
    k = 2 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = value * k + ema * (1 - k)
    return ema


def _rsi(values, period: int = 14):
    values = [float(v) for v in values if v is not None]
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for idx in range(1, len(values)):
        change = values[idx] - values[idx - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(candles, period: int = 14):
    if len(candles) <= 1:
        return None
    true_ranges = []
    for idx in range(1, len(candles)):
        candle = candles[idx]
        prev_close = candles[idx - 1]["close"]
        true_ranges.append(
            max(
                candle["high"] - candle["low"],
                abs(candle["high"] - prev_close),
                abs(candle["low"] - prev_close),
            )
        )
    if len(true_ranges) < period:
        return sum(true_ranges) / len(true_ranges) if true_ranges else None
    return sum(true_ranges[-period:]) / period


def _vwap(candles):
    volume = sum(c["volume"] for c in candles if c.get("volume"))
    if volume <= 0:
        return None
    turnover = sum(c["turnover"] for c in candles if c.get("turnover"))
    if turnover > 0:
        return turnover / volume
    typical_turnover = sum(((c["high"] + c["low"] + c["close"]) / 3) * c["volume"] for c in candles)
    return typical_turnover / volume


def _anchored_vwaps(candles, label: str):
    if not candles:
        return {}
    high_idx = max(range(len(candles)), key=lambda idx: candles[idx]["high"])
    low_idx = min(range(len(candles)), key=lambda idx: candles[idx]["low"])
    recent_idx = max(0, len(candles) - min(20, len(candles)))

    def anchor(idx, name):
        candle = candles[idx]
        return {
            "anchor": name,
            "anchor_time": datetime.fromtimestamp(candle["ts"] / 1000, ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M"),
            "anchor_price": _round(candle["high"] if "high" in name else candle["low"] if "low" in name else candle["close"], 6),
            "vwap": _round(_vwap(candles[idx:]), 6),
        }

    return {
        "swing_high": anchor(high_idx, f"{label} swing high"),
        "swing_low": anchor(low_idx, f"{label} swing low"),
        "recent_20": anchor(recent_idx, f"{label} recent 20-candle anchor"),
    }


def _indicator_summary(candles):
    closes = [c["close"] for c in candles]
    last = closes[-1] if closes else None
    ema20 = _ema(closes[-50:], 20)
    ema50 = _ema(closes[-90:], 50)
    atr14 = _atr(candles, 14)
    return {
        "last_close": _round(last, 6),
        "ema20": _round(ema20, 6),
        "ema50": _round(ema50, 6),
        "rsi14": _round(_rsi(closes, 14), 2),
        "atr14": _round(atr14, 6),
        "atr14_pct": _round((atr14 / last * 100) if atr14 and last else None, 2),
        "position_vs_ema20_pct": _round(_pct_change(last, ema20), 2),
        "position_vs_ema50_pct": _round(_pct_change(last, ema50), 2),
    }


def _trend_summary(rows):
    if not rows:
        return {}
    current = rows[-1]["open_interest"]
    out = {"current": _round(current, 4)}
    offsets = {"5m": 1, "1h": 12, "4h": 48}
    for label, offset in offsets.items():
        if len(rows) > offset:
            out[f"change_{label}_pct"] = _round(_pct_change(current, rows[-1 - offset]["open_interest"]), 2)
    return out


def _price_change_from_15m(candles, bars_back: int):
    if len(candles) <= bars_back:
        return None
    return _pct_change(candles[-1]["close"], candles[-1 - bars_back]["close"])


def _positioning_read(price_change, oi_change):
    if price_change is None or oi_change is None:
        return "insufficient data"
    price_up = price_change > 0.02
    price_down = price_change < -0.02
    oi_up = oi_change > 0.05
    oi_down = oi_change < -0.05
    if not price_up and not price_down and not oi_up and not oi_down:
        return "flat price and flat OI: no meaningful positioning edge"
    if price_up and not oi_up and not oi_down:
        return "price up with flat OI: mild move without strong new positioning confirmation"
    if price_down and not oi_up and not oi_down:
        return "price down with flat OI: mild sell pressure without strong new positioning confirmation"
    if not price_up and not price_down and oi_up:
        return "flat price with OI up: positioning is building without directional resolution"
    if not price_up and not price_down and oi_down:
        return "flat price with OI down: positions are closing without directional confirmation"
    if price_up and oi_up:
        return "price up with OI up: trend participation / new longs likely supporting the move"
    if price_up and oi_down:
        return "price up with OI down: short-covering/deleveraging, weaker continuation quality"
    if price_down and oi_up:
        return "price down with OI up: aggressive shorts or trapped longs building, squeeze/follow-through risk rises"
    return "price down with OI down: deleveraging, continuation signal is less reliable"


def _funding_summary(rows, current):
    rates = [r["funding_rate_pct"] for r in rows]
    avg = sum(rates) / len(rates) if rates else None
    latest = rates[-1] if rates else current
    return {
        "current_pct": _round(current, 6),
        "latest_history_pct": _round(latest, 6),
        "history_avg_pct": _round(avg, 6),
        "vs_history_avg_pct_points": _round((latest - avg) if latest is not None and avg is not None else None, 6),
        "recent": [
            {
                "time": datetime.fromtimestamp(row["ts"] / 1000, ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M"),
                "funding_rate_pct": _round(row["funding_rate_pct"], 6),
            }
            for row in rows[-8:]
        ],
    }


def _funding_countdown(ticker):
    raw = ticker.get("next_funding_time_ms")
    if not raw:
        return {}
    try:
        next_dt = datetime.fromtimestamp(float(raw) / 1000, timezone.utc)
    except (TypeError, ValueError, OSError):
        return {}
    seconds = max(0, int((next_dt - datetime.now(timezone.utc)).total_seconds()))
    return {
        "next_funding_time_utc": next_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "seconds_until_next_funding": seconds,
        "minutes_until_next_funding": _round(seconds / 60, 1),
        "hours_until_next_funding": _round(seconds / 3600, 2),
        "funding_interval_hours": _round(ticker.get("funding_interval_hours"), 2),
    }


def _funding_positioning_label(current_pct):
    if current_pct is None:
        return "funding unavailable"
    if current_pct >= 0.08:
        return "very positive funding: long crowding / long-squeeze risk if price stalls"
    if current_pct >= 0.03:
        return "positive funding: longs are paying; be careful chasing late longs"
    if current_pct <= -0.08:
        return "very negative funding: short crowding / upside squeeze risk"
    if current_pct <= -0.03:
        return "negative funding: shorts are paying; short continuation needs stronger confirmation"
    return "neutral funding: positioning is not obviously crowded from funding alone"


def _orderbook_depth_summary(book, last_price):
    bids = sorted(book.get("bids") or [], key=lambda row: row["price"], reverse=True)
    asks = sorted(book.get("asks") or [], key=lambda row: row["price"])
    best_bid = bids[0]["price"] if bids else None
    best_ask = asks[0]["price"] if asks else None
    mid = ((best_bid + best_ask) / 2) if best_bid and best_ask else last_price
    spread_pct = _pct_change(best_ask, best_bid) if best_bid and best_ask else None

    def depth(side_rows, pct, direction):
        if not mid:
            return {"base": None, "notional": None}
        if direction == "bid":
            selected = [row for row in side_rows if row["price"] >= mid * (1 - pct / 100)]
        else:
            selected = [row for row in side_rows if row["price"] <= mid * (1 + pct / 100)]
        return {
            "base": _round(sum(row["size"] for row in selected), 4),
            "notional": _round(sum(row["notional"] for row in selected), 2),
        }

    depth_bands = {}
    for pct in (0.25, 0.5, 1.0):
        bid_depth = depth(bids, pct, "bid")
        ask_depth = depth(asks, pct, "ask")
        bid_notional = bid_depth.get("notional") or 0
        ask_notional = ask_depth.get("notional") or 0
        depth_bands[f"within_{str(pct).replace('.', '_')}_pct"] = {
            "bid_depth": bid_depth,
            "ask_depth": ask_depth,
            "book_imbalance": _round(
                ((bid_notional - ask_notional) / (bid_notional + ask_notional) * 100)
                if (bid_notional + ask_notional)
                else None,
                2,
            ),
        }

    top_bids = sorted(bids[:50], key=lambda row: row["notional"], reverse=True)[:3]
    top_asks = sorted(asks[:50], key=lambda row: row["notional"], reverse=True)[:3]
    return {
        "source": "Bybit public order book snapshot",
        "best_bid": _round(best_bid, 8),
        "best_ask": _round(best_ask, 8),
        "mid": _round(mid, 8),
        "spread_pct": _round(spread_pct, 4),
        "depth_bands": depth_bands,
        "largest_nearby_bid_walls": [
            {"price": _round(row["price"], 8), "notional": _round(row["notional"], 2)}
            for row in top_bids
        ],
        "largest_nearby_ask_walls": [
            {"price": _round(row["price"], 8), "notional": _round(row["notional"], 2)}
            for row in top_asks
        ],
    }


def _positioning_edge(ticker, funding_rows, oi_rows, candles_15m, orderbook, coinalyze_edge=None):
    oi_changes = _trend_summary(oi_rows)
    horizons = {
        "15m": {"oi_offset": 3, "price_bars": 1},
        "1h": {"oi_offset": 12, "price_bars": 4},
        "4h": {"oi_offset": 48, "price_bars": 16},
    }
    horizon_reads = {}
    current_oi = oi_rows[-1]["open_interest"] if oi_rows else None
    for label, cfg in horizons.items():
        oi_change = None
        if current_oi is not None and len(oi_rows) > cfg["oi_offset"]:
            oi_change = _pct_change(current_oi, oi_rows[-1 - cfg["oi_offset"]]["open_interest"])
        price_change = _price_change_from_15m(candles_15m, cfg["price_bars"])
        horizon_reads[label] = {
            "price_change_pct": _round(price_change, 2),
            "open_interest_change_pct": _round(oi_change, 2),
            "read": _positioning_read(price_change, oi_change),
        }

    funding_context = _funding_summary(funding_rows, ticker.get("funding_rate_pct"))
    orderbook_context = _orderbook_depth_summary(orderbook, ticker.get("last"))
    coinalyze_edge = coinalyze_edge or {}
    spread = orderbook_context.get("spread_pct")
    thin_warning = None
    if spread is not None and spread > 0.08:
        thin_warning = "Wide spread: tight stops and market entries carry higher slippage/wick risk."
    elif spread is not None and spread > 0.03:
        thin_warning = "Moderate spread: use caution with very tight stops."

    liquidation_read = "Mixed: not available yet; do not use as edge."
    spot_perp_read = "Mixed: not available yet; do not use as edge."
    if coinalyze_edge.get("available"):
        liquidation_read = ((coinalyze_edge.get("liquidations") or {}).get("read")) or liquidation_read
        spot_perp_read = ((coinalyze_edge.get("spot_perp_cvd") or {}).get("read")) or spot_perp_read
    elif coinalyze_edge.get("error"):
        liquidation_read = f"Mixed: Coinalyze unavailable ({coinalyze_edge.get('error')})."
        spot_perp_read = f"Mixed: Coinalyze unavailable ({coinalyze_edge.get('error')})."

    return {
        "purpose": "Use this positioning layer to judge whether the chart setup is supported, crowded, thin, or squeeze-prone.",
        "funding": {
            **funding_context,
            **_funding_countdown(ticker),
            "positioning_read": _funding_positioning_label(funding_context.get("current_pct")),
        },
        "open_interest": {
            "source": "Bybit open-interest history, 5-minute sampling",
            **oi_changes,
            "horizon_reads": horizon_reads,
        },
        "order_book": {
            **orderbook_context,
            "liquidity_warning": thin_warning,
        },
        "liquidations": {
            "source": "Coinalyze liquidation history",
            "read": liquidation_read,
            **((coinalyze_edge.get("liquidations") or {}) if coinalyze_edge.get("available") else {}),
        },
        "spot_perp_cvd": {
            "source": "Coinalyze OHLCV buy-volume proxy",
            "read": spot_perp_read,
            **((coinalyze_edge.get("spot_perp_cvd") or {}) if coinalyze_edge.get("available") else {}),
            "spot_flow": coinalyze_edge.get("spot_flow") if coinalyze_edge.get("available") else None,
            "perp_flow": coinalyze_edge.get("perp_flow") if coinalyze_edge.get("available") else None,
        },
        "coinalyze": coinalyze_edge,
        "missing_edge_data": [
            "Spot-vs-perp CVD is derived from buy-volume history where spot coverage exists.",
        ],
    }


def _volume_profile(candles, bins: int = 12):
    if not candles:
        return {}
    low = min(c["low"] for c in candles)
    high = max(c["high"] for c in candles)
    if high <= low:
        return {}
    step = (high - low) / bins
    buckets = [{"low": low + idx * step, "high": low + (idx + 1) * step, "volume": 0.0} for idx in range(bins)]
    for candle in candles:
        typical = (candle["high"] + candle["low"] + candle["close"]) / 3
        idx = min(bins - 1, max(0, int((typical - low) / step)))
        buckets[idx]["volume"] += candle["volume"]
    total = sum(bucket["volume"] for bucket in buckets)
    poc = max(buckets, key=lambda bucket: bucket["volume"])
    ranked = sorted(buckets, key=lambda bucket: bucket["volume"], reverse=True)
    value_volume = 0.0
    selected = []
    for bucket in ranked:
        selected.append(bucket)
        value_volume += bucket["volume"]
        if total and value_volume / total >= 0.7:
            break
    return {
        "range": {"low": _round(low, 6), "high": _round(high, 6)},
        "poc": {
            "low": _round(poc["low"], 6),
            "high": _round(poc["high"], 6),
            "volume_share_pct": _round((poc["volume"] / total * 100) if total else None, 2),
        },
        "value_area_approx": {
            "low": _round(min(bucket["low"] for bucket in selected), 6),
            "high": _round(max(bucket["high"] for bucket in selected), 6),
            "volume_share_pct": _round((value_volume / total * 100) if total else None, 2),
        },
        "high_volume_nodes": [
            {
                "low": _round(bucket["low"], 6),
                "high": _round(bucket["high"], 6),
                "volume_share_pct": _round((bucket["volume"] / total * 100) if total else None, 2),
            }
            for bucket in ranked[:3]
        ],
    }


def _candle_summary(candles, limit=18):
    out = []
    for c in candles[-limit:]:
        out.append(
            {
                "time": datetime.fromtimestamp(c["ts"] / 1000, ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M"),
                "o": _round(c["open"]),
                "h": _round(c["high"]),
                "l": _round(c["low"]),
                "c": _round(c["close"]),
                "vol": _round(c["volume"], 2),
            }
        )
    return out


def build_evidence_pack(symbol: str):
    symbol = normalise_symbol(symbol)
    if not symbol:
        raise ValueError("Enter a symbol such as INJUSDT.")

    intervals = {"1D": "D", "4H": "240", "1H": "60", "15M": "15"}
    with httpx.Client(headers={"User-Agent": "orion-lite/1.0"}) as client:
        ticker = _ticker(client, symbol)
        candles = {
            label: _klines(client, symbol, interval, limit=CANDLE_WINDOWS[label])
            for label, interval in intervals.items()
        }
        btc_15m = _klines(client, "BTCUSDT", "15", limit=CANDLE_WINDOWS["15M"])
        eth_15m = _klines(client, "ETHUSDT", "15", limit=CANDLE_WINDOWS["15M"])
        oi_5m = _open_interest_history(client, symbol, "5min", limit=60)
        funding = _funding_history(client, symbol, limit=24)
        orderbook = _orderbook(client, symbol, limit=200)

    cor = scanner._pearson(_returns(candles["15M"]), _returns(btc_15m))
    generated = datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%b %-d, %Y, %-I:%M %p %Z")
    coinalyze_edge = coinalyze.enhanced_positioning(symbol)
    positioning_edge = _positioning_edge(ticker, funding, oi_5m, candles["15M"], orderbook, coinalyze_edge)
    return {
        "symbol": symbol,
        "generated_at_melbourne": generated,
        "source": "Bybit public linear perpetual market data",
        "ticker": {k: _round(v, 6) if isinstance(v, (int, float)) else v for k, v in ticker.items()},
        "positioning_edge": positioning_edge,
        "btc_cor_15m": _round(cor, 4),
        "candle_window_policy": {
            "context": {
                "1D": "last 90 candles for higher-timeframe regime and major levels",
                "4H": "last 90 candles for trade context, trend, range, failed breakdowns, and reclaims",
                "1H": "last 72 candles for near-term structure and setup development",
            },
            "execution": {
                "15M": "last 36 candles for execution context",
                "15M_last_18_highlight": "most recent 18 candles used as the trigger/confirmation window, not the whole analysis",
            },
        },
        "candles": {label: _candle_summary(rows, limit=CANDLE_WINDOWS[label]) for label, rows in candles.items()},
        "execution_highlight": {
            "15M_last_18": _candle_summary(candles["15M"], limit=EXECUTION_HIGHLIGHT_CANDLES),
        },
        "derived_indicators": {
            "note": "Computed locally from Bybit OHLCV. Use as evidence, not as a separate trading system.",
            "trend_momentum_volatility": {
                label: _indicator_summary(rows) for label, rows in candles.items()
            },
            "open_interest_trend": {
                "source": "Bybit open-interest history, 5-minute sampling",
                **_trend_summary(oi_5m),
            },
            "funding_context": _funding_summary(funding, ticker.get("funding_rate_pct")),
            "anchored_vwap": {
                "1D": _anchored_vwaps(candles["1D"], "1D"),
                "4H": _anchored_vwaps(candles["4H"], "4H"),
                "1H": _anchored_vwaps(candles["1H"], "1H"),
            },
            "volume_profile_approx": {
                "method": "Approximate profile from candle typical-price volume buckets; useful for POC/value-area context, not tick-accurate order flow.",
                "1H_72": _volume_profile(candles["1H"]),
                "15M_36": _volume_profile(candles["15M"]),
            },
        },
        "context": {
            "btc_15m_recent": _candle_summary(btc_15m, limit=CANDLE_WINDOWS["15M"]),
            "eth_15m_recent": _candle_summary(eth_15m, limit=CANDLE_WINDOWS["15M"]),
        },
        "limitations": [
            "Detailed order-flow is approximated from available public market data.",
            "Volume profile is approximated from candle data, not tick-level traded volume at price.",
            "AVWAP anchors are algorithmic swing/recent anchors; treat them as context unless they align with visible structure.",
        ],
    }


def _read_framework_prompt() -> str:
    with open(_FRAMEWORK_PROMPT_PATH, "r") as f:
        return f.read()


def _fmt_price(value):
    if value is None:
        return "—"
    value = float(value)
    if value >= 1:
        return f"${value:,.2f}"
    if value >= 0.01:
        return f"${value:.4f}"
    return f"${value:.6f}"


def _fmt_money(value):
    if value is None:
        return "—"
    value = float(value)
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    if value >= 1e3:
        return f"${value / 1e3:.2f}K"
    return f"${value:.0f}"


def _fmt_compact(value):
    if value is None:
        return "—"
    value = float(value)
    if value >= 1e9:
        return f"{value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:.2f}M"
    if value >= 1e3:
        return f"{value / 1e3:.2f}K"
    return f"{value:.0f}"


def _fmt_pct(value, digits=4):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}%"


def _display_symbol(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}/USDT"
    if symbol.endswith("PERP"):
        return symbol
    return symbol


def _extract_text(payload: dict) -> str:
    parts = []
    for item in payload.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") in ("output_text", "text") and content.get("text"):
                parts.append(content["text"])
    if parts:
        return "\n\n".join(parts).strip()
    return (payload.get("output_text") or "").strip()


def _post_openai(payload: dict, api_key: str, timeout: int = 120) -> dict:
    last_exc = None
    last_retry = None
    for attempt in range(3):
        try:
            response = httpx.post(
                OPENAI_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            if response.status_code in (429, 500, 502, 503, 504, 520):
                body = response.text[:800].strip()
                last_retry = f"OpenAI returned {response.status_code}"
                if body:
                    last_retry += f": {body}"
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            last_exc = exc
            time.sleep(2 ** attempt)
    if last_exc:
        raise last_exc
    if last_retry:
        raise RuntimeError(f"OpenAI request failed after retries. Last response: {last_retry}")
    raise RuntimeError("OpenAI request failed after retries.")


def _capture_tradingview_chart(symbol: str, setup_timeframe: str) -> dict:
    """TradingView screenshots must be handed in from the Codex in-app browser."""
    raise RuntimeError(
        "AI mode requires a TradingView screenshot captured from the in-app browser. "
        "No app-owned browser capture was attempted."
    )


def _latest_tradingview_capture(symbol: str, setup_timeframe: str):
    safe_tf = re.sub(r"[^A-Z0-9]", "", (setup_timeframe or "4H").upper())
    pattern = os.path.join(TRADINGVIEW_CAPTURE_DIR, f"{symbol}_{safe_tf}_*.png")
    matches = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not matches:
        return None
    image_path = matches[0]
    age_seconds = time.time() - os.path.getmtime(image_path)
    if age_seconds > 10 * 60:
        return None
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("ascii")
    return {
        "ok": True,
        "symbol": symbol,
        "timeframe": setup_timeframe,
        "url": "TradingView screenshot handoff",
        "title": f"{symbol} {setup_timeframe} TradingView screenshot",
        "image_path": image_path,
        "image_base64": image_base64,
        "captured_at": datetime.fromtimestamp(os.path.getmtime(image_path), timezone.utc).isoformat(),
        "fallback": True,
    }


def _parse_json_response(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    start = clean.find("{")
    end = clean.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("OpenAI did not return dashboard JSON.")
    return json.loads(clean[start : end + 1])


def _openai_usage_receipt(payload: dict, model: str) -> dict:
    usage = payload.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    details = usage.get("input_tokens_details") or {}
    cached_tokens = int(details.get("cached_tokens") or 0)
    billable_input = max(input_tokens - cached_tokens, 0)
    rates = OPENAI_PRICING_USD_PER_1M.get(model) or OPENAI_PRICING_USD_PER_1M.get(DEFAULT_MODEL)
    estimated_cost = None
    if rates:
        estimated_cost = (
            billable_input * rates["input"]
            + cached_tokens * rates["cached_input"]
            + output_tokens * rates["output"]
        ) / 1_000_000
    return {
        "model": model,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost, 6) if estimated_cost is not None else None,
        "pricing_note": "Estimated from configured per-1M token rates; verify against OpenAI billing for final charged amount.",
    }


def _schema_hint(symbol: str, evidence: dict, setup_timeframe: str = "4H") -> dict:
    return {
        "schema_version": 2,
        "framework_version": "Trade Setup Framework v1",
        "symbol": _display_symbol(symbol),
        "contract": "PERP",
        "generated_at": "UTC ISO timestamp",
        "price": "$...",
        "change_pct_24h": 0.0,
        "meta": {
            "timeframe_analyzed": "Daily + 4H + 1H + 15M",
            "setup_timeframe": setup_timeframe,
            "analysis_time": "Melbourne local time",
        },
        "snapshot": [
            {"label": "Current Price", "value": "$..."},
            {"label": "24H High", "value": "$..."},
            {"label": "24H Low", "value": "$..."},
            {"label": "24H Volume", "value": "$..."},
            {"label": "Funding", "value": "0.0000%"},
            {"label": "Open Interest", "value": "..."},
        ],
        "market_structure": {
            "state": "Trending Up | Trending Down | Range Bound | Transition",
            "volatility": "Compression | Expansion | Neutral",
            "bias": "Bullish | Bearish | Neutral",
            "structure": ["prose bullet", "prose bullet"],
            "volatility_note": "prose",
            "bias_note": "prose",
        },
        "intermarket": {
            "cor": evidence.get("btc_cor_15m"),
            "cor_tf": "15M",
            "note": "prose",
        },
        "positioning_edge": {
            "funding": "plain-language implication of funding and next funding timing",
            "open_interest": "plain-language implication of 15m/1h/4h OI changes",
            "liquidations": "plain-language implication of recent liquidation history",
            "spot_perp_cvd": "spot-vs-perp CVD implication, or unavailable caveat",
            "liquidity": "plain-language implication of order-book depth/spread for entries and stops",
            "missing": "CVD availability caveat if relevant",
        },
        "pattern_candidates": [
            {
                "name": "pattern name",
                "maturity": "Nascent | Forming | Mature | Ready | Triggered",
                "entry_mode": "Aggressive | Balanced | Chasing",
                "classification": "Continuation | Reversal | Compression | Liquidity / Reversal | Trap",
                "qualifier": "short qualifier",
                "grade": "A | B | C | D",
                "success_likelihood": {
                    "percent": 55,
                    "definition": "Estimated chance this setup reaches TP1 before invalidation",
                    "reason": "<=12 words explaining the probability driver",
                },
                "summary": "free-form honest reasoning, max 2 sentences",
                "positioning_edge": {
                    "funding": "Strengthens|Weakens|Mixed: one plain consequence sentence for this exact trade",
                    "funding_timing": "Strengthens|Weakens|Mixed: one plain consequence sentence for this exact trade",
                    "open_interest": "Strengthens|Weakens|Mixed: one plain consequence sentence for this exact trade",
                    "liquidations": "Strengthens|Weakens|Mixed: one plain consequence sentence from recent liquidation history",
                    "spot_perp_cvd": "Strengthens|Weakens|Mixed: one plain consequence sentence, or unavailable caveat",
                    "liquidity": "Strengthens|Weakens|Mixed: one plain entry/stop consequence sentence, not raw book data",
                    "trade_implication": "Strengthens|Weakens|Mixed: one plain sentence saying what to do differently",
                    "warnings": ["<=10 words each; only if needed"],
                },
                "entry": {
                    "direction": "long | short",
                    "zone": {
                        "low": 0.0,
                        "high": 0.0,
                        "label": "$x – $y or No valid entry",
                        "subtitle": "condition / rationale",
                    },
                    "stop": {
                        "value": 0.0,
                        "label": "$...",
                        "note": "what invalidates the thesis",
                    },
                    "risk": {"label": "~$...", "unit": f"per {symbol[:-4] if symbol.endswith('USDT') else symbol}"},
                    "t1": {"value": 0.0, "label": "$...", "rr": "~1 : X.X", "note": "implication"},
                    "t2": {"value": 0.0, "label": "$...", "rr": "~1 : X.X", "note": "implication"},
                    "tools": "tools actually used",
                },
                "alert_suggestions": [
                    {
                        "label": "short human label, e.g. 4H close above trigger",
                        "type": "Price enters zone | Price crosses level | Candle closes above | Candle closes below | Approaching trigger | Invalidation",
                        "timeframe": setup_timeframe,
                        "condition": "plain-language condition to watch",
                        "level": 0.0,
                        "zone": {"low": 0.0, "high": 0.0},
                        "note": "why this alert matters for this setup",
                    }
                ],
                "evidence": ["what is observed + why it matters"],
                "missing": ["what prevents progression"],
                "confluence": {
                    "strength": "STRONG | MODERATE | WEAK",
                    "checks": ["include relevant positioning-edge confirmations such as funding/OI/order-book support"],
                    "warnings": ["include relevant positioning-edge warnings such as crowded funding, OI divergence, or thin book"],
                },
            }
        ],
    }


def _stamp_dashboard_metadata(
    data: dict,
    symbol: str,
    evidence: dict,
    setup_timeframe: str = "4H",
    openai_receipt=None,
) -> dict:
    ticker = evidence.get("ticker") or {}
    last = ticker.get("last")
    high = ticker.get("high_24h")
    low = ticker.get("low_24h")
    turnover = ticker.get("turnover_24h")
    funding = ticker.get("funding_rate_pct")
    open_interest = ticker.get("open_interest")
    data["schema_version"] = 2
    data["framework_version"] = "Trade Setup Framework v1"
    data["symbol"] = _display_symbol(symbol)
    data["contract"] = "PERP"
    data["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data["price"] = _fmt_price(last)
    data["change_pct_24h"] = round(float(ticker.get("change_24h_pct") or 0), 2)
    data["meta"] = data.get("meta") or {}
    data["meta"]["timeframe_analyzed"] = (
        data["meta"].get("timeframe_analyzed")
        or "Context: 1D 90, 4H 90, 1H 72; execution: 15M 36, last 18 highlighted"
    )
    data["meta"]["setup_timeframe"] = setup_timeframe
    data["meta"]["analysis_time"] = datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%b %-d, %Y, %-I:%M %p %Z")
    if openai_receipt:
        data["meta"]["openai"] = openai_receipt
    data["snapshot"] = [
        {"label": "Current Price", "value": _fmt_price(last)},
        {"label": "24H High", "value": _fmt_price(high)},
        {"label": "24H Low", "value": _fmt_price(low)},
        {"label": "24H Volume", "value": _fmt_money(turnover)},
        {"label": "Funding", "value": _fmt_pct(funding)},
        {"label": "Open Interest", "value": _fmt_compact(open_interest)},
    ]
    data["intermarket"] = data.get("intermarket") or {}
    data["intermarket"]["cor"] = evidence.get("btc_cor_15m")
    data["intermarket"]["cor_tf"] = "15M"
    if not data.get("positioning_edge"):
        edge = evidence.get("positioning_edge") or {}
        funding = edge.get("funding") or {}
        oi = edge.get("open_interest") or {}
        book = edge.get("order_book") or {}
        liquidations = edge.get("liquidations") or {}
        spot_perp = edge.get("spot_perp_cvd") or {}
        data["positioning_edge"] = {
            "funding": funding.get("positioning_read") or "Funding read unavailable.",
            "open_interest": "; ".join(
                read.get("read", "")
                for read in (oi.get("horizon_reads") or {}).values()
                if read.get("read")
            )
            or "Open-interest read unavailable.",
            "liquidity": book.get("liquidity_warning")
            or f"Spread {book.get('spread_pct', '—')}%; use order-book depth bands for tight-stop context.",
            "liquidations": liquidations.get("read") or "Mixed: liquidation history unavailable.",
            "spot_perp_cvd": spot_perp.get("read") or "Mixed: spot/perp flow unavailable.",
            "missing": "Spot/perp flow depends on available spot coverage.",
        }
    _sanitize_candidate_numbers(data, last)
    return data


def _valid_price(value) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _risk_reward(entry_mid, stop_value, target_value, direction):
    try:
        entry_mid = float(entry_mid)
        stop_value = float(stop_value)
        target_value = float(target_value)
    except (TypeError, ValueError):
        return None
    risk = abs(entry_mid - stop_value)
    reward = target_value - entry_mid if direction == "long" else entry_mid - target_value
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def _sanitize_candidate_numbers(data: dict, fallback_price):
    """Keep renderer-required numeric fields non-zero without changing prose.

    The dashboard renderer calculates distance from the entry zone. When OpenAI
    honestly says "No valid entry" it may use zero/null numeric placeholders; we
    preserve that wording but replace zero numbers with the current price so the
    card can render instead of crashing.
    """
    if not _valid_price(fallback_price):
        fallback_price = 1.0
    fallback_price = float(fallback_price)
    for candidate in data.get("pattern_candidates") or []:
        entry = candidate.setdefault("entry", {})
        zone = entry.setdefault("zone", {})
        for key in ("low", "high"):
            if not _valid_price(zone.get(key)):
                zone[key] = fallback_price
        if float(zone["low"]) > float(zone["high"]):
            zone["low"], zone["high"] = zone["high"], zone["low"]
        for key in ("stop", "t1", "t2"):
            block = entry.setdefault(key, {})
            if not _valid_price(block.get("value")):
                block["value"] = fallback_price
        direction = (entry.get("direction") or "").strip().lower()
        if direction not in {"long", "short"}:
            direction = "short" if float(entry["t1"]["value"]) < float(zone["low"]) else "long"
            entry["direction"] = direction
        entry_mid = (float(zone["low"]) + float(zone["high"])) / 2
        stop_value = float(entry["stop"]["value"])
        for key in ("t1", "t2"):
            rr = _risk_reward(entry_mid, stop_value, float(entry[key]["value"]), direction)
            if rr is not None:
                entry[key]["rr"] = f"~1 : {rr:.1f}"
        risk = entry.setdefault("risk", {})
        risk.setdefault("label", "N/A")
        risk.setdefault("unit", "")


def generate_dashboard_analysis(
    symbol: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    tactical_mode: bool = False,
    setup_timeframe: str = "4H",
    prompt_mode: str = "prompt",
    chart_image_path: str = None,
    chart_image_meta: dict = None,
) -> dict:
    """Call OpenAI and write analyses/<SYMBOL>.json for the Trade Dashboard."""
    symbol = normalise_symbol(symbol)
    setup_timeframe = (setup_timeframe or "4H").upper()
    if setup_timeframe not in {"4H", "1H", "15M"}:
        setup_timeframe = "4H"
    prompt_mode = "ai" if (prompt_mode or "").lower() == "ai" else "prompt"
    evidence = build_evidence_pack(symbol)
    evidence["selected_setup_chart"] = setup_timeframe
    chart_capture = None
    if prompt_mode == "ai" and chart_image_path:
        if not os.path.exists(chart_image_path):
            raise RuntimeError("TradingView screenshot path is not readable.")
        with open(chart_image_path, "rb") as f:
            chart_capture = {
                "image_path": chart_image_path,
                "image_base64": base64.b64encode(f.read()).decode("ascii"),
                **(chart_image_meta or {}),
            }
        evidence["tradingview_chart"] = {
            "source": chart_capture.get("url") or "Codex in-app browser screenshot",
            "title": chart_capture.get("title"),
            "timeframe": setup_timeframe,
            "observed_symbol": chart_capture.get("observed_symbol"),
            "captured_at": chart_capture.get("captured_at"),
        }
    elif prompt_mode == "ai":
        raise RuntimeError(
            "AI mode requires a TradingView chart screenshot. No analysis was run because "
            "TradingView visual capture was not performed."
        )
    framework = _read_framework_prompt()
    tactical_instruction = ""
    if tactical_mode:
        tactical_instruction = (
            "\nLOW CAP IMPULSE MODE:\n"
            "This symbol was selected by a low-cap impulse scanner. In addition to clean A/B setups, identify the next "
            "tactical participation point even if the setup is messy. A tactical idea may be C-grade if it is not a clean "
            "framework trade, but it still needs a real participation level, invalidation, and reason not to chase. "
            "Prefer practical labels such as Tactical Long, Momentum Breakout, Pullback Watch, Failed Breakdown Reclaim, "
            "or Do Not Chase. Do not pretend the setup is high quality if it is not; the goal is to show where the next "
            "tradeable participation point would be for a fast low-cap impulse name.\n"
        )
    prompt = (
        f"You are generating the dashboard-renderable analysis for {symbol}.\n\n"
        "Use the user's framework prompt and the Bybit evidence pack below. Return ONLY valid JSON "
        "matching the dashboard schema. The schema is a container, not a cage: preserve your real "
        "judgement and write expressive prose inside each field. You must return exactly three pattern "
        "candidates because the dashboard needs three cards. For each candidate, include executable "
        "trade-location fields. If a candidate has no clean live trade, still fill the entry object "
        "with conditional or no-trade language in labels/subtitles/notes; do not make up a clean entry.\n\n"
        "Do not mention TradingView unless the evidence supports it; this is Bybit OHLCV/ticker/OI/funding "
        "data. Do not claim CVD or detailed order-flow because those are not supplied. You may use the "
        "supplied derived indicators: OI trend, funding context, EMA, RSI, ATR, anchored VWAP, approximate "
        "volume profile, support/resistance, candle swings, compression, measured moves, and BTC-COR 15M. "
        "Treat approximate volume profile and algorithmic AVWAP anchors as contextual evidence, not as "
        "tick-perfect confirmation.\n\n"
        "Setup validation rule: use the derived indicators to validate whether each candidate is a legitimate "
        "trade setup before assigning entry, trigger, and any grade. The purpose of OI trend, funding context, "
        "EMA/RSI/ATR, anchored VWAP, and approximate volume profile is validation, not decorative confidence. "
        "Ask whether the pattern is actually tradable at this location, whether the trigger is present or near, "
        "whether the stop/target structure is defensible, and whether participation/structure supports the idea. "
        "If the validation evidence does not support the setup, say so plainly rather than upgrading the grade.\n\n"
        "Positioning edge rule: explicitly use evidence.positioning_edge. Explain how funding plus the next funding "
        "timing, 15m/1h/4h open-interest change, and order-book depth/spread change the trade decision. Use this "
        "to identify crowded longs/shorts, short-covering moves, deleveraging, weak breakouts, squeeze risk, and "
        "whether a tight stop is realistic in the current book. If spot-vs-perp CVD would matter but is not available, "
        "say that as a limitation; do not invent it. Include the practical implication "
        "inside the top-level positioning_edge object and inside every candidate's positioning_edge object. Each "
        "candidate must explain how the same data changes that specific trade idea, not merely repeat a market summary. "
        "For each candidate positioning_edge field, start with exactly one of: Strengthens, Weakens, Mixed. Keep each "
        "field to one plain-English consequence sentence, not shorthand. Do not write raw observations by themselves. "
        "Bad: 'OI down; bounce likely covering.' Good: 'Weakens: the bounce may be short-covering, so take profits quickly.' "
        "Bad: 'spot+perp deltas negative.' Good: 'Strengthens: selling is coming from both spot and perps, so the short has better follow-through odds.' "
        "Bad: 'tight spread enables invalidation.' Good: 'Strengthens: orders should execute close to plan, so the tight stop is more realistic.' "
        "Bad: 'positive funding makes shorts slightly paid against.' Good: 'Strengthens: longs are paying shorts, so holding the short is slightly easier.' "
        "Explain whether the factor helps the entry, argues for smaller size, requires faster profit-taking, "
        "forces a stricter stop, or warns the setup may fail. For liquidity/order-book comments, do not say 'supportive for "
        "scalps' unless the candidate is explicitly a scalp and the entry/stop logic supports that. A bid-side imbalance "
        "does not prove scalpers are active; it only suggests visible bids may cushion a long entry or slow a breakdown until "
        "those bids pull or get filled. Say that practical implication plainly. Every candidate must include rows for "
        "funding, funding_timing, open_interest, liquidations, spot_perp_cvd, and liquidity. If spot-vs-perp CVD "
        "is unavailable, write 'Mixed: not available yet; do not use as edge.'\n\n"
        "Trade grade model: grade opportunity quality, not certainty. A means a high-quality opportunity is still "
        "available: the setup is validated, the entry is not stale, risk/reward is strong, enough move remains, "
        "and the trade is not chasing into nearby support/resistance. B means a good setup with one or more major "
        "weaknesses in validation rather than execution: mixed context, thinner confluence, incomplete trigger, "
        "higher dependency on confirmation, or a meaningful caveat. Valid A/B trade ideas should still preserve "
        "clean trade location, defensible invalidation, and decent risk/reward; otherwise they belong in C/D or "
        "no-trade territory. C means a watchlist or tactical-only idea: plausible but early, late, aggressive, or requiring "
        "too much to go right. D means no valid trade setup: poor location, stale/resolved pattern, bad R:R, "
        "invalid structure, or purely hypothetical conditions. Cap stale or lagging setups at C even if the "
        "original pattern read was correct; if most of the move has already resolved, the opportunity is no "
        "longer A-grade.\n\n"
        "Candle weighting rule: use 1D 90, 4H 90, and 1H 72 candles as the context window. "
        "Use 15M 36 candles as the execution window, with the supplied 15M last-18 highlight "
        "as the trigger/confirmation window only. Do not let the last 18 candles override the "
        "broader context if they are merely a late move into support/resistance or exhaustion.\n\n"
        f"Selected setup chart: {setup_timeframe}. Preserve multi-timeframe context and use broader/lower "
        "timeframes for bias, confluence, risk, invalidation, and timing nuance. However, construct the "
        "actual trade setup options primarily from the selected setup chart: pattern maturity, entry zone, "
        "trigger, stop, targets, and invalidation should reference that chart unless there is a clear "
        "reason to state that the selected chart has no valid setup.\n\n"
        "Maintain normal trading awareness of relevant support and resistance when assessing entries, "
        "exits, invalidation, and setup trajectory.\n\n"
        "For each pattern candidate, include 1-3 alert_suggestions where useful. These are not extra "
        "trade ideas; they are the specific moments the user may want the dashboard to watch so a "
        "developing setup is not missed. Prefer observable Bybit conditions such as price entering "
        "the entry zone, candle close above/below a trigger level, price approaching a trigger, or "
        "invalidation. Keep them practical and editable: include the timeframe, condition, level or "
        "zone when relevant, and a short note explaining why that alert matters. If no useful alert "
        "exists for a weak/no-trade candidate, return an empty alert_suggestions list.\n\n"
        f"{tactical_instruction}\n"
        "Dashboard schema hint:\n"
        f"{json.dumps(_schema_hint(symbol, evidence, setup_timeframe), indent=2)}\n\n"
        "USER FRAMEWORK PROMPT:\n"
        f"{framework}\n\n"
        "BYBIT EVIDENCE PACK:\n"
        f"{json.dumps(evidence, indent=2)}\n"
    )
    if prompt_mode == "ai":
        prompt = (
            f"You are acting like an unconstrained chart-analysis assistant for {symbol}.\n\n"
            "The user has attached the actual TradingView chart screenshot for the selected symbol and timeframe. "
            "Use the TradingView screenshot as the primary evidence. Use the Bybit evidence pack below as supporting "
            "market data for current price, recent candles, OI, funding, and cross-market context. "
            "Do your own chart-style assessment first: structure, trend, support/resistance, momentum, "
            "volatility, Fibonacci swings, measured moves, entry quality, invalidation, and target logic. "
            "Do not use the user's framework prompt, framework grading model, or framework decision rules in "
            "this mode. The dashboard schema below is ONLY a rendering template so the existing boxes can display "
            "your answer; it must not constrain the analytical method or force a framework-style response.\n\n"
            "Answer this task:\n"
            "What are the three best trade setups for this chart? Present them in order of viability. "
            "Run Fibonacci analysis and any other assessment needed to decide the best setups.\n\n"
            "Trading style for this AI mode: prioritise open trade opportunities right now. Prefer aggressive but "
            "defensible entries with tight stops and clear invalidation when the chart supports them. Do not make "
            "the user wait for a perfect future confirmation if there is a reasonable live entry already available. "
            "Only use conditional wait-for-confirmation setups when the current chart location is genuinely poor, "
            "the risk is too wide, or the trade would be pure chasing. Put live/aggressive opportunities before "
            "slow conservative triggers when both are valid.\n\n"
            "Return ONLY valid JSON matching the dashboard schema. The existing dashboard boxes will render "
            "your output, so you must still populate the schema fields completely. Treat field names such as "
            "pattern_candidates, grade, confluence, evidence, and missing as UI slots, not as instructions to follow "
            "the older framework. Do not force a long or short if the evidence does not support it. If one of the "
            "three best ideas is conditional, early, late, or a no-trade/watchlist idea, say that plainly inside "
            "the candidate fields rather than upgrading it.\n\n"
            "You must return exactly three pattern_candidates, ordered by viability from best to weakest. "
            "For each candidate, include executable trade-location fields: direction, entry zone, trigger "
            "context, stop/invalidation, TP1, TP2, risk:reward, tools used, evidence, missing conditions, "
            "alert_suggestions where useful, and success_likelihood.percent. success_likelihood is the estimated "
            "chance that this setup reaches TP1 before invalidation based on the visible chart and supporting data; "
            "it is not a guaranteed win rate and it does not mean TP2. "
            "For aggressive setups, keep stops tight around visible invalidation, not wide around distant structural "
            "levels unless the setup truly requires that wider stop. "
            "Use Fibonacci retracement/extension or measured-move logic where relevant, and name that in the "
            "tools/evidence text when used.\n\n"
            "Evidence limits: the screenshot shows the user's TradingView chart and indicators, but you still "
            "cannot see hidden settings beyond what is visible. Do not claim detailed order-flow or CVD unless "
            "it is visibly present in the screenshot or supplied evidence. You may use supplied EMA, RSI, ATR, "
            "anchored VWAP, approximate volume profile, candle swings, support/resistance, compression, measured "
            "moves, OI/funding, BTC/ETH context, Fibonacci-style swing analysis, and 15M trigger context.\n\n"
            "Positioning edge rule: explicitly use evidence.positioning_edge as the data layer behind the chart. "
            "For each setup, explain whether funding and next funding timing help or hurt the trade, whether "
            "15m/1h/4h open-interest confirms the direction or warns of short covering/deleveraging/crowding, "
            "and whether order-book depth/spread makes tight stops realistic. Use this to find edge that is not "
            "obvious from the screenshot alone. If spot-vs-perp CVD would matter but is not available, say so briefly; "
            "do not invent unavailable data. Put this inside every candidate's "
            "positioning_edge object as setup-specific trade advice, not as a generic summary at the top. "
            "For each candidate positioning_edge field, start with exactly one of: Strengthens, Weakens, Mixed. Keep each "
            "field to one plain-English consequence sentence, not shorthand. Do not write raw observations by themselves. "
            "Bad: 'OI down; bounce likely covering.' Good: 'Weakens: the bounce may be short-covering, so take profits quickly.' "
            "Bad: 'spot+perp deltas negative.' Good: 'Strengthens: selling is coming from both spot and perps, so the short has better follow-through odds.' "
            "Bad: 'tight spread enables invalidation.' Good: 'Strengthens: orders should execute close to plan, so the tight stop is more realistic.' "
            "Bad: 'positive funding makes shorts slightly paid against.' Good: 'Strengthens: longs are paying shorts, so holding the short is slightly easier.' "
            "Explain whether the factor helps the entry, argues for smaller size, requires faster profit-taking, "
            "forces a stricter stop, or warns the setup may fail. For liquidity/order-book comments, do not say 'supportive for "
            "scalps' unless the candidate is explicitly a scalp and the entry/stop logic supports that. A bid-side imbalance "
            "does not prove scalpers are active; it only suggests visible bids may cushion a long entry or slow a breakdown until "
            "those bids pull or get filled. Say that practical implication plainly. Every candidate must include rows for "
            "funding, funding_timing, open_interest, liquidations, spot_perp_cvd, and liquidity. If spot-vs-perp CVD "
            "is unavailable, write 'Mixed: not available yet; do not use as edge.'\n\n"
            f"Selected setup chart: {setup_timeframe}. Build the actual setup options primarily from this chart, "
            "using broader/lower timeframes only for context, confluence, risk, invalidation, and timing nuance.\n\n"
            "Dashboard schema hint:\n"
            f"{json.dumps(_schema_hint(symbol, evidence, setup_timeframe), indent=2)}\n\n"
            "BYBIT EVIDENCE PACK:\n"
            f"{json.dumps(evidence, indent=2)}\n"
        )
    input_payload = prompt
    if chart_capture and chart_capture.get("image_base64"):
        input_payload = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{chart_capture['image_base64']}",
                    },
                ],
            }
        ]
    payload = _post_openai(
        {
            "model": model,
            "input": input_payload,
            "max_output_tokens": 6000,
        },
        api_key=api_key,
        timeout=120,
    )
    raw = _extract_text(payload)
    if not raw:
        raise RuntimeError("OpenAI returned no text output.")
    receipt = _openai_usage_receipt(payload, model)
    data = _stamp_dashboard_metadata(_parse_json_response(raw), symbol, evidence, setup_timeframe, receipt)
    data["meta"]["prompt_mode"] = prompt_mode
    if chart_capture:
        data["meta"]["tradingview_chart"] = {
            "url": chart_capture.get("url"),
            "title": chart_capture.get("title"),
            "image_path": chart_capture.get("image_path"),
            "captured_at": chart_capture.get("captured_at"),
        }
    os.makedirs(_ANALYSES_DIR, exist_ok=True)
    json_path = os.path.join(_ANALYSES_DIR, f"{symbol}.json")
    raw_path = os.path.join(_ANALYSES_DIR, f"{symbol}.openai.raw.txt")
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    with open(raw_path, "w") as f:
        f.write(raw)
    return {
        "symbol": symbol,
        "json_path": json_path,
        "raw_path": raw_path,
        "data": data,
    }


def run_openai_analysis(symbol: str, api_key: str, model: str = DEFAULT_MODEL):
    evidence = build_evidence_pack(symbol)
    framework = _read_framework_prompt()
    action_prompt = (
        "You are powering a Trade Dashboard action. Analyse the selected symbol using the "
        "framework below and the market evidence pack. The dashboard has required sections, "
        "but your judgement must remain honest: do not beautify weak setups, do not force "
        "certainty, and do not hide conditionality. Return markdown for a temporary review "
        "panel, with clear headings that mirror the framework.\n\n"
        "TEMPORARY REVIEW PANEL OUTPUT REQUIREMENTS:\n"
        "- Return exactly three pattern candidates unless the evidence pack is unusable.\n"
        "- For each candidate, include a Trade Setup subsection with these labelled lines: "
        "Trade Status, Entry Zone, Stop / Invalidation, TP1, TP2, Risk:Reward, Supporting "
        "Tools, and Execution Commentary.\n"
        "- If a candidate does not have a valid trade location, do not omit the fields. Set "
        "Trade Status to No Trade, set Entry Zone to No valid entry at current location, "
        "and explain exactly what would need to change before an entry exists.\n"
        "- Entries and targets may be conditional. Say the condition plainly, for example "
        "'only after 4H acceptance below support' or 'only on reclaim above the swept low'.\n"
        "- Do not make the levels neat just to satisfy the dashboard. If the level is ugly, "
        "late, wide, speculative, or low quality, state that directly inside the field.\n"
        "- The point is executable trade-location thinking for every option, not just high-level "
        "pattern commentary.\n\n"
        "FRAMEWORK PROMPT:\n"
        f"{framework}\n\n"
        "MARKET EVIDENCE PACK:\n"
        f"{evidence}\n"
    )
    payload = _post_openai(
        {
            "model": model,
            "input": action_prompt,
            "max_output_tokens": 3500,
        },
        api_key=api_key,
        timeout=90,
    )
    text = _extract_text(payload)
    if not text:
        raise RuntimeError("OpenAI returned no text output.")
    return {
        "symbol": evidence["symbol"],
        "model": model,
        "evidence": evidence,
        "analysis": text,
    }
