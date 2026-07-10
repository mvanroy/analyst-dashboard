"""Bybit private-API helpers (read-only). Pulls closed USDT-perp trades for the journal +
Trade Analytics. Credentials can come from deployment environment variables or the local
journal_config.json file. Read-only keys can see trade history but cannot trade, transfer,
or withdraw.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import time

import httpx

_ROOT = os.path.dirname(os.path.abspath(__file__))
_CFG = os.path.join(_ROOT, "journal_config.json")
_BASE = "https://api.bybit.com"


def _env_value(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _local_config() -> dict:
    try:
        with open(_CFG) as f:
            return json.load(f)
    except Exception:
        return {}


def _creds():
    key = _env_value("BYBIT_API_KEY", "bybit_api_key")
    secret = _env_value("BYBIT_API_SECRET", "bybit_api_secret")
    if key and secret:
        return key, secret

    c = _local_config()
    return (c.get("bybit_api_key") or "").strip(), (c.get("bybit_api_secret") or "").strip()


def have_creds() -> bool:
    k, s = _creds()
    return bool(k and s)


def _num_or_none(v):
    try:
        if v in ("", None):
            return None
        f = float(v)
        return f if f != 0 else None
    except (TypeError, ValueError):
        return None


def _num_or_zero(v):
    try:
        if v in ("", None):
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _rate_to_decimal(v):
    """Bybit risk-limit margin rates may arrive as decimals or percentages."""
    n = _num_or_zero(v)
    return n / 100.0 if n > 0.2 else n


def _public_get(path, params):
    data = httpx.get(f"{_BASE}{path}", params=params, timeout=20).json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    return data


def sheet_url() -> str:
    """The journal Google Sheet URL (for the Launch Journal button), or '' if not set."""
    return _env_value("JOURNAL_SHEET_URL", "journal_sheet_url") or (
        _local_config().get("journal_sheet_url") or ""
    ).strip()


def webhook_url() -> str:
    """The Apps Script web-app /exec URL (for reading the journal via doGet), or ''."""
    return _env_value("JOURNAL_WEBHOOK_URL", "WEBHOOK_URL", "webhook_url") or (
        _local_config().get("webhook_url") or ""
    ).strip()


def fetch_symbol_trade_terms(symbol: str):
    """Return public Bybit USDT-perp trading terms for a symbol.

    This is the pre-trade "symbol DNA" used by the calculator. It is public data:
    precision, tick/quantity steps, min order rules, leverage limits, funding context,
    and the first risk tier's margin rates. The calculator still labels liquidation as
    estimated because Bybit's final liquidation can depend on account state.
    """
    sym = (symbol or "").upper().replace("/", "").replace("-", "")
    if sym and not sym.endswith("USDT"):
        sym += "USDT"
    if not sym:
        return {}

    inst = _public_get(
        "/v5/market/instruments-info",
        {"category": "linear", "symbol": sym},
    )
    instruments = (inst.get("result") or {}).get("list") or []
    if not instruments:
        return {}
    item = instruments[0]
    lev = item.get("leverageFilter") or {}
    price = item.get("priceFilter") or {}
    lot = item.get("lotSizeFilter") or {}

    terms = {
        "symbol": item.get("symbol") or sym,
        "status": item.get("status"),
        "contract_type": item.get("contractType"),
        "max_leverage": _num_or_zero(lev.get("maxLeverage")) or 100.0,
        "min_leverage": _num_or_zero(lev.get("minLeverage")) or 1.0,
        "leverage_step": _num_or_zero(lev.get("leverageStep")) or 0.01,
        "tick_size": _num_or_zero(price.get("tickSize")) or 0.0001,
        "min_price": _num_or_zero(price.get("minPrice")),
        "max_price": _num_or_zero(price.get("maxPrice")),
        "qty_step": _num_or_zero(lot.get("qtyStep")) or 0.001,
        "min_order_qty": _num_or_zero(lot.get("minOrderQty")),
        "max_order_qty": _num_or_zero(lot.get("maxOrderQty")),
        "min_notional": _num_or_zero(lot.get("minNotionalValue")),
        "max_order_qty_market": _num_or_zero(lot.get("maxMktOrderQty")),
        "funding_interval_minutes": _num_or_zero(item.get("fundingInterval")),
        "risk_parameters": item.get("riskParameters") or {},
    }

    try:
        ticker = fetch_market_ticker(terms["symbol"])
    except Exception:
        ticker = {}
    terms.update(
        {
            "last_price": ticker.get("last_price"),
            "price_24h_pct": ticker.get("price_24h_pct"),
            "funding_rate_pct": ticker.get("funding_rate"),
        }
    )

    try:
        risk = _public_get(
            "/v5/market/risk-limit",
            {"category": "linear", "symbol": terms["symbol"]},
        )
        tiers = (risk.get("result") or {}).get("list") or []
    except Exception:
        tiers = []
    cleaned_tiers = []
    for row in tiers:
        cleaned_tiers.append(
            {
                "id": row.get("id") or row.get("riskId"),
                "risk_limit_value": _num_or_zero(row.get("riskLimitValue")),
                "initial_margin_rate": _rate_to_decimal(row.get("initialMargin")),
                "maintenance_margin_rate": _rate_to_decimal(row.get("maintenanceMargin")),
                "max_leverage": _num_or_zero(row.get("maxLeverage")),
                "maintenance_margin_deduction": _num_or_zero(row.get("mmDeduction")),
            }
        )
    cleaned_tiers.sort(key=lambda r: r.get("risk_limit_value") or 0)
    terms["risk_tiers"] = cleaned_tiers
    first_tier = cleaned_tiers[0] if cleaned_tiers else {}
    if first_tier:
        terms["initial_margin_rate"] = first_tier.get("initial_margin_rate") or (1 / terms["max_leverage"])
        terms["maintenance_margin_rate"] = first_tier.get("maintenance_margin_rate") or 0.005
        if first_tier.get("max_leverage"):
            terms["max_leverage"] = min(terms["max_leverage"], first_tier["max_leverage"])
    else:
        terms["initial_margin_rate"] = 1 / terms["max_leverage"] if terms["max_leverage"] else 0.01
        terms["maintenance_margin_rate"] = 0.005
    return terms


def journal_rows():
    """GET the 'Bybit Journal' rows from the Apps Script web app (doGet) as a list of dicts
    keyed by the journal payload keys (setup_type, pl_net, long_short, coin, win_loss, ...).

    Returns [] if no webhook is configured or the request fails. This is how the manual
    judgment columns (Set Up Type etc.) reach Trade Analytics — Bybit's API has no notion
    of them; they live only in the Sheet.
    """
    url = webhook_url()
    if not url:
        return []
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True)
        data = r.json()
    except Exception:
        return []
    if isinstance(data, dict) and data.get("ok"):
        return data.get("rows") or []
    return []


def _signed_get(key, secret, path, params):
    recv = "5000"
    ts = str(int(time.time() * 1000))
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    sign = hmac.new(secret.encode(), (ts + key + recv + qs).encode(), hashlib.sha256).hexdigest()
    headers = {"X-BAPI-API-KEY": key, "X-BAPI-TIMESTAMP": ts,
               "X-BAPI-RECV-WINDOW": recv, "X-BAPI-SIGN": sign}
    return httpx.get(f"{_BASE}{path}?{qs}", headers=headers, timeout=20).json()


def fetch_closed_trades(days: int = 180):
    """Return a list of normalised closed trades (newest last), or [] if no creds/none found.

    Each trade: {trade_id, ts, date(datetime), opened_ts, closed_ts, duration_min,
    coin, direction, size, entry, exit, gross, fees, net}.
    Bybit's closedPnl is already NET of fees; gross = net + fees. The closed-pnl 'side' is the
    CLOSING side, so the position direction is the opposite.
    """
    key, secret = _creds()
    if not (key and secret):
        return []
    now = int(time.time() * 1000)
    week = 7 * 24 * 3600 * 1000
    seen, raw = set(), []
    for i in range(days // 7 + 1):
        end = now - i * week
        d = _signed_get(key, secret, "/v5/position/closed-pnl",
                        {"category": "linear", "startTime": end - week, "endTime": end, "limit": 100})
        if d.get("retCode") != 0:
            raise RuntimeError(f"Bybit error {d.get('retCode')}: {d.get('retMsg')}")
        for t in (d.get("result") or {}).get("list") or []:
            k = t.get("orderId", "") + t.get("updatedTime", "")
            if k not in seen:
                seen.add(k)
                raw.append(t)
        time.sleep(0.12)

    out = []
    for t in raw:
        fees = float(t.get("openFee", 0) or 0) + float(t.get("closeFee", 0) or 0)
        net = float(t["closedPnl"])
        opened_ts = int(t.get("createdTime") or 0)
        closed_ts = int(t.get("updatedTime") or opened_ts or 0)
        duration_min = max(0, round((closed_ts - opened_ts) / 60000)) if opened_ts and closed_ts else None
        trade_id = t.get("orderId", "") + t.get("updatedTime", "")
        stop_loss = _num_or_none(t.get("stopLoss") or t.get("slPrice") or t.get("triggerPrice"))
        take_profit = _num_or_none(t.get("takeProfit") or t.get("tpPrice"))
        out.append({
            "trade_id": trade_id,
            "ts": opened_ts,
            "date": datetime.datetime.fromtimestamp(opened_ts / 1000),
            "opened_ts": opened_ts,
            "closed_ts": closed_ts,
            "duration_min": duration_min,
            "coin": t["symbol"],
            "direction": "Long" if t["side"] == "Sell" else "Short",
            "size": round(float(t["cumEntryValue"]), 2),
            "entry": float(t["avgEntryPrice"]),
            "exit": float(t["avgExitPrice"]),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "gross": round(net + fees, 4),
            "fees": round(fees, 4),
            "net": round(net, 4),
        })
    out.sort(key=lambda r: r["ts"])
    return out


def fetch_open_positions():
    """Return LIVE open USDT-perp positions (in-flight trades), or [] if no creds/none open.

    Read-only: hits /v5/position/list. Unlike closed-pnl, the 'side' here IS the position
    direction (Buy = Long). uPnL %, R-multiple and TP/SL distances are derived locally.

    Each: {coin, direction, size, notional, leverage, entry, mark, upnl, upnl_pct, liq,
           tp, sl, live_r, target_r, to_tp, to_sl, opened(datetime|None), age_h}.
    """
    key, secret = _creds()
    if not (key and secret):
        return []
    d = _signed_get(key, secret, "/v5/position/list",
                    {"category": "linear", "settleCoin": "USDT"})
    if d.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {d.get('retCode')}: {d.get('retMsg')}")

    now = time.time()
    out = []
    for p in (d.get("result") or {}).get("list") or []:
        size = float(p.get("size") or 0)
        if size == 0:
            continue
        direction = "Long" if p.get("side") == "Buy" else "Short"
        entry = float(p.get("avgPrice") or 0)
        mark = float(p.get("markPrice") or 0)
        notional = float(p.get("positionValue") or 0)
        lev = float(p.get("leverage") or 0)
        upnl = float(p.get("unrealisedPnl") or 0)
        margin = notional / lev if lev else 0.0
        tp, sl, liq = _num_or_none(p.get("takeProfit")), _num_or_none(p.get("stopLoss")), _num_or_none(p.get("liqPrice"))

        live_r = target_r = None
        if sl and entry:
            risk = abs(entry - sl)
            if risk > 0:
                live_r = (mark - entry) / risk if direction == "Long" else (entry - mark) / risk
                if tp:
                    target_r = abs(tp - entry) / risk

        # createdTime is the first-ever position record for this symbol, so it
        # can predate the current trade. openTime is the active position's
        # actual opening timestamp; retain createdTime only for older payloads.
        opened = int(p.get("openTime") or p.get("createdTime") or 0)
        out.append({
            "coin": p.get("symbol"),
            "direction": direction,
            "size": size,
            "notional": round(notional, 2),
            "leverage": lev,
            "entry": entry,
            "mark": mark,
            "upnl": round(upnl, 4),
            "upnl_pct": round(upnl / margin * 100, 2) if margin else 0.0,
            "liq": liq,
            "tp": tp,
            "sl": sl,
            "live_r": round(live_r, 2) if live_r is not None else None,
            "target_r": round(target_r, 2) if target_r is not None else None,
            "to_tp": round((tp - mark) / mark * 100, 2) if (tp and mark) else None,
            "to_sl": round((sl - mark) / mark * 100, 2) if (sl and mark) else None,
            "opened": datetime.datetime.fromtimestamp(opened / 1000) if opened else None,
            "age_h": round((now - opened / 1000) / 3600, 1) if opened else None,
        })
    out.sort(key=lambda r: -(r["notional"] or 0))
    return out


def fetch_account_summary():
    """Return read-only Bybit account equity/margin summary, or {} if unavailable.

    Uses /v5/account/wallet-balance. The app only needs aggregate balances for display
    percentages; position data still comes from fetch_open_positions().
    """
    key, secret = _creds()
    if not (key and secret):
        return {}
    d = _signed_get(key, secret, "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
    if d.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {d.get('retCode')}: {d.get('retMsg')}")
    accounts = (d.get("result") or {}).get("list") or []
    if not accounts:
        return {}
    account = accounts[0]
    equity = _num_or_none(account.get("totalEquity"))
    margin = _num_or_none(account.get("totalInitialMargin"))
    available = _num_or_none(account.get("totalAvailableBalance"))
    wallet = _num_or_none(account.get("totalWalletBalance"))
    if margin is None:
        margin = 0.0
        for coin in account.get("coin") or []:
            margin += _num_or_none(coin.get("totalPositionIM")) or 0.0
            margin += _num_or_none(coin.get("totalOrderIM")) or 0.0
    if available is None and equity is not None and margin is not None:
        available = max(0.0, equity - margin)
    return {
        "equity": equity,
        "margin_used": margin,
        "available_margin": available,
        "wallet_balance": wallet,
    }


def fetch_btc_daily(days: int = 180):
    """Public Bybit daily BTCUSDT candles for benchmark overlays."""
    now = int(time.time() * 1000)
    start = now - int(days * 1.2) * 24 * 3600 * 1000
    params = {
        "category": "linear",
        "symbol": "BTCUSDT",
        "interval": "D",
        "start": start,
        "end": now,
        "limit": min(1000, max(30, int(days * 1.2))),
    }
    data = httpx.get(f"{_BASE}/v5/market/kline", params=params, timeout=20).json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    rows = []
    for item in (data.get("result") or {}).get("list") or []:
        rows.append(
            {
                "date": datetime.datetime.fromtimestamp(int(item[0]) / 1000),
                "btc_close": float(item[4]),
            }
        )
    rows.sort(key=lambda r: r["date"])
    return rows[-days:]


def fetch_market_klines(symbol: str, interval: str = "60", limit: int = 80):
    """Public Bybit candles for live portfolio risk controls.

    interval follows Bybit values: "15", "60", "240", "D", etc.
    Returns oldest-first rows with open/high/low/close/volume.
    """
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    data = httpx.get(f"{_BASE}/v5/market/kline", params=params, timeout=20).json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    rows = []
    for item in (data.get("result") or {}).get("list") or []:
        rows.append(
            {
                "date": datetime.datetime.fromtimestamp(int(item[0]) / 1000),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
            }
        )
    rows.sort(key=lambda r: r["date"])
    return rows


def fetch_market_ticker(symbol: str):
    """Public Bybit linear ticker for live price, 24h move, and funding rate."""
    params = {
        "category": "linear",
        "symbol": symbol,
    }
    data = httpx.get(f"{_BASE}/v5/market/tickers", params=params, timeout=20).json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    rows = (data.get("result") or {}).get("list") or []
    if not rows:
        return {}
    row = rows[0]
    return {
        "symbol": row.get("symbol"),
        "last_price": _num_or_none(row.get("lastPrice")),
        "price_24h_pct": (_num_or_none(row.get("price24hPcnt")) or 0) * 100,
        "funding_rate": (_num_or_none(row.get("fundingRate")) or 0) * 100,
    }
