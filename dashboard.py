"""Analyst Dashboard renderer (Trade Setup Framework).

Pure renderer: takes a structured analysis dict (produced by
framework/trade_setup_framework.md via /trade + /push-dashboard, per
framework/dashboard_json_contract.md) and draws the single-coin dashboard —
market structure + pattern candidates ranked by opportunity. No intelligence
here; it only displays what's in the JSON. Static HTML/CSS via st.markdown.

This is the promoted v3 renderer; dashboard_v3_demo.py remains the sandbox copy.
"""
from __future__ import annotations

import glob
import html as _html
import json
import math
import os
import re

import streamlit as st

import scanner

ANALYSES_DIR = os.path.join(os.path.dirname(__file__), "analyses")


def fmt_price(v):
    """Format a live numeric price like the dashboard's static prices ($58.11)."""
    if v >= 1:
        return f"${v:,.2f}"
    if v >= 0.01:
        return f"${v:.4f}"
    return f"${v:.6f}"


def fmt_volume(v):
    """Compact volume like the dashboard's static '8.7M' (base-asset, no $)."""
    if v is None:
        return "—"
    v = float(v)
    if v >= 1e9:
        return f"{v / 1e9:.1f}B"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:.0f}"


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


def latest_symbol(default="HYPEUSDT"):
    """Symbol of the most recently written analyses/<SYMBOL>.json (by mtime), so
    the dashboard always shows the newest analysis Claude generated."""
    files = glob.glob(os.path.join(ANALYSES_DIR, "*.json"))
    if not files:
        return default
    newest = max(files, key=os.path.getmtime)
    return os.path.splitext(os.path.basename(newest))[0]


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


def _gauge(sc):
    """Semicircular bias gauge driven by the scorecard count (replaces the donut).
    Needle leans bearish (left, red) → bullish (right, green); BIAS SCORE is the
    dominant directional count out of the total factors. No invented percentages."""
    cnt = sc.get("count", {})
    bull = int(cnt.get("bullish", 0) or 0)
    neu = int(cnt.get("neutral", 0) or 0)
    bear = int(cnt.get("bearish", 0) or 0)
    total = (bull + neu + bear) or 1
    # 0 = full bearish (left), 1 = full bullish (right); neutrals hold the centre.
    pos = max(0.0, min(1.0, (bull - bear + total) / (2 * total)))
    if bear > bull:
        score, scls = bear, "bear"
    elif bull > bear:
        score, scls = bull, "bull"
    else:
        score, scls = neu, "neu"

    cx, cy, R, L = 100.0, 100.0, 80.0, 62.0

    def pt(p, r):
        th = math.radians(180 * (1 - p))
        return cx + r * math.cos(th), cy - r * math.sin(th)

    def arc(p0, p1, color):
        x0, y0 = pt(p0, R)
        x1, y1 = pt(p1, R)
        return (
            f'<path d="M {x0:.1f} {y0:.1f} A {R:.0f} {R:.0f} 0 0 1 {x1:.1f} {y1:.1f}" '
            f'stroke="{color}" stroke-width="15" fill="none"/>'
        )

    nx, ny = pt(pos, L)
    svg = (
        '<svg viewBox="0 0 200 112" class="gauge">'
        + arc(0.0, 0.40, "#f6465d")
        + arc(0.40, 0.60, "#e0a33e")
        + arc(0.60, 1.0, "#0ecb81")
        + f'<line x1="{cx:.0f}" y1="{cy:.0f}" x2="{nx:.1f}" y2="{ny:.1f}" '
        'stroke="#cdd3da" stroke-width="3" stroke-linecap="round"/>'
        + f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="6" fill="#6b747e"/>'
        + "</svg>"
    )
    return (
        '<div class="gaugewrap">'
        + svg
        + f'<div class="gscore"><span class="gslab">Bias Score</span>'
        f'<span class="gsnum {scls}">{score}</span><span class="gsout">/ {total}</span></div>'
        '<div class="gtally">'
        f'<div class="gt"><div class="gtl">Bearish</div><div class="gtv bear">{bear}</div></div>'
        f'<div class="gt"><div class="gtl">Neutral</div><div class="gtv neu">{neu}</div></div>'
        f'<div class="gt"><div class="gtl">Bullish</div><div class="gtv bull">{bull}</div></div>'
        "</div>"
        "</div>"
    )


def _scorecard_table(sc):
    """Just the factor breakdown table (Bull/Neu/Bear + COUNT). The donut is
    rendered separately via _donut so it can headline the Analyst Summary card."""
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
    return (
        '<table class="dt sctable"><thead><tr>'
        '<th></th><th class="sc-bull">Bull</th><th class="sc-neu">Neu</th>'
        '<th class="sc-bear">Bear</th></tr></thead><tbody>'
        + rows + "</tbody></table>"
    )


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


def _wcmm_boxes(w):
    """The two 'What Changes My Mind' resolution boxes (bullish / bearish).
    Rendered under the Setup Classification content."""
    if not w:
        return ""

    def col(d, klass):
        checks = "".join(f'<li>{_e(c)}</li>' for c in d.get("checks", []))
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


def _case_lines(bull_case=None, bear_case=None):
    """The competing-hypothesis one-liners (⚑ Bull case / Bear case), rendered
    under the Trade Plan (below Push To Calculator)."""
    rows = ""
    if bull_case:
        rows += (
            '<div class="wcase wcase-bull"><span class="wflag">⚑</span>'
            f'<b>Bull case</b> — {_e(bull_case)}</div>'
        )
    if bear_case:
        rows += (
            '<div class="wcase wcase-bear"><span class="wflag">⚑</span>'
            f'<b>Bear case</b> — {_e(bear_case)}</div>'
        )
    return f'<div class="wcases">{rows}</div>' if rows else ""


def _verdict_badge(v):
    """The take/skip call rendered under the Trade Plan: a coloured ACTION pill
    (ENTER / WAIT / AVOID) plus a one-line plain-English rationale. Driven by the
    top-level `verdict` field; omitted entirely if absent."""
    if not v:
        return ""
    action = (v.get("action") or "").strip().upper()
    cls = {"ENTER": "venter", "WAIT": "vwait", "AVOID": "vavoid"}.get(action, "vwait")
    rationale = v.get("rationale", "")
    rtext = f'<div class="vbtext">{_e(rationale)}</div>' if rationale else ""
    return (
        f'<div class="vbadge {cls}">'
        '<div class="vbhead">'
        f'<span class="vbaction">{_e(action)}</span>'
        "</div>"
        f"{rtext}"
        "</div>"
    )


def _trade_plan(tp, symbol=""):
    # map "To Target 1" -> Target 1 row so the R:R sits inline on that row
    rr_map = {}
    for x in tp.get("rr", []):
        key = (x.get("label", "") or "").replace("To ", "").strip().lower()
        rr_map[key] = x.get("value")

    rows = ""
    for r in tp.get("rows", []):
        tone = r.get("tone")
        vcls = tone if tone in ("bull", "bear", "blue") else ""
        note = f'<span class="tpnote">({_e(r.get("note"))})</span>' if r.get("note") else ""
        rrv = rr_map.get((r.get("label", "") or "").strip().lower())
        rrbox = (
            f'<div class="rrbox"><span class="rrlab">RR</span> {_e(rrv)}</div>'
            if rrv else ""
        )
        rows += (
            f'<div class="tprow"><div class="tplab {vcls}">{_e(r.get("label"))}</div>'
            f'<div class="tpval {vcls}">{_e(r.get("value"))} {note}</div>'
            f"{rrbox}</div>"
        )
    head = (
        '<div class="tphead"><div class="dtitle">Trade Plan</div>'
        f'<div class="tpdir">{_e(tp.get("direction"))}</div></div>'
    )
    return head + rows


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


def _derivatives(items):
    """OI / Funding / CVD as asserted conclusions (one cell each). `tone`
    (bull/bear/neutral) colours the left accent + the reading line."""
    if not items:
        return ""
    rows = ""
    for it in items:
        tone = _cls(it.get("tone"))
        rows += (
            f'<div class="dvrow {tone}">'
            '<span class="dvdot"></span>'
            f'<span class="dvmetric">{_e(it.get("metric"))}</span>'
            f'<span class="dvsignal">{_e(it.get("signal"))}</span>'
            f'<span class="dvnote">· {_e(it.get("note"))}</span>'
            "</div>"
        )
    return f'<div class="dvexec">{rows}</div>'


# bull / bear icons loaded from assets; forced to inherit colour via
# fill:currentColor so they match the bias word (green bull / red bear).
def _load_icon(filename, keep_index=None, viewbox="0 0 60 60", size=32):
    """Load an SVG asset. If keep_index is set, keep only that <path> (used to
    drop the trend-arrow path and keep just the animal)."""
    path = os.path.join(os.path.dirname(__file__), "assets", filename)
    try:
        with open(path, "r") as f:
            svg = f.read().strip()
    except OSError:
        return ""
    paths = re.findall(r"<path[^>]*?/>", svg)
    if keep_index is not None and 0 <= keep_index < len(paths):
        inner = paths[keep_index]
    else:
        inner = "".join(paths)
    return (
        f'<svg class="bias-ico" fill="currentColor" width="{size}" height="{size}" '
        f'viewBox="{viewbox}" xmlns="http://www.w3.org/2000/svg">{inner}</svg>'
    )


# bull animal is the 1st path, bear animal is the 2nd (the other path is the
# arrow). viewBox is cropped to each animal's bbox so it fills the icon.
_BULL_SVG = _load_icon("bull-market.svg", keep_index=0, viewbox="-1 19 62 42", size=34)
_BEAR_SVG = _load_icon("bear-market.svg", keep_index=1, viewbox="-1 23 62 38", size=34)
def _load_neutral_svg():
    """The 'crab' icon for a NEUTRAL bias (crabs go sideways → range/chop). Keeps
    the figure and restyles the root <svg> to inherit the neutral colour via
    currentColor. Falls back to a plain dash if the asset is missing."""
    path = os.path.join(os.path.dirname(__file__), "assets", "crab2.svg")
    try:
        with open(path, "r") as f:
            svg = f.read().strip()
    except OSError:
        return (
            '<svg class="bias-ico" viewBox="0 0 40 40" width="30" height="30" fill="currentColor">'
            '<rect x="8" y="18" width="24" height="5" rx="2.5"/></svg>'
        )
    # Preserve the file's own viewBox (this crab is 0 0 48 48, not 512) so it scales right.
    m = re.search(r'viewBox="([^"]+)"', svg)
    vb = m.group(1) if m else "0 0 512 512"
    return re.sub(
        r"<svg[^>]*?>",
        '<svg class="bias-ico neu-ico" fill="currentColor" width="30" height="30" '
        f'viewBox="{vb}" xmlns="http://www.w3.org/2000/svg">',
        svg,
        count=1,
    )


_NEU_SVG = _load_neutral_svg()


def _bias_icon(cls):
    return {"bull": _BULL_SVG, "bear": _BEAR_SVG}.get(cls, _NEU_SVG)


def _load_live_svg():
    """The 'LIVE' broadcast badge for the live (2s-refreshed) header boxes.
    Recolours the icon's raw red to the dashboard red token; waves/text stay white."""
    path = os.path.join(os.path.dirname(__file__), "assets", "live-stream.svg")
    try:
        with open(path, "r") as f:
            svg = f.read().strip()
    except OSError:
        return ""
    svg = svg.replace("#f51e1e", "#f6465d")
    return svg.replace("<svg ", '<svg class="livebadge-svg" width="34" height="34" ', 1)


_LIVE_SVG = _load_live_svg()


def _live_badge():
    """Flashing LIVE badge, absolutely pinned to the top-right of its parent box
    (parent must be position:relative). Marks a box whose data refreshes live."""
    if not _LIVE_SVG:
        return ""
    return f'<span class="livebadge" title="Live — updates every 2s">{_LIVE_SVG}</span>'


def _load_down_arrow_svg():
    path = os.path.join(os.path.dirname(__file__), "assets", "down-arrow.svg")
    try:
        with open(path, "r") as f:
            svg = f.read().strip()
    except OSError:
        return '<svg class="down-arrow-svg" viewBox="0 0 128 128"><path fill="currentColor" d="M64 88 21 45l6-6 37 37 37-37 6 6z"/></svg>'
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg)
    svg = re.sub(r"<svg\b", '<svg class="down-arrow-svg"', svg, count=1)
    svg = svg.replace("<path ", '<path fill="currentColor" ')
    return svg


_DOWN_ARROW_SVG = _load_down_arrow_svg()


# ----------------------------------------------------------------- header
def _price_bias_card(d, live_price=None, live_chg=None, right_html=None, left_html=None, badge_inline=False):
    """The first dashboard box: symbol/price/headline + Market Bias. Pass
    live_price / live_chg to override the static values from the analysis JSON
    with a frequently-updating live quote (e.g. on the Position Calculator).

    right_html  — replace the Market Bias column with arbitrary HTML.
    left_html   — render this as the LEFT column instead, pushing symbol/price to
                  the right (the Position Calculator puts a LONG/SHORT indicator on
                  the left so the LIVE badge lands in the symbol box's top-right).
    badge_inline — render the LIVE badge inline beside the symbol instead of pinned
                  to the box's top-right corner."""
    price = live_price if live_price is not None else d.get("price")
    chg = live_chg if live_chg is not None else d.get("change_pct_24h", 0)
    chg_cls = "bull" if (isinstance(chg, (int, float)) and chg >= 0) else "bear"
    chg_str = (f"+{chg}" if isinstance(chg, (int, float)) and chg >= 0 else f"{chg}") + "%"

    badge = _live_badge()
    sym_badge = (" " + badge) if badge_inline else ""
    top_badge = "" if badge_inline else badge

    price_col = (
        '<div class="hprice-col">'
        f'<div class="hsym">{_e(d.get("symbol"))} <span class="hperp">{_e(d.get("contract"))}</span>{sym_badge}</div>'
        f'<div class="hprice">{_e(price)} <span class="{chg_cls} hchg">{_e(chg_str)}</span></div>'
        f'<div class="hhead">{_e(d.get("headline"))}</div>'
        "</div>"
    )

    if left_html is not None:
        cols = left_html + price_col
    elif right_html is not None:
        cols = price_col + right_html
    else:
        bias = d.get("market_bias", "")
        bc = _cls(bias)
        icon = _bias_icon(bc)
        cols = price_col + (
            f'<div class="hbias-col {bc}">'
            '<div class="hbl">Market Bias</div>'
            f'<div class="hbv">{_e(bias)} {icon}</div>'
            f'<div class="hbq">({_e(d.get("bias_qualifier"))})</div>'
            "</div>"
        )

    return '<div class="hmain">' + top_badge + cols + "</div>"


def _dash(inner):
    """Wrap an HTML fragment with the dashboard CSS + `.dash` scope."""
    style = "<style>" + _CSS.replace("\n", " ") + "</style>"
    return style + '<div class="dash">' + inner + "</div>"


@st.cache_data(ttl=30, show_spinner=False)
def _live_derivatives(symbol):
    return scanner.live_bybit_derivatives(symbol)


def render_price_bias_card(d, live_price=None, live_chg=None, right_html=None, left_html=None, badge_inline=False):
    """Render just the price+bias card (with the dashboard CSS) on its own — used
    to surface a coin's live price/bias on other pages (e.g. Position Calculator).
    See _price_bias_card for right_html / left_html / badge_inline."""
    st.markdown(
        _dash(_price_bias_card(d, live_price, live_chg, right_html, left_html, badge_inline)),
        unsafe_allow_html=True,
    )


def _snapshot_box(d, q=None):
    """Market Snapshot card. Pass a live quote `q` (from scanner.live_ticker) to
    override Current Price / 24H High / 24H Low / 24H Volume with live values."""
    live = {}
    if q:
        live = {
            "current price": fmt_price(q["last"]),
            "24h high": fmt_price(q["high"]),
            "24h low": fmt_price(q["low"]),
            "24h volume": fmt_volume(q.get("vol")),
        }
    snap_rows = "".join(
        f'<div class="msrow"><span class="msl">{_e(s.get("label"))}</span>'
        f'<span class="msv">{_e(live.get((s.get("label") or "").strip().lower(), s.get("value")))}</span></div>'
        for s in d.get("snapshot", [])[:4]
    )
    return (
        '<div class="mcell mcell-snap">'
        + '<div class="cardhead"><div class="dtitle">Market Snapshot</div>'
        + _live_badge()
        + "</div>"
        + snap_rows
        + "</div>"
    )


def _stroke_icon(paths, size=17):
    return (
        f'<svg class="mcic" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{paths}</svg>'
    )


def _ms_icon(state):
    """Semantic glyph for the Market State: rising/falling arrow, range box, or
    the two-way 'swap' arrows for a Transition."""
    s = (state or "").lower()
    if "up" in s or "bull" in s:
        return _stroke_icon('<path d="M4 17l6-6 3 3 7-8"/><path d="M16 6h5v5"/>')
    if "down" in s or "bear" in s:
        return _stroke_icon('<path d="M4 7l6 6 3-3 7 8"/><path d="M16 18h5v-5"/>')
    if "range" in s:
        return _stroke_icon('<rect x="4" y="7" width="16" height="10" rx="1.5"/>')
    # Transition (default): two arrows pointing opposite ways = control shifting.
    return _stroke_icon('<path d="M4 9h12"/><path d="M13 6l3 3-3 3"/><path d="M20 15H8"/><path d="M11 12l-3 3 3 3"/>')


def _vol_icon(vol):
    """Semantic glyph for Volatility: arrows converging (Compression), diverging
    (Expansion), or steady twin lines (Neutral)."""
    v = (vol or "").lower()
    if "compress" in v:
        return _stroke_icon('<path d="M3 12h7"/><path d="M7 9l3 3-3 3"/><path d="M21 12h-7"/><path d="M17 9l-3 3 3 3"/>')
    if "expan" in v:
        return _stroke_icon('<path d="M10 12H3"/><path d="M6 9l-3 3 3 3"/><path d="M14 12h7"/><path d="M18 9l3 3-3 3"/>')
    return _stroke_icon('<path d="M4 10h16"/><path d="M4 14h16"/>')  # Neutral


_BTC_ICON = '<span class="mcbtc">₿</span>'

# Row icons for the trade-setup list (stop / risk / targets).
_IC_SHIELD = _stroke_icon('<path d="M12 3l7 2.5v5.5c0 4-3 6.9-7 8-4-1.1-7-4-7-8V5.5z"/>')
_IC_RISK = _stroke_icon('<path d="M12 4l9 15.5H3z"/><path d="M12 10v3.6"/><path d="M12 16.6h.01"/>')
_IC_TARGET = _stroke_icon('<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>')
_IC_TARGET2 = _stroke_icon('<circle cx="12" cy="12" r="8"/><path d="M12 2v3.5"/><path d="M12 18.5V22"/><path d="M2 12h3.5"/><path d="M18.5 12H22"/>')
_IC_DOLLAR = (
    '<svg class="dollic" viewBox="0 0 32 32" width="22" height="22" fill="#eef2f8">'
    '<path d="M21,13a1,1,0,0,0,1-1v-.8262a5.17,5.17,0,0,0-5-5.1562V4a1,1,0,0,0-2,0V6.0176a5.1648,'
    '5.1648,0,0,0-1.7476,9.96l4.7525,1.9019A3.1738,3.1738,0,0,1,16.8262,24H15.1738A3.1774,3.1774,'
    '0,0,1,12,20.8262V20a1,1,0,0,0-2,0v.8262a5.17,5.17,0,0,0,5,5.1562V28a1,1,0,0,0,2,0V25.9824a5.'
    '1648,5.1648,0,0,0,1.7476-9.96l-4.7525-1.9019A3.1738,3.1738,0,0,1,15.1738,8h1.6524A3.1774,'
    '3.1774,0,0,1,20,11.1738V12A1,1,0,0,0,21,13Z"/></svg>'
)
_ESTEP_ARROW = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13"/>'
    '<path d="M13 6l6 6-6 6"/></svg>'
)


def _cor_band(cor):
    """Map a BTC-correlation coefficient to its (label, tone-key) per the
    framework's Intermarket Correlation Bands (trade_setup_framework.md, Phase 5).
    The label describes degree of BTC dependency, NOT market direction — the
    directional read lives in the note. Returns None when cor is missing/NaN."""
    if not isinstance(cor, (int, float)) or cor != cor:
        return None
    if cor >= 0.80:
        return ("Risk On", "on")
    if cor >= 0.60:
        return ("Moderate", "mod")
    if cor >= 0.30:
        return ("Partial", "partial")
    if cor >= 0.00:
        return ("Neutral", "neutral")
    if cor >= -0.20:
        return ("Risk Off", "off")
    return ("Inverse", "inverse")


def _market_condition_box(d):
    """v3 Market Condition — a 3-node stepper (Trade Setup Framework):
      ① Market State   ② Volatility   ③ Intermarket Context (BTC)
    Each node carries a semantic icon, a status chip, and one evidence line.
    Reads `market_structure` (state / volatility / structure[] / volatility_note)
    and `intermarket` (read / note); falls back to legacy meta.* fields."""
    ms = d.get("market_structure", {})
    meta = d.get("meta", {})
    state = ms.get("state") or meta.get("market_state") or meta.get("market_regime") or "—"
    vol = ms.get("volatility") or meta.get("volatility_state") or "—"
    structure = ms.get("structure") or []
    state_text = structure[0] if structure else (meta.get("market_state_note") or "")
    vol_text = ms.get("volatility_note") or ""
    inter = d.get("intermarket") or {}
    inter_text = inter.get("note") or ""

    su = state.upper()
    state_tone = "tone-up" if ("UP" in su or "BULL" in su) else "tone-dn" if ("DOWN" in su or "BEAR" in su) else "tone-amber"
    state_chip = {"tone-up": "chip-up", "tone-dn": "chip-dn"}.get(state_tone, "chip-amber")
    vu = vol.upper()
    vol_tone = "tone-exp" if "EXPAN" in vu else "tone-comp" if "COMPRESS" in vu else "tone-neu"
    vol_chip = {"tone-exp": "chip-exp", "tone-comp": "chip-comp"}.get(vol_tone, "chip-neu")

    # Intermarket label is DERIVED from the COR value (never hand-set). Falls back
    # to a stored `read` only when no correlation number is present.
    cor = inter.get("cor")
    cor_tf = inter.get("cor_tf") or ""
    band = _cor_band(cor)
    if band:
        inter_label, key = band
        inter_tone, inter_chip = f"tone-cor-{key}", f"chip-cor-{key}"
    else:
        inter_label, inter_tone, inter_chip = inter.get("read") or "—", "tone-neu", "chip-neu"

    cor_html = ""
    if isinstance(cor, (int, float)) and cor == cor:  # number, not NaN
        lbl = f"COR ({cor_tf})" if cor_tf else "COR"
        cor_html = f'<span class="mccor">{lbl} {"+" if cor >= 0 else ""}{cor:.2f}</span>'

    def seg(tone, icon, label, chip_cls, chip_text, text, last=False, metric=""):
        chip = f'<span class="vchip {chip_cls}">{_e(chip_text)}</span>' if chip_text else ""
        return (
            f'<div class="mcseg {tone}{" mclast" if last else ""}">'
            + f'<div class="mcseglabel">{_e(label)}</div>'
            + f'<div class="mcchiprow">{chip}{metric}</div>'
            + (f'<div class="mcsegtext">{_hl_numbers(text)}</div>' if text else "")
            + "</div>"
        )

    body = (
        '<div class="mc-grid">'
        + '<div class="mc-sv">'
        + seg(state_tone, _ms_icon(state), "Market State", state_chip, state, state_text)
        + seg(vol_tone, _vol_icon(vol), "Volatility", vol_chip, vol, vol_text)
        + "</div>"
        + '<div class="mc-im">'
        + seg(inter_tone, _BTC_ICON, "Intermarket Context", inter_chip, inter_label, inter_text, last=True, metric=cor_html)
        + "</div>"
        + "</div>"
    )
    card = _card("", body, "mc-cond")
    return (
        f'<div class="mc-desktop">{card}</div>'
        '<details class="mc-collapse">'
        f'<summary aria-label="Toggle market state"><span class="mc-summary-label">Market State</span>{_DOWN_ARROW_SVG}</summary>'
        + card
        + "</details>"
    )


def _bias_box(d):
    """Standalone Market Bias box: the directional read (Bullish / Bearish /
    Neutral) with its animal icon — bull, bear, or crab (sideways) — and the
    one-line bias thesis underneath, so the 'what to do about it' sits with the call."""
    ms = d.get("market_structure") or {}
    bias = ms.get("bias") or d.get("market_bias", "") or "—"
    note = ms.get("bias_note") or d.get("bias_qualifier")
    bc = _cls(bias)
    # Title sits top-left (via _card); the bias value + note live in a wrapper
    # that flex-centres vertically in the space beneath the title.
    inner = (
        f'<div class="biasrow {bc}">'
        f'<div class="biasval">{_e(bias)}</div>'
        f'{_bias_icon(bc)}'
        "</div>"
    )
    if note:
        inner += f'<div class="biasnote">{_hl_numbers(note)}</div>'
    body = f'<div class="biaswrap">{inner}</div>'
    return _card("Market Bias", body, "mc-bias")


def _positioning_edge_box(d):
    edge = d.get("positioning_edge") or {}
    if not edge:
        return ""

    items = [
        ("Funding", edge.get("funding")),
        ("Open Interest", edge.get("open_interest")),
        ("Liquidity", edge.get("liquidity")),
        ("Missing Data", edge.get("missing")),
    ]
    cells = ""
    for label, text in items:
        if not text:
            continue
        cells += (
            '<div class="pecell">'
            f'<div class="pelabel">{_e(label)}</div>'
            f'<div class="petext">{_hl_numbers(text)}</div>'
            "</div>"
        )
    if not cells:
        return ""
    return _card(
        "Positioning Edge",
        '<div class="pegrid">' + cells + "</div>",
        "positioning-edge",
    )


def _regime_thesis(d):
    """Leverage and Flow box (OI/Funding/CVD). The Trading Thesis cell was removed
    for now so the pattern candidates follow straight after the price-ticker band.
    Returns "" when there's nothing to show."""
    # Leverage & Flow box: OI/Funding/CVD exec summary | divider | net-read
    # synthesis. Small font so the one-line signal+note lines fit the column width.
    deriv = _derivatives(d.get("derivatives", []))
    if not deriv:
        return ""
    split = "<div class='dvsplit'>" + deriv
    dsum = d.get("derivatives_summary")
    if dsum:
        split += f'<div class="dvsummary">{_e(dsum)}</div>'
    split += "</div>"
    lf = f'<div class="hmeta-deriv"><div class="dtitle">Leverage and Flow</div>{split}</div>'
    return '<div class="hmeta-rt">' + lf + "</div>"


def _dhead_bottom(d):
    """Header's bottom row, three columns:
      1. Setup Classification + What Changes My Mind (stacked)
      2. Trade Plan (+ Push To Calculator) + Verdict (stacked)
      3. Analyst Summary
    """
    sym = re.sub(r"[^A-Z0-9]", "", (d.get("symbol") or "").upper())

    wcmm = _wcmm_boxes(d.get("what_changes_my_mind", {}))
    verdict_body = _verdict_badge(d.get("verdict")) + _case_lines(
        d.get("bull_case"), d.get("bear_case")
    )

    sc = d.get("scorecard", {})
    summary = "".join(f"<li>{_e(s)}</li>" for s in d.get("analyst_summary", []))
    analyst_body = (
        _gauge(sc)
        + f'<ul class="sumlist">{summary}</ul>'
    )

    # 3x2 grid: setup|plan|analyst over wcmm|verdict|analyst (analyst spans both
    # rows). WCMM and Verdict share a row, so the grid forces them to equal height.
    return (
        '<div class="dhead-bottom">'
        + f'<div class="g-setup">{_setup_box(d)}</div>'
        + f'<div class="g-plan">{_card("", _trade_plan(d.get("trade_plan", {}), sym))}</div>'
        + f'<div class="g-analyst">{_card("Analyst Summary", analyst_body)}</div>'
        + f'<div class="g-wcmm">{(_card("What Changes My Mind?", wcmm) if wcmm else "")}</div>'
        + f'<div class="g-verdict">{(_card("Verdict", verdict_body) if verdict_body else "")}</div>'
        + "</div>"
    )


_PRICE_RE = re.compile(r"\$\d[\d,]*(?:\.\d+)?(?:\s*[-–]\s*\$?\d[\d,]*(?:\.\d+)?)*")


def _setup_box(d):
    # v3: one "Setup Classification" box per setup thesis (up to 3), each combining
    # Setup Type + the patterns identified + Thesis + Most Likely Failure. Falls
    # back to the single legacy `setup` + top-level `patterns`/`failure_scenario`.
    setups = d.get("setups")
    if not setups:
        s = d.get("setup", {})
        setups = [{
            "type": s.get("type"),
            "patterns": d.get("patterns", []),
            "thesis": s.get("thesis"),
            "failure_scenario": d.get("failure_scenario"),
        }]
    setups = [s for s in setups if s][:3]

    # colour price levels by TRADE direction (not market bias): long -> green,
    # short -> red.
    direction = (d.get("trade_plan", {}).get("direction") or "").lower()
    num_cls = "numred" if "short" in direction else "numgreen"

    def hl(text):
        esc = _e(text)
        return _PRICE_RE.sub(
            lambda m: f'<span class="num {num_cls}">{m.group(0)}</span>', esc
        )

    def row(label, value_html, cls=""):
        return (
            f'<div class="srow"><div class="slab">{_e(label)}</div>'
            f'<div class="sval {cls}">{value_html}</div></div>'
        )

    def one(s):
        pats = s.get("patterns") or []
        patrow = ""
        if pats:
            chips = "".join(f'<span class="patchip">{_e(p)}</span>' for p in pats)
            patrow = (
                '<div class="srow"><div class="slab">Patterns</div>'
                f'<div class="sval"><div class="patrow">{chips}</div></div></div>'
            )
        body = (
            row("Setup Type", _e(s.get("type")), "blue")
            + patrow
            + row("Thesis", hl(s.get("thesis")))
            + row("Most Likely Failure", hl(s.get("failure_scenario")))
        )
        return (
            '<div class="setupbox"><div class="dtitle">Setup Classification</div>'
            '<div class="setup-grid">' + body + "</div></div>"
        )

    return '<div class="setupstack">' + "".join(one(s) for s in setups) + "</div>"


# ----------------------------------------------------------------- CSS
_CSS = """
.dash{color:#dfe3e8;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.dash *{box-sizing:border-box;}
.bull{color:#0ecb81;} .bear{color:#f6465d;} .neu{color:#aab2bd;}
.blue{color:#4c8dff;} .amber{color:#e0a33e;}
.dcard{background:#13101e;border:1px solid #1e242c;border-radius:10px;padding:12px 14px;margin-bottom:12px;break-inside:avoid;}
.dtitle{font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#8b94a0;margin-bottom:9px;}
.dbody{column-count:3;column-gap:12px;}
@media(max-width:1100px){.dbody{column-count:2;}}
@media(max-width:760px){.dbody{column-count:1;}}
.drow2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:auto auto auto auto;gap:12px;margin-bottom:12px;align-items:start;}
.drow3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-rows:auto auto auto auto;gap:12px;margin-bottom:12px;align-items:start;}
.drow4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:12px;align-items:stretch;}
.drow2 .dcard,.drow3 .dcard,.drow4 .dcard{margin-bottom:0;}
.dstack{display:flex;flex-direction:column;gap:12px;}
.positioning-edge{border-color:rgba(224,163,62,.36)!important;background:rgba(18,16,28,.78);}
.pegrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;}
.pecell{min-width:0;border:1px solid rgba(139,92,246,.20);border-radius:8px;background:rgba(8,10,18,.30);padding:9px 10px;}
.pelabel{font-size:10px;font-weight:850;letter-spacing:.07em;text-transform:uppercase;color:#e0a33e;margin-bottom:5px;}
.petext{font-size:12.5px;line-height:1.42;color:#dce3ec;}
@media(max-width:1100px){.pegrid{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:760px){.pegrid{grid-template-columns:1fr;}.petext{font-size:12.2px;}}
/* pattern candidate cards (Phase 3/4) — hex glyph · name + maturity pill ·
   qualifier subtitle · large grade box · classification · summary */
.drowlab{font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#8b94a0;margin:2px 0 8px;}
.pcard{display:flex;flex-direction:column;gap:11px;}
/* In a multi-column row, each card becomes a subgrid spanning the 4 shared row
   lines so head/summary/entry/rest align across columns (entry zones level). */
.drow2 .pcard,.drow3 .pcard{display:grid;grid-template-rows:subgrid;grid-row:1/-1;row-gap:11px;}
.pc-tools{align-self:end;}
.phead{display:flex;align-items:flex-start;gap:12px;}
.pmain{flex:1 1 auto;min-width:0;}
.ptoprow{display:flex;align-items:center;gap:9px;flex-wrap:wrap;}
.ppills{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px;}
.pname{font-size:20.5px;font-weight:600;color:#f0f2f5;line-height:1.15;letter-spacing:-.01em;}
.pmeta{font-size:13px;line-height:1.45;margin-top:6px;}
.pmeta .pcls{color:#8b5cf6;font-weight:700;}
.pmeta .pcls.dir-long{color:#2ebd85;}
.pmeta .pcls.dir-short{color:#f6465d;}
.pmeta .pqal{color:#aab2bd;}
.pmat{font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border-radius:6px;padding:3px 9px;white-space:nowrap;background:transparent;color:#f0f2f5;border:1px solid rgba(255,255,255,.6);}
.pmat.triggered{background:rgba(228,160,8,.18);color:#e3a008;border:1px solid rgba(228,160,8,.55);}
.pmat.ready{background:rgba(14,203,129,.16);color:#0ecb81;border:1px solid rgba(14,203,129,.5);}
.pmat.mature{background:rgba(46,189,133,.16);color:#26a69a;border:1px solid rgba(46,189,133,.5);}
.pmat.developing{background:rgba(76,141,255,.16);color:#4c8dff;border:1px solid rgba(76,141,255,.5);}
.pmat.emerging{background:rgba(139,148,158,.16);color:#aab2bd;border:1px solid rgba(139,148,158,.45);}
.pmode{font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border-radius:6px;padding:3px 9px;white-space:nowrap;background:transparent;color:#f0f2f5;border:1px solid rgba(255,255,255,.6);}
.pmode.aggressive{background:rgba(245,130,31,.16);color:#f5821f;border:1px solid rgba(245,130,31,.5);}
.pmode.balanced{background:rgba(46,189,133,.16);color:#2ebd85;border:1px solid rgba(46,189,133,.5);}
.pmode.chasing{background:rgba(139,148,158,.16);color:#aab2bd;border:1px solid rgba(139,148,158,.45);}
.pgrade{flex:0 0 auto;width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900;color:#f0f2f5;border:1px solid #eef2f8;background:transparent;box-shadow:none;}
.pgrade.a,.pgrade.b,.pgrade.c{color:#f0f2f5;}
.psummary{font-size:13px;color:#e6e8eb;line-height:1.5;}
.plab{font-size:9px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;margin:6px 0 1px;}
.plist{margin:0;padding-left:15px;font-size:13px;color:#cdd3da;line-height:1.5;}
.dash .plist li{font-size:13px;}
.plist.miss{color:#9aa3ad;}
.note-section .plist,.note-section .plist.miss,.note-section .plist li{color:#f2f4f8;}
.note-section .success-note{color:#f2f4f8;font-weight:400;}
.pconf{font-size:11px;color:#cdd3da;line-height:1.5;}
.psec-mobile-collapse{display:none;}
/* coloured number tokens in pattern prose */
.numpos{color:#2ebd85;font-weight:700;}
.numneg{color:#f6465d;font-weight:700;}
.numneu{color:#e8edf6;font-weight:700;}
/* Phase 5 trade entry — hero + tiles */
.pentry{margin-top:6px;display:flex;flex-direction:column;gap:11px;}
.ezhero{position:relative;border:1px solid rgba(46,189,133,.32);background:linear-gradient(180deg,rgba(46,189,133,.06),rgba(46,189,133,.015));border-radius:12px;padding:16px;}
/* short setups tint the entry hero red instead of green */
.ezhero.ez-short{border-color:rgba(246,70,93,.32);background:linear-gradient(180deg,rgba(246,70,93,.06),rgba(246,70,93,.015));}
.ez-short .ezpill{color:#f6465d;border-color:rgba(246,70,93,.5);}
.ez-short .ezsub{color:#f6465d;}
/* calculator push icon — top-right of the entry hero, grey idle → blue on hover */
.dash a.ezcalc{position:absolute;top:14px;right:14px;color:#8b94a0;line-height:0;display:block;text-decoration:none;}
.dash a.ezcalc:hover{color:#4c8dff;}
.dash .ez-long a.ezcalc:hover{color:#2ebd85;}
.dash .ez-short a.ezcalc:hover{color:#f6465d;}
.dash a.ezcalc svg{width:29px;height:29px;display:block;}
.ezpill{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#2ebd85;border:1px solid rgba(46,189,133,.5);border-radius:7px;padding:3px 10px;}
.ezbig{font-size:24px;font-weight:800;color:#f4f7fa;letter-spacing:-.01em;margin-top:10px;line-height:1;}
.ezsub{font-size:11px;font-weight:700;letter-spacing:.04em;color:#2ebd85;margin-top:9px;}
.ezdash{border-top:1px dashed #2f3a44;margin:14px 0;}
.ezstats{display:flex;align-items:center;gap:24px;}
.hzlab{font-size:11px;color:#8b94a0;}
.hzval{font-size:18px;font-weight:800;color:#e8edf6;margin-top:3px;display:flex;align-items:center;gap:8px;}
.hzsub{font-size:13px;font-weight:700;color:#8b94a0;white-space:nowrap;}
.hzval.bull{color:#2ebd85;}.hzval.bear{color:#f6465d;}.hzval.neu{color:#e8edf6;}
.hzpill{font-size:9.5px;font-weight:700;letter-spacing:.02em;border-radius:6px;padding:2px 7px;border:1px solid currentColor;}
.aring{position:absolute;top:14px;right:14px;width:64px;text-align:center;}
.aring svg{width:62px;height:62px;display:block;margin:0 auto;}
.arnum{position:absolute;top:20px;left:0;right:0;font-size:17px;font-weight:800;color:#f4f7fa;}
.arnum .arden{font-size:8.5px;color:#8b94a0;font-weight:600;}
.arlab{font-size:8px;letter-spacing:.04em;text-transform:uppercase;color:#8b94a0;margin-top:1px;}
.ltrack{position:relative;height:70px;margin-top:36px;}
.ltline{position:absolute;left:0;right:0;top:34px;height:2px;background:#2a323c;border-radius:2px;}
.lzbox{position:absolute;top:31px;height:8px;background:#2ebd85;border-radius:1px;z-index:1;}
.lzbox:before,.lzbox:after{content:"";position:absolute;top:50%;width:1px;height:20px;background:#2ebd85;border-radius:1px;}
.lzbox:before{left:0;transform:translate(-50%,-50%);}
.lzbox:after{right:0;transform:translate(50%,-50%);}
.lmark{position:absolute;top:0;bottom:0;transform:translateX(-50%);width:120px;z-index:2;}
.lmtop{position:absolute;top:4px;left:0;right:0;text-align:center;font-size:14.5px;font-weight:800;white-space:nowrap;}
.lmdot{position:absolute;top:35px;left:50%;width:13px;height:13px;border-radius:50%;transform:translate(-50%,-50%);border:2px solid #0e1116;z-index:2;}
.lmbot{position:absolute;top:48px;left:0;right:0;text-align:center;font-size:9.5px;font-weight:800;letter-spacing:.05em;white-space:nowrap;color:#8b94a0;}
.lmtop.c-bear{color:#f6465d;}.lmdot.c-bear{background:#f6465d;}.lmbot.c-bear{color:#f6465d;}
.lmtop.c-blue{color:#4c8dff;}.lmdot.c-blue{background:#4c8dff;}.lmbot.c-blue{color:#4c8dff;}
.lmtop.c-bull{color:#2ebd85;}.lmdot.c-bull{background:#2ebd85;}.lmbot.c-bull{color:#2ebd85;}
.ltnow{position:absolute;top:0;width:1px;height:60px;background:#eef2f8;transform:translateX(-50%);z-index:0;}
.ltnowic{position:absolute;left:50%;bottom:100%;transform:translateX(-50%);margin-bottom:4px;display:inline-flex;}
.ekey{margin-top:6px;display:flex;flex-direction:column;gap:11px;}
.ekrow{display:flex;align-items:center;gap:11px;}
.eklead{flex:0 0 32px;display:inline-flex;align-items:center;}
.ekic{display:inline-flex;align-items:center;}
.ekic svg{width:17px;height:17px;}
.ektp{font-size:12.5px;font-weight:800;letter-spacing:.03em;color:#4c8dff;}
.eknote{flex:1;min-width:0;font-size:13px;color:#aab2bd;line-height:1.4;}
.ekrr{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;font-size:13.5px;font-weight:800;letter-spacing:.02em;color:#fff;background:#3a7afe;border-radius:7px;padding:3px 10px;white-space:nowrap;}
.ekrisk{flex:0 0 auto;display:inline-flex;align-items:center;font-size:13.5px;font-weight:800;letter-spacing:.02em;color:#e8edf6;white-space:nowrap;}
.etiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;}
.etile{border-radius:11px;padding:12px;border:1px solid;}
.etlh{display:flex;align-items:center;gap:7px;font-size:10px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;}
.etbig{font-size:17px;font-weight:800;margin-top:8px;color:#f4f7fa;white-space:nowrap;}
.etsub{font-size:10.5px;color:#8b94a0;margin-top:3px;}
.tic{width:14px;height:14px;}
.t-stop{border-color:rgba(246,70,93,.4);background:rgba(246,70,93,.07);}.t-stop .etlh{color:#f6465d;}
.t-risk{border-color:rgba(228,160,8,.4);background:rgba(228,160,8,.07);}.t-risk .etlh{color:#e0a33e;}
.t-t1{border-color:rgba(76,141,255,.4);background:rgba(76,141,255,.07);}.t-t1 .etlh,.t-t1 .etsub{color:#4c8dff;}
.t-t2{border-color:rgba(76,141,255,.4);background:rgba(76,141,255,.07);}.t-t2 .etlh,.t-t2 .etsub{color:#4c8dff;}
.t-t1 .etsub,.t-t2 .etsub{font-size:12.5px;font-weight:800;}
/* analysis sections with icon column */
.psec{display:flex;gap:11px;margin-top:13px;}
.psec-plain{display:block;}
.psecic{flex:0 0 auto;width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;border:1px solid #2a323c;background:#161b22;}
.psecic .sic{width:15px;height:15px;}
.psecic.ic-ev{color:#eef2f8;background:transparent;border-color:#eef2f8;}
.psecic.ic-note{color:#eef2f8;background:transparent;border-color:#eef2f8;}
.psecic.ic-conf{color:#eef2f8;background:transparent;border-color:#eef2f8;}
.psecic.ic-edge{color:#e0a33e;background:rgba(228,160,8,.06);border-color:rgba(228,160,8,.34);}
.psecbody{flex:1;min-width:0;}
.psechd{font-size:10px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;margin-bottom:5px;display:flex;align-items:center;gap:9px;}
.pe-detail{display:flex;flex-direction:column;gap:7px;}
.perow{display:grid;grid-template-columns:92px minmax(0,1fr);gap:10px;align-items:start;padding:7px 0;border-top:1px solid rgba(139,148,158,.12);}
.perow:first-child{border-top:0;padding-top:0;}
.perlab{font-size:9px;font-weight:850;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;line-height:1.35;}
.pertext{font-size:12.5px;color:#cdd3da;line-height:1.45;}
.perow.pe-impact{grid-template-columns:1fr;padding:9px 10px;border:1px solid rgba(228,160,8,.28);border-radius:9px;background:rgba(228,160,8,.06);}
.perow.pe-impact .perlab{color:#e0a33e;}
.perow.pe-impact .pertext{font-size:13px;color:#f0e6cf;font-weight:650;}
.peverdict{display:inline-flex;align-items:center;margin-right:7px;padding:2px 7px;border-radius:999px;
  font-size:9px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;border:1px solid currentColor;line-height:1.15;}
.peverdict.strengthens{color:#2ebd85;background:rgba(46,189,133,.10);}
.peverdict.weakens{color:#f6465d;background:rgba(246,70,93,.10);}
.peverdict.mixed,.peverdict.neutral{color:#e0a33e;background:rgba(228,160,8,.10);}
.pe-list li{color:#d9d0bd;}
.pconfcols{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;}
.cchk{display:flex;align-items:flex-start;gap:7px;font-size:11px;color:#cdd3da;line-height:1.4;margin:3px 0;}
.cic{width:14px;height:14px;flex:0 0 auto;margin-top:1px;}
.cchk.ok{color:#cdd3da;}.cchk.ok .cic{color:#2ebd85;}
.cchk.warn{color:#aab2bd;}.cchk.warn .cic{color:#e0a33e;}
.cstr{font-size:8.5px;font-weight:800;letter-spacing:.05em;border-radius:5px;padding:2px 7px;}
.cstr.s-strong{background:rgba(46,189,133,.16);color:#2ebd85;border:1px solid rgba(46,189,133,.5);}
.cstr.s-mod{background:rgba(228,160,8,.15);color:#e0a33e;border:1px solid rgba(228,160,8,.45);}
.cstr.s-weak{background:rgba(246,70,93,.15);color:#f6465d;border:1px solid rgba(246,70,93,.45);}
.ptools{font-size:10px;color:#6e7681;margin-top:0;border-top:1px solid #1e242c;padding-top:9px;}
.ptlab{font-weight:700;color:#8b94a0;}
/* Phase 4.5 Opportunity Window — three-tier strip inside each pattern card */
.psecic.ic-opp{color:#e0a33e;border-color:rgba(228,160,8,.3);}
.oppwrap{display:flex;flex-direction:column;gap:1px;border:1px solid #232a33;border-radius:9px;overflow:hidden;background:#11161d;}
.opprow{display:flex;align-items:center;gap:10px;padding:7px 10px;background:#161b22;}
.opprow+.opprow{border-top:1px solid #1c222b;}
.opptier{flex:0 0 78px;font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#aab2bd;}
.oppmid{flex:1;min-width:0;}
.oppzone{font-size:11.5px;color:#e6e8eb;line-height:1.35;}
.oppreason{font-size:10px;color:#7d8794;line-height:1.35;margin-top:2px;}
.oppstat{flex:0 0 auto;font-size:9px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;border-radius:5px;padding:3px 8px;white-space:nowrap;align-self:flex-start;margin-top:1px;}
.oppstat.st-avail{background:rgba(46,189,133,.16);color:#2ebd85;border:1px solid rgba(46,189,133,.5);}
.oppstat.st-approach{background:rgba(228,160,8,.16);color:#e3a008;border:1px solid rgba(228,160,8,.5);}
.oppstat.st-trig{background:rgba(76,141,255,.16);color:#4c8dff;border:1px solid rgba(76,141,255,.5);}
.oppstat.st-missed{background:rgba(139,148,158,.13);color:#8b94a0;border:1px solid rgba(139,148,158,.4);}
.oppstat.st-unavail{background:rgba(139,148,158,.07);color:#5b636e;border:1px solid rgba(91,99,110,.3);}
.oppstat.st-invalid{background:rgba(246,70,93,.15);color:#f6465d;border:1px solid rgba(246,70,93,.45);}
.alertwrap{display:flex;flex-direction:column;gap:8px;}
.alertrow{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;padding:9px 10px;border:1px solid #232a33;border-radius:9px;background:#11161d;}
.alertbody{flex:1;min-width:0;}
.alerttop{display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:11px;font-weight:800;color:#e6e8eb;line-height:1.25;}
.alerttop em{font-style:normal;font-size:9px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#e0a33e;border:1px solid rgba(228,160,8,.38);border-radius:999px;padding:2px 7px;}
.alertcond{font-size:11.5px;color:#cdd3da;line-height:1.4;margin-top:4px;}
.alertnote{font-size:10px;color:#7d8794;line-height:1.35;margin-top:3px;}
.dash a.alertbtn{justify-self:end;display:inline-flex;align-items:center;justify-content:center;padding:5px 9px;border:1px solid rgba(76,141,255,.55);border-radius:999px;color:#9fc0ff;font-size:10px;font-weight:800;text-decoration:none;white-space:nowrap;background:rgba(76,141,255,.08);}
.dash a.alertbtn:hover{border-color:#4c8dff;color:#e6e8eb;background:rgba(76,141,255,.16);text-decoration:none;}
@media(max-width:700px){.alertrow{grid-template-columns:1fr;align-items:start;}.dash a.alertbtn{justify-self:start;}}
/* Decision-zone convergence callout — full width above the pattern cards */
.convg{display:flex;gap:13px;align-items:flex-start;margin:2px 0 14px;padding:12px 16px;border-radius:11px;
  background:linear-gradient(90deg,rgba(228,160,8,.10),rgba(228,160,8,.02));border:1px solid rgba(228,160,8,.34);}
.convgic{flex:0 0 auto;width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;
  color:#e3a008;border:1px solid rgba(228,160,8,.4);background:rgba(228,160,8,.08);}
.convgic .sic{width:16px;height:16px;}
.convghd{font-size:10px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:#e3a008;margin-bottom:3px;}
.convgtxt{font-size:12.5px;color:#d4dae1;line-height:1.5;}
.dash a.pcalc{display:flex;align-items:center;justify-content:center;gap:7px;width:fit-content;margin:12px auto 0;padding:6px 15px;border:1px solid rgba(230,232,235,.22);border-radius:9999px;color:#cdd3da;font-size:11.5px;font-weight:600;text-decoration:none;}
.dash a.pcalc:hover{border-color:#4c8dff;color:#4c8dff;background:transparent;text-decoration:none;}
.dash a.pcalc svg{width:15px;height:15px;display:block;}
/* legacy compact entry rows (fallback) */
.elabhd{font-size:9px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;margin-bottom:2px;}
.erow{display:flex;align-items:baseline;gap:10px;}
.elab{flex:0 0 78px;font-size:9px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;line-height:1.5;}
.elab.bull{color:#0ecb81;}.elab.bear{color:#f6465d;}.elab.blue{color:#4c8dff;}.elab.neu{color:#8b94a0;}
.eval{flex:1 1 auto;min-width:0;font-size:12.5px;font-weight:700;line-height:1.4;}
.eval.bull{color:#0ecb81;}.eval.bear{color:#f6465d;}.eval.blue{color:#4c8dff;}.eval.neu{color:#e6e8eb;}
.eval .enote{font-weight:400;color:#8b94a0;font-size:11px;}
.errbox{flex:0 0 auto;border:1px solid rgba(76,141,255,.45);border-radius:7px;padding:1px 8px;font-size:11px;font-weight:700;color:#9bbcff;white-space:nowrap;}
.errbox .errlab{color:#6b7686;margin-right:6px;}
.etools{font-size:10px;color:#6e7681;margin-top:3px;}
@media(max-width:760px){.drow2{grid-template-columns:1fr;}}
@media(max-width:980px){.drow3{grid-template-columns:1fr;}}
@media(max-width:1200px){.drow4{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:760px){.drow4{grid-template-columns:1fr;}}
@media(max-width:980px){
  .drow2,.drow3{grid-template-rows:auto!important;}
  .drow2 .pcard,.drow3 .pcard{display:flex;grid-row:auto;row-gap:11px;}
}

/* header — two decoupled grids so the bottom row (setup|trade|wcmm) can be
   even thirds while the top row keeps the price card wider than the meta strip */
.dhead-top{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px;align-items:stretch;}
.dhead-bottom{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:14px;
  grid-template-areas:"setup plan analyst" "wcmm verdict analyst";}
.g-setup{grid-area:setup;} .g-plan{grid-area:plan;} .g-analyst{grid-area:analyst;}
.g-wcmm{grid-area:wcmm;} .g-verdict{grid-area:verdict;}
.dhead-bottom>div{display:flex;}
.dhead-bottom>div>*{width:100%;}
@media(max-width:980px){.dhead-top{grid-template-columns:1fr;}
  .dhead-bottom{grid-template-columns:1fr;grid-template-areas:"setup" "wcmm" "plan" "verdict" "analyst";}}
.dhead-top .dcard,.dhead-bottom .dcard{margin-bottom:0;}
.hmain{position:relative;background:#13101e;border:1px solid #1e242c;border-radius:10px;display:flex;overflow:hidden;}
.setupbox{background:#13101e;border:1px solid #1e242c;border-radius:10px;padding:12px 14px;}
/* purple edge highlight on the main cards so they stand out on the gradient bg */
.dash .dcard,.dash .hmain,.dash .setupbox,.dash .mcell{border-color:rgba(139,92,246,.38);box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);}
.setup-grid{display:flex;flex-direction:column;gap:11px;margin-top:2px;}
.srow{display:flex;gap:12px;}
.slab{flex:0 0 86px;font-size:9.5px;letter-spacing:.05em;text-transform:uppercase;color:#8b94a0;line-height:1.4;}
.sval{flex:1;font-size:12px;color:#cdd3da;line-height:1.5;}
.sval.blue{color:#4c8dff;font-weight:700;}
.setupstack{display:flex;flex-direction:column;gap:12px;width:100%;}
.patrow{display:flex;flex-wrap:wrap;gap:6px;}
.patchip{display:inline-block;font-size:11px;font-weight:600;color:#dfe3e8;background:rgba(124,58,237,.14);border:1px solid rgba(139,92,246,.4);border-radius:6px;padding:2px 8px;}
.num{font-weight:600;}
.numgreen{color:#0ecb81;}
.numred{color:#f6465d;}
.hprice-col{flex:1;padding:12px 14px;display:flex;flex-direction:column;justify-content:center;}
.hbias-col{flex:1;padding:12px 14px;border-left:1px solid #1e242c;display:flex;flex-direction:column;justify-content:center;text-align:center;}
.bias-ico{transform:scaleX(-1);flex:0 0 auto;}
.bias-ico.neu-ico{transform:none;}
.hsym{font-size:16px;font-weight:800;letter-spacing:.02em;}
.hperp{font-size:10px;color:#8b94a0;border:1px solid #2a323c;border-radius:4px;padding:1px 5px;vertical-align:middle;margin-left:4px;}
.hprice{font-size:36px;font-weight:800;margin-top:4px;}
.hchg{font-size:15px;font-weight:700;}
.hhead{color:#8b94a0;font-size:12px;margin-top:2px;}
/* v3 header — layout only, reuses .hsym/.hperp/.hprice/.hhead/.amber type scale */
.v3banner{position:relative;padding:2px 2px 4px;}
.mobilelive{display:none;}
.v3striprow{display:flex;align-items:center;margin:8px 0 0;min-width:0;}
.v3strip{flex:1 1 auto;width:100%;min-width:0;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 12px;padding:10px 2px;border-top:1px solid #1e242c;border-bottom:1px solid #1e242c;}
.v3strip .livebadge{position:static;display:inline-flex;align-items:center;}
.v3bias{display:flex;align-items:flex-end;gap:10px;}
.v3bias.bull{color:#2ebd85;}.v3bias.bear{color:#f6465d;}.v3bias.neu{color:#e3a008;}
.v3biasv{font-size:17px;font-weight:700;margin-top:3px;line-height:1.1;color:inherit;}
.v3bias .bias-ico{width:44px;height:44px;flex:0 0 auto;display:block;position:relative;top:6px;}
.v3si{min-width:0;flex:0 1 auto;}
.v3sl{font-size:10px;color:#8b94a0;letter-spacing:.04em;white-space:nowrap;}
.v3sv{font-size:15px;font-weight:700;margin-top:3px;white-space:nowrap;}
.v3sv.bull{color:#26a69a;}.v3sv.bear{color:#f6465d;}.v3sv.neu{color:#e6e8eb;}
/* Top row: ticker block (Market Bias folded into its top-right) + Market Condition
   filling the rest of the row. */
.v3toprow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;align-items:start;}
@media(max-width:980px){.v3toprow{grid-template-columns:1fr;}}
.v3left{justify-self:stretch;min-width:0;width:100%;display:flex;flex-direction:column;}
.v3condside{grid-column:2 / 4;display:flex;min-width:0;}
@media(max-width:980px){.v3condside{grid-column:auto;}}
.v3condside .mc-cond{width:100%;margin-bottom:0;}
/* Market Condition split: State+Volatility share the card-2 width, Intermarket
   takes the card-3 width. */
.mc-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
@media(max-width:980px){.mc-grid{grid-template-columns:1fr;}}
.mc-sv{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
.mc-im{padding-left:14px;}
@media(max-width:700px){
  .mc-sv{grid-template-columns:1fr;gap:18px;}
  .mc-im{padding-left:0;}
  .v3left{position:relative;}
  .v3banner{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-rows:auto auto;
    column-gap:14px;row-gap:5px;padding:0 12px 4px 14px;margin:-7px 0 0;align-items:start;}
  .v3banner .hperp{display:none;}
  .v3banner .hsym{grid-column:1;grid-row:1;font-size:18px;line-height:1.15;max-width:220px;
    display:flex;align-items:center;gap:8px;}
  .mobilelive{display:inline-flex;align-items:center;line-height:0;}
  .mobilelive .livebadge{position:static;display:inline-flex;animation:livepulse 1.6s ease-in-out infinite;}
  .mobilelive .livebadge-svg{width:26px;height:26px;}
  .v3banner .hprice{grid-column:1;grid-row:2;display:flex;align-items:baseline;justify-content:flex-start;
    gap:8px;margin-top:0;padding-right:0;font-size:30px;line-height:1.05;width:100%;}
  .v3banner .hchg{font-size:15px;line-height:1.25;margin-left:0;text-align:left;padding-top:0;min-width:0;}
  .v3striprow{display:none;}
  .v3biasinline{position:static!important;grid-column:2!important;grid-row:1 / 3!important;
    justify-self:end!important;align-self:stretch!important;margin-right:8px!important;}
  .v3biasv2{height:100%!important;flex-direction:column!important;align-items:center!important;
    justify-content:space-between!important;gap:2px!important;}
  .v3biasword{font-size:18px!important;line-height:1.05!important;}
  .v3biasicon{margin-top:0!important;line-height:0!important;}
  .v3biasinline .bias-ico{width:48px!important;height:48px!important;}
  .v3condside{margin-top:-2px;}
}
.v3banntop{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;}
.v3biasinline{position:absolute;top:5px;right:2px;}
.v3biasinline.bull{color:#2ebd85;}.v3biasinline.bear{color:#f6465d;}.v3biasinline.neu{color:#e3a008;}
.v3biasv2{display:flex;flex-direction:column;align-items:center;color:inherit;}
.v3biasword{font-size:18px;font-weight:700;line-height:1.1;}
.v3biasicon{margin-top:22px;line-height:0;}
.v3biasinline .bias-ico{width:34px;height:34px;flex:0 0 auto;}
.v3biasnote{margin-top:9px;color:#c2c9d2;font-size:12.5px;line-height:1.45;max-width:380px;}
.mc-bias .biaswrap{flex:1;display:flex;flex-direction:column;justify-content:center;}
.v3right{display:flex;flex-direction:column;gap:14px;}
.v3right .dcard{margin-bottom:0;}
.v3right .mc-cond{flex:1;}
.v3condside .mc-desktop{width:100%;}
.v3condside .mc-collapse{width:100%;}
.mc-collapse{display:none;}
.mc-collapse>summary{display:none;}
.mc-bias .biasrow{display:flex;align-items:center;gap:12px;}
.mc-bias .biasrow.bull{color:#2ebd85;}.mc-bias .biasrow.bear{color:#f6465d;}.mc-bias .biasrow.neu{color:#e3a008;}
.mc-bias .biasval{font-size:22px;font-weight:800;line-height:1;color:inherit;}
.mc-bias .biasrow .bias-ico{width:38px;height:38px;flex:0 0 auto;}
.mc-bias .biasnote{margin-top:7px;color:#c2c9d2;font-size:12.5px;line-height:1.4;}
/* Market Condition 3-node stepper: icon node + connector line per segment,
   then label, status chip, evidence line. Dot/line/icon take the segment tone
   via currentColor. */
.mc-cond .mcsteps{display:flex;}
.mc-cond .mcseg{display:flex;flex-direction:column;min-width:0;}
.mc-cond .mcseg.mclast{padding-right:0;}
.mc-cond .mcsegrail{display:flex;align-items:center;height:34px;margin-bottom:-6px;}
.mc-cond .mcdot{width:32px;height:32px;border-radius:50%;border:1.5px solid currentColor;display:flex;align-items:center;justify-content:center;flex:0 0 auto;background:rgba(255,255,255,.025);}
.mc-cond .mcic{display:block;}
.mc-cond .mcbtc{font-size:17px;font-weight:800;line-height:1;color:currentColor;}
.mc-cond .mcline{flex:1;height:2px;margin-left:0;border-radius:2px;background:linear-gradient(90deg,currentColor,rgba(255,255,255,.06));opacity:.55;}
.mc-cond .mcseglabel{font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#8b94a0;margin-bottom:9px;}
.mc-cond .mcchiprow{display:flex;align-items:center;gap:9px;margin-bottom:11px;min-height:26px;}
.mc-cond .mcseg .vchip{align-self:center;font-size:13px;padding:4px 12px;}
/* Market State / Volatility chips use the quiet white-outline pill UX (like the
   maturity/entry-mode pills); colour stays reserved for the Intermarket read. */
.mc-cond .mc-sv .vchip{background:transparent;color:#f0f2f5;border:1px solid rgba(255,255,255,.6);font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border-radius:6px;padding:3px 9px;}
.mc-cond .mccor{font-size:11px;font-weight:700;letter-spacing:.02em;color:#aab2bd;border:1px solid #2a2f3a;border-radius:6px;padding:3px 8px;white-space:nowrap;}
.mc-cond .mcsegtext{font-size:12px;line-height:1.5;color:#c2c9d2;}
.mc-cond .tone-up{color:#2ebd85;}
.mc-cond .tone-dn{color:#f6465d;}
.mc-cond .tone-amber{color:#e3a008;}
.mc-cond .tone-comp{color:#4493f8;}
.mc-cond .tone-exp{color:#e3a008;}
.mc-cond .tone-neu{color:#aab2bd;}
.mc-cond .tone-cor-on{color:#f6465d;}
.mc-cond .tone-cor-mod{color:#e0b400;}
.mc-cond .tone-cor-partial{color:#f5821f;}
.mc-cond .tone-cor-neutral{color:#aab2bd;}
.mc-cond .tone-cor-off{color:#4493f8;}
.mc-cond .tone-cor-inverse{color:#a855f7;}
@media(max-width:1100px){.mc-cond .mcsteps{flex-direction:column;gap:18px;}.mc-cond .mcseg{padding-right:0;}.mc-cond .mcline{display:none;}}
@media(max-width:700px){
  .mc-desktop{display:none!important;}
  .mc-collapse{position:relative;display:block;}
  .mc-collapse>summary{position:absolute;top:12px;right:12px;z-index:3;display:flex;align-items:center;justify-content:flex-end;
    min-height:16px;list-style:none;color:#8b94a0;cursor:pointer;}
  .mc-collapse>summary::-webkit-details-marker{display:none;}
  .mc-collapse>summary .down-arrow-svg{width:13px;height:13px;display:block;}
  .mc-collapse>summary .mc-summary-label{display:none;}
  .mc-collapse[open]>summary .down-arrow-svg{transform:rotate(180deg);}
  .mc-collapse:not([open]){border:1px solid rgba(139,92,246,.38);border-radius:10px;background:#13101e;
    min-height:42px;margin-bottom:12px;box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);}
  .mc-collapse:not([open]) .mc-cond{display:none!important;}
  .mc-collapse:not([open])>summary{position:static;min-height:40px;padding:12px 14px;justify-content:space-between;}
  .mc-collapse:not([open])>summary .mc-summary-label{display:block;font-size:10.5px;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:#8b94a0;line-height:1;}
  .mt-detail .psec-desktop-copy{display:none!important;}
  .mt-detail .psec-mobile-collapse{display:block;margin:0 0 12px 0;}
  .mt-detail .psec-mobile-collapse>summary{min-height:24px;padding:0;display:flex;align-items:center;
    justify-content:space-between;list-style:none;color:#8b94a0;cursor:pointer;}
  .mt-detail .psec-mobile-collapse>summary::-webkit-details-marker{display:none;}
  .mt-detail .psec-mobile-collapse>summary .mc-summary-label{display:block;font-size:10.5px;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:#8b94a0;line-height:1;}
  .mt-detail .psec-mobile-collapse>summary .down-arrow-svg{width:13px;height:13px;display:block;}
  .mt-detail .psec-mobile-collapse[open]>summary .down-arrow-svg{transform:rotate(180deg);}
  .mt-detail .psec-mobile-collapse:not([open]) .psec{display:none!important;}
  .mt-detail .psec-mobile-collapse[open] .psec{margin:0!important;border:0!important;background:transparent!important;box-shadow:none!important;}
  .mt-detail .psec-mobile-collapse[open] .psecic,
  .mt-detail .psec-mobile-collapse[open] .psechd{display:none!important;}
  .mt-detail .psec-mobile-collapse[open] .psecbody{width:100%!important;}
}
.mcnote{font-size:13px;color:#ffffff;margin-top:14px;line-height:1.5;}
.mcchips{display:flex;gap:20px;}
.mclab{font-size:11px;color:#8b94a0;letter-spacing:.07em;margin-bottom:6px;}
.vchip{display:inline-block;padding:5px 14px;border-radius:20px;font-size:15px;font-weight:700;letter-spacing:.02em;}
.vchip.chip-amber{background:rgba(228,160,8,.15);color:#e3a008;border:1px solid rgba(228,160,8,.4);}
.vchip.chip-up{background:rgba(46,189,133,.15);color:#26a69a;border:1px solid rgba(46,189,133,.4);}
.vchip.chip-dn{background:rgba(246,70,93,.15);color:#f6465d;border:1px solid rgba(246,70,93,.4);}
.vchip.chip-comp{background:rgba(68,147,248,.15);color:#4493f8;border:1px solid rgba(68,147,248,.4);}
.vchip.chip-exp{background:rgba(228,160,8,.15);color:#e3a008;border:1px solid rgba(228,160,8,.4);}
.vchip.chip-neu{background:rgba(139,148,158,.15);color:#8b94a0;border:1px solid rgba(139,148,158,.35);}
/* Intermarket correlation bands (COR → label) — see trade_setup_framework.md */
.vchip.chip-cor-on{background:rgba(246,70,93,.15);color:#f6465d;border:1px solid rgba(246,70,93,.4);}
.vchip.chip-cor-mod{background:rgba(224,180,0,.15);color:#e0b400;border:1px solid rgba(224,180,0,.4);}
.vchip.chip-cor-partial{background:rgba(245,130,31,.15);color:#f5821f;border:1px solid rgba(245,130,31,.4);}
.vchip.chip-cor-neutral{background:rgba(170,178,189,.15);color:#aab2bd;border:1px solid rgba(170,178,189,.35);}
.vchip.chip-cor-off{background:rgba(68,147,248,.15);color:#4493f8;border:1px solid rgba(68,147,248,.4);}
.vchip.chip-cor-inverse{background:rgba(168,85,247,.15);color:#a855f7;border:1px solid rgba(168,85,247,.4);}
.hmeta-rt{display:flex;flex-direction:column;gap:8px;}
.hmeta-rt-row{display:flex;gap:10px;}
.hmeta-note{font-size:12px;line-height:1.5;color:#cdd3da;background:#13101e;border:1px solid #1e242c;border-radius:8px;padding:7px 10px;}
.mcell{flex:1;background:#13101e;border:1px solid #1e242c;border-radius:10px;padding:10px 12px;display:flex;flex-direction:column;justify-content:flex-start;}
.ml{font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;color:#8b94a0;}
.mv{font-size:13px;font-weight:700;margin-top:6px;text-align:center;text-transform:uppercase;}
.mcell-snap{position:relative;flex:2;justify-content:flex-start;gap:0;}
/* flashing LIVE badge, top-right of the live (2s-refreshed) header boxes */
.livebadge{position:absolute;top:8px;right:10px;line-height:0;z-index:3;pointer-events:none;animation:livepulse 1.6s ease-in-out infinite;}
/* inline LIVE badge (beside the symbol) — used on the Position Calculator */
.hsym:has(.livebadge){display:inline-flex;align-items:center;gap:7px;}
.hsym .livebadge{position:static;display:inline-flex;align-items:center;margin-left:2px;top:auto;right:auto;}
.livebadge-svg{display:block;}
@keyframes livepulse{0%,100%{opacity:1;}50%{opacity:.35;}}
/* flex header: title left, LIVE badge right, in normal flow (no overlap, responsive) */
.cardhead{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:9px;}
.cardhead .dtitle{margin-bottom:0;}
.cardhead .livebadge{position:static;flex:0 0 auto;}
.mcell-snap .dtitle{margin-bottom:4px;}
.msrow{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:3px 0;border-bottom:1px solid #161b21;}
.msrow:last-child{border-bottom:none;}
.msl{color:#8b94a0;font-size:9px;letter-spacing:.03em;text-transform:uppercase;white-space:nowrap;}
.msv{color:#dfe3e8;font-size:11px;font-weight:700;white-space:nowrap;}
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
.gaugewrap{display:flex;flex-direction:column;align-items:center;margin-bottom:10px;}
.gauge{width:180px;height:auto;display:block;}
.gscore{margin-top:2px;display:flex;align-items:baseline;gap:7px;}
.gslab{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:#8b94a0;font-weight:700;}
.gsnum{font-size:24px;font-weight:800;line-height:1;}
.gsnum.bear{color:#f6465d;} .gsnum.bull{color:#0ecb81;} .gsnum.neu{color:#e0a33e;}
.gsout{font-size:13px;color:#8b94a0;font-weight:700;}
.gtally{display:flex;gap:22px;margin-top:9px;}
.gt{text-align:center;}
.gtl{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:#8b94a0;}
.gtv{font-size:18px;font-weight:800;margin-top:1px;}
.gtv.bull{color:#0ecb81;} .gtv.neu{color:#e0a33e;} .gtv.bear{color:#f6465d;}
.donutwrap{display:flex;flex-direction:column;align-items:center;margin-bottom:10px;}
.donut{width:120px;height:120px;border-radius:50%;display:flex;align-items:center;justify-content:center;}
.donuthole{width:84px;height:84px;border-radius:50%;background:#13101e;display:flex;flex-direction:column;align-items:center;justify-content:center;}
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
.tphead{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;}
.tphead .dtitle{margin-bottom:0;}
.tpdir{display:inline-block;background:rgba(76,141,255,.12);color:#4c8dff;border:1px solid rgba(76,141,255,.4);border-radius:5px;padding:2px 8px;font-size:10px;font-weight:700;}
.tprow{display:flex;gap:10px;align-items:baseline;padding:4px 0;}
.tplab{flex:0 0 74px;color:#8b94a0;font-size:9.5px;letter-spacing:.04em;text-transform:uppercase;line-height:1.3;}
.tplab.bull{color:#0ecb81;} .tplab.bear{color:#f6465d;} .tplab.blue{color:#4c8dff;}
.tpval{flex:1;font-size:12px;font-weight:700;color:#dfe3e8;line-height:1.35;}
.tpval.bull{color:#0ecb81;} .tpval.bear{color:#f6465d;} .tpval.blue{color:#4c8dff;}
.tpnote{color:#cdd3da;font-weight:500;font-size:12px;}
.rrbox{flex:0 0 86px;background:#11151b;border:1px solid #4c8dff;border-radius:5px;padding:2px 7px;font-size:10px;font-weight:800;color:#4c8dff;white-space:nowrap;display:flex;justify-content:space-between;align-items:center;gap:6px;}
.rrlab{color:#8b94a0;font-weight:700;}
/* verdict badge — the take/skip call under the trade plan. Coloured by action:
   ENTER green, WAIT amber, AVOID red. Border-left accent + tinted background. */
.vbadge{margin-top:2px;padding:2px 0 2px 12px;border-left:3px solid #232a33;}
.vbhead{display:flex;align-items:center;gap:8px;}
.vblab{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#8b94a0;}
.vbaction{font-size:15px;font-weight:800;letter-spacing:.04em;}
.vbtext{margin-top:5px;font-size:12px;line-height:1.5;color:#cdd3da;}
.vbadge.venter{border-left-color:#0ecb81;}
.vbadge.venter .vbaction{color:#0ecb81;}
.vbadge.vwait{border-left-color:#e0a33e;}
.vbadge.vwait .vbaction{color:#e0a33e;}
.vbadge.vavoid{border-left-color:#f6465d;}
.vbadge.vavoid .vbaction{color:#f6465d;}
/* matches the Market Scanner pill buttons (app.py div[data-testid=stButton] > button).
   .dash a.pushbtn specificity (0,2,1) beats Streamlit's default anchor-colour rule. */
.dash a.pushbtn{display:block;width:fit-content;margin:14px auto 0;padding:0.25rem 0.85rem;
  border-radius:9999px;border:1px solid rgba(230,232,235,.2);background:transparent;color:#e6e8eb;
  font-family:"Source Sans",sans-serif;font-size:1rem;font-weight:500;line-height:1.6;
  text-decoration:none;white-space:nowrap;}
.dash a.pushbtn:hover{border-color:#4c8dff;color:#4c8dff;background:transparent;text-decoration:none;}

/* levels */
.lvgrid{display:flex;gap:14px;}
.lvcol{flex:1;}
.lvhead{font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;margin-bottom:5px;}
.lvrow{display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px solid #161b21;}
.lvp{font-weight:700;} .lvl{color:#8b94a0;font-size:10px;text-align:right;}

/* what changes my mind */
.setup-wcmm{margin-top:13px;border-top:1px solid #232a33;padding-top:11px;}
.setup-wcmm .dtitle{margin-bottom:9px;}
.wgrid{display:flex;gap:10px;}
.wcol{flex:1;border:1px solid #232a33;border-radius:8px;padding:9px;}
.wtit{font-weight:800;font-size:12px;}
.wcol.bull .wtit{color:#0ecb81;} .wcol.bear .wtit{color:#f6465d;}
.wsub{font-size:9.5px;color:#8b94a0;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px;}
.wchecks{margin:0;padding-left:15px;color:#cdd3da;}
.wchecks li{margin-bottom:4px;font-size:12px;line-height:1.45;}
.wres{margin-top:8px;font-size:10.5px;color:#aab2bd;border-top:1px solid #232a33;padding-top:6px;}
.wcases{margin-top:10px;border-top:1px solid #1e242c;padding-top:9px;display:flex;flex-direction:row;flex-wrap:wrap;gap:12px;}
.wcase{flex:1;min-width:150px;font-size:12px;line-height:1.5;color:#cdd3da;}
.wcase b{color:#dfe3e8;}
.wflag{margin-right:6px;font-weight:800;}
.wcase-bull .wflag{color:#0ecb81;} .wcase-bear .wflag{color:#f6465d;}

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
.sumlist{margin:0;padding-left:16px;color:#cdd3da;line-height:1.5;}
.sumlist li{margin-bottom:6px;font-size:12px;}
.botline{margin-top:9px;border-top:1px solid #232a33;padding-top:8px;font-size:11px;color:#aab2bd;}
/* analyst-summary headline (the former bottom line, now leading under the gauge) —
   body font size, slightly brighter/heavier so it reads as the lead */
.aheadline{font-size:12px;line-height:1.5;color:#dfe3e8;font-weight:600;margin:2px 0 12px;}
.botline b{color:#dfe3e8;}
.failtext{font-size:11.5px;color:#f0b9c1;line-height:1.5;}
/* derivatives — compact executive summary boxed like the other cards */
.hmeta-deriv{background:#13101e;border:1px solid rgba(139,92,246,.38);border-radius:10px;padding:10px 12px;box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);}
.hmeta-deriv .dtitle{margin-bottom:8px;}
/* Option B: signal+note one line each, horizontal divider, synthesis below */
.dvexec{display:flex;flex-direction:column;gap:5px;}
.dvrow{display:flex;align-items:center;gap:5px;font-size:10px;line-height:1.45;white-space:nowrap;}
.dvdot{flex:0 0 auto;width:7px;height:7px;border-radius:50%;background:#8b94a0;}
.dvrow.bull .dvdot{background:#0ecb81;} .dvrow.bear .dvdot{background:#f6465d;} .dvrow.neu .dvdot{background:#e0a33e;}
.dvmetric{font-weight:700;text-transform:uppercase;font-size:9px;letter-spacing:.03em;color:#8b94a0;}
.dvsignal{font-weight:700;color:#dfe3e8;}
.dvrow.bull .dvmetric,.dvrow.bull .dvsignal{color:#0ecb81;} .dvrow.bear .dvmetric,.dvrow.bear .dvsignal{color:#f6465d;} .dvrow.neu .dvmetric,.dvrow.neu .dvsignal{color:#e0a33e;}
.dvnote{color:#9aa3ae;}
.dvsplit{display:flex;flex-direction:column;}
.dvsummary{border-top:1px solid #2a2f37;margin-top:8px;padding-top:8px;font-size:11.5px;line-height:1.5;color:#dfe3e8;font-weight:500;}
.mobile-trades{display:none;}
@media(max-width:700px){
  .desktop-patterns{display:none!important;}
  .mobile-trades{display:block;margin:6px 0 12px;}
  .mt-head{display:none;}
  .mt-head h3{margin:0;color:#f2f4f8;font-size:20px;line-height:1.15;font-weight:820;letter-spacing:0;}
  .mt-head span{color:#a855f7;font-size:14px;font-weight:780;}
  .mt-setup{border:1px solid rgba(139,92,246,.38);border-radius:14px;background:rgba(10,18,28,.58);
    margin:0 0 12px;overflow:hidden;box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15),inset 0 1px 0 rgba(255,255,255,.035);}
  .mt-setup.long[open]{border-color:rgba(14,203,129,.58);box-shadow:0 0 0 1px rgba(14,203,129,.10),0 0 24px rgba(14,203,129,.18),inset 0 1px 0 rgba(255,255,255,.035);}
  .mt-setup.short[open]{border-color:rgba(246,70,93,.58);box-shadow:0 0 0 1px rgba(246,70,93,.10),0 0 24px rgba(246,70,93,.18),inset 0 1px 0 rgba(255,255,255,.035);}
  .mt-setup summary{list-style:none;display:grid;grid-template-columns:54px minmax(0,1fr);gap:10px;
    align-items:center;padding:10px 11px;cursor:pointer;min-height:78px;}
  .mt-setup summary::-webkit-details-marker{display:none;}
  .mt-sketch{width:54px;height:44px;stroke:#eef1f5;stroke-width:2.25;stroke-linecap:round;stroke-linejoin:round;
    filter:drop-shadow(0 2px 2px rgba(0,0,0,.55));}
  .mt-sketch .dash{stroke:#9aa3ae;stroke-width:1.5;stroke-dasharray:7 7;}
  .mt-main{min-width:0;display:flex;flex-direction:column;gap:7px;overflow:hidden;}
  .mt-titleline{display:grid;grid-template-columns:minmax(0,auto) auto 1fr auto;align-items:center;gap:8px;min-width:0;}
  .mt-name{min-width:0;color:#e6e8eb;font-size:14.5px;font-weight:620;line-height:1.18;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .mt-dir{flex:0 0 auto;border:1px solid currentColor;border-radius:5px;padding:2px 6px;font-size:10.5px;
    line-height:1.1;font-weight:760;letter-spacing:.02em;color:#0ecb81;background:rgba(14,203,129,.045);}
  .mt-setup.short .mt-dir{color:#f6465d;background:rgba(246,70,93,.06);}
  .mt-facts{display:grid;grid-template-columns:62px minmax(0,1fr) 26px;gap:9px;min-width:0;align-items:end;}
  .mt-fact{min-width:0;border-left:1px solid rgba(139,148,158,.20);padding-left:8px;}
  .mt-fact:first-child{border-left:0;padding-left:0;}
  .mt-fact em{display:block;font-style:normal;color:#8b94a0;font-size:9.5px;font-weight:680;line-height:1.15;text-transform:uppercase;letter-spacing:.04em;}
  .mt-fact strong{display:block;color:#dfe3e8;font-size:12.5px;font-weight:650;line-height:1.18;margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .mt-setup.long .mt-entry strong{color:#0ecb81;}
  .mt-setup.short .mt-entry strong{color:#f6465d;}
  .mt-grade{justify-self:end;display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:18px;
    border:1px solid rgba(255,255,255,.72);border-radius:5px;color:#f2f4f8;background:transparent;
    font-size:10px;font-weight:760;line-height:1;}
  .mt-grade-empty{visibility:hidden;}
  .mt-side{display:flex;align-items:flex-end;justify-content:flex-end;height:100%;min-height:32px;}
  .mt-caret{width:14px;height:14px;color:#cdd3da;display:flex;align-items:center;justify-content:center;align-self:flex-end;
    justify-self:end;margin-bottom:0;transition:transform .18s ease;opacity:.9;}
  .mt-caret .down-arrow-svg{width:14px;height:14px;display:block;}
  .mt-setup[open] .mt-caret{transform:rotate(180deg);}
  .mt-detail{border-top:1px solid rgba(139,148,158,.18);padding:12px;background:rgba(7,12,19,.36);}
  .mt-detail .psummary{margin-bottom:12px;}
  .mt-detail .pentry{margin-top:0;}
  .mt-detail .psec{padding:10px 0;border-top:1px solid rgba(139,148,158,.14);}
  .mt-detail .psec:first-child{border-top:0;}
}
"""


# Hexagon-with-candlesticks glyph shown top-left of every pattern card.
_PATTERN_GLYPH = (
    '<svg viewBox="0 0 48 48" width="46" height="46" fill="none" class="phex">'
    '<polygon points="12,2 36,2 46,24 36,46 12,46 2,24" '
    'fill="rgba(139,92,246,0.12)" stroke="#8b5cf6" stroke-width="2.4" stroke-linejoin="round"/>'
    '<line x1="17" y1="16" x2="17" y2="34" stroke="#a78bfa" stroke-width="1.6"/>'
    '<rect x="14.6" y="21" width="4.8" height="9" rx="1" fill="#a78bfa"/>'
    '<line x1="24" y1="12" x2="24" y2="33" stroke="#c4b5fd" stroke-width="1.6"/>'
    '<rect x="21.6" y="16" width="4.8" height="12" rx="1" fill="#c4b5fd"/>'
    '<line x1="31" y1="17" x2="31" y2="36" stroke="#a78bfa" stroke-width="1.6"/>'
    '<rect x="28.6" y="23" width="4.8" height="9" rx="1" fill="#a78bfa"/>'
    "</svg>"
)


def _grade_cls(g):
    return {"A": "a", "B": "b", "C": "c"}.get((g or "").strip().upper()[:1], "c")


def _mode_cls(m):
    m = (m or "").strip().lower()
    if m.startswith("aggress"):
        return "aggressive"
    if m.startswith("chas"):
        return "chasing"
    return "balanced"


def _mode_label(m):
    m = (m or "").strip()
    return m.split()[0].capitalize() if m else ""


def _maturity_cls(m):
    """Canonical stage key for sorting (Nascent/Forming map onto the legacy
    emerging/developing ranks)."""
    m = (m or "").strip().lower()
    if m.startswith("triggered"):
        return "triggered"
    if m.startswith(("ready", "near completion", "near-completion")):
        return "ready"
    if m.startswith("mature"):
        return "mature"
    if m.startswith(("forming", "developing", "almost developed")):
        return "developing"
    if m.startswith(("nascent", "emerging")):
        return "emerging"
    return "developing"


def _maturity_label(m):
    """Display stage word for the pill — vocabulary: Nascent · Forming · Mature ·
    Ready · Triggered. Legacy stage words map across (Emerging -> Nascent,
    Developing -> Forming) so older analyses still render correctly."""
    m = (m or "").strip()
    if not m:
        return ""
    low = m.lower()
    for prefix, label in (
        ("triggered", "Triggered"),
        ("ready", "Ready"),
        ("near completion", "Ready"),
        ("near-completion", "Ready"),
        ("mature", "Mature"),
        ("forming", "Forming"),
        ("developing", "Forming"),
        ("almost developed", "Forming"),
        ("nascent", "Nascent"),
        ("emerging", "Nascent"),
    ):
        if low.startswith(prefix):
            return label
    # Custom (non-standard) label: keep the full phrase, just trim trailing notes.
    return m.split("—")[0].split("(")[0].strip()


# Colour price/number tokens in pattern prose so they stand out, tinted by the
# sentiment of their clause. Matches $-amounts, %-values and decimals (skips bare
# integers like "20-EMA", "4H", "RSI 71" so indicator labels stay plain).
_NUM_RE = re.compile(r'(\$\d[\d,]*(?:\.\d+)?|\d[\d,]*\.\d+|\d[\d,]*%)')
_POS_CUES = (
    "reclaim", "broke above", "break above", "broke out", "breakout", "held",
    "holding", "hold above", "bounce", "confirm", "building", "built", "rising",
    "room to run", "higher low", "higher high", "demand", "support reclaim",
)
_NEG_CUES = (
    "retrac", "below", "lost", "losing", "loss", "invalidat", "reject", "failed",
    "fail", "breakdown", "give-back", "give back", "flush", "overbought", "extended",
    "crash", "fell", "knife", "negat", "drop", "weak", "unproven",
)


def _clause_tone(clause):
    c = clause.lower()
    neg = any(k in c for k in _NEG_CUES)
    pos = any(k in c for k in _POS_CUES)
    if neg and not pos:
        return "numneg"
    if pos and not neg:
        return "numpos"
    return "numneu"


def _hl_numbers(text):
    """Escape text, then wrap number tokens in a tone span per their clause."""
    if not text:
        return ""
    esc = _e(text)
    parts = re.split(r'(\s—\s|\s–\s|,\s|;\s|\sbut\s|\swhile\s)', esc)
    out = []
    for part in parts:
        if re.fullmatch(r'\s—\s|\s–\s|,\s|;\s|\sbut\s|\swhile\s', part):
            out.append(part)
            continue
        tone = _clause_tone(part)
        out.append(_NUM_RE.sub(lambda m: f'<span class="{tone}">{m.group(1)}</span>', part))
    return "".join(out)


# --- small inline icons (stroke = currentColor) ---
_IC_SHIELD = '<svg viewBox="0 0 24 24" class="tic" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6z"/></svg>'
_IC_CALC = '<svg viewBox="0 0 24 24" class="tic" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="3" width="14" height="18" rx="2"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8.5" y1="12" x2="8.5" y2="12"/><line x1="12" y1="12" x2="12" y2="12"/><line x1="15.5" y1="12" x2="15.5" y2="16"/></svg>'
_IC_TGT = '<svg viewBox="0 0 24 24" class="tic" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg>'
_IC_EV = '<svg viewBox="0 0 24 24" class="sic" fill="none" stroke="currentColor" stroke-width="2"><line x1="6" y1="20" x2="6" y2="13"/><line x1="12" y1="20" x2="12" y2="8"/><line x1="18" y1="20" x2="18" y2="11"/></svg>'
_IC_NOTE = '<svg viewBox="0 0 24 24" class="sic" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 3h9l4 4v14H6z"/><line x1="9" y1="10" x2="15" y2="10"/><line x1="9" y1="14" x2="15" y2="14"/></svg>'
_IC_CONF = '<svg viewBox="0 0 24 24" class="sic" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>'
_IC_CHECK = '<svg viewBox="0 0 24 24" class="cic" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 13l4 4L19 7"/></svg>'
_IC_WARN = '<svg viewBox="0 0 24 24" class="cic" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4l9 16H3z"/><line x1="12" y1="10" x2="12" y2="14.5"/><line x1="12" y1="17.5" x2="12" y2="17.5"/></svg>'
_IC_OPP = '<svg viewBox="0 0 24 24" class="sic" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.6" fill="currentColor"/></svg>'

# Phase 4.5 Opportunity Assessment, rendered as a compact three-tier strip
# (Aggressive / Balanced / Confirmation) inside each pattern card so the "when
# is the opportunity live" read sits with the trade setup itself.
_OPP_STAT = {
    "available":   "st-avail",
    "approaching": "st-approach",
    "triggered":   "st-trig",
    "missed":      "st-missed",
    "unavailable": "st-unavail",
    "invalid":     "st-invalid",
}


def _opportunity(opp):
    """opp = [{type, zone, status, reason}] -> three-tier opportunity strip."""
    if not opp:
        return ""
    rows = ""
    for o in opp:
        st_raw = (o.get("status") or "").strip().lower()
        scls = _OPP_STAT.get(st_raw, "st-unavail")
        reason = f'<div class="oppreason">{_hl_numbers(o.get("reason"))}</div>' if o.get("reason") else ""
        rows += (
            '<div class="opprow">'
            f'<div class="opptier">{_e(o.get("type"))}</div>'
            '<div class="oppmid">'
            f'<div class="oppzone">{_hl_numbers(o.get("zone") or "—")}</div>'
            f'{reason}'
            '</div>'
            f'<span class="oppstat {scls}">{_e(o.get("status"))}</span>'
            '</div>'
        )
    return f'<div class="oppwrap">{rows}</div>'


def _load_calc_icon(size=29):
    """Inline assets/calculator.svg, recoloured to currentColor. Preserves the
    file's own viewBox and sets fill on the root so unstyled paths inherit colour."""
    path = os.path.join(os.path.dirname(__file__), "assets", "calculator.svg")
    try:
        with open(path) as f:
            svg = f.read().strip()
    except OSError:
        return _IC_CALC
    m = re.search(r'viewBox="([^"]+)"', svg)
    vb = m.group(1) if m else "0 0 512 512"
    svg = re.sub(
        r"<svg[^>]*?>",
        f'<svg width="{size}" height="{size}" viewBox="{vb}" fill="currentColor" '
        'xmlns="http://www.w3.org/2000/svg">',
        svg, count=1,
    )
    return svg.replace('fill="#000000"', 'fill="currentColor"')


_CALC_SVG = _load_calc_icon()


def _num(v):
    try:
        return float(re.sub(r"[^0-9.]", "", str(v)))
    except (TypeError, ValueError):
        return None


def _money(x):
    return f"${x:,.2f}" if isinstance(x, (int, float)) else ""


def _g(x):
    """Compact number for track labels — thousands-separated for big values."""
    if not isinstance(x, (int, float)):
        return ""
    return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:g}"


def _align_ring(score):
    try:
        s = max(0, min(100, int(round(float(score)))))
    except (TypeError, ValueError):
        return ""
    R = 26.0
    C = 2 * math.pi * R
    col = "#2ebd85" if s >= 75 else "#e0a33e" if s >= 50 else "#f6465d"
    off = C * (1 - s / 100)
    return (
        '<div class="aring">'
        '<svg viewBox="0 0 64 64">'
        '<circle cx="32" cy="32" r="26" fill="none" stroke="#222a35" stroke-width="4.5"/>'
        f'<circle cx="32" cy="32" r="26" fill="none" stroke="{col}" stroke-width="4.5" '
        f'stroke-linecap="round" stroke-dasharray="{C:.1f}" stroke-dashoffset="{off:.1f}" '
        'transform="rotate(-90 32 32)"/></svg>'
        f'<div class="arnum">{s}<span class="arden">/100</span></div>'
        '<div class="arlab">Setup Alignment</div>'
        "</div>"
    )


def _level_track(stop, elow, ehigh, t1, t2, current=None, risk_label=""):
    """Spatial level map: a plain line with dots placed at their true relative
    prices — red = stop, blue = TP1/TP2, green rectangle (or dot) = entry zone —
    plus a current-price caret. No colouring of the line itself."""
    core = [p for p in (stop, elow, ehigh, t1, t2) if p is not None]
    if len(core) < 2:
        return ""
    pts = core + ([current] if current is not None else [])
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    pad = 11.0

    def pct(p):
        return pad + (p - lo) / span * (100 - 2 * pad)

    boxed = elow is not None and ehigh is not None and ehigh > elow
    emid = (elow + ehigh) / 2 if boxed else (elow if elow is not None else ehigh)
    eblo = pct(min(elow, ehigh)) if boxed else pct(emid)
    ebhi = pct(max(elow, ehigh)) if boxed else pct(emid)

    out = '<div class="ltrack"><div class="ltline"></div>'

    if boxed:
        out += f'<div class="lzbox" style="left:{eblo:.1f}%;width:{max(ebhi - eblo, 1):.1f}%;"></div>'

    def mark(p, cls, price, label, dot=True):
        return (
            f'<div class="lmark" style="left:{pct(p):.1f}%;">'
            f'<div class="lmtop {cls}">{price}</div>'
            + (f'<div class="lmdot {cls}"></div>' if dot else "")
            + f'<div class="lmbot {cls}">{label}</div></div>'
        )

    if stop is not None:
        out += mark(stop, "c-bear", f"${stop:.2f}", "")
    if elow is not None or ehigh is not None:
        out += mark(emid, "c-bull", "", "", dot=not boxed)
    if t1 is not None:
        out += mark(t1, "c-blue", f"${t1:.2f}", "TP1")
    if t2 is not None:
        out += mark(t2, "c-blue", f"${t2:.2f}", "TP2")

    if current is not None:
        out += f'<div class="ltnow" style="left:{pct(current):.1f}%;"><span class="ltnowic">{_IC_DOLLAR}</span></div>'
    return out + "</div>"


def _pattern_entry(entry, current=None, symbol=None):
    """Phase 5 entry: Entry-Zone hero (range, current/distance, alignment ring,
    level track) + four coloured stat tiles + Push-to-Calculator. Falls back to
    legacy rows if needed."""
    if not entry:
        return ""
    zone = entry.get("zone")
    if not zone:
        return _pattern_entry_rows(entry)
    elow, ehigh = zone.get("low"), zone.get("high")
    stop = entry.get("stop") or {}
    risk = entry.get("risk") or {}
    t1, t2 = entry.get("t1") or {}, entry.get("t2") or {}
    sv, t1v, t2v = stop.get("value"), t1.get("value"), t2.get("value")

    # current price + distance from the entry zone
    statmid = ""
    if current is not None and (elow is not None or ehigh is not None):
        top = ehigh if ehigh is not None else elow
        bot = elow if elow is not None else ehigh
        if current > top:
            dist, lab, dc = (current - top) / top * 100, "Above Entry", "bull"
        elif current < bot:
            dist, lab, dc = (current - bot) / bot * 100, "Below Entry", "bear"
        else:
            dist, lab, dc = 0.0, "In Entry Zone", "neu"
        sign = "+" if dist > 0 else ""
        statmid = (
            '<div class="hzcur"><div class="hzlab">Current Price</div>'
            f'<div class="hzval">${current:,.2f}</div></div>'
            '<div class="hzcur"><div class="hzlab">Distance from Entry</div>'
            f'<div class="hzval {dc}">{sign}{dist:.1f}% '
            f'<span class="hzpill {dc}">{_e(lab)}</span></div></div>'
        )
    ref0 = t1v if t1v is not None else t2v
    em0 = (elow + ehigh) / 2 if (elow is not None and ehigh is not None) else (elow if elow is not None else ehigh)
    direction = (entry.get("direction") or ("short" if (em0 is not None and ref0 is not None and ref0 < em0) else "long")).lower()

    hero = (
        f'<div class="ezhero ez-{direction}">'
        + '<div class="ezpill">Entry Zone</div>'
        + f'<div class="ezbig">{_e(zone.get("label") or "")}</div>'
        + (f'<div class="ezsub">{_e((zone.get("subtitle") or "").upper())}</div>' if zone.get("subtitle") else "")
        + '<div class="ezdash"></div>'
        + f'<div class="ezstats">{statmid}</div>'
        + _level_track(sv, elow, ehigh, t1v, t2v, current, (risk or {}).get("label"))
        + "</div>"
    )

    # Key under the trade map: a lead (stop icon, or TP1/TP2 label) · rationale,
    # with a right-side chip — red risk on the stop row (the sizing input), blue
    # R:R on the Target rows.
    def keyrow(lead, note, chip=""):
        if not (note or chip):
            return ""
        note_html = (
            f'<span class="eknote">{_hl_numbers(note)}</span>' if note
            else '<span class="eknote"></span>'
        )
        return (
            '<div class="ekrow">'
            + f'<span class="eklead">{lead}</span>'
            + note_html
            + chip
            + "</div>"
        )

    def rr_chip(rr):
        rrtxt = _e((rr or "").replace("~", "").strip())
        return f'<span class="ekrr">{rrtxt}</span>' if rrtxt else ""

    # Stop-distance row: amber hazard icon · entry→stop distance ($ per unit + %).
    # Computed from em0 (the entry pushed to the calculator) and the stop, so the
    # value always matches the calculator's Stop Distance for the same setup —
    # not the hand-rounded JSON risk label.
    risk_row = ""
    if sv is not None and em0:
        _sd = abs(em0 - sv)
        risk_row = keyrow(
            f'<span class="ekic" style="color:#f5a623">{_IC_RISK}</span>',
            "Entry → stop",
            f'<span class="ekrisk">${_sd:.2f} · {_sd / em0 * 100:.1f}%</span>',
        )

    stop_lead = f'<span class="ekic" style="color:#f6465d">{_IC_SHIELD}</span>'
    key = (
        '<div class="ekey">'
        + keyrow(stop_lead, stop.get("note"))
        + keyrow('<span class="ektp">TP1</span>', t1.get("note"), rr_chip(t1.get("rr")))
        + keyrow('<span class="ektp">TP2</span>', t2.get("note"), rr_chip(t2.get("rr")))
        + risk_row
        + "</div>"
    )

    return f'<div class="pentry">{hero}{key}</div>'


def _pattern_entry_rows(entry):
    """Legacy compact entry (Entry/Stop/Risk/Targets rows) — kept for older files."""
    rows = entry.get("rows", [])
    if not rows:
        return ""
    out = ""
    for r in rows:
        tone = r.get("tone") or "neu"
        note = f' <span class="enote">{_e(r.get("note"))}</span>' if r.get("note") else ""
        rr = f'<div class="errbox"><span class="errlab">RR</span>{_e(r.get("rr"))}</div>' if r.get("rr") else ""
        out += (
            '<div class="erow">'
            f'<div class="elab {tone}">{_e(r.get("label"))}</div>'
            f'<div class="eval {tone}">{_e(r.get("value"))}{note}</div>{rr}</div>'
        )
    hd = f'<div class="elabhd">Trade Entry{(" · " + _e(entry.get("model"))) if entry.get("model") else ""}</div>'
    return f'<div class="pentry">{hd}{out}</div>'


def _rr_compact(rr):
    txt = (rr or "").replace("~", "").strip()
    if not txt or txt.upper() == "N/A":
        return "N/A"
    m = re.search(r"1\s*:\s*([0-9]+(?:\.[0-9]+)?)", txt)
    return f"1:{m.group(1)}" if m else _e(txt)


def _top_rr(entry):
    entry = entry or {}
    for key in ("t2", "t1"):
        rr = (entry.get(key) or {}).get("rr")
        if rr and rr.upper() != "N/A":
            return _rr_compact(rr)
    return "N/A"


def _setup_name(name):
    low = (name or "").lower()
    explicit_patterns = (
        ("inverse head", "Inverse H&S"),
        ("head and shoulders", "Head & Shoulders"),
        ("head-and-shoulders", "Head & Shoulders"),
        ("bull flag", "Bull Flag"),
        ("bear flag", "Bear Flag"),
        ("double bottom", "Double Bottom"),
        ("double top", "Double Top"),
        ("triple bottom", "Triple Bottom"),
        ("triple top", "Triple Top"),
        ("falling wedge", "Falling Wedge"),
        ("rising wedge", "Rising Wedge"),
        ("wedge", "Wedge"),
        ("ascending triangle", "Ascending Triangle"),
        ("descending triangle", "Descending Triangle"),
        ("symmetrical triangle", "Sym Triangle"),
        ("triangle", "Triangle"),
        ("rectangle", "Rectangle"),
        ("range", "Range"),
        ("pennant", "Pennant"),
    )
    contextual_setups = (
        ("failed breakdown", "Failed Breakdown"),
        ("failed breakout", "Failed Breakout"),
        ("breakout retest", "Breakout Retest"),
        ("breakdown retest", "Breakdown Retest"),
        ("breakout", "Breakout"),
        ("breakdown", "Breakdown"),
        ("retest", "Retest"),
        ("pullback", "Pullback"),
        ("support", "Support Test"),
        ("resistance", "Resistance Test"),
        ("base", "Base"),
        ("reversal", "Reversal"),
        ("continuation", "Continuation"),
    )
    for needle, label in explicit_patterns + contextual_setups:
        if needle in low:
            return label
    return (name or "Trade Setup").split("(")[0].split("/")[0].strip()[:28]


def _entry_label(entry):
    zone = (entry or {}).get("zone") or {}
    label = zone.get("label")
    if label:
        if "no valid" in label.lower() or len(label) > 24:
            prices = re.findall(r"\$?\d+(?:\.\d+)?", label)
            if len(prices) >= 2:
                return f"${prices[0].lstrip('$')}-${prices[1].lstrip('$')}"
            if prices:
                return f"${prices[0].lstrip('$')}"
            return "No entry"
        return label.replace(" – ", "-").replace(" — ", "-")
    low, high = zone.get("low"), zone.get("high")
    if low is not None and high is not None:
        return f"{_money(low)}-{_money(high)}"
    if low is not None:
        return _money(low)
    if high is not None:
        return _money(high)
    return "No entry"


def _setup_sketch(name):
    low = (name or "").lower()
    if "inverse head" in low:
        lines = (
            '<path d="M8 18 C18 30 24 30 34 18 C40 44 58 48 64 18 C74 30 82 30 92 18" />'
            '<path d="M10 18 H92" class="dash" />'
        )
    elif "head" in low and "shoulder" in low:
        lines = (
            '<path d="M8 54 C18 38 26 38 34 54 C42 16 56 10 64 54 C74 38 84 38 94 54" />'
            '<path d="M10 54 H92" class="dash" />'
        )
    elif "triple bottom" in low:
        lines = (
            '<path d="M8 20 L20 56 L34 24 L48 56 L62 24 L76 56 L92 20" />'
            '<path d="M14 56 H82" class="dash" />'
        )
    elif "triple top" in low:
        lines = (
            '<path d="M8 56 L20 20 L34 52 L48 20 L62 52 L76 20 L92 56" />'
            '<path d="M14 20 H82" class="dash" />'
        )
    elif "double top" in low:
        lines = (
            '<path d="M10 56 L30 18 L50 54 L70 18 L90 56" />'
            '<path d="M22 18 H78" class="dash" />'
        )
    elif "wedge" in low:
        lines = (
            '<path d="M8 40 L22 12 L92 48" />'
            '<path d="M8 40 L86 24" />'
            '<path d="M27 20 L27 43 M48 27 L48 39 M68 30 L68 35" />'
        )
    elif "ascending triangle" in low:
        lines = (
            '<path d="M10 18 H92" class="dash" />'
            '<path d="M12 60 L92 18" />'
            '<path d="M20 52 L34 18 L48 42 L62 18 L76 32" />'
        )
    elif "descending triangle" in low:
        lines = (
            '<path d="M10 58 H92" class="dash" />'
            '<path d="M12 18 L92 58" />'
            '<path d="M20 24 L34 58 L48 34 L62 58 L76 46" />'
        )
    elif "triangle" in low or "pennant" in low:
        lines = (
            '<path d="M10 18 L92 38 L10 58 Z" />'
            '<path d="M22 24 L36 52 L50 31 L64 46 L78 36" />'
        )
    elif "rectangle" in low or "range" in low:
        lines = (
            '<path d="M12 20 H90 M12 56 H90" class="dash" />'
            '<path d="M14 44 L28 22 L42 54 L56 24 L72 54 L88 30" />'
        )
    elif "bottom" in low:
        lines = (
            '<path d="M10 18 L28 58 L48 26 L66 58 L88 12" />'
            '<path d="M12 28 H34 M40 58 H62 M70 22 H94" class="dash" />'
        )
    elif "flag" in low:
        lines = (
            '<path d="M18 60 L30 10" />'
            '<path d="M30 14 L92 44 M26 35 L84 64 M26 35 L30 14 M84 64 L92 44" />'
            '<path d="M37 50 L45 28 L54 48 L65 31 L75 55" />'
        )
    elif "failed breakdown" in low or "support" in low or "retest" in low:
        lines = (
            '<path d="M10 52 H92" class="dash" />'
            '<path d="M12 22 L28 50 L45 28 L62 52 L80 36 L92 28" />'
            '<path d="M54 52 L62 52 L62 44" />'
        )
    elif "failed breakout" in low or "resistance" in low:
        lines = (
            '<path d="M10 22 H92" class="dash" />'
            '<path d="M12 52 L28 24 L45 48 L62 20 L80 36 L92 46" />'
            '<path d="M54 22 L62 22 L62 30" />'
        )
    elif "pullback" in low:
        lines = (
            '<path d="M10 56 L28 40 L44 22 L58 34 L72 28 L92 12" />'
            '<path d="M44 22 L58 34 L72 28" class="dash" />'
        )
    elif "breakout" in low:
        lines = (
            '<path d="M10 44 H58" class="dash" />'
            '<path d="M14 54 L30 38 L46 48 L60 30 L78 20 L92 10" />'
        )
    elif "breakdown" in low:
        lines = (
            '<path d="M10 30 H58" class="dash" />'
            '<path d="M14 20 L30 36 L46 26 L60 44 L78 54 L92 64" />'
        )
    elif "base" in low:
        lines = (
            '<path d="M12 56 H90" class="dash" />'
            '<path d="M12 44 L28 56 L44 46 L60 56 L76 48 L90 54" />'
        )
    elif "reversal" in low:
        lines = (
            '<path d="M12 18 L28 36 L44 56 L60 42 L76 28 L92 18" />'
            '<path d="M48 56 C58 38 72 24 92 18" class="dash" />'
        )
    elif "continuation" in low:
        lines = (
            '<path d="M10 56 L30 36 L48 22" />'
            '<path d="M48 22 L66 34 L82 26" class="dash" />'
            '<path d="M82 26 L94 14" />'
        )
    else:
        lines = (
            '<path d="M10 50 L28 36 L45 42 L62 22 L88 30" />'
            '<path d="M12 58 H88" class="dash" />'
        )
    return f'<svg class="mt-sketch" viewBox="0 0 100 74" fill="none">{lines}</svg>'


def _mobile_trade_setups(built):
    if not built:
        return ""
    rows = ""
    for i, b in enumerate(built[:3], 1):
        p = b["raw"]
        entry = p.get("entry") or {}
        direction = (entry.get("direction") or "").upper()
        dcls = "long" if direction == "LONG" else "short" if direction == "SHORT" else "neu"
        grade = (p.get("grade") or "").strip().upper()[:1]
        grade_html = f'<span class="mt-grade">{_e(grade)}</span>' if grade else '<span class="mt-grade mt-grade-empty"></span>'
        details = (
            (b.get("sum") or "")
            + (b.get("note") or "")
            + (b.get("entry") or "")
            + (b.get("edge") or "")
            + (b.get("opp") or "")
            + (b.get("ev") or "")
            + (b.get("conf") or "")
            + (b.get("tools") or "")
        )
        rows += (
            f'<details class="mt-setup {dcls}">'
            '<summary>'
            f'{_setup_sketch(p.get("name"))}'
            '<span class="mt-main">'
            '<span class="mt-titleline">'
            f'<span class="mt-name">{_e(_setup_name(p.get("name")))}</span>'
            f'<span class="mt-dir">{_e(direction)}</span>'
            '<span></span>'
            f'{grade_html}'
            '</span>'
            '<span class="mt-facts">'
            f'<span class="mt-fact"><em>RR</em><strong>{_e(_top_rr(entry))}</strong></span>'
            f'<span class="mt-fact mt-entry"><em>Entry</em><strong>{_e(_entry_label(entry))}</strong></span>'
            f'<span class="mt-side"><span class="mt-caret">{_DOWN_ARROW_SVG}</span></span>'
            '</span>'
            '</span>'
            '</summary>'
            f'<div class="mt-detail">{details}</div>'
            '</details>'
        )
    return (
        '<div class="mobile-trades">'
        '<div class="mt-head"><h3>Top Trade Setups</h3></div>'
        f'{rows}'
        '</div>'
    )


def _section(icon, label, body, iccls, pill=""):
    if not body:
        return ""
    return (
        f'<div class="psec"><div class="psecic {iccls}">{icon}</div>'
        f'<div class="psecbody"><div class="psechd">{label}{pill}</div>{body}</div></div>'
    )


def _section_plain(label, body, cls="", pill=""):
    if not body:
        return ""
    return f'<div class="psec psec-plain {cls}"><div class="psecbody"><div class="psechd">{label}{pill}</div>{body}</div></div>'


def _mobile_collapsible_section(label, section_html):
    if not section_html:
        return ""
    return (
        f'<div class="psec-desktop-copy">{section_html}</div>'
        f'<details class="psec-mobile-collapse">'
        f'<summary><span class="mc-summary-label">{_e(label)}</span>{_DOWN_ARROW_SVG}</summary>'
        f'{section_html}'
        '</details>'
    )


def _success_likelihood_note(candidate):
    raw = (
        candidate.get("success_likelihood")
        or candidate.get("trade_success_likelihood")
        or candidate.get("ai_confidence")
        or candidate.get("success_probability")
        or candidate.get("setup_confidence")
    )
    if raw is None:
        return ""
    if isinstance(raw, dict):
        pct = raw.get("percent") or raw.get("probability") or raw.get("value")
    else:
        pct = raw
    try:
        pct_val = max(0, min(100, round(float(str(pct).replace("%", "").strip()))))
    except (TypeError, ValueError):
        return ""
    return f'<li class="success-note">Estimated chance this reaches TP1 before invalidation: {pct_val}%.</li>'


def _confluence(conf):
    """Returns (strength_pill_html, body_html). dict -> check/warn checklist; str -> paragraph."""
    if not conf:
        return "", ""
    if isinstance(conf, str):
        return "", f'<div class="pconf">{_hl_numbers(conf)}</div>'
    strength = conf.get("strength")
    scls = {"STRONG": "s-strong", "MODERATE": "s-mod", "WEAK": "s-weak"}.get((strength or "").upper(), "s-mod")
    pill = f'<span class="cstr {scls}">{_e(strength)}</span>' if strength else ""
    checks = "".join(f'<div class="cchk ok">{_IC_CHECK}<span>{_hl_numbers(c)}</span></div>' for c in conf.get("checks", []))
    warns = "".join(f'<div class="cchk warn">{_IC_WARN}<span>{_hl_numbers(w)}</span></div>' for w in conf.get("warnings", []))
    body = f'<div class="pconfcols"><div>{checks}</div><div>{warns}</div></div>'
    return pill, body


_POSITIONING_TERMS = (
    "funding", "open interest", "oi ", "oi-", "oi:", "order book", "order-book",
    "depth", "spread", "liquidity", "liquidation", "cvd", "bid", "ask", "book",
    "wall", "crowd", "crowded", "squeeze", "short covering", "deleverag",
)


def _is_positioning_text(text):
    low = f" {str(text or '').lower()} "
    return any(term in low for term in _POSITIONING_TERMS)


def _candidate_positioning_items(p):
    raw = p.get("positioning_edge")
    items = []
    if isinstance(raw, dict):
        for key in ("funding", "open_interest", "liquidity", "trade_implication", "implication"):
            val = raw.get(key)
            if val:
                items.append(str(val))
        warnings = raw.get("warnings")
        if isinstance(warnings, list):
            items.extend(str(w) for w in warnings if w)
        elif warnings:
            items.append(str(warnings))
    elif isinstance(raw, list):
        items.extend(str(x) for x in raw if x)
    elif raw:
        items.append(str(raw))

    conf = p.get("confluence") or {}
    if isinstance(conf, dict):
        for key in ("checks", "warnings"):
            for text in conf.get(key, []) or []:
                if _is_positioning_text(text):
                    items.append(str(text))
    for text in p.get("evidence", []) or []:
        if _is_positioning_text(text):
            items.append(str(text))

    out, seen = [], set()
    for item in items:
        item = item.strip()
        if not item:
            continue
        norm = re.sub(r"\s+", " ", item.lower())
        if norm in seen:
            continue
        seen.add(norm)
        out.append(item)
    return out[:4]


def _positioning_factor_label(text):
    low = str(text or "").lower()
    if "funding" in low:
        return "Funding"
    if "open interest" in low or re.search(r"\boi\b", low):
        return "OI"
    if any(k in low for k in ("order book", "order-book", "bid", "ask", "spread", "depth", "wall", "liquidity")):
        return "Liquidity"
    if "btc" in low or "correlation" in low:
        return "Correlation"
    return "Edge"


def _positioning_verdict(text):
    low = str(text or "").lower()
    if re.match(r"^\s*(strengthens|weakens|mixed|neutral)\b", low):
        return re.match(r"^\s*(strengthens|weakens|mixed|neutral)\b", low).group(1)
    weak = any(k in low for k in (
        "weakens", "cost", "reduces", "danger", "risk", "fail", "failed", "squeeze risk",
        "not too tight", "moderate spread", "wide spread", "thin", "stall", "less reliable",
    ))
    strong = any(k in low for k in (
        "strengthens", "supports", "supportive", "benefit", "adequate", "confirms",
        "stronger", "helps", "receive", "follow through",
    ))
    if weak and strong:
        return "mixed"
    if weak:
        return "weakens"
    if strong:
        return "strengthens"
    return "mixed"


def _positioning_display_text(text):
    text = str(text or "").strip()
    low = text.lower()
    if "supportive for scalps" in low:
        return re.sub(
            r"supportive for scalps\.?",
            "may cushion a tight long entry; not proof scalpers are active.",
            text,
            flags=re.I,
        )
    if "bid-side depth" in low and "stronger than ask" in low:
        return text.rstrip(".") + "; useful only if bids stay in place."
    return text


def _positioning_consequence_text(label, text):
    text = _positioning_display_text(text)
    verdict = ""
    match = re.match(r"^(strengthens|weakens|mixed|neutral)\b\s*[:—-]?\s*(.*)$", text, re.I)
    if match:
        verdict = match.group(1).lower()
        text = match.group(2).strip() or text
    cleaned = text
    replacements = {
        "OI": "open interest",
        "positive funding makes shorts slightly paid against": "longs are paying shorts, so holding a short is slightly easier",
        "positive funding charges longs to hold": "longs are paying funding, so holding a long is slightly less attractive",
        "negative funding pays long holds": "shorts are paying longs, so holding a long is slightly easier",
        "negative funding penalizes shorts on hold": "shorts are paying funding, so holding a short is slightly less attractive",
        "positive funding slightly offsets short holding costs": "longs are paying shorts, so funding slightly helps the short",
        "open interest down; bounce likely covering not new longs": "the bounce may be short-covering, so take profits quickly if price stalls",
        "open interest falling can reduce breakdown follow-through": "falling participation can make the breakdown weaker, so do not overstay it",
        "spot+perp": "spot and perp",
        "deltas negative": "selling pressure",
        "deltas positive": "buying pressure",
        "tight spread enables tight invalidation": "orders should execute close to plan, so the tight stop is more realistic",
        "tight spread supports tight stop execution": "orders should execute close to plan, so the tight stop is more realistic",
        "tight spread helps breakout execution": "orders should execute close to plan if the breakout triggers",
        "tight spread helps quick invalidation": "orders should execute close to plan if the trade is wrong",
        "take trigger": "take the trigger",
        "take profits fast": "take profits quickly",
    }
    for old, new in replacements.items():
        cleaned = re.sub(rf"\b{re.escape(old)}\b", new, cleaned, flags=re.I)
    low_cleaned = cleaned.lower()
    if "holding a short is slightly easier" in low_cleaned or "funding slightly helps the short" in low_cleaned:
        verdict = "strengthens"
    elif "holding a long is slightly less attractive" in low_cleaned or "holding a short is slightly less attractive" in low_cleaned:
        verdict = "weakens"
    cleaned = re.sub(r"^(this\s+)?(strengthens|weakens)\s+(the\s+)?idea\s*:\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^(mixed|neutral)\s+read\s*:\s*", "", cleaned, flags=re.I)
    return verdict, cleaned


def _candidate_positioning_edge(p):
    raw = p.get("positioning_edge")
    if isinstance(raw, dict):
        rows = []

        def edge_row(label, value, cls=""):
            if not value:
                return ""
            verdict, text = _positioning_consequence_text(label, value)
            vchip = f'<span class="peverdict {verdict}">{_e(verdict)}</span>' if verdict else ""
            return (
                f'<div class="perow {cls}">'
                f'<div class="perlab">{_e(label)}</div>'
                f'<div class="pertext">{vchip}{_hl_numbers(text)}</div>'
                "</div>"
            )

        rows.append(edge_row("Net", raw.get("trade_implication") or raw.get("implication"), "pe-impact"))
        rows.append(edge_row("Funding", raw.get("funding")))
        rows.append(edge_row("Funding Timing", raw.get("funding_timing") or raw.get("funding_countdown")))
        rows.append(edge_row("Open Interest", raw.get("open_interest")))
        rows.append(edge_row("Liquidations", raw.get("liquidations") or raw.get("liquidation_history") or "Mixed: not available yet; do not use as edge."))
        rows.append(edge_row("Spot/Perp CVD", raw.get("spot_perp_cvd") or raw.get("cvd") or "Mixed: not available yet; do not use as edge."))
        rows.append(edge_row("Liquidity", raw.get("liquidity")))
        warnings = raw.get("warnings")
        if isinstance(warnings, list):
            warn_body = "".join(f"<li>{_hl_numbers(w)}</li>" for w in warnings if w)
            if warn_body:
                rows.append(
                    '<div class="perow">'
                    '<div class="perlab">Watch-outs</div>'
                    '<div class="pertext"><ul class="plist pe-list">' + warn_body + "</ul></div>"
                    "</div>"
                )
        elif warnings:
            rows.append(edge_row("Watch-outs", str(warnings)))
        body = "".join(rows)
        if body:
            return _section_plain("Positioning Edge", f'<div class="pe-detail">{body}</div>', "positioning-edge-section")

    items = _candidate_positioning_items(p)
    if not items:
        return ""
    rows = ""
    for item in items:
        verdict, item = _positioning_consequence_text("", item)
        verdict = verdict or _positioning_verdict(item)
        label = _positioning_factor_label(item)
        rows += (
            '<div class="perow">'
            f'<div class="perlab">{_e(label)}</div>'
            f'<div class="pertext"><span class="peverdict {verdict}">{_e(verdict)}</span>{_hl_numbers(item)}</div>'
            "</div>"
        )
    rows += (
        '<div class="perow"><div class="perlab">Liquidations</div>'
        '<div class="pertext"><span class="peverdict mixed">mixed</span>not available yet; do not use as edge.</div></div>'
        '<div class="perow"><div class="perlab">Spot/Perp CVD</div>'
        '<div class="pertext"><span class="peverdict mixed">mixed</span>not available yet; do not use as edge.</div></div>'
    )
    return _section_plain("Positioning Edge", f'<div class="pe-detail">{rows}</div>', "positioning-edge-section")


def _pattern_cards(cands, current=None, symbol=None):
    """Phase 3/4 pattern candidates as horizontal cards: name + maturity pill ·
    classification: qualifier · summary · Phase 5 entry hero + tiles · evidence ·
    note · confluence checklist · tools footer. `current` = live price for distance;
    `symbol` = ticker for the Push-to-Calculator link."""
    if not cands:
        return ""
    # Order by OPPORTUNITY, not completeness (framework Phase 3 — Pattern
    # Prioritisation): best Trade Grade first, and within a grade the less-complete
    # pattern (more upside remaining) ahead of one whose move is largely done.
    _gr = {"A": 0, "B": 1, "C": 2, "D": 3}
    _mr = {"emerging": 0, "developing": 1, "mature": 2, "ready": 3, "triggered": 4}
    cands = sorted(
        cands,
        key=lambda p: (
            _gr.get((p.get("grade") or "").strip().upper()[:1], 4),
            _mr.get(_maturity_cls(p.get("maturity")), 2),
        ),
    )
    # First pass: build every card's sections so we can give each section its own
    # shared subgrid row (Evidence aligns with Evidence, Note with Note, etc.).
    built = []
    for p in cands[:3]:
        grade = (p.get("grade") or "").strip().upper()[:1]
        gbadge = f'<div class="pgrade {_grade_cls(grade)}">{_e(grade)}</div>' if grade else ""
        # Pills are deliberately uniform violet (quiet metadata) — colour is reserved
        # for direction (long/short) and targets, not these tags.
        matpill = (
            f'<span class="pmat">{_e(_maturity_label(p.get("maturity")))}</span>'
            if p.get("maturity") else ""
        )
        modepill = (
            f'<span class="pmode">{_e(_mode_label(p.get("entry_mode")))}</span>'
            if p.get("entry_mode") else ""
        )
        cls, qln = p.get("classification"), p.get("qualifier")
        # Classification heading is coloured by trade direction: long → green, short → red.
        _dir = ((p.get("entry") or {}).get("direction") or "").lower()
        dcls = "dir-long" if _dir == "long" else "dir-short" if _dir == "short" else ""
        if cls and qln:
            meta = f'<div class="pmeta"><span class="pcls {dcls}">{_e(cls)}:</span> <span class="pqal">{_hl_numbers(qln)}</span></div>'
        elif cls or qln:
            meta = f'<div class="pmeta"><span class="pcls {dcls}">{_e(cls or qln)}</span></div>'
        else:
            meta = ""
        pills = f'<div class="ppills">{matpill}{modepill}</div>' if (matpill or modepill) else ""
        head = (
            '<div class="phead">'
            '<div class="pmain">'
            f'<div class="ptoprow"><span class="pname">{_e(p.get("name"))}</span></div>'
            f"{pills}"
            f"{meta}"
            "</div>"
            f"{gbadge}"
            "</div>"
        )
        summary = f'<div class="psummary">{_hl_numbers(p.get("summary"))}</div>' if p.get("summary") else ""
        entryblock = _pattern_entry(p.get("entry"), current, symbol)
        ev = "".join(f"<li>{_hl_numbers(x)}</li>" for x in p.get("evidence", []))
        miss = "".join(f"<li>{_hl_numbers(x)}</li>" for x in p.get("missing", []))
        note_body = miss + _success_likelihood_note(p)
        cpill, cbody = _confluence(p.get("confluence"))
        ev_section = _section(_IC_EV, "Evidence", f'<ul class="plist">{ev}</ul>' if ev else "", "ic-ev")
        conf_section = _section(_IC_CONF, "Confluence", cbody, "ic-conf", cpill)
        tools = (p.get("entry") or {}).get("tools")
        toolsfoot = (
            f'<div class="ptools"><span class="ptlab">Tools used:</span> {_e(tools)}</div>'
            if tools else ""
        )
        built.append({
            "raw": p,
            "head": head,
            "sum": summary,
            "entry": entryblock,
            "edge": _candidate_positioning_edge(p),
            "opp": _section(_IC_OPP, "Opportunity Window", _opportunity(p.get("opportunity")), "ic-opp"),
            "ev": _mobile_collapsible_section("Evidence", ev_section),
            "note": _section_plain("Note", f'<ul class="plist miss">{note_body}</ul>' if note_body else "", "note-section"),
            "conf": _mobile_collapsible_section("Confluence", conf_section),
            "tools": toolsfoot,
        })

    # One subgrid row per slot. Fixed slots first, then any optional section that
    # appears in at least one card (so empty rows don't leave gaps). Tools last so
    # it pins to the bottom of every card.
    fixed = [("head", "pc-head"), ("sum", "pc-sum")]
    if any(b["note"] for b in built):
        fixed.append(("note", "pc-note"))
    fixed.append(("entry", "pc-entry"))
    optional = [("edge", "pc-edge"), ("opp", "pc-opp"), ("ev", "pc-ev"),
                ("conf", "pc-conf"), ("tools", "pc-tools")]
    slots = fixed + [s for s in optional if any(b[s[0]] for b in built)]
    nrows = len(slots)

    cells = ""
    for b in built:
        inner = "".join(f'<div class="{c}">{b[k]}</div>' for k, c in slots)
        cells += f'<div class="dcard pcard">{inner}</div>'

    # Adapt the grid to the number of cards so 2 patterns aren't left in a 3-up row.
    grid = "drow3" if len(cands) >= 3 else "drow2" if len(cands) == 2 else "dstack"
    rows_style = f"grid-template-rows:repeat({nrows},auto);" if grid in ("drow2", "drow3") else ""
    mobile = _mobile_trade_setups(built)
    return (
        f'{mobile}'
        '<div class="desktop-patterns">'
        '<div class="drowlab">&nbsp;</div>'
        f'<div class="{grid}" style="{rows_style}">{cells}</div>'
        '</div>'
    )


def _convergence(d):
    """A full-width callout above the pattern cards when multiple candidates point
    at one decision level — surfaces the single pivot the whole setup hinges on."""
    c = d.get("convergence")
    if not c:
        return ""
    if isinstance(c, str):
        title, body = "Decision Zone", c
    else:
        title, body = c.get("title") or "Decision Zone", c.get("note") or ""
    if not body:
        return ""
    return (
        '<div class="convg">'
        f'<div class="convgic">{_IC_OPP}</div>'
        '<div class="convgbody">'
        f'<div class="convghd">{_e(title)}</div>'
        f'<div class="convgtxt">{_hl_numbers(body)}</div>'
        '</div>'
        '</div>'
    )


def _body_rows(d):
    """Everything below the header: the three card rows."""
    sc = d.get("scorecard", {})

    # Row 1 (3 cols): Key Levels | Probability Distribution | Bias Scorecard.
    # (What Changes My Mind now lives under Setup Classification; bull/bear case
    # under the Trade Plan — see _setup_box / _trade_plan.)
    row1 = (
        '<div class="drow3">'
        + _card("Key Levels", _levels(d.get("key_levels", {})))
        + _card("Probability Distribution", _prob(d.get("probability_distribution", [])))
        + _card("Bias Scorecard", _scorecard_table(sc))
        + "</div>"
    )

    # Row 2 (3 cols): 4-Hour | Daily | Evidence Matrix.
    row2 = (
        '<div class="drow3">'
        + _card("4-Hour Timeframe — Bias Assessment", _factor_table(d.get("h4", {})))
        + _card("Daily Timeframe — Bias Assessment", _factor_table(d.get("daily", {})))
        + _card("Evidence Matrix — What Weighs In", _evidence_matrix(d.get("evidence_matrix", [])))
        + "</div>"
    )

    # Row 3: Additional Data Check (Volume Profile / VWAP). Derivatives now live
    # under Market State / Trading Thesis in the header.
    row3 = _card("Additional Data Check", _kv(d.get("additional_data", [])))
    return row1 + row2 + row3


# ----------------------------------------------------------------- render
def _dhead_top(d, q):
    """v3 header (layout move, existing styling): price top-left unboxed +
    orange caveat line + a thin horizontal snapshot strip across the top.
    Market State / Thesis / Leverage follow underneath. Live quote `q` drives
    price / high / low."""
    if q:
        price, chg = fmt_price(q["last"]), round(q["pct"], 2)
    else:
        price, chg = d.get("price"), d.get("change_pct_24h", 0)
    chg_cls = "bull" if (isinstance(chg, (int, float)) and chg >= 0) else "bear"
    chg_str = (f"+{chg}" if isinstance(chg, (int, float)) and chg >= 0 else f"{chg}") + "%"

    meta = d.get("meta", {})
    sub = " · ".join(x for x in [d.get("contract"), meta.get("timeframe_analyzed")] if x)

    # Market Bias is folded into the ticker block: the Bullish/Bearish/Neutral call
    # (+ animal icon) sits top-right above Open Interest, and the bias thesis runs
    # under the price — freeing the whole right side of the top row for Market
    # Condition. headline / liquidity_note still intentionally not rendered.
    ms = d.get("market_structure") or {}
    bias = ms.get("bias") or d.get("market_bias", "") or ""
    bc = _cls(bias)
    bias_inline = (
        f'<div class="v3biasinline {bc}">'
        f'<div class="v3biasv2"><div class="v3biasword">{_e(bias)}</div>'
        f'<div class="v3biasicon">{_bias_icon(bc)}</div></div>'
        "</div>"
    ) if bias else ""

    # bias_note (the "thesis" line) intentionally NOT rendered here — it's redundant
    # with the Market State bullet (the 2.13 pivot) and the long/short pattern cards.
    # bias_inline is absolutely pinned to the banner's top-right (word aligns with
    # the symbol line, icon drops centred beneath it) so dropping the icon doesn't
    # push the price down.
    banner = (
        '<div class="v3banner">'
        + bias_inline
        + f'<div class="hsym">{_e(d.get("symbol"))}<span class="mobilelive">{_live_badge()}</span> <span class="hperp">{_e(sub)}</span></div>'
        + f'<div class="hprice">{_e(price)} <span class="{chg_cls} hchg">{_e(chg_str)}</span></div>'
        + "</div>"
    )

    snap = {(s.get("label") or "").strip().lower(): s.get("value") for s in d.get("snapshot", [])}

    def si(label, value, vc=""):
        return (
            f'<div class="v3si"><div class="v3sl">{_e(label)}</div>'
            f'<div class="v3sv {vc}">{_e(value if value not in (None, "") else "—")}</div></div>'
        )

    hi = fmt_price(q["high"]) if q else snap.get("24h high")
    lo = fmt_price(q["low"]) if q else snap.get("24h low")
    funding = f'{q["funding"]:.4f}%' if q and q.get("funding") is not None else snap.get("funding rate") or snap.get("funding")
    open_interest = fmt_volume(q["open_interest"]) if q and q.get("open_interest") is not None else snap.get("open interest")

    strip = (
        '<div class="v3striprow">'
        + '<div class="v3strip">'
        + _live_badge()
        + si("24H High", hi)
        + si("24H Low", lo)
        + si("Funding", funding)
        + si("Open Interest", open_interest)
        + "</div>"
        + "</div>"
    )

    # Top row: ticker block (left, with bias folded in) + Market Condition (right).
    head = (
        '<div class="v3toprow">'
        + '<div class="v3left">' + banner + strip + "</div>"
        + '<div class="v3condside">' + _market_condition_box(d) + "</div>"
        + "</div>"
    )
    return head + _regime_thesis(d)


def render(d, symbol=None):
    # The header price strip AND the pattern cards' Current Price / Distance-from-
    # Entry refresh from one Binance quote every 2s via a single fragment, so those
    # values track live. The header-bottom row + body card rows are static.
    sym = symbol or re.sub(r"[^A-Z0-9]", "", (d.get("symbol") or "").upper())
    cands = d.get("pattern_candidates", [])

    # Section-by-section build: only draw a block once its data exists, so a
    # partially-converted analysis (e.g. market_structure only) renders cleanly
    # instead of a page of empty section-boxes.
    def _mid(cur):
        return _convergence(d) + (_pattern_cards(cands, cur, sym) if cands else "")

    if symbol:
        @st.fragment(run_every=2)
        def _live_top():
            try:
                q = scanner.live_ticker(symbol)
                deriv = _live_derivatives(symbol)
                if q and deriv:
                    q.update(deriv)
            except Exception:
                q = None
            cur = q.get("last") if q else _num(d.get("price"))
            st.markdown(_dash(_dhead_top(d, q) + _mid(cur)), unsafe_allow_html=True)
        _live_top()
    else:
        st.markdown(_dash(_dhead_top(d, None) + _mid(_num(d.get("price")))), unsafe_allow_html=True)

    # Header bottom row + the three card rows — only when their sections exist yet.
    _bottom_keys = (
        "scorecard", "key_levels", "probability_distribution", "h4", "daily",
        "evidence_matrix", "additional_data", "trade_plan", "verdict",
        "what_changes_my_mind", "analyst_summary", "setup_classification",
    )
    if any(d.get(k) for k in _bottom_keys):
        st.markdown(_dash(_dhead_bottom(d) + _body_rows(d)), unsafe_allow_html=True)
