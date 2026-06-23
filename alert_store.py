"""Local storage for AI-assisted trade alerts."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os

import supabase_alert_store

ALERTS_PATH = os.path.join(os.path.dirname(__file__), "alerts.json")


def load_alerts() -> list[dict]:
    if supabase_alert_store.is_configured():
        try:
            return supabase_alert_store.load_alerts()
        except Exception:
            pass
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
    if supabase_alert_store.is_configured():
        try:
            supabase_alert_store.save_alerts(alerts)
            return
        except Exception:
            pass
    with open(ALERTS_PATH, "w") as f:
        json.dump(alerts, f, indent=2)


def load_local_alerts() -> list[dict]:
    return _load_local_alerts()


def migrate_local_alerts_to_supabase() -> dict:
    if not supabase_alert_store.is_configured():
        return {"ok": False, "error": "Supabase is not configured.", "migrated": 0}
    migrated = 0
    skipped = 0
    for alert in _load_local_alerts():
        if not isinstance(alert, dict):
            continue
        alert["id"] = alert.get("id") or _alert_id(alert)
        try:
            created, _ = supabase_alert_store.add_alert(alert)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "migrated": migrated, "skipped": skipped}
        if created:
            migrated += 1
        else:
            skipped += 1
    return {"ok": True, "migrated": migrated, "skipped": skipped}


def alert_key(alert: dict) -> tuple:
    return (
        alert.get("symbol"),
        alert.get("pattern"),
        alert.get("type"),
        alert.get("timeframe"),
        alert.get("condition"),
    )


def add_alert(alert: dict) -> tuple[bool, dict]:
    alert = dict(alert)
    alert["status"] = alert.get("status") or "active"
    alert["created_at"] = alert.get("created_at") or datetime.now().isoformat(timespec="seconds")
    alert["id"] = alert.get("id") or _alert_id(alert)
    if not alert.get("baseline"):
        from alert_watcher import capture_baseline

        alert["baseline"] = capture_baseline(alert)
    if supabase_alert_store.is_configured():
        try:
            return supabase_alert_store.add_alert(alert)
        except Exception:
            pass
    alerts = load_alerts()
    existing = {alert_key(a) for a in alerts}
    if alert_key(alert) in existing:
        return False, alert
    alerts.insert(0, alert)
    save_alerts(alerts)
    return True, alert


def set_status(alert_id: str, status: str) -> bool:
    if supabase_alert_store.is_configured():
        try:
            return supabase_alert_store.set_status(alert_id, status)
        except Exception:
            pass
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


def mark_triggered(alert_id: str, trigger: dict) -> bool:
    if supabase_alert_store.is_configured():
        try:
            return supabase_alert_store.mark_triggered(alert_id, trigger)
        except Exception:
            pass
    alerts = load_alerts()
    changed = False
    now = datetime.now().isoformat(timespec="seconds")
    for alert in alerts:
        if alert.get("id") == alert_id:
            if alert.get("status") == "triggered":
                return False
            alert["status"] = "triggered"
            alert["triggered_at"] = now
            alert["updated_at"] = now
            alert["trigger"] = trigger
            changed = True
            break
    if changed:
        save_alerts(alerts)
    return changed


def mark_notified(alert_id: str, channel: str, result: dict | None = None) -> bool:
    if supabase_alert_store.is_configured():
        try:
            return supabase_alert_store.mark_notified(alert_id, channel, result)
        except Exception:
            pass
    alerts = load_alerts()
    changed = False
    now = datetime.now().isoformat(timespec="seconds")
    for alert in alerts:
        if alert.get("id") == alert_id:
            notified = alert.get("notified") if isinstance(alert.get("notified"), dict) else {}
            notified[channel] = {
                "sent_at": now,
                "ok": bool((result or {}).get("ok", True)),
            }
            alert["notified"] = notified
            alert["updated_at"] = now
            changed = True
            break
    if changed:
        save_alerts(alerts)
    return changed


def delete_alert(alert_id: str) -> bool:
    if supabase_alert_store.is_configured():
        try:
            return supabase_alert_store.delete_alert(alert_id)
        except Exception:
            pass
    alerts = load_alerts()
    kept = [a for a in alerts if a.get("id") != alert_id]
    if len(kept) == len(alerts):
        return False
    save_alerts(kept)
    return True


def _alert_id(alert: dict) -> str:
    base = "|".join(str(x or "") for x in alert_key(alert))
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def _load_local_alerts() -> list[dict]:
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
        with open(ALERTS_PATH, "w") as f:
            json.dump(alerts, f, indent=2)
    return alerts
