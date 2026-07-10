#!/usr/bin/env python3
"""Sync from Bybit — pull closed USDT-perp trades and current open positions into
the Google Sheet journal via the Apps Script web app.

Closed trades append to the Bybit Journal tab. De-dup is handled by the script
(by trade_id), so re-running is safe. Open positions rewrite the Open Positions
tab as a current snapshot while preserving manual columns for positions that are
still open. Reads creds/URL from journal_config.json (gitignored).

Usage:
    python journal/sync_bybit.py              # sync closed trades
    python journal/sync_bybit.py --dry        # print rows, don't post
    python journal/sync_bybit.py --days 365   # custom closed-trade window
    python journal/sync_bybit.py --include-open
    python journal/sync_bybit.py --closed-only
    python journal/sync_bybit.py --open-only
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import sys
import time

import httpx

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG = os.getenv("IGBY_JOURNAL_CONFIG") or os.path.join(_ROOT, "journal_config.json")
_BASE = "https://api.bybit.com"
_REQUIRED_SCRIPT_VERSION = "2026-07-10-live-cycle-journal-v1"


def _cfg():
    try:
        with open(_CFG) as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}
    config["bybit_api_key"] = os.getenv("BYBIT_API_KEY") or config.get("bybit_api_key")
    config["bybit_api_secret"] = os.getenv("BYBIT_API_SECRET") or config.get("bybit_api_secret")
    config["webhook_url"] = (
        os.getenv("JOURNAL_WEBHOOK_URL") or os.getenv("WEBHOOK_URL") or config.get("webhook_url")
    )
    config["token"] = os.getenv("JOURNAL_TOKEN") or config.get("token", "")
    enabled = os.getenv("JOURNAL_OPEN_POSITIONS_ENABLED")
    if enabled is not None:
        config["open_positions_enabled"] = enabled.strip().lower() in {"1", "true", "yes", "on"}
    return config


def _journal_features(url):
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True)
        data = r.json()
    except Exception:
        return {}
    if isinstance(data, dict):
        return data.get("features") or {}
    return {}


def _signed_get(key, secret, path, params):
    recv = "5000"
    ts = str(int(time.time() * 1000))
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    sign = hmac.new(secret.encode(), (ts + key + recv + qs).encode(), hashlib.sha256).hexdigest()
    headers = {"X-BAPI-API-KEY": key, "X-BAPI-TIMESTAMP": ts,
               "X-BAPI-RECV-WINDOW": recv, "X-BAPI-SIGN": sign}
    r = httpx.get(f"{_BASE}{path}?{qs}", headers=headers, timeout=20)
    return r.json()


def fetch_closed(key, secret, days=180):
    """Closed P&L over the last `days`, paginated in 7-day windows (Bybit's max per request)."""
    now = int(time.time() * 1000)
    week = 7 * 24 * 3600 * 1000
    seen, out = set(), []
    for i in range(days // 7 + 1):
        end = now - i * week
        d = _signed_get(key, secret, "/v5/position/closed-pnl",
                        {"category": "linear", "startTime": end - week, "endTime": end, "limit": 100})
        if d.get("retCode") != 0:
            raise RuntimeError(f"Bybit error: {d.get('retCode')} {d.get('retMsg')}")
        for t in (d.get("result") or {}).get("list") or []:
            k = t.get("orderId", "") + t.get("updatedTime", "")
            if k not in seen:
                seen.add(k)
                out.append(t)
        time.sleep(0.15)
    out.sort(key=lambda t: int(t["createdTime"]))
    return out


def _num(v):
    try:
        f = float(v)
        return f if f != 0 else None
    except (TypeError, ValueError):
        return None


def fetch_open(key, secret):
    d = _signed_get(key, secret, "/v5/position/list", {"category": "linear", "settleCoin": "USDT"})
    if d.get("retCode") != 0:
        raise RuntimeError(f"Bybit error: {d.get('retCode')} {d.get('retMsg')}")
    out = []
    for p in (d.get("result") or {}).get("list") or []:
        size = float(p.get("size") or 0)
        if size == 0:
            continue
        out.append(p)
    out.sort(key=lambda p: float(p.get("positionValue") or 0), reverse=True)
    return out


def to_row(t):
    """Bybit closed-pnl record -> Bybit Journal payload (objective columns only)."""
    open_fee = float(t.get("openFee", 0) or 0)
    close_fee = float(t.get("closeFee", 0) or 0)
    fees = open_fee + close_fee
    net = float(t["closedPnl"])            # Bybit's closed P&L is already NET of fees
    gross = net + fees                     # so price-only result = net + fees
    # closed-pnl "side" is the CLOSING side, so the position is the opposite
    long_short = "Long" if t["side"] == "Sell" else "Short"
    return {
        "action": "bybit",
        "opened_ts": int(t["createdTime"]),
        "closed_ts": int(t["updatedTime"]),
        "trade_id": t.get("orderId", "") + t.get("updatedTime", ""),
        "entry_date": datetime.datetime.fromtimestamp(int(t["createdTime"]) / 1000).strftime("%Y-%m-%d"),
        "coin": t["symbol"],
        "long_short": long_short,
        "position_size": round(float(t["cumEntryValue"]), 2),
        "entry_price": float(t["avgEntryPrice"]),
        "exit_price": float(t["avgExitPrice"]),
        "pl_gross": round(gross, 4),
        "fees": round(fees, 4),
        "pl_net": round(net, 4),
    }


def open_to_row(p):
    side = p.get("side") or ""
    direction = "Long" if side == "Buy" else "Short" if side == "Sell" else side
    created = int(p.get("createdTime") or 0)
    opened_at = (
        datetime.datetime.fromtimestamp(created / 1000).strftime("%Y-%m-%d %H:%M:%S")
        if created else ""
    )
    entry = _num(p.get("avgPrice"))
    mark = _num(p.get("markPrice"))
    tp = _num(p.get("takeProfit"))
    sl = _num(p.get("stopLoss"))
    live_r = target_r = None
    if entry and sl:
        risk = abs(entry - sl)
        if risk > 0 and mark:
            live_r = (mark - entry) / risk if direction == "Long" else (entry - mark) / risk
        if risk > 0 and tp:
            target_r = abs(tp - entry) / risk
    position_id = "|".join([
        p.get("symbol") or "",
        side,
        str(p.get("positionIdx") or ""),
        str(p.get("createdTime") or ""),
    ])
    notional = float(p.get("positionValue") or 0)
    lev = float(p.get("leverage") or 0)
    upnl = float(p.get("unrealisedPnl") or 0)
    margin = notional / lev if lev else 0
    return {
        "position_id": position_id,
        "opened_ts": created,
        "entry_date": datetime.datetime.fromtimestamp(created / 1000).strftime("%Y-%m-%d") if created else "",
        "opened_at": opened_at,
        "coin": p.get("symbol") or "",
        "long_short": direction,
        "position_size": round(float(p.get("positionValue") or 0), 2),
        "notional": round(notional, 2),
        "leverage": lev,
        "entry_price": entry,
        "mark_price": mark,
        "liq_price": _num(p.get("liqPrice")),
        "take_profit": tp,
        "stop_loss": sl,
        "unrealized_pnl": round(upnl, 4),
        "unrealized_pct": round(upnl / margin, 6) if margin else "",
        "live_r": round(live_r, 2) if live_r is not None else "",
        "target_r": round(target_r, 2) if target_r is not None else "",
        "status": "Open",
    }


def main(argv):
    dry = "--dry" in argv
    closed_only = "--closed-only" in argv
    open_only = "--open-only" in argv
    include_open_arg = "--include-open" in argv
    days = 180
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])

    cfg = _cfg()
    key, secret = cfg.get("bybit_api_key"), cfg.get("bybit_api_secret")
    url, token = cfg.get("webhook_url"), cfg.get("token", "")
    include_open = bool(cfg.get("open_positions_enabled")) or include_open_arg or open_only
    if not key or not secret:
        print("Missing bybit_api_key / bybit_api_secret in journal_config.json"); return 1

    if closed_only and open_only:
        print("Use only one of --closed-only or --open-only"); return 1

    rows = []
    open_rows = []
    if not open_only:
        trades = fetch_closed(key, secret, days)
        rows = [to_row(t) for t in trades]
        print(f"Found {len(rows)} closed trades over the last {days} days.")
    if include_open and not closed_only:
        open_positions = fetch_open(key, secret)
        open_rows = [open_to_row(p) for p in open_positions]
        print(f"Found {len(open_rows)} open positions.")
    elif not closed_only:
        print("Open-position sync is disabled until the Google Apps Script is redeployed.")

    if dry:
        if rows:
            print("\nClosed trades:")
            for r in rows:
                print(f"  {r['entry_date']}  {r['coin']:<10} {r['long_short']:<5} "
                      f"size ${r['position_size']:<9} entry {r['entry_price']:<10} exit {r['exit_price']:<10} "
                      f"gross {r['pl_gross']:<9} fees {r['fees']:<8} net {r['pl_net']}")
        if open_rows:
            print("\nOpen positions:")
            for r in open_rows:
                print(f"  {r['coin']:<10} {r['long_short']:<5} notional ${r['notional']:<9} "
                      f"entry {r['entry_price']:<10} mark {r['mark_price']:<10} "
                      f"uPnL {r['unrealized_pnl']:<9} liveR {r['live_r']}")
        return 0

    if not url:
        print("Missing webhook_url in journal_config.json"); return 1
    features = _journal_features(url)
    if features.get("script_version") != _REQUIRED_SCRIPT_VERSION:
        print("Google Apps Script is not updated for journal sync yet. Redeploy journal/apps_script.gs first.")
        return 1
    if include_open and not features.get("open_positions"):
        print("Google Apps Script is not updated for open-position sync yet. Redeploy journal/apps_script.gs first.")
        return 1
    posted = dup = fail = 0
    for r in rows:
        if token:
            r = {**r, "token": token}
        try:
            resp = httpx.post(url, json=r, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            b = resp.json()
            if b.get("dup"):
                dup += 1
            elif b.get("ok"):
                posted += 1
            else:
                fail += 1
                print("  rejected:", b)
        except Exception as e:
            fail += 1
            print("  error:", repr(e))
    open_synced = False
    if open_rows:
        payload = {"action": "open_positions", "rows": open_rows}
        if token:
            payload["token"] = token
        try:
            resp = httpx.post(url, json=payload, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            b = resp.json()
            if b.get("ok"):
                open_synced = True
            else:
                fail += 1
                print("  open positions rejected:", b)
        except Exception as e:
            fail += 1
            print("  open positions error:", repr(e))
        cycle_payload = {"action": "cycle_open_positions", "rows": open_rows}
        if token:
            cycle_payload["token"] = token
        try:
            resp = httpx.post(url, json=cycle_payload, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            b = resp.json()
            if not b.get("ok"):
                fail += 1
                print("  cycle journal open positions rejected:", b)
        except Exception as e:
            fail += 1
            print("  cycle journal open positions error:", repr(e))
    elif include_open and not closed_only:
        payload = {"action": "open_positions", "rows": []}
        if token:
            payload["token"] = token
        try:
            resp = httpx.post(url, json=payload, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            b = resp.json()
            open_synced = bool(b.get("ok"))
        except Exception as e:
            fail += 1
            print("  open positions clear error:", repr(e))
    print(f"Done. closed_posted={posted}  closed_skipped(dup)={dup}  open_synced={open_synced}  failed={fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
