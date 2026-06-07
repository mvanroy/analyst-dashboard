"""Orion-Lite — a live Binance Futures activity dashboard.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import base64
import os
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from st_aggrid import AgGrid, JsCode

import icons
import rules
import scanner

GREEN = "#0ecb81"
RED = "#f6465d"
NEUTRAL = "#848e9c"

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")


@st.cache_data(show_spinner=False)
def logo_data_uri():
    try:
        with open(LOGO_PATH, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


st.set_page_config(page_title="Market Scanner", layout="wide", page_icon=LOGO_PATH)

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
      .orion-logo {font-size: 1.7rem; font-weight: 800; letter-spacing: .04em; color: #e6e8eb; line-height: 1.1;}
      .orion-logo .accent {color: #4c8dff;}
      .orion-logo .sub {display: block; font-size: .8rem; font-weight: 400; color: #848e9c; letter-spacing: .02em;}
      .orion-meta {color: #5b626c; font-size: .8rem; margin-top: .2rem;}
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


# S&P 500 futures sentiment — refreshes at most every 5 min, and on Run Market
# Scan. Only the % is fetched here; the live clocks tick client-side (see below).
@st.cache_data(ttl=300, show_spinner=False)
def sp_futures():
    return scanner.sp500_futures()


# Live session-clock strip (Tokyo / London / NYSE) + S&P 500 futures tile.
# Everything ticks in the BROWSER via setInterval — no Streamlit reruns, no
# flicker. Only SP_PCT is injected from Python. {pct} -> "null" or a number.
CLOCKS_HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  html,body { margin:0; padding:0; background:transparent;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  .strip { display:flex; justify-content:flex-end; align-items:stretch;
    gap:7px; flex-wrap:wrap; }
  .tile { background:#15181f; border:1px solid #2a2f37; border-radius:9px;
    padding:6px 10px; min-width:84px; display:flex; flex-direction:column;
    justify-content:center; }
  .top { display:flex; justify-content:space-between; align-items:baseline;
    gap:14px; }
  .tile.live { background:rgba(14,203,129,0.13); border-color:rgba(14,203,129,0.55); }
  .name { color:#c5ccd4; font-size:11px; font-weight:800; letter-spacing:.04em;
    text-transform:uppercase; }
  .when { color:#848e9c; font-size:10px; font-weight:600; white-space:nowrap;
    font-variant-numeric:tabular-nums; }
  .label { color:#6b747e; font-size:8px; font-weight:700; letter-spacing:.13em;
    text-transform:uppercase; margin-top:4px; line-height:1; text-align:center; }
  .value { font-size:16px; font-weight:800; margin-top:1px; line-height:1.15;
    font-variant-numeric:tabular-nums; white-space:nowrap; text-align:center; }
  .green { color:#0ecb81; }
  .red { color:#f6465d; }
  .muted { color:#848e9c; }
</style></head><body>
  <div class="strip" id="strip"></div>
  <script>
    var SP_PCT = __SP_PCT__;
    // sessions are [openMin, closeMin] in local minutes-since-midnight.
    var EX = [
      {name:'TOKYO',  tz:'Asia/Tokyo',        sessions:[[540,690],[750,900]]}, // 9:00-11:30, 12:30-15:00 (lunch)
      {name:'LONDON', tz:'Europe/London',     sessions:[[480,990]]},           // 8:00-16:30
      {name:'NYSE',   tz:'America/New_York',  sessions:[[570,960]]}            // 9:30-16:00
    ];
    function tzParts(tz){
      var d = new Date(new Date().toLocaleString('en-US',{timeZone:tz}));
      return {dow:d.getDay(), sec:d.getHours()*3600 + d.getMinutes()*60 + d.getSeconds()};
    }
    function isWeekday(dow){ return dow>=1 && dow<=5; }
    function statusFor(ex){
      var p = tzParts(ex.tz), min = p.sec/60, i, s;
      if(isWeekday(p.dow)){
        for(i=0;i<ex.sessions.length;i++){ s=ex.sessions[i];
          if(min>=s[0] && min<s[1]) return {open:true, secs:(s[1]*60 - p.sec)}; }
      }
      var best = null;                       // seconds to the next open
      for(i=0;i<8;i++){
        var d2 = (p.dow+i)%7;
        if(!isWeekday(d2)) continue;
        for(var j=0;j<ex.sessions.length;j++){
          var off = i*86400 - p.sec + ex.sessions[j][0]*60;
          if(off>0 && (best===null || off<best)) best = off;
        }
      }
      return {open:false, secs:best};
    }
    function fmt(secs){
      if(secs==null) return '--';
      var h=Math.floor(secs/3600), m=Math.floor((secs%3600)/60), s=Math.floor(secs%60);
      if(h>=1) return h+'h '+m+'m';
      if(m>=1) return m+'m '+s+'s';
      return s+'s';
    }
    function dayTime(tz){
      var d=new Date();
      var wd=new Intl.DateTimeFormat('en-US',{timeZone:tz,weekday:'short'}).format(d).toUpperCase();
      var tm=new Intl.DateTimeFormat('en-US',{timeZone:tz,hour:'numeric',minute:'2-digit',hour12:true}).format(d);
      return wd+' '+tm;
    }
    function tile(name, when, label, value, extra){
      var top = '<div class="top"><span class="name">'+name+'</span>'
        + (when ? '<span class="when">'+when+'</span>' : '') + '</div>';
      return '<div class="tile'+(extra?' '+extra:'')+'">'+top
        + '<div class="label">'+label+'</div>'+value+'</div>';
    }
    function render(){
      var html='', i;
      for(i=0;i<EX.length;i++){
        var ex=EX[i], st=statusFor(ex), label, value, extra;
        if(st.open){
          label='Closes in';
          value='<div class="value green">'+fmt(st.secs)+'</div>';
          extra='live';
        } else {
          label='Opens in';
          value='<div class="value red">'+fmt(st.secs)+'</div>';
          extra='';
        }
        html += tile(ex.name, dayTime(ex.tz), label, value, extra);
      }
      var sp;
      if(SP_PCT===null || isNaN(SP_PCT)){ sp='<div class="value muted">—</div>'; }
      else {
        var up = SP_PCT>=0, cls = up?'green':'red', dot = up?'🟢':'🔴';
        sp='<div class="value '+cls+'">'+dot+' '+(up?'+':'')+SP_PCT.toFixed(2)+'%</div>';
      }
      html += tile('S&amp;P 500 Fut', '', 'Day Chg', sp, '');
      document.getElementById('strip').innerHTML = html;
    }
    render(); setInterval(render, 1000);
  </script>
</body></html>
"""


def render_clocks():
    sp = sp_futures()
    pct = sp.get("pct") if sp else None
    val = "null" if pct is None else f"{pct:.4f}"
    components.html(CLOCKS_HTML.replace("__SP_PCT__", val), height=66)


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
    _nav = st.container(key="topnav")
    _nav.page_link("app.py", label="Market Scanner")
    _nav.page_link("pages/1_Analyst_Dashboard.py", label="Analyst Dashboard")
    _nav.page_link("pages/2_Position_Size_Calculator.py", label="Position Size Calculator")
with clockc:
    render_clocks()

# ---------------- header: logo + refresh (left) + shortlist (right) ----------------
left, right = st.columns([1, 3])

with left:
    _logo = logo_data_uri()
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
        sp_futures.clear()
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

