<!--
  OUTPUT FORMAT EXAMPLE (v2) — companion to analyst_framework_v2.md, used by /trade.

  ⚠️ THIS FILE TEACHES LAYOUT, NOT DIRECTION.

  This worked example happens to resolve as a LONG (a countertrend reversal
  attempt). That direction is INCIDENTAL. Direction is NEVER inherited from this
  example — you derive it fresh from your own Phase 1–2 evidence on the requested
  coin. If your honest read is a SHORT or NEUTRAL, mirror this exact section/table
  structure in that direction: flip entries, stops, invalidation, targets, and the
  "buy the dip / sell the rally" framing accordingly. A short verdict is just as
  valid an output of this format as a long one; a Neutral / no-clean-trade verdict
  (with both edges named) is equally valid.

  Every number, level, evidence cell, case, and sentence below is illustrative
  filler — NEVER reuse them. analyst_framework_v2.md defines WHAT to assess and
  decide; this file shows only HOW to lay the answer out so the chat is readable
  AND the Dashboard JSON Contract can map it. Structure is fixed; substance is
  always your own live read.
-->

# Output Format

Worked example below is **HYPEUSDT** — illustrative only, worked as a long for
demonstration. Match this **structure and these section/field names**; replace
every number, level, and sentence with your genuine analysis, in whatever
direction the evidence supports.

---

Current price: $58.11 (HYPE is mid-bounce off the $55.45 low).

## PHASE 1: MARKET BIAS ASSESSMENT

### Daily Timeframe

| Factor | Reading | Evidence | Call |
|---|---|---|---|
| Structure | LH + LL | Rally 38→75.8 made clean HH/HL; the double top ($75.8/$75.6) was a lower-high failure, and the drop broke the rising higher-low sequence (67.8 → 60 → 56), printing a LL at 55.45. | Bearish |
| 20 EMA | $60.7 | Price $58.1 is below the 20 EMA. | Bearish |
| 50 EMA | $53.6 | Price above the 50 EMA; 20>50 stack still intact. | Neutral |
| AVWAP (cycle low $44.2) | ~$61.0 | Price below AVWAP. | Bearish |
| RSI regime | 49.7 | Fell from ~70 to the midline; no longer bullish, not yet bearish. | Neutral |
| Volume trend | Expanding on declines | The two biggest-volume daily bars (14.4M, 15.7M) were down days; bounce volume light. | Bearish |

Daily lean: **Bearish** (3 bearish / 2 neutral / 1 ~neutral).

### 4-Hour Timeframe

| Factor | Reading | Evidence | Call |
|---|---|---|---|
| Structure | LL, bounce | Downtrend intact; bouncing off 55.45 but hasn't reclaimed the $61 swing high. | Bearish |
| 20 EMA | $61.7 | Price $58.1 below. | Bearish |
| AVWAP (from $75.8 top) | ~$66 | Price well below. | Bearish |
| Momentum | RSI 37.4, rising | Below 50 but rising off oversold with a bullish divergence (price LL 57.2→55.45, RSI HL). | Neutral |
| Volume | Selling dried up | Down-volume contracted into the low (1.3M→0.6M); bounce modest (~1M). | Neutral |

4H lean: **Bearish** (3 bearish / 2 neutral / 0 bullish).

### Bias Scorecard

| Factor | Bullish | Bearish | Neutral |
|---|---|---|---|
| Daily Structure | | ✅ | |
| Daily EMA Position | | | ✅ |
| Daily AVWAP Position | | ✅ | |
| Daily RSI Regime | | | ✅ |
| Daily Volume Trend | | ✅ | |
| 4H Structure | | ✅ | |
| 4H EMA Position | | ✅ | |
| 4H AVWAP Position | | ✅ | |
| 4H Momentum | | | ✅ |
| 4H Volume | | | ✅ |
| **Count** | **0** | **6** | **4** |

→ **OVERALL BIAS: BEARISH (transitional)** — 0 bullish factors; price parked on major support with a momentum turn, not a bullish structure.

## PHASE 1.5: MARKET STATE ASSESSMENT

**Market State: TRANSITIONAL.**

Why: the prior downtrend has paused at major support ($55.4 sweep + daily 0.618 + 50 EMA) with a 4H momentum divergence, but no break of structure has confirmed a reversal — neither trending down any longer nor trending up yet.

- **Favoured setups:** Bullish/Bearish Divergence Reversal, Failed Breakdown, Mean Reversion.
- **Disadvantaged setups:** Trend Continuation (no clean trend to ride), Breakout/Breakdown (acceptance unproven).

Note: the bearish bias does **not** license a trend short here — price is on major support with selling exhausting, which is hostile to fresh continuation shorts.

## PHASE 2: SETUP CLASSIFICATION

### Competing Hypotheses

**Strongest Bullish Interpretation:** A 4H bullish RSI divergence at major confluence support ($55.4 sweep + daily 0.618 + 50 EMA), after a liquidity sweep of the sell-side below $56 and a reclaim — an oversold reversal back toward the means ($61–62).

**Strongest Bearish Interpretation:** Bias is bearish (6/10), structure is broken, price is below every EMA and AVWAP, and HVN supply $57–61 caps the bounce — a weak counter-rally to be sold for continuation to lower lows.

**Comparison:** The bear case owns the higher-timeframe structure; the bull case owns the actionable event (divergence + sweep + reclaim at confluence support, selling exhausted). For a *tactical* trade the bull evidence at this specific location is stronger; for a *swing* the bear structure dominates. The nearer, better-defined edge is the reversal long off support.

**Selected Setup Type: Bullish Divergence Reversal (countertrend).** The defining signature — lower price low / higher RSI low at major support following a sweep + reclaim — is present. Not Trend Continuation (structure broken); only loosely a Pullback (the decline was a structural breakdown, not an orderly retrace).

## PHASE 3: TRADE EVALUATION (vs. the Bullish Divergence Reversal archetype)

**Required characteristics:** ✅ bullish divergence present (price LL / RSI HL); ✅ selling pressure weakening (down-volume contracted into the low).

**Expected (not penalties):** ✅ below major EMAs; ✅ below AVWAP; ✅ weak trend structure — all expected for a reversal starting below the means.

**Preferred:** ✅ support zone nearby ($54–55 demand + 0.618); ✅ liquidity sweep of lows (<$56 reclaimed); ✅ volume exhaustion. ❌ OI flush — unavailable in feed.

**Confidence reducers:** ⚠️ no confirmation yet (needs a 4H reclaim/close above $61); ⚠️ HVN supply $57–61 overhead. No heavy continuation selling and no fresh breakdown acceptance — so the archetype holds, unconfirmed.

## PHASE 4: ADDITIONAL CONFIRMATION (vs. the long-reversal thesis)

| Factor | Assessment | Verdict |
|---|---|---|
| RSI Divergence | 4H bullish divergence, RSI rising 32→37 | Supports |
| Volume Expansion/Contraction | Sell-volume contracted into the low; bounce not volume-confirmed | Neutral |
| Open Interest | Not available in feed | — |
| Funding Rate | Not available in feed | — |
| CVD | Not available in feed | — |
| Volume Profile | HVN $57–61 overhead — bounce climbs into supply | Contradicts |
| VWAP / AVWAP | Below daily ($61) & 4H (~$66) AVWAP; not reclaimed | Neutral (expected early) |
| Liquidity Sweeps | Swept stops < $56 then reclaimed | Supports |
| Support / Resistance | Bouncing at 0.618 daily + $54–55 demand | Supports |

Net: 3 support / 1 contradict / 2 neutral / 3 unavailable.

## PHASE 5: FINAL VERDICT

**Market Bias:** Bearish (transitional)

**Market State:** Transitional

**Setup Type:** Bullish Divergence Reversal — countertrend

**Bull Case:** 4H bullish divergence + sell-side sweep & reclaim of $56 at major confluence support ($54–55 demand + daily 0.618 + 50 EMA), selling exhausted into the low — an oversold snap back to the means ($61–62).

**Bear Case:** Bearish bias (6/10), structure broken, price below every EMA and AVWAP, HVN supply $57–61 capping the bounce, daily volume expanding on declines — a counter-rally to be sold toward a lower low.

**Trade Thesis:** Long the oversold divergence reversal off the $55.4–56.3 support, targeting mean-reversion into the overhead supply/means at $61–62.

**Supporting Evidence:** 4H bullish RSI divergence; sell-side sweep + reclaim of $56; selling-volume exhaustion; major confluence support; RSI rising.

**Contradicting Evidence:** Bearish bias; below every EMA/AVWAP (none reclaimed); no break of structure; HVN supply $57–61 overhead; daily volume expanded on the downside; bounce not volume-confirmed.

**Scoring:**
- Setup Quality: 5/10 — good reversal ingredients, unconfirmed and against bias.
- Reward-to-Risk Quality: 6/10 — entry ~$58, stop <$55.4 (risk ~$2.6), target $61.5 (reward ~$3.5) ≈ 1.3:1; ~3:1 only if it stretches to $63.7+.
- Probability Assessment: 5/10 — oversold bounces to the mean are common; a sustained reversal is below even odds without confirmation.

**Trade Management:**
- **Invalidation Level:** 4H close below $55.40 (the sweep low).
- **Primary Target:** $61–62 (4H 20 EMA $61.7 + daily AVWAP $61.0 + daily 0.50 fib $60.0).
- **Most Likely Failure Scenario:** Bounce stalls into the $58–61 HVN/EMA/AVWAP supply, gets rejected, bearish bias reasserts, and price makes a lower low below $55.4 toward the daily 50 EMA ($53.6) / 0.786 fib ($51.0).

**Conclusion:** This is a **Countertrend / Reversal Attempt** — explicitly not trend-following. You'd be buying a bounce against a bearish bias into overhead supply, with the divergence and support on your side but no confirmation yet.

## Analyst Notes (optional safety valve)

Short free-form bullets for a genuinely important observation that fits no field above — a BTC/macro correlation, an event risk, a data caveat. Only real signal, no filler. These flow into the dashboard's Analyst Summary.

- (example) BTC is coiling under its own 4H 20 EMA; a BTC breakdown would override this long.
