from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path


def init_db(path: str) -> None:
    db = Path(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            create table if not exists scan_rows (
                id integer primary key autoincrement,
                scanned_at text not null,
                symbol text not null,
                rank integer,
                overall_score real,
                classification text,
                current_price real,
                resistance real,
                invalidated_below real,
                payload_json text not null
            )
            """
        )
        conn.execute(
            """
            create table if not exists alert_state (
                symbol text primary key,
                last_state text,
                last_alert_at text,
                payload_json text
            )
            """
        )


def save_scan_rows(path: str, rows) -> None:
    init_db(path)
    with sqlite3.connect(path) as conn:
        for row in rows:
            data = asdict(row)
            conn.execute(
                """
                insert into scan_rows (
                    scanned_at, symbol, rank, overall_score, classification,
                    current_price, resistance, invalidated_below, payload_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.scanned_at,
                    row.symbol,
                    row.rank,
                    row.overall_score,
                    row.classification,
                    row.current_price,
                    row.breakout_level_resistance,
                    row.invalidated_below,
                    json.dumps(data, default=str),
                ),
            )


def load_alert_state(path: str) -> dict[str, dict]:
    init_db(path)
    with sqlite3.connect(path) as conn:
        rows = conn.execute("select symbol, last_state, last_alert_at, payload_json from alert_state").fetchall()
    return {
        symbol: {
            "last_state": last_state,
            "last_alert_at": last_alert_at,
            "payload": json.loads(payload_json) if payload_json else {},
        }
        for symbol, last_state, last_alert_at, payload_json in rows
    }


def save_alert_state(path: str, symbol: str, state: str, alert_at: str | None, payload: dict) -> None:
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            insert into alert_state (symbol, last_state, last_alert_at, payload_json)
            values (?, ?, ?, ?)
            on conflict(symbol) do update set
                last_state=excluded.last_state,
                last_alert_at=excluded.last_alert_at,
                payload_json=excluded.payload_json
            """,
            (symbol, state, alert_at, json.dumps(payload, default=str)),
        )
