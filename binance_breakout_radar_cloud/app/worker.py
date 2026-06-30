from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
import sys

from app.alerts import rules, telegram
from app.config import load_config
from app.output import write_csv, write_json
from app.scanner import scan
from app.storage import db


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Binance Breakout Radar cloud worker.")
    parser.add_argument("--config", default=os.getenv("RADAR_CONFIG", "config/balanced.yml"))
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--symbol", action="append")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    apply_env_overrides(config)
    if args.smoke_test:
        print_json(
            {
                "ok": True,
                "config": args.config,
                "telegram_configured": telegram.is_configured(),
                "db_path": config["outputs"]["db_path"],
                "checked_at": now(),
            }
        )
        return 0
    delivery_error = validate_alert_delivery(config)
    if delivery_error:
        print_json(delivery_error)
        return 2
    if args.loop:
        return asyncio.run(run_loop(config, args.symbol))
    return asyncio.run(run_once(config, args.symbol))


async def run_loop(config: dict, symbols: list[str] | None) -> int:
    interval = max(60, int(config["scan"].get("scan_interval_seconds", 300)))
    alerts = config.get("alerts", {})
    print_json(
        {
            "ok": True,
            "mode": "loop",
            "interval": interval,
            "alerts_enabled": alerts.get("enabled", False),
            "alerts_dry_run": alerts.get("dry_run", True),
            "telegram_configured": telegram.is_configured(),
            "started_at": now(),
        }
    )
    while True:
        try:
            await run_once(config, symbols)
        except Exception as exc:
            print_json({"ok": False, "error": str(exc), "checked_at": now()})
        sys.stdout.flush()
        await asyncio.sleep(interval)


async def run_once(config: dict, symbols: list[str] | None = None) -> int:
    all_rows = await scan(config, symbols, limit_to_top_n=False)
    report_rows = all_rows[: int(config["scan"].get("top_n", 30))]
    outputs = config["outputs"]
    write_json(report_rows, outputs["json_path"])
    write_csv(report_rows, outputs["csv_path"])
    db.save_scan_rows(outputs["db_path"], report_rows)
    state = db.load_alert_state(outputs["db_path"])
    sent = []
    skipped = []
    max_alerts = int(config.get("alerts", {}).get("max_per_scan", 0) or 0)
    for row in all_rows:
        ok, reason = rules.should_alert(row, config, state)
        state_name = rules.setup_state(row)
        if ok:
            if max_alerts and len(sent) >= max_alerts:
                skipped.append({"symbol": row.symbol, "reason": "per-scan alert cap reached", "state": state_name, "classification": row.classification})
                db.save_alert_state(outputs["db_path"], row.symbol, state_name, state.get(row.symbol, {}).get("last_alert_at"), asdict(row))
                continue
            message = rules.format_alert(row)
            if config.get("alerts", {}).get("dry_run", True):
                sent.append({"symbol": row.symbol, "dry_run": True, "state": state_name, "classification": row.classification})
                db.save_alert_state(outputs["db_path"], row.symbol, state_name, now(), asdict(row))
            else:
                try:
                    response = telegram.send_message(message)
                except Exception as exc:
                    response = {"ok": False, "error": str(exc)}
                if response.get("ok"):
                    sent.append({"symbol": row.symbol, "state": state_name, "classification": row.classification, "response": response})
                    db.save_alert_state(outputs["db_path"], row.symbol, state_name, now(), asdict(row))
                else:
                    skipped.append(
                        {
                            "symbol": row.symbol,
                            "reason": response.get("error", "telegram send failed"),
                            "state": state_name,
                            "classification": row.classification,
                        }
                    )
                    db.save_alert_state(
                        outputs["db_path"],
                        row.symbol,
                        state_name,
                        state.get(row.symbol, {}).get("last_alert_at"),
                        asdict(row),
                    )
        else:
            skipped.append({"symbol": row.symbol, "reason": reason, "state": state_name, "classification": row.classification})
            db.save_alert_state(outputs["db_path"], row.symbol, state_name, state.get(row.symbol, {}).get("last_alert_at"), asdict(row))
    print_json(
        {
            "ok": True,
            "rows": len(report_rows),
            "scanned_symbols": len(all_rows),
            "alerts_sent": len(sent),
            "alerts_skipped": len(skipped),
            "sent_symbols": [item.get("symbol") for item in sent if item.get("symbol")],
            "skipped_reason_counts": dict(Counter(item["reason"] for item in skipped)),
            "top_skipped": skipped[:5],
            "top_symbol": report_rows[0].symbol if report_rows else None,
            "json": outputs["json_path"],
            "csv": outputs["csv_path"],
            "db": outputs["db_path"],
            "checked_at": now(),
        }
    )
    return 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def print_json(value: dict) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def validate_alert_delivery(config: dict) -> dict | None:
    alerts = config.get("alerts", {})
    if not alerts.get("enabled", False) or alerts.get("dry_run", True):
        return None
    if telegram.is_configured():
        return None
    return {
        "ok": False,
        "error": "Live radar alerts are enabled, but Telegram is not configured.",
        "required_env": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
        "checked_at": now(),
    }


def apply_env_overrides(config: dict) -> None:
    outputs = config.setdefault("outputs", {})
    scan_config = config.setdefault("scan", {})
    universe = config.setdefault("universe", {})
    alerts = config.setdefault("alerts", {})

    if os.getenv("RADAR_DB_PATH"):
        outputs["db_path"] = os.getenv("RADAR_DB_PATH")
    if os.getenv("RADAR_JSON_PATH"):
        outputs["json_path"] = os.getenv("RADAR_JSON_PATH")
    if os.getenv("RADAR_CSV_PATH"):
        outputs["csv_path"] = os.getenv("RADAR_CSV_PATH")
    if os.getenv("RADAR_SCAN_INTERVAL_SECONDS"):
        scan_config["scan_interval_seconds"] = int(os.getenv("RADAR_SCAN_INTERVAL_SECONDS", "300"))
    if os.getenv("RADAR_TOP_N"):
        scan_config["top_n"] = int(os.getenv("RADAR_TOP_N", "30"))
    if os.getenv("RADAR_WORKERS"):
        scan_config["workers"] = int(os.getenv("RADAR_WORKERS", "8"))
    if os.getenv("RADAR_MIN_QUOTE_VOLUME_24H"):
        universe["min_quote_volume_24h"] = float(os.getenv("RADAR_MIN_QUOTE_VOLUME_24H", "0"))
    if os.getenv("RADAR_ALERTS_ENABLED") is not None:
        alerts["enabled"] = _env_bool("RADAR_ALERTS_ENABLED")
    if os.getenv("RADAR_ALERTS_DRY_RUN") is not None:
        alerts["dry_run"] = _env_bool("RADAR_ALERTS_DRY_RUN")
    if os.getenv("RADAR_ALERT_COOLDOWN_HOURS"):
        alerts["cooldown_hours"] = float(os.getenv("RADAR_ALERT_COOLDOWN_HOURS", "6"))
    if os.getenv("RADAR_ALERT_STATE_CHANGE_ONLY") is not None:
        alerts["state_change_only"] = _env_bool("RADAR_ALERT_STATE_CHANGE_ONLY")
    if os.getenv("RADAR_ALERT_MIN_OVERALL_SCORE"):
        alerts["min_overall_score"] = float(os.getenv("RADAR_ALERT_MIN_OVERALL_SCORE", "75"))
    if os.getenv("RADAR_ALERT_MIN_COMPRESSION_SCORE"):
        alerts["min_compression_score"] = float(os.getenv("RADAR_ALERT_MIN_COMPRESSION_SCORE", "70"))
    if os.getenv("RADAR_ALERT_MIN_STRUCTURE_SCORE"):
        alerts["min_structure_score"] = float(os.getenv("RADAR_ALERT_MIN_STRUCTURE_SCORE", "70"))
    if os.getenv("RADAR_ALERT_MIN_PARTICIPATION_SCORE"):
        alerts["min_participation_score"] = float(os.getenv("RADAR_ALERT_MIN_PARTICIPATION_SCORE", "50"))
    if os.getenv("RADAR_ALERT_MIN_ACCEPTANCE_SCORE"):
        alerts["min_acceptance_score"] = float(os.getenv("RADAR_ALERT_MIN_ACCEPTANCE_SCORE", "50"))
    if os.getenv("RADAR_ALERT_MIN_RR"):
        alerts["min_rr"] = float(os.getenv("RADAR_ALERT_MIN_RR", "1"))
    if os.getenv("RADAR_ALERT_MAX_DISTANCE_TO_RESISTANCE_PCT"):
        alerts["max_distance_to_resistance_pct"] = float(os.getenv("RADAR_ALERT_MAX_DISTANCE_TO_RESISTANCE_PCT", "3"))
    if os.getenv("RADAR_ALERT_MAX_PER_SCAN"):
        alerts["max_per_scan"] = int(os.getenv("RADAR_ALERT_MAX_PER_SCAN", "8"))


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    sys.exit(main())
