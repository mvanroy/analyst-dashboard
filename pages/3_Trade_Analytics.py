"""Trade Analytics — at-a-glance performance from your live Bybit closed trades.

Phase 1 (objective, $-based): KPI cards, equity curve, P&L distribution, win-rate over time,
and breakdowns by coin and by direction. Qualitative breakdowns (by setup / bias / grade) will
read the journal's manual columns in a later phase.
"""
from __future__ import annotations

import base64

import altair as alt
import pandas as pd
import streamlit as st

import bybit
import chrome

st.set_page_config(page_title="Trade Analytics", page_icon="📈", layout="wide")
chrome.inject_background()

# --------------------------------------------------------------------------- #
# Styling — reuse the app's purple-edged card system + a KPI grid + dark charts
# --------------------------------------------------------------------------- #
st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
.ac-card{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);padding:14px 16px;}
.ac-h{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#8b94a0;margin:0 0 10px;}
/* equity-curve container styled as a card (so it sits beside the Performance-by-Setup box) */
.st-key-eqcard{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);padding:14px 16px;height:100%;}
.ac-setup{height:100%;min-height:322px;display:flex;flex-direction:column;}
.ac-setup .empty{flex:1;display:flex;align-items:center;justify-content:center;text-align:center;
  color:#6b747e;font-size:12.5px;line-height:1.5;padding:10px;}
.ac-setup .viewall{margin-top:10px;}
.ac-setup .viewall a{color:#4c8dff;font-size:12px;font-weight:600;text-decoration:none;}
/* Refresh — icon-only (↻), same pill treatment as Launch Journal (transparent + light border,
   hover→blue), sized to the period selector's height */
.st-key-an_refresh button{border-radius:9999px!important;border:1px solid rgba(230,232,235,.2)!important;
  background:transparent!important;color:#e6e8eb!important;width:40px!important;height:40px!important;
  min-height:0!important;padding:0!important;display:flex;align-items:center;justify-content:center;}
.st-key-an_refresh button p{font-size:18px!important;line-height:1!important;font-weight:500!important;}
.st-key-an_refresh button:hover{border-color:#4c8dff!important;color:#4c8dff!important;background:transparent!important;}
/* Launch Journal — Run-pill style, right-aligned flush to the Avg Loss box's right edge */
.st-key-journallaunch{display:flex;align-items:flex-end;}
.st-key-journallaunch [data-testid="stElementContainer"],
.st-key-journallaunch [data-testid="stLinkButton"]{width:auto!important;margin-right:0!important;}
.st-key-journallaunch a,.st-key-journallaunch button{border-radius:9999px!important;
  border:1px solid rgba(230,232,235,.2)!important;background:transparent!important;color:#e6e8eb!important;
  font-weight:500!important;min-height:0;padding:0.25rem 0.95rem!important;width:auto!important;white-space:nowrap;}
.st-key-journallaunch a:hover,.st-key-journallaunch button:hover{border-color:#4c8dff!important;
  color:#4c8dff!important;background:transparent!important;}
/* KPI grid */
.kgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:4px 0 14px;}
@media (min-width:1300px){.kgrid{grid-template-columns:repeat(8,1fr);}}
.kcard{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);padding:13px 15px;}
.kcap{font-size:9.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;}
.kbig{font-size:25px;font-weight:800;color:#e6e8eb;line-height:1.1;margin-top:5px;font-variant-numeric:tabular-nums;}
.kbig.green{color:#0ecb81;} .kbig.red{color:#f6465d;} .kbig.blue{color:#4c8dff;} .kbig.amber{color:#e0a33e;}
.ksub{font-size:11px;color:#8b94a0;margin-top:4px;font-weight:600;}
/* tables */
.atbl{width:100%;border-collapse:collapse;font-size:13px;}
.atbl th{text-align:left;font-size:9.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:#8b94a0;padding:0 8px 8px;border-bottom:1px solid #232a33;}
.atbl td{padding:8px;border-bottom:1px solid #161b21;color:#cdd3da;font-variant-numeric:tabular-nums;}
.atbl tr:last-child td{border-bottom:none;}
.atbl td.r,.atbl th.r{text-align:right;}
.pos{color:#0ecb81;} .neg{color:#f6465d;}
.pill{font-size:11px;font-weight:700;padding:1px 7px;border-radius:5px;}
.pill.long{color:#0ecb81;background:rgba(14,203,129,.12);}
.pill.short{color:#f6465d;background:rgba(246,70,93,.12);}
.pill.win{color:#0ecb81;background:rgba(14,203,129,.12);}
.pill.loss{color:#f6465d;background:rgba(246,70,93,.12);}
.pill.be{color:#8b94a0;background:rgba(139,148,160,.12);}
</style>""",
    unsafe_allow_html=True,
)

# Refresh icon (the user's refresh.svg) as a CSS mask, so it tints with the pill (grey → blue
# on hover). The button's text label is hidden; only the icon shows.
_REFRESH_SVG = (
    "<svg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'><path d='M480.6,235.6c-11.3,0-20.4,9.1-20.4,20.4"
    "c0,112.6-91.6,204.2-204.2,204.2c-112.6,0-204.2-91.6-204.2-204.2S143.4,51.8,256,51.8c61.5,0,118.5,27.1,157.1,73.7"
    "h-70.5c-11.3,0-20.4,9.1-20.4,20.4s9.1,20.4,20.4,20.4h114.6c11.3,0,20.4-9.1,20.4-20.4V31.4c0-11.3-9.1-20.4-20.4-20.4"
    "s-20.4,9.1-20.4,20.4v59C390.7,40.1,325.8,11,256,11C120.9,11,11,120.9,11,256c0,135.1,109.9,245,245,245s245-109.9,"
    "245-245C501,244.7,491.9,235.6,480.6,235.6z'/></svg>"
)
_refresh_uri = "data:image/svg+xml;base64," + base64.b64encode(_REFRESH_SVG.encode()).decode()
st.markdown(
    f"""<style>
.st-key-an_refresh button p{{font-size:0!important;}}
.st-key-an_refresh button::before{{content:"";display:inline-block;width:16px;height:16px;
  background-color:#e6e8eb;transition:background-color .12s;
  -webkit-mask:url("{_refresh_uri}") center/contain no-repeat;mask:url("{_refresh_uri}") center/contain no-repeat;}}
.st-key-an_refresh button:hover::before{{background-color:#4c8dff;}}
</style>""",
    unsafe_allow_html=True,
)

chrome.render_header("TRADE", "ANALYTICS", "Bybit · USDT Perp")

# --------------------------------------------------------------------------- #
# Controls + data
# --------------------------------------------------------------------------- #
_PERIODS = {"Last 30 days": 30, "Last 90 days": 90, "Last 180 days": 180, "Last 365 days": 365}


# Cache the IMPORTED fetch (its source lives in bybit.py). Defining a local cached function
# here would make st.cache_data run inspect.getsource on THIS file, whose large inline CSS
# string trips Python's tokenizer ("EOF in multi-line string").
_load = st.cache_data(ttl=300, show_spinner="Pulling your Bybit trades…")(bybit.fetch_closed_trades)
# Journal rows (the manual Set Up Type / Market Bias columns live in the Sheet, not Bybit's API).
_load_journal = st.cache_data(ttl=300, show_spinner=False)(bybit.journal_rows)


_sel, _ref, _spacer, _launch = st.columns([1.1, 0.35, 2.6, 0.95])
with _sel:
    period_label = st.selectbox("Period", list(_PERIODS), index=2, label_visibility="collapsed")
with _ref:
    if st.button("↻", key="an_refresh", help="Refresh Bybit trades + journal"):
        _load.clear()
        _load_journal.clear()
        st.rerun()
with _launch:
    # Launch Journal — opens the journal Google Sheet in a new tab (Run-pill style, right-aligned).
    with st.container(key="journallaunch"):
        _jurl = bybit.sheet_url()
        if _jurl:
            st.link_button("Launch Journal", _jurl)
        else:
            st.button("Launch Journal", disabled=True,
                      help="Add your journal Sheet URL to journal_config.json (paste it to me).")
days = _PERIODS[period_label]


if not bybit.have_creds():
    st.warning("No Bybit API key configured — add `bybit_api_key` / `bybit_api_secret` to "
               "`journal_config.json` to see your analytics.")
    st.stop()

try:
    trades = _load(days)
except Exception as e:
    st.error(f"Couldn't reach Bybit: {e}")
    st.stop()

if not trades:
    st.info(f"No closed trades found in the {period_label.lower()}.")
    st.stop()

df = pd.DataFrame(trades).sort_values("ts").reset_index(drop=True)


def fusd(v, sign=False):
    s = "+" if (sign and v >= 0) else ""
    return f"{s}${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"


# --------------------------------------------------------------------------- #
# Metrics ($-based)
# --------------------------------------------------------------------------- #
n = len(df)
wins, losses = df[df.net > 0], df[df.net < 0]
win_rate = len(wins) / n * 100
net = df.net.sum()
gross_profit, gross_loss = wins.net.sum(), -losses.net.sum()
profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
expectancy = net / n
avg_win = wins.net.mean() if len(wins) else 0.0
avg_loss = losses.net.mean() if len(losses) else 0.0
df["cum"] = df.net.cumsum()
max_dd = (df.cum - df.cum.cummax()).min()  # most negative peak-to-trough
pf_txt = "∞" if profit_factor == float("inf") else f"{profit_factor:.2f}"

kpis = [
    ("Total Trades", f"{n}", "", f"{len(wins)}W · {len(losses)}L"),
    ("Win Rate", f"{win_rate:.1f}%", "green" if win_rate >= 50 else "amber", f"{len(wins)}/{n}"),
    ("Net P&L", fusd(net, sign=True), "green" if net >= 0 else "red", "after fees"),
    ("Profit Factor", pf_txt, "green" if profit_factor >= 1 else "red", "gross win ÷ loss"),
    ("Expectancy", fusd(expectancy, sign=True), "green" if expectancy >= 0 else "red", "per trade"),
    ("Max Drawdown", fusd(max_dd), "red", "peak to trough"),
    ("Avg Win", fusd(avg_win, sign=True), "green", f"{len(wins)} trades"),
    ("Avg Loss", fusd(avg_loss, sign=True), "red", f"{len(losses)} trades"),
]
cards = "".join(
    f"<div class='kcard'><div class='kcap'>{cap}</div>"
    f"<div class='kbig {cls}'>{val}</div><div class='ksub'>{sub}</div></div>"
    for cap, val, cls, sub in kpis
)
st.markdown(f"<div class='kgrid'>{cards}</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Charts — dark Altair theme
# --------------------------------------------------------------------------- #
def _theme(c):
    return (c.configure_view(strokeWidth=0)
            .configure_axis(labelColor="#8b94a0", titleColor="#8b94a0",
                            gridColor="#19202e", domainColor="#2a323c", tickColor="#2a323c")
            .properties(background="transparent"))


# Equity curve (left, half width) + Performance by Setup (right, half width)
eq_col, setup_col = st.columns(2, gap="medium")
with eq_col:
    with st.container(key="eqcard"):
        st.markdown("<div class='ac-h'>Equity Curve — cumulative net P&amp;L ($)</div>", unsafe_allow_html=True)
        # Aggregate to one end-of-day point per day so the curve runs over DAYS (not intraday
        # hours), and start it from $0 the day before the first trade.
        _d = df.copy()
        _d["day"] = _d["date"].dt.normalize()
        daily = _d.groupby("day", as_index=False).agg(cum=("cum", "last"))
        _base = pd.DataFrame([{"day": daily["day"].min() - pd.Timedelta(days=1), "cum": 0.0}])
        eq = pd.concat([_base, daily], ignore_index=True)
        area = alt.Chart(eq).mark_area(
            line={"color": "#a78bfa", "strokeWidth": 2},
            color=alt.Gradient(gradient="linear",
                               stops=[alt.GradientStop(color="#7c3aed", offset=0),
                                      alt.GradientStop(color="rgba(124,58,237,0.02)", offset=1)],
                               x1=1, x2=1, y1=1, y2=0),
        ).encode(
            x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b")),
            y=alt.Y("cum:Q", title=None),
            tooltip=[alt.Tooltip("day:T", title="Date", format="%d %b %Y"),
                     alt.Tooltip("cum:Q", title="Cumulative $", format=",.2f")],
        ).properties(height=250)
        st.altair_chart(_theme(area), use_container_width=True)
with setup_col:
    # Performance by Setup — reads the journal's "Set Up Type" column from the Sheet (the manual
    # judgment columns don't exist in Bybit's API). Groups tagged trades by setup; empty until
    # at least one journal row has a Set Up Type filled in.
    _setup_cols = ("<tr><th>Setup</th><th class='r'>Trades</th><th class='r'>Win Rate</th>"
                   "<th class='r'>Avg P&amp;L</th><th class='r'>Net P&amp;L</th></tr>")
    _setups = {}
    for _jr in _load_journal():
        _name = str(_jr.get("setup_type") or "").strip()
        if not _name:
            continue
        try:
            _net = float(_jr.get("pl_net") or 0)
        except (TypeError, ValueError):
            continue
        _s = _setups.setdefault(_name, {"trades": 0, "wins": 0, "net": 0.0})
        _s["trades"] += 1
        _s["wins"] += 1 if _net > 0 else 0
        _s["net"] += _net
    _setup_rows = sorted(
        ({"key": k, "trades": v["trades"], "wr": v["wins"] / v["trades"] * 100,
          "avg": v["net"] / v["trades"], "net": v["net"]} for k, v in _setups.items()),
        key=lambda r: r["net"], reverse=True)
    if _setup_rows:
        _body = "".join(
            f"<tr><td>{r['key']}</td><td class='r'>{r['trades']}</td>"
            f"<td class='r'>{r['wr']:.0f}%</td>"
            f"<td class='r {'pos' if r['avg'] >= 0 else 'neg'}'>{fusd(r['avg'], sign=True)}</td>"
            f"<td class='r {'pos' if r['net'] >= 0 else 'neg'}'>{fusd(r['net'], sign=True)}</td></tr>"
            for r in _setup_rows)
        st.markdown(
            "<div class='ac-card ac-setup'>"
            "<div class='ac-h'>Performance by Setup</div>"
            f"<table class='atbl'>{_setup_cols}{_body}</table>"
            "<div class='viewall'><a>View all setups →</a></div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='ac-card ac-setup'>"
            "<div class='ac-h'>Performance by Setup</div>"
            f"<table class='atbl'>{_setup_cols}</table>"
            "<div class='empty'>No tagged setups yet — add a <b style='color:#8b94a0'>Set Up Type</b> "
            "to your journal trades and this fills in automatically.</div>"
            "<div class='viewall'><a>View all setups →</a></div>"
            "</div>",
            unsafe_allow_html=True,
        )

# Breakdown tables: by coin | by direction
col_a, col_b = st.columns(2)


def _breakdown(group_col):
    g = df.groupby(group_col)
    rows = []
    for key, sub in g:
        w = (sub.net > 0).sum()
        rows.append({"key": key, "trades": len(sub), "wr": w / len(sub) * 100, "net": sub.net.sum()})
    return sorted(rows, key=lambda r: r["net"], reverse=True)


def _table(rows, head):
    body = "".join(
        f"<tr><td>{r['key']}</td><td class='r'>{r['trades']}</td>"
        f"<td class='r'>{r['wr']:.0f}%</td>"
        f"<td class='r {'pos' if r['net'] >= 0 else 'neg'}'>{fusd(r['net'], sign=True)}</td></tr>"
        for r in rows
    )
    return (f"<div class='ac-card'><div class='ac-h'>{head}</div>"
            f"<table class='atbl'><tr><th>{head.split(' ')[-1]}</th><th class='r'>Trades</th>"
            f"<th class='r'>Win Rate</th><th class='r'>Net P&amp;L</th></tr>{body}</table></div>")


with col_a:
    st.markdown(_table(_breakdown("coin"), "Performance by Coin"), unsafe_allow_html=True)
with col_b:
    # direction first by a fixed order (Long, Short)
    drows = _breakdown("direction")
    st.markdown(_table(drows, "Performance by Direction"), unsafe_allow_html=True)

# Distribution + win-rate-over-time
col_c, col_d = st.columns(2)
with col_c:
    st.markdown("<div class='ac-h'>Distribution of Net P&amp;L</div>", unsafe_allow_html=True)
    hist = alt.Chart(df).mark_bar().encode(
        x=alt.X("net:Q", bin=alt.Bin(maxbins=12), title="Net P&L ($)"),
        y=alt.Y("count():Q", title=None),
        color=alt.condition("datum.net >= 0", alt.value("#0ecb81"), alt.value("#f6465d")),
        tooltip=[alt.Tooltip("count():Q", title="Trades")],
    ).properties(height=240)
    st.altair_chart(_theme(hist), use_container_width=True)
with col_d:
    st.markdown("<div class='ac-h'>Win Rate Over Time (cumulative)</div>", unsafe_allow_html=True)
    df["trade_no"] = range(1, n + 1)
    df["cum_wr"] = (df.net > 0).cumsum() / df.trade_no * 100
    wr = alt.Chart(df).mark_line(color="#a78bfa", strokeWidth=2, point={"color": "#a78bfa", "size": 28}).encode(
        x=alt.X("trade_no:Q", title="Trade #"),
        y=alt.Y("cum_wr:Q", title=None, scale=alt.Scale(domain=[0, 100])),
        tooltip=[alt.Tooltip("trade_no:Q", title="Trade #"), alt.Tooltip("cum_wr:Q", title="Win rate %", format=".1f")],
    ).properties(height=240)
    st.altair_chart(_theme(wr), use_container_width=True)

# Recent trades
st.markdown("<div class='ac-h' style='margin-top:6px'>Recent Trades</div>", unsafe_allow_html=True)
recent = df.sort_values("ts", ascending=False).head(12)
rows = ""
for _, t in recent.iterrows():
    ls = t["direction"].lower()
    wl = "win" if t.net > 0 else ("loss" if t.net < 0 else "be")
    wl_txt = "Win" if t.net > 0 else ("Loss" if t.net < 0 else "BE")
    rows += (
        f"<tr><td>{t['date'].strftime('%d %b %Y')}</td><td>{t['coin']}</td>"
        f"<td><span class='pill {ls}'>{t['direction']}</span></td>"
        f"<td class='r'>{t['entry']:g}</td><td class='r'>{t['exit']:g}</td>"
        f"<td class='r'>${t['size']:,.2f}</td>"
        f"<td class='r {'pos' if t.net >= 0 else 'neg'}'>{fusd(t.net, sign=True)}</td>"
        f"<td class='r'><span class='pill {wl}'>{wl_txt}</span></td></tr>"
    )
st.markdown(
    "<div class='ac-card'><table class='atbl'>"
    "<tr><th>Date</th><th>Coin</th><th>Direction</th><th class='r'>Entry</th><th class='r'>Exit</th>"
    "<th class='r'>Size</th><th class='r'>Net P&amp;L</th><th class='r'>Result</th></tr>"
    f"{rows}</table></div>",
    unsafe_allow_html=True,
)

st.markdown(
    "<div style='color:#6b747e;font-size:12px;margin-top:12px;'>Live from Bybit · "
    "$-based (R multiples need your stop, coming later) · by-setup / by-bias panels arrive as you "
    "fill the journal.</div>",
    unsafe_allow_html=True,
)
