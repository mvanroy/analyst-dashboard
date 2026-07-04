"""15m feature battery + event-aligned window extraction.

All features are computed as full vectorized time series per symbol, then
sampled at offsets relative to the open of the (event or control) 1H bar.
Offset -1 = last completed 15m bar before that hour; offsets 0..3 sit inside
the breakout hour but still close before the 1H candle completes.

Per-event normalisation: robust z-score against the event's own baseline
window (offsets -128..-33, ~24h) using median / MAD, so every event is
measured as "how unusual is this bar relative to this market's own recent
behaviour", which removes symbol- and regime-level scale differences.
"""
import numpy as np
import pandas as pd

from config import BASELINE_OFFSETS, EVENT_OFFSETS

EPS = 1e-12


def _atr(df, n=14):
    pc = df["close"].shift(1)
    tr = np.maximum(df["high"] - df["low"],
                    np.maximum((df["high"] - pc).abs(),
                               (df["low"] - pc).abs()))
    return tr.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()


def _rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, min_periods=n,
                                adjust=False).mean()
    return 100 - 100 / (1 + up / (dn + EPS))


def _adx(df, n=14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0),
                        index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0),
                         index=df.index)
    pc = df["close"].shift(1)
    tr = np.maximum(df["high"] - df["low"],
                    np.maximum((df["high"] - pc).abs(),
                               (df["low"] - pc).abs()))
    alpha = 1.0 / n
    atr_ = tr.ewm(alpha=alpha, min_periods=n, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=alpha, min_periods=n,
                            adjust=False).mean() / (atr_ + EPS)
    mdi = 100 * minus_dm.ewm(alpha=alpha, min_periods=n,
                             adjust=False).mean() / (atr_ + EPS)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi + EPS)
    return dx.ewm(alpha=alpha, min_periods=n, adjust=False).mean()


def _linreg_slope(close, n=20):
    x = np.arange(n) - (n - 1) / 2.0
    w = x / (x ** 2).sum()
    vals = np.convolve(close.values, w[::-1], mode="valid")
    out = np.full(len(close), np.nan)
    out[n - 1:] = vals
    return pd.Series(out, index=close.index)


def _consec(cond):
    """Length of the current run of True values ending at each bar."""
    c = cond.astype(int).values
    out = np.zeros(len(c), dtype=float)
    run = 0
    for i, v in enumerate(c):
        run = run + 1 if v else 0
        out[i] = run
    return pd.Series(out, index=cond.index)


def compute_features(df):
    """df: 15m klines with open/high/low/close/volume/quote_volume/count/
    taker_buy_volume. Returns DataFrame of features indexed like df."""
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    v, qv, cnt = df["volume"], df["quote_volume"], df["count"]
    tb = df["taker_buy_volume"]
    atr = _atr(df, 14)
    rng = (h - l)
    body = (c - o)
    F = pd.DataFrame(index=df.index)

    # --- volatility ---
    F["atr_pct"] = atr / c
    F["atr_pctile_480"] = F["atr_pct"].rolling(480, min_periods=240) \
                                      .rank(pct=True)
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    F["bb_width"] = (4 * sd) / (mid + EPS)
    F["hv_48"] = np.log(c / c.shift(1)).rolling(48).std()
    dc96 = h.rolling(96).max() - l.rolling(96).min()
    dc24 = h.rolling(24).max() - l.rolling(24).min()
    F["donchian_width_96"] = dc96 / c
    F["range_compression_24v96"] = dc24 / (dc96 + EPS)

    # --- participation ---
    vmed = v.rolling(96, min_periods=48).median()
    vmean = v.rolling(96, min_periods=48).mean()
    vstd = v.rolling(96, min_periods=48).std()
    F["rel_volume"] = v / (vmed + EPS)
    F["volume_z"] = (v - vmean) / (vstd + EPS)
    qmean = qv.rolling(96, min_periods=48).mean()
    qstd = qv.rolling(96, min_periods=48).std()
    F["dollar_volume_z"] = (qv - qmean) / (qstd + EPS)
    cmean = cnt.rolling(96, min_periods=48).mean()
    cstd = cnt.rolling(96, min_periods=48).std()
    F["trade_count_z"] = (cnt - cmean) / (cstd + EPS)
    F["taker_buy_ratio"] = tb / (v + EPS)
    delta = 2 * tb - v                       # net taker flow per bar
    F["cvd_slope_8"] = delta.rolling(8).sum() / (vmean * 8 + EPS)

    # --- trend ---
    ema20 = c.ewm(span=20, adjust=False).mean()
    F["ema20_slope"] = (ema20 - ema20.shift(4)) / (atr + EPS)
    F["linreg_slope_20"] = _linreg_slope(c, 20) / (atr + EPS)
    F["adx_14"] = _adx(df, 14)
    F["rsi_14"] = _rsi(c, 14)
    F["roc_8"] = (c - c.shift(8)) / (atr + EPS)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26,
                                                       adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    F["macd_hist"] = (macd - signal) / (atr + EPS)

    # --- structure ---
    hi96 = h.rolling(96).max()
    hi32 = h.rolling(32).max()
    F["dist_from_high_96"] = (hi96 - c) / (atr + EPS)
    F["pullback_depth_32"] = (hi32 - c) / (atr + EPS)
    F["bars_since_high_32"] = 31 - h.rolling(32).apply(np.argmax, raw=True)
    F["higher_low_freq_16"] = (l > l.shift(4)).rolling(16).mean()
    F["lower_high_freq_16"] = (h < h.shift(4)).rolling(16).mean()

    # --- behaviour ---
    F["body_atr"] = body.abs() / (atr + EPS)
    F["body_frac"] = body.abs() / (rng + EPS)
    F["upper_wick_frac"] = (h - np.maximum(o, c)) / (rng + EPS)
    F["lower_wick_frac"] = (np.minimum(o, c) - l) / (rng + EPS)
    F["consec_up_closes"] = _consec(c > c.shift(1))
    F["consec_down_closes"] = _consec(c < c.shift(1))
    F["clv"] = ((c - l) - (h - c)) / (rng + EPS)
    F["avg_spread_8"] = (rng / (atr + EPS)).rolling(8).mean()

    return F


def extract_windows(feature_df, open_time_ms, event_open_ms_list):
    """Sample features at EVENT_OFFSETS around each event's 1H-bar open.

    Returns dict feature -> (n_events, n_offsets) raw matrix, plus a robust
    z-scored version against each event's own baseline, and the row mask of
    events that could be aligned.
    """
    idx_of = pd.Series(np.arange(len(open_time_ms)), index=open_time_ms)
    offsets = np.array(EVENT_OFFSETS)
    b0, b1 = BASELINE_OFFSETS
    base_off = np.arange(b0, b1 + 1)

    rows, kept = [], []
    for k, t in enumerate(event_open_ms_list):
        i0 = idx_of.get(t)
        if i0 is None or i0 + b0 < 0 or i0 + offsets[-1] >= len(feature_df):
            continue
        rows.append(i0)
        kept.append(k)
    if not rows:
        return None, None, []
    rows = np.array(rows)

    raw, z = {}, {}
    vals = feature_df.values
    cols = list(feature_df.columns)
    ev_idx = rows[:, None] + offsets[None, :]        # (n, n_off)
    base_idx = rows[:, None] + base_off[None, :]     # (n, n_base)
    for j, name in enumerate(cols):
        col = vals[:, j]
        m = col[ev_idx]
        b = col[base_idx]
        med = np.nanmedian(b, axis=1, keepdims=True)
        mad = np.nanmedian(np.abs(b - med), axis=1, keepdims=True)
        scale = 1.4826 * mad
        # fall back to baseline std when MAD collapses (discrete features)
        std = np.nanstd(b, axis=1, keepdims=True)
        scale = np.where(scale < EPS, std, scale)
        zz = (m - med) / np.where(scale < EPS, np.nan, scale)
        raw[name] = m
        z[name] = np.clip(zz, -10, 10)
    return raw, z, kept
