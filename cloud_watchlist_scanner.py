"""Cloud worker for Watch List scanner Telegram updates.

This is separate from the old Trade Setup saved-alert watcher. It runs the
watchlist scanner, compares against prior scanner state, and sends Telegram
messages only when scanner state changes are detected.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
import time

import telegram_notifier
from watchlist_engine import cron_scan
from watchlist_engine.config import STATE_FILE


DEFAULT_INTERVAL_SECONDS = 300


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Watch List scanner Telegram worker.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("SCANNER_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))),
        help="Seconds between scanner cycles in loop mode.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Check Telegram/state configuration without scanning exchanges.",
    )
    args = parser.parse_args()

    telegram = scanner_telegram_credentials()
    if not telegram["configured"]:
        print_json(
            {
                "ok": False,
                "error": "Scanner Telegram is not configured.",
                "checked_at": now(),
            }
        )
        return 2

    if args.smoke_test:
        print_json(
            {
                "ok": True,
                "mode": "smoke-test",
                "telegram_source": telegram["source"],
                "state_file": STATE_FILE,
                "checked_at": now(),
            }
        )
        return 0

    if args.loop:
        return run_loop(interval=max(args.interval, 30))
    return run_once()


def run_loop(interval: int) -> int:
    print_json(
        {
            "ok": True,
            "mode": "watchlist-scanner-loop",
            "interval": interval,
            "state_file": STATE_FILE,
            "started_at": now(),
        }
    )
    while True:
        try:
            run_once()
        except Exception as exc:
            print_json({"ok": False, "error": str(exc), "checked_at": now()})
        sys.stdout.flush()
        time.sleep(interval)


def run_once() -> int:
    telegram = scanner_telegram_credentials()
    messages = cron_scan.scan_messages()
    sent = []
    errors = []
    for message in messages:
        try:
            result = telegram_notifier.send_message(
                message,
                token=telegram["token"],
                chat_id=telegram["chat_id"],
                parse_mode="Markdown",
            )
            sent.append(result)
        except Exception as exc:
            errors.append(str(exc))

    print_json(
        {
            "ok": not errors,
            "messages": len(messages),
            "sent": len(sent),
            "errors": errors,
            "telegram_source": telegram["source"],
            "state_file": STATE_FILE,
            "checked_at": now(),
        }
    )
    return 0 if not errors else 1


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def scanner_telegram_credentials() -> dict:
    """Return scanner-specific Telegram credentials without exposing secrets."""
    sources = (
        ("watchlist", "WATCHLIST_TELEGRAM_BOT_TOKEN", "WATCHLIST_TELEGRAM_CHAT_ID"),
        ("jchelper", "JCHELPER_TELEGRAM_BOT_TOKEN", "JCHELPER_TELEGRAM_CHAT_ID"),
        ("default", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"),
    )
    for source, token_key, chat_key in sources:
        token = (os.getenv(token_key) or "").strip()
        chat_id = (os.getenv(chat_key) or "").strip()
        if token and chat_id:
            return {
                "configured": True,
                "source": source,
                "token": token,
                "chat_id": chat_id,
            }

    return {
        "configured": telegram_notifier.is_configured(),
        "source": "default-secrets-file",
        "token": None,
        "chat_id": None,
    }


def print_json(value: dict) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
