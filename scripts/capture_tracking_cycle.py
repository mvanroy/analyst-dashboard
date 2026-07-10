#!/usr/bin/env python3
"""Capture an immutable trading-cycle archive and Google journal backup."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bybit


def serialise(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    raise TypeError(f"Unsupported value: {type(value).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff-utc", required=True)
    parser.add_argument("--expected-open", type=int, default=2)
    args = parser.parse_args()

    cutoff = dt.datetime.fromisoformat(args.cutoff_utc.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        raise SystemExit("--cutoff-utc must include a timezone")
    cutoff_ms = int(cutoff.timestamp() * 1000)

    closed = bybit.fetch_closed_trades(365)
    open_positions = bybit.fetch_open_positions()
    journal_rows = bybit.journal_rows()
    if len(open_positions) != args.expected_open:
        raise SystemExit(
            f"Refusing capture: expected {args.expected_open} open positions, found {len(open_positions)}"
        )

    legacy_open = []
    for position in open_positions:
        opened = position.get("opened")
        legacy_open.append(
            {
                "coin": position.get("coin"),
                "direction": position.get("direction"),
                "opened_ts": int(opened.timestamp() * 1000) if opened else 0,
                "opened_at": opened.isoformat() if opened else "",
            }
        )

    archive = {
        "contract": "igby-trading-cycle/v1",
        "cycle": {
            "id": "cycle-1",
            "name": "Cycle 1",
            "status": "archived_pending",
            "cutoff_at_utc": cutoff.astimezone(dt.timezone.utc).isoformat(),
            "cutoff_ts": cutoff_ms,
            "closed_trade_count_at_cutoff": len(closed),
            "pending_open_count": len(legacy_open),
        },
        "legacy_open_positions": legacy_open,
        "closed_trades": closed,
    }

    cycles_dir = ROOT / "data" / "trading_cycles"
    backups_dir = ROOT / "data" / "journal_backups"
    cycles_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    (cycles_dir / "cycle_1.json").write_text(
        json.dumps(archive, indent=2, default=serialise) + "\n"
    )
    backup_name = f"bybit_journal_{cutoff.strftime('%Y%m%dT%H%M%SZ')}.json"
    (backups_dir / backup_name).write_text(
        json.dumps(
            {
                "contract": "igby-journal-backup/v1",
                "captured_at_utc": cutoff.astimezone(dt.timezone.utc).isoformat(),
                "row_count": len(journal_rows),
                "rows": journal_rows,
            },
            indent=2,
            default=serialise,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "closed_trades": len(closed),
                "legacy_open_positions": legacy_open,
                "journal_rows_backed_up": len(journal_rows),
                "archive": str(cycles_dir / "cycle_1.json"),
                "journal_backup": str(backups_dir / backup_name),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
