"""Trading-cycle boundaries and immutable Cycle 1 archive access."""
from __future__ import annotations

import json
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_PATH = os.path.join(ROOT_DIR, "data", "trading_cycles", "cycle_1.json")


def load_cycle_one() -> dict:
    try:
        with open(ARCHIVE_PATH, "r") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def cutoff_ts() -> int:
    return int((load_cycle_one().get("cycle") or {}).get("cutoff_ts") or 0)


def archived_trades(live_trades: list[dict] | None = None) -> list[dict]:
    archive = load_cycle_one()
    trades = [_normalise_trade(row) for row in archive.get("closed_trades") or []]
    seen = {str(row.get("trade_id") or "") for row in trades}
    legacy = archive.get("legacy_open_positions") or []
    for row in live_trades or []:
        trade_id = str(row.get("trade_id") or "")
        if trade_id in seen or not _matches_legacy_position(row, legacy):
            continue
        trades.append(dict(row))
        seen.add(trade_id)
    return sorted(trades, key=lambda row: int(row.get("closed_ts") or row.get("ts") or 0))


def current_trades(live_trades: list[dict]) -> list[dict]:
    archive = load_cycle_one()
    legacy = archive.get("legacy_open_positions") or []
    boundary = cutoff_ts()
    return [
        dict(row)
        for row in live_trades
        if int(row.get("closed_ts") or 0) >= boundary and not _matches_legacy_position(row, legacy)
    ]


def legacy_positions() -> list[dict]:
    return list(load_cycle_one().get("legacy_open_positions") or [])


def pending_legacy_positions(live_trades: list[dict]) -> list[dict]:
    positions = legacy_positions()
    return [
        position
        for position in positions
        if not any(_matches_legacy_position(trade, [position]) for trade in live_trades)
    ]


def _matches_legacy_position(trade: dict, positions: list[dict]) -> bool:
    opened_ts = int(trade.get("opened_ts") or trade.get("ts") or 0)
    for position in positions:
        if str(trade.get("coin") or "") != str(position.get("coin") or ""):
            continue
        if str(trade.get("direction") or "") != str(position.get("direction") or ""):
            continue
        if abs(opened_ts - int(position.get("opened_ts") or 0)) <= 120_000:
            return True
    return False


def _normalise_trade(row: dict) -> dict:
    return dict(row)
