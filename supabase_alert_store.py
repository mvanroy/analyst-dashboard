"""Supabase-backed storage for trade alerts."""
from __future__ import annotations

from datetime import datetime
import os

import httpx


TABLE = "alerts"


def is_configured() -> bool:
    url, key = _credentials()
    return bool(url and key)


def load_alerts() -> list[dict]:
    rows = _request(
        "GET",
        f"/rest/v1/{TABLE}",
        params={"select": "*", "order": "created_at.desc"},
    )
    return [_row_to_alert(row) for row in rows]


def save_alerts(alerts: list[dict]) -> None:
    if not alerts:
        return
    rows = [_alert_to_row(alert) for alert in alerts if isinstance(alert, dict)]
    _request(
        "POST",
        f"/rest/v1/{TABLE}",
        params={"on_conflict": "local_id"},
        headers={"Prefer": "resolution=merge-duplicates"},
        json=rows,
    )


def add_alert(alert: dict) -> tuple[bool, dict]:
    alert = dict(alert)
    rows = _request(
        "GET",
        f"/rest/v1/{TABLE}",
        params={
            "select": "local_id",
            "local_id": f"eq.{alert.get('id')}",
            "limit": "1",
        },
    )
    if rows:
        return False, alert
    _request("POST", f"/rest/v1/{TABLE}", json=_alert_to_row(alert))
    return True, alert


def set_status(alert_id: str, status: str) -> bool:
    return _patch_alert(alert_id, {"status": status, "updated_at": _now()})


def mark_triggered(alert_id: str, trigger: dict) -> bool:
    rows = _request(
        "GET",
        f"/rest/v1/{TABLE}",
        params={"select": "status", "local_id": f"eq.{alert_id}", "limit": "1"},
    )
    if rows and rows[0].get("status") == "triggered":
        return False
    now = _now()
    return _patch_alert(
        alert_id,
        {
            "status": "triggered",
            "triggered_at": now,
            "updated_at": now,
            "trigger": trigger or {},
        },
    )


def mark_notified(alert_id: str, channel: str, result: dict | None = None) -> bool:
    rows = _request(
        "GET",
        f"/rest/v1/{TABLE}",
        params={"select": "notified", "local_id": f"eq.{alert_id}", "limit": "1"},
    )
    notified = rows[0].get("notified") if rows and isinstance(rows[0].get("notified"), dict) else {}
    notified[channel] = {"sent_at": _now(), "ok": bool((result or {}).get("ok", True))}
    return _patch_alert(alert_id, {"notified": notified, "updated_at": _now()})


def delete_alert(alert_id: str) -> bool:
    response = _request(
        "DELETE",
        f"/rest/v1/{TABLE}",
        params={"local_id": f"eq.{alert_id}"},
        headers={"Prefer": "return=representation"},
    )
    return bool(response)


def _patch_alert(alert_id: str, values: dict) -> bool:
    response = _request(
        "PATCH",
        f"/rest/v1/{TABLE}",
        params={"local_id": f"eq.{alert_id}"},
        headers={"Prefer": "return=representation"},
        json=values,
    )
    return bool(response)


def _request(method: str, path: str, **kwargs):
    url, key = _credentials()
    if not url or not key:
        raise RuntimeError("Supabase is not configured.")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    headers.update(kwargs.pop("headers", {}) or {})
    response = httpx.request(
        method,
        url.rstrip("/") + path,
        headers=headers,
        timeout=20,
        **kwargs,
    )
    response.raise_for_status()
    if not response.content:
        return []
    return response.json()


def _credentials() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if url and key:
        return url, key

    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    supabase = _read_section(secrets_path, "supabase")
    return (
        url or str(supabase.get("url") or "").strip(),
        key
        or str(
            supabase.get("service_role_key")
            or supabase.get("secret_key")
            or supabase.get("anon_key")
            or ""
        ).strip(),
    )


def _read_section(path: str, section: str) -> dict:
    values: dict[str, str] = {}
    active = False
    try:
        with open(path, "r") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    active = line == f"[{section}]"
                    continue
                if not active or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def _alert_to_row(alert: dict) -> dict:
    zone = alert.get("zone") if isinstance(alert.get("zone"), dict) else {}
    return {
        "local_id": alert.get("id"),
        "symbol": alert.get("symbol"),
        "timeframe": alert.get("timeframe"),
        "direction": alert.get("direction"),
        "pattern": alert.get("pattern"),
        "alert_type": alert.get("type") or alert.get("alert_type") or "price",
        "condition": alert.get("condition"),
        "level": _num_or_none(alert.get("level")),
        "zone_low": _num_or_none(zone.get("low")),
        "zone_high": _num_or_none(zone.get("high")),
        "status": alert.get("status") or "active",
        "note": alert.get("note"),
        "setup_snapshot": alert.get("setup_snapshot") if isinstance(alert.get("setup_snapshot"), dict) else {},
        "baseline": alert.get("baseline") if isinstance(alert.get("baseline"), dict) else {},
        "trigger": alert.get("trigger") if isinstance(alert.get("trigger"), dict) else {},
        "notified": alert.get("notified") if isinstance(alert.get("notified"), dict) else {},
        "created_at": alert.get("created_at") or _now(),
        "updated_at": alert.get("updated_at") or _now(),
        "triggered_at": alert.get("triggered_at"),
    }


def _row_to_alert(row: dict) -> dict:
    alert = {
        "id": row.get("local_id") or row.get("id"),
        "symbol": row.get("symbol"),
        "timeframe": row.get("timeframe"),
        "direction": row.get("direction"),
        "pattern": row.get("pattern"),
        "type": row.get("alert_type"),
        "condition": row.get("condition"),
        "level": _num_or_none(row.get("level")),
        "status": row.get("status") or "active",
        "note": row.get("note"),
        "setup_snapshot": row.get("setup_snapshot") or {},
        "baseline": row.get("baseline") or {},
        "trigger": row.get("trigger") or {},
        "notified": row.get("notified") or {},
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "triggered_at": row.get("triggered_at"),
    }
    if row.get("zone_low") is not None or row.get("zone_high") is not None:
        alert["zone"] = {"low": _num_or_none(row.get("zone_low")), "high": _num_or_none(row.get("zone_high"))}
    return alert


def _num_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
