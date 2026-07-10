#!/usr/bin/env python3
"""Sync from Bybit — pull closed USDT-perp trades and append them to the Bybit Journal
(Google Sheet) via the Apps Script web app. De-dup is handled by the script (by trade_id),
so re-running is safe. Reads creds/URL from journal_config.json (gitignored).

Usage:
    python journal/sync_bybit.py            # sync the last ~180 days
    python journal/sync_bybit.py --dry      # print the rows, don't post
    python journal/sync_bybit.py --days 365 # custom window
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
_CFG = os.path.join(_ROOT, "journal_config.json")
_BASE = "https://api.bybit.com"


def _cfg():
    try:
        with open(_CFG) as f:
            config = json.load(f)
    except (OSError, ValueError):
        config = {}
    config["bybit_api_key"] = os.getenv("BYBIT_API_KEY") or config.get("bybit_api_key")
    config["bybit_api_secret"] = os.getenv("BYBIT_API_SECRET") or config.get("bybit_api_secret")
    config["webhook_url"] = (
        os.getenv("JOURNAL_WEBHOOK_URL")
        or os.getenv("WEBHOOK_URL")
        or config.get("webhook_url")
    )
    config["token"] = os.getenv("JOURNAL_TOKEN") or config.get("token", "")
    if os.getenv("JOURNAL_OPEN_POSITIONS_ENABLED") is not None:
        config["open_positions_enabled"] = os.getenv("JOURNAL_OPEN_POSITIONS_ENABLED", "").lower() in {
            "1", "true", "yes", "on"
        }
    return config


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


def main(argv):
    dry = "--dry" in argv
    days = 180
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])

    cfg = _cfg()
    key, secret = cfg.get("bybit_api_key"), cfg.get("bybit_api_secret")
    url, token = cfg.get("webhook_url"), cfg.get("token", "")
    if not key or not secret:
        print("Missing bybit_api_key / bybit_api_secret in journal_config.json"); return 1

    trades = fetch_closed(key, secret, days)
    rows = [to_row(t) for t in trades]
    print(f"Found {len(rows)} closed trades over the last {days} days.")

    if dry:
        for r in rows:
            print(f"  {r['entry_date']}  {r['coin']:<10} {r['long_short']:<5} "
                  f"size ${r['position_size']:<9} entry {r['entry_price']:<10} exit {r['exit_price']:<10} "
                  f"gross {r['pl_gross']:<9} fees {r['fees']:<8} net {r['pl_net']}")
        return 0

    if not url:
        print("Missing webhook_url in journal_config.json"); return 1
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
    print(f"Done. posted={posted}  skipped(dup)={dup}  failed={fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
