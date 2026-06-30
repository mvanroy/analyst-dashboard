# Cloud Worker Runbook

This radar is designed to run as a separate background worker. Do not deploy it
as part of the existing dashboard app service.

## What The Worker Does

```text
Loop every RADAR_SCAN_INTERVAL_SECONDS
  discover active Binance USDT perpetuals
  filter the universe
  fetch 1H/4H candles and derivatives
  score the six proof-test engines plus magnitude
  write latest JSON and CSV
  append scan rows to SQLite
  evaluate alert state
  send Telegram only if alerts are enabled and dry-run is false
```

## Default Mode

The default mode is live:

```text
RADAR_ALERTS_ENABLED=true
RADAR_ALERTS_DRY_RUN=false
```

That means the worker scans, records evidence, and sends Telegram messages when
the alert rules pass.

## Required Cloud Environment Variables

```text
RADAR_CONFIG=config/balanced.yml
RADAR_DB_PATH=/data/radar.sqlite
RADAR_JSON_PATH=/data/latest_top30.json
RADAR_CSV_PATH=/data/latest_top30.csv
RADAR_SCAN_INTERVAL_SECONDS=300
RADAR_TOP_N=30
RADAR_WORKERS=8
RADAR_MIN_QUOTE_VOLUME_24H=10000000
RADAR_ALERTS_ENABLED=true
RADAR_ALERTS_DRY_RUN=false
RADAR_ALERT_COOLDOWN_HOURS=6
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## Persistent Storage

Mount a persistent volume at:

```text
/data
```

The worker stores:

```text
/data/radar.sqlite
/data/latest_top30.json
/data/latest_top30.csv
```

Without persistent storage, the worker can still run, but it may lose scan
history and alert state on restart.

## Docker

Local:

```bash
docker compose up --build
```

Cloud:

```bash
python -m app.worker --loop
```

## Railway

Use this folder as a separate Railway service.

The isolated Railway config is:

```text
railway.worker.json
```

Start command:

```bash
python -m app.worker --loop
```

Do not reuse the dashboard app's Railway service. This should be a separate
worker service with its own volume.

## Smoke Test

```bash
python -m app.worker --smoke-test
```

Expected output:

```json
{
  "ok": true,
  "telegram_configured": false
}
```

## One-Off Scan

```bash
python -m app.worker --once
```

## Loop Mode

```bash
python -m app.worker --loop
```

## When To Turn Telegram On

Only after the worker has run in dry-run mode long enough to inspect:

```text
scan count
top ranked setups
classification blockers
false positives
state changes
```

Then switch:

```text
RADAR_ALERTS_ENABLED=true
RADAR_ALERTS_DRY_RUN=false
```
