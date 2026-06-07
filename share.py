"""Bridge between Claude's scans and the dashboard.

When Claude runs a scan it calls write_snapshot(), which drops a JSON file the
Streamlit app reads and renders in its "Claude's latest scan" panel. This is how
Claude's work shows up live on the dashboard you're watching.
"""
from __future__ import annotations

import json
import os
import time

import scanner

SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude_snapshot.json")


def write_snapshot(note=""):
    df = scanner.scan()
    payload = {
        "ts": time.time(),
        "note": note,
        "rows": df.to_dict(orient="records"),
    }
    tmp = SNAPSHOT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, SNAPSHOT)  # atomic, so the dashboard never reads a half-written file
    return df


def read_snapshot():
    if not os.path.exists(SNAPSHOT):
        return None
    try:
        with open(SNAPSHOT) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


if __name__ == "__main__":
    import sys

    msg = " ".join(sys.argv[1:])
    out = write_snapshot(note=msg)
    print(f"pushed {len(out)} symbols to dashboard" + (f" · note: {msg}" if msg else ""))
