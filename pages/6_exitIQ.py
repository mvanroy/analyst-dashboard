"""exitIQ front-end concept page.

Static mock surface for the collapsible Exit IQ card. This intentionally does
not touch the existing data-driven Exit IQ page.
"""
from __future__ import annotations

import html

import streamlit as st

import chrome


st.set_page_config(page_title="exitIQ", page_icon="x", layout="wide")
chrome.render_header("exit", "IQ", "Exit management cockpit")


def _e(value) -> str:
    return html.escape("" if value is None else str(value))


POSITION = {
    "symbol": "ALTUSDT",
    "venue": "Bybit Perp",
    "side": "Long",
    "leverage": "10x",
    "valid": "Assessment valid",
    "timestamp": "08 Jul 2026 11:42",
    "closes": "4H closes",
    "exit_iq": 35,
    "condition": "Poor Exit Conditions",
    "subtitle": "Aggressive management required",
    "status": "Losing",
    "pnl": "-1.3%",
    "decision": "WAIT",
    "decision_note": "Waiting for one of these levels",
    "sell_zone": "0.0065-0.0066",
    "sell_action": "Sell into strength",
    "exit_level": "0.0062",
    "exit_action": "Exit remainder",
    "entry": "0.006359",
    "current": "0.006188",
    "size": "5,000 ALT",
    "liquidation": "0.00584",
    "time_window": "3 days left",
}


LADDER = [
    ("0.0075", "Jun 19 high", "+21.2%", ""),
    ("0.0068", "Jul 4 bounce high", "+9.9%", "Breaks = cancel exits"),
    ("0.0065-0.0066", "Jul 5-7 supply shelf", "+5.0%", "Sell zone"),
    ("0.006188", "Current price", "live", "You are here"),
    ("0.0062", "Equal lows", "-0.2%", "Exit level"),
    ("0.0059", "Jul 3 base", "-4.7%", "Next support"),
    ("0.00584", "Liquidation", "-7.0%", "Danger"),
]

ORDERS = [
    ("Waiting", "0.0065-0.0066", "Sell into strength", "Sell 80-100%"),
    ("Armed", "0.0062", "Exit remainder", "Exit"),
    ("Contingency", "0.0068", "Cancel exit plan", "Breaks resistance"),
]

REASONS = [
    ("Momentum collapsing", "CVD -306k, taker buy 41.6%, funding negative"),
    ("Sellers increasing", "OI +10.1% while price down, shorts building"),
    ("Thin liquidity", "$1.25M daily turnover, $1.56M OI"),
    ("Dated risk ahead", "Jul 25 unlock + Jul 14 CPI"),
]

HEALTH = [
    ("CVD", "-306k", "Falling"),
    ("Taker Buy %", "41.6%", "Weak"),
    ("Open Interest", "+10.1%", "Rising"),
    ("Funding", "-0.0085%", "Bearish"),
    ("Price vs BTC", "-1.2%", "Weak"),
]


def _metric(label: str, value: str, sub: str = "", cls: str = "") -> str:
    return (
        "<div class='xi-metric'>"
        f"<span>{_e(label)}</span>"
        f"<b class='{_e(cls)}'>{_e(value)}</b>"
        + (f"<small>{_e(sub)}</small>" if sub else "")
        + "</div>"
    )


def _status_icon(kind: str = "down") -> str:
    if kind == "up":
        return "<svg viewBox='0 0 24 24'><path d='M12 4 4 12h5v8h6v-8h5z'/></svg>"
    if kind == "exit":
        return "<svg viewBox='0 0 24 24'><path d='M11 4h2v12l5-5 1.4 1.4L12 20l-7.4-7.6L6 11l5 5z'/></svg>"
    return "<svg viewBox='0 0 24 24'><path d='M5 7h4l4.5 5.5L16 10h3v2h-2.2l-3.3 4L8 9H5z'/><path d='M16 15h4v4h-2v-1.6l-4.7-4.7 1.4-1.4 4.7 4.7H16z'/></svg>"


st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
.st-key-brandrow{display:none!important;}
.xi-shell{max-width:1160px;margin:-42px auto 0;padding:0 10px 18px;}
.xi-card{position:relative;border:1px solid rgba(93,104,130,.42);border-radius:8px;background:
  radial-gradient(900px 360px at 8% -10%,rgba(72,96,150,.18),transparent 58%),
  linear-gradient(145deg,rgba(9,15,31,.96),rgba(7,11,23,.92));box-shadow:0 18px 44px rgba(0,0,0,.25);overflow:hidden;}
.xi-card summary{list-style:none;cursor:pointer;}
.xi-card summary::-webkit-details-marker{display:none;}
.xi-toggle{position:absolute;left:0;right:0;top:0;height:294px;z-index:4;color:transparent;}
.xi-toggle span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}
.xi-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}
.xi-collapsed{position:relative;z-index:1;display:grid;grid-template-columns:minmax(130px,.55fr) auto minmax(0,1.05fr) minmax(0,1.25fr) 22px;gap:12px;align-items:center;padding:14px 16px;min-height:74px;}
.xi-compact-asset{min-width:0;}
.xi-compact-symbol{display:flex;align-items:center;gap:8px;color:#f6f8fd;font-size:18px;font-weight:950;line-height:1;letter-spacing:.02em;white-space:nowrap;}
.xi-compact-star{color:#697184;font-size:16px;}
.xi-compact-meta{margin-top:6px;color:#9ea7b8;font-size:12px;font-weight:740;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.xi-compact-meta b{color:#18d486;}
.xi-compact-score{display:flex;align-items:baseline;gap:5px;border:1px solid rgba(255,70,95,.42);border-radius:7px;background:rgba(255,70,95,.1);padding:8px 10px;color:#ff465f;white-space:nowrap;}
.xi-compact-score b{font-size:28px;font-weight:950;line-height:.9;}
.xi-compact-score span{color:#aeb6c6;font-size:12px;font-weight:850;}
.xi-compact-condition{min-width:0;}
.xi-compact-condition b{display:block;color:#ff5369;font-size:15px;font-weight:900;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.xi-compact-condition span{display:block;color:#aeb7c8;font-size:12px;font-weight:680;line-height:1.25;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.xi-compact-decision{display:flex;align-items:center;gap:9px;min-width:0;border-left:1px solid rgba(111,122,149,.2);padding-left:12px;}
.xi-compact-decision strong{color:#f3b441;font-size:16px;font-weight:950;letter-spacing:.05em;white-space:nowrap;}
.xi-compact-decision span{color:#d8deeb;font-size:12px;font-weight:740;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.xi-compact-chevron{display:flex;align-items:center;justify-content:center;color:#8f98aa;}
.xi-compact-chevron svg{width:18px;height:18px;fill:currentColor;transition:transform .16s ease;}
.xi-card[open] .xi-compact-chevron svg{transform:rotate(180deg);}
.xi-top{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:14px;align-items:start;padding:20px 22px 14px;border-bottom:1px solid rgba(128,139,164,.14);}
.xi-asset{display:grid;grid-template-columns:42px minmax(0,1fr);gap:13px;align-items:center;min-width:0;}
.xi-token{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:1px solid rgba(165,174,196,.28);color:#f2f5fb;font-size:26px;font-weight:900;background:rgba(13,18,32,.72);}
.xi-symbol{display:flex;align-items:center;gap:10px;color:#f6f8fd;font-size:28px;font-weight:900;letter-spacing:.03em;line-height:1;}
.xi-star{color:#697184;font-size:22px;}
.xi-meta{margin-top:7px;color:#b9c0ce;font-size:14px;font-weight:700;}
.xi-meta b{color:#18d486;font-weight:840;}
.xi-valid{display:inline-flex;align-items:center;gap:7px;border:1px solid rgba(18,201,129,.34);border-radius:6px;background:rgba(18,201,129,.08);color:#21df94;padding:8px 13px;font-size:12px;font-weight:850;white-space:nowrap;}
.xi-time{color:#c8ceda;font-size:14px;font-weight:760;line-height:1.35;text-align:left;white-space:nowrap;}
.xi-time span{display:block;color:#9ba4b5;}
.xi-score-row{display:grid;grid-template-columns:minmax(160px,.58fr) minmax(0,1.15fr) minmax(150px,.42fr) 34px;gap:0;border:1px solid rgba(86,100,138,.34);border-radius:8px;margin:18px 22px 12px;background:rgba(11,17,34,.62);overflow:hidden;}
.xi-score-cell,.xi-condition,.xi-status,.xi-chevron{min-height:104px;padding:18px 20px;display:flex;align-items:center;}
.xi-score-cell,.xi-condition,.xi-status{border-right:1px solid rgba(86,100,138,.28);}
.xi-label{display:block;color:#9ca5b6;font-size:11px;font-weight:900;letter-spacing:.1em;text-transform:uppercase;margin-bottom:8px;}
.xi-score{color:#ff465f;font-size:68px;font-weight:950;letter-spacing:-1px;line-height:.9;text-shadow:0 8px 22px rgba(255,70,95,.18);}
.xi-score small{color:#9ba4b5;font-size:25px;font-weight:800;letter-spacing:0;}
.xi-condition{display:block;padding-top:28px;}
.xi-condition b{display:block;color:#ff465f;font-size:25px;font-weight:900;line-height:1.12;}
.xi-condition span{display:block;color:#c3cad8;font-size:15px;font-weight:680;margin-top:9px;}
.xi-status{gap:14px;}
.xi-status-icon{width:46px;height:46px;border-radius:7px;display:flex;align-items:center;justify-content:center;color:#ff4d66;background:rgba(255,70,95,.12);}
.xi-status-icon svg{width:27px;height:27px;fill:currentColor;}
.xi-status strong{display:block;color:#f1f4fb;font-size:17px;font-weight:850;}
.xi-status b{display:block;color:#ff465f;font-size:25px;font-weight:900;margin-top:4px;}
.xi-chevron{justify-content:center;color:#8f98aa;padding:0;}
.xi-chevron svg{width:18px;height:18px;fill:currentColor;transition:transform .16s ease;}
.xi-card[open] .xi-chevron svg{transform:rotate(180deg);}
.xi-decision{display:grid;grid-template-columns:minmax(110px,.32fr) minmax(0,1fr);gap:18px;align-items:center;margin:0 22px 18px;border:1px solid rgba(243,180,65,.58);border-radius:8px;background:linear-gradient(90deg,rgba(243,180,65,.13),rgba(10,14,30,.34));padding:18px 20px;}
.xi-decision-main span{display:block;color:#f6c765;font-size:11px;font-weight:900;letter-spacing:.1em;text-transform:uppercase;}
.xi-decision-main b{display:block;color:#f3b441;font-size:45px;font-weight:950;line-height:.95;margin-top:7px;letter-spacing:.02em;}
.xi-gates{min-width:0;}
.xi-gates-title{color:#d8ddea;font-size:14px;font-weight:760;margin-bottom:10px;}
.xi-gate-row{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);gap:12px;align-items:center;}
.xi-gate{display:grid;grid-template-columns:44px minmax(0,1fr);gap:12px;align-items:center;border:1px solid rgba(120,129,155,.34);border-radius:8px;background:rgba(15,20,38,.64);padding:11px 13px;min-width:0;}
.xi-gate-icon{width:38px;height:38px;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#ff4d66;background:rgba(255,70,95,.12);}
.xi-gate-icon svg{width:24px;height:24px;fill:currentColor;}
.xi-gate b{display:block;color:#ff4d66;font-size:22px;font-weight:900;letter-spacing:.02em;line-height:1.05;white-space:nowrap;}
.xi-gate span{display:block;color:#f1f4fb;font-size:13px;font-weight:720;margin-top:3px;}
.xi-or{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#c2c8d6;color:#2b3040;font-size:11px;font-weight:900;letter-spacing:.08em;}
.xi-expanded{padding:14px 22px 20px;border-top:1px solid rgba(86,100,138,.28);}
.xi-position{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid rgba(86,100,138,.34);border-radius:8px;background:rgba(10,15,30,.56);overflow:hidden;margin-bottom:14px;}
.xi-metric{padding:15px 16px;border-right:1px solid rgba(86,100,138,.22);min-width:0;}
.xi-metric:last-child{border-right:0;}
.xi-metric span{display:block;color:#9ca5b6;font-size:10px;font-weight:900;letter-spacing:.1em;text-transform:uppercase;}
.xi-metric b{display:block;color:#eef2fb;font-size:21px;font-weight:850;margin-top:8px;line-height:1.05;font-variant-numeric:tabular-nums;}
.xi-metric small{display:block;color:#9aa3b3;font-size:12px;font-weight:650;margin-top:6px;}
.xi-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.95fr);gap:14px;}
.xi-panel{border:1px solid rgba(86,100,138,.34);border-radius:8px;background:rgba(10,15,30,.56);padding:16px;min-width:0;}
.xi-panel-title{display:flex;justify-content:space-between;align-items:center;gap:12px;color:#f2f4f8;font-size:15px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;margin-bottom:13px;}
.xi-panel-title small{color:#a879ff;font-size:11px;}
.xi-ladder{display:grid;gap:0;}
.xi-rung{display:grid;grid-template-columns:96px minmax(0,1fr) auto;gap:10px;align-items:center;border-top:1px solid rgba(111,122,149,.18);padding:10px 0;}
.xi-rung:first-child{border-top:0;}
.xi-rung b{color:#eef2fb;font-size:14px;font-weight:860;font-variant-numeric:tabular-nums;}
.xi-rung span{color:#c4cbd8;font-size:12px;font-weight:680;line-height:1.3;}
.xi-rung em{font-style:normal;color:#8f98aa;font-size:11px;font-weight:850;text-align:right;white-space:nowrap;}
.xi-rung.current{margin:4px -8px;padding:10px 8px;border:1px solid rgba(139,92,246,.58);border-radius:7px;background:rgba(139,92,246,.12);}
.xi-rung.current b,.xi-rung.current span,.xi-rung.current em{color:#b997ff;}
.xi-rung.danger b,.xi-rung.danger span,.xi-rung.danger em{color:#ff4d66;}
.xi-orders,.xi-reasons,.xi-health{display:grid;gap:9px;}
.xi-order{display:grid;grid-template-columns:86px minmax(0,1fr) auto;gap:9px;align-items:center;border:1px solid rgba(255,70,95,.28);border-radius:7px;background:rgba(255,70,95,.07);padding:11px;}
.xi-order span{color:#d7a2ad;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;}
.xi-order b{color:#f4f6fb;font-size:15px;font-weight:850;line-height:1.2;}
.xi-order small{color:#ff6b7f;font-size:11px;font-weight:900;text-transform:uppercase;text-align:right;}
.xi-reason{display:grid;grid-template-columns:34px minmax(0,1fr);gap:11px;align-items:start;}
.xi-reason i{width:31px;height:31px;border-radius:7px;background:rgba(255,70,95,.12);display:flex;align-items:center;justify-content:center;color:#ff4d66;font-style:normal;font-size:16px;font-weight:900;}
.xi-reason b{display:block;color:#f2f4f8;font-size:13px;font-weight:850;}
.xi-reason span{display:block;color:#aeb7c8;font-size:11px;font-weight:650;line-height:1.32;margin-top:3px;}
.xi-health{grid-template-columns:repeat(5,minmax(0,1fr));}
.xi-health-card{border:1px solid rgba(86,100,138,.28);border-radius:7px;background:rgba(15,20,38,.54);padding:12px 13px;}
.xi-health-card span{display:block;color:#d7dce7;font-size:11px;font-weight:760;}
.xi-health-card b{display:block;color:#ff4d66;font-size:18px;font-weight:900;margin-top:8px;}
.xi-health-card small{display:block;color:#9aa3b3;font-size:11px;margin-top:3px;}
.xi-bottom{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:14px;margin-top:14px;}
.xi-plan{display:grid;grid-template-columns:74px minmax(0,1fr) auto;gap:14px;align-items:center;border:1px solid rgba(255,70,95,.58);border-radius:8px;background:rgba(255,70,95,.08);padding:14px 16px;margin-top:14px;}
.xi-plan-icon{width:52px;height:52px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#ff4d66;border:1px solid rgba(255,70,95,.58);}
.xi-plan-icon svg{width:34px;height:34px;fill:currentColor;}
.xi-plan b{color:#ff4d66;font-size:19px;font-weight:950;letter-spacing:.12em;text-transform:uppercase;}
.xi-plan span{color:#f3f5fb;font-size:14px;font-weight:760;line-height:1.35;}
.xi-plan button{border:0;border-radius:7px;background:#c73248;color:white;padding:12px 16px;font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;}
.red{color:#ff4d66!important}.green{color:#18d486!important}.amber{color:#f3b441!important}.muted{color:#9aa3b3!important}
@media(max-width:760px){
  .xi-shell{margin:-18px auto 0;padding:0 0 14px;}
  .xi-card{border-radius:8px;}
  .xi-toggle{height:392px;}
  .xi-collapsed{grid-template-columns:minmax(0,1fr) auto 20px;gap:5px 8px;padding:8px 11px;min-height:62px;}
  .xi-compact-asset{grid-column:1 / 2;grid-row:1 / 2;}
  .xi-compact-symbol{font-size:17px;}
  .xi-compact-meta{display:none;}
  .xi-compact-score{grid-column:2 / 3;grid-row:1 / 2;}
  .xi-compact-score{padding:5px 7px;}
  .xi-compact-score b{font-size:20px;}
  .xi-compact-score span{font-size:10px;}
  .xi-compact-condition{grid-column:1 / 2;grid-row:2 / 3;min-width:0;}
  .xi-compact-condition b{font-size:12px;max-width:none;}
  .xi-compact-condition span{display:none;}
  .xi-compact-decision{grid-column:2 / 4;grid-row:2 / 3;border-left:0;padding-left:0;gap:6px;justify-content:flex-end;min-width:0;}
  .xi-compact-decision strong{font-size:12px;}
  .xi-compact-decision span{font-size:10px;max-width:145px;}
  .xi-compact-chevron{grid-column:3 / 4;grid-row:1 / 2;}
  .xi-top{grid-template-columns:minmax(0,1fr) auto;gap:9px;padding:16px 14px 10px;}
  .xi-symbol{font-size:24px;}
  .xi-valid{grid-column:2;grid-row:1;padding:7px 10px;font-size:10px;}
  .xi-time{grid-column:1 / -1;font-size:12px;text-align:right;}
  .xi-score-row{grid-template-columns:minmax(0,.74fr) minmax(0,1fr) 34px;margin:12px 14px 10px;}
  .xi-score-cell,.xi-condition,.xi-chevron{min-height:94px;padding:14px 15px;}
  .xi-status{display:none;}
  .xi-score{font-size:56px;}
  .xi-score small{font-size:20px;}
  .xi-condition{padding-top:23px;}
  .xi-condition b{font-size:20px;}
  .xi-condition span{font-size:13px;}
  .xi-decision{grid-template-columns:1fr;margin:0 14px 14px;padding:15px;gap:12px;}
  .xi-decision-main{display:flex;align-items:baseline;gap:13px;}
  .xi-decision-main b{font-size:36px;margin-top:0;}
  .xi-gate-row{grid-template-columns:1fr;gap:9px;}
  .xi-or{display:none;}
  .xi-gate b{font-size:19px;}
  .xi-expanded{padding:0 14px 16px;}
  .xi-position,.xi-grid,.xi-bottom{grid-template-columns:1fr;}
  .xi-position{border-radius:8px;}
  .xi-metric{border-right:0;border-bottom:1px solid rgba(86,100,138,.22);}
  .xi-metric:last-child{border-bottom:0;}
  .xi-health{grid-template-columns:repeat(2,minmax(0,1fr));}
  .xi-plan{grid-template-columns:44px minmax(0,1fr);gap:10px;}
  .xi-plan button{grid-column:1 / -1;width:100%;}
  .xi-plan-icon{width:42px;height:42px;}
}
</style>""",
    unsafe_allow_html=True,
)


ladder_html = "".join(
    "<div class='xi-rung"
    + (" current" if label == "Current price" else "")
    + (" danger" if tag == "Danger" else "")
    + "'>"
    f"<b>{_e(price)}</b><span>{_e(label)}</span><em>{_e(tag or dist)}</em></div>"
    for price, label, dist, tag in LADDER
)

orders_html = "".join(
    "<div class='xi-order'>"
    f"<span>{_e(state)}</span><b>{_e(level)}<br><small class='muted'>{_e(action)}</small></b><small>{_e(plan)}</small>"
    "</div>"
    for state, level, action, plan in ORDERS
)

reasons_html = "".join(
    "<div class='xi-reason'><i>!</i><div>"
    f"<b>{_e(title)}</b><span>{_e(copy)}</span>"
    "</div></div>"
    for title, copy in REASONS
)

health_html = "".join(
    f"<div class='xi-health-card'><span>{_e(name)}</span><b>{_e(value)}</b><small>{_e(state)}</small></div>"
    for name, value, state in HEALTH
)

card_html = f"""
<div class="xi-shell">
  <details class="xi-card">
    <summary class="xi-collapsed">
      <span class="xi-sr">Toggle exitIQ details</span>
      <div class="xi-compact-asset">
        <div class="xi-compact-symbol">{_e(POSITION["symbol"])} <span class="xi-compact-star">*</span></div>
        <div class="xi-compact-meta">{_e(POSITION["venue"])} &nbsp;.&nbsp; <b>{_e(POSITION["side"])}</b> &nbsp;.&nbsp; {_e(POSITION["leverage"])}</div>
      </div>
      <div class="xi-compact-score"><b>{_e(POSITION["exit_iq"])}</b><span>/100</span></div>
      <div class="xi-compact-condition">
        <b>{_e(POSITION["condition"])}</b>
        <span>{_e(POSITION["status"])} {_e(POSITION["pnl"])} · {_e(POSITION["subtitle"])}</span>
      </div>
      <div class="xi-compact-decision">
        <strong>{_e(POSITION["decision"])}</strong>
        <span>Sell {_e(POSITION["sell_zone"])} or exit {_e(POSITION["exit_level"])} · {_e(POSITION["closes"])}</span>
      </div>
      <div class="xi-compact-chevron"><svg viewBox="0 0 24 24"><path d="m7 10 5 5 5-5z"/></svg></div>
    </summary>

    <div class="xi-expanded">
      <div class="xi-position">
        {_metric("Entry Price", POSITION["entry"])}
        {_metric("Current Price", POSITION["current"], POSITION["pnl"], "red")}
        {_metric("Position Size", POSITION["size"], POSITION["leverage"])}
        {_metric("Liquidation", POSITION["liquidation"], "7.0% away", "amber")}
        {_metric("Time Window", POSITION["time_window"], "until next key event")}
      </div>

      <div class="xi-grid">
        <div class="xi-panel">
          <div class="xi-panel-title">Price Ladder <small>Current price {_e(POSITION["current"])}</small></div>
          <div class="xi-ladder">{ladder_html}</div>
        </div>
        <div style="display:grid;gap:14px;align-content:start;">
          <div class="xi-panel">
            <div class="xi-panel-title">Active Orders <small>Standing plan</small></div>
            <div class="xi-orders">{orders_html}</div>
          </div>
          <div class="xi-panel">
            <div class="xi-panel-title">Why 35?</div>
            <div class="xi-reasons">{reasons_html}</div>
          </div>
        </div>
      </div>

      <div class="xi-panel" style="margin-top:14px;">
        <div class="xi-panel-title">Market Health <small>Last 72h</small></div>
        <div class="xi-health">{health_html}</div>
      </div>

      <div class="xi-bottom">
        <div class="xi-panel">
          <div class="xi-panel-title">Time Stop</div>
          <div class="xi-metric" style="border:0;padding:0;"><b class="red">0 / 3 bars used</b><small>Reclaim of 0.0065 required by 11 Jul 2026. On expiry: exit on whatever strength appears.</small></div>
        </div>
        <div class="xi-panel">
          <div class="xi-panel-title">Key Events</div>
          <div class="xi-order"><span>14 Jul</span><b>US CPI</b><small>6 days</small></div>
          <div class="xi-order" style="margin-top:9px;"><span>25 Jul</span><b>ALT Unlock<br><small class="muted">240M ALT, 2.4% supply</small></b><small>17 days</small></div>
        </div>
      </div>

      <div class="xi-plan">
        <div class="xi-plan-icon"><svg viewBox="0 0 24 24"><path d="M12 3 2 21h20L12 3zm1 14h-2v-2h2v2zm0-4h-2V8h2v5z"/></svg></div>
        <b>The Plan</b>
        <span>Sell 0.0065-0.0066. Dead below 0.0062. Fix leverage now. Manage actively.</span>
        <button>Manage Position</button>
      </div>
    </div>
  </details>
</div>
"""

st.markdown("".join(line.strip() for line in card_html.splitlines()), unsafe_allow_html=True)
