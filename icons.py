"""Resolve a small logo URL for every Binance perp symbol.

Real coin logos come from the CoinCap icon CDN, which covers most established
coins but not brand-new listings. For anything it doesn't have, we fall back to a
generated letter badge so every row shows a consistent icon (no blank cells).

Whether a coin has a real logo is probed once per base asset and cached to disk,
so repeat scans do zero network work and only newly-listed coins trigger a check.
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon_cache.json")
COINCAP = "https://assets.coincap.io/assets/icons/{}@2x.png"
FALLBACK = (
    "https://ui-avatars.com/api/?name={}&size=48&length=3"
    "&background=1f2937&color=8fb4ff&bold=true&font-size=0.36&format=png"
)
QUOTES = ("USDT", "USDC", "BUSD")


def base_asset(symbol):
    base = symbol
    for q in QUOTES:
        if base.endswith(q):
            base = base[: -len(q)]
            break
    if base.startswith("1000"):
        base = base[4:]
    return base


def _load_cache():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE)


async def _has_icon(client, sem, base):
    async with sem:
        try:
            r = await client.head(COINCAP.format(base.lower()), timeout=8.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False


async def _probe(cache, unknown):
    sem = asyncio.Semaphore(20)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(_has_icon(client, sem, b) for b in unknown))
    cache.update(dict(zip(unknown, results)))
    _save_cache(cache)
    return cache


def icon_urls(symbols):
    bases = sorted({base_asset(s) for s in symbols})
    cache = _load_cache()
    unknown = [b for b in bases if b not in cache]
    if unknown:
        cache = asyncio.run(_probe(cache, unknown))
    out = {}
    for s in symbols:
        b = base_asset(s)
        out[s] = COINCAP.format(b.lower()) if cache.get(b) else FALLBACK.format(b.upper())
    return out
