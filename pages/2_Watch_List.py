"""Watch List - ranked trade setups from the scanner engine."""
from __future__ import annotations

import base64
import html
import os
import time
from urllib.parse import urlencode

import requests
import streamlit as st

import chrome
import icons


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
UP_TREND_PATH = os.path.join(ASSETS_DIR, "trend.svg")
DOWN_TREND_PATH = os.path.join(ASSETS_DIR, "trend-2.svg")
DOWN_ARROW_SVG = '<svg class="down-arrow-svg" viewBox="0 0 128 128"><path fill="currentColor" d="M64 88 21 45l6-6 37 37 37-37 6 6z"/></svg>'
HERMES_DASHBOARD_URL = os.getenv(
    "HERMES_DASHBOARD_URL",
    "https://scanner-api-production-4411.up.railway.app/api/dashboard",
)


def _asset_data_uri(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


UP_TREND_URI = _asset_data_uri(UP_TREND_PATH)
DOWN_TREND_URI = _asset_data_uri(DOWN_TREND_PATH)


st.set_page_config(page_title="Watch List", page_icon="📋", layout="wide")
chrome.render_header("WATCH", "LIST", brand=False)


st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important;}
.st-key-watch_shell{max-width:1180px;margin:0 auto;}
.st-key-watch_header_row{margin-top:-76px!important;margin-bottom:40px!important;}
.st-key-watch_controls{display:flex!important;flex-direction:row!important;align-items:center!important;justify-content:flex-end!important;gap:0!important;margin:0!important;
  width:100%!important;}
.st-key-watch_controls > [data-testid="stElementContainer"]{width:auto!important;min-width:0!important;}
.st-key-watch_controls > [data-testid="stElementContainer"]{flex:0 0 86px!important;}
.st-key-watch_refresh button{width:86px!important;height:34px!important;min-height:34px!important;border:1px solid #4c6fff!important;
  border-radius:999px!important;background:rgba(76,111,255,.14)!important;color:#587dff!important;
  font-size:.84rem!important;font-weight:500!important;letter-spacing:0!important;text-transform:uppercase!important;
  box-shadow:none!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:8px!important;}
.st-key-watch_refresh button:hover{border-color:#4c8dff!important;background:rgba(76,141,255,.18)!important;color:#6f95ff!important;
  box-shadow:0 0 16px rgba(76,141,255,.16)!important;}
.st-key-watch_refresh button:active{transform:translateY(1px) scale(.99);background:rgba(76,111,255,.22)!important;
  box-shadow:inset 0 0 0 1px rgba(76,141,255,.7),0 0 18px rgba(76,141,255,.22)!important;}
.st-key-watch_shell [data-baseweb="tab"] p{font-size:16px!important;}
.watch-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid rgba(86,100,138,.36);
  border-radius:11px;background:rgba(8,12,25,.72);overflow:hidden;margin-bottom:16px;}
.watch-metric{padding:14px 18px;border-right:1px solid rgba(86,100,138,.25);border-bottom:1px solid rgba(86,100,138,.25);min-width:0;}
.watch-metric:nth-child(4n){border-right:none;}
.watch-metric:nth-last-child(-n+4){border-bottom:none;}
.watch-metric .cap{font-size:.64rem;color:#9aa3b3;text-transform:uppercase;letter-spacing:.07em;font-weight:800;white-space:nowrap;}
.watch-metric .val{font-size:1.05rem;color:#f2f4f8;margin-top:7px;font-weight:780;font-variant-numeric:tabular-nums;}
.watch-metric .val.green{color:#21df77}.watch-metric .val.yellow{color:#f6c940}.watch-metric .val.red{color:#ff444d}
.watch-metric .fresh{display:flex;align-items:center;gap:7px;justify-content:flex-end;}
.fresh-dot{width:8px;height:8px;border-radius:999px;background:#20db75;box-shadow:0 0 9px rgba(32,219,117,.7);}
.watch-head,.watch-row{display:grid;grid-template-columns:minmax(210px,1.5fr) 46px 62px 96px 72px 92px 128px 24px;gap:12px;
  align-items:center;}
.watch-head{padding:0 22px 9px;color:#adb5c4;font-size:.67rem;text-transform:uppercase;letter-spacing:.055em;font-weight:850;}
.watch-list{border:1px solid rgba(86,100,138,.3);border-radius:0;overflow:hidden;background:rgba(7,11,22,.62);}
.watch-item{border-bottom:1px solid rgba(86,100,138,.22);border-radius:0;}
.watch-item:last-child{border-bottom:none;}
.watch-item:first-child,.watch-item:first-child .watch-row,.watch-row{border-radius:0!important;}
.watch-item summary{list-style:none;cursor:pointer;}
.watch-item summary::-webkit-details-marker{display:none;}
.watch-row{padding:13px 22px;min-height:76px;}
.watch-item[open]{background:linear-gradient(90deg,rgba(112,99,255,.14),rgba(7,11,22,.52) 44%,rgba(7,11,22,.78));
  box-shadow:inset 0 0 0 1px rgba(112,99,255,.72);}
.watch-item[open] .watch-row{background:transparent;box-shadow:none;}
.watch-row.featured{border:none;border-radius:0;margin:0;background:transparent;box-shadow:none;}
.coin-preview{display:flex;align-items:center;gap:12px;min-width:0;}
.coin-text{min-width:0;}
.rank-badge{width:34px;height:34px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;padding:0;
  border:1px solid rgba(160,168,184,.36);background:#252a3c;color:#f3f5fb;font-size:.52rem;letter-spacing:.02em;
  font-weight:900;font-variant-numeric:tabular-nums;position:relative;white-space:nowrap;overflow:hidden;}
.rank-badge.coin-symbol{background:rgba(21,25,39,.94);border-color:rgba(151,93,255,.42);box-shadow:0 0 12px rgba(151,93,255,.18);}
.rank-badge img{width:100%;height:100%;object-fit:cover;display:block;}
.rank-badge.no-logo{background:linear-gradient(135deg,rgba(151,93,255,.16),rgba(21,25,39,.94));padding:0 3px;}
.rank-badge.top{background:radial-gradient(circle at 35% 30%,rgba(246,212,72,.24),rgba(21,25,39,.94) 62%);
  border-color:#f6d448;color:#ffe66b;box-shadow:0 0 12px rgba(246,212,72,.25);}
.coin-line{display:flex;align-items:center;gap:8px;min-width:0;}
.coin-main{font-size:1.02rem;font-weight:850;color:#f4f6fb;line-height:1.15;white-space:nowrap;}
.coin-price{font-size:.82rem;font-weight:760;color:#7f899f;font-variant-numeric:tabular-nums;white-space:nowrap;}
.coin-sub{font-size:.76rem;color:#aeb6c4;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.mobile-badges{display:none;}
.dir-pill,.grade-pill,.maturity-pill,.score-pill{display:inline-flex;align-items:center;justify-content:center;border:1px solid currentColor;border-radius:6px;
  padding:6px 10px;font-size:.72rem;font-weight:900;text-transform:uppercase;letter-spacing:.035em;width:max-content;}
.dir-pill.long{color:#21df77;background:rgba(33,223,119,.08)}.dir-pill.short{color:#ff4f5d;background:rgba(255,79,93,.08)}
.dir-box{width:34px;height:30px;border-radius:7px;display:inline-flex;align-items:center;justify-content:center;border:1px solid currentColor;}
.dir-box.long{color:#21df77;background:rgba(33,223,119,.08)}.dir-box.short{color:#ff4f5d;background:rgba(255,79,93,.08)}
.dir-icon{width:17px;height:17px;display:block;background:currentColor;}
.dir-box.long .dir-icon{-webkit-mask:url('__UP_TREND_URI__') center/contain no-repeat;mask:url('__UP_TREND_URI__') center/contain no-repeat;}
.dir-box.short .dir-icon{-webkit-mask:url('__DOWN_TREND_URI__') center/contain no-repeat;mask:url('__DOWN_TREND_URI__') center/contain no-repeat;}
.grade-pill{min-width:42px;color:#21df77;background:rgba(33,223,119,.07)}.grade-pill.grade-b{color:#f6c940;background:rgba(246,201,64,.07)}
.grade-pill.grade-c{color:#ff4f5d;background:rgba(255,79,93,.07)}
.score-pill{color:#b9c2d5;background:rgba(126,137,159,.12);border-color:rgba(126,137,159,.32);min-width:52px;}
.ready-pill{color:#12c99b;background:rgba(18,201,155,.10);border-color:rgba(18,201,155,.42);}
.score-wrap{min-width:0}.score-num{font-size:1.22rem;font-weight:860;color:#f6f8fd;font-variant-numeric:tabular-nums;}
.score-bar{height:4px;width:min(118px,100%);border-radius:999px;background:#20283a;overflow:hidden;margin-top:8px;}
.score-bar i{display:block;height:100%;border-radius:999px;background:#21df77;width:var(--w);}
.maturity{display:flex;align-items:center;gap:8px;color:#e6e9f1;font-size:.82rem;}
.maturity-dot{width:10px;height:10px;border-radius:999px;background:#3d8cff;box-shadow:0 0 10px rgba(61,140,255,.45);}
.maturity.ready .maturity-dot{background:#21df77}.maturity.forming .maturity-dot{background:#f6c940}
.rr,.entry{font-size:.86rem;color:#f0f2f7;font-variant-numeric:tabular-nums;white-space:nowrap;}
.chev{display:flex;align-items:center;justify-content:center;color:#7f899f;transition:color .16s ease;}
.chev .down-arrow-svg{width:13px;height:13px;display:block;transition:transform .16s ease;}
.watch-item[open] .chev{color:#bd8cff;}
.watch-item[open] .chev .down-arrow-svg{transform:rotate(180deg);}
.feature-card{border:1px solid rgba(151,93,255,.72);border-radius:11px;margin:10px 0;background:
  radial-gradient(circle at 0 10%,rgba(125,59,232,.22),transparent 34%),rgba(9,12,24,.9);
  padding:20px 20px 16px;box-shadow:0 0 28px rgba(125,59,232,.16);}
.feature-top{display:grid;grid-template-columns:1.5fr minmax(130px,.6fr) minmax(150px,.7fr);gap:20px;align-items:center;margin-bottom:18px;}
.selected-title{display:flex;align-items:center;gap:13px;min-width:0;}
.coin-orb{width:56px;height:56px;border-radius:999px;background:rgba(33,223,119,.12);border:1px solid rgba(33,223,119,.5);
  color:#21df77;display:flex;align-items:center;justify-content:center;font-size:1.55rem;font-weight:900;}
.sel-coin{font-size:1.78rem;font-weight:900;color:#fff;line-height:1;letter-spacing:.01em;}
.sel-pattern{font-size:.92rem;color:#d7dbe6;margin-top:8px;}
.sel-note{font-size:.78rem;color:#21df77;margin-top:8px;}
.feature-score{border-left:1px solid rgba(86,100,138,.32);padding-left:24px;}
.feature-score .cap{color:#a5adbd;text-transform:uppercase;letter-spacing:.06em;font-size:.66rem;font-weight:850;}
.feature-score .big{font-size:3.2rem;line-height:.95;color:#21df77;font-weight:900;margin-top:8px;font-variant-numeric:tabular-nums;}
.feature-score .big span{font-size:1.05rem;color:#a5adbd;font-weight:650;}
.feature-actions{display:flex;flex-direction:column;gap:10px;}
.ghost-action{height:44px;border:1px solid rgba(151,93,255,.4);border-radius:8px;display:flex;align-items:center;justify-content:center;
  color:#eadfff;background:rgba(151,93,255,.06);font-size:.86rem;}
.trade-plan{border:none;border-radius:0;padding:0;margin-bottom:18px;}
.drawer-plan{border-top:1px solid rgba(86,100,138,.32);padding-top:12px;margin-bottom:22px;}
.plan-row{display:flex;align-items:baseline;justify-content:space-between;gap:16px;padding:3px 0;font-size:1.02rem;}
.plan-label{color:#7f899f;min-width:112px;}.plan-value{color:#eef2fb;font-size:1.02rem;font-weight:850;text-align:right;font-variant-numeric:tabular-nums;}
.plan-value.entry{color:#2cd8ad}.plan-value.stop{color:#ff4f5d}.plan-value.tp,.plan-value.tp small{color:#587dff}
.section-label{font-size:.78rem;font-weight:880;color:#f3f5fb;text-transform:uppercase;letter-spacing:.04em;margin-bottom:12px;}
.evidence-gap-heading{margin-top:14px;}
.plan-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:0;border:1px solid rgba(86,100,138,.25);border-radius:8px;overflow:hidden;}
.plan-item{padding:14px 14px;text-align:center;border-right:1px solid rgba(86,100,138,.22);min-width:0;}
.plan-item:last-child{border-right:none}.plan-item .cap{font-size:.64rem;color:#a5adbd;text-transform:uppercase;letter-spacing:.06em;font-weight:850;}
.plan-item .val{font-size:1.02rem;color:#f2f4f8;font-weight:820;margin-top:9px;font-variant-numeric:tabular-nums;word-break:break-word;}
.plan-item .val.green{color:#21df77}.plan-item .val.red{color:#ff4f5d}.plan-item .val.blue{color:#3d8cff}
.deep-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:13px;margin-bottom:16px;}
.deep-card{border:1px solid rgba(86,100,138,.38);border-radius:9px;padding:15px 16px;background:rgba(13,17,33,.58);min-width:0;}
.deep-list{display:flex;flex-direction:column;gap:12px;color:#e5e8f0;font-size:.84rem;line-height:1.3;}
.deep-line{display:flex;align-items:flex-start;gap:10px;min-width:0;}
.check{width:20px;height:20px;border-radius:999px;border:1px solid #21df77;color:#21df77;display:inline-flex;align-items:center;justify-content:center;
  flex:0 0 auto;font-size:.76rem;line-height:1;}
.bubble{width:22px;height:22px;border-radius:999px;background:#6543bf;color:#fff;display:inline-flex;align-items:center;justify-content:center;
  flex:0 0 auto;font-size:.62rem;font-weight:900;}
.deep-more{height:42px;margin-top:15px;border:1px solid rgba(151,93,255,.35);border-radius:8px;display:flex;align-items:center;justify-content:center;
  color:#bd8cff;background:rgba(151,93,255,.06);font-size:.82rem;}
.perf-strip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid rgba(86,100,138,.34);border-radius:9px;overflow:hidden;}
.perf{padding:13px 15px;border-right:1px solid rgba(86,100,138,.22);min-width:0}.perf:last-child{border-right:none}
.perf .cap{font-size:.62rem;color:#a5adbd;text-transform:uppercase;letter-spacing:.06em;font-weight:850}.perf .val{font-size:1rem;color:#f2f4f8;margin-top:7px;font-weight:800}
.watch-detail-wrap{padding:0 22px 18px;background:transparent;}
.watch-detail-wrap .feature-card{margin:0;border:none;background:transparent;box-shadow:none;border-radius:0;padding:0;}
.watch-detail-wrap .feature-top{display:none;}
.ctx-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:18px;}
.ctx-card{border:1px solid rgba(86,100,138,.34);border-radius:8px;background:rgba(8,11,22,.5);padding:9px 11px;min-width:0;}
.ctx-card.wide{grid-column:1/-1}.ctx-label{font-size:.64rem;color:#7f899f;letter-spacing:.06em;text-transform:uppercase;font-weight:850;}
.ctx-value{font-size:1rem;color:#eef2fb;font-weight:850;margin-top:5px;font-variant-numeric:tabular-nums;word-break:break-word;}
.ctx-value.pos,.bd-score.pass{color:#2cd8ad}.ctx-value.neg,.bd-score.fail{color:#ff4f5d}
.order-signal{display:inline-flex;align-items:center;gap:6px;font-weight:900;}
.order-signal::before{content:"";width:8px;height:8px;border-radius:999px;background:#7f899f;box-shadow:0 0 8px rgba(127,137,159,.45);}
.order-signal.bullish{color:#2cd8ad}.order-signal.bullish::before{background:#2cd8ad;box-shadow:0 0 9px rgba(44,216,173,.6);}
.order-signal.bearish{color:#ff4f5d}.order-signal.bearish::before{background:#ff4f5d;box-shadow:0 0 9px rgba(255,79,93,.6);}
.depth-title{font-size:.78rem;font-weight:900;margin:11px 0 6px}.depth-title.ask{color:#ff4f5d}.depth-title.bid{color:#12c99b}
.depth-line{display:grid;grid-template-columns:76px minmax(0,1fr) 42px;gap:7px;align-items:center;margin:3px 0;color:#7f899f;font-size:.7rem;font-variant-numeric:tabular-nums;}
.depth-price small{display:block;font-size:.58rem;color:#5f687d;line-height:1.05;}
.depth-pct{text-align:right;color:#aeb6c4;font-weight:850;}
.depth-track{height:9px;border-radius:4px;background:#1a1a2e;overflow:hidden}.depth-fill{display:block;height:100%;border-radius:4px;opacity:.88}.depth-fill.ask{background:#c7445b}.depth-fill.bid{background:#12a48a}
.bd-row{display:grid;grid-template-columns:28px 1fr auto;gap:8px;align-items:baseline;margin:8px 0 2px;}
.bd-icon{font-size:1rem}.bd-label{font-size:.92rem;color:#7f899f}.bd-score{font-size:.84rem;font-weight:900;font-variant-numeric:tabular-nums;}
.bd-text{margin-left:36px;color:#7f899f;font-size:.8rem;line-height:1.22;padding:1px 0}.bd-text.pass{color:#56cfb2}.bd-text.fail{color:#7f899f}
.evidence-list{list-style:none;margin:0;padding:0;border-top:1px solid rgba(86,100,138,.32);padding-top:8px;}
.evidence-list li{font-size:.84rem;line-height:1.22;padding:2px 0;color:#56cfb2}.evidence-list li.bad{color:#ff4f5d}.evidence-list li.warn{color:#f6c940}
.hermes-meta{border:1px solid rgba(139,92,246,.36);border-radius:10px;background:rgba(13,17,33,.62);padding:14px 16px;margin-bottom:12px;color:#aab2bd;font-size:.82rem;line-height:1.38;}
.hermes-meta b{display:block;color:#f1f4fb;font-size:.92rem;margin-bottom:4px;}
.hermes-table{border:1px solid rgba(86,100,138,.3);background:rgba(7,11,22,.62);overflow:hidden;}
.hermes-head,.hermes-row{display:grid;gap:10px;align-items:center;}
.hermes-head{padding:0 18px 9px;color:#adb5c4;font-size:.66rem;text-transform:uppercase;letter-spacing:.055em;font-weight:850;}
.hermes-row{padding:13px 18px;min-height:74px;border-top:1px solid rgba(86,100,138,.22);}
.hermes-item:first-child .hermes-row{border-top:none;}
.hermes-item summary{list-style:none;cursor:pointer;}
.hermes-item summary::-webkit-details-marker{display:none;}
.hermes-item[open]{background:linear-gradient(90deg,rgba(112,99,255,.14),rgba(7,11,22,.52) 44%,rgba(7,11,22,.78));box-shadow:inset 0 0 0 1px rgba(112,99,255,.72);}
.hermes-cell{min-width:0;color:#e8ecf5;font-size:.84rem;font-variant-numeric:tabular-nums;}
.hermes-muted{display:block;color:#7f899f;font-size:.72rem;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.hermes-symbol{display:flex;align-items:center;gap:11px;min-width:0;}
.hermes-symbol b{font-size:.98rem;color:#f7f9fd;white-space:nowrap;}
.hermes-rank{width:32px;height:32px;border-radius:999px;border:1px solid rgba(151,93,255,.42);background:rgba(21,25,39,.94);display:flex;align-items:center;justify-content:center;color:#f3f5fb;font-size:.68rem;font-weight:900;flex:0 0 32px;}
.hermes-logo{width:32px;height:32px;border-radius:999px;border:1px solid rgba(151,93,255,.42);background:rgba(21,25,39,.94);box-shadow:0 0 12px rgba(151,93,255,.18);display:flex;align-items:center;justify-content:center;overflow:hidden;flex:0 0 32px;color:#f3f5fb;font-size:.58rem;font-weight:900;}
.hermes-logo img{width:100%;height:100%;object-fit:cover;display:block;}
.hermes-score{font-size:1.1rem;font-weight:900;color:#21df77;}
.hermes-score.neg{color:#ff4f5d}.hermes-score.warn{color:#f6c940}
.hermes-pill{display:inline-flex;align-items:center;justify-content:center;border-radius:6px;border:1px solid rgba(126,137,159,.32);background:rgba(126,137,159,.12);color:#d8deea;padding:5px 8px;font-size:.7rem;font-weight:900;text-transform:uppercase;letter-spacing:.025em;white-space:nowrap;}
.hermes-pill.primary,.hermes-pill.hold_add{color:#21df77;border-color:rgba(33,223,119,.35);background:rgba(33,223,119,.08);}
.hermes-pill.watch,.hermes-pill.tighten{color:#f6c940;border-color:rgba(246,201,64,.35);background:rgba(246,201,64,.08);}
.hermes-pill.exit_now{color:#ff4f5d;border-color:rgba(255,79,93,.4);background:rgba(255,79,93,.08);}
.hermes-pill.hold{color:#3d8cff;border-color:rgba(61,140,255,.38);background:rgba(61,140,255,.08);}
.hermes-drawer{padding:0 18px 18px;}
.hermes-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0;}
.hermes-kv{border:1px solid rgba(86,100,138,.34);border-radius:8px;background:rgba(8,11,22,.5);padding:9px 11px;min-width:0;}
.hermes-kv span{display:block;color:#7f899f;text-transform:uppercase;letter-spacing:.06em;font-size:.6rem;font-weight:850;}
.hermes-kv b{display:block;color:#eef2fb;font-size:.96rem;margin-top:5px;font-variant-numeric:tabular-nums;word-break:break-word;}
.hermes-section{font-size:.72rem;font-weight:880;color:#f3f5fb;text-transform:uppercase;letter-spacing:.04em;margin:14px 0 9px;}
.hermes-chip-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;}
.hermes-chip{border:1px solid rgba(86,100,138,.34);border-radius:8px;background:rgba(8,11,22,.5);padding:10px;min-width:0;}
.hermes-chip span{display:block;color:#9aa3b3;font-size:.64rem;font-weight:850;letter-spacing:.04em;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.hermes-chip b{display:block;color:#f2f4f8;font-size:1rem;margin-top:7px;font-weight:900;}
.hermes-reasons{color:#aeb6c4;font-size:.8rem;line-height:1.35;margin-top:8px;}
.hermes-pre{white-space:pre-wrap;font-size:.75rem;line-height:1.35;color:#aeb6c4;border:1px solid rgba(86,100,138,.25);background:rgba(8,11,22,.42);border-radius:8px;padding:10px;margin-top:8px;}
.trade-plan-compact{border-top:1px solid rgba(123,110,214,.16);border-bottom:1px solid rgba(123,110,214,.16);padding:10px 0;margin:10px 0 12px;}
.trade-plan-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:baseline;min-height:26px;font-variant-numeric:tabular-nums;}
.trade-plan-label{color:#7f899f;font-size:15px;font-weight:500;line-height:1.15;}
.trade-plan-value{font-size:15px;font-weight:780;line-height:1.15;letter-spacing:.03em;}
.trade-plan-value.entry{color:#5d82ff}.trade-plan-value.stop{color:#ff5968}.trade-plan-value.target{color:#55d8b3}
.trade-plan-rr{color:#717a90;font-size:12px;font-weight:760;line-height:1.15;min-width:40px;text-align:right;}
.trade-plan-rr.blank{visibility:hidden;}
.score-breakdown{border:1px solid rgba(139,92,246,.34);border-radius:9px;background:linear-gradient(180deg,rgba(20,19,38,.82),rgba(12,10,23,.9));padding:14px 14px 2px;margin:12px 0 14px;}
.score-breakdown-head{position:relative;min-height:86px;padding-right:86px;border-bottom:1px solid rgba(123,110,214,.16);margin-bottom:8px;}
.score-breakdown-title{font-size:16px;font-weight:760;letter-spacing:.04em;text-transform:uppercase;color:#f3f5fb;line-height:1.1;}
.score-breakdown-summary{font-size:11px;font-weight:500;color:#d8deeb;line-height:1.35;margin-top:16px;max-width:245px;}
.score-breakdown-muted{font-size:11px;font-weight:450;color:#8f98ab;line-height:1.35;margin-top:4px;max-width:245px;}
.score-circle{position:absolute;right:4px;top:2px;width:70px;height:70px;border:1px solid rgba(143,152,171,.72);border-radius:999px;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.score-circle b{font-size:19px;font-weight:720;line-height:1;font-variant-numeric:tabular-nums;}
.score-circle span{font-size:11px;font-weight:650;color:#8f98ab;line-height:1.1;margin-top:3px;font-variant-numeric:tabular-nums;}
.score-circle.pass b,.score-line.pass .score-line-mark,.score-line.pass .score-line-label,.score-line.pass .score-line-score{color:#23d47d;}
.score-circle.partial b,.score-line.partial .score-line-mark,.score-line.partial .score-line-label,.score-line.partial .score-line-score{color:#e6aa36;}
.score-circle.fail b,.score-line.fail .score-line-mark,.score-line.fail .score-line-label,.score-line.fail .score-line-score{color:#ff5968;}
.score-line{display:grid;grid-template-columns:16px minmax(0,1fr) auto;gap:5px 6px;align-items:start;padding:9px 0;border-top:1px solid rgba(123,110,214,.16);}
.score-breakdown-head + .score-line{border-top:none;}
.score-line-mark{font-size:14px;font-weight:760;line-height:1.05;text-align:center;}
.score-line.partial .score-line-mark{font-size:16px;font-weight:700;transform:translateY(-1px);}
.score-line-label{font-size:12px;font-weight:680;line-height:1.08;}
.score-line-score{font-size:12px;font-weight:740;line-height:1.08;font-variant-numeric:tabular-nums;}
.score-line-detail{grid-column:2 / -1;color:#aeb7c8;font-size:10px;font-weight:450;line-height:1.22;margin-top:0;}
.score-line-action{display:none;}
.score-warning{border-top:1px solid rgba(123,110,214,.16);color:#ff7b86;font-size:11px;line-height:1.35;padding:11px 0 12px;}
.ai-interpretation{border:1px solid rgba(88,125,255,.34);border-radius:9px;background:linear-gradient(180deg,rgba(16,22,42,.82),rgba(9,12,24,.9));padding:13px 14px;margin:12px 0 14px;}
.ai-interpretation-title{font-size:15px;font-weight:760;letter-spacing:.04em;text-transform:uppercase;color:#f3f5fb;line-height:1.1;margin-bottom:8px;}
.ai-interpretation-compact{color:#d8deeb;font-size:12px;font-weight:520;line-height:1.38;margin-bottom:8px;}
.ai-interpretation details{border-top:1px solid rgba(88,125,255,.18);padding-top:9px;}
.ai-interpretation summary{list-style:none;cursor:pointer;color:#7f9cff;font-size:11px;font-weight:760;text-transform:uppercase;letter-spacing:.04em;}
.ai-interpretation summary::-webkit-details-marker{display:none;}
.ai-interpretation-expanded{color:#aeb7c8;font-size:11px;line-height:1.42;margin-top:9px;}
.hermes-pre-head,.hermes-pre-row{grid-template-columns:44px minmax(135px,1.1fr) 72px 84px 96px 118px minmax(150px,1fr) 24px;}
.hermes-v2-head,.hermes-v2-row,.hermes-v3-head,.hermes-v3-row{grid-template-columns:44px minmax(135px,1.05fr) 70px 86px 90px 78px 70px minmax(150px,1fr) 24px;}
.hermes-exit-head,.hermes-exit-row{grid-template-columns:44px minmax(145px,1.1fr) 76px 100px 84px 84px minmax(170px,1.2fr) 24px;}
.errbox{background:#13101e;border:1px solid rgba(246,70,93,.42);border-radius:10px;padding:16px;color:#f4c3c9;}
.scan-error-list{margin:10px 0 0;padding-left:18px;color:#f4c3c9;font-size:.82rem;line-height:1.35;}
.scan-error-more{margin-top:8px;color:#aeb6c4;font-size:.78rem;}
.empty{background:#13101e;border:1px solid rgba(139,92,246,.36);border-radius:10px;padding:26px 20px;color:#aab2bd;}
.empty b{display:block;color:#e6e8eb;font-size:1rem;margin-bottom:6px;}
@media(max-width:980px), (max-device-width:980px), (hover:none) and (pointer:coarse){
  .watch-metrics{grid-template-columns:repeat(4,minmax(0,1fr));border-radius:9px;margin-bottom:12px;}
  .watch-metric{min-width:0;padding:11px 10px}.watch-metric .cap{font-size:.55rem}.watch-metric .val{font-size:.9rem}
  .watch-head{display:none}.watch-list{border-radius:0}.watch-item[open]{background:linear-gradient(90deg,rgba(112,99,255,.14),rgba(7,11,22,.52) 44%,rgba(7,11,22,.78));box-shadow:inset 0 0 0 1px rgba(112,99,255,.72);}
  .watch-item[open] .watch-row{background:transparent;box-shadow:none;}
  .watch-row,.watch-row.featured{grid-template-columns:minmax(0,1fr) 32px 40px 60px 48px 16px;gap:5px;padding:12px 9px;min-height:82px;border-radius:0;margin:0;}
  .watch-row .rr,.watch-row .entry{display:none;}
  .watch-row.featured{border-left:none;border-right:none;}
  .star{display:none}.rank-badge{width:32px;height:32px;flex:0 0 32px;font-size:.48rem;border-radius:999px}.coin-preview{gap:10px;align-items:flex-start;min-width:0;}
  .coin-text{flex:1;min-width:0}.coin-line{display:flex;align-items:center;gap:7px;line-height:1.05;min-width:0}
  .coin-main{font-size:.95rem}.coin-price{display:none}
  .coin-sub{font-size:.69rem;margin-top:7px;max-width:none}
  .watch-row > .dir-box{width:30px;height:27px;justify-self:end}.watch-row > .dir-box .dir-icon{width:15px;height:15px}
  .watch-row > .grade-pill{min-width:34px;padding:5px 6px;font-size:.6rem;justify-self:end}.watch-row > .ready-pill{min-width:58px;padding:5px 6px;font-size:.56rem;justify-self:end}.watch-row > .score-pill{min-width:43px;padding:5px 6px;font-size:.59rem;justify-self:end}
  .watch-row > .chev{justify-self:end}
  .score-num{font-size:1rem}.score-bar{height:4px;width:68px;margin-top:6px}
  .hermes-head{display:none}.hermes-table{border-radius:0}
  .hermes-pre-row,.hermes-v2-row,.hermes-v3-row,.hermes-exit-row{grid-template-columns:minmax(0,1fr) 58px 64px 18px;gap:8px;padding:12px 10px;}
  .hermes-row .mobile-hide{display:none!important}
  .hermes-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
  .hermes-chip-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
  .hermes-drawer{padding:0 10px 14px;}
}
@media(max-width:700px), (max-device-width:700px), (hover:none) and (pointer:coarse){
  .st-key-watch_header_row{margin-top:-130px!important;margin-bottom:26px!important;}
  .st-key-watch_shell{margin-top:0;}
  .st-key-watch_controls{width:100%!important;margin:8px 0 8px!important;flex-direction:row!important;justify-content:flex-end!important;}
  .st-key-watch_refresh button{width:86px!important;height:34px!important;min-height:34px!important;border-radius:999px!important;}
  .feature-card{padding:0;margin:0;border-radius:0;}
  .feature-top{grid-template-columns:1fr;gap:13px;margin-bottom:13px}.selected-title{gap:11px}.coin-orb{width:48px;height:48px}
  .sel-coin{font-size:1.45rem}.sel-pattern{font-size:.84rem}.sel-note{font-size:.74rem}
  .feature-score{border-left:none;border-top:1px solid rgba(86,100,138,.28);padding:12px 0 0;display:flex;align-items:center;justify-content:space-between;}
  .feature-score .big{font-size:2.35rem;margin-top:0}.feature-actions{display:none}
  .watch-detail-wrap{padding:0 10px 14px}.trade-plan{padding:0;margin-bottom:12px}.section-label{font-size:.72rem;margin-bottom:10px}
  .plan-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.plan-item{border-right:1px solid rgba(86,100,138,.22);border-bottom:1px solid rgba(86,100,138,.22);padding:12px 9px}
  .plan-item:nth-child(2n){border-right:none}.plan-item:nth-last-child(-n+2){border-bottom:none}
  .deep-grid{grid-template-columns:1fr;gap:10px}.deep-card{padding:13px}.deep-list{font-size:.8rem;gap:10px}.deep-more{height:38px;margin-top:12px}
  .perf-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.perf{padding:11px 12px;border-bottom:1px solid rgba(86,100,138,.22)}
  .perf:nth-child(2n){border-right:none}.perf:nth-last-child(-n+2){border-bottom:none}
  .plan-row{font-size:1rem;padding:2px 0}.ctx-grid{gap:7px;margin-bottom:16px}.ctx-card{padding:8px 10px}.ctx-label{font-size:.6rem}.ctx-value{font-size:.96rem;margin-top:4px}
}
html.force-mobile .st-key-watch_header_row{margin-top:-130px!important;margin-bottom:26px!important;}
html.force-mobile .st-key-watch_shell{margin-top:0;}
html.force-mobile .st-key-watch_controls{width:100%!important;margin:8px 0 8px!important;flex-direction:row!important;justify-content:flex-end!important;}
html.force-mobile .st-key-watch_refresh button{width:86px!important;height:34px!important;min-height:34px!important;border-radius:999px!important;}
html.force-mobile .watch-metrics{grid-template-columns:repeat(4,minmax(0,1fr));border-radius:9px;margin-bottom:12px;}
html.force-mobile .watch-head,
html.force-mobile .hermes-head{display:none!important;}
html.force-mobile .watch-list,
html.force-mobile .hermes-table{border-radius:0;}
html.force-mobile .watch-row,
html.force-mobile .watch-row.featured{grid-template-columns:minmax(0,1fr) 32px 40px 60px 48px 16px;gap:5px;padding:12px 9px;min-height:82px;border-radius:0;margin:0;}
html.force-mobile .watch-row .rr,
html.force-mobile .watch-row .entry,
html.force-mobile .star,
html.force-mobile .watch-row .mobile-hide,
html.force-mobile .hermes-row .mobile-hide{display:none!important;}
html.force-mobile .hermes-pre-row,
html.force-mobile .hermes-v2-row,
html.force-mobile .hermes-v3-row,
html.force-mobile .hermes-exit-row{grid-template-columns:minmax(0,1fr) 58px 64px 18px;gap:8px;padding:12px 10px;}
html.force-mobile .hermes-grid,
html.force-mobile .hermes-chip-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
html.force-mobile .hermes-drawer{padding:0 10px 14px;}
    </style>""".replace("__UP_TREND_URI__", UP_TREND_URI).replace("__DOWN_TREND_URI__", DOWN_TREND_URI),
    unsafe_allow_html=True,
)


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _price(value) -> str:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    if v >= 100:
        return f"{v:,.2f}"
    if v >= 1:
        return f"{v:.4f}"
    return f"{v:.6f}"


def _pct(value) -> str:
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return "-"


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rr_float(value) -> float | None:
    if not value:
        return None
    try:
        return float(str(value).split(":")[-1].strip())
    except (TypeError, ValueError):
        return None


FILTER_OPTIONS = (
    "All Setups",
    "Ready",
    "Forming",
    "Nascent",
    "Long",
    "Short",
    "Grade A",
    "Grade B",
    "Grade C",
)


def _filter_rows(rows: list[dict], selected: str) -> list[dict]:
    selected = selected or "All Setups"
    if selected == "All Setups":
        return rows
    if selected in {"Ready", "Forming", "Nascent"}:
        target = selected.lower()
        return [row for row in rows if (row.get("maturity") or "").lower() == target]
    if selected in {"Long", "Short"}:
        target = selected.lower()
        return [row for row in rows if (row.get("direction") or "").lower() == target]
    if selected.startswith("Grade "):
        target = selected.replace("Grade ", "").lower()
        return [row for row in rows if _grade_bucket(str(row.get("grade") or "")) == target]
    return rows


def _rr(value) -> str:
    parsed = _rr_float(value)
    return f"1 : {parsed:.1f}" if parsed is not None else "-"


def _score_width(row: dict) -> int:
    try:
        score = float(row.get("score") or 0)
        max_score = float(row.get("max_score") or 11)
        return max(4, min(100, round((score / max_score) * 100)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 4


def _grade_class(grade: str) -> str:
    g = (grade or "").upper()
    if g.startswith("A"):
        return "grade-a"
    if g.startswith("B"):
        return "grade-b"
    return "grade-c"


def _grade_bucket(grade: str) -> str:
    g = (grade or "").upper()
    if g.startswith("A"):
        return "a"
    if g.startswith("B"):
        return "b"
    return "c"


@st.cache_data(ttl=300, show_spinner=False)
def _load_watchlist_data(_refresh_key: int = 0) -> dict:
    from watchlist_engine.webdash import run_scan

    return run_scan()


@st.cache_data(ttl=300, show_spinner=False)
def _load_flush_reversal_data(_refresh_key: int = 0) -> dict:
    from reversal_watchlist import run_scan

    return run_scan()


@st.cache_data(ttl=300, show_spinner=False)
def _load_hermes_dashboard(_refresh_key: int = 0, force_scan: bool = False) -> dict:
    params = {"refresh": "1"} if force_scan else {}
    separator = "&" if "?" in HERMES_DASHBOARD_URL else "?"
    url = HERMES_DASHBOARD_URL
    if params:
        url = f"{HERMES_DASHBOARD_URL}{separator}{urlencode(params)}"
    response = requests.get(url, timeout=130 if force_scan else 35, headers={"Cache-Control": "no-cache"})
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3600, show_spinner=False)
def _icon_lookup(symbols: tuple[str, ...]) -> dict:
    return icons.icon_urls(list(symbols))


def _entry(row: dict) -> str:
    low = row.get("entry_low")
    high = row.get("entry_high")
    if low is not None and high is not None:
        if str(low) == str(high):
            return _price(low)
        return f"{_price(low)} - {_price(high)}"
    return "-"


def _score_label(row: dict) -> str:
    score = row.get("score")
    max_score = row.get("max_score")
    if max_score in ("", None):
        return _e(score)
    return f"{_e(score)}/{_e(max_score)}"


def _score_grade(score: float) -> str:
    if score >= 70:
        return "A"
    if score >= 50:
        return "B"
    return "C"


def _score_breakdown_from_scores(scores: dict) -> list[dict]:
    breakdown = []
    for key, item in (scores or {}).items():
        if not isinstance(item, dict):
            continue
        breakdown.append(
            {
                "label": item.get("label") or key.upper(),
                "score": item.get("value") or 0,
                "max": item.get("max") or 0,
                "pass": _num(item.get("value")) > 0,
            }
        )
    return breakdown


def _score_breakdown_from_filters(filters: dict) -> list[dict]:
    labels = {
        "f1_consolidation": "Consolidation",
        "f2_resistance_proximity": "Resistance Proximity",
        "f3_volume_surge": "Volume Surge",
        "f4_momentum_divergence": "Momentum / Divergence",
        "f5_relative_strength": "Relative Strength",
    }
    return [
        {"label": labels.get(key, key), "score": value, "max": "", "pass": _num(value) > 0}
        for key, value in (filters or {}).items()
    ]


def _score_breakdown_from_exit_factors(factors: dict) -> list[dict]:
    labels = {
        "profit_zone": "Profit Zone",
        "momentum_decay": "Momentum Decay",
        "structure_breach": "Structure Breach",
        "funding_oi": "Funding / OI",
        "order_book": "Order Book",
        "scanner_status": "Scanner Status",
        "btc_risk": "BTC Risk",
        "next_target": "Next Target",
    }
    return [
        {"label": labels.get(key, key), "score": value, "max": "", "pass": _num(value) >= 0}
        for key, value in (factors or {}).items()
    ]


def _hermes_maturity(row: dict, tab_key: str) -> str:
    if tab_key == "exits":
        label = str(row.get("classification") or "").replace("_", " ").title()
        return label or "-"
    classification = str(row.get("classification") or "").lower()
    if classification == "primary":
        return "Ready"
    if classification == "watch":
        return "Forming"
    return "Nascent" if classification else "Ready"


def _hermes_rr(row: dict) -> str | None:
    rr = row.get("rr")
    if rr is None:
        return None
    return f"1:{rr}"


def _normalise_hermes_row(row: dict, tab_key: str) -> dict:
    symbol = str(row.get("symbol") or "").upper()
    score = _num(row.get("total_score" if tab_key == "exits" else "score"))
    max_score = 100 if tab_key != "exits" else ""
    direction = row.get("direction") or "long"
    if tab_key == "exits":
        pattern = row.get("action") or row.get("classification") or "Exit Management"
        price = row.get("current_price")
        score_breakdown = _score_breakdown_from_exit_factors(row.get("exit_factors") or {})
        evidence = [
            f"Entry: ${_price(row.get('entry_price'))}",
            f"P&L: {row.get('pnl_display') or _pct(row.get('pnl_pct'))}",
            f"Held: {row.get('held_hours')}h",
        ]
    elif tab_key == "pre_breakout":
        pattern = f"{row.get('timing_class') or 'Pre-Breakout'} · {row.get('timing_window') or ''}".strip(" ·")
        price = row.get("price")
        score_breakdown = _score_breakdown_from_filters(row.get("filters") or {})
        evidence = [
            f"Distance: {_num(row.get('distance')):.2f}% to resistance",
            f"Resistance: ${_price(row.get('resistance'))}",
            f"BB percentile: {row.get('bb_percentile')}",
            f"Rising volume candles: {row.get('vol_rising')}",
        ]
    else:
        timing = row.get("timing") or "Swing Setup"
        distance = row.get("distance")
        ceiling = row.get("ceiling") or row.get("resistance")
        pattern = f"{timing} · {_num(distance):.2f}% to level · R:R {row.get('rr') or '-'}"
        price = row.get("price")
        score_breakdown = _score_breakdown_from_scores(row.get("scores") or {})
        evidence = [
            f"Class: {row.get('classification') or '-'}",
            f"Resistance: ${_price(row.get('resistance') or row.get('pivot'))}",
            f"Ceiling: ${_price(ceiling)}",
            f"Penalties: {row.get('penalties') or 0}",
        ]
        for reason in row.get("pen_reasons") or []:
            evidence.append(f"Penalty reason: {reason}")

    normalised = {
        "coin": symbol,
        "symbol": f"{symbol}/USDT:USDT" if symbol and not symbol.endswith("USDT") else symbol,
        "price": price,
        "pattern": pattern,
        "direction": str(direction).lower(),
        "grade": _score_grade(score if tab_key != "exits" else 70 if score >= 0 else 50),
        "maturity": _hermes_maturity(row, tab_key),
        "score": int(score) if float(score).is_integer() else score,
        "max_score": max_score,
        "rr": _hermes_rr(row),
        "entry_low": row.get("entry_level") or row.get("entry_price"),
        "entry_high": row.get("entry_level") or row.get("entry_price"),
        "stop": row.get("invalidation"),
        "t1": row.get("tp1"),
        "t2": row.get("tp2"),
        "confidence": min(100, max(0, score if tab_key != "exits" else 50 + score)),
        "score_breakdown": score_breakdown,
        "evidence": [item for item in evidence if item and "None" not in str(item)],
        "warnings": [],
        "missing": [],
        "raw": row,
    }
    return normalised


def _hermes_tab_data(dashboard: dict | None, tab_key: str) -> dict:
    dashboard = dashboard or {}
    tabs = dashboard.get("tabs") or {}
    tab = tabs.get(tab_key) or {}
    rows = [_normalise_hermes_row(row, tab_key) for row in (tab.get("rows") or []) if isinstance(row, dict)]
    return {
        "rows": rows,
        "status": tab.get("status") or "unknown",
        "description": tab.get("description") or "",
        "last_scan": dashboard.get("last_scan") or "",
        "setup_count": dashboard.get("setup_count"),
        "coin_count": dashboard.get("coin_count"),
        "errors": [],
    }


def _target_text(row: dict) -> str:
    return f"T1 {_price(row.get('t1'))} · T2 {_price(row.get('t2'))}"


def _money_millions(value) -> str:
    try:
        return f"${float(value) / 1_000_000:.1f}M"
    except (TypeError, ValueError):
        return "-"


def _funding(value) -> tuple[str, str]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-", ""
    return f"{v:+.4f}%", "pos" if v > 0 else "neg" if v < 0 else ""


def _ctx_card(label: str, value: str, cls: str = "", wide: bool = False) -> str:
    wide_cls = " wide" if wide else ""
    value_cls = f" {cls}" if cls else ""
    return f"<div class='ctx-card{wide_cls}'><div class='ctx-label'>{_e(label)}</div><div class='ctx-value{value_cls}'>{value}</div></div>"


def _depth_bars(clusters: list, side: str) -> str:
    lines = []
    for cluster in clusters[:4]:
        price = _price(cluster.get("price"))
        width = max(2, min(100, int(float(cluster.get("bar_width") or 0))))
        distance = _e(cluster.get("distance_pct"))
        lines.append(
            f"<div class='depth-line'><span class='depth-price'>${price}<small>{distance}% away</small></span>"
            f"<span class='depth-track'><i class='depth-fill {side}' style='width:{width}%'></i></span>"
            f"<span class='depth-pct'>{width}%</span></div>"
        )
    return "".join(lines)


def _order_book_html(row: dict) -> str:
    ob = row.get("order_book") or {}
    if not isinstance(ob, dict) or ob.get("error"):
        return _ctx_card("Order Book", "-", wide=True)
    signal_raw = str(ob.get("order_book_imbalance") or "neutral").lower()
    signal = _e(signal_raw)
    ratio = _e(ob.get("bid_ask_ratio") or "-")
    clusters = ob.get("clusters") or {}
    asks = clusters.get("ask_clusters") or []
    bids = clusters.get("bid_clusters") or []
    ask_html = _depth_bars(asks, "ask")
    bid_html = _depth_bars(bids, "bid")
    body = (
        f"<div class='ctx-label'>Order Book - <span class='order-signal {signal}'>{signal}</span> (ratio {ratio})</div>"
        + ("<div class='depth-title ask'>SELL WALLS (asks)</div>" + ask_html if ask_html else "")
        + ("<div class='depth-title bid'>BUY WALLS (bids)</div>" + bid_html if bid_html else "")
    )
    return f"<div class='ctx-card wide'>{body}</div>"


def _score_breakdown_html(row: dict) -> str:
    parts = []
    for item in row.get("score_breakdown") or []:
        if not isinstance(item, dict):
            continue
        passed = bool(item.get("pass"))
        score_cls = "pass" if float(item.get("score") or 0) > 0 else "fail"
        score_text = _e(item.get("score") or 0)
        if item.get("max") not in ("", None):
            score_text = f"{score_text}/{_e(item.get('max'))}"
        icon = "✓" if passed else "×"
        parts.append(
            f"<div class='bd-row'><span class='bd-icon'>{icon}</span>"
            f"<span class='bd-label'>{_e(item.get('label'))}</span>"
            f"<span class='bd-score {score_cls}'>{score_text}</span></div>"
        )
        if item.get("text"):
            parts.append(f"<div class='bd-text'>{_e(item.get('text'))}</div>")
        for check in item.get("checks") or []:
            if not isinstance(check, dict):
                continue
            cls = "pass" if check.get("pass") else "fail"
            prefix = "✓" if check.get("pass") else "×"
            parts.append(f"<div class='bd-text {cls}'>{prefix} {_e(check.get('text'))}</div>")
    return "".join(parts) or "<div class='bd-text'>No score breakdown supplied by scanner.</div>"


def _evidence_html(row: dict) -> str:
    lines = []
    for item in row.get("evidence") or []:
        lines.append(f"<li>✓ {_e(item)}</li>")
    for item in row.get("missing") or []:
        lines.append(f"<li class='bad'>× {_e(item)}</li>")
    for item in row.get("warnings") or []:
        lines.append(f"<li class='warn'>! {_e(item)}</li>")
    if not lines:
        lines.append("<li>No evidence or gaps supplied by scanner.</li>")
    return "<ul class='evidence-list'>" + "".join(lines) + "</ul>"


def _exchange_symbol(row: dict) -> str:
    symbol = str(row.get("symbol") or row.get("coin") or "")
    base = symbol.split(":")[0].replace("/", "").replace("-", "").upper()
    if base and not base.endswith("USDT"):
        base = f"{base}USDT"
    return base or "-"


def _base_asset(row: dict) -> str:
    symbol = str(row.get("symbol") or row.get("coin") or "")
    return symbol.split("/")[0].split(":")[0].replace("-", "").upper() or str(row.get("coin") or "?").upper()


def _coin_logo_html(row: dict, icon_lookup: dict) -> str:
    asset = _base_asset(row)
    symbol = _exchange_symbol(row)
    uri = icon_lookup.get(symbol, "")
    if uri:
        return f'<span class="rank-badge coin-symbol"><img src="{_e(uri)}" alt="{_e(asset)} logo"></span>'
    return f'<span class="rank-badge coin-symbol no-logo">{_e(asset[:4])}</span>'


def _row(row: dict, rank: int, icon_lookup: dict, featured: bool = False) -> str:
    direction = (row.get("direction") or "").lower()
    maturity = (row.get("maturity") or "").lower()
    grade = row.get("grade") or "-"
    star_class = "hot" if featured else ""
    row_class = "watch-row featured" if featured else "watch-row"
    logo_html = _coin_logo_html(row, icon_lookup)
    exchange_symbol = _exchange_symbol(row)
    maturity_cls = maturity or "nascent"
    maturity_label = row.get("maturity") or "-"
    return f"""
<div class="{row_class}">
  <div class="coin-preview">{logo_html}<div class="coin-text"><div class="coin-line"><span class="coin-main">{_e(exchange_symbol)}</span><span class="mobile-badges"><span class="dir-box {direction}" aria-label="{_e(direction or "-")}"><span class="dir-icon"></span></span><span class="grade-pill {_grade_class(str(grade))}">{_e(grade)}</span><span class="grade-pill ready-pill {maturity_cls}">✓ {_e(maturity_label)}</span><span class="score-pill">{_score_label(row)}</span></span></div><div class="coin-sub">{_e(row.get("pattern"))}</div></div><span class="star {star_class}">☆</span></div>
  <span class="dir-box {direction}" aria-label="{_e(direction or "-")}"><span class="dir-icon"></span></span>
  <span class="grade-pill {_grade_class(str(grade))}">{_e(grade)}</span>
  <span class="grade-pill ready-pill {maturity_cls}">✓ {_e(maturity_label)}</span>
  <span class="score-pill">{_score_label(row)}</span>
  <div class="rr">{_rr(row.get("rr"))}</div>
  <div class="entry">{_entry(row)}</div>
  <div class="chev">{DOWN_ARROW_SVG}</div>
</div>
"""


def _accordion(row: dict, rank: int, icon_lookup: dict, featured: bool = False) -> str:
    return (
        "<details class='watch-item'>"
        f"<summary>{_row(row, rank, icon_lookup, featured)}</summary>"
        f"<div class='watch-detail-wrap'>{_feature(row)}</div>"
        "</details>"
    )


def _list_items(items: list, limit: int, fallback: str, confluence: bool = False) -> str:
    clean = [str(x) for x in items if x]
    if not clean:
        clean = [fallback]
    parts = []
    for idx, item in enumerate(clean[:limit]):
        if confluence:
            label = "".join([w[0] for w in item.split()[:2]]).upper()[:2] or "C"
            parts.append(f"<div class='deep-line'><span class='bubble'>{_e(label)}</span><span>{_e(item)}</span></div>")
        else:
            parts.append(f"<div class='deep-line'><span class='check'>✓</span><span>{_e(item)}</span></div>")
    return "".join(parts)


def _feature(row: dict) -> str:
    confidence = _pct(row.get("confidence"))
    score = row.get("score") or 0
    max_score = row.get("max_score") or 100
    grade = row.get("grade") or "-"
    direction = (row.get("direction") or "").lower()
    direction_arrow = "↓" if direction == "short" else "↑" if direction == "long" else ""
    funding_text, funding_cls = _funding(row.get("funding"))
    cvd = row.get("cvd") or {}
    cvd_value = "-"
    cvd_cls = ""
    if isinstance(cvd, dict) and not cvd.get("error"):
        cvd_signal = str(cvd.get("cvd_signal") or "").lower()
        cvd_cls = "pos" if cvd_signal == "bullish" else "neg" if cvd_signal == "bearish" else ""
        cvd_value = f"{_e(cvd.get('taker_buy_pct') or '-')}% buy"
    range_text = f"${_price(row.get('low24h'))}-${_price(row.get('high24h'))}"

    return f"""
<div class="feature-card">
  <div class="feature-top">
    <div class="selected-title">
      <div class="coin-orb">{_e(str(row.get("coin") or "?")[:1])}</div>
      <div>
        <div class="sel-coin"><span class="dir-pill {direction}">{direction_arrow} {_e(direction or "-")}</span> {_e(row.get("coin"))} <span style="color:#7f899f;font-weight:700">${_price(row.get("price"))}</span></div>
        <div class="sel-pattern">{_e(row.get("pattern"))}</div>
        <div class="sel-note"><span class="grade-pill {_grade_class(str(grade))}">{_e(grade)}</span> <span class="dir-pill ready">✓ {_e(row.get("maturity") or "-")}</span> <span class="grade-pill">{_score_label(row)}</span></div>
      </div>
    </div>
    <div class="feature-score"><div><div class="cap">Opportunity Score</div><div class="big">{_e(score)}<span>{"/" + _e(max_score) if max_score not in ("", None) else ""}</span></div></div></div>
  </div>
  <div class="trade-plan">
    <div class="section-label">Trade Plan</div>
    <div class="drawer-plan">
      <div class="plan-row"><span class="plan-label">Entry Zone</span><span class="plan-value entry">${_entry(row)}</span></div>
      <div class="plan-row"><span class="plan-label">Stop Loss</span><span class="plan-value stop">${_price(row.get("stop"))}</span></div>
      <div class="plan-row"><span class="plan-label">Take Profit 1</span><span class="plan-value tp">${_price(row.get("t1"))} <small>{_e(row.get("t1_rr") or "")}</small></span></div>
      <div class="plan-row"><span class="plan-label">Take Profit 2</span><span class="plan-value tp">${_price(row.get("t2"))} <small>{_e(row.get("t2_rr") or "")}</small></span></div>
      <div class="plan-row"><span class="plan-label">Risk / Unit</span><span class="plan-value">${_price(row.get("risk"))}</span></div>
      <div class="plan-row"><span class="plan-label">Confidence</span><span class="plan-value">{confidence}</span></div>
    </div>
  </div>
  <div class="section-label">Market Context</div>
  <div class="ctx-grid">
    {_ctx_card("Price", "$" + _price(row.get("price")))}
    {_ctx_card("OI", _money_millions(row.get("oi")))}
    {_ctx_card("Funding", funding_text, funding_cls)}
    {_ctx_card("24H Range", range_text)}
    {_ctx_card("CVD (5M)", cvd_value, cvd_cls)}
    {_order_book_html(row)}
  </div>
  <div class="section-label">Score Breakdown</div>
  {_score_breakdown_html(row)}
  <div class="section-label evidence-gap-heading">Evidence & Gaps</div>
  {_evidence_html(row)}
</div>
"""


def _rows_with_default_direction(rows: list[dict], direction: str | None = None) -> list[dict]:
    if not direction:
        return rows
    normalized = []
    for row in rows:
        if row.get("direction"):
            normalized.append(row)
        else:
            updated = dict(row)
            updated["direction"] = direction
            normalized.append(updated)
    return normalized


def _read_scan_data(
    session_key: str,
    loader,
    refresh: bool,
    refresh_key: int,
    spinner_text: str,
):
    try:
        if refresh or session_key not in st.session_state:
            if refresh:
                with st.spinner(spinner_text):
                    data = loader(refresh_key)
            else:
                data = loader(refresh_key)
            st.session_state[session_key] = data
        return st.session_state[session_key], None
    except ModuleNotFoundError as exc:
        return None, (
            "<div class='errbox'><b>Watch List dependencies need installing.</b><br>"
            f"Missing module: <code>{_e(exc.name)}</code>. The deployment requirements have been updated; "
            "restart the app after installing dependencies.</div>"
        )
    except Exception as exc:
        return None, f"<div class='errbox'><b>Watch List scan failed.</b><br>{_e(exc)}</div>"


def _fmt_money(value) -> str:
    price = _price(value)
    return "-" if price == "-" else f"${price}"


def _fmt_pct2(value) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


def _fmt_num(value) -> str:
    if value in (None, ""):
        return "-"
    try:
        v = float(value)
        if v.is_integer():
            return f"{int(v)}"
        return f"{v:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _native_symbol(row: dict) -> str:
    return str(row.get("symbol") or "-").upper()


def _native_icon_symbol(row: dict) -> str:
    symbol = _native_symbol(row)
    return f"{symbol}USDT" if symbol and symbol != "-" and not symbol.endswith("USDT") else symbol


def _native_logo_html(row: dict, icon_lookup: dict) -> str:
    symbol = _native_symbol(row)
    icon_symbol = _native_icon_symbol(row)
    uri = icon_lookup.get(icon_symbol, "")
    if uri:
        return f"<span class='hermes-logo'><img src='{_e(uri)}' alt='{_e(symbol)} logo'></span>"
    return f"<span class='hermes-logo'>{_e(symbol[:4])}</span>"


def _native_rank(row: dict, idx: int) -> str:
    return str(row.get("rank") or idx + 1)


def _native_pill(value: str, cls: str = "") -> str:
    clean = str(value or "-")
    css = cls or clean.lower().replace(" ", "_")
    return f"<span class='hermes-pill {css}'>{_e(clean.replace('_', ' '))}</span>"


def _native_meta(tab: dict, dashboard: dict | None) -> str:
    dashboard = dashboard or {}
    bits = []
    if tab.get("description"):
        bits.append(_e(tab.get("description")))
    meta = []
    if dashboard.get("last_scan"):
        meta.append(f"Last scan: {_e(dashboard.get('last_scan'))}")
    if dashboard.get("setup_count") is not None:
        meta.append(f"{_e(dashboard.get('setup_count'))} setups")
    if dashboard.get("coin_count") is not None:
        meta.append(f"{_e(dashboard.get('coin_count'))} coins")
    if meta:
        bits.append(" · ".join(meta))
    return "<div class='hermes-meta'>" + "<br>".join(bits) + "</div>" if bits else ""


def _kv(label: str, value: str) -> str:
    return f"<div class='hermes-kv'><span>{_e(label)}</span><b>{value}</b></div>"


def _kv_grid(items: list[tuple[str, str]]) -> str:
    return "<div class='hermes-grid'>" + "".join(_kv(label, value) for label, value in items) + "</div>"


def _chip_grid(items: dict, title: str) -> str:
    chips = []
    for key, value in (items or {}).items():
        if isinstance(value, dict):
            label = value.get("label") or key
            val = value.get("value")
            max_val = value.get("max")
            display = f"{_fmt_num(val)}/{_fmt_num(max_val)}" if max_val not in (None, "") else _fmt_num(val)
        else:
            label = key
            display = _fmt_num(value)
        chips.append(f"<div class='hermes-chip'><span>{_e(label)}</span><b>{_e(display)}</b></div>")
    if not chips:
        return ""
    return f"<div class='hermes-section'>{_e(title)}</div><div class='hermes-chip-grid'>{''.join(chips)}</div>"


def _compact_score_items(items: dict) -> str:
    parts = []
    for key, value in (items or {}).items():
        label = key.split("_", 1)[-1] if "_" in key else key
        if isinstance(value, dict):
            score = value.get("score", value.get("value", "-"))
            max_score = value.get("max")
            display = f"{_fmt_num(score)}/{_fmt_num(max_score)}" if max_score not in (None, "") else _fmt_num(score)
        else:
            display = _fmt_num(value)
        parts.append(f"{label} {display}")
    return " · ".join(parts)


def _raw_scalars(row: dict) -> str:
    lines = []
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            continue
        lines.append(f"{key}: {value}")
    return "<div class='hermes-section'>Native Fields</div><div class='hermes-pre'>" + _e("\n".join(lines)) + "</div>"


def _score_tone(value, max_value, classification: str | None = None) -> str:
    cls = str(classification or "").lower()
    if cls == "primary":
        return "pass"
    if cls == "watch":
        return "partial"
    try:
        ratio = float(value or 0) / float(max_value or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        ratio = 0
    if ratio >= 0.65:
        return "pass"
    if ratio >= 0.40:
        return "partial"
    return "fail"


def _score_mark(tone: str) -> str:
    return {"pass": "✓", "partial": "−", "fail": "×"}.get(tone, "−")


def _v2_score_label(key: str, item: dict) -> str:
    labels = {
        "cmp": "Compression",
        "rq": "Resistance Quality",
        "vol": "Volume",
        "der": "Derivatives",
        "rs": "Relative Strength",
        "ob": "Order Book",
        "rr_score": "R:R Quality",
    }
    return item.get("label") or labels.get(key, key.replace("_", " ").title())


def _score_detail_value(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return _fmt_num(value)
    return str(value)


def _score_detail_from_fields(row: dict, keys: list[tuple[str, str]]) -> str:
    bits = []
    for field, label in keys:
        value = _score_detail_value(row.get(field))
        if value:
            bits.append(f"{label} {value}")
    return " · ".join(bits)


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def _detail_bool(detail: dict, field: str, yes: str, no: str | None = None) -> str:
    value = _as_bool(detail.get(field))
    if value is True:
        return yes
    if value is False and no:
        return no
    return ""


def _detail_num(detail: dict, field: str, label: str, suffix: str = "") -> str:
    value = detail.get(field)
    if value in (None, ""):
        return ""
    return f"{label} {_fmt_num(value)}{suffix}"


def _score_item_detail(key: str, item: dict) -> str:
    detail = item.get("detail") if isinstance(item, dict) else None
    if not isinstance(detail, dict) or not detail:
        return ""
    pieces = []
    if key == "cmp":
        pieces = [
            _detail_num(detail, "bb_percentile", "BB pct"),
            _detail_bool(detail, "atr_falling", "ATR falling", "ATR not falling"),
            _detail_num(detail, "range_tight_pct", "range", "%"),
            _detail_bool(detail, "higher_lows", "higher lows", "no higher lows"),
            _detail_bool(detail, "coil", "coil", "no coil"),
            _detail_num(detail, "coil_width", "coil width", "%"),
            _detail_num(detail, "coil_touches", "touches"),
        ]
    elif key == "rq":
        pieces = [
            _detail_num(detail, "approaches", "touches"),
            _detail_bool(detail, "shallower", "shallower tests", "not shallower"),
            _detail_bool(detail, "aligned", "level aligned", "not aligned"),
            _detail_bool(detail, "upper_third", "upper third", "not upper third"),
            _detail_bool(detail, "no_fail", "no failed break", "failed break risk"),
        ]
    elif key == "vol":
        pieces = [
            _detail_bool(detail, "dry_up", "dry-up"),
            _detail_bool(detail, "surge", "surge"),
            _detail_bool(detail, "cq", "candle quality"),
            _detail_bool(detail, "vol_pressure", "volume pressure"),
            _detail_bool(detail, "no_sell", "no sell pressure", "sell pressure"),
            _detail_bool(detail, "constructive", "constructive"),
        ]
    elif key == "der":
        pieces = [
            _detail_num(detail, "oi_change", "OI", "%"),
            _detail_num(detail, "price_change", "price", "%"),
            _detail_num(detail, "funding", "funding", "%"),
            _detail_bool(detail, "not_crowded", "not crowded", "crowded"),
        ]
    elif key == "ob":
        pieces = [
            _detail_num(detail, "spread", "spread", "%"),
            _detail_bool(detail, "bid_support", "bid support", "weak bids"),
            _detail_bool(detail, "ask_absorb", "ask absorption", "no ask absorption"),
        ]
    elif key == "rr_score":
        pieces = [
            _detail_num(detail, "rr", "R:R"),
            _detail_bool(detail, "no_overhead", "no overhead", "overhead nearby"),
        ]
    else:
        pieces = [f"{name.replace('_', ' ')} {_score_detail_value(value)}" for name, value in detail.items()]
    return " · ".join(piece for piece in pieces if piece)


def _v2_score_evidence(key: str, row: dict, item: dict | None = None) -> str:
    nested_detail = _score_item_detail(key, item or {})
    if nested_detail:
        return nested_detail

    details = row.get("score_details") or row.get("score_detail") or {}
    block = details.get(key) if isinstance(details, dict) else None
    checks = block.get("checks") if isinstance(block, dict) else None
    if checks:
        pieces = []
        for check in checks[:3]:
            if isinstance(check, dict):
                label = check.get("label") or check.get("name") or check.get("metric")
                value = check.get("value") or check.get("status") or check.get("detail")
                if label and value:
                    pieces.append(f"{label} {value}")
                elif label:
                    pieces.append(str(label))
            elif check:
                pieces.append(str(check))
        if pieces:
            return " · ".join(pieces)

    if key == "cmp":
        bits = []
        if row.get("atr_val") not in (None, ""):
            bits.append(f"ATR {_fmt_num(row.get('atr_val'))}")
        if row.get("ema20_1h") not in (None, ""):
            bits.append(f"EMA20 {_fmt_money(row.get('ema20_1h'))}")
        if row.get("distance") not in (None, ""):
            bits.append(f"distance {_fmt_pct2(row.get('distance'))}")
        return " · ".join(bits)
    if key == "rq":
        level = row.get("resistance") or row.get("pivot") or row.get("ceiling")
        return f"Resistance {_fmt_money(level)} · distance {_fmt_pct2(row.get('distance'))}"
    if key == "vol":
        return _score_detail_from_fields(row, [("vol_rising", "vol rising"), ("volume", "volume"), ("volume_24h", "24h vol")])
    if key == "der":
        return _score_detail_from_fields(row, [("oi_change", "OI"), ("funding", "funding"), ("funding_rate", "funding")])
    if key == "rs":
        return _score_detail_from_fields(row, [("rs_btc", "vs BTC"), ("rs_eth", "vs ETH"), ("btc_rel", "vs BTC"), ("eth_rel", "vs ETH")])
    if key == "ob":
        return _score_detail_from_fields(row, [("spread", "spread"), ("bid_ask_ratio", "bid/ask"), ("depth", "depth")])
    if key == "rr_score":
        return f"R:R {row.get('rr') or '—'} · entry {_fmt_money(row.get('entry_level'))} · invalidation {_fmt_money(row.get('invalidation'))}"
    return ""


def _v2_score_action(key: str, tone: str, row: dict) -> str:
    if key == "cmp":
        return "Volatility is coiling; needs one cleaner structural hold." if tone != "fail" else "Compression is not tight enough yet."
    if key == "rq":
        return "The level exists, but quality is not clean enough to chase." if tone != "pass" else "Resistance quality supports a planned breakout entry."
    if key == "vol":
        return "Participation is present; confirms the setup if price holds." if tone == "pass" else "Wait for stronger participation before treating the move as live."
    if key == "der":
        return "Positioning supports accumulation, not late FOMO." if tone == "pass" else "Positioning is not yet giving a clean confirmation."
    if key == "rs":
        return "Relative strength supports the setup against the broader market." if tone == "pass" else "Relative strength is not strong enough to be a timing edge."
    if key == "ob":
        return "Wait for bid support or wall pull before entry." if tone != "pass" else "Order book pressure is supportive enough to monitor closely."
    if key == "rr_score":
        return "Reward is acceptable relative to invalidation." if tone != "fail" else "Risk/reward is not attractive enough without a better entry."
    return "Use this block as supporting context, not a standalone entry signal."


def _score_breakdown_panel(row: dict) -> str:
    scores = row.get("scores") or {}
    if not isinstance(scores, dict) or not scores:
        return _chip_grid(scores, "Score Blocks")
    max_total = sum(_num(item.get("max")) for item in scores.values() if isinstance(item, dict) and item.get("max") not in (None, ""))
    if max_total <= 0:
        max_total = 100
    total_score = row.get("score")
    total_tone = _score_tone(total_score, max_total, row.get("classification"))
    summary = "Strong setup, but not clean enough to chase yet." if total_tone == "pass" else (
        "Setup is mixed; wait for more confirmation." if total_tone == "partial" else "Setup is weak; avoid until conditions improve."
    )
    penalties = _num(row.get("penalties"))
    reasons = row.get("pen_reasons") or []
    blocker = "Order book is the main blocker; wait for bid support."
    if reasons:
        blocker = str(reasons[0])
    elif penalties:
        blocker = f"Penalties are reducing confidence by {_fmt_num(penalties)}."

    rows = []
    for key, item in scores.items():
        if not isinstance(item, dict):
            continue
        value = item.get("value", item.get("score", 0))
        max_value = item.get("max", "")
        tone = _score_tone(value, max_value)
        score_text = f"{_fmt_num(value)} / {_fmt_num(max_value)}" if max_value not in (None, "") else _fmt_num(value)
        detail = _v2_score_evidence(key, row, item)
        detail_html = f"<div class='score-line-detail'>{_e(detail)}</div>" if detail else ""
        rows.append(
            "<div class='score-line {tone}'>"
            "<div class='score-line-mark'>{mark}</div>"
            "<div class='score-line-label'>{label}</div>"
            "<div class='score-line-score'>{score}</div>"
            "{detail}"
            "<div class='score-line-action'>{action}</div>"
            "</div>".format(
                tone=tone,
                mark=_e(_score_mark(tone)),
                label=_e(_v2_score_label(key, item)),
                score=_e(score_text),
                detail=detail_html,
                action=_e(_v2_score_action(key, tone, row)),
            )
        )

    warning = ""
    if reasons or penalties:
        warning_text = " · ".join(map(str, reasons)) if reasons else f"Penalty impact: {_fmt_num(penalties)}"
        warning = f"<div class='score-warning'>• {_e(warning_text)}</div>"

    return (
        "<div class='score-breakdown'>"
        "<div class='score-breakdown-head'>"
        "<div class='score-breakdown-title'>Score Breakdown</div>"
        f"<div class='score-breakdown-summary'>{_e(summary)}</div>"
        f"<div class='score-breakdown-muted'>{_e(blocker)}</div>"
        f"<div class='score-circle {total_tone}'><b>{_e(_fmt_num(total_score))}</b><span>/{_e(_fmt_num(max_total))}</span></div>"
        "</div>"
        + "".join(rows)
        + warning
        + "</div>"
    )


def _target_rr(entry, stop, target) -> str:
    entry_n = _num(entry)
    stop_n = _num(stop)
    target_n = _num(target)
    risk = abs(entry_n - stop_n)
    reward = abs(target_n - entry_n)
    if risk <= 0 or reward <= 0:
        return ""
    return f"1:{reward / risk:.1f}"


def _trade_plan_compact(row: dict) -> str:
    entry = row.get("entry_level")
    stop = row.get("invalidation")
    tp1 = row.get("tp1")
    tp2 = row.get("tp2")
    rows = [
        ("Entry", _fmt_money(entry), "entry", ""),
        ("Stop", _fmt_money(stop), "stop", ""),
        ("TP1", _fmt_money(tp1), "target", _target_rr(entry, stop, tp1)),
        ("TP2", _fmt_money(tp2), "target", _target_rr(entry, stop, tp2)),
    ]
    return "<div class='trade-plan-compact'>" + "".join(
        "<div class='trade-plan-row'>"
        f"<div class='trade-plan-label'>{_e(label)}</div>"
        f"<div class='trade-plan-value {cls}'>{_e(value)}</div>"
        f"<div class='trade-plan-rr{' blank' if not rr else ''}'>{_e(rr or '-')}</div>"
        "</div>"
        for label, value, cls, rr in rows
    ) + "</div>"


def _ai_interpretation_payload(row: dict) -> dict:
    scores = row.get("scores") or {}
    score_items = []
    if isinstance(scores, dict):
        for key, item in scores.items():
            if not isinstance(item, dict):
                continue
            value = _num(item.get("value", item.get("score", 0)))
            max_value = _num(item.get("max"), 0)
            score_items.append(
                {
                    "key": key,
                    "label": _v2_score_label(key, item),
                    "value": value,
                    "max": max_value,
                    "ratio": value / max_value if max_value else value,
                }
            )
    score_items.sort(key=lambda item: item["ratio"], reverse=True)
    strongest = score_items[0] if score_items else None
    weakest = score_items[-1] if score_items else None
    return {
        "symbol": _native_symbol(row),
        "score": row.get("score"),
        "classification": row.get("classification"),
        "timing": row.get("timing"),
        "distance": row.get("distance"),
        "rr": row.get("rr"),
        "resistance": row.get("resistance"),
        "penalties": row.get("penalties"),
        "penalty_reasons": row.get("pen_reasons") or [],
        "strongest": strongest,
        "weakest": weakest,
    }


def _local_ai_interpretation(row: dict) -> tuple[str, str]:
    payload = _ai_interpretation_payload(row)
    strongest = payload.get("strongest") or {}
    weakest = payload.get("weakest") or {}
    penalties = _num(payload.get("penalties"))
    reasons = payload.get("penalty_reasons") or []
    score = _fmt_num(payload.get("score"))
    classification = str(payload.get("classification") or "setup").replace("_", " ")
    timing = payload.get("timing") or "pre-breakout"
    distance = _fmt_pct2(payload.get("distance"))
    resistance = _fmt_money(payload.get("resistance"))

    strong_label = strongest.get("label") or "the strongest score block"
    weak_label = weakest.get("label") or "the weakest score block"
    compact = (
        f"{classification.title()} {timing} setup near {resistance}, with {strong_label.lower()} carrying the read. "
        f"{weak_label} is the main area to improve before treating the breakout as cleaner."
    )
    if penalties or reasons:
        compact += " Current penalties keep it as a watchlist setup rather than a clean trigger."

    blocker = str(reasons[0]) if reasons else f"{weak_label} needs to strengthen."
    expanded = (
        f"HERMES rates this at {score} with price {distance} from resistance. "
        f"The strongest evidence is {strong_label}, which explains why the setup remains on the pre-breakout radar. "
        f"The weakest evidence is {weak_label}; that is the part most likely to hold the score back. "
        f"The setup would improve if price continues to respect the level while the weak block confirms and penalties fade. "
        f"The current score makes sense because HERMES is balancing stored breakout pressure against the blocker: {blocker}"
    )
    return compact, expanded


def _ai_interpretation_panel(row: dict) -> str:
    ai = row.get("ai_interpretation") if isinstance(row.get("ai_interpretation"), dict) else {}
    compact = ai.get("compact")
    expanded = ai.get("expanded")
    if not compact or not expanded:
        compact, expanded = _local_ai_interpretation(row)
    return (
        "<div class='ai-interpretation'>"
        "<div class='ai-interpretation-title'>AI Interpretation</div>"
        f"<div class='ai-interpretation-compact'>{_e(compact)}</div>"
        "<details><summary>Show More</summary>"
        f"<div class='ai-interpretation-expanded'>{_e(expanded)}</div>"
        "</details></div>"
    )


def _pre_breakout_drawer(row: dict) -> str:
    return (
        "<div class='hermes-drawer'>"
        + _kv_grid(
            [
                ("Price", _fmt_money(row.get("price"))),
                ("Score", _e(row.get("score"))),
                ("Distance", _fmt_pct2(row.get("distance"))),
                ("Timing Class", _e(row.get("timing_class"))),
                ("Timing Window", _e(row.get("timing_window"))),
                ("Resistance", _fmt_money(row.get("resistance"))),
                ("Entry Level", _fmt_money(row.get("entry_level"))),
                ("Invalidation", _fmt_money(row.get("invalidation"))),
                ("TP1", _fmt_money(row.get("tp1"))),
                ("TP2", _fmt_money(row.get("tp2"))),
                ("ATR", _e(row.get("atr_val"))),
                ("BB Percentile", _e(row.get("bb_percentile"))),
                ("Vol Rising", _e(row.get("vol_rising"))),
            ]
        )
        + _chip_grid(row.get("filters") or {}, "Filters")
        + _raw_scalars(row)
        + "</div>"
    )


def _v2_drawer(row: dict, include_pivot: bool = False, include_ai: bool = False) -> str:
    fields = [
        ("Price", _fmt_money(row.get("price"))),
        ("Score", _e(row.get("score"))),
        ("Class", _native_pill(row.get("classification"))),
        ("Timing", _e(row.get("timing"))),
        ("Distance", _fmt_pct2(row.get("distance"))),
        ("R:R", _e(row.get("rr"))),
        ("Resistance", _fmt_money(row.get("resistance"))),
        ("ATR", _e(row.get("atr_val"))),
    ]
    if include_pivot:
        fields.insert(7, ("Pivot", _fmt_money(row.get("pivot"))))
        fields.insert(8, ("Ceiling", _fmt_money(row.get("ceiling"))))
    else:
        fields.append(("EMA20 1H", _fmt_money(row.get("ema20_1h"))))
    reasons = row.get("pen_reasons") or []
    reason_html = (
        "<div class='hermes-reasons'><b>Penalty reasons:</b> " + _e(", ".join(map(str, reasons))) + "</div>"
        if reasons
        else ""
    )
    return (
        "<div class='hermes-drawer'>"
        + _kv_grid(fields + [("Penalties", _e(row.get("penalties")))])
        + _trade_plan_compact(row)
        + (_ai_interpretation_panel(row) if include_ai else "")
        + (_chip_grid(row.get("scores") or {}, "Score Blocks") if include_pivot else _score_breakdown_panel(row))
        + reason_html
        + _raw_scalars(row)
        + "</div>"
    )


def _exits_drawer(row: dict) -> str:
    return (
        "<div class='hermes-drawer'>"
        + _kv_grid(
            [
                ("Direction", _e(row.get("direction"))),
                ("Current Price", _fmt_money(row.get("current_price"))),
                ("Entry Price", _fmt_money(row.get("entry_price"))),
                ("P&L", _e(row.get("pnl_display") or _fmt_pct2(row.get("pnl_pct")))),
                ("Held Hours", _e(row.get("held_hours"))),
                ("Entry Time", _e(row.get("entry_time"))),
                ("Total Score", _e(row.get("total_score"))),
                ("Classification", _native_pill(row.get("classification"))),
                ("Action", _e(row.get("action"))),
                ("Invalidation", _fmt_money(row.get("invalidation"))),
                ("TP1", _fmt_money(row.get("tp1"))),
                ("TP2", _fmt_money(row.get("tp2"))),
            ]
        )
        + _chip_grid(row.get("exit_factors") or {}, "Exit Factors")
        + _raw_scalars(row)
        + "</div>"
    )


def _render_hermes_native_tab(dashboard: dict | None, error_html: str | None, tab_key: str) -> None:
    if error_html:
        st.markdown(error_html, unsafe_allow_html=True)
        return
    dashboard = dashboard or {}
    source_tab_key = "pre_breakout_v2" if tab_key == "pre_breakout_v3" else tab_key
    tab = (dashboard.get("tabs") or {}).get(source_tab_key) or {}
    rows = [row for row in (tab.get("rows") or []) if isinstance(row, dict)]
    st.markdown(_native_meta(tab, dashboard), unsafe_allow_html=True)
    if not rows:
        status = str(tab.get("status") or "").lower()
        title = "Hermes is scanning." if status == "scanning" else "No Hermes rows."
        body = "This tab is rebuilding. Try Scan again in a minute." if status == "scanning" else "Hermes returned an empty result set for this tab."
        st.markdown(f"<div class='empty'><b>{_e(title)}</b>{_e(body)}</div>", unsafe_allow_html=True)
        return
    icon_lookup = _icon_lookup(tuple(_native_icon_symbol(row) for row in rows))

    if tab_key == "pre_breakout":
        head = "<div class='hermes-head hermes-pre-head'><div>#</div><div>Coin</div><div>Score</div><div>Price</div><div>Distance</div><div>Timing</div><div>Filters</div><div></div></div>"
        row_html = []
        for idx, row in enumerate(rows):
            filt = _compact_score_items(row.get("filters") or {})
            row_html.append(
                "<details class='hermes-item'><summary>"
                "<div class='hermes-row hermes-pre-row'>"
                f"<div class='hermes-cell mobile-hide'><span class='hermes-rank'>{_e(_native_rank(row, idx))}</span></div>"
                f"<div class='hermes-symbol'>{_native_logo_html(row, icon_lookup)}<div><b>{_e(_native_symbol(row))}</b><span class='hermes-muted'>Resistance {_fmt_money(row.get('resistance'))}</span></div></div>"
                f"<div class='hermes-cell'><span class='hermes-score'>{_e(row.get('score'))}</span></div>"
                f"<div class='hermes-cell mobile-hide'>{_fmt_money(row.get('price'))}</div>"
                f"<div class='hermes-cell'>{_fmt_pct2(row.get('distance'))}</div>"
                f"<div class='hermes-cell mobile-hide'>{_e(row.get('timing_class'))}<span class='hermes-muted'>{_e(row.get('timing_window'))}</span></div>"
                f"<div class='hermes-cell mobile-hide'>{_e(filt)}</div>"
                f"<div class='chev'>{DOWN_ARROW_SVG}</div></div></summary>{_pre_breakout_drawer(row)}</details>"
            )
    elif tab_key in {"pre_breakout_v2", "pre_breakout_v3", "swing_compression"}:
        include_pivot = tab_key == "swing_compression"
        include_ai = tab_key == "pre_breakout_v3"
        row_class = "hermes-v3-row" if include_ai else "hermes-v2-row"
        head_class = "hermes-v3-head" if include_ai else "hermes-v2-head"
        level_label = "Pivot / Ceiling" if include_pivot else "Resistance"
        head = f"<div class='hermes-head {head_class}'><div>#</div><div>Coin</div><div>Score</div><div>Class</div><div>Timing</div><div>Distance</div><div>R:R</div><div>{level_label}</div><div></div></div>"
        row_html = []
        for idx, row in enumerate(rows):
            level = (
                f"{_fmt_money(row.get('pivot'))} / {_fmt_money(row.get('ceiling'))}"
                if include_pivot
                else _fmt_money(row.get("resistance"))
            )
            row_html.append(
                "<details class='hermes-item'><summary>"
                f"<div class='hermes-row {row_class}'>"
                f"<div class='hermes-cell mobile-hide'><span class='hermes-rank'>{_e(_native_rank(row, idx))}</span></div>"
                f"<div class='hermes-symbol'>{_native_logo_html(row, icon_lookup)}<div><b>{_e(_native_symbol(row))}</b><span class='hermes-muted'>{_fmt_money(row.get('price'))}</span></div></div>"
                f"<div class='hermes-cell'><span class='hermes-score'>{_e(row.get('score'))}</span></div>"
                f"<div class='hermes-cell mobile-hide'>{_native_pill(row.get('classification'))}</div>"
                f"<div class='hermes-cell'>{_e(row.get('timing'))}</div>"
                f"<div class='hermes-cell mobile-hide'>{_fmt_pct2(row.get('distance'))}</div>"
                f"<div class='hermes-cell mobile-hide'>{_e(row.get('rr'))}</div>"
                f"<div class='hermes-cell mobile-hide'>{level}</div>"
                f"<div class='chev'>{DOWN_ARROW_SVG}</div></div></summary>{_v2_drawer(row, include_pivot, include_ai)}</details>"
            )
    else:
        head = "<div class='hermes-head hermes-exit-head'><div>#</div><div>Trade</div><div>Score</div><div>Class</div><div>P&L</div><div>Held</div><div>Action</div><div></div></div>"
        row_html = []
        for idx, row in enumerate(rows):
            score = _num(row.get("total_score"))
            score_cls = "neg" if score < 0 else "warn" if score < 5 else ""
            row_html.append(
                "<details class='hermes-item'><summary>"
                "<div class='hermes-row hermes-exit-row'>"
                f"<div class='hermes-cell mobile-hide'><span class='hermes-rank'>{_e(_native_rank(row, idx))}</span></div>"
                f"<div class='hermes-symbol'>{_native_logo_html(row, icon_lookup)}<div><b>{_e(_native_symbol(row))}</b><span class='hermes-muted'>{_e(row.get('direction'))} · Entry {_fmt_money(row.get('entry_price'))}</span></div></div>"
                f"<div class='hermes-cell'><span class='hermes-score {score_cls}'>{_e(row.get('total_score'))}</span></div>"
                f"<div class='hermes-cell'>{_native_pill(row.get('classification'))}</div>"
                f"<div class='hermes-cell'>{_e(row.get('pnl_display') or _fmt_pct2(row.get('pnl_pct')))}</div>"
                f"<div class='hermes-cell mobile-hide'>{_e(row.get('held_hours'))}h</div>"
                f"<div class='hermes-cell mobile-hide'>{_e(row.get('action'))}</div>"
                f"<div class='chev'>{DOWN_ARROW_SVG}</div></div></summary>{_exits_drawer(row)}</details>"
            )

    st.markdown(head + "<div class='hermes-table'>" + "".join(row_html) + "</div>", unsafe_allow_html=True)


def _render_watch_table(
    data: dict | None,
    error_html: str | None,
    selected_filter: str,
    empty_title: str,
    empty_body: str,
    no_match_label: str,
    default_direction: str | None = None,
) -> None:
    if error_html:
        st.markdown(error_html, unsafe_allow_html=True)
        return

    data = data or {}
    if data.get("description") or data.get("last_scan"):
        meta_parts = []
        if data.get("description"):
            meta_parts.append(_e(data.get("description")))
        if data.get("last_scan"):
            meta_parts.append(f"Last scan: {_e(data.get('last_scan'))}")
        st.markdown(
            "<div class='empty' style='padding:14px 16px;margin-bottom:12px;'>"
            + "<br>".join(meta_parts)
            + "</div>",
            unsafe_allow_html=True,
        )
    all_rows = _rows_with_default_direction(data.get("rows", []), default_direction)
    rows = _filter_rows(all_rows, selected_filter)
    scan_errors = data.get("errors") or []
    status = str(data.get("status") or "").lower()

    if not rows:
        if all_rows:
            st.markdown(
                f"<div class='empty'><b>No matching setups.</b>No {no_match_label} setups match the {_e(selected_filter)} filter.</div>",
                unsafe_allow_html=True,
            )
            return
        if scan_errors:
            sample_errors = scan_errors[:4]
            error_lines = "".join(
                f"<li><b>{_e(item.get('coin', 'Coin'))}</b>: {_e(item.get('error', 'Exchange data unavailable'))}</li>"
                for item in sample_errors
                if isinstance(item, dict)
            )
            extra = len(scan_errors) - len(sample_errors)
            more_text = f"<div class='scan-error-more'>+ {extra} more exchange errors</div>" if extra > 0 else ""
            st.markdown(
                "<div class='errbox'><b>Watch List scan did not return tradable setups.</b><br>"
                "The exchange data fetch failed, so the leaderboard could not be rebuilt."
                f"<ul class='scan-error-list'>{error_lines}</ul>{more_text}</div>",
                unsafe_allow_html=True,
            )
            return
        title = "Hermes is scanning." if status == "scanning" else empty_title
        body = "This tab is rebuilding. Try Scan again in a minute." if status == "scanning" else empty_body
        st.markdown(f"<div class='empty'><b>{_e(title)}</b>{_e(body)}</div>", unsafe_allow_html=True)
        return

    icon_lookup = _icon_lookup(tuple(_exchange_symbol(row) for row in rows))

    st.markdown(
        "<div class='watch-head'><div>Coin / Setup</div><div>Dir</div><div>Grade</div><div>Status</div>"
        "<div>Score</div><div>R:R</div><div>Entry Range</div><div></div></div>"
        "<div class='watch-list'>"
        + "".join(_accordion(row, idx + 1, icon_lookup, featured=(idx == 0)) for idx, row in enumerate(rows))
        + "</div>",
        unsafe_allow_html=True,
    )


with st.container(key="watch_shell"):
    with st.container(key="watch_header_row"):
        selected_filter = "All Setups"
        with st.container(key="watch_controls"):
            refresh = st.button("Scan", key="watch_refresh")

    refresh_key = int(time.time()) if refresh else 0
    hermes_data, hermes_error = _read_scan_data(
        "hermes_dashboard_data",
        lambda key: _load_hermes_dashboard(key, force_scan=refresh),
        refresh,
        refresh_key,
        "Refreshing Hermes dashboard...",
    )

    pre_tab, pre_v2_tab, pre_v3_tab, swing_tab, exits_tab = st.tabs(["Pre-Breakout", "Pre-Breakout V2", "Pre-Breakout V3", "Swing Compression", "Exits"])
    with pre_tab:
        _render_hermes_native_tab(hermes_data, hermes_error, "pre_breakout")
    with pre_v2_tab:
        _render_hermes_native_tab(hermes_data, hermes_error, "pre_breakout_v2")
    with pre_v3_tab:
        _render_hermes_native_tab(hermes_data, hermes_error, "pre_breakout_v3")
    with swing_tab:
        _render_hermes_native_tab(hermes_data, hermes_error, "swing_compression")
    with exits_tab:
        _render_hermes_native_tab(hermes_data, hermes_error, "exits")
