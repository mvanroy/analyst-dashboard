"""
Order Book & CVD Analysis
===========================
Fetches order book depth and Cumulative Volume Delta from Binance.
Identifies volume clusters (big grouped orders) from the order book.
All public endpoints — no API key needed.
"""
import time
import ccxt
import numpy as np
from typing import Dict, Optional, List, Tuple

_book_cache = {}
_cvd_cache = {}
_exchange_cache = {}
CACHE_TTL = 5


def _clean_symbol(symbol: str) -> str:
    return symbol.split(":")[0]


def _get_bucket_size(price: float) -> float:
    """Determine appropriate bucket size based on price level."""
    if price >= 1000:
        return price * 0.001  # 0.1% buckets for high price assets
    elif price >= 100:
        return price * 0.002  # 0.2%
    elif price >= 10:
        return price * 0.003  # 0.3%
    elif price >= 1:
        return price * 0.005  # 0.5%
    else:
        return price * 0.01   # 1% for sub-dollar coins


def _get_exchange(exchange_name: str):
    key = exchange_name or "binance"
    if key not in _exchange_cache:
        if key == "bybit":
            _exchange_cache[key] = ccxt.bybit({
                "options": {"defaultType": "linear"},
                "enableRateLimit": True,
                "timeout": 8000,
            })
        else:
            _exchange_cache[key] = ccxt.binance({
                "options": {"defaultType": "future"},
                "enableRateLimit": True,
                "timeout": 8000,
            })
    return _exchange_cache[key]


def compute_volume_clusters(bids: List, asks: List, mid_price: float, max_clusters: int = 6) -> Dict:
    """
    Group order book entries into price buckets to identify where big volume clusters sit.
    
    Returns structured data about the largest bid and ask clusters with 
    their distance from current price.
    """
    bucket_size = _get_bucket_size(mid_price)
    
    # Bucket bids
    bid_buckets = {}
    for price, vol in bids:
        bucket = round(price / bucket_size) * bucket_size
        bid_buckets[bucket] = bid_buckets.get(bucket, 0) + vol
    
    # Bucket asks
    ask_buckets = {}
    for price, vol in asks:
        bucket = round(price / bucket_size) * bucket_size
        ask_buckets[bucket] = ask_buckets.get(bucket, 0) + vol
    
    # Sort and get top clusters
    sorted_bids = sorted(bid_buckets.items(), key=lambda x: x[1], reverse=True)
    sorted_asks = sorted(ask_buckets.items(), key=lambda x: x[1], reverse=True)
    
    def format_clusters(clusters, side):
        result = []
        for price, vol in clusters[:max_clusters]:
            dist = (price - mid_price) / mid_price * 100 if side == "asks" else (mid_price - price) / mid_price * 100
            result.append({
                "price": price,
                "volume": round(vol, 2),
                "distance_pct": round(dist, 2),
                "bar_width": 0,  # calculated below
            })
        # Calculate relative bar widths (0-100)
        if result:
            max_vol = max(r["volume"] for r in result)
            for r in result:
                r["bar_width"] = int((r["volume"] / max_vol) * 100) if max_vol > 0 else 0
        return result
    
    bid_clusters = format_clusters(sorted_bids, "bids")
    ask_clusters = format_clusters(sorted_asks, "asks")
    
    # Total volume in each direction
    total_bid_cluster_vol = sum(c["volume"] for c in bid_clusters)
    total_ask_cluster_vol = sum(c["volume"] for c in ask_clusters)
    
    return {
        "bid_clusters": bid_clusters,
        "ask_clusters": ask_clusters,
        "total_bid_cluster_vol": round(total_bid_cluster_vol, 2),
        "total_ask_cluster_vol": round(total_ask_cluster_vol, 2),
        "bucket_size_pct": round(bucket_size / mid_price * 100, 3),
        "strongest_support": bid_clusters[0] if bid_clusters else None,
        "strongest_resistance": ask_clusters[0] if ask_clusters else None,
    }


def fetch_order_book(symbol: str, exchange_name: str = "binance", limit: int = 100) -> Optional[Dict]:
    """Fetch order book and analyze bid/ask walls + volume clusters."""
    cache_key = f"{exchange_name}:{symbol}"
    now = time.time()
    cached = _book_cache.get(cache_key)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["data"]

    try:
        clean = _clean_symbol(symbol)
        ex = _get_exchange(exchange_name)

        book = ex.fetch_order_book(clean, limit=limit)
        if not book or not book.get("bids") or not book.get("asks"):
            return None

        bids = book["bids"]
        asks = book["asks"]
        total_bid_vol = sum(b[1] for b in bids)
        total_ask_vol = sum(a[1] for a in asks)
        spread = asks[0][0] - bids[0][0] if bids and asks else 0
        mid = (bids[0][0] + asks[0][0]) / 2 if bids and asks else 0
        spread_pct = (spread / mid * 100) if mid else 0

        ba_ratio = total_bid_vol / total_ask_vol if total_ask_vol > 0 else 0

        # Top individual walls
        bid_walls = sorted(bids, key=lambda x: x[1], reverse=True)[:5]
        ask_walls = sorted(asks, key=lambda x: x[1], reverse=True)[:5]

        # Nearest walls
        nbw, nbd = None, None
        for b in bid_walls:
            if b[0] < mid:
                d = (mid - b[0]) / mid * 100
                if nbd is None or d < nbd:
                    nbd, nbw = d, b[0]
        naw, nad = None, None
        for a in ask_walls:
            if a[0] > mid:
                d = (a[0] - mid) / mid * 100
                if nad is None or d < nad:
                    nad, naw = d, a[0]

        # Volume clusters
        clusters = compute_volume_clusters(bids, asks, mid)

        result = {
            "mid_price": mid,
            "spread": spread,
            "spread_pct": spread_pct,
            "total_bid_vol": total_bid_vol,
            "total_ask_vol": total_ask_vol,
            "bid_ask_ratio": round(ba_ratio, 2),
            "top_bid_walls": [{"price": w[0], "volume": w[1]} for w in bid_walls],
            "top_ask_walls": [{"price": a[0], "volume": a[1]} for a in ask_walls],
            "nearest_bid_wall_price": nbw,
            "nearest_bid_wall_dist_pct": round(nbd, 3) if nbd else None,
            "nearest_ask_wall_price": naw,
            "nearest_ask_wall_dist_pct": round(nad, 3) if nad else None,
            "order_book_imbalance": "bullish" if ba_ratio > 1.3 else "bearish" if ba_ratio < 0.7 else "neutral",
            "clusters": clusters,
        }
        _book_cache[cache_key] = {"data": result, "ts": now}
        return result
    except Exception as e:
        return {"error": str(e)}


def fetch_cvd(symbol: str, exchange_name: str = "binance") -> Optional[Dict]:
    """Compute CVD approximation from 5-minute klines."""
    cache_key = f"cvd:{exchange_name}:{symbol}"
    now = time.time()
    cached = _cvd_cache.get(cache_key)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["data"]

    try:
        clean = _clean_symbol(symbol)
        ex = _get_exchange(exchange_name)

        ohlcv = ex.fetch_ohlcv(clean, "5m", limit=24)
        if not ohlcv or len(ohlcv) < 6:
            return None

        buy_vol = sell_vol = total_vol = 0.0
        for candle in ohlcv:
            o, c, v = candle[1], candle[4], candle[5]
            total_vol += v
            if c > o:
                buy_vol += v
            elif c < o:
                sell_vol += v
            else:
                buy_vol += v / 2
                sell_vol += v / 2

        if total_vol <= 0:
            return None

        buy_pct = (buy_vol / total_vol) * 100
        cvd = buy_vol - sell_vol
        result = {
            "taker_buy_pct": round(buy_pct, 1),
            "taker_sell_pct": round(100 - buy_pct, 1),
            "total_volume_5m": round(total_vol, 2),
            "cvd": round(cvd, 2),
            "cvd_pct": round(cvd / total_vol * 100, 1),
            "candles_analyzed": len(ohlcv),
            "cvd_signal": "bullish" if buy_pct > 55 else "bearish" if buy_pct < 45 else "neutral",
        }
        _cvd_cache[cache_key] = {"data": result, "ts": now}
        return result
    except Exception as e:
        return {"error": str(e)}


def assess_cvd(cvd_data: Optional[Dict], direction: str) -> Dict:
    if not cvd_data or cvd_data.get("error"):
        return {"verdict": "neutral", "score": 1, "note": "No CVD data"}
    signal = cvd_data.get("cvd_signal", "neutral")
    pct = cvd_data.get("taker_buy_pct", 50)
    if direction == "short":
        if signal == "bearish":
            return {"verdict": "confirms", "score": 2, "note": f"Sell pressure ({pct}% buy)"}
        elif signal == "bullish":
            return {"verdict": "contradicts", "score": 0, "note": f"Buy pressure ({pct}% buy)"}
        return {"verdict": "neutral", "score": 1, "note": f"Neutral ({pct}% buy)"}
    else:
        if signal == "bullish":
            return {"verdict": "confirms", "score": 2, "note": f"Buy pressure ({pct}% buy)"}
        elif signal == "bearish":
            return {"verdict": "contradicts", "score": 0, "note": f"Sell pressure ({pct}% buy)"}
        return {"verdict": "neutral", "score": 1, "note": f"Neutral ({pct}% buy)"}


def assess_order_book(book_data: Optional[Dict], direction: str) -> Dict:
    if not book_data or book_data.get("error"):
        return {"verdict": "neutral", "score": 1, "note": "No order book data"}
    imbalance = book_data.get("order_book_imbalance", "neutral")
    ba_ratio = book_data.get("bid_ask_ratio", 1)
    clusters = book_data.get("clusters", {})
    sr = clusters.get("strongest_resistance", {})
    ss = clusters.get("strongest_support", {})

    if direction == "short":
        wall_info = ""
        if sr and sr.get("distance_pct", 99) < 2:
            wall_info = f" | Resistance ${sr['price']:.1f} ({sr['distance_pct']:.1f}%)"
        if imbalance == "bearish":
            return {"verdict": "confirms", "score": 2, "note": f"Ratio {ba_ratio}{wall_info}"}
        elif imbalance == "bullish":
            return {"verdict": "contradicts", "score": 0, "note": f"Ratio {ba_ratio}{wall_info}"}
        return {"verdict": "neutral", "score": 1, "note": f"Ratio {ba_ratio}{wall_info}"}
    else:
        wall_info = ""
        if ss and ss.get("distance_pct", 99) < 2:
            wall_info = f" | Support ${ss['price']:.1f} ({ss['distance_pct']:.1f}%)"
        if imbalance == "bullish":
            return {"verdict": "confirms", "score": 2, "note": f"Ratio {ba_ratio}{wall_info}"}
        elif imbalance == "bearish":
            return {"verdict": "contradicts", "score": 0, "note": f"Ratio {ba_ratio}{wall_info}"}
        return {"verdict": "neutral", "score": 1, "note": f"Ratio {ba_ratio}{wall_info}"}


def compute_cvd_from_ohlcv(ohlcv_4h, ohlcv_1h) -> Dict:
    """
    Compute per-candle CVD from OHLCV data and detect CVD/price divergences.

    CVD per candle = volume if close > open else -volume
    Then we compare price swings against CVD swings to detect divergence.
    """
    if ohlcv_4h is None or len(ohlcv_4h) < 30:
        return {"detected": False, "signal": "neutral"}

    close = ohlcv_4h['close'].values
    high = ohlcv_4h['high'].values
    low = ohlcv_4h['low'].values
    volume = ohlcv_4h['volume'].values if 'volume' in ohlcv_4h.columns else np.ones(len(close))
    open_p = ohlcv_4h['open'].values

    # Per-candle CVD: positive if close > open, negative if close < open
    cvd_per = np.where(close > open_p, volume, -volume)

    n = len(close)

    # Find recent swing lows in price (last 20 candles)
    lookback = min(30, n)
    recent = close[-lookback:]
    recent_cvd = cvd_per[-lookback:]
    recent_high = high[-lookback:]
    recent_low = low[-lookback:]

    # Find price low and corresponding CVD low
    price_min_idx = int(np.argmin(recent))
    price_min_val = recent[price_min_idx]

    # CVD value at that same point
    cvd_at_price_min = recent_cvd[price_min_idx]

    # Find CVD low in same window
    cvd_min_idx = int(np.argmin(recent_cvd))
    cvd_min_val = recent_cvd[cvd_min_idx]
    price_at_cvd_min = recent[cvd_min_idx]

    # Bullish divergence: price made lower low, but CVD made higher low
    # i.e., price_min_val is the lowest price, but cvd at that point is NOT the lowest CVD
    bullish_div = False
    bearish_div = False

    # Check for divergence in the last 20 candles
    sub_lookback = min(20, len(recent))

    # Find most significant price swing low
    swing_low_idx = int(np.argmin(recent[-sub_lookback:]))
    swing_low_price = recent[-sub_lookback:][swing_low_idx]

    # Check prior swing (candles before the lowest point)
    prior_start = max(0, sub_lookback - 12)
    prior_end = max(1, swing_low_idx - 2) if swing_low_idx > 3 else 1

    if prior_end > prior_start:
        prior_slice = recent[-sub_lookback:][prior_start:prior_end]
        if len(prior_slice) > 0:
            prior_low_idx_in_slice = int(np.argmin(prior_slice))
            prior_low_price = prior_slice[prior_low_idx_in_slice]
            prior_low_global_idx = prior_start + prior_low_idx_in_slice

            # CVD at prior low vs CVD at current low
            cvd_at_prior = recent_cvd[-sub_lookback:][prior_low_global_idx]
            cvd_at_current = recent_cvd[-sub_lookback:][swing_low_idx]

            # Bullish divergence: price made lower low, CVD made higher low
            if swing_low_price < prior_low_price * 0.995 and cvd_at_current > cvd_at_prior * 1.01:
                bullish_div = True

    # Bearish divergence: price made higher high, CVD made lower high
    # Find swing highs
    swing_high_idx = int(np.argmax(recent[-sub_lookback:]))
    swing_high_price = recent[-sub_lookback:][swing_high_idx]

    prior_high_start = max(0, sub_lookback - 12)
    prior_high_end = max(1, swing_high_idx - 2) if swing_high_idx > 3 else 1

    if prior_high_end > prior_high_start:
        prior_slice_h = recent[-sub_lookback:][prior_high_start:prior_high_end]
        if len(prior_slice_h) > 0:
            prior_high_idx_in_slice = int(np.argmax(prior_slice_h))
            prior_high_price = prior_slice_h[prior_high_idx_in_slice]
            prior_high_global_idx = prior_high_start + prior_high_idx_in_slice

            cvd_at_prior_high = recent_cvd[-sub_lookback:][prior_high_global_idx]
            cvd_at_current_high = recent_cvd[-sub_lookback:][swing_high_idx]

            if swing_high_price > prior_high_price * 1.005 and cvd_at_current_high < cvd_at_prior_high * 0.99:
                bearish_div = True

    # Calculate aggregate CVD trend over last 12 candles
    recent_12_cvd = cvd_per[-12:] if len(cvd_per) >= 12 else cvd_per
    net_cvd = float(np.sum(recent_12_cvd))
    cvd_trend = (net_cvd / max(float(np.sum(np.abs(recent_12_cvd))), 0.001)) * 100 if len(recent_12_cvd) > 0 else 0

    signal = "neutral"
    if bullish_div:
        signal = "bullish_divergence"
    elif bearish_div:
        signal = "bearish_divergence"
    elif cvd_trend > 20:
        signal = "bullish"
    elif cvd_trend < -20:
        signal = "bearish"

    return {
        "detected": bullish_div or bearish_div,
        "signal": signal,
        "bullish_divergence": bullish_div,
        "bearish_divergence": bearish_div,
        "net_cvd_12_candles": round(net_cvd, 2),
        "cvd_trend_pct": round(cvd_trend, 1),
        "analysis_note": _cvd_note(bullish_div, bearish_div, cvd_trend, swing_low_price, swing_high_price),
    }


def _cvd_note(bullish_div, bearish_div, cvd_trend, swing_low, swing_high):
    if bullish_div:
        return f"Bullish CVD divergence: lower low (${swing_low:.4f}) but CVD rising — accumulation"
    if bearish_div:
        return f"Bearish CVD divergence: higher high (${swing_high:.4f}) but CVD falling — distribution"
    if cvd_trend > 15:
        return f"Strong buying pressure ({cvd_trend:+.0f}% CVD) — aggressive bids"
    if cvd_trend < -15:
        return f"Strong selling pressure ({cvd_trend:+.0f}% CVD) — aggressive offers"
    return ""
