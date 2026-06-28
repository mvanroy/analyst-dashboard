"""
Cron Scanner Runner
====================
Runs the full scanner and outputs formatted alerts to stdout.
Designed for no_agent=True cron mode: stdout = Telegram message.
Empty stdout = silent cycle (nothing to report).
"""
import sys, os

from .config import WATCHLIST, SYMBOL_LABELS
from .data import fetch_all_data
from .patterns import detect_all, PATTERNS
from .state_tracker import compute_actions
import numpy as np


def label_for(symbol: str) -> str:
    return SYMBOL_LABELS.get(symbol, symbol.replace("/USDT:USDT", ""))


def format_setup_breakdown(setup: dict, symbol_label: str) -> str:
    """
    Full verbose breakdown for one setup — matches the MNT debug format.
    """
    event = setup.get('event', 'new')
    lines = []

    # ─── FLIP EVENT — special short format ───────────────────────────
    if event == 'flip':
        flip_from = setup.get('flip_from', '').upper()
        flip_to = setup.get('flip_to', '').upper()
        grade = setup.get('grade', '')
        grade_icon = "⭐" if grade == "A" else "✦"
        flip_emoji = "🟢" if flip_to == "LONG" else "🔴"
        lines.append(f"🔄 **{symbol_label} — BIAS FLIP**")
        lines.append(f"   `{flip_from}` → `{flip_to}` {grade_icon} Grade-{grade}")
        lines.append(f"   Pattern: {setup.get('name', '')}")

        price = setup.get('price', 0)
        entry = setup.get('entry', {})
        zone = entry.get('zone', {})
        stop = entry.get('stop', {})
        t1 = entry.get('t1', {})
        t2 = entry.get('t2', {})
        if zone.get('low') and zone.get('high'):
            lines.append(f"   Entry: `${zone['low']:.4f}` – `${zone['high']:.4f}`")
        if stop.get('value') if isinstance(stop, dict) else stop:
            sv = stop['value'] if isinstance(stop, dict) else stop
            lines.append(f"   Stop: `${sv:.4f}`")
        if isinstance(t1, dict) and t1.get('value'):
            lines.append(f"   TP1: `${t1['value']:.4f}`  {t1.get('rr', '')}")
        if isinstance(t2, dict) and t2.get('value'):
            lines.append(f"   TP2: `${t2['value']:.4f}`  {t2.get('rr', '')}")

        con = setup.get('confluence', {})
        if con and isinstance(con, dict):
            for w in con.get('warnings', [])[:2]:
                lines.append(f"   ⚠ {w}")

        lines.append("   ───────────────")
        lines.append(f"   `Previous bias was {flip_from}. Review your position.`")
        return "\n".join(lines)

    # ─── INVALIDATION ────────────────────────────────────────────────
    if event == 'invalidated':
        prev_dir = setup.get('direction', '').upper()
        inv_emoji = "🟢" if prev_dir == "LONG" else "🔴"
        lines.append(f"🚫 **{symbol_label} — SETUP INVALIDATED**")
        lines.append(f"   Previous: {inv_emoji} {prev_dir}")
        lines.append(f"   No active signals remaining for {symbol_label}")
        return "\n".join(lines)

    direction = setup.get('direction', 'short').upper()
    grade = setup.get('grade', '')
    maturity = setup.get('maturity', '')
    debug = setup.get('debug', {})
    entry = setup.get('entry', {})
    price = setup.get('price', 0)

    # ─── Header ──────────────────────────────────────────────────────
    grade_icon = "⭐" if grade == "A" else "✦"
    emoji_dir = "🔴" if direction == "SHORT" else "🟢"
    lines.append(f"{emoji_dir} **{symbol_label} — {direction}** {grade_icon} Grade-{grade} ({maturity})")
    lines.append(f"`Price: ${price:.4f}`")

    # ─── 1. Trend Breakdown ─────────────────────────────────────────
    td = debug.get('trend', {})
    if td:
        lines.append("")
        lines.append(f"**1. TREND ({td.get('score', 0)}/{td.get('max', 3)})**")
        for check in td.get('checks', []):
            icon = "✓" if check.get('pass') else "✗"
            lines.append(f"  {icon} {check.get('text', '')}")

    # ─── 2. Retracement ─────────────────────────────────────────────
    rd = debug.get('retracement', {})
    if rd:
        lines.append("")
        lines.append(f"**2. RETRACEMENT ({rd.get('score', 0)}/{rd.get('max', 2)})**")
        icon = "✓" if rd.get('pass') else "✗"
        lines.append(f"  {icon} {rd.get('text', '')}")

    # ─── 3. Supply Zone ─────────────────────────────────────────────
    sd = debug.get('supply', {})
    if sd:
        lines.append("")
        lines.append(f"**3. SUPPLY ZONE ({sd.get('score', 0)}/{sd.get('max', 2)})**")
        icon = "✓" if sd.get('pass') else "✗"
        lines.append(f"  {icon} {sd.get('text', '')}")

    # ─── 4. OI Confirmation ─────────────────────────────────────────
    od = debug.get('oi', {})
    if od:
        lines.append("")
        lines.append(f"**4. OPEN INTEREST ({od.get('score', 0)}/{od.get('max', 2)})**")
        icon = "✓" if od.get('pass') else "✗"
        lines.append(f"  {icon} {od.get('text', '')}")

    # ─── 5. Funding ─────────────────────────────────────────────────
    fd = debug.get('funding', {})
    if fd:
        lines.append("")
        lines.append(f"**5. FUNDING ({fd.get('score', 0)}/{fd.get('max', 2)})**")
        icon = "✓" if fd.get('pass') else "✗"
        lines.append(f"  {icon} {fd.get('text', '')}")

    # ─── Total ──────────────────────────────────────────────────────
    total = debug.get('total', {})
    if total:
        lines.append("")
        lines.append(f"**TOTAL: {total.get('score', 0)}/{total.get('max', 0)} — Grade {grade}**")
        likelihood = setup.get('success_likelihood', {})
        if likelihood.get('percent'):
            lines.append(f"`Confidence: ~{likelihood['percent']}%`")

    # ─── Entry Details ──────────────────────────────────────────────
    lines.append("")
    lines.append(f"**ENTRY**")
    ez = entry.get('zone', {})
    stop = entry.get('stop', {})
    t1 = entry.get('t1', {})
    t2 = entry.get('t2', {})
    if ez.get('low') and ez.get('high'):
        lines.append(f"  Zone: `${ez['low']:.4f}` – `${ez['high']:.4f}`")
    if stop.get('value'):
        lines.append(f"  Stop: `${stop['value']:.4f}` ({stop.get('note', '')})")
        risk = entry.get('risk', 0)
        lines.append(f"  Risk: `${risk:.4f}` per unit")
    if t1.get('value'):
        rr = t1.get('rr', '')
        lines.append(f"  TP1: `${t1['value']:.4f}` (R:R {rr})")
    if t2.get('value'):
        rr = t2.get('rr', '')
        lines.append(f"  TP2: `${t2['value']:.4f}` (R:R {rr})")

    # ─── OI, Funding, CVD & Order Book ──────────────────────────────
    oi_val = setup.get('oi')
    funding_val = setup.get('funding')
    ob = setup.get('_order_book')
    cvd = setup.get('_cvd')
    extra = []
    if oi_val:
        extra.append(f"OI: `${oi_val/1e6:.1f}M`")
    if funding_val is not None:
        sign = "+" if funding_val > 0 else ""
        extra.append(f"Funding: `{sign}{funding_val:.4f}%`")
    if cvd and not isinstance(cvd, dict) or (isinstance(cvd, dict) and not cvd.get('error')):
        if isinstance(cvd, dict):
            sig = cvd.get('cvd_signal', '?')
            pct = cvd.get('taker_buy_pct', '?')
            emoji = "🟢" if sig == "bullish" else "🔴" if sig == "bearish" else "⚪"
            extra.append(f"CVD: `{emoji} {pct}% buy`")
    if ob and isinstance(ob, dict) and not ob.get('error'):
        sig = ob.get('order_book_imbalance', '?')
        emoji = "🟢" if sig == "bullish" else "🔴" if sig == "bearish" else "⚪"
        cls = ob.get('clusters', {})
        wall_note = ""
        if cls:
            sr = cls.get('strongest_resistance', {})
            ss = cls.get('strongest_support', {})
            if direction == "short" and sr and sr.get('distance_pct', 99) < 2:
                wall_note = f" R @${sr['price']:.2f}"
            elif direction == "long" and ss and ss.get('distance_pct', 99) < 2:
                wall_note = f" S @${ss['price']:.2f}"
        extra.append(f"Book: `{emoji} {sig}{wall_note}`")
    if extra:
        lines.append("")
        lines.append(" | ".join(extra))

    # ─── Confluence & Warnings ──────────────────────────────────────
    confluence = setup.get('confluence', {})
    if confluence.get('warnings'):
        lines.append("")
        lines.append("**⚠️ Warnings:**")
        for w in confluence['warnings'][:2]:
            lines.append(f"  • {w}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def scan_messages(symbol: str = None):
    """Run the scan and return Telegram-ready scanner state-change messages."""
    all_setups = []

    symbols_to_scan = [symbol] if symbol else WATCHLIST

    # Scan each coin — collect silently
    for sym in symbols_to_scan:
        label = label_for(sym)
        try:
            data = fetch_all_data(sym)
            if data.get('error'):
                continue

            setups = detect_all(data)
            ob = data.get('order_book')
            cvd = data.get('cvd')
            for s in setups:
                s['_symbol'] = sym
                s['_order_book'] = ob
                s['_cvd'] = cvd

            all_setups.extend(setups)
        except Exception:
            continue

    # Compare state
    actions = compute_actions(all_setups, skip_invalidation=symbol is not None)

    if not actions:
        return []

    # Format alerts
    alerts_output = []
    for setup in actions:
        sym = setup.get('_symbol', 'UNKNOWN')
        label = label_for(sym)
        msg = format_setup_breakdown(setup, label)
        alerts_output.append(msg)

    return alerts_output


def run_and_report(symbol: str = None):
    """Run the scan and output verbose alerts."""
    alerts_output = scan_messages(symbol)
    if not alerts_output:
        # Silent cycle — no output at all
        return

    # Print everything at once
    sys.stdout.write("\n".join(alerts_output) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", "-s", help="Scan only this symbol (e.g. MNT/USDT:USDT)")
    args = parser.parse_args()
    run_and_report(symbol=args.symbol)
