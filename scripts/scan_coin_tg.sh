#!/usr/bin/env bash
# Runs the Watch List scanner and sends any state-change output to Telegram.
#
# Required:
#   JCHELPER_TELEGRAM_BOT_TOKEN
#   JCHELPER_TELEGRAM_CHAT_ID
#
# Optional:
#   SYMBOL="BTC/USDT:USDT"

set -euo pipefail

: "${JCHELPER_TELEGRAM_BOT_TOKEN:?not set}"
: "${JCHELPER_TELEGRAM_CHAT_ID:?not set}"

SYMBOL="${SYMBOL:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONUNBUFFERED=1
cd "$APP_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

OUTPUT=$(python3 -m watchlist_engine.cron_scan ${SYMBOL:+--symbol "$SYMBOL"} 2>/dev/null || true)

if [[ -n "$OUTPUT" ]]; then
  printf '%s' "$OUTPUT" | python3 -c '
import os
import sys

import telegram_notifier

text = sys.stdin.read().strip()
if not text:
    raise SystemExit(0)

telegram_notifier.send_message(
    text,
    token=os.environ["JCHELPER_TELEGRAM_BOT_TOKEN"],
    chat_id=os.environ["JCHELPER_TELEGRAM_CHAT_ID"],
    parse_mode="Markdown",
)
'
fi
