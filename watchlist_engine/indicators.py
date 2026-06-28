"""
Technical Indicators
=====================
Pure Python — no TA-Lib required. All numpy-based.
"""
import numpy as np


def ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average"""
    result = np.zeros_like(data, dtype=float)
    result[:] = np.nan
    if len(data) < period:
        return result
    multiplier = 2.0 / (period + 1)
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index"""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period + 1:
        return result
    deltas = np.diff(data)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(period + 1, len(data)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range"""
    result = np.full_like(close, np.nan, dtype=float)
    if len(close) < period + 1:
        return result
    tr = np.zeros(len(close))
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i],
                    abs(high[i] - close[i - 1]),
                    abs(low[i] - close[i - 1]))
    result[period - 1] = np.mean(tr[1:period + 1])
    for i in range(period, len(close)):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period
    return result


def find_pivot_highs(high: np.ndarray, window: int = 3) -> list:
    """Find pivot high indices. A candle where high > both neighbors within window."""
    pivots = []
    for i in range(window, len(high) - window):
        if all(high[i] > high[i - j] for j in range(1, window + 1)) and \
           all(high[i] > high[i + j] for j in range(1, window + 1)):
            pivots.append((i, high[i]))
    return pivots


def find_pivot_lows(low: np.ndarray, window: int = 3) -> list:
    """Find pivot low indices."""
    pivots = []
    for i in range(window, len(low) - window):
        if all(low[i] < low[i - j] for j in range(1, window + 1)) and \
           all(low[i] < low[i + j] for j in range(1, window + 1)):
            pivots.append((i, low[i]))
    return pivots


def nearest_resistance_above(price: float, pivot_highs: list) -> float:
    """Find the closest pivot high above current price."""
    above = [ph for idx, ph in pivot_highs if ph > price]
    return min(above) if above else None


def nearest_support_below(price: float, pivot_lows: list) -> float:
    """Find the closest pivot low below current price."""
    below = [pl for idx, pl in pivot_lows if pl < price]
    return max(below) if below else None


def hh_hh_lower(high: np.ndarray, low: np.ndarray, window: int = 5) -> tuple:
    """
    Simple higher-high / lower-high detection on recent data.
    Returns (trend: str, is_downtrend: bool)
    """
    pivots_h = find_pivot_highs(high, window)
    pivots_l = find_pivot_lows(low, window)

    if len(pivots_h) < 3 or len(pivots_l) < 3:
        return "insufficient_data", False

    last_3h = [p[1] for p in pivots_h[-3:]]
    last_3l = [p[1] for p in pivots_l[-3:]]

    lower_highs = all(last_3h[i] > last_3h[i+1] for i in range(len(last_3h)-1))
    lower_lows = all(last_3l[i] > last_3l[i+1] for i in range(len(last_3l)-1))

    if lower_highs and lower_lows:
        return "downtrend", True
    return "mixed", False


def sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average"""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1:i + 1])
    return result