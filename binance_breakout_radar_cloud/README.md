# Binance Breakout Radar Cloud

Isolated, deleteable cloud-first radar project.

This folder does not import or modify the existing dashboard app. It is designed
to be run as a separate worker service.

## What It Does

- Discovers Binance USDT perpetual futures.
- Scores each symbol with six engines:
  - Compression
  - Structural Pressure
  - Participation
  - Momentum
  - Smart Money / Derivatives
  - Price Acceptance
- Displays scores as `x / 100`.
- Writes top-ranked results to JSON and CSV.
- Stores scan history and alert state in SQLite.
- Supports Telegram alerts, disabled by default.
- Keeps tunable settings in YAML profiles.

## Run A Smoke Test

```bash
python -m app.worker --smoke-test
```

## Run One Scan

```bash
python -m app.worker --once
```

## Run One Symbol

```bash
python -m app.worker --once --symbol TRXUSDT
```

## Run Continuously

```bash
python -m app.worker --loop
```

## Config Profiles

```text
config/balanced.yml
config/aggressive.yml
config/conservative.yml
```

Use a profile with:

```bash
python -m app.worker --once --config config/conservative.yml
```

## Telegram

Copy `.env.example` to `.env` and fill:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Then set this in the config when ready:

```yaml
alerts:
  enabled: true
  dry_run: false
```

Leave `dry_run: true` while tuning.

## Docker

```bash
docker compose up --build
```

## Cloud Worker

See:

```text
CLOUD_WORKER.md
```

The worker is meant to be deployed as a separate background service, not inside
the existing dashboard app.

The SQLite database is mounted at:

```text
data/radar.sqlite
```

Outputs are written to:

```text
outputs/latest_top30.json
outputs/latest_top30.csv
```

## Deleting It

This is intentionally self-contained. To remove the project, delete:

```text
binance_breakout_radar_cloud/
```
