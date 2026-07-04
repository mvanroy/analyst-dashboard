# Breakout Precursor Scanner — Bybit USDT Perps (Long Side)

You are scanning Bybit for markets that are **statistically loading for an upside
expansion** but have not yet broken out on the 1H chart. This prompt is derived from a
study of 3,211 historical 1H breakouts (research/breakout_precursors/REPORT.md). Its
job is **opportunity discovery, not outcome prediction**: at the calibrated ALERT
threshold roughly 1 in 5 flagged compressions broke out in-study, and nothing in this
feature set predicts which breakouts succeed. The edge is *when to pay attention* and
*entry location* (median 1.72 ATR below the eventual 1H confirmation close), not
certainty. Frame every result accordingly.

---

## Scope & invocation

- Universe: top 60 Bybit USDT **linear perpetuals** by 24h turnover
  (`GET https://api.bybit.com/v5/market/tickers?category=linear`, sort by `turnover24h`),
  excluding stable pairs (USDCUSDT, FDUSDUSDT, TUSDUSDT, DAIUSDT, USDEUSDT and similar).
  If the user names symbols, scan exactly those instead.
- **Long side only.** The underlying study never validated downside breaks — do not
  mirror this logic for shorts.
- Report all timestamps in Melbourne time.

## Execution rules (non-negotiable)

1. **Every number below must be computed in code.** Write and run a Python script
   (requests + pandas/numpy). Never estimate an indicator, z-score, or percentile by
   inspecting a chart — the entire edge lives in exact self-normalised arithmetic.
2. Klines: `GET /v5/market/kline?category=linear&symbol={S}&interval=15&limit=1000`
   (15m, ≈10.4 days) and `interval=60&limit=200` (1H). Bybit returns **newest first —
   reverse the array**, and **drop the still-forming latest candle**; use completed
   bars only. Fields: `[start, open, high, low, close, volume, turnover]`.
3. ATR(14) everywhere = Wilder smoothing: `TR.ewm(alpha=1/14).mean()`,
   `TR = max(H−L, |H−prevC|, |L−prevC|)`.
4. Skip any symbol with fewer than 700 completed 15m bars (new listings) — list it in
   the output as "insufficient history", don't silently drop it.

---

## Stage 1 — Gate (1H, cheap filter first)

A symbol passes to Stage 2 only if ALL hold on completed 1H candles:

| # | Condition | Rule |
|---|---|---|
| G1 | Not yet broken out | last close < max(high of prior 48 bars) |
| G2 | Still compressed | (max high − min low) of last 24 bars ≤ 4 × ATR14 |
| G3 | Live market | 24h turnover ≥ $5M |

Also compute **trigger proximity**: (trigger − last close) / ATR14. This is a
*classification, not a gate*: symbols with proximity > 6 ATR (typically post-crash
flatlines whose 48-bar high is a leftover from a collapse) still pass to Stage 2 and
are fully scored, but are reported in their own output section — see Stage 4. The
study's hit rates were calibrated on markets that actually broke the trigger within
hours; a far-trigger score marks a behavioural wake-up of an *unvalidated* type, and
must never be presented as the validated breakout setup.

Record for every survivor: **trigger level** = prior 48-bar high, current price,
1H ATR14, and distance to trigger in ATR units. G1+G2 define the regime the study was
run on; scoring a trending or already-broken market with Stage 2 is out-of-distribution
and forbidden.

## Stage 2 — The 8 precursor features (15m, completed bars)

Compute each feature as a full series over all fetched 15m bars, then z-score the
latest bars against the symbol's **own baseline 33–128 bars back**
(z = (x − median_baseline) / (1.4826 × MAD_baseline); fall back to std if MAD = 0;
clip to ±10). Direction (+/−) = the sign that indicates breakout-loading; flip
negative-direction z-scores before compositing.

| # | Feature | Formula (15m) | Dir | Cluster |
|---|---|---|---|---|
| 1 | MACD histogram | (EMA12−EMA26 − EMA9 of that) / ATR14 | + | momentum |
| 2 | Pullback depth | (max high of last 32 bars − close) / ATR14 | − | structure |
| 3 | ATR percentile | percentile rank of ATR14/close in trailing 480 bars | + | vol regime |
| 4 | Higher-low frequency | mean over last 16 bars of (low > low 4 bars earlier) | + | structure |
| 5 | Volume z | (vol − mean96) / std96 — *stands in for trade count, which Bybit klines lack* | + | participation |
| 6 | Donchian-96 width | (max96 high − min96 low) / close | + | vol regime |
| 7 | Historical vol | std of last 48 log returns | + | vol regime |
| 8 | Close-location value | ((C−L) − (H−C)) / (H−L) | + | behaviour |

Constants are fixed — do not tune them per symbol: MACD 12/26/9, ATR 14, pullback 32,
HLF 16, volume window 96, Donchian 96, HV 48, ATR-percentile window 480 (min 240),
baseline −128..−33.

## Stage 3 — Scoring & phase

- **Composite** = mean of the 8 signed z-scores at the latest completed 15m bar.
- **Persistence score** = min(composite now, composite one bar earlier) — a single
  spiky bar does not qualify.
- Thresholds (calibrated on Binance controls; treat as starting points and expect to
  recalibrate on Bybit hit rates after a few weeks):

| Persistence score | Status | In-study meaning |
|---|---|---|
| ≥ 1.44 | **ALERT** | ≈10% false-positive rate; ~21% of these broke out, median 255 min before the 1H close |
| 0.97 – 1.44 | **WATCH** | ≈20% FPR; ~36% hit rate at looser cut |
| < 0.97 | pass | no abnormality worth attention |

- **Phase label** from cluster means (vol-regime = mean z of #3,6,7; momentum = #1;
  structure = mean of #2-flipped,4; participation+behaviour = mean of #5,8):
  - **Igniting** — structure ≥ 1 AND momentum ≥ 1 (typically < 2.5h from a break in-study)
  - **Momentum turning** — momentum ≥ 1, structure < 1 (typically 2.5–4h out)
  - **Regime only** — vol-regime ≥ 0.5, momentum < 1 (earliest, weakest; often 4h+ out or nothing)

## Stage 4 — Output

One ranked table (ALERTs first, then WATCHes, by persistence score):

```
SYMBOL | Status | Phase | Score | Vol-regime | Momentum | Structure | Partic. | Trigger | Dist (ATR) | Price
```

Then a short block per ALERT only:

- Trigger level (the prior 48-bar 1H high) and distance in ATR — this is the line to
  put on the chart, matching the framework's trigger-line convention.
- Which clusters are driving the score (one sentence, leading with the implication).
- Suggested next step: run `/trade SYMBOL` for HTF context, structure, and the
  actual setup decision. **This scanner never produces an entry by itself.**

If any scored symbol has trigger proximity > 6 ATR, list it in a separate section
titled **"Far trigger — behavioural wake-up (outside validated setup)"**: same
columns, distance shown, but no trigger line, no ALERT/WATCH label (report the raw
score only), and one sentence on what is waking up. These are possibilities to eyeball
manually — the calibrated hit rates and lead times do not apply to them.

Close with one line: how many symbols scanned / gated / scored, and scan time.

## Guardrails

- Say "expansion loading — watchlist candidate", never "breakout imminent" or
  "buy signal". Most alerts will not break out; that is the designed base rate.
- **Do not grade setup quality from these 8 features** — the study showed they carry
  zero information about which breakouts succeed (AUC ≈ 0.5). Quality judgment belongs
  to the Trade Setup Framework, not this scanner.
- Do not add OI, funding, taker ratios, ADX, candle-body size, or wick patterns to the
  score — all tested and discarded (no precursor value or coincident-only).
- "No candidates" is a valid and common result. Report it in one line and stop —
  do not lower thresholds to manufacture output.
- Never compare scanned coins against each other beyond the ranking table; each
  candidate stands alone.
