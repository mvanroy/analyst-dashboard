from __future__ import annotations

import math

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    prev_close = d["close"].shift(1)
    true_range = pd.concat(
        [(d["high"] - d["low"]), (d["high"] - prev_close).abs(), (d["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    d["atr14"] = true_range.rolling(14).mean()
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["sma20"] = d["close"].rolling(20).mean()
    d["std20"] = d["close"].rolling(20).std()
    d["bb_width"] = (4 * d["std20"]) / d["sma20"]
    log_returns = np.log(d["close"] / d["close"].shift(1))
    d["hv20"] = log_returns.rolling(20).std() * math.sqrt(24 * 365)
    d["donchian_width"] = (d["high"].rolling(20).max() - d["low"].rolling(20).min()) / d["close"]
    d["range20"] = d["high"].rolling(20).max() - d["low"].rolling(20).min()
    d["keltner_width"] = (4 * d["atr14"]) / d["ema20"]
    d["std_pct"] = d["std20"] / d["close"]
    d["vwap"] = d["quote_volume"].cumsum() / d["volume"].replace(0, np.nan).cumsum()
    d["obv"] = (np.sign(d["close"].diff()).fillna(0) * d["volume"]).cumsum()
    d["cmf20"] = chaikin_money_flow(d, 20)
    d["rsi14"] = rsi(d["close"], 14)
    d["adx14"] = adx(d, true_range, 14)
    macd = d["close"].ewm(span=12, adjust=False).mean() - d["close"].ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    d["macd_hist"] = macd - signal
    d["roc10"] = (d["close"] / d["close"].shift(10) - 1) * 100
    d["mfi20"] = money_flow_index(d, 20)
    return d


def percentile_rank(series: pd.Series, lookback: int) -> float | None:
    values = series.dropna()
    if len(values) < lookback + 1:
        return None
    window = values.iloc[-lookback - 1 : -1]
    current = values.iloc[-1]
    return float((window <= current).mean() * 100)


def slope(series: pd.Series, bars: int) -> float:
    y = series.dropna().iloc[-bars:]
    if len(y) < bars:
        return 0.0
    x = np.arange(len(y))
    return float(np.polyfit(x, y.to_numpy(), 1)[0])


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def adx(df: pd.DataFrame, true_range: pd.Series, period: int) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([np.inf, -np.inf], np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def chaikin_money_flow(df: pd.DataFrame, period: int) -> pd.Series:
    spread = (df["high"] - df["low"]).replace(0, np.nan)
    multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / spread
    return (multiplier * df["volume"]).rolling(period).sum() / df["volume"].rolling(period).sum()


def money_flow_index(df: pd.DataFrame, period: int) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    flow = typical * df["volume"]
    positive = flow.where(typical > typical.shift(1), 0.0).rolling(period).sum()
    negative = flow.where(typical < typical.shift(1), 0.0).rolling(period).sum()
    ratio = positive / negative.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))
