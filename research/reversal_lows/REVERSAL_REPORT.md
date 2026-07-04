# Durable Low or Falling Knife? 15m Capitulation Reversals

**Sibling study to the breakout-precursor report · same 60 Binance USDT perps,
Jan 2024 – Jun 2026 · 29,263 candidate lows**

Motivating question (from three live charts — VELVET, TAIKO, ONDO): *what analysis
would let us be there to buy at the reversal low of a steep decline?*

---

## 1. Headline answers

> **The finding in one sentence:** when a decline is actually ending, the ending is
> visible *inside the final bar* — buyers absorb the last flush, leaving a long tail,
> a strong close, and abnormal volume; when the decline isn't ending, the new-low bar
> closes weak on ordinary volume. That difference is modest per bar, but it is the
> single most reliable real-time distinction the data contains.

1. **Most fresh lows are not the low.** Of 29,263 events where a market made a new
   24h low after a steep (≥8 ATR) decline, only **36.7% were durable** (rallied +3 ATR
   before undercutting −0.75 ATR). Buying every flush loses money. The circled charts
   are what the 36.7% look like *after* the fact.

2. **The flush bar's own anatomy is the best real-time tell — not momentum, not
   divergence.** Ranked by discrimination *at the low bar itself* (durable vs knife):
   close-location-value (AUC 0.625), lower-wick fraction (0.621), wick-dominated
   small body (0.591 inverted), capitulation volume / trade count z (0.567) — every
   one directionally consistent across **all 56 testable symbols**. A hammer-shaped,
   high-volume flush bar genuinely is different from a mid-knife bar, everywhere,
   in every year of the sample.

3. **The folklore mostly fails.** RSI bullish divergence — the classic bottom
   signal — scores AUC 0.534 (barely above coin-flip). The *size* of the preceding
   decline is irrelevant (0.511). Nothing before the low bar (offsets −8..−1) adds
   material information: **you cannot see the bottom coming; you can only recognise
   it while it prints and confirm it after.**

4. **Confirmation works as a filter.** Requiring one 15m close back above the flush
   bar's high ("reclaim") before entering catches 71% of durable lows while rejecting
   79% of knives — precision jumps from 37% to **66%**, at a median cost of entering
   1.7 ATR off the low, ~30–45 min after it. Adding a volume condition (reclaim close
   with volume z ≥ 1) pushes precision to **~75%** but only fires on 22% of durable
   lows. On your VELVET chart, this is precisely the big green reclaim candle inside
   your circle.

5. **The sobering part: timing alone carries no mechanical edge.** With the natural
   bracket (stop below the low, target +3 ATR), *every* trigger variant — and every
   flush-quality tier — lands at expectancy ≈ 0R (−0.05 to +0.00 before fees, and
   fees at 15m scale are material). Better flushes reclaim from higher, so what you
   gain in win rate you pay in entry giveback. The market prices its own
   confirmation almost perfectly. **The edge in these trades must come from
   selection and management, not the trigger**: which markets you allow candidates
   from (HTF structure, the 4H context you mentioned), and how winners are ridden
   (durable lows bought at the flush close ran a median 3.1R of favourable excursion
   against the fixed 3.75-ATR bracket's ~1.9R — the tails are where VELVET-type
   results live).

**Bottom line for "being there":** a deployable pipeline is (a) detect the candidate
in real time (new 24h low + ≥8 ATR decline — trivial to compute), (b) score the flush
bar (CLV, lower wick, volume z — the validated trio), (c) alert you, (d) enter only on
the reclaim, with the framework — not this scanner — deciding whether the coin
deserves the trade. That gets you into VELVET at ~0.41 against the 0.395 low. What it
cannot do is make the decision for you: identification is now statistical;
selection remains judgment.

---

## 2. Methodology

- **Candidate** (all on completed 15m bars): fresh 96-bar (24h) low, total decline
  from the 96-bar high ≥ 8 × ATR14, active leg (32-bar high to low ≥ 4 × ATR14),
  16-bar spacing between candidates. Successive lows in one decline each count —
  deliberately, since each looked catchable in real time.
- **Labels:** from the candidate's low L and ATR A: **durable** = high reaches
  L + 3A within 48 bars before low reaches L − 0.75A; **knife** = the stop side
  first (same-bar ambiguity → knife, conservative). Undecided (1.2%) dropped.
  Result: 10,744 durable / 18,524 knives.
- **Features:** the 31-feature engine from the breakout study, z-scored per event
  against the market's own baseline 8–32h earlier; analysed at offsets −8..0
  (pre-low and at-low = predictive; post-low bars are confirmation and are handled
  by the trigger backtest instead, to avoid outcome contamination). Event-level
  extras: RSI level, RSI divergence vs the previous candidate low, decline size.
- **Triggers:** simulated bar-by-bar on raw OHLCV. Entry only if the trigger fires
  within 12 bars of the low *and* the stop hasn't already been breached; outcome =
  target-before-stop from entry; MFE tracked separately without the target cap.
- Multiple testing controlled with BH-FDR; composite validated with symbol-grouped
  5-fold CV (no symbol appears in both train and test).

## 3. What identifies a durable low (at the bar, real-time knowable)

| Rank | Signal | AUC (durable vs knife) | Symbol consistency | Verdict |
|---|---|---|---|---|
| 1 | Close-location value (close near bar high) | 0.625 | 56/56 | **KEEP** |
| 2 | Lower-wick fraction | 0.621 | 56/56 | **KEEP** (pairs with #1: the hammer shape) |
| 3 | Small body / wide range (body_frac, inverted) | 0.591 | 56/56 | **KEEP** — same cluster |
| 4 | Trade-count z (capitulation participation) | 0.567 | 56/56 | **KEEP** |
| 5 | Relative volume / volume z / dollar-volume z | 0.566–0.567 | 54–56/56 | redundant with #4 — use one |
| 6 | Average spread (8-bar, wide bars) | 0.558 | 56/56 | TEST — cousin of #3 |
| 7 | Shallow vs 32-bar high (pullback_depth inv.) | 0.546 | 53/56 | TEST |
| — | Taker-buy ratio, EMA slope, ATR%, ROC, RSI level | 0.53–0.535 | — | marginal |
| — | **RSI divergence** | **0.534** | — | **folklore largely busted** |
| — | Decline magnitude, MACD hist, HV, BB width, ADX | 0.50–0.51 | — | DISCARD |

Composite of everything at the low: **AUC 0.651** (grouped CV) — enough to tier
candidates (top tercile ≈ 46% durable vs 28% in the bottom tercile), nowhere near
enough to buy the flush bar naked.

## 4. Confirmation triggers (the actionable layer)

29,229 candidates simulated. "Entered knives" are the false catches.

| Trigger | Durable lows entered | Knives entered | Precision | Win rate (3A/0.75A bracket) | Median entry vs low | Median bars after low | Expectancy |
|---|---|---|---|---|---|---|---|
| T0: buy flush close (no confirmation) | 96% | 100% | 37% | 35.9% | +0.53 ATR | 0 | **−0.05R** |
| T1: 15m close > flush high | 71% | 21% | 66% | 65.6% | +1.73 ATR | 2 | −0.03R |
| T2: 15m close > flush open | 75% | 28% | 63% | 60.6% | +1.55 ATR | 2 | −0.04R |
| T3: T2 + volume z ≥ 1 | 22% | 4% | **75%** | **70.2%** | +1.98 ATR | 3 | −0.03R |
| T4: two higher closes + CLV ≥ 0.5 | 64% | 22% | 65% | 62.2% | +1.67 ATR | 3 | −0.05R |

Stacking flush quality on top of T1 raises win rate monotonically (63% → 68% by
score tercile) but expectancy stays ≈ 0 in every cell — higher-quality flushes
reclaim from higher, and the giveback offsets the odds. **Precision and timing are
solvable; mechanical edge from the trigger alone is not there.** (All figures before
fees; at 15m scale round-trip taker fees cost roughly 0.05–0.15R more.)

## 5. Reconciliation with the three charts

- **VELVET:** textbook top-tercile flush (long lower wick, volume spike, strong CLV)
  → T1/T3 fire 2–3 bars after the low ≈ 0.41 vs the 0.395 low, and it was
  simultaneously flagged by the breakout scanner's far-trigger section. The system
  described here would have had you there.
- **TAIKO:** an *undercut base* — the first candidate stopped out (knife by label),
  the undercut low 16+ bars later was a fresh candidate that ran. The per-candidate
  framing handles this honestly: the first catch attempt lost, the second won.
- **ONDO (1h):** a **higher-low retest, not a capitulation low** — it never made a
  fresh 24h low, so this study's detector would not (and should not) claim it.
  Different event class, worth its own study if it recurs in your trading.

## 5b. Deleveraging test (added 2026-07-04, deleveraging.py)

Hypothesis: durable lows are liquidation events — OI forcibly flushed into the low.
Tested on all 29,252 flushes with 5-min OI history. **Directionally confirmed,
practically useless**: durable lows do show larger OI drops into the low (all OI
features p < 1e-5), but the effect is tiny — biggest-OI-dump quartile 39.1% durable
vs 34.8% for OI-intact — and incremental value over the flush-anatomy features is
zero (grouped-CV AUC 0.641 → 0.642). Liquidation *is* volume: the volume z-score
already carries the information. **Verdict: DISCARD for the scanner** (matches the
breakout study's derivatives verdict). Taker-flow ratio at the low: AUC 0.52,
likewise not worth the feed.

## 5c. HTF-context conditioning test (added 2026-07-04, htf_context.py)

Hypothesis (and this report's own §6 conjecture): the higher-timeframe situation —
flush landing on prior congestion vs mid-air, daily trend, position in the 90-day
range, BTC regime — conditions the durable rate. Tested on 25,504 flushes.
**Falsified, in both directions that matter:**

- *Durability:* all context AUCs 0.48–0.49. Congestion landings 35.8% durable vs
  mid-air 38.1% (support zones do not rescue flushes); daily trend irrelevant;
  BTC 4H above EMA50 worth ~3 points (38.7% vs 35.6%). Full combined spread
  33.6%–38.8%. Anatomy+HTF model: 0.642 → 0.647.
- *Tails:* median 24h MFE of durable lows 7.08 ATR (BTC up) vs 6.58 (BTC down),
  ~7% relative; congestion vs mid-air 6.91 vs 6.71; trend ≈ nothing.

**Verdict: whether a 15m capitulation flush holds — and how far it runs in 24h — is
a local order-flow event, not an HTF event.** The flush bar's anatomy and the
confirmation sequence dominate; the only context feature worth even a minor flag is
BTC's 4H state. Caveat: these are crude context proxies (time-at-price, EMA trends);
a discretionary HTF read may encode information they miss — but across 25k events the
proxies being flat is strong evidence. This revises §6's conjecture and narrows what
the HTF layer should be asked to do for THIS setup: coin selection for liquidity and
structure, exit/target planning — not flush triage. (One genuinely useful side-stat:
durable lows' median 24h MFE from the low is **6.75 ATR**, P75 9.8 — the tails are
even fatter than §5's trigger-capped numbers suggested.)

## 6. Limitations & next steps

- Fixed bracket (stop −0.75A, target +3A) is one management scheme; the MFE numbers
  say trailing/partial schemes on the winners' tails are where positive expectancy
  would have to come from — testable as a follow-up.
- No HTF conditioning: candidates were taken in all regimes. Conditioning on 4H/1D
  structure (the selection layer your framework already does) is the most promising
  unexplored cut of this dataset — e.g. durable-rate by BTC regime or by position in
  the daily range.
- Long side only; intrabar sequencing unknowable from klines (ambiguity resolved
  against the trade); Binance-calibrated.

## 7. Reproduce

```
.venv/bin/python detect_lows.py      # candidates.json (29,636)
.venv/bin/python build_windows.py    # windows.pkl
.venv/bin/python analyze_lows.py     # at-the-low AUCs, composite CV
.venv/bin/python triggers.py         # trigger backtest (trigger_stats.csv)
.venv/bin/python combo.py            # flush-quality x trigger stacking
```
