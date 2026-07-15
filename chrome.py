"""Shared page chrome — the nav + world-clocks bar + brand block.

Used by every page (Scanner in pages/0_Scanner.py and the secondary pages) so the
header is identical and aligned across the app. Importing this module has NO
Streamlit side effects, so it is safe to import from any page; it is also the
single source of truth for the live clocks (app.py imports them from here).
"""
from __future__ import annotations

import base64
import os
import sys

import streamlit as st
import streamlit.components.v1 as components

_ROOT = os.path.dirname(os.path.abspath(__file__))
_WATCHLIST_ENGINE_DIR = os.path.join(_ROOT, "watchlist_engine")
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _WATCHLIST_ENGINE_DIR]

import scanner

LOGO_PATH = os.path.join(_ROOT, "assets", "logo.png")
ASSETS_DIR = os.path.join(_ROOT, "assets")


def build_sha():
    """Return the deployed Git revision for staging/production verification."""
    raw = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "local")
    return "".join(ch for ch in raw if ch.isalnum())[:40] or "local"


def logo_data_uri():
    try:
        with open(LOGO_PATH, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


def _inline_icon(filename):
    try:
        with open(os.path.join(ASSETS_DIR, filename), "r") as f:
            svg = f.read().strip()
    except OSError:
        return ""
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].strip()
    while svg.startswith("<!--"):
        svg = svg.split("-->", 1)[1].strip()
    svg = svg.replace('<?xml version="1.0" encoding="iso-8859-1"?>', "")
    svg = svg.replace('fill="none"', "")
    svg = svg.replace("<path ", '<path fill="currentColor" ')
    svg = svg.replace("<svg ", '<svg aria-hidden="true" ')
    return svg


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
    border-color:rgba(76,141,255,.56); background:rgba(76,141,255,.12); }
  .name { color:#c5ccd4; font-size:10.5px; font-weight:800; letter-spacing:.04em;
    text-transform:uppercase; white-space:nowrap; }
  .when { color:#848e9c; font-size:9px; font-weight:700; white-space:nowrap;
    font-variant-numeric:tabular-nums; text-transform:uppercase; }
  .label { color:#6b747e; font-size:8px; font-weight:700; letter-spacing:.13em;
    text-transform:uppercase; margin-top:2px; line-height:1; text-align:center; }
  .value { font-size:15.5px; font-weight:800; margin-top:2px; line-height:1.15;
    font-variant-numeric:tabular-nums; white-space:nowrap; text-align:center; }
  .fourh .name { font-size:9.5px; text-align:center; display:block; }
  .fourh .value { color:#4c8dff; font-size:17px; }
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
        + '<div class="label">Closes in</div><div class="value">'+fmt(secs)+'</div></div>';
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


def _server_is_mobile() -> bool:
    try:
        headers = getattr(st.context, "headers", {}) or {}
        user_agent = str(headers.get("User-Agent") or headers.get("user-agent") or "").lower()
    except Exception:
        return False
    return any(marker in user_agent for marker in ("iphone", "ipod", "android", "mobile", "windows phone"))


# CSS subset of the Scanner chrome shared by the secondary pages so their header
# matches exactly (hide default chrome, nav row, brand).
_HEADER_CSS = """<style>
  html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{background:#0a0711!important;}
  body{overscroll-behavior-y:none;}
  [data-testid="stAppViewContainer"]{background:
    radial-gradient(1100px 720px at 8% 12%, rgba(124,58,237,.22), transparent 60%),
    radial-gradient(1000px 800px at 92% 6%, rgba(168,85,247,.16), transparent 55%),
    radial-gradient(1200px 900px at 78% 92%, rgba(99,57,213,.20), transparent 60%),
    radial-gradient(900px 720px at 18% 86%, rgba(147,51,234,.14), transparent 55%),
    #0a0711!important;background-attachment:fixed!important;}
  [data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:transparent!important;}
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
  .mobile-topbar{display:none;}
  .mobile-footer-nav{display:none;}
  @media (max-width: 700px), (max-device-width: 700px), (hover: none) and (pointer: coarse){
    .block-container{padding:0.85rem 0.8rem 1rem!important;}
    .st-key-topnav,[data-testid="stHorizontalBlock"]:has(.st-key-topnav){display:none!important;}
    [data-testid="stHorizontalBlock"]:has(.st-key-topnav) iframe{display:none!important;}
    .mobile-topbar{display:flex;align-items:center;margin:-2px 0 0;padding:0 2px;color:#f2f4f8;}
    .mobile-topbar .orion-brand{gap:.55rem;}
    .mobile-topbar .orion-brand img{width:40px;height:40px;}
    .mobile-topbar .orion-logo{font-size:1.34rem;font-weight:820;letter-spacing:.035em;line-height:1;color:#e6e8eb;}
    .mobile-topbar .orion-logo .accent{color:#4c8dff;}
    .mobile-topbar .orion-logo .sub{display:none;}
    .mobile-footer-nav{position:fixed;left:0;right:0;bottom:0;z-index:2147483647;display:flex;overflow-x:auto;overflow-y:hidden;
      gap:0;padding:7px 8px calc(7px + env(safe-area-inset-bottom));background:rgba(7,11,18,.88);
      border-top:1px solid rgba(230,232,235,.12);backdrop-filter:blur(14px);box-shadow:0 -12px 34px rgba(0,0,0,.35);
      pointer-events:auto!important;transform:translateZ(0);isolation:isolate;scrollbar-width:none;-webkit-overflow-scrolling:touch;}
    .mobile-footer-nav::-webkit-scrollbar{display:none;}
    .mobile-footer-nav a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;height:50px;border-radius:10px;
      border:0;background:transparent;color:#7f8996!important;
      text-decoration:none!important;font-size:.58rem;font-weight:500;letter-spacing:0;line-height:1.05;flex:0 0 20%;min-width:68px;
      pointer-events:auto!important;touch-action:manipulation;-webkit-tap-highlight-color:transparent;user-select:none;-webkit-user-select:none;}
    .mobile-footer-nav a *{pointer-events:none!important;}
    .mobile-footer-nav svg{width:17px;height:17px;display:block;fill:currentColor;stroke:none;}
    .mobile-footer-nav a.active{color:#4c8dff!important;background:transparent;text-shadow:0 0 14px rgba(76,141,255,.38);}
    .mobile-footer-nav a.active svg{filter:drop-shadow(0 0 7px rgba(76,141,255,.42));}
    .block-container{padding-bottom:calc(5.75rem + env(safe-area-inset-bottom))!important;}
  }
  html.force-mobile .block-container{padding:0.85rem 0.8rem calc(5.75rem + env(safe-area-inset-bottom))!important;}
  html.force-mobile .st-key-topnav,
  html.force-mobile .st-key-desktop_header_row,
  html.force-mobile .st-key-desktop_header_row *,
  html.force-mobile [data-testid="stHorizontalBlock"]:has(.st-key-topnav),
  html.force-mobile [data-testid="stHorizontalBlock"]:has(.st-key-topnav) iframe{display:none!important;}
  html.force-mobile .st-key-topnav *,
  html.force-mobile .st-key-desktop_clocks,
  html.force-mobile .st-key-desktop_clocks *,
  html.force-mobile .desktop-topnav,
  html.force-mobile .desktop-clocks{display:none!important;}
  html.force-mobile .st-key-brandrow [data-testid="stElementContainer"]:has(.orion-brand),
  html.force-mobile .st-key-brandrow [data-testid="stMarkdown"]:has(.orion-brand),
  html.force-mobile .st-key-brandrow [data-testid="stMarkdownContainer"]:has(.orion-brand){display:none!important;}
  html.force-mobile .mobile-topbar{display:flex!important;align-items:center;margin:-2px 0 0;padding:0 2px;color:#f2f4f8;}
  html.force-mobile .mobile-topbar .orion-brand{gap:.55rem;}
  html.force-mobile .mobile-topbar .orion-brand img{width:40px;height:40px;}
  html.force-mobile .mobile-topbar .orion-logo{font-size:1.34rem;font-weight:820;letter-spacing:.035em;line-height:1;color:#e6e8eb;}
  html.force-mobile .mobile-topbar .orion-logo .accent{color:#4c8dff;}
  html.force-mobile .mobile-topbar .orion-logo .sub{display:none;}
  html.force-mobile .mobile-footer-nav{position:fixed;left:0;right:0;bottom:0;z-index:2147483647;display:flex!important;overflow-x:auto!important;overflow-y:hidden!important;
    gap:0;padding:7px 8px calc(7px + env(safe-area-inset-bottom));background:rgba(7,11,18,.88);
    border-top:1px solid rgba(230,232,235,.12);backdrop-filter:blur(14px);box-shadow:0 -12px 34px rgba(0,0,0,.35);
    pointer-events:auto!important;transform:translateZ(0);isolation:isolate;scrollbar-width:none;-webkit-overflow-scrolling:touch;}
  html.force-mobile .mobile-footer-nav::-webkit-scrollbar{display:none;}
  html.force-mobile .mobile-footer-nav a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;height:50px;border-radius:10px;
    border:0;background:transparent;color:#7f8996!important;text-decoration:none!important;font-size:.58rem;font-weight:500;letter-spacing:0;line-height:1.05;flex:0 0 20%;min-width:68px;
    pointer-events:auto!important;touch-action:manipulation;-webkit-tap-highlight-color:transparent;user-select:none;-webkit-user-select:none;cursor:pointer;}
  html.force-mobile .mobile-footer-nav a *{pointer-events:none!important;}
  html.force-mobile .mobile-footer-nav svg{width:17px;height:17px;display:block;fill:currentColor;stroke:none;}
  html.force-mobile .mobile-footer-nav a.active{color:#4c8dff!important;background:transparent;text-shadow:0 0 14px rgba(76,141,255,.38);}
  html.force-mobile .mobile-footer-nav a.active svg{filter:drop-shadow(0 0 7px rgba(76,141,255,.42));}
</style>"""

_MOBILE_DETECTOR_HTML = """
<!doctype html><html><body><script>
(function(){
  function mark(){
    try{
      var doc = window.parent.document;
      var w = Math.min(
        window.parent.innerWidth || 9999,
        doc.documentElement.clientWidth || 9999,
        window.parent.visualViewport ? window.parent.visualViewport.width : 9999
      );
      var sw = Math.min(
        window.parent.screen ? window.parent.screen.width : 9999,
        window.parent.screen ? window.parent.screen.availWidth : 9999
      );
      var ua = window.parent.navigator.userAgent || "";
      var touch = (window.parent.navigator.maxTouchPoints || 0) > 0;
      var phoneUA = /iPhone|iPod|Android.*Mobile|Mobile Safari/i.test(ua);
      var mobile = w <= 760 || sw <= 760 || (touch && phoneUA);
      doc.documentElement.classList.toggle("force-mobile", mobile);
    }catch(e){}
  }
  mark();
  window.parent.addEventListener("resize", mark, {passive:true});
  window.parent.addEventListener("orientationchange", mark, {passive:true});
})();
</script></body></html>
"""

# Ambient purple gradient behind page content — shared across all pages so the
# look is consistent. Fixed attachment so it reads as soft ambient lighting.
_PAGE_BG_CSS = """<style>
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{background:#0a0711!important;}
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
    ("pages/7_Boys_Log.py", "Log"),
    ("pages/0_Scanner.py", "Scanner"),
    ("pages/1_Trade_Setup.py", "Trade Setup"),
    ("pages/4_Live_Trades.py", "Live Trades"),
    ("pages/5_Tracker.py", "Tracking"),
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
    components.html(_MOBILE_DETECTOR_HTML, height=0)
    st.markdown(_mobile_nav_html(word1, word2), unsafe_allow_html=True)
    st.markdown(_mobile_footer_html(word1, word2), unsafe_allow_html=True)

    with st.container(key="desktop_header_row"):
        navc, clockc = st.columns([1.5, 2.1])
        with navc:
            render_nav(st.container(key="topnav"))
        with clockc:
            with st.container(key="desktop_clocks"):
                if not _server_is_mobile():
                    render_clocks()

    if brand:
        brand_row = st.container(key="brandrow")
        brand_row.markdown(brand_html(word1, word2, sub), unsafe_allow_html=True)


def _mobile_nav_html(word1, word2):
    return f'<div class="mobile-topbar" data-igby-build="{build_sha()}">{brand_html(word1, word2)}</div>'


def _mobile_footer_html(word1, word2):
    current = f"{word1} {word2}".strip().lower()
    log_active = "active" if "daily log" in current or "boys log" in current else ""
    setup_active = "active" if "trade setup" in current else ""
    trades_active = "active" if "live trades" in current else ""
    tracking_active = "active" if "tracker" in current or "tracking" in current else ""
    log_icon = _inline_icon("baby-check.svg")
    trade_icon = _inline_icon("target.svg")
    trades_icon = _inline_icon("alert-play.svg")
    tracking_icon = _inline_icon("data-analytics.svg")
    base = "https://app.igbycentral.com"
    def item(active, path, icon, label):
        href = f"{base}{path}"
        nav = f"window.location.href='{href}';return false;"
        return (
            f'<a class="{active}" href="{href}" target="_self" '
            f'onclick="{nav}" ontouchend="{nav}" aria-label="{label}">'
            f'{icon}<span>{label}</span></a>'
        )
    return (
        '<nav class="mobile-footer-nav" aria-label="Mobile navigation">'
        + item(log_active, "/Boys_Log", log_icon, "Log")
        + item(setup_active, "/Trade_Setup", trade_icon, "Setup")
        + item(trades_active, "/Live_Trades", trades_icon, "Trades")
        + item(tracking_active, "/Tracker", tracking_icon, "Tracking")
        + '</nav>'
    )
