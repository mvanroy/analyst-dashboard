"""Bybit private-API helpers (read-only). Pulls closed USDT-perp trades for the journal +
Trade Analytics. Creds live in journal_config.json (gitignored). Read-only key: it can see
trade history but cannot trade, transfer, or withdraw.
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


def _creds():
    try:
        with open(_CFG) as f:
            c = json.load(f)
        return (c.get("bybit_api_key") or "").strip(), (c.get("bybit_api_secret") or "").strip()
    except Exception:
        return "", ""


def have_creds() -> bool:
    k, s = _creds()
    return bool(k and s)


def sheet_url() -> str:
    """The journal Google Sheet URL (for the Launch Journal button), or '' if not set."""
    try:
        with open(_CFG) as f:
            return (json.load(f).get("journal_sheet_url") or "").strip()
    except Exception:
        return ""


def webhook_url() -> str:
    """The Apps Script web-app /exec URL (for reading the journal via doGet), or ''."""
    try:
        with open(_CFG) as f:
            return (json.load(f).get("webhook_url") or "").strip()
    except Exception:
        return ""


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

    Each trade: {ts, date(datetime), coin, direction, size, entry, exit, gross, fees, net}.
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
        out.append({
            "ts": int(t["createdTime"]),
            "date": datetime.datetime.fromtimestamp(int(t["createdTime"]) / 1000),
            "coin": t["symbol"],
            "direction": "Long" if t["side"] == "Sell" else "Short",
            "size": round(float(t["cumEntryValue"]), 2),
            "entry": float(t["avgEntryPrice"]),
            "exit": float(t["avgExitPrice"]),
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

    def _num(v):
        try:
            f = float(v)
            return f if f != 0 else None
        except (TypeError, ValueError):
            return None

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
        tp, sl, liq = _num(p.get("takeProfit")), _num(p.get("stopLoss")), _num(p.get("liqPrice"))

        live_r = target_r = None
        if sl and entry:
            risk = abs(entry - sl)
            if risk > 0:
                live_r = (mark - entry) / risk if direction == "Long" else (entry - mark) / risk
                if tp:
                    target_r = abs(tp - entry) / risk

        created = int(p.get("createdTime") or 0)
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
            "opened": datetime.datetime.fromtimestamp(created / 1000) if created else None,
            "age_h": round((now - created / 1000) / 3600, 1) if created else None,
        })
    out.sort(key=lambda r: -(r["notional"] or 0))
    return out
