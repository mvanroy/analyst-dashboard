"""Telegram delivery for trade alert notifications."""
from __future__ import annotations

from datetime import datetime
import os

import httpx


TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def is_configured() -> bool:
    token, chat_id = _credentials()
    return bool(token and chat_id)


def send_test_message() -> dict:
    return send_message(
        "Trade alerts are connected.\n\n"
        f"Test sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
    )


def send_alert(alert: dict, trigger: dict) -> dict:
    return send_message(_format_alert_message(alert, trigger))


def send_message(text: str) -> dict:
    token, chat_id = _credentials()
    if not token or not chat_id:
        return {"ok": False, "skipped": True, "error": "Telegram is not configured."}
    response = httpx.post(
        TELEGRAM_URL.format(token=token),
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _credentials() -> tuple[str, str]:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if token and chat_id:
        return token, chat_id

    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    telegram = _read_telegram_section(secrets_path)
    return (
        token or str(telegram.get("bot_token") or "").strip(),
        chat_id or str(telegram.get("chat_id") or "").strip(),
    )


def _read_telegram_section(path: str) -> dict:
    values: dict[str, str] = {}
    in_telegram = False
    try:
        with open(path, "r") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_telegram = line == "[telegram]"
                    continue
                if not in_telegram or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def _format_alert_message(alert: dict, trigger: dict) -> str:
    setup = alert.get("setup_snapshot") if isinstance(alert.get("setup_snapshot"), dict) else {}
    entry = setup.get("entry_zone") or {}
    stop = setup.get("stop") or {}
    t1 = setup.get("t1") or {}
    t2 = setup.get("t2") or {}
    summary = setup.get("summary") or alert.get("note") or ""
    lines = [
        f"{alert.get('symbol', 'Trade')} alert triggered",
        "",
        trigger.get("message") or alert.get("condition") or "Saved alert condition was met.",
    ]
    if alert.get("timeframe"):
        lines.append(f"Timeframe: {alert.get('timeframe')}")
    if alert.get("direction"):
        lines.append(f"Direction: {str(alert.get('direction')).upper()}")
    if alert.get("pattern"):
        lines.append(f"Setup: {alert.get('pattern')}")
    if entry.get("label"):
        lines.append(f"Entry: {entry.get('label')}")
    if stop.get("label"):
        lines.append(f"Stop: {stop.get('label')}")
    if t1.get("label"):
        lines.append(f"TP1: {t1.get('label')}{(' ' + t1.get('rr')) if t1.get('rr') else ''}")
    if t2.get("label"):
        lines.append(f"TP2: {t2.get('label')}{(' ' + t2.get('rr')) if t2.get('rr') else ''}")
    if summary:
        lines.extend(["", str(summary)[:500]])
    lines.extend(["", "Check the dashboard before acting."])
    return "\n".join(lines)
