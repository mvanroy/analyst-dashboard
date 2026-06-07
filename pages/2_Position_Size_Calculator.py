"""Position Size Calculator — Bybit USDT perps, isolated margin.

Pure-Python math (no LLM): position sizing, risk, required margin, an estimated
liquidation price, and R:R + P/L per target. Trade levels are copied from the
coin's analysis (analyses/<SYMBOL>.json); account inputs are yours. Live Bybit
mark price is shown only as a reference.
"""
from __future__ import annotations

import httpx
import streamlit as st

import dashboard

st.set_page_config(page_title="Position Size Calculator", page_icon="📐", layout="wide")

st.markdown(
    "<style>"
    "[data-testid='stSidebarNav']{display:none;}"
    "[data-testid='stHeader']{display:none;}"
    ".block-container{padding-top:1.6rem;}"
    ".st-key-topnav{flex-direction:row!important;gap:1.1rem;align-items:center;}"
    ".st-key-topnav [data-testid='stElementContainer']{width:auto!important;}"
    ".st-key-topnav [data-testid='stMarkdownContainer'] p{width:auto!important;"
    "overflow:visible!important;text-overflow:clip!important;white-space:nowrap;}"
    ".pxref{color:#aab2bd;font-size:13px;margin:2px 0 4px;}"
    ".pxref b{color:#e6e8eb;}"
    ".cres{background:#0e1116;border:1px solid #1e242c;border-radius:10px;padding:4px 14px;}"
    ".cr{display:flex;justify-content:space-between;align-items:baseline;padding:9px 0;"
    "border-bottom:1px solid #161b21;font-size:13px;}"
    ".cr:last-child{border-bottom:none;}"
    ".cr span{color:#8b94a0;} .cr b{font-weight:700;color:#dfe3e8;}"
    ".cr b.red{color:#f6465d;} .cr b.green{color:#0ecb81;} .cr b.blue{color:#4c8dff;}"
    "</style>",
    unsafe_allow_html=True,
)

# ---- horizontal page nav (top-left) ----
_nav = st.container(key="topnav")
_nav.page_link("app.py", label="Market Scanner")
_nav.page_link("pages/1_Analyst_Dashboard.py", label="Analyst Dashboard")
_nav.page_link("pages/2_Position_Size_Calculator.py", label="Position Size Calculator")

# ---- which coin? from ?symbol= or the last-analysed coin ----
symbol = st.query_params.get("symbol") or st.session_state.get("dash_symbol", "HYPEUSDT")
symbol = symbol.upper()
coin = symbol[:-4] if symbol.endswith("USDT") else symbol
data = dashboard.load_analysis(symbol)
levels = (data or {}).get("levels", {})
direction = (levels.get("direction") or "long").lower()

st.title("📐 Position Size Calculator")
st.caption(f"{symbol} · Bybit · USDT Perp · Isolated · {direction.title()}")


@st.cache_data(ttl=60, show_spinner=False)
def bybit_price(sym):
    try:
        r = httpx.get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "linear", "symbol": sym},
            timeout=8,
        )
        d = r.json()["result"]["list"][0]
        return {"last": float(d["lastPrice"]), "mark": float(d["markPrice"])}
    except Exception:
        return None


px = bybit_price(symbol)
pxcol, btncol = st.columns([4, 1], vertical_alignment="center")
if px:
    pxcol.markdown(
        f"<div class='pxref'>Bybit mark price: <b>{px['mark']:,.4f}</b> "
        f"· last {px['last']:,.4f} <span style='color:#6b747e'>(reference only)</span></div>",
        unsafe_allow_html=True,
    )
else:
    pxcol.markdown(
        "<div class='pxref'>Bybit price unavailable (symbol may not list on Bybit)</div>",
        unsafe_allow_html=True,
    )
if btncol.button("↻ Refresh price", use_container_width=True):
    bybit_price.clear()
    st.rerun()

st.divider()
left, right = st.columns(2, gap="large")

with left:
    st.markdown("#### Your inputs")
    equity = st.number_input("Account equity ($)", min_value=0.0, value=10000.0, step=100.0, key="calc_equity")
    risk_pct = st.number_input("Risk per trade (%)", min_value=0.0, value=1.0, step=0.1, key="calc_risk")
    leverage = st.number_input("Leverage (x)", min_value=1.0, value=10.0, step=1.0, key="calc_lev")
    mmr = st.number_input(
        "Maintenance margin rate (%)", min_value=0.0, value=0.5, step=0.1, key="calc_mmr",
        help="Bybit's tier-based rate. Default 0.5% — we'll auto-pull the exact tier later.",
    )
    st.markdown("###### Trade levels (from analysis — editable)")
    entry = st.number_input("Entry", min_value=0.0, value=float(levels.get("entry", 0.0)), step=0.01, format="%.4f", key=f"entry_{symbol}")
    stop = st.number_input("Stop loss", min_value=0.0, value=float(levels.get("stop", 0.0)), step=0.01, format="%.4f", key=f"stop_{symbol}")
    t1 = st.number_input("Target 1", min_value=0.0, value=float(levels.get("target1", 0.0)), step=0.01, format="%.4f", key=f"t1_{symbol}")
    t2 = st.number_input("Target 2", min_value=0.0, value=float(levels.get("target2", 0.0)), step=0.01, format="%.4f", key=f"t2_{symbol}")

with right:
    st.markdown("#### Result")
    stop_dist = abs(entry - stop)
    warnings = []
    if entry <= 0 or stop_dist == 0:
        st.info("Enter a valid entry and stop to calculate.", icon="✏️")
    else:
        risk_amount = equity * risk_pct / 100
        stop_dist_pct = stop_dist / entry * 100
        size = risk_amount / stop_dist
        notional = size * entry
        req_margin = notional / leverage
        imr = 1.0 / leverage
        mmr_f = mmr / 100
        if direction == "short":
            liq = entry * (1 + imr - mmr_f)
        else:
            liq = entry * (1 - imr + mmr_f)
        liq_dist_pct = abs(entry - liq) / entry * 100

        def rr(target):
            return abs(target - entry) / stop_dist if stop_dist else 0.0

        def pl(target):
            return size * abs(target - entry)

        # sanity checks
        if direction == "long" and liq >= stop:
            warnings.append("Liquidation sits at/above your stop — reduce leverage.")
        if direction == "short" and liq <= stop:
            warnings.append("Liquidation sits at/below your stop — reduce leverage.")
        if req_margin > equity:
            warnings.append("Required margin exceeds your account equity.")

        m = lambda x: f"${x:,.2f}"
        liq_sign = "−" if direction == "long" else "+"
        rows = [
            ("Position size", f"{size:,.4f} {coin}", ""),
            ("Notional value", m(notional), ""),
            ("Risk amount", f"{m(risk_amount)} ({risk_pct:.1f}%)", "red"),
            ("Stop distance", f"{stop_dist_pct:.2f}%", ""),
            ("Required margin", m(req_margin), ""),
            ("Est. liquidation ≈", f"{liq:,.4f} ({liq_sign}{liq_dist_pct:.1f}%)", "red"),
            ("R:R → Target 1", f"1 : {rr(t1):.2f}", "blue"),
            ("P/L → Target 1", f"+{m(pl(t1))}", "green"),
            ("R:R → Target 2", f"1 : {rr(t2):.2f}", "blue"),
            ("P/L → Target 2", f"+{m(pl(t2))}", "green"),
        ]
        html = '<div class="cres">' + "".join(
            f'<div class="cr"><span>{lab}</span><b class="{cls}">{val}</b></div>'
            for lab, val, cls in rows
        ) + "</div>"
        st.markdown(html, unsafe_allow_html=True)

    for w in warnings:
        st.warning(w, icon="⚠️")
