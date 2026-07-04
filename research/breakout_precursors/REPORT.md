# What Changes First? 15-Minute Precursors of 1-Hour Breakouts

**Binance USDT perpetual futures · Jan 2024 – Jun 2026 · 3,211 breakout events, 57 symbols**

---

## 1. Headline answers

**The hypothesis is confirmed.** Successful 1H breakouts are measurably different on the
15m chart hours before the 1H breakout candle closes — but the *kind* of signal changes
with distance from the breakout:

1. **The volatility regime changes first (≥ 8¾ hours out, window-censored).**
   ATR percentile, historical volatility and 96-bar Donchian width separate future
   breakout markets from ordinary consolidations at *every* offset we tested, out to the
   edge of the 8-hour lookback window. The effect is asymmetric: it is less that
   pre-breakout markets get loud, more that ordinary consolidations go quiet (control
   median ATR-percentile z = −0.40 at −8h vs −0.07 for events). A compression whose
   volatility floor *holds* is the earliest tell.

2. **Momentum turns next (≈ 4¼ hours out).** The 15m MACD histogram is the earliest
   significant *directional* precursor (sustained from −255 min, AUC rising from 0.53 at
   −4h to 0.73 at the last bar before the breakout hour). ROC follows at −210 min.

3. **Participation arrives ≈ 3 hours out.** Trade-count z-score is significant from
   −180 min — transaction count leads volume (−135 min) by ~45 minutes, making it the
   single best participation variable.

4. **Structure ignites in the last 2½ hours.** Pullback depth starts refilling from
   −180 min and becomes the strongest single structural signal (signed AUC 0.68 in the
   final hour); higher-low frequency turns from −150 min; close-location-value (closes
   near bar highs) from −105 min.

5. **How much earlier than the breakout candle?** A composite detector built from the
   8 surviving features, thresholded at a 10% false-positive rate on matched
   non-breakout consolidations, fires a **median 255 minutes (≈ 4¼ h) before the 1H
   breakout close** (75% of detections ≥ 2h early, 52% ≥ 4h early) and enters a
   **median 1.72 ATR cheaper** than the 1H confirmation close — against a median 24h
   post-breakout run of 4.30 ATR from the breakout level. It catches ~21% of successful
   breakouts at that false-positive cost; at 20% FPR it catches 36% with a median
   300-minute lead.

6. **The one thing the 15m tape does NOT tell you: which breakouts will succeed.**
   Success-vs-failure AUC is 0.48–0.53 for every one of the 38 variables. The
   pre-breakout tape identifies *that* an expansion attempt is loading, not *whether*
   it will hold. Filtering for quality has to come from somewhere else (HTF context).

---

## 2. Methodology

### Data
- Top 60 USDT perpetuals by 24h quote volume (stables excluded), Binance UM futures.
- Monthly 15m and 1h klines from `data.binance.vision`, 2024-01 → 2026-06
  (~4.7M 15m bars). Klines include trade count and taker-buy volume.
- Derivatives: full funding-rate history via REST; open interest and long/short ratios
  from the daily `metrics` archive (5-min granularity) for every event/control window.
- **Liquidation volume is not reproducible historically** from public Binance data (the
  force-order stream is real-time only, and there is no archive). Not tested.

### Event definition (objective, on completed 1H bars)
- **Breakout:** close above the prior 48-bar (2-day) Donchian high.
- **From compression:** the preceding 24-bar high-low range ≤ 4 × ATR(14) — the market
  must still look "ordinary" on the 1H before the break.
- **De-duplication:** ≥ 48 bars between events per symbol.
- **Success label:** from breakout level B, high reaches B + 2×ATR before low touches
  B − 1×ATR, within 24 hours (a 2R-before-1R outcome). 1,634 of 3,211 events (51%)
  succeeded. Analysis compares **successful events vs controls** throughout.
- **Visibility timestamp:** the close of the breakout 1H candle. All lead times are
  measured against this moment.

### Controls
6,422 windows passing the identical compression filter with **no** Donchian break at
the bar or in the following 24 hours — i.e. consolidations that stayed consolidations.
Same symbols, same period, same de-dup spacing, 2 controls per event.

### Measurement
- 38 features computed on every 15m bar (list in §4), sampled at offsets −32 … −1
  (8h → 15 min) before the breakout-hour open, plus 0…+3 inside the breakout hour.
- **Per-event robust normalisation:** every feature is z-scored against the *same
  market's own* baseline 8–32 hours earlier (median/MAD), so results measure "how
  unusual vs this market's recent self", never cross-symbol scale.
- **Tests per feature × offset:** Mann-Whitney AUC (events vs controls) and one-sample
  Wilcoxon (event z vs 0), Benjamini-Hochberg FDR across all 38 × 36 tests.
- **Earliest lead:** most distant offset from which significance (q < 0.05 and signed
  AUC ≥ 0.54) is sustained through to the breakout hour (one gap allowed).
- **Trigger stats:** per-feature threshold set at the 90th percentile of the control
  distribution → every feature is scored at a fixed 10% false-positive rate, making hit
  rates and leads directly comparable.
- **Consistency:** share of the 54 symbols (≥ 5 events each) whose own event-vs-control
  AUC agrees in direction with the global result.

---

## 3. The timeline of a breakout (what changes, in order)

| When (before 1H visibility) | What changes | Evidence |
|---|---|---|
| **≥ 8¾ h** (censored at window edge) | Volatility regime holds up while ordinary consolidations decay: ATR percentile, HV(48), Donchian-96 width all elevated vs controls | AUC 0.55–0.58 at −8h, q < 10⁻¹⁹ |
| **≈ 8 h → 4 h** | The future breakout looks like a *mature, deeper pullback*: more bars since the last 32-bar high, price further below the range high, more consecutive down closes than controls | pullback_depth AUC 0.557 at −8h (deep side) |
| **−255 min** | **Momentum turn:** MACD histogram flips and stays significant — the earliest directional signal | AUC 0.53 → 0.73 by −15 min |
| **−210 min** | Rate-of-change (8-bar) confirms | AUC 0.66 final hour |
| **−180 min** | **Participation:** trade-count z turns up (leads volume by ~45 min); pullback begins refilling — depth now *shrinking* | trade_count AUC 0.62 at −15 min |
| **−150 min** | Structure: higher-low frequency rises, lower-high frequency falls | AUC 0.60 final hour |
| **−135 min** | Volume z / relative volume / dollar volume confirm; CVD slope turns positive | AUC 0.57–0.59 |
| **−120 min** | Retail long/short ratio starts *falling* (crowd fades the move) | AUC 0.57 (inverse) |
| **−105 min** | Close-location-value: 15m closes migrate to the top of their ranges | AUC 0.58, consistency 98% |
| **−75 min** | Late confirmations only: ADX, distance-to-range-high, average spread | AUC 0.54–0.55 |
| **Breakout hour** | Everything peaks; body expansion (body_atr) only becomes abnormal *inside* this hour — candle size is a coincident signal, not a precursor | — |

The behavioural arc: **an elevated-volatility compression → a mature pullback that quietly
stops making progress downward → momentum flips → transactions pick up before volume →
higher lows stack and closes pin to bar highs → the 1H candle everyone sees.**
By the time the 1H breakout candle closes, the 15m tape has typically been abnormal for
3–4 hours.

---

## 4. Ranked variable report

Full numbers in `results/feature_stats.csv`; per-offset detail in `results/offset_stats.csv`.
"Lead" = sustained significance vs controls before the 1H close. "Hit@10%" = share of
successful breakouts flagged by that feature alone at a fixed 10% FPR on controls.
"Consist." = share of 54 symbols agreeing in direction. Redundancy: |ρ| > 0.7 with a
stronger kept feature (mean z, final 2h).

### KEEP — 8 non-redundant precursors (one per behaviour cluster)

| # | Feature | Cluster | Lead (min) | AUC final hr | Hit@10% | Consist. | Notes |
|---|---|---|---|---|---|---|---|
| 1 | **MACD histogram** (12/26/9, ATR-norm) | momentum | **255** | 0.68 | 16% | 96% | earliest directional signal |
| 2 | **Pullback depth** (vs 32-bar high, ATR) | structure | **180** | 0.68 (inv) | 7% | 100% | deep early → refilling late; the flip is the signal |
| 3 | **ATR percentile** (480-bar) | vol regime | **≥ 525** (censored) | 0.61 | 19% | 94% | strongest regime gate; also the best single trigger |
| 4 | **Higher-low frequency** (16-bar) | structure | **150** | 0.60 | 13% | 89% | direct micro-structure read |
| 5 | **Trade-count z** (vs 24h) | participation | **180** | 0.59 | 12% | 85% | leads volume by ~45 min |
| 6 | **Donchian-96 width** | vol regime | **450** | 0.59 | 15% | 87% | slow regime confirmation |
| 7 | **HV(48)** | vol regime | **≥ 525** (censored) | 0.58 | 16% | 81% | survives dedup vs ATR pct (ρ ≤ 0.7) |
| 8 | **Close-location value** | behaviour | **105** | 0.58 | 10% | 98% | most consistent feature in the set; late but nearly universal |

### TEST FURTHER — real signal, but redundant or weaker

| Feature | Lead (min) | AUC final hr | Why not KEEP |
|---|---|---|---|
| RSI(14) | 165 | 0.67 | ρ > 0.7 with pullback depth — same reclaim information |
| ROC(8) | 210 | 0.66 | duplicate of MACD histogram |
| EMA20 slope | 165 | 0.64 | duplicate of pullback depth |
| LinReg slope(20) | 150 | 0.62 | duplicate of pullback depth |
| ATR % of price | ≥ 525 | 0.60 | duplicate of ATR percentile |
| Lower-high frequency | 135 | 0.60 (inv) | mirror of higher-low frequency |
| Dollar volume z / Volume z / Rel. volume | 135 | 0.58–0.59 | all duplicate trade-count z, and lag it |
| Bollinger-band width | 195 | 0.57 | weaker cousin of the kept vol trio |
| **Retail long/short ratio Δ4h** (inverse) | 120 | 0.57 | best derivatives signal: crowd gets *shorter* into the move; only 30-day-lagged public data, worth a dedicated study |
| CVD slope (taker-flow, 8-bar) | 135 | 0.57 | real but late and modest |
| Consecutive up-closes | 90 | 0.56 | crude version of CLV |
| Distance from 96-bar high | 75 | 0.55 (inv) | direction flips across the window; hard to use |

### DISCARD — failed to justify inclusion

| Feature | Verdict |
|---|---|
| Taker-buy ratio | marginal (0.55) and adds nothing over CVD slope |
| Consecutive down-closes | early-phase curiosity, no reliable trigger |
| Bars-since-32-bar-high | early-phase only, consistency 65% |
| ADX(14) | **coincident, not predictive** — significant only from −75 min |
| Average spread (8-bar) | late, weak (0.54) |
| Candle body / ATR | **abnormal only inside the breakout hour** — this is the breakout, not a precursor |
| Body fraction, upper/lower wick fractions | pure noise at every horizon (AUC ≈ 0.50) |
| Range compression 24v96 | no added value over the Donchian/ATR set |
| OI Δ1h / OI Δ4h | 0.53–0.54, final 2h only, consistency 69% — OI follows price here, it does not lead |
| Funding rate, funding Δ24h | nothing (0.47–0.51); funding reprices after breakouts |
| Top-trader L/S Δ4h | no precursor value (0.51); *only* variable with a hint of success-prediction (succ-vs-fail AUC 0.53) — the single derivatives idea worth a follow-up |
| Taker long/short vol ratio | 0.52, inconsistent |
| Liquidation volume | **untestable** — no public historical archive |

---

## 5. Composite model (grouped 5-fold CV, no symbol overlap between folds)

Logistic regression, successful events vs controls, features averaged per horizon band:

| Horizon before 1H visibility | Cross-validated AUC |
|---|---|
| 4¼ – 8¾ h | **0.639 ± 0.006** |
| 2¼ – 4¼ h | **0.658 ± 0.012** |
| 1 – 2 h (last four 15m bars before the breakout hour) | **0.798 ± 0.014** |

Sequential walk-forward detector (mean signed z of the 8 KEEP features, 2-bar
persistence, threshold set on controls):

| Control FPR | Hit rate | Median lead | ≥ 2h early | ≥ 4h early |
|---|---|---|---|---|
| 5% | 12.6% | 240 min | 74% | 52% |
| **10%** | **20.9%** | **255 min** | **75%** | **52%** |
| 20% | 36.3% | 300 min | 82% | 61% |

At the 10% operating point the detector's entry is a **median 1.72 ATR below the 1H
confirmation close** (IQR 1.14–2.38, n = 342), against a median 24h excursion of
4.30 ATR above the breakout level for successful events — early detection roughly
**doubles the favourable-excursion-to-risk ratio** relative to waiting for confirmation.

## 6. Robustness

- **Across time:** all 8 KEEP features hold direction and magnitude in each of 2024
  (533 events), 2025 (702) and 2026 (398). ATR percentile was strongest in 2025;
  momentum/structure features are remarkably flat across years.
- **Across markets:** consistency 81–100% across the 54 symbols with ≥ 5 events.
- **Multiple testing:** all quoted significance survives BH-FDR across 1,368 tests
  (typical top-feature q-values < 10⁻³⁰ in the final hours).

## 7. Honest limitations

1. **Regime leads are censored:** the vol-regime trio is significant at the earliest
   offset tested (−8h); its true lead is longer. Extend the window if the exact onset
   matters.
2. **The detector's hit rate is modest by design.** One in five successful breakouts
   flagged at 10% FPR is what a genuinely early signal looks like; most of the
   discriminating power (AUC 0.80) concentrates in the final 2 hours. There is no
   free 8-hour-early, 90%-hit-rate signal in this feature set.
3. **Long side only.** Downside breaks were not studied; wick/CLV asymmetries suggest
   shorts may differ.
4. **Controls share the compression filter but not macro context** (BTC regime,
   session time). Both cut across events and controls symmetrically, but a
   session-time-stratified rerun is a sensible follow-up.
5. **Success prediction is an open problem** — nothing on the 15m tape before the
   breakout separates the 51% that ran from the 49% that failed (top-trader
   positioning is the only lead worth chasing, AUC 0.53).

## 8. Reproduce / extend

```
.venv/bin/python download_data.py     # ~375 MB klines cache
.venv/bin/python detect_breakouts.py  # events.json / controls.json
.venv/bin/python build_windows.py     # 15m feature windows (windows.pkl)
.venv/bin/python derivatives.py       # OI / L-S / funding windows
.venv/bin/python analyze.py           # feature_stats.csv, offset_stats.csv
.venv/bin/python composite.py         # composite CV + sequential detector
```

Tunables live in `config.py` (breakout rule, compression filter, success label,
horizon bands, control ratio).
