"""Shared configuration for the breakout-precursor study."""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
KLINES_DIR = os.path.join(DATA_DIR, "klines")
METRICS_DIR = os.path.join(DATA_DIR, "metrics")
FUNDING_DIR = os.path.join(DATA_DIR, "funding")
RESULTS_DIR = os.path.join(ROOT, "results")

# Study window (inclusive months, UTC)
START_MONTH = "2024-01"
END_MONTH = "2026-06"

N_SYMBOLS = 60                 # top USDT perps by 24h quote volume
EXCLUDE = {                    # stables / synthetic pairs
    "USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "EURUSDT",
    "USDPUSDT", "DAIUSDT", "AEURUSDT", "USD1USDT", "BFUSDUSDT",
}

# ---- 1H breakout definition ------------------------------------------------
DONCHIAN_LOOKBACK_1H = 48      # bars: breakout = close above prior 48h high
COMPRESSION_LOOKBACK_1H = 24   # bars used for the pre-breakout compression test
COMPRESSION_MAX_RANGE_ATR = 4.0  # prior 24-bar high-low range <= 4 x ATR(14)
ATR_LEN_1H = 14
DEDUP_BARS_1H = 48             # min spacing between events on the same symbol

# Success label: from the breakout level B, within the next 24 1H bars,
# high reaches B + 2*ATR before low reaches B - 1*ATR.
SUCCESS_TARGET_ATR = 2.0
SUCCESS_STOP_ATR = 1.0
SUCCESS_HORIZON_1H = 24

# ---- 15m analysis windows ---------------------------------------------------
# Offsets are in 15m bars relative to the OPEN of the breakout 1H bar.
# offset -1 = last completed 15m bar before the breakout hour begins.
# offsets 0..3 fall inside the breakout hour (still before 1H close/visibility).
EVENT_OFFSETS = list(range(-32, 4))    # 8h before -> inside breakout hour
BASELINE_OFFSETS = (-128, -33)         # ~24h of per-event baseline
CONTROLS_PER_EVENT = 2

RANDOM_SEED = 7
