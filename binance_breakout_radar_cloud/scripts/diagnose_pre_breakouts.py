from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alerts import rules
from app.backtest import fetch_bybit_history, list_bybit_symbols
from app.config import load_config
from app.data_loader import DerivativesData, SymbolData
from app.indicators import add_indicators
from app.scanner import analyse


async def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose engine evidence before actual breakout windows.")
    parser.add_argument("--config", default="config/balanced.yml")
    parser.add_argument("--max-symbols", type=int, default=120)
    parser.add_argument("--history-candles", type=int, default=420)
    parser.add_argument("--lookback-candles", type=int, default=200)
    parser.add_argument("--last-bars", type=int, default=168)
    parser.add_argument("--forward-bars", type=int, default=24)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--output-dir", default="outputs/backtests/pre_breakout_diagnostic")
    args = parser.parse_args()

    config = load_config(args.config)
    config.setdefault("universe", {})["min_quote_volume_24h"] = 0
    symbols = (await list_bybit_symbols(config))[: args.max_symbols]
    semaphore = asyncio.Semaphore(args.workers)

    async def load(symbol_row: dict[str, Any]):
        async with semaphore:
            return symbol_row, await fetch_bybit_history(symbol_row["symbol"], args.history_candles)

    loaded = await asyncio.gather(*(load(row) for row in symbols))
    events = []
    processed = 0
    for symbol_row, candles in loaded:
        if candles is None or len(candles) < args.lookback_candles + args.forward_bars + args.last_bars:
            continue
        df = add_indicators(candles)
        start = max(args.lookback_candles, len(df) - args.forward_bars - args.last_bars)
        end = len(df) - args.forward_bars
        last_event_idx = -10_000
        for idx in range(start, end):
            if idx - last_event_idx < 12:
                continue
            historical = df.iloc[idx + 1 - args.lookback_candles : idx + 1].copy()
            future = df.iloc[idx + 1 : idx + 1 + args.forward_bars].copy()
            if historical[["rsi14", "adx14", "mfi20"]].iloc[-1].isna().any():
                continue
            positive, move = _actual_breakout(historical, future)
            if not positive:
                continue
            symbol_data = SymbolData(
                symbol=symbol_row["symbol"],
                price=float(historical["close"].iloc[-1]),
                quote_volume_24h=float(symbol_row.get("quote_volume_24h", 0)),
                k1h=historical,
                k4h=historical,
                derivatives=DerivativesData(),
            )
            row = analyse(symbol_data, config)
            ok, reason = rules.should_alert(row, config, {})
            scores = _scores(row)
            weakest_engine, weakest_score = min(scores.items(), key=lambda item: item[1])
            events.append(
                {
                    "symbol": symbol_row["symbol"],
                    "time": str(historical["close_time"].iloc[-1]),
                    **move,
                    "classification": row.classification,
                    "alert_blocker": "would_alert" if ok else reason,
                    "weakest_engine": weakest_engine,
                    "weakest_score": round(weakest_score, 2),
                    **{f"{name}_score": round(value, 2) for name, value in scores.items()},
                    "engine_resistance": row.breakout_level_resistance,
                    "engine_distance_pct": row.distance_to_resistance_pct,
                    "resistance_source": row.raw_metrics.get("structural_pressure", {}).get("_resistance_source"),
                    "resistance_candidates": json.dumps(row.raw_metrics.get("structural_pressure", {}).get("_resistance_candidates", [])),
                    "classification_blockers": " | ".join(row.classification_blockers),
                    "missing_evidence": " | ".join(row.missing_evidence[:8]),
                    "key_evidence": " | ".join(row.key_evidence[:8]),
                }
            )
            last_event_idx = idx
        processed += 1
        if processed % 30 == 0:
            print(f"processed {processed}/{args.max_symbols}; breakout events {len(events)}", flush=True)

    summary = _summarize(events, processed)
    _write_outputs(events, summary, args.output_dir)
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _actual_breakout(historical, future) -> tuple[bool, dict[str, Any]]:
    resistance = float(historical["high"].iloc[-72:].max())
    entry = float(historical["close"].iloc[-1])
    if resistance <= 0:
        return False, {}
    distance_pct = (resistance - entry) / resistance * 100
    if distance_pct < -1 or distance_pct > 10:
        return False, {}
    future_high = float(future["high"].max())
    broke = future_high > resistance * 1.002
    closes_above = int((future["close"] > resistance).sum())
    mfe_pct = (future_high / entry - 1) * 100
    final_pct = (float(future["close"].iloc[-1]) / entry - 1) * 100
    if not (broke and closes_above >= 2 and mfe_pct >= 2.0):
        return False, {}
    return True, {
        "prior_72h_resistance": round(resistance, 8),
        "distance_to_prior_resistance_pct": round(distance_pct, 2),
        "mfe_pct": round(mfe_pct, 2),
        "final_return_pct": round(final_pct, 2),
        "closes_above_prior_resistance": closes_above,
    }


def _scores(row) -> dict[str, float]:
    return {
        "overall": row.overall_score,
        "compression": row.compression_score,
        "structure": row.structural_pressure_score,
        "participation": row.participation_score,
        "momentum": row.momentum_score,
        "acceptance": row.price_acceptance_score,
        "magnitude": row.magnitude_score,
    }


def _summarize(events: list[dict[str, Any]], processed: int) -> dict[str, Any]:
    blockers = Counter(event["alert_blocker"] for event in events)
    classifications = Counter(event["classification"] for event in events)
    weakest = Counter(event["weakest_engine"] for event in events)
    score_totals: dict[str, float] = defaultdict(float)
    for event in events:
        for name in ["overall", "compression", "structure", "participation", "momentum", "acceptance", "magnitude"]:
            score_totals[name] += float(event[f"{name}_score"])
    avg_scores = {name: round(total / len(events), 2) for name, total in score_totals.items()} if events else {}
    return {
        "symbols_processed": processed,
        "actual_breakout_events_found": len(events),
        "symbols_with_breakouts": len({event["symbol"] for event in events}),
        "classification_counts_before_breakout": dict(classifications.most_common()),
        "alert_blockers_before_breakout": dict(blockers.most_common()),
        "weakest_engine_before_breakout": dict(weakest.most_common()),
        "average_scores_before_breakout": avg_scores,
        "top_missed_breakouts_by_mfe": sorted(events, key=lambda event: event["mfe_pct"], reverse=True)[:20],
    }


def _write_outputs(events: list[dict[str, Any]], summary: dict[str, Any], output_dir: str) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    if not events:
        (target / "events.csv").write_text("")
        return
    with (target / "events.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(events[0].keys()))
        writer.writeheader()
        writer.writerows(events)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
