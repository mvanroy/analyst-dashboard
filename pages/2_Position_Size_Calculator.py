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

import httpx
import streamlit as st

import chrome
import dashboard
import scanner

st.set_page_config(page_title="Position Calculator", page_icon="📐", layout="wide")

# Shared chrome: nav + world-clocks (brand rendered below alongside the trade chip).
chrome.render_header("POSITION", "CALCULATOR", "Bybit · USDT Perp", brand=False)

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
/* ---- Mode toggles: two segmented controls stacked top-to-bottom, right-aligned in the brand
   row. Each shows BOTH options at once using the "direct" colour scheme — the ACTIVE segment
   gets light shading + a bold label + a coloured border; the inactive segment stays a plain
   light-bordered, muted-label chip. (No dark "inverted" fill, no sliding knob, no heading.) */
.st-key-modestack{flex-direction:column!important;align-items:flex-end!important;gap:6px!important;
  width:auto!important;margin-left:auto!important;align-self:center!important;}
/* each control is a row of two equal segments, butted together (no gap) */
.st-key-sizeseg,.st-key-ctxseg{flex-direction:row!important;gap:0!important;width:220px!important;
  align-items:stretch!important;}
.st-key-sizeseg > [data-testid="stElementContainer"],
.st-key-ctxseg > [data-testid="stElementContainer"]{flex:1 1 0!important;width:auto!important;min-width:0!important;}
/* base segment button */
.st-key-modestack button{width:100%!important;min-height:0!important;font-size:12px!important;
  letter-spacing:.02em;padding:0.34rem 0.4rem!important;white-space:nowrap!important;transition:none!important;
  border:1px solid #2a323c!important;}
/* round only the OUTER corners; overlap the shared inner edge so it reads as one divider */
.st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(1) button,
.st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(1) button{border-radius:7px 0 0 7px!important;}
.st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(2),
.st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(2){margin-left:-1px!important;}
.st-key-sizeseg > [data-testid="stElementContainer"]:nth-child(2) button,
.st-key-ctxseg  > [data-testid="stElementContainer"]:nth-child(2) button{border-radius:0 7px 7px 0!important;}
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
   reach the bottom of the (taller) Position Summary + Risk/Reward Score column */
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
/* Restore Trade Plan button — identical to the Trade Dashboard "Run" pill, centred
   (horizontally + vertically in the leftover space) in the now-taller Trade Inputs box */
.st-key-inputs_card [data-testid="stButton"]{display:flex;justify-content:center;width:100%;}
.st-key-inputs_card [data-testid="stElementContainer"]:has([data-testid="stButton"]){
  margin-top:auto;margin-bottom:auto;width:100%;}
.st-key-inputs_card [data-testid="stButton"] button{border-radius:9999px;
  border:1px solid rgba(230,232,235,.2)!important;background:transparent!important;
  color:#e6e8eb!important;font-weight:500!important;min-height:0;padding:0.25rem 0.85rem;
  width:auto;white-space:nowrap;}
.st-key-inputs_card [data-testid="stButton"] button:hover{border-color:#4c8dff!important;
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
.srow{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;
  border-bottom:1px solid #161b21;font-size:14.5px;line-height:1.5;}
.srow:last-child{border-bottom:none;}
.srow .k{color:#8b94a0;}
.srow .v{font-weight:700;color:#cdd3da;font-variant-numeric:tabular-nums;}
.srow .v.red{color:#f6465d;} .srow .v.green{color:#0ecb81;} .srow .v.blue{color:#4c8dff;}
.srow .v.amber{color:#e0a33e;} .srow .v.white{color:#ffffff;}
.srow .u{color:#8b94a0;font-weight:600;font-size:13px;margin-left:3px;}
/* R:R pill sitting to the right of its reward value (merged from the old R:R rows) */
.srow .rrpill{margin-left:9px;font-size:12.5px;font-weight:800;color:#4c8dff;
  border:1px solid rgba(76,141,255,.45);background:rgba(76,141,255,.10);border-radius:5px;
  padding:1px 6px;font-variant-numeric:tabular-nums;white-space:nowrap;line-height:16px;display:inline-block;}
/* liquidation-inside-stop danger banner in the Position Summary */
.liqwarn{margin-top:11px;padding:8px 11px;border-radius:8px;font-size:11.5px;line-height:1.5;
  background:rgba(246,70,93,.10);border:1px solid rgba(246,70,93,.42);color:#f3a4ad;}

/* ---- score / checklist (matches .vbaction / .wchecks) ---- */
.scoreflex{display:flex;align-items:center;gap:8px;}
.scoreflex .scoregauge{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;}
.scoreflex .scorechecks{flex:1;min-width:0;}
/* score sitting inside the semicircle gauge — 31px SVG renders ≈14.5px (Reward → TP1 size) */
.gsn{font-size:31px;font-weight:800;font-variant-numeric:tabular-nums;font-family:inherit;}
.gso{font-size:13px;font-weight:700;fill:#8b94a0;font-family:inherit;}
/* Risk/Reward Score (small gauge left of the checklist) + Win-Rate (right) under the
   Position Summary, in the narrower account-sized box (tighter padding for room) */
.scorecard{height:100%;padding:14px 9px;}
/* Win-Rate box — mirrors the Leverage box (small, content centred) */
.wrcard{height:100%;display:flex;flex-direction:column;padding:14px 10px;}
.wrcard .chead{margin:0 0 6px;}
.wrcard .chead .t{font-size:9px;letter-spacing:.03em;}
.wrmid{flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;gap:1px;}
.wr-n{font-size:22px;font-weight:800;color:#4c8dff;font-variant-numeric:tabular-nums;line-height:1.05;}
.wr-s{font-size:8.5px;color:#8b94a0;text-transform:uppercase;letter-spacing:.05em;}
.wr-e{font-size:12px;font-weight:700;margin-top:6px;line-height:1.3;}
.wr-e.green{color:#0ecb81;} .wr-e.amber{color:#e0a33e;}
/* Market Moves box (exposure mode) — four price-move → P&L rows, stacked + centred */
.mmcard .mmlist{flex:1;display:flex;flex-direction:column;justify-content:center;gap:9px;}
.mm-row{display:flex;flex-direction:column;align-items:center;text-align:center;line-height:1.18;}
.mm-l{font-size:9px;color:#8b94a0;white-space:nowrap;}
.mm-v{font-size:15px;font-weight:800;font-variant-numeric:tabular-nums;margin-top:1px;}
.mm-v.pos{color:#0ecb81;} .mm-v.neg{color:#f6465d;}
/* stretch the Win-Rate box to match the Score box height */
[data-testid="stColumn"]:has(.wrcard) [data-testid="stLayoutWrapper"],
[data-testid="stColumn"]:has(.wrcard) [data-testid="stElementContainer"],
[data-testid="stColumn"]:has(.wrcard) [data-testid="stMarkdown"],
[data-testid="stColumn"]:has(.wrcard) [data-testid="stMarkdownContainer"]{height:100%;}
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

# Clear-inputs icon (the exchange/swap arrows from the user's SVG), embedded as a CSS mask so a
# single shape can be tinted grey (inactive) → "Calculator" blue (active) via background-color.
_EXCHANGE_SVG = (
    "<svg viewBox='0 0 64 64' xmlns='http://www.w3.org/2000/svg'>"
    "<path d='m2.44 32.33h6.57v-14.53h41.21l-6.32 6.32 4.64 4.65 14.12-14.13.26-.26-14.12-14.12-.26-.26-4.64 4.64 6.58 6.58h-48.04z'/>"
    "<path d='m1.08 49.62 14.12 14.12.26.26 4.64-4.65-6.58-6.58h47.9v-21.11h-6.57v14.54h-41.07l6.32-6.33-4.64-4.64-14.12 14.13z'/>"
    "</svg>"
)
_exchange_uri = "data:image/svg+xml;base64," + base64.b64encode(_EXCHANGE_SVG.encode()).decode()
st.markdown(
    f"""<style>
/* Clear-inputs icon button — exchange arrows, centred at the bottom of the Trade Inputs box in
   Blank Calc. Inactive = grey; activated (hover / press / focus) = the "Calculator" blue. */
.st-key-refreshbtn button{{border:none!important;background:transparent!important;box-shadow:none!important;
  min-height:0!important;width:auto!important;padding:7px!important;border-radius:8px!important;
  font-size:0!important;line-height:0!important;}}
/* hide the (text) label entirely so only the icon shows */
.st-key-refreshbtn button p,.st-key-refreshbtn button [data-testid="stMarkdownContainer"]{{
  font-size:0!important;line-height:0!important;margin:0!important;}}
.st-key-refreshbtn button::before{{content:"";display:inline-block;width:26px;height:26px;
  background-color:#8b94a0;transition:background-color .12s;
  -webkit-mask:url("{_exchange_uri}") center/contain no-repeat;
  mask:url("{_exchange_uri}") center/contain no-repeat;}}
.st-key-refreshbtn button:hover,.st-key-refreshbtn button:focus{{background:rgba(76,141,255,.10)!important;}}
.st-key-refreshbtn button:hover::before,.st-key-refreshbtn button:active::before,
.st-key-refreshbtn button:focus::before,.st-key-refreshbtn button:focus-visible::before{{background-color:#4c8dff;}}
</style>""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Which coin? (persisted; mirrors the most-recently-pushed trade)
# --------------------------------------------------------------------------- #
_pushed = st.query_params.get("symbol")
if _pushed:
    _pu = _pushed.upper()
    st.session_state["calc_symbol"] = _pu
    # A fresh push from the dashboard reloads the plan: drop any persisted edits/shadows for the
    # pushed symbol, then clear the URL param so later reruns + mode switches keep your edits.
    for _s in ("entry", "stop", "t1", "t2"):
        st.session_state.pop(f"{_s}_{_pu}", None)
        st.session_state.pop(f"pv_{_s}_{_pu}", None)
    try:
        del st.query_params["symbol"]
    except Exception:
        pass
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
# Direction: in Blank Calc it's a user choice (persisted); in Push Trade it follows the plan.
if _blank_mode:
    direction = (st.session_state.get("calc_blank_direction") or "long").lower()
else:
    direction = (levels.get("direction") or "long").lower()
is_long = direction != "short"

# Per-setup push from the v3 pattern cards: explicit levels in the URL override the
# file plan (backward-compatible — symbol-only pushes are unaffected).
_qp_entry = st.query_params.get("entry")
if _qp_entry and not _blank_mode:
    try:
        levels = {
            "direction": (st.query_params.get("dir") or "long").lower(),
            "entry": float(_qp_entry),
            "stop": float(st.query_params.get("stop") or 0),
            "target1": float(st.query_params.get("t1") or 0),
            "target2": float(st.query_params.get("t2") or 0),
        }
        direction = levels["direction"]
        is_long = direction != "short"
        for _s in ("entry", "stop", "t1", "t2"):
            st.session_state.pop(f"{_s}_{symbol}", None)
            st.session_state.pop(f"pv_{_s}_{symbol}", None)
        for _k in ("dir", "entry", "stop", "t1", "t2"):
            try:
                del st.query_params[_k]
            except Exception:
                pass
    except (TypeError, ValueError):
        pass

# Level-input keys are namespaced per mode so Blank Calc levels never collide with a pushed
# trade on the same symbol — each set persists independently across mode switches.
_kpfx = "blank_" if _blank_mode else ""
K_ENTRY = f"entry_{_kpfx}{symbol}"
K_STOP = f"stop_{_kpfx}{symbol}"
K_T1 = f"t1_{_kpfx}{symbol}"
K_T2 = f"t2_{_kpfx}{symbol}"

MMR = 0.005  # isolated-margin maintenance margin rate (Bybit default tier)

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
    """Flip Risk ⇄ Exposure sizing mode (on_click for the pill toggle) and persist it."""
    st.session_state["calc_mode"] = not st.session_state.get("calc_mode", False)
    _save_prefs(mode="exposure" if st.session_state["calc_mode"] else "risk")


def _set_mode(exposure: bool):
    """Segmented sizing toggle: select Risk (exposure=False) or Exposure (exposure=True)."""
    st.session_state["calc_mode"] = exposure
    _save_prefs(mode="exposure" if exposure else "risk")


def _set_blank(blank: bool):
    """Segmented context toggle: select Push Trade (blank=False) or Blank Calc (blank=True)."""
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
    lv = (dashboard.load_analysis(_sym) or {}).get("levels", {})
    for suffix, plankey in (("entry", "entry"), ("stop", "stop"), ("t1", "target1"), ("t2", "target2")):
        k = f"{suffix}_{_sym}"
        v = float(lv.get(plankey, 0.0))
        st.session_state[k] = v
        st.session_state[f"pv_{k}"] = v


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


def _persist_balance_exposure():
    """Exposure mode: balance is a fixed reference. The margin-to-use is the canonical
    input, so when balance changes we keep the $ margin and re-derive the % from it."""
    _persist_account()
    _sync_margin_from_usd()


RISK_GUARD_PCT = 2.0  # exposure mode warns when the derived loss-at-stop exceeds this % of balance


# --------------------------------------------------------------------------- #
# Brand row: brand (left) + symbol chip / direction (right) — same container
# pattern as the Trade Dashboard so the heading lands in the identical position.
# --------------------------------------------------------------------------- #
_mode_default = _load_prefs().get("mode", "risk")
_brow = st.container(key="brandrow")
with _brow:
    st.markdown(chrome.brand_html("POSITION", "CALCULATOR", "Bybit · USDT Perp"), unsafe_allow_html=True)
    st.session_state.setdefault("calc_mode", _mode_default == "exposure")
    _exp_on = bool(st.session_state.get("calc_mode", False))
    _blank = st.session_state.get("calc_blank", False)
    # Two segmented toggles, stacked top-to-bottom and pushed to the far right of the brand row.
    # Each shows BOTH options at once with the active one highlighted (the "direct" colour
    # scheme: light shading + bold label + coloured border on the active segment; light border +
    # muted label on the inactive one). Top = sizing (Risk | Exposure); bottom = context
    # (Push Trade | Blank Calc). The active segment's key ends in "_on" so the CSS can colour it.
    with st.container(key="modestack"):
        with st.container(key="sizeseg"):
            st.button("Risk", key="segrisk_on" if not _exp_on else "segrisk_off",
                      on_click=_set_mode, args=(False,))
            st.button("Exposure", key="segexp_on" if _exp_on else "segexp_off",
                      on_click=_set_mode, args=(True,))
        with st.container(key="ctxseg"):
            st.button("Push Trade", key="segpush_on" if not _blank else "segpush_off",
                      on_click=_set_blank, args=(False,))
            st.button("Blank Calc", key="segblank_on" if _blank else "segblank_off",
                      on_click=_set_blank, args=(True,))
mode = "exposure" if _exp_on else "risk"
is_exposure = mode == "exposure"

_modecap = "Exposure-based" if is_exposure else "Risk-based"
st.markdown(
    f"<div class='ctx-cap'>{symbol} · Bybit · USDT Perp · Isolated · {direction.title()} · "
    f"<b style='color:#cdd3da'>{_modecap}</b> sizing</div>",
    unsafe_allow_html=True,
)

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

# --------------------------------------------------------------------------- #
# Main row: Trade Inputs (levels from the dashboard) | Visualization | Summary + Score
# --------------------------------------------------------------------------- #
c_in, c_viz, c_sum = st.columns([1, 1.5, 1.18], gap="medium")

with c_in:
    card = st.container(key="inputs_card")
    with card:
        st.markdown("<div class='chead'><span class='t'>Trade Inputs</span></div>", unsafe_allow_html=True)
        # Blank Calc levels persist across mode switches via a shadow value (pv_*): Streamlit
        # clears a widget's state when it isn't rendered (e.g. while you're in Push Trade), so we
        # seed value= from the shadow and re-save it each render. Push Trade seeds from the plan
        # each time, so it always reflects the pushed levels.
        # BOTH modes persist edits across mode switches via a shadow value (pv_*): Streamlit
        # clears a widget's state when it isn't rendered, so we seed each input from its shadow
        # (falling back to the plan in Push Trade / 0 in Blank Calc) and re-save it each render.
        # A fresh dashboard push or "Restore Trade Plan" resets the shadow back to the plan
        # (handled where the push is read, and in _restore_plan). value= is omitted so the clear/
        # restore callbacks can set these keys without the "default value + Session State" warning.
        def _seed(key, plan_val):
            return float(st.session_state.get(f"pv_{key}", plan_val))

        st.session_state.setdefault(K_ENTRY, _seed(K_ENTRY, float(levels.get("entry", 0.0))))
        st.session_state.setdefault(K_STOP, _seed(K_STOP, float(levels.get("stop", 0.0))))
        st.session_state.setdefault(K_T1, _seed(K_T1, float(levels.get("target1", 0.0))))
        st.session_state.setdefault(K_T2, _seed(K_T2, float(levels.get("target2", 0.0))))
        entry = st.number_input("Entry Price", min_value=0.0, step=0.0001, format="%.4f", key=K_ENTRY)
        stop = st.number_input("Stop Loss", min_value=0.0, step=0.0001, format="%.4f", key=K_STOP)
        t1 = st.number_input("Target 1", min_value=0.0, step=0.0001, format="%.4f", key=K_T1)
        t2 = st.number_input("Target 2", min_value=0.0, step=0.0001, format="%.4f", key=K_T2)
        # keep the shadow in sync (both modes) so edits survive the widget unmounting on a switch
        st.session_state[f"pv_{K_ENTRY}"], st.session_state[f"pv_{K_STOP}"] = entry, stop
        st.session_state[f"pv_{K_T1}"], st.session_state[f"pv_{K_T2}"] = t1, t2
        # Bottom actions — centred: the clear/restore button on top, then Push to Journal beneath
        # it (styled like the Restore Trade Plan pill).
        with st.container(key="inputs_actions"):
            if _blank_mode:
                # Blank Calc: a centred exchange/refresh icon button that CLEARS the trade inputs
                # so you can enter a fresh trade (clears via _clear_blank_inputs). Icon-only label.
                st.button("clear", key="refreshbtn", on_click=_clear_blank_inputs)
            else:
                # Push Trade: "Restore Trade Plan" reloads the pushed levels (account persists).
                st.button("Restore Trade Plan", key="restorebtn", on_click=_restore_plan)
            journal_clicked = st.button("Push to Journal", key="journalbtn")

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
        # Risk-based: you fix the dollar RISK; size follows from risk ÷ stop distance, and
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
def build_viz() -> str:
    badge = f"<span class='posbadge {'long' if is_long else 'short'}'>{'LONG' if is_long else 'SHORT'} POSITION</span>"
    head = f"<div class='chead'><span class='t'>Trade Visualization</span>{badge}</div>"
    if not valid:
        # Skeleton diagram: the full chart structure (grid, zones, level boxes, arrows) at its
        # final size, with evenly-spaced placeholder levels and muted "—" prices/percentages.
        VBW, VBH, top, bot = 760, 430, 28, 28
        x0, x1 = 132, 478
        ax = (x0 + x1) // 2
        plotH = VBH - top - bot
        BW, BH = 116, 42
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
            f"<div class='vliqtxt' style='top:{(y_sl + (26 if is_long else -26)) / VBH * 100:.3f}%;color:{SK};'>LIQ —</div>"
        )
        return f"<div class='ocard'>{head}<div class='vizrel'>{sk_svg}{sk_overlay}</div></div>"

    pts = [entry, stop, t1, t2]
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or (hi * 0.1) or 1.0
    # Extend the axis toward the liquidation price so the liq line is visible — but cap
    # the stretch (at low leverage liq sits near 0 and would squash everything).
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
    VBW, VBH, top, bot = 760, 430, 28, 28
    x0, x1 = 132, 478          # chart (zones/grid/lines) lives in the CENTRE; boxes sit
    ax = (x0 + x1) // 2         # in the gutters either side. vertical arrow column = centre
    plotH = VBH - top - bot

    def Y(p):
        return top + (hi - p) / (hi - lo) * plotH

    ey, sy, y1, y2 = Y(entry), Y(stop), Y(t1), Y(t2)
    liq_y = Y(min(max(liq, lo), hi))                 # clamp into view
    rew_top, rew_bot = min(ey, y2), max(ey, y2)
    risk_top, risk_bot = min(ey, sy), max(ey, sy)
    pctv = lambda p: (p - entry) / entry * 100

    BW, BH = 116, 42           # rounded label-box size
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
        f"<line x1='{x0}' y1='{liq_y:.1f}' x2='{x1}' y2='{liq_y:.1f}' stroke='{liq_color}' stroke-width='1.2' stroke-dasharray='1.5 5'/>",
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
        + f"<div class='vliqtxt' style='top:{liq_y / VBH * 100:.3f}%;color:{liq_color};'>LIQ {fpx(liq)}{liq_arrow}</div>"
    )

    return f"<div class='ocard'>{head}<div class='vizrel'>{''.join(svg)}{overlay}</div></div>"


# --------------------------------------------------------------------------- #
# Position Summary + Score (SVG gauge)
# --------------------------------------------------------------------------- #
def build_summary() -> str:
    head = "<div class='chead'><span class='t'>Position Summary</span><span class='ico'>⧉</span></div>"

    def row(k, v, cls="", unit="USDT", tail=""):
        u = f"<span class='u'>{unit}</span>" if unit else ""
        return f"<div class='srow'><span class='k'>{k}</span><span class='v {cls}'>{v}{u}{tail}</span></div>"

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
    liq_val = f"{fpx(liq)} <span class='u'>· {liq_dist_pct:.0f}% from entry</span>"
    if liq_buffer > 0:
        buf_val = f"{fpx(liq_buffer)} <span class='u'>· {liq_buffer_pct:.0f}% past stop</span>"
        buf_cls = "green"
    else:
        buf_val = f"−{fpx(abs(liq_buffer))} <span class='u'>· inside stop</span>"
        buf_cls = "red"
    risk_tail = (f"<span class='u' style=\"{'color:#f6465d' if risk_over_guard else ''}\">"
                 f" · {risk_pct_eff:.2f}% of acct</span>")
    rows = (
        row("Position Size", f"{size:,.4f}", "white", coin)
        + row("Position Value [exposure]" if is_exposure else "Position Value",
              f"{notional:,.2f}", "blue" if is_exposure else "")
        + row("Stop Distance", f"${stop_dist:.2f}", "",
              unit="", tail=f"<span class='u'> · {(stop_dist / entry * 100) if entry else 0:.1f}%</span>")
        + row("Risk Amount", f"{risk_amount:,.2f}", "red", tail=risk_tail)
        + row("Reward → TP1", f"{rew1:,.2f}", "green", tail=f"<span class='rrpill'>1 : {rr1:.2f}</span>")
        + row("Reward → TP2", f"{rew2:,.2f}", "green", tail=f"<span class='rrpill'>1 : {rr2:.2f}</span>")
        + ("" if is_exposure else row("Minimum leverage", levreq_txt, "", ""))
        + row("Liquidation Price", liq_val, liq_cls, "")
        + row("Liquidation buffer", buf_val, buf_cls, "")
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
            "<div class='liqwarn'>⚠ Exposure mode: loss at stop is "
            f"<b>${risk_amount:,.0f}</b> = <b>{risk_pct_eff:.1f}%</b> of your ${equity:,.0f} balance "
            f"(guard {RISK_GUARD_PCT:.0f}%). Leverage scales this — lower the leverage or margin.</div>"
        )
    return f"<div class='ocard'>{head}{rows}{warn}</div>"


def build_score() -> str:
    head = "<div class='chead'><span class='t'>Risk / Reward Score</span></div>"

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
    head = "<div class='chead'><span class='t'>Win-Rate</span></div>"
    if not valid:
        # Skeleton: break-even structure with muted dashes until levels are entered.
        return (
            f"<div class='ocard wrcard'>{head}"
            "<div class='wrmid'>"
            "<div class='wr-n skel'>—</div>"
            "<div class='wr-s'>Break-even</div>"
            "<div class='wr-e skel'>—</div>"
            "</div></div>"
        )
    edge_txt, edge_cls = ("Has an edge", "green") if be1 < 50 else ("Needs hit-rate", "amber")
    return (
        f"<div class='ocard wrcard'>{head}"
        "<div class='wrmid'>"
        f"<div class='wr-n'>{be1:.2f}%</div>"
        "<div class='wr-s'>Break-even</div>"
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


with c_viz:
    st.markdown(build_viz(), unsafe_allow_html=True)

with c_sum:
    st.markdown(build_summary(), unsafe_allow_html=True)
    # Underneath the Position Summary: Risk/Reward Score (account-sized, left) + Win-Rate
    # Break-even (leverage-sized, bottom-right) — the inverse of the top Leverage|Account row.
    sc_l, sc_r = st.columns([0.82, 0.36])
    with sc_l:
        st.markdown(build_score(), unsafe_allow_html=True)
    with sc_r:
        st.markdown(build_marketmoves() if is_exposure else build_winrate(), unsafe_allow_html=True)

# (Bottom metrics strip removed — Risk Per Trade, Risk:Reward and Position Size are shown
#  elsewhere in the calculator; Win-Rate Break-even moved into the Risk/Reward Score card.)

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
        <div class='ti-r'><b>Risk</b> — your capital at risk is fixed. Leverage only changes the
          margin required to hold the trade, not your dollar loss if you're stopped out. Use it
          to keep a consistent risk per trade.</div>
        <div class='ti-r'><b>Exposure</b> — you fix the margin, and margin × leverage drives the
          position. Both profit and loss scale with leverage, so it's more aggressive: more
          leverage means a bigger position and a bigger potential loss.</div>
      </div></span> Sizing — how Risk and Exposure differ <i>(hover)</i></span>
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
            "sizing_mode": "Exposure" if is_exposure else "Risk",
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
