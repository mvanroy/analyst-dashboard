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
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

import scanner

BYBIT_BASE = "https://api.bybit.com"
OPENAI_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.2"

_ROOT = os.path.dirname(os.path.abspath(__file__))
_FRAMEWORK_PROMPT_PATH = os.path.join(_ROOT, "framework", "openai_trade_action_prompt.txt")
_ANALYSES_DIR = os.path.join(_ROOT, "analyses")


def normalise_symbol(value: str) -> str:
    symbol = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    if symbol and not symbol.endswith("USDT"):
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
        "change_24h_pct": (num("price24hPcnt") or 0.0) * 100,
        "high_24h": num("highPrice24h"),
        "low_24h": num("lowPrice24h"),
        "turnover_24h": num("turnover24h"),
        "volume_24h": num("volume24h"),
        "funding_rate_pct": (num("fundingRate") or 0.0) * 100,
        "open_interest": num("openInterest"),
    }


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
        candles = {label: _klines(client, symbol, interval) for label, interval in intervals.items()}
        btc_15m = _klines(client, "BTCUSDT", "15")
        eth_15m = _klines(client, "ETHUSDT", "15")

    cor = scanner._pearson(_returns(candles["15M"]), _returns(btc_15m))
    generated = datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%b %-d, %Y, %-I:%M %p %Z")
    return {
        "symbol": symbol,
        "generated_at_melbourne": generated,
        "source": "Bybit public linear perpetual market data",
        "ticker": {k: _round(v, 6) if isinstance(v, (int, float)) else v for k, v in ticker.items()},
        "btc_cor_15m": _round(cor, 4),
        "candles": {label: _candle_summary(rows) for label, rows in candles.items()},
        "context": {
            "btc_15m_recent": _candle_summary(btc_15m, limit=10),
            "eth_15m_recent": _candle_summary(eth_15m, limit=10),
        },
        "limitations": [
            "This prototype uses Bybit public market data, not a TradingView chart screenshot.",
            "CVD and detailed order-flow are not included yet.",
            "Open interest is current snapshot only in this first pass.",
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


def _display_symbol(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}/USDT"
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
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            last_exc = exc
            time.sleep(2 ** attempt)
    if last_exc:
        raise last_exc
    raise RuntimeError("OpenAI request failed after retries.")


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


def _schema_hint(symbol: str, evidence: dict) -> dict:
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
            "analysis_time": "Melbourne local time",
        },
        "snapshot": [
            {"label": "Current Price", "value": "$..."},
            {"label": "24H High", "value": "$..."},
            {"label": "24H Low", "value": "$..."},
            {"label": "24H Volume", "value": "$..."},
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
        "pattern_candidates": [
            {
                "name": "pattern name",
                "maturity": "Nascent | Forming | Mature | Ready | Triggered",
                "entry_mode": "Aggressive | Balanced | Chasing",
                "classification": "Continuation | Reversal | Compression | Liquidity / Reversal | Trap",
                "qualifier": "short qualifier",
                "grade": "A | B | C | D",
                "summary": "free-form honest reasoning, max 2 sentences",
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
                "evidence": ["what is observed + why it matters"],
                "missing": ["what prevents progression"],
                "confluence": {
                    "strength": "STRONG | MODERATE | WEAK",
                    "checks": [],
                    "warnings": [],
                },
            }
        ],
    }


def _stamp_dashboard_metadata(data: dict, symbol: str, evidence: dict) -> dict:
    ticker = evidence.get("ticker") or {}
    last = ticker.get("last")
    high = ticker.get("high_24h")
    low = ticker.get("low_24h")
    turnover = ticker.get("turnover_24h")
    data["schema_version"] = 2
    data["framework_version"] = "Trade Setup Framework v1"
    data["symbol"] = _display_symbol(symbol)
    data["contract"] = "PERP"
    data["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data["price"] = _fmt_price(last)
    data["change_pct_24h"] = round(float(ticker.get("change_24h_pct") or 0), 2)
    data["meta"] = data.get("meta") or {}
    data["meta"]["timeframe_analyzed"] = data["meta"].get("timeframe_analyzed") or "Daily + 4H + 1H + 15M"
    data["meta"]["analysis_time"] = datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%b %-d, %Y, %-I:%M %p %Z")
    data["snapshot"] = [
        {"label": "Current Price", "value": _fmt_price(last)},
        {"label": "24H High", "value": _fmt_price(high)},
        {"label": "24H Low", "value": _fmt_price(low)},
        {"label": "24H Volume", "value": _fmt_money(turnover)},
    ]
    data["intermarket"] = data.get("intermarket") or {}
    data["intermarket"]["cor"] = evidence.get("btc_cor_15m")
    data["intermarket"]["cor_tf"] = "15M"
    _sanitize_candidate_numbers(data, last)
    return data


def _valid_price(value) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


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
        risk = entry.setdefault("risk", {})
        risk.setdefault("label", "N/A")
        risk.setdefault("unit", "")


def generate_dashboard_analysis(symbol: str, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """Call OpenAI and write analyses/<SYMBOL>.json for the Trade Dashboard."""
    symbol = normalise_symbol(symbol)
    evidence = build_evidence_pack(symbol)
    framework = _read_framework_prompt()
    prompt = (
        f"You are generating the dashboard-renderable analysis for {symbol}.\n\n"
        "Use the user's framework prompt and the Bybit evidence pack below. Return ONLY valid JSON "
        "matching the dashboard schema. The schema is a container, not a cage: preserve your real "
        "judgement and write expressive prose inside each field. You must return exactly three pattern "
        "candidates because the dashboard needs three cards. For each candidate, include executable "
        "trade-location fields. If a candidate has no clean live trade, still fill the entry object "
        "with conditional or no-trade language in labels/subtitles/notes; do not make up a clean entry.\n\n"
        "Do not mention TradingView unless the evidence supports it; this is Bybit OHLCV/ticker/OI/funding "
        "data. Do not claim CVD, AVWAP, RSI, EMA, or volume profile unless you can derive it from the "
        "supplied evidence. You may use support/resistance, candle swings, compression, measured moves, "
        "funding, OI, and BTC-COR 15M.\n\n"
        "Dashboard schema hint:\n"
        f"{json.dumps(_schema_hint(symbol, evidence), indent=2)}\n\n"
        "USER FRAMEWORK PROMPT:\n"
        f"{framework}\n\n"
        "BYBIT EVIDENCE PACK:\n"
        f"{json.dumps(evidence, indent=2)}\n"
    )
    payload = _post_openai(
        {
            "model": model,
            "input": prompt,
            "max_output_tokens": 6000,
        },
        api_key=api_key,
        timeout=120,
    )
    raw = _extract_text(payload)
    if not raw:
        raise RuntimeError("OpenAI returned no text output.")
    data = _stamp_dashboard_metadata(_parse_json_response(raw), symbol, evidence)
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
