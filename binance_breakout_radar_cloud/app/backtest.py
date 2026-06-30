from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

import httpx
import pandas as pd

from app import data_loader
from app.config import load_config
from app.indicators import add_indicators
from app.scanner import analyse, classify
from app.data_loader import DerivativesData, SymbolData, parse_klines

BYBIT_BASE = "https://api.bybit.com"

STATE_RANK = {
    "Ignore": 0,
    "Early / Incomplete": 1,
    "Developing Setup": 2,
    "High Watch": 3,
    "Breakout Radar Priority": 4,
}


async def run_backtest(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    symbol_rows = await list_symbols_with_backoff(config, args)
    if args.min_quote_volume is not None:
        symbol_rows = [row for row in symbol_rows if row["quote_volume_24h"] >= args.min_quote_volume]
    if args.max_symbols:
        symbol_rows = symbol_rows[: args.max_symbols]

    semaphore = asyncio.Semaphore(args.workers)

    async def load(row: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame | None]:
        async with semaphore:
            return row, await fetch_history(row["symbol"], args.history_candles, args.exchange)

    loaded = await asyncio.gather(*(load(row) for row in symbol_rows))
    signals = []
    symbol_summaries = []
    for row, candles in loaded:
        if candles is None or len(candles) < args.lookback_candles + args.forward_bars + 5:
            symbol_summaries.append({"symbol": row["symbol"], "signals": 0, "status": "insufficient_history"})
            continue
        symbol_signals = backtest_symbol(row, candles, config, args)
        signals.extend(symbol_signals)
        symbol_summaries.append({"symbol": row["symbol"], "signals": len(symbol_signals), "status": "ok"})
        if args.progress:
            done = len(symbol_summaries)
            if done % args.progress_every == 0 or done == len(loaded):
                print(f"Backtested {done}/{len(loaded)} symbols; signals so far: {len(signals)}", flush=True)

    summary = summarize(signals, symbol_summaries, args)
    write_outputs(signals, symbol_summaries, summary, args.output_dir)
    return summary


async def fetch_history(symbol: str, limit: int, exchange: str) -> pd.DataFrame | None:
    if exchange == "bybit":
        return await fetch_bybit_history(symbol, limit)
    try:
        async with httpx.AsyncClient(base_url=data_loader.FAPI_BASE, timeout=30) as client:
            response = await client.get("/fapi/v1/klines", params={"symbol": symbol, "interval": "1h", "limit": limit})
            response.raise_for_status()
            return parse_klines(response.json())
    except Exception:
        return None


async def list_symbols_with_backoff(config: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    last_error = None
    for attempt in range(1, args.symbol_list_retries + 1):
        try:
            if args.exchange == "bybit":
                return await list_bybit_symbols(config)
            return await data_loader.list_symbols(config)
        except Exception as exc:
            last_error = exc
            wait = args.symbol_list_backoff_seconds * attempt
            print(f"Symbol list fetch failed on attempt {attempt}: {exc}. Waiting {wait}s.", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Could not fetch Binance symbol list after retries: {last_error}")


async def list_bybit_symbols(config: dict[str, Any]) -> list[dict[str, Any]]:
    universe = config.get("universe", {})
    excluded = set(universe.get("exclude_base_assets", []))
    excluded_symbols = set(universe.get("exclude_symbols", []))
    min_quote_volume = float(universe.get("min_quote_volume_24h", 0))
    instruments = []
    cursor = ""
    async with httpx.AsyncClient(base_url=BYBIT_BASE, timeout=30) as client:
        while True:
            params = {"category": "linear", "status": "Trading", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            response = await client.get("/v5/market/instruments-info", params=params)
            response.raise_for_status()
            payload = response.json()
            if payload.get("retCode") != 0:
                raise RuntimeError(f"Bybit instruments error {payload.get('retCode')}: {payload.get('retMsg')}")
            result = payload.get("result") or {}
            instruments.extend(result.get("list") or [])
            cursor = result.get("nextPageCursor") or ""
            if not cursor:
                break
        tickers_response = await client.get("/v5/market/tickers", params={"category": "linear"})
        tickers_response.raise_for_status()
        tickers_payload = tickers_response.json()
        if tickers_payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit tickers error {tickers_payload.get('retCode')}: {tickers_payload.get('retMsg')}")
    tickers = {
        row.get("symbol"): row
        for row in (tickers_payload.get("result") or {}).get("list") or []
    }
    rows = []
    for item in instruments:
        symbol = item.get("symbol")
        base = item.get("baseCoin")
        quote = item.get("quoteCoin")
        contract_type = item.get("contractType")
        if (
            quote != "USDT"
            or base in excluded
            or symbol in excluded_symbols
            or contract_type not in {"LinearPerpetual", ""}
            or (universe.get("crypto_only", True) and not _looks_like_crypto_symbol(symbol, base))
        ):
            continue
        ticker = tickers.get(symbol, {})
        quote_volume = _float(ticker.get("turnover24h"))
        if quote_volume < min_quote_volume:
            continue
        rows.append(
            {
                "symbol": symbol,
                "quote_volume_24h": quote_volume,
                "last_price": _float(ticker.get("lastPrice")),
            }
        )
    return sorted(rows, key=lambda row: row["quote_volume_24h"], reverse=True)


async def fetch_bybit_history(symbol: str, limit: int) -> pd.DataFrame | None:
    rows: list[list[str]] = []
    end_ms: int | None = None
    async with httpx.AsyncClient(base_url=BYBIT_BASE, timeout=30) as client:
        while len(rows) < limit:
            params: dict[str, Any] = {
                "category": "linear",
                "symbol": symbol,
                "interval": "60",
                "limit": min(1000, limit - len(rows)),
            }
            if end_ms is not None:
                params["end"] = end_ms
            try:
                response = await client.get("/v5/market/kline", params=params)
                response.raise_for_status()
                payload = response.json()
                if payload.get("retCode") != 0:
                    return None
                batch = (payload.get("result") or {}).get("list") or []
                if not batch:
                    break
                rows.extend(batch)
                oldest = min(int(item[0]) for item in batch)
                next_end = oldest - 1
                if end_ms == next_end:
                    break
                end_ms = next_end
            except Exception:
                return None
    if len(rows) < 250:
        return None
    rows = sorted(rows, key=lambda item: int(item[0]))[-limit:]
    return parse_bybit_klines(rows)


def parse_bybit_klines(rows: list[list[str]]) -> pd.DataFrame:
    parsed = []
    for row in rows:
        start_ms = int(row[0])
        open_price = float(row[1])
        high = float(row[2])
        low = float(row[3])
        close = float(row[4])
        volume = float(row[5])
        turnover = float(row[6])
        parsed.append(
            {
                "open_time": pd.to_datetime(start_ms, unit="ms", utc=True),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "close_time": pd.to_datetime(start_ms + 60 * 60 * 1000 - 1, unit="ms", utc=True),
                "quote_volume": turnover,
                "trades": 0,
                "taker_buy_base": volume / 2,
                "taker_buy_quote": turnover / 2,
                "ignore": "",
            }
        )
    return pd.DataFrame(parsed)


def backtest_symbol(row: dict[str, Any], candles: pd.DataFrame, config: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    df = add_indicators(candles)
    signals = []
    previous_state_rank = 0
    previous_classification = "Ignore"
    min_signal_rank = STATE_RANK[args.min_state]
    start = args.lookback_candles
    end = len(df) - args.forward_bars
    for idx in range(start, end, args.step):
        historical = df.iloc[idx + 1 - args.lookback_candles : idx + 1].copy()
        future = df.iloc[idx + 1 : idx + 1 + args.forward_bars].copy()
        if historical[["rsi14", "adx14", "mfi20"]].iloc[-1].isna().any():
            continue
        sd = SymbolData(
            symbol=row["symbol"],
            price=float(historical["close"].iloc[-1]),
            quote_volume_24h=float(row.get("quote_volume_24h", 0)),
            k1h=historical,
            k4h=historical,
            derivatives=DerivativesData(),
        )
        scan_row = analyse(sd, config)
        state_rank = STATE_RANK[scan_row.classification]
        upgraded = state_rank > previous_state_rank and state_rank >= min_signal_rank
        if upgraded:
            signals.append(label_signal(scan_row, historical, future, previous_classification, args.forward_bars))
        previous_state_rank = state_rank
        previous_classification = scan_row.classification
    return signals


def label_signal(scan_row, historical: pd.DataFrame, future: pd.DataFrame, previous_state: str, forward_bars: int) -> dict[str, Any]:
    entry = float(historical["close"].iloc[-1])
    future_high = float(future["high"].max())
    future_low = float(future["low"].min())
    final_close = float(future["close"].iloc[-1])
    mfe_pct = (future_high / entry - 1) * 100
    mae_pct = (future_low / entry - 1) * 100
    forward_return_pct = (final_close / entry - 1) * 100
    resistance = scan_row.breakout_level_resistance
    invalidation = scan_row.invalidated_below
    broke_resistance = bool(resistance is not None and future_high > resistance)
    invalidated = bool(invalidation is not None and future_low < invalidation)
    accepted = False
    if resistance is not None:
        accepted = int((future["close"] > resistance).sum()) >= 2
    if accepted and not invalidated:
        outcome = "CLEAN_WIN"
    elif broke_resistance and not accepted:
        outcome = "NO_FOLLOW_THROUGH"
    elif invalidated:
        outcome = "INVALIDATED"
    elif mfe_pct >= 1.5:
        outcome = "PARTIAL_WIN"
    else:
        outcome = "NO_FOLLOW_THROUGH"
    return {
        "symbol": scan_row.symbol,
        "signal_time": str(historical["close_time"].iloc[-1]),
        "previous_state": previous_state,
        "new_state": scan_row.classification,
        "entry_price": entry,
        "overall_score": scan_row.overall_score,
        "overall_score_display": scan_row.overall_score_display,
        "compression_score": scan_row.compression_score,
        "structural_pressure_score": scan_row.structural_pressure_score,
        "participation_score": scan_row.participation_score,
        "momentum_score": scan_row.momentum_score,
        "smart_money_score": scan_row.smart_money_score,
        "price_acceptance_score": scan_row.price_acceptance_score,
        "magnitude_score": scan_row.magnitude_score,
        "resistance": resistance,
        "invalidated_below": invalidation,
        "forward_bars": forward_bars,
        "forward_return_pct": round(forward_return_pct, 4),
        "max_favorable_excursion_pct": round(mfe_pct, 4),
        "max_adverse_excursion_pct": round(mae_pct, 4),
        "broke_resistance": broke_resistance,
        "accepted_above_resistance": accepted,
        "invalidation_hit": invalidated,
        "outcome": outcome,
        "classification_blockers": " | ".join(scan_row.classification_blockers),
    }


def summarize(signals: list[dict[str, Any]], symbol_summaries: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    by_state: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    by_symbol = {}
    for signal in signals:
        by_state[signal["new_state"]] = by_state.get(signal["new_state"], 0) + 1
        by_outcome[signal["outcome"]] = by_outcome.get(signal["outcome"], 0) + 1
        by_symbol[signal["symbol"]] = by_symbol.get(signal["symbol"], 0) + 1
    returns = [signal["forward_return_pct"] for signal in signals]
    mfes = [signal["max_favorable_excursion_pct"] for signal in signals]
    maes = [signal["max_adverse_excursion_pct"] for signal in signals]
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exchange": args.exchange,
        "symbols_tested": len(symbol_summaries),
        "symbols_with_signals": len(by_symbol),
        "setups_spotted": len(signals),
        "min_state": args.min_state,
        "history_candles": args.history_candles,
        "lookback_candles": args.lookback_candles,
        "forward_bars": args.forward_bars,
        "step": args.step,
        "by_state": by_state,
        "by_outcome": by_outcome,
        "avg_forward_return_pct": round(sum(returns) / len(returns), 4) if returns else None,
        "avg_max_favorable_excursion_pct": round(sum(mfes) / len(mfes), 4) if mfes else None,
        "avg_max_adverse_excursion_pct": round(sum(maes) / len(maes), 4) if maes else None,
        "top_signal_symbols": sorted(by_symbol.items(), key=lambda item: item[1], reverse=True)[:20],
    }


def write_outputs(signals: list[dict[str, Any]], symbol_summaries: list[dict[str, Any]], summary: dict[str, Any], output_dir: str) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (target / "symbol_summary.json").write_text(json.dumps(symbol_summaries, indent=2, default=str))
    if signals:
        with (target / "signals.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(signals[0].keys()))
            writer.writeheader()
            writer.writerows(signals)
    else:
        (target / "signals.csv").write_text("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward backtest for the isolated Breakout Radar.")
    parser.add_argument("--exchange", choices=["binance", "bybit"], default="binance")
    parser.add_argument("--config", default="config/balanced.yml")
    parser.add_argument("--history-candles", type=int, default=1500)
    parser.add_argument("--lookback-candles", type=int, default=200)
    parser.add_argument("--forward-bars", type=int, default=24)
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--min-quote-volume", type=float, default=None)
    parser.add_argument("--min-state", choices=["Developing Setup", "High Watch", "Breakout Radar Priority"], default="Developing Setup")
    parser.add_argument("--output-dir", default="outputs/backtests/latest")
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--symbol-list-retries", type=int, default=4)
    parser.add_argument("--symbol-list-backoff-seconds", type=int, default=20)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.min_quote_volume is None:
        config.setdefault("universe", {})["min_quote_volume_24h"] = 0
    summary = asyncio.run(run_backtest(config, args))
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _looks_like_crypto_symbol(symbol: str, base: str | None) -> bool:
    non_crypto_bases = {
        "XAU", "XAG", "SPY", "IWM", "EWY", "QQQ", "DIA", "GLD", "SLV",
        "SKHYNIX", "NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "META", "AMZN",
        "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD", "USD1",
        "USDE", "RLUSD", "EUR", "TRY",
    }
    if not base or base in non_crypto_bases:
        return False
    if symbol.startswith(("1000XAU", "XAU", "SPY", "IWM", "EWY", "QQQ")):
        return False
    if symbol.count("USDT") != 1:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
