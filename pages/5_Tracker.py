from __future__ import annotations

import html
import base64
import json
import os

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import bybit
import chrome
import tracking_cycles

st.set_page_config(page_title="Tracker", page_icon="📊", layout="wide")
chrome.render_header("TRACKER", "", "Mobile performance")

st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
.st-key-brandrow{display:none!important;}
.tracker-shell{max-width:720px;margin:0 auto;}
.st-key-tracker_filters{margin:-50px 0 2px!important;}
.st-key-tracker_filters [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;gap:8px!important;}
.st-key-tracker_filters [data-testid="stColumn"]:first-child{width:auto!important;flex:1 1 auto!important;min-width:0!important;}
.st-key-tracker_filters [data-testid="stColumn"]:nth-child(2){width:42px!important;flex:0 0 42px!important;min-width:42px!important;}
.st-key-tracker_filters [data-testid="stColumn"]:last-child{width:82px!important;flex:0 0 82px!important;min-width:82px!important;}
.st-key-tracker_cycle [data-baseweb="select"]>div{height:42px!important;min-height:42px!important;border-radius:8px!important;}
.st-key-tracker_cycle [data-baseweb="select"] span{font-size:12px!important;font-weight:850!important;}
.st-key-tracker_journal{height:42px!important;margin:0!important;}
.tracker-journal-icon{width:42px;height:42px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;border:1px solid rgba(139,92,246,.42);border-radius:8px;background:#13101e;text-decoration:none!important;transition:border-color .15s ease,background .15s ease;}
.tracker-journal-icon:hover{border-color:#8b5cf6;background:#1b1628;}
.tracker-journal-icon img{width:23px;height:23px;display:block;filter:invert(1);}
.st-key-tracker_period{margin:0!important;}
.st-key-tracker_period [data-testid="stSegmentedControl"]{width:100%!important;}
.st-key-tracker_period [data-testid="stSegmentedControl"] > div{width:100%!important;display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:3px!important;padding:3px!important;}
.st-key-tracker_period [data-testid="stSegmentedControl"] label{height:42px!important;min-height:42px!important;padding:0!important;display:flex!important;align-items:center!important;justify-content:center!important;}
.st-key-tracker_period [data-testid="stSegmentedControl"] label p{font-size:.78rem!important;line-height:1!important;margin:0!important;font-weight:720!important;}
.tk-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:-14px 0 10px;}
.tk-card{background:#13101e;border:1px solid rgba(139,92,246,.34);border-radius:8px;padding:12px 13px;
  box-shadow:0 0 0 1px rgba(124,58,237,.05),0 14px 34px rgba(0,0,0,.20);}
.tk-cap{display:block;color:#8b94a0;font-size:9px;font-weight:850;letter-spacing:.07em;text-transform:uppercase;}
.tk-big{display:block;color:#f4f7fb;font-size:23px;font-weight:900;line-height:1.06;margin-top:7px;font-variant-numeric:tabular-nums;}
.tk-big.green,.green{color:#0ecb81!important}.tk-big.red,.red{color:#f6465d!important}.tk-big.amber,.amber{color:#e0a33e!important}
.tk-sub{display:block;color:#8b94a0;font-size:11px;font-weight:650;margin-top:5px;line-height:1.3;}
.tk-section{background:#13101e;border:1px solid rgba(139,92,246,.34);border-radius:8px;padding:13px;margin:10px 0;
  box-shadow:0 0 0 1px rgba(124,58,237,.05),0 14px 34px rgba(0,0,0,.18);}
.tk-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:10px;}
.tk-head b{color:#f4f7fb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;}
.tk-head span{color:#8b94a0;font-size:10px;font-weight:750;}
.tk-row{display:grid;grid-template-columns:22px minmax(0,1fr) 54px 68px;gap:8px;align-items:center;padding:9px 0;border-top:1px solid rgba(139,148,160,.12);}
.tk-row:first-child{border-top:0;padding-top:0;}
.tk-rank{display:flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:5px;background:rgba(139,148,160,.10);color:#8b94a0;font-size:10px;font-weight:900;font-variant-numeric:tabular-nums;}
.tk-row strong{color:#f4f7fb;font-size:13px;font-weight:850;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tk-row small{display:block;color:#8b94a0;font-size:10px;font-weight:650;margin-top:3px;}
.tk-row b{text-align:right;color:#cdd3da;font-size:12px;font-weight:850;font-variant-numeric:tabular-nums;}
.tk-row .tk-mini-stat{text-align:right;}
.tk-row .tk-mini-stat b{display:block;}
.tk-row .tk-mini-stat small{margin-top:2px;text-align:right;font-size:9px;font-weight:850;letter-spacing:.06em;}
.tk-dir{display:grid;grid-template-columns:1fr 1fr;gap:9px;}
.tk-dir-box{position:relative;min-height:96px;overflow:hidden;border:1px solid rgba(139,148,160,.14);border-radius:8px;background:rgba(15,23,42,.30);padding:11px 70px 11px 11px;}
.tk-dir-box span{display:block;color:#8b94a0;font-size:9px;font-weight:850;letter-spacing:.06em;text-transform:uppercase;}
.tk-dir-box b{display:block;color:#f4f7fb;font-size:20px;font-weight:900;margin-top:6px;font-variant-numeric:tabular-nums;}
.tk-dir-copy{position:relative;z-index:2;}
.tk-animal{position:absolute;right:4px;top:50%;width:76px;height:76px;transform:translateY(-50%);opacity:.96;z-index:1;pointer-events:none;}
.tk-animal svg,.tk-animal img{width:100%;height:100%;display:block;object-fit:contain;}
.tk-dir-box.long .tk-animal{right:0;}
.tk-dir-box.short .tk-animal{right:-1px;}
.st-key-tracker_chart_split{margin:10px 0;}
.st-key-tracker_chart_split [data-testid="stHorizontalBlock"]{gap:10px!important;align-items:stretch!important;}
.st-key-tracker_chart_split [data-testid="stColumn"]{min-width:0!important;}
.st-key-tracker_split_card,.st-key-tracker_split_card .tk-section{height:230px;}
.st-key-tracker_split_card .tk-section{box-sizing:border-box;margin:0;display:flex;flex-direction:column;}
.st-key-tracker_split_card .tk-dir{flex:1;}
.st-key-tracker_split_card .tk-dir-box{height:100%;box-sizing:border-box;}
.recent-scroll{max-height:640px;overflow-y:auto;margin-right:-6px;padding-right:6px;}
.recent-scroll::-webkit-scrollbar{width:7px}.recent-scroll::-webkit-scrollbar-track{background:rgba(139,148,160,.08);border-radius:999px}
.recent-scroll::-webkit-scrollbar-thumb{background:rgba(139,148,160,.38);border-radius:999px}
.trade-card{border-top:1px solid rgba(139,148,160,.12);padding:8px 0;}
.trade-card:first-child{border-top:0;padding-top:0;}
.trade-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;}
.trade-top strong{color:#f4f7fb;font-size:14px;font-weight:900;}
.trade-top small{display:block;color:#8b94a0;font-size:10px;font-weight:650;margin-top:3px;}
.trade-side{display:flex;flex-direction:column;align-items:flex-end;gap:3px;}
.trade-pnl{text-align:right;font-size:14px;font-weight:900;font-variant-numeric:tabular-nums;}
.trade-line{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:7px;color:#8b94a0;font-size:10px;font-weight:700;line-height:1.25;}
.trade-line b{color:#dfe3e8;font-size:10px;font-weight:850;}
.trade-detail{margin-top:4px;overflow:visible;}
.trade-detail summary{list-style:none;width:30px;height:20px;margin:0 0 0 auto;padding:0;display:flex;align-items:center;justify-content:center;color:#8b94a0;cursor:pointer;}
.trade-detail summary::-webkit-details-marker{display:none;}
.trade-detail summary:after{content:"⌄";font-size:15px;font-weight:900;line-height:1;transition:transform .16s ease;}
.trade-detail[open] summary:after{transform:rotate(180deg);}
.trade-detail summary span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}
.trade-detail-body{margin-top:4px;border:1px solid rgba(139,148,160,.13);border-radius:7px;background:rgba(15,23,42,.24);padding:9px 10px 10px;}
.trade-note{margin:0 0 9px;color:#dfe3e8;font-size:11px;font-weight:650;line-height:1.38;}
.trade-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px 10px;}
.trade-detail-grid span{display:block;color:#8b94a0;font-size:9px;font-weight:850;letter-spacing:.06em;text-transform:uppercase;}
.trade-detail-grid b{display:block;color:#f4f7fb;font-size:11px;font-weight:850;margin-top:3px;font-variant-numeric:tabular-nums;}
.pill{display:inline-flex;align-items:center;border-radius:5px;padding:2px 7px;font-size:10px;font-weight:850;}
.pill.long{color:#0ecb81;background:rgba(14,203,129,.12)}.pill.short{color:#f6465d;background:rgba(246,70,93,.12)}
.tk-empty{padding:14px 0;color:#8b94a0;font-size:11px;font-weight:700;}
@media(max-width:700px){
  .tracker-shell{margin-top:-18px!important;}
  .st-key-tracker_filters{margin-top:-18px!important;}
  .st-key-tracker_filters [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr) 82px!important;grid-template-rows:42px 42px!important;gap:7px 8px!important;align-items:center!important;}
  .st-key-tracker_filters [data-testid="stColumn"]:first-child{grid-column:1;grid-row:2;width:100%!important;}
  .st-key-tracker_filters [data-testid="stColumn"]:nth-child(2){grid-column:2;grid-row:1;width:42px!important;min-width:42px!important;justify-self:end;}
  .st-key-tracker_filters [data-testid="stColumn"]:last-child{grid-column:2;grid-row:2;width:82px!important;min-width:82px!important;}
  .st-key-tracker_cycle [data-baseweb="select"] span,.st-key-tracker_cycle input{font-size:16px!important;}
  .st-key-tracker_chart_split [data-testid="stHorizontalBlock"]{display:block!important;}
  .st-key-tracker_chart_split [data-testid="stColumn"]{width:100%!important;flex:0 0 100%!important;}
  .st-key-tracker_split_card{margin-top:10px;}
}
@media(min-width:701px){
  .tracker-shell{margin-top:18px}
  .tk-grid{grid-template-columns:repeat(6,minmax(0,1fr));gap:7px}
  .tk-card{min-width:0;padding:10px 8px}
  .tk-cap{color:#fff!important;font-size:12px;letter-spacing:.045em;white-space:nowrap}
  .tk-big{font-size:22px;white-space:nowrap}
  .tk-sub{font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .recent-scroll{max-height:520px}
}
</style>""",
    unsafe_allow_html=True,
)

PERIODS = {
    "1D": 1,
    "7D": 7,
    "30D": 30,
    "90D": 90,
    "365D": 365,
}

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT_DIR, "assets", "write.svg"), "rb") as _journal_icon_file:
    JOURNAL_ICON_DATA = base64.b64encode(_journal_icon_file.read()).decode("ascii")


def svg_data_uri(filename: str) -> str:
    path = os.path.join(ROOT_DIR, "assets", filename)
    try:
        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    except OSError:
        return ""


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def money(value, sign=False) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    prefix = "+" if sign and v >= 0 else ""
    return f"{prefix}${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"


def price(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 100:
        return f"{v:,.2f}"
    if abs(v) >= 1:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}".rstrip("0").rstrip(".")


def duration_label(minutes) -> str:
    if pd.isna(minutes):
        return "—"
    total = max(0, int(round(float(minutes))))
    if total < 1:
        return "<1m"
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def pct(value, digits=1) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def timestamp_label(ms) -> str:
    try:
        value = int(ms)
    except (TypeError, ValueError):
        return "—"
    if value <= 0:
        return "—"
    return pd.to_datetime(value, unit="ms").strftime("%d %b %H:%M")


def trade_move_pct(row) -> float | None:
    try:
        entry = float(row.get("entry") or 0)
        exit_price = float(row.get("exit") or 0)
    except (TypeError, ValueError):
        return None
    if entry <= 0:
        return None
    if str(row.get("direction")) == "Short":
        return (entry - exit_price) / entry * 100
    return (exit_price - entry) / entry * 100


def trade_commentary(row, pnl: float, context: dict) -> str:
    move = trade_move_pct(row)
    minutes = row.get("duration_min")
    duration = float(minutes) if not pd.isna(minutes) else None
    fees = abs(float(row.get("fees") or 0))
    gross = abs(float(row.get("gross") or 0))
    fee_drag = fees / gross * 100 if gross > 0 else 0
    avg_win_ctx = abs(float(context.get("avg_win") or 0))
    avg_loss_ctx = abs(float(context.get("avg_loss") or 0))
    median_duration = context.get("median_duration")
    rank_best = context.get("rank_best", {}).get(str(row.get("trade_id")))
    rank_worst = context.get("rank_worst", {}).get(str(row.get("trade_id")))

    def duration_read() -> str:
        if duration is None:
            return "hold time is unavailable"
        if median_duration and duration >= median_duration * 1.75 and duration >= 60:
            return "held longer than your typical trade"
        if median_duration and duration <= median_duration * 0.5 and duration <= 60:
            return "quick compared with your typical trade"
        return f"held for {duration_label(duration)}"

    if pnl > 0:
        if avg_win_ctx and pnl >= avg_win_ctx * 1.25:
            opener = "Efficient win" if duration is not None and (not median_duration or duration <= median_duration * 1.2) else "Strong win"
            compare = "beat your average winner"
        elif avg_win_ctx and pnl < avg_win_ctx * 0.5:
            opener = "Small win"
            compare = "finished below your average winner"
        else:
            opener = "Winning trade"
            compare = "landed near your normal winning range"

        if move is None:
            move_read = "price movement is unavailable"
        elif move >= 1.0:
            move_read = f"the move went {pct(move, 2)} in your favour"
        elif move >= 0.25:
            move_read = f"the move was only {pct(move, 2)} in your favour"
        else:
            move_read = "price barely moved in your favour"

        rank_read = f" This was your #{rank_best} win in the period." if rank_best and rank_best <= 3 else ""
        fee_read = " Fees took a noticeable bite." if fee_drag >= 20 else ""
        return f"{opener}: {move_read}, {duration_read()}, and {compare}.{rank_read}{fee_read}"

    elif pnl < 0:
        loss_abs = abs(pnl)
        if avg_loss_ctx and loss_abs >= avg_loss_ctx * 1.25:
            opener = "Loss worth reviewing"
            compare = "larger than your average loser"
        elif avg_loss_ctx and loss_abs <= avg_loss_ctx * 0.6:
            opener = "Controlled loss"
            compare = "smaller than your average loser"
        else:
            opener = "Controlled loss" if move is not None and abs(move) < 0.75 else "Losing trade"
            compare = "close to your normal losing range"

        if move is None:
            move_read = "price movement is unavailable"
        elif move <= -1.5:
            move_read = f"the move went {pct(abs(move), 2)} against entry and was probably hard to recover"
        elif move <= -0.75:
            move_read = f"the move went {pct(abs(move), 2)} against entry"
        elif move < 0:
            move_read = f"the move only went {pct(abs(move), 2)} against entry, so the loss looks contained"
        else:
            move_read = f"price finished {pct(move, 2)} in your favour, so this loss may be fee, sizing, or execution related"

        rank_read = f" This was your #{rank_worst} loss in the period." if rank_worst and rank_worst <= 3 else ""
        fee_read = " Fees made the result worse." if fee_drag >= 20 else ""
        return f"{opener}: {move_read}. Loss was {compare}, and it was {duration_read()}.{rank_read}{fee_read}"

    return f"Breakeven-style result: price movement was small, it was {duration_read()}, and there is probably not much to learn unless this pattern repeats."


def cumulative_chart(df: pd.DataFrame) -> str:
    if df.empty:
        values = [0.0, 0.0]
        labels = ["Cycle start", "Now"]
    else:
        daily = df.copy()
        daily["day"] = daily["date"].dt.normalize()
        daily = daily.groupby("day", as_index=False).agg(cum=("cum", "last"))
        start_day = daily.iloc[0]["day"] - pd.Timedelta(days=1)
        labels = [start_day.strftime("%d %b")] + [row["day"].strftime("%d %b") for _, row in daily.iterrows()]
        values = [0.0] + [float(v) for v in daily["cum"].tolist()]
        if len(values) < 2:
            values = [0.0, 0.0]
            labels = ["Cycle start", "Now"]
    width, height = 320, 170
    left, right, top, bottom = 14, 10, 12, 28
    plot_w = width - left - right
    plot_h = height - top - bottom
    low = min(values + [0.0])
    high = max(values + [0.0])
    span = high - low or 1.0

    def x_at(idx: int) -> float:
        return left + idx / max(1, len(values) - 1) * plot_w

    def y_at(value: float) -> float:
        return top + (high - value) / span * plot_h

    chart_points = [
        {
            "x": round(x_at(i), 2),
            "y": round(y_at(v), 2),
            "value": round(v, 2),
            "label": labels[min(i, len(labels) - 1)],
        }
        for i, v in enumerate(values)
    ]
    point_text = " ".join(f"{p['x']},{p['y']}" for p in chart_points)
    area = f"{left:.1f},{height - bottom:.1f} {point_text} {width - right:.1f},{height - bottom:.1f}"
    zero_y = y_at(0.0)
    end_cls = "green" if values[-1] >= 0 else "red"
    points_json = json.dumps(chart_points)
    return f"""
<style>
  html,body{{margin:0;background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}}
  .card{{box-sizing:border-box;height:230px;background:#13101e;border:1px solid rgba(139,92,246,.34);border-radius:8px;padding:13px;
    box-shadow:0 0 0 1px rgba(124,58,237,.05),0 14px 34px rgba(0,0,0,.18);}}
  .head{{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:10px;}}
  .head b{{color:#f4f7fb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;}}
  .head span{{color:{'#0ecb81' if end_cls == 'green' else '#f6465d'};font-size:10px;font-weight:850;}}
  .wrap{{position:relative;height:170px;touch-action:pan-y;}}
  svg{{height:170px;width:100%;display:block;}}
  text{{font-family:inherit;font-size:10px;font-weight:750;fill:#8b94a0;}}
  .grid{{stroke:rgba(139,148,160,.14);stroke-width:1;}}
  .zero{{stroke:rgba(244,247,251,.24);stroke-width:1;stroke-dasharray:4 4;}}
  .area{{fill:rgba(76,141,255,.14);}}
  .line{{fill:none;stroke:#4c8dff;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;}}
  .guide{{stroke:#f4f7fb;stroke-width:1.3;opacity:.86;}}
  .dot{{fill:#f4f7fb;stroke:#4c8dff;stroke-width:2;}}
  .tip{{position:absolute;top:12px;transform:translateX(-50%);min-width:86px;border:1px solid rgba(244,247,251,.18);
    border-radius:7px;background:rgba(7,11,18,.88);box-shadow:0 10px 26px rgba(0,0,0,.28);padding:6px 8px;text-align:center;
    pointer-events:none;}}
  .tip b{{display:block;color:#f4f7fb;font-size:12px;font-weight:900;font-variant-numeric:tabular-nums;}}
  .tip span{{display:block;color:#8b94a0;font-size:9px;font-weight:800;margin-top:2px;}}
</style>
<div class="card">
  <div class="head"><b>Cumulative P&amp;L</b><span>{money(values[-1], True)}</span></div>
  <div class="wrap" id="wrap">
    <svg id="chart" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" aria-label="Interactive cumulative P&L chart">
      <line class="grid" x1="{left}" x2="{width - right}" y1="{top}" y2="{top}"/>
      <line class="grid" x1="{left}" x2="{width - right}" y1="{top + plot_h / 2:.1f}" y2="{top + plot_h / 2:.1f}"/>
      <line class="grid" x1="{left}" x2="{width - right}" y1="{height - bottom}" y2="{height - bottom}"/>
      <line class="zero" x1="{left}" x2="{width - right}" y1="{zero_y:.1f}" y2="{zero_y:.1f}"/>
      <polygon class="area" points="{area}"/>
      <polyline class="line" points="{point_text}"/>
      <line id="guide" class="guide" x1="0" x2="0" y1="{top}" y2="{height - bottom}"/>
      <circle id="dot" class="dot" cx="0" cy="0" r="4"/>
      <text x="{left}" y="{height - 8}">{esc(labels[0])}</text>
      <text x="{width - right}" y="{height - 8}" text-anchor="end">{esc(labels[-1])}</text>
    </svg>
    <div class="tip" id="tip"><b></b><span></span></div>
  </div>
</div>
<script>
  const points = {points_json};
  const wrap = document.getElementById('wrap');
  const svg = document.getElementById('chart');
  const guide = document.getElementById('guide');
  const dot = document.getElementById('dot');
  const tip = document.getElementById('tip');
  const areaEl = svg.querySelector('.area');
  const lineEl = svg.querySelector('.line');
  const axisLabels = svg.querySelectorAll('text');
  let viewWidth = {width};
  const money = (v) => {{
    const sign = v >= 0 ? '+' : '-';
    return `${{sign}}${{new Intl.NumberFormat('en-US', {{style:'currency', currency:'USD'}}).format(Math.abs(v))}}`;
  }};
  function show(index) {{
    const p = points[Math.max(0, Math.min(points.length - 1, index))];
    guide.setAttribute('x1', p.x);
    guide.setAttribute('x2', p.x);
    dot.setAttribute('cx', p.x);
    dot.setAttribute('cy', p.y);
    tip.querySelector('b').textContent = money(p.value);
    tip.querySelector('span').textContent = p.label;
    const rect = svg.getBoundingClientRect();
    const leftPx = (p.x / viewWidth) * rect.width;
    tip.style.left = `${{Math.max(46, Math.min(rect.width - 46, leftPx))}}px`;
  }}
  function layout() {{
    viewWidth = Math.max(240, Math.round(svg.getBoundingClientRect().width));
    svg.setAttribute('viewBox', `0 0 ${{viewWidth}} {height}`);
    points.forEach((p, i) => {{
      p.x = {left} + i / Math.max(1, points.length - 1) * (viewWidth - {left} - {right});
    }});
    const renderedPoints = points.map(p => `${{p.x}},${{p.y}}`).join(' ');
    lineEl.setAttribute('points', renderedPoints);
    areaEl.setAttribute('points', `{left},{height - bottom} ${{renderedPoints}} ${{viewWidth - {right}}},{height - bottom}`);
    svg.querySelectorAll('.grid,.zero').forEach(el => el.setAttribute('x2', viewWidth - {right}));
    if (axisLabels.length > 1) axisLabels[axisLabels.length - 1].setAttribute('x', viewWidth - {right});
    show(points.length - 1);
  }}
  function move(ev) {{
    const rect = svg.getBoundingClientRect();
    const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX;
    const vx = ((clientX - rect.left) / rect.width) * viewWidth;
    let best = 0;
    let bestDist = Infinity;
    points.forEach((p, i) => {{
      const dist = Math.abs(p.x - vx);
      if (dist < bestDist) {{
        bestDist = dist;
        best = i;
      }}
    }});
    show(best);
  }}
  wrap.addEventListener('pointermove', move);
  wrap.addEventListener('pointerdown', move);
  wrap.addEventListener('touchstart', move, {{passive:true}});
  wrap.addEventListener('touchmove', move, {{passive:true}});
  layout();
  new ResizeObserver(layout).observe(svg);
</script>
"""


@st.cache_data(ttl=300, show_spinner="Loading tracker...")
def load_trades(days: int):
    return bybit.fetch_closed_trades(days)


st.markdown("<div class='tracker-shell'>", unsafe_allow_html=True)
with st.container(key="tracker_filters"):
    period_col, journal_col, cycle_col = st.columns([1, 0.12, 0.24], gap="small")
    with period_col:
        with st.container(key="tracker_period"):
            period = st.segmented_control("Period", list(PERIODS), default="30D", label_visibility="collapsed")
    with cycle_col:
        with st.container(key="tracker_cycle"):
            cycle_view = st.selectbox(
                "Trading cycle",
                ["Cyc 2", "Cyc 1"],
                index=0,
                label_visibility="collapsed",
            )
    journal_tab_id = "1842282429" if cycle_view == "Cyc 2" else "1304074642"
    journal_url = (
        "https://docs.google.com/spreadsheets/d/1PhD6GM1onHo3Fwi8jveo8GEnP12FymfmCTU1qpAR_xw/"
        f"edit?gid={journal_tab_id}#gid={journal_tab_id}"
    )
    with journal_col:
        with st.container(key="tracker_journal"):
            st.markdown(
                f'<a class="tracker-journal-icon" href="{html.escape(journal_url)}" target="_blank" '
                'rel="noopener noreferrer" aria-label="Open journal" title="Open journal">'
                f'<img src="data:image/svg+xml;base64,{JOURNAL_ICON_DATA}" alt=""></a>',
                unsafe_allow_html=True,
            )

if not bybit.have_creds():
    st.warning("No Bybit API key configured.")
    st.stop()

days = PERIODS.get(period or "30D", 30)
cycle_age_days = max(1, int((pd.Timestamp.now(tz="UTC").timestamp() * 1000 - tracking_cycles.cutoff_ts()) / 86_400_000) + 1)
fetch_days = 7 if cycle_view == "Cyc 1" else max(7, min(days, cycle_age_days))
try:
    live_trades = load_trades(fetch_days)
except Exception as exc:
    st.error(f"Couldn't reach Bybit: {exc}")
    st.stop()

if cycle_view == "Cyc 1":
    trades = tracking_cycles.archived_trades(live_trades)
else:
    trades = tracking_cycles.current_trades(live_trades)
    period_cutoff = pd.Timestamp.now(tz="Australia/Melbourne") - pd.Timedelta(days=days)
    effective_cutoff_ms = max(tracking_cycles.cutoff_ts(), int(period_cutoff.timestamp() * 1000))
    trades = [row for row in trades if int(row.get("closed_ts") or 0) >= effective_cutoff_ms]

trade_columns = [
    "trade_id", "ts", "date", "opened_ts", "closed_ts", "duration_min", "coin",
    "direction", "size", "entry", "exit", "gross", "fees", "net", "stop_loss", "take_profit",
]
df = pd.DataFrame(trades, columns=trade_columns)
if not df.empty:
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("ts").reset_index(drop=True)
n = len(df)
wins = df[df.net > 0]
losses = df[df.net < 0]
net = float(df.net.sum())
win_rate = len(wins) / n * 100 if n else 0
avg_win = float(wins.net.mean()) if len(wins) else 0.0
avg_loss = float(losses.net.mean()) if len(losses) else 0.0
df["cum"] = df.net.cumsum()
max_dd = float((df.cum - df.cum.cummax()).min()) if n else 0.0
median_duration = float(df["duration_min"].dropna().median()) if df["duration_min"].notna().any() else None
rank_best = {
    str(row.trade_id): idx
    for idx, row in enumerate(df[df.net > 0].sort_values("net", ascending=False).itertuples(), 1)
}
rank_worst = {
    str(row.trade_id): idx
    for idx, row in enumerate(df[df.net < 0].sort_values("net").itertuples(), 1)
}
trade_context = {
    "avg_win": avg_win,
    "avg_loss": avg_loss,
    "median_duration": median_duration,
    "rank_best": rank_best,
    "rank_worst": rank_worst,
}

cards = [
    ("Total Trades", f"{n}", "", f"{len(wins)}W / {len(losses)}L"),
    ("Win Rate", pct(win_rate), "green" if win_rate >= 50 else "amber", f"{len(wins)}W / {len(losses)}L"),
    ("Net P&L", money(net, True), "green" if net >= 0 else "red", "after fees"),
    ("Max Drawdown", money(max_dd), "red" if max_dd < 0 else "", "peak to trough"),
    ("Avg Win", money(avg_win, True), "green", f"{len(wins)} winners"),
    ("Avg Loss", money(avg_loss, True), "red", f"{len(losses)} losers"),
]
st.markdown(
    "<div class='tk-grid'>"
    + "".join(
        f"<div class='tk-card'><span class='tk-cap'>{cap}</span><b class='tk-big {cls}'>{val}</b><span class='tk-sub'>{sub}</span></div>"
        for cap, val, cls, sub in cards
    )
    + "</div>",
    unsafe_allow_html=True,
)

dir_cards = []
for direction in ("Long", "Short"):
    sub = df[df.direction == direction]
    d_net = float(sub.net.sum()) if len(sub) else 0
    d_wr = (sub.net > 0).sum() / len(sub) * 100 if len(sub) else 0
    side_cls = direction.lower()
    animal_src = svg_data_uri("tracker-bull.svg" if direction == "Long" else "tracker-bear.svg")
    animal = f"<img src='{animal_src}' alt='{direction} graphic'>" if animal_src else ""
    dir_cards.append(
        f"<div class='tk-dir-box {side_cls}'><div class='tk-dir-copy'><span>{direction}</span><b class='{'green' if d_net >= 0 else 'red'}'>{money(d_net, True)}</b>"
        f"<small class='tk-sub'>{len(sub)} trades · {pct(d_wr, 0)} WR</small></div><div class='tk-animal'>{animal}</div></div>"
    )
with st.container(key="tracker_chart_split"):
    chart_col, split_col = st.columns(2, gap="small")
    with chart_col:
        components.html(cumulative_chart(df), height=230, scrolling=False)
    with split_col:
        with st.container(key="tracker_split_card"):
            st.markdown(
                "<div class='tk-section'><div class='tk-head'><b>Long / Short Split</b><span>Closed</span></div>"
                f"<div class='tk-dir'>{''.join(dir_cards)}</div></div>",
                unsafe_allow_html=True,
            )

coin_rows = []
for coin, sub in df.groupby("coin"):
    coin_wins = int((sub.net > 0).sum())
    coin_rows.append(
        {
            "coin": coin,
            "trades": len(sub),
            "wr": coin_wins / len(sub) * 100,
            "net": float(sub.net.sum()),
        }
    )
coin_rows = sorted(coin_rows, key=lambda r: r["net"], reverse=True)[:10]
st.markdown(
    "<div class='tk-section'><div class='tk-head'><b>Performance by Coin</b><span>Top 10</span></div>"
    + ("".join(
        f"<div class='tk-row'><span class='tk-rank'>{idx}</span><div><strong>{esc(row['coin'])}</strong><small>{row['trades']} trade{'s' if row['trades'] != 1 else ''}</small></div>"
        f"<div class='tk-mini-stat'><b>{pct(row['wr'], 0)}</b><small>WR</small></div><b class='{'green' if row['net'] >= 0 else 'red'}'>{money(row['net'], True)}</b></div>"
        for idx, row in enumerate(coin_rows, 1)
    ) if coin_rows else "<div class='tk-empty'>No closed trades in this cycle yet.</div>")
    + "</div>",
    unsafe_allow_html=True,
)

recent_rows = []
for _, row in df.sort_values("ts", ascending=False).head(20).iterrows():
    side = str(row.get("direction") or "").lower()
    pnl = float(row.get("net") or 0)
    move = trade_move_pct(row)
    detail_items = [
        ("Move", pct(move, 2) if move is not None else "—"),
        ("Gross", money(row.get("gross"), True)),
        ("Fees", money(row.get("fees"))),
        ("Opened", timestamp_label(row.get("opened_ts"))),
        ("Closed", timestamp_label(row.get("closed_ts"))),
        ("Net", money(pnl, True)),
    ]
    stop_loss = row.get("stop_loss")
    take_profit = row.get("take_profit")
    if not pd.isna(stop_loss):
        detail_items.append(("Stop", price(stop_loss)))
    if not pd.isna(take_profit):
        detail_items.append(("Target", price(take_profit)))
    detail_grid = "".join(
        f"<div><span>{label}</span><b>{esc(value)}</b></div>"
        for label, value in detail_items
    )
    recent_rows.append(
        "<div class='trade-card'>"
        "<div class='trade-top'>"
        f"<div><strong>{esc(row.get('coin'))}</strong><small>{row['date'].strftime('%d %b %Y')}</small></div>"
        f"<div class='trade-side'><div class='trade-pnl {'green' if pnl >= 0 else 'red'}'>{money(pnl, True)}</div></div>"
        "</div>"
        "<div class='trade-line'>"
        f"<span class='pill {side}'>{esc(row.get('direction'))}</span>"
        f"<span>Entry <b>{price(row.get('entry'))}</b></span>"
        f"<span>Exit <b>{price(row.get('exit'))}</b></span>"
        f"<span>Size <b>{money(row.get('size'))}</b></span>"
        f"<span>Held <b>{duration_label(row.get('duration_min'))}</b></span>"
        f"<span class='{'green' if pnl > 0 else 'red' if pnl < 0 else 'amber'}'>{'Win' if pnl > 0 else 'Loss' if pnl < 0 else 'BE'}</span>"
        "</div>"
        "<details class='trade-detail'>"
        "<summary><span>Trade details</span></summary>"
        "<div class='trade-detail-body'>"
        f"<p class='trade-note'>{esc(trade_commentary(row, pnl, trade_context))}</p>"
        f"<div class='trade-detail-grid'>{detail_grid}</div>"
        "</div></details></div>"
    )

recent_html = "".join(recent_rows) if recent_rows else '<div class="tk-empty">No closed trades in this cycle yet.</div>'
st.markdown(
    "<div class='tk-section'><div class='tk-head'><b>Recent Trades</b><span>Scroll top 20</span></div>"
    f"<div class='recent-scroll'>{recent_html}</div></div>",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)
