"""Storage for the twins daily care log."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
import threading
import uuid
from zoneinfo import ZoneInfo

import httpx


TABLE = "baby_log_events"
CARE_TABLE = "baby_care_details"
FEED_KINDS = {"left", "right", "bottle"}
MILK_TYPES = ("FOR", "EBM")
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_PATH = os.path.join(ROOT_DIR, "baby_log_events.json")
LOCAL_DETAILS_PATH = os.path.join(ROOT_DIR, "baby_care_details.json")
MEL = ZoneInfo("Australia/Melbourne")


class StorageError(RuntimeError):
    """Raised when the configured shared baby-log store is unavailable."""


_storage_warning = ""
_client_lock = threading.Lock()
_shared_client: httpx.Client | None = None
_shared_client_credentials: tuple[str, str] | None = None


def storage_warning() -> str:
    return _storage_warning


def _set_storage_warning(action: str) -> None:
    global _storage_warning
    _storage_warning = (
        "Shared storage is currently unavailable. "
        "Showing the local cache in read-only mode; new changes will not be saved locally."
    )


def _shared_store_error(action: str, exc: Exception) -> StorageError:
    return StorageError(
        f"Could not {action} in the shared baby-log database. "
        "Nothing was written locally; please check the connection and try again."
    )


def is_supabase_configured() -> bool:
    if _storage_mode() == "local":
        return False
    url, key = _credentials()
    return bool(url and key)


def _storage_mode() -> str:
    explicit = (os.getenv("BABY_LOG_STORAGE_MODE") or "").strip().lower()
    if not explicit:
        secrets_path = os.path.join(ROOT_DIR, ".streamlit", "secrets.toml")
        explicit = str(_read_section(secrets_path, "baby_log").get("storage_mode") or "").strip().lower()
    return explicit if explicit in {"local", "supabase"} else "supabase"


def load_events(day: str | None = None) -> list[dict]:
    global _storage_warning
    _storage_warning = ""
    if is_supabase_configured():
        try:
            return _load_supabase(day)
        except Exception:
            _set_storage_warning("load events")
            return _load_local(day)
    return _load_local(day)


def load_events_range(start_day: str, end_day: str) -> list[dict]:
    """Load an inclusive day range without issuing one request per day."""
    global _storage_warning
    _storage_warning = ""
    if is_supabase_configured():
        try:
            rows = _request(
                "GET",
                f"/rest/v1/{TABLE}",
                params=[
                    ("day", f"gte.{start_day}"),
                    ("day", f"lte.{end_day}"),
                    ("select", "*"),
                    ("order", "event_ts.asc"),
                ],
            )
            return _effective_events([_row_to_event(row) for row in rows])
        except Exception:
            _set_storage_warning("load events")
    return [
        event
        for event in _load_local(None)
        if start_day <= str(event.get("day") or "") <= end_day
    ]


def replace_feed_cell(
    day: str,
    baby: str,
    kind: str,
    hour: int,
    selections: dict[str, dict | None],
    *,
    event_ts: datetime,
) -> list[dict]:
    """Atomically replace the effective values for one feed cell.

    Canonical records use deterministic IDs, so a retry updates the same rows
    instead of creating duplicates. A cleared selection is represented by a
    tombstone. Older event rows are retained as history but are superseded by
    the canonical row when events are loaded.
    """
    if kind not in FEED_KINDS:
        raise ValueError(f"Unsupported feed kind: {kind}")
    expected = set(MILK_TYPES if kind == "bottle" else ("",))
    if set(selections) != expected:
        raise ValueError("Feed-cell selections do not match the requested kind.")

    now = datetime.now(MEL)
    canonical: list[dict] = []
    for milk_type in sorted(expected):
        selection = selections[milk_type]
        state = "active" if selection is not None else "cleared"
        note_parts = [f"feed_state={state}"]
        if kind == "bottle":
            note_parts.append(f"milk_type={milk_type}")
        amount_ml = None
        if selection is not None:
            amount_ml = selection.get("amount_ml")
            extra_note = str(selection.get("note") or "").strip()
            if extra_note:
                note_parts.extend(
                    part for part in extra_note.split(";") if part and not part.startswith("feed_state=")
                )
        canonical.append(
            {
                "id": feed_cell_record_id(day, baby, hour, kind, milk_type),
                "baby": baby,
                "kind": kind,
                "amount_ml": amount_ml,
                "note": ";".join(note_parts),
                "event_ts": event_ts.isoformat(timespec="seconds"),
                "day": day,
                "created_at": now.isoformat(timespec="seconds"),
            }
        )

    if is_supabase_configured():
        try:
            rows = _request(
                "POST",
                f"/rest/v1/{TABLE}",
                params={"on_conflict": "id"},
                json=[_event_to_row(event) for event in canonical],
                headers={"Prefer": "resolution=merge-duplicates,return=representation"},
            )
            saved = [_row_to_event(row) for row in rows]
            return saved or canonical
        except Exception as exc:
            raise _shared_store_error("save this feed", exc) from exc

    events = _load_local_raw()
    replacements = {event["id"]: event for event in canonical}
    events = [event for event in events if event.get("id") not in replacements]
    events.extend(replacements.values())
    _save_local(events)
    return canonical


def feed_cell_record_id(day: str, baby: str, hour: int, kind: str, milk_type: str = "") -> str:
    """Return the stable ID used for an editable feed-cell value."""
    identity = f"igby-baby-log:{day}:{baby}:{hour:02d}:{kind}:{milk_type.upper()}"
    return uuid.uuid5(uuid.NAMESPACE_URL, identity).hex


def add_event(
    baby: str,
    kind: str,
    *,
    amount_ml: int | None = None,
    note: str = "",
    event_ts: datetime | None = None,
) -> dict:
    now = datetime.now(MEL)
    event_dt = event_ts or now
    event = {
        "id": uuid.uuid4().hex,
        "baby": baby,
        "kind": kind,
        "amount_ml": amount_ml,
        "note": note.strip(),
        "event_ts": event_dt.isoformat(timespec="seconds"),
        "day": event_dt.date().isoformat(),
        "created_at": now.isoformat(timespec="seconds"),
    }
    if is_supabase_configured():
        try:
            _request("POST", f"/rest/v1/{TABLE}", json=_event_to_row(event))
            return event
        except Exception as exc:
            raise _shared_store_error("save this event", exc) from exc
    events = _load_local_raw()
    events.append(event)
    _save_local(events)
    return event


def delete_event(event_id: str) -> bool:
    if is_supabase_configured():
        try:
            deleted = _request(
                "DELETE",
                f"/rest/v1/{TABLE}",
                params={"id": f"eq.{event_id}"},
                headers={"Prefer": "return=representation"},
            )
            if deleted:
                return True
        except Exception as exc:
            raise _shared_store_error("delete this event", exc) from exc
    events = _load_local_raw()
    kept = [event for event in events if event.get("id") != event_id]
    if len(kept) == len(events):
        return False
    _save_local(kept)
    return True


def delete_events_for_hour(day: str, baby: str, kind: str, hour: int) -> int:
    if is_supabase_configured():
        try:
            start = datetime.fromisoformat(day).replace(tzinfo=MEL, hour=hour, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
            deleted_rows = _request(
                "DELETE",
                f"/rest/v1/{TABLE}",
                params=[
                    ("baby", f"eq.{baby}"),
                    ("kind", f"eq.{kind}"),
                    ("day", f"eq.{day}"),
                    ("event_ts", f"gte.{start.isoformat()}"),
                    ("event_ts", f"lt.{end.isoformat()}"),
                ],
                headers={"Prefer": "return=representation"},
            )
            if deleted_rows:
                return len(deleted_rows)
        except Exception as exc:
            raise _shared_store_error("delete this event", exc) from exc

    deleted = 0
    for event in load_events(day):
        if event.get("baby") != baby or event.get("kind") != kind:
            continue
        try:
            event_hour = datetime.fromisoformat(str(event.get("event_ts")).replace("Z", "+00:00")).astimezone(MEL).hour
        except ValueError:
            continue
        if event_hour == hour and delete_event(event.get("id")):
            deleted += 1
    return deleted


def load_care_details(day: str, baby: str) -> dict:
    if is_supabase_configured():
        try:
            rows = _request(
                "GET",
                f"/rest/v1/{CARE_TABLE}",
                params={"day": f"eq.{day}", "baby": f"eq.{baby}", "select": "*", "limit": "1"},
            )
            return _normalise_details(rows[0] if rows else {}, day, baby)
        except Exception:
            _set_storage_warning("load care details")
            details = _load_local_details()
            return _normalise_details(details.get(f"{day}:{baby}", {}), day, baby)
    details = _load_local_details()
    return _normalise_details(details.get(f"{day}:{baby}", {}), day, baby)


def load_care_details_range(start_day: str, end_day: str) -> list[dict]:
    """Load daily care measurements for both babies over an inclusive range."""
    if is_supabase_configured():
        try:
            rows = _request(
                "GET",
                f"/rest/v1/{CARE_TABLE}",
                params=[
                    ("day", f"gte.{start_day}"),
                    ("day", f"lte.{end_day}"),
                    ("select", "*"),
                    ("order", "day.asc"),
                ],
            )
            return [
                _normalise_details(row, str(row.get("day") or ""), str(row.get("baby") or ""))
                for row in rows
            ]
        except Exception:
            _set_storage_warning("load care details")
    details = _load_local_details()
    records = []
    for record in details.values():
        if not isinstance(record, dict):
            continue
        record_day = str(record.get("day") or "")
        baby = str(record.get("baby") or "")
        if start_day <= record_day <= end_day and baby:
            records.append(_normalise_details(record, record_day, baby))
    return sorted(records, key=lambda record: (record.get("day") or "", record.get("baby") or ""))


def save_care_details(day: str, baby: str, updates: dict) -> dict:
    if is_supabase_configured():
        current = load_care_details(day, baby)
        for field in ("bath_time", "length", "weight", "notes"):
            if field in updates:
                current[field] = str(updates.get(field) or "").strip()
        current["updated_at"] = datetime.now(MEL).isoformat(timespec="seconds")
        try:
            rows = _request(
                "POST",
                f"/rest/v1/{CARE_TABLE}",
                params={"on_conflict": "day,baby"},
                json=current,
                headers={"Prefer": "resolution=merge-duplicates,return=representation"},
            )
            return _normalise_details(rows[0] if rows else current, day, baby)
        except Exception as exc:
            raise _shared_store_error("save care details", exc) from exc
    details = _load_local_details()
    key = f"{day}:{baby}"
    current = _normalise_details(details.get(key, {}), day, baby)
    for field in ("bath_time", "length", "weight", "notes"):
        if field in updates:
            current[field] = str(updates.get(field) or "").strip()
    current["updated_at"] = datetime.now(MEL).isoformat(timespec="seconds")
    details[key] = current
    _save_local_details(details)
    return current


def _load_supabase(day: str | None) -> list[dict]:
    params = {"select": "*", "order": "event_ts.asc"}
    if day:
        params["day"] = f"eq.{day}"
    rows = _request("GET", f"/rest/v1/{TABLE}", params=params)
    return _effective_events([_row_to_event(row) for row in rows])


def _load_local(day: str | None) -> list[dict]:
    cleaned = _effective_events(_load_local_raw())
    if day:
        cleaned = [event for event in cleaned if event.get("day") == day]
    return sorted(cleaned, key=lambda event: event.get("event_ts") or "")


def _load_local_raw() -> list[dict]:
    if not os.path.exists(LOCAL_PATH):
        return []
    try:
        with open(LOCAL_PATH, "r") as f:
            events = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(events, list):
        return []
    return [_normalise_event(event) for event in events if isinstance(event, dict)]


def _note_value(event: dict, key: str) -> str:
    prefix = f"{key}="
    for part in str(event.get("note") or "").split(";"):
        if part.startswith(prefix):
            return part[len(prefix):].strip()
    return ""


def _feed_cell_key(event: dict) -> tuple[str, str, int, str, str] | None:
    kind = str(event.get("kind") or "")
    if kind not in FEED_KINDS:
        return None
    try:
        hour = datetime.fromisoformat(str(event.get("event_ts") or "").replace("Z", "+00:00")).astimezone(MEL).hour
    except ValueError:
        return None
    milk_type = _note_value(event, "milk_type").upper() if kind == "bottle" else ""
    if kind == "bottle" and milk_type not in MILK_TYPES:
        milk_type = "FOR"
    return (
        str(event.get("day") or ""),
        str(event.get("baby") or ""),
        hour,
        kind,
        milk_type,
    )


def _effective_events(events: list[dict]) -> list[dict]:
    """Resolve canonical feed rows while leaving all legacy records intact."""
    canonical_by_key: dict[tuple[str, str, int, str, str], dict] = {}
    for event in events:
        key = _feed_cell_key(event)
        if key is None:
            continue
        day, baby, hour, kind, milk_type = key
        if event.get("id") == feed_cell_record_id(day, baby, hour, kind, milk_type):
            canonical_by_key[key] = event

    resolved: list[dict] = []
    emitted: set[tuple[str, str, int, str, str]] = set()
    for event in sorted(events, key=lambda item: item.get("event_ts") or ""):
        key = _feed_cell_key(event)
        canonical = canonical_by_key.get(key) if key is not None else None
        if canonical is None:
            resolved.append(event)
            continue
        if key in emitted:
            continue
        emitted.add(key)
        if _note_value(canonical, "feed_state") != "cleared":
            resolved.append(canonical)
    return resolved


def _save_local(events: list[dict]) -> None:
    with open(LOCAL_PATH, "w") as f:
        json.dump(events, f, indent=2)


def _load_local_details() -> dict:
    if not os.path.exists(LOCAL_DETAILS_PATH):
        return {}
    try:
        with open(LOCAL_DETAILS_PATH, "r") as f:
            details = json.load(f)
    except (OSError, ValueError):
        return {}
    return details if isinstance(details, dict) else {}


def _save_local_details(details: dict) -> None:
    with open(LOCAL_DETAILS_PATH, "w") as f:
        json.dump(details, f, indent=2)


def _request(method: str, path: str, **kwargs):
    url, key = _credentials()
    if not url or not key:
        raise RuntimeError("Supabase is not configured.")
    client = _shared_http_client(url, key)
    headers = kwargs.pop("headers", {}) or None
    response = client.request(
        method,
        path,
        headers=headers,
        **kwargs,
    )
    response.raise_for_status()
    if not response.content:
        return []
    return response.json()


def _shared_http_client(url: str, key: str) -> httpx.Client:
    global _shared_client, _shared_client_credentials
    credentials = (url.rstrip("/"), key)
    with _client_lock:
        if _shared_client is None or _shared_client_credentials != credentials:
            if _shared_client is not None:
                _shared_client.close()
            _shared_client = httpx.Client(
                base_url=credentials[0],
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(20.0, connect=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                transport=httpx.HTTPTransport(retries=1),
            )
            _shared_client_credentials = credentials
        return _shared_client


def _credentials() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if url and key:
        return url, key

    secrets_path = os.path.join(ROOT_DIR, ".streamlit", "secrets.toml")
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


def _event_to_row(event: dict) -> dict:
    return {
        "id": event.get("id"),
        "baby": event.get("baby"),
        "kind": event.get("kind"),
        "amount_ml": event.get("amount_ml"),
        "note": event.get("note") or "",
        "event_ts": event.get("event_ts"),
        "day": event.get("day"),
        "created_at": event.get("created_at"),
    }


def _row_to_event(row: dict) -> dict:
    return _normalise_event(
        {
            "id": row.get("id"),
            "baby": row.get("baby"),
            "kind": row.get("kind"),
            "amount_ml": row.get("amount_ml"),
            "note": row.get("note") or "",
            "event_ts": row.get("event_ts"),
            "day": row.get("day"),
            "created_at": row.get("created_at"),
        }
    )


def _normalise_event(event: dict) -> dict:
    event = dict(event)
    event["id"] = str(event.get("id") or uuid.uuid4().hex)
    event["baby"] = str(event.get("baby") or "a")
    event["kind"] = str(event.get("kind") or "other")
    if event.get("amount_ml") in ("", None):
        event["amount_ml"] = None
    else:
        try:
            event["amount_ml"] = int(float(event.get("amount_ml")))
        except (TypeError, ValueError):
            event["amount_ml"] = None
    event["note"] = str(event.get("note") or "")
    event["event_ts"] = str(event.get("event_ts") or datetime.now(MEL).isoformat(timespec="seconds"))
    event["day"] = str(event.get("day") or event["event_ts"][:10])
    event["created_at"] = str(event.get("created_at") or event["event_ts"])
    return event


def _normalise_details(details: dict, day: str, baby: str) -> dict:
    details = dict(details) if isinstance(details, dict) else {}
    return {
        "day": day,
        "baby": baby,
        "bath_time": str(details.get("bath_time") or ""),
        "length": str(details.get("length") or ""),
        "weight": str(details.get("weight") or ""),
        "notes": str(details.get("notes") or ""),
        "updated_at": str(details.get("updated_at") or ""),
    }
