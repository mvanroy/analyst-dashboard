from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import asyncio
import httpx
import pandas as pd

FAPI_BASE = "https://fapi.binance.com"


@dataclass
class DerivativesData:
    oi_hist: list[dict[str, Any]] | None = None
    funding_rate: float | None = None
    taker_ratio: list[dict[str, Any]] | None = None
    long_short_ratio: list[dict[str, Any]] | None = None

    @property
    def available(self) -> bool:
        return any(
            item is not None
            for item in (self.oi_hist, self.funding_rate, self.taker_ratio, self.long_short_ratio)
        )


@dataclass
class SymbolData:
    symbol: str
    price: float
    quote_volume_24h: float
    k1h: pd.DataFrame
    k4h: pd.DataFrame
    derivatives: DerivativesData = field(default_factory=DerivativesData)


async def list_symbols(config: dict[str, Any]) -> list[dict[str, Any]]:
    universe = config.get("universe", {})
    excluded = set(universe.get("exclude_base_assets", []))
    min_quote_volume = float(universe.get("min_quote_volume_24h", 0))
    async with httpx.AsyncClient(base_url=FAPI_BASE, timeout=30) as client:
        exchange_info, tickers = await _gather(
            _get(client, "/fapi/v1/exchangeInfo"),
            _get(client, "/fapi/v1/ticker/24hr"),
        )
    tradable = {
        row["symbol"]: row
        for row in exchange_info.json().get("symbols", [])
        if row.get("contractType") == universe.get("contract_type", "PERPETUAL")
        and row.get("quoteAsset") == universe.get("quote_asset", "USDT")
        and row.get("status") == universe.get("status", "TRADING")
        and row.get("baseAsset") not in excluded
    }
    symbols = []
    for ticker in tickers.json():
        symbol = ticker.get("symbol")
        quote_volume = _float(ticker.get("quoteVolume"))
        if symbol not in tradable or quote_volume < min_quote_volume:
            continue
        symbols.append(
            {
                "symbol": symbol,
                "quote_volume_24h": quote_volume,
                "last_price": _float(ticker.get("lastPrice")),
            }
        )
    return sorted(symbols, key=lambda row: row["quote_volume_24h"], reverse=True)


async def load_symbol(symbol_row: dict[str, Any], config: dict[str, Any]) -> SymbolData | None:
    scan = config.get("scan", {})
    limit = int(scan.get("lookback_candles", 200))
    include_derivatives = bool(scan.get("include_derivatives", True))
    symbol = symbol_row["symbol"]
    async with httpx.AsyncClient(base_url=FAPI_BASE, timeout=30) as client:
        try:
            k1h_resp, k4h_resp = await _gather(
                _get(client, "/fapi/v1/klines", params={"symbol": symbol, "interval": "1h", "limit": limit}),
                _get(client, "/fapi/v1/klines", params={"symbol": symbol, "interval": "4h", "limit": limit}),
            )
            k1h = parse_klines(k1h_resp.json())
            k4h = parse_klines(k4h_resp.json())
            if len(k1h) < 120 or len(k4h) < 60:
                return None
            derivatives = await fetch_derivatives(client, symbol) if include_derivatives else DerivativesData()
        except Exception:
            return None
    return SymbolData(
        symbol=symbol,
        price=float(k1h["close"].iloc[-1]),
        quote_volume_24h=float(symbol_row.get("quote_volume_24h", 0)),
        k1h=k1h,
        k4h=k4h,
        derivatives=derivatives,
    )


async def fetch_derivatives(client: httpx.AsyncClient, symbol: str) -> DerivativesData:
    data = DerivativesData()
    data.oi_hist = await _optional_json(
        client, "/futures/data/openInterestHist", {"symbol": symbol, "period": "1h", "limit": 30}
    )
    premium = await _optional_json(client, "/fapi/v1/premiumIndex", {"symbol": symbol})
    if premium and premium.get("lastFundingRate") is not None:
        data.funding_rate = _float(premium.get("lastFundingRate"))
    data.taker_ratio = await _optional_json(
        client, "/futures/data/takerlongshortRatio", {"symbol": symbol, "period": "1h", "limit": 30}
    )
    data.long_short_ratio = await _optional_json(
        client, "/futures/data/globalLongShortAccountRatio", {"symbol": symbol, "period": "1h", "limit": 10}
    )
    return data


def parse_klines(rows: list[list[Any]]) -> pd.DataFrame:
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_buy_base",
        "taker_buy_quote",
        "ignore",
    ]
    df = pd.DataFrame(rows, columns=cols)
    for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base", "taker_buy_quote"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df


async def _optional_json(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any | None:
    try:
        response = await _get(client, path, params=params, retries=2)
        return response.json()
    except Exception:
        return None


async def _gather(*requests):
    responses = await asyncio.gather(*requests)
    for response in responses:
        response.raise_for_status()
    return responses


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def _get(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any] | None = None,
    retries: int = 4,
) -> httpx.Response:
    for attempt in range(retries + 1):
        response = await client.get(path, params=params)
        if response.status_code not in {418, 429, 500, 502, 503, 504}:
            response.raise_for_status()
            return response
        if attempt >= retries:
            response.raise_for_status()
        retry_after = response.headers.get("Retry-After")
        delay = float(retry_after) if retry_after else min(30, 2 ** attempt)
        await asyncio.sleep(delay)
    raise RuntimeError("unreachable retry state")
