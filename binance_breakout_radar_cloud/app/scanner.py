from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import pandas as pd

from app import data_loader
from app.config import load_config
from app.indicators import add_indicators
from app.scoring import acceptance, compression, magnitude, momentum, participation, smart_money, structure


@dataclass
class ScanRow:
    symbol: str
    current_price: float
    overall_score: float
    overall_score_display: str
    rank: int = 0
    classification: str = ""
    compression_score: float = 0.0
    compression_score_display: str = ""
    structural_pressure_score: float = 0.0
    structural_pressure_score_display: str = ""
    participation_score: float = 0.0
    participation_score_display: str = ""
    momentum_score: float = 0.0
    momentum_score_display: str = ""
    smart_money_score: float | None = None
    smart_money_score_display: str | None = None
    price_acceptance_score: float = 0.0
    price_acceptance_score_display: str = ""
    magnitude_score: float = 0.0
    magnitude_score_display: str = ""
    strongest_engine: str = ""
    weakest_engine: str = ""
    key_evidence: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    breakout_level_resistance: float | None = None
    invalidated_below: float | None = None
    distance_to_resistance_pct: float | None = None
    classification_blockers: list[str] = field(default_factory=list)
    quote_volume_24h: float = 0.0
    notes: str = ""
    raw_metrics: dict = field(default_factory=dict)
    scanned_at: str = ""


async def scan(config: dict, symbols: list[str] | None = None, limit_to_top_n: bool = True) -> list[ScanRow]:
    symbol_rows = await data_loader.list_symbols(config)
    if symbols:
        wanted = {symbol.upper() for symbol in symbols}
        symbol_rows = [row for row in symbol_rows if row["symbol"] in wanted]
    workers = int(config["scan"].get("workers", 8))
    semaphore = asyncio.Semaphore(workers)

    async def load(row):
        async with semaphore:
            return await data_loader.load_symbol(row, config)

    loaded = [item for item in await asyncio.gather(*(load(row) for row in symbol_rows)) if item is not None]
    benchmark_symbol = config.get("market_context", {}).get("benchmark_symbol", "BTCUSDT")
    benchmark = next((item.k1h for item in loaded if item.symbol == benchmark_symbol), None)
    rows = [analyse(item, config, benchmark) for item in loaded]
    rows.sort(key=lambda row: row.overall_score, reverse=True)
    for idx, row in enumerate(rows, 1):
        row.rank = idx
    if limit_to_top_n:
        return rows[: int(config["scan"].get("top_n", 30))]
    return rows


def analyse(symbol_data: data_loader.SymbolData, config: dict, benchmark_k1h=None) -> ScanRow:
    k1h = add_indicators(symbol_data.k1h)
    comp = compression.score(k1h, config)
    struct = structure.score(k1h, config)
    part = participation.score(k1h, config, struct.metrics)
    mom = momentum.score(k1h, config)
    sm = smart_money.score(k1h, symbol_data.derivatives, config)
    resistance = struct.metrics.get("_resistance")
    support = struct.metrics.get("_support")
    acc = acceptance.score(k1h, resistance, config)
    mag = magnitude.score(k1h, resistance, support, config)
    market_context = _market_context(symbol_data.symbol, k1h, benchmark_k1h, config)
    engine_scores = {
        "Compression": comp.score,
        "Structural Pressure": struct.score,
        "Participation": part.score,
        "Momentum": mom.score,
        "Price Acceptance": acc.score,
    }
    weights = config["weights"]["without_smart_money"]
    weighted = {
        "compression": comp.score,
        "structure": struct.score,
        "participation": part.score,
        "momentum": mom.score,
        "acceptance": acc.score,
    }
    if sm is not None:
        engine_scores["Smart Money"] = sm.score
        weighted["smart_money"] = sm.score
        weights = config["weights"]["with_smart_money"]
    overall = sum(weighted[key] * weights[key] for key in weights)
    strongest = max(engine_scores, key=engine_scores.get)
    weakest = min(engine_scores, key=engine_scores.get)
    evidence = []
    missing = []
    for result in [comp, struct, part, mom, acc] + ([sm] if sm else []):
        evidence.extend(result.evidence)
        missing.extend(result.missing)
    distance = None
    if resistance:
        distance = (resistance - symbol_data.price) / resistance * 100
    classification, blockers = classify_with_gates(overall, comp, struct, part, mom, acc, mag, distance, config)
    return ScanRow(
        symbol=symbol_data.symbol,
        current_price=round(symbol_data.price, 8),
        overall_score=round(overall, 2),
        overall_score_display=_display(overall),
        classification=classification,
        compression_score=comp.score,
        compression_score_display=comp.display,
        structural_pressure_score=struct.score,
        structural_pressure_score_display=struct.display,
        participation_score=part.score,
        participation_score_display=part.display,
        momentum_score=mom.score,
        momentum_score_display=mom.display,
        smart_money_score=sm.score if sm else None,
        smart_money_score_display=sm.display if sm else None,
        price_acceptance_score=acc.score,
        price_acceptance_score_display=acc.display,
        magnitude_score=mag.score,
        magnitude_score_display=mag.display,
        strongest_engine=strongest,
        weakest_engine=weakest,
        key_evidence=evidence[:8],
        missing_evidence=missing[:8],
        breakout_level_resistance=resistance,
        invalidated_below=support,
        distance_to_resistance_pct=round(distance, 2) if distance is not None else None,
        classification_blockers=blockers,
        quote_volume_24h=round(symbol_data.quote_volume_24h, 2),
        notes=_notes(engine_scores, sm is None),
        raw_metrics={
            "compression": comp.metrics,
            "structural_pressure": struct.metrics,
            "participation": part.metrics,
            "momentum": mom.metrics,
            "smart_money": sm.metrics if sm else None,
            "price_acceptance": acc.metrics,
            "magnitude": mag.metrics,
            "market_context": market_context,
        },
        scanned_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _market_context(symbol: str, k1h, benchmark_k1h, config: dict) -> dict:
    params = config.get("market_context", {})
    benchmark_symbol = params.get("benchmark_symbol", "BTCUSDT")
    lookback = int(params.get("correlation_lookback_bars", 50))
    trend_bars = int(params.get("benchmark_trend_bars", 6))
    if symbol == benchmark_symbol:
        return {
            "benchmark_symbol": benchmark_symbol,
            "correlation_1h": None,
            "benchmark_change_pct": None,
            "symbol_change_pct": None,
            "relationship": "benchmark symbol",
        }
    if benchmark_k1h is None or len(k1h) < lookback + 1 or len(benchmark_k1h) < lookback + 1:
        return {
            "benchmark_symbol": benchmark_symbol,
            "correlation_1h": None,
            "benchmark_change_pct": None,
            "symbol_change_pct": None,
            "relationship": "unavailable",
        }
    symbol_returns = k1h["close"].pct_change().iloc[-lookback:]
    benchmark_returns = benchmark_k1h["close"].pct_change().iloc[-lookback:]
    aligned = pd.concat([symbol_returns.reset_index(drop=True), benchmark_returns.reset_index(drop=True)], axis=1).dropna()
    corr = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])) if len(aligned) >= 10 else None
    benchmark_change = _pct_change(benchmark_k1h["close"].iloc[-trend_bars], benchmark_k1h["close"].iloc[-1])
    symbol_change = _pct_change(k1h["close"].iloc[-trend_bars], k1h["close"].iloc[-1])
    relationship = _btc_relationship(corr, benchmark_change, symbol_change)
    return {
        "benchmark_symbol": benchmark_symbol,
        "correlation_1h": round(corr, 3) if corr is not None else None,
        "benchmark_change_pct": round(benchmark_change, 2) if benchmark_change is not None else None,
        "symbol_change_pct": round(symbol_change, 2) if symbol_change is not None else None,
        "relationship": relationship,
    }


def _pct_change(start, end) -> float | None:
    try:
        start = float(start)
        end = float(end)
    except (TypeError, ValueError):
        return None
    if not start:
        return None
    return (end / start - 1) * 100


def _btc_relationship(corr: float | None, btc_change: float | None, symbol_change: float | None) -> str:
    if corr is None or btc_change is None or symbol_change is None:
        return "unavailable"
    if corr >= 0.65 and btc_change < -0.5:
        return "btc drag risk"
    if corr >= 0.65 and btc_change > 0.5:
        return "btc tailwind"
    if corr <= 0.25 and symbol_change > 0:
        return "idiosyncratic strength"
    if corr <= 0.25:
        return "low btc dependence"
    return "moderate btc link"


def classify(score: float) -> str:
    if score >= 85:
        return "Breakout Radar Priority"
    if score >= 75:
        return "High Watch"
    if score >= 65:
        return "Developing Setup"
    if score >= 50:
        return "Early / Incomplete"
    return "Ignore"


def classify_with_gates(
    overall: float,
    comp,
    struct,
    part,
    mom,
    acc,
    mag,
    distance: float | None,
    config: dict,
) -> tuple[str, list[str]]:
    raw = classify(overall)
    gates = config.get("classification_gates", {})
    order = [
        ("Breakout Radar Priority", "priority"),
        ("High Watch", "high_watch"),
        ("Developing Setup", "developing"),
        ("Early / Incomplete", None),
        ("Ignore", None),
    ]
    raw_rank = {name: idx for idx, (name, _) in enumerate(reversed(order))}
    allowed = raw
    blockers: list[str] = []
    for label, gate_key in order:
        if raw_rank.get(label, 0) > raw_rank.get(raw, 0):
            continue
        if gate_key is None:
            allowed = label
            break
        ok, gate_blockers = _passes_gate(gates.get(gate_key, {}), overall, comp, struct, part, mom, acc, mag, distance)
        if ok:
            allowed = label
            break
        blockers = gate_blockers
    return allowed, blockers


def _passes_gate(gate: dict, overall: float, comp, struct, part, mom, acc, mag, distance: float | None) -> tuple[bool, list[str]]:
    blockers = []
    checks = [
        ("overall", overall, gate.get("min_overall")),
        ("compression", comp.score, gate.get("min_compression")),
        ("structure", struct.score, gate.get("min_structure")),
        ("participation", part.score, gate.get("min_participation")),
        ("momentum", mom.score, gate.get("min_momentum")),
        ("acceptance", acc.score, gate.get("min_acceptance")),
        ("magnitude", mag.score, gate.get("min_magnitude")),
    ]
    for name, value, minimum in checks:
        if minimum is not None and value < float(minimum):
            blockers.append(f"{name} {value:.2f} below {float(minimum):.2f}")
    max_distance = gate.get("max_distance_to_resistance_pct")
    if max_distance is not None and distance is not None and distance > float(max_distance):
        blockers.append(f"distance {distance:.2f}% above {float(max_distance):.2f}%")
    return not blockers, blockers


def to_dicts(rows: list[ScanRow]) -> list[dict]:
    return [asdict(row) for row in rows]


def _display(score: float) -> str:
    return f"{score:.2f} / 100"


def _notes(scores: dict[str, float], smart_money_missing: bool) -> str:
    notes = []
    if scores.get("Compression", 0) >= 70 and scores.get("Participation", 0) < 50:
        notes.append("Compression present, but participation is not confirming yet.")
    if scores.get("Price Acceptance", 0) < 50:
        notes.append("Acceptance is weak; breakout may not sustain.")
    if smart_money_missing:
        notes.append("Smart Money unavailable and excluded from weighting.")
    return " ".join(notes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated Binance Breakout Radar scanner.")
    parser.add_argument("--config", default="config/balanced.yml")
    parser.add_argument("--symbol", action="append", help="Limit scan to one symbol. Can be repeated.")
    args = parser.parse_args()
    config = load_config(args.config)
    rows = asyncio.run(scan(config, args.symbol))
    from app.output import print_summary, write_csv, write_json

    print_summary(rows)
    write_json(rows, config["outputs"]["json_path"])
    write_csv(rows, config["outputs"]["csv_path"])


if __name__ == "__main__":
    main()
