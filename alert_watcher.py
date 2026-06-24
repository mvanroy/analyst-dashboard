"""Local alert watcher for saved AI-assisted trade alerts."""
from __future__ import annotations

from datetime import datetime, timezone
import re
import time

import httpx

import alert_store
import telegram_notifier


BYBIT_BASE = "https://api.bybit.com"
OKX_BASE = "https://www.okx.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"
TF_TO_BYBIT = {"15M": "15", "1H": "60", "4H": "240", "1D": "D", "D": "D"}
TF_TO_OKX = {"15M": "15m", "1H": "1H", "4H": "4H", "1D": "1D", "D": "1D"}
TF_TO_BINANCE = {"15M": "15m", "1H": "1h", "4H": "4h", "1D": "1d", "D": "1d"}
TF_MS = {"15M": 15 * 60_000, "1H": 60 * 60_000, "4H": 4 * 60 * 60_000, "1D": 24 * 60 * 60_000, "D": 24 * 60 * 60_000}


def capture_baseline(alert: dict) -> dict:
    """Capture the market state at save time so stale conditions don't trigger.

    Candle alerts remember the latest closed candle that already existed. Price
    and zone alerts remember the current Bybit price and whether price was
    already inside the watched zone.
    """
    symbol = (alert.get("symbol") or "").upper()
    baseline = {"captured_at": datetime.now().isoformat(timespec="seconds")}
    if not symbol:
        return baseline
    typ = (alert.get("type") or "").lower()
    condition = (alert.get("condition") or "").lower()
    if "candle" in typ or "close" in typ or "close" in condition:
        tf = _normalise_tf(alert.get("timeframe") or _tf_from_text(alert.get("condition") or ""))
        candle = _latest_closed_candle(symbol, tf) if tf else None
        baseline["kind"] = "candle"
        baseline["timeframe"] = tf
        if candle:
            baseline["candle_start"] = candle.get("start")
            baseline["candle_close_time"] = candle.get("close_time")
            baseline["candle_close"] = candle.get("close")
        return baseline

    price = _live_price(symbol)
    baseline["kind"] = "price"
    baseline["price"] = price
    zone = alert.get("zone") if isinstance(alert.get("zone"), dict) else {}
    low = _to_float(zone.get("low"))
    high = _to_float(zone.get("high"))
    if price is not None and low is not None and high is not None:
        lo, hi = sorted([low, high])
        baseline["in_zone"] = lo <= price <= hi
        baseline["zone"] = {"low": lo, "high": hi}
    return baseline


def check_alerts(limit: int = 80) -> dict:
    """Evaluate active alerts once. Returns counts and newly-triggered alerts.

    This is intentionally mechanical: no AI call, no inference beyond the saved
    rule. Candle-close alerts only inspect fully closed candles.
    """
    alerts = alert_store.load_alerts()
    active = [a for a in alerts if (a.get("status") or "active") == "active"][:limit]
    prices: dict[str, float | None] = {}
    candles: dict[tuple[str, str], dict | None] = {}
    triggered = []
    checked = 0
    errors = []
    baseline_changed = False
    for alert in active:
        checked += 1
        symbol = (alert.get("symbol") or "").upper()
        if not symbol:
            continue
        if not alert.get("baseline"):
            alert["baseline"] = capture_baseline(alert)
            baseline_changed = True
            continue
        try:
            result = _evaluate_alert(alert, prices, candles)
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
            continue
        if result and alert_store.mark_triggered(alert.get("id"), result):
            delivered = _notify_triggered_alert(alert, result)
            triggered.append({**alert, "trigger": result, "notification": delivered})
    if baseline_changed:
        alert_store.save_alerts(alerts)
    return {
        "checked": checked,
        "triggered": triggered,
        "errors": errors[:5],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def _notify_triggered_alert(alert: dict, trigger: dict) -> dict:
    notified = alert.get("notified") if isinstance(alert.get("notified"), dict) else {}
    if notified.get("telegram"):
        return {"ok": True, "skipped": True, "reason": "Already sent."}
    try:
        result = telegram_notifier.send_alert(alert, trigger)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if result.get("ok"):
        alert_store.mark_notified(alert.get("id"), "telegram", result)
    return result


def _evaluate_alert(alert: dict, prices: dict, candles: dict) -> dict | None:
    typ = (alert.get("type") or "").lower()
    condition = (alert.get("condition") or "").lower()
    if "candle" in typ or "close" in typ or "close" in condition:
        return _evaluate_candle_close(alert, candles)
    return _evaluate_price(alert, prices)


def _evaluate_price(alert: dict, prices: dict) -> dict | None:
    symbol = (alert.get("symbol") or "").upper()
    if symbol not in prices:
        prices[symbol] = _live_price(symbol)
    price = prices.get(symbol)
    if price is None:
        return None

    zone = alert.get("zone") if isinstance(alert.get("zone"), dict) else {}
    low = _to_float(zone.get("low"))
    high = _to_float(zone.get("high"))
    if low is not None and high is not None:
        lo, hi = sorted([low, high])
        baseline = alert.get("baseline") if isinstance(alert.get("baseline"), dict) else {}
        started_in_zone = baseline.get("in_zone") is True
        if lo <= price <= hi:
            if started_in_zone:
                return None
            return {
                "kind": "price_zone",
                "message": f"Price entered zone {lo:g}-{hi:g}.",
                "price": price,
                "zone": {"low": lo, "high": hi},
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            }
        return None

    level = _to_float(alert.get("level")) or _level_from_text(alert.get("condition") or "")
    if level is None:
        return None
    direction = _direction_from_text(alert)
    baseline = alert.get("baseline") if isinstance(alert.get("baseline"), dict) else {}
    start_price = _to_float(baseline.get("price"))
    if direction == "below" and price <= level:
        if start_price is not None and start_price <= level:
            return None
        return _price_level_trigger("price_below", price, level)
    if direction == "above" and price >= level:
        if start_price is not None and start_price >= level:
            return None
        return _price_level_trigger("price_above", price, level)
    return None


def _evaluate_candle_close(alert: dict, candles: dict) -> dict | None:
    symbol = (alert.get("symbol") or "").upper()
    tf = _normalise_tf(alert.get("timeframe") or _tf_from_text(alert.get("condition") or ""))
    if not tf:
        return None
    key = (symbol, tf)
    if key not in candles:
        candles[key] = _latest_closed_candle(symbol, tf)
    candle = candles.get(key)
    if not candle:
        return None
    created_ms = _created_at_ms(alert.get("created_at"))
    baseline = alert.get("baseline") if isinstance(alert.get("baseline"), dict) else {}
    baseline_start = _to_float(baseline.get("candle_start"))
    if baseline_start is not None and candle["start"] <= baseline_start:
        return None
    if created_ms is not None and candle["close_time"] <= created_ms:
        return None
    level = _to_float(alert.get("level")) or _level_from_text(alert.get("condition") or "")
    if level is None:
        return None
    direction = _direction_from_text(alert)
    close = candle["close"]
    if direction == "below" and close <= level:
        return _candle_trigger("candle_close_below", tf, candle, level)
    if direction == "above" and close >= level:
        return _candle_trigger("candle_close_above", tf, candle, level)
    return None


def _live_price(symbol: str) -> float | None:
    for getter in (_bybit_live_price, _okx_live_price, _binance_live_price):
        try:
            price = getter(symbol)
        except httpx.HTTPStatusError:
            continue
        if price is not None:
            return price
    return None


def _bybit_live_price(symbol: str) -> float | None:
    response = httpx.get(
        BYBIT_BASE + "/v5/market/tickers",
        params={"category": "linear", "symbol": symbol},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("retCode") not in (0, "0"):
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    rows = data.get("result", {}).get("list", []) or []
    if not rows:
        return None
    return float(rows[0]["lastPrice"])


def _binance_live_price(symbol: str) -> float | None:
    response = httpx.get(
        BINANCE_FUTURES_BASE + "/fapi/v1/ticker/price",
        params={"symbol": symbol},
        timeout=15,
    )
    if response.status_code == 400:
        return None
    response.raise_for_status()
    data = response.json()
    price = data.get("price")
    return float(price) if price is not None else None


def _okx_live_price(symbol: str) -> float | None:
    inst_id = _okx_swap_inst_id(symbol)
    if not inst_id:
        return None
    response = httpx.get(
        OKX_BASE + "/api/v5/market/ticker",
        params={"instId": inst_id},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("code") not in (0, "0"):
        return None
    rows = data.get("data") or []
    if not rows:
        return None
    last = rows[0].get("last")
    return float(last) if last is not None else None


def _latest_closed_candle(symbol: str, tf: str) -> dict | None:
    for getter in (_bybit_latest_closed_candle, _okx_latest_closed_candle, _binance_latest_closed_candle):
        try:
            candle = getter(symbol, tf)
        except httpx.HTTPStatusError:
            continue
        if candle is not None:
            return candle
    return None


def _bybit_latest_closed_candle(symbol: str, tf: str) -> dict | None:
    interval = TF_TO_BYBIT.get(tf)
    if not interval:
        return None
    response = httpx.get(
        BYBIT_BASE + "/v5/market/kline",
        params={"category": "linear", "symbol": symbol, "interval": interval, "limit": 4},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("retCode") not in (0, "0"):
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    now_ms = int(data.get("time") or datetime.utcnow().timestamp() * 1000)
    tf_ms = TF_MS[tf]
    for raw in data.get("result", {}).get("list", []) or []:
        start = int(raw[0])
        if start + tf_ms <= now_ms:
            return {
                "start": start,
                "close_time": start + tf_ms,
                "time": datetime.utcfromtimestamp(start / 1000).strftime("%Y-%m-%d %H:%M UTC"),
                "open": float(raw[1]),
                "high": float(raw[2]),
                "low": float(raw[3]),
                "close": float(raw[4]),
            }
    return None


def _binance_latest_closed_candle(symbol: str, tf: str) -> dict | None:
    interval = TF_TO_BINANCE.get(tf)
    if not interval:
        return None
    response = httpx.get(
        BINANCE_FUTURES_BASE + "/fapi/v1/klines",
        params={"symbol": symbol, "interval": interval, "limit": 4},
        timeout=15,
    )
    if response.status_code == 400:
        return None
    response.raise_for_status()
    rows = response.json() or []
    now_ms = int(time.time() * 1000)
    for raw in reversed(rows):
        start = int(raw[0])
        close_time = int(raw[6])
        if close_time < now_ms:
            return {
                "start": start,
                "close_time": close_time,
                "time": datetime.utcfromtimestamp(start / 1000).strftime("%Y-%m-%d %H:%M UTC"),
                "open": float(raw[1]),
                "high": float(raw[2]),
                "low": float(raw[3]),
                "close": float(raw[4]),
            }
    return None


def _okx_latest_closed_candle(symbol: str, tf: str) -> dict | None:
    inst_id = _okx_swap_inst_id(symbol)
    interval = TF_TO_OKX.get(tf)
    if not inst_id or not interval:
        return None
    response = httpx.get(
        OKX_BASE + "/api/v5/market/candles",
        params={"instId": inst_id, "bar": interval, "limit": 4},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("code") not in (0, "0"):
        return None
    for raw in data.get("data") or []:
        if len(raw) < 9 or raw[8] != "1":
            continue
        start = int(raw[0])
        return {
            "start": start,
            "close_time": start + TF_MS[tf],
            "time": datetime.utcfromtimestamp(start / 1000).strftime("%Y-%m-%d %H:%M UTC"),
            "open": float(raw[1]),
            "high": float(raw[2]),
            "low": float(raw[3]),
            "close": float(raw[4]),
        }
    return None


def _okx_swap_inst_id(symbol: str) -> str:
    if not symbol.endswith("USDT") or len(symbol) <= 4:
        return ""
    base = symbol[:-4]
    return f"{base}-USDT-SWAP"


def _direction_from_text(alert: dict) -> str:
    text = " ".join(str(alert.get(k) or "") for k in ("type", "condition", "label")).lower()
    if re.search(r"\b(below|under|loses|loss of|beneath)\b", text):
        return "below"
    if re.search(r"\b(above|over|reclaim|breakout)\b|break above|close through", text):
        return "above"
    direction = (alert.get("direction") or "").lower()
    if direction == "short":
        return "below"
    return "above"


def _tf_from_text(text: str) -> str:
    t = text.upper()
    if "15M" in t or "15 M" in t or "15-M" in t:
        return "15M"
    if "1H" in t or "1 H" in t or "HOURLY" in t:
        return "1H"
    if "4H" in t or "4 H" in t:
        return "4H"
    if "1D" in t or "DAILY" in t:
        return "1D"
    return ""


def _normalise_tf(value: str) -> str:
    v = (value or "").upper().replace(" ", "")
    if v in {"15", "15M", "15MIN"}:
        return "15M"
    if v in {"60", "1H"}:
        return "1H"
    if v in {"240", "4H"}:
        return "4H"
    if v in {"D", "1D", "DAILY"}:
        return "1D"
    return ""


def _level_from_text(text: str) -> float | None:
    marked = re.findall(r"\$\s*\d+(?:,\d{3})*(?:\.\d+)?", text or "")
    comma_or_decimal = re.findall(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+\.\d+\b", text or "")
    plain = re.findall(r"(?<![A-Z])\b\d+\b(?!\s*[HMDA-Z])", text or "", flags=re.IGNORECASE)
    for group in (marked, comma_or_decimal, plain):
        nums = [_parse_float(raw) for raw in group]
        nums = [n for n in nums if n is not None]
        if nums:
            return nums[-1]
    return None


def _parse_float(raw: str) -> float | None:
    try:
        return float(raw.replace("$", "").replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _created_at_ms(value: str | None) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _price_level_trigger(kind: str, price: float, level: float) -> dict:
    return {
        "kind": kind,
        "message": f"Price {price:g} reached level {level:g}.",
        "price": price,
        "level": level,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def _candle_trigger(kind: str, tf: str, candle: dict, level: float) -> dict:
    return {
        "kind": kind,
        "message": f"{tf} closed at {candle['close']:g} versus level {level:g}.",
        "timeframe": tf,
        "level": level,
        "candle": candle,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
