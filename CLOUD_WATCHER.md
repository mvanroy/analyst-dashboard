# Cloud Alert Watcher

The cloud watcher runs the same mechanical alert checks as the dashboard watcher,
but from a scheduled cloud job so the laptop does not need to stay on.

Recommended first deployment target: Render Cron Job.

## Worker Command

```bash
python cloud_alert_watcher.py
```

## Smoke Test Command

This checks Supabase and Telegram configuration without evaluating or triggering
alerts:

```bash
python cloud_alert_watcher.py --smoke-test
```

## Required Environment Variables

Set these in the cloud host, not in source control:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Current Alert Scope

The watcher is deliberately mechanical. It can track saved conditions such as:

- Price enters a saved entry zone
- Price reaches or crosses a saved level
- Candle closes above or below a saved trigger level
- Price enters a saved HTF demand/supply zone

Pattern-discovery alerts should be built later as a separate scanner layer.
