"""Position Size Calculator — Bybit USDT perps, isolated margin.

A high-fidelity calculator rendered in the established Orion style:
  • Trade Inputs (account, risk, entry/stop/T1/T2, leverage)
  • Trade Visualization (a zone diagram of risk vs reward)
  • Position Summary (size, notional, risk/reward $, R:R, liq, margin)
  • Risk/Reward setup Score (0–10 gauge + checklist)
  • a 5-card metrics strip + footer

All maths is pure Python (no LLM). Trade levels pre-fill from the coin's analysis
(analyses/<SYMBOL>.json) — mirroring the most-recently-pushed trade — and stay
editable; account inputs are yours.
"""
from __future__ import annotations

import base64
import datetime
import json
import math
import os
import re
from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components

import chrome
import bybit
import dashboard
import scanner

st.set_page_config(page_title="Calculator", page_icon="📐", layout="wide")

# Shared chrome: nav + world-clocks (brand rendered below alongside the trade chip).
chrome.render_header("POSITION", "CALCULATOR", "Bybit · USDT Perp", brand=False)


@st.cache_data(ttl=60, show_spinner=False)
def _calculator_account_summary() -> dict:
    try:
        if bybit.have_creds():
            return bybit.fetch_account_summary() or {}
    except Exception:
        return {}
    return {}

# --------------------------------------------------------------------------- #
# Styling — page gradient (folded in so there is ONE style element before the
# brand row, matching the dashboard's element order → identical heading position)
# + Orion card system + heavily-styled native inputs + SVG label classes
# --------------------------------------------------------------------------- #
st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
/* ---- Orion card (matches dashboard .dcard + purple-edge highlight) ---- */
.ocard{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:14px 16px;margin-bottom:12px;}
.ocard.tight{padding:12px 14px;}
/* consistent 12px gutters between every box — matches the Trade Dashboard's grid gap
   (Streamlit's default column gaps were wide and varied: ~32px medium / ~16px small) */
[data-testid="stHorizontalBlock"]{gap:12px!important;}
.chead{display:flex;align-items:center;justify-content:space-between;margin:0 0 9px;}
.chead .t{font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#8b94a0;}
.chead .ico{color:#8b94a0;font-size:13px;}

/* ---- Direction box: two stacked pill buttons (active filled / inactive outline) ---- */
.dirbox{height:100%;margin-bottom:0;display:flex;flex-direction:column;}
.dirbtns{flex:1;display:flex;flex-direction:column;justify-content:center;gap:9px;padding:2px 0 4px;}
.dbtn{border-radius:9999px;padding:9px 6px;text-align:center;font-weight:700;font-size:14px;
  border:2px solid;letter-spacing:.02em;white-space:nowrap;}
.dbtn.active{font-weight:800;}
.dbtn.inactive{background:transparent;border-width:1.5px;opacity:1;}
/* active side = solid-fill pill (Long green, Short red); inactive = neutral grey outline */
.dbtn.long.active{background:#0ecb81;border-color:#0ecb81;color:#08120c;}
.dbtn.short.active{background:#f6465d;border-color:#f6465d;color:#ffffff;}
.dbtn.long.inactive,.dbtn.short.inactive{border-color:#2a323c;color:#8b94a0;}
/* ---- Blank-calc interactive Direction box — the same stacked Long/Short solid-fill pills,
   clickable to set the trade direction. ---- */
.st-key-dirseg{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:14px 16px;min-height:190px;height:100%;display:flex!important;flex-direction:column!important;}
.st-key-dirseg .chead{margin:0 0 9px;}
.st-key-dirbtns{flex:1!important;justify-content:center!important;gap:9px!important;}
/* make each button fill the box width so border-radius reads as a PILL, not a circle */
.st-key-dirbtns [data-testid="stElementContainer"],
.st-key-dirbtns [data-testid="stButton"]{width:100%!important;}
.st-key-dirseg button{width:100%!important;border-radius:9999px!important;border:2px solid #2a323c!important;
  background:transparent!important;color:#8b94a0!important;font-weight:700!important;font-size:14px!important;
  min-height:0!important;height:auto!important;padding:7px 6px!important;line-height:1.1!important;
  white-space:nowrap!important;transition:none!important;}
.st-key-dirseg button p{white-space:nowrap!important;line-height:1.1!important;margin:0!important;}
.st-key-dirlong_on button,.st-key-dirlong_on button:hover{background:#0ecb81!important;
  border-color:#0ecb81!important;color:#08120c!important;font-weight:800!important;}
.st-key-dirshort_on button,.st-key-dirshort_on button:hover{background:#f6465d!important;
  border-color:#f6465d!important;color:#ffffff!important;font-weight:800!important;}
.st-key-dirlong_off button:hover,.st-key-dirshort_off button:hover{border-color:#3a4250!important;color:#cdd3da!important;}
/* ---- P&L box (where the leverage box was) ---- */
.pnlbox{height:100%;margin-bottom:0;display:flex;flex-direction:column;}
.pnlrows{flex:1;display:flex;flex-direction:column;justify-content:center;gap:2px;}
.pnlrow{display:flex;align-items:baseline;gap:3px;font-size:14.5px;padding:3px 0;}
.pnlrow .pl{color:#8b94a0;flex:1;white-space:nowrap;}
.pnlrow b{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;min-width:56px;text-align:right;}
.pnlrow .pos{color:#0ecb81;} .pnlrow .neg{color:#f6465d;}
.pnlrow .roe{font-size:9.5px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;min-width:28px;text-align:right;}
.pnlrow .rr{font-size:12.5px;font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap;
  border-radius:5px;padding:1px 6px;border:1px solid;line-height:16px;}
.pnlrow .rr.ok{color:#0ecb81;border-color:rgba(14,203,129,.5);background:rgba(14,203,129,.10);}
.pnlrow .rr.lo{color:#e0a33e;border-color:rgba(224,163,62,.5);background:rgba(224,163,62,.10);}
.pnlrow .rr.base{color:#6b747e;border-color:#2a323c;}
.pnlcap{font-size:9px;color:#6b747e;margin-top:6px;line-height:1.4;}
/* make the top-strip boxes fill the row height (the account box is the tallest and
   sets it) so live price / direction / leverage / account all line up */
[data-testid="stColumn"]:has(.hmain) [data-testid="stLayoutWrapper"],
[data-testid="stColumn"]:has(.hmain) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.hmain) [data-testid="stElementContainer"],
[data-testid="stColumn"]:has(.hmain) [data-testid="stMarkdown"],
[data-testid="stColumn"]:has(.hmain) [data-testid="stMarkdownContainer"],
[data-testid="stColumn"]:has(.hmain) .dash,
[data-testid="stColumn"]:has(.dirbox) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.dirbox) [data-testid="stElementContainer"],
[data-testid="stColumn"]:has(.dirbox) [data-testid="stMarkdown"],
[data-testid="stColumn"]:has(.dirbox) [data-testid="stMarkdownContainer"],
[data-testid="stColumn"]:has(.pnlbox) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.pnlbox) [data-testid="stElementContainer"],
[data-testid="stColumn"]:has(.pnlbox) [data-testid="stMarkdown"],
[data-testid="stColumn"]:has(.pnlbox) [data-testid="stMarkdownContainer"]{height:100%;}
/* leverage box (keyed container) stretches to the account box's height in the top strip
   — the height chain runs column → stVerticalBlock → stLayoutWrapper → lev_card */
[data-testid="stColumn"]:has(.st-key-lev_card) [data-testid="stLayoutWrapper"],
[data-testid="stColumn"]:has(.st-key-lev_card) [data-testid="stVerticalBlock"]{height:100%;}
.hmain{height:100%!important;}

/* ---- brand row (brand left + symbol chip / direction right), matches dashboard ---- */
.st-key-brandrow{justify-content:flex-start!important;margin-top:-20px!important;}
.st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-modestack){width:auto!important;
  flex:0 0 auto!important;}
/* ---- Mode toggles: two segmented controls stacked top-to-bottom, right-aligned in the brand
   row. Each shows BOTH options at once using the "direct" colour scheme — the ACTIVE segment
   gets light shading + a bold label + a coloured border; the inactive segment stays a plain
   light-bordered, muted-label chip. (No dark "inverted" fill, no sliding knob, no heading.) */
.st-key-modestack{flex-direction:column!important;align-items:center!important;gap:6px!important;
  width:250px!important;margin:0!important;align-self:center!important;
  --rocket-icon:url("data:image/svg+xml,%3Csvg%20id%3D%22Layer_1%22%20enable-background%3D%22new%200%200%20100%20100%22%20viewBox%3D%220%200%20100%20100%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20d%3D%22m69.4420853%2055.0907669c.3093185-.3093224.6104965-.6105003.9035263-.9198227%2015.2300338-15.5392609%2024.7701111-33.2356472%2027.1144333-48.0342378.3337708-2.1082358-1.4732895-3.9152954-3.5734711-3.5897741-14.8310852%202.3281316-32.5193215%2011.8600568-48.0586815%2027.1062888-.3092232.293129-.6185493.6024532-.9197235.9036293-7.9120712%207.8957748-14.3183594%2016.3694572-19.0396061%2024.7863045-.3418179.5860596-.6592903%201.163868-.9685154%201.7338295l18.0300522%2018.0137596c.5617142-.301178%201.1477699-.610405%201.7255783-.9441757l-.0081444-.0081482c8.4086952-4.7130966%2016.8824806-11.135582%2024.7945519-19.0476532zm-12.0635605-12.4705582c-3.4919968-3.4919968-3.4918976-9.1575165-.008049-12.641367%203.4920998-3.4758015%209.1575165-3.4758015%2012.6333237%200%203.4919968%203.4919987%203.4838486%209.149271-.0082474%2012.641367-3.475708%203.4757042-9.1330758%203.4839516-12.6170273%200z%22%2F%3E%3Cpath%20d%3D%22m40.7724648%2029.6501007c-7.2461472%207.4848251-13.3104248%2015.5427399-18.0139179%2023.9108009-.2507.429821-.4894009.8476334-.7045002%201.265419l-18.4300307-2.5223732c-1.0637298-.1455841-1.5013576-1.445713-.7421751-2.2048988l20.0686836-20.0686855c.2435417-.2435417.5738544-.3803596.9182739-.3803577z%22%2F%3E%3Cpath%20d%3D%22m70.3422318%2059.2198677v16.9023399c0%20.3444138-.1368179.6747284-.3803558.9182663l-20.0688783%2020.0688782c-.7591515.7591476-2.0592232.3216019-2.2048836-.7420731l-2.5222054-18.4178543c.4178314-.2147217.8356438-.4418106%201.2414398-.6805115l1.8264313-1.0387421v-.0239791c7.7119865-4.5360947%2015.1369476-10.2425613%2022.1082611-16.9865036z%22%2F%3E%3Cpath%20d%3D%22m35.2703781%2076.0027313c0%205.9651108-8.7728138%2012.6053391-14.7364578%2011.7554703%203.0986824-2.0655518%204.7898693-5.1770172%205.3073807-9.1604004-5.7881203%206.3263092-13.6118832%2010.4531555-22.658247%2013.2589111%2013.7874956-13.7874985%205.4616909-19.8366547%2019.8135834-28.1277275z%22%2F%3E%3C%2Fsvg%3E");
  --preloaded-icon:url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20version%3D%221.1%22%20xmlns%3Axlink%3D%22http%3A%2F%2Fwww.w3.org%2F1999%2Fxlink%22%20width%3D%22512%22%20height%3D%22512%22%20x%3D%220%22%20y%3D%220%22%20viewBox%3D%220%200%2032%2032%22%20style%3D%22enable-background%3Anew%200%200%20512%20512%22%20xml%3Aspace%3D%22preserve%22%3E%3Cg%20transform%3D%22matrix%286.123233995736766e-17%2C-1%2C1%2C6.123233995736766e-17%2C0.47075366973876775%2C31.529248237609863%29%22%3E%3Cpath%20d%3D%22M9.16%2014.86a1%201%200%200%201%201.51-1.31L15%2018.5V5a1%201%200%200%201%202%200v13.5l4.33-4.95a1%201%200%200%201%201.51%201.31l-6.09%207a1%201%200%200%201-1.5%200zM27%2022.05a1%201%200%200%200-1%201v1.19c0%20.38-.5.81-1.22.81H7.22c-.72%200-1.22-.43-1.22-.81v-1.19a1%201%200%200%200-2%200v1.19a3%203%200%200%200%203.22%202.81h17.56A3%203%200%200%200%2028%2024.24v-1.19a1%201%200%200%200-1-1z%22%20data-name%3D%22Layer%2041%22%20fill%3D%22%23000000%22%20opacity%3D%221%22%20data-original%3D%22%23000000%22%3E%3C%2Fpath%3E%3C%2Fg%3E%3C%2Fsvg%3E");}
/* each control is a row of two equal segments, butted together (no gap) */
.st-key-sizeseg,.st-key-ctxseg{flex-direction:row!important;gap:0!important;width:250px!important;
  align-items:stretch!important;}
.st-key-sizeseg > [data-testid="stElementContainer"],
.st-key-ctxseg > [data-testid="stElementContainer"]{flex:1 1 0!important;width:auto!important;min-width:0!important;}
/* base segment button */
.st-key-modestack button{width:100%!important;height:34px!important;min-height:0!important;font-size:11px!important;
  letter-spacing:.01em;padding:0 0.35rem!important;white-space:nowrap!important;transition:none!important;
  border:1px solid #2a323c!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:5px!important;}
.st-key-modestack button p{line-height:1!important;margin:0!important;white-space:nowrap!important;}
.st-key-modestack button::before{content:"";display:inline-block;width:13px;height:13px;flex:0 0 13px;background:currentColor;}
/* round only the OUTER corners; overlap the shared inner edge so it reads as one divider */
.st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(1) button,
.st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(1) button{border-radius:999px 0 0 999px!important;}
.st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(2),
.st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(2){margin-left:-1px!important;}
.st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(2) button,
.st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(2) button{border-radius:0 999px 999px 0!important;}
.st-key-segrisk_on button::before,.st-key-segrisk_off button::before{
  -webkit-mask:url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M12 2 4.5 5.2v5.7c0 4.7 3.1 8.9 7.5 11.1 4.4-2.2 7.5-6.4 7.5-11.1V5.2L12 2Zm3.5 8-4.2 4.2-2.1-2.1-1.4 1.4 3.5 3.5 5.6-5.6L15.5 10Z'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M12 2 4.5 5.2v5.7c0 4.7 3.1 8.9 7.5 11.1 4.4-2.2 7.5-6.4 7.5-11.1V5.2L12 2Zm3.5 8-4.2 4.2-2.1-2.1-1.4 1.4 3.5 3.5 5.6-5.6L15.5 10Z'/%3E%3C/svg%3E") center/contain no-repeat;}
.st-key-segexp_on button::before,.st-key-segexp_off button::before{
  -webkit-mask:var(--rocket-icon) center/contain no-repeat;mask:var(--rocket-icon) center/contain no-repeat;}
.st-key-segpush_on button::before,.st-key-segpush_off button::before{
  -webkit-mask:var(--preloaded-icon) center/contain no-repeat;mask:var(--preloaded-icon) center/contain no-repeat;}
.st-key-segblank_on button::before,.st-key-segblank_off button::before{
  -webkit-mask:url("data:image/svg+xml,%3Csvg%20id=%22Layer_1%22%20viewBox=%220%200%2024%2024%22%20xmlns=%22http://www.w3.org/2000/svg%22%20data-name=%22Layer%201%22%3E%3Cpath%20d=%22m8.62549%202.64648a.49983.49983%200%200%201%200%20.707l-5.272%205.272a.49995.49995%200%200%201%20-.707-.707l5.272-5.272a.49982.49982%200%200%201%20.707%200zm5.65722%200-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm6.1709.89991a.4998.4998%200%200%200%20-.707%200l-16.20022%2016.20019a.49995.49995%200%201%200%20.707.707l16.20022-16.20016a.4998.4998%200%200%200%200-.70703zm.19287%205.46386-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm0%206.36426-5.272%205.272a.49995.49995%200%201%200%20.707.707l5.272-5.272a.49995.49995%200%200%200%20-.707-.707z%22/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg%20id=%22Layer_1%22%20viewBox=%220%200%2024%2024%22%20xmlns=%22http://www.w3.org/2000/svg%22%20data-name=%22Layer%201%22%3E%3Cpath%20d=%22m8.62549%202.64648a.49983.49983%200%200%201%200%20.707l-5.272%205.272a.49995.49995%200%200%201%20-.707-.707l5.272-5.272a.49982.49982%200%200%201%20.707%200zm5.65722%200-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm6.1709.89991a.4998.4998%200%200%200%20-.707%200l-16.20022%2016.20019a.49995.49995%200%201%200%20.707.707l16.20022-16.20016a.4998.4998%200%200%200%200-.70703zm.19287%205.46386-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm0%206.36426-5.272%205.272a.49995.49995%200%201%200%20.707.707l5.272-5.272a.49995.49995%200%200%200%20-.707-.707z%22/%3E%3C/svg%3E") center/contain no-repeat;}
/* INACTIVE segment — transparent fill, light border, muted label */
.st-key-modestack [class*="seg"][class*="_off"] button{background:transparent!important;
  color:#8b94a0!important;font-weight:600!important;}
.st-key-modestack [class*="seg"][class*="_off"] button:hover{color:#cdd3da!important;
  border-color:#3a4250!important;background:rgba(255,255,255,.02)!important;}
/* ACTIVE segment — light shading + bold + coloured border, raised so its border wins the overlap */
.st-key-modestack [class*="seg"][class*="_on"] button{position:relative!important;z-index:2!important;
  font-weight:800!important;}
.st-key-segrisk_on button,.st-key-segrisk_on button:hover{background:rgba(14,203,129,.13)!important;
  border-color:#0ecb81!important;color:#0ecb81!important;}
.st-key-segexp_on button,.st-key-segexp_on button:hover{background:rgba(246,70,93,.13)!important;
  border-color:#f6465d!important;color:#f6465d!important;}
.st-key-segpush_on button,.st-key-segpush_on button:hover{background:rgba(76,141,255,.14)!important;
  border-color:#4c8dff!important;color:#4c8dff!important;}
.st-key-segblank_on button,.st-key-segblank_on button:hover{background:rgba(255,255,255,.10)!important;
  border-color:#e6e8eb!important;color:#ffffff!important;}
/* Sizing-mode ⓘ info icon — hover reveals the explanation, styled like the FUNDING (8H)
   tooltip in the scanner. Replaces the button's disruptive on-hover help. */
.modeinfo{position:relative;display:inline-flex;align-items:center;justify-content:center;
  width:17px;height:17px;border-radius:50%;border:1px solid #3a4250;color:#8b94a0;
  font-size:11px;font-weight:700;font-style:italic;font-family:Georgia,'Times New Roman',serif;
  cursor:help;text-transform:none;letter-spacing:normal;line-height:1;}
.modeinfo:hover{color:#cdd3da;border-color:#4c8dff;}
.modeinfo-tip{position:absolute;top:150%;right:0;left:auto;z-index:1000;
  display:none;width:340px;padding:11px 13px;background:#15181f;border:1px solid #2a2f37;
  border-radius:6px;color:#cbd2da;font-size:12px;font-weight:400;font-style:normal;
  line-height:1.5;letter-spacing:normal;text-transform:none;text-align:left;white-space:normal;
  box-shadow:0 6px 20px rgba(0,0,0,.45);}
.modeinfo:hover .modeinfo-tip{display:block;}
.modeinfo-tip .ti-h{font-weight:700;color:#e6e8eb;margin-bottom:7px;}
.modeinfo-tip .ti-r{margin-bottom:6px;}
.modeinfo-tip .ti-r:last-child{margin-bottom:0;}
.modeinfo-tip b{color:#e6e8eb;}

/* ---- input cards (keyed containers) ---- */
.st-key-inputs_card,.st-key-acct_card{background:#13101e;border:1px solid rgba(139,92,246,.38);
  border-radius:10px;box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:8px 16px 16px;}
.st-key-acct_card{height:100%;padding-top:14px;min-height:190px;}
/* Pin BOTH modes' top-strip right-zone boxes to the SAME min-height so the top row is the same
   height in Risk-Safe and Exposure mode at any viewport width (no jolt when toggling). At
   narrower widths the risk-mode Account box reflows taller, so the floor must cover that. */
.st-key-acct_card:has(.acct-exp){gap:0.45rem!important;min-height:190px;}
/* extend the Trade Inputs + Trade Visualization boxes to the full row height, so both
   reach the bottom of the (taller) Position Summary + Position Quality column */
[data-testid="stColumn"]:has(.st-key-inputs_card) [data-testid="stLayoutWrapper"],
[data-testid="stColumn"]:has(.st-key-inputs_card) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.vizrel) [data-testid="stLayoutWrapper"],
[data-testid="stColumn"]:has(.vizrel) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.vizrel) [data-testid="stElementContainer"],
[data-testid="stColumn"]:has(.vizrel) [data-testid="stMarkdown"],
[data-testid="stColumn"]:has(.vizrel) [data-testid="stMarkdownContainer"]{height:100%;}
.st-key-inputs_card{height:100%;}
[data-testid="stColumn"]:has(.vizrel) .ocard{height:100%;}
/* account fields are type-only (no +/- steppers) so the value stays readable in the
   narrow ~30% box and the two fields fit side by side */
.st-key-acct_card [data-testid="stNumberInputStepUp"],
.st-key-acct_card [data-testid="stNumberInputStepDown"]{display:none!important;}
/* tighter input padding so values fit in the narrower (75%) Account box */
.st-key-acct_card [data-testid="stNumberInput"] input{padding-left:7px!important;padding-right:3px!important;}
/* compress the Account box vertically so exposure mode (which stacks an extra margin × lev
   input row) ends up the SAME height as the risk-mode top row */
.st-key-acct_card [data-testid="stVerticalBlock"]{gap:0.5rem!important;}
.st-key-acct_card .acct-exp{margin-bottom:4px;padding-bottom:4px;}
.st-key-acct_card .acct-exp .ae-kpi{gap:2px;}
.st-key-acct_card .acct-exp .ae-kpi{gap:2px;}
.st-key-acct_card .acct-exp .ae-kpi b{font-size:19px;}
.st-key-acct_card .acct-exp .c .lq{font-weight:700;}
.st-key-acct_card [data-testid="stNumberInput"] label,
.st-key-acct_card .stWidgetLabel{margin:0!important;padding:0!important;min-height:0!important;}
.st-key-acct_card .stWidgetLabel p{line-height:1!important;}
.st-key-acct_card [data-testid="stNumberInput"] div[data-baseweb="input"]{min-height:28px!important;}
.st-key-acct_card [data-testid="stNumberInputContainer"]{min-height:0!important;height:28px!important;}
.st-key-acct_card [data-testid="stNumberInput"] input{padding-top:2px!important;padding-bottom:2px!important;line-height:1.1!important;}
/* exposure mode: the split-out Account box (Balance + Margin %) — card + compact inputs */
.st-key-account_card{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);height:100%;padding:14px 16px 16px;gap:0.45rem!important;min-height:190px;}
[data-testid="stColumn"]:has(.st-key-account_card) [data-testid="stLayoutWrapper"],
[data-testid="stColumn"]:has(.st-key-account_card) [data-testid="stVerticalBlock"]{height:100%;}
.st-key-account_card [data-testid="stNumberInputStepUp"],
.st-key-account_card [data-testid="stNumberInputStepDown"]{display:none!important;}
.st-key-account_card [data-testid="stNumberInput"] input{padding-left:7px!important;padding-right:3px!important;}
.st-key-account_card [data-testid="stVerticalBlock"]{gap:0.35rem;}
.st-key-account_card .stWidgetLabel{margin:0!important;padding:0!important;min-height:0!important;}
.st-key-account_card .stWidgetLabel p{line-height:1!important;}
.st-key-account_card [data-testid="stNumberInputContainer"]{min-height:0!important;height:28px!important;}
.st-key-account_card [data-testid="stNumberInput"] div[data-baseweb="input"]{min-height:28px!important;}
.st-key-account_card [data-testid="stNumberInput"] input{padding-top:2px!important;padding-bottom:2px!important;line-height:1.1!important;}
[data-testid="stNumberInput"] label p{font-size:9.5px!important;
  font-weight:700!important;letter-spacing:.06em;color:#8b94a0!important;text-transform:uppercase;}
[data-testid="stNumberInput"] input{background:#11151b!important;
  color:#dfe3e8!important;font-weight:700!important;font-variant-numeric:tabular-nums;}
/* trade-input value colours: entry green, stop red, targets blue (keyed per symbol) */
[class*="st-key-entry_"] input{color:#ffffff!important;}
[class*="st-key-stop_"] input{color:#f6465d!important;}
[class*="st-key-t1_"] input{color:#0ecb81!important;}
[class*="st-key-t2_"] input{color:#0ecb81!important;}
[data-testid="stNumberInput"] div[data-baseweb="input"]{background:#11151b!important;
  border:1px solid #232a33!important;border-radius:8px!important;}
[data-testid="stNumberInputStepUp"],
[data-testid="stNumberInputStepDown"]{background:#15181f!important;
  color:#8b94a0!important;border-color:#232a33!important;}
/* Restore Trade Plan is the only non-direction button allowed inside pushed Trade Input. */
.st-key-inputs_actions [data-testid="stButton"]{display:flex;justify-content:center;width:100%;}
.st-key-inputs_actions [data-testid="stElementContainer"]:has([data-testid="stButton"]){
  margin-top:8px;margin-bottom:0;width:100%;}
.st-key-restorebtn button{border-radius:9999px!important;
  border:1px solid rgba(230,232,235,.2)!important;background:transparent!important;
  color:#e6e8eb!important;font-weight:500!important;min-height:0!important;padding:0.25rem 0.85rem!important;
  width:auto!important;white-space:nowrap!important;}
.st-key-restorebtn button:hover{border-color:#4c8dff!important;
  color:#4c8dff!important;background:transparent!important;}
/* Bottom actions group (Push to Journal + clear/restore) — centred as one block in the
   leftover space, buttons stacked with a small gap. */
.st-key-inputs_actions{margin-top:auto!important;margin-bottom:auto!important;
  gap:8px!important;align-items:center!important;width:100%!important;}
.st-key-inputs_actions [data-testid="stElementContainer"]:has([data-testid="stButton"]){
  margin:0!important;width:100%!important;display:flex!important;justify-content:center!important;}
/* Push to Journal inherits the generic Restore-Trade-Plan pill style (transparent + outline). */
/* account card: the monetary "capital at risk" figure (e.g. 1% of 10,000 = $100) */
.acct-risk{display:flex;align-items:baseline;gap:10px;margin:0 0 14px;padding-bottom:12px;
  border-bottom:1px solid #161b21;font-size:12px;color:#8b94a0;}
.acct-risk b{font-size:22px;font-weight:800;color:#4c8dff;font-variant-numeric:tabular-nums;line-height:1;}
.acct-risk .l{font-weight:700;}
.acct-risk .c{color:#6b747e;font-size:11px;margin-left:auto;}
/* exposure headline: two KPIs — Exposure (left) + Risk at stop (right, red) — numbers aligned */
.acct-exp{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;
  margin:0 0 14px;padding-bottom:12px;border-bottom:1px solid #161b21;}
.acct-exp .ae-kpi{display:flex;flex-direction:column;gap:5px;}
.acct-exp .ae-kpi .l{font-weight:700;color:#8b94a0;font-size:12px;white-space:nowrap;}
.acct-exp .ae-kpi b{font-size:22px;font-weight:800;color:#4c8dff;font-variant-numeric:tabular-nums;
  line-height:1;white-space:nowrap;}
.acct-exp .ae-kpi .c{color:#6b747e;font-size:11px;margin-top:1px;}
.acct-exp .ae-kpi .c.rasl{margin-top:4px;}
.acct-exp .ae-kpi .c.rasl b.neg{color:#f6465d;font-size:12.5px;font-weight:800;font-variant-numeric:tabular-nums;}
/* Margin Allocation headline: two downside figures (Risk at Stop / Risk at Liquidation) */
.malloc-risks{display:flex;flex-direction:column;gap:3px;}
.malloc-risks .risk-row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;}
.malloc-risks .risk-row .l{font-size:12px;font-weight:700;color:#8b94a0;white-space:nowrap;}
.malloc-risks .risk-row b{font-size:17px;font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap;}
.malloc-risks .risk-row b.neg{color:#f6465d;}
.malloc-risks .risk-row b.liq{color:#e0a33e;}
.st-key-acct_card .lev-ic{font-size:16px;line-height:1;}
/* risk mode nests Leverage|Account inside the right zone — stretch the nested cells full height */
[data-testid="stColumn"]:has(>div>[data-testid="stVerticalBlock"]>[data-testid="stColumn"] .st-key-acct_card){align-self:stretch;}

/* Blank-calc skeleton — muted "—" placeholders so every box shows its FULL structure at its
   final size before any levels are entered, then fills in as you type. */
.srow .v.skel,.pnlrow b.skel,.pnlrow .roe.skel,.wr-n.skel,.mm-v.skel,.wr-e.skel{color:#4d5663!important;}
.srow .rrpill.skel,.pnlrow .rr.skel{color:#4d5663!important;border-color:#2a323c!important;
  background:transparent!important;}

/* ---- summary rows (matches .statrow / .kvrow) ---- */
.srow{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:7px 0;
  border-bottom:1px solid #161b21;font-size:14.5px;line-height:1.35;}
.srow:last-child{border-bottom:none;}
.srow .k{color:#8b94a0;min-width:0;padding-top:1px;}
.srow .v{font-weight:700;color:#cdd3da;font-variant-numeric:tabular-nums;text-align:right;
  min-width:0;max-width:58%;display:flex;flex-direction:column;align-items:flex-end;gap:2px;}
.srow .vm{display:block;white-space:nowrap;font-size:16px;font-weight:740;line-height:1.12;}
.srow.has-tail .vm{display:flex;align-items:center;justify-content:flex-end;gap:6px;}
.srow .vd{display:block;color:#8b94a0;font-size:12px;font-weight:650;line-height:1.2;white-space:nowrap;}
.srow .v.red{color:#f6465d;} .srow .v.green{color:#0ecb81;} .srow .v.blue{color:#4c8dff;}
.srow .v.amber{color:#e0a33e;} .srow .v.white{color:#ffffff;}
.srow .u{color:#8b94a0;font-weight:600;font-size:12px;margin-left:3px;}
/* R:R pill sitting to the right of its reward value (merged from the old R:R rows) */
.srow .rrpill{margin-left:0;font-size:16px;font-weight:800;color:#4c8dff;
  border:1px solid rgba(76,141,255,.45);background:rgba(76,141,255,.10);border-radius:5px;
  padding:1px 6px;font-variant-numeric:tabular-nums;white-space:nowrap;line-height:18px;display:inline-block;}
/* liquidation-inside-stop danger banner in the Position Summary */
.liqwarn{margin-top:11px;padding:8px 11px;border-radius:8px;font-size:11.5px;line-height:1.5;
  background:rgba(246,70,93,.10);border:1px solid rgba(246,70,93,.42);color:#f3a4ad;}

/* ---- score / checklist (matches .vbaction / .wchecks) ---- */
.scoreflex{flex:1;display:flex;align-items:center;justify-content:center;gap:14px;}
.scoreflex .scoregauge{flex:0 1 44%;min-width:0;display:flex;flex-direction:column;justify-content:center;}
.scoreflex .scorechecks{flex:0 1 auto;min-width:0;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;}
/* score sitting inside the semicircle gauge — 31px SVG renders ≈14.5px (Reward → TP1 size) */
.gsn{font-size:31px;font-weight:800;font-variant-numeric:tabular-nums;font-family:inherit;}
.gso{font-size:13px;font-weight:700;fill:#8b94a0;font-family:inherit;}
/* Position Quality Score (small gauge left of the checklist) + Break-even Win Rate (right) under the
   Position Summary, in the narrower account-sized box (tighter padding for room) */
.quality-row{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,3fr);gap:10px;align-items:stretch;margin-top:10px;}
.quality-row .ocard{margin:0!important;}
.scorecard{height:100%;padding:14px 11px;display:flex;flex-direction:column;}
/* Break-even Win Rate box — compact companion to the wider quality score card */
.wrcard{height:100%;display:flex;flex-direction:column;padding:14px 10px;}
.wrcard .chead{margin:0 0 6px;}
.wrcard .chead .t{font-size:8.5px;letter-spacing:.02em;white-space:normal;line-height:1.15;}
.wrmid{flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;gap:1px;}
.wr-n{font-size:21px;font-weight:800;color:#4c8dff;font-variant-numeric:tabular-nums;line-height:1.05;}
.wr-s{font-size:8.5px;color:#8b94a0;text-transform:uppercase;letter-spacing:.05em;}
.wr-e{font-size:12px;font-weight:700;margin-top:6px;line-height:1.3;}
.wr-e.green{color:#0ecb81;} .wr-e.amber{color:#e0a33e;}
/* Market Moves box (exposure mode) — four price-move → P&L rows, stacked + centred */
.mmcard .mmlist{flex:1;display:flex;flex-direction:column;justify-content:center;gap:9px;}
.mm-row{display:flex;flex-direction:column;align-items:center;text-align:center;line-height:1.18;}
.mm-l{font-size:9px;color:#8b94a0;white-space:nowrap;}
.mm-v{font-size:15px;font-weight:800;font-variant-numeric:tabular-nums;margin-top:1px;}
.mm-v.pos{color:#0ecb81;} .mm-v.neg{color:#f6465d;}
.quality-row .scorecard,.quality-row .wrcard{height:100%;}
.svhead{font-size:15px;font-weight:800;letter-spacing:.04em;margin:0 0 8px;}
.svhead.exc{color:#0ecb81;} .svhead.good{color:#4c8dff;} .svhead.fair{color:#e0a33e;} .svhead.bad{color:#f6465d;}
.ck{display:flex;align-items:center;gap:8px;font-size:12px;line-height:1.45;color:#cdd3da;padding:3px 0;}
.ck .i{width:15px;height:15px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:10px;font-weight:900;flex:0 0 auto;}
.ck .i.ok{background:rgba(14,203,129,.18);color:#0ecb81;}
.ck .i.no{background:rgba(246,70,93,.18);color:#f6465d;}

/* ---- visualization stats strip (inset boxes = #11151b) ---- */
.vstats{display:flex;gap:10px;margin-top:12px;}
.vstat{flex:1;background:#11151b;border:1px solid #232a33;border-radius:8px;padding:9px 12px;}
.vstat .l{font-size:9px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;}
.vstat .n{font-size:14px;font-weight:800;color:#dfe3e8;margin-top:3px;font-variant-numeric:tabular-nums;}
.vstat .n.red{color:#f6465d;} .vstat .n.green{color:#0ecb81;} .vstat .n.blue{color:#4c8dff;}
.posbadge{font-size:10px;font-weight:700;letter-spacing:.06em;padding:3px 9px;border-radius:5px;}
.posbadge.long{background:rgba(76,141,255,.12);color:#4c8dff;border:1px solid rgba(76,141,255,.4);}
.posbadge.short{background:rgba(246,70,93,.12);color:#f6465d;border:1px solid rgba(246,70,93,.4);}

/* ---- SVG text classes ---- */
/* trade-viz label boxes: small caption + price value (drawn inside the SVG) */
.vboxlab{font-size:9px;font-weight:800;letter-spacing:.03em;font-family:inherit;}
.vboxval{fill:#e8ebef;font-size:16px;font-weight:800;font-family:inherit;font-variant-numeric:tabular-nums;}
.gscore{fill:#ffffff;font-size:17px;font-weight:800;font-family:inherit;}
.gden{fill:#9a93c0;font-size:8px;font-weight:700;font-family:inherit;}

/* trade-viz overlay text (HTML over the SVG) — fixed font sizes, positioned by % so they
   track each level but never scale with the chart width */
.vizrel{position:relative;}
.vpctlabel{position:absolute;left:80.8%;transform:translateY(-50%);font-size:14.5px;font-weight:800;
  font-variant-numeric:tabular-nums;line-height:1;white-space:nowrap;}
.vliqpct{position:absolute;left:88%;transform:translateY(-50%);font-size:11px;font-weight:800;
  font-variant-numeric:tabular-nums;line-height:1;white-space:nowrap;}
/* LIQ label centred on the chart's arrow column (ax ≈ 40.1% of the SVG width) */
.vliqtxt{position:absolute;left:40.1%;transform:translate(-50%,-108%);font-size:12px;font-weight:800;
  letter-spacing:.03em;text-transform:uppercase;font-variant-numeric:tabular-nums;line-height:1;white-space:nowrap;}

/* ---- metrics strip (matches .dcard recipe) ---- */
.mcard{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);padding:14px 16px;height:100%;}
.mcard .ic{font-size:17px;}
.mcard .cap{font-size:9.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;margin:6px 0 2px;}
.mcard .big{font-size:26px;font-weight:800;color:#e6e8eb;line-height:1.05;font-variant-numeric:tabular-nums;}
.mcard .big.red{color:#f6465d;} .mcard .big.green{color:#0ecb81;} .mcard .big.blue{color:#4c8dff;} .mcard .big.amber{color:#e0a33e;}
.mcard .sub{font-size:12px;font-weight:700;margin-top:4px;}
.mcard .sub.green{color:#0ecb81;} .mcard .sub.amber{color:#e0a33e;} .mcard .sub.red{color:#f6465d;} .mcard .sub.muted{color:#8b94a0;}
.mcard .fine{font-size:11px;color:#8b94a0;margin-top:2px;}

/* ---- editable Leverage box (top strip, beside Account; ~25% of its width) ---- */
/* heading pinned at the top (same Y as Direction/P&L); ⚡ + number + quality centred
   in the space below — so the heading lands in exactly the same place as the others */
.st-key-lev_card{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:14px 8px;height:100%;min-height:190px;display:flex;flex-direction:column;}
.st-key-lev_card .chead{margin:0;}
/* ⚡ pinned to the top-right of the heading row (mirrors the LIVE badge in the price box) */
.st-key-lev_card .lev-ic{font-size:16px;line-height:1;}
/* centre the number + quality cluster in the space below the heading row */
.st-key-lev_card [data-testid="stElementContainer"]:has([data-testid="stNumberInput"]){margin-top:auto;}
.st-key-lev_card [data-testid="stElementContainer"]:has(.lev-fine){margin-bottom:auto;}
.st-key-lev_card [data-testid="stNumberInput"]{width:100%;}
.st-key-lev_card [data-testid="stNumberInputStepUp"],
.st-key-lev_card [data-testid="stNumberInputStepDown"]{display:none!important;}
.st-key-lev_card [data-testid="stNumberInputContainer"]{position:relative;}
.st-key-lev_card [data-testid="stNumberInput"] div[data-baseweb="input"]{padding:0!important;}
.st-key-lev_card [data-testid="stNumberInput"] input{font-size:18px!important;font-weight:800!important;
  color:#4c8dff!important;padding:2px 17px 2px 4px!important;text-align:right;}
/* persistent "×" suffix on the value (display only — never touches the editable number) */
.st-key-lev_card [data-testid="stNumberInputContainer"]::after{content:"×";position:absolute;
  right:5px;top:50%;transform:translateY(-50%);color:#4c8dff;font-weight:800;font-size:18px;
  line-height:1;pointer-events:none;}
.st-key-lev_card .lev-sub{font-size:11px;font-weight:700;margin-top:7px;line-height:1.2;}
.st-key-lev_card .lev-fine{font-size:9px;color:#8b94a0;line-height:1.3;margin-top:2px;}
/* exposure mode: the margin × leverage equation row folded into the Account box */
.acct_card .mx-op,.st-key-acct_card .mx-op{font-size:20px;font-weight:800;color:#7a8290;
  text-align:center;line-height:1;padding-bottom:8px;transform:translateY(-16px);}
.st-key-acct_card .mx-desc{font-size:9.5px;font-weight:700;line-height:1.3;margin-top:7px;}
.st-key-acct_card .mx-desc span{color:#8b94a0;font-weight:400;}

/* ---- footer ---- */
.cfoot{display:flex;justify-content:space-between;align-items:center;color:#8b94a0;font-size:12px;
  border-top:1px solid #232a33;margin-top:6px;padding-top:12px;}
.cfoot b{color:#cdd3da;}
/* second footer row — the sizing-mode ⓘ explainer, sitting just under the risk disclaimer
   (no second divider, left-aligned beneath the "Always ensure…" line) */
.cfoot-mode{border-top:none!important;margin-top:0!important;padding-top:6px!important;
  justify-content:flex-start!important;}
.cfoot-modeline{display:inline-flex;align-items:center;gap:7px;}
.cfoot-modeline i{font-style:italic;color:#6b747e;}
/* the footer ⓘ sits at the bottom of the page, so its tooltip opens UPWARD + left-aligned */
.modeinfo-tip.up{top:auto;bottom:150%;right:auto;left:0;}
.ctx-cap{color:#8b94a0;font-size:12px;margin:2px 0 10px;font-variant-numeric:tabular-nums;}
@media(max-width:700px){
  html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"]{overflow-x:hidden!important;}
  .st-key-brandrow{margin-top:-66px!important;gap:8px!important;min-height:0!important;
    align-items:stretch!important;flex-wrap:wrap!important;}
  .st-key-brandrow [data-testid="stElementContainer"]:has(.orion-brand){display:none!important;}
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-mobile_price_symbol_stack){width:48%!important;flex:0 0 calc(48% - 4px)!important;
    height:auto!important;margin:0!important;}
  .st-key-mobile_price_symbol_stack{display:flex!important;flex-direction:column!important;gap:7px!important;width:100%!important;margin:0!important;}
  .st-key-brandrow [data-testid="stElementContainer"]:has(.mobile-live-ticker){width:100%!important;flex:1 1 auto!important;
    height:72px!important;margin:0!important;}
  .st-key-brandrow [data-testid="stMarkdown"]:has(.mobile-live-ticker),
  .st-key-brandrow [data-testid="stMarkdownContainer"]:has(.mobile-live-ticker){height:100%!important;margin:0!important;}
  .mobile-live-ticker{display:flex!important;height:72px;flex-direction:column;justify-content:center;
    background:transparent;border:0;border-radius:0;box-shadow:none;
    padding:3px 2px;color:#dfe3e8;margin:0!important;position:relative;overflow:hidden;}
  .mlt-symbol{display:inline-flex;align-items:center;gap:6px;min-width:0;font-size:15px;font-weight:780;
    color:#f2f4f8;line-height:1;white-space:nowrap;}
  .mlt-price{font-size:30px;font-weight:800;line-height:1.02;color:#f2f4f8;margin-top:7px;font-variant-numeric:tabular-nums;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .mobile-live-ticker .livebadge{position:static;display:inline-flex;align-items:center;margin-left:1px;}
  .mobile-live-ticker .livebadge-svg{width:28px;height:28px;}
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-modestack){width:52%!important;flex:0 0 calc(52% - 4px)!important;}
  .st-key-brandrow [data-testid="stElementContainer"]:has(.mobile-risk-mini){width:100%!important;flex:1 1 auto!important;
    height:156px!important;margin:0!important;}
  .st-key-brandrow [data-testid="stMarkdown"]:has(.mobile-risk-mini),
  .st-key-brandrow [data-testid="stMarkdownContainer"]:has(.mobile-risk-mini){margin:0!important;}
  .st-key-modestack{width:100%!important;align-items:stretch!important;justify-content:flex-start!important;gap:5px!important;height:auto!important;}
  .st-key-sizeseg,.st-key-ctxseg{position:relative!important;width:100%!important;min-width:0!important;
    padding-top:0!important;gap:0!important;align-items:stretch!important;border:1px solid #2b3140!important;
    border-radius:999px!important;overflow:hidden!important;background:rgba(8,10,22,.22)!important;}
  .st-key-modestack button{height:31px!important;min-height:0!important;font-size:8px!important;
    padding:0 0.18rem!important;letter-spacing:0!important;font-weight:660!important;
    border:0!important;background:transparent!important;color:#8f96a3!important;
    display:flex!important;align-items:center!important;justify-content:center!important;gap:4px!important;}
  .st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(1) button,
  .st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(1) button{border-radius:999px 0 0 999px!important;}
  .st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(2) button,
  .st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(2) button{border-radius:0 999px 999px 0!important;}
  .st-key-modestack button p{line-height:1!important;margin:0!important;white-space:nowrap!important;}
  .st-key-modestack button::before{content:"";display:inline-block;width:12px;height:12px;flex:0 0 12px;
    background:currentColor;}
  .st-key-segrisk_on button::before,.st-key-segrisk_off button::before{
    -webkit-mask:url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M12 2 4.5 5.2v5.7c0 4.7 3.1 8.9 7.5 11.1 4.4-2.2 7.5-6.4 7.5-11.1V5.2L12 2Zm3.5 8-4.2 4.2-2.1-2.1-1.4 1.4 3.5 3.5 5.6-5.6L15.5 10Z'/%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M12 2 4.5 5.2v5.7c0 4.7 3.1 8.9 7.5 11.1 4.4-2.2 7.5-6.4 7.5-11.1V5.2L12 2Zm3.5 8-4.2 4.2-2.1-2.1-1.4 1.4 3.5 3.5 5.6-5.6L15.5 10Z'/%3E%3C/svg%3E") center/contain no-repeat;}
  .st-key-segblank_on button::before,.st-key-segblank_off button::before{
    background:currentColor;border:0;border-radius:0;
    -webkit-mask:url("data:image/svg+xml,%3Csvg%20id=%22Layer_1%22%20viewBox=%220%200%2024%2024%22%20xmlns=%22http://www.w3.org/2000/svg%22%20data-name=%22Layer%201%22%3E%3Cpath%20d=%22m8.62549%202.64648a.49983.49983%200%200%201%200%20.707l-5.272%205.272a.49995.49995%200%200%201%20-.707-.707l5.272-5.272a.49982.49982%200%200%201%20.707%200zm5.65722%200-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm6.1709.89991a.4998.4998%200%200%200%20-.707%200l-16.20022%2016.20019a.49995.49995%200%201%200%20.707.707l16.20022-16.20016a.4998.4998%200%200%200%200-.70703zm.19287%205.46386-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm0%206.36426-5.272%205.272a.49995.49995%200%201%200%20.707.707l5.272-5.272a.49995.49995%200%200%200%20-.707-.707z%22/%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg%20id=%22Layer_1%22%20viewBox=%220%200%2024%2024%22%20xmlns=%22http://www.w3.org/2000/svg%22%20data-name=%22Layer%201%22%3E%3Cpath%20d=%22m8.62549%202.64648a.49983.49983%200%200%201%200%20.707l-5.272%205.272a.49995.49995%200%200%201%20-.707-.707l5.272-5.272a.49982.49982%200%200%201%20.707%200zm5.65722%200-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm6.1709.89991a.4998.4998%200%200%200%20-.707%200l-16.20022%2016.20019a.49995.49995%200%201%200%20.707.707l16.20022-16.20016a.4998.4998%200%200%200%200-.70703zm.19287%205.46386-11.63623%2011.63623a.5.5%200%201%200%20.707.707l11.63627-11.63619a.5.5%200%201%200%20-.707-.707zm0%206.36426-5.272%205.272a.49995.49995%200%201%200%20.707.707l5.272-5.272a.49995.49995%200%200%200%20-.707-.707z%22/%3E%3C/svg%3E") center/contain no-repeat;}
  .st-key-segrisk_on button,.st-key-segrisk_on button:hover{background:rgba(14,203,129,.14)!important;
    box-shadow:inset 0 0 0 1px #0ecb81,0 0 16px rgba(14,203,129,.16)!important;color:#31e59a!important;}
  .st-key-segexp_on button,.st-key-segexp_on button:hover{background:rgba(246,70,93,.13)!important;
    box-shadow:inset 0 0 0 1px #f6465d,0 0 16px rgba(246,70,93,.16)!important;color:#ff6f81!important;}
  .st-key-segpush_on button,.st-key-segpush_on button:hover{background:rgba(76,111,255,.14)!important;
    box-shadow:inset 0 0 0 1px #4c6fff,0 0 16px rgba(76,111,255,.18)!important;color:#587dff!important;}
  .st-key-segblank_on button,.st-key-segblank_on button:hover{background:rgba(255,255,255,.10)!important;
    box-shadow:inset 0 0 0 1px #ffffff,0 0 16px rgba(255,255,255,.12)!important;color:#ffffff!important;}
  .st-key-inputs_card{position:relative!important;}
  .st-key-mobile_trade_dirswitch{display:block!important;position:absolute!important;z-index:6;top:26px;right:13px;
    width:158px!important;height:34px!important;min-height:34px!important;border:0!important;
    border-radius:0!important;overflow:visible!important;background:transparent!important;padding:0!important;}
  .st-key-mobile_trade_dirswitch [data-testid="stVerticalBlock"]{gap:0!important;height:100%!important;}
  .st-key-mobile_trade_dirswitch [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;gap:6px!important;width:100%!important;height:100%!important;align-items:center!important;}
  .st-key-mobile_trade_dirswitch [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{width:auto!important;min-width:0!important;height:100%!important;}
  .st-key-mobile_trade_dirswitch [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1){flex:0 0 118px!important;width:118px!important;}
  .st-key-mobile_trade_dirswitch [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){flex:0 0 34px!important;width:34px!important;}
  .st-key-mobile_trade_dirswitch [data-testid="stElementContainer"],
  .st-key-mobile_trade_dirswitch [data-testid="stButton"]{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;}
  .st-key-mobile_trade_pair{position:relative!important;width:118px!important;height:34px!important;min-height:34px!important;
    border:1px solid rgba(139,92,246,.42)!important;border-radius:999px!important;background:#0d1119!important;
    padding:3px!important;overflow:hidden!important;box-sizing:border-box!important;}
  .st-key-mobile_trade_pair.stVerticalBlock{height:34px!important;min-height:34px!important;max-height:34px!important;}
  .st-key-mobile_trade_pair *, .st-key-mobile_trade_pair::before{box-sizing:border-box!important;}
  .st-key-mobile_trade_pair::before{content:"";position:absolute;z-index:0;top:3px;bottom:3px;width:55px;
    border-radius:999px;background:#0ecb81;box-shadow:0 0 14px rgba(14,203,129,.18);}
  .st-key-mobile_trade_pair:has(.st-key-mob_trade_dirlong_on)::before{left:3px;background:#0ecb81;box-shadow:0 0 14px rgba(14,203,129,.18);}
  .st-key-mobile_trade_pair:has(.st-key-mob_trade_dirshort_on)::before{right:3px;background:#f6465d;box-shadow:0 0 14px rgba(246,70,93,.18);}
  .st-key-mobile_trade_pair [data-testid="stVerticalBlock"]{height:100%!important;min-height:0!important;gap:0!important;}
  .st-key-mobile_trade_pair [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;gap:3px!important;height:100%!important;position:relative!important;z-index:1!important;}
  .st-key-mobile_trade_pair [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-mobile_trade_pair [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
  .st-key-mobile_trade_pair [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){flex:1 1 0!important;width:auto!important;height:100%!important;min-width:0!important;margin-left:0!important;}
  .st-key-mobile_trade_pair [data-testid="stElementContainer"],
  .st-key-mobile_trade_pair [data-testid="stButton"]{height:100%!important;width:100%!important;min-height:0!important;margin:0!important;}
  .st-key-mobile_trade_pair .st-key-mob_trade_dirlong_on,
  .st-key-mobile_trade_pair .st-key-mob_trade_dirlong_off,
  .st-key-mobile_trade_pair .st-key-mob_trade_dirshort_on,
  .st-key-mobile_trade_pair .st-key-mob_trade_dirshort_off{margin:0!important;}
  .st-key-mobile_trade_dirswitch button{width:100%!important;height:28px!important;min-height:28px!important;border:0!important;border-radius:999px!important;
    background:transparent!important;color:#9aa2ae!important;font-size:8px!important;font-weight:760!important;letter-spacing:.055em!important;
    text-transform:uppercase!important;padding:0!important;box-shadow:none!important;}
  .st-key-mobile_trade_dirswitch button p{line-height:1!important;margin:0!important;white-space:nowrap!important;}
  .st-key-mob_trade_dirlong_on button,.st-key-mob_trade_dirlong_on button:hover{color:#07120c!important;}
  .st-key-mob_trade_dirshort_on button,.st-key-mob_trade_dirshort_on button:hover{color:#ffffff!important;}
  .st-key-refreshbtn button{position:relative!important;display:block!important;color:#ffffff!important;background:rgba(17,21,31,.72)!important;border:1px solid rgba(139,92,246,.38)!important;border-radius:999px!important;width:34px!important;height:34px!important;min-height:34px!important;padding:0!important;line-height:0!important;}
  .st-key-refreshbtn button:hover{background:rgba(255,255,255,.07)!important;color:#ffffff!important;}
  .st-key-refreshbtn button p{display:none!important;}
  .st-key-refreshbtn button::before{content:"";position:absolute;left:17px;top:17px;display:block;width:18px;height:18px;background:currentColor;transform:translate(-50%,-50%);
    -webkit-mask:url("data:image/svg+xml,%3Csvg%20height%3D%22533pt%22%20viewBox%3D%22-16%20-18%20533.33331%20533%22%20width%3D%22533pt%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20d%3D%22m248.429688%2025.082031c39.289062%200%2078.640624%2011.152344%20113.800781%2032.253907%2022.300781%2013.417968%2042.339843%2030.28125%2059.363281%2049.972656l-58.738281-1.9375c-6.898438-.230469-12.675781%205.179687-12.902344%2012.082031-.226563%206.898437%205.179687%2012.679687%2012.082031%2012.902344l81.269532%202.683593c4.667968%201.921876%2010.035156.847657%2013.605468-2.726562%203.566406-3.574219%204.632813-8.941406%202.703125-13.609375l-2.675781-81.25c-.15625-6.902344-5.878906-12.371094-12.78125-12.21875-6.898438.15625-12.375%205.878906-12.21875%2012.777344%200%20.09375%200%20.179687.007812.269531l1.546876%2046.875c-17.195313-18.375-36.847657-34.285156-58.398438-47.265625-39.042969-23.425781-82.84375-35.8085938-126.664062-35.8085938-70%200-134.539063%2028.8632808-181.703126%2081.2695308-41.78125%2046.425782-66.726562%20108.914063-66.726562%20167.160157%200%206.902343%205.59375%2012.5%2012.5%2012.5s12.5-5.597657%2012.5-12.5c0-52.238281%2022.542969-108.476563%2060.308594-150.433594%2042.367187-47.066406%20100.292968-72.996094%20163.121094-72.996094zm0%200%22%2F%3E%3Cpath%20d%3D%22m487.5%20236.011719c-6.90625%200-12.5%205.59375-12.5%2012.5%200%2052.234375-22.542969%20108.476562-60.308594%20150.4375-42.367187%2047.066406-100.292968%2072.988281-163.121094%2072.988281-39.289062%200-78.640624-11.144531-113.800781-32.246094-22.300781-13.421875-42.339843-30.285156-59.363281-49.972656l58.738281%201.9375c6.898438.222656%2012.675781-5.1875%2012.902344-12.085938.226563-6.898437-5.179687-12.675781-12.082031-12.90625l-81.269532-2.679687c-4.667968-1.921875-10.035156-.84375-13.605468%202.726563-3.566406%203.574218-4.632813%208.9375-2.703125%2013.605468l2.675781%2081.25c.15625%206.90625%205.878906%2012.378906%2012.78125%2012.222656%206.898438-.152343%2012.375-5.875%2012.21875-12.777343%200-.089844%200-.175781-.007812-.269531l-1.546876-46.875c17.195313%2018.378906%2036.847657%2034.28125%2058.398438%2047.269531%2039.042969%2023.429687%2082.84375%2035.808593%20126.664062%2035.808593%2070%200%20134.539063-28.859374%20181.703126-81.265624%2041.78125-46.429688%2066.726562-108.917969%2066.726562-167.167969%200-6.90625-5.59375-12.5-12.5-12.5zm0%200%22%2F%3E%3C%2Fsvg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg%20height%3D%22533pt%22%20viewBox%3D%22-16%20-18%20533.33331%20533%22%20width%3D%22533pt%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20d%3D%22m248.429688%2025.082031c39.289062%200%2078.640624%2011.152344%20113.800781%2032.253907%2022.300781%2013.417968%2042.339843%2030.28125%2059.363281%2049.972656l-58.738281-1.9375c-6.898438-.230469-12.675781%205.179687-12.902344%2012.082031-.226563%206.898437%205.179687%2012.679687%2012.082031%2012.902344l81.269532%202.683593c4.667968%201.921876%2010.035156.847657%2013.605468-2.726562%203.566406-3.574219%204.632813-8.941406%202.703125-13.609375l-2.675781-81.25c-.15625-6.902344-5.878906-12.371094-12.78125-12.21875-6.898438.15625-12.375%205.878906-12.21875%2012.777344%200%20.09375%200%20.179687.007812.269531l1.546876%2046.875c-17.195313-18.375-36.847657-34.285156-58.398438-47.265625-39.042969-23.425781-82.84375-35.8085938-126.664062-35.8085938-70%200-134.539063%2028.8632808-181.703126%2081.2695308-41.78125%2046.425782-66.726562%20108.914063-66.726562%20167.160157%200%206.902343%205.59375%2012.5%2012.5%2012.5s12.5-5.597657%2012.5-12.5c0-52.238281%2022.542969-108.476563%2060.308594-150.433594%2042.367187-47.066406%20100.292968-72.996094%20163.121094-72.996094zm0%200%22%2F%3E%3Cpath%20d%3D%22m487.5%20236.011719c-6.90625%200-12.5%205.59375-12.5%2012.5%200%2052.234375-22.542969%20108.476562-60.308594%20150.4375-42.367187%2047.066406-100.292968%2072.988281-163.121094%2072.988281-39.289062%200-78.640624-11.144531-113.800781-32.246094-22.300781-13.421875-42.339843-30.285156-59.363281-49.972656l58.738281%201.9375c6.898438.222656%2012.675781-5.1875%2012.902344-12.085938.226563-6.898437-5.179687-12.675781-12.082031-12.90625l-81.269532-2.679687c-4.667968-1.921875-10.035156-.84375-13.605468%202.726563-3.566406%203.574218-4.632813%208.9375-2.703125%2013.605468l2.675781%2081.25c.15625%206.90625%205.878906%2012.378906%2012.78125%2012.222656%206.898438-.152343%2012.375-5.875%2012.21875-12.777343%200-.089844%200-.175781-.007812-.269531l-1.546876-46.875c17.195313%2018.378906%2036.847657%2034.28125%2058.398438%2047.269531%2039.042969%2023.429687%2082.84375%2035.808593%20126.664062%2035.808593%2070%200%20134.539063-28.859374%20181.703126-81.265624%2041.78125-46.429688%2066.726562-108.917969%2066.726562-167.167969%200-6.90625-5.59375-12.5-12.5-12.5zm0%200%22%2F%3E%3C%2Fsvg%3E") center/contain no-repeat;}
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-mobile_exposure_top){
    width:100%!important;flex:0 0 100%!important;margin:0!important;height:auto!important;
  }
  .st-key-mobile_exposure_top{
    display:block!important;width:100%!important;margin:0!important;padding:13px 11px!important;
    background:#130f1d;border:1px solid rgba(139,92,246,.58);border-radius:8px;
    box-shadow:0 0 0 1px rgba(124,58,237,.08),0 0 24px rgba(124,58,237,.18);
  }
  .st-key-mobile_exposure_top [data-testid="stHorizontalBlock"]{gap:9px!important;align-items:center!important;}
  .st-key-mobile_margin_control_row,
  .st-key-mobile_leverage_control_row{display:block!important;margin:0!important;padding:0!important;}
  .st-key-mobile_leverage_control_row{border-top:1px solid rgba(139,92,246,.18)!important;margin-top:10px!important;padding-top:11px!important;}
  .st-key-mobile_margin_control_row [data-testid="stVerticalBlock"],
  .st-key-mobile_leverage_control_row [data-testid="stVerticalBlock"]{gap:0!important;}
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"],
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;
    align-items:center!important;gap:9px!important;width:100%!important;min-height:0!important;margin-top:7px!important;
  }
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{min-height:0!important;min-width:0!important;width:auto!important;}
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1){
    flex:1 1 auto!important;width:auto!important;
  }
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) > [data-testid="stVerticalBlock"],
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) > [data-testid="stVerticalBlock"]{
    align-items:stretch!important;width:100%!important;
  }
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) [data-testid="stElementContainer"],
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) [data-testid="stMarkdown"],
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) [data-testid="stMarkdownContainer"],
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) [data-testid="stElementContainer"],
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) [data-testid="stMarkdown"],
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) [data-testid="stMarkdownContainer"]{
    width:100%!important;text-align:left!important;
  }
  .st-key-mobile_margin_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2),
  .st-key-mobile_leverage_control_row > [data-testid="stLayoutWrapper"]:has([data-testid="stHorizontalBlock"]) > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){
    flex:0 0 58px!important;width:58px!important;
  }
  .st-key-mobile_margin_control_row [data-testid="stElementContainer"],
  .st-key-mobile_margin_control_row [data-testid="stMarkdown"],
  .st-key-mobile_margin_control_row [data-testid="stMarkdownContainer"],
  .st-key-mobile_leverage_control_row [data-testid="stElementContainer"],
  .st-key-mobile_leverage_control_row [data-testid="stMarkdown"],
  .st-key-mobile_leverage_control_row [data-testid="stMarkdownContainer"]{margin-top:0!important;margin-bottom:0!important;}
  .mobile-exposure-control{display:block!important;width:100%!important;margin:0!important;min-width:0!important;text-align:left!important;}
  .mobile-exposure-control.second{margin:0!important;border-top:0!important;padding-top:0!important;}
  .mec-copy{text-align:left!important;justify-self:start!important;align-self:center!important;width:100%!important;}
  .mec-copy span{display:flex;align-items:center;gap:5px;color:#a7acb7;font-size:8.5px;font-weight:820;letter-spacing:.075em;
    text-transform:uppercase;line-height:1;margin:0 0 8px!important;white-space:nowrap;text-align:left!important;justify-content:flex-start!important;}
  .mec-value-row{display:flex!important;flex-direction:row!important;align-items:baseline!important;justify-content:flex-start!important;gap:8px;min-width:0;width:100%!important;flex-wrap:nowrap!important;text-align:left!important;}
  .mec-copy b{display:block;font-size:25px;font-weight:860;line-height:.95;font-variant-numeric:tabular-nums;letter-spacing:-.01em;text-align:left!important;}
  .mec-copy b.green{color:#0ecb81!important;}
  .mec-copy b.purple{color:#9b6dff!important;}
  .mec-copy em{display:block;margin:0!important;color:#a7acb7;font-size:9.5px;font-weight:650;font-style:normal;line-height:1.25;white-space:nowrap;text-align:left!important;}
  .st-key-mobile_margin_value_row,
  .st-key-mobile_leverage_value_row{width:100%!important;margin:0!important;}
  .st-key-mobile_margin_value_row [data-testid="stVerticalBlock"],
  .st-key-mobile_leverage_value_row [data-testid="stVerticalBlock"]{gap:1px!important;align-items:flex-start!important;}
  .st-key-mobile_margin_value_row [data-testid="stElementContainer"],
  .st-key-mobile_leverage_value_row [data-testid="stElementContainer"],
  .st-key-mobile_margin_value_row [data-testid="stMarkdown"],
  .st-key-mobile_leverage_value_row [data-testid="stMarkdown"],
  .st-key-mobile_margin_value_row [data-testid="stMarkdownContainer"],
  .st-key-mobile_leverage_value_row [data-testid="stMarkdownContainer"]{
    width:auto!important;max-width:max-content!important;align-self:flex-start!important;
    margin-left:0!important;margin-right:auto!important;text-align:left!important;
  }
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInput"],
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInput"]{margin:0!important;padding:0!important;}
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInput"] div[data-baseweb="input"],
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInput"] div[data-baseweb="input"]{
    background:transparent!important;border:0!important;box-shadow:none!important;
    min-height:27px!important;height:27px!important;padding:0!important;
  }
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInputContainer"],
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInputContainer"]{
    position:relative!important;height:27px!important;background:transparent!important;border:0!important;box-shadow:none!important;
  }
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInputContainer"]::before{
    content:"$";position:absolute;left:0;top:50%;transform:translateY(-50%);
    color:#0ecb81;font-size:25px;font-weight:860;line-height:1;pointer-events:none;
  }
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInputContainer"]::before{
    content:"x";position:absolute;left:0;top:50%;transform:translateY(-50%);
    color:#9b6dff;font-size:25px;font-weight:860;line-height:1;pointer-events:none;
  }
  .st-key-calc_mobile_margin_usd_input input,
  .st-key-calc_mobile_leverage_input input{
    background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;
    font-size:25px!important;font-weight:860!important;line-height:1!important;
    font-variant-numeric:tabular-nums!important;letter-spacing:-.01em!important;text-align:left!important;
    min-height:27px!important;height:27px!important;
  }
  .st-key-calc_mobile_margin_usd_input input{color:#0ecb81!important;padding-left:15px!important;}
  .st-key-calc_mobile_leverage_input input{color:#9b6dff!important;padding-left:15px!important;}
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInputStepUp"],
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInputStepDown"],
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInputStepUp"],
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInputStepDown"]{display:none!important;}
  .mec-inline-summary{color:#a7acb7;font-size:11.5px;font-weight:650;line-height:1.25;white-space:nowrap;text-align:left!important;margin:0!important;padding-left:1px!important;}
  .st-key-mobile_exposure_top [data-testid="stButton"]{margin:0!important;}
  .st-key-mobile_exposure_top button{height:39px!important;min-height:39px!important;border-radius:7px!important;
    background:rgba(255,255,255,.035)!important;border:1px solid rgba(167,172,183,.48)!important;
    color:#e8eaf0!important;font-size:9.5px!important;font-weight:850!important;letter-spacing:.055em!important;
    text-transform:uppercase!important;padding:0 8px!important;box-shadow:none!important;}
  .st-key-mobile_exposure_top button:hover{border-color:rgba(155,109,255,.72)!important;background:rgba(155,109,255,.10)!important;color:#ffffff!important;}
  .mec-max-value{margin-top:11px;color:#a7acb7;font-size:9.5px;font-weight:760;text-align:center;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap;}
  .st-key-mobile_exposure_top [data-testid="stElementContainer"]:has([data-testid="stSlider"]){margin:0!important;width:100%!important;}
  .st-key-mobile_exposure_top .st-key-mobile_margin_slider_full,
  .st-key-mobile_exposure_top .st-key-mobile_leverage_slider_full{width:100%!important;margin-top:0!important;}
  .st-key-mobile_exposure_top .st-key-mobile_margin_slider_full [data-testid="stElementContainer"],
  .st-key-mobile_exposure_top .st-key-mobile_margin_slider_full [data-testid="stSlider"],
  .st-key-mobile_exposure_top .st-key-mobile_margin_slider_full [data-baseweb="slider"],
  .st-key-mobile_exposure_top .st-key-mobile_leverage_slider_full [data-testid="stElementContainer"],
  .st-key-mobile_exposure_top .st-key-mobile_leverage_slider_full [data-testid="stSlider"],
  .st-key-mobile_exposure_top .st-key-mobile_leverage_slider_full [data-baseweb="slider"]{width:100%!important;min-width:0!important;}
  .st-key-mobile_exposure_top [data-testid="stSlider"] [data-testid="stWidgetLabel"],
  .st-key-mobile_exposure_top [data-testid="stSlider"] label,
  .st-key-mobile_exposure_top [data-testid="stSlider"] label p{
    position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;
    opacity:0!important;pointer-events:none!important;margin:0!important;padding:0!important;
  }
  .st-key-mobile_exposure_top [data-testid="stSlider"]{display:block!important;padding:0!important;margin-top:2px!important;min-height:30px!important;}
  .st-key-mobile_exposure_top [data-baseweb="slider"]{display:block!important;padding-top:8px!important;padding-bottom:0!important;width:100%!important;min-height:28px!important;}
  .st-key-mobile_exposure_top [data-testid="stSliderThumbValue"],
  .st-key-mobile_exposure_top [data-testid="stSliderTickBar"],
  .st-key-mobile_exposure_top [data-testid="stSliderTickBar"] span{display:none!important;visibility:hidden!important;}
  .mec-ticks{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));align-items:center;
    width:calc(100% + 58px)!important;margin:4px 0 0!important;
    color:#a7acb7;font-size:9.5px;font-weight:760;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:visible!important;}
  .mec-ticks span{text-align:center;}
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-mobile_risk_box){width:50%!important;flex:0 0 calc(50% - 4px)!important;
    height:132px!important;margin:0!important;}
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.mobile-lev-mini){width:50%!important;flex:0 0 calc(50% - 4px)!important;
    height:132px!important;margin:0!important;}
  .st-key-brandrow [data-testid="stElementContainer"]:has(.mobile-lev-mini){width:50%!important;flex:0 0 calc(50% - 4px)!important;
    height:132px!important;margin:0!important;}
  .st-key-brandrow [data-testid="stMarkdown"]:has(.mobile-lev-mini),
  .st-key-brandrow [data-testid="stMarkdownContainer"]:has(.mobile-lev-mini){height:100%!important;margin:0!important;}
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-mobile_symbol_box),
  .st-key-brandrow [data-testid="stElementContainer"]:has(.st-key-mobile_symbol_box),
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-mobile_dirseg),
  .st-key-brandrow [data-testid="stElementContainer"]:has(.st-key-mobile_dirseg){
    width:50%!important;flex:0 0 calc(50% - 4px)!important;margin:0!important;}
  .st-key-brandrow [data-testid="stLayoutWrapper"]:has(.st-key-mobile_price_symbol_stack),
  .st-key-brandrow [data-testid="stElementContainer"]:has(.st-key-mobile_price_symbol_stack){
    width:48%!important;flex:0 0 calc(48% - 4px)!important;margin:0!important;}
  .st-key-mobile_price_symbol_stack [data-testid="stLayoutWrapper"]:has(.st-key-mobile_symbol_box),
  .st-key-mobile_price_symbol_stack [data-testid="stElementContainer"]:has(.st-key-mobile_symbol_box){
    width:100%!important;flex:1 1 auto!important;margin:0!important;}
  .st-key-mobile_risk_box{display:flex!important;min-height:132px;height:132px!important;flex-direction:column;justify-content:flex-start;
    background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
    box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
    padding:10px 10px!important;color:#dfe3e8;margin:0!important;gap:6px!important;overflow:hidden;}
  .mobile-lev-mini{display:flex!important;height:132px;flex-direction:column;justify-content:flex-start;
    background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
    box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
    padding:10px 10px;color:#dfe3e8;margin:0!important;overflow:hidden;}
  .st-key-mobile_risk_box [data-testid="stVerticalBlock"]{gap:5px!important;}
  .mini-card-head{display:flex;align-items:center;gap:8px;min-width:0;height:20px;}
  .mini-card-icon{display:block;width:17px;height:17px;flex:0 0 17px;background:#9a7cff;
    filter:none;transform:none;backface-visibility:hidden;shape-rendering:geometricPrecision;}
  .wallet-mask{-webkit-mask:url("data:image/svg+xml,%3Csvg%20id=%22Layer_1%22%20enable-background=%22new%200%200%20507.246%20507.246%22%20viewBox=%220%200%20507.246%20507.246%22%20xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cpath%20d=%22m457.262%2089.821c-2.734-35.285-32.298-63.165-68.271-63.165h-320.491c-37.771%200-68.5%2030.729-68.5%2068.5v316.934c0%2037.771%2030.729%2068.5%2068.5%2068.5h370.247c37.771%200%2068.5-30.729%2068.5-68.5v-256.333c-.001-31.354-21.184-57.836-49.985-65.936zm-388.762-31.165h320.492c17.414%200%2032.008%2012.261%2035.629%2028.602h-356.121c-13.411%200-25.924%203.889-36.5%2010.577v-2.679c0-20.126%2016.374-36.5%2036.5-36.5zm370.246%20389.934h-370.246c-20.126%200-36.5-16.374-36.5-36.5v-256.333c0-20.126%2016.374-36.5%2036.5-36.5h370.247c20.126%200%2036.5%2016.374%2036.5%2036.5v55.838h-102.026c-40.43%200-73.322%2032.893-73.322%2073.323s32.893%2073.323%2073.322%2073.323h102.025v53.849c0%2020.126-16.374%2036.5-36.5%2036.5zm36.5-122.349h-102.025c-22.785%200-41.322-18.537-41.322-41.323s18.537-41.323%2041.322-41.323h102.025z%22/%3E%3Ccircle%20cx=%22379.16%22%20cy=%22286.132%22%20r=%2216.658%22/%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg%20id=%22Layer_1%22%20enable-background=%22new%200%200%20507.246%20507.246%22%20viewBox=%220%200%20507.246%20507.246%22%20xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cpath%20d=%22m457.262%2089.821c-2.734-35.285-32.298-63.165-68.271-63.165h-320.491c-37.771%200-68.5%2030.729-68.5%2068.5v316.934c0%2037.771%2030.729%2068.5%2068.5%2068.5h370.247c37.771%200%2068.5-30.729%2068.5-68.5v-256.333c-.001-31.354-21.184-57.836-49.985-65.936zm-388.762-31.165h320.492c17.414%200%2032.008%2012.261%2035.629%2028.602h-356.121c-13.411%200-25.924%203.889-36.5%2010.577v-2.679c0-20.126%2016.374-36.5%2036.5-36.5zm370.246%20389.934h-370.246c-20.126%200-36.5-16.374-36.5-36.5v-256.333c0-20.126%2016.374-36.5%2036.5-36.5h370.247c20.126%200%2036.5%2016.374%2036.5%2036.5v55.838h-102.026c-40.43%200-73.322%2032.893-73.322%2073.323s32.893%2073.323%2073.322%2073.323h102.025v53.849c0%2020.126-16.374%2036.5-36.5%2036.5zm36.5-122.349h-102.025c-22.785%200-41.322-18.537-41.322-41.323s18.537-41.323%2041.322-41.323h102.025z%22/%3E%3Ccircle%20cx=%22379.16%22%20cy=%22286.132%22%20r=%2216.658%22/%3E%3C/svg%3E") center/contain no-repeat;}
  .wallet2-mask{-webkit-mask:url("data:image/svg+xml,%3Csvg%20viewBox='0%200%2032%2032'%20xmlns='http://www.w3.org/2000/svg'%3E%3Cpath%20d='m28%208h-21c-.5498047%200-1-.4501953-1-1s.4501953-1%201-1h20c0-1.6499023-1.3500977-3-3-3h-18c-2.7597656%200-5%202.2402344-5%205v18c0%201.6499023%201.3500977%203%203%203h24c1.6499023%200%203-1.3500977%203-3v-15c0-1.6499023-1.3500977-3-3-3zm-3%2012.5c-1.1030273%200-2-.8969727-2-2s.8969727-2%202-2%202%20.8969727%202%202-.8969727%202-2%202z'/%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg%20viewBox='0%200%2032%2032'%20xmlns='http://www.w3.org/2000/svg'%3E%3Cpath%20d='m28%208h-21c-.5498047%200-1-.4501953-1-1s.4501953-1%201-1h20c0-1.6499023-1.3500977-3-3-3h-18c-2.7597656%200-5%202.2402344-5%205v18c0%201.6499023%201.3500977%203%203%203h24c1.6499023%200%203-1.3500977%203-3v-15c0-1.6499023-1.3500977-3-3-3zm-3%2012.5c-1.1030273%200-2-.8969727-2-2s.8969727-2%202-2%202%20.8969727%202%202-.8969727%202-2%202z'/%3E%3C/svg%3E") center/contain no-repeat;}
  .transfer-mask{-webkit-mask:url("data:image/svg+xml,%3Csvg%20viewBox='0%200%2016.933333%2016.933334'%20xmlns='http://www.w3.org/2000/svg'%3E%3Cg%20transform='translate(0%20-280.067)'%3E%3Cpath%20d='m8.4666641%20280.59582c-1.1676195.00002-2.2781499.25138-3.2773197.70486-.136779.0621-.1945138.22543-.1271244.35967l.4728395.94723c.0635.12722.2161567.18153.3457152.12299.7897998-.35263%201.6639593-.54674%202.5858894-.54674%203.5101389%200%206.3494839%202.83936%206.3494839%206.34949%200%201.32045-.406432%202.54068-1.095542%203.55689l-.834057-.83458c-.057-.0571-.136892-.0851-.21704-.076-.133702.0155-.234455.12895-.234095.26355v2.91041c-.00053.14612.11743.26504.263548.26562h2.909901c.237731.002.357037-.28646.187584-.4532l-.937926-.93793c.967642-1.31546%201.545643-2.9378%201.545643-4.6948%200-4.38063-3.556881-7.93751-7.9374999-7.9375zm-7.1447846%201.85156c-.2352887.00009-.35343574.28424-.1875843.45114l.9384427.93844c-.9677982%201.31561-1.54357384%202.93905-1.54357384%204.69636%200%204.38063%203.55688104%207.93749%207.93750004%207.9375%201.1676195%200%202.2781489-.25345%203.2773189-.70694.13657-.0623.194048-.22557.126606-.35967l-.474387-.94722c-.0634-.12608-.21463-.1802-.343649-.12299-.789792.35264-1.6639695.5488-2.5858889.5488-3.5101398%200-6.3494841-2.83934-6.3494841-6.34948%200-1.31999.4040399-2.54168%201.0924407-3.55793l.8371576.83509c.1669018.16587.4510458.0477.4511357-.18758v-2.9099c.0005292-.14693-.1186868-.26618-.2656178-.26562zm7.1442686%201.85209c-2.3348712%200-4.2323015%201.89949-4.2323015%204.23436s1.8974303%204.2323%204.2323015%204.2323c2.3348679%200%204.2343649-1.89743%204.2343649-4.2323s-1.899497-4.23436-4.2343649-4.23436zm-.00106%201.05678c.1323314%200%20.2645833.0881.2645833.26458v.56069c.6022314.12299%201.0588493.65825%201.0588493%201.29553.00799.36069-.537165.36069-.5291667%200%200-.44151-.3517212-.79272-.7932314-.79272s-.7927181.35121-.7927181.79272.3512079.79323.7927181.79323c.7274904%200%201.3223981.59646%201.3223981%201.32395%200%20.63729-.4566179%201.17306-1.0588493%201.29605v.55552c0%20.35286-.5291666.35286-.5291666%200v-.55604c-.6012101-.12379-1.056267-.65897-1.056267-1.29553.00765-.34503.5211683-.34503.5291667%200%200%20.44151.3512079.79324.7927181.79324s.7932314-.35173.7932314-.79324-.3517212-.79478-.7932314-.79478c-.727501%200-1.3218848-.59491-1.3218848-1.3224%200-.63656.4550569-1.17122%201.056267-1.29501v-.56121c0-.17643.1322625-.26458.2645833-.26458z'/%3E%3C/g%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg%20viewBox='0%200%2016.933333%2016.933334'%20xmlns='http://www.w3.org/2000/svg'%3E%3Cg%20transform='translate(0%20-280.067)'%3E%3Cpath%20d='m8.4666641%20280.59582c-1.1676195.00002-2.2781499.25138-3.2773197.70486-.136779.0621-.1945138.22543-.1271244.35967l.4728395.94723c.0635.12722.2161567.18153.3457152.12299.7897998-.35263%201.6639593-.54674%202.5858894-.54674%203.5101389%200%206.3494839%202.83936%206.3494839%206.34949%200%201.32045-.406432%202.54068-1.095542%203.55689l-.834057-.83458c-.057-.0571-.136892-.0851-.21704-.076-.133702.0155-.234455.12895-.234095.26355v2.91041c-.00053.14612.11743.26504.263548.26562h2.909901c.237731.002.357037-.28646.187584-.4532l-.937926-.93793c.967642-1.31546%201.545643-2.9378%201.545643-4.6948%200-4.38063-3.556881-7.93751-7.9374999-7.9375zm-7.1447846%201.85156c-.2352887.00009-.35343574.28424-.1875843.45114l.9384427.93844c-.9677982%201.31561-1.54357384%202.93905-1.54357384%204.69636%200%204.38063%203.55688104%207.93749%207.93750004%207.9375%201.1676195%200%202.2781489-.25345%203.2773189-.70694.13657-.0623.194048-.22557.126606-.35967l-.474387-.94722c-.0634-.12608-.21463-.1802-.343649-.12299-.789792.35264-1.6639695.5488-2.5858889.5488-3.5101398%200-6.3494841-2.83934-6.3494841-6.34948%200-1.31999.4040399-2.54168%201.0924407-3.55793l.8371576.83509c.1669018.16587.4510458.0477.4511357-.18758v-2.9099c.0005292-.14693-.1186868-.26618-.2656178-.26562zm7.1442686%201.85209c-2.3348712%200-4.2323015%201.89949-4.2323015%204.23436s1.8974303%204.2323%204.2323015%204.2323c2.3348679%200%204.2343649-1.89743%204.2343649-4.2323s-1.899497-4.23436-4.2343649-4.23436zm-.00106%201.05678c.1323314%200%20.2645833.0881.2645833.26458v.56069c.6022314.12299%201.0588493.65825%201.0588493%201.29553.00799.36069-.537165.36069-.5291667%200%200-.44151-.3517212-.79272-.7932314-.79272s-.7927181.35121-.7927181.79272.3512079.79323.7927181.79323c.7274904%200%201.3223981.59646%201.3223981%201.32395%200%20.63729-.4566179%201.17306-1.0588493%201.29605v.55552c0%20.35286-.5291666.35286-.5291666%200v-.55604c-.6012101-.12379-1.056267-.65897-1.056267-1.29553.00765-.34503.5211683-.34503.5291667%200%200%20.44151.3512079.79324.7927181.79324s.7932314-.35173.7932314-.79324-.3517212-.79478-.7932314-.79478c-.727501%200-1.3218848-.59491-1.3218848-1.3224%200-.63656.4550569-1.17122%201.056267-1.29501v-.56121c0-.17643.1322625-.26458.2645833-.26458z'/%3E%3C/g%3E%3C/svg%3E") center/contain no-repeat;}
  .flash-mask{-webkit-mask:url("data:image/svg+xml,%3Csvg%20viewBox='0%200%20512%20512'%20xmlns='http://www.w3.org/2000/svg'%3E%3Cpath%20d='M400.268%20175.599c-1.399-3.004-4.412-4.932-7.731-4.932h-101.12l99.797-157.568c1.664-2.628%201.766-5.956.265-8.678C389.977%201.69%20387.109%200%20384.003%200H247.47c-3.234%200-6.187%201.826-7.637%204.719l-128%20256c-1.323%202.637-1.178%205.777.375%208.294%201.562%202.517%204.301%204.053%207.262%204.053h87.748l-95.616%20227.089c-1.63%203.883-.179%208.388%203.413%2010.59%201.382.845%202.918%201.254%204.446%201.254%202.449%200%204.864-1.05%206.537-3.029l273.067-324.267c2.141-2.542%202.602-6.092%201.203-9.104z'/%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg%20viewBox='0%200%20512%20512'%20xmlns='http://www.w3.org/2000/svg'%3E%3Cpath%20d='M400.268%20175.599c-1.399-3.004-4.412-4.932-7.731-4.932h-101.12l99.797-157.568c1.664-2.628%201.766-5.956.265-8.678C389.977%201.69%20387.109%200%20384.003%200H247.47c-3.234%200-6.187%201.826-7.637%204.719l-128%20256c-1.323%202.637-1.178%205.777.375%208.294%201.562%202.517%204.301%204.053%207.262%204.053h87.748l-95.616%20227.089c-1.63%203.883-.179%208.388%203.413%2010.59%201.382.845%202.918%201.254%204.446%201.254%202.449%200%204.864-1.05%206.537-3.029l273.067-324.267c2.141-2.542%202.602-6.092%201.203-9.104z'/%3E%3C/svg%3E") center/contain no-repeat;}
  .scale-mask{-webkit-mask:url("data:image/svg+xml,%3Csvg%20version=%221.1%22%20id=%22Capa_1%22%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%20464.985%20464.985%22%3E%3Cpath%20d=%22M457.145,218.479L386.092,75.327c-1.875-3.465-5.465-5.659-9.404-5.747l-4.702,1.045h-91.951c-6.798-26.257-33.594-42.032-59.851-35.235c-17.274,4.472-30.763,17.961-35.235,35.235H92.998l-4.702-1.045c-3.939,0.088-7.529,2.282-9.404,5.747L7.839,218.479c-4.655,1.001-7.943,5.166-7.837,9.927c0,43.886,39.706,79.935,88.294,79.935s88.816-36.049,88.816-79.935c-0.086-4.694-3.291-8.754-7.837-9.927L106.06,91.523h78.367c3.951,18.899,18.717,33.665,37.616,37.616v183.38c-33.959,4.18-60.604,29.78-64.784,55.902h-22.988c-6.132,0.493-11.001,5.362-11.494,11.494v41.796c0.545,5.745,5.645,9.96,11.39,9.414c0.035-0.003,0.069-0.007,0.104-0.01h196.441c5.739,0.603,10.881-3.561,11.483-9.3c0.004-0.035,0.007-0.069,0.01-0.104v-41.796c-0.493-6.132-5.362-11.001-11.494-11.494h-22.988c-4.18-26.122-30.825-51.722-64.784-55.902V129.14c18.899-3.951,33.665-18.717,37.616-37.616h78.367l-63.216,126.955c-4.545,1.173-7.751,5.233-7.837,9.927c0,43.886,39.706,79.935,88.816,79.935c49.11,0,88.294-36.049,88.294-79.935C465.089,223.645,461.8,219.48,457.145,218.479z%22/%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg%20version=%221.1%22%20id=%22Capa_1%22%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%20464.985%20464.985%22%3E%3Cpath%20d=%22M457.145,218.479L386.092,75.327c-1.875-3.465-5.465-5.659-9.404-5.747l-4.702,1.045h-91.951c-6.798-26.257-33.594-42.032-59.851-35.235c-17.274,4.472-30.763,17.961-35.235,35.235H92.998l-4.702-1.045c-3.939,0.088-7.529,2.282-9.404,5.747L7.839,218.479c-4.655,1.001-7.943,5.166-7.837,9.927c0,43.886,39.706,79.935,88.294,79.935s88.816-36.049,88.816-79.935c-0.086-4.694-3.291-8.754-7.837-9.927L106.06,91.523h78.367c3.951,18.899,18.717,33.665,37.616,37.616v183.38c-33.959,4.18-60.604,29.78-64.784,55.902h-22.988c-6.132,0.493-11.001,5.362-11.494,11.494v41.796c0.545,5.745,5.645,9.96,11.39,9.414c0.035-0.003,0.069-0.007,0.104-0.01h196.441c5.739,0.603,10.881-3.561,11.483-9.3c0.004-0.035,0.007-0.069,0.01-0.104v-41.796c-0.493-6.132-5.362-11.001-11.494-11.494h-22.988c-4.18-26.122-30.825-51.722-64.784-55.902V129.14c18.899-3.951,33.665-18.717,37.616-37.616h78.367l-63.216,126.955c-4.545,1.173-7.751,5.233-7.837,9.927c0,43.886,39.706,79.935,88.816,79.935c49.11,0,88.294-36.049,88.294-79.935C465.089,223.645,461.8,219.48,457.145,218.479z%22/%3E%3C/svg%3E") center/contain no-repeat;}
  .mrm-label,.mlv-label{font-size:8.5px;font-weight:760;letter-spacing:.08em;text-transform:uppercase;color:#a7acb7;line-height:1.1;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .mrm-value{font-size:22px;font-weight:800;line-height:1;color:#4c8dff;margin-top:8px;font-variant-numeric:tabular-nums;}
  .mlv-value{font-size:22px;font-weight:800;line-height:1;color:#e0a33e;margin-top:8px;font-variant-numeric:tabular-nums;}
  .mlv-sub{font-size:9px;color:#a7acb7;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .mlv-rail{position:relative;height:30px;margin-top:8px;}
  .mlv-track{position:absolute;left:3px;right:3px;top:10px;height:4px;border-radius:999px;background:#48505f;}
  .mlv-fill{position:absolute;left:3px;top:10px;height:4px;border-radius:999px;background:#e0a33e;}
  .mlv-ticks{position:absolute;left:0;right:0;top:22px;display:flex;justify-content:space-between;color:#a7acb7;font-size:8px;font-weight:650;}
  .st-key-mobile_risk_box [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;
    flex-wrap:nowrap!important;gap:5px!important;}
  .st-key-mobile_risk_box [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 0!important;
    width:auto!important;min-width:0!important;}
  .st-key-mobile_risk_box [data-testid="stNumberInput"] label{margin:0!important;min-height:0!important;}
  .st-key-mobile_risk_box [data-testid="stNumberInput"] label p{font-size:9px!important;line-height:1!important;
    color:#a7acb7!important;text-transform:uppercase;font-weight:760!important;letter-spacing:.04em!important;}
  .st-key-mobile_risk_box [data-testid="stNumberInput"] div[data-baseweb="input"]{min-height:38px!important;border-radius:9px!important;
    background:#1b1a2b!important;border:1px solid rgba(255,255,255,.04)!important;}
  .st-key-mobile_risk_box [data-testid="stNumberInputContainer"]{height:38px!important;}
  .st-key-mobile_risk_box [data-testid="stNumberInput"] input{font-size:16px!important;font-weight:760!important;
    padding:7px 8px 5px!important;color:#f2f4f8!important;}
  .ctx-cap{font-size:10.5px;text-align:center;margin:0 0 8px!important;}

  .ocard,.st-key-inputs_card,.st-key-acct_card,.st-key-account_card,.st-key-lev_card,
  .st-key-dirseg,.mcard{border-color:rgba(139,92,246,.38)!important;
    box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15)!important;}
  .ocard{padding:12px 13px;margin-bottom:10px;}
  .chead{margin-bottom:8px;}
  .chead .t{font-size:10px;letter-spacing:.08em;}

  .dirbox,.pnlbox,.st-key-dirseg,.st-key-acct_card,.st-key-account_card,.st-key-lev_card{height:auto!important;min-height:0!important;}
  .dirbtns{flex-direction:row;gap:8px;padding:0;}
  .dbtn{flex:1;padding:8px 6px;font-size:12.5px;}
  .st-key-dirbtns{flex-direction:row!important;gap:8px!important;}
  .st-key-dirseg{display:none!important;}

  .st-key-mobile_symbol_box{display:block!important;width:100%!important;flex:1 1 auto!important;
    margin:0!important;background:transparent!important;border:0!important;box-shadow:none!important;
    padding:0!important;min-height:48px!important;}
  .st-key-mobile_symbol_box [data-testid="stTextInput"]{width:100%!important;}
  .st-key-mobile_symbol_box [data-testid="stTextInput"] label{display:none!important;}
  .st-key-mobile_symbol_box [data-testid="stTextInput"] div[data-baseweb="input"]{background:#13101e!important;
    border:1px solid rgba(139,92,246,.48)!important;border-radius:10px!important;min-height:48px!important;
    box-shadow:0 0 0 1px rgba(124,58,237,.05),0 0 16px rgba(124,58,237,.14)!important;}
  .st-key-mobile_symbol_box [data-testid="stTextInput"] input{background:transparent!important;color:#dfe3e8!important;
    font-size:16px!important;font-weight:500!important;letter-spacing:0!important;text-transform:uppercase!important;
    padding:8px 15px!important;}
  .st-key-mobile_symbol_box [data-testid="stTextInput"] input::placeholder{text-transform:uppercase!important;
    font-weight:500!important;letter-spacing:.02em;color:#9aa2ae!important;opacity:1!important;}
  .st-key-mobile_symbol_box .symerr{color:#f6465d;font-size:9px;font-weight:700;margin:0 0 5px;line-height:1.2;}

  .st-key-mobile_dirseg{display:flex!important;width:100%!important;flex:1 1 auto!important;
    margin:0!important;background:#13101e;border:1px solid rgba(139,92,246,.48);border-radius:10px;
    box-shadow:0 0 0 1px rgba(124,58,237,.05),0 0 16px rgba(124,58,237,.14);
    padding:0!important;min-height:48px!important;height:48px!important;overflow:hidden!important;}
  .st-key-mobile_dirseg [data-testid="stVerticalBlock"]{gap:0!important;width:100%!important;height:48px!important;min-height:48px!important;}
  .mobile-dir-label{display:none!important;}
  .st-key-mobile_dirbtns{display:flex!important;flex-direction:row!important;gap:0!important;width:100%!important;height:48px!important;min-height:48px!important;}
  .st-key-mobile_dirbtns [data-testid="stVerticalBlock"]{height:48px!important;min-height:48px!important;}
  .st-key-mobile_dirbtns [data-testid="stHorizontalBlock"]{gap:0!important;width:100%!important;height:48px!important;min-height:48px!important;}
  .st-key-mobile_dirbtns [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{width:50%!important;flex:0 0 50%!important;min-width:0!important;height:48px!important;}
  .st-key-mobile_dirbtns [data-testid="stElementContainer"],
  .st-key-mobile_dirbtns [data-testid="stButton"]{width:100%!important;height:48px!important;min-height:48px!important;margin:0!important;}
  .st-key-mobile_dirseg button{height:48px!important;border-radius:0!important;border:0!important;
    background:#13101e!important;color:#dfe3e8!important;font-size:16px!important;font-weight:500!important;
    letter-spacing:0!important;text-transform:uppercase!important;padding:0 8px!important;box-shadow:none!important;}
  .st-key-mobile_dirseg button p{line-height:1!important;margin:0!important;}
  .st-key-mob_dirlong_on button,.st-key-mob_dirlong_on button:hover{background:#0ecb81!important;
    color:#08120c!important;font-weight:650!important;box-shadow:inset 0 0 0 1px rgba(255,255,255,.10)!important;}
  .st-key-mob_dirshort_on button,.st-key-mob_dirshort_on button:hover{background:#f6465d!important;
    color:#ffffff!important;font-weight:650!important;box-shadow:inset 0 0 0 1px rgba(255,255,255,.10)!important;}
  .st-key-mob_dirlong_off button:hover,.st-key-mob_dirshort_off button:hover{background:#171a24!important;color:#f2f4f8!important;}
  .mobile-dir-pill{height:48px;border-radius:0;display:flex;align-items:center;justify-content:center;
    font-size:16px;font-weight:500;letter-spacing:0;text-transform:uppercase;border:0;color:#dfe3e8;background:#13101e;}
  .mobile-dir-pill.long.active{background:#0ecb81;border-color:#0ecb81;color:#08120c;}
  .mobile-dir-pill.short.active{background:#f6465d;border-color:#f6465d;color:#ffffff;}

  .pnlrows{gap:0;}
  .pnlrow{font-size:12.5px;padding:2px 0;}
  .pnlrow b{min-width:50px;}
  .pnlcap{font-size:8.5px;margin-top:4px;}

  .st-key-inputs_card,.st-key-acct_card,.st-key-account_card,.st-key-lev_card{padding:12px 13px!important;}
  .st-key-acct_card,.st-key-lev_card{display:none!important;}
  .st-key-inputs_card{height:auto!important;margin-top:0!important;}
  [data-testid="stHorizontalBlock"]:has(.hmain),
  [data-testid="stHorizontalBlock"]:has(.st-key-symbox),
  [data-testid="stHorizontalBlock"]:has(.dirbox),
  [data-testid="stHorizontalBlock"]:has(.pnlbox){
    display:none!important;height:0!important;min-height:0!important;
    margin:0!important;padding:0!important;overflow:hidden!important;
  }
  [data-testid="stHorizontalBlock"]:has(.st-key-inputs_card){margin-top:-24px!important;}
  [data-testid="stColumn"]:has(.st-key-inputs_card) [data-testid="stLayoutWrapper"],
  [data-testid="stColumn"]:has(.st-key-inputs_card) [data-testid="stVerticalBlock"]{height:auto!important;}
  .st-key-inputs_actions{margin-top:8px!important;margin-bottom:0!important;}
  [data-testid="stColumn"]:not(:has(.st-key-symbox)) .hmain,
  .dirbox,
  .pnlbox{display:none!important;}

  [data-testid="stNumberInput"] label p{font-size:9px!important;}
  [data-testid="stNumberInput"] div[data-baseweb="input"],
  .st-key-acct_card [data-testid="stNumberInput"] div[data-baseweb="input"],
  .st-key-account_card [data-testid="stNumberInput"] div[data-baseweb="input"]{min-height:38px!important;}
  [data-testid="stNumberInputContainer"],
  .st-key-acct_card [data-testid="stNumberInputContainer"],
  .st-key-account_card [data-testid="stNumberInputContainer"]{height:38px!important;}
  [data-testid="stNumberInput"] input{font-size:16px!important;padding-top:7px!important;padding-bottom:7px!important;}
  [data-testid="stNumberInputStepUp"],[data-testid="stNumberInputStepDown"]{display:none!important;}
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInput"] div[data-baseweb="input"],
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInput"] div[data-baseweb="input"],
  .st-key-calc_mobile_margin_usd_input [data-testid="stNumberInputContainer"],
  .st-key-calc_mobile_leverage_input [data-testid="stNumberInputContainer"]{
    min-height:27px!important;height:27px!important;background:transparent!important;border:0!important;box-shadow:none!important;
  }
  .st-key-calc_mobile_margin_usd_input input[data-testid="stNumberInputField"],
  .st-key-calc_mobile_leverage_input input[data-testid="stNumberInputField"]{
    font-size:25px!important;font-weight:860!important;line-height:1!important;
    padding-top:0!important;padding-bottom:0!important;min-height:27px!important;height:27px!important;
  }
  .st-key-calc_mobile_margin_usd_input input[data-testid="stNumberInputField"]{padding-left:15px!important;color:#0ecb81!important;}
  .st-key-calc_mobile_leverage_input input[data-testid="stNumberInputField"]{padding-left:15px!important;color:#9b6dff!important;}

  .acct-risk,.acct-exp{margin-bottom:10px;padding-bottom:10px;}
  .acct-risk b,.acct-exp .ae-kpi b{font-size:18px;}
  .acct-risk{gap:7px;font-size:11px;}
  .acct-exp .ae-kpi .l{font-size:10.5px;}
  .malloc-risks .risk-row .l{font-size:10.5px;}
  .malloc-risks .risk-row b{font-size:14px;}
  .st-key-acct_card .mx-op{transform:none;padding-bottom:0;font-size:15px;}

  .st-key-lev_card [data-testid="stElementContainer"]:has([data-testid="stNumberInput"]),
  .st-key-lev_card [data-testid="stElementContainer"]:has(.lev-fine){margin-top:6px!important;margin-bottom:0!important;}
  .st-key-lev_card [data-testid="stNumberInput"] input{font-size:16px!important;}
  .st-key-lev_card .lev-sub{font-size:10px;margin-top:5px;}
  .st-key-lev_card .lev-fine{font-size:8.5px;}

  .srow{font-size:12.5px;padding:6px 0;}
  .srow .vm{font-size:16px!important;line-height:1.12!important;}
  .srow .vd{font-size:11.5px!important;}
  .srow .u{display:block;margin-left:0;font-size:10.5px;}
  .srow.has-tail .u{display:inline;margin-left:3px;}
  .srow .rrpill{font-size:16px!important;margin-left:0;line-height:18px!important;}
  .liqwarn{font-size:10.5px;padding:7px 9px;}

  .scoreflex{flex-direction:column;align-items:center;gap:8px;}
  .scoreflex .scoregauge{width:100%;}
  .scoreflex .scorechecks{width:max-content;max-width:100%;margin:0 auto;align-items:flex-start;}
  .scorecard{padding:12px 13px;}
  .ck{font-size:11px;padding:2px 0;}

  .vstats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;}
  .vstat{padding:8px 9px;}
  .vstat .n{font-size:12.5px;}
  .vizrel{overflow:hidden;}
  .vizrel svg{max-width:100%;height:auto;}
  .vpctlabel{font-size:11px;left:88%;}
  .vliqtxt{font-size:10px;}
  .mobile-viz{display:block!important;}
  .st-key-mobile_exec_wrap{display:none!important;}
  .st-key-mobile_margin_cap{display:block!important;position:absolute!important;z-index:8;
    top:72px;right:23px;width:calc((100% - 39px) / 2 - 18px)!important;margin:0!important;}
  .st-key-mobile_margin_cap [data-testid="stNumberInput"]{width:100%!important;}
  .st-key-mobile_margin_cap [data-testid="stNumberInput"] label{display:none!important;}
  .st-key-mobile_margin_cap [data-testid="stNumberInput"] label p{font-size:8.5px!important;line-height:1!important;
    color:#8b94a0!important;text-transform:uppercase!important;font-weight:760!important;letter-spacing:.08em!important;}
  .st-key-mobile_margin_cap [data-testid="stNumberInput"] div[data-baseweb="input"]{min-height:28px!important;border-radius:0!important;
    background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;}
  .st-key-mobile_margin_cap [data-testid="stNumberInputContainer"]{height:28px!important;}
  .st-key-mobile_margin_cap [data-testid="stNumberInput"] input{font-size:18px!important;font-weight:780!important;
    color:#e0a33e!important;padding:0!important;}
  [data-testid="stVerticalBlock"]:has(.mobile-viz-grid-marker){display:flex!important;}
  [data-testid="stVerticalBlock"]:has(.mobile-liq-adjust){display:flex!important;}
  .st-key-mobile_viz_grid{margin-top:2px!important;gap:0!important;row-gap:0!important;}
  [data-testid="stColumn"]:has(.desktop-viz){display:none!important;}
  [data-testid="stColumn"]:has(.desktop-liq-adjust){display:none!important;}

  .mcard{padding:12px 13px;}
  .mcard .big{font-size:20px;}
  .mcard .sub{font-size:10.5px;}
  .cfoot{font-size:10.5px;align-items:flex-start;gap:8px;}
  .cfoot-mode{display:none;}
  .mobile-exec{display:block!important;}
}
.st-key-mobile_risk_box,.st-key-mobile_exposure_top,.mobile-live-ticker,.mobile-lev-mini,.st-key-mobile_price_symbol_stack,.st-key-mobile_trade_dirswitch{display:none;}
.st-key-mobile_symbol_box{display:none!important;}
.st-key-mobile_dirseg{display:none!important;}
.mobile-viz{display:none;}
.st-key-mobile_viz_grid{display:none!important;}
.st-key-liq_adjust_mobile{display:none!important;}
.mobile-exec{display:none;}
.st-key-mobile_margin_cap{display:none!important;}
@media(max-width:700px){
  .st-key-mobile_price_symbol_stack{display:flex!important;}
  .st-key-mobile_trade_dirswitch{display:block!important;}
  .st-key-mobile_symbol_box{display:block!important;}
  .st-key-mobile_dirseg{display:flex!important;}
}
@media (max-width: 900px){
  .mobile-exec{display:block!important;}
  .st-key-mobile_margin_cap{display:block!important;}
}
.st-key-liq_adjust_mobile,.st-key-liq_adjust_desktop{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:9px 13px 10px;margin:0 0 8px;color:#dfe3e8;min-height:0;}
.liq-adjust-head{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin-bottom:4px;}
.liq-adjust-title{font-size:10px;font-weight:760;letter-spacing:.08em;text-transform:uppercase;color:#8b94a0;}
.liq-adjust-note{font-size:10px;color:#8b94a0;white-space:nowrap;}
.liq-step-row{display:none;}
.st-key-liq_adjust_mobile [data-testid="stNumberInput"] label,
.st-key-liq_adjust_desktop [data-testid="stNumberInput"] label{display:none!important;}
.st-key-liq_adjust_mobile [data-testid="stNumberInput"] label p,
.st-key-liq_adjust_desktop [data-testid="stNumberInput"] label p{text-align:center!important;font-size:9px!important;letter-spacing:.08em!important;text-transform:uppercase!important;}
.st-key-liq_adjust_mobile [data-testid="stNumberInput"] input,
.st-key-liq_adjust_desktop [data-testid="stNumberInput"] input{text-align:center!important;font-weight:760!important;color:#e0a33e!important;}
.st-key-liq_adjust_mobile [data-testid="stNumberInput"] div[data-baseweb="input"],
.st-key-liq_adjust_desktop [data-testid="stNumberInput"] div[data-baseweb="input"]{min-height:34px!important;}
.st-key-liq_adjust_mobile [data-testid="stNumberInputContainer"],
.st-key-liq_adjust_desktop [data-testid="stNumberInputContainer"]{height:34px!important;}
.st-key-liq_adjust_mobile [data-testid="stHorizontalBlock"],
.st-key-liq_adjust_desktop [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;align-items:center!important;gap:8px!important;min-height:36px!important;}
.st-key-liq_adjust_mobile [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
.st-key-liq_adjust_desktop [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{min-width:0!important;}
.st-key-liq_adjust_mobile [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
.st-key-liq_adjust_mobile [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3),
.st-key-liq_adjust_desktop [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
.st-key-liq_adjust_desktop [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3){flex:0 0 44px!important;width:44px!important;}
.st-key-liq_adjust_mobile [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2),
.st-key-liq_adjust_desktop [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){flex:1 1 auto!important;width:auto!important;}
.st-key-liq_adjust_mobile [data-testid="stColumn"] [data-testid="stVerticalBlock"],
.st-key-liq_adjust_desktop [data-testid="stColumn"] [data-testid="stVerticalBlock"],
.st-key-liq_adjust_mobile [data-testid="stElementContainer"]:has([data-testid="stButton"]),
.st-key-liq_adjust_desktop [data-testid="stElementContainer"]:has([data-testid="stButton"]){width:100%!important;}
.st-key-liq_adjust_mobile [data-testid="stButton"],
.st-key-liq_adjust_desktop [data-testid="stButton"]{width:100%!important;display:block!important;}
.st-key-liq_adjust_mobile [data-testid="stButton"] div,
.st-key-liq_adjust_desktop [data-testid="stButton"] div{width:100%!important;}
.st-key-liq_adjust_mobile [data-testid="stButton"] button,
.st-key-liq_adjust_desktop [data-testid="stButton"] button{height:34px!important;width:100%!important;min-width:0!important;
  border-radius:10px!important;border:1px solid rgba(139,92,246,.42)!important;background:rgba(17,21,27,.72)!important;
  color:#f2f4f8!important;font-size:18px!important;font-weight:500!important;line-height:1!important;padding:0!important;
  box-shadow:0 0 14px rgba(124,58,237,.12)!important;}
.st-key-liq_adjust_mobile [data-testid="stButton"] button:hover,
.st-key-liq_adjust_desktop [data-testid="stButton"] button:hover{border-color:#8b5cf6!important;background:rgba(139,92,246,.16)!important;}
.st-key-liq_adjust_mobile [data-testid="stNumberInputStepUp"],
.st-key-liq_adjust_mobile [data-testid="stNumberInputStepDown"],
.st-key-liq_adjust_desktop [data-testid="stNumberInputStepUp"],
.st-key-liq_adjust_desktop [data-testid="stNumberInputStepDown"]{display:none!important;}
@media(max-width:760px){
  [data-testid="stVerticalBlock"]:has(.mobile-viz-grid-marker){display:flex!important;}
  [data-testid="stVerticalBlock"]:has(.mobile-liq-adjust){display:flex!important;}
  .st-key-liq_adjust_desktop{display:none!important;}
}
.st-key-mobile_viz_grid [data-testid="stHorizontalBlock"],
.st-key-desktop_viz_grid [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;gap:8px!important;align-items:stretch!important;}
.st-key-mobile_viz_grid [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2),
.st-key-desktop_viz_grid [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){flex:0 0 52px!important;width:52px!important;min-width:52px!important;}
.st-key-mobile_viz_grid [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
.st-key-desktop_viz_grid [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1){flex:1 1 calc(100% - 60px)!important;width:calc(100% - 60px)!important;min-width:0!important;max-width:calc(100% - 60px)!important;}
.st-key-mobile_viz_grid .mobile-viz,
.st-key-desktop_viz_grid .desktop-viz{width:100%!important;min-width:0!important;}
.st-key-mobile_viz_grid .ocard:has(.vizrel),
.st-key-desktop_viz_grid .ocard:has(.vizrel){height:auto!important;min-height:0!important;display:flex!important;flex-direction:column!important;}
.st-key-mobile_viz_grid .vizrel,
.st-key-desktop_viz_grid .vizrel{flex:0 0 auto!important;display:block!important;overflow:visible!important;}
.st-key-mobile_viz_grid .vizrel svg,
.st-key-desktop_viz_grid .vizrel svg{width:100%!important;height:auto!important;max-height:none!important;}
.st-key-liq_rail_mobile,.st-key-liq_rail_desktop{height:100%;}
.liq-rail-card{height:276px;min-height:276px;margin-top:37px;border:1px solid rgba(139,92,246,.38);border-radius:10px;
  background:#13101e;box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:8px 6px;display:flex;flex-direction:column;align-items:center;justify-content:space-between;color:#dfe3e8;}
.liq-rail-label{font-size:8px;font-weight:780;letter-spacing:.08em;color:#8b94a0;line-height:1;text-transform:uppercase;}
.liq-rail-track{position:relative;width:4px;flex:1;min-height:196px;border-radius:999px;background:rgba(139,148,158,.22);margin:7px 0;}
.liq-rail-track::before{content:"";position:absolute;inset:0;border-radius:999px;background:linear-gradient(180deg,rgba(224,163,62,.45),rgba(224,163,62,.10));}
.liq-rail-dragzone{position:absolute;left:50%;top:-6px;bottom:-6px;width:48px;transform:translateX(-50%);
  touch-action:none;cursor:grab;z-index:4;}
.liq-rail-dragzone.dragging{cursor:grabbing;}
.liq-rail-dot{position:absolute;left:50%;width:14px;height:14px;border-radius:999px;transform:translate(-50%,-50%);
  background:#e0a33e;border:2px solid #17121e;box-shadow:0 0 0 1px rgba(224,163,62,.7),0 0 14px rgba(224,163,62,.22);z-index:5;pointer-events:none;}
.liq-rail-value{font-size:9px;font-weight:760;color:#e0a33e;line-height:1;font-variant-numeric:tabular-nums;}
.liq-rail-lev{font-size:8px;font-weight:760;color:#f2f4f8;line-height:1;font-variant-numeric:tabular-nums;margin-top:3px;}
.st-key-liq_rail_mobile [data-testid="stButton"],
.st-key-liq_rail_desktop [data-testid="stButton"],
.st-key-liq_rail_mobile [data-testid="stElementContainer"]:has([data-testid="stButton"]),
.st-key-liq_rail_desktop [data-testid="stElementContainer"]:has([data-testid="stButton"]){display:none!important;width:100%!important;}
.st-key-liq_rail_mobile [data-testid="stButton"] button,
.st-key-liq_rail_desktop [data-testid="stButton"] button{width:100%!important;height:34px!important;min-width:0!important;padding:0!important;border-radius:10px!important;
  border:1px solid rgba(139,92,246,.42)!important;background:rgba(17,21,27,.72)!important;color:#e0a33e!important;
  font-size:16px!important;line-height:1!important;box-shadow:0 0 14px rgba(124,58,237,.12)!important;}
.mxec{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:12px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:12px 13px;margin:0 0 6px;color:#dfe3e8;}
.mxec-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:11px;}
.mxec-title{font-size:10px;font-weight:740;letter-spacing:.08em;text-transform:uppercase;color:#8b94a0;}
.mxec-dir{font-size:10px;font-weight:820;letter-spacing:.05em;border:1px solid currentColor;border-radius:6px;padding:3px 8px;}
.mxec-dir.long{color:#0ecb81;background:rgba(14,203,129,.06);}
.mxec-dir.short{color:#f6465d;background:rgba(246,70,93,.06);}
.mxec-main{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:10px;}
.mxec-kpi{border:1px solid rgba(230,232,235,.10);border-radius:9px;background:rgba(17,21,27,.68);padding:9px 10px;}
.mxec-l{font-size:9px;font-weight:720;letter-spacing:.06em;text-transform:uppercase;color:#8b94a0;line-height:1.1;}
.mxec-v{font-size:20px;font-weight:780;line-height:1.1;color:#f2f4f8;margin-top:5px;font-variant-numeric:tabular-nums;}
.mxec-v.blue{color:#4c8dff;}.mxec-v.red{color:#f6465d;}.mxec-v.amber{color:#e0a33e;}
.mxec-margin .mxec-v{min-height:22px;}
.mxec-margin-edit{display:flex;align-items:baseline;gap:2px;}
.mxec-margin-edit span{color:#e0a33e;}
.mxec-margin-input{width:100%;min-width:0;border:0!important;background:transparent!important;box-shadow:none!important;
  color:#e0a33e!important;font:inherit!important;line-height:inherit!important;padding:0!important;margin:0!important;
  outline:none!important;-webkit-appearance:none;appearance:textfield;}
.mxec-margin-input::-webkit-outer-spin-button,.mxec-margin-input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0;}
.mxec-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.mxec-cell{min-width:0;border-left:1px solid rgba(139,148,158,.18);padding-left:9px;}
.mxec-cell:nth-child(odd){border-left:0;padding-left:0;}
.mxec-cell .mxec-l{font-size:8.5px;}
.mxec-cell .mxec-v{font-size:16px;font-weight:740;margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.mxec-cell.entry .mxec-v{color:#f2f4f8;}
.mxec-cell.stop .mxec-v{color:#f6465d;}
.mxec-cell.tp .mxec-v{color:#0ecb81;}
.mxec-cell.rr .mxec-v{color:#4c8dff;}
.mxec-cell.rr .mxec-v{display:flex;align-items:baseline;justify-content:space-between;gap:8px;width:100%;}
.mxec-reward{display:inline-block;font-size:16px;font-weight:740;color:#f2f4f8;margin-left:0;line-height:1.1;
  font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right;}
.mxec-note{border-top:1px solid rgba(139,148,158,.16);margin-top:10px;padding-top:8px;color:#8b94a0;font-size:10.5px;line-height:1.35;}
.st-key-blank_exec_inputs{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:12px;
  box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);
  padding:12px 13px;margin:0 0 12px;color:#dfe3e8;}
.st-key-blank_exec_inputs [data-testid="stNumberInput"] label p{font-size:9px!important;line-height:1!important;
  color:#8b94a0!important;text-transform:uppercase!important;font-weight:760!important;letter-spacing:.06em!important;}
.st-key-blank_exec_inputs [data-testid="stNumberInputContainer"]{height:38px!important;}
.st-key-blank_exec_inputs div[data-baseweb="input"]{min-height:38px!important;background:#11151b!important;
  border:1px solid #232a33!important;border-radius:8px!important;}
.st-key-blank_exec_inputs div[data-baseweb="input"]:focus-within{border-color:#4c8dff!important;}
.st-key-blank_exec_inputs input{font-size:16px!important;font-weight:740!important;font-variant-numeric:tabular-nums!important;}
</style>""",
    unsafe_allow_html=True,
)


# Blank-calc symbol box — a compact text field above the live price, styled to match the
# numeric inputs (dark field, bold uppercase value). Only rendered in Blank Calc mode.
st.markdown(
    """<style>
/* Symbol field — a compact ticker input dropped into the BOTTOM-RIGHT corner of the live-price
   card (blank mode only). Same UX as the Market Scanner's "Ticker…" field: a standard
   rectangular input (NOT a pill), sized to a ticker + USDT, no dropdown. It's rendered outside
   the 2s price fragment so typing is never interrupted; CSS positions it in the corner. */
/* the price column is the positioning context for the corner symbol box */
[data-testid="stColumn"]:has(.st-key-symbox){position:relative!important;}
/* Once a 2nd child (the symbox) joins the column, Streamlit inserts a layout wrapper that
   collapses to the price card's content height instead of the row height, leaving dead space
   below the card. The wrapper's height won't resolve via the parent chain, so make the price
   card itself absolutely fill the column: neutralise the intermediate wrappers' positioning
   (so the relative column becomes the offset parent), then pin .hmain to inset:0. */
[data-testid="stColumn"]:has(.st-key-symbox) [data-testid="stLayoutWrapper"]:has(.dash),
[data-testid="stColumn"]:has(.st-key-symbox) [data-testid="stElementContainer"]:has(.dash),
[data-testid="stColumn"]:has(.st-key-symbox) [data-testid="stMarkdown"]:has(.dash),
[data-testid="stColumn"]:has(.st-key-symbox) [data-testid="stMarkdownContainer"]:has(.dash),
[data-testid="stColumn"]:has(.st-key-symbox) .dash{position:static!important;}
[data-testid="stColumn"]:has(.st-key-symbox) .hmain{position:absolute!important;inset:0!important;}
/* reserve a bottom strip in the price content so the corner input never overlaps the headline */
[data-testid="stColumn"]:has(.st-key-symbox) .hprice-col{padding-bottom:48px!important;}
/* drop the symbol picker into the card's bottom-right corner — auto height (the column's
   stretch rule must NOT make it full-height), error stacks above the bottom-anchored input */
[data-testid="stColumn"]:has(.st-key-symbox) .st-key-symbox{position:absolute!important;
  right:13px;bottom:11px;z-index:6;width:150px!important;height:auto!important;margin:0!important;
  display:flex!important;flex-direction:column!important;align-items:flex-end!important;gap:2px!important;}
.st-key-symbox [data-testid="stTextInput"]{width:150px!important;}
.st-key-symbox [data-testid="stTextInput"] div[data-baseweb="input"]{background:#11151b!important;
  border:1px solid #232a33!important;border-radius:8px!important;min-height:38px!important;}
.st-key-symbox [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within{border-color:#4c8dff!important;}
.st-key-symbox [data-testid="stTextInput"] input{background:transparent!important;color:#dfe3e8!important;
  font-weight:700!important;letter-spacing:.02em;text-transform:uppercase;text-align:left;
  padding:6px 10px!important;}
/* resting "Ticker…" hint — normal-case + muted, mirroring the scanner's placeholder */
.st-key-symbox [data-testid="stTextInput"] input::placeholder{text-transform:none!important;
  font-weight:400!important;letter-spacing:normal;color:#6b747e!important;opacity:1!important;}
.st-key-symbox .symerr{color:#f6465d;font-size:9px;font-weight:700;margin-top:2px;line-height:1.2;
  white-space:normal;max-width:150px;}
</style>""",
    unsafe_allow_html=True,
)

_DOWN_ARROW_URI = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(Path("assets/down-arrow.svg").read_bytes()).decode()
)
_PIGGY_BANK_URI = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(Path("assets/piggy-bank.svg").read_bytes()).decode()
)
_DATA_ANALYTICS_URI = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(Path("assets/data-analytics.svg").read_bytes()).decode()
)
st.markdown(
    f"""<style>
.piggy-mask{{
  -webkit-mask:url("{_PIGGY_BANK_URI}") center/contain no-repeat;
  mask:url("{_PIGGY_BANK_URI}") center/contain no-repeat;
}}
.analytics-mask{{
  display:block;width:17px;height:17px;flex:0 0 17px;background:#9a7cff;
  -webkit-mask:url("{_DATA_ANALYTICS_URI}") center/contain no-repeat;
  mask:url("{_DATA_ANALYTICS_URI}") center/contain no-repeat;
}}
.st-key-inputs_card{{position:relative!important;}}
.st-key-inputs_card [data-testid="stExpander"]{{
  border:0!important;background:transparent!important;box-shadow:none!important;margin:0!important;
}}
.st-key-inputs_card details{{
  border:0!important;background:transparent!important;box-shadow:none!important;margin:0!important;padding:0!important;
}}
.st-key-inputs_card details>summary{{
  list-style:none!important;display:flex!important;align-items:center!important;justify-content:space-between!important;
  min-height:22px!important;padding:0 0 8px!important;margin:0!important;cursor:pointer!important;
  color:#8b94a0!important;background:transparent!important;border:0!important;box-shadow:none!important;
}}
.st-key-inputs_card details:not([open])>summary{{
  transform:translateY(13px)!important;min-height:22px!important;padding:0!important;
}}
.st-key-inputs_card details[open]>summary{{
  transform:none!important;min-height:22px!important;padding:0 0 8px!important;
}}
.st-key-inputs_card details>summary::-webkit-details-marker{{display:none!important;}}
.st-key-inputs_card details>summary p{{
  margin:0!important;color:#8b94a0!important;font-size:10.5px!important;font-weight:700!important;
  letter-spacing:.08em!important;text-transform:uppercase!important;line-height:1.15!important;
}}
.st-key-inputs_card details>summary svg{{display:none!important;}}
.st-key-inputs_card details>summary [data-testid="stIconMaterial"]{{
  display:none!important;font-size:0!important;line-height:0!important;width:0!important;height:0!important;
  margin:0!important;padding:0!important;overflow:hidden!important;
}}
.st-key-inputs_card details>summary span:has(> [data-testid="stIconMaterial"]){{
  display:none!important;width:0!important;height:0!important;margin:0!important;padding:0!important;overflow:hidden!important;
}}
.st-key-inputs_card details>summary [data-testid="stIconMaterial"]+*{{
  margin-left:0!important;
}}
.st-key-inputs_card details>summary::after{{
  content:"";display:block;width:13px;height:13px;flex:0 0 13px;background:#8b94a0;
  -webkit-mask:url("{_DOWN_ARROW_URI}") center/contain no-repeat;
  mask:url("{_DOWN_ARROW_URI}") center/contain no-repeat;
  transition:transform .16s ease,background-color .12s ease;
}}
.st-key-inputs_card details[open]>summary::after{{transform:rotate(180deg);}}
.st-key-inputs_card details>summary:hover::after{{background:#f2f4f8;}}
.st-key-inputs_card details [data-testid="stExpanderDetails"]{{
  padding:0!important;margin:0!important;border:0!important;background:transparent!important;
}}
@media(max-width:700px){{
  .st-key-inputs_card{{
    min-height:0!important;height:auto!important;overflow:visible!important;z-index:30!important;
  }}
  .st-key-inputs_card [data-testid="stExpander"]{{
    height:auto!important;min-height:0!important;overflow:visible!important;
  }}
  .st-key-inputs_card details{{
    height:auto!important;min-height:0!important;overflow:visible!important;
  }}
  .st-key-inputs_card details>summary,
  .st-key-inputs_card details[open]>summary,
  .st-key-inputs_card details:not([open])>summary{{
    position:relative!important;left:auto!important;right:auto!important;top:auto!important;
    transform:none!important;min-height:34px!important;padding:4px 0 8px!important;margin:0!important;
    cursor:default!important;
  }}
  .st-key-inputs_card details>summary::after,
  .st-key-inputs_card details[open]>summary::after,
  .st-key-inputs_card details>summary:hover::after{{
    content:none!important;display:none!important;width:0!important;height:0!important;
  }}
  .st-key-inputs_card details [data-testid="stExpanderDetails"]{{
    position:relative!important;left:auto!important;right:auto!important;top:auto!important;
    z-index:auto!important;max-height:none!important;overflow:visible!important;
    padding:4px 0 0!important;margin:0!important;border:0!important;border-radius:0!important;
    background:transparent!important;box-shadow:none!important;
  }}
  .st-key-inputs_card details:not([open]) [data-testid="stExpanderDetails"]{{
    display:none!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stExpanderDetails"]{{
    display:block!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"]{{
    height:auto!important;min-height:0!important;overflow:visible!important;gap:8px!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stExpanderDetails"] [data-testid="stElementContainer"]:has([data-testid="stNumberInput"]){{
    margin:0!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stNumberInput"]{{
    margin:0!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stNumberInput"] label{{
    min-height:0!important;margin:0 0 3px!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stNumberInput"] label p{{
    font-size:9px!important;line-height:1.05!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stNumberInput"] div[data-baseweb="input"]{{
    min-height:38px!important;
  }}
  .st-key-inputs_card details[open] [data-testid="stNumberInputContainer"]{{
    height:38px!important;
  }}
}}
</style>""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Which coin? (persisted; mirrors the most-recently-pushed trade)
# --------------------------------------------------------------------------- #
_pushed = st.query_params.get("symbol")
_pushed_entry = st.query_params.get("entry")
_push_sig = "|".join([
    str(st.query_params.get(k) or "")
    for k in ("symbol", "dir", "entry", "stop", "t1", "t2")
])
_fresh_push = bool(_push_sig.strip("|")) and st.session_state.get("calc_last_push_sig") != _push_sig
if not (_pushed or _pushed_entry) and "calc_context_user_selected" not in st.session_state:
    st.session_state["calc_blank"] = True
else:
    st.session_state.setdefault("calc_blank", True)
if _pushed or _pushed_entry:
    st.session_state["calc_blank"] = False
if _pushed:
    _pu = _pushed.upper()
    st.session_state["calc_symbol"] = _pu
    if _fresh_push and not _pushed_entry:
        st.session_state.pop("calc_pushed_levels", None)
    # A fresh push from the dashboard reloads the plan: drop any persisted edits/shadows for the
    # pushed symbol once. Keep the URL params so a browser refresh can rebuild the same trade.
    if _fresh_push:
        st.session_state["calc_inputs_open"] = False
        for _s in ("entry", "stop", "t1", "t2"):
            st.session_state.pop(f"{_s}_{_pu}", None)
            st.session_state.pop(f"pv_{_s}_{_pu}", None)
_blank_mode = bool(st.session_state.get("calc_blank"))
if _blank_mode:
    # Blank Calc is an ad-hoc calculator on ANY coin — it defaults to BTCUSDT rather than
    # inheriting the pushed trade's symbol, and tracks its own ticker independent of the plan.
    symbol = (st.session_state.get("calc_blank_symbol") or "BTCUSDT").upper()
else:
    symbol = (st.session_state.get("calc_symbol") or dashboard.latest_symbol()).upper()
coin = symbol[:-4] if symbol.endswith("USDT") else symbol

data = dashboard.load_analysis(symbol)
# Blank Calc ignores the inherited plan and starts empty; you fill Entry / Stop / TPs yourself.
levels = {} if _blank_mode else (data or {}).get("levels", {})
_saved_push = st.session_state.get("calc_pushed_levels") or {}
if not _blank_mode and _saved_push.get("symbol") == symbol:
    levels = dict(_saved_push.get("levels") or levels)
# Direction: in Blank Calc it's a user choice (persisted); in Push Trade it follows the plan.
if _blank_mode:
    direction = (st.session_state.get("calc_blank_direction") or "long").lower()
else:
    direction = (levels.get("direction") or "long").lower()
is_long = direction != "short"

# Per-setup push from the v3 pattern cards: explicit levels in the URL override the
# file plan (backward-compatible — symbol-only pushes are unaffected).
_qp_entry = _pushed_entry
if _qp_entry and not _blank_mode:
    try:
        levels = {
            "direction": (st.query_params.get("dir") or "long").lower(),
            "entry": float(_qp_entry),
            "stop": float(st.query_params.get("stop") or 0),
            "target1": float(st.query_params.get("t1") or 0),
            "target2": float(st.query_params.get("t2") or 0),
        }
        st.session_state["calc_pushed_levels"] = {"symbol": symbol, "levels": dict(levels)}
        direction = levels["direction"]
        is_long = direction != "short"
        if _fresh_push:
            for _s in ("entry", "stop", "t1", "t2"):
                st.session_state.pop(f"{_s}_{symbol}", None)
                st.session_state.pop(f"pv_{_s}_{symbol}", None)
            st.session_state["calc_last_push_sig"] = _push_sig
    except (TypeError, ValueError):
        pass
elif _fresh_push:
    st.session_state["calc_last_push_sig"] = _push_sig

# Level-input keys are namespaced per mode so Blank Calc levels never collide with a pushed
# trade on the same symbol — each set persists independently across mode switches.
_kpfx = "blank_" if _blank_mode else ""
K_ENTRY = f"entry_{_kpfx}{symbol}"
K_STOP = f"stop_{_kpfx}{symbol}"
K_T1 = f"t1_{_kpfx}{symbol}"
K_T2 = f"t2_{_kpfx}{symbol}"

MMR = 0.005  # isolated-margin maintenance margin rate (Bybit default tier)

_liq_drag = st.query_params.get("liq_drag")
if _liq_drag and not _blank_mode:
    try:
        _target_liq = float(_liq_drag)
        _entry_for_liq = float(st.session_state.get(K_ENTRY, levels.get("entry", 0.0)) or 0)
        if _target_liq > 0 and _entry_for_liq > 0:
            _denom = (
                1 + MMR - _target_liq / _entry_for_liq
                if is_long else
                _target_liq / _entry_for_liq - 1 + MMR
            )
            if _denom > 0:
                _lev_100_liq = (
                    _entry_for_liq * (1 - 1 / 100 + MMR)
                    if is_long else
                    _entry_for_liq * (1 + 1 / 100 - MMR)
                )
                _target_liq = min(_target_liq, _lev_100_liq) if is_long else max(_target_liq, _lev_100_liq)
                _denom = (
                    1 + MMR - _target_liq / _entry_for_liq
                    if is_long else
                    _target_liq / _entry_for_liq - 1 + MMR
                )
                st.session_state["calc_lev"] = round(max(1.0, min(100.0, 1 / _denom)), 2)
                st.session_state["calc_liq_drag_applied"] = True
                st.session_state["calc_scroll_to_liq"] = True
    except (TypeError, ValueError):
        pass
    try:
        del st.query_params["liq_drag"]
    except Exception:
        pass

_qp_lev = st.query_params.get("lev")
if _qp_lev and not _blank_mode:
    try:
        _lev_from_url = float(_qp_lev)
        st.session_state["calc_lev"] = round(max(1.0, min(100.0, _lev_from_url)), 2)
        st.session_state["calc_liq_drag_applied"] = True
    except (TypeError, ValueError):
        pass

# --------------------------------------------------------------------------- #
# Trade Journal — "Push to Journal" posts the planned trade to a Google Sheet via an
# Apps Script web app (URL in journal_config.json, gitignored). See journal/SETUP.md.
# --------------------------------------------------------------------------- #
_JOURNAL_CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "journal_config.json")


def _journal_config():
    try:
        with open(_JOURNAL_CFG_PATH) as f:
            c = json.load(f)
        return (c.get("webhook_url") or "").strip(), (c.get("token") or "").strip()
    except Exception:
        return "", ""


def _post_journal(payload: dict):
    """POST a trade row to the journal web app. Returns (ok, message)."""
    url, token = _journal_config()
    if not url:
        return False, "No journal webhook set — add it to journal_config.json (see journal/SETUP.md)."
    if token:
        payload = {**payload, "token": token}
    try:
        # Apps Script web apps 302-redirect to googleusercontent.com — follow it.
        r = httpx.post(url, json=payload, timeout=12, follow_redirects=True)
        r.raise_for_status()
        try:
            body = r.json()
            if isinstance(body, dict) and body.get("ok") is False:
                return False, str(body.get("error", "rejected by script"))
        except Exception:
            pass
        return True, "ok"
    except Exception as e:
        return False, str(e)


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def fpx(v: float) -> str:
    a = abs(v)
    if a >= 1000:
        return f"{v:,.2f}"
    if a >= 1:
        return f"{v:,.4f}"
    if a >= 0.01:
        return f"{v:.4f}"
    return f"{v:.6f}"


def fusd(v: float) -> str:
    return f"${v:,.2f}"


def fpct(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# Account details (balance / risk / leverage) persist to a small JSON so they survive
# reloads and coin pushes — they're your settings, not part of the trade plan.
_PREFS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calc_prefs.json")


def _load_prefs():
    try:
        with open(_PREFS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_prefs(**kw):
    try:
        cur = _load_prefs()
        # Drop None values — in exposure mode the risk widget isn't rendered (and vice
        # versa), so st.session_state.get(...) returns None for it; writing that would
        # clobber the stored value and crash float() on the next load.
        cur.update({k: v for k, v in kw.items() if v is not None})
        with open(_PREFS_PATH, "w") as f:
            json.dump(cur, f)
    except Exception:
        pass


def _persist_account():
    """Save the account settings — fired only when you actually change one of the
    inputs (not on every rerun), so the value you type is remembered next session."""
    if st.session_state.get("calc_equity") is not None:
        st.session_state["calc_mobile_equity"] = st.session_state.get("calc_equity")
    if st.session_state.get("calc_risk") is not None:
        st.session_state["calc_mobile_risk"] = st.session_state.get("calc_risk")
    _save_prefs(
        equity=st.session_state.get("calc_equity"),
        risk_pct=st.session_state.get("calc_risk"),
        leverage=st.session_state.get("calc_lev"),
    )


def _persist_mode():
    _save_prefs(mode="exposure" if st.session_state.get("calc_mode") else "risk")


# Exposure mode: margin can be entered as a $ amount OR a % of balance — the two stay in
# sync (edit either, the other follows). The $ value is the canonical one used in the maths.
def _sync_margin_from_usd():
    bal = float(st.session_state.get("calc_equity", 0) or 0)
    usd = float(st.session_state.get("calc_margin_usd", 0) or 0)
    st.session_state["calc_margin_pct"] = round(usd / bal * 100, 4) if bal else 0.0
    _save_prefs(margin_usd=usd, margin_pct=st.session_state["calc_margin_pct"])


def _sync_margin_from_pct():
    bal = float(st.session_state.get("calc_equity", 0) or 0)
    pct = float(st.session_state.get("calc_margin_pct", 0) or 0)
    st.session_state["calc_margin_usd"] = round(pct * bal / 100, 2)
    _save_prefs(margin_usd=st.session_state["calc_margin_usd"], margin_pct=pct)


def _toggle_mode():
    """Flip Protect ⇄ Maximise sizing mode (on_click for the pill toggle) and persist it."""
    st.session_state["calc_mode"] = not st.session_state.get("calc_mode", False)
    _save_prefs(mode="exposure" if st.session_state["calc_mode"] else "risk")


def _set_mode(exposure: bool):
    """Segmented sizing toggle: select Protect (exposure=False) or Maximise (exposure=True)."""
    st.session_state["calc_mode"] = exposure
    _save_prefs(mode="exposure" if exposure else "risk")


def _set_blank(blank: bool):
    """Segmented context toggle: select Push Trade (blank=False) or Blank Calc (blank=True)."""
    st.session_state["calc_context_user_selected"] = True
    st.session_state["calc_blank"] = blank
    # First-ever entry into Blank Calc seeds BTCUSDT + an empty Ticker field. On every later
    # entry we leave the blank-calc symbol/levels/direction exactly as you left them — they
    # live in their own namespaced session keys, so they persist across mode switches and
    # never collide with the pushed trade. (Push Trade levels load from the plan via value=.)
    if blank and not st.session_state.get("calc_blank_symbol"):
        st.session_state["calc_blank_symbol"] = "BTCUSDT"
        st.session_state["calc_symbol_input"] = ""
        st.session_state["calc_sym_err"] = ""


def _set_direction(d: str):
    """Blank-calc Direction toggle: set Long / Short (persisted)."""
    st.session_state["calc_blank_direction"] = d


def _clear_blank_inputs():
    """Refresh button (on_click, runs before the inputs re-render): zero out the Blank Calc
    Entry/Stop/Targets and their shadows so you can enter a fresh trade. We SET the values to
    0 (rather than popping the keys) so the displayed fields actually update, not just the maths."""
    _sym = (st.session_state.get("calc_blank_symbol") or "BTCUSDT").upper()
    for n in ("entry", "stop", "t1", "t2"):
        k = f"{n}_blank_{_sym}"
        st.session_state[k] = 0.0
        st.session_state[f"pv_{k}"] = 0.0


def _restore_plan():
    """Restore button (on_click): reload the pushed plan's levels into the Push Trade inputs +
    shadows, discarding any edits. Sets the values (not pop) so the displayed fields update too."""
    _sym = (st.session_state.get("calc_symbol") or dashboard.latest_symbol()).upper()
    lv = {}
    _saved = st.session_state.get("calc_pushed_levels") or {}
    if _saved.get("symbol") == _sym and isinstance(_saved.get("levels"), dict):
        lv = dict(_saved.get("levels") or {})
    if not lv and st.query_params.get("entry"):
        try:
            lv = {
                "entry": float(st.query_params.get("entry") or 0),
                "stop": float(st.query_params.get("stop") or 0),
                "target1": float(st.query_params.get("t1") or 0),
                "target2": float(st.query_params.get("t2") or 0),
            }
        except (TypeError, ValueError):
            lv = {}
    if not lv:
        lv = (dashboard.load_analysis(_sym) or {}).get("levels", {})
    for suffix, plankey in (("entry", "entry"), ("stop", "stop"), ("t1", "target1"), ("t2", "target2")):
        k = f"{suffix}_{_sym}"
        v = float(lv.get(plankey, 0.0))
        st.session_state[k] = v
        st.session_state[f"pv_{k}"] = v
    st.session_state["calc_inputs_open"] = True


def _apply_symbol():
    """Blank-calc symbol box: normalise the typed ticker to a Binance USDT-perp symbol,
    validate it against the live ticker, and point the whole page at it. An unknown ticker
    leaves the current symbol untouched and surfaces an inline error."""
    raw = re.sub(r"[^A-Z0-9]", "", (st.session_state.get("calc_symbol_input") or "").upper())
    if not raw:
        return
    sym = raw if raw.endswith("USDT") else raw + "USDT"
    if scanner.live_ticker(sym):
        st.session_state["calc_blank_symbol"] = sym   # blank-calc tracks its own ticker
        st.session_state["calc_symbol_input"] = ""    # reset to the "Ticker…" hint
        st.session_state["calc_sym_err"] = ""
    else:
        st.session_state["calc_sym_err"] = sym


def _apply_mobile_symbol():
    st.session_state["calc_symbol_input"] = st.session_state.get("calc_mobile_symbol_input", "")
    _apply_symbol()
    st.session_state["calc_mobile_symbol_input"] = ""


def _persist_balance_exposure():
    """Exposure mode: balance is a fixed reference. The margin-to-use is the canonical
    input, so when balance changes we keep the $ margin and re-derive the % from it."""
    _persist_account()
    _sync_margin_from_usd()


def _sync_mobile_equity():
    st.session_state["calc_equity"] = float(st.session_state.get("calc_mobile_equity", 0) or 0)
    _persist_account()


def _sync_mobile_risk():
    st.session_state["calc_risk"] = float(st.session_state.get("calc_mobile_risk", 0) or 0)
    _persist_account()


def _sync_mobile_margin_usd():
    st.session_state["calc_margin_usd"] = float(st.session_state.get("calc_mobile_margin_usd", 0) or 0)
    _sync_margin_from_usd()


def _sync_mobile_margin_input():
    max_margin = float(st.session_state.get("calc_mobile_margin_max", 0) or 0)
    if max_margin <= 0:
        max_margin = float(st.session_state.get("calc_mobile_equity", 0) or 0)
    typed_margin = clamp(float(st.session_state.get("calc_mobile_margin_usd_input", 0) or 0), 0.0, max_margin)
    st.session_state["calc_mobile_margin_usd"] = typed_margin
    st.session_state["calc_margin_usd"] = typed_margin
    _sync_margin_from_usd()


def _sync_mobile_leverage():
    st.session_state["calc_lev"] = float(st.session_state.get("calc_mobile_leverage", 1) or 1)
    _persist_account()


def _sync_mobile_leverage_input():
    typed_lev = float(clamp(st.session_state.get("calc_mobile_leverage_input", 1) or 1, 1.0, 100.0))
    st.session_state["calc_mobile_leverage"] = typed_lev
    st.session_state["calc_lev"] = typed_lev
    _persist_account()


def _set_mobile_margin_max():
    max_margin = float(st.session_state.get("calc_mobile_margin_max", 0) or 0)
    if max_margin <= 0:
        max_margin = float(st.session_state.get("calc_mobile_equity", 0) or 0)
    st.session_state["calc_mobile_margin_usd"] = max_margin
    st.session_state["calc_margin_usd"] = max_margin
    _sync_margin_from_usd()


def _set_mobile_leverage_max():
    st.session_state["calc_mobile_leverage"] = 100.0
    st.session_state["calc_lev"] = 100.0
    _persist_account()


RISK_GUARD_PCT = 2.0  # exposure mode warns when the derived loss-at-stop exceeds this % of balance


# --------------------------------------------------------------------------- #
# Brand row: brand (left) + symbol chip / direction (right) — same container
# pattern as the Trade Dashboard so the heading lands in the identical position.
# --------------------------------------------------------------------------- #
_mode_default = _load_prefs().get("mode", "risk")
st.session_state.setdefault("calc_mode", _mode_default == "exposure")
_exp_on = bool(st.session_state.get("calc_mode", False))
_blank = st.session_state.get("calc_blank", False)
_top_prefs = _load_prefs()
_bybit_account = _calculator_account_summary()
_bybit_equity = float(_bybit_account.get("equity") or 0)
_top_equity = float(st.session_state.get("calc_mobile_equity", st.session_state.get("calc_equity", _top_prefs.get("equity") or 10000.0)) or 0)
if _bybit_equity > 0:
    _top_equity = _bybit_equity
_top_risk_pct = float(st.session_state.get("calc_mobile_risk", st.session_state.get("calc_risk", _top_prefs.get("risk_pct") or 1.0)) or 0)
_top_risk_amt = _top_equity * _top_risk_pct / 100
_top_margin_usd = float(st.session_state.get("calc_mobile_margin_usd", st.session_state.get("calc_margin_usd", _top_prefs.get("margin_usd") or max(10.0, _top_equity * 0.10))) or 0)
_top_current_lev = float(st.session_state.get("calc_lev", _top_prefs.get("leverage") or 1.0) or 1.0)
st.session_state.setdefault("calc_mobile_equity", _top_equity)
st.session_state.setdefault("calc_mobile_risk", _top_risk_pct)
st.session_state.setdefault("calc_mobile_margin_usd", _top_margin_usd)
st.session_state.setdefault("calc_mobile_leverage", _top_current_lev)
st.session_state["calc_equity"] = _top_equity
st.session_state["calc_risk"] = _top_risk_pct
st.session_state["calc_margin_usd"] = _top_margin_usd


def _recommended_leverage_for_mobile() -> tuple[float, str]:
    try:
        e = float(levels.get("entry", 0) or 0)
        s = float(levels.get("stop", 0) or 0)
    except (TypeError, ValueError):
        e, s = 0.0, 0.0
    if not (e > 0 and s > 0 and e != s):
        return _top_current_lev, "current setting"
    buffer = 0.75  # stay comfortably below the theoretical liquidation-at-stop ceiling
    if is_long:
        denom = 1 + MMR - (s / e)
    else:
        denom = (s / e) - 1 + MMR
    if denom <= 0:
        return _top_current_lev, "check stop"
    max_safe = max(1.0, 1 / denom)
    rec = clamp(math.floor(max_safe * buffer * 2) / 2, 1.0, 25.0)
    return rec, "keeps liq beyond stop"


_top_rec_lev, _top_rec_source_note = _recommended_leverage_for_mobile()
_top_has_rec_lev = _top_rec_source_note == "keeps liq beyond stop"
_top_auto_lev = _top_rec_lev
_liq_drag_applied = bool(st.session_state.pop("calc_liq_drag_applied", False))
_trade_lev_sig = "|".join([
    symbol,
    direction,
    str(levels.get("entry", "")),
    str(levels.get("stop", "")),
    str(levels.get("target1", "")),
    str(levels.get("target2", "")),
])
if not _exp_on and not _liq_drag_applied and st.session_state.get("calc_lev_trade_sig") != _trade_lev_sig:
    st.session_state["calc_lev"] = float(_top_rec_lev)
    st.session_state["calc_lev_trade_sig"] = _trade_lev_sig
elif _liq_drag_applied:
    st.session_state["calc_lev_trade_sig"] = _trade_lev_sig
_top_display_lev = float(st.session_state.get("calc_lev", _top_rec_lev) or _top_rec_lev)


def _mobile_leverage_note(v: float) -> str:
    v = float(v or 1.0)
    if v <= 3:
        return "Conservative · Low risk exposure"
    if v <= 10:
        return "Moderate · Watch your margin"
    return "Aggressive · High liquidation risk"


_top_rec_note = _mobile_leverage_note(_top_display_lev) if _top_has_rec_lev else "Enter entry + stop to calculate"


def _leverage_scale_pct(v: float) -> float:
    ticks = [(1.0, 0.0), (10.0, 25.0), (25.0, 50.0), (50.0, 75.0), (100.0, 100.0)]
    v = clamp(float(v or 1.0), ticks[0][0], ticks[-1][0])
    for (v0, p0), (v1, p1) in zip(ticks, ticks[1:]):
        if v <= v1:
            return p0 + (v - v0) / (v1 - v0) * (p1 - p0)
    return 100.0


_top_lev_pct = _leverage_scale_pct(_top_display_lev) if _top_has_rec_lev else 0.0
_top_lev_text = f"{_top_display_lev:g}x" if _top_has_rec_lev else "—"
_wallet_icon = '<span class="mini-card-icon piggy-mask" aria-hidden="true"></span>'
_flash_icon = '<span class="mini-card-icon flash-mask" aria-hidden="true"></span>'


@st.fragment(run_every=2)
def _mobile_live_ticker_box():
    q = scanner.live_ticker(symbol)
    fallback_price = float(levels.get("entry", 0) or 0)
    price_txt = "$" + fpx(q["last"]) if q else ("$" + fpx(fallback_price) if fallback_price > 0 else "—")
    badge = dashboard._live_badge() if hasattr(dashboard, "_live_badge") else ""
    sym_txt = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
    st.markdown(
        f"<div class='mobile-live-ticker'>"
        f"<div class='mlt-symbol'><span>{sym_txt}</span>{badge}</div>"
        f"<div class='mlt-price'>{price_txt}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


_brow = st.container(key="brandrow")
with _brow:
    st.markdown(chrome.brand_html("POSITION", "CALCULATOR", "Bybit · USDT Perp"), unsafe_allow_html=True)
    with st.container(key="mobile_price_symbol_stack"):
        _mobile_live_ticker_box()
        if _blank_mode:
            with st.container(key="mobile_symbol_box"):
                _serr = st.session_state.get("calc_sym_err")
                if _serr:
                    st.markdown(f"<div class='symerr'>“{_serr}” not found</div>", unsafe_allow_html=True)
                st.text_input(
                    "Symbol",
                    key="calc_mobile_symbol_input",
                    on_change=_apply_mobile_symbol,
                    placeholder="TICKER",
                    label_visibility="collapsed",
                )
    # Page-level sizing/context controls sit beside the heading. The far-right
    # header space stays available for the shared trading-clock widget.
    with st.container(key="modestack"):
        with st.container(key="sizeseg"):
            st.button("Protect", key="segrisk_on" if not _exp_on else "segrisk_off",
                      on_click=_set_mode, args=(False,))
            st.button("Maximise", key="segexp_on" if _exp_on else "segexp_off",
                      on_click=_set_mode, args=(True,))
        with st.container(key="ctxseg"):
            st.button("Blank", key="segblank_on" if _blank else "segblank_off",
                      on_click=_set_blank, args=(True,))
            st.button("Preloaded", key="segpush_on" if not _blank else "segpush_off",
                      on_click=_set_blank, args=(False,))
    if _exp_on:
        with st.container(key="mobile_exposure_top"):
            _margin_max = max(10.0, float(st.session_state.get("calc_mobile_equity", _top_equity) or _top_equity or 10.0))
            st.session_state["calc_mobile_margin_max"] = _margin_max
            _margin_value = clamp(float(st.session_state.get("calc_mobile_margin_usd", _top_margin_usd) or 0), 0.0, _margin_max)
            _mobile_lev_value = float(clamp(st.session_state.get("calc_mobile_leverage", _top_current_lev), 1.0, 100.0))
            st.session_state["calc_mobile_margin_usd"] = _margin_value
            st.session_state["calc_margin_usd"] = _margin_value
            st.session_state["calc_mobile_leverage"] = _mobile_lev_value
            st.session_state["calc_lev"] = _mobile_lev_value
            st.session_state["calc_mobile_margin_usd_input"] = _margin_value
            st.session_state["calc_mobile_leverage_input"] = _mobile_lev_value
            _mobile_exposure_value = _margin_value * _mobile_lev_value
            _margin_pct_text = (_margin_value / _top_equity * 100) if _top_equity else 0
            with st.container(key="mobile_margin_control_row"):
                st.markdown(
                    "<div class='mobile-exposure-control'>"
                    "<div class='mec-copy'><span>Margin Deployed</span></div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                with st.container(key="mobile_margin_value_row"):
                    st.number_input(
                        "Margin Deployed Value",
                        min_value=0.0,
                        max_value=float(_margin_max),
                        step=1.0,
                        format="%.2f",
                        key="calc_mobile_margin_usd_input",
                        on_change=_sync_mobile_margin_input,
                        label_visibility="collapsed",
                    )
                    st.markdown(f"<div class='mec-inline-summary'>{_margin_pct_text:.1f}% of account equity</div>", unsafe_allow_html=True)
                _margin_slider, _margin_max_col = st.columns([1, 0.18], gap="small", vertical_alignment="center")
                with _margin_slider:
                    with st.container(key="mobile_margin_slider_full"):
                        st.slider(
                            "Margin Deployed",
                            min_value=0.0,
                            max_value=float(_margin_max),
                            value=float(_margin_value),
                            step=1.0,
                            format="$%.0f",
                            key="calc_mobile_margin_usd",
                            on_change=_sync_mobile_margin_usd,
                            label_visibility="collapsed",
                        )
                        st.markdown("<div class='mec-ticks'><span>$10</span><span>$50</span><span>$100</span><span>$200</span></div>", unsafe_allow_html=True)
                with _margin_max_col:
                    st.button("MAX", key="mobile_margin_max_btn", on_click=_set_mobile_margin_max, use_container_width=True)
                    st.markdown(f"<div class='mec-max-value'>${_margin_max:,.2f}</div>", unsafe_allow_html=True)
            with st.container(key="mobile_leverage_control_row"):
                st.markdown(
                    "<div class='mobile-exposure-control second'>"
                    "<div class='mec-copy'><span>Leverage</span></div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                with st.container(key="mobile_leverage_value_row"):
                    st.number_input(
                        "Leverage Value",
                        min_value=1.0,
                        max_value=100.0,
                        step=0.5,
                        format="%.1f",
                        key="calc_mobile_leverage_input",
                        on_change=_sync_mobile_leverage_input,
                        label_visibility="collapsed",
                    )
                    st.markdown(f"<div class='mec-inline-summary'>Exposure: ${_mobile_exposure_value:,.2f}</div>", unsafe_allow_html=True)
                _lev_slider, _lev_max_col = st.columns([1, 0.18], gap="small", vertical_alignment="center")
                with _lev_slider:
                    with st.container(key="mobile_leverage_slider_full"):
                        st.slider(
                            "Leverage",
                            min_value=1.0,
                            max_value=100.0,
                            value=_mobile_lev_value,
                            step=0.5,
                            format="%.1fx",
                            key="calc_mobile_leverage",
                            on_change=_sync_mobile_leverage,
                            label_visibility="collapsed",
                        )
                        st.markdown("<div class='mec-ticks'><span>1x</span><span>10x</span><span>25x</span><span>50x</span></div>", unsafe_allow_html=True)
                with _lev_max_col:
                    st.button("MAX", key="mobile_leverage_max_btn", on_click=_set_mobile_leverage_max, use_container_width=True)
                    st.markdown("<div class='mec-max-value'>100x</div>", unsafe_allow_html=True)
    with st.container(key="mobile_risk_box"):
        st.markdown(
            f"<div class='mobile-risk-mini'>"
            f"<div class='mini-card-head'>{_wallet_icon}<div class='mrm-label'>Capital at Risk</div></div>"
            f"<div class='mrm-value'>${_top_risk_amt:,.2f}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        mr_bal, mr_risk = st.columns([1.1, 0.9], gap="small")
        mr_bal.number_input(
            "Balance", min_value=0.0, step=100.0, format="%.0f",
            key="calc_mobile_equity", on_change=_sync_mobile_equity,
        )
        mr_risk.number_input(
            "Risk", min_value=0.0, step=0.1, format="%.2f",
            key="calc_mobile_risk", on_change=_sync_mobile_risk,
        )
    st.markdown(
        f"<div class='mobile-lev-mini'>"
        f"<div class='mini-card-head'>{_flash_icon}<div class='mlv-label'>Recommended Leverage</div></div>"
        f"<div class='mlv-value'>{_top_lev_text}</div>"
        f"<div class='mlv-sub'>{_top_rec_note}</div>"
        f"<div class='mlv-rail'>"
        f"<div class='mlv-track'></div><div class='mlv-fill' style='width:{_top_lev_pct:.2f}%'></div>"
        f"<div class='mlv-ticks'><span>1x</span><span>10x</span><span>25x</span><span>50x</span><span>100x</span></div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
mode = "exposure" if _exp_on else "risk"
is_exposure = mode == "exposure"

# --------------------------------------------------------------------------- #
# Top strip: live price + market bias (left) | account inputs (right)
# --------------------------------------------------------------------------- #
_pcard = data or {"symbol": f"{coin}/USDT", "contract": "PERP"}

# Direction box — its OWN box (no LIVE icon; not price data). Two stacked pill
# buttons; the side matching the trade is filled (active), the other is a coloured
# outline (inactive).
_long_cls = "active" if is_long else "inactive"
_short_cls = "active" if not is_long else "inactive"
_dir_box = (
    '<div class="ocard dirbox">'
    '<div class="chead"><span class="t">Direction</span></div>'
    '<div class="dirbtns">'
    f'<div class="dbtn long {_long_cls}">Long</div>'
    f'<div class="dbtn short {_short_cls}">Short</div>'
    "</div>"
    "</div>"
)


@st.fragment(run_every=2)
def _live_price_box():
    """Live PRICE box (its own box) — symbol + live price with the LIVE badge in the
    top-right corner. Refreshes every 2s; reference only (sizing uses Entry). The
    empty right_html means a single-column price box (no direction column)."""
    q = scanner.live_ticker(symbol)
    if q:
        dashboard.render_price_bias_card(
            _pcard, live_price="$" + fpx(q["last"]), live_chg=round(q["pct"], 2),
            right_html="",
        )
    else:
        dashboard.render_price_bias_card(_pcard, right_html="")


# Persisted account defaults (used only when a fresh session has no value yet).
_prefs = _load_prefs()
_eq_default = float(_prefs.get("equity") or 10000.0)
_rk_default = float(_prefs.get("risk_pct") or 1.0)
_lev_default = float(_prefs.get("leverage") or 1.0)
_margin_pct_default = float(_prefs.get("margin_pct") or 2.0)
_margin_usd_default = float(_prefs.get("margin_usd") or round(_eq_default * _margin_pct_default / 100, 2)) or round(_eq_default * 0.02, 2)
# Seed the two linked margin fields once (non-zero) so they're created from session_state
# rather than defaulting to the 0 min_value; the on_change callbacks keep them in sync.
st.session_state.setdefault("calc_margin_usd", _margin_usd_default)
st.session_state.setdefault("calc_margin_pct", _margin_pct_default)
# Leverage is seeded here so its widget can render in EITHER the standalone ⚡ box (risk
# mode) or folded into the Account box (exposure mode) without a value=/session clash.
st.session_state.setdefault("calc_lev", _lev_default)

# Leverage lives in its own editable box up top (beside Account). Read it from
# session_state here so the maths below can use it; editing the box reruns the script
# and this picks up the new value.
leverage = float(st.session_state.get("calc_lev", _lev_default))

# Leverage quality descriptor (label, colour, one-liner) — drives the ⚡ box's caption
# and recomputes live as the leverage value changes.
_lev_q = (("Conservative", "#0ecb81", "Low risk exposure") if leverage <= 3
          else ("Moderate", "#e0a33e", "Watch your margin") if leverage <= 10
          else ("Aggressive", "#f6465d", "High liquidation risk"))

# P&L preview — computed from the CURRENT inputs (read from session_state so this can
# render in the top strip, above the Trade Inputs box). The dollar P&L is fixed by
# your risk; leverage scales the RETURN ON MARGIN (the % column), not the dollars.
def _pnl_preview():
    g = lambda k, d: float(st.session_state.get(k, d) or 0)
    e = g(K_ENTRY, levels.get("entry", 0.0))
    s = g(K_STOP, levels.get("stop", 0.0))
    t1v = g(K_T1, levels.get("target1", 0.0))
    t2v = g(K_T2, levels.get("target2", 0.0))
    eqv, levv = g("calc_equity", _eq_default), g("calc_lev", _lev_default)
    sd = abs(e - s)
    if not (e > 0 and sd > 0 and levv > 0):
        return None
    if st.session_state.get("calc_mode"):                 # exposure: margin × leverage drives size
        margin = g("calc_margin_usd", _margin_usd_default)
        sz = (margin * levv) / e if e else 0.0
        risk_amt = sz * sd
    else:                                                 # risk: capital at risk is fixed
        risk_amt = eqv * g("calc_risk", _rk_default) / 100
        sz = risk_amt / sd
        margin = (sz * e) / levv
    p1, p2 = sz * abs(t1v - e), sz * abs(t2v - e)
    # Loss if price reaches the isolated-margin liquidation price (≈ the margin committed).
    liqp = e * (1 - 1 / levv + MMR) if is_long else e * (1 + 1 / levv - MMR)
    liqp = max(liqp, 0.0)
    return {"tp1": p1, "tp2": p2, "sl": risk_amt, "liq_loss": sz * abs(e - liqp),
            "r1": p1 / margin * 100 if margin else 0,
            "r2": p2 / margin * 100 if margin else 0,
            "rsl": risk_amt / margin * 100 if margin else 0,
            "rr1": abs(t1v - e) / sd, "rr2": abs(t2v - e) / sd}


_pnl = _pnl_preview()
if _pnl:
    # R:R tag per target — green when it clears the 1:2 floor, amber when it falls short.
    _rr = lambda v: f'<span class="rr {"ok" if v >= 2 else "lo"}">1 : {v:.1f}</span>'
    _pnl_rows = (
        f'<div class="pnlrow"><span class="pl">Profit → TP1</span><b class="pos">+${_pnl["tp1"]:,.2f}</b><span class="roe pos">+{_pnl["r1"]:.1f}%</span>{_rr(_pnl["rr1"])}</div>'
        f'<div class="pnlrow"><span class="pl">Profit → TP2</span><b class="pos">+${_pnl["tp2"]:,.2f}</b><span class="roe pos">+{_pnl["r2"]:.1f}%</span>{_rr(_pnl["rr2"])}</div>'
        f'<div class="pnlrow"><span class="pl">Loss → SL</span><b class="neg">−${_pnl["sl"]:,.2f}</b><span class="roe neg">−{_pnl["rsl"]:.1f}%</span><span class="rr base">1R</span></div>'
    )
else:
    # Skeleton: show the full P&L structure with muted dashes until levels are entered.
    _pnl_rows = (
        '<div class="pnlrow"><span class="pl">Profit → TP1</span><b class="skel">—</b><span class="roe skel">—</span><span class="rr skel">—</span></div>'
        '<div class="pnlrow"><span class="pl">Profit → TP2</span><b class="skel">—</b><span class="roe skel">—</span><span class="rr skel">—</span></div>'
        '<div class="pnlrow"><span class="pl">Loss → SL</span><b class="skel">—</b><span class="roe skel">—</span><span class="rr base">1R</span></div>'
    )
_pnl_box = (
    '<div class="ocard pnlbox">'
    '<div class="chead"><span class="t">P&amp;L</span></div>'
    f'<div class="pnlrows">{_pnl_rows}</div>'
    '<div class="pnlcap">% = return on margin (scales w/ leverage)<br>R:R tag turns green at ≥ 1:2</div>'
    "</div>"
)


def _mobile_execution_panel_from_state() -> str:
    g = lambda k, d: float(st.session_state.get(k, d) or 0)
    e = g(K_ENTRY, levels.get("entry", 0.0))
    s = g(K_STOP, levels.get("stop", 0.0))
    t1v = g(K_T1, levels.get("target1", 0.0))
    t2v = g(K_T2, levels.get("target2", 0.0))
    levv = g("calc_lev", _lev_default)
    eqv = g("calc_equity", _eq_default)
    sd = abs(e - s)
    side = "long" if is_long else "short"
    direction_label = "LONG" if is_long else "SHORT"
    if not (e > 0 and sd > 0 and levv > 0):
        size_txt = margin_txt = risk_txt = "—"
        margin_value = ""
        entry_txt = stop_txt = t1_txt = t2_txt = rr1_txt = rr2_txt = "—"
        rew1_txt = rew2_txt = "—"
        note = "Enter an entry and stop to calculate the position."
    else:
        if is_exposure:
            margin = g("calc_margin_usd", _margin_usd_default)
            sz = (margin * levv) / e if e else 0.0
            risk_amt = sz * sd
            margin_needed = margin
        else:
            risk_amt = eqv * g("calc_risk", _rk_default) / 100
            sz = risk_amt / sd
            margin_needed = (sz * e) / levv
        risk_pct_now = (risk_amt / eqv * 100) if eqv > 0 else 0.0
        size_txt = f"{sz:,.4f} {coin}"
        margin_txt = f"${margin_needed:,.2f}"
        margin_value = f"{margin_needed:.2f}"
        risk_txt = f"${risk_amt:,.2f}"
        entry_txt = fpx(e)
        stop_txt = fpx(s)
        t1_txt = fpx(t1v)
        t2_txt = fpx(t2v)
        rr1_txt = f"1 : {abs(t1v - e) / sd:.2f}" if t1v > 0 else "—"
        rr2_txt = f"1 : {abs(t2v - e) / sd:.2f}" if t2v > 0 else "—"
        rew1_txt = f"${sz * abs(t1v - e):,.2f}" if t1v > 0 else "—"
        rew2_txt = f"${sz * abs(t2v - e):,.2f}" if t2v > 0 else "—"
        note = f"Risk at stop: {risk_pct_now:.2f}% of account."
    return f"""
    <div class="mobile-exec">
      <div class="mxec">
        <div class="mxec-top">
          <div class="mxec-title">Bybit Execution</div>
          <div class="mxec-dir {side}">{direction_label}</div>
        </div>
        <div class="mxec-main">
          <div class="mxec-kpi"><div class="mxec-l">Position Size</div><div class="mxec-v">{size_txt}</div></div>
          <div class="mxec-kpi mxec-margin"><div class="mxec-l">Margin</div><div class="mxec-v amber">{margin_txt}</div></div>
        </div>
        <div class="mxec-grid">
          <div class="mxec-cell entry"><div class="mxec-l">Entry</div><div class="mxec-v">{entry_txt}</div></div>
          <div class="mxec-cell stop"><div class="mxec-l">Stop</div><div class="mxec-v">{stop_txt}</div></div>
          <div class="mxec-cell tp"><div class="mxec-l">TP1</div><div class="mxec-v">{t1_txt}</div></div>
          <div class="mxec-cell tp"><div class="mxec-l">TP2</div><div class="mxec-v">{t2_txt}</div></div>
          <div class="mxec-cell rr"><div class="mxec-l">RR1</div><div class="mxec-v">{rr1_txt}<span class="mxec-reward">{rew1_txt}</span></div></div>
          <div class="mxec-cell rr"><div class="mxec-l">RR2</div><div class="mxec-v">{rr2_txt}<span class="mxec-reward">{rew2_txt}</span></div></div>
        </div>
        <div class="mxec-note">{note}</div>
      </div>
    </div>
    """


def _risk_sized_notional_from_state() -> float:
    try:
        e = float(st.session_state.get(K_ENTRY, levels.get("entry", 0.0)) or 0)
        s = float(st.session_state.get(K_STOP, levels.get("stop", 0.0)) or 0)
        eqv = float(st.session_state.get("calc_equity", _eq_default) or 0)
        rkv = float(st.session_state.get("calc_risk", _rk_default) or 0)
    except (TypeError, ValueError):
        return 0.0
    sd = abs(e - s)
    if not (e > 0 and sd > 0 and eqv > 0 and rkv > 0):
        return 0.0
    risk_amt = eqv * rkv / 100
    size = risk_amt / sd
    return size * e


def _sync_leverage_from_margin_cap():
    if st.session_state.get("calc_mode"):
        return
    notional_v = _risk_sized_notional_from_state()
    try:
        margin_cap = float(st.session_state.get("calc_margin_cap", 0) or 0)
    except (TypeError, ValueError):
        margin_cap = 0.0
    if not (notional_v > 0 and margin_cap > 0):
        return
    next_lev = clamp(notional_v / margin_cap, 1.0, 100.0)
    st.session_state["calc_lev"] = round(next_lev, 2)
    try:
        e = float(st.session_state.get(K_ENTRY, levels.get("entry", 0.0)) or 0)
        if e > 0:
            next_liq = e * (1 - 1 / next_lev + MMR) if is_long else e * (1 + 1 / next_lev - MMR)
            st.query_params["lev"] = f"{next_lev:.2f}"
            st.query_params["liq"] = f"{max(next_liq, 0.0):.10f}"
    except Exception:
        pass
    st.session_state["calc_liq_drag_applied"] = True
    _persist_account()


def _render_trade_level_inputs(location: str):
    # BOTH modes persist edits across mode switches via a shadow value (pv_*): Streamlit
    # clears a widget's state when it isn't rendered, so we seed each input from its shadow
    # and re-save it each render.
    def _seed(key, plan_val):
        return float(st.session_state.get(f"pv_{key}", plan_val))

    st.session_state.setdefault(K_ENTRY, _seed(K_ENTRY, float(levels.get("entry", 0.0))))
    st.session_state.setdefault(K_STOP, _seed(K_STOP, float(levels.get("stop", 0.0))))
    st.session_state.setdefault(K_T1, _seed(K_T1, float(levels.get("target1", 0.0))))
    st.session_state.setdefault(K_T2, _seed(K_T2, float(levels.get("target2", 0.0))))

    if location == "execution":
        with st.container(key="blank_exec_inputs"):
            st.markdown("<div class='chead'><span class='t'>Trade Inputs</span></div>", unsafe_allow_html=True)
            r1c1, r1c2 = st.columns(2, gap="small")
            with r1c1:
                entry_v = st.number_input("Entry Price", min_value=0.0, step=0.0001, format="%.4f", key=K_ENTRY)
            with r1c2:
                stop_v = st.number_input("Stop Loss", min_value=0.0, step=0.0001, format="%.4f", key=K_STOP)
            r2c1, r2c2 = st.columns(2, gap="small")
            with r2c1:
                t1_v = st.number_input("Target 1", min_value=0.0, step=0.0001, format="%.4f", key=K_T1)
            with r2c2:
                t2_v = st.number_input("Target 2", min_value=0.0, step=0.0001, format="%.4f", key=K_T2)
    else:
        title = "Trade Input" if _blank_mode else "Trade Input - Manual Override"
        with st.expander(title, expanded=False):
            entry_v = st.number_input("Entry Price", min_value=0.0, step=0.0001, format="%.4f", key=K_ENTRY)
            stop_v = st.number_input("Stop Loss", min_value=0.0, step=0.0001, format="%.4f", key=K_STOP)
            t1_v = st.number_input("Target 1", min_value=0.0, step=0.0001, format="%.4f", key=K_T1)
            t2_v = st.number_input("Target 2", min_value=0.0, step=0.0001, format="%.4f", key=K_T2)
            if not _blank_mode:
                with st.container(key="inputs_actions"):
                    st.button("Restore Trade Plan", key="restorebtn", on_click=_restore_plan)

    st.session_state[f"pv_{K_ENTRY}"], st.session_state[f"pv_{K_STOP}"] = entry_v, stop_v
    st.session_state[f"pv_{K_T1}"], st.session_state[f"pv_{K_T2}"] = t1_v, t2_v
    return entry_v, stop_v, t1_v, t2_v


# Column weights keep the Live Price box the same width as the Trade Inputs box below
# it (1 ≈ 27%) and Direction + P&L together span the Visualization column's width. The
# Position-Summary-width cell is split into Leverage (0.295 ≈ 25%) + Account (0.885 ≈
# 75%) — together 1.18, so the pair lines up under the Position Summary below.
# The right-hand zone is a FIXED 1.18 wide in BOTH modes — so Live / Direction / P&L stay
# exactly the same width when you toggle, and the zone lines up under the Position Summary
# below. Risk mode splits the zone into Leverage (0.36) | Account (0.82); exposure mode
# gives the whole zone to the Account box, with ⚡ Leverage folded in as the margin × lev row.
top_price, top_dir, top_pnl, top_right = st.columns([1, 0.45, 1.05, 1.18], gap="medium")
with top_price:
    _live_price_box()
    if st.session_state.get("calc_blank"):
        # Blank Calc: the symbol picker is dropped into the bottom-right corner of the live-price
        # card via CSS. It's a SIBLING of the price fragment (rendered outside the 2s refresh, so
        # typing is never interrupted) and absolutely positioned against the price column — which
        # already stretches to the card's full height. Plan mode renders the card normally.
        with st.container(key="symbox"):
            _serr = st.session_state.get("calc_sym_err")
            if _serr:
                st.markdown(
                    f"<div class='symerr'>“{_serr}” not found</div>", unsafe_allow_html=True,
                )
            st.text_input(
                "Symbol", key="calc_symbol_input", on_change=_apply_symbol,
                placeholder="Ticker…", label_visibility="collapsed",
            )
with top_dir:
    if _blank_mode:
        # Blank Calc: Direction is a choice — two stacked pill buttons (direct colour scheme).
        with st.container(key="dirseg"):
            st.markdown("<div class='chead'><span class='t'>Direction</span></div>", unsafe_allow_html=True)
            with st.container(key="dirbtns"):
                st.button("Long", key="dirlong_on" if is_long else "dirlong_off",
                          on_click=_set_direction, args=("long",), use_container_width=True)
                st.button("Short", key="dirshort_on" if not is_long else "dirshort_off",
                          on_click=_set_direction, args=("short",), use_container_width=True)
    else:
        st.markdown(_dir_box, unsafe_allow_html=True)
with top_pnl:
    st.markdown(_pnl_box, unsafe_allow_html=True)
with top_right:
    _eq = float(st.session_state.get("calc_equity", _eq_default))
    if is_exposure:
        # Right zone split into Margin Allocation (the exposure equation) + Account (your
        # funds: Balance + Margin %). One input row each, so both match the risk-mode height.
        malloc_col, acc_col = st.columns([0.82, 0.36], gap="medium")
        with malloc_col:
            mcard = st.container(key="acct_card")
            with mcard:
                # ⚡ in the corner signifies this is the leverage box (margin × leverage).
                st.markdown("<div class='chead'><span class='t'>Margin Allocation</span><span class='lev-ic'>⚡</span></div>", unsafe_allow_html=True)
                # Headline — the two downside figures: loss if price hits your stop, and loss
                # if it reaches the liquidation price (≈ your whole margin).
                _mu = float(st.session_state.get("calc_margin_usd", _margin_usd_default))
                _ras = _pnl["sl"] if _pnl else 0.0
                _ral = _pnl["liq_loss"] if _pnl else 0.0
                st.markdown(
                    f"<div class='acct-exp malloc-risks'>"
                    f"<div class='risk-row'><span class='l'>Risk at Stop</span>"
                    f"<b class='neg'>−${_ras:,.2f}</b></div>"
                    f"<div class='risk-row'><span class='l'>Risk at Liquidation</span>"
                    f"<b class='liq'>−${_ral:,.2f}</b></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                # Margin $ × Leverage — the equation, with the × operator between the fields.
                m1, mx, m2 = st.columns([1, 0.3, 1], gap="small", vertical_alignment="bottom")
                margin_usd = m1.number_input("Margin $", min_value=0.0, step=50.0, format="%.2f", key="calc_margin_usd", on_change=_sync_margin_from_usd)
                mx.markdown("<div class='mx-op'>×</div>", unsafe_allow_html=True)
                m2.number_input("Leverage", min_value=1.0, step=0.5, format="%g", key="calc_lev", on_change=_persist_account)
        with acc_col:
            acard = st.container(key="account_card")
            with acard:
                st.markdown("<div class='chead'><span class='t'>Account</span></div>", unsafe_allow_html=True)
                equity = st.number_input("Balance", min_value=0.0, value=_eq_default, step=100.0, format="%.0f", key="calc_equity", on_change=_persist_balance_exposure)
                margin_pct = st.number_input("Margin %", min_value=0.0, step=0.5, format="%.2f", key="calc_margin_pct", on_change=_sync_margin_from_pct)
        risk_pct = _rk_default  # not used as an input in exposure mode
    else:
        # Account Risk on the left (wide), Leverage on the right (narrow).
        racct, rlev = st.columns([0.82, 0.36], gap="medium")
        with racct:
            acard = st.container(key="acct_card")
            with acard:
                st.markdown("<div class='chead'><span class='t'>Account Risk</span></div>", unsafe_allow_html=True)
                # Risk mode — capital at risk is the figure that matters.
                _rk = float(st.session_state.get("calc_risk", _rk_default))
                st.markdown(
                    f"<div class='acct-risk'><span class='l'>Capital at risk</span>"
                    f"<b>${_eq * _rk / 100:,.2f}</b>"
                    f"<span class='c'>{_rk:.2f}% of ${_eq:,.0f}</span></div>",
                    unsafe_allow_html=True,
                )
                ac1, ac2 = st.columns([1.5, 1])
                equity = ac1.number_input("Account Bal", min_value=0.0, value=_eq_default, step=100.0, format="%.0f", key="calc_equity", on_change=_persist_account)
                risk_pct = ac2.number_input("Risk (%)", min_value=0.0, value=_rk_default, step=0.1, format="%.2f", key="calc_risk", on_change=_persist_account)
        with rlev:
            # Editable Leverage box — its own box beside Account (risk mode). Steppers hidden
            # to keep the number clean; the value drives leverage everywhere below.
            lev_box = st.container(key="lev_card")
            with lev_box:
                st.markdown(
                    "<div class='chead'><span class='t'>Leverage</span><span class='lev-ic'>⚡</span></div>",
                    unsafe_allow_html=True,
                )
                st.number_input(
                    "Leverage", min_value=1.0, step=0.5, format="%g",
                    key="calc_lev", on_change=_persist_account, label_visibility="collapsed",
                )
                st.markdown(
                    f"<div class='lev-sub' style='color:{_lev_q[1]}'>{_lev_q[0]}</div>"
                    f"<div class='lev-fine'>{_lev_q[2]}</div>",
                    unsafe_allow_html=True,
                )

components.html(
    """
    <script>
    (() => {
      const w = window.parent;
      const removeMobileOldTopStrip = () => {
        if (!w.matchMedia("(max-width: 700px)").matches) return;
        const doc = w.document;
        doc.querySelectorAll('.hmain, .st-key-symbox, .dirbox, .pnlbox').forEach((node) => {
          const row = node.closest('[data-testid="stHorizontalBlock"]');
          const wrap = row?.closest('[data-testid="stLayoutWrapper"]');
          (wrap || row || node).remove();
        });
      };
      removeMobileOldTopStrip();
      new MutationObserver(removeMobileOldTopStrip).observe(w.document.body, {childList: true, subtree: true});
    })();
    </script>
    """,
    height=0,
)

# --------------------------------------------------------------------------- #
# Main row: Trade Inputs (levels from the dashboard) | Visualization | Summary + Score
# --------------------------------------------------------------------------- #
journal_clicked = False
c_in, c_viz, c_sum = st.columns([1, 1.5, 1.18], gap="medium")

with c_in:
    card = st.container(key="inputs_card")
    with card:
        if _blank_mode:
            with st.container(key="mobile_trade_dirswitch"):
                mt_pair, mt_refresh = st.columns([0.78, 0.22], gap="small")
                with mt_pair:
                    with st.container(key="mobile_trade_pair"):
                        mt_long, mt_short = st.columns(2, gap="small")
                        with mt_long:
                            st.button(
                                "LONG",
                                key="mob_trade_dirlong_on" if is_long else "mob_trade_dirlong_off",
                                on_click=_set_direction,
                                args=("long",),
                                use_container_width=True,
                            )
                        with mt_short:
                            st.button(
                                "SHORT",
                                key="mob_trade_dirshort_on" if not is_long else "mob_trade_dirshort_off",
                                on_click=_set_direction,
                                args=("short",),
                                use_container_width=True,
                            )
                with mt_refresh:
                    st.button(
                        "Refresh",
                        key="refreshbtn",
                        on_click=_clear_blank_inputs,
                        use_container_width=True,
                    )
        entry, stop, t1, t2 = _render_trade_level_inputs("manual")

_mobile_exec_wrap = st.container(key="mobile_exec_wrap")
with _mobile_exec_wrap:
    st.markdown(_mobile_execution_panel_from_state(), unsafe_allow_html=True)
    if not _exp_on:
        _cap_notional = _risk_sized_notional_from_state()
        _cap_lev = float(st.session_state.get("calc_lev", _lev_default) or _lev_default)
        _cap_margin = (_cap_notional / _cap_lev) if (_cap_notional > 0 and _cap_lev > 0) else 0.0
        st.session_state["calc_margin_cap"] = round(_cap_margin, 2)
        with st.container(key="mobile_margin_cap"):
            st.number_input(
                "Margin Cap",
                min_value=0.0,
                step=25.0,
                format="%.2f",
                key="calc_margin_cap",
                on_change=_sync_leverage_from_margin_cap,
            )

_mobile_viz_slot = st.empty()

components.html(
    """
    <script>
    (() => {
      const w = window.parent;
      const bind = () => {
        const doc = w.document;
        const card = doc.querySelector(".st-key-inputs_card");
        const details = card?.querySelector("details");
        const summary = details?.querySelector("summary");
        if (!card || !details || !summary) return;
        const isMobile = w.matchMedia("(max-width: 700px)").matches;
        if (isMobile) {
          details.open = true;
          summary.style.pointerEvents = "none";
          return;
        }
        summary.style.pointerEvents = "";
        if (summary.dataset.calcNativeAccordionBound === "1") return;
        summary.dataset.calcNativeAccordionBound = "1";
        summary.addEventListener("click", (ev) => {
          ev.preventDefault();
          ev.stopImmediatePropagation();
          details.open = !details.open;
        }, {capture: true});
      };
      bind();
      new MutationObserver(bind).observe(w.document.body, {childList: true, subtree: true});
    })();
    </script>
    """,
    height=0,
)

# --------------------------------------------------------------------------- #
# Maths
# --------------------------------------------------------------------------- #
stop_dist = abs(entry - stop)
valid = entry > 0 and stop_dist > 0 and leverage > 0

if valid:
    if is_exposure:
        # Exposure-based: you fix the MARGIN; leverage multiplies it into the notional, so
        # position size — and therefore profit AND loss — scale with leverage.
        margin_committed = float(st.session_state.get("calc_margin_usd", _margin_usd_default))
        notional = margin_committed * leverage
        size = notional / entry if entry > 0 else 0.0
        risk_amount = size * stop_dist          # now a DERIVED output, not a fixed input
        margin_req = margin_committed
        lev_req = leverage
    else:
        # Risk-Safe: you fix the dollar risk; size follows from risk ÷ stop distance, and
        # leverage only sets the margin you post (profit is leverage-independent).
        risk_amount = equity * risk_pct / 100
        size = risk_amount / stop_dist
        notional = size * entry
        margin_req = notional / leverage
        lev_req = notional / equity if equity > 0 else 0.0
    # Effective capital-at-risk as a % of balance — fixed in risk mode, derived (and
    # leverage-driven) in exposure mode. Drives the score, checklist and risk guard.
    risk_pct_eff = (risk_amount / equity * 100) if equity > 0 else 0.0
    risk_over_guard = is_exposure and risk_pct_eff > RISK_GUARD_PCT

    rew1_dist = abs(t1 - entry)
    rew2_dist = abs(t2 - entry)
    rew1 = size * rew1_dist
    rew2 = size * rew2_dist
    rr1 = rew1_dist / stop_dist
    rr2 = rew2_dist / stop_dist
    be1 = 100.0 / (1.0 + rr1) if rr1 > 0 else 100.0

    if is_long:
        liq = entry * (1 - 1 / leverage + MMR)
    else:
        liq = entry * (1 + 1 / leverage - MMR)
    liq = max(liq, 0.0)
    liq_dist_pct = abs(entry - liq) / entry * 100 if entry else 0.0
    # Cushion between the stop and liquidation: positive = liq sits safely beyond the
    # stop; negative = liq is inside the stop (you'd be liquidated first).
    liq_buffer = (stop - liq) if is_long else (liq - stop)
    liq_buffer_pct = liq_buffer / entry * 100 if entry else 0.0

    # ---- setup score (0–10) ----
    rr_pts = clamp(rr1 / 3.0, 0, 1) * 4.0
    if risk_pct_eff <= 1:
        risk_pts = 2.0
    elif risk_pct_eff <= 2:
        risk_pts = 2.0 - (risk_pct_eff - 1) * 0.7
    else:
        risk_pts = clamp(1.3 - (risk_pct_eff - 2) * 0.4, 0, 1.3)
    if leverage <= 3:
        lev_pts = 2.0
    elif leverage <= 10:
        lev_pts = 2.0 - (leverage - 3) * (0.8 / 7.0)
    else:
        lev_pts = clamp(1.2 - (leverage - 10) * 0.1, 0, 1.2)
    margin_ok = margin_req <= equity
    liq_ok = (liq < stop) if is_long else (liq > stop)
    safe_pts = 2.0 - (0 if margin_ok else 1) - (0 if liq_ok else 1)
    safe_pts = clamp(safe_pts, 0, 2)
    score = clamp(rr_pts + risk_pts + lev_pts + safe_pts, 0, 10)

    # checklist
    rr_ok = rr1 >= 2
    size_ok = risk_pct_eff <= 2 and margin_ok
    lev_label_ok = leverage <= 3
    risk_ok = risk_pct_eff <= 2 and margin_ok and liq_ok

    if score >= 8.5:
        sv_label, sv_cls = "EXCELLENT SETUP", "exc"
    elif score >= 7:
        sv_label, sv_cls = "GOOD SETUP", "good"
    elif score >= 5:
        sv_label, sv_cls = "FAIR SETUP", "fair"
    else:
        sv_label, sv_cls = "HIGH-RISK SETUP", "bad"

# --------------------------------------------------------------------------- #
# Visualization (SVG zone diagram)
# --------------------------------------------------------------------------- #
def _current_liq_from_state() -> float:
    try:
        e = float(st.session_state.get(K_ENTRY, levels.get("entry", 0.0)) or 0)
        levv = float(st.session_state.get("calc_lev", leverage) or leverage)
    except (TypeError, ValueError):
        return float(liq)
    if not (e > 0 and levv > 0):
        return float(liq)
    next_liq = e * (1 - 1 / levv + MMR) if is_long else e * (1 + 1 / levv - MMR)
    return max(next_liq, 0.0)


LIQ_RAIL_MIN_LEVERAGE = 1.0


def _liq_at_leverage(levv: float) -> float:
    if not (valid and entry > 0):
        return float(liq)
    levv = max(1.0, float(levv or 1.0))
    next_liq = entry * (1 - 1 / levv + MMR) if is_long else entry * (1 + 1 / levv - MMR)
    return max(next_liq, 0.0)


def _liq_at_100x() -> float:
    return _liq_at_leverage(100.0)


def _liq_at_rail_min_leverage() -> float:
    return _liq_at_leverage(LIQ_RAIL_MIN_LEVERAGE)


def _clamp_liq_to_max_leverage(target_liq: float) -> float:
    if not (valid and target_liq > 0):
        return target_liq
    liq_100x = _liq_at_100x()
    return min(target_liq, liq_100x) if is_long else max(target_liq, liq_100x)


def _sync_liq_target_to_leverage(liq_key: str):
    if is_exposure:
        return
    try:
        target_liq = float(st.session_state.get(liq_key, 0) or 0)
        e = float(st.session_state.get(K_ENTRY, levels.get("entry", 0.0)) or 0)
    except (TypeError, ValueError):
        return
    if not (target_liq > 0 and e > 0):
        return
    target_liq = _clamp_liq_to_max_leverage(target_liq)
    st.session_state[liq_key] = target_liq
    denom = (1 + MMR - target_liq / e) if is_long else (target_liq / e - 1 + MMR)
    if denom <= 0:
        return
    st.session_state["calc_lev"] = round(clamp(1 / denom, 1.0, 100.0), 2)
    st.session_state["calc_scroll_to_liq"] = True
    _persist_account()


def _nudge_liq_target(liq_key: str, delta: float):
    try:
        current = float(st.session_state.get(liq_key, liq) or liq)
    except (TypeError, ValueError):
        current = float(liq)
    st.session_state[liq_key] = _clamp_liq_to_max_leverage(max(0.0, current + delta))
    _sync_liq_target_to_leverage(liq_key)


def _liq_axis_bounds() -> tuple[float, float]:
    if not valid:
        return 0.0, 1.0
    pts = [entry, stop, t1, t2]
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or (hi * 0.1) or 1.0
    # Keep the trade map readable. The rail can cover 1x-100x, but the chart should
    # only stretch a little toward liquidation; otherwise entry/stop/targets collapse.
    cap = span * 1.5
    if is_long and liq < lo:
        lo = liq if liq >= entry - cap else entry - cap
    elif (not is_long) and liq > hi:
        hi = liq if liq <= entry + cap else entry + cap
    lo -= span * 0.16
    hi += span * 0.16
    return lo, hi


def _liq_rail_bounds() -> tuple[float, float]:
    lo, hi = _liq_axis_bounds()
    if not valid:
        return lo, hi
    lo = max(0.0, lo)
    liq_100x = _liq_at_100x()
    min_lev_liq = _liq_at_rail_min_leverage()
    if is_long:
        lo = max(0.0, min_lev_liq)
        hi = liq_100x
    else:
        lo = liq_100x
        hi = min_lev_liq
    if hi <= lo:
        lo, hi = _liq_axis_bounds()
        lo = max(0.0, lo)
    return lo, hi


def _liq_axis_pct() -> float:
    if not valid:
        return 50.0
    lo, hi = _liq_axis_bounds()
    if hi == lo:
        return 50.0
    y = (hi - min(max(liq, lo), hi)) / (hi - lo)
    return clamp(y * 100, 2.0, 98.0)


def _liq_rail_pct() -> float:
    if not valid:
        return 50.0
    levv = clamp(float(st.session_state.get("calc_lev", leverage) or leverage), 1.0, 100.0)
    pos = math.log10(levv) / 2.0
    if is_long:
        pos = 1.0 - pos
    return clamp(pos * 100, 0.0, 100.0)


def _render_liq_rail(liq_key: str, card_key: str):
    if not valid or is_exposure:
        return
    liq_step = max(abs(entry) * 0.001, 0.0001)
    axis_lo, axis_hi = _liq_axis_bounds()
    rail_lo, rail_hi = _liq_rail_bounds()
    liq_100x = _liq_at_100x()
    st.session_state[liq_key] = _current_liq_from_state()
    with st.container(key=card_key):
        st.markdown(
            "<div class='liq-rail-card'>"
            "<div class='liq-rail-label'>LIQ</div>"
            f"<div class='liq-rail-track' data-liq-min='{rail_lo:.10f}' data-liq-max='{rail_hi:.10f}' "
            f"data-chart-min='{axis_lo:.10f}' data-chart-max='{axis_hi:.10f}' data-liq-current='{liq:.10f}'>"
            f"<div class='liq-rail-dragzone' data-symbol='{symbol}' data-dir='{direction}' "
            f"data-entry='{entry:.10f}' data-stop='{stop:.10f}' data-t1='{t1:.10f}' data-t2='{t2:.10f}' "
            f"data-liq-limit='{liq_100x:.10f}' data-notional='{notional:.10f}'></div>"
            f"<div class='liq-rail-dot' style='top:{_liq_rail_pct():.2f}%'></div>"
            "</div>"
            f"<div class='liq-rail-value'>{fpx(liq)}</div>"
            f"<div class='liq-rail-lev'>{leverage:g}x</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        components.html(
            """
            <script>
            (() => {
              const doc = window.parent.document;
              const parentWin = doc.defaultView || window.parent;
              doc.getElementById('liq-rail-parent-drag-script-v3')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v4')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v5')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v6')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v7')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v8')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v9')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v10')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v11')?.remove();
              doc.getElementById('liq-rail-parent-drag-script-v12')?.remove();
              if (!doc.getElementById('liq-rail-parent-drag-script-v13')) {
                const parentScript = doc.createElement('script');
                parentScript.id = 'liq-rail-parent-drag-script-v13';
                parentScript.textContent = `
                  (() => {
                    const fmt = (v) => {
                      const a = Math.abs(v);
                      if (a >= 1000) return v.toLocaleString(undefined, {maximumFractionDigits: 2});
                      if (a >= 1) return v.toFixed(4);
                      if (a >= 0.01) return v.toFixed(4);
                      return v.toFixed(6);
                    };
                    const fmtMoney = (v) => '$' + Number(v || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    const fmtPct = (v) => (v >= 0 ? '+' : '') + Number(v || 0).toFixed(2) + '%';
                    const levNote = (v) => {
                      v = Number(v) || 1;
                      if (v <= 3) return 'Conservative · Low risk exposure';
                      if (v <= 10) return 'Moderate · Watch your margin';
                      return 'Aggressive · High liquidation risk';
                    };
                    const bind = () => {
                      const zones = Array.from(document.querySelectorAll('.liq-rail-dragzone'));
                      for (const zone of zones) {
                        if (zone.dataset.parentBoundV13 === '1') continue;
                        zone.dataset.parentBoundV13 = '1';
                        let startY = 0, active = false, moved = false, pending = null, pendingLev = null;
                        const track = zone.closest('.liq-rail-track');
                        const card = zone.closest('.liq-rail-card');
                        const dot = track?.querySelector('.liq-rail-dot');
                        const value = card?.querySelector('.liq-rail-value');
                        if (!track || !dot || !value) continue;
                        const priceFromY = (clientY) => {
                          const rect = track.getBoundingClientRect();
                          const pct = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
                          const entry = Number(zone.dataset.entry);
                          const dir = zone.dataset.dir || 'long';
                          if (!(entry > 0)) return 0;
                          const levPct = dir === 'short' ? pct : (1 - pct);
                          const lev = Math.pow(10, levPct * 2);
                          const mmr = 0.005;
                          return dir === 'short'
                            ? entry * (1 + 1 / lev - mmr)
                            : Math.max(0, entry * (1 - 1 / lev + mmr));
                        };
                        const clampPrice = (raw) => {
                          const liq100 = Number(zone.dataset.liqLimit);
                          if (!(liq100 > 0)) return raw;
                          return (zone.dataset.dir || 'long') === 'short' ? Math.max(raw, liq100) : Math.min(raw, liq100);
                        };
                        const pctFromPrice = (price) => {
                          const hi = Number(track.dataset.chartMax);
                          const lo = Number(track.dataset.chartMin);
                          if (!(hi > lo)) return 0.5;
                          return Math.max(0, Math.min(1, (hi - price) / (hi - lo)));
                        };
                        const leveragePct = (v) => {
                          const ticks = [[1,0],[10,25],[25,50],[50,75],[100,100]];
                          v = Math.max(1, Math.min(100, Number(v) || 1));
                          for (let i = 0; i < ticks.length - 1; i++) {
                            const [v0, p0] = ticks[i];
                            const [v1, p1] = ticks[i + 1];
                            if (v <= v1) return p0 + ((v - v0) / (v1 - v0)) * (p1 - p0);
                          }
                          return 100;
                        };
                        const updateLeveragePreview = (targetLiq) => {
                          const entry = Number(zone.dataset.entry);
                          const dir = zone.dataset.dir || 'long';
                          if (!(entry > 0 && targetLiq > 0)) return;
                          const mmr = 0.005;
                          const denom = dir === 'short'
                            ? (targetLiq / entry - 1 + mmr)
                            : (1 + mmr - targetLiq / entry);
                          const lev = denom > 0 ? Math.max(1, Math.min(100, 1 / denom)) : 100;
                          const pct = leveragePct(lev);
                          const levText = lev.toFixed(lev >= 10 ? 2 : 1).replace(/\\.0+$/, '').replace(/(\\.\\d*[1-9])0$/, '$1') + 'x';
                          const notional = Number(zone.dataset.notional);
                          const marginText = notional > 0 && lev > 0 ? fmtMoney(notional / lev) : null;
                          document.querySelectorAll('.mlv-value').forEach((el) => { el.textContent = levText; });
                          document.querySelectorAll('.mlv-sub').forEach((el) => { el.textContent = levNote(lev); });
                          document.querySelectorAll('.mlv-fill').forEach((el) => { el.style.width = pct.toFixed(2) + '%'; });
                          card?.querySelectorAll('.liq-rail-lev').forEach((el) => { el.textContent = levText; });
                          if (marginText) {
                            document.querySelectorAll('.mxec-margin .mxec-v').forEach((el) => { el.textContent = marginText; });
                            document.querySelectorAll('.mxec-margin-input, .st-key-mobile_margin_cap input[aria-label="Margin Cap"]').forEach((el) => {
                              el.value = (notional / lev).toFixed(2);
                            });
                          }
                          return lev;
                        };
                        const paint = (clientY) => {
                          const rect = track.getBoundingClientRect();
                          const thumbPct = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
                          pending = clampPrice(priceFromY(clientY));
                          const pct = pctFromPrice(pending);
                          dot.style.top = (thumbPct * 100) + '%';
                          value.textContent = fmt(pending);
                          const grid = zone.closest('.st-key-mobile_viz_grid, .st-key-desktop_viz_grid');
                          const liqLine = grid?.querySelector('.vliqline');
                          const liqText = grid?.querySelector('.vliqtxt');
                          const svgY = 28 + pct * (430 - 56);
                          if (liqLine) {
                            liqLine.setAttribute('y1', String(svgY));
                            liqLine.setAttribute('y2', String(svgY));
                          }
                          if (liqText) {
                            liqText.style.top = ((svgY / 430) * 100) + '%';
                            liqText.textContent = 'LIQ ' + fmt(pending);
                          }
                          const liqPct = grid?.querySelector('.vliqpct');
                          const entry = Number(zone.dataset.entry);
                          if (liqPct && entry > 0) {
                            liqPct.style.top = ((svgY / 430) * 100) + '%';
                            liqPct.textContent = fmtPct((pending / entry - 1) * 100);
                          }
                          pendingLev = updateLeveragePreview(pending);
                        };
                        const persistPreview = () => {
                          if (!(pending > 0 && pendingLev > 0)) return;
                          try {
                            const url = new URL(window.location.href);
                            url.searchParams.set('lev', pendingLev.toFixed(2));
                            url.searchParams.set('liq', pending.toFixed(10));
                            window.history.replaceState({}, '', url);
                          } catch (_) {}
                        };
                        const begin = (clientY, pointerId) => {
                          startY = clientY;
                          active = true;
                          moved = false;
                          pending = null;
                          if (pointerId != null) {
                            try { zone.setPointerCapture?.(pointerId); } catch (_) {}
                          }
                        };
                        const move = (clientY, ev) => {
                          if (!active) return;
                          if (!moved && Math.abs(clientY - startY) < 8) return;
                          moved = true;
                          zone.classList.add('dragging');
                          ev?.preventDefault?.();
                          paint(clientY);
                        };
                        const end = (ev) => {
                          if (!active) return;
                          active = false;
                          zone.classList.remove('dragging');
                          persistPreview();
                          try { zone.releasePointerCapture?.(ev.pointerId); } catch (_) {}
                        };
                        zone.addEventListener('pointerdown', (ev) => begin(ev.clientY, ev.pointerId), {passive: true});
                        zone.addEventListener('pointermove', (ev) => move(ev.clientY, ev), {passive: false});
                        zone.addEventListener('pointerup', end);
                        zone.addEventListener('pointercancel', end);
                        zone.addEventListener('mousedown', (ev) => begin(ev.clientY, null));
                        document.addEventListener('mousemove', (ev) => move(ev.clientY, ev));
                        document.addEventListener('mouseup', end);
                        zone.addEventListener('touchstart', (ev) => {
                          const touch = ev.touches && ev.touches[0];
                          if (touch) begin(touch.clientY, null);
                        }, {passive: true});
                        document.addEventListener('touchmove', (ev) => {
                          const touch = ev.touches && ev.touches[0];
                          if (touch) move(touch.clientY, ev);
                        }, {passive: false});
                        document.addEventListener('touchend', end);
                        document.addEventListener('touchcancel', end);
                      }
                      const marginInputs = Array.from(document.querySelectorAll('.mxec-margin-input, .st-key-mobile_margin_cap input[aria-label="Margin Cap"]'));
                      for (const input of marginInputs) {
                        if (input.dataset.marginBoundV13 === '1') continue;
                        input.dataset.marginBoundV13 = '1';
                        let marginSettle = null;
                        const applyMarginCap = (commit = false) => {
                          const zone = document.querySelector('.liq-rail-dragzone');
                          if (!zone) return;
                          const track = zone.closest('.liq-rail-track');
                          const card = zone.closest('.liq-rail-card');
                          const dot = track?.querySelector('.liq-rail-dot');
                          const value = card?.querySelector('.liq-rail-value');
                          const entry = Number(zone.dataset.entry);
                          const notional = Number(zone.dataset.notional);
                          const margin = Number(String(input.value || '').replace(/[^0-9.]/g, ''));
                          if (!(entry > 0 && notional > 0 && margin > 0 && track && dot && value)) return;
                          const dir = zone.dataset.dir || 'long';
                          const mmr = 0.005;
                          const lev = Math.max(1, Math.min(100, notional / margin));
                          const targetLiq = dir === 'short'
                            ? entry * (1 + 1 / lev - mmr)
                            : Math.max(0, entry * (1 - 1 / lev + mmr));
                          const chartHi = Number(track.dataset.chartMax);
                          const chartLo = Number(track.dataset.chartMin);
                          const chartPct = chartHi > chartLo ? Math.max(0, Math.min(1, (chartHi - targetLiq) / (chartHi - chartLo))) : 0.5;
                          const thumbPct = dir === 'short' ? Math.log10(lev) / 2 : 1 - Math.log10(lev) / 2;
                          const svgY = 28 + chartPct * (430 - 56);
                          const leveragePct = (v) => {
                            const ticks = [[1,0],[10,25],[25,50],[50,75],[100,100]];
                            v = Math.max(1, Math.min(100, Number(v) || 1));
                            for (let i = 0; i < ticks.length - 1; i++) {
                              const [v0, p0] = ticks[i];
                              const [v1, p1] = ticks[i + 1];
                              if (v <= v1) return p0 + ((v - v0) / (v1 - v0)) * (p1 - p0);
                            }
                            return 100;
                          };
                          const levText = lev.toFixed(lev >= 10 ? 2 : 1).replace(/\\.0+$/, '').replace(/(\\.\\d*[1-9])0$/, '$1') + 'x';
                          dot.style.top = (Math.max(0, Math.min(1, thumbPct)) * 100) + '%';
                          value.textContent = fmt(targetLiq);
                          card?.querySelectorAll('.liq-rail-lev').forEach((el) => { el.textContent = levText; });
                          document.querySelectorAll('.mlv-value').forEach((el) => { el.textContent = levText; });
                          document.querySelectorAll('.mlv-sub').forEach((el) => { el.textContent = levNote(lev); });
                          document.querySelectorAll('.mlv-fill').forEach((el) => { el.style.width = leveragePct(lev).toFixed(2) + '%'; });
                          const actualMargin = (notional / lev).toFixed(2);
                          document.querySelectorAll('.mxec-margin .mxec-v').forEach((el) => { el.textContent = fmtMoney(notional / lev); });
                          document.querySelectorAll('.mxec-margin-input, .st-key-mobile_margin_cap input[aria-label="Margin Cap"]').forEach((el) => {
                            if (commit || el !== input) el.value = actualMargin;
                          });
                          const grid = zone.closest('.st-key-mobile_viz_grid, .st-key-desktop_viz_grid');
                          const liqLine = grid?.querySelector('.vliqline');
                          if (liqLine) {
                            liqLine.setAttribute('y1', String(svgY));
                            liqLine.setAttribute('y2', String(svgY));
                          }
                          const liqText = grid?.querySelector('.vliqtxt');
                          if (liqText) {
                            liqText.style.top = ((svgY / 430) * 100) + '%';
                            liqText.textContent = 'LIQ ' + fmt(targetLiq);
                          }
                          const liqPct = grid?.querySelector('.vliqpct');
                          if (liqPct) {
                            liqPct.style.top = ((svgY / 430) * 100) + '%';
                            liqPct.textContent = fmtPct((targetLiq / entry - 1) * 100);
                          }
                          try {
                            const url = new URL(window.location.href);
                            url.searchParams.set('lev', lev.toFixed(2));
                            url.searchParams.set('liq', targetLiq.toFixed(10));
                            window.history.replaceState({}, '', url);
                          } catch (_) {}
                        };
                        input.addEventListener('input', () => {
                          applyMarginCap(false);
                          clearTimeout(marginSettle);
                          marginSettle = setTimeout(() => applyMarginCap(true), 650);
                        });
                        input.addEventListener('change', () => applyMarginCap(true));
                        input.addEventListener('keydown', (ev) => {
                          if (ev.key === 'Enter') applyMarginCap(true);
                        });
                      }
                    };
                    bind();
                    new MutationObserver(bind).observe(document.body, {childList: true, subtree: true});
                  })();
                `;
                doc.body.appendChild(parentScript);
              }
              const zones = Array.from(doc.querySelectorAll('.liq-rail-dragzone'));
              const fmt = (v) => {
                const a = Math.abs(v);
                if (a >= 1000) return v.toLocaleString(undefined, {maximumFractionDigits: 2});
                if (a >= 1) return v.toFixed(4);
                if (a >= 0.01) return v.toFixed(4);
                return v.toFixed(6);
              };
              const fmtMoney = (v) => '$' + Number(v || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
              const fmtPct = (v) => (v >= 0 ? '+' : '') + Number(v || 0).toFixed(2) + '%';
              const levNote = (v) => {
                v = Number(v) || 1;
                if (v <= 3) return 'Conservative · Low risk exposure';
                if (v <= 10) return 'Moderate · Watch your margin';
                return 'Aggressive · High liquidation risk';
              };
              for (const zone of zones) {
                if (zone.dataset.bound === '1') continue;
                zone.dataset.bound = '1';
                let startY = 0, active = false, moved = false, pending = null, pendingLev = null;
                const track = zone.closest('.liq-rail-track');
                const card = zone.closest('.liq-rail-card');
                const dot = track?.querySelector('.liq-rail-dot');
                const value = card?.querySelector('.liq-rail-value');
                if (!track || !dot || !value) continue;
                const priceFromY = (clientY) => {
                  const rect = track.getBoundingClientRect();
                  const pct = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
                  const entry = Number(zone.dataset.entry);
                  const dir = zone.dataset.dir || 'long';
                  if (!(entry > 0)) return 0;
                  const levPct = dir === 'short' ? pct : (1 - pct);
                  const lev = Math.pow(10, levPct * 2);
                  const mmr = 0.005;
                  return dir === 'short'
                    ? entry * (1 + 1 / lev - mmr)
                    : Math.max(0, entry * (1 - 1 / lev + mmr));
                };
                const clampPrice = (raw) => {
                  const liq100 = Number(zone.dataset.liqLimit);
                  if (!(liq100 > 0)) return raw;
                  return (zone.dataset.dir || 'long') === 'short' ? Math.max(raw, liq100) : Math.min(raw, liq100);
                };
                const pctFromPrice = (price) => {
                  const hi = Number(track.dataset.chartMax);
                  const lo = Number(track.dataset.chartMin);
                  if (!(hi > lo)) return 0.5;
                  return Math.max(0, Math.min(1, (hi - price) / (hi - lo)));
                };
                const leveragePct = (v) => {
                  const ticks = [[1,0],[10,25],[25,50],[50,75],[100,100]];
                  v = Math.max(1, Math.min(100, Number(v) || 1));
                  for (let i = 0; i < ticks.length - 1; i++) {
                    const [v0, p0] = ticks[i];
                    const [v1, p1] = ticks[i + 1];
                    if (v <= v1) return p0 + ((v - v0) / (v1 - v0)) * (p1 - p0);
                  }
                  return 100;
                };
                const updateLeveragePreview = (targetLiq) => {
                  const entry = Number(zone.dataset.entry);
                  const dir = zone.dataset.dir || 'long';
                  if (!(entry > 0 && targetLiq > 0)) return;
                  const mmr = 0.005;
                  const denom = dir === 'short'
                    ? (targetLiq / entry - 1 + mmr)
                    : (1 + mmr - targetLiq / entry);
                  const lev = denom > 0 ? Math.max(1, Math.min(100, 1 / denom)) : 100;
                  const pct = leveragePct(lev);
                  const levText = lev.toFixed(lev >= 10 ? 2 : 1).replace(/\\.0+$/, '').replace(/(\\.\\d*[1-9])0$/, '$1') + 'x';
                  const notional = Number(zone.dataset.notional);
                  const marginText = notional > 0 && lev > 0 ? fmtMoney(notional / lev) : null;
                  doc.querySelectorAll('.mlv-value').forEach((el) => { el.textContent = levText; });
                  doc.querySelectorAll('.mlv-sub').forEach((el) => { el.textContent = levNote(lev); });
                  doc.querySelectorAll('.mlv-fill').forEach((el) => { el.style.width = pct.toFixed(2) + '%'; });
                  card?.querySelectorAll('.liq-rail-lev').forEach((el) => { el.textContent = levText; });
                  if (marginText) {
                    doc.querySelectorAll('.mxec-margin .mxec-v').forEach((el) => { el.textContent = marginText; });
                    doc.querySelectorAll('.mxec-margin-input, .st-key-mobile_margin_cap input[aria-label="Margin Cap"]').forEach((el) => {
                      el.value = (notional / lev).toFixed(2);
                    });
                  }
                  return lev;
                };
                const paint = (clientY) => {
                  const rect = track.getBoundingClientRect();
                  const thumbPct = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
                  pending = clampPrice(priceFromY(clientY));
                  const pct = pctFromPrice(pending);
                  dot.style.top = `${thumbPct * 100}%`;
                  value.textContent = fmt(pending);
                  const grid = zone.closest('.st-key-mobile_viz_grid, .st-key-desktop_viz_grid');
                  const liqLine = grid?.querySelector('.vliqline');
                  const liqText = grid?.querySelector('.vliqtxt');
                  const svgY = 28 + pct * (430 - 56);
                  if (liqLine) {
                    liqLine.setAttribute('y1', String(svgY));
                    liqLine.setAttribute('y2', String(svgY));
                  }
                  if (liqText) {
                    liqText.style.top = ((svgY / 430) * 100) + '%';
                    liqText.textContent = 'LIQ ' + fmt(pending);
                  }
                  const liqPct = grid?.querySelector('.vliqpct');
                  const entry = Number(zone.dataset.entry);
                  if (liqPct && entry > 0) {
                    liqPct.style.top = ((svgY / 430) * 100) + '%';
                    liqPct.textContent = fmtPct((pending / entry - 1) * 100);
                  }
                  pendingLev = updateLeveragePreview(pending);
                };
                const persistPreview = () => {
                  if (!(pending > 0 && pendingLev > 0)) return;
                  try {
                    const win = doc.defaultView || window.parent;
                    const url = new URL(win.location.href);
                    url.searchParams.set('lev', pendingLev.toFixed(2));
                    url.searchParams.set('liq', pending.toFixed(10));
                    win.history.replaceState({}, '', url);
                  } catch (_) {}
                };
                zone.addEventListener('pointerdown', (ev) => {
                  startY = ev.clientY;
                  active = true;
                  moved = false;
                  pending = null;
                  zone.setPointerCapture?.(ev.pointerId);
                }, {passive: true});
                zone.addEventListener('pointermove', (ev) => {
                  if (!active) return;
                  if (!moved && Math.abs(ev.clientY - startY) < 8) return;
                  moved = true;
                  zone.classList.add('dragging');
                  ev.preventDefault();
                  paint(ev.clientY);
                }, {passive: false});
                const end = (ev) => {
                  if (!active) return;
                  active = false;
                  zone.classList.remove('dragging');
                  persistPreview();
                  try { zone.releasePointerCapture?.(ev.pointerId); } catch (_) {}
                };
                zone.addEventListener('pointerup', end);
                zone.addEventListener('pointercancel', end);
                zone.addEventListener('mousedown', (ev) => {
                  startY = ev.clientY;
                  active = true;
                  moved = false;
                  pending = null;
                });
                doc.addEventListener('mousemove', (ev) => {
                  if (!active) return;
                  if (!moved && Math.abs(ev.clientY - startY) < 8) return;
                  moved = true;
                  zone.classList.add('dragging');
                  ev.preventDefault();
                  paint(ev.clientY);
                });
                doc.addEventListener('mouseup', end);
                zone.addEventListener('touchstart', (ev) => {
                  const touch = ev.touches && ev.touches[0];
                  if (!touch) return;
                  startY = touch.clientY;
                  active = true;
                  moved = false;
                  pending = null;
                }, {passive: true});
                doc.addEventListener('touchmove', (ev) => {
                  if (!active) return;
                  const touch = ev.touches && ev.touches[0];
                  if (!touch) return;
                  if (!moved && Math.abs(touch.clientY - startY) < 8) return;
                  moved = true;
                  zone.classList.add('dragging');
                  ev.preventDefault();
                  paint(touch.clientY);
                }, {passive: false});
                doc.addEventListener('touchend', end);
                doc.addEventListener('touchcancel', end);
              }
            })();
            </script>
            """,
            height=0,
        )


def build_viz() -> str:
    head = "<div class='chead'><span class='t'>Trade Visualization</span></div>"
    if not valid:
        # Skeleton diagram: the full chart structure (grid, zones, level boxes, arrows) at its
        # final size, with evenly-spaced placeholder levels and muted "—" prices/percentages.
        VBW, VBH, top, bot = 430, 430, 28, 28
        x0, x1 = 104, 270
        ax = (x0 + x1) // 2
        plotH = VBH - top - bot
        BW, BH = 92, 42
        LEFT_BX, RIGHT_BX = x0 - BW - 6, x1 + 6
        SK = "#4d5663"  # muted placeholder colour
        yf = lambda f: top + f * plotH
        # Orient the skeleton by direction: Long → TPs up top / stop at the bottom; Short → the
        # mirror image (stop up top, TPs below), matching how a real long/short trade plots.
        if is_long:
            y_tp2, y_tp1, y_en, y_sl = yf(0.12), yf(0.34), yf(0.54), yf(0.78)
        else:
            y_sl, y_en, y_tp1, y_tp2 = yf(0.12), yf(0.34), yf(0.54), yf(0.78)

        def sbox(y, color, label, side="right"):
            bx = LEFT_BX if side == "left" else RIGHT_BX
            by = y - BH / 2
            return (f"<rect x='{bx}' y='{by:.1f}' width='{BW}' height='{BH}' rx='8' fill='#0d1422' "
                    f"fill-opacity='0.95' stroke='{color}' stroke-width='1' vector-effect='non-scaling-stroke'/>"
                    f"<text x='{bx + BW / 2:.0f}' y='{by + 17:.1f}' text-anchor='middle' class='vboxlab' fill='{color}'>{label}</text>"
                    f"<text x='{bx + BW / 2:.0f}' y='{by + 34:.1f}' text-anchor='middle' class='vboxval' fill='{SK}'>—</text>")

        def sdline(y, color):
            return f"<line x1='{x0}' y1='{y:.1f}' x2='{x1}' y2='{y:.1f}' stroke='{color}' stroke-width='1.4' stroke-dasharray='6 5' opacity='0.7'/>"

        grid = "".join(
            f"<line x1='{x0}' y1='{top + i * plotH / 4:.0f}' x2='{x1}' y2='{top + i * plotH / 4:.0f}' stroke='#19202e' stroke-width='1'/>"
            for i in range(5)
        ) + "".join(
            f"<line x1='{x0 + i * (x1 - x0) / 6:.0f}' y1='{top}' x2='{x0 + i * (x1 - x0) / 6:.0f}' y2='{VBH - bot}' stroke='#19202e' stroke-width='1'/>"
            for i in range(7)
        )
        sk_svg = (
            f"<svg viewBox='0 0 {VBW} {VBH}' width='100%' style='display:block'>"
            + grid
            + f"<rect x='{x0}' y='{min(y_en, y_tp2):.1f}' width='{x1 - x0}' height='{abs(y_tp2 - y_en):.1f}' fill='#0ecb81' fill-opacity='0.06' rx='4'/>"
            + f"<rect x='{x0}' y='{min(y_en, y_sl):.1f}' width='{x1 - x0}' height='{abs(y_sl - y_en):.1f}' fill='#f6465d' fill-opacity='0.06' rx='4'/>"
            + sdline(y_tp2, "#0ecb81") + sdline(y_tp1, "#0ecb81")
            + f"<line x1='{x0}' y1='{y_en:.1f}' x2='{x1}' y2='{y_en:.1f}' stroke='#c9d1d9' stroke-width='1.4' stroke-dasharray='2 4' opacity='0.4'/>"
            + sdline(y_sl, "#f6465d")
            + f"<circle cx='{ax}' cy='{y_en:.1f}' r='4.5' fill='{SK}' stroke='#0d1422' stroke-width='1.5' vector-effect='non-scaling-stroke'/>"
            + sbox(y_en, "#5b8cff", "ENTRY", side="left")
            + sbox(y_tp2, "#0ecb81", "TAKE PROFIT 2")
            + sbox(y_tp1, "#0ecb81", "TAKE PROFIT 1")
            + sbox(y_sl, "#f6465d", "STOP LOSS")
            + "</svg>"
        )
        sk_overlay = (
            f"<div class='vpctlabel' style='top:{y_sl / VBH * 100:.3f}%;color:{SK};'>—</div>"
            f"<div class='vpctlabel' style='top:{y_tp1 / VBH * 100:.3f}%;color:{SK};'>—</div>"
            f"<div class='vpctlabel' style='top:{y_tp2 / VBH * 100:.3f}%;color:{SK};'>—</div>"
            f"<div class='vliqpct' style='top:{(y_sl + (26 if is_long else -26)) / VBH * 100:.3f}%;color:{SK};'>—</div>"
            f"<div class='vliqtxt' style='top:{(y_sl + (26 if is_long else -26)) / VBH * 100:.3f}%;color:{SK};'>LIQ —</div>"
        )
        return f"<div class='ocard'>{head}<div class='vizrel'>{sk_svg}{sk_overlay}</div></div>"

    pts = [entry, stop, t1, t2]
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or (hi * 0.1) or 1.0
    # Extend the axis toward liquidation only a little. The slider can cover the full
    # 1x-100x range, but the trade map should stay focused on entry/stop/targets.
    cap = span * 1.5
    liq_clamped = False
    if is_long and liq < lo:
        lo = liq if liq >= entry - cap else entry - cap
        liq_clamped = liq < lo
    elif (not is_long) and liq > hi:
        hi = liq if liq <= entry + cap else entry + cap
        liq_clamped = liq > hi
    lo -= span * 0.16
    hi += span * 0.16
    liq_color = "#f6465d" if not liq_ok else "#e0a33e"  # red when inside the stop
    VBW, VBH, top, bot = 430, 430, 28, 28
    x0, x1 = 104, 270          # chart (zones/grid/lines) lives in the CENTRE; boxes sit
    ax = (x0 + x1) // 2         # in the gutters either side. vertical arrow column = centre
    plotH = VBH - top - bot

    def Y(p):
        return top + (hi - p) / (hi - lo) * plotH

    ey, sy, y1, y2 = Y(entry), Y(stop), Y(t1), Y(t2)
    liq_y = Y(min(max(liq, lo), hi))                 # clamp into view
    rew_top, rew_bot = min(ey, y2), max(ey, y2)
    risk_top, risk_bot = min(ey, sy), max(ey, sy)
    pctv = lambda p: (p - entry) / entry * 100

    BW, BH = 92, 42            # rounded label-box size
    # boxes sit OFF the chart: ENTRY in the left gutter, stop/TPs in the right gutter,
    # each connected to its dashed level line; the big % sits further right still.
    LEFT_BX, RIGHT_BX = x0 - BW - 6, x1 + 6

    def box(y, color, label, price, side="right"):
        bx = LEFT_BX if side == "left" else RIGHT_BX
        by = y - BH / 2
        return (f"<rect x='{bx}' y='{by:.1f}' width='{BW}' height='{BH}' rx='8' "
                f"fill='#0d1422' fill-opacity='0.95' stroke='{color}' stroke-width='1' vector-effect='non-scaling-stroke'/>"
                f"<text x='{bx + BW / 2:.0f}' y='{by + 17:.1f}' text-anchor='middle' class='vboxlab' fill='{color}'>{label}</text>"
                f"<text x='{bx + BW / 2:.0f}' y='{by + 34:.1f}' text-anchor='middle' class='vboxval'>{fpx(price)}</text>")

    def dline(y, color, w=1.4, dash="6 5"):
        return f"<line x1='{x0}' y1='{y:.1f}' x2='{x1}' y2='{y:.1f}' stroke='{color}' stroke-width='{w}' stroke-dasharray='{dash}'/>"

    grid = "".join(
        f"<line x1='{x0}' y1='{top + i * plotH / 4:.0f}' x2='{x1}' y2='{top + i * plotH / 4:.0f}' stroke='#19202e' stroke-width='1'/>"
        for i in range(5)
    ) + "".join(
        f"<line x1='{x0 + i * (x1 - x0) / 6:.0f}' y1='{top}' x2='{x0 + i * (x1 - x0) / 6:.0f}' y2='{VBH - bot}' stroke='#19202e' stroke-width='1'/>"
        for i in range(7)
    )
    liq_arrow = " ↑" if (liq_clamped and not is_long) else (" ↓" if liq_clamped else "")

    svg = [
        f"<svg viewBox='0 0 {VBW} {VBH}' width='100%' style='display:block'>",
        "<defs>",
        "<marker id='arwG' markerWidth='10' markerHeight='10' refX='5' refY='5' orient='auto-start-reverse'><path d='M2.5,3 L8,5 L2.5,7 Z' fill='#0ecb81'/></marker>",
        "<marker id='arwR' markerWidth='10' markerHeight='10' refX='5' refY='5' orient='auto-start-reverse'><path d='M2.5,3 L8,5 L2.5,7 Z' fill='#f6465d'/></marker>",
        "</defs>",
        grid,
        # shaded reward (entry→TP2) and risk (entry→stop) zones
        f"<rect x='{x0}' y='{rew_top:.1f}' width='{x1 - x0}' height='{rew_bot - rew_top:.1f}' fill='#0ecb81' fill-opacity='0.10' rx='4'/>",
        f"<rect x='{x0}' y='{risk_top:.1f}' width='{x1 - x0}' height='{risk_bot - risk_top:.1f}' fill='#f6465d' fill-opacity='0.11' rx='4'/>",
        # dashed level lines
        dline(y2, "#0ecb81"), dline(y1, "#0ecb81"),
        f"<line x1='{x0}' y1='{ey:.1f}' x2='{x1}' y2='{ey:.1f}' stroke='#c9d1d9' stroke-width='1.4' stroke-dasharray='2 4'/>",
        dline(sy, "#f6465d"),
        f"<line class='vliqline' x1='{x0}' y1='{liq_y:.1f}' x2='{x1}' y2='{liq_y:.1f}' stroke='{liq_color}' stroke-width='1.2' stroke-dasharray='1.5 5'/>",
        # vertical reward (entry→TP2) + risk (entry→stop) arrows, double-headed
        f"<line x1='{ax}' y1='{ey:.1f}' x2='{ax}' y2='{y2:.1f}' stroke='#0ecb81' stroke-width='1.4' marker-start='url(#arwG)' marker-end='url(#arwG)'/>",
        f"<line x1='{ax}' y1='{ey:.1f}' x2='{ax}' y2='{sy:.1f}' stroke='#f6465d' stroke-width='1.4' marker-start='url(#arwR)' marker-end='url(#arwR)'/>",
        # entry-point dot sitting on the entry line, where the reward/risk arrows pivot
        f"<circle cx='{ax}' cy='{ey:.1f}' r='4.5' fill='#ffffff' stroke='#0d1422' stroke-width='1.5' vector-effect='non-scaling-stroke'/>",
        # rounded level boxes
        box(ey, "#5b8cff", "ENTRY", entry, side="left"),
        box(y2, "#0ecb81", "TAKE PROFIT 2", t2),
        box(y1, "#0ecb81", "TAKE PROFIT 1", t1),
        box(sy, "#f6465d", "STOP LOSS", stop),
        "</svg>",
    ]
    # HTML overlay for the % and LIQ text — fixed font sizes (so they don't scale with the
    # chart), positioned over the SVG by % so each still tracks its level at any width.
    def pctlabel(y, color, pct):
        return f"<div class='vpctlabel' style='top:{y / VBH * 100:.3f}%;color:{color};'>{fpct(pct)}</div>"
    overlay = (
        pctlabel(sy, "#f6465d", pctv(stop))
        + pctlabel(y1, "#0ecb81", pctv(t1))
        + pctlabel(y2, "#0ecb81", pctv(t2))
        + f"<div class='vliqpct' style='top:{liq_y / VBH * 100:.3f}%;color:{liq_color};'>{fpct(pctv(liq))}</div>"
        + f"<div class='vliqtxt' style='top:{liq_y / VBH * 100:.3f}%;color:{liq_color};'>LIQ {fpx(liq)}{liq_arrow}</div>"
    )

    return f"<div class='ocard'>{head}<div class='vizrel'>{''.join(svg)}{overlay}</div></div>"


# --------------------------------------------------------------------------- #
# Position Summary + Score (SVG gauge)
# --------------------------------------------------------------------------- #
def build_summary() -> str:
    head = "<div class='chead'><span class='t'>Position Summary</span><span class='analytics-mask' aria-hidden='true'></span></div>"

    def row(k, v, cls="", unit="USDT", detail="", tail=""):
        u = f"<span class='u'>{unit}</span>" if unit else ""
        detail_html = f"<span class='vd'>{detail}</span>" if detail else ""
        tail_cls = " has-tail" if tail else ""
        return (
            f"<div class='srow{tail_cls}'><span class='k'>{k}</span>"
            f"<span class='v {cls}'><span class='vm'>{v}{u}{tail}</span>{detail_html}</span></div>"
        )

    if not valid:
        # Skeleton: every summary row at full size with a muted "—" until levels are entered.
        rp = "<span class='rrpill skel'>—</span>"
        skel = (
            row("Position Size", "—", "skel", "")
            + row("Position Value [exposure]" if is_exposure else "Position Value", "—", "skel", "")
            + row("Stop Distance", "—", "skel", "")
            + row("Risk Amount", "—", "skel", "")
            + row("Reward → TP1", "—", "skel", "", tail=rp)
            + row("Reward → TP2", "—", "skel", "", tail=rp)
            + ("" if is_exposure else row("Minimum leverage", "—", "skel", ""))
            + row("Liquidation Price", "—", "skel", "")
            + row("Liquidation buffer", "—", "skel", "")
            + row("Margin Required", "—", "skel", "")
        )
        return f"<div class='ocard'>{head}{skel}</div>"

    levreq_txt = "&lt;1× (none needed)" if lev_req < 1 else f"{lev_req:.2f}×"
    # Liquidation is only "dangerous" when it sits inside the stop (you'd be force-closed
    # before your stop triggers). Otherwise show it neutral with how far it sits from entry.
    liq_inside = not liq_ok
    liq_cls = "red" if liq_inside else "amber"
    liq_val = fpx(liq)
    liq_detail = f"{liq_dist_pct:.0f}% from entry"
    if liq_buffer > 0:
        buf_val = fpx(liq_buffer)
        buf_detail = f"{liq_buffer_pct:.0f}% past stop"
        buf_cls = "green"
    else:
        buf_val = f"−{fpx(abs(liq_buffer))}"
        buf_detail = "inside stop"
        buf_cls = "red"
    risk_detail = f"{risk_pct_eff:.2f}% of acct"
    if risk_over_guard:
        risk_detail = f"<span style='color:#f6465d'>{risk_detail}</span>"
    rows = (
        row("Position Size", f"{size:,.4f}", "white", coin)
        + row("Position Value [exposure]" if is_exposure else "Position Value",
              f"{notional:,.2f}", "blue" if is_exposure else "")
        + row("Stop Distance", f"${stop_dist:.2f}", "",
              unit="", detail=f"{(stop_dist / entry * 100) if entry else 0:.1f}%")
        + row("Risk Amount", f"{risk_amount:,.2f}", "red", detail=risk_detail)
        + row("Reward → TP1", f"{rew1:,.2f}", "green", tail=f"<span class='rrpill'>1 : {rr1:.2f}</span>")
        + row("Reward → TP2", f"{rew2:,.2f}", "green", tail=f"<span class='rrpill'>1 : {rr2:.2f}</span>")
        + ("" if is_exposure else row("Minimum leverage", levreq_txt, "", ""))
        + row("Liquidation Price", liq_val, liq_cls, "", detail=liq_detail)
        + row("Liquidation buffer", buf_val, buf_cls, "", detail=buf_detail)
        + row("Margin Required", f"{margin_req:,.2f}", "red")
    )
    warn = ""
    if liq_inside:
        warn += (
            "<div class='liqwarn'>⚠ At "
            f"{leverage:.0f}× your liquidation ({fpx(liq)}) sits inside your stop ({fpx(stop)}) — "
            "the position would be force-closed before your stop is hit. Lower the leverage.</div>"
        )
    if risk_over_guard:
        warn += (
            "<div class='liqwarn'>⚠ Maximise mode: loss at stop is "
            f"<b>${risk_amount:,.0f}</b> = <b>{risk_pct_eff:.1f}%</b> of your ${equity:,.0f} balance "
            f"(guard {RISK_GUARD_PCT:.0f}%). Leverage scales this — lower the leverage or margin.</div>"
        )
    return f"<div class='ocard'>{head}{rows}{warn}</div>"


def build_score() -> str:
    head = "<div class='chead'><span class='t'>Position Quality Score</span></div>"

    # Risk/Reward gauge — same semicircular gauge the Trade Dashboard uses (red/amber/green
    # zones with a needle), pointed at the score, with the value below. The coloured arcs are
    # static, so build them once and reuse for both the skeleton and the live gauge.
    gcx, gcy, gR, gL = 100.0, 100.0, 80.0, 62.0

    def _gpt(p, r):
        th = math.radians(180 * (1 - p))
        return gcx + r * math.cos(th), gcy - r * math.sin(th)

    def _garc(p0, p1, color):
        x0, y0 = _gpt(p0, gR)
        x1, y1 = _gpt(p1, gR)
        return (f'<path d="M {x0:.1f} {y0:.1f} A {gR:.0f} {gR:.0f} 0 0 1 {x1:.1f} {y1:.1f}" '
                f'stroke="{color}" stroke-width="15" fill="none"/>')

    arcs = _garc(0.0, 0.40, "#f6465d") + _garc(0.40, 0.60, "#e0a33e") + _garc(0.60, 1.0, "#0ecb81")

    if not valid:
        # Skeleton: the gauge (no needle, "—" score) + the four checklist items with neutral
        # markers, so the box shows its full structure at final size before levels are entered.
        sk_gauge = (
            '<svg viewBox="0 0 200 108" width="100%" style="display:block">'
            + arcs
            + f'<circle cx="{gcx:.0f}" cy="{gcy:.0f}" r="6" fill="#6b747e"/>'
            + '<text x="100" y="72" text-anchor="middle" class="gsn" fill="#4d5663">—</text>'
            + '<text x="100" y="90" text-anchor="middle" class="gso">/ 10</text>'
            + "</svg>"
        )

        def ckskel(label):
            return ("<div class='ck'><span class='i' style='background:#1a202b;color:#4d5663'>–</span>"
                    f"<span style='color:#6b747e'>{label}</span></div>")

        sk_checks = (
            "<div class='svhead' style='color:#4d5663'>—</div>"
            + ckskel("Risk / Reward") + ckskel("Position size")
            + ckskel("Leverage") + ckskel("Risk within limits")
        )
        return f"<div class='ocard scorecard'>{head}<div class='scoreflex'><div class='scoregauge'>{sk_gauge}</div><div class='scorechecks'>{sk_checks}</div></div></div>"

    gpos = max(0.0, min(1.0, score / 10.0))
    gnum_color = "#0ecb81" if gpos >= 0.6 else "#e0a33e" if gpos >= 0.4 else "#f6465d"

    nx, ny = _gpt(gpos, gL)
    gauge = (
        '<svg viewBox="0 0 200 108" width="100%" style="display:block">'
        + arcs
        + f'<line x1="{gcx:.0f}" y1="{gcy:.0f}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#cdd3da" stroke-width="3" stroke-linecap="round"/>'
        + f'<circle cx="{gcx:.0f}" cy="{gcy:.0f}" r="6" fill="#6b747e"/>'
        + f'<text x="100" y="72" text-anchor="middle" class="gsn" fill="{gnum_color}">{score:.1f}</text>'
        + '<text x="100" y="90" text-anchor="middle" class="gso">/ 10</text>'
        + "</svg>"
    )

    def ck(ok, yes, no):
        ic = "<span class='i ok'>✓</span>" if ok else "<span class='i no'>✕</span>"
        return f"<div class='ck'>{ic}<span>{yes if ok else no}</span></div>"

    checks = (
        f"<div class='svhead {sv_cls}'>{sv_label}</div>"
        + ck(rr_ok, "Risk/Reward is great", "Risk/Reward is thin")
        + ck(size_ok, "Position size is optimal", "Position size is heavy")
        + ck(lev_label_ok, "Leverage is conservative", "Leverage is elevated")
        + ck(risk_ok, "Risk is within limits", "Risk exceeds limits")
    )
    return f"<div class='ocard scorecard'>{head}<div class='scoreflex'><div class='scoregauge'>{gauge}</div><div class='scorechecks'>{checks}</div></div></div>"


def build_winrate() -> str:
    head = "<div class='chead'><span class='t'>Break-even Win Rate</span></div>"
    if not valid:
        # Skeleton: break-even structure with muted dashes until levels are entered.
        return (
            f"<div class='ocard wrcard'>{head}"
            "<div class='wrmid'>"
            "<div class='wr-n skel'>—</div>"
            "<div class='wr-s'>Required hit rate</div>"
            "<div class='wr-e skel'>—</div>"
            "</div></div>"
        )
    edge_txt, edge_cls = ("Has an edge", "green") if be1 < 50 else ("Needs hit-rate", "amber")
    return (
        f"<div class='ocard wrcard'>{head}"
        "<div class='wrmid'>"
        f"<div class='wr-n'>{be1:.2f}%</div>"
        "<div class='wr-s'>Required hit rate</div>"
        f"<div class='wr-e {edge_cls}'>{edge_txt}</div>"
        "</div></div>"
    )


def build_marketmoves() -> str:
    """Exposure traders think in price moves, not hit-rate. Show the P&L of a ±5/±10%
    move on the full exposure — direction-aware (a price rise loses on a short)."""
    head = "<div class='chead'><span class='t'>Market Moves</span></div>"
    if not valid:
        # Skeleton: the four price-move rows with muted dashes until levels are entered.
        rows = "".join(
            f"<div class='mm-row'><span class='mm-l'>If Price Moves {'+' if mv > 0 else '−'}{abs(mv)}%</span>"
            "<span class='mm-v skel'>—</span></div>"
            for mv in (5, 10, -5, -10)
        )
        return f"<div class='ocard wrcard mmcard'>{head}<div class='mmlist'>{rows}</div></div>"
    sgn = 1 if is_long else -1
    rows = ""
    for mv in (5, 10, -5, -10):
        pnl = notional * (mv / 100.0) * sgn
        cls = "pos" if pnl >= 0 else "neg"
        dsign = "+" if pnl >= 0 else "−"
        msign = "+" if mv > 0 else "−"
        rows += (
            "<div class='mm-row'>"
            f"<span class='mm-l'>If Price Moves {msign}{abs(mv)}%</span>"
            f"<span class='mm-v {cls}'>{dsign}${abs(pnl):,.0f}</span>"
            "</div>"
        )
    return f"<div class='ocard wrcard mmcard'>{head}<div class='mmlist'>{rows}</div></div>"


with _mobile_viz_slot.container():
    with st.container(key="mobile_viz_grid"):
        st.markdown("<div class='mobile-viz-grid-marker'></div>", unsafe_allow_html=True)
        mv_chart, mv_rail = st.columns([0.86, 0.14])
        with mv_chart:
            st.markdown(f"<div class='mobile-viz'>{build_viz()}</div>", unsafe_allow_html=True)
        with mv_rail:
            _render_liq_rail(f"liq_target_mobile_{symbol}", "liq_rail_mobile")

with c_viz:
    with st.container(key="desktop_viz_grid"):
        dv_chart, dv_rail = st.columns([0.86, 0.14])
        with dv_chart:
            st.markdown(f"<div class='desktop-viz'>{build_viz()}</div>", unsafe_allow_html=True)
        with dv_rail:
            _render_liq_rail(f"liq_target_desktop_{symbol}", "liq_rail_desktop")

if st.session_state.pop("calc_scroll_to_liq", False):
    components.html(
        """
        <script>
        setTimeout(() => {
          const doc = window.parent.document;
          const mobile = doc.querySelector('.st-key-mobile_viz_grid');
          const desktop = doc.querySelector('.st-key-desktop_viz_grid');
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = window.parent.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none';
          };
          const el = visible(mobile) ? mobile : desktop;
          if (!el) return;
          const top = el.getBoundingClientRect().top + window.parent.scrollY - 320;
          window.parent.scrollTo({ top: Math.max(0, top), behavior: 'auto' });
        }, 80);
        </script>
        """,
        height=0,
    )

with c_sum:
    st.markdown(build_summary(), unsafe_allow_html=True)
    # Underneath the Position Summary: Position Quality Score gets the wider readout,
    # while Break-even Win Rate stays as the compact companion card.
    st.markdown(
        f"<div class='quality-row'>{build_score()}{build_marketmoves() if is_exposure else build_winrate()}</div>",
        unsafe_allow_html=True,
    )

# (Bottom metrics strip removed — Risk Per Trade, Risk:Reward and Position Size are shown
#  elsewhere in the calculator; break-even win rate has its own compact card.)

# --------------------------------------------------------------------------- #
# Footer
# --------------------------------------------------------------------------- #
st.markdown(
    f"""<div class='cfoot'>
      <span>ⓘ Always ensure you understand the risks. Never risk more than you can afford to lose.</span>
      <span>Calculated at: <b>{fpx(entry) if valid else '—'} USDT</b></span>
    </div>
    <div class='cfoot cfoot-mode'>
      <span class='cfoot-modeline'><span class='modeinfo'>i<div class='modeinfo-tip up'>
        <div class='ti-h'>Sizing mode</div>
        <div class='ti-r'><b>Protect</b> — your capital at risk is fixed. Leverage only changes the
          margin required to hold the trade, not your dollar loss if you're stopped out. Use it
          to keep a consistent risk per trade.</div>
        <div class='ti-r'><b>Maximise</b> — you fix the margin, and margin × leverage drives the
          position. Both profit and loss scale with leverage, so it's more aggressive: more
          leverage means a bigger position and a bigger potential loss.</div>
      </div></span> Sizing — how Protect and Maximise differ <i>(hover)</i></span>
    </div>""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Push to Journal — handled here (end of script) so every computed value exists. The button
# lives in the Trade Inputs box; clicking it builds the planned-trade row and POSTs it to the
# Google Sheet. Works in BOTH Push Trade and Blank Calc; analyst columns fill on pushed trades.
# --------------------------------------------------------------------------- #
if journal_clicked:
    if not valid:
        st.toast("Enter a valid trade (entry + stop) before pushing to the journal.", icon="⚠️")
    else:
        _q = scanner.live_ticker(symbol)
        _live = _q["last"] if _q else entry
        _payload = {
            "planned_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol,
            "direction": "Long" if is_long else "Short",
            "sizing_mode": "Maximise" if is_exposure else "Protect",
            "entry": round(entry, 6), "stop": round(stop, 6),
            "tp1": round(t1, 6), "tp2": round(t2, 6),
            "rr_tp1": round(rr1, 2), "rr_tp2": round(rr2, 2),
            "position_size": round(size, 6), "notional": round(notional, 2),
            "leverage": leverage, "margin": round(margin_req, 2),
            "risk_usd": round(risk_amount, 2), "risk_pct": round(risk_pct_eff, 3),
            "account_balance": round(equity, 2),
            "liq_price": round(liq, 6), "liq_buffer": round(liq_buffer, 6),
            "setup_score": round(score, 1), "live_price": round(_live, 6),
            "status": "Planned",
        }
        # Analyst columns — only meaningful for a pushed trade with an analysis behind it.
        if not _blank_mode and data:
            _meta = data.get("meta", {}) or {}
            _setup = data.get("setup", {}) if isinstance(data.get("setup"), dict) else {}
            _verdict = data.get("verdict", {}) if isinstance(data.get("verdict"), dict) else {}
            _payload.update({
                "analyst_bias": data.get("market_bias", ""),
                "analyst_market_state": _meta.get("market_state", ""),
                "analyst_phase": _meta.get("current_phase", ""),
                "analyst_setup": _setup.get("type", ""),
                "analyst_verdict": _verdict.get("action", ""),
            })
        _ok, _msg = _post_journal(_payload)
        if _ok:
            st.toast(f"Pushed {symbol} ({_payload['direction']}) to the journal ✓", icon="✅")
        else:
            st.toast(f"Journal push failed — {_msg}", icon="⚠️")
