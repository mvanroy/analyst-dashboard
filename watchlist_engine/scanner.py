"""
Trade Setup Scanner — Main Entry Point
========================================
Scans all coins on watchlist, runs pattern detectors, compares against
previous state, and outputs alerts to stdout.

Cron-friendly: outputs nothing when no new setups (silent cycle).
Outputs formatted alert messages when there are new/matured setups.
"""
import sys
import traceback
from typing import List, Dict, Any

from .config import WATCHLIST, SYMBOL_LABELS, STATE_FILE
from .data import fetch_all_data, fetch_btc_data, calc_correlation
from .patterns import detect_all
from .state_tracker import compute_actions


def label_for(symbol: str) -> str:
    """Get short display label for a symbol."""
    return SYMBOL_LABELS.get(symbol, symbol.replace("/USDT:USDT", ""))


def format_alert(setup: Dict[str, Any], symbol_label: str) -> str:
    """
    Format a setup as a human-readable Telegram alert message.
    """
    event = setup.get('event', '')
    direction = setup.get('direction', '')
    grade = setup.get('grade', '')
    maturity = setup.get('maturity', '')
    name = setup.get('name', 'Setup')
    entry = setup.get('entry', {})

    # ─── Header ──────────────────────────────────────────────────────
    emoji_dir = "🔴" if direction == "short" else "🟢"
    emoji_event = "🆕" if event == 'new' else "🔄"
    grade_stars = "⭐" if grade == 'A' else "✦" if grade == 'B' else "•"
    
    lines = []

    if event == 'invalidated':
        lines.append(f"🚫 **{symbol_label} — {setup.get('name', 'Setup')} Invalidated**")
        lines.append(f"")
        lines.append(f"✅ Setup no longer in play — removed from watchlist.")
        return "\n".join(lines)

    lines.append(f"{emoji_event} {emoji_dir} **{symbol_label} {direction.upper()}** {grade_stars} Grade-{grade}")
    lines.append(f"**{name}**")
    lines.append(f"`Status: {maturity}`")

    # ─── Price ───────────────────────────────────────────────────────
    price = setup.get('price', 0)
    if price:
        lines.append(f"`Current: ${price:.4f}`")

    # ─── Entry Zone ──────────────────────────────────────────────────
    ez = entry.get('zone', {})
    if ez.get('low') and ez.get('high'):
        lines.append(f"")
        lines.append(f"**Entry Zone:** `${ez['low']:.4f}` – `${ez['high']:.4f}`")
    
    # ─── Stop + Targets ──────────────────────────────────────────────
    stop = entry.get('stop', {})
    t1 = entry.get('t1', {})
    t2 = entry.get('t2', {})

    if stop.get('value'):
        lines.append(f"**Stop:** `${stop['value']:.4f}` — {stop.get('note', '')}")
    if t1.get('value'):
        rr = t1.get('rr', '')
        lines.append(f"**TP1:** `${t1['value']:.4f}` {f'(R:R {rr})' if rr else ''}")
    if t2.get('value'):
        rr = t2.get('rr', '')
        lines.append(f"**TP2:** `${t2['value']:.4f}` {f'(R:R {rr})' if rr else ''}")

    # ─── Score / Conviction ──────────────────────────────────────────
    score = setup.get('score', 0)
    max_score = setup.get('max_score', 10)
    likelihood = setup.get('success_likelihood', {}).get('percent', '')
    lines.append(f"")
    lines.append(f"`Score: {score}/{max_score} — ~{likelihood}% confidence`")

    # ─── Confluence ──────────────────────────────────────────────────
    confluence = setup.get('confluence', {})
    strength = confluence.get('strength', '')
    checks = confluence.get('checks', [])
    warns = confluence.get('warnings', [])

    if strength:
        lines.append(f"**Confluence:** {strength}")

    for check in checks[:3]:
        lines.append(f"  ✅ {check[:80]}")
    for warn in warns[:2]:
        lines.append(f"  ⚠️ {warn[:80]}")

    # ─── Missing / Considerations ────────────────────────────────────
    missing = setup.get('missing', [])
    if missing:
        lines.append(f"")
        lines.append(f"**Needs:**")
        for m in missing[:2]:
            lines.append(f"  • {m[:80]}")

    # ─── Evidence Summary ────────────────────────────────────────────
    evidence = setup.get('evidence', [])
    if evidence:
        lines.append(f"")
        lines.append(f"**Evidence:**")
        for e in evidence[:3]:
            lines.append(f"  • {e[:80]}")

    # ─── OI / Funding Summary ────────────────────────────────────────
    oi = setup.get('oi')
    funding = setup.get('funding')
    extra = []
    if oi:
        extra.append(f"OI: ${oi/1e6:.1f}M")
    if funding is not None:
        extra.append(f"Funding: {funding:.4f}%")
    if extra:
        lines.append(f"")
        lines.append(f"`{' | '.join(extra)}`")
    if setup.get('retrace_pct') is not None:
        lines.append(f"`Retrace: {setup['retrace_pct']:.1f}% from low`")

    lines.append(f"")
    lines.append(f"---")
    return "\n".join(lines)


def run_scan() -> List[str]:
    """
    Run a full scan cycle.
    
    Returns a list of alert strings to deliver. Empty list = silent cycle.
    """
    all_setups = []

    # ─── Fetch BTC data for correlation ──────────────────────────────
    btc_data = fetch_btc_data()

    # ─── Scan each coin ──────────────────────────────────────────────
    for symbol in WATCHLIST:
        label = label_for(symbol)
        try:
            data = fetch_all_data(symbol)
            if data.get('error'):
                print(f"[SKIP] {label}: {data['error']}", flush=True)
                continue

            setups = detect_all(data)

            # Attach symbol to each setup for state tracking
            for s in setups:
                s['_symbol'] = symbol
                # Add BTC correlation if available
                if btc_data.get('1h') is not None and data.get('ohlcv_1h') is not None:
                    corr = calc_correlation(data['ohlcv_1h'], btc_data['1h'])
                    s['btc_correlation'] = round(corr, 3)

            all_setups.extend(setups)
            if setups:
                print(f"[SCAN] {label}: {len(setups)} setup(s) — grades: {', '.join(s.get('grade','?') for s in setups)}", flush=True)
            else:
                print(f"[SCAN] {label}: no setups", flush=True)

        except Exception as e:
            print(f"[SCAN ERROR] {label}: {e}", flush=True)
            traceback.print_exc()

    # ─── Compare against previous state ──────────────────────────────
    actions = compute_actions(all_setups)

    if not actions:
        print(f"[STATE] No new alerts — silent cycle", flush=True)
        return []

    # ─── Format alerts ───────────────────────────────────────────────
    alerts = []
    for setup in actions:
        sym = setup.get('_symbol', 'UNKNOWN')
        label = label_for(sym)
        msg = format_alert(setup, label)
        alerts.append(msg)
        print(f"[ALERT] {label}: {setup.get('event', '?')} — {setup.get('name', 'Setup')}", flush=True)

    return alerts


if __name__ == "__main__":
    print(f"═══ Trade Scanner Cycle ═══", flush=True)
    alerts = run_scan()
    
    if alerts:
        print(f"\n——— {len(alerts)} Alert(s) ———", flush=True)
        for alert in alerts:
            print(alert, flush=True)
            print("", flush=True)
    else:
        # Silent cycle — no output to stdout
        pass