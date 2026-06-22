"""Analyst Dashboard — v3 DEMO (sandbox).

A SAFE, ISOLATED copy of pages/1_Trade_Setup.py used to rework the layout
toward framework v3. It imports `dashboard_v3_demo` (a copy of dashboard.py) which
reads from `analyses_demo/` — so nothing here touches the live page 1, the live
`dashboard.py`, or the live `analyses/` data.

Iterate freely on `dashboard_v3_demo.py` + `analyses_demo/*.json`.
"""
from __future__ import annotations

import streamlit as st

import chrome
import dashboard_v3_demo as dashboard  # isolated copy → reads analyses_demo/

st.set_page_config(page_title="Trade Setup v3 (DEMO)", page_icon="🧪", layout="wide")

chrome.render_header("TRADE", "SETUP", brand=False)

st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + "[data-testid='stMain'],[data-testid='stMainBlockContainer']{background:transparent!important;}"
    # This page puts nothing in the sidebar (page-nav is hidden, no Settings), so the
    # empty panel is just confusing dead space — and chrome.py hides stHeader, which
    # removes the only control to reopen it once collapsed. Hide it outright here.
    + "[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none!important;}"
    ".st-key-runbtn button{border-radius:9999px;border:1px solid rgba(230,232,235,.2)!important;"
    "background:transparent!important;color:#e6e8eb!important;font-weight:500;min-height:0;"
    "padding:0.25rem 0.85rem;width:auto;white-space:nowrap;transform:translateY(8px);}"
    ".st-key-runbtn button:hover{border-color:#4c8dff!important;color:#4c8dff!important;"
    "background:transparent!important;}"
    "</style>",
    unsafe_allow_html=True,
)
_brow = st.container(key="brandrow")
_brow.markdown(chrome.brand_html("TRADE", "SETUP"), unsafe_allow_html=True)
_brow.button("Run", key="runbtn")

# DEMO banner so it's unmistakable which dashboard you're on.
st.markdown(
    "<div style='margin:.4rem 0 -.2rem 0;display:inline-block;padding:3px 10px;"
    "border-radius:6px;background:rgba(227,160,8,.15);border:1px solid rgba(227,160,8,.45);"
    "color:#e3a008;font-size:11px;font-weight:700;letter-spacing:.06em;'>"
    "🧪 v3 DEMO — sandbox copy · reads analyses_demo/ · live dashboard untouched</div>",
    unsafe_allow_html=True,
)

# Always show the most recently generated demo analysis (newest analyses_demo/<SYMBOL>.json).
symbol = dashboard.latest_symbol()
data = dashboard.load_analysis(symbol)

# Caption hugging the divider line, directly under the heading (no wasted space).
if data:
    _m = data.get("meta", {})
    _cap = (
        f"Showing <b>{data.get('symbol', symbol)}</b> · analysis time "
        f"{_m.get('analysis_time', '—')} · analysis performed on "
        f"{_m.get('timeframe_analyzed', '—')} · framework "
        f"{data.get('framework_version', 'v3')}"
    )
    st.markdown(
        "<style>.v3capline{color:#8b94a0;font-size:.8rem;line-height:1.3;margin:0 0 14px 0;"
        "padding-bottom:6px;border-bottom:1px solid #2a2f3a;}</style>"
        f"<div class='v3capline'>{_cap}</div>",
        unsafe_allow_html=True,
    )
    dashboard.render(data, symbol=symbol)
else:
    st.divider()
    st.warning(
        f"No demo analysis on file for **{symbol}**. Drop a JSON into analyses_demo/.",
        icon="📭",
    )
