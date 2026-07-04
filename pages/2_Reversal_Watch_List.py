"""Reversal Lows - capitulation flush watch list (Rulebook + provisional Learned Model).

Front end duplicated from 2_Watch_List.py; backend is reversal_watchlist.run_scan().
"""
from __future__ import annotations

import base64
import html
import os
import time

import streamlit as st

import chrome
import icons


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
UP_TREND_PATH = os.path.join(ASSETS_DIR, "trend.svg")
DOWN_TREND_PATH = os.path.join(ASSETS_DIR, "trend-2.svg")
DOWN_ARROW_SVG = '<svg class="down-arrow-svg" viewBox="0 0 128 128"><path fill="currentColor" d="M64 88 21 45l6-6 37 37 37-37 6 6z"/></svg>'


def _asset_data_uri(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


UP_TREND_URI = _asset_data_uri(UP_TREND_PATH)
DOWN_TREND_URI = _asset_data_uri(DOWN_TREND_PATH)


st.set_page_config(page_title="Reversal Lows", page_icon="📉", layout="wide")
chrome.render_header("REVERSAL", "LOWS", brand=False)


st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important;}
.st-key-rev_shell{max-width:1180px;margin:0 auto;}
.st-key-rev_header_row{margin-top:12px!important;margin-bottom:14px!important;}
.st-key-rev_controls{display:flex!important;align-items:center!important;justify-content:flex-end!important;gap:14px!important;margin:0!important;
  width:100%!important;}
.st-key-rev_controls > [data-testid="stElementContainer"]{width:auto!important;min-width:0!important;}
.st-key-rev_controls > [data-testid="stElementContainer"]:nth-child(1){flex:1 1 310px!important;}
.st-key-rev_controls > [data-testid="stElementContainer"]:nth-child(2){flex:0 0 154px!important;}
.st-key-rev_controls > [data-testid="stElementContainer"]:nth-child(3){flex:0 0 134px!important;}
.st-key-rev_add_coin [data-testid="stTextInputRootElement"]{height:52px!important;border:1px solid rgba(86,100,138,.46)!important;
  border-radius:9px!important;background:#0c1020!important;box-shadow:none!important;}
.st-key-rev_add_coin [data-testid="stTextInputRootElement"]:focus-within{border-color:#4c8dff!important;
  box-shadow:0 0 0 1px rgba(76,141,255,.14)!important;}
.st-key-rev_add_coin input{height:100%!important;border:0!important;background:transparent!important;color:#e6e8eb!important;
  font-size:.82rem!important;padding:0 15px!important;box-shadow:none!important;}
.st-key-rev_add_coin input::placeholder{color:#778197!important;opacity:1!important;}
.st-key-rev_filter_select [data-baseweb="select"] > div{height:52px!important;min-height:52px!important;border:1px solid rgba(86,100,138,.46)!important;
  border-radius:9px!important;background:#0c1020!important;color:#f1f3f8!important;box-shadow:none!important;}
.st-key-rev_filter_select [data-baseweb="select"] span,.st-key-rev_filter_select [data-baseweb="select"] div{font-size:.82rem!important;}
.st-key-rev_filter_select [data-baseweb="select"] svg{color:#aeb6c4!important;}
.st-key-rev_refresh button{width:134px!important;height:38px!important;min-height:38px!important;border:1px solid #4c6fff!important;
  border-radius:999px!important;background:rgba(76,111,255,.14)!important;color:#587dff!important;
  font-size:.84rem!important;font-weight:500!important;letter-spacing:0!important;text-transform:uppercase!important;
  box-shadow:none!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:8px!important;}
.st-key-rev_refresh button:hover{border-color:#4c8dff!important;background:rgba(76,141,255,.18)!important;color:#6f95ff!important;
  box-shadow:0 0 16px rgba(76,141,255,.16)!important;}
.st-key-rev_refresh button:active{transform:translateY(1px) scale(.99);background:rgba(76,111,255,.22)!important;
  box-shadow:inset 0 0 0 1px rgba(76,141,255,.7),0 0 18px rgba(76,141,255,.22)!important;}
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
.watch-head,.watch-row{display:grid;grid-template-columns:minmax(210px,1.5fr) 62px 96px 72px 92px 128px 24px;gap:12px;
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
.errbox{background:#13101e;border:1px solid rgba(246,70,93,.42);border-radius:10px;padding:16px;color:#f4c3c9;}
.scan-error-list{margin:10px 0 0;padding-left:18px;color:#f4c3c9;font-size:.82rem;line-height:1.35;}
.scan-error-more{margin-top:8px;color:#aeb6c4;font-size:.78rem;}
.empty{background:#13101e;border:1px solid rgba(139,92,246,.36);border-radius:10px;padding:26px 20px;color:#aab2bd;}
.empty b{display:block;color:#e6e8eb;font-size:1rem;margin-bottom:6px;}
@media(max-width:980px){
  .watch-metrics{grid-template-columns:repeat(4,minmax(0,1fr));border-radius:9px;margin-bottom:12px;}
  .watch-metric{min-width:0;padding:11px 10px}.watch-metric .cap{font-size:.55rem}.watch-metric .val{font-size:.9rem}
  .watch-head{display:none}.watch-list{border-radius:0}.watch-item[open]{background:linear-gradient(90deg,rgba(112,99,255,.14),rgba(7,11,22,.52) 44%,rgba(7,11,22,.78));box-shadow:inset 0 0 0 1px rgba(112,99,255,.72);}
  .watch-item[open] .watch-row{background:transparent;box-shadow:none;}
  .watch-row,.watch-row.featured{grid-template-columns:minmax(0,1fr) 40px 60px 48px 16px;gap:5px;padding:12px 9px;min-height:82px;border-radius:0;margin:0;}
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
}
@media(max-width:700px){
  .st-key-rev_header_row{margin-top:-58px!important;margin-bottom:0!important;}
  .st-key-rev_shell{margin-top:0;}
  .st-key-rev_controls{width:100%!important;margin:8px 0 12px!important;justify-content:flex-start!important;}
  .st-key-rev_controls > [data-testid="stElementContainer"]:nth-child(3){flex:0 0 104px!important;}
  .st-key-rev_controls [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr) 134px!important;gap:8px!important;width:100%!important;}
  .st-key-rev_controls [data-testid="stColumn"]{width:100%!important;min-width:0!important;}
  .st-key-rev_controls [data-testid="stColumn"]:nth-child(1){grid-column:1/-1!important;}
  .st-key-rev_controls [data-testid="stColumn"]:nth-child(2){grid-column:1!important;}
  .st-key-rev_controls [data-testid="stColumn"]:nth-child(3){grid-column:2!important;width:134px!important;}
  .st-key-rev_add_coin [data-testid="stTextInputRootElement"],.st-key-rev_filter_select [data-baseweb="select"] > div{height:46px!important;min-height:46px!important;}
  .st-key-rev_refresh button{width:134px!important;height:38px!important;min-height:38px!important;border-radius:999px!important;}
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


def _rr_float(value) -> float | None:
    if not value:
        return None
    try:
        return float(str(value).split(":")[-1].strip())
    except (TypeError, ValueError):
        return None


FILTER_OPTIONS = (
    "All Setups",
    "Confirmed",
    "Awaiting",
    "Stale",
    "Grade A",
    "Grade B",
    "Grade C",
)


def _filter_rows(rows: list[dict], selected: str) -> list[dict]:
    selected = selected or "All Setups"
    if selected == "All Setups":
        return rows
    if selected in {"Confirmed", "Awaiting", "Stale"}:
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
    from reversal_watchlist import run_scan

    return run_scan()


@st.cache_data(ttl=3600, show_spinner=False)
def _icon_lookup(symbols: tuple[str, ...]) -> dict:
    return icons.icon_urls(list(symbols))


def _entry(row: dict) -> str:
    low = row.get("entry_low")
    high = row.get("entry_high")
    if low is not None and high is not None:
        return f"{_price(low)} - {_price(high)}"
    return "-"


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
        icon = "✓" if passed else "×"
        parts.append(
            f"<div class='bd-row'><span class='bd-icon'>{icon}</span>"
            f"<span class='bd-label'>{_e(item.get('label'))}</span>"
            f"<span class='bd-score {score_cls}'>{_e(item.get('score') or 0)}/{_e(item.get('max') or 0)}</span></div>"
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
  <div class="coin-preview">{logo_html}<div class="coin-text"><div class="coin-line"><span class="coin-main">{_e(exchange_symbol)}</span><span class="mobile-badges"><span class="grade-pill {_grade_class(str(grade))}">{_e(grade)}</span><span class="grade-pill ready-pill {maturity_cls}">✓ {_e(maturity_label)}</span><span class="score-pill">{_e(row.get("score"))}/{_e(row.get("max_score"))}</span></span></div><div class="coin-sub">{_e(row.get("pattern"))}</div></div><span class="star {star_class}">☆</span></div>
  <span class="grade-pill {_grade_class(str(grade))}">{_e(grade)}</span>
  <span class="grade-pill ready-pill {maturity_cls}">✓ {_e(maturity_label)}</span>
  <span class="score-pill">{_e(row.get("score"))}/{_e(row.get("max_score"))}</span>
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
        <div class="sel-coin">{_e(row.get("coin"))} <span style="color:#7f899f;font-weight:700">${_price(row.get("price"))}</span></div>
        <div class="sel-pattern">{_e(row.get("pattern"))}</div>
        <div class="sel-note"><span class="grade-pill {_grade_class(str(grade))}">{_e(grade)}</span> <span class="dir-pill ready">✓ {_e(row.get("maturity") or "-")}</span> <span class="grade-pill">{_e(score)}/{_e(max_score)}</span></div>
      </div>
    </div>
    <div class="feature-score"><div><div class="cap">Learned Model Score</div><div class="big">{_e(score)}<span>/{_e(max_score)}</span></div></div></div>
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


with st.container(key="rev_shell"):
    with st.container(key="rev_header_row"):
        with st.container(key="rev_controls"):
            search, filt, action = st.columns([1, 0.5, 0.4], vertical_alignment="center")
            with search:
                st.text_input(
                    "Filter symbol",
                    key="rev_add_coin",
                    placeholder="Filter symbol",
                    label_visibility="collapsed",
                )
            with filt:
                selected_filter = st.selectbox(
                    "Filter setups",
                    FILTER_OPTIONS,
                    key="rev_filter_select",
                    label_visibility="collapsed",
                )
            with action:
                refresh = st.button("Run Scan", key="rev_refresh")

    try:
        if refresh or "reversal_watch_data" not in st.session_state:
            refresh_key = int(time.time()) if refresh else 0
            if refresh:
                with st.spinner("Scanning all Bybit perps for flushes (~2 min)..."):
                    data = _load_watchlist_data(refresh_key)
            else:
                data = _load_watchlist_data(refresh_key)
            st.session_state["reversal_watch_data"] = data
        else:
            data = st.session_state["reversal_watch_data"]
    except ModuleNotFoundError as exc:
        st.markdown(
            "<div class='errbox'><b>Reversal Lows dependencies need installing.</b><br>"
            f"Missing module: <code>{_e(exc.name)}</code>. The deployment requirements have been updated; "
            "restart the app after installing dependencies.</div>",
            unsafe_allow_html=True,
        )
        st.stop()
    except Exception as exc:
        st.markdown(
            "<div class='errbox'><b>Reversal scan failed.</b><br>"
            f"{_e(exc)}</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    all_rows = data.get("rows", [])
    rows = _filter_rows(all_rows, selected_filter)
    scan_errors = data.get("errors") or []
    generated = data.get("generated_at") or time.time()
    age = max(0, int(time.time() - generated))
    if age < 60:
        age_text = f"{age}s ago"
    elif age < 3600:
        age_text = f"{age // 60}m ago"
    else:
        age_text = time.strftime("%d %b %H:%M", time.localtime(generated))

    ready = sum(1 for r in rows if (r.get("maturity") or "").lower() == "confirmed")
    awaiting = sum(1 for r in rows if (r.get("maturity") or "").lower() == "awaiting")
    longs = sum(1 for r in rows if (r.get("direction") or "").lower() == "long")
    shorts = sum(1 for r in rows if (r.get("direction") or "").lower() == "short")
    grade_counts = {"a": 0, "b": 0, "c": 0}
    for row in rows:
        grade_counts[_grade_bucket(str(row.get("grade") or ""))] += 1
    avg_rr_values = [x for x in (_rr_float(r.get("rr")) for r in rows) if x is not None]
    avg_rr = sum(avg_rr_values) / len(avg_rr_values) if avg_rr_values else 0
    thrilling = sum(1 for r in rows if "THRILLING" in str(r.get("pattern") or ""))
    confidence_values = [float(r.get("confidence") or 0) for r in rows if r.get("confidence") is not None]
    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0
    if longs > shorts:
        bias = "Long"
        bias_class = "green"
    elif shorts > longs:
        bias = "Short"
        bias_class = "red"
    else:
        bias = "Neutral"
        bias_class = "yellow"

    st.markdown(
        f"""
<div class="watch-metrics">
  <div class="watch-metric"><div class="cap">Awaiting</div><div class="val yellow">{awaiting}</div></div>
  <div class="watch-metric"><div class="cap">Confirmed</div><div class="val green">{ready}</div></div>
  <div class="watch-metric"><div class="cap">Total Setups</div><div class="val">{len(rows)}</div></div>
  <div class="watch-metric"><div class="cap">Thrilling Wicks</div><div class="val green">{thrilling}</div></div>
  <div class="watch-metric"><div class="cap">Grade B</div><div class="val yellow">{grade_counts["b"]}</div></div>
  <div class="watch-metric"><div class="cap">Grade C</div><div class="val red">{grade_counts["c"]}</div></div>
  <div class="watch-metric"><div class="cap">Grade A</div><div class="val green">{grade_counts["a"]}</div></div>
  <div class="watch-metric"><div class="cap">Last Updated</div><div class="val fresh">{age_text}<span class="fresh-dot"></span></div></div>
</div>
""",
        unsafe_allow_html=True,
    )

    if not rows:
        if all_rows:
            st.markdown(
                f"<div class='empty'><b>No matching setups.</b>No reversal setups match the {_e(selected_filter)} filter.</div>",
                unsafe_allow_html=True,
            )
            st.stop()
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
                "<div class='errbox'><b>Reversal scan did not return setups.</b><br>"
                "The exchange data fetch failed, so the leaderboard could not be rebuilt."
                f"<ul class='scan-error-list'>{error_lines}</ul>{more_text}</div>",
                unsafe_allow_html=True,
            )
            st.stop()
        st.markdown(
            "<div class='empty'><b>No flushes on the board.</b>No capitulation-flush candidates in the last 6 hours - a normal result. Re-scan later.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    icon_lookup = _icon_lookup(tuple(_exchange_symbol(row) for row in rows))

    st.markdown(
        "<div class='watch-head'><div>Coin / Setup</div><div>Grade</div><div>Status</div>"
        "<div>Score</div><div>R:R</div><div>Entry Range</div><div></div></div>"
        "<div class='watch-list'>"
        + "".join(_accordion(row, idx + 1, icon_lookup, featured=(idx == 0)) for idx, row in enumerate(rows))
        + "</div>",
        unsafe_allow_html=True,
    )
