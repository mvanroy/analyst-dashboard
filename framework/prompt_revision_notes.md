# Pending Prompt Revisions — Analyst Framework

Running list of changes to fold into the analyst framework prompt
(`analyst_framework_v3.md`) on the next revision. These are NOT yet in the prompt.

---

## 2026-06-16 — Enforce the Insight Rule on every output line

**Problem.** Evidence bullets, notes, and confluence lines arrive as *descriptions*
of readings rather than *interpretations* of what they mean. They then have to be
hand-tightened on the dashboard each run. Examples that slipped through (HYPE):

- "Bullish daily AND 4H EMA stacks (price above rising 20/50/200)." — states the
  coordinates, not the meaning.
- "Opposing structure formed: higher lows $52.58 → $56.8 → $59.6 → $63.1." — lists
  the lows without saying buyers are defending dips higher.
- "4H momentum overbought (RSI 71), extended above the 4H EMAs." — a reading, not
  an implication.

**Reframed rule (drop-in text):**

> **INSIGHT RULE — pre-crunch every number.**
> The reader never does the math or the interpretation — you do it for them. Every
> data point (price level, EMA position, RSI, OI/funding/CVD, volume, % move) must be
> stated WITH what it means for the trade in the same breath. The number is the
> evidence; the sentence must deliver the conclusion that number supports. If a line
> could be lifted straight from a data feed or an indicator pane, it isn't finished —
> rewrite it, implication first.
>
> Reading → Insight:
> - "Price is above the 20/50/200 EMA stack." → "Price holds above a rising 20/50/200
>   stack on daily and 4H — trend aligned across timeframes, with layered support
>   under every pullback."
> - "RSI is 71." → "RSI 71 — strong but stretched, so a cool-off is likely before
>   continuation."
> - "OI rose into the move." → "OI is building as price rises — fresh longs backing
>   the breakout, not short-covering."
> - "Higher lows at 52.58, 56.8, 59.6, 63.1." → "Each dip is being bought higher —
>   demand is stepping up, not fading."

**Placement — three spots, not one** (a trailing style-note doesn't pre-crunch; the
rule has to bite where each line is written):

1. **Define once, high up.** Move the reframed rule into CORE PRINCIPLE (or the head
   of OUTPUT FORMAT), broadened from candles/structure to *all* numbers — so it is
   governing, not cosmetic. (Today's INSIGHT RULE only covers candles.)
2. **Bind at generation.** Add a one-liner to Phase 3 (Evidence), Phase 4
   (Confluence — now folded into Evidence), and Phase 5 (Entry): "Write each line per
   the Insight Rule — implication first, number in support."
3. **Gate in FINAL CHECK.** "Scan every evidence/note/confluence line: if any states a
   raw reading (price / EMA / RSI / OI / funding / CVD / %) without its trade
   implication, rewrite before submitting."

**Applies to:** the live Phase 1–5 prompt (the version pasted in chat, NOT the stale
`analyst_framework_v3.md` on disk — that file is an older Phase 1–6 structure and
needs reconciling with the live prompt separately).

**Why prompt-side, not dashboard-side:** the dashboard renders whatever the
analysis writes verbatim; the only durable fix is to make the bullets arrive
already-interpreted.

---

## 2026-06-16 — Drop the editorial header lines (`headline` / `liquidity_note`)

**Problem.** The card header carried two synthesised prose lines — `headline`
("Strong recovery off $60, pressing into $76-78 supply…") and `liquidity_note`
("⚠ clears = trend extends, rejects = countertrend bounce"). They:
- imposed a single **directional story** over cards that are deliberately
  multi-directional (e.g. a bearish Resistance Retest card under a "strong recovery"
  header);
- duplicated the **Market Condition chips** (Market State / Volatility / Bias) and
  each card's own summary;
- violated the framework's own rules — "you are not a market commentator", "remove
  trade coaching", "remove filler" (the if/then is forward-looking coaching).

**Change.**
- Dashboard side (DONE 2026-06-16): `_dhead_top` no longer renders `headline` or
  `liquidity_note`. Fields left in the JSON but ignored.
- Prompt/contract side (TODO): stop generating these fields at all. Remove
  `headline` and `liquidity_note` from the dashboard JSON contract and from any
  push-to-dashboard mapping, so they're never manufactured. The factual orientation
  is the Market Condition chips + per-pattern summaries; nothing else is needed.

**Applies to:** the dashboard JSON contract (`framework/dashboard_json_contract.md`)
and the push-to-dashboard mapping step. No change needed to the analyst prompt
itself (it never emitted these — they were synthesised at mapping time).
