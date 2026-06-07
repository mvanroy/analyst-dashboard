"""Analyst Dashboard renderer.

Pure renderer: takes a structured analysis dict (produced by the locked
framework, framework/analyst_framework_v1.md) and draws the institutional
single-coin dashboard. No intelligence here — it only displays what's in the
JSON. Static HTML/CSS via st.markdown (auto-heights, no iframe).
"""
from __future__ import annotations

import html as _html
import json
import os
import re

import streamlit as st

ANALYSES_DIR = os.path.join(os.path.dirname(__file__), "analyses")


# ----------------------------------------------------------------- data load
def load_analysis(symbol: str):
    """Return the parsed analysis dict for a symbol, or None if absent."""
    safe = re.sub(r"[^A-Z0-9]", "", (symbol or "").upper())
    if not safe:
        return None
    path = os.path.join(ANALYSES_DIR, f"{safe}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


# ----------------------------------------------------------------- helpers
def _e(v):
    return _html.escape(str(v if v is not None else ""))


def _cls(v):
    v = (v or "").lower()
    if v.startswith("bull") or v == "up":
        return "bull"
    if v.startswith("bear") or v == "down":
        return "bear"
    return "neu"


def _card(title, body, klass=""):
    t = f'<div class="dtitle">{_e(title)}</div>' if title else ""
    return f'<div class="dcard {klass}">{t}{body}</div>'


def _factor_table(block):
    rows = ""
    for fct in block.get("factors", []):
        c = _cls(fct.get("call"))
        rows += (
            "<tr>"
            f'<td class="ffac">{_e(fct.get("factor"))}</td>'
            f'<td class="fread">{_e(fct.get("reading"))}</td>'
            f'<td class="fev">{_e(fct.get("evidence"))}</td>'
            f'<td class="fcall {c}">{_e(fct.get("call"))}</td>'
            "</tr>"
        )
    head = (
        '<table class="dt"><thead><tr>'
        "<th>Factor</th><th>Reading</th><th>Evidence</th><th>Call</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )
    lean = block.get("lean", "")
    lc = _cls(lean)
    foot = (
        f'<div class="lean {lc}">LEAN: {_e(lean)} '
        f'<span class="leanc">({_e(block.get("count",""))})</span></div>'
    )
    return head + foot


def _stars(score, out_of):
    try:
        filled = round(float(score) / float(out_of) * 5)
    except (TypeError, ValueError, ZeroDivisionError):
        filled = 0
    filled = max(0, min(5, filled))
    return (
        '<span class="stars">' + ("★" * filled) + '<span class="emp">'
        + ("★" * (5 - filled)) + "</span></span>"
    )


def _key_stats(stats):
    rows = ""
    for s in stats:
        if "score" in s:
            val = (
                _stars(s["score"], s.get("out_of", 10))
                + f'<span class="statn">{_e(s["score"])}/{_e(s.get("out_of",10))}</span>'
            )
        else:
            rows_cls = "bull" if str(s.get("text","")).lower() in ("high","strong") else "neu"
            val = f'<span class="conf {rows_cls}">{_e(s.get("text"))}</span>'
        rows += f'<div class="statrow"><span class="statl">{_e(s["label"])}</span>{val}</div>'
    return rows


def _donut(bear, bull):
    return (
        '<div class="donutwrap">'
        f'<div class="donut" style="background:conic-gradient(#f6465d 0% {bear}%,#0ecb81 {bear}% 100%);">'
        '<div class="donuthole">'
        f'<div class="dp bear">{_e(bear)}%</div>'
        '<div class="dpl">Bearish</div>'
        "</div></div>"
        f'<div class="dpb"><span class="bull">{_e(bull)}% Bullish</span></div>'
        "</div>"
    )


def _scorecard(sc):
    rows = ""
    for f in sc.get("factors", []):
        c = _cls(f.get("call"))
        mark = {"bull": "✓", "bear": "✓", "neu": "✓"}[c]
        cells = ""
        for col in ("bull", "neu", "bear"):
            on = c == col
            cells += f'<td class="sc-{col}">{(mark if on else "")}</td>'
        rows += f'<tr><td class="scfac">{_e(f.get("factor"))}</td>{cells}</tr>'
    cnt = sc.get("count", {})
    rows += (
        '<tr class="sccount"><td>COUNT</td>'
        f'<td class="sc-bull">{_e(cnt.get("bullish",0))}</td>'
        f'<td class="sc-neu">{_e(cnt.get("neutral",0))}</td>'
        f'<td class="sc-bear">{_e(cnt.get("bearish",0))}</td></tr>'
    )
    table = (
        '<table class="dt sctable"><thead><tr>'
        '<th></th><th class="sc-bull">Bull</th><th class="sc-neu">Neu</th>'
        '<th class="sc-bear">Bear</th></tr></thead><tbody>'
        + rows + "</tbody></table>"
    )
    return _donut(sc.get("bearish_pressure", 0), sc.get("bullish_pressure", 0)) + table


def _evidence_matrix(rows):
    body = ""
    for r in rows:
        ic = _cls(r.get("impact"))
        arrow = {"bull": "↑", "bear": "↓", "neu": "→"}[ic]
        intc = _cls(r.get("interpretation"))
        body += (
            "<tr>"
            f'<td class="ffac">{_e(r.get("factor"))}</td>'
            f'<td class="fread">{_e(r.get("timeframe"))}</td>'
            f'<td class="fev">{_e(r.get("reading"))}</td>'
            f'<td class="fcall {intc}">{_e(r.get("interpretation"))}</td>'
            f'<td class="fcall {ic}">{arrow}</td>'
            f'<td class="fread">{_e(r.get("weight"))}</td>'
            "</tr>"
        )
    return (
        '<table class="dt"><thead><tr>'
        "<th>Factor</th><th>TF</th><th>Reading / Data</th>"
        "<th>Read</th><th>Impact</th><th>Weight</th>"
        "</tr></thead><tbody>" + body + "</tbody></table>"
    )


def _wcmm(w):
    def col(d, klass):
        checks = "".join(
            f'<li>{_e(c)}</li>' for c in d.get("checks", [])
        )
        return (
            f'<div class="wcol {klass}">'
            f'<div class="wtit">{_e(d.get("title"))}</div>'
            f'<div class="wsub">{_e(d.get("subtitle"))}</div>'
            f'<ul class="wchecks">{checks}</ul>'
            f'<div class="wres"><b>Result</b><br>{_e(d.get("result"))}</div>'
            "</div>"
        )
    return (
        '<div class="wgrid">'
        + col(w.get("bullish_upgrade", {}), "bull")
        + col(w.get("bearish_confirmation", {}), "bear")
        + "</div>"
    )


def _trade_plan(tp):
    rows = ""
    for r in tp.get("rows", []):
        tone = _cls(r.get("tone"))
        note = f'<span class="tpnote">{_e(r.get("note"))}</span>' if r.get("note") else ""
        rows += (
            f'<div class="tprow"><span class="tpl">{_e(r.get("label"))}</span>'
            f'<span class="tpv {tone}">{_e(r.get("value"))} {note}</span></div>'
        )
    rr = ""
    for x in tp.get("rr", []):
        rr += f'<div class="rrbox"><div class="rrl">{_e(x.get("label"))}</div><div class="rrv">{_e(x.get("value"))}</div></div>'
    return (
        f'<div class="tpdir">{_e(tp.get("direction"))}</div>'
        + rows + f'<div class="rrwrap">{rr}</div>'
    )


def _levels(kl):
    def side(items, klass, title):
        li = "".join(
            f'<div class="lvrow"><span class="lvp {klass}">{_e(i.get("price"))}</span>'
            f'<span class="lvl">{_e(i.get("label"))}</span></div>'
            for i in items
        )
        return f'<div class="lvcol"><div class="lvhead {klass}">{title}</div>{li}</div>'
    return (
        '<div class="lvgrid">'
        + side(kl.get("resistance", []), "bear", "Resistance")
        + side(kl.get("support", []), "bull", "Support")
        + "</div>"
    )


def _prob(rows):
    out = ""
    for r in rows:
        t = _cls(r.get("tone"))
        out += (
            '<div class="probrow">'
            f'<div class="probl">{_e(r.get("scenario"))}</div>'
            f'<div class="pbar"><div class="pfill {t}" style="width:{_e(r.get("pct"))}%"></div></div>'
            f'<div class="probp">{_e(r.get("pct"))}%</div>'
            "</div>"
        )
    return out


def _kv(items):
    return "".join(
        f'<div class="kvrow"><span class="kvl">{_e(i.get("label"))}</span>'
        f'<span class="kvv {_cls(i.get("tone"))}">{_e(i.get("value"))}</span></div>'
        for i in items
    )


# bull / bear icons loaded from assets; forced to inherit colour via
# fill:currentColor so they match the bias word (green bull / red bear).
def _load_icon(filename, size=32):
    path = os.path.join(os.path.dirname(__file__), "assets", filename)
    try:
        with open(path, "r") as f:
            svg = f.read().strip()
    except OSError:
        return ""
    svg = svg.replace('id="Icons"', "")
    svg = svg.replace(
        "<svg ",
        f'<svg class="bias-ico" fill="currentColor" width="{size}" height="{size}" ',
        1,
    )
    return svg


_BULL_SVG = _load_icon("bull-market.svg")
_BEAR_SVG = _load_icon("bear-market.svg")
_NEU_SVG = (
    '<svg class="bias-ico" viewBox="0 0 40 40" width="30" height="30" fill="currentColor">'
    '<rect x="8" y="18" width="24" height="5" rx="2.5"/></svg>'
)


def _bias_icon(cls):
    return {"bull": _BULL_SVG, "bear": _BEAR_SVG}.get(cls, _NEU_SVG)


# ----------------------------------------------------------------- header
def _header(d):
    chg = d.get("change_pct_24h", 0)
    chg_cls = "bull" if (isinstance(chg, (int, float)) and chg >= 0) else "bear"
    chg_str = (f"+{chg}" if isinstance(chg, (int, float)) and chg >= 0 else f"{chg}") + "%"
    bias = d.get("market_bias", "")
    bc = _cls(bias)
    icon = _bias_icon(bc)
    meta = d.get("meta", {})

    def cell(label, val, vc=""):
        return (
            f'<div class="mcell"><div class="ml">{_e(label)}</div>'
            f'<div class="mv {vc}">{_e(val)}</div></div>'
        )

    main = (
        '<div class="hmain">'
        '<div class="hprice-col">'
        f'<div class="hsym">{_e(d.get("symbol"))} <span class="hperp">{_e(d.get("contract"))}</span></div>'
        f'<div class="hprice">{_e(d.get("price"))} <span class="{chg_cls} hchg">{_e(chg_str)}</span></div>'
        f'<div class="hhead">{_e(d.get("headline"))}</div>'
        "</div>"
        f'<div class="hbias-col {bc}">'
        '<div class="hbl">Market Bias</div>'
        f'<div class="hbv">{_e(bias)} {icon}</div>'
        f'<div class="hbq">({_e(d.get("bias_qualifier"))})</div>'
        "</div>"
        "</div>"
    )
    metastrip = (
        '<div class="hmeta">'
        + cell("Timeframe", meta.get("timeframe_analyzed"), "blue")
        + cell("Analysis Time", meta.get("analysis_time"))
        + cell("Market Regime", meta.get("market_regime"), "amber")
        + cell("Current Phase", meta.get("current_phase"), "blue")
        + "</div>"
    )
    return f'<div class="dhead">{main}{metastrip}</div>'


# ----------------------------------------------------------------- CSS
_CSS = """
.dash{color:#dfe3e8;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.dash *{box-sizing:border-box;}
.bull{color:#0ecb81;} .bear{color:#f6465d;} .neu{color:#aab2bd;}
.blue{color:#4c8dff;} .amber{color:#e0a33e;}
.dcard{background:#0e1116;border:1px solid #1e242c;border-radius:10px;padding:12px 14px;margin-bottom:12px;break-inside:avoid;}
.dtitle{font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#8b94a0;margin-bottom:9px;}
.dbody{column-count:3;column-gap:12px;}
@media(max-width:1100px){.dbody{column-count:2;}}
@media(max-width:760px){.dbody{column-count:1;}}

/* header */
.dhead{display:flex;gap:12px;align-items:stretch;margin-bottom:14px;flex-wrap:wrap;}
.hmain{flex:1 1 320px;background:#0e1116;border:1px solid #1e242c;border-radius:10px;display:flex;overflow:hidden;}
.hprice-col{flex:1;padding:12px 14px;display:flex;flex-direction:column;justify-content:center;}
.hbias-col{flex:1;padding:12px 14px;border-left:1px solid #1e242c;display:flex;flex-direction:column;justify-content:center;text-align:center;}
.bias-ico{transform:scaleX(-1);flex:0 0 auto;}
.hsym{font-size:16px;font-weight:800;letter-spacing:.02em;}
.hperp{font-size:10px;color:#8b94a0;border:1px solid #2a323c;border-radius:4px;padding:1px 5px;vertical-align:middle;margin-left:4px;}
.hprice{font-size:30px;font-weight:800;margin-top:4px;}
.hchg{font-size:15px;font-weight:700;}
.hhead{color:#8b94a0;font-size:12px;margin-top:2px;}
.hmeta{flex:2 1 420px;display:flex;gap:10px;}
.mcell{flex:1;background:#0e1116;border:1px solid #1e242c;border-radius:10px;padding:10px 12px;}
.ml{font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;}
.mv{font-size:14px;font-weight:700;margin-top:5px;}
.hbl{font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#8b94a0;}
.hbv{font-size:26px;font-weight:800;margin-top:2px;display:flex;align-items:center;justify-content:center;gap:6px;}
.hbq{font-size:11px;color:#8b94a0;letter-spacing:.06em;}

/* tables */
.dt{width:100%;border-collapse:collapse;font-size:11px;}
.dt th{text-align:left;color:#8b94a0;font-weight:600;font-size:9px;letter-spacing:.05em;text-transform:uppercase;padding:4px 6px;border-bottom:1px solid #232a33;}
.dt td{padding:5px 6px;border-bottom:1px solid #161b21;vertical-align:top;}
.ffac{font-weight:700;color:#cdd3da;white-space:nowrap;}
.fread{color:#aab2bd;white-space:nowrap;}
.fev{color:#8b94a0;font-size:10.5px;}
.fcall{font-weight:700;white-space:nowrap;}
.lean{margin-top:8px;font-size:11px;font-weight:800;letter-spacing:.04em;}
.leanc{color:#8b94a0;font-weight:600;}

/* scorecard */
.donutwrap{display:flex;flex-direction:column;align-items:center;margin-bottom:10px;}
.donut{width:120px;height:120px;border-radius:50%;display:flex;align-items:center;justify-content:center;}
.donuthole{width:84px;height:84px;border-radius:50%;background:#0e1116;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.dp{font-size:22px;font-weight:800;} .dpl{font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#8b94a0;}
.dpb{margin-top:6px;font-size:11px;font-weight:700;}
.sctable td,.sctable th{text-align:center;}
.sctable .scfac{text-align:left;font-weight:600;color:#cdd3da;white-space:nowrap;font-size:10.5px;}
.sc-bull{color:#0ecb81;} .sc-bear{color:#f6465d;} .sc-neu{color:#aab2bd;}
.sccount td{font-weight:800;border-top:1px solid #232a33;border-bottom:none;font-size:12px;}
.sccount td:first-child{color:#8b94a0;font-size:10px;}

/* key stats */
.statrow{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid #161b21;font-size:12px;}
.statl{color:#aab2bd;}
.stars{color:#e0a33e;letter-spacing:1px;} .stars .emp{color:#3a424d;}
.statn{color:#8b94a0;font-size:11px;margin-left:8px;}
.conf{font-weight:700;}

/* setup */
.setrow{margin-bottom:7px;font-size:11.5px;}
.setlab{color:#8b94a0;font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;}
.setval{color:#dfe3e8;} .setval.blue{color:#4c8dff;font-weight:700;}

/* trade plan */
.tpdir{display:inline-block;background:rgba(76,141,255,.12);color:#4c8dff;border:1px solid rgba(76,141,255,.4);border-radius:5px;padding:2px 8px;font-size:10px;font-weight:700;margin-bottom:9px;}
.tprow{display:flex;justify-content:space-between;align-items:baseline;padding:5px 0;border-bottom:1px solid #161b21;font-size:12px;}
.tpl{color:#8b94a0;font-size:10px;letter-spacing:.05em;text-transform:uppercase;}
.tpv{font-weight:700;text-align:right;}
.tpnote{color:#8b94a0;font-weight:500;font-size:10px;}
.rrwrap{display:flex;gap:8px;margin-top:9px;}
.rrbox{flex:1;background:#11151b;border:1px solid #232a33;border-radius:7px;padding:7px;text-align:center;}
.rrl{font-size:9px;color:#8b94a0;text-transform:uppercase;letter-spacing:.05em;}
.rrv{font-size:15px;font-weight:800;color:#4c8dff;margin-top:2px;}

/* levels */
.lvgrid{display:flex;gap:14px;}
.lvcol{flex:1;}
.lvhead{font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;margin-bottom:5px;}
.lvrow{display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px solid #161b21;}
.lvp{font-weight:700;} .lvl{color:#8b94a0;font-size:10px;text-align:right;}

/* what changes my mind */
.wgrid{display:flex;gap:10px;}
.wcol{flex:1;border:1px solid #232a33;border-radius:8px;padding:9px;}
.wcol.bull{background:rgba(14,203,129,.05);} .wcol.bear{background:rgba(246,70,93,.05);}
.wtit{font-weight:800;font-size:12px;}
.wcol.bull .wtit{color:#0ecb81;} .wcol.bear .wtit{color:#f6465d;}
.wsub{font-size:9.5px;color:#8b94a0;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px;}
.wchecks{margin:0;padding-left:15px;font-size:11px;color:#cdd3da;}
.wchecks li{margin-bottom:3px;}
.wres{margin-top:8px;font-size:10.5px;color:#aab2bd;border-top:1px solid #232a33;padding-top:6px;}

/* probability */
.probrow{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:11px;}
.probl{flex:1.4;color:#cdd3da;}
.pbar{flex:1;height:9px;background:#11151b;border-radius:5px;overflow:hidden;}
.pfill{height:100%;border-radius:5px;}
.pfill.bull{background:#0ecb81;} .pfill.bear{background:#f6465d;} .pfill.neu{background:#e0a33e;}
.probp{width:34px;text-align:right;font-weight:700;}

/* kv + summary */
.kvrow{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #161b21;font-size:11.5px;}
.kvl{color:#8b94a0;} .kvv{font-weight:700;}
.sumlist{margin:0;padding-left:16px;font-size:11.5px;color:#cdd3da;line-height:1.5;}
.sumlist li{margin-bottom:6px;}
.botline{margin-top:9px;border-top:1px solid #232a33;padding-top:8px;font-size:11px;color:#aab2bd;}
.botline b{color:#dfe3e8;}
.failtext{font-size:11.5px;color:#f0b9c1;line-height:1.5;}
"""


# ----------------------------------------------------------------- render
def render(d):
    setup = d.get("setup", {})
    setup_html = (
        f'<div class="setrow"><span class="setlab">Setup Type</span><br>'
        f'<span class="setval blue">{_e(setup.get("type"))}</span></div>'
        f'<div class="setrow"><span class="setlab">Why</span><br>'
        f'<span class="setval">{_e(setup.get("why"))}</span></div>'
        f'<div class="setrow"><span class="setlab">Not</span><br>'
        f'<span class="setval">{_e(setup.get("not"))}</span></div>'
    )

    summary = "".join(f"<li>{_e(s)}</li>" for s in d.get("analyst_summary", []))
    summary_html = (
        f'<ul class="sumlist">{summary}</ul>'
        f'<div class="botline"><b>Bottom Line:</b> {_e(d.get("bottom_line"))}</div>'
    )

    body = (
        '<div class="dbody">'
        + _card("Market Snapshot", _kv(d.get("snapshot", [])))
        + _card("Setup Classification", setup_html)
        + _card("Key Stats", _key_stats(d.get("key_stats", [])))
        + _card("Bias Scorecard", _scorecard(d.get("scorecard", {})))
        + _card("Daily Timeframe — Bias Assessment", _factor_table(d.get("daily", {})))
        + _card("4-Hour Timeframe — Bias Assessment", _factor_table(d.get("h4", {})))
        + _card("Trade Plan", _trade_plan(d.get("trade_plan", {})))
        + _card("Key Levels", _levels(d.get("key_levels", {})))
        + _card("Analyst Summary", summary_html)
        + _card("What Changes My Mind?", _wcmm(d.get("what_changes_my_mind", {})))
        + _card("Probability Distribution", _prob(d.get("probability_distribution", [])))
        + _card("Evidence Matrix — What Weighs In", _evidence_matrix(d.get("evidence_matrix", [])))
        + _card("Additional Data Check", _kv(d.get("additional_data", [])))
        + _card("Most Likely Failure Scenario",
                f'<div class="failtext">{_e(d.get("failure_scenario"))}</div>', "")
        + "</div>"
    )

    style = "<style>" + _CSS.replace("\n", " ") + "</style>"
    html = style + '<div class="dash">' + _header(d) + body + "</div>"
    st.markdown(html, unsafe_allow_html=True)
