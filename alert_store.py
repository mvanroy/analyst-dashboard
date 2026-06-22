"""Local storage for AI-assisted trade alerts."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os


ALERTS_PATH = os.path.join(os.path.dirname(__file__), "alerts.json")


def load_alerts() -> list[dict]:
    if not os.path.exists(ALERTS_PATH):
        return []
    try:
        with open(ALERTS_PATH, "r") as f:
            data = json.load(f)
        alerts = data if isinstance(data, list) else []
    except Exception:
        return []
    changed = False
    for alert in alerts:
        if isinstance(alert, dict) and not alert.get("id"):
            alert["id"] = _alert_id(alert)
            changed = True
    if changed:
        save_alerts(alerts)
    return alerts


def save_alerts(alerts: list[dict]) -> None:
    with open(ALERTS_PATH, "w") as f:
        json.dump(alerts, f, indent=2)


def alert_key(alert: dict) -> tuple:
    return (
        alert.get("symbol"),
        alert.get("pattern"),
        alert.get("type"),
        alert.get("timeframe"),
        alert.get("condition"),
    )


def add_alert(alert: dict) -> tuple[bool, dict]:
    alerts = load_alerts()
    alert = dict(alert)
    alert["status"] = alert.get("status") or "active"
    alert["created_at"] = alert.get("created_at") or datetime.now().isoformat(timespec="seconds")
    alert["id"] = alert.get("id") or _alert_id(alert)
    existing = {alert_key(a) for a in alerts}
    if alert_key(alert) in existing:
        return False, alert
    alerts.insert(0, alert)
    save_alerts(alerts)
    return True, alert


def set_status(alert_id: str, status: str) -> bool:
    alerts = load_alerts()
    changed = False
    for alert in alerts:
        if alert.get("id") == alert_id:
            alert["status"] = status
            alert["updated_at"] = datetime.now().isoformat(timespec="seconds")
            changed = True
            break
    if changed:
        save_alerts(alerts)
    return changed


def delete_alert(alert_id: str) -> bool:
    alerts = load_alerts()
    kept = [a for a in alerts if a.get("id") != alert_id]
    if len(kept) == len(alerts):
        return False
    save_alerts(kept)
    return True


def _alert_id(alert: dict) -> str:
    base = "|".join(str(x or "") for x in alert_key(alert))
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
