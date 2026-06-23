"""Trade Alerts - saved AI-assisted alert rules."""
from __future__ import annotations

import base64
from datetime import datetime
import html
import os
from urllib.parse import quote

import streamlit as st

import alert_store
import alert_watcher
import chrome
import scanner


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ASSET_DIR = os.path.join(_ROOT, "assets")


def _svg_data_uri(filename: str) -> str:
    path = os.path.join(_ASSET_DIR, filename)
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/svg+xml;base64,{encoded}"


_ICON_PAUSE = _svg_data_uri("alert-pause.svg")
_ICON_PLAY = _svg_data_uri("alert-play.svg")
_ICON_DELETE = _svg_data_uri("alert-delete.svg")


st.set_page_config(page_title="Alerts", page_icon="🔔", layout="wide")
chrome.render_header("TRADE", "ALERTS", brand=False)

st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + "[data-testid='stMain'],[data-testid='stMainBlockContainer']{background:transparent!important;}"
    + "[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none!important;}"
    ".st-key-alertbrand{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:6px;}"
    ".alert-actions{display:flex;gap:9px;align-items:center;justify-content:flex-end;}"
    ".alert-pillbtn{display:inline-flex;align-items:center;justify-content:center;border:1px solid rgba(76,141,255,.68);"
    "border-radius:999px;padding:7px 14px;color:#e6e8eb;background:rgba(76,141,255,.12);font-size:.78rem;"
    "font-weight:800;text-decoration:none!important;white-space:nowrap;}"
    ".alert-pillbtn:hover,.alert-pillbtn:focus,.alert-pillbtn:visited{text-decoration:none!important;}"
    ".alert-pillbtn.ghost{border-color:rgba(230,232,235,.18);background:rgba(10,14,20,.25);color:#aab2bd;}"
    ".alert-meta{color:#8b94a0;font-size:.8rem;line-height:1.35;margin:0 0 14px;"
    "padding-bottom:8px;border-bottom:1px solid #2a2f3a;}"
    ".alert-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:15px;}"
    ".alert-stat{background:#13101e;border:1px solid rgba(139,92,246,.36);border-radius:10px;padding:13px 14px;}"
    ".alert-stat .cap{font-size:.63rem;color:#8b94a0;font-weight:900;letter-spacing:.09em;text-transform:uppercase;}"
    ".alert-stat .big{font-size:1.65rem;font-weight:900;line-height:1;margin-top:8px;color:#e6e8eb;}"
    ".alert-stat .sub{font-size:.74rem;color:#aab2bd;margin-top:6px;}"
    ".alert-stat .amber{color:#e0a33e}.alert-stat .green{color:#2ebd85}.alert-stat .blue{color:#4c8dff}"
    ".alert-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:18px 0 11px;}"
    ".st-key-alert_filter_bar{margin:18px 0 11px;}"
    ".st-key-alert_filter_bar [data-testid='stWidgetLabel']{display:none!important;}"
    ".st-key-alert_filter_bar [data-testid='stPills']{display:flex;gap:7px;flex-wrap:wrap;}"
    ".st-key-alert_filter_bar [data-testid='stPills'] button{border:1px solid rgba(230,232,235,.18)!important;"
    "border-radius:999px!important;background:rgba(10,14,20,.25)!important;color:#4c8dff!important;"
    "font-size:.72rem!important;font-weight:900!important;padding:7px 11px!important;min-height:0!important;}"
    ".st-key-alert_filter_bar [data-testid='stPills'] button:hover{border-color:rgba(76,141,255,.55)!important;color:#dce3ec!important;}"
    ".st-key-alert_filter_bar button[data-testid='stBaseButton-pillsActive'],"
    ".st-key-alert_filter_bar [data-testid='stPills'] button[aria-pressed='true'],"
    ".st-key-alert_filter_bar [data-testid='stPills'] button[aria-selected='true']{"
    "border-color:rgba(76,141,255,.75)!important;background:rgba(76,141,255,.16)!important;color:#e6e8eb!important;}"
    ".alert-search-placeholder{display:inline-flex;align-items:center;border:1px solid rgba(230,232,235,.18);"
    "border-radius:999px;background:rgba(10,14,20,.25);color:#aab2bd;font-size:.72rem;font-weight:900;"
    "padding:7px 11px;text-decoration:none;}"
    ".alert-grid{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:12px;align-items:start;}"
    ".alert-table{background:#10141b;border:1px solid rgba(139,92,246,.36);border-radius:10px;overflow:hidden;}"
    ".alert-head,.alert-row{display:grid;grid-template-columns:110px 92px minmax(220px,1fr) 115px 105px 92px;}"
    ".alert-head{background:#13101e;color:#8b94a0;font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;font-weight:900;}"
    ".alert-head>div,.alert-row>div{padding:11px 10px;border-right:1px solid #252c37;}"
    ".alert-head>div:last-child,.alert-row>div:last-child{border-right:0;}"
    ".alert-row{background:#11161d;border-top:1px solid #252c37;min-height:88px;}"
    ".asym strong{display:block;font-size:.86rem;color:#e6e8eb;}.asym span{display:block;color:#8b94a0;font-size:.7rem;line-height:1.35;margin-top:4px;}"
    ".apill{display:inline-flex;width:fit-content;align-items:center;border:1px solid currentColor;border-radius:999px;padding:3px 8px;"
    "font-size:.62rem;font-weight:900;text-transform:uppercase;letter-spacing:.04em;color:#aab2bd;}"
    ".apill.long{color:#2ebd85}.apill.short{color:#f6465d}.apill.watch{color:#e0a33e}.apill.blue{color:#4c8dff}"
    ".acond b{display:block;color:#e8edf6;font-size:.82rem;margin-bottom:4px;line-height:1.28;}"
    ".acond span{display:block;color:#aab2bd;font-size:.74rem;line-height:1.35;}"
    ".asetup{margin-top:8px;padding-top:7px;border-top:1px dashed #2c3440;color:#8b94a0;font-size:.68rem;line-height:1.35;}"
    ".asetup b{display:inline;color:#cdd3da;font-size:.68rem;margin:0;}"
    ".adist strong{display:block;font-size:1rem;color:#e6e8eb;line-height:1.1;}.adist strong.amber{color:#e0a33e}.adist strong.green{color:#2ebd85}.adist strong.blue{color:#4c8dff}"
    ".abar{height:7px;background:#242b35;border-radius:99px;overflow:hidden;margin-top:8px;}.abar i{display:block;height:100%;border-radius:99px;background:#e0a33e;}"
    ".astatus small{display:block;color:#8b94a0;font-size:.68rem;margin-top:6px;line-height:1.25;}"
    ".aacts{display:flex;flex-direction:column;gap:6px;align-items:center;}"
    ".aact{display:inline-flex;align-items:center;justify-content:center;width:27px;height:27px;border:1px solid rgba(230,232,235,.18);"
    "border-radius:7px;color:#aab2bd;text-decoration:none!important;font-size:.86rem;font-weight:900;background:rgba(10,14,20,.22);}"
    ".aact:hover,.aact:focus,.aact:visited{text-decoration:none!important;}"
    ".aact img{display:block;width:15px;height:15px;filter:invert(75%) sepia(7%) saturate(316%) hue-rotate(177deg) brightness(88%) contrast(86%);}"
    ".aact:hover img{filter:invert(100%);}.aact.delete:hover img{filter:none;}"
    ".aact:hover{border-color:#4c8dff;color:#e6e8eb;}.aact.delete:hover{border-color:#f6465d;color:#f6465d;}"
    ".alert-side{display:flex;flex-direction:column;gap:12px;}"
    ".alert-panel{background:#13101e;border:1px solid rgba(139,92,246,.36);border-radius:10px;padding:14px;}"
    ".alert-panel h3{margin:0 0 12px;font-size:.66rem;color:#8b94a0;letter-spacing:.09em;text-transform:uppercase;}"
    ".aevent{border-top:1px solid #252c37;padding:11px 0;}.aevent:first-of-type{border-top:0;padding-top:0;}"
    ".aevent strong{display:block;font-size:.82rem;color:#e6e8eb;}.aevent span{display:block;color:#aab2bd;font-size:.74rem;line-height:1.35;margin-top:4px;}"
    ".aevent small{display:block;color:#8b94a0;font-size:.66rem;margin-top:6px;}"
    ".routeitem{display:flex;justify-content:space-between;gap:10px;border:1px solid #252c37;border-radius:8px;padding:9px 10px;"
    "background:#11161d;font-size:.74rem;margin-top:8px;}.routeitem span{color:#8b94a0;text-align:right;}"
    ".empty-alerts{background:#13101e;border:1px solid rgba(139,92,246,.36);border-radius:10px;padding:28px 24px;color:#aab2bd;}"
    ".empty-alerts b{display:block;color:#e6e8eb;font-size:1rem;margin-bottom:6px;}"
    "@media(max-width:1050px){.alert-stats,.alert-grid{grid-template-columns:1fr}.alert-head{display:none}"
    ".alert-row{grid-template-columns:1fr}.alert-row>div{border-right:0;border-bottom:1px solid #252c37}.alert-row>div:last-child{border-bottom:0}}"
    "</style>",
    unsafe_allow_html=True,
)


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _fmt_price(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    if v >= 1:
        return f"${v:,.2f}"
    if v >= 0.01:
        return f"${v:.4f}"
    return f"${v:.6f}"


def _href(action: str, alert_id: str) -> str:
    return f"?alert_action={quote(action)}&alert_id={quote(alert_id or '')}"


def _status_href(action: str) -> str:
    return f"?alert_action={quote(action)}"


def _set_many_alerts_status(current_status: str, new_status: str) -> int:
    alerts = alert_store.load_alerts()
    changed = 0
    now = datetime.now().isoformat(timespec="seconds")
    for alert in alerts:
        if (alert.get("status") or "active") == current_status:
            alert["status"] = new_status
            alert["updated_at"] = now
            changed += 1
    if changed:
        alert_store.save_alerts(alerts)
    return changed


def _handle_action() -> None:
    action = st.query_params.get("alert_action")
    alert_id = st.query_params.get("alert_id")
    if not action:
        return
    if action == "pause_all":
        count = _set_many_alerts_status("active", "paused")
        st.toast(f"{count} alert{'s' if count != 1 else ''} paused.", icon="🔔")
    elif action == "resume_all":
        count = _set_many_alerts_status("paused", "active")
        st.toast(f"{count} alert{'s' if count != 1 else ''} resumed.", icon="🔔")
    elif not alert_id:
        return
    elif action == "delete":
        alert_store.delete_alert(alert_id)
        st.toast("Alert deleted.", icon="🔔")
    elif action == "pause":
        alert_store.set_status(alert_id, "paused")
        st.toast("Alert paused.", icon="🔔")
    elif action == "resume":
        alert_store.set_status(alert_id, "active")
        st.toast("Alert resumed.", icon="🔔")
    st.query_params.clear()
    st.rerun()


def _run_watcher_once(show_toast: bool = False) -> dict:
    try:
        result = alert_watcher.check_alerts()
    except Exception as exc:
        return {"checked": 0, "triggered": [], "errors": [{"error": str(exc)}], "checked_at": datetime.now().isoformat(timespec="seconds")}
    if show_toast and result.get("triggered"):
        st.toast(f"{len(result['triggered'])} alert triggered.", icon="🔔")
    return result


def _ticker_price(symbol: str) -> float | None:
    try:
        q = scanner.live_ticker(symbol)
        return float(q["last"]) if q and q.get("last") is not None else None
    except Exception:
        return None


def _proximity(alert: dict, price: float | None) -> dict:
    status = (alert.get("status") or "active").lower()
    if status == "paused":
        return {"label": "Paused", "class": "", "distance": "Paused", "bar": 0, "tone": ""}
    if status in {"triggered", "acknowledged"}:
        return {"label": "Triggered", "class": "green", "distance": "Triggered", "bar": 100, "tone": "green"}
    typ = (alert.get("type") or "").lower()
    if "candle" in typ or "close" in typ:
        tf = alert.get("timeframe") or "selected chart"
        return {"label": "Waiting", "class": "blue", "distance": f"{tf} close", "bar": 25, "tone": "blue"}
    if price is None:
        return {"label": "Active", "class": "", "distance": "No price", "bar": 0, "tone": ""}
    zone = alert.get("zone") if isinstance(alert.get("zone"), dict) else {}
    low = _to_float(zone.get("low"))
    high = _to_float(zone.get("high"))
    level = _to_float(alert.get("level"))
    if low is not None and high is not None:
        lo, hi = sorted([low, high])
        if lo <= price <= hi:
            return {"label": "Triggered", "class": "green", "distance": "In zone", "bar": 100, "tone": "green"}
        target = lo if price < lo else hi
        pct = abs(target - price) / price * 100 if price else 0
        side = "below" if price < lo else "above"
        return _distance_state(pct, f"{pct:.1f}% {side}")
    if level is not None:
        pct = abs(level - price) / price * 100 if price else 0
        side = "below" if price < level else "above"
        return _distance_state(pct, f"{pct:.1f}% {side}")
    return {"label": "Active", "class": "", "distance": "Watching", "bar": 45, "tone": ""}


def _distance_state(pct: float, text: str) -> dict:
    if pct <= 0.8:
        return {"label": "Approaching", "class": "watch", "distance": text, "bar": 88, "tone": "amber"}
    if pct <= 2.0:
        return {"label": "Active", "class": "", "distance": text, "bar": 62, "tone": ""}
    return {"label": "Active", "class": "", "distance": text, "bar": 32, "tone": ""}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _symbol_line(alert: dict) -> str:
    grade = alert.get("grade")
    pattern = alert.get("pattern") or "AI-assisted alert"
    tail = f"Grade {grade}" if grade else "Saved alert"
    return f"{pattern[:28]}{'...' if len(pattern) > 28 else ''} · {tail}"


def _setup_context(alert: dict) -> str:
    setup = alert.get("setup_snapshot") if isinstance(alert.get("setup_snapshot"), dict) else {}
    if not setup:
        return ""
    entry = setup.get("entry_zone") or {}
    stop = setup.get("stop") or {}
    t1 = setup.get("t1") or {}
    t2 = setup.get("t2") or {}
    summary = setup.get("summary") or ""
    bits = []
    if entry.get("label"):
        bits.append(f"<b>Entry</b> {_esc(entry.get('label'))}")
    if stop.get("label"):
        bits.append(f"<b>Stop</b> {_esc(stop.get('label'))}")
    if t1.get("label"):
        bits.append(f"<b>TP1</b> {_esc(t1.get('label'))}{(' ' + _esc(t1.get('rr'))) if t1.get('rr') else ''}")
    if t2.get("label"):
        bits.append(f"<b>TP2</b> {_esc(t2.get('label'))}{(' ' + _esc(t2.get('rr'))) if t2.get('rr') else ''}")
    if summary:
        bits.append(f"<b>Thesis</b> {_esc(summary[:190])}{'...' if len(summary) > 190 else ''}")
    if not bits:
        return ""
    return "<div class='asetup'>" + "<br>".join(bits) + "</div>"


def _render_row(alert: dict, price: float | None) -> str:
    prox = _proximity(alert, price)
    direction = (alert.get("direction") or "watch").lower()
    dcls = "long" if direction == "long" else "short" if direction == "short" else "watch"
    aid = alert.get("id") or ""
    pause_icon = f"<img src='{_ICON_PAUSE}' alt=''>" if _ICON_PAUSE else "Ⅱ"
    resume_icon = f"<img src='{_ICON_PLAY}' alt=''>" if _ICON_PLAY else "▶"
    delete_icon = f"<img src='{_ICON_DELETE}' alt=''>" if _ICON_DELETE else "×"
    condition = alert.get("condition") or alert.get("note") or "Watch condition"
    note = alert.get("note") or alert.get("type") or "AI-assisted alert rule"
    trigger = alert.get("trigger") if isinstance(alert.get("trigger"), dict) else {}
    if trigger.get("message"):
        note = f"Triggered: {trigger.get('message')} · {note}"
    last = datetime.now().strftime("%H:%M:%S")
    bar_color = "#2ebd85" if prox["tone"] == "green" else "#4c8dff" if prox["tone"] == "blue" else "#e0a33e"
    return (
        "<div class='alert-row'>"
        f"<div class='asym'><strong>{_esc(alert.get('symbol') or '')}</strong><span>{_esc(_symbol_line(alert))}</span></div>"
        f"<div><span class='apill {dcls}'>{_esc(direction or 'watch')}</span></div>"
        f"<div class='acond'><b>{_esc(condition)}</b><span>{_esc(note)}</span>{_setup_context(alert)}</div>"
        f"<div class='adist'><strong class='{_esc(prox['tone'])}'>{_esc(prox['distance'])}</strong>"
        f"<div class='abar'><i style='width:{int(prox['bar'])}%;background:{bar_color}'></i></div></div>"
        f"<div class='astatus'><span class='apill {_esc(prox['class'])}'>{_esc(prox['label'])}</span><small>{_esc(last)}</small></div>"
        "<div class='aacts'>"
        f"<a class='aact' href='{_href('pause', aid)}' title='Pause' aria-label='Pause'>{pause_icon}</a>"
        f"<a class='aact' href='{_href('resume', aid)}' title='Resume' aria-label='Resume'>{resume_icon}</a>"
        f"<a class='aact delete' href='{_href('delete', aid)}' title='Delete' aria-label='Delete'>{delete_icon}</a>"
        "</div></div>"
    )


_handle_action()

watcher_result = _run_watcher_once(show_toast=True)


@st.fragment(run_every=30)
def _watcher_tick():
    _run_watcher_once(show_toast=True)


_watcher_tick()

brand = st.container(key="alertbrand")
brand.markdown(
    chrome.brand_html("TRADE", "ALERTS")
    + "<div class='alert-actions'>"
    + f"<a class='alert-pillbtn ghost' href='{_status_href('pause_all')}'>Pause All</a>"
    + f"<a class='alert-pillbtn ghost' href='{_status_href('resume_all')}'>Resume All</a>"
    + "<a class='alert-pillbtn' href='?'>Refresh Now</a>"
    + "</div>",
    unsafe_allow_html=True,
)

alerts = alert_store.load_alerts()
active_alerts = [a for a in alerts if (a.get("status") or "active") == "active"]
paused_alerts = [a for a in alerts if a.get("status") == "paused"]
triggered_alerts = [a for a in alerts if a.get("status") in {"triggered", "acknowledged"}]

prices = {}
for alert in alerts[:40]:
    sym = (alert.get("symbol") or "").upper()
    if sym and sym not in prices:
        prices[sym] = _ticker_price(sym)

prox_map = {a.get("id"): _proximity(a, prices.get((a.get("symbol") or "").upper())) for a in alerts}
approaching = [a for a in active_alerts if prox_map.get(a.get("id"), {}).get("label") == "Approaching"]
entry_zone_count = sum(1 for a in active_alerts if "zone" in (a.get("type") or "").lower() or isinstance(a.get("zone"), dict))
candle_count = sum(1 for a in active_alerts if "candle" in (a.get("type") or "").lower() or "close" in (a.get("type") or "").lower())

st.markdown(
    "<div class='alert-meta'>"
    f"AI-assisted alert watch list &middot; Bybit live-price and closed-candle watcher &middot; "
    f"Last checked <b>{datetime.now().strftime('%H:%M:%S')}</b> "
    f"&middot; Checked <b>{watcher_result.get('checked', 0)}</b> active alert(s)"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    "<section class='alert-stats'>"
    f"<div class='alert-stat'><div class='cap'>Active Alerts</div><div class='big'>{len(active_alerts)}</div>"
    f"<div class='sub'>{entry_zone_count} price zones &middot; {candle_count} candle-close rules</div></div>"
    f"<div class='alert-stat'><div class='cap'>Approaching</div><div class='big amber'>{len(approaching)}</div>"
    "<div class='sub'>Within 0.8% of level or zone</div></div>"
    f"<div class='alert-stat'><div class='cap'>Triggered</div><div class='big green'>{len(triggered_alerts)}</div>"
    "<div class='sub'>Triggered alerts</div></div>"
    "<div class='alert-stat'><div class='cap'>Watcher Status</div><div class='big blue'>Live</div>"
    "<div class='sub'>Runs while Alerts page is open</div></div>"
    "</section>",
    unsafe_allow_html=True,
)

tabs = [
    ("active", "All Active"),
    ("approaching", "Approaching"),
    ("candle", "Candle Close"),
    ("zones", "Entry Zones"),
    ("triggered", "Triggered"),
    ("paused", "Paused"),
]
tab_labels = [label for _, label in tabs]
tab_by_label = {label: key for key, label in tabs}
if "alert_view_label" not in st.session_state:
    st.session_state.alert_view_label = "All Active"

with st.container(key="alert_filter_bar"):
    filter_cols = st.columns([4.3, 1.2], vertical_alignment="top")
    with filter_cols[0]:
        selected_label = st.pills(
            "",
            tab_labels,
            selection_mode="single",
            key="alert_view_label",
            label_visibility="collapsed",
        )
    with filter_cols[1]:
        st.markdown("<span class='alert-search-placeholder'>Filter by ticker or condition...</span>", unsafe_allow_html=True)

view = tab_by_label.get(selected_label or st.session_state.get("alert_view_label"), "active")

if view == "approaching":
    visible = approaching
elif view == "candle":
    visible = [a for a in active_alerts if "candle" in (a.get("type") or "").lower() or "close" in (a.get("type") or "").lower()]
elif view == "zones":
    visible = [a for a in active_alerts if "zone" in (a.get("type") or "").lower() or isinstance(a.get("zone"), dict)]
elif view == "triggered":
    visible = triggered_alerts
elif view == "paused":
    visible = paused_alerts
else:
    visible = active_alerts

rows = "".join(_render_row(a, prices.get((a.get("symbol") or "").upper())) for a in visible)
if not rows:
    rows = (
        "<div class='empty-alerts'><b>No alerts in this view yet.</b>"
        "Set an alert from any Trade Setup card and it will appear here. "
        "While this page is open, the local watcher will check saved rules against live Bybit data and closed candles.</div>"
    )
else:
    rows = (
        "<div class='alert-table'><div class='alert-head'>"
        "<div>Symbol</div><div>Setup</div><div>Condition</div><div>Distance</div><div>Last Check</div><div>Actions</div>"
        "</div>"
        + rows
        + "</div>"
    )

events = triggered_alerts[:3] or approaching[:3] or active_alerts[:3]
event_html = ""
for alert in events:
    setup = alert.get("setup_snapshot") if isinstance(alert.get("setup_snapshot"), dict) else {}
    entry = (setup.get("entry_zone") or {}).get("label") if setup else ""
    stop = (setup.get("stop") or {}).get("label") if setup else ""
    trigger = alert.get("trigger") if isinstance(alert.get("trigger"), dict) else {}
    detail = trigger.get("message") or alert.get("condition") or alert.get("note") or ""
    if entry or stop:
        detail += f" Original trade: entry {entry or '-'}, stop {stop or '-'}."
    event_html += (
        "<div class='aevent'>"
        f"<strong>{_esc(alert.get('symbol'))} {_esc(alert.get('label') or 'Watch condition')}</strong>"
        f"<span>{_esc(detail)}</span>"
        f"<small>{_esc(alert.get('status') or 'active')} &middot; {_esc(alert.get('created_at') or 'saved alert')}</small>"
        "</div>"
    )
if not event_html:
    event_html = "<div class='aevent'><strong>No alert activity yet</strong><span>Saved alerts will feed this panel once they exist.</span></div>"

st.markdown(
    "<section class='alert-grid'>"
    + rows
    + "<aside class='alert-side'>"
    + "<div class='alert-panel'><h3>Alert Feed</h3>"
    + event_html
    + "</div>"
    + "<div class='alert-panel'><h3>Watcher Route</h3>"
    + "<div class='routeitem'><b>Data</b><span>Bybit price + candles</span></div>"
    + "<div class='routeitem'><b>Logic</b><span>Price zones + closed candles</span></div>"
    + "<div class='routeitem'><b>Notify</b><span>Dashboard trigger state + Telegram</span></div>"
    + "<div class='routeitem'><b>Cloud</b><span>Optional always-on phase</span></div>"
    + "</div></aside></section>",
    unsafe_allow_html=True,
)
