"""Download Binance UM-futures monthly klines (15m + 1h) for the study universe.

Symbol universe: top N_SYMBOLS USDT perps by current 24h quote volume
(stables excluded). Monthly zips come from data.binance.vision; months where
a symbol did not yet trade 404 and are skipped. Each symbol/interval is
cached as a single pickle DataFrame in data/klines/.
"""
import io
import json
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from config import (DATA_DIR, END_MONTH, EXCLUDE, KLINES_DIR, N_SYMBOLS,
                    START_MONTH)

BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume",
        "ignore"]
NUM_COLS = ["open", "high", "low", "close", "volume", "quote_volume", "count",
            "taker_buy_volume", "taker_buy_quote_volume"]


def month_range(start, end):
    months = []
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return months


def pick_symbols():
    info = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo",
                        timeout=30).json()
    perps = {s["symbol"] for s in info["symbols"]
             if s["contractType"] == "PERPETUAL"
             and s["quoteAsset"] == "USDT"
             and s["status"] == "TRADING"}
    tickers = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr",
                           timeout=30).json()
    ranked = sorted((t for t in tickers if t["symbol"] in perps
                     and t["symbol"] not in EXCLUDE),
                    key=lambda t: float(t["quoteVolume"]), reverse=True)
    return [t["symbol"] for t in ranked[:N_SYMBOLS]]


def fetch_month(symbol, interval, month):
    url = f"{BASE}/{symbol}/{interval}/{symbol}-{interval}-{month}.zip"
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        raw = zf.read(zf.namelist()[0])
    first_line = raw.split(b"\n", 1)[0]
    header = 0 if first_line.startswith(b"open_time") else None
    df = pd.read_csv(io.BytesIO(raw), header=header, names=COLS,
                     usecols=[c for c in COLS if c != "ignore"])
    return df


def build_symbol(symbol, interval, months):
    out_path = os.path.join(KLINES_DIR, f"{symbol}_{interval}.pkl")
    if os.path.exists(out_path):
        return symbol, interval, "cached"
    frames = []
    for month in months:
        df = fetch_month(symbol, interval, month)
        if df is not None:
            frames.append(df)
    if not frames:
        return symbol, interval, "empty"
    df = pd.concat(frames, ignore_index=True)
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Binance switched zip timestamps to microseconds in 2025 -> normalise to ms
    ts = df["open_time"].astype("int64")
    df["open_time"] = ts.where(ts < 10**14, ts // 1000)
    df = (df.drop(columns=["close_time"])
            .dropna(subset=["open", "close"])
            .drop_duplicates(subset="open_time")
            .sort_values("open_time")
            .reset_index(drop=True))
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df.to_pickle(out_path)
    return symbol, interval, f"{len(df)} bars"


def main():
    os.makedirs(KLINES_DIR, exist_ok=True)
    months = month_range(START_MONTH, END_MONTH)
    sym_file = os.path.join(DATA_DIR, "symbols.json")
    if os.path.exists(sym_file):
        symbols = json.load(open(sym_file))
    else:
        symbols = pick_symbols()
        json.dump(symbols, open(sym_file, "w"), indent=1)
    print(f"{len(symbols)} symbols x {len(months)} months x 2 intervals")

    jobs = [(s, iv) for s in symbols for iv in ("15m", "1h")]
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(build_symbol, s, iv, months): (s, iv)
                for s, iv in jobs}
        for fut in as_completed(futs):
            s, iv, status = fut.result()
            done += 1
            print(f"[{done}/{len(jobs)}] {s} {iv}: {status}", flush=True)
    print("DOWNLOAD COMPLETE")


if __name__ == "__main__":
    sys.exit(main())
