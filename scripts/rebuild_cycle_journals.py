#!/usr/bin/env python3
"""Rebuild the two workbook cycle tabs from canonical Bybit facts and saved notes.

The script previews by default. Pass --apply only after the cycle-aware Apps Script
has been redeployed. It takes a fresh JSON backup through the workbook webhook
before replacing any data rows.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "trading_cycles" / "cycle_1.json"
NOTES_BACKUP = ROOT / "data" / "journal_backups" / "bybit_journal_20260710T044827Z.json"
BACKUP_DIR = ROOT / "data" / "journal_backups"
CUTOFF_MS = 1783666800000
SCRIPT_VERSION = "2026-07-10-trading-cycles-v2"
MANUAL_FIELDS = (
    "market_bias", "setup_type", "entry_rationale", "strategy",
    "setup_grade", "risk_reward", "screenshot", "cut_reason", "cut_result",
)
LEGACY = (
    ("EDENUSDT", "Long", 1783647072852),
    ("XCNUSDT", "Long", 1783647192431),
)


def _load_sync():
    path = ROOT / "journal" / "sync_bybit.py"
    spec = importlib.util.spec_from_file_location("igby_sync_bybit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _legacy(row: dict) -> bool:
    opened = int(row.get("opened_ts") or 0)
    return any(
        row.get("coin") == coin and row.get("long_short") == side and abs(opened - ts) <= 120_000
        for coin, side, ts in LEGACY
    )


def _archive_row(trade: dict) -> dict:
    return {
        "trade_id": str(trade["trade_id"]),
        "opened_ts": int(trade["opened_ts"]),
        "closed_ts": int(trade["closed_ts"]),
        "entry_date": str(trade["date"])[:10],
        "coin": trade["coin"],
        "long_short": trade["direction"],
        "position_size": trade["size"],
        "entry_price": trade["entry"],
        "exit_price": trade["exit"],
        "pl_gross": trade["gross"],
        "fees": trade["fees"],
        "pl_net": trade["net"],
    }


def _close(a, b, tolerance=1e-6):
    try:
        return math.isclose(float(a), float(b), rel_tol=tolerance, abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def _note_match(row: dict, saved: list[dict]) -> dict | None:
    for note in saved:
        if (
            str(note.get("coin") or "") == str(row.get("coin") or "")
            and str(note.get("long_short") or "") == str(row.get("long_short") or "")
            and _close(note.get("position_size"), row.get("position_size"), 1e-5)
            and _close(note.get("entry_price"), row.get("entry_price"), 1e-5)
            and _close(note.get("exit_price"), row.get("exit_price"), 1e-5)
            and _close(note.get("pl_net"), row.get("pl_net"), 1e-4)
        ):
            return note
    return None


def _attach_notes(rows: list[dict], saved: list[dict]) -> int:
    matched = 0
    for row in rows:
        note = _note_match(row, saved)
        if not note:
            continue
        matched += 1
        for field in MANUAL_FIELDS:
            row[field] = note.get(field, "")
    return matched


def _post(url: str, token: str, payload: dict) -> dict:
    if token:
        payload = {**payload, "token": token}
    response = httpx.post(url, json=payload, timeout=60, follow_redirects=True)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="replace the two workbook cycle tabs")
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    sync = _load_sync()
    cfg = sync._cfg()
    key, secret = cfg.get("bybit_api_key"), cfg.get("bybit_api_secret")
    url, token = cfg.get("webhook_url"), cfg.get("token", "")
    if not key or not secret:
        raise SystemExit("Missing Bybit credentials")

    archive = json.loads(ARCHIVE.read_text())
    saved = json.loads(NOTES_BACKUP.read_text())["rows"]
    cycle1_by_id = {str(t["trade_id"]): _archive_row(t) for t in archive["closed_trades"]}

    live = [sync.to_row(t) for t in sync.fetch_closed(key, secret, args.days)]
    cycle2 = []
    for row in live:
        if int(row["closed_ts"]) < CUTOFF_MS or _legacy(row):
            cycle1_by_id.setdefault(str(row["trade_id"]), row)
        else:
            cycle2.append(row)
    cycle1 = sorted(cycle1_by_id.values(), key=lambda r: (int(r["closed_ts"]), str(r["trade_id"])))
    cycle2.sort(key=lambda r: (int(r["closed_ts"]), str(r["trade_id"])))
    notes_matched = _attach_notes(cycle1, saved)

    print(f"Cycle 1 canonical rows: {len(cycle1)} ({notes_matched} saved-note rows matched)")
    print(f"Cycle 2 rows since cutoff: {len(cycle2)}")
    if not args.apply:
        print("Preview only. Redeploy journal/apps_script.gs, then rerun with --apply.")
        return 0
    if not url:
        raise SystemExit("Missing journal webhook URL")

    current = httpx.get(url, params={"cycle": 2}, timeout=30, follow_redirects=True).json()
    if (current.get("features") or {}).get("script_version") != SCRIPT_VERSION:
        raise SystemExit("Cycle-aware Apps Script is not deployed yet; no workbook rows were changed.")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fresh = {}
    for cycle in (1, 2):
        fresh[str(cycle)] = httpx.get(
            url, params={"cycle": cycle}, timeout=30, follow_redirects=True
        ).json()
    backup_path = BACKUP_DIR / f"cycle_tabs_before_rebuild_{stamp}.json"
    backup_path.write_text(json.dumps(fresh, indent=2, default=str) + "\n")

    result1 = _post(url, token, {"action": "replace_cycle", "cycle": 1, "rows": cycle1})
    result2 = _post(url, token, {"action": "replace_cycle", "cycle": 2, "rows": cycle2})
    print(f"Workbook backup: {backup_path}")
    print(f"Cycle 1 replaced: {result1['replaced_rows']} rows")
    print(f"Cycle 2 replaced: {result2['replaced_rows']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
