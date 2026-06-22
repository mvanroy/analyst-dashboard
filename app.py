"""Orion-Lite — a live Binance Futures activity dashboard.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import base64
import glob
import html
import json
import os
import re
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from st_aggrid import AgGrid, JsCode

import icons
import openai_analysis
import rules
import scanner
import chrome  # shared nav/clocks/brand chrome (single source of truth)

GREEN = "#0ecb81"
RED = "#f6465d"
NEUTRAL = "#848e9c"

LOGO_PATH = chrome.LOGO_PATH

st.set_page_config(page_title="Market Scanner", layout="wide", page_icon=LOGO_PATH)

chrome.inject_background()

# ---------------- Orion-style chrome ----------------
st.markdown(
    """
    <style>
      [data-testid="stToolbar"] {display: none;}
      /* the default Streamlit header is a 60px opaque bar pinned on top of the
         page (z-index ~999990); it was covering the top of our headings, so hide it */
      [data-testid="stHeader"] {display: none;}
      /* we surface page navigation as an in-page list (top-left), so hide the
         default sidebar page-nav */
      [data-testid="stSidebarNav"] {display: none;}
      /* lay the page-nav links out horizontally (a row, not a stack) */
      .st-key-topnav {flex-direction: row !important; gap: 1.1rem; align-items: center;}
      .st-key-topnav [data-testid="stElementContainer"] {width: auto !important;}
      .st-key-topnav [data-testid="stMarkdownContainer"] p {
        width: auto !important; overflow: visible !important;
        text-overflow: clip !important; white-space: nowrap;}
      footer {display: none;}
      .block-container {padding-top: 1.6rem; padding-bottom: 1rem; max-width: 100%;}
      .orion-brand {display: flex; align-items: center; gap: .7rem;}
      .orion-brand img {width: 54px; height: 54px;}
      /* align the page heading vertically with the other pages (Trade Dashboard /
         Position Calculator) so it doesn't jump when switching pages */
      [data-testid="stHorizontalBlock"]:has(.orion-brand) {margin-top: 12px !important;}
      .orion-logo {font-size: 1.7rem; font-weight: 800; letter-spacing: .04em; color: #e6e8eb; line-height: 1.1;}
      .orion-logo .accent {color: #4c8dff;}
      .orion-logo .sub {display: block; font-size: .8rem; font-weight: 400; color: #848e9c; letter-spacing: .02em;}
      .orion-meta {color: #5b626c; font-size: .8rem; margin-top: .2rem;}
      .st-key-entry_zone_heading {margin: 1.05rem 0 .45rem 0;}
      .st-key-entry_zone_heading [data-testid="stHorizontalBlock"] {align-items: flex-start;}
      .st-key-entry_zone_filters {margin: -.15rem 0 .65rem 0;}
      .st-key-entry_zone_filters [data-testid="stWidgetLabel"] {
        display: none !important;
      }
      .st-key-entry_zone_filters [role="radiogroup"] {
        display: flex; flex-wrap: wrap; gap: .5rem;
      }
      .st-key-entry_zone_filters label {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 30px;
        border: 1px solid #1f2a38;
        border-radius: 9999px;
        padding: .22rem .82rem;
        background: #0e1117;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,.015);
        color: #9aa3ae;
        transition: border-color .15s ease, background .15s ease, color .15s ease;
      }
      .st-key-entry_zone_filters label:hover {
        border-color: rgba(76,141,255,.55);
        color: #dce3ec;
      }
      .st-key-entry_zone_filters label > div:first-child:not([data-testid="stMarkdownContainer"]) {
        display: none;
      }
      .st-key-entry_zone_filters label [data-testid="stMarkdownContainer"] p {
        margin: 0;
        line-height: 1.15;
        transform: translateY(-.5px);
      }
      .st-key-entry_zone_filters label:has(input:checked) {
        border-color: rgba(76,141,255,.85);
        background: rgba(76,141,255,.16);
        color: #e6e8eb;
        box-shadow: 0 0 0 1px rgba(76,141,255,.14), inset 0 0 0 1px rgba(255,255,255,.025);
      }
      .st-key-entry_zone_filters label:has(input:checked) [data-testid="stMarkdownContainer"] p {
        color: #e6e8eb;
        font-weight: 700;
      }
      .st-key-entry_zone_filters [data-testid="stMarkdownContainer"] p {
        color: inherit; font-size: .72rem; margin: 0;
      }
      .st-key-entry_zone_watchlist {
        margin: 0 0 1.15rem 0;
        border: 0;
        border-radius: 0;
        background: transparent;
        box-shadow: none;
        padding: 0;
      }
      .ezw-time {font-size: .76rem; color: #6f7885; text-align: right; margin-top: 5px;}
      .ezw-scan-note {font-size: .76rem; color: #8b94a0; margin: -.25rem 0 .65rem 0;}
      .ezw-empty {border-top: 1px solid #252b35; padding-top: 12px; color: #8b94a0; font-size: .84rem;}
      .ezw-table {
        width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; font-size: .78rem;
        background: #0e1117; border: 1px solid #1f2329; border-radius: 6px; overflow: hidden;
      }
      .ezw-table th {
        color: #8b94a0; font-size: .68rem; letter-spacing: .06em; text-transform: uppercase;
        text-align: left; padding: 8px 7px; border-bottom: 1px solid #252b35;
      }
      .ezw-table td {padding: 9px 7px; border-bottom: 1px solid #191f28; color: #d7dde5; vertical-align: top;}
      .ezw-table tr:last-child td {border-bottom: none;}
      .ezw-table th:nth-child(1), .ezw-table td:nth-child(1) {width: 128px; padding-right: 16px;}
      .ezw-table th:nth-child(2), .ezw-table td:nth-child(2) {width: 58px; text-align: center;}
      .ezw-table th:nth-child(3), .ezw-table td:nth-child(3) {width: 72px;}
      .ezw-table th:nth-child(5), .ezw-table td:nth-child(5) {width: 112px;}
      .ezw-table th:nth-child(7), .ezw-table td:nth-child(7) {width: 92px;}
      .ezw-table th:nth-child(8), .ezw-table td:nth-child(8) {width: 104px;}
      .ezw-symbol {display: flex; align-items: center; gap: 8px; min-width: 0; white-space: nowrap;}
      .ezw-symbol b {overflow: hidden; text-overflow: ellipsis;}
      .ezw-symbol img {width: 19px; height: 19px; border-radius: 50%; background: #111827;}
      .ezw-grade {
        display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px;
        border-radius: 7px; font-weight: 900; color: #f0f2f5;
      }
      .ezw-grade-a {border: 1px solid rgba(14,203,129,.75); background: rgba(14,203,129,.15); color: #0ecb81;}
      .ezw-grade-b {border: 1px solid rgba(76,141,255,.75); background: rgba(76,141,255,.15); color: #9fc0ff;}
      .ezw-grade-c {border: 1px solid rgba(227,160,8,.7); background: rgba(227,160,8,.14); color: #e3a008;}
      .ezw-dir-long, .ezw-dir-short {
        display: inline-flex; align-items: center; justify-content: center; min-width: 50px;
        border-radius: 999px; padding: 2px 8px; font-size: .68rem; font-weight: 900;
      }
      .ezw-dir-long {color: #0ecb81; border: 1px solid rgba(14,203,129,.45); background: rgba(14,203,129,.10);}
      .ezw-dir-short {color: #f6465d; border: 1px solid rgba(246,70,93,.45); background: rgba(246,70,93,.10);}
      .ezw-status {display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: .68rem; font-weight: 800;}
      .ezw-status.approaching {color: #e3a008; border: 1px solid rgba(227,160,8,.45); background: rgba(227,160,8,.12);}
      .ezw-status.waiting {color: #9fc0ff; border: 1px solid rgba(76,141,255,.45); background: rgba(76,141,255,.10);}
      .ezw-status.at-zone {color: #0ecb81; border: 1px solid rgba(14,203,129,.45); background: rgba(14,203,129,.10);}
      .ezw-status.below-zone, .ezw-status.above-zone {color: #b7c2d0; border: 1px solid rgba(183,194,208,.35); background: rgba(183,194,208,.08);}
      .ezw-subline {margin-top: 4px; color: #8b94a0; font-size: .69rem; line-height: 1.25;}
      .ezw-distance {font-weight: 800; color: #dce3ec; white-space: nowrap;}
      .ezw-muted {color: #8b94a0;}
      .ezw-trigger {max-width: 360px; color: #aeb7c3; line-height: 1.35;}
      .ezw-info {display: flex; justify-content: flex-start; margin-top: 10px; padding-top: 8px; border-top: 1px solid #252b35;}
      .ezw-infoicon {
        position: relative; display: inline-flex; align-items: center; justify-content: center;
        width: 16px; height: 16px; border: 1px solid #4c8dff; border-radius: 50%;
        color: #9fc0ff; font-size: 10px; font-weight: 800; cursor: help;
      }
      .ezw-eyebox {
        display: none; position: absolute; left: 0; bottom: 24px; z-index: 20; width: 360px;
        padding: 11px 12px; border: 1px solid rgba(76,141,255,.45); border-radius: 8px;
        background: #101722; color: #dce3ec; box-shadow: 0 14px 32px rgba(0,0,0,.35);
        font-size: .74rem; line-height: 1.45; font-weight: 400;
      }
      .ezw-infoicon:hover .ezw-eyebox, .ezw-infoicon:focus .ezw-eyebox {display: block;}
      .st-key-entry_zone_refresh div[data-testid="stButton"] {justify-content: flex-end; margin-top: 0;}
      .st-key-entry_zone_refresh button {
        border-radius: 9999px !important;
        border: 1px solid rgba(76,141,255,.75) !important;
        background: rgba(76,141,255,.12) !important;
        color: #e6e8eb !important;
        font-weight: 600 !important;
        min-height: 0 !important;
        padding: 0.25rem 0.9rem !important;
        width: auto !important;
        white-space: nowrap !important;
      }
      .st-key-entry_zone_refresh button:hover {
        border-color: #4c8dff !important;
        color: #4c8dff !important;
        background: transparent !important;
      }
      .rationale {margin-top: 1rem; border-left: 2px solid #2a2f37; padding-left: .8rem;}
      .rationale h4 {color: #e6e8eb; font-size: .95rem; font-weight: 700; margin: 0 0 .4rem 0; letter-spacing: .02em;}
      .rationale ol {margin: 0; padding-left: 1.1rem; color: #9aa3ad; font-size: .8rem; line-height: 1.5;}
      .rationale li {margin-bottom: .35rem;}
      .rationale b {color: #cbd2da;}
      /* tighten the divider that separates the shortlist from All Symbols */
      hr {margin-top: 0.4rem !important; margin-bottom: 0.4rem !important;}
      /* push the Scan-a-coin input + button row to the bottom of the left
         column so it lines up with the bottom of the shortlist table */
      [data-testid="stVerticalBlock"]:has(> [data-testid="stHorizontalBlock"]:has(.st-key-analyse_select)) {height: 100%;}
      [data-testid="stHorizontalBlock"]:has(.st-key-analyse_select) {margin-top: auto;}
      /* close-scan ✕ : sit in the left margin, right-aligned next to the
         result table and vertically centred against it */
      .st-key-close_scan {height: 102px; display: flex; align-items: center; justify-content: flex-end;}
      .st-key-close_scan div[data-testid="stButton"] {margin-top: 0 !important; width: auto;}
      /* muted grey favourite / search tags instead of bright blue */
      span[data-baseweb="tag"] {
        background-color: #2a2f37 !important;
        color: #c5ccd4 !important;
      }
      span[data-baseweb="tag"] svg {fill: #c5ccd4 !important;}
      /* gap above the Run Market Scan button + centre it under the rationale */
      div[data-testid="stElementContainer"]:has(> div[data-testid="stButton"]) {width: 100%;}
      div[data-testid="stButton"] {display: flex; justify-content: center; width: 100%; margin-top: 1.1rem;}
      /* make the Run Market Scan button match the pill / chip filters */
      div[data-testid="stButton"] > button {
        border-radius: 9999px;
        border: 1px solid rgba(230, 232, 235, 0.2);
        background-color: transparent;
        color: #e6e8eb;
        font-weight: 500;
        min-height: 0;
        padding: 0.25rem 0.85rem;
        width: auto;
        white-space: nowrap;
      }
      div[data-testid="stButton"] > button:hover {
        border-color: #4c8dff;
        color: #4c8dff;
        background-color: transparent;
      }
      div[data-testid="stButton"] > button:focus:not(:active) {
        border-color: #4c8dff;
        color: #e6e8eb;
      }
      /* tighten dataframe borders to feel like Orion's grid */
      [data-testid="stDataFrame"] {border: 1px solid #1f2329; border-radius: 6px;}
    </style>
    """,
    unsafe_allow_html=True,
)


if "favs" not in st.session_state:
    st.session_state.favs = set()


# No TTL: the scan is fetched once on load and then only re-fetched when the
# user clicks "Run Market Scan" (which clears these caches). This keeps the data
# stable across interactions and avoids any background polling / flicker.
@st.cache_data(show_spinner="Scanning Binance Futures…")
def load_data():
    return scanner.scan(), time.time()


@st.cache_data(ttl=3600, show_spinner=False)
def icon_map(symbols):
    return icons.icon_urls(list(symbols))


@st.cache_data(show_spinner=False)
def oi_map(symbols):
    return scanner.oi_change_pct(list(symbols))


@st.cache_data(show_spinner=False)
def funding_map(symbols):
    return scanner.funding_relative(list(symbols))


@st.cache_data(show_spinner=False)
def taker_map(symbols):
    return scanner.taker_ratio(list(symbols))


def _clean_symbol(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _h(value):
    return html.escape(str(value if value is not None else ""))


def _analysis_symbol(data, fallback):
    symbol = _clean_symbol(data.get("symbol") or fallback)
    if symbol and not symbol.endswith(("USDT", "PERP")):
        symbol += "USDT"
    return symbol


def _fmt_entry_price(value):
    if value is None:
        return "—"
    value = float(value)
    if value >= 1:
        return f"${value:,.2f}"
    if value >= 0.01:
        return f"${value:.4f}"
    return f"${value:.6f}"


def _position_label(current, low, high):
    if low <= current <= high:
        return "Price in zone"
    if current < low:
        return "Price below zone"
    return "Price above zone"


def _candidate_watch_row(symbol, data, candidate, tactical=False):
    grade = (candidate.get("grade") or "").strip().upper()[:1]
    allowed_grades = {"A", "B", "C"} if tactical else {"A", "B"}
    if grade not in allowed_grades:
        return None

    entry = candidate.get("entry") or {}
    direction = (entry.get("direction") or "").strip().lower()
    zone = entry.get("zone") or {}
    try:
        low = float(zone.get("low"))
        high = float(zone.get("high"))
    except (TypeError, ValueError):
        return None
    if low <= 0 or high <= 0:
        return None
    if low > high:
        low, high = high, low
    if direction not in {"long", "short"}:
        return None

    quote = scanner.live_bybit_ticker(symbol) or scanner.live_ticker(symbol)
    if not quote:
        return None
    current = float(quote["last"])

    position = _position_label(current, low, high)
    if low <= current <= high:
        if not tactical:
            return None
        distance = 0.0
        gap = 0.0
        status = "At Zone"
    elif current < low:
        gap = low - current
        distance = (low - current) / current * 100
        status = "Approaching" if distance <= 1.0 else "Waiting"
    else:
        gap = current - high
        distance = (current - high) / current * 100
        status = "Approaching" if distance <= 1.0 else "Waiting"

    if not tactical and status not in {"Approaching", "Waiting"}:
        return None

    subtitle = zone.get("subtitle") or ""
    trigger = subtitle if subtitle else candidate.get("qualifier") or candidate.get("summary") or "Entry condition pending."
    return {
        "symbol": symbol,
        "grade": grade,
        "direction": direction,
        "setup": candidate.get("name") or candidate.get("classification") or ("Tactical Setup" if tactical else "Setup"),
        "status": status,
        "position": position,
        "entry": zone.get("label") or f"{_fmt_entry_price(low)} – {_fmt_entry_price(high)}",
        "current": _fmt_entry_price(current),
        "distance": distance,
        "distance_label": "In zone" if distance == 0 else f"{distance:.2f}%",
        "distance_detail": "Active now" if gap == 0 else f"{_fmt_entry_price(gap)} from zone",
        "trigger": trigger,
    }


WATCHLIST_MODES = {
    "Top Volume": "top_volume",
    "Gainers": "gainers",
    "24h %": "change_24h",
    "New": "new",
    "TradFi: Stocks": "tradfi_stocks",
    "Low Cap Impulse": "low_cap_impulse",
}


WATCHLIST_SUBTITLES = {
    "Top Volume": "Saved A/B setups · most traded Bybit crypto perps · price still outside entry",
    "Gainers": "Saved A/B setups · positive movers with liquidity filter · price still outside entry",
    "24h %": "Saved A/B setups · raw Bybit 24h percentage movers · price still outside entry",
    "New": "Saved A/B setups · newest Bybit crypto perps · price still outside entry",
    "TradFi: Stocks": "Saved A/B setups · Bybit stock perps only · crypto excluded",
    "Low Cap Impulse": "Tactical participation points · lower-volume movers with unusual upside impulse",
}


WATCHLIST_REFRESH_LIMIT = 8


@st.cache_data(show_spinner="Loading watchlist universe…")
def watchlist_universe(mode):
    return tuple(scanner.bybit_watchlist_universe(mode, limit=30))


def refresh_watchlist_analyses(mode, api_key):
    """Cheaply triage the selected universe, then run full OpenAI analysis."""
    triage = scanner.bybit_watchlist_triage(mode, limit=WATCHLIST_REFRESH_LIMIT)
    symbols = triage.get("symbols") or []
    tactical_mode = mode == "low_cap_impulse"
    results = []
    errors = []
    for symbol in symbols:
        try:
            result = openai_analysis.generate_dashboard_analysis(
                symbol,
                api_key=api_key,
                tactical_mode=tactical_mode,
            )
            results.append(result["symbol"])
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
    return results, errors, triage


@st.cache_data(show_spinner="Refreshing Entry Zone Watchlist…")
def build_entry_zone_watchlist(source_symbols, tactical=False):
    top = set(source_symbols)
    rows = []
    analyses_dir = os.path.join(os.path.dirname(__file__), "analyses")
    for path in glob.glob(os.path.join(analyses_dir, "*.json")):
        fallback = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        symbol = _analysis_symbol(data, fallback)
        if symbol not in top:
            continue
        for candidate in data.get("pattern_candidates") or []:
            row = _candidate_watch_row(symbol, data, candidate, tactical=tactical)
            if row:
                rows.append(row)

    rows.sort(key=lambda row: ({"A": 0, "B": 1, "C": 2}.get(row["grade"], 3), row["distance"]))
    return rows[:12], time.time()


# S&P 500 futures sentiment — refreshes at most every 5 min, and on Run Market
# Scan. Only the % is fetched here; the live clocks tick client-side (see below).
@st.cache_data(ttl=300, show_spinner=False)
def build_full(d, icon_lookup):
    out = pd.DataFrame()
    out["fav"] = d["symbol"].isin(st.session_state.favs).values
    out["icon"] = d["symbol"].map(icon_lookup).values
    out["symbol"] = d["symbol"].values
    out["trd5m"] = d["trd5m"].values / 1000.0
    out["chg5m"] = d["chg5m"].values
    out["chg1d"] = d["chg1d"].values
    out["vol5m"] = d["vol5m"].values / 1_000_000.0
    out["cor5m"] = d["cor5m"].values
    return out.reset_index(drop=True)


# Vanilla ag-grid cell renderer (class with init/getGui) — bypasses React so it
# can return a real DOM node: gold/hollow star + coin icon + ticker, all inline.
SYMBOL_RENDERER = JsCode(
    """
    class {
      init(params) {
        const fav = !!params.data.fav;
        const div = document.createElement('div');
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.height = '100%';
        div.style.gap = '8px';

        const star = document.createElement('span');
        star.textContent = fav ? '★' : '☆';
        star.title = fav ? 'Favourited' : 'Not favourited';
        star.style.fontSize = '15px';
        star.style.color = fav ? '#f0b90b' : '#5b626c';

        const img = document.createElement('img');
        img.src = params.data.icon;
        img.width = 18;
        img.height = 18;
        img.style.borderRadius = '50%';
        img.onerror = function() { this.style.visibility = 'hidden'; };

        const sym = document.createElement('span');
        sym.textContent = params.value;

        div.appendChild(star);
        div.appendChild(img);
        div.appendChild(sym);
        this.eGui = div;
      }
      getGui() { return this.eGui; }
    }
    """
)

# Shortlist symbol cell: coin icon inline with the ticker, same look as the main
# table (no favourite star here — the shortlist is a curated result list).
SHORT_RENDERER = JsCode(
    """
    class {
      init(params) {
        const div = document.createElement('div');
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.height = '100%';
        div.style.gap = '8px';

        const img = document.createElement('img');
        img.src = params.data.icon;
        img.width = 18;
        img.height = 18;
        img.style.borderRadius = '50%';
        img.onerror = function() { this.style.visibility = 'hidden'; };

        const sym = document.createElement('span');
        sym.textContent = params.value;

        div.appendChild(img);
        div.appendChild(sym);
        this.eGui = div;
      }
      getGui() { return this.eGui; }
    }
    """
)

PCT_FORMATTER = JsCode(
    "function(p){ return p.value==null ? '' : (p.value>=0?'+':'') + p.value.toFixed(2) + '%'; }"
)
# value is already in thousands → append K to the data (header stays "TRD 5M")
TRD_FORMATTER = JsCode("function(p){ return p.value==null ? '' : p.value.toFixed(2) + 'K'; }")
# value is already in millions → $ prefix + M suffix
VOL_FORMATTER = JsCode("function(p){ return p.value==null ? '' : '$' + p.value.toFixed(2) + 'M'; }")
# open-interest 5m change: '—' when not computed (e.g. main table), signed % otherwise
OI_FORMATTER = JsCode(
    "function(p){ if(p.value==null||isNaN(p.value)) return '—'; return (p.value>=0?'+':'') + p.value.toFixed(2) + '%'; }"
)
# correlation coefficient, 2 decimals
COR_FORMATTER = JsCode(
    "function(p){ return (p.value==null||isNaN(p.value)) ? '' : p.value.toFixed(2); }"
)
# funding cell: raw % (neutral) · relative tag (muted; amber on the crowded
# extremes). Tag = how stretched funding is vs the coin's own recent normal.
FUNDING_RENDERER = JsCode(
    """
    class {
      init(params) {
        const rate = params.data.funding;
        const tag = params.data.funding_tag;
        const div = document.createElement('div');
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.height = '100%';
        div.style.gap = '6px';

        const num = document.createElement('span');
        num.textContent = (rate == null || isNaN(rate))
          ? '—' : (rate >= 0 ? '+' : '') + rate.toFixed(4) + '%';
        div.appendChild(num);

        const real = ['Crowded long','Long tilt','Normal','Short tilt','Crowded short'];
        if (tag && real.indexOf(tag) >= 0) {
          const sep = document.createElement('span');
          sep.textContent = '·';
          sep.style.color = '#5b626c';
          const t = document.createElement('span');
          t.textContent = tag;
          t.style.fontSize = '11px';
          t.style.color = (tag === 'Crowded long' || tag === 'Crowded short')
            ? '#e0a23c' : '#848e9c';
          div.appendChild(sep);
          div.appendChild(t);
        }
        this.eGui = div;
      }
      getGui() { return this.eGui; }
    }
    """
)
PCT_STYLE = JsCode(
    "function(p){ if(p.value>0) return {color:'#0ecb81'}; if(p.value<0) return {color:'#f6465d'}; return {color:'#848e9c'}; }"
)
# colour the 1H positioning verdict: genuine moves bold green/red, the
# self-limiting (covering / unwind) ones amber, neutral grey
LEAN_STYLE = JsCode(
    """
    function(p){
      var v = p.value;
      if(v==='Longs building')  return {color:'#0ecb81', fontWeight:'600'};
      if(v==='Shorts building') return {color:'#f6465d', fontWeight:'600'};
      if(v==='Short cover' || v==='Long unwind') return {color:'#e0a23c'};
      return {color:'#848e9c'};
    }
    """
)
# rich hover card shown on the LEAN (1H) header — the full rationale, formatted
LEAN_TOOLTIP = JsCode(
    """
    class {
      init(params) {
        const d = document.createElement('div');
        d.style.maxWidth = '320px';
        d.style.padding = '11px 13px';
        d.style.background = '#15181f';
        d.style.border = '1px solid #2a2f37';
        d.style.borderRadius = '6px';
        d.style.color = '#cbd2da';
        d.style.fontSize = '12px';
        d.style.lineHeight = '1.5';
        d.style.boxShadow = '0 6px 20px rgba(0,0,0,0.45)';
        d.innerHTML =
          '<div style="font-weight:700;color:#e6e8eb;margin-bottom:7px;">LEAN (1H) — Rationale</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">1. Price (1H):</b> whether price rose or fell over the past hour — the direction of the move.</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">2. Open Interest (1H):</b> whether the number of open positions rose (<i>new money entering</i>) or fell (<i>positions being closed out</i>) over the same hour.</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">3. Combined lean:</b> moves backed by new positions '
          + '(<span style="color:#0ecb81;">Longs building</span> / <span style="color:#f6465d;">Shorts building</span>) signal genuine conviction; '
          + 'moves driven by positions closing (<span style="color:#e0a23c;">Short cover</span> / <span style="color:#e0a23c;">Long unwind</span>) are weaker and tend to fade.</div>'
          + '<div><b style="color:#e6e8eb;">4. Neutral:</b> price barely moved over the hour — nothing meaningful to read.</div>';
        this.eGui = d;
      }
      getGui() { return this.eGui; }
    }
    """
)
# rich hover card shown on the FUNDING (8H) header — the full rationale, formatted
FUND_TOOLTIP = JsCode(
    """
    class {
      init(params) {
        const d = document.createElement('div');
        d.style.maxWidth = '330px';
        d.style.padding = '11px 13px';
        d.style.background = '#15181f';
        d.style.border = '1px solid #2a2f37';
        d.style.borderRadius = '6px';
        d.style.color = '#cbd2da';
        d.style.fontSize = '12px';
        d.style.lineHeight = '1.5';
        d.style.boxShadow = '0 6px 20px rgba(0,0,0,0.45)';
        d.innerHTML =
          '<div style="font-weight:700;color:#e6e8eb;margin-bottom:7px;">FUNDING (8H) — Rationale</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">1. Funding rate (8H):</b> Capture the coin\\'s current funding rate — the fee exchanged between longs and shorts every 8 hours. A positive rate means longs are the crowded side paying to hold their position; a negative rate means shorts are the crowded, paying side.</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">2. The coin\\'s baseline:</b> Pull the last 7 days of that coin\\'s funding history and work out its typical level and how much it usually varies. <i>Note: the same funding figure means very different things for a calm major versus a wild small-cap.</i></div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">3. How stretched (relative):</b> Measure how far the current funding sits from that coin\\'s baseline rather than against a fixed market-wide number. "Crowded" will then reflect what is unusual for that specific coin.</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">4. The tag:</b> Long tilt / <span style="color:#e0a23c;">Crowded long</span> when funding is positive, Short tilt / <span style="color:#e0a23c;">Crowded short</span> when negative — escalating from tilt (a little beyond the coin\\'s normal range) to Crowded (well beyond it). When funding is within the coin\\'s usual range, it reads Normal.</div>'
          + '<div><b style="color:#e6e8eb;">5. Not enough history:</b> Where a coin is too newly listed to have a reliable normal, show only the raw rate with no tag, to avoid a misleading judgement.</div>';
        this.eGui = d;
      }
      getGui() { return this.eGui; }
    }
    """
)

# B/S cell: buy% + flow arrow · the Read (confirm grey / absorbed-reversal amber)
BS_RENDERER = JsCode(
    """
    class {
      init(params) {
        const pct = params.data.bs_pct;
        const flow = params.data.bs_flow;
        const cat = params.data.bs_read;
        const GREY = '#848e9c', GREEN = '#0ecb81', RED = '#f6465d';
        const div = document.createElement('div');
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.height = '100%';
        div.style.gap = '6px';

        const num = document.createElement('span');
        if (pct == null || isNaN(pct)) {
          num.textContent = '—';
          div.appendChild(num);
          this.eGui = div;
          return;
        }
        const arrow = flow === 'buy' ? ' ▲' : (flow === 'sell' ? ' ▼' : '');
        num.textContent = Math.round(pct) + '%' + arrow;
        div.appendChild(num);

        function part(txt, color) {
          const s = document.createElement('span');
          s.textContent = txt;
          s.style.color = color;
          s.style.fontSize = '11px';
          return s;
        }
        function sep() {
          const s = document.createElement('span');
          s.textContent = '·';
          s.style.color = '#5b626c';
          return s;
        }

        if (cat === 'confirm_up') {
          div.appendChild(sep()); div.appendChild(part('Confirms ↑', GREY));
        } else if (cat === 'confirm_down') {
          div.appendChild(sep()); div.appendChild(part('Confirms ↓', GREY));
        } else if (cat === 'sells_absorbed') {
          div.appendChild(sep()); div.appendChild(part('Sells absorbed', GREY));
          div.appendChild(sep()); div.appendChild(part('⤴ bullish reversal', GREEN));
        } else if (cat === 'buys_absorbed') {
          div.appendChild(sep()); div.appendChild(part('Buys absorbed', GREY));
          div.appendChild(sep()); div.appendChild(part('⤵ bearish reversal', RED));
        } else if (cat === 'balanced') {
          div.appendChild(sep()); div.appendChild(part('Balanced', GREY));
        }
        this.eGui = div;
      }
      getGui() { return this.eGui; }
    }
    """
)
# rich hover card / key for the B/S (1H) header
BS_TOOLTIP = JsCode(
    """
    class {
      init(params) {
        const d = document.createElement('div');
        d.style.maxWidth = '340px';
        d.style.padding = '11px 13px';
        d.style.background = '#15181f';
        d.style.border = '1px solid #2a2f37';
        d.style.borderRadius = '6px';
        d.style.color = '#cbd2da';
        d.style.fontSize = '12px';
        d.style.lineHeight = '1.5';
        d.style.boxShadow = '0 6px 20px rgba(0,0,0,0.45)';
        d.innerHTML =
          '<div style="font-weight:700;color:#e6e8eb;margin-bottom:7px;">B/S (5M) — Rationale</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">Buy %:</b> share of aggressive (taker) volume that was buying over the last 5 minutes. Above 50% = buyers pressing, below = sellers pressing.</div>'
          + '<div style="margin-bottom:6px;"><b style="color:#e6e8eb;">Read:</b> compares that flow to the 5m price move —</div>'
          + '<div style="margin-bottom:3px;">• <b style="color:#e6e8eb;">Confirms ↑ / ↓</b> — flow agrees with the move (real demand / selling).</div>'
          + '<div style="margin-bottom:3px;">• Sells absorbed · <span style="color:#0ecb81;">⤴ bullish reversal</span> — selling, but price held up → hidden buyer.</div>'
          + '<div style="margin-bottom:3px;">• Buys absorbed · <span style="color:#f6465d;">⤵ bearish reversal</span> — buying, but price held down → hidden seller.</div>'
          + '<div>• <b style="color:#e6e8eb;">Balanced</b> — no decisive flow.</div>';
        this.eGui = d;
      }
      getGui() { return this.eGui; }
    }
    """
)

AGGRID_CSS = {
    ".ag-root-wrapper": {"border": "1px solid #1f2329", "border-radius": "6px"},
    ".ag-header-cell-text": {"letter-spacing": "0.04em", "font-size": "12px"},
    ".ag-cell": {"font-size": "13px"},
}


def full_grid_options():
    return {
        "columnDefs": [
            {"field": "fav", "hide": True},
            {"field": "icon", "hide": True},
            {
                "field": "symbol",
                "headerName": "SYMBOL",
                "cellRenderer": SYMBOL_RENDERER,
                "pinned": "left",
                "width": 200,
                "minWidth": 180,
            },
            {
                "field": "trd5m",
                "headerName": "TRD (5M)",
                "valueFormatter": TRD_FORMATTER,
                "flex": 1,
                "minWidth": 120,
            },
            {
                "field": "chg5m",
                "headerName": "CHG % (5M)",
                "valueFormatter": PCT_FORMATTER,
                "cellStyle": PCT_STYLE,
                "flex": 1,
                "minWidth": 120,
            },
            {
                "field": "chg1d",
                "headerName": "CHG % (1D)",
                "valueFormatter": PCT_FORMATTER,
                "cellStyle": PCT_STYLE,
                "flex": 1,
                "minWidth": 120,
            },
            {
                "field": "vol5m",
                "headerName": "VOL (5M)",
                "valueFormatter": VOL_FORMATTER,
                "flex": 1,
                "minWidth": 120,
            },
            {
                "field": "cor5m",
                "headerName": "COR (5M)",
                "valueFormatter": COR_FORMATTER,
                "flex": 1,
                "minWidth": 100,
            },
        ],
        "defaultColDef": {
            "sortable": True,
            "resizable": True,
            "suppressMovable": True,
            "wrapHeaderText": True,
        },
        "rowHeight": 36,
        "headerHeight": 46,
        "suppressCellFocus": True,
        "suppressRowClickSelection": True,
    }


def _bs(buy_pct, chg):
    """B/S read: compare 5m taker flow to the 5m price move (same window).

    Returns (flow, read) where flow is 'buy'/'sell'/'flat'. Decisive flow is
    >55% / <45% taker-buy; price dead-zone is ±0.1%. Flow agreeing with price =
    Confirms; flow against price (or price flat) = absorption / reversal risk.
    """
    if buy_pct is None or buy_pct != buy_pct:
        return "flat", ""
    if buy_pct > 55:
        flow = "buy"
    elif buy_pct < 45:
        flow = "sell"
    else:
        return "flat", "balanced"
    if chg is None or chg != chg or abs(chg) < 0.1:
        price_up = None  # flat
    else:
        price_up = chg > 0
    if flow == "buy":
        if price_up is True:
            return "buy", "confirm_up"
        return "buy", "buys_absorbed"
    if price_up is False:
        return "sell", "confirm_down"
    return "sell", "sells_absorbed"


def _quadrant(chg1h, oi1h):
    """Price + OI (both over ~1h) → positioning lean. Same-window pairing."""
    if chg1h is None or oi1h is None or chg1h != chg1h or oi1h != oi1h:
        return ""
    if abs(chg1h) < 0.1:  # no meaningful price move → direction unclear
        return "Neutral"
    up, oi_up = chg1h > 0, oi1h > 0
    if up and oi_up:
        return "Longs building"      # price up + OI up  → fresh longs (genuine bull)
    if up and not oi_up:
        return "Short cover"         # price up + OI down → shorts exiting (weak bull)
    if (not up) and oi_up:
        return "Shorts building"     # price down + OI up → fresh shorts (genuine bear)
    return "Long unwind"             # price down + OI down → longs exiting (weak bear)


def build_short(d, icon_lookup, oi_lookup, fund_lookup, taker_lookup):
    out = pd.DataFrame()
    out["icon"] = d["symbol"].map(icon_lookup).values
    out["symbol"] = d["symbol"].values
    out["chg5m"] = d["chg5m"].values
    out["chg1h"] = d["chg1h"].values
    out["chg1d"] = d["chg1d"].values
    out["vol5m"] = d["vol5m"].values / 1_000_000.0
    oi5m = [(oi_lookup.get(s) or {}).get("oi5m", float("nan")) for s in d["symbol"]]
    oi1h = [(oi_lookup.get(s) or {}).get("oi1h", float("nan")) for s in d["symbol"]]
    out["oi5m"] = oi5m
    out["oi1h"] = oi1h
    out["cor5m"] = d["cor5m"].values
    fund = [fund_lookup.get(s) or {} for s in d["symbol"]]
    out["funding"] = [f.get("rate", float("nan")) for f in fund]
    out["funding_tag"] = [f.get("tag", "—") for f in fund]
    taker = [taker_lookup.get(s, float("nan")) for s in d["symbol"]]
    bs = [_bs(p, c) for p, c in zip(taker, d["chg5m"].values)]
    out["bs_pct"] = taker
    out["bs_flow"] = [b[0] for b in bs]
    out["bs_read"] = [b[1] for b in bs]
    out["lean"] = [_quadrant(c, o) for c, o in zip(out["chg1h"], oi1h)]
    return out.reset_index(drop=True)


def short_grid_options(with_tooltips=True):
    return {
        "columnDefs": [
            {"field": "icon", "hide": True},
            {
                "field": "symbol",
                "headerName": "SYMBOL",
                "cellRenderer": SHORT_RENDERER,
                "flex": 1.3,
                "minWidth": 104,
            },
            {
                "field": "chg5m",
                "headerName": "CHG % (5M)",
                "valueFormatter": PCT_FORMATTER,
                "cellStyle": PCT_STYLE,
                "flex": 1,
                "minWidth": 66,
            },
            {
                "field": "chg1h",
                "headerName": "CHG % (1H)",
                "valueFormatter": PCT_FORMATTER,
                "cellStyle": PCT_STYLE,
                "flex": 1,
                "minWidth": 66,
            },
            {
                "field": "chg1d",
                "headerName": "CHG % (1D)",
                "valueFormatter": PCT_FORMATTER,
                "cellStyle": PCT_STYLE,
                "flex": 1,
                "minWidth": 66,
            },
            {
                "field": "vol5m",
                "headerName": "VOL (5M)",
                "valueFormatter": VOL_FORMATTER,
                "flex": 1,
                "minWidth": 64,
            },
            {
                "field": "oi5m",
                "headerName": "OI CHG % (5M)",
                "valueFormatter": OI_FORMATTER,
                "cellStyle": PCT_STYLE,
                "flex": 1,
                "minWidth": 70,
            },
            {
                "field": "oi1h",
                "headerName": "OI CHG % (1H)",
                "valueFormatter": OI_FORMATTER,
                "cellStyle": PCT_STYLE,
                "flex": 1,
                "minWidth": 70,
            },
            {
                "field": "cor5m",
                "headerName": "COR (5M)",
                "valueFormatter": COR_FORMATTER,
                "flex": 0.8,
                "minWidth": 52,
            },
            {"field": "funding_tag", "hide": True},
            {
                "field": "funding",
                "headerName": "FUNDING (8H)" + (" ⓘ" if with_tooltips else ""),
                "cellRenderer": FUNDING_RENDERER,
                **({"headerTooltip": "funding", "tooltipComponent": FUND_TOOLTIP} if with_tooltips else {}),
                "flex": 1.8,
                "minWidth": 164,
            },
            {"field": "bs_flow", "hide": True},
            {"field": "bs_read", "hide": True},
            {
                "field": "bs_pct",
                "headerName": "B/S (5M)" + (" ⓘ" if with_tooltips else ""),
                "cellRenderer": BS_RENDERER,
                **({"headerTooltip": "bs", "tooltipComponent": BS_TOOLTIP} if with_tooltips else {}),
                "flex": 3,
                "minWidth": 258,
            },
            {
                "field": "lean",
                "headerName": "LEAN (1H)" + (" ⓘ" if with_tooltips else ""),
                "cellStyle": LEAN_STYLE,
                **({"headerTooltip": "lean", "tooltipComponent": LEAN_TOOLTIP} if with_tooltips else {}),
                "flex": 1.4,
                "minWidth": 124,
            },
        ],
        "defaultColDef": {
            "sortable": True,
            "resizable": True,
            "suppressMovable": True,
            "wrapHeaderText": True,
        },
        "rowHeight": 36,
        "headerHeight": 46,
        "suppressCellFocus": True,
        "suppressRowClickSelection": True,
        "tooltipShowDelay": 300,
    }


# ---------------- sidebar ----------------
st.sidebar.title("Settings")
shortlist_floor = st.sidebar.number_input(
    "Shortlist volume floor ($)", value=500_000, step=100_000, min_value=0,
    help="Minimum 5M volume for a coin to qualify for the shortlist.",
)

# ---------------- data ----------------
try:
    df, ts = load_data()
except Exception as exc:
    st.error(f"Scan failed: {exc}")
    st.stop()

ICONS = icon_map(tuple(df["symbol"]))

# ---------------- top bar: page nav (left) + live clocks (right) ----------------
navc, clockc = st.columns([1.5, 2.1])
with navc:
    chrome.render_nav(st.container(key="topnav"))
with clockc:
    chrome.render_clocks()


# ---------------- entry zone watchlist ----------------
if "entry_zone_mode_label" not in st.session_state:
    st.session_state.entry_zone_mode_label = "Top Volume"
if "entry_zone_scan_note" not in st.session_state:
    st.session_state.entry_zone_scan_note = ""

selected_watchlist_label = st.session_state.entry_zone_mode_label
watchlist_symbols = watchlist_universe(WATCHLIST_MODES[selected_watchlist_label])
watchlist_icons = icon_map(watchlist_symbols)
low_cap_tactical = WATCHLIST_MODES[selected_watchlist_label] == "low_cap_impulse"
watch_rows, watch_ts = build_entry_zone_watchlist(watchlist_symbols, tactical=low_cap_tactical)
last_scanned = time.strftime("%H:%M:%S", time.localtime(watch_ts))

if watch_rows:
    body = ""
    for row in watch_rows:
        dir_cls = "ezw-dir-long" if row["direction"] == "long" else "ezw-dir-short"
        grade_cls = f"ezw-grade-{row['grade'].lower()}"
        status_cls = row["status"].lower().replace(" ", "-")
        icon_url = watchlist_icons.get(row["symbol"], "")
        icon_html = f"<img src='{_h(icon_url)}' alt=''>" if icon_url else ""
        body += (
            "<tr>"
            f"<td><div class='ezw-symbol'>{icon_html}<b>{_h(row['symbol'])}</b></div></td>"
            f"<td><span class='ezw-grade {grade_cls}'>{_h(row['grade'])}</span></td>"
            f"<td><span class='{dir_cls}'>{_h(row['direction'].upper())}</span></td>"
            f"<td>{_h(row['setup'])}</td>"
            f"<td><span class='ezw-status {status_cls}'>{_h(row['status'])}</span>"
            f"<div class='ezw-subline'>{_h(row['position'])}</div></td>"
            f"<td>{_h(row['entry'])}</td>"
            f"<td>{_h(row['current'])}</td>"
            f"<td><span class='ezw-distance'>{_h(row['distance_label'])}</span>"
            f"<div class='ezw-subline'>{_h(row['distance_detail'])}</div></td>"
            f"<td class='ezw-trigger'>{_h(row['trigger'])}</td>"
            "</tr>"
        )
    table = (
        "<table class='ezw-table'><thead><tr>"
        "<th>Symbol</th><th>Grade</th><th>Dir</th><th>Setup</th><th>Status</th>"
        "<th>Entry Zone</th><th>Current</th><th>Distance</th><th>Trigger / Condition</th>"
        "</tr></thead><tbody>"
        f"{body}"
        "</tbody></table>"
    )
else:
    if low_cap_tactical:
        table = (
            "<div class='ezw-empty'>No tactical participation points are available from the current Low Cap Impulse scan yet. "
            "Refresh to analyse the current impulse candidates.</div>"
        )
    else:
        table = (
            "<div class='ezw-empty'>No A/B saved setups from this universe are waiting outside their entry zone. "
            "Run Analyse on symbols you want tracked, then Refresh.</div>"
        )

watchlist_help = (
    "<div class='ezw-info'>"
    "<span class='ezw-infoicon' tabindex='0' aria-label='Entry Zone Watchlist status definitions'>i"
    "<span class='ezw-eyebox'>"
    "<b>Status key</b><br>"
    "<b>Approaching</b>: price is close to the entry zone but has not reached it yet.<br>"
    "<b>Waiting</b>: setup remains valid, but price is still some distance from entry.<br>"
    "<b>At Zone</b>: price is testing the entry zone now; this should move to the Trade Dashboard for confirmation.<br>"
    "<b>Below/Above Zone</b>: price is outside the proposed participation area; the trigger is still ahead.<br>"
    "<b>Low Cap Impulse</b>: may include C-grade tactical participation points, not only clean A/B setups.<br>"
    "<b>Missed</b>: price has already passed through the entry zone and run; avoid chasing.<br>"
    "<b>Invalidated</b>: the setup condition has broken before entry."
    "</span></span></div>"
)

_ezw_logo = chrome.logo_data_uri()
_ezw_logo_img = f'<img src="{_ezw_logo}" alt="logo">' if _ezw_logo else ""
with st.container(key="entry_zone_heading"):
    wz_l, wz_r = st.columns([3, 1], vertical_alignment="top")
    with wz_l:
        st.markdown(
            '<div class="orion-brand">'
            f"{_ezw_logo_img}"
            '<div class="orion-logo">ENTRY ZONE <span class="accent">WATCHLIST</span>'
            f'<span class="sub">{_h(WATCHLIST_SUBTITLES[selected_watchlist_label])}</span></div>'
            "</div>",
            unsafe_allow_html=True,
        )
    with wz_r:
        if st.button("Refresh", key="entry_zone_refresh"):
            try:
                api_key = (st.secrets.get("openai_api_key") or "").strip()
                if not api_key or api_key == "PASTE_OPENAI_API_KEY_HERE":
                    raise RuntimeError("OpenAI API key is not configured in .streamlit/secrets.toml.")
                with st.spinner(f"Scanning {selected_watchlist_label}: triage first, then OpenAI..."):
                    refreshed, scan_errors, triage = refresh_watchlist_analyses(
                        WATCHLIST_MODES[selected_watchlist_label],
                        api_key,
                    )
                st.session_state.entry_zone_scan_note = (
                    f"Fresh scan: triaged {triage.get('universe_count', 0)} symbols, "
                    f"sent {triage.get('qualified_count', 0)} candidates through the cheap filter, "
                    f"analysed {len(refreshed)} with OpenAI. "
                    f"{len(scan_errors)} failed." if scan_errors else
                    f"Fresh scan: triaged {triage.get('universe_count', 0)} symbols, "
                    f"sent {triage.get('qualified_count', 0)} candidates through the cheap filter, "
                    f"analysed {len(refreshed)} with OpenAI."
                )
                if scan_errors:
                    st.session_state.entry_zone_scan_errors = scan_errors[:3]
                else:
                    st.session_state.entry_zone_scan_errors = []
            except Exception as exc:
                st.session_state.entry_zone_scan_note = f"Fresh scan failed: {exc}"
            finally:
                watchlist_universe.clear()
                build_entry_zone_watchlist.clear()
                st.rerun()
        st.markdown(f"<div class='ezw-time'>Last scanned: {last_scanned}</div>", unsafe_allow_html=True)

with st.container(key="entry_zone_filters"):
    st.radio(
        "",
        list(WATCHLIST_MODES.keys()),
        key="entry_zone_mode_label",
        horizontal=True,
        label_visibility="collapsed",
    )
    if st.session_state.get("entry_zone_scan_note"):
        st.markdown(f"<div class='ezw-scan-note'>{_h(st.session_state.entry_zone_scan_note)}</div>", unsafe_allow_html=True)
    if st.session_state.get("entry_zone_scan_errors"):
        with st.expander("Recent scan warnings"):
            for err in st.session_state.entry_zone_scan_errors:
                st.write(err)

with st.container(key="entry_zone_watchlist"):
    st.markdown(
        f"{table}{watchlist_help}",
        unsafe_allow_html=True,
    )


# ---------------- header: logo + refresh (left) + shortlist (right) ----------------
left, right = st.columns([1, 3])

with left:
    _logo = chrome.logo_data_uri()
    _logo_img = f'<img src="{_logo}" alt="logo">' if _logo else ""
    st.markdown(
        '<div class="orion-brand">'
        f"{_logo_img}"
        '<div class="orion-logo">MARKET <span class="accent">SCANNER</span>'
        '<span class="sub">Binance Futures</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="orion-meta">{len(df)} symbols · updated '
        f'{time.strftime("%H:%M:%S", time.localtime(ts))} · 5M = last closed candle</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="rationale">
          <h4>Shortlist Rationale</h4>
          <ol>
            <li><b>TRD (5M):</b> Rank coins by the number of executed trades in the
                previous 5 minutes to identify assets attracting the highest trader
                participation.</li>
            <li><b>Vol (5M):</b> Exclude coins with less than $500K volume in the
                previous 5 minutes to ensure sufficient liquidity and minimise
                slippage.</li>
            <li><b>Change % (5M) &amp; (1D):</b> Prioritise coins showing the strongest
                positive or negative price movement across both timeframes, regardless
                of direction, to identify assets attracting momentum and attention.</li>
          </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Run Market Scan"):
        load_data.clear()
        oi_map.clear()
        funding_map.clear()
        taker_map.clear()
        chrome.sp_futures.clear()
        st.rerun()

    # Scan a coin — input + Scan button side by side, tucked under Run Market
    # Scan. The result appears at the bottom of the shortlist table on the right.
    csel, cbtn = st.columns([3, 1], vertical_alignment="bottom")
    an_sym = csel.selectbox(
        "Scan a coin",
        options=sorted(df["symbol"]),
        index=None,
        placeholder="Ticker…",
        label_visibility="collapsed",
        key="analyse_select",
    )
    if cbtn.button("Scan", use_container_width=True) and an_sym:
        st.session_state["analysed_coin"] = an_sym
        st.rerun()

with right:
    st.markdown("#### Shortlist Result: What to Trade")
    st.caption(f"Top movers by activity · vol ≥ ${shortlist_floor:,.0f}")
    st.caption(f"Market scan run at {time.strftime('%H:%M:%S', time.localtime(ts))}")
    short = rules.build_shortlist(df, min_vol=shortlist_floor, top_n=20, pick=10)
    if short.empty:
        st.info("No coins pass the shortlist filter right now.")
    else:
        SHORT_OI = oi_map(tuple(short["symbol"]))
        SHORT_FUND = funding_map(tuple(short["symbol"]))
        SHORT_TAKER = taker_map(tuple(short["symbol"]))
        AgGrid(
            build_short(short, ICONS, SHORT_OI, SHORT_FUND, SHORT_TAKER),
            gridOptions=short_grid_options(),
            update_on=[],
            allow_unsafe_jscode=True,
            enable_enterprise_modules=False,
            fit_columns_on_grid_load=False,
            theme="streamlit",
            height=len(short) * 36 + 42,
            custom_css=AGGRID_CSS,
            key="short_grid",
        )

# Row 2: analysed result under the table (right). It's in its own row so Row 1's
# height is just the table — letting the left input bottom-align to the table.
xc, r2 = st.columns([1, 3])
asym = st.session_state.get("analysed_coin")
show_scan = bool(asym and (df["symbol"] == asym).any())
with xc:
    if show_scan and st.button("✕", help="Close scan", key="close_scan"):
        st.session_state["analysed_coin"] = None
        st.rerun()
with r2:
    abox = st.container(height=102, border=False)
    if show_scan:
        with abox:
            a_src = df[df["symbol"] == asym]
            A_OI = oi_map((asym,))
            A_FUND = funding_map((asym,))
            A_TAKER = taker_map((asym,))
            AgGrid(
                build_short(a_src, ICONS, A_OI, A_FUND, A_TAKER),
                gridOptions=short_grid_options(with_tooltips=False),
                update_on=[],
                allow_unsafe_jscode=True,
                enable_enterprise_modules=False,
                fit_columns_on_grid_load=False,
                theme="streamlit",
                height=100,
                custom_css=AGGRID_CSS,
                key="analysed_grid",
            )

st.divider()

# ---------------- full symbol list with filters ----------------
st.subheader("All Symbols")

fc1, fc2, fc3 = st.columns([2, 1, 1])
search_syms = fc1.multiselect(
    "Search",
    options=sorted(df["symbol"]),
    placeholder="Type to search, e.g. SOL, PEPE",
)
min_vol = fc2.number_input("Min Volume 5M ($)", value=0, step=100_000, min_value=0)
min_trd = fc3.number_input("Min TRD 5M", value=0, step=500, min_value=0)
qf_col, fav_col = st.columns([2, 2])
with qf_col:
    chips = st.pills(
        "Quick filters",
        ["★ Favourites", "High Volume", "Big Movers", "Gainers", "Losers"],
        selection_mode="multi",
        default=[],
    )
with fav_col:
    fav_pick = st.multiselect(
        "★ Favourites",
        options=sorted(df["symbol"]),
        default=sorted(st.session_state.favs & set(df["symbol"])),
        placeholder="Type to add, e.g. BTCUSDT",
    )
if set(fav_pick) != st.session_state.favs:
    st.session_state.favs = set(fav_pick)
    st.rerun()

view = df.copy()
if search_syms:
    view = view[view["symbol"].isin(search_syms)]
view = view[(view["vol5m"] >= min_vol) & (view["trd5m"] >= min_trd)]
if "★ Favourites" in chips:
    view = view[view["symbol"].isin(st.session_state.favs)]
if "High Volume" in chips:
    view = view[view["vol5m"] >= 5_000_000]
if "Big Movers" in chips:
    view = view[view["chg1d"].abs() >= 10]
gainers, losers = "Gainers" in chips, "Losers" in chips
if gainers and not losers:
    view = view[view["chg1d"] > 0]
elif losers and not gainers:
    view = view[view["chg1d"] < 0]
view = view.sort_values("trd5m", ascending=False)

st.caption(
    f"Showing {len(view)} of {len(df)} symbols · ★ = favourite (manage above) · click a column header to sort"
)
AgGrid(
    build_full(view, ICONS),
    gridOptions=full_grid_options(),
    update_on=[],
    allow_unsafe_jscode=True,
    enable_enterprise_modules=False,
    fit_columns_on_grid_load=False,
    theme="streamlit",
    height=720,
    custom_css=AGGRID_CSS,
    key="full_grid",
)
