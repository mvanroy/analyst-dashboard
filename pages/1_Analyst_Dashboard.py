"""Analyst Dashboard — single-coin read rendered from a structured analysis
file (analyses/<SYMBOL>.json) produced by the Trade Setup Framework
(framework/trade_setup_framework.md) via /trade + /push-dashboard.

The Market Scanner in app.py is untouched; this page is fully isolated.
"""
from __future__ import annotations

import re

import streamlit as st

import chrome
import dashboard
import openai_analysis

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
    ".st-key-brandrow .stTextInput{width:150px!important;transform:translateY(8px);}"
    ".st-key-brandrow .stTextInput input{height:30px;border-radius:9999px!important;"
    "border:1px solid rgba(230,232,235,.2)!important;background:rgba(10,14,20,.35)!important;"
    "color:#e6e8eb!important;font-size:.82rem!important;padding:0.25rem .85rem!important;"
    "text-transform:uppercase;}"
    ".st-key-brandrow .stTextInput input:focus{border-color:#4c8dff!important;"
    "box-shadow:none!important;}"
    ".st-key-runbtn button{border-radius:9999px;border:1px solid rgba(230,232,235,.2)!important;"
    "background:transparent!important;color:#e6e8eb!important;font-weight:500;min-height:0;"
    "padding:0.25rem 0.85rem;width:auto;white-space:nowrap;transform:translateY(8px);}"
    ".st-key-analysebtn button{border-radius:9999px;border:1px solid rgba(76,141,255,.75)!important;"
    "background:rgba(76,141,255,.12)!important;color:#e6e8eb!important;font-weight:600;"
    "min-height:0;padding:0.25rem 0.9rem;width:auto;white-space:nowrap;transform:translateY(8px);}"
    ".st-key-runbtn button:hover,.st-key-analysebtn button:hover{border-color:#4c8dff!important;color:#4c8dff!important;"
    "background:transparent!important;}"
    "</style>",
    unsafe_allow_html=True,
)


def _normalise_symbol(value: str) -> str:
    symbol = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    if symbol and not symbol.endswith("USDT"):
        symbol += "USDT"
    return symbol


_brow = st.container(key="brandrow")
_brow.markdown(chrome.brand_html("TRADE", "DASHBOARD"), unsafe_allow_html=True)
_brow.button("Run", key="runbtn")
_brow.text_input(
    "Symbol",
    key="analysis_symbol_input",
    placeholder="INJUSDT",
    label_visibility="collapsed",
)
if _brow.button("Analyse", key="analysebtn"):
    requested = _normalise_symbol(st.session_state.get("analysis_symbol_input", ""))
    if requested:
        st.session_state.analysis_request_submitted = True
        st.session_state.openai_analysis_error = None
        try:
            api_key = (st.secrets.get("openai_api_key") or "").strip()
            if not api_key or api_key == "PASTE_OPENAI_API_KEY_HERE":
                raise RuntimeError("OpenAI API key is not configured in .streamlit/secrets.toml.")
            with st.spinner(f"Analysing {requested} with OpenAI..."):
                openai_analysis.generate_dashboard_analysis(
                    requested,
                    api_key=api_key,
                )
            st.session_state.analysis_requested_symbol = requested
            st.rerun()
        except Exception as exc:
            st.session_state.openai_analysis_error = str(exc)

# Show the requested symbol when the user has used the Analyse control; otherwise
# show the most recently generated analysis (newest analyses/<SYMBOL>.json).
symbol = st.session_state.get("analysis_requested_symbol") or dashboard.latest_symbol()
data = dashboard.load_analysis(symbol)

if st.session_state.get("openai_analysis_error"):
    st.error(st.session_state.openai_analysis_error, icon="⚠️")

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
    if st.session_state.get("analysis_request_submitted"):
        st.info(
            f"Ready to run OpenAI analysis for **{symbol}**. Add the action prompt/API "
            "step next and this button can generate the dashboard result directly.",
            icon="✨",
        )
    else:
        st.warning(
            f"No analysis on file for **{symbol}**.",
            icon="📭",
        )
