from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import base64
import html
import os
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

import baby_log_store
import buggins_auth
import buggins_pwa


STANDALONE = (os.getenv("BUGGINS_STANDALONE") or "").strip().lower() in {"1", "true", "yes", "on"}
if not STANDALONE:
    import chrome

st.set_page_config(
    page_title="Buggins Daily Log",
    page_icon="baby",
    layout="wide",
    initial_sidebar_state="collapsed",
)
if STANDALONE:
    buggins_pwa.install()
buggins_auth.require_auth()
if not STANDALONE:
    chrome.render_header("BUGGINS DAILY", "LOG", "")

MEL = ZoneInfo("Australia/Melbourne")
BABIES = [("a", "Baby A"), ("b", "Baby B")]
KINDS = [
    ("left", "L"),
    ("right", "R"),
    ("bottle", "Bottle"),
    ("pee", "Pee"),
    ("poop", "Poop"),
    ("sleep", "Sleep"),
    ("other", "Other"),
]
KIND_LABELS = dict(KINDS)
BOTTLE_AMOUNTS = (30, 60, 90, 120)
FEED_KINDS = {"left", "right", "bottle"}
CHANGE_KINDS = {"pee", "poop"}
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_ASSET_VERSION = "2026-07-watercolor-v4-title"
ICON_FILES = {
    "left": "baby-feed-left.svg",
    "right": "baby-feed-right.svg",
    "bottle": "baby-bottle-watercolor.png",
    "feed_kpi": "baby-feed-bottle-kpi.png",
    "pee": "baby-pee-watercolor.png",
    "poop": "baby-poop-watercolor.png",
    "sleep": "baby-sleep-watercolor-v2.png",
    "sleep_kpi": "baby-sleep-pillow.png",
    "other": "baby-rattle-watercolor-v2.png",
    "nappy": "baby-nappy.png",
    "bath": "baby-bathtub.png",
    "check": "baby-check.svg",
    "time_clock": "baby-time-clock.svg",
    "time_night": "baby-time-night.svg",
    "time_sunrise": "baby-time-sunrise.svg",
    "time_daylight": "baby-time-daylight.svg",
    "time_day_evening": "baby-time-day-evening.svg",
    "title_bun_left": "buns-left-header.png",
    "title_bun_right": "buns-right-header.png",
    "title_koala": "baby-title-koala.png",
    "title_echidna": "baby-title-echidna.png",
}


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def parse_dt(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(MEL)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MEL)
    return parsed.astimezone(MEL)


def fmt_time(value: str) -> str:
    return parse_dt(value).strftime("%H:%M")


def fmt_sheet_time(value: str) -> str:
    return parse_dt(value).strftime("%I:%M %p").lstrip("0")


@st.cache_data(show_spinner=False)
def _cached_icon_data_uri(kind: str, asset_version: str) -> str:
    _ = asset_version
    filename = ICON_FILES.get(kind)
    if not filename:
        return ""
    path = os.path.join(ROOT_DIR, "assets", filename)
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""
    ext = os.path.splitext(filename)[1].lower()
    mime = "image/png" if ext == ".png" else "image/svg+xml"
    return f"data:{mime};base64,{encoded}"


def icon_data_uri(kind: str) -> str:
    return _cached_icon_data_uri(kind, ICON_ASSET_VERSION)


def header_label(kind: str, label: str) -> str:
    icon = icon_data_uri(kind)
    if kind == "left":
        return (
            "<span class='bl-lr-letter left'>L</span>"
            + (f"<span class='bl-shared-feed-icon'><img src='{icon}' alt='Breastfeeding'></span>" if icon else "")
        )
    if kind == "right":
        return "<span class='bl-lr-letter right'>R</span>"
    if not icon:
        return esc(label)
    return (
        f"<span class='bl-headicon {esc(kind)}'><img src='{icon}' alt='{esc(label)}'>"
        + "</span>"
    )


def time_header_label() -> str:
    icon = icon_data_uri("time_clock")
    if not icon:
        return ""
    return f"<span class='bl-time-head'><img src='{icon}' alt='Time'></span>"


def time_marker_kind(hour: int) -> str:
    if hour < 6 or hour >= 20:
        return "time_night"
    if hour < 9:
        return "time_sunrise"
    if hour < 18:
        return "time_daylight"
    return "time_day_evening"


def time_cell_label(hour: int, has_events: bool) -> str:
    icon = icon_data_uri(time_marker_kind(hour))
    marker = f"<span class='bl-time-marker'><img src='{icon}' alt=''></span>" if icon else ""
    time_cls = " has-event" if has_events else ""
    return f"<div class='bl-time{time_cls}'>{marker}<span>{esc(row_time_label([], hour))}</span></div>"


def sleep_cell_fill(sleep_class: str) -> str:
    if not sleep_class:
        return ""
    return f"<span class='bl-sleep-implied {esc(sleep_class)}'><span class='bl-sleep-fill'></span></span>"


def event_label(event: dict) -> str:
    label = KIND_LABELS.get(event.get("kind"), "Other")
    if event.get("kind") == "bath":
        return "Bath time"
    if event.get("kind") == "left":
        return "Breast fed, left side"
    if event.get("kind") == "right":
        return "Breast fed, right side"
    if event.get("kind") == "bottle" and event.get("amount_ml"):
        return f"Bottle fed, {event['amount_ml']} ml"
    if event.get("kind") == "bottle":
        return "Bottle fed"
    if event.get("kind") == "pee":
        return "Nappy changed, pee"
    if event.get("kind") == "poop":
        return "Nappy changed, poop"
    return label


def cell_event_label(event: dict) -> str:
    if event.get("kind") == "bottle" and event.get("amount_ml"):
        return f"<b class='bl-chip-amount'>{esc(event.get('amount_ml'))} ml</b>"
    icon = icon_data_uri("check")
    if not icon:
        return "✓"
    return f"<img src='{icon}' alt='Done'>"


def event_class(kind: str) -> str:
    if kind in ("left", "right", "bottle"):
        return "feed"
    if kind in ("pee", "poop"):
        return "change"
    if kind == "sleep":
        return "sleep"
    return "other"


def metric_card(kind: str, label: str, value: str, sublabel: str) -> str:
    icon = icon_data_uri(kind)
    icon_html = f"<img src='{icon}' alt='{esc(label)}'>" if icon else ""
    return (
        f"<div class='bl-metric {esc(kind)}'>"
        f"<div class='bl-metric-icon'>{icon_html}</div>"
        f"<div><span>{esc(label)}</span><b>{esc(value)}</b><small>{esc(sublabel)}</small></div>"
        "</div>"
    )


def metric_group_card(
    kind: str,
    label: str,
    rows: list[tuple[str, str, str]],
    footer: str = "",
    secondary_kind: str | None = None,
) -> str:
    icon = icon_data_uri(kind)
    secondary_icon = icon_data_uri(secondary_kind) if secondary_kind else ""
    icon_html = "".join(
        [
            f"<img src='{icon}' alt='{esc(label)}'>" if icon else "",
            f"<img src='{secondary_icon}' alt='' class='secondary'>" if secondary_icon else "",
        ]
    )
    row_html = "".join(
        f"<div class='bl-metric-line'><span>{esc(text)}</span><b>{esc(value)}</b>"
        + (f"<small>{esc(unit)}</small>" if unit else "")
        + "</div>"
        for text, value, unit in rows
    )
    footer_html = f"<em>{esc(footer)}</em>" if footer else ""
    return (
        f"<div class='bl-metric bl-metric-group {esc(kind)}'>"
        f"<div class='bl-metric-icons'>{icon_html}</div>"
        f"<div class='bl-metric-body'><strong>{esc(label)}</strong><div class='bl-metric-lines'>{row_html}</div>"
        f"{footer_html}</div>"
        "</div>"
    )


def metric_simple_card(kind: str, label: str, value: str, sublabel: str = "") -> str:
    icon = icon_data_uri(kind)
    icon_html = f"<img src='{icon}' alt='{esc(label)}'>" if icon else ""
    sublabel_html = f"<small>{esc(sublabel)}</small>" if sublabel else ""
    return (
        f"<div class='bl-metric bl-metric-simple {esc(kind)}'>"
        f"<div class='bl-metric-icons'>{icon_html}</div>"
        f"<div class='bl-metric-body'><strong>{esc(label)}</strong>"
        f"<div class='bl-metric-total'>{sublabel_html}<b>{esc(value)}</b></div></div>"
        "</div>"
    )


def care_details_card(bath_time: str = "") -> str:
    bath_icon = icon_data_uri("bath")
    bath_html = f"<img src='{bath_icon}' alt='Bath'>" if bath_icon else ""
    bath_time_html = esc(bath_time) if bath_time else ""
    return f"""
<div class='bl-care'>
  <div class='bl-care-title'>
    <div><span>Care Details</span></div>
  </div>
  <div class='bl-care-rule'></div>
  <div class='bl-care-row bath'>
    <span>Bath time</span>
    <b>{bath_time_html}</b>
    <i>{bath_html}</i>
  </div>
  <div class='bl-care-rule'></div>
  <div class='bl-care-row measures'>
    <span>Length</span>
    <b></b>
    <span>Weight</span>
    <b></b>
  </div>
  <div class='bl-care-rule'></div>
  <div class='bl-care-row notes'>
    <span>Notes</span>
    <b></b>
  </div>
</div>
"""


def selected_day() -> date:
    if "boys_log_day" not in st.session_state:
        st.session_state.boys_log_day = datetime.now(MEL).date()
    if "bl_date_picker" not in st.session_state:
        st.session_state.bl_date_picker = st.session_state.boys_log_day
    return st.session_state.boys_log_day


def set_day(value: date) -> None:
    st.session_state.boys_log_day = value
    st.session_state.bl_date_picker = value


def shift_day(days: int) -> None:
    set_day(selected_day() + timedelta(days=days))


def use_today() -> None:
    set_day(datetime.now(MEL).date())


def sync_day_from_picker() -> None:
    picked = st.session_state.get("bl_date_picker")
    if isinstance(picked, date):
        st.session_state.boys_log_day = picked


def log_event(baby: str, kind: str, amount_ml: int | None = None, note: str = "") -> None:
    baby_log_store.add_event(baby, kind, amount_ml=amount_ml, note=note)
    st.toast(f"Logged {KIND_LABELS.get(kind, kind)} for {dict(BABIES).get(baby, baby)}")


def toggle_cell_event(baby: str, kind: str, hour: int, amount_ml: int | None = None) -> None:
    day = selected_day().isoformat()
    existing = [
        event
        for event in baby_log_store.load_events(day)
        if event.get("baby") == baby
        and event.get("kind") == kind
        and parse_dt(event.get("event_ts")).hour == hour
    ]
    if existing:
        baby_log_store.delete_events_for_hour(day, baby, kind, hour)
        st.toast(f"Cleared {KIND_LABELS.get(kind, kind)} at {hour_label(hour)}")
        return

    now = datetime.now(MEL)
    event_ts = datetime.combine(selected_day(), datetime.min.time(), tzinfo=MEL).replace(
        hour=hour,
        minute=now.minute,
        second=now.second,
        microsecond=0,
    )
    baby_log_store.add_event(baby, kind, amount_ml=amount_ml, event_ts=event_ts)
    st.toast(f"Logged {KIND_LABELS.get(kind, kind)} at {event_ts.strftime('%H:%M')}")


def open_bottle_picker(baby: str, hour: int) -> None:
    st.session_state.boys_log_bottle_picker = (baby, hour)


def log_bottle_picker(baby: str, hour: int) -> None:
    key = f"bl_bottle_picker_{baby}_{hour}"
    selected = st.session_state.get(key)
    if not selected:
        return
    amount = int(str(selected).split()[0])
    day = selected_day().isoformat()
    baby_log_store.delete_events_for_hour(day, baby, "bottle", hour)
    now = datetime.now(MEL)
    event_ts = datetime.combine(selected_day(), datetime.min.time(), tzinfo=MEL).replace(
        hour=hour,
        minute=now.minute,
        second=now.second,
        microsecond=0,
    )
    baby_log_store.add_event(baby, "bottle", amount_ml=amount, event_ts=event_ts)
    st.session_state.boys_log_bottle_picker = None
    st.toast(f"Logged {amount} ml at {event_ts.strftime('%H:%M')}")


def choose_bottle_amount(baby: str, hour: int, amount: int | None) -> None:
    day = selected_day().isoformat()
    baby_log_store.delete_events_for_hour(day, baby, "bottle", hour)
    st.session_state.boys_log_bottle_picker = None
    if amount is None:
        st.toast(f"Cleared Bottle at {hour_label(hour)}")
        return
    now = datetime.now(MEL)
    event_ts = datetime.combine(selected_day(), datetime.min.time(), tzinfo=MEL).replace(
        hour=hour,
        minute=now.minute,
        second=now.second,
        microsecond=0,
    )
    baby_log_store.add_event(baby, "bottle", amount_ml=amount, event_ts=event_ts)
    st.toast(f"Logged {amount} ml at {event_ts.strftime('%H:%M')}")


def log_bath_time(baby: str) -> None:
    day = selected_day().isoformat()
    existing = [event for event in baby_log_store.load_events(day) if event.get("baby") == baby and event.get("kind") == "bath"]
    if existing:
        for event in existing:
            baby_log_store.delete_event(event.get("id"))
        baby_log_store.save_care_details(day, baby, {"bath_time": ""})
        st.session_state[f"bl_care_bath_time_{baby}"] = ""
        st.toast("Cleared bath time")
        return

    now = datetime.now(MEL)
    event_ts = datetime.combine(selected_day(), datetime.min.time(), tzinfo=MEL).replace(
        hour=now.hour,
        minute=now.minute,
        second=now.second,
        microsecond=0,
    )
    baby_log_store.add_event(baby, "bath", event_ts=event_ts)
    bath_time = fmt_sheet_time(event_ts.isoformat())
    baby_log_store.save_care_details(day, baby, {"bath_time": bath_time})
    st.session_state[f"bl_care_bath_time_{baby}"] = bath_time
    st.toast(f"Logged bath time at {event_ts.strftime('%H:%M')}")


def strip_care_unit(value: str, unit: str) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered.endswith(unit):
        return cleaned[:-len(unit)].strip()
    return cleaned


def save_care_field(baby: str, field: str) -> None:
    key = f"bl_care_{field}_{baby}"
    value = st.session_state.get(key, "")
    if field == "length":
        value = strip_care_unit(value, "cm")
        st.session_state[key] = value
    elif field == "weight":
        value = strip_care_unit(value, "kg")
        st.session_state[key] = value
    baby_log_store.save_care_details(selected_day().isoformat(), baby, {field: value})


def toggle_baby_panel(baby: str) -> None:
    key = f"bl_panel_open_{baby}"
    st.session_state[key] = not st.session_state.get(key, False)


def client_is_phone(user_agent: str) -> bool:
    user_agent = str(user_agent or "").lower()
    return any(marker in user_agent for marker in ("iphone", "ipod", "windows phone")) or (
        "android" in user_agent and "mobile" in user_agent
    )


def default_baby_panels_open() -> bool:
    try:
        headers = getattr(st.context, "headers", {}) or {}
        user_agent = headers.get("User-Agent") or headers.get("user-agent") or ""
    except Exception:
        user_agent = ""
    return not client_is_phone(str(user_agent))


def initialise_baby_panels() -> None:
    defaults_key = "bl_panel_defaults_desktop_tablet_v1"
    if st.session_state.get(defaults_key):
        return
    is_open = default_baby_panels_open()
    for baby, _ in BABIES:
        st.session_state[f"bl_panel_open_{baby}"] = is_open
    st.session_state[defaults_key] = True


def totals(events: list[dict], baby: str) -> dict:
    baby_events = [event for event in events if event.get("baby") == baby]
    bottle_total = sum(int(event.get("amount_ml") or 0) for event in baby_events if event.get("kind") == "bottle")
    breastfed = sum(1 for event in baby_events if event.get("kind") in ("left", "right"))
    return {
        "feeds": sum(1 for event in baby_events if event.get("kind") in FEED_KINDS),
        "breastfed": breastfed,
        "bottle": bottle_total,
        "pee": sum(1 for event in baby_events if event.get("kind") == "pee"),
        "poop": sum(1 for event in baby_events if event.get("kind") == "poop"),
        "sleep": sum(1 for event in baby_events if event.get("kind") == "sleep"),
        "last": max((parse_dt(event.get("event_ts")) for event in baby_events), default=None),
    }


def hour_label(hour: int) -> str:
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def row_time_label(events_for_hour: list[dict], hour: int) -> str:
    return hour_label(hour)


def sleep_block_summary(events: list[dict], baby: str, day: date) -> tuple[int, dict[int, str]]:
    """Treat gaps without recorded care activity as inferred sleep."""
    baby_events = sorted(
        [event for event in events if event.get("baby") == baby],
        key=lambda event: parse_dt(event.get("event_ts")),
    )
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=MEL)
    day_end = day_start + timedelta(days=1)
    now = datetime.now(MEL)
    if day == now.date():
        cutoff = min(now, day_end)
    elif day < now.date():
        cutoff = day_end
    else:
        return 0, {}

    event_times = [parse_dt(event.get("event_ts")) for event in baby_events]
    active_hours = {event_time.hour for event_time in event_times if day_start <= event_time < day_end}
    sleep_classes: dict[int, str] = {}
    total_seconds = 0
    hour = 0

    while hour < 24:
        hour_start = day_start + timedelta(hours=hour)
        if hour in active_hours or hour_start >= cutoff:
            hour += 1
            continue

        block_start_hour = hour
        while hour < 24:
            next_hour_start = day_start + timedelta(hours=hour)
            if hour in active_hours or next_hour_start >= cutoff:
                break
            hour += 1
        block_end_hour = hour - 1
        block_start = day_start + timedelta(hours=block_start_hour)
        block_end = min(day_start + timedelta(hours=block_end_hour + 1), cutoff)

        previous_events = [event_time for event_time in event_times if event_time < block_start]
        next_events = [event_time for event_time in event_times if event_time > block_end]
        sleep_start = max(previous_events) if previous_events else block_start
        sleep_end = min(next_events) if next_events else block_end
        sleep_start = max(sleep_start, day_start)
        sleep_end = min(sleep_end, cutoff)
        if sleep_end > sleep_start:
            total_seconds += int((sleep_end - sleep_start).total_seconds())

        for sleep_hour in range(block_start_hour, block_end_hour + 1):
            parts = ["sleep-implied", f"sleep-stars-{sleep_hour % 4}"]
            if sleep_hour == block_start_hour:
                parts.append("sleep-start")
            if sleep_hour == block_end_hour:
                parts.append("sleep-end")
            sleep_classes[sleep_hour] = " ".join(parts)

    return total_seconds, sleep_classes


def format_sleep_duration(total_seconds: int) -> tuple[str, str]:
    minutes = max(0, round(total_seconds / 60))
    hours, mins = divmod(minutes, 60)
    if hours:
        return f"{hours}h {mins:02d}m", ""
    return f"{mins}m", ""


def toggle_dashboard_view() -> None:
    current = st.session_state.get("boys_log_view", "log")
    st.session_state["boys_log_view"] = "log" if current == "analytics" else "analytics"


def numeric_measurement(value) -> float | None:
    cleaned = "".join(char for char in str(value or "") if char.isdigit() or char in ".-")
    if not cleaned or cleaned in {".", "-", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_measurement(value: float | None, unit: str) -> str:
    if value is None:
        return "Not recorded"
    shown = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{shown} {unit}"


def analytics_data(end_day: date) -> dict:
    days = [end_day - timedelta(days=offset) for offset in range(6, -1, -1)]
    start_day = days[0].isoformat()
    end_day_text = days[-1].isoformat()
    events = baby_log_store.load_events_range(start_day, end_day_text)
    care_records = baby_log_store.load_care_details_range(start_day, end_day_text)
    daily: dict[str, list[dict]] = {baby: [] for baby, _ in BABIES}
    hour_counts: dict[str, list[int]] = {baby: [0] * 24 for baby, _ in BABIES}

    for baby, _ in BABIES:
        for day_value in days:
            day_events = [
                event
                for event in events
                if event.get("baby") == baby and event.get("day") == day_value.isoformat()
            ]
            if day_value < datetime.now(MEL).date() and not day_events:
                sleep_seconds = 0
            else:
                sleep_seconds, _ = sleep_block_summary(day_events, baby, day_value)
            entry = {
                "day": day_value,
                "feeds": sum(1 for event in day_events if event.get("kind") in FEED_KINDS),
                "breastfeeds": sum(1 for event in day_events if event.get("kind") in {"left", "right"}),
                "bottle_ml": sum(
                    int(event.get("amount_ml") or 0)
                    for event in day_events
                    if event.get("kind") == "bottle"
                ),
                "pee": sum(1 for event in day_events if event.get("kind") == "pee"),
                "poop": sum(1 for event in day_events if event.get("kind") == "poop"),
                "sleep_seconds": sleep_seconds,
            }
            daily[baby].append(entry)
            for event in day_events:
                if event.get("kind") in FEED_KINDS | CHANGE_KINDS | {"sleep", "other", "bath"}:
                    hour_counts[baby][parse_dt(event.get("event_ts")).hour] += 1

    summaries = {}
    growth = {}
    for baby, _ in BABIES:
        baby_days = daily[baby]
        summaries[baby] = {
            "feeds": sum(item["feeds"] for item in baby_days),
            "breastfeeds": sum(item["breastfeeds"] for item in baby_days),
            "bottle_ml": sum(item["bottle_ml"] for item in baby_days),
            "pee": sum(item["pee"] for item in baby_days),
            "poop": sum(item["poop"] for item in baby_days),
            "sleep_seconds": sum(item["sleep_seconds"] for item in baby_days),
        }
        baby_records = sorted(
            [record for record in care_records if record.get("baby") == baby],
            key=lambda record: record.get("day") or "",
        )
        growth[baby] = {}
        for field, unit in (("weight", "kg"), ("length", "cm")):
            values = [
                (record.get("day"), numeric_measurement(record.get(field)))
                for record in baby_records
            ]
            values = [(record_day, value) for record_day, value in values if value is not None]
            latest = values[-1][1] if values else None
            change = latest - values[0][1] if len(values) > 1 and latest is not None else None
            growth[baby][field] = {"latest": latest, "change": change, "unit": unit}

    return {
        "days": days,
        "events": events,
        "care_records": care_records,
        "daily": daily,
        "summaries": summaries,
        "hour_counts": hour_counts,
        "growth": growth,
    }


def grouped_bar_chart(data: dict, key: str, value_label) -> str:
    maximum = max(
        [item[key] for baby, _ in BABIES for item in data["daily"][baby]] + [1]
    )
    groups = []
    for index, day_value in enumerate(data["days"]):
        bars = []
        for baby, _ in BABIES:
            value = data["daily"][baby][index][key]
            height = 3 if value <= 0 else max(8, round((value / maximum) * 100))
            bars.append(
                f"<span class='ba-bar ba-{baby}' style='height:{height}%' title='{esc(value_label(value))}'></span>"
            )
        groups.append(
            "<div class='ba-bar-group'><div class='ba-bar-pair'>"
            + "".join(bars)
            + f"</div><small>{esc(day_value.strftime('%a'))}</small></div>"
        )
    return "<div class='ba-chart'>" + "".join(groups) + "</div>"


def rhythm_row(hour_counts: list[int], baby: str, label: str) -> str:
    maximum = max(hour_counts + [1])
    cells = "".join(
        f"<span class='ba-rhythm-cell ba-{baby}' style='opacity:{0.12 + (count / maximum) * 0.88:.2f}' title='{hour_label(hour)}: {count} activities'></span>"
        for hour, count in enumerate(hour_counts)
    )
    return (
        f"<div class='ba-rhythm-row'><b>{esc(label)}</b><div class='ba-rhythm-cells'>{cells}</div></div>"
    )


def analytics_dashboard_html(end_day: date) -> str:
    data = analytics_data(end_day)
    summaries = data["summaries"]
    sleep_text = {
        baby: format_sleep_duration(summaries[baby]["sleep_seconds"])[0]
        for baby, _ in BABIES
    }
    range_label = f"{data['days'][0].strftime('%d %b')} – {data['days'][-1].strftime('%d %b %Y')}"
    comparison_rows = [
        ("Total feeds", str(summaries["a"]["feeds"]), str(summaries["b"]["feeds"])),
        ("Breastfeeds", str(summaries["a"]["breastfeeds"]), str(summaries["b"]["breastfeeds"])),
        ("Bottle volume", f"{summaries['a']['bottle_ml']} ml", f"{summaries['b']['bottle_ml']} ml"),
        ("Total sleep", sleep_text["a"], sleep_text["b"]),
        (
            "Nappy changes",
            str(summaries["a"]["pee"] + summaries["a"]["poop"]),
            str(summaries["b"]["pee"] + summaries["b"]["poop"]),
        ),
    ]
    comparison_html = "".join(
        f"<div class='ba-compare-row'><span>{esc(label)}</span><b class='ba-a'>{esc(a_value)}</b><b class='ba-b'>{esc(b_value)}</b></div>"
        for label, a_value, b_value in comparison_rows
    )
    feed_chart = grouped_bar_chart(data, "bottle_ml", lambda value: f"{value} ml")
    sleep_chart = grouped_bar_chart(
        data,
        "sleep_seconds",
        lambda value: format_sleep_duration(value)[0],
    )
    nappy_max = max(
        summaries["a"]["pee"], summaries["a"]["poop"], summaries["b"]["pee"], summaries["b"]["poop"], 1
    )
    nappy_rows = "".join(
        f"<div class='ba-nappy-row'><b>{esc(label)}</b>"
        f"<div><span>Pee</span><i><em class='ba-{baby}' style='width:{round(summaries[baby]['pee'] / nappy_max * 100)}%'></em></i><strong>{summaries[baby]['pee']}</strong></div>"
        f"<div><span>Poop</span><i><em class='ba-{baby}' style='width:{round(summaries[baby]['poop'] / nappy_max * 100)}%'></em></i><strong>{summaries[baby]['poop']}</strong></div></div>"
        for baby, label in BABIES
    )
    rhythm_html = "".join(
        rhythm_row(data["hour_counts"][baby], baby, label)
        for baby, label in BABIES
    )
    growth_cards = []
    for baby, label in BABIES:
        fields = data["growth"][baby]
        metric_html = "".join(
            f"<div><span>{esc(field.title())}</span><b>{esc(format_measurement(fields[field]['latest'], fields[field]['unit']))}</b>"
            + (
                f"<small>{fields[field]['change']:+.1f} {fields[field]['unit']} in 7 days</small>"
                if fields[field]["change"] is not None
                else "<small>No 7-day change yet</small>"
            )
            + "</div>"
            for field in ("weight", "length")
        )
        growth_cards.append(
            f"<div class='ba-growth-baby ba-{baby}'><b class='ba-baby-title'>{esc(label)}</b>{metric_html}</div>"
        )
    unique_days = len({event.get("day") for event in data["events"] if event.get("day")})
    total_feeds = summaries["a"]["feeds"] + summaries["b"]["feeds"]
    total_bottle = summaries["a"]["bottle_ml"] + summaries["b"]["bottle_ml"]
    has_growth = any(
        data["growth"][baby][field]["latest"] is not None
        for baby, _ in BABIES
        for field in ("weight", "length")
    )
    milestones = [
        ("Tracking started", 1 if data["events"] else 0, 1),
        ("10 feeds recorded", total_feeds, 10),
        ("1,000 ml bottle volume", total_bottle, 1000),
        ("First growth check", 1 if has_growth else 0, 1),
        ("Seven days recorded", unique_days, 7),
    ]
    milestone_html = "".join(
        f"<div class='ba-milestone {'achieved' if value >= target else ''}'><span>{'✓' if value >= target else '○'}</span>"
        f"<div><b>{esc(label)}</b><small>{'Achieved' if value >= target else f'{value} of {target}'}</small>"
        f"<i><em style='width:{min(100, round(value / target * 100))}%'></em></i></div></div>"
        for label, value, target in milestones
    )
    return f"""
<div class='ba-shell'>
  <section class='ba-hero'>
    <div><span>7-day analytics</span><b class='ba-title'>Twin care overview</b><p>{esc(range_label)}</p></div>
    <div class='ba-legend'><span class='ba-a'>Baby A</span><span class='ba-b'>Baby B</span></div>
  </section>
  <div class='ba-grid'>
    <section class='ba-card ba-wide'>
      <div class='ba-card-head'><div><span>Comparison</span><b class='ba-card-title'>Twin comparison</b></div><small>7 days</small></div>
      <div class='ba-compare-head'><span></span><b>Baby A</b><b>Baby B</b></div>
      <div class='ba-compare'>{comparison_html}</div>
    </section>
    <section class='ba-card'>
      <div class='ba-card-head'><div><span>Feeding</span><b class='ba-card-title'>7-day daily feed volume</b></div></div>
      <p class='ba-note'>Recorded bottle volume only; breastfeeds are counted separately.</p>
      {feed_chart}
      <div class='ba-chart-foot'><span>Baby A: <b>{summaries['a']['bottle_ml']} ml</b></span><span>Baby B: <b>{summaries['b']['bottle_ml']} ml</b></span></div>
    </section>
    <section class='ba-card'>
      <div class='ba-card-head'><div><span>Rest</span><b class='ba-card-title'>Total sleep</b></div></div>
      <p class='ba-note'>Inferred from inactive periods; untracked past days remain at zero.</p>
      {sleep_chart}
      <div class='ba-chart-foot'><span>Baby A: <b>{sleep_text['a']}</b></span><span>Baby B: <b>{sleep_text['b']}</b></span></div>
    </section>
    <section class='ba-card'>
      <div class='ba-card-head'><div><span>Care</span><b class='ba-card-title'>Nappy summary</b></div><small>7 days</small></div>
      <div class='ba-nappy'>{nappy_rows}</div>
    </section>
    <section class='ba-card ba-wide'>
      <div class='ba-card-head'><div><span>Pattern</span><b class='ba-card-title'>Daily rhythm</b></div><small>All logged activity</small></div>
      <div class='ba-rhythm'>{rhythm_html}<div class='ba-rhythm-labels'><span>12am</span><span>6am</span><span>12pm</span><span>6pm</span><span>11pm</span></div></div>
    </section>
    <section class='ba-card'>
      <div class='ba-card-head'><div><span>Measurements</span><b class='ba-card-title'>Growth overview</b></div><small>Latest in range</small></div>
      <div class='ba-growth'>{''.join(growth_cards)}</div>
    </section>
    <section class='ba-card'>
      <div class='ba-card-head'><div><span>Achievements</span><b class='ba-card-title'>Milestones</b></div><small>From logged records</small></div>
      <div class='ba-milestones'>{milestone_html}</div>
    </section>
  </div>
</div>
"""


st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"],.stApp{background:#fff!important;background-image:none!important;}
[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:transparent!important;}
.st-key-topnav a,.st-key-topnav a p,.st-key-topnav a span{color:#526784!important;}
.st-key-topnav a[data-testid="stPageLink-NavLink"][aria-current="page"],.st-key-topnav a:hover{background:rgba(82,103,132,.10)!important;color:#173664!important;}
.st-key-brandrow{display:none!important;}
.bl-mobile-title{display:none;}
.bl-shell{max-width:1500px;margin:-30px auto 0;padding:0 10px 30px;color:#14315f;}
.bl-toolbar{display:grid;grid-template-columns:auto 1fr auto auto auto;gap:10px;align-items:center;margin-bottom:14px;}
.bl-date{border:1px solid #dce6f3;background:#fff;border-radius:12px;padding:12px 15px;color:#173664;font-size:18px;font-weight:950;text-align:center;box-shadow:0 12px 30px rgba(61,95,140,.08);}
.st-key-bl_date_control{position:relative;min-height:46px;}
.bl-date-display{height:46px;border:1px solid #dce6f3;background:#fff;border-radius:12px;color:#173664;font-size:18px;font-weight:950;text-align:center;box-shadow:0 12px 30px rgba(61,95,140,.08);display:flex;align-items:center;justify-content:center;white-space:nowrap;}
.bl-date-short{display:none;}
.st-key-bl_date_control .stDateInput{position:absolute!important;inset:0!important;opacity:0!important;z-index:2!important;margin:0!important;}
.st-key-bl_date_control .stDateInput *{cursor:pointer!important;}
.stDateInput input{background:#fff!important;border:1px solid #dce6f3!important;color:#173664!important;border-radius:12px!important;height:46px!important;box-shadow:0 12px 30px rgba(61,95,140,.08)!important;font-weight:900!important;}
.stDateInput [data-baseweb="input"]{background:#fff!important;border-color:#dce6f3!important;border-radius:12px!important;}
.bl-sync{border:1px solid #dce6f3;background:#fff;border-radius:12px;padding:10px 12px;color:#7184a4;font-size:11px;font-weight:850;text-transform:uppercase;letter-spacing:.06em;text-align:right;box-shadow:0 10px 24px rgba(61,95,140,.07);}
.bl-mel{color:#7c8eaa;font-size:10px;font-weight:850;letter-spacing:.08em;text-transform:uppercase;margin-top:6px;text-align:right;}
.bl-twins{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;}
.st-key-bl_panel_a,.st-key-bl_panel_b{position:relative;border:1px solid #dfe8f4;border-radius:20px;padding:14px;min-width:0;box-shadow:0 18px 48px rgba(61,95,140,.08);overflow:visible;}
.st-key-bl_panel_a{border-color:#d7e8fb;background:linear-gradient(135deg,rgba(236,246,255,.98),rgba(249,252,255,.78));}
.st-key-bl_panel_b{border-color:#d8eadf;background:linear-gradient(135deg,rgba(240,250,244,.98),rgba(249,253,250,.78));}
.bl-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin:0 0 10px;}
.bl-title{color:#163767;font-size:25px;font-weight:950;line-height:1;}
.bl-title span{display:block;color:#7184a4;font-size:11px;font-weight:850;letter-spacing:.08em;text-transform:uppercase;margin-top:6px;}
.bl-toggle-pill{position:absolute;top:12px;right:12px;z-index:20;display:inline-flex;align-items:center;border:1px solid #dce6f3;border-radius:999px;background:rgba(255,255,255,.88);color:#7184a4;font-size:10px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;padding:5px 9px;box-shadow:none;pointer-events:none;}
.bl-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:16px;}
.bl-metric{display:grid;grid-template-columns:42px minmax(0,1fr);gap:9px;align-items:center;border:1px solid #dfe8f4;border-radius:16px;background:#fff;padding:10px 10px;min-width:0;box-shadow:0 14px 34px rgba(61,95,140,.09);}
.bl-metric-icon{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#eef5ff;}
.bl-metric-icon img{width:28px;height:28px;object-fit:contain;}
.bl-metric.bottle .bl-metric-icon{background:#e8fbfb;}
.bl-metric.pee .bl-metric-icon{background:#eaf5ff;}
.bl-metric.poop .bl-metric-icon{background:#f6eef8;}
.bl-metric.sleep .bl-metric-icon{background:#fff4d8;}
.bl-metric span{display:block;color:#63779c;font-size:10px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bl-metric b{display:inline-block;color:#112f62;font-size:29px;font-weight:950;line-height:1;margin-top:3px;font-variant-numeric:tabular-nums;}
.bl-metric small{display:inline-block;color:#63779c;font-size:14px;font-weight:850;margin-left:3px;}
.bl-metric-group{grid-template-columns:54px minmax(0,1fr);align-items:center;gap:8px;border-radius:18px;padding:27px 8px 9px;min-height:118px;}
.bl-metric-group.bottle,.bl-metric-simple.feed_kpi{border-color:#cfe0f8;background:linear-gradient(180deg,#fff,#f7fbff);}
.bl-metric-group.nappy{border-color:#cfe0f8;background:linear-gradient(180deg,#fff,#f8fcfa);}
.bl-metric-group.sleep_kpi{border-color:#cfe0f8;background:linear-gradient(180deg,#fff,#fbf8ff);}
.bl-metric-icons{position:relative;display:flex;align-items:center;justify-content:center;min-width:0;}
.bl-metric-icons:before{content:"";position:absolute;width:54px;height:54px;border-radius:50%;background:#eef5ff;left:50%;top:50%;transform:translate(-50%,-50%);}
.bl-metric-group.nappy .bl-metric-icons:before{display:block;width:78px;height:68px;top:50%;background:radial-gradient(circle at 35% 35%,rgba(239,248,255,.95),rgba(218,235,255,.72) 58%,rgba(202,226,252,.28) 100%);border-radius:57% 43% 61% 39% / 45% 58% 42% 55%;filter:blur(.2px);}
.bl-metric-group.sleep_kpi .bl-metric-icons:before{display:none;}
.bl-metric-icons img{position:relative;z-index:1;width:48px;height:48px;object-fit:contain;}
.bl-metric-icons img.secondary{position:absolute;width:35px;height:35px;right:0;bottom:18px;}
.bl-metric-group.nappy .bl-metric-icons img{width:72px;height:72px;max-width:none!important;min-width:72px;transform:scaleX(-1);}
.bl-metric-simple.feed_kpi .bl-metric-icons:before{display:block;width:70px;height:64px;top:50%;background:radial-gradient(circle at 38% 34%,rgba(239,248,255,.95),rgba(216,234,255,.74) 58%,rgba(196,222,252,.28) 100%);border-radius:48% 52% 43% 57% / 55% 44% 56% 45%;filter:blur(.2px);}
.bl-metric-simple.feed_kpi .bl-metric-icons img{width:72px;height:72px;max-width:none!important;min-width:72px;}
.bl-metric-group.sleep_kpi .bl-metric-icons img{width:78px;height:78px;max-width:none!important;min-width:78px;}
.bl-metric-group.nappy,.bl-metric-group.sleep_kpi{position:relative;padding-top:28px;}
.bl-metric-group.nappy .bl-metric-body strong,.bl-metric-group.sleep_kpi .bl-metric-body strong{position:absolute;left:0;right:0;top:8px;text-align:center;}
.bl-metric-simple.feed_kpi{position:relative;padding-top:28px;}
.bl-metric-simple.feed_kpi .bl-metric-body strong{position:absolute;left:0;right:0;top:8px;text-align:center;}
.bl-metric-body{display:flex;flex-direction:column;min-width:0;}
.bl-metric-body strong{display:block;text-align:center;color:#63779c;font-size:12px;font-weight:950;letter-spacing:.07em;text-transform:uppercase;margin:0 0 5px;white-space:nowrap;}
.bl-metric-lines{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:center;gap:4px;min-height:40px;}
.bl-metric-line{min-width:0;text-align:center;border-left:1px solid #dce6f3;}
.bl-metric-line:first-child{border-left:0;}
.bl-metric-line span{display:block;color:#63779c;font-size:9px;font-weight:850;letter-spacing:0;text-transform:none;margin-bottom:2px;white-space:nowrap;}
.bl-metric-line b{display:block;color:#112f62;font-size:20px;font-weight:950;line-height:1;font-variant-numeric:tabular-nums;margin:0;white-space:nowrap;}
.bl-metric-line small{display:block;color:#63779c;font-size:9px;font-weight:850;line-height:1;margin:2px 0 0;white-space:nowrap;}
.bl-metric-group.sleep_kpi .bl-metric-lines{grid-template-columns:1fr;}
.bl-metric-group.sleep_kpi .bl-metric-line{border-left:0;display:flex;flex-wrap:wrap;align-items:baseline;justify-content:center;gap:4px;}
.bl-metric-group.sleep_kpi .bl-metric-line span{display:block;width:100%;margin:0 0 3px;flex-basis:100%;}
.bl-metric-group.sleep_kpi .bl-metric-line b{display:inline-block;font-size:21px;}
.bl-metric-group.sleep_kpi .bl-metric-line small{display:inline-block;font-size:13px;margin:0;color:#63779c;}
.bl-metric-body em{display:block;margin-top:6px;border-radius:999px;background:#eef5ff;color:#4f76b6;font-size:10px;font-style:normal;font-weight:900;text-align:center;padding:4px 6px;white-space:nowrap;}
.bl-metric-group.sleep_kpi .bl-metric-body em{background:#f1eaf8;color:#7655a5;}
.bl-metric-simple{grid-template-columns:64px minmax(0,1fr);}
.bl-metric-simple .bl-metric-body strong{text-align:center;margin-bottom:8px;}
.bl-metric-total{text-align:center;}
.bl-metric-total b{display:inline-block;color:#112f62;font-size:30px;font-weight:950;line-height:1;font-variant-numeric:tabular-nums;margin:0;}
.bl-metric-total small{display:block;color:#63779c;font-size:11px;font-weight:850;line-height:1.1;margin:0 0 4px;white-space:nowrap;}
.bl-toolbar .stButton>button,[class*="st-key-bl_"] .stButton>button{height:46px;border-radius:12px!important;border:1px solid #dce6f3!important;background:#fff!important;color:#173664!important;font-weight:900!important;font-size:13px!important;box-shadow:0 10px 24px rgba(61,95,140,.07)!important;}
.bl-toolbar .stButton>button:active,[class*="st-key-bl_"] .stButton>button:active{transform:scale(.98);}
.st-key-bl_panel_a [class*="st-key-bl_toggle_"],.st-key-bl_panel_b [class*="st-key-bl_toggle_"]{margin:0!important;}
.st-key-bl_panel_a [class*="st-key-bl_toggle_"],.st-key-bl_panel_a [class*="st-key-bl_toggle_"] *,.st-key-bl_panel_b [class*="st-key-bl_toggle_"],.st-key-bl_panel_b [class*="st-key-bl_toggle_"] *{-webkit-tap-highlight-color:transparent!important;box-shadow:none!important;filter:none!important;outline:0!important;}
.st-key-bl_panel_a [class*="st-key-bl_toggle_"] button,.st-key-bl_panel_a [class*="st-key-bl_toggle_"] button:hover,.st-key-bl_panel_a [class*="st-key-bl_toggle_"] button:focus,.st-key-bl_panel_a [class*="st-key-bl_toggle_"] button:focus-visible,.st-key-bl_panel_a [class*="st-key-bl_toggle_"] button:active,.st-key-bl_panel_b [class*="st-key-bl_toggle_"] button,.st-key-bl_panel_b [class*="st-key-bl_toggle_"] button:hover,.st-key-bl_panel_b [class*="st-key-bl_toggle_"] button:focus,.st-key-bl_panel_b [class*="st-key-bl_toggle_"] button:focus-visible,.st-key-bl_panel_b [class*="st-key-bl_toggle_"] button:active{background:transparent!important;border:0!important;box-shadow:none!important;outline:0!important;transform:none!important;}
.st-key-bl_panel_a:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"],.st-key-bl_panel_b:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"]{position:absolute!important;top:12px!important;right:12px!important;z-index:30!important;width:64px!important;height:29px!important;margin:0!important;}
.st-key-bl_panel_a:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"] .stButton,.st-key-bl_panel_b:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"] .stButton{width:auto!important;margin:0!important;}
.st-key-bl_panel_a:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"] .stButton>button,.st-key-bl_panel_b:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"] .stButton>button{width:64px!important;height:29px!important;min-height:29px!important;background:transparent!important;border:0!important;box-shadow:none!important;color:transparent!important;font-size:0!important;padding:0!important;}
.st-key-bl_panel_a:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"] .stButton>button *,.st-key-bl_panel_b:has(.bl-panel-state.open) [class*="st-key-bl_toggle_"] .stButton>button *{color:transparent!important;font-size:0!important;line-height:0!important;}
.st-key-bl_panel_a:has(.bl-panel-state.collapsed),.st-key-bl_panel_b:has(.bl-panel-state.collapsed){cursor:pointer;}
.st-key-bl_panel_a:has(.bl-panel-state.collapsed):before,.st-key-bl_panel_b:has(.bl-panel-state.collapsed):before{content:none;}
.st-key-bl_panel_a:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"],.st-key-bl_panel_b:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"]{position:absolute!important;inset:0!important;z-index:30!important;margin:0!important;width:100%!important;height:100%!important;}
.st-key-bl_panel_a:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] div,.st-key-bl_panel_a:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] span,.st-key-bl_panel_a:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] .stButton,.st-key-bl_panel_a:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] button,.st-key-bl_panel_b:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] div,.st-key-bl_panel_b:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] span,.st-key-bl_panel_b:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] .stButton,.st-key-bl_panel_b:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] button{width:100%!important;height:100%!important;min-height:100%!important;margin:0!important;}
.st-key-bl_panel_a:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] button,.st-key-bl_panel_b:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] button{background:transparent!important;border:0!important;box-shadow:none!important;color:transparent!important;font-size:0!important;padding:0!important;}
.st-key-bl_panel_a:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] button:hover,.st-key-bl_panel_b:has(.bl-panel-state.collapsed) [class*="st-key-bl_toggle_"] button:hover{background:transparent!important;}
.st-key-bl_panel_a [data-testid="stElementContainer"]:has(.bl-grid),.st-key-bl_panel_b [data-testid="stElementContainer"]:has(.bl-grid){position:sticky!important;top:0!important;z-index:50!important;padding-top:10px!important;}
.st-key-bl_panel_a [data-testid="stElementContainer"]:has(.bl-grid),.st-key-bl_panel_b [data-testid="stElementContainer"]:has(.bl-grid){background:#fff!important;}
.st-key-bl_panel_a [data-testid="stElementContainer"]:has(.bl-grid):after,.st-key-bl_panel_b [data-testid="stElementContainer"]:has(.bl-grid):after{display:none!important;}
.bl-grid{border:1px solid #dfe8f4;border-radius:18px;overflow:hidden;background:#fff;margin-top:0;box-shadow:0 18px 46px rgba(61,95,140,.10);}
.bl-grid-baby{height:36px;display:flex;align-items:center;justify-content:center;border-radius:18px 18px 0 0;border-bottom:1px solid #e3ebf5;background:#fff;color:#163767;font-size:14px;font-weight:950;letter-spacing:.05em;text-transform:uppercase;}
.st-key-bl_panel_a .bl-grid-baby,.st-key-bl_panel_b .bl-grid-baby{background:#fff;border-bottom-color:#e3ebf5;}
.bl-grid-head{display:grid;grid-template-columns:1.12fr repeat(7,minmax(0,1fr));border-bottom:1px solid #e3ebf5;border-radius:0 0 16px 16px;overflow:visible;}
.bl-grid-head{background:#fff;}
.bl-grid-head div{position:relative;min-height:70px;padding:13px 5px;color:#173664;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.06em;text-align:center;border-left:1px solid #e3ebf5;display:flex;align-items:center;justify-content:center;}
.bl-grid-head div:first-child{border-left:0;}
.bl-grid-head div:nth-child(3){border-left:0;}
.bl-time-head{display:inline-flex;align-items:center;justify-content:center;gap:7px;}
.bl-time-head img{width:20px;height:20px;object-fit:contain;}
.bl-headicon{height:42px;display:inline-flex;align-items:center;justify-content:center;gap:5px;}
.bl-headicon img{width:34px;height:34px;object-fit:contain;filter:none;}
.bl-headicon.pee img,.bl-headicon.poop img{width:68px!important;height:68px!important;min-width:68px;max-width:none!important;}
.bl-headicon.bottle img{width:65px!important;height:65px!important;min-width:65px;max-width:none!important;}
.bl-headicon.sleep img{width:67px!important;height:67px!important;min-width:67px;max-width:none!important;}
.bl-headicon.other img{width:67px!important;height:67px!important;min-width:67px;max-width:none!important;transform:none;}
.bl-lr-letter{position:absolute;bottom:14px;z-index:6;color:#173664;font-size:20px;font-weight:950;line-height:1;letter-spacing:0;}
.bl-lr-letter.left{left:20px;}
.bl-lr-letter.right{right:20px;}
.bl-shared-feed-icon{position:absolute;left:100%;top:50%;width:78px;height:78px;transform:translate(-50%,-51%);z-index:5;pointer-events:none;display:flex;align-items:center;justify-content:center;}
.bl-shared-feed-icon img{width:78px;height:78px;object-fit:contain;filter:none;}
.bl-row-wrap{border-top:1px solid #e2ebf5;}
.bl-row-wrap.current{background:#fbfdff;}
[class*="st-key-blrow_"] [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:1.12fr repeat(7,minmax(0,1fr))!important;gap:0!important;align-items:stretch!important;}
[class*="st-key-blrow_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{width:auto!important;flex:initial!important;min-width:0!important;padding:0!important;}
.bl-time{position:relative;display:flex;align-items:center;justify-content:center;color:#14315f;font-size:16px;font-weight:950;font-variant-numeric:tabular-nums;background:transparent;padding:4px 3px 4px 28px;text-align:center;line-height:1.1;}
.bl-time-marker{position:absolute;left:0;top:50%;width:28px;height:28px;border-radius:999px;background:#f1f6fc;display:flex;align-items:center;justify-content:center;transform:translateY(-50%);z-index:1;}
.bl-time-marker img{width:21px;height:21px;object-fit:contain;}
.bl-time:before,.bl-time:after{content:"";position:absolute;left:13px;width:2px;background:repeating-linear-gradient(to bottom,#c5d5e8 0 2px,transparent 2px 6px);pointer-events:none;z-index:0;}
.bl-time:before{top:0;bottom:calc(50% + 14px);}
.bl-time:after{top:calc(50% + 14px);bottom:0;}
.bl-time,[class*="st-key-blslot_"]{min-height:50px;}
.bl-time.has-event{color:#14315f;background:transparent;}
.st-key-blgrid_cell,[class*="st-key-blslot_"]{position:relative!important;border-left:1px solid #e3ebf5;padding:0!important;min-width:0;display:flex;align-items:center;justify-content:center;}
[class*="st-key-blslot_"] [class*="st-key-blcell_"]{position:absolute!important;inset:0!important;z-index:3;width:100%!important;height:100%!important;margin:0!important;}
[class*="st-key-blslot_"] [class*="st-key-blcell_"] div,[class*="st-key-blslot_"] [class*="st-key-blcell_"] span,[class*="st-key-blslot_"] [class*="st-key-blcell_"] .stButton{width:100%!important;height:100%!important;margin:0!important;}
[class*="st-key-blslot_"] [class*="st-key-blcell_"] button{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;min-height:100%!important;border-radius:0!important;padding:0!important;background:transparent!important;border:0!important;color:transparent!important;font-size:0!important;line-height:1!important;box-shadow:none!important;outline:0!important;}
[class*="st-key-blslot_"] [class*="st-key-blcell_"] button:hover,[class*="st-key-blslot_"] [class*="st-key-blcell_"] button:focus,[class*="st-key-blslot_"] [class*="st-key-blcell_"] button:active{background:rgba(59,130,246,.045)!important;border:0!important;box-shadow:none!important;outline:0!important;transform:none!important;}
[class*="st-key-blslot_"]:not(:has(.bl-chip)):not(:has(.bl-sleep-implied)):not(:has([class*="st-key-bl_bottle_picker_"])):not(:has([class*="st-key-bl_bottle_menu_"])):after{content:"-";position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#8aa0c0;font-size:18px;font-weight:850;z-index:1;pointer-events:none;}
[class*="st-key-blslot_"] [data-testid="stElementContainer"]:has(.bl-sleep-implied),[class*="st-key-blslot_"] [data-testid="stMarkdown"]:has(.bl-sleep-implied),[class*="st-key-blslot_"] [data-testid="stMarkdownContainer"]:has(.bl-sleep-implied){position:absolute!important;inset:0!important;width:100%!important;height:100%!important;margin:0!important;z-index:5!important;pointer-events:none!important;}
.bl-sleep-implied{position:absolute;inset:0;z-index:5;display:block;pointer-events:none;}
.bl-sleep-fill{position:absolute;left:6px;right:6px;top:-27px;bottom:-27px;border-radius:0;background:radial-gradient(circle at 28% 34%,#ffd977 0 2px,transparent 3px),radial-gradient(circle at 68% 58%,#ffe59b 0 1.8px,transparent 3px),radial-gradient(circle at 48% 74%,#fff1a8 0 1.6px,transparent 3px),linear-gradient(180deg,rgba(239,232,252,.72),rgba(220,209,246,.88),rgba(239,232,252,.72));box-shadow:none;}
.bl-sleep-implied.sleep-start .bl-sleep-fill{top:6px;border-radius:12px 12px 0 0;}
.bl-sleep-implied.sleep-end .bl-sleep-fill{bottom:6px;border-radius:0 0 12px 12px;}
.bl-sleep-implied.sleep-start.sleep-end .bl-sleep-fill{top:6px;bottom:6px;border-radius:12px;}
.bl-chip{position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;background:transparent!important;border:0!important;border-radius:0;padding:0;}
.bl-chip img{width:19px;height:19px;display:block;object-fit:contain;filter:none;}
.bl-chip.feed img,.bl-chip.change img{filter:invert(48%) sepia(42%) saturate(746%) hue-rotate(94deg) brightness(89%) contrast(90%);}
.bl-chip.sleep img{filter:invert(35%) sepia(56%) saturate(821%) hue-rotate(222deg) brightness(88%) contrast(85%);}
.bl-chip-amount{display:block;color:#174f9d;font-size:14px;font-weight:950;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap;}
.bl-chip-time{display:block;color:#6e84a8;font-size:12px;font-weight:900;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap;}
.bl-chip.feed,.bl-chip.change,.bl-chip.sleep,.bl-chip.other{color:inherit;background:transparent!important;border:0!important;}
[class*="st-key-bl_bottle_picker_"]{position:absolute!important;inset:2px!important;z-index:4;width:calc(100% - 4px)!important;min-width:0!important;height:34px!important;margin:0!important;}
[class*="st-key-bl_bottle_picker_"] label{display:none!important;}
[class*="st-key-bl_bottle_picker_"] [data-baseweb="select"]{height:34px!important;width:100%!important;min-width:0!important;}
[class*="st-key-bl_bottle_picker_"] [data-baseweb="select"]>div{min-height:34px!important;height:34px!important;border-radius:6px!important;background:transparent!important;border-color:transparent!important;color:#173664!important;font-size:12px!important;display:flex!important;align-items:center!important;justify-content:center!important;padding:0!important;}
[class*="st-key-bl_bottle_picker_"] [data-baseweb="select"] span{display:none!important;}
[class*="st-key-bl_bottle_picker_"] [data-baseweb="select"] div:has(>svg){position:absolute!important;left:calc(50% + 4px)!important;top:50%!important;width:24px!important;height:24px!important;transform:translate(-50%,-50%)!important;display:flex!important;align-items:center!important;justify-content:center!important;}
[class*="st-key-bl_bottle_picker_"] [data-baseweb="select"] svg{position:static!important;transform:none!important;color:#173664!important;}
[class*="st-key-bl_bottle_menu_"]{position:absolute!important;left:6px!important;right:6px!important;top:3px!important;z-index:8!important;background:#fff!important;border:1px solid #dbe6f5!important;border-radius:9px!important;box-shadow:0 14px 32px rgba(61,95,140,.18)!important;padding:3px!important;margin:0!important;}
[class*="st-key-bl_bottle_menu_"] .stButton{height:auto!important;margin:0!important;}
[class*="st-key-bl_bottle_menu_"] .stButton>button{height:25px!important;min-height:25px!important;border:0!important;border-radius:6px!important;background:#fff!important;box-shadow:none!important;color:#174f9d!important;font-size:12px!important;font-weight:950!important;padding:0 4px!important;}
[class*="st-key-bl_bottle_menu_"] .stButton>button:hover{background:#eef5ff!important;}
.bl-care{position:relative;margin-top:14px;border:1px solid #cfe0f8;border-radius:18px;background:#fbfdff;padding:18px 22px 16px;overflow:hidden;box-shadow:0 12px 30px rgba(61,95,140,.06);}
.bl-care-title{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;}
.bl-care-title span{display:block;color:#63779c;font-size:12px;font-weight:950;letter-spacing:.07em;text-transform:uppercase;line-height:1;}
.bl-care-rule{position:relative;z-index:1;height:2px;background:#dfe8f4;margin:0;}
.bl-care-row{position:relative;z-index:1;display:grid;align-items:center;gap:10px;min-height:54px;}
.bl-care-row.bath{grid-template-columns:92px minmax(0,1fr) 124px;}
.bl-care-row.measures{grid-template-columns:92px minmax(0,1fr) 100px 118px;}
.bl-care-row.notes{grid-template-columns:92px minmax(0,1fr);}
.bl-care-row span{color:#6f83a3;font-size:15px;font-weight:900;line-height:1;white-space:nowrap;}
.bl-care-row.measures span:last-of-type{text-align:center;}
.bl-care-row b{color:#173664;font-size:16px;font-weight:400;line-height:1.15;white-space:nowrap;}
.bl-care-row.notes b{font-size:16px;font-weight:400;white-space:normal;}
.bl-care-row.bath i{display:flex;align-items:center;justify-content:center;width:124px;height:64px;margin:-10px 0 -2px;font-style:normal;}
.bl-care-row.bath img{width:120px;height:64px;object-fit:contain;display:block;transform:scaleX(-1);}
.bl-care-updated{margin:6px 2px 10px;color:#7184a4;font-size:11px;font-weight:850;letter-spacing:.06em;text-transform:uppercase;text-align:left;}
[class*="st-key-bl_care_"]{position:relative!important;}
[class*="st-key-bl_bath_btn_"]{position:absolute!important;right:22px!important;top:66px!important;width:124px!important;height:64px!important;z-index:8!important;margin:0!important;}
[class*="st-key-bl_bath_btn_"] div,[class*="st-key-bl_bath_btn_"] span,[class*="st-key-bl_bath_btn_"] .stButton,[class*="st-key-bl_bath_btn_"] button{width:100%!important;height:100%!important;min-height:100%!important;margin:0!important;}
[class*="st-key-bl_bath_btn_"] button,[class*="st-key-bl_bath_btn_"] button *{background:transparent!important;border:0!important;box-shadow:none!important;color:transparent!important;font-size:0!important;line-height:0!important;padding:0!important;outline:0!important;}
[class*="st-key-bl_bath_btn_"] button:hover,[class*="st-key-bl_bath_btn_"] button:focus,[class*="st-key-bl_bath_btn_"] button:active{background:rgba(59,130,246,.04)!important;border-radius:12px!important;border:0!important;box-shadow:none!important;outline:0!important;}
[class*="st-key-bl_care_length_"],[class*="st-key-bl_care_weight_"],[class*="st-key-bl_care_notes_"]{position:absolute!important;z-index:9!important;margin:0!important;}
[class*="st-key-bl_care_length_"]{top:126px!important;left:124px!important;width:58px!important;}
[class*="st-key-bl_care_weight_"]{top:126px!important;right:22px!important;width:118px!important;}
[class*="st-key-bl_care_notes_"]{top:180px!important;left:124px!important;width:calc(100% - 146px)!important;}
[class*="st-key-bl_care_length_"] label,[class*="st-key-bl_care_weight_"] label,[class*="st-key-bl_care_notes_"] label{display:none!important;}
[class*="st-key-bl_care_length_"] div,[class*="st-key-bl_care_weight_"] div,[class*="st-key-bl_care_notes_"] div{background:transparent!important;border-color:transparent!important;box-shadow:none!important;}
[class*="st-key-bl_care_length_"] [data-baseweb="input"],[class*="st-key-bl_care_weight_"] [data-baseweb="input"],[class*="st-key-bl_care_notes_"] [data-baseweb="input"]{height:24px!important;min-height:24px!important;background:transparent!important;border:0!important;box-shadow:none!important;}
[class*="st-key-bl_care_length_"] input,[class*="st-key-bl_care_weight_"] input,[class*="st-key-bl_care_notes_"] input{height:24px!important;min-height:24px!important;background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;color:#173664!important;font-size:16px!important;font-weight:400!important;line-height:1.15!important;outline:0!important;-webkit-appearance:none!important;overflow:hidden!important;text-overflow:clip!important;white-space:nowrap!important;}
[class*="st-key-bl_care_length_"] input:focus,[class*="st-key-bl_care_weight_"] input:focus,[class*="st-key-bl_care_notes_"] input:focus{outline:0!important;box-shadow:none!important;}
[class*="st-key-bl_care_length_"] input{padding-right:24px!important;}
[class*="st-key-bl_care_weight_"] input{padding-right:22px!important;}
[class*="st-key-bl_care_length_"]::after,[class*="st-key-bl_care_weight_"]::after{position:absolute!important;top:2px!important;right:0!important;color:#8aa0c0!important;font-size:16px!important;font-weight:400!important;line-height:24px!important;pointer-events:none!important;z-index:11!important;}
[class*="st-key-bl_care_length_"]::after{content:"cm";}
[class*="st-key-bl_care_weight_"]::after{content:"kg";}
[class*="st-key-bl_care_length_"] input::placeholder,[class*="st-key-bl_care_weight_"] input::placeholder,[class*="st-key-bl_care_notes_"] input::placeholder{color:#8aa0c0!important;opacity:1!important;}
.bl-log{padding:0 1px 4px;}
.bl-log-date{color:#7184a4;font-size:10px;font-weight:850;letter-spacing:.07em;text-transform:uppercase;margin:0 0 6px;}
.st-key-bl_daily_log_a,.st-key-bl_daily_log_b{margin-top:14px;}
.st-key-bl_daily_log_a [data-testid="stExpander"],.st-key-bl_daily_log_b [data-testid="stExpander"]{border:1px solid #dce6f3!important;border-radius:12px!important;background:rgba(255,255,255,.72)!important;box-shadow:none!important;overflow:hidden;}
.st-key-bl_daily_log_a [data-testid="stExpander"] details,.st-key-bl_daily_log_b [data-testid="stExpander"] details{border:0!important;}
.st-key-bl_daily_log_a [data-testid="stExpander"] summary,.st-key-bl_daily_log_b [data-testid="stExpander"] summary{min-height:46px!important;padding:0 12px!important;color:#173664!important;}
.st-key-bl_daily_log_a [data-testid="stExpander"] summary p,.st-key-bl_daily_log_b [data-testid="stExpander"] summary p{color:#173664!important;font-size:13px!important;font-weight:950!important;letter-spacing:.05em!important;text-transform:uppercase!important;}
.st-key-bl_daily_log_a [data-testid="stExpander"] summary svg,.st-key-bl_daily_log_b [data-testid="stExpander"] summary svg{color:#7184a4!important;width:20px!important;height:20px!important;}
.st-key-bl_daily_log_a [data-testid="stExpander"] summary,
.st-key-bl_daily_log_b [data-testid="stExpander"] summary,
.st-key-bl_daily_log_a [data-testid="stExpander"] summary:hover,
.st-key-bl_daily_log_b [data-testid="stExpander"] summary:hover,
.st-key-bl_daily_log_a [data-testid="stExpander"] summary:focus,
.st-key-bl_daily_log_b [data-testid="stExpander"] summary:focus,
.st-key-bl_daily_log_a [data-testid="stExpander"] summary:focus-visible,
.st-key-bl_daily_log_b [data-testid="stExpander"] summary:focus-visible,
.st-key-bl_daily_log_a [data-testid="stExpander"] details[open] summary,
.st-key-bl_daily_log_b [data-testid="stExpander"] details[open] summary{background:transparent!important;box-shadow:none!important;outline:0!important;border-bottom:0!important;}
.st-key-bl_daily_log_a [data-testid="stExpander"] summary [data-testid="stIconMaterial"],
.st-key-bl_daily_log_b [data-testid="stExpander"] summary [data-testid="stIconMaterial"]{color:#7184a4!important;font-size:22px!important;opacity:1!important;}
.st-key-bl_daily_log_a [data-testid="stExpanderDetails"],.st-key-bl_daily_log_b [data-testid="stExpanderDetails"]{padding:0 12px 10px!important;border-top:0!important;background:transparent!important;}
.bl-event{display:grid;grid-template-columns:48px minmax(0,1fr);gap:8px;align-items:baseline;border-top:1px solid #e4ecf6;padding:3px 0;}
.bl-event:first-of-type{border-top:0;}
.bl-event time{color:#7184a4;font-size:11px;font-weight:900;font-variant-numeric:tabular-nums;line-height:1.15;}
.bl-event b{color:#173664;font-size:12px;font-weight:850;line-height:1.15;}
.bl-event span{color:#7184a4;font-size:11px;font-weight:750;line-height:1.15;margin-left:5px;}
.bl-empty{color:#7184a4;font-size:12px;font-weight:750;padding:5px 0;}
.st-key-boys_log_view_nav{position:relative!important;z-index:5!important;max-width:1500px;margin:18px auto 28px;padding:0 10px;display:flex!important;flex-direction:row!important;justify-content:flex-end!important;align-items:center!important;}
.st-key-boys_log_view_nav [data-testid="stElementContainer"]{width:auto!important;}
.st-key-boys_log_analytics_nav{position:relative!important;z-index:5!important;max-width:1500px;margin:-2px auto 12px;padding:0 10px;display:flex!important;flex-direction:row!important;justify-content:center!important;align-items:center!important;}
.st-key-boys_log_analytics_nav [data-testid="stElementContainer"]{width:auto!important;}
.st-key-bl_view_toggle button{width:auto!important;min-width:112px!important;height:38px!important;min-height:38px!important;border:1px solid #cbdcf2!important;border-radius:999px!important;background:#fff!important;color:#173664!important;font-size:12px!important;font-weight:900!important;box-shadow:none!important;padding:0 16px!important;}
.st-key-bl_view_toggle button:hover,.st-key-bl_view_toggle button:focus,.st-key-bl_view_toggle button:active{border-color:#9fc0e9!important;background:#f4f8ff!important;box-shadow:none!important;outline:0!important;transform:none!important;}
.ba-shell{max-width:1500px;margin:0 auto;padding:0 10px 34px;color:#173664;}
.ba-hero{display:flex;align-items:center;justify-content:space-between;gap:18px;border:1px solid #d8e5f4;border-radius:8px;background:#f8fbff;padding:18px 20px;margin-bottom:12px;}
.ba-hero span,.ba-card-head span{display:block;color:#7184a4;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;}
.ba-title{display:block!important;font-size:23px!important;line-height:1.05!important;margin:4px 0 5px!important;color:#173664!important;letter-spacing:0!important;}
.ba-hero p{margin:0;color:#7184a4;font-size:12px;font-weight:800;}
.ba-legend{display:flex;align-items:center;gap:14px;white-space:nowrap;}
.ba-legend span{display:inline-flex;align-items:center;gap:6px;color:#526b91;font-size:11px;letter-spacing:0;text-transform:none;}
.ba-legend span:before{content:"";width:8px;height:8px;border-radius:50%;background:#75aef5;}
.ba-legend span.ba-b:before{background:#7fc79b;}
.ba-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;align-items:start;}
.ba-card{min-width:0;border:1px solid #dce6f3;border-radius:8px;background:#fff;padding:16px;box-shadow:0 8px 24px rgba(61,95,140,.05);}
.ba-card.ba-wide{grid-column:1/-1;}
.ba-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:13px;}
.ba-card-title{display:block!important;margin:3px 0 0!important;color:#173664!important;font-size:16px!important;line-height:1.15!important;letter-spacing:0!important;}
.ba-card-head>small{color:#7184a4;font-size:10px;font-weight:800;white-space:nowrap;margin-top:2px;}
.ba-note{min-height:28px;margin:-5px 0 9px;color:#7184a4;font-size:10px;font-weight:700;line-height:1.35;}
.ba-compare-head,.ba-compare-row{display:grid;grid-template-columns:minmax(110px,1.5fr) repeat(2,minmax(70px,1fr));align-items:center;gap:10px;}
.ba-compare-head{padding:0 10px 7px;color:#7184a4;font-size:10px;text-align:center;}
.ba-compare-row{min-height:42px;border-top:1px solid #edf2f8;padding:7px 10px;}
.ba-compare-row span{color:#526b91;font-size:11px;font-weight:800;}
.ba-compare-row b{font-size:14px;text-align:center;font-variant-numeric:tabular-nums;}
.ba-a{color:#2f72c9!important;}.ba-b{color:#278252!important;}
.ba-chart{height:170px;display:flex;align-items:stretch;justify-content:space-between;gap:5px;border-bottom:1px solid #dfe8f4;padding:5px 3px 0;}
.ba-bar-group{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:6px;}
.ba-bar-pair{width:100%;height:136px;display:flex;align-items:flex-end;justify-content:center;gap:3px;}
.ba-bar{display:block;width:min(16px,42%);min-height:3px;border-radius:3px 3px 0 0;background:#75aef5;}
.ba-bar.ba-b{background:#7fc79b;}
.ba-bar-group small{color:#7184a4;font-size:9px;font-weight:800;}
.ba-chart-foot{display:flex;justify-content:space-between;gap:10px;margin-top:10px;color:#7184a4;font-size:10px;}
.ba-chart-foot b{color:#173664;font-size:11px;}
.ba-nappy{display:grid;gap:14px;}
.ba-nappy-row{display:grid;grid-template-columns:58px minmax(0,1fr) minmax(0,1fr);gap:10px;align-items:center;}
.ba-nappy-row>b{font-size:12px;}
.ba-nappy-row>div{display:grid;grid-template-columns:32px minmax(0,1fr) 20px;gap:6px;align-items:center;}
.ba-nappy-row span{color:#7184a4;font-size:9px;font-weight:800;}
.ba-nappy-row i{display:block;height:8px;border-radius:999px;background:#edf3f9;overflow:hidden;}
.ba-nappy-row em{display:block;height:100%;min-width:2px;background:#75aef5;border-radius:999px;}
.ba-nappy-row em.ba-b{background:#7fc79b;}
.ba-nappy-row strong{font-size:11px;font-variant-numeric:tabular-nums;text-align:right;}
.ba-rhythm{overflow:hidden;}
.ba-rhythm-row{display:grid;grid-template-columns:60px minmax(0,1fr);gap:10px;align-items:center;margin:10px 0;}
.ba-rhythm-row>b{font-size:11px;}
.ba-rhythm-cells{display:grid;grid-template-columns:repeat(24,minmax(3px,1fr));gap:2px;height:34px;align-items:stretch;}
.ba-rhythm-cell{display:block;border-radius:2px;background:#4f91e5;}
.ba-rhythm-cell.ba-b{background:#35a063;}
.ba-rhythm-labels{margin-left:70px;display:flex;justify-content:space-between;color:#7184a4;font-size:8px;font-weight:800;}
.ba-growth{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}
.ba-growth-baby{border:1px solid #d8e7f7;border-radius:7px;background:#f7fbff;padding:12px;}
.ba-growth-baby.ba-b{border-color:#cee7d7;background:#f6fcf8;}
.ba-baby-title{display:block!important;margin:0 0 10px!important;font-size:13px!important;color:#173664!important;}
.ba-growth-baby>div{margin-top:9px;}
.ba-growth-baby span{display:block;color:#7184a4;font-size:9px;font-weight:850;text-transform:uppercase;}
.ba-growth-baby b{display:block;color:#173664;font-size:13px;margin-top:3px;}
.ba-growth-baby small{display:block;color:#7184a4;font-size:9px;margin-top:2px;}
.ba-milestones{display:grid;gap:8px;}
.ba-milestone{display:grid;grid-template-columns:24px minmax(0,1fr);gap:9px;align-items:start;border:1px solid #e3eaf3;border-radius:7px;padding:9px;background:#fbfcfe;}
.ba-milestone>span{display:flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#edf2f8;color:#7184a4;font-size:12px;font-weight:900;}
.ba-milestone.achieved>span{background:#e5f6eb;color:#278252;}
.ba-milestone b{display:block;color:#173664;font-size:11px;}
.ba-milestone small{display:block;color:#7184a4;font-size:9px;margin-top:2px;}
.ba-milestone i{display:block;height:4px;border-radius:999px;background:#e9eff6;overflow:hidden;margin-top:6px;}
.ba-milestone em{display:block;height:100%;border-radius:999px;background:#75aef5;}
.ba-milestone.achieved em{background:#58b77d;}
@media(max-width:900px){.st-key-boys_log_view_nav{padding:0 4px;margin:0 auto 10px}.st-key-bl_view_toggle button{min-width:104px!important;height:34px!important;min-height:34px!important;font-size:11px!important}.ba-shell{padding:0 4px 26px}.ba-hero{padding:14px;align-items:flex-start}.ba-title{font-size:20px!important}.ba-grid{grid-template-columns:1fr;gap:10px}.ba-card.ba-wide{grid-column:auto}.ba-card{padding:13px}.ba-card-title{font-size:15px!important}.ba-compare-head,.ba-compare-row{grid-template-columns:minmax(94px,1.4fr) repeat(2,minmax(64px,1fr));gap:5px}.ba-compare-row{padding:7px 5px}.ba-chart{height:154px}.ba-bar-pair{height:120px}.ba-nappy-row{grid-template-columns:52px minmax(0,1fr);}.ba-nappy-row>div{grid-column:2}.ba-growth{grid-template-columns:1fr 1fr}.ba-rhythm-row{grid-template-columns:52px minmax(0,1fr);gap:7px}.ba-rhythm-labels{margin-left:59px}}
@media(max-width:430px){.ba-hero{display:block}.ba-legend{margin-top:10px}.ba-growth{grid-template-columns:1fr}.ba-chart-foot{display:grid;grid-template-columns:1fr 1fr}.ba-rhythm-cells{gap:1px}.ba-rhythm-labels{font-size:7px}}
@media(max-width:1200px){.bl-metric{grid-template-columns:36px minmax(0,1fr);}.bl-metric b{font-size:24px;}.bl-metric-group{grid-template-columns:58px minmax(0,1fr);}}
@media(max-width:900px){.bl-shell{margin-top:-18px;padding:0 4px 24px}.bl-twins{grid-template-columns:1fr}.bl-toolbar{grid-template-columns:44px minmax(0,1fr) 44px;gap:7px}.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:44px minmax(0,1fr) 44px!important;gap:7px!important;align-items:center!important}.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:auto!important;flex:initial!important;min-width:0!important}.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:has(.st-key-bl_prev){grid-column:1}.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:has(.st-key-bl_date_control){grid-column:2}.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:has(.st-key-bl_today){display:none!important}.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:has(.st-key-bl_next){grid-column:3}.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:has(.bl-sync){grid-column:1/-1}.st-key-bl_today{display:none!important}.st-key-bl_prev .stButton>button,.st-key-bl_next .stButton>button{font-size:0!important;color:transparent!important;padding:0!important}.st-key-bl_prev .stButton>button:before{content:"‹";font-size:28px;line-height:1;color:#173664}.st-key-bl_next .stButton>button:before{content:"›";font-size:28px;line-height:1;color:#173664}.bl-date-full{display:none}.bl-date-short{display:inline}.bl-date-display{height:42px;font-size:14px;border-radius:10px}.bl-sync{grid-column:1/-1;text-align:left}.st-key-bl_panel_a,.st-key-bl_panel_b{padding:8px;overflow:hidden}.bl-summary{gap:5px}.bl-metric{display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:19px 5px 8px;gap:4px;border-radius:12px;min-height:118px}.bl-metric-group,.bl-metric-simple{display:flex;grid-template-columns:none}.bl-metric-body{width:100%;align-items:center}.bl-metric-body strong{font-size:10px;margin:0;top:7px!important}.bl-metric-icons{width:100%;height:48px;margin-top:12px}.bl-metric-icons:before{width:44px;height:44px}.bl-metric-icons img{width:44px;height:44px}.bl-metric-simple.feed_kpi .bl-metric-icons img,.bl-metric-group.nappy .bl-metric-icons img,.bl-metric-group.sleep_kpi .bl-metric-icons img{width:48px!important;height:48px!important;min-width:48px!important}.bl-metric-simple.feed_kpi .bl-metric-icons:before{width:52px;height:48px}.bl-metric-group.nappy .bl-metric-icons:before{width:54px;height:48px}.bl-metric-total{margin-top:1px}.bl-metric-total b{font-size:20px}.bl-metric-total small{font-size:9px;margin-top:2px}.bl-metric-lines{width:100%;min-height:30px;gap:2px;margin-top:0}.bl-metric-line span{font-size:8px;margin-bottom:1px}.bl-metric-line b{font-size:18px}.bl-metric-line small{font-size:9px}.bl-metric-group.sleep_kpi .bl-metric-line b{font-size:18px}.bl-metric-group.sleep_kpi .bl-metric-line small{font-size:10px}.bl-grid{border-radius:14px}.bl-grid-baby{height:30px;font-size:12px}.bl-grid-head{grid-template-columns:1.18fr repeat(7,minmax(0,1fr))}.bl-grid-head div{min-height:52px;padding:7px 1px;font-size:9px}.bl-time-head img{width:17px;height:17px}.bl-headicon{height:34px}.bl-headicon img{width:24px!important;height:24px!important;min-width:24px!important}.bl-headicon.pee img,.bl-headicon.poop img{width:34px!important;height:34px!important;min-width:34px!important}.bl-headicon.sleep img{width:36px!important;height:36px!important;min-width:36px!important}.bl-headicon.bottle img{width:38px!important;height:38px!important;min-width:38px!important}.bl-headicon.other img{width:26px!important;height:34px!important;min-width:26px!important}.bl-lr-letter{font-size:15px;bottom:8px}.bl-lr-letter.left{left:9px}.bl-lr-letter.right{right:9px}.bl-shared-feed-icon{width:48px;height:48px}.bl-shared-feed-icon img{width:48px;height:48px}[class*="st-key-blrow_"] [data-testid="stHorizontalBlock"]{grid-template-columns:1.18fr repeat(7,minmax(0,1fr))!important;min-width:0!important;width:100%!important}.bl-time,[class*="st-key-blslot_"]{min-height:44px}.bl-time{font-size:12px;padding:3px 1px 3px 20px}.bl-time-marker{width:20px;height:20px}.bl-time-marker img{width:16px;height:16px}.bl-time:before,.bl-time:after{left:10px}.bl-time:before{top:0;bottom:calc(50% + 10px)}.bl-time:after{top:calc(50% + 10px);bottom:0}.bl-chip img{width:15px;height:15px}.bl-chip-amount{font-size:11px}.bl-chip-time{font-size:10px}.bl-sleep-fill{left:3px;right:3px;top:-24px;bottom:-24px}.bl-care{padding:14px 12px}.bl-care-row.bath{grid-template-columns:72px minmax(0,1fr) 86px}.bl-care-row.measures{grid-template-columns:72px minmax(0,1fr) 58px 62px}.bl-care-row.notes{grid-template-columns:72px minmax(0,1fr)}.bl-care-row span{font-size:13px}.bl-care-row b{font-size:14px}.bl-care-row.bath i{width:86px;height:52px}.bl-care-row.bath img{width:86px;height:52px}[class*="st-key-bl_bath_btn_"]{right:12px!important;top:67px!important;width:86px!important;height:52px!important}[class*="st-key-bl_care_length_"]{left:94px!important;width:48px!important}[class*="st-key-bl_care_weight_"]{right:12px!important;width:62px!important}[class*="st-key-bl_care_notes_"]{left:94px!important;width:calc(100% - 106px)!important}}
@media(max-width:900px){.st-key-boys_log_toolbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:has(.bl-sync){display:none!important}.bl-head{display:flex;flex-direction:column;align-items:flex-start;gap:3px;margin:0 0 8px}.bl-head .bl-sync{order:-1;border:0;background:transparent;border-radius:0;box-shadow:none;padding:0;color:#7184a4;font-size:10px;font-weight:850;letter-spacing:.06em;text-align:left}.bl-title{font-size:23px}.bl-title span{font-size:10px;margin-top:4px}}
@media(max-width:900px){.bl-grid-head div{min-height:64px;padding:5px 1px}.bl-headicon{height:54px}.bl-shared-feed-icon{width:50px;height:50px}.bl-shared-feed-icon img{width:50px;height:50px}}
@media(max-width:900px){.bl-metric-total small{margin:0 0 3px}.bl-care-updated{font-size:10px;margin:6px 2px 8px}}
@media(max-width:1100px){.mobile-topbar{display:none!important}.bl-mobile-title{display:flex;align-items:center;justify-content:center;gap:10px;text-align:center;margin:-4px 0 10px}.bl-mobile-title img{width:76px;height:76px;object-fit:contain;display:block;flex:0 0 76px}.bl-mobile-title h1{margin:0;color:#173664;font-size:22px;font-weight:950;letter-spacing:.01em;line-height:1.05;white-space:nowrap}}
html.force-mobile .st-key-desktop_header_row,html.force-mobile .st-key-desktop_header_row *,html.force-mobile [data-testid="stHorizontalBlock"]:has(.st-key-desktop_header_row),html.force-mobile .st-key-brandrow,html.force-mobile .st-key-brandrow *{display:none!important;height:0!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important}
html.force-mobile .mobile-topbar{display:none!important}
html.force-mobile [data-testid="stMainBlockContainer"]>[data-testid="stVerticalBlock"]>*:has(~ [data-testid="stElementContainer"] .bl-mobile-title):not(:has(.mobile-footer-nav)){display:none!important}
html.force-mobile [data-testid="stElementContainer"]:has(.bl-mobile-title){margin:0!important}
html.force-mobile .bl-mobile-title{display:flex!important;position:relative!important;align-items:center!important;justify-content:center!important;width:100%!important;min-height:105px!important;margin:0 0 6px!important}
html.force-mobile .bl-mobile-title img{position:absolute!important;top:50%!important;width:105px!important;height:105px!important;transform:translateY(calc(-50% + 6px))}
html.force-mobile .bl-mobile-title .bl-title-bun-left{left:max(0px,calc(50% - 200px))!important}
html.force-mobile .bl-mobile-title .bl-title-bun-right{left:auto!important;right:max(0px,calc(50% - 200px))!important}
html.force-mobile .bl-mobile-title h1{position:absolute!important;left:50%!important;top:50%!important;width:max-content!important;font-size:21px!important;text-align:center!important;transform:translate(-50%,-50%)}
html.force-mobile [data-testid="stElementContainer"]:has(.bl-shell){display:none!important}
html.force-mobile .bl-shell{margin-top:0!important}
html.force-mobile .st-key-boys_log_toolbar{margin-top:0!important}
html.force-mobile .bl-toolbar{margin-bottom:10px!important}
html.force-mobile .st-key-bl_panel_a:has(.bl-panel-state.open),html.force-mobile .st-key-bl_panel_b:has(.bl-panel-state.open){overflow:visible!important}
html.force-mobile .bl-metric-icons{height:58px!important;margin-top:7px!important;display:flex!important;align-items:center!important;justify-content:center!important}
html.force-mobile .bl-metric-simple.feed_kpi .bl-metric-icons img,html.force-mobile .bl-metric-group.nappy .bl-metric-icons img,html.force-mobile .bl-metric-group.sleep_kpi .bl-metric-icons img{width:58px!important;height:58px!important;min-width:58px!important}
html.force-mobile .bl-metric-simple.feed_kpi .bl-metric-icons:before{display:block!important;width:68px!important;height:64px!important;background:radial-gradient(circle at 38% 34%,rgba(226,242,255,.90) 0%,rgba(207,230,253,.68) 58%,rgba(190,220,249,.20) 100%)!important;border-radius:50%!important;filter:blur(2px)!important}
html.force-mobile .bl-metric-group.nappy .bl-metric-icons:before{display:block!important;width:68px!important;height:64px!important;background:radial-gradient(circle at 38% 34%,rgba(226,242,255,.90) 0%,rgba(207,230,253,.68) 58%,rgba(190,220,249,.20) 100%)!important;border-radius:50%!important;filter:blur(2px)!important}
html.force-mobile .bl-metric-group.sleep_kpi .bl-metric-icons:before{display:none!important}
html.force-mobile .st-key-bl_panel_a{border-color:#bcd9f6!important;background:linear-gradient(135deg,rgba(222,240,255,.99),rgba(242,249,255,.94))!important}
html.force-mobile .st-key-bl_panel_b{border-color:#bcdcc8!important;background:linear-gradient(135deg,rgba(224,246,233,.99),rgba(242,251,246,.94))!important}
html.force-mobile .st-key-bl_panel_b .bl-metric{border-color:#bcdcc8!important}

/* Light / dark mode control */
.st-key-boys_log_theme{position:relative!important;z-index:70!important;display:block!important;width:100%!important;max-width:1500px!important;min-height:42px!important;margin:-8px auto -24px!important;padding:0 10px!important}
.st-key-boys_log_theme .st-key-bl_theme_choice{position:absolute!important;left:50%!important;top:0!important;width:auto!important;margin:0!important;transform:translateX(-50%)!important}
.st-key-boys_log_theme [data-testid="stRadio"]{width:auto!important;margin:0!important}
.st-key-boys_log_theme_state{position:absolute!important;width:0!important;height:0!important;margin:0!important;padding:0!important;overflow:hidden!important}
.st-key-boys_log_theme [role="radiogroup"]{display:inline-flex!important;flex-direction:row!important;gap:3px!important;border:1px solid #dce6f3!important;border-radius:999px!important;background:#f4f7fb!important;padding:3px!important;box-shadow:0 10px 24px rgba(61,95,140,.07)!important}
.st-key-boys_log_theme [role="radiogroup"] label{position:relative!important;display:flex!important;align-items:center!important;justify-content:center!important;min-width:88px!important;height:34px!important;margin:0!important;border-radius:999px!important;padding:0 14px!important;cursor:pointer!important}
.st-key-boys_log_theme [role="radiogroup"] label>div:first-child{display:none!important}
.st-key-boys_log_theme [role="radiogroup"] label div:has(>[data-testid="stMarkdownContainer"])>div:not([data-testid="stMarkdownContainer"]){display:none!important}
.st-key-boys_log_theme [role="radiogroup"] input[type="radio"]{position:absolute!important;width:1px!important;height:1px!important;opacity:0!important;pointer-events:none!important}
.st-key-boys_log_theme [role="radiogroup"] label p{display:flex!important;align-items:center!important;gap:6px!important;margin:0!important;color:#7184a4!important;font-size:12px!important;font-weight:900!important}
.st-key-boys_log_theme [role="radiogroup"] label:first-child p:before{content:"☀";font-size:16px;line-height:1}
.st-key-boys_log_theme [role="radiogroup"] label:last-child p:before{content:"☾";font-size:17px;line-height:1}
.st-key-boys_log_theme [role="radiogroup"] label:has(input:checked){background:#fff!important;box-shadow:0 4px 12px rgba(61,95,140,.12)!important}
.st-key-boys_log_theme [role="radiogroup"] label:has(input:checked) p{color:#173664!important}
.bl-theme-state{position:absolute;width:0;height:0;overflow:hidden;pointer-events:none}

/* Carry each baby's identity colour through the existing one-pixel borders. */
.st-key-bl_panel_a .bl-metric,.st-key-bl_panel_a .bl-grid{border-color:#a9d8f7!important}
.st-key-bl_panel_b .bl-metric,.st-key-bl_panel_b .bl-grid{border-color:#c7b5ef!important}
.st-key-bl_panel_a .bl-grid-baby,.st-key-bl_panel_a .bl-grid-head div{border-color:#bfdcf1!important}
.st-key-bl_panel_b .bl-grid-baby,.st-key-bl_panel_b .bl-grid-head div{border-color:#d3c7ed!important}
.bl-headicon.pee img,.bl-headicon.poop img{width:53px!important;height:53px!important;min-width:53px!important;max-width:53px!important}
.bl-headicon.pee img{filter:none!important}
.bl-headicon.poop img{filter:none!important}

/* Dark mode: starry page canvas, clean panels and a restrained summary tint. */
body:has(.bl-theme-state.dark),body:has(.bl-theme-state.dark) [data-testid="stAppViewContainer"],body:has(.bl-theme-state.dark) [data-testid="stApp"],body:has(.bl-theme-state.dark) .stApp{
  background-color:#061326!important;
  background-image:radial-gradient(circle at 8% 18%,rgba(255,255,255,.86) 0 1px,transparent 1.7px),radial-gradient(circle at 31% 9%,rgba(158,220,255,.78) 0 1px,transparent 1.8px),radial-gradient(circle at 68% 22%,rgba(255,255,255,.72) 0 1px,transparent 1.8px),radial-gradient(circle at 88% 12%,rgba(185,161,255,.75) 0 1px,transparent 1.9px),radial-gradient(circle at 21% 72%,rgba(255,255,255,.65) 0 1px,transparent 1.7px),radial-gradient(circle at 76% 82%,rgba(158,220,255,.58) 0 1px,transparent 1.8px),linear-gradient(180deg,#061326 0%,#08182d 52%,#061326 100%)!important;
  background-size:360px 300px,470px 390px,520px 440px,610px 510px,420px 360px,560px 470px,100% 100%!important;
  background-attachment:fixed!important;
}
body:has(.bl-theme-state.dark) [data-testid="stMain"],body:has(.bl-theme-state.dark) [data-testid="stMainBlockContainer"]{background:transparent!important}
body:has(.bl-theme-state.dark) .st-key-topnav a,body:has(.bl-theme-state.dark) .st-key-topnav a p,body:has(.bl-theme-state.dark) .st-key-topnav a span{color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .st-key-topnav a[data-testid="stPageLink-NavLink"][aria-current="page"],body:has(.bl-theme-state.dark) .st-key-topnav a:hover{background:rgba(126,182,255,.14)!important;color:#f5f7fb!important}
body:has(.bl-theme-state.dark) .bl-shell{color:#dce7f6}
body:has(.bl-theme-state.dark) .bl-mobile-title h1{color:#f5f7fb!important;text-shadow:0 2px 14px rgba(0,0,0,.35)}
body:has(.bl-theme-state.dark) .st-key-boys_log_theme [role="radiogroup"]{border-color:#29425f!important;background:#0c1d34!important;box-shadow:0 10px 24px rgba(0,0,0,.22)!important}
body:has(.bl-theme-state.dark) .st-key-boys_log_theme [role="radiogroup"] label p{color:#8fa3bd!important}
body:has(.bl-theme-state.dark) .st-key-boys_log_theme [role="radiogroup"] label:has(input:checked){background:linear-gradient(135deg,#4d7fe6,#7767d8)!important;box-shadow:0 5px 15px rgba(82,118,224,.30)!important}
body:has(.bl-theme-state.dark) .st-key-boys_log_theme [role="radiogroup"] label:has(input:checked) p{color:#fff!important}
body:has(.bl-theme-state.dark) .bl-date-display,body:has(.bl-theme-state.dark) .bl-sync,body:has(.bl-theme-state.dark) .bl-toolbar .stButton>button,body:has(.bl-theme-state.dark) [class*="st-key-bl_"] .stButton>button{border-color:#29425f!important;background:#0d1d33!important;color:#e8eef8!important;box-shadow:0 10px 24px rgba(0,0,0,.18)!important}
body:has(.bl-theme-state.dark) .bl-date-display{color:#f5f7fb!important}
body:has(.bl-theme-state.dark) .bl-sync{color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .st-key-bl_prev .stButton>button:before,body:has(.bl-theme-state.dark) .st-key-bl_next .stButton>button:before{color:#dce7f6!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a,body:has(.bl-theme-state.dark) html.force-mobile .st-key-bl_panel_a{border:1px solid rgba(76,141,255,.56)!important;background:linear-gradient(180deg,rgba(76,141,255,.12) 0,rgba(76,141,255,.08) 145px,rgba(13,29,51,0) 245px),#0d1d33!important;box-shadow:0 18px 48px rgba(0,0,0,.26)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b,body:has(.bl-theme-state.dark) html.force-mobile .st-key-bl_panel_b{border:1px solid rgba(185,161,255,.62)!important;background:linear-gradient(180deg,rgba(139,105,210,.20) 0,rgba(112,80,177,.11) 145px,rgba(13,29,51,0) 245px),#0d1d33!important;box-shadow:0 18px 48px rgba(0,0,0,.26)!important}
body:has(.bl-theme-state.dark) .bl-title{color:#f5f7fb!important}
body:has(.bl-theme-state.dark) .bl-title span{color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .bl-toggle-pill{border-color:#37506d!important;background:rgba(9,24,43,.88)!important;color:#b8c6d8!important}
body:has(.bl-theme-state.dark) .bl-metric{border-color:#29425f!important;background:rgba(17,38,65,.92)!important;box-shadow:0 12px 30px rgba(0,0,0,.18)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-metric{border-color:rgba(76,141,255,.56)!important;background:rgba(76,141,255,.07)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-metric{border-color:rgba(185,161,255,.62)!important;background:transparent!important}
body:has(.bl-theme-state.dark) .bl-metric-simple.feed_kpi .bl-metric-icons:before,body:has(.bl-theme-state.dark) .bl-metric-group.nappy .bl-metric-icons:before{display:none!important}
body:has(.bl-theme-state.dark) .bl-metric-body strong,body:has(.bl-theme-state.dark) .bl-metric-line span,body:has(.bl-theme-state.dark) .bl-metric-line small,body:has(.bl-theme-state.dark) .bl-metric-total small{color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .bl-metric-line{border-left-color:#37506d!important}
body:has(.bl-theme-state.dark) .bl-metric-line b,body:has(.bl-theme-state.dark) .bl-metric-total b{color:#f5f7fb!important}
body:has(.bl-theme-state.dark) .bl-metric-group.sleep_kpi .bl-metric-line b{color:#cabaff!important}
body:has(.bl-theme-state.dark) .bl-metric-body em{background:#183454!important;color:#9edcff!important}
body:has(.bl-theme-state.dark) .bl-metric-group.sleep_kpi .bl-metric-body em{background:#282346!important;color:#cbbcff!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a [data-testid="stElementContainer"]:has(.bl-grid),body:has(.bl-theme-state.dark) .st-key-bl_panel_b [data-testid="stElementContainer"]:has(.bl-grid){background:#10243d!important}
body:has(.bl-theme-state.dark) .bl-grid{border-color:#29425f!important;background:#10243d!important;box-shadow:0 18px 46px rgba(0,0,0,.22)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-grid{border-color:rgba(76,141,255,.56)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-grid{border-color:rgba(185,161,255,.62)!important}
body:has(.bl-theme-state.dark) .bl-grid-baby,body:has(.bl-theme-state.dark) .bl-grid-head{background:#10243d!important;color:#f5f7fb!important;border-color:#29425f!important}
body:has(.bl-theme-state.dark) .bl-grid-head div,body:has(.bl-theme-state.dark) .st-key-blgrid_cell,body:has(.bl-theme-state.dark) [class*="st-key-blslot_"]{color:#dce7f6!important;border-color:#29425f!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-grid-baby,body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-grid-head,body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-grid-head div{border-color:rgba(76,141,255,.44)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-grid-baby,body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-grid-head div{border-color:rgba(185,161,255,.42)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-grid-head div{background:rgba(76,141,255,.06)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-grid-head div{background:rgba(185,161,255,.03)!important}
body:has(.bl-theme-state.dark) .bl-row-wrap{border-color:#29425f!important}
body:has(.bl-theme-state.dark) .bl-row-wrap.current{background:rgba(126,182,255,.06)!important}
body:has(.bl-theme-state.dark) .bl-time,body:has(.bl-theme-state.dark) .bl-time.has-event,body:has(.bl-theme-state.dark) .bl-lr-letter{color:#e8eef8!important}
body:has(.bl-theme-state.dark) .bl-time-marker{background:#172f4d!important}
body:has(.bl-theme-state.dark) .bl-time-head img,body:has(.bl-theme-state.dark) .bl-time-marker img,body:has(.bl-theme-state.dark) .bl-shared-feed-icon img{filter:grayscale(1) brightness(0) invert(1)!important;opacity:.94!important}
body:has(.bl-theme-state.dark) .bl-time:before,body:has(.bl-theme-state.dark) .bl-time:after{background:repeating-linear-gradient(to bottom,rgba(207,222,241,.58) 0 2px,transparent 2px 6px)!important}
body:has(.bl-theme-state.dark) [class*="st-key-blslot_"]:not(:has(.bl-chip)):not(:has(.bl-sleep-implied)):not(:has([class*="st-key-bl_bottle_picker_"])):not(:has([class*="st-key-bl_bottle_menu_"])):after{color:#69809d!important}
body:has(.bl-theme-state.dark) .bl-sleep-fill{left:14%!important;right:14%!important;background:#514786!important;border-left:1px solid rgba(194,180,255,.18)!important;border-right:1px solid rgba(194,180,255,.18)!important;box-shadow:0 0 15px rgba(116,92,190,.12)!important}
body:has(.bl-theme-state.dark) .bl-sleep-implied.sleep-start .bl-sleep-fill{border-radius:18px 18px 0 0!important;background:linear-gradient(180deg,#8f82ce,#514786 88%)!important}
body:has(.bl-theme-state.dark) .bl-sleep-implied.sleep-end .bl-sleep-fill{border-radius:0 0 18px 18px!important}
body:has(.bl-theme-state.dark) .bl-sleep-implied.sleep-start.sleep-end .bl-sleep-fill{border-radius:18px!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-sleep-fill{background:#425f8e!important;border-color:rgba(145,181,230,.25)!important;box-shadow:0 0 15px rgba(76,141,255,.10)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-sleep-implied.sleep-start .bl-sleep-fill{background:linear-gradient(180deg,#7897c7,#425f8e 88%)!important}
body:has(.bl-theme-state.dark) .bl-sleep-implied.sleep-start .bl-sleep-fill:before{content:"★";position:absolute;left:20%;top:17px;color:#ffd65a;font-size:11px;line-height:1;text-shadow:25px 18px 0 #ffdc66,11px 36px 0 rgba(255,214,90,.20);filter:drop-shadow(0 0 2px rgba(255,214,90,.36));z-index:2}
body:has(.bl-theme-state.dark) .bl-sleep-implied:not(.sleep-start) .bl-sleep-fill:after{content:"✦";position:absolute;top:38px;color:#ffd65a;font-size:8px;line-height:1;filter:drop-shadow(0 0 2px rgba(255,214,90,.28));z-index:2}
body:has(.bl-theme-state.dark) .bl-sleep-implied:not(.sleep-start) .bl-sleep-fill:before{content:"★";position:absolute;top:64px;color:rgba(255,224,104,.68);font-size:6px;line-height:1;filter:drop-shadow(0 0 2px rgba(255,214,90,.18));z-index:2}
body:has(.bl-theme-state.dark) .sleep-stars-0 .bl-sleep-fill:after{left:22%;text-shadow:20px 16px 0 rgba(255,225,118,.48)}
body:has(.bl-theme-state.dark) .sleep-stars-1 .bl-sleep-fill:after{left:57%;font-size:6px;text-shadow:-18px 20px 0 rgba(255,214,90,.62)}
body:has(.bl-theme-state.dark) .sleep-stars-2 .bl-sleep-fill:after{left:34%;font-size:9px;text-shadow:16px 19px 0 rgba(255,225,118,.34)}
body:has(.bl-theme-state.dark) .sleep-stars-3 .bl-sleep-fill:after{left:65%;font-size:7px;text-shadow:-24px 17px 0 rgba(255,214,90,.52)}
body:has(.bl-theme-state.dark) .sleep-stars-0 .bl-sleep-fill:before{left:70%}
body:has(.bl-theme-state.dark) .sleep-stars-1 .bl-sleep-fill:before{left:28%;font-size:5px;opacity:.6}
body:has(.bl-theme-state.dark) .sleep-stars-2 .bl-sleep-fill:before{left:74%;font-size:7px}
body:has(.bl-theme-state.dark) .sleep-stars-3 .bl-sleep-fill:before{left:38%;font-size:5px;opacity:.72}
body:has(.bl-theme-state.dark) .bl-care{border-color:#29425f!important;background:#10243d!important;box-shadow:0 12px 30px rgba(0,0,0,.18)!important}
body:has(.bl-theme-state.dark) .bl-care-title span,body:has(.bl-theme-state.dark) .bl-care-row span,body:has(.bl-theme-state.dark) .bl-care-updated{color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .bl-care-row b{color:#e8eef8!important}
body:has(.bl-theme-state.dark) .bl-care-rule{background:#29425f!important}
body:has(.bl-theme-state.dark) [class*="st-key-bl_care_"] input{color:#e8eef8!important;-webkit-text-fill-color:#e8eef8!important}
body:has(.bl-theme-state.dark) .st-key-bl_daily_log_a [data-testid="stExpander"],body:has(.bl-theme-state.dark) .st-key-bl_daily_log_b [data-testid="stExpander"]{border-color:#29425f!important;background:rgba(16,36,61,.90)!important}
body:has(.bl-theme-state.dark) .st-key-bl_daily_log_a [data-testid="stExpander"] summary p,body:has(.bl-theme-state.dark) .st-key-bl_daily_log_b [data-testid="stExpander"] summary p,body:has(.bl-theme-state.dark) .bl-event b{color:#e8eef8!important}
body:has(.bl-theme-state.dark) .st-key-bl_daily_log_a [data-testid="stExpander"] summary svg,body:has(.bl-theme-state.dark) .st-key-bl_daily_log_b [data-testid="stExpander"] summary svg,body:has(.bl-theme-state.dark) .bl-log-date,body:has(.bl-theme-state.dark) .bl-event time,body:has(.bl-theme-state.dark) .bl-event span,body:has(.bl-theme-state.dark) .bl-empty{color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .bl-event{border-color:#29425f!important}
body:has(.bl-theme-state.dark) .ba-shell{color:#e8eef8!important}
body:has(.bl-theme-state.dark) .ba-hero,body:has(.bl-theme-state.dark) .ba-card{border-color:#29425f!important;background:rgba(13,29,51,.94)!important;box-shadow:0 12px 30px rgba(0,0,0,.18)!important}
body:has(.bl-theme-state.dark) .ba-title,body:has(.bl-theme-state.dark) .ba-card-title,body:has(.bl-theme-state.dark) .ba-chart-foot b,body:has(.bl-theme-state.dark) .ba-growth-baby b,body:has(.bl-theme-state.dark) .ba-baby-title,body:has(.bl-theme-state.dark) .ba-milestone b{color:#f5f7fb!important}
body:has(.bl-theme-state.dark) .ba-hero span,body:has(.bl-theme-state.dark) .ba-card-head span,body:has(.bl-theme-state.dark) .ba-hero p,body:has(.bl-theme-state.dark) .ba-card-head>small,body:has(.bl-theme-state.dark) .ba-note,body:has(.bl-theme-state.dark) .ba-compare-head,body:has(.bl-theme-state.dark) .ba-compare-row span,body:has(.bl-theme-state.dark) .ba-chart-foot,body:has(.bl-theme-state.dark) .ba-growth-baby span,body:has(.bl-theme-state.dark) .ba-growth-baby small,body:has(.bl-theme-state.dark) .ba-milestone small{color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .ba-compare-row,body:has(.bl-theme-state.dark) .ba-chart{border-color:#29425f!important}
body:has(.bl-theme-state.dark) .ba-growth-baby,body:has(.bl-theme-state.dark) .ba-milestone{border-color:#29425f!important;background:#10243d!important}
body:has(.bl-theme-state.dark) .ba-a{color:#9edcff!important}body:has(.bl-theme-state.dark) .ba-b{color:#b9a1ff!important}
@media(max-width:900px){.st-key-boys_log_theme{min-height:40px!important;margin:-2px auto -18px!important}.st-key-boys_log_theme [role="radiogroup"] label{min-width:78px!important;height:32px!important;padding:0 12px!important}.st-key-boys_log_theme [role="radiogroup"] label p{font-size:11px!important}}
@media(max-width:900px){.bl-headicon.pee img,.bl-headicon.poop img{width:41px!important;height:41px!important;min-width:41px!important;max-width:41px!important}}
@media(max-width:900px){.bl-headicon.sleep img{width:43px!important;height:43px!important;min-width:43px!important;max-width:43px!important}.bl-headicon.other img{width:46px!important;height:46px!important;min-width:46px!important;max-width:46px!important}}

/* Profile-coloured KPI values and profile controls. */
.st-key-bl_panel_a .bl-metric-total b,.st-key-bl_panel_a .bl-metric-line b{color:#397dcc!important}
.st-key-bl_panel_b .bl-metric-total b,.st-key-bl_panel_b .bl-metric-line b{color:#7655a5!important}
.st-key-bl_panel_a .bl-toggle-pill{border-color:#7eb6ff!important}
.st-key-bl_panel_b .bl-toggle-pill{border-color:#b9a1ff!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-metric-total b,body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-metric-line b{color:#7eb6ff!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-metric-total b,body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-metric-line b{color:#cabaff!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-toggle-pill{border-color:rgba(76,141,255,.72)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-toggle-pill{border-color:rgba(185,161,255,.72)!important}

/* Keep the date control clean and borderless. */
.bl-date-display,
body:has(.bl-theme-state.dark) .bl-date-display{border:0!important}

/* Keep Care Details and Daily Log aligned with each baby's profile colour. */
.st-key-bl_panel_a .bl-care,
.st-key-bl_panel_a .st-key-bl_daily_log_a [data-testid="stExpander"]{border-color:#a9d8f7!important}
.st-key-bl_panel_b .bl-care,
.st-key-bl_panel_b .st-key-bl_daily_log_b [data-testid="stExpander"]{border-color:#c7b5ef!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-care,
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .st-key-bl_daily_log_a [data-testid="stExpander"]{border-color:rgba(76,141,255,.56)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-care,
body:has(.bl-theme-state.dark) .st-key-bl_panel_b .st-key-bl_daily_log_b [data-testid="stExpander"]{border-color:rgba(185,161,255,.62)!important}

/* Dark-mode completion marks and timestamps: brighter and easier to scan. */
body:has(.bl-theme-state.dark) .bl-chip img{width:21px!important;height:21px!important;filter:grayscale(1) brightness(0) invert(1)!important;opacity:1!important}
body:has(.bl-theme-state.dark) .bl-chip-amount{color:#fff!important}
body:has(.bl-theme-state.dark) .bl-chip-time{font-size:13px!important;color:#e8eef8!important}
@media(max-width:900px){body:has(.bl-theme-state.dark) .bl-chip img{width:17px!important;height:17px!important}body:has(.bl-theme-state.dark) .bl-chip-time{font-size:11px!important}}

/* KPI values are white in dark mode; keep a readable navy equivalent in light mode. */
.st-key-bl_panel_a .bl-metric-total b,.st-key-bl_panel_a .bl-metric-line b,.st-key-bl_panel_b .bl-metric-total b,.st-key-bl_panel_b .bl-metric-line b{color:#112f62!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-metric-total b,body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-metric-line b,body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-metric-total b,body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-metric-line b{color:#f5f7fb!important}
.bl-metric-group.sleep_kpi .bl-metric-line b,.bl-metric-group.sleep_kpi .bl-metric-line small{position:relative;top:-4px}

/* Mobile date navigation: one precisely centred arrow, without a surrounding box. */
@media(max-width:900px){.st-key-bl_prev .stButton>button,.st-key-bl_next .stButton>button{position:relative!important;display:block!important;width:44px!important;height:42px!important;min-height:42px!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;color:transparent!important}.st-key-bl_prev .stButton>button p,.st-key-bl_prev .stButton>button span,.st-key-bl_next .stButton>button p,.st-key-bl_next .stButton>button span{font-size:0!important;line-height:0!important;color:transparent!important}.st-key-bl_prev .stButton>button:before,.st-key-bl_next .stButton>button:before{position:absolute!important;left:50%!important;top:50%!important;display:block!important;width:28px!important;margin:0!important;transform:translate(-50%,-54%)!important;text-align:center!important;font-size:30px!important;line-height:1!important;color:#173664!important}.st-key-bl_prev .stButton>button:before{content:"‹"!important}.st-key-bl_next .stButton>button:before{content:"›"!important}.st-key-bl_prev .stButton>button:hover,.st-key-bl_prev .stButton>button:focus,.st-key-bl_next .stButton>button:hover,.st-key-bl_next .stButton>button:focus{border:0!important;background:rgba(126,182,255,.08)!important;box-shadow:none!important}body:has(.bl-theme-state.dark) .st-key-bl_prev .stButton>button:before,body:has(.bl-theme-state.dark) .st-key-bl_next .stButton>button:before{color:#dce7f6!important}}
@media(max-width:900px){body:has(.bl-theme-state.dark) .st-key-bl_prev .stButton>button,body:has(.bl-theme-state.dark) .st-key-bl_next .stButton>button{border:0!important;background:transparent!important;box-shadow:none!important}}

/* Bottom utility row: theme selector immediately to the left of Analytics/Back. */
.st-key-boys_log_theme{position:relative!important;display:flex!important;align-items:center!important;width:auto!important;max-width:none!important;min-height:38px!important;margin:0!important;padding:0!important}
.st-key-boys_log_theme .st-key-bl_theme_choice{position:relative!important;left:auto!important;top:auto!important;width:auto!important;margin:0!important;transform:none!important}
.st-key-boys_log_view_nav [data-testid="stHorizontalBlock"],.st-key-boys_log_analytics_nav [data-testid="stHorizontalBlock"]{display:flex!important;align-items:center!important;justify-content:flex-end!important;gap:10px!important;width:auto!important}
.st-key-boys_log_view_nav [data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-boys_log_analytics_nav [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:0 0 auto!important}
.st-key-boys_log_view_nav .st-key-boys_log_theme [role="radiogroup"],.st-key-boys_log_analytics_nav .st-key-boys_log_theme [role="radiogroup"]{box-shadow:none!important}
@media(max-width:900px){.st-key-boys_log_view_nav{padding:0 8px!important}.st-key-boys_log_view_nav [data-testid="stHorizontalBlock"],.st-key-boys_log_analytics_nav [data-testid="stHorizontalBlock"]{gap:8px!important}.st-key-boys_log_view_nav .st-key-boys_log_theme [role="radiogroup"] label,.st-key-boys_log_analytics_nav .st-key-boys_log_theme [role="radiogroup"] label{min-width:68px!important;padding:0 9px!important}}

/* Formula amount menu: readable popup sizing and full dark-mode treatment. */
[class*="st-key-bl_bottle_menu_"]{left:50%!important;right:auto!important;width:100px!important;min-width:100px!important;transform:translateX(-50%)!important;padding:5px!important;border-radius:11px!important;overflow:hidden!important}
[class*="st-key-bl_bottle_menu_"] .stButton,[class*="st-key-bl_bottle_menu_"] .stButton>button{width:100%!important;margin:0!important}
[class*="st-key-bl_bottle_menu_"] .stButton>button{position:relative!important;inset:auto!important;height:30px!important;min-height:30px!important;border-radius:7px!important;font-size:12px!important;line-height:1!important;padding:0 8px!important;color:#174f9d!important;background:#fff!important}
[class*="st-key-bl_bottle_menu_"] .stButton>button:hover,[class*="st-key-bl_bottle_menu_"] .stButton>button:focus{background:#eef5ff!important;color:#173664!important}
body:has(.bl-theme-state.dark) [class*="st-key-bl_bottle_menu_"]{background:#10243d!important;border-color:#37506d!important;box-shadow:0 16px 36px rgba(0,0,0,.48)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a [class*="st-key-bl_bottle_menu_"]{border-color:rgba(76,141,255,.62)!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_b [class*="st-key-bl_bottle_menu_"]{border-color:rgba(185,161,255,.62)!important}
body:has(.bl-theme-state.dark) [class*="st-key-bl_bottle_menu_"] .stButton>button{height:30px!important;min-height:30px!important;border:0!important;background:#132a46!important;color:#e8eef8!important;box-shadow:none!important}
body:has(.bl-theme-state.dark) [class*="st-key-bl_bottle_menu_"] .stButton>button:hover,body:has(.bl-theme-state.dark) [class*="st-key-bl_bottle_menu_"] .stButton>button:focus{background:#1b3a5e!important;color:#fff!important}
body:has(.bl-theme-state.dark) [class*="st-key-bl_bottle_clear_"] .stButton>button{background:#0d1d33!important;color:#9fb0c6!important}
body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-metric-group.sleep_kpi .bl-metric-line b,body:has(.bl-theme-state.dark) .st-key-bl_panel_a .bl-metric-group.sleep_kpi .bl-metric-line small,body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-metric-group.sleep_kpi .bl-metric-line b,body:has(.bl-theme-state.dark) .st-key-bl_panel_b .bl-metric-group.sleep_kpi .bl-metric-line small{color:#f5f7fb!important}
/* Carry sleep caps through Streamlit's inter-row spacing to the hour divider. */
.bl-sleep-implied.sleep-start .bl-sleep-fill{top:0!important}
.bl-sleep-implied.sleep-end .bl-sleep-fill{bottom:-27px!important}
.bl-sleep-implied.sleep-start.sleep-end .bl-sleep-fill{top:0!important;bottom:-27px!important}
@media(max-width:900px){.bl-sleep-implied.sleep-start .bl-sleep-fill{top:0!important}.bl-sleep-implied.sleep-end .bl-sleep-fill{bottom:-24px!important}.bl-sleep-implied.sleep-start.sleep-end .bl-sleep-fill{top:0!important;bottom:-24px!important}}
/* Each time icon owns only the dotted trail beneath it, through to the divider. */
.bl-time:before{display:none!important}
.bl-time:after{top:calc(50% + 14px)!important;bottom:-27px!important;height:auto!important}
@media(max-width:900px){.bl-time:after{top:calc(50% + 10px)!important;bottom:-24px!important;height:auto!important}}
@media(max-width:1100px){.bl-mobile-title,html.force-mobile .bl-mobile-title{width:100vw!important;max-width:100vw!important;margin-left:calc(50% - 50vw)!important;margin-right:calc(50% - 50vw)!important}.bl-mobile-title h1,html.force-mobile .bl-mobile-title h1{left:50%!important;text-align:center!important}}
@media(max-width:700px),(max-device-width:700px){html.force-mobile .bl-mobile-title h1{left:calc(50% + 12px)!important}}
@media(max-width:700px),(max-device-width:700px){.st-key-boys_log_toolbar{margin-top:0!important}.bl-shell{margin-top:0!important}}
.bl-scroll-anchor{height:0!important;scroll-margin-top:12px!important;}
.bl-mobile-jump-nav{display:none;}
@media(max-width:1100px){
  html{scroll-behavior:smooth;}
  .bl-mobile-jump-nav{position:fixed;left:50%;bottom:calc(73px + env(safe-area-inset-bottom));transform:translate(-50%,12px);z-index:2147483646;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;width:min(calc(100vw - 24px),360px);padding:0;border:0;border-radius:0;background:transparent;box-shadow:none;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .18s ease,transform .18s ease,visibility 0s linear .18s;}
  .bl-mobile-jump-nav.is-active{transform:translate(-50%,0);opacity:1;visibility:visible;pointer-events:auto;transition:opacity .18s ease,transform .18s ease,visibility 0s;}
  .bl-mobile-jump-nav a{display:flex;align-items:center;justify-content:center;height:38px;border:1px solid rgba(122,151,188,.28);border-radius:11px;color:#e8eef8!important;background:rgba(16,36,61,.72);font-size:12px;font-weight:900;letter-spacing:.02em;text-decoration:none!important;-webkit-tap-highlight-color:transparent;}
  .bl-mobile-jump-nav a[href="#bl-baby-a"]{border-color:rgba(76,141,255,.60);background:rgba(76,141,255,.15);}
  .bl-mobile-jump-nav a[href="#bl-baby-b"]{border-color:rgba(185,161,255,.62);background:rgba(139,105,210,.17);}
  .bl-mobile-jump-nav a:hover,.bl-mobile-jump-nav a:focus,.bl-mobile-jump-nav a:active{color:#fff!important;background:rgba(39,66,99,.94);outline:0;box-shadow:none;}
  .st-key-boys_log_view_nav{padding-bottom:76px!important;}
}
</style>""",
    unsafe_allow_html=True,
)


title_koala = icon_data_uri("title_koala")
title_echidna = icon_data_uri("title_echidna")
st.markdown(
    "<div id='bl-top-anchor' class='bl-mobile-title'>"
    f"<img class='bl-title-art-left bl-title-bun-left' src='{title_koala}' alt='Sleeping koala on a crescent moon'>"
    "<h1>Buggins Daily Log</h1>"
    f"<img class='bl-title-art-right bl-title-bun-right' src='{title_echidna}' alt='Sleeping echidna on a star'>"
    "</div>",
    unsafe_allow_html=True,
)

with st.container(key="boys_log_theme_state"):
    theme_choice = st.session_state.get("bl_theme_choice", "Dark")
    st.markdown(
        f"<div class='bl-theme-state {'dark' if theme_choice == 'Dark' else 'light'}'></div>",
        unsafe_allow_html=True,
    )

st.markdown("<div class='bl-shell'>", unsafe_allow_html=True)

with st.container(key="boys_log_toolbar"):
    current_day = selected_day()
    c_prev, c_date, c_today, c_next, c_sync = st.columns([0.8, 2.4, 0.9, 0.8, 1.4])
    with c_prev:
        st.button("‹", key="bl_prev", on_click=shift_day, args=(-1,), use_container_width=True)
    with c_date:
        with st.container(key="bl_date_control"):
            st.markdown(
                f"<div class='bl-date-display'><span class='bl-date-full'>{esc(current_day.strftime('%A, %d %B %Y'))}</span><span class='bl-date-short'>{esc(current_day.strftime('%a, %d %B %Y'))}</span></div>",
                unsafe_allow_html=True,
            )
            picked = st.date_input(
                "Log day",
                label_visibility="collapsed",
                key="bl_date_picker",
                on_change=sync_day_from_picker,
            )
    with c_today:
        st.button("Today", key="bl_today", on_click=use_today, use_container_width=True)
    with c_next:
        st.button("›", key="bl_next", on_click=shift_day, args=(1,), use_container_width=True)
    with c_sync:
        st.markdown(
            f"<div class='bl-sync'>Melbourne time {datetime.now(MEL).strftime('%H:%M')}</div>",
            unsafe_allow_html=True,
        )

day = selected_day()
analytics_view = st.session_state.get("boys_log_view", "log") == "analytics"

if analytics_view:
    with st.container(key="boys_log_analytics_nav"):
        theme_col, back_col = st.columns([1, 1], gap="small")
        with theme_col:
            with st.container(key="boys_log_theme"):
                st.radio(
                    "Theme",
                    ("Light", "Dark"),
                    horizontal=True,
                    index=1,
                    key="bl_theme_choice",
                    label_visibility="collapsed",
                )
        with back_col:
            st.button(
                "Back to log",
                key="bl_view_toggle",
                on_click=toggle_dashboard_view,
            )
    try:
        st.markdown(analytics_dashboard_html(day), unsafe_allow_html=True)
    except baby_log_store.StorageError as exc:
        st.error(str(exc))
    if baby_log_store.storage_warning():
        st.caption("Storage status: shared database unavailable — analytics are using the local cache.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

try:
    events = baby_log_store.load_events(day.isoformat())
except baby_log_store.StorageError as exc:
    st.error(str(exc))
    st.stop()
if baby_log_store.storage_warning():
    st.caption("Storage status: shared database unavailable — viewing the local cache read-only.")
storage_warning_shown = bool(baby_log_store.storage_warning())
events_by_baby_hour_kind: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
events_by_baby_hour: dict[tuple[str, int], list[dict]] = defaultdict(list)
for event in events:
    dt = parse_dt(event.get("event_ts"))
    events_by_baby_hour_kind[(event.get("baby"), dt.hour, event.get("kind"))].append(event)
    events_by_baby_hour[(event.get("baby"), dt.hour)].append(event)

initialise_baby_panels()
cols = st.columns(2)
for idx, (baby_id, baby_label) in enumerate(BABIES):
    with cols[idx]:
        st.markdown(
            f"<div id='bl-baby-{baby_id}' class='bl-scroll-anchor'></div>",
            unsafe_allow_html=True,
        )
        panel = st.container(key=f"bl_panel_{baby_id}")
    with panel:
        is_open = st.session_state.get(f"bl_panel_open_{baby_id}", False)
        panel_state = "open" if is_open else "collapsed"
        baby_totals = totals(events, baby_id)
        sleep_seconds, sleep_hour_classes = sleep_block_summary(events, baby_id, day)
        sleep_value, sleep_unit = format_sleep_duration(sleep_seconds)
        last = baby_totals["last"].strftime("%H:%M") if baby_totals["last"] else "None yet"
        feed_unit = "Feed" if baby_totals["feeds"] == 1 else "Feeds"
        metric_cards = "".join(
            [
                metric_simple_card(
                    "feed_kpi",
                    "Feeds",
                    str(baby_totals["feeds"]),
                    feed_unit,
                ),
                metric_group_card(
                    "nappy",
                    "Nappy Changes",
                    [
                        ("Pee", str(baby_totals["pee"]), ""),
                        ("Poop", str(baby_totals["poop"]), ""),
                    ],
                ),
                metric_group_card(
                    "sleep_kpi",
                    "Sleep",
                    [("Total Sleep", sleep_value, sleep_unit)],
                ),
            ]
        )
        st.markdown(
            f"""
<div class='bl-panel-state {panel_state}'></div>
<div class='bl-toggle-pill'>{'Close' if is_open else 'Tap to log'}</div>
<div class='bl-head'>
  <div class='bl-title'>{esc(baby_label)}<span>{esc(day.strftime('%A %d %b'))}</span></div>
</div>
<div class='bl-summary'>
  {metric_cards}
</div>
""",
            unsafe_allow_html=True,
        )
        st.button(
            " ",
            key=f"bl_toggle_{baby_id}",
            help=f"{'Collapse' if is_open else 'Open'} {baby_label}",
            on_click=toggle_baby_panel,
            args=(baby_id,),
            use_container_width=True,
        )
        if not is_open:
            continue

        header_cells = [
            f"<div class='bl-grid'><div class='bl-grid-baby'>{esc(baby_label)}</div><div class='bl-grid-head'><div>{time_header_label()}</div>"
        ]
        header_cells.extend(f"<div>{header_label(kind, label)}</div>" for kind, label in KINDS)
        header_cells.append("</div>")
        st.markdown("".join(header_cells), unsafe_allow_html=True)

        for hour in range(24):
            now_hour = datetime.now(MEL).hour if day == datetime.now(MEL).date() else None
            current_cls = " current" if hour == now_hour else ""
            with st.container(key=f"blrow_{baby_id}_{hour}"):
                st.markdown(f"<div class='bl-row-wrap{current_cls}'></div>", unsafe_allow_html=True)
                row_cols = st.columns([1.12, 1, 1, 1, 1, 1, 1, 1], gap=None)
                with row_cols[0]:
                    hour_events = events_by_baby_hour.get((baby_id, hour), [])
                    st.markdown(
                        time_cell_label(hour, bool(hour_events)),
                        unsafe_allow_html=True,
                    )
                for cell_col, (kind, _) in zip(row_cols[1:], KINDS):
                    chips = []
                    for event in events_by_baby_hour_kind.get((baby_id, hour, kind), []):
                        chips.append(
                            f"<span class='bl-chip {event_class(kind)}'>"
                            f"{cell_event_label(event)}<small class='bl-chip-time'>{esc(fmt_time(event.get('event_ts')))}</small></span>"
                        )
                    with cell_col:
                        with st.container(key=f"blslot_{baby_id}_{hour}_{kind}"):
                            picker_open = st.session_state.get("boys_log_bottle_picker") == (baby_id, hour)
                            if kind == "bottle" and picker_open:
                                with st.container(key=f"bl_bottle_menu_{baby_id}_{hour}"):
                                    st.button(
                                        "✕ Clear",
                                        key=f"bl_bottle_clear_{baby_id}_{hour}",
                                        on_click=choose_bottle_amount,
                                        args=(baby_id, hour, None),
                                        use_container_width=True,
                                    )
                                    for amount in BOTTLE_AMOUNTS:
                                        st.button(
                                            f"{amount} ml",
                                            key=f"bl_bottle_amount_{baby_id}_{hour}_{amount}",
                                            on_click=choose_bottle_amount,
                                            args=(baby_id, hour, amount),
                                            use_container_width=True,
                                        )
                            else:
                                on_click = open_bottle_picker if kind == "bottle" else toggle_cell_event
                                st.button(
                                    " ",
                                    key=f"blcell_{baby_id}_{hour}_{kind}",
                                    help=f"Log {KIND_LABELS.get(kind, kind)} at {hour_label(hour)} Melbourne time",
                                    on_click=on_click,
                                    args=(baby_id, hour) if kind == "bottle" else (baby_id, kind, hour),
                                    use_container_width=True,
                                )
                            if chips:
                                st.markdown("".join(chips), unsafe_allow_html=True)
                            if kind == "sleep" and sleep_hour_classes.get(hour):
                                st.markdown(sleep_cell_fill(sleep_hour_classes[hour]), unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        baby_events = [event for event in events if event.get("baby") == baby_id]
        log_events = sorted(baby_events, key=lambda event: event.get("event_ts") or "")
        bath_events = sorted(
            [event for event in baby_events if event.get("kind") == "bath"],
            key=lambda event: event.get("event_ts") or "",
        )
        care_details = baby_log_store.load_care_details(day.isoformat(), baby_id)
        if baby_log_store.storage_warning() and not storage_warning_shown:
            st.caption("Storage status: shared database unavailable — viewing the local cache read-only.")
            storage_warning_shown = True
        bath_time = care_details.get("bath_time") or (fmt_sheet_time(bath_events[-1].get("event_ts")) if bath_events else "")
        if bath_time and not care_details.get("bath_time"):
            care_details = baby_log_store.save_care_details(day.isoformat(), baby_id, {"bath_time": bath_time})
        for field in ("length", "weight", "notes"):
            input_key = f"bl_care_{field}_{baby_id}"
            if input_key not in st.session_state:
                value = care_details.get(field, "")
                if field == "length":
                    value = strip_care_unit(value, "cm")
                elif field == "weight":
                    value = strip_care_unit(value, "kg")
                st.session_state[input_key] = value
            elif field == "length":
                st.session_state[input_key] = strip_care_unit(st.session_state.get(input_key, ""), "cm")
            elif field == "weight":
                st.session_state[input_key] = strip_care_unit(st.session_state.get(input_key, ""), "kg")
        with st.container(key=f"bl_care_{baby_id}"):
            st.markdown(
                care_details_card(bath_time),
                unsafe_allow_html=True,
            )
            st.text_input(
                "Length",
                key=f"bl_care_length_{baby_id}",
                label_visibility="collapsed",
                placeholder="",
                on_change=save_care_field,
                args=(baby_id, "length"),
            )
            st.text_input(
                "Weight",
                key=f"bl_care_weight_{baby_id}",
                label_visibility="collapsed",
                placeholder="",
                on_change=save_care_field,
                args=(baby_id, "weight"),
            )
            st.text_input(
                "Notes",
                key=f"bl_care_notes_{baby_id}",
                label_visibility="collapsed",
                placeholder="Add note",
                on_change=save_care_field,
                args=(baby_id, "notes"),
            )
            with st.container(key=f"bl_bath_btn_{baby_id}"):
                st.button(
                    "Log bath time",
                    key=f"bl_bath_time_{baby_id}",
                    help=f"Log bath time for {baby_label}",
                    on_click=log_bath_time,
                    args=(baby_id,),
                    use_container_width=True,
                )
        st.markdown(
            f"<div class='bl-care-updated'>Last updated {esc(last)}</div>",
            unsafe_allow_html=True,
        )
        with st.container(key=f"bl_daily_log_{baby_id}"):
            with st.expander("Daily Log", expanded=False):
                st.markdown(
                    f"<div class='bl-log'><div class='bl-log-date'>{esc(day.strftime('%A %d %B %Y'))}</div>",
                    unsafe_allow_html=True,
                )
                if not log_events:
                    st.markdown("<div class='bl-empty'>No logs for this day yet.</div>", unsafe_allow_html=True)
                for event in log_events:
                    detail = event_label(event)
                    note = event.get("note") or KIND_LABELS.get(event.get("kind"), "Other")
                    if event.get("kind") in ("left", "right", "bottle", "pee", "poop", "bath"):
                        note = ""
                    show_note = note and note != detail
                    st.markdown(
                        "<div class='bl-event'>"
                        f"<time>{esc(fmt_time(event.get('event_ts')))}</time>"
                        f"<div><b>{esc(detail)}</b>"
                        + (f"<span>{esc(note)}</span>" if show_note else "")
                        + "</div></div>",
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
st.markdown(
    """
<nav class="bl-mobile-jump-nav" aria-label="Quick page navigation">
  <a href="#bl-top-anchor" aria-label="Back to top">↑ Top</a>
  <a href="#bl-baby-a">Baby A</a>
  <a href="#bl-baby-b">Baby B</a>
</nav>
""",
    unsafe_allow_html=True,
)
components.html(
    """
<script>
(() => {
  const w = window.parent;
  const doc = w.document;
  if (w.__blMobileJumpCleanup) w.__blMobileJumpCleanup();

  const scrollHost = doc.querySelector('[data-testid="stMain"]') || w;
  let frame = 0;
  const update = () => {
    frame = 0;
    const nav = doc.querySelector('.bl-mobile-jump-nav');
    if (!nav) return;
    const compact = w.matchMedia('(max-width: 1100px)').matches;
    const openPanels = [...doc.querySelectorAll(
      '.st-key-bl_panel_a:has(.bl-panel-state.open), .st-key-bl_panel_b:has(.bl-panel-state.open)'
    )];
    const reachedFiveAm = openPanels.some((panel) => {
      const baby = panel.classList.contains('st-key-bl_panel_a') ? 'a' : 'b';
      const fiveAmRow = doc.querySelector(`.st-key-blrow_${baby}_5`);
      return fiveAmRow && fiveAmRow.getBoundingClientRect().top < Math.max(180, Math.min(650, w.innerHeight - 132));
    });
    nav.classList.toggle('is-active', compact && reachedFiveAm);
  };
  const schedule = () => {
    if (!frame) frame = w.requestAnimationFrame(update);
  };
  const observer = new MutationObserver(schedule);
  observer.observe(doc.body, {childList: true, subtree: true});
  scrollHost.addEventListener('scroll', schedule, {passive: true});
  w.addEventListener('resize', schedule, {passive: true});
  w.addEventListener('orientationchange', schedule, {passive: true});
  w.__blMobileJumpCleanup = () => {
    observer.disconnect();
    scrollHost.removeEventListener('scroll', schedule);
    w.removeEventListener('resize', schedule);
    w.removeEventListener('orientationchange', schedule);
    if (frame) w.cancelAnimationFrame(frame);
  };
  update();
})();
</script>
""",
    height=0,
)
with st.container(key="boys_log_view_nav"):
    theme_col, analytics_col = st.columns([1, 1], gap="small")
    with theme_col:
        with st.container(key="boys_log_theme"):
            st.radio(
                "Theme",
                ("Light", "Dark"),
                horizontal=True,
                index=1,
                key="bl_theme_choice",
                label_visibility="collapsed",
            )
    with analytics_col:
        st.button(
            "Analytics",
            key="bl_view_toggle",
            on_click=toggle_dashboard_view,
        )
