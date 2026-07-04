"""Reversal-Low alert worker — cloud loop for the flush watch list.

Runs the same engine as the dashboard page (reversal_watchlist.run_scan) every
15 minutes, tracks each candidate's lifecycle, and sends a Telegram message on
STATE CHANGES only:

  🩸 NEW        flush admitted to the board (wick >= 1 ATR; THRILLING >= 2)
  ✅ CONFIRMED  reclaim close printed (grade + health)
  ⏳ SEASONED   low intact 5 bars after the flush (57% -> ~79% class, in-study)
  ❌ INVALIDATED low broke (candidate vanished from the scan before ageing out)

Stale transitions are silent (96% of giant crash bars go stale; it means
nothing). First run after startup establishes a baseline without alerting.

Env (separate bot on purpose — do NOT reuse the radar's token):
  REVERSAL_TG_BOT_TOKEN   bot token from @BotFather
  REVERSAL_TG_CHAT_ID     chat id to send to
  REVERSAL_STATE_PATH     state file (default ./reversal_state.json)
  REVERSAL_MIN_TURNOVER   optional USD floor, e.g. 1000000 (default 0 = all)

Run: python worker.py --loop   (or --once for a single cycle, --dry to print
instead of sending).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reversal_watchlist import run_scan  # noqa: E402

TOKEN = os.getenv("REVERSAL_TG_BOT_TOKEN", "")
CHAT = os.getenv("REVERSAL_TG_CHAT_ID", "")
STATE_PATH = os.getenv("REVERSAL_STATE_PATH", "./reversal_state.json")
MIN_TURNOVER = float(os.getenv("REVERSAL_MIN_TURNOVER", "0"))
MEL = timezone(timedelta(hours=10))  # AEST; Melbourne (ignore DST for brevity)
SEASONED_BARS = 5
AGE_OUT_BARS = 23        # scan window covers the last 24 bars


def melb_now():
    return datetime.now(MEL).strftime("%H:%M")


def send(text, dry=False):
    if dry or not (TOKEN and CHAT):
        print(f"[DRY] {text}\n---", flush=True)
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": CHAT, "text": text,
                            "disable_web_page_preview": True}, timeout=15)
    except Exception as exc:
        print(f"telegram send failed: {exc}", flush=True)


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception as exc:
        print(f"state save failed: {exc}", flush=True)


def fmt_price(v):
    return f"{v:.6g}"


def wick_word(tail):
    return "THRILLING wick" if tail >= 2.0 else "Long wick"


def new_msg(r):
    m = r["meta"]
    lines = [
        f"🩸 {r['coin']} — {wick_word(m['tail_atr'])} {m['tail_atr']:.1f} ATR",
        f"Rulebook {r['grade']} · Learned {r['score']}%",
        f"low {fmt_price(m['low'])} · stop {fmt_price(m['stop'])} · "
        f"reclaim {fmt_price(m['reclaim'])}",
        f"price {fmt_price(r['price'])} · "
        f"turnover ${m['turnover_usd'] / 1e6:.1f}M",
    ]
    warn = [w for w in r.get("warnings", []) if "Micro-cap" in w]
    if warn:
        lines.append("⚠️ " + warn[0])
    lines.append(f"{melb_now()} Melb")
    return "\n".join(lines)


def confirm_msg(r):
    m = r["meta"]
    return (f"✅ {r['coin']} — reclaim CONFIRMED ({m['grade']}, {m['health']})"
            f"\nwick {m['tail_atr']:.1f} ATR · Rulebook {r['grade']} · "
            f"Learned {r['score']}%"
            f"\nentry zone {fmt_price(r['entry_low'])}-"
            f"{fmt_price(r['entry_high'])} · stop {fmt_price(m['stop'])}"
            f"\nprice {fmt_price(r['price'])} · {melb_now()} Melb")


def seasoned_msg(r):
    m = r["meta"]
    return (f"⏳ {r['coin']} — low intact {m['bars_since_low']} bars "
            f"(seasoned; class odds improve with survival)"
            f"\nwick {m['tail_atr']:.1f} ATR · low {fmt_price(m['low'])} · "
            f"reclaim {fmt_price(m['reclaim'])}"
            f"\nprice {fmt_price(r['price'])} · {melb_now()} Melb")


def invalid_msg(sym, st):
    return (f"❌ {sym} — flush INVALIDATED (low {fmt_price(st['low'])} broke)"
            f"\n{melb_now()} Melb")


def cycle(state, baseline=False, dry=False):
    data = run_scan()
    rows = [r for r in data["rows"]
            if r["meta"]["turnover_usd"] >= MIN_TURNOVER]
    seen = set()
    n_alerts = 0
    for r in rows:
        m = r["meta"]
        key = f"{r['coin']}:{m['t_open_ms']}"
        seen.add(key)
        st = state.get(key)
        if st is None:
            state[key] = {"stage": m["state"], "seasoned": False,
                          "low": m["low"], "bars": m["bars_since_low"]}
            if not baseline and m["bars_since_low"] <= 4:
                send(new_msg(r), dry)
                n_alerts += 1
            continue
        st["bars"] = m["bars_since_low"]
        if m["state"] == "CONFIRMED" and st["stage"] != "CONFIRMED":
            st["stage"] = "CONFIRMED"
            if not baseline:
                send(confirm_msg(r), dry)
                n_alerts += 1
        elif (m["state"] == "AWAITING" and not st["seasoned"]
              and m["bars_since_low"] >= SEASONED_BARS):
            st["seasoned"] = True
            if not baseline:
                send(seasoned_msg(r), dry)
                n_alerts += 1
        elif m["state"] == "STALE":
            st["stage"] = "STALE"          # silent transition

    # disappearance before ageing out == invalidation (the only removal path)
    for key in list(state):
        if key in seen:
            continue
        st = state.pop(key)
        if st.get("bars", 99) < AGE_OUT_BARS and st.get("stage") != "RETIRED" \
                and not baseline:
            send(invalid_msg(key.split(":")[0], st), dry)
            n_alerts += 1
    print(f"{datetime.now(MEL):%H:%M} cycle: {len(rows)} on board, "
          f"{n_alerts} alerts", flush=True)
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    state = load_state()
    first = not state
    if args.once or not args.loop:
        state = cycle(state, baseline=first, dry=args.dry)
        save_state(state)
        return

    send(f"🔌 Reversal-low alert worker online — all wicks ≥ 1 ATR, "
         f"state-change alerts only. {melb_now()} Melb", args.dry)
    while True:
        try:
            state = cycle(state, baseline=first, dry=args.dry)
            first = False
            save_state(state)
        except Exception as exc:
            print(f"cycle error: {exc}", flush=True)
        # sleep to ~45s past the next quarter-hour
        now = time.time()
        next_bar = (int(now // 900) + 1) * 900 + 45
        time.sleep(max(30, next_bar - now))


if __name__ == "__main__":
    main()
