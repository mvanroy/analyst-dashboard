"""
State Tracker
==============
Persists setup states between scan cycles so we can:
- Track new vs. mature vs. duplicate vs. invalidated setups
- Track direction flips (short→long, long→short)
- Only alert on state transitions
- Auto-purge stale setups

State file is JSON. One entry per (symbol, pattern_id) pair,
plus _direction:<symbol> entries for flip tracking.
"""
import json
import os
import time
from typing import Dict, Any, List, Optional

from .config import STATE_FILE


def _load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_state(state: Dict[str, Any]):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def compute_actions(current_setups: List[Dict[str, Any]], skip_invalidation: bool = False) -> List[Dict[str, Any]]:
    """
    Compare current scan results against previous state.

    Returns alert-worthy entries with an 'event' field:
    - 'new': setup appeared for the first time
    - 'matured': setup transitioned from Forming/Nascent to Ready
    - 'flip': dominant direction changed (short↔long) for a coin
    - 'invalidated': a coin that had setups now has none

    Does NOT return duplicates (same maturity as last cycle).
    """
    state = _load_state()
    now = time.time()
    alerts = []

    # Group current setups by coin symbol
    coin_setups: Dict[str, List[Dict]] = {}
    for setup in current_setups:
        symbol = setup.get('_symbol', 'unknown')
        if symbol not in coin_setups:
            coin_setups[symbol] = []
        coin_setups[symbol].append(setup)

    current_keys = set()

    # Process each coin
    for symbol, setups in coin_setups.items():
        # Find the dominant (highest grade) setup for this coin
        setups_sorted = sorted(setups, key=lambda s: {"A": 3, "B": 2, "C": 1}.get(s.get('grade', 'C'), 0), reverse=True)
        best = setups_sorted[0] if setups_sorted else None

        if not best:
            continue

        pattern_id = best.get('pattern_id', 'unknown')
        maturity = best.get('maturity', '')
        direction = best.get('direction', '')
        grade = best.get('grade', '')
        price = best.get('price', 0)
        score = best.get('score', 0)

        # ─── Process per-setup state ──────────────────────────
        for s in setups:
            pid = s.get('pattern_id', 'unknown')
            mat = s.get('maturity', '')
            key = f"{symbol}|{pid}|{pid}"
            prev = state.get(key)

            if prev is None:
                if mat == "Ready":
                    s['event'] = 'new'
                    alerts.append(s)
            else:
                prev_maturity = prev.get('maturity', '')
                if mat == "Ready" and prev_maturity in ("Forming", "Nascent"):
                    s['event'] = 'matured'
                    alerts.append(s)

            # Update per-setup state
            state[key] = {
                'maturity': mat,
                'score': s.get('score', 0),
                'price': s.get('price', 0),
                'timestamp': now,
                'symbol': symbol,
            }
            current_keys.add(key)

        # ─── Direction flip detection ──────────────────────────
        dir_key = f"_direction:{symbol}"
        prev_dir_entry = state.get(dir_key)
        prev_direction = prev_dir_entry.get('direction') if prev_dir_entry else None
        prev_grade = prev_dir_entry.get('grade') if prev_dir_entry else None

        # Determine the dominant direction for this coin
        best_direction = best.get('direction', '')

        if prev_direction is not None and prev_direction != best_direction:
            # FLIP detected!
            flip_setup = dict(best)  # shallow copy
            flip_setup['event'] = 'flip'
            flip_setup['flip_from'] = prev_direction
            flip_setup['flip_to'] = best_direction
            flip_setup['flip_prev_grade'] = prev_grade
            alerts.append(flip_setup)

        # Save current dominant direction
        state[dir_key] = {
            'direction': best_direction,
            'grade': grade,
            'pattern': best.get('name', ''),
            'price': price,
            'score': score,
            'timestamp': now,
            'symbol': symbol,
        }

    # ─── Invalidation detection ────────────────────────────────
    # Find coins that had a direction but now have no setups
    # Only run when scanning all coins (skip for single-coin per-cron-job scans)
    if not skip_invalidation:
        for key, entry in list(state.items()):
            if key.startswith("_direction:"):
                symbol = key.replace("_direction:", "")
                if symbol not in coin_setups or not coin_setups[symbol]:
                    prev_dir = entry.get('direction')
                    if prev_dir:
                        age = now - entry.get('timestamp', 0)
                        if age > 900:  # 15 min grace period before invalidating
                            alerts.append({
                                '_symbol': symbol,
                                'event': 'invalidated',
                                'direction': prev_dir,
                                'maturity': 'Invalidated',
                                'pattern_id': 'invalidation',
                                'name': f"All setups expired — no active signals for {symbol}",
                                'price': entry.get('price', 0),
                            })
                            del state[key]
                        else:
                            # Keep the direction alive during grace period
                            pass

    # ─── Cleanup stale per-setup entries (>24h) ───────────────
    for key, entry in list(state.items()):
        if key != '_meta' and not key.startswith("_direction:"):
            age = now - entry.get('timestamp', 0)
            if age > 86400:
                del state[key]

    state['_meta'] = {
        'last_scan': now,
        'total_active': len([k for k in state if k != '_meta' and not k.startswith("_direction:")]),
    }
    _save_state(state)

    return alerts