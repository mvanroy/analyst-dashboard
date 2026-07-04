# Reversal-Low Alert Worker

Separate Telegram bot that pings on **state changes** in the capitulation-flush
watch list (same engine as the dashboard's Reversal Lows page —
`reversal_watchlist.py`). All wicks ≥ 1 ATR are tracked; THRILLING (≥ 2 ATR)
flagged in the message.

Alerts: 🩸 new flush · ✅ reclaim confirmed · ⏳ low intact 5 bars ·
❌ invalidated. Stale transitions are silent. First cycle after a cold start
baselines without alerting (no spam after redeploys).

## One-time setup

1. **Create the bot** (must be separate from the radar bot): message
   [@BotFather](https://t.me/BotFather) → `/newbot` → name it (e.g.
   "Reversal Lows") → copy the token.
2. **Get your chat id**: message the new bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and read
   `message.chat.id`.
3. **Railway**: add a new service on this repo with config file
   `reversal_alert_cloud/railway.worker.json`, and set env vars:
   - `REVERSAL_TG_BOT_TOKEN` — from step 1
   - `REVERSAL_TG_CHAT_ID` — from step 2
   - `REVERSAL_MIN_TURNOVER` — optional USD floor (e.g. `1000000`); default 0
     tracks everything, micro-caps arrive tagged with a warning.

## Local test (no Telegram needed)

```
.venv/bin/python reversal_alert_cloud/worker.py --once --dry
```

Note: the Learned Model score requires `research/reversal_lows/results/
learned_model.pkl` to be present (and scikit-learn installed). Without it the
worker still runs — scores fall back to the tail-bucket class rate.
