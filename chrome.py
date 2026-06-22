"""Shared page chrome — the nav + world-clocks bar + brand block.

Used by every page (Scanner in pages/0_Scanner.py and the secondary pages) so the
header is identical and aligned across the app. Importing this module has NO
Streamlit side effects, so it is safe to import from any page; it is also the
single source of truth for the live clocks (app.py imports them from here).
"""
from __future__ import annotations

import base64
import os

import streamlit as st
import streamlit.components.v1 as components

import scanner

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")


def logo_data_uri():
    try:
        with open(LOGO_PATH, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


# Only the % is fetched here; the live clocks tick client-side (see CLOCKS_HTML).
@st.cache_data(ttl=300, show_spinner=False)
def sp_futures():
    return scanner.sp500_futures()


# Live session-clock strip (Tokyo / London / NYSE) + S&P 500 futures tile
# + a 4H candle close countdown.
# Everything ticks in the BROWSER via setInterval — no Streamlit reruns, no
# flicker. Only SP_PCT is injected from Python. {pct} -> "null" or a number.
CLOCKS_HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  html,body { margin:0; padding:0; background:transparent;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  * { box-sizing:border-box; }
  .strip { display:flex; justify-content:flex-end; align-items:stretch;
    gap:7px; flex-wrap:nowrap; }
  .tile { background:#15181f; border:1px solid rgba(139,92,246,0.40); border-radius:9px;
    padding:6px 9px; width:92px; min-width:92px; min-height:72px; display:flex; flex-direction:column;
    justify-content:center; }
  .top { display:flex; flex-direction:column; justify-content:center; align-items:center; gap:2px; }
  .tile.live { background:rgba(14,203,129,0.13); border-color:rgba(14,203,129,0.55); }
  .tile.sp { width:96px; min-width:96px; }
  .tile.fourh { width:112px; min-width:112px;
    border-color:rgba(224,163,62,.56); background:rgba(224,163,62,.10); }
  .name { color:#c5ccd4; font-size:10.5px; font-weight:800; letter-spacing:.04em;
    text-transform:uppercase; white-space:nowrap; }
  .when { color:#848e9c; font-size:9px; font-weight:700; white-space:nowrap;
    font-variant-numeric:tabular-nums; text-transform:uppercase; }
  .label { color:#6b747e; font-size:8px; font-weight:700; letter-spacing:.13em;
    text-transform:uppercase; margin-top:2px; line-height:1; text-align:center; }
  .value { font-size:15.5px; font-weight:800; margin-top:2px; line-height:1.15;
    font-variant-numeric:tabular-nums; white-space:nowrap; text-align:center; }
  .fourh .name { font-size:9.5px; text-align:center; display:block; }
  .fourh .value { color:#e0a33e; font-size:17px; }
  .fourh .when { color:#6b747e; font-size:9.5px; font-weight:700; }
  .green { color:#0ecb81; }
  .red { color:#f6465d; }
  .muted { color:#848e9c; }
  .amber { color:#e0a33e; }
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
    function melTimeFromUtc(date){
      return new Intl.DateTimeFormat('en-AU',{
        timeZone:'Australia/Melbourne', hour:'numeric', minute:'2-digit', hour12:false
      }).format(date) + ' MEL';
    }
    function nextFourHourClose(){
      var now = new Date();
      var close = new Date(now);
      close.setUTCMinutes(0,0,0);
      close.setUTCHours(Math.floor(now.getUTCHours()/4)*4 + 4);
      if(close <= now) close.setUTCHours(close.getUTCHours() + 4);
      return close;
    }
    function tile(name, when, label, value, extra){
      var top = '<div class="top"><span class="name">'+name+'</span>'
        + (when ? '<span class="when">'+when+'</span>' : '<span class="when">&nbsp;</span>') + '</div>';
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
        var up = SP_PCT>=0, cls = up?'green':'red';
        sp='<div class="value '+cls+'">'+(up?'+':'')+SP_PCT.toFixed(2)+'%</div>';
      }
      var close = nextFourHourClose(), secs = Math.max(0, Math.floor((close - new Date())/1000));
      html += tile('S&amp;P 500 Fut', '', 'Day Chg', sp, 'sp');
      html += '<div class="tile fourh"><div class="top"><span class="name">Next 4H Close</span>'
        + '<span class="when">'+melTimeFromUtc(close)+'</span></div>'
        + '<div class="label">Closes in</div><div class="value amber">'+fmt(secs)+'</div></div>';
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
    components.html(CLOCKS_HTML.replace("__SP_PCT__", val), height=78)


# CSS subset of the Scanner chrome shared by the secondary pages so their header
# matches exactly (hide default chrome, nav row, brand).
_HEADER_CSS = """<style>
  [data-testid="stToolbar"]{display:none;}
  [data-testid="stHeader"]{display:none;}
  [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important;}
  [data-testid="stSidebarNav"]{display:none;}
  footer{display:none;}
  .block-container{padding-top:1.6rem;padding-bottom:1rem;max-width:100%;}
  .st-key-topnav{flex-direction:row!important;gap:1.1rem;align-items:center;
    transform:translateY(16px);}
  .st-key-topnav [data-testid="stElementContainer"]{width:auto!important;}
  .st-key-topnav [data-testid="stMarkdownContainer"] p{width:auto!important;
    overflow:visible!important;text-overflow:clip!important;white-space:nowrap;}
  [data-testid="stHorizontalBlock"]:has(.st-key-topnav) iframe{transform:translateY(16px);}
  .orion-brand{display:flex;align-items:center;gap:.7rem;}
  .orion-brand img{width:54px;height:54px;}
  .orion-logo{font-size:1.7rem;font-weight:800;letter-spacing:.04em;color:#e6e8eb;line-height:1.1;white-space:nowrap;}
  .orion-logo .accent{color:#4c8dff;}
  .orion-logo .sub{display:block;font-size:.8rem;font-weight:400;color:#848e9c;letter-spacing:.02em;}
  .st-key-brandrow{flex-direction:row!important;align-items:flex-start!important;gap:1.3rem;
    margin-top:12px!important;min-height:54px;}
  .st-key-brandrow [data-testid="stElementContainer"]{width:auto!important;
    align-self:center!important;flex-shrink:0!important;}
  .st-key-brandrow [data-testid="stElementContainer"]:has(.orion-brand){align-self:flex-start!important;}
</style>"""

# Ambient purple gradient behind page content — shared across all pages so the
# look is consistent. Fixed attachment so it reads as soft ambient lighting.
_PAGE_BG_CSS = """<style>
[data-testid="stAppViewContainer"]{background:
  radial-gradient(1100px 720px at 8% 12%, rgba(124,58,237,.22), transparent 60%),
  radial-gradient(1000px 800px at 92% 6%, rgba(168,85,247,.16), transparent 55%),
  radial-gradient(1200px 900px at 78% 92%, rgba(99,57,213,.20), transparent 60%),
  radial-gradient(900px 720px at 18% 86%, rgba(147,51,234,.14), transparent 55%),
  #0a0711!important;background-attachment:fixed!important;}
[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:transparent!important;}
</style>"""


def inject_background():
    """Ambient purple gradient behind the page content (shared across pages).
    Call once near the top of each page."""
    st.markdown(_PAGE_BG_CSS, unsafe_allow_html=True)


# Page nav links, in order. Labels are the single source of truth across pages.
_NAV = [
    ("pages/0_Scanner.py", "Scanner"),
    ("pages/1_Trade_Setup.py", "Trade Setup"),
    ("pages/2_Alerts.py", "Alerts"),
    ("pages/2_Position_Size_Calculator.py", "Calculator"),
    ("pages/3_Trade_Analytics.py", "Analytics"),
]


def render_nav(container=None):
    """Render the horizontal page-nav links into `container` (or a new topnav)."""
    nav = container or st.container(key="topnav")
    for path, label in _NAV:
        nav.page_link(path, label=label)
    return nav


def brand_html(word1, word2, sub=""):
    """The brand block markup: logo + two-tone wordmark + optional subtitle.
    Exposed so a page can place it alongside other elements (e.g. a Run button)."""
    logo = logo_data_uri()
    return (
        '<div class="orion-brand">'
        + (f'<img src="{logo}" alt="logo">' if logo else "")
        + f'<div class="orion-logo">{word1}'
        + (f' <span class="accent">{word2}</span>' if word2 else "")
        + (f'<span class="sub">{sub}</span>' if sub else "")
        + "</div></div>"
    )


def render_header(word1, word2, sub="", brand=True):
    """Top chrome for a secondary page: nav + clocks row, then the brand block.
    Reproduces app.py's header layout (st.columns([1.5, 2.1]) with the clocks on
    the right) so the brand aligns across pages. Call once at the page top. Pass
    brand=False to render only the nav + clocks (e.g. when the page wants to place
    the brand alongside an action button itself)."""
    st.markdown(_HEADER_CSS, unsafe_allow_html=True)

    navc, clockc = st.columns([1.5, 2.1])
    with navc:
        render_nav(st.container(key="topnav"))
    with clockc:
        render_clocks()

    if brand:
        brand_row = st.container(key="brandrow")
        brand_row.markdown(brand_html(word1, word2, sub), unsafe_allow_html=True)
