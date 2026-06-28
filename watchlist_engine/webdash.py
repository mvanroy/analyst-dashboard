#!/usr/bin/env python3
"""
Web Dashboard Server — Trade Scanner (Leaderboard Edition)
============================================================
Serves a live leaderboard at http://localhost:3000
Each row = one trade setup, ranked by score. Chevron expands deep-dive.

Usage:
  python3 webdash.py              # port 3000
  python3 webdash.py --port 9090
"""
import os, sys, json, time, argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import numpy as np

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE = {"data": None, "ts": 0, "ttl": 300}


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def run_scan():
    from .config import WATCHLIST, SYMBOL_LABELS
    from .data import fetch_all_data
    from .patterns import detect_all, PATTERNS
    from .state_tracker import _load_state

    rows = []
    errors = []

    for symbol in WATCHLIST:
        label = SYMBOL_LABELS.get(symbol, symbol.replace("/USDT:USDT", ""))
        try:
            data = fetch_all_data(symbol)
            if data.get("error"):
                errors.append({"coin": label, "error": data["error"]})
                continue
            setups = detect_all(data)
            ticker = data.get("ticker", {})
            oi = data.get("oi", 0)
            funding = data.get("funding", 0)

            for s in setups:
                entry = s.get("entry", {})
                zone = entry.get("zone", {})
                stop = entry.get("stop", {})
                t1 = entry.get("t1", {})
                t2 = entry.get("t2", {})
                cf = s.get("confluence", {})
                debug = s.get("debug", {})

                # Build score breakdown for deep-dive
                score_breakdown = []
                for key, val in debug.items():
                    if key == "total" or not isinstance(val, dict):
                        continue
                    score_breakdown.append({
                        "label": key.replace("_", " ").title(),
                        "score": val.get("score", 0),
                        "max": val.get("max", 0),
                        "pass": val.get("pass", False),
                        "text": val.get("text", ""),
                        "checks": val.get("checks", []),
                    })

                # Best R:R
                rr_str = ""
                t2_rr = t2.get("rr", "") if isinstance(t2, dict) else ""
                t1_rr = t1.get("rr", "") if isinstance(t1, dict) else ""
                for rr in [t2_rr, t1_rr]:
                    if ":" in rr:
                        try:
                            val_f = float(rr.split(":")[1].strip())
                            if val_f >= 0.5:
                                rr_str = f"1:{val_f:.1f}"
                                break
                        except:
                            pass

                rows.append({
                    "coin": label,
                    "symbol": symbol,
                    "price": ticker.get("last", 0),
                    "high24h": ticker.get("high", 0),
                    "low24h": ticker.get("low", 0),
                    "volume24h": ticker.get("baseVolume", 0),
                    "oi": oi,
                    "funding": funding,
                    "order_book": data.get("order_book"),
                    "cvd": data.get("cvd"),
                    "pattern": s.get("name", ""),
                    "direction": s.get("direction", ""),
                    "grade": s.get("grade", ""),
                    "maturity": s.get("maturity", ""),
                    "score": s.get("score", 0),
                    "max_score": s.get("max_score", 11),
                    "confidence": s.get("success_likelihood", {}).get("percent", 0),
                    "entry_low": zone.get("low"),
                    "entry_high": zone.get("high"),
                    "stop": stop.get("value") if isinstance(stop, dict) else stop,
                    "stop_note": stop.get("note", "") if isinstance(stop, dict) else "",
                    "t1": t1.get("value") if isinstance(t1, dict) else t1,
                    "t1_rr": t1_rr,
                    "t2": t2.get("value") if isinstance(t2, dict) else t2,
                    "t2_rr": t2_rr,
                    "rr": rr_str,
                    "risk": entry.get("risk", 0),
                    "score_breakdown": score_breakdown,
                    "evidence": s.get("evidence", []),
                    "missing": s.get("missing", []),
                    "warnings": cf.get("warnings", []) if cf else [],
                    "confluence_strength": cf.get("strength", "") if cf else "",
                    "cvd_analysis": s.get("cvd_analysis"),
                })
        except Exception as e:
            errors.append({"coin": label, "error": str(e)})

    # Sort by score descending, then by grade
    rows.sort(key=lambda r: ({"A": 3, "B": 2, "C": 1}.get(r["grade"], 0), r["score"]), reverse=True)

    state = _load_state()
    last_scan = state.get("_meta", {}).get("last_scan", time.time())

    return {
        "rows": rows,
        "errors": errors,
        "total_setups": len(rows),
        "total_coins": len(set(r["coin"] for r in rows)),
        "last_scan": last_scan,
        "generated_at": time.time(),
    }


def get_data():
    now = time.time()
    if now - CACHE["ts"] > CACHE["ttl"] or CACHE["data"] is None:
        CACHE["data"] = run_scan()
        CACHE["ts"] = now
    return CACHE["data"]


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trade Leaderboard</title>
<style>
  :root {
    --bg:       #0a0d14;
    --surface:  #0f1320;
    --surface2: #141827;
    --border:   #1e2540;
    --border2:  #252d45;
    --text:     #e8eaf6;
    --muted:    #5c6480;
    --accent:   #4f6ef7;
    --green:    #00c896;
    --green-bg: #00c89618;
    --red:      #f04b5e;
    --red-bg:   #f04b5e18;
    --gold:     #f5c542;
    --amber:    #f0a030;
    --blue:     #4f6ef7;
    --purple:   #9b72f5;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 24px 20px 40px;
  }

  /* ── HEADER ─────────────────────────────── */
  .header {
    max-width: 900px; margin: 0 auto 28px;
    display: flex; justify-content: space-between; align-items: flex-start;
  }
  .header-left h1 {
    font-size: 22px; font-weight: 700; letter-spacing: -0.3px;
    background: linear-gradient(135deg, #a0b4ff, #c8b0ff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .header-left .subtitle { color: var(--muted); font-size: 13px; margin-top: 4px; }
  .stat-pills { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
  .stat-pill {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; padding: 4px 12px; font-size: 12px; color: var(--muted);
  }
  .stat-pill strong { color: var(--text); }
  .header-right { text-align: right; }
  .refresh-btn {
    background: var(--surface); border: 1px solid var(--border2);
    color: var(--text); padding: 7px 16px; border-radius: 8px;
    cursor: pointer; font-size: 13px; transition: all 0.15s;
  }
  .refresh-btn:hover { background: var(--border2); }
  .scan-time { color: var(--muted); font-size: 12px; margin-top: 6px; }

  /* ── COLUMN HEADERS ─────────────────────── */
  .col-headers {
    max-width: 900px; margin: 0 auto 8px;
    display: grid;
    grid-template-columns: 36px 1fr 90px 90px 80px 80px 36px;
    gap: 0 12px;
    padding: 0 16px;
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.6px; color: var(--muted);
  }

  /* ── LEADERBOARD ────────────────────────── */
  .leaderboard { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 6px; }

  .row-wrap { border-radius: 12px; overflow: hidden; border: 1px solid var(--border); transition: border-color 0.2s; }
  .row-wrap:hover { border-color: var(--border2); }
  .row-wrap.expanded { border-color: var(--accent); }

  .row {
    background: var(--surface);
    display: grid;
    grid-template-columns: 36px 1fr 90px 90px 80px 80px 36px;
    gap: 0 12px;
    align-items: center;
    padding: 13px 16px;
    cursor: pointer;
    user-select: none;
    transition: background 0.15s;
  }
  .row:hover { background: var(--surface2); }

  /* rank */
  .rank {
    font-size: 13px; font-weight: 700; text-align: center;
    color: var(--muted); line-height: 1;
  }
  .rank.r1 { color: #f5c542; }
  .rank.r2 { color: #c0c0c0; }
  .rank.r3 { color: #cd7f32; }

  /* coin + pattern */
  .coin-cell { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .coin-top { display: flex; align-items: center; gap: 8px; }
  .dir-pill {
    font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
    padding: 2px 8px; border-radius: 4px;
  }
  .dir-short { background: var(--red-bg); color: var(--red); border: 1px solid #f04b5e30; }
  .dir-long  { background: var(--green-bg); color: var(--green); border: 1px solid #00c89630; }
  .coin-name { font-size: 15px; font-weight: 700; color: var(--text); }
  .pattern-name { font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mobile-badges { display: none; }

  /* grade */
  .grade-cell { text-align: center; }
  .grade-badge {
    display: inline-block; font-size: 13px; font-weight: 700;
    padding: 3px 10px; border-radius: 6px; min-width: 36px; text-align: center;
  }
  .grade-A { background: linear-gradient(135deg, #00c89622, #00c89610); color: #00c896; border: 1px solid #00c89635; }
  .grade-B { background: linear-gradient(135deg, #f0a03022, #f0a03010); color: #f0a030; border: 1px solid #f0a03035; }
  .grade-C { background: linear-gradient(135deg, #f04b5e22, #f04b5e10); color: #f04b5e; border: 1px solid #f04b5e35; }

  /* maturity */
  .maturity-cell { text-align: center; }
  .mat-badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 6px;
  }
  .mat-ready   { background: #00c89618; color: #00c896; border: 1px solid #00c89630; }
  .mat-forming { background: #f0a03018; color: #f0a030; border: 1px solid #f0a03030; }
  .mat-nascent { background: #4f6ef718; color: #4f6ef7; border: 1px solid #4f6ef730; }

  /* score bar */
  .score-cell { display: flex; flex-direction: column; gap: 4px; }
  .score-label { font-size: 11px; color: var(--muted); text-align: right; }
  .score-bar-bg { height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; }
  .score-bar-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #4f6ef7, #9b72f5); transition: width 0.4s ease; }

  /* rr */
  .rr-cell { text-align: center; }
  .rr-value { font-size: 14px; font-weight: 700; color: var(--text); }
  .rr-label { font-size: 10px; color: var(--muted); }

  /* chevron */
  .chevron {
    display: flex; align-items: center; justify-content: center;
    color: var(--muted); transition: transform 0.25s ease;
  }
  .chevron svg { width: 16px; height: 16px; }
  .expanded .chevron { transform: rotate(180deg); color: var(--accent); }

  /* ── EXPANDED DRAWER ────────────────────── */
  .drawer {
    background: var(--surface2);
    border-top: 1px solid var(--border);
    display: none;
    padding: 20px;
  }
  .drawer.open { display: block; }

  .drawer-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 640px) { .drawer-grid { grid-template-columns: 1fr; } }

  .drawer-section { margin-bottom: 16px; }
  .drawer-section h4 {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--muted); margin-bottom: 10px;
    padding-bottom: 6px; border-bottom: 1px solid var(--border);
  }

  /* trade plan */
  .trade-plan { display: flex; flex-direction: column; gap: 6px; }
  .plan-row {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 13px;
  }
  .plan-label { color: var(--muted); }
  .plan-value { font-weight: 600; color: var(--text); font-family: 'SF Mono', 'Fira Code', monospace; font-size: 13px; }
  .plan-value.entry { color: var(--accent); }
  .plan-value.stop  { color: var(--red); }
  .plan-value.tp1   { color: #56cfb2; }
  .plan-value.tp2   { color: var(--green); }

  /* score breakdown */
  .breakdown-row {
    display: flex; align-items: center; gap: 8px;
    font-size: 12px; margin-bottom: 6px;
  }
  .bd-icon { width: 16px; text-align: center; flex-shrink: 0; }
  .bd-label { color: var(--muted); flex: 1; }
  .bd-score { font-weight: 600; font-size: 12px; min-width: 32px; text-align: right; }
  .bd-score.pass { color: var(--green); }
  .bd-score.fail { color: var(--red); }
  .bd-text { font-size: 11px; color: var(--muted); padding-left: 24px; margin-bottom: 4px; }

  /* evidence / missing */
  .evidence-list { list-style: none; display: flex; flex-direction: column; gap: 4px; }
  .evidence-list li { font-size: 12px; display: flex; align-items: flex-start; gap: 6px; }
  .evidence-list li.ok  { color: #56cfb2; }
  .evidence-list li.bad { color: #f04b5e; }
  .evidence-list li.warn { color: #f0a030; }

  /* market context */
  .ctx-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .ctx-item { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; }
  .ctx-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .ctx-value { font-size: 14px; font-weight: 600; color: var(--text); margin-top: 2px; font-family: 'SF Mono', 'Fira Code', monospace; }
  .ctx-value.positive { color: var(--green); }
  .ctx-value.negative { color: var(--red); }

  /* loading / empty */
  .loading { text-align: center; padding: 60px 20px; color: var(--muted); font-size: 15px; }
  .pulse { animation: pulse 1.5s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

  /* misc */
  .error-banner {
    max-width: 900px; margin: 0 auto 12px;
    background: #f04b5e15; border: 1px solid #f04b5e30;
    border-radius: 8px; padding: 10px 16px; font-size: 13px; color: #f04b5e;
  }
  @media (max-width: 640px) {
    .col-headers { display: none; }
    .header { flex-direction: column; gap: 12px; }
    .header-right { text-align: left; width: 100%; display: flex; justify-content: space-between; align-items: center; }
    .row {
      grid-template-columns: 28px 1fr 28px;
      gap: 4px 8px;
      padding: 10px 12px;
    }
    .rank { font-size: 11px; }
    .coin-top { flex-wrap: wrap; gap: 4px; }
    .coin-name { font-size: 14px; }
    .dir-pill { font-size: 9px; padding: 1px 6px; }
    .pattern-name { font-size: 11px; margin-bottom: 4px; }
    .grade-cell, .maturity-cell, .score-cell, .rr-cell { display: none !important; }
    .mobile-badges { display: flex !important; gap: 4px; flex-wrap: wrap; }
    .mobile-badge {
      font-size: 9px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
      display: inline-flex; align-items: center; gap: 2px;
    }
    .mb-grade-A { background: #00c89622; color: #00c896; border: 1px solid #00c89635; }
    .mb-grade-B { background: #f0a03022; color: #f0a030; border: 1px solid #f0a03035; }
    .mb-grade-C { background: #f04b5e22; color: #f04b5e; border: 1px solid #f04b5e35; }
    .mb-ready   { background: #00c89618; color: #00c896; border: 1px solid #00c89630; }
    .mb-forming { background: #f0a03018; color: #f0a030; border: 1px solid #f0a03030; }
    .mb-nascent { background: #4f6ef718; color: #4f6ef7; border: 1px solid #4f6ef730; }
    .mb-score { background: #252840; color: #8a8fad; border: 1px solid #30363d; }
    .row-wrap { border-radius: 10px; }
    .drawer { padding: 14px; }
    .drawer-grid { grid-template-columns: 1fr; gap: 12px; }
    .stat-pills { gap: 4px; }
    .stat-pill { font-size: 11px; padding: 3px 8px; }
    body { padding: 12px 10px 24px; }
    .header { margin-bottom: 16px; }
    .leaderboard { gap: 4px; }
  }
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>🏆 Trade Leaderboard</h1>
    <div class="subtitle">Ranked by setup quality · Melbourne time</div>
    <div class="stat-pills" id="statPills">
      <div class="stat-pill pulse">Scanning...</div>
    </div>
  </div>
  <div class="header-right">
    <button class="refresh-btn" onclick="refreshData()">⟳ Refresh</button>
    <div class="scan-time" id="scanTime"></div>
  </div>
</div>

<div class="col-headers">
  <span>#</span>
  <span>Opportunity</span>
  <span style="text-align:center">Grade</span>
  <span style="text-align:center">Maturity</span>
  <span>Score</span>
  <span style="text-align:center">R:R</span>
  <span></span>
</div>

<div id="errorContainer"></div>
<div class="leaderboard" id="leaderboard">
  <div class="loading pulse">⟳ Scanning markets...</div>
</div>

<script>
const TZ = 'Australia/Melbourne';

async function loadData() {
  try {
    const r = await fetch('/api/data');
    const d = await r.json();
    render(d);
  } catch(e) {
    document.getElementById('leaderboard').innerHTML =
      '<div class="loading">⚠ Failed to load data</div>';
  }
}

async function refreshData() {
  const btn = document.querySelector('.refresh-btn');
  btn.textContent = '⟳ Scanning...';
  btn.disabled = true;
  try {
    await fetch('/api/refresh');
  } catch(e) {}
  await loadData();
  btn.textContent = '⟳ Refresh';
  btn.disabled = false;
}

function render(d) {
  const ls = new Date(d.last_scan * 1000);
  const timeStr = ls.toLocaleTimeString('en-AU', {timeZone: TZ, hour: '2-digit', minute: '2-digit'});

  document.getElementById('statPills').innerHTML =
    `<div class="stat-pill"><strong>${d.total_setups}</strong> setups</div>` +
    `<div class="stat-pill"><strong>${d.total_coins}</strong> coins</div>` +
    `<div class="stat-pill">Refreshes every 10m</div>`;

  document.getElementById('scanTime').textContent = `Last scan: ${timeStr} AEST`;

  const ec = document.getElementById('errorContainer');
  ec.innerHTML = d.errors.map(e =>
    `<div class="error-banner">⚠ ${e.coin}: ${e.error}</div>`
  ).join('');

  const lb = document.getElementById('leaderboard');
  if (!d.rows || d.rows.length === 0) {
    lb.innerHTML = '<div class="loading">No setups found in current scan.</div>';
    return;
  }

  lb.innerHTML = d.rows.map((row, i) => buildRow(row, i)).join('');
}

function buildRow(r, i) {
  const rank = i + 1;
  const rankClass = rank <= 3 ? ` r${rank}` : '';
  const rankLabel = rank <= 3
    ? ['🥇','🥈','🥉'][rank-1]
    : rank;

  const dirClass = r.direction === 'short' ? 'dir-short' : 'dir-long';
  const dirLabel = r.direction === 'short' ? '↓ SHORT' : '↑ LONG';

  const gradeClass = `grade-${r.grade}`;

  const matClass = {Ready:'mat-ready', Forming:'mat-forming', Nascent:'mat-nascent'}[r.maturity] || 'mat-nascent';
  const matIcon  = {Ready:'✅', Forming:'⏳', Nascent:'🔹'}[r.maturity] || '';

  const scorePct = r.max_score > 0 ? Math.round((r.score / r.max_score) * 100) : 0;

  const rrDisp = r.rr || '—';

  const entryStr = r.entry_low && r.entry_high
    ? `${fmtP(r.entry_low)} – ${fmtP(r.entry_high)}`
    : '—';

  const drawer = buildDrawer(r);

  return `
  <div class="row-wrap" id="wrap-${i}">
    <div class="row" onclick="toggle(${i})">
      <div class="rank${rankClass}">${rankLabel}</div>
      <div class="coin-cell">
        <div class="coin-top">
          <span class="dir-pill ${dirClass}">${dirLabel}</span>
          <span class="coin-name">${r.coin}</span>
          <span style="font-size:13px;color:var(--muted);font-family:monospace">${fmtP(r.price)}</span>
        </div>
        <div class="pattern-name">${r.pattern}</div>
        <div class="mobile-badges">
          <span class="mobile-badge mb-grade-${r.grade}">${r.grade}</span>
          <span class="mobile-badge mb-${r.maturity.toLowerCase()}">${matIcon} ${r.maturity}</span>
          <span class="mobile-badge mb-score">${r.score}/${r.max_score}</span>
        </div>
      </div>
      <div class="grade-cell">
        <span class="grade-badge ${gradeClass}">${r.grade}</span>
      </div>
      <div class="maturity-cell">
        <span class="mat-badge ${matClass}">${matIcon} ${r.maturity}</span>
      </div>
      <div class="score-cell">
        <div class="score-label">${r.score}/${r.max_score}</div>
        <div class="score-bar-bg"><div class="score-bar-fill" style="width:${scorePct}%"></div></div>
      </div>
      <div class="rr-cell">
        <div class="rr-value">${rrDisp}</div>
        <div class="rr-label">R:R</div>
      </div>
      <div class="chevron">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </div>
    </div>
    <div class="drawer" id="drawer-${i}">${drawer}</div>
  </div>`;
}

function buildDrawer(r) {
  // ── Trade Plan ──────────────────────────────────────────
  const planRows = [];
  if (r.entry_low && r.entry_high)
    planRows.push(`<div class="plan-row"><span class="plan-label">Entry Zone</span><span class="plan-value entry">${fmtP(r.entry_low)} – ${fmtP(r.entry_high)}</span></div>`);
  if (r.stop)
    planRows.push(`<div class="plan-row"><span class="plan-label">Stop Loss</span><span class="plan-value stop">${fmtP(r.stop)}</span></div>`);
  if (r.t1)
    planRows.push(`<div class="plan-row"><span class="plan-label">Take Profit 1</span><span class="plan-value tp1">${fmtP(r.t1)} <small style="color:var(--muted)">${r.t1_rr}</small></span></div>`);
  if (r.t2)
    planRows.push(`<div class="plan-row"><span class="plan-label">Take Profit 2</span><span class="plan-value tp2">${fmtP(r.t2)} <small style="color:var(--muted)">${r.t2_rr}</small></span></div>`);
  if (r.risk)
    planRows.push(`<div class="plan-row"><span class="plan-label">Risk / Unit</span><span class="plan-value">${fmtP(Math.abs(r.risk))}</span></div>`);
  if (r.confidence)
    planRows.push(`<div class="plan-row"><span class="plan-label">Confidence</span><span class="plan-value">${r.confidence}%</span></div>`);

  // ── Score Breakdown ─────────────────────────────────────
  const bdRows = (r.score_breakdown || []).map(b => {
    const passIcon = b.pass ? '✅' : '❌';
    const scoreClass = b.score > 0 ? 'pass' : 'fail';
    let html = `<div class="breakdown-row">
      <span class="bd-icon">${passIcon}</span>
      <span class="bd-label">${b.label}</span>
      <span class="bd-score ${scoreClass}">${b.score}/${b.max}</span>
    </div>`;
    if (b.text) html += `<div class="bd-text">${b.text}</div>`;
    if (b.checks && b.checks.length) {
      b.checks.forEach(ch => {
        const ci = ch.pass ? '✓' : '✗';
        const cc = ch.pass ? '#56cfb2' : '#666';
        html += `<div class="bd-text" style="color:${cc}">${ci} ${ch.text}</div>`;
      });
    }
    return html;
  }).join('');

  // ── Evidence & Missing ──────────────────────────────────
  const evidence = (r.evidence || []).map(e =>
    `<li class="ok">✓ ${e}</li>`).join('');
  const missing = (r.missing || []).map(m =>
    `<li class="bad">✗ ${m}</li>`).join('');
  const warnings = (r.warnings || []).map(w =>
    `<li class="warn">⚠ ${w}</li>`).join('');

  // ── Market Context ──────────────────────────────────────
  const fundingColour = r.funding > 0 ? 'positive' : r.funding < 0 ? 'negative' : '';
  const fundingSign   = r.funding > 0 ? '+' : '';
  
  // CVD display
  let cvdHtml = '<div class="ctx-item"><div class="ctx-label">CVD</div><div class="ctx-value">—</div></div>';
  if (r.cvd && !r.cvd.error) {
    const cvdSignal = r.cvd.cvd_signal;
    const cvdColour = cvdSignal === 'bullish' ? 'positive' : cvdSignal === 'bearish' ? 'negative' : '';
    const cvdIcon = cvdSignal === 'bullish' ? '🟢' : cvdSignal === 'bearish' ? '🔴' : '⚪';
    cvdHtml = `<div class="ctx-item"><div class="ctx-label">CVD (5m)</div><div class="ctx-value ${cvdColour}">${cvdIcon} ${r.cvd.taker_buy_pct}% buy</div></div>`;
  }
  
  // CVD Divergence analysis (from cvd_divergence pattern)
  let cvdDivHtml = '';
  if (r.cvd_analysis && r.cvd_analysis.detected) {
    const divSignal = r.cvd_analysis.signal || '';
    const divNote = r.cvd_analysis.note || '';
    const divIcon = divSignal.includes('bullish') ? '🟢' : '🔴';
    const divColour = divSignal.includes('bullish') ? 'positive' : 'negative';
    cvdDivHtml = `<div class="ctx-item" style="grid-column:span 2;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 10px">
      <div class="ctx-label">CVD Divergence — ${divIcon} <span style="color:var(--${divColour})">${divSignal}</span></div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px">${divNote}</div>
      <div style="display:flex;gap:10px;margin-top:4px;font-size:10px;color:var(--muted)">
        <span>Net CVD: ${r.cvd_analysis.net_cvd || 0}</span>
        <span>Trend: ${r.cvd_analysis.cvd_trend_pct || 0}%</span>
      </div>
    </div>`;
  }

  // Order Book display with volume clusters
    let obHtml = '<div class="ctx-item" style="grid-column:span 2"><div class="ctx-label">Order Book</div><div class="ctx-value">—</div></div>';
    if (r.order_book && !r.order_book.error) {
      const obSignal = r.order_book.order_book_imbalance;
      const obColour = obSignal === 'bullish' ? 'positive' : obSignal === 'bearish' ? 'negative' : '';
      const obIcon = obSignal === 'bullish' ? '🟢' : obSignal === 'bearish' ? '🔴' : '⚪';
      const clusters = r.order_book.clusters || {};
      const bids = clusters.bid_clusters || [];
      const asks = clusters.ask_clusters || [];
    
      // Build depth bars
      let depthHtml = '<div style="margin-top:6px">';
      // Ask (sell) side - above price
      if (asks.length) {
        depthHtml += '<div style="font-size:10px;color:#f04b5e;margin-bottom:2px;font-weight:600">SELL WALLS (asks)</div>';
        asks.slice(0,4).forEach(a => {
          depthHtml += `<div style="display:flex;align-items:center;gap:4px;margin-bottom:2px">
            <span style="font-size:10px;color:var(--muted);min-width:55px;text-align:right;font-family:monospace">$${fmtShort(a.price)}</span>
            <div style="flex:1;height:10px;background:#1a1a2e;border-radius:3px;overflow:hidden">
              <div style="height:100%;width:${a.bar_width}%;background:#f04b5e;border-radius:3px;opacity:0.7"></div>
            </div>
            <span style="font-size:9px;color:var(--muted);min-width:30px;text-align:right">(${a.distance_pct}%)</span>
          </div>`;
        });
      }
      // Bid (buy) side - below price
      if (bids.length) {
        depthHtml += '<div style="font-size:10px;color:#00c896;margin-top:4px;margin-bottom:2px;font-weight:600">BUY WALLS (bids)</div>';
        bids.slice(0,4).forEach(b => {
          depthHtml += `<div style="display:flex;align-items:center;gap:4px;margin-bottom:2px">
            <span style="font-size:10px;color:var(--muted);min-width:55px;text-align:right;font-family:monospace">$${fmtShort(b.price)}</span>
            <div style="flex:1;height:10px;background:#1a1a2e;border-radius:3px;overflow:hidden">
              <div style="height:100%;width:${b.bar_width}%;background:#00c896;border-radius:3px;opacity:0.7"></div>
            </div>
            <span style="font-size:9px;color:var(--muted);min-width:30px;text-align:right">(${b.distance_pct}%)</span>
          </div>`;
        });
      }
      depthHtml += '</div>';
    
      obHtml = `<div class="ctx-item" style="grid-column:span 2">
        <div class="ctx-label">Order Book — ${obIcon} ${obSignal} (ratio ${r.order_book.bid_ask_ratio})</div>
        ${depthHtml}
      </div>`;
    }

  const ctx = `
    <div class="ctx-grid" style="grid-template-columns:1fr 1fr">
      <div class="ctx-item"><div class="ctx-label">Price</div><div class="ctx-value">${fmtP(r.price)}</div></div>
      <div class="ctx-item"><div class="ctx-label">OI</div><div class="ctx-value">${r.oi ? '$' + (r.oi/1e6).toFixed(1) + 'M' : '—'}</div></div>
      <div class="ctx-item"><div class="ctx-label">Funding</div><div class="ctx-value ${fundingColour}">${r.funding != null ? fundingSign + r.funding.toFixed(4) + '%' : '—'}</div></div>
      <div class="ctx-item"><div class="ctx-label">24H Range</div><div class="ctx-value">${fmtP(r.low24h)}–${fmtP(r.high24h)}</div></div>
      ${cvdHtml}
           ${cvdDivHtml}
           ${obHtml}
    </div>`;

  return `
  <div class="drawer-grid">
    <div>
      <div class="drawer-section">
        <h4>Trade Plan</h4>
        <div class="trade-plan">${planRows.join('') || '<span style="color:var(--muted);font-size:13px">No entry calculated</span>'}</div>
      </div>
      <div class="drawer-section">
        <h4>Market Context</h4>
        ${ctx}
      </div>
    </div>
    <div>
      <div class="drawer-section">
        <h4>Score Breakdown</h4>
        ${bdRows || '<span style="color:var(--muted);font-size:13px">No breakdown available</span>'}
      </div>
      ${evidence || missing || warnings ? `
      <div class="drawer-section">
        <h4>Evidence & Gaps</h4>
        <ul class="evidence-list">
          ${evidence}${missing}${warnings}
        </ul>
      </div>` : ''}
    </div>
  </div>`;
}

function toggle(i) {
  const wrap   = document.getElementById(`wrap-${i}`);
  const drawer = document.getElementById(`drawer-${i}`);
  const isOpen = drawer.classList.contains('open');
  drawer.classList.toggle('open', !isOpen);
  wrap.classList.toggle('expanded', !isOpen);
}

function fmtP(p) {
  if (p == null || isNaN(p)) return '—';
  if (p >= 1000) return '$' + p.toFixed(0);
  if (p >= 100)  return '$' + p.toFixed(2);
  if (p >= 1)    return '$' + p.toFixed(3);
  return '$' + p.toFixed(4);
}
function fmtShort(p) {
  if (p == null || isNaN(p)) return '—';
  if (p >= 1000) return p.toFixed(0);
  if (p >= 100)  return p.toFixed(2);
  if (p >= 1)    return p.toFixed(3);
  return p.toFixed(4);
}

loadData();
setInterval(loadData, 600000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

        elif path == "/api/data":
            data = get_data()
            payload = json.dumps(data, cls=NumpyEncoder).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        elif path == "/api/refresh":
            # Force clear cache and run fresh scan
            global CACHE
            CACHE["data"] = None
            CACHE["ts"] = 0
            # Update last_scan timestamp in state
            state_path = os.path.join(DASHBOARD_DIR, "state", "scanner_state.json")
            try:
                with open(state_path) as f:
                    st = json.load(f)
            except:
                st = {}
            if "_meta" not in st:
                st["_meta"] = {}
            st["_meta"]["last_scan"] = time.time()
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(st, f)
            data = get_data()
            payload = json.dumps({"status": "ok", "setups": len(data["rows"]), "coins": data["total_coins"]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404")

    def log_message(self, fmt, *args):
        if "/api/data" in str(args):
            return
        super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=3000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"🏆 Trade Leaderboard running at http://localhost:{args.port}")
    print(f"   Cache TTL: {CACHE['ttl']}s · Auto-refresh: 10m")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
