"""Cloud entry point for the trade alert watcher.

Run this from a scheduled cloud job. It reads active alerts from Supabase,
checks Bybit price/candle data, and sends Telegram messages for newly
triggered alerts.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys

import alert_store
import alert_watcher
import supabase_alert_store
import telegram_notifier


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the trade alert watcher once.")
    parser.add_argument("--limit", type=int, default=80, help="Maximum active alerts to check.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Check Supabase/Telegram configuration without evaluating alerts.",
    )
    args = parser.parse_args()

    if not supabase_alert_store.is_configured():
        print_json({"ok": False, "error": "Supabase is not configured."})
        return 2
    if not telegram_notifier.is_configured():
        print_json({"ok": False, "error": "Telegram is not configured."})
        return 2

    if args.smoke_test:
        alerts = alert_store.load_alerts()
        print_json(
            {
                "ok": True,
                "mode": "smoke-test",
                "alerts": len(alerts),
                "checked_at": now(),
            }
        )
        return 0

    result = alert_watcher.check_alerts(limit=args.limit)
    print_json(
        {
            "ok": not bool(result.get("errors")),
            "checked": result.get("checked", 0),
            "triggered": len(result.get("triggered", [])),
            "errors": result.get("errors", []),
            "checked_at": result.get("checked_at") or now(),
        }
    )
    return 0 if not result.get("errors") else 1


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def print_json(value: dict) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
