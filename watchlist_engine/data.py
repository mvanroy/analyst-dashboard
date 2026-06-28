"""
Data Fetcher
=============
Fetches OHLCV, Open Interest, and Funding Rate from exchanges via ccxt.
All public endpoints — no API key needed.

Binance: primary exchange for most coins
Bybit: fallback for coins not on Binance Futures (like MNT)
"""
import time
import ccxt
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from .config import WATCHLIST, CANDLE_LIMIT, BTC_SYMBOL
from .book_cvd import fetch_order_book, fetch_cvd


# ─── Symbol Map ──────────────────────────────────────────────────────
# Some coins only exist on certain exchanges as perpetuals
SYMBOL_EXCHANGE_MAP = {
    "MNT/USDT:USDT": "bybit",
    "UB/USDT:USDT": "binance",
    "INJ/USDT:USDT": "binance",
    "PORTAL/USDT:USDT": "binance",
    "NEAR/USDT:USDT": "binance",
    "HYPE/USDT:USDT": "binance",
    "RE/USDT:USDT": "binance",
    "ONDO/USDT:USDT": "binance",
    "WLD/USDT:USDT": "binance",
    "LAB/USDT:USDT": "binance",
}

# Also map BTC to the right exchange for each coin's correlation
BTC_EXCHANGE_MAP = {
    "bybit": "BTC/USDT:USDT",
    "binance": "BTC/USDT:USDT",
}


# ─── Exchange Cache ─────────────────────────────────────────────────
_exchange_cache = {}


def _get_exchange(exchange_name: str = "binance"):
    """Get or create the exchange instance (singleton)"""
    key = f"{exchange_name}_future"
    if key not in _exchange_cache:
        config = {
            'options': {'defaultType': 'future'},
            'enableRateLimit': True,
            'timeout': 8000,
        }
        exchange_class = getattr(ccxt, exchange_name)
        ex = exchange_class(config)
        ex.load_markets()
        _exchange_cache[key] = ex
    return _exchange_cache[key]


def _get_exchange_for_symbol(symbol: str):
    """Get the right exchange instance for a given symbol."""
    preferred = SYMBOL_EXCHANGE_MAP.get(symbol, "binance")
    return _get_exchange(preferred), preferred


def _safe_float(val, default=0.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ─── Public Fetch Functions ──────────────────────────────────────────


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    limit: int = CANDLE_LIMIT,
    exchange_name: str = "binance",
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV candles."""
    ex = _get_exchange(exchange_name)
    try:
        raw = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"[DATA ERROR] {symbol} {timeframe} ({exchange_name}): {e}", flush=True)
        return None


def fetch_open_interest(symbol: str, exchange_name: str = "binance") -> Optional[float]:
    """Fetch current open interest in USD terms.
    
    Handles various API return formats:
    - Binance: returns openInterestValue (can be None), openInterestAmount (string)
    - Bybit: returns openInterestValue (float)
    
    Falls back to amount * last_price when value is None.
    """
    ex = _get_exchange(exchange_name)
    try:
        oi = ex.fetch_open_interest(symbol)
        # Try openInterestValue first
        oi_value = _safe_float(oi.get('openInterestValue'), None)
        if oi_value is not None and oi_value > 0:
            return oi_value
        
        # Fall back: amount * last price
        oi_amount = _safe_float(oi.get('openInterestAmount'), 0)
        if oi_amount > 0:
            # Get last price from ticker
            ticker = ex.fetch_ticker(symbol)
            last_price = _safe_float(ticker.get('last'), 0)
            if last_price > 0:
                return oi_amount * last_price
            return oi_amount  # Return raw amount as last resort
        
        # Last resort: parse from info
        info = oi.get('info', {})
        if isinstance(info, dict):
            raw_oi = _safe_float(info.get('openInterest', info.get('open_interest', 0)), 0)
            if raw_oi > 0:
                return raw_oi
                
        return None
    except Exception as e:
        print(f"[OI ERROR] {symbol} ({exchange_name}): {e}", flush=True)
        return None


def fetch_funding_rate(symbol: str, exchange_name: str = "binance") -> Optional[float]:
    """Fetch current funding rate as percentage."""
    ex = _get_exchange(exchange_name)
    try:
        fr = ex.fetch_funding_rate(symbol)
        rate = _safe_float(fr.get('fundingRate'), None)
        if rate is not None:
            return rate * 100  # convert to percentage
        return None
    except Exception as e:
        print(f"[FUNDING ERROR] {symbol} ({exchange_name}): {e}", flush=True)
        return None


def fetch_ticker(symbol: str, exchange_name: str = "binance") -> Optional[Dict[str, Any]]:
    """Fetch 24hr ticker stats."""
    ex = _get_exchange(exchange_name)
    try:
        t = ex.fetch_ticker(symbol)
        return {
            'last': _safe_float(t.get('last'), 0),
            'high': _safe_float(t.get('high'), 0),
            'low': _safe_float(t.get('low'), 0),
            'baseVolume': _safe_float(t.get('baseVolume'), 0),
            'quoteVolume': _safe_float(t.get('quoteVolume'), 0),
            'change': _safe_float(t.get('change'), None),
            'percentage': _safe_float(t.get('percentage'), None),
        }
    except Exception as e:
        print(f"[TICKER ERROR] {symbol} ({exchange_name}): {e}", flush=True)
        return None


def fetch_historical_oi(symbol: str, exchange_name: str = "binance", 
                        timeframe: str = '4h', limit: int = 30) -> Optional[pd.DataFrame]:
    """Fetch historical open interest data. Not all exchanges support this."""
    ex = _get_exchange(exchange_name)
    try:
        if hasattr(ex, 'fetch_open_interest_history'):
            raw = ex.fetch_open_interest_history(symbol, timeframe, limit=limit)
            df = pd.DataFrame(raw)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        return None
    except Exception as e:
        # Many exchanges don't support this — not an error
        return None


def fetch_all_data(symbol: str) -> Dict[str, Any]:
    """Fetch all data for one symbol from the correct exchange."""
    ex_name = SYMBOL_EXCHANGE_MAP.get(symbol, "binance")
    
    result = {
        'symbol': symbol,
        'ohlcv_4h': None,
        'ohlcv_1h': None,
        'oi': None,
        'oi_history': None,
        'funding': None,
        'ticker': None,
        'order_book': None,
        'cvd': None,
        'exchange': ex_name,
        'error': None,
    }

    try:
        result['ohlcv_4h'] = fetch_ohlcv(symbol, '4h', exchange_name=ex_name)
        result['ohlcv_1h'] = fetch_ohlcv(symbol, '1h', exchange_name=ex_name)
        result['oi'] = fetch_open_interest(symbol, exchange_name=ex_name)
        result['funding'] = fetch_funding_rate(symbol, exchange_name=ex_name)
        result['ticker'] = fetch_ticker(symbol, exchange_name=ex_name)
        result['oi_history'] = fetch_historical_oi(symbol, exchange_name=ex_name)
        result['order_book'] = fetch_order_book(symbol, exchange_name=ex_name)
        result['cvd'] = fetch_cvd(symbol, exchange_name=ex_name)
    except Exception as e:
        result['error'] = str(e)

    return result


def fetch_btc_data(timeframes: list = None) -> Dict[str, Any]:
    """Fetch BTC data — try Binance first, fallback to Bybit."""
    if timeframes is None:
        timeframes = ['15m', '1h']
    result = {}
    for ex_name in ['binance', 'bybit']:
        try:
            btc_sym = BTC_EXCHANGE_MAP.get(ex_name, "BTC/USDT:USDT")
            for tf in timeframes:
                df = fetch_ohlcv(btc_sym, tf, limit=100, exchange_name=ex_name)
                if df is not None:
                    result[tf] = df
                    break  # Found data on this exchange
            if timeframes and all(tf in result for tf in timeframes):
                break  # All timeframes found
        except Exception:
            continue
    return result


def calc_correlation(coin_df: pd.DataFrame, btc_df: pd.DataFrame) -> float:
    """Pearson correlation between coin and BTC returns."""
    import numpy as np
    if coin_df is None or btc_df is None:
        return 0.0
    coin_returns = coin_df['close'].pct_change().dropna()
    btc_returns = btc_df['close'].pct_change().dropna()
    n = min(len(coin_returns), len(btc_returns), 50)
    if n < 5:
        return 0.0
    c = coin_returns.tail(n).values
    b = btc_returns.tail(n).values
    return float(np.corrcoef(c, b)[0, 1])
