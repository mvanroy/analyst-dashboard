"""
Trade Dashboard
================
Compact at-a-glance view of all trade setups across the watchlist.
Run manually: python dashboard.py
Triggers a full scan and outputs a formatted summary.
"""
import sys, os, datetime, time

from .config import WATCHLIST, SYMBOL_LABELS
from .data import fetch_all_data
from .patterns import detect_all, PATTERNS
from .state_tracker import _load_state

# ─── Helpers ─────────────────────────────────────────────────────────

def label_for(symbol: str) -> str:
    return SYMBOL_LABELS.get(symbol, symbol.replace("/USDT:USDT", ""))

def emoji_for_grade(g):
    return {"A": "⭐", "B": "✦", "C": "•"}.get(g, "")

def emoji_for_maturity(m):
    return {"Ready": "✅", "Forming": "⏳", "Nascent": "🔹", "Invalidated": "🚫"}.get(m, "")

def direction_arrow(d):
    return "🔴" if d == "short" else "🟢"

def short_entry_label(entry):
    """Compact entry zone string."""
    z = entry.get('zone', {})
    low = z.get('low')
    high = z.get('high')
    if low and high:
        if high > 1:
            return f"${low:.2f}–{high:.2f}"
        else:
            return f"${low:.4f}–{high:.4f}"
    return "-"

def short_price(p):
    if p is None:
        return "-"
    if p >= 100:
        return f"${p:.1f}"
    elif p >= 1:
        return f"${p:.3f}"
    else:
        return f"${p:.4f}"

def best_rr(entry):
    """Best R:R ratio from T1 or T2."""
    t1 = entry.get('t1', {})
    t2 = entry.get('t2', {})
    rr1 = t1.get('rr', '')
    rr2 = t2.get('rr', '')
    
    for rr in [rr2, rr1]:
        if ':' in rr:
            try:
                val = float(rr.split(':')[1].strip())
                if val >= 1:
                    return f"1:{val:.1f}"
            except:
                pass
    return rr1 if rr1 else "-"

# ─── Main ────────────────────────────────────────────────────────────

def run_dashboard():
    """Run scan and produce formatted dashboard output."""
    start = time.time()
    scan_results = {}

    for symbol in WATCHLIST:
        label = label_for(symbol)
        try:
            data = fetch_all_data(symbol)
            if data.get('error'):
                continue
            setups = detect_all(data)
            for s in setups:
                s['_symbol'] = symbol
            if setups:
                scan_results[label] = setups
        except Exception:
            continue

    elapsed = time.time() - start

    state = _load_state()
    last_scan_ts = state.get('_meta', {}).get('last_scan', None)
    last_scan_str = datetime.datetime.fromtimestamp(last_scan_ts).strftime('%H:%M UTC') if last_scan_ts else 'just now'

    lines = []
    total_setups = sum(len(v) for v in scan_results.values())

    # ─── Header ──────────────────────────────────────────────────────
    lines.append("📊 **Crypto Trade Dashboard**")
    lines.append(f"`{total_setups} setups · {len(scan_results)} coins · {len(PATTERNS)} patterns · {elapsed:.1f}s`")
    lines.append("")

    # ─── Coin Cards ──────────────────────────────────────────────────
    for symbol in WATCHLIST:
        label = label_for(symbol)
        setups = scan_results.get(label, [])
        if not setups:
            continue

        setups_sorted = sorted(setups, key=lambda s: {"A": 3, "B": 2, "C": 1}.get(s.get('grade', 'C'), 0), reverse=True)

        best = setups_sorted[0]
        g = best.get('grade', '')
        dir_arrow = direction_arrow(best.get('direction', ''))
        mat = best.get('maturity', '')
        mat_emoji = emoji_for_maturity(mat)
        p = best.get('price', 0)
        entry_label = short_entry_label(best.get('entry', {}))
        rr = best_rr(best.get('entry', {}))
        pattern = best.get('name', '')
        grade_icon = emoji_for_grade(g)

        # Card header
        lines.append(f"{dir_arrow} **{label}** {grade_icon} {mat_emoji}  `{short_price(p)}`")

        # Card detail line — pattern · entry · R:R
        lines.append(f"   └ {pattern}  →  `{entry_label}`  ·  R:R `{rr}`")

        # Additional setups (max 2, inline)
        if len(setups_sorted) > 1:
            extra = []
            for s in setups_sorted[1:3]:
                g2 = s.get('grade', '')
                p2 = s.get('name', '')
                d2 = direction_arrow(s.get('direction', ''))
                m2 = emoji_for_maturity(s.get('maturity', ''))
                extra.append(f"{d2}{p2} {emoji_for_grade(g2)} {m2}")
            if extra:
                lines.append(f"      ⤷ {' | '.join(extra)}")

    if not total_setups:
        lines.append("  No setups found in current scan.")

    lines.append("")
    lines.append(f"`Run: dashboard.py · Scan: {last_scan_str} · Cron: every 30m`")

    return "\n".join(lines)


if __name__ == "__main__":
    output = run_dashboard()
    print(output, flush=True)
