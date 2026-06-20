<!--
  DASHBOARD JSON CONTRACT (v3) — companion to trade_setup_framework.md.
  Used by the /push-dashboard step. This is NOT the framework and NOT the output
  format; it is the bridge that turns a finished /trade verdict into the data file
  the Trade Dashboard (dashboard.py) renders.
-->

# Dashboard JSON Contract (Trade Setup Framework)

## What this is

`/trade` runs `framework/trade_setup_framework.md` and prints a written verdict
(Market Structure → Pattern Candidates Ranked by Opportunity → Trade Setup per
candidate). This contract maps that verdict into `analyses/<SYMBOL>.json`, which
`dashboard.py` renders.

- **Input:** the most recent `/trade` verdict in the current session.
- **Output:** `analyses/<SYMBOL>.json` (e.g. `analyses/SOLUSDT.json`).
- **Canonical example:** `analyses_demo/<SYMBOL>.json` — match that structure exactly.
- **After writing:** tell the user to open the Trade Dashboard and click **Run**
  (it auto-loads the newest `analyses/*.json` by mtime).

## Golden rules

1. **Pin structure, free substance.** Field names/shape are fixed; content is the
   analyst's live read. Narrative fields (summary, evidence, notes, confluence) are
   copied **verbatim** from the verdict — never rewritten, summarised, or genericised.
2. **No fabrication.** If the verdict doesn't state something, omit the optional
   field; never invent.
3. **Timestamps now.** `generated_at` = UTC ISO; `meta.analysis_time` = **Melbourne**
   local (see Derivation Rules).
4. **Validate** the file parses as JSON before finishing.

## Top-level fields

| Field | Type | Value |
|---|---|---|
| `schema_version` | int | `2` |
| `framework_version` | string | `"Trade Setup Framework v1"` |
| `symbol` | string | `BASE/QUOTE` (e.g. `"NEAR/USDT"`) |
| `contract` | string | `"PERP"` |
| `generated_at` | string | UTC ISO 8601 (e.g. `"2026-06-20T04:51:00Z"`) |
| `price` | string | current price (e.g. `"$2.17"`) — LIVE, app overwrites every 2s |
| `change_pct_24h` | number | 24h % change — LIVE |
| `meta` | object | `{ timeframe_analyzed, analysis_time }` (see below) |
| `snapshot` | array | `{label, value}` × 4: Current Price / 24H High / 24H Low / 24H Volume (optional: Funding, Open Interest) — LIVE placeholders |
| `market_structure` | object | Phase 1 (see below) |
| `intermarket` | object | correlation read (see below) |
| `pattern_candidates` | array | top 3, sorted by opportunity (see below) |

### `meta`
- `timeframe_analyzed` — e.g. `"Daily + 4H + 15m"`.
- `analysis_time` — **Melbourne** local string (Derivation Rules).

### `market_structure` (Phase 1)
`{ state, volatility, bias, structure[], volatility_note, bias_note }`
- `state` ∈ `Trending Up` · `Trending Down` · `Range Bound` · `Transition`.
- `volatility` ∈ `Compression` · `Expansion` · `Neutral`.
- `bias` ∈ `Bullish` · `Bearish` · `Neutral` (drives bull/bear/crab icon).
- `structure[]` — 1–2 bullets, the structure read (verbatim).
- `volatility_note`, `bias_note` — one line each (verbatim).

### `intermarket` (Phase 5 correlation)
`{ cor, cor_tf, note }`
- `cor` — measured Pearson correlation vs BTC (number, e.g. `0.94`). **Computed,
  never hand-set** (Derivation Rules). The dashboard derives the
  Risk-On/Moderate/Partial/Neutral/Risk-Off/Inverse label via `_cor_band()`, so
  the JSON stores only the number.
- `cor_tf` — the timeframe used, e.g. `"15M"`.
- `note` — the correlation read and what it implies for the coin (verbatim).

### `pattern_candidates[]` (top 3, ranked by opportunity)
Each:
- `name` — pattern name (e.g. `"Failed Breakdown / Double Bottom"`).
- `maturity` ∈ `Nascent` · `Forming` · `Mature` · `Ready` · `Triggered`
  (framework's Emerging→`Nascent`, Developing→`Forming`).
- `entry_mode` ∈ `Aggressive` · `Balanced` · `Chasing`.
- `classification` ∈ `Continuation` · `Reversal` · `Compression` ·
  `Liquidity / Reversal` · `Trap` (the structural role; coloured by direction).
- `qualifier` — short inline note (e.g. `"live at the 2.13 base"`).
- `grade` ∈ `A` · `B` · `C` · `D`.
- `summary` — ≤2 sentences (verbatim).
- `evidence[]` — ≤5 bullets, each **leads with the implication** (verbatim).
- `missing[]` — ≤3 bullets: only what blocks progression (verbatim).
- `entry` object:
  - `direction` ∈ `long` · `short`.
  - `zone` — `{ low, high, label, subtitle }` (numbers + display label + why it
    belongs to the pattern).
  - `stop` — `{ value, label, note }` (note = what the stop invalidates).
  - `risk` — `{ label, unit }` (e.g. `{"label":"~$0.08","unit":"per NEAR"}`).
  - `t1`, `t2` — `{ value, label, rr, note }` (rr computed; note = implication).
  - `tools` — string list of references actually used (e.g.
    `"Predictive Ranges · 1H RSI divergence · horizontal S/R"`).
- `confluence` — `{ strength, checks[], warnings[] }` where `strength` ∈
  `STRONG` · `MODERATE` · `WEAK`; `checks[]` = strengthening factors, `warnings[]`
  = caveats (verbatim).

## Derivation rules

1. **`meta.analysis_time` (Melbourne):**
   ```
   python3 -c "from datetime import datetime; from zoneinfo import ZoneInfo; d=datetime.now(ZoneInfo('Australia/Melbourne')); print(d.strftime('%b %-d, %Y, %-I:%M %p ')+d.strftime('%Z'))"
   ```
   → e.g. `"Jun 20, 2026, 2:51 PM AEST"` (auto-handles AEST/AEDT). `generated_at`
   stays UTC ISO.
2. **`intermarket.cor`:** Pearson on **15m returns vs BTC** using
   `scanner._pearson` on Binance 15m closes (closed candles only) — same method as
   `/tmp/cor_near15.py`. Set `cor_tf` to `"15M"`.
3. **R:R (`t1.rr`, `t2.rr`):** computed `|target − entry| / |entry − stop|`,
   formatted `"~1 : X.X"`. Never copied from prose.
4. **Sort `pattern_candidates`** by opportunity: best Trade Grade first (A→D), then
   less-complete-first within a grade. (The renderer also enforces this.)
5. **`symbol`** — `BASE/QUOTE` from the ticker (`NEARUSDT` → `"NEAR/USDT"`).

## Notes

- Derivatives (OI/Funding/CVD) are **not** a separate field — they belong inside a
  candidate's `evidence` / `confluence` / `tools` per the framework. (A dedicated
  Evidence treatment is planned separately.)
- The old v1 fields (`setup`, `verdict`, `scorecard`, `evidence_matrix`,
  `probability_distribution`, `trade_plan`, `what_changes_my_mind`,
  `key_levels`, `derivatives`, `daily`/`h4`, `bull_case`/`bear_case`) are **not**
  emitted by this contract.
