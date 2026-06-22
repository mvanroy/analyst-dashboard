"""Trade Setup — single-coin read rendered from a structured analysis
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

st.set_page_config(page_title="Trade Setup", page_icon="📊", layout="wide")

# Shared chrome: nav + live clocks row (brand rendered below alongside the
# ticker analysis controls).
chrome.render_header("TRADE", "SETUP", brand=False)

# Brand + ticker analysis controls on one row.
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
    ".st-key-brandrow .stTextInput{width:150px!important;transform:translateY(2px);}"
    ".st-key-brandrow .stTextInput [data-testid='stTextInputRootElement']{height:32px!important;"
    "border-radius:7px!important;border:1px solid rgba(230,232,235,.22)!important;"
    "background:rgba(10,14,20,.42)!important;box-shadow:none!important;}"
    ".st-key-brandrow .stTextInput [data-testid='stTextInputRootElement']:focus-within{"
    "border-color:#4c8dff!important;box-shadow:0 0 0 1px rgba(76,141,255,.14)!important;}"
    ".st-key-brandrow .stTextInput [data-testid='stTextInputRootElement'] > div{"
    "background:transparent!important;height:100%!important;}"
    ".st-key-brandrow .stTextInput input{height:100%!important;border:0!important;"
    "border-radius:0!important;background:transparent!important;color:#e6e8eb!important;"
    "font-size:.82rem!important;padding:0.25rem .85rem!important;text-transform:uppercase;}"
    ".st-key-brandrow .stTextInput input:focus{box-shadow:none!important;outline:none!important;}"
    ".st-key-analysis_setup_chart{transform:translateY(2px);}"
    ".st-key-analysis_setup_chart [data-testid='stWidgetLabel']{display:none!important;}"
    ".st-key-analysis_setup_chart [data-testid='stPills']{display:flex;gap:.28rem;}"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button{min-height:32px!important;"
    "border-radius:7px!important;border:1px solid rgba(230,232,235,.18)!important;"
    "background:rgba(10,14,20,.30)!important;color:#8b94a0!important;font-size:.76rem!important;"
    "font-weight:800!important;padding:.18rem .58rem!important;}"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button:hover{"
    "border-color:rgba(76,141,255,.55)!important;color:#dce3ec!important;}"
    ".st-key-analysis_setup_chart button[data-testid='stBaseButton-pillsActive'],"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button[aria-pressed='true'],"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button[aria-selected='true']{"
    "border-color:rgba(76,141,255,.85)!important;background:rgba(76,141,255,.16)!important;"
    "color:#e6e8eb!important;}"
    ".st-key-analysebtn button{border-radius:9999px;border:1px solid rgba(76,141,255,.75)!important;"
    "background:rgba(76,141,255,.12)!important;color:#e6e8eb!important;font-weight:600;"
    "min-height:0;padding:0.25rem 0.9rem;width:auto;white-space:nowrap;transform:translateY(2px);}"
    ".st-key-analysebtn button:hover{border-color:#4c8dff!important;color:#4c8dff!important;"
    "background:transparent!important;}"
    "</style>",
    unsafe_allow_html=True,
)


def _normalise_symbol(value: str) -> str:
    symbol = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    if symbol and not symbol.endswith("USDT"):
        symbol += "USDT"
    return symbol


if "analysis_setup_chart" not in st.session_state:
    st.session_state.analysis_setup_chart = "4H"

_brow = st.container(key="brandrow")
_brow.markdown(chrome.brand_html("TRADE", "SETUP"), unsafe_allow_html=True)
_brow.text_input(
    "Ticker",
    key="analysis_symbol_input",
    placeholder="Ticker",
    label_visibility="collapsed",
)
_brow.pills(
    "Setup chart",
    ["4H", "1H", "15M"],
    selection_mode="single",
    key="analysis_setup_chart",
    label_visibility="collapsed",
)
if _brow.button("Analyse", key="analysebtn"):
    requested = _normalise_symbol(st.session_state.get("analysis_symbol_input", ""))
    setup_chart = st.session_state.get("analysis_setup_chart") or "4H"
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
                    setup_timeframe=setup_chart,
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
    _last_analysed = _m.get("analysis_time") or data.get("generated_at") or "unknown"
    _grade_key = (
        "<span class='gradehelp' tabindex='0'>i"
        "<span class='gradehelpbox'>"
        "<b>Trade grade key</b><br>"
        "<b>A</b>: validated setup, strong R:R, clean location, entry not stale, meaningful move remains.<br>"
        "<b>B</b>: good setup with weaker validation: mixed context, thinner confluence, incomplete trigger, confirmation dependency, or caveat.<br>"
        "<b>C</b>: watchlist / tactical only; plausible but early, late, aggressive, or needing too much to go right.<br>"
        "<b>D</b>: no valid trade setup: poor location, stale pattern, bad R:R, invalid structure, or hypothetical only.<br>"
        "<b>Cap:</b> stale, lagging, chasing, or mostly resolved setups cannot be A-grade."
        "</span></span>"
    )
    _cap = (
        f"Viewing saved result for <b>{data.get('symbol', symbol)}</b> · "
        f"<b>Last analysed:</b> {_last_analysed} · analysis performed on "
        f"{_m.get('timeframe_analyzed', '—')} · setup chart "
        f"<b>{_m.get('setup_timeframe', '—')}</b> · framework "
        f"{data.get('framework_version', 'Trade Setup Framework')} {_grade_key}"
    )
    st.markdown(
        "<style>.v3capline{color:#8b94a0;font-size:.8rem;line-height:1.3;margin:0 0 14px 0;"
        "padding-bottom:6px;border-bottom:1px solid #2a2f3a;}"
        ".gradehelp{position:relative;display:inline-flex;align-items:center;justify-content:center;"
        "width:16px;height:16px;margin-left:5px;border:1px solid #4c8dff;border-radius:50%;"
        "color:#9fc0ff;font-size:10px;font-weight:800;cursor:help;vertical-align:1px;}"
        ".gradehelpbox{display:none;position:absolute;right:0;top:22px;z-index:10;width:360px;"
        "padding:11px 12px;border:1px solid rgba(76,141,255,.45);border-radius:8px;"
        "background:#101722;color:#dce3ec;box-shadow:0 14px 32px rgba(0,0,0,.35);"
        "font-size:.74rem;line-height:1.45;font-weight:400;text-align:left;}"
        ".gradehelp:hover .gradehelpbox,.gradehelp:focus .gradehelpbox{display:block;}</style>"
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
