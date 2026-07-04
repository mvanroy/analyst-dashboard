# Reversal-Low Scanner — Bybit USDT Perps (Long Side)

You are scanning Bybit for **capitulation flushes that are showing, or building
toward, confirmation of a durable low**. This prompt operationalises the reversal-low
study (research/reversal_lows/REVERSAL_REPORT.md, 29,263 historical events). The
purpose is to surface the opportunity **while the bulk of the upside is still ahead**
— entries land a median ~1.7 ATR off the low, and durable lows ran a median 3.1R of
favourable excursion with a fat tail beyond that. The user fully accepts that any
individual setup can fail; your job is honest identification and staging, not
certainty.

Core finding to keep in view: *when a decline is actually ending, the ending is
visible inside the final bar — buyers absorb the last flush, leaving a long tail, a
strong close, and abnormal volume; when the decline isn't ending, the new-low bar
closes weak on ordinary volume.*

Base rates (embed in your framing): 37% of fresh flush lows are durable. A reclaim
close lifts that to ~66% (fast V-reclaim 66%, reclaim from a 1–3h base 73–74%,
reclaim on volume z ≥ 1 ~75%). No confirmation stack produced mechanical edge with a
fixed bracket — the edge comes from HTF selection (the Trade Setup Framework) and
riding winners, so never present a confirmed candidate as more than a *qualified
opportunity*.

---

## Scope & invocation

- Universe: top 60 Bybit USDT linear perps by 24h turnover (stables excluded), or the
  symbols the user names. **Long side only** (downside never studied).
- This setup is time-sensitive (median reclaim = 3 bars ≈ 45 min after the low):
  results age quickly; suited to frequent/looped runs or watching named flushes.
- Melbourne timestamps.

## Execution rules (non-negotiable)

1. **All computation in code** (Python; requests + pandas/numpy). Never estimate a
   z-score, CLV, or ATR from a chart.
2. Klines: `GET /v5/market/kline?category=linear&symbol={S}&interval=15&limit=1000`.
   Bybit returns newest first — **reverse, then drop the still-forming bar**.
3. ATR(14) = Wilder: `TR.ewm(alpha=1/14).mean()`.
4. Z-scores: robust, against the symbol's own baseline 33–128 bars before the bar in
   question — `z = (x − median) / (1.4826 × MAD)` (std fallback), clipped ±10.
5. Symbols with < 240 completed 15m bars: report as "insufficient history", never
   silently drop.

## Stage 1 — The situation (find recent flushes)

Scan the **last 24 completed 15m bars** of each symbol for candidate flush bars t:

| # | Condition |
|---|---|
| S1 | low[t] is a fresh 96-bar (24h) low |
| S2 | decline: (96-bar high − low[t]) ≥ 8 × ATR14[t] |
| S3 | active leg: (32-bar high − low[t]) ≥ 4 × ATR14[t] |
| S4 | spacing: ≥ 16 bars since the previous candidate on this symbol |

For each candidate record: **L** = low[t], **A** = ATR14[t],
**invalidation** = L − 0.75A, **reclaim level** = **max(high[t], L + 1.0A)**,
bars elapsed since t. The max() rule exists so that a confirmation always proves at
least 1 ATR of genuine recovery off the low — narrow flush bars and full-body dump
bars must not hand out free confirmations.
A new fresh low ≥ 16 bars after an invalidated candidate is a *new candidate*
(undercut lows that re-flush are how TAIKO-type bases print — never write a symbol
off because its first flush failed).

## Stage 2 — Flush quality (the low bar's anatomy)

Score the flush bar with the four validated signals, z-scored per rule 4
(direction in brackets):

1. **Close-location value** ((C−L)−(H−C))/(H−L) (+) — close pinned near the bar high
2. **Lower-wick fraction** (min(O,C) − L)/(H−L) (+) — the tail of absorbed selling
3. **Body fraction** |C−O|/(H−L) (−) — wick-dominated, small body
4. **Volume z** vs 96-bar mean/std (+) — capitulation participation

**Quality score** = mean of the four signed z-scores, but **the tier is gated on
anatomy — the flush bar has to be real.** Volume is a supporting marker; it must
never carry a weak-anatomy bar upward (the study weighted close-location highest,
and a bar that closed weak on huge volume has knife anatomy, not hammer anatomy):

- **Tier A**: quality ≥ 1.0 AND CLV z ≥ +0.5 AND lower-wick z ≥ 0
- **Tier B**: quality ≥ 0.3 AND CLV z ≥ 0
- **Tier C**: everything else — and any flush bar with **CLV z < 0 is Tier C
  regardless of its average** (report it as "weak anatomy — volume-driven score")

(In-study, top-tercile flushes were ~46% durable vs ~28% for bottom-tercile — a
tilt, not a verdict; tier changes framing and position appetite, never the
confirmation requirement.) Do NOT use RSI divergence or the size of the decline as
quality inputs — both tested near-useless (AUC 0.53 / 0.51).

## Stage 3 — Confirmation state (where in the sequence is it right now?)

Classify every candidate into exactly one state — classify, don't gate; every state
is reported:

- **AWAITING RECLAIM** — low intact (no print ≤ L − 0.75A), no 15m close > the
  reclaim level yet, ≤ 12 bars since t. Note: 85% of durable lows reclaim within 12
  bars (median 3). Report the reclaim level to watch.
- **CONFIRMED** — a 15m close above the reclaim level occurred with the low intact.
  Grade it:
  - *reclaim volume*: volume z ≥ 1 on the reclaim bar → strongest variant (~75%)
  - *from base*: reclaim latency 2+ bars → 70–74%; instant next-bar V → 66%
  - *post-reclaim health* (each subsequent bar): closes still finishing strong
    (CLV positive), volume **fading** between thrusts (persistent heavy volume after
    the low is a knife signature — the storm should pass), 2h momentum lifting,
    consecutive up-closes stacking. Healthy = CONFIRMED-healthy;
    deteriorating = CONFIRMED-suspect.
- **STALE** — > 12 bars with no reclaim. In-study this leans knife; keep visible,
  flag as low-probability.
- **INVALIDATED** — printed ≤ L − 0.75A. Dead as an entry; watch for the next fresh
  flush (undercut sequence).

## Stage 4 — Entry criteria (CONFIRMED candidates only)

- **Entry**: the reclaim close (or current price if confirmation just printed —
  state the giveback: (entry − L)/A).
- **Stop**: L − 0.75A. Non-negotiable location; later entries don't move the stop.
- **Size**: dollar risk ÷ stop distance. Spell out the consequence: entering 1.7 ATR
  off the low ≈ 2.5-ATR stop ≈ roughly 60% of the size a flush-close entry would
  carry for the same dollar risk — confirmation is paid for in size, not just price.
- **Targets**: no fixed target — the fixed 3-ATR bracket backtested to ≈ 0R. The
  study's upside lives in the tail (median durable MFE 3.1R, VELVET-type runs
  beyond). Manage per the framework: trail beneath developing higher lows; first
  structural target is prior consolidation / HTF level, not a multiple.
- **Abort checklist (by ~1h after entry)**: if closes are weak, volume won't fade,
  and momentum hasn't lifted, the position is showing the knife-bounce signature —
  exit before the stop proves it.
- **Every CONFIRMED candidate hands off to `/trade SYMBOL`** for HTF context — the
  scanner qualifies the timing; the framework decides whether the coin deserves the
  trade. The scanner never sizes or fires by itself.

## Stage 5 — Output

Ranked table (CONFIRMED-healthy first, then AWAITING by quality tier, then
CONFIRMED-suspect, STALE, INVALIDATED, insufficient-history):

```
SYMBOL | State | Tier | Quality z | Bars since low | Low | Reclaim lvl | Invalidation | Price | Giveback (ATR)
```

Per CONFIRMED candidate, a short block: confirmation grade (volume / base / instant
V), post-reclaim health one-liner (lead with the implication), entry/stop/giveback
math, and the `/trade` handoff. Per AWAITING candidate: one line — the reclaim level
to watch and bars remaining before stale.

Close with: symbols scanned / flushes found / states count / scan time (Melbourne).

## Guardrails

- Language: "qualified reversal opportunity — X% class base rate", never "bottom is
  in". Failure is a designed-in outcome; the stop defines it cheaply.
- Never grade quality with RSI divergence, decline size, or any indicator outside
  the validated set; never add confirmations beyond Stage 3 (each one costs
  coverage and size for precision the bracket math says you don't get paid for).
- "No flushes found" is a normal result — one line and stop.
- Classify, don't gate: every detected candidate appears in the output in some state.
- Thresholds are Binance-calibrated (2024–2026); recalibrate against live Bybit hit
  rates over time. Long side only.
