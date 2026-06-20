"""Analyst Dashboard — single-coin read rendered from a structured analysis
file (analyses/<SYMBOL>.json) produced by the Trade Setup Framework
(framework/trade_setup_framework.md) via /trade + /push-dashboard.

The Market Scanner in app.py is untouched; this page is fully isolated.
"""
from __future__ import annotations

import streamlit as st

import chrome
import dashboard

st.set_page_config(page_title="Trade Dashboard", page_icon="📊", layout="wide")

# Shared chrome: nav + live clocks row (brand rendered below alongside the Run
# button so they share one horizontal row).
chrome.render_header("TRADE", "DASHBOARD", brand=False)

# Brand + "Run" pill on one row (Run to the right of the brand). The Run pill
# matches the Push To Calculator button; clicking it re-scans analyses/ for the
# newest analysis Claude generated and re-renders.
st.markdown(
    "<style>"
    # Ambient purple gradient behind the cards — shared with the Market Scanner and
    # Position Calculator. Folded into this one <style> (rather than a separate
    # inject_background() markdown) so the element count before the brand row is
    # unchanged and the heading stays vertically aligned with the other pages.
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + "[data-testid='stMain'],[data-testid='stMainBlockContainer']{background:transparent!important;}"
    # This page puts nothing in the sidebar (page-nav is hidden, no Settings), so the
    # empty panel is just confusing dead space — and chrome.py hides stHeader, which
    # removes the only control to reopen it once collapsed. Hide it outright here.
    + "[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none!important;}"
    ".st-key-brandrow{flex-direction:row!important;align-items:center!important;gap:1.3rem;}"
    ".st-key-brandrow [data-testid='stElementContainer']{width:auto!important;align-self:center!important;}"
    ".st-key-runbtn button{border-radius:9999px;border:1px solid rgba(230,232,235,.2)!important;"
    "background:transparent!important;color:#e6e8eb!important;font-weight:500;min-height:0;"
    "padding:0.25rem 0.85rem;width:auto;white-space:nowrap;transform:translateY(8px);}"
    ".st-key-runbtn button:hover{border-color:#4c8dff!important;color:#4c8dff!important;"
    "background:transparent!important;}"
    "</style>",
    unsafe_allow_html=True,
)
_brow = st.container(key="brandrow")
_brow.markdown(chrome.brand_html("TRADE", "DASHBOARD"), unsafe_allow_html=True)
_brow.button("Run", key="runbtn")

# Always show the most recently generated analysis (newest analyses/<SYMBOL>.json).
symbol = dashboard.latest_symbol()
data = dashboard.load_analysis(symbol)

# Caption hugging the divider line, directly under the heading (no wasted space).
if data:
    _m = data.get("meta", {})
    _cap = (
        f"Showing <b>{data.get('symbol', symbol)}</b> · analysis time "
        f"{_m.get('analysis_time', '—')} · analysis performed on "
        f"{_m.get('timeframe_analyzed', '—')} · framework "
        f"{data.get('framework_version', 'Trade Setup Framework')}"
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
        f"No analysis on file for **{symbol}**. Ask Claude in chat to run the "
        f"framework on {symbol}.",
        icon="📭",
    )
