"""
Trade Scanner Configuration
============================
All tunable parameters live here. Tweak thresholds and watchlist in one place.
"""
import os

# ─── Exchange ────────────────────────────────────────────────────────
EXCHANGE = "binance"
EXCHANGE_TYPE = "future"  # 'future' for perp, 'spot' for spot
EXCHANGE_CONFIG = {
    'options': {'defaultType': 'future'},
    'enableRateLimit': True,
}

# ─── Watchlist ───────────────────────────────────────────────────────
# Symbols in Binance Futures format (perp pairs)
WATCHLIST = [
    "UB/USDT:USDT",
    "INJ/USDT:USDT",
    "PORTAL/USDT:USDT",
    "NEAR/USDT:USDT",
    "HYPE/USDT:USDT",
    "RE/USDT:USDT",
    "MNT/USDT:USDT",
    "ONDO/USDT:USDT",
    "WLD/USDT:USDT",
    "LAB/USDT:USDT",
    "BTC/USDT:USDT",
]

# Display names (for alerts)
SYMBOL_LABELS = {
    "UB/USDT:USDT": "UB",
    "INJ/USDT:USDT": "INJ",
    "PORTAL/USDT:USDT": "PORTAL",
    "NEAR/USDT:USDT": "NEAR",
    "HYPE/USDT:USDT": "HYPE",
    "RE/USDT:USDT": "RE",
    "MNT/USDT:USDT": "MNT",
    "ONDO/USDT:USDT": "ONDO",
    "WLD/USDT:USDT": "WLD",
    "LAB/USDT:USDT": "LAB",
    "BTC/USDT:USDT": "BTC",
}

# ─── Timeframes ──────────────────────────────────────────────────────
TIMEFRAMES = {
    "trend": "4h",       # Higher timeframe for trend direction
    "entry": "1h",       # Lower timeframe for entry zone detection
}

# Candle count to fetch (200 is enough for EMA20/50, ATR, etc.)
CANDLE_LIMIT = 200

# ─── Pullback Short Pattern ──────────────────────────────────────────
PULLBACK_SHORT = {
    "ema_periods": [20, 50],
    "retrace_min_pct": 0.008,     # 0.8% minimum bounce off low
    "retrace_max_pct": 0.06,      # 6% maximum bounce (stops catching tops)
    "supply_zone_distance_pct": 0.03,  # within 3% of nearest resistance
    "oi_decline_threshold_pct": -0.3,  # OI change % to confirm weak bounce
    # Scoring thresholds
    "score_nascent": 2,
    "score_forming": 4,
    "score_ready": 6,
    "score_max": 9,
}

# ─── Breakdown Continuation Pattern ──────────────────────────────────
BREAKDOWN_CONTINUATION = {
    "range_lookback_candles": 12,       # candles to define the range
    "break_confirm_candles": 2,         # need N closes below range low
    "oi_decline_threshold_pct": -0.3,
    # Scoring thresholds
    "score_nascent": 2,
    "score_forming": 4,
    "score_ready": 6,
    "score_max": 8,
}

# ─── Bull/Bear Flag Pattern ────────────────────────────────────────────
FLAG_PATTERNS = {
    "lookback_candles": 24,        # candles to search for flagpole
    "min_flagpole_pct": 5.0,       # minimum 5% impulse to qualify as flagpole
    "strong_pole_pct": 10.0,       # 10%+ is a strong flagpole
    "min_flag_candles": 4,         # minimum candles in the flag/consolidation
    "max_retrace_pct": 50.0,       # max retrace of flagpole as % (50% = 0.5 Fibonacci)
    "tight_flag_pct": 4.0,         # flag range < 4% = tight
    "good_retrace_pct": 30.0,      # ideal retrace < 30% of pole
    # Scoring thresholds
    "score_nascent": 2,
    "score_forming": 4,
    "score_ready": 6,
}

# ─── OI Divergence Pattern ─────────────────────────────────────────────
OI_DIVERGENCE = {
    "score_nascent": 2,
    "score_forming": 4,
    "score_ready": 6,
}

# ─── Mean Reversion Pattern ────────────────────────────────────────────
MEAN_REVERSION = {
    "oversold_rsi": 35,            # RSI below this = oversold
    "deep_oversold_rsi": 25,       # RSI below this = deeply oversold
    "near_oversold_rsi": 40,       # RSI near oversold
    "tight_support_pct": 2.0,      # within 2% of support
    "near_support_pct": 5.0,       # within 5% of support
    "tight_candle_range": 2.0,     # avg candle range < 2% = stabilizing
    "moderate_candle_range": 4.0,  # avg candle range < 4% = moderating
    # Scoring thresholds
    "score_nascent": 2,
    "score_forming": 4,
    "score_ready": 6,
}

# ─── Breakout with OI Pattern ──────────────────────────────────────────
BREAKOUT_OI = {
    "break_proximity_pct": 2.0,    # within 2% of break level
    "oi_rise_threshold": 0.5,      # OI change % to confirm conviction
    "volume_surge_multiple": 1.5,  # volume surge relative to average
    # Scoring thresholds
    "score_nascent": 2,
    "score_forming": 4,
    "score_ready": 6,
}

# ─── RSI Divergence Pattern ────────────────────────────────────────────
RSI_DIVERGENCE = {
    "score_nascent": 2,
    "score_forming": 4,
    "score_ready": 6,
}

# ─── State Tracking ──────────────────────────────────────────────────
STATE_FILE = os.getenv(
    "WATCHLIST_STATE_FILE",
    os.path.join(os.path.dirname(__file__), "state/scanner_state.json"),
)

# ─── BTC Correlation ─────────────────────────────────────────────────
BTC_SYMBOL = "BTC/USDT:USDT"
BTC_CORRELATION_TIMEFRAMES = ["15m", "1h"]

# ─── ATR Default for Stop/Target Sizing ──────────────────────────────
ATR_MULTIPLIER_STOP = 1.5
ATR_MULTIPLIER_TP1 = 1.0
ATR_MULTIPLIER_TP2 = 2.0
