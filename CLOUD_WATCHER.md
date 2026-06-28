# Watch List Scanner Worker

This worker is for the Watch List scanner Telegram path only.

It is separate from the old Trade Setup saved-alert system. It runs the scanner,
compares the latest scan against the previous scanner state, and sends Telegram
messages when a setup becomes newly ready, matures, flips direction, or becomes
invalidated.

This matches the original JCHelper cron pattern: run the scanner, collect stdout,
and send the resulting setup text to Telegram using Markdown formatting.

Recommended live deployment target: Railway always-on worker.

## Worker Command

```bash
python cloud_watchlist_scanner.py
```

## Always-On Worker Command

```bash
python cloud_watchlist_scanner.py --loop
```

The loop checks every 5 minutes by default. Set `SCANNER_INTERVAL_SECONDS` to
change this.

## Smoke Test Command

This checks Telegram and state configuration without scanning exchanges or
sending scanner messages:

```bash
python cloud_watchlist_scanner.py --smoke-test
```

## Required Environment Variables

Set these as GitHub repository secrets, not in source control:

Preferred for the Watch List scanner:

- `WATCHLIST_TELEGRAM_BOT_TOKEN`
- `WATCHLIST_TELEGRAM_CHAT_ID`

Or, if using the existing JCHelper bot:

- `JCHELPER_TELEGRAM_BOT_TOKEN`
- `JCHELPER_TELEGRAM_CHAT_ID`

Fallback supported:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional:

- `SCANNER_INTERVAL_SECONDS`, default `300`
- `WATCHLIST_STATE_FILE`, default `watchlist_engine/state/scanner_state.json`

For production, use persistent storage for `WATCHLIST_STATE_FILE`. On Railway,
mount a volume and point this variable at that volume path, for example:

```text
WATCHLIST_STATE_FILE=/data/scanner_state.json
```

Without persistent state, the worker can still scan, but it may forget previous
setups after a redeploy or restart.

## GitHub Actions

The workflow lives at:

```text
.github/workflows/alert-watcher.yml
```

It is deliberately a manual smoke test only. Do not use scheduled GitHub Actions
for live scanner Telegram alerts unless scanner state is moved to persistent
storage outside the job, otherwise the scanner can forget previous state between
runs.

## Railway

The Railway config lives at:

```text
railway.json
```

It starts:

```bash
python cloud_watchlist_scanner.py --loop
```

Required Railway variables:

- `JCHELPER_TELEGRAM_BOT_TOKEN`
- `JCHELPER_TELEGRAM_CHAT_ID`
- optional: `SCANNER_INTERVAL_SECONDS`, default `300`
- optional but recommended with a Railway volume: `WATCHLIST_STATE_FILE`

## Current Scanner Scope

The scanner sends Telegram messages for scanner state changes:

- New ready setup
- Setup matures into ready
- Dominant direction flips long/short
- Previously active setup becomes invalidated

It does not use the old Trade Setup suggested-alert UI.
