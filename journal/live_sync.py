#!/usr/bin/env python3
"""Continuously synchronize Bybit trades into the cycle journal."""
import os
import subprocess
import sys
import time


def main():
    if os.getenv("JOURNAL_SYNC_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        print("journal sync disabled for this environment", flush=True)
        return
    interval = max(30, int(os.getenv("JOURNAL_SYNC_INTERVAL_SECONDS", "60")))
    while True:
        result = subprocess.run(
            [sys.executable, "journal/sync_bybit.py", "--days", "7", "--recent-hours", "24", "--include-open"],
            check=False,
        )
        if result.returncode:
            print(f"journal sync failed with exit code {result.returncode}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
