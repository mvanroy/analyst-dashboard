# Trade Setup Framework

> Pattern-discovery trading framework. Five phases: classify the market condition, discover candidate chart patterns, assess them, convert the strongest into trade setups, then manage with intermarket context. Companion reference: [Chart Pattern Library](chart_pattern_library.md).

---

## PHASE 1 — MARKET CONDITION CLASSIFICATION

Determine the dominant Market Condition before assessing any trade. Market Condition must be mutually distinct and observable from price. To provide an accurate classification, confirm:

- What is the Market Structure?
- Whether Volatility is Compressing or Expanding. If volatility is neither clearly compressing nor expanding, classify it as **Neutral**.

Only **one** primary Market Structure should be selected from the matrix below.

### Market Structure Matrix

| Market State | Structure | Behaviour | Market Psychology | Invalidated When |
|---|---|---|---|---|
| **Trending Up** | Higher Highs (HH), Higher Lows (HL), bullish trend intact | Pullbacks are bought; resistance frequently becomes support; buyers regain control after retracement | Buyers are willing to pay increasingly higher prices; sellers are unable to create sustained lower lows | A significant higher low breaks; structure begins producing lower highs; acceptance below key support develops |
| **Trending Down** | Lower Highs (LH), Lower Lows (LL), bearish trend intact | Rallies are sold; support frequently becomes resistance; sellers regain control after bounces | Participants are willing to sell at progressively lower prices; buyers cannot maintain higher highs | A major lower high is broken; higher lows begin developing; sustained acceptance above resistance occurs |
| **Range Bound** | No sustained HH/HL sequence; no sustained LH/LL sequence | Resistance repeatedly holds; support repeatedly holds; breakouts often fail | Participants broadly agree on fair value; neither side has sufficient conviction to establish trend | Sustained acceptance above resistance; sustained acceptance below support |
| **Transition** | Trend structure damaged, mixed highs and lows, conflicting evidence, new market condition not yet confirmed | Breakouts fail; reversals fail; increased uncertainty | Control is shifting between buyers and sellers; a new equilibrium is being established | — |

> **Important:** Transition does NOT mean reversal. It means the previous trend is no longer behaving normally.

Only **one** Volatility State should be selected from the matrix below.

### Volatility Matrix

| Volatility State | Structure | Behaviour | Market Psychology |
|---|---|---|---|
| **Compression** | Volatility is contracting; narrowing range, reduced volatility, smaller candles | Price swings shrink; momentum decreases; breakout pressure builds | Buyers and sellers are reaching a temporary equilibrium; neither side is strong enough to force expansion |
| **Expansion** | Volatility is increasing; largest price swings, increased range, strong directional movement | Breakouts gain follow-through; participation increases; momentum accelerates | One side is gaining control; participants are willing to transact at increasingly different prices |
| **Neutral** | Volatility is stable; price swings consistent in size; candle ranges steady | Price moves in a measured way; breakouts not explosive; pullbacks not unusually sharp; trend or range behaviour continues without major volatility change; market rhythm is readable | Participants are broadly acting within expected conditions; no obvious panic, squeeze, capitulation, or aggressive chase; neither side is forcing a major volatility shift |

> **Important:** Compression is directionally neutral — not bullish, not bearish. Expansion describes volatility, not direction (it can occur upward or downward).

### Example Interpretations

| Market State | Volatility State | Interpretation |
|---|---|---|
| Uptrend | Neutral | Healthy trend continuation |
| Downtrend | Neutral | Controlled bearish trend |
| Range | Neutral | Balanced rotation |
| Transition | Neutral | Unclear regime shift without volatility acceleration |

---

## PHASE 2 — CHART PATTERN DISCOVERY

Using the Market Condition identified in Phase 1:

- Search TradingView for structurally valid chart patterns.
- Market conditions should guide search priority but must not suppress valid pattern recognition.
- Use Location, Behaviour and Structural evidence to identify candidate patterns.
- Identify up to **five** candidate patterns and eliminate structurally weaker interpretations using the Chart Eligibility Matrix and the Pattern Uniqueness Rule.
- These candidate patterns will be fully assessed in Phase 3.

The Chart Eligibility Matrix maps chart patterns to Structural Role and Market Condition. Multiple patterns may apply. Identify primary patterns and any valid secondary patterns.

### Chart Eligibility Matrix

| Pattern | Structural Role | Typical Function | Trending Up | Trending Down | Range Bound | Transition |
|---|---|---|---|---|---|---|
| Bull Flag | Continuation | Trend resumption | Primary | No | No | Possible |
| Bear Flag | Continuation | Trend resumption | No | Primary | No | Possible |
| Bull Pennant | Continuation / Compression | Trend resumption | Primary | No | No | Possible |
| Bear Pennant | Continuation / Compression | Trend resumption | No | Primary | No | Possible |
| Rising Channel Pullback | Continuation | Trend resumption | Primary | No | No | Possible |
| Falling Channel Pullback | Continuation | Trend resumption | No | Primary | No | Possible |
| Support Retest | Continuation | Trend resumption | Primary | No | Possible | Possible |
| Resistance Retest | Continuation | Trend resumption | No | Primary | Possible | Possible |
| Ascending Triangle | Compression | Breakout preparation | Primary | No | Possible | Possible |
| Descending Triangle | Compression | Breakout preparation | No | Primary | Possible | Possible |
| Rising Wedge | Compression / Reversal | Trend exhaustion | Possible | No | Possible | Primary |
| Falling Wedge | Compression / Reversal | Trend exhaustion | No | Possible | Possible | Primary |
| Double Top | Reversal | Trend exhaustion | Possible | No | Primary | Primary |
| Double Bottom | Reversal | Trend exhaustion | No | Possible | Primary | Primary |
| Head & Shoulders | Reversal | Trend exhaustion | Possible | No | Possible | Primary |
| Inverse Head & Shoulders | Reversal | Trend exhaustion | No | Possible | Possible | Primary |
| Structure Shift | Reversal | Regime change | Possible | Possible | Possible | Primary |
| Bearish SFP | Liquidity Reversal | Liquidity rejection | Possible | Possible | Primary | Primary |
| Bullish SFP | Liquidity Reversal | Liquidity rejection | Possible | Possible | Primary | Primary |
| Equal High Sweep | Liquidity Reversal | Liquidity rejection | Possible | Possible | Primary | Primary |
| Equal Low Sweep | Liquidity Reversal | Liquidity rejection | Possible | Possible | Primary | Primary |
| Prior Day High Sweep | Liquidity Reversal | Liquidity rejection | Possible | Possible | Primary | Primary |
| Prior Day Low Sweep | Liquidity Reversal | Liquidity rejection | Possible | Possible | Primary | Primary |
| Failed Breakout | Trap / Liquidity | Trap pattern | Possible | Possible | Primary | Primary |
| Failed Breakdown | Trap / Liquidity | Trap pattern | Possible | Possible | Primary | Primary |

### Pattern Requirements

- **Continuation Patterns:** Require an existing trend.
- **Reversal Patterns:** Require evidence of trend exhaustion, structural damage, or loss of trend efficiency.
- **Compression Patterns:** Require observable volatility contraction. They may not be classified above **Developing** unless compression is visibly present. If compression is absent, maximum Maturity Status is Developing.
- **Liquidity Patterns:** May occur in any market condition.

### Matrix Interpretation

- **Primary:** Pattern naturally belongs in this environment and should be prioritised.
- **Possible:** Pattern is structurally valid and must be evaluated if evidence exists.
- **No:** Pattern is structurally inconsistent with the environment and should normally be excluded unless the market condition appears misclassified.

Market Condition guides search priority but must not suppress valid pattern recognition.

### Pattern Uniqueness Rule

- A structure may only be assigned one primary pattern.
- If multiple pattern names describe the same structure, report the pattern with the highest Maturity Status.
- Do not report duplicate interpretations of the same structure.
- **Structure Shift** is a fallback classification and should only be used when no named reversal pattern explains the structure equally well.
- A pattern marked **Possible** may never be discarded solely because it is not Primary.

### Candidate Selection Rule

- Identify up to five candidate patterns.
- Select the strongest structural candidates.
- Eliminate duplicate or weaker interpretations using the Chart Eligibility Matrix and the Pattern Uniqueness Rule where applicable.

---

## PHASE 3 — CHART PATTERN ASSESSMENT

Fully assess only the **three strongest** candidate patterns identified in Phase 2.

Use the pattern-specific observations, structural development, confluence factors, failure lens and entry mode logic defined in the [Chart Pattern Library](chart_pattern_library.md) to guide your assessment.

The Chart Pattern Library is a pattern-specific guide, not a checklist. **The chart itself takes precedence over the Library.** Its purpose is to answer "Could this become the pattern with tradable upside?" rather than "Has the pattern already completed?"

- Interpret Location, Behaviour and Structure through the lens of the relevant pattern.
- Do not force observations simply because they appear in the reference.
- Structural Development should be assessed in the sequence defined by that pattern.
- Confluence factors may strengthen or weaken the thesis but should not override price structure.
- Use Failure Lens observations to determine whether the pattern thesis remains valid.

**Evidence to use:**
- **Location:** Is price interacting with locations that commonly precede this pattern?
- **Behaviour:** Is price behaving in a manner consistent with this pattern?
- **Structure:** How much of the actual pattern structure currently exists?

**Assign:** Pattern Stage, Entry Mode. Apply Market Logic Reasoning, then produce a concise Market Logic Commentary.

Do not force a pattern. A pattern must be supported by observable price structure. Do not require confirmation before identifying a developing opportunity. The objective is to determine whether the market is behaving in a manner that commonly leads to the development of the pattern.

### Pattern Stage

| Score | Status | Meaning |
|---|---|---|
| 0–2 | Emerging | I can see the shape forming |
| 3–5 | Developing | The structure is becoming recognisable |
| 6–7 | Mature | Most requirements are present |
| 8–9 | Ready | All requirements are present except the trigger |
| 10 | Triggered | The trigger has occurred |

Pattern Stage describes how complete the chart pattern structure is.

### Entry Mode

| Entry Mode | Meaning | Trade-Off | Key Question |
|---|---|---|---|
| **Aggressive (A)** | Early Entry | Greater upside ↔ greater uncertainty | Is there enough evidence to justify early participation? |
| **Balanced (B)** | Developing Entry | Balanced reward ↔ balanced certainty | Has the opportunity become sufficiently developed without becoming crowded? |
| **Chasing (C)** | Late Entry | Greater certainty ↔ less upside remaining | Has much of the opportunity already been recognised? |

Entry Mode describes the timing of a potential entry, not the completeness of Pattern Stage. They are related but not identical:
- Pattern Stage answers: "How complete is the pattern?"
- Entry Mode answers: "How early or late is participation relative to the expected move?"

A developing pattern may still present an excellent opportunity if risk is clearly defined and substantial upside remains. Likewise, a fully triggered pattern may present a poor opportunity if much of the move has already occurred.

### Trade Mode Signal

Determine what the current stage of pattern development implies about participation, and therefore entry. Consult the Entry Implication Guide below to understand which chart behaviours typically correspond to the assigned Entry Mode for the current pattern. The purpose is to interpret what the current development means in terms of participation — not to generate signals or prescribe entries. Use as a reference; the chart takes precedence.

#### Trade Mode Signal Guide

| Pattern | Aggressive (Early) | Balanced (Developing) | Chasing (Late) |
|---|---|---|---|
| Bull Flag | Support reaction inside flag | Higher low forms inside flag | Breakout above flag |
| Bear Flag | Resistance rejection inside flag | Lower high forms inside flag | Breakdown below flag |
| Bull Pennant | Lower boundary reaction | Higher low near apex | Breakout above pennant |
| Bear Pennant | Upper boundary rejection | Lower high near apex | Breakdown below pennant |
| Rising Channel Pullback | Lower channel support reaction | Higher low inside channel | Expansion above channel |
| Falling Channel Pullback | Upper channel rejection | Lower high inside channel | Breakdown below channel |
| Support Retest | First support reaction | Higher low above support | Acceptance above level |
| Resistance Retest | First resistance rejection | Lower high below resistance | Acceptance below level |
| Ascending Triangle | Rising support reaction | Compression into apex | Resistance breakout |
| Descending Triangle | Falling resistance rejection | Compression into apex | Support breakdown |
| Symmetrical Triangle | Boundary reaction | Apex compression | Breakout from structure |
| Rising Wedge | Upper boundary rejection | Internal structure break | Breakdown below wedge |
| Falling Wedge | Lower boundary support | Internal structure break | Breakout above wedge |
| Bullish Rectangle | Range support reaction | Higher low inside range | Range breakout |
| Bearish Rectangle | Range resistance rejection | Lower high inside range | Range breakdown |
| Cup & Handle | Handle support reaction | Handle compression develops | Breakout above handle |
| Rounded Bottom | Accumulation support reaction | Internal structure shift | Resistance breakout |
| Rounded Top | Distribution resistance rejection | Internal structure shift | Support breakdown |
| Double Bottom | Second low rejection | Internal structure break | Neckline breakout |
| Double Top | Second high rejection | Internal structure break | Neckline breakdown |
| Triple Bottom | Third low rejection | Internal structure break | Neckline breakout |
| Triple Top | Third high rejection | Internal structure break | Neckline breakdown |
| Head & Shoulders | Right shoulder rejection | Neckline becomes obvious | Neckline breakdown |
| Inverse Head & Shoulders | Right shoulder support | Neckline becomes obvious | Neckline breakout |
| Structure Shift | First HL/LH after BOS | Retest holds | Expansion confirms shift |
| Bearish SFP | Sweep wick rejection | Reaction low breaks | Acceptance below structure |
| Bullish SFP | Sweep wick support | Reaction high breaks | Acceptance above structure |
| Equal High Sweep | Liquidity grab rejection | Local structure breaks | Acceptance below range |
| Equal Low Sweep | Liquidity grab support | Local structure breaks | Acceptance above range |
| Prior Day High Sweep | PDH rejection wick | Reaction low breaks | Acceptance below structure |
| Prior Day Low Sweep | PDL support wick | Reaction high breaks | Acceptance above structure |
| Failed Breakout | Rejection back into range | Acceptance below breakout level | Expansion away from reclaimed resistance |
| Failed Breakdown | Reclaim back above support | Acceptance above breakdown level | Expansion away from reclaimed support |

### Market Logic Reasoning

Do not assess patterns using a checklist. Determine whether the observed behaviour genuinely supports the pattern thesis. Focus on the interaction between Location, Behaviour, and Structure rather than counting characteristics.

Consider:
- What are buyers doing? What are sellers doing?
- Is one side losing control? Is one side gaining control?
- Is behaviour changing relative to the preceding trend?
- Does this behaviour commonly precede the pattern?

Do not treat all observations equally. Some carry significantly more weight than others.

### Market Logic Commentary (Output)

After completing your assessment, produce a concise Market Logic Commentary using the Location, Behaviour and Structural evidence together with Pattern Stage and Entry Mode. Explain **why** the pattern may be developing. Do not simply list observations — explain the pattern rather than describe it. Present as one short paragraph, not a checklist.

### Pattern Prioritisation

The objective is **not** to identify the most mature or most complete pattern — it is to identify the opportunity with the greatest expected value.

Prioritise opportunities that exhibit:
- Strong market logic.
- Clearly defined risk.
- Meaningful upside remaining.
- Sufficient evidence that the pattern is continuing to develop as expected.

Prioritise favourable risk-to-reward and asymmetric opportunities over perfectly formed patterns. A less-complete pattern with clearly defined risk and substantial upside may be superior to a fully developed pattern whose expected move is largely complete.

---

## PHASE 4 — TRADE SETUP PLAN

Convert the highest-ranked patterns into executable trade ideas (Trade Setups).

A valid Trade Setup must possess:
- A natural entry location specific to the current chart.
- A clearly defined invalidation thesis.
- Sufficient upside remaining.
- Attractive asymmetry between risk and reward.

Not every valid pattern provides a valid trade. If these conditions are absent, classify the pattern as **No Trade**. Do not force trades.

### Inherited Analysis

Trade Setups build upon Phase 3. Inherit (do not reassess): Pattern, Pattern Maturity, Entry Mode, Market Logic Commentary. The purpose of Phase 4 is not to rediscover opportunities, but to express them as trades using the current TradingView chart.

### Trade Setup Philosophy

- Only pitch the top three patterns.
- Trade entries should belong naturally to the pattern and its current stage of development.
- Different patterns require different execution and trade management.
- Market Condition provides context rather than exclusion. Reversal, liquidity and transition patterns may develop against the prevailing condition and should be evaluated on their own merits.
- The objective is to identify the cleanest entry and exit structure that naturally belongs to the pattern — not to produce a trade for every pattern.
- Do not force trades. If conditions for a valid trade are absent, classify as No Trade.

### Trade Setup Hierarchy

```
Inherited: Pattern, Pattern Maturity, Entry Mode
        ↓
Current TradingView Chart
        ↓
Entry Zone
        ↓
Invalidation Level
        ↓
Profit Objectives
        ↓
Technical Analysis References
        ↓
Trade Quality
```

The current chart determines the trade location. Technical Analysis References may refine execution. Price structure always takes precedence. The pattern determines the Technical Analysis References, not the other way around.

#### 1. Determine Trade Entry or Entry Zone

Using Pattern, Pattern Maturity, Entry Mode and the current chart, determine Entry Price or Entry Zone. Ask: What is the most appropriate entry? Where does participation naturally belong? When multiple locations are available, prefer the one with clearly defined risk, attractive asymmetry, meaningful upside remaining, and a clearly invalidated thesis.

##### Technical Analysis Reference Guide

Once Entry, Invalidation and Profit Objectives have been identified from price structure, determine whether any Technical Analysis References materially improve execution precision.

- Begin with the chart pattern itself. Identify which references naturally belong to the pattern.
- Different patterns require different references. Apply only those that materially improve the precision of the entry zone, invalidation level, or profit objectives.
- Not every reference will be relevant.
- The pattern and chart determine the references, not the other way around. The purpose is not to confirm the pattern, but to refine execution. Price structure always takes precedence.

Example reference applicability:
- **Fibonacci Golden Pocket** — Flags, Retests, Channels.
- **AVWAP** — Continuation patterns, Retests, Structure Shifts.
- **EMA** — Continuation patterns.
- **Measured Moves** — Double Tops, Double Bottoms, Head & Shoulders, Triangles.
- **Liquidity Pools** — Sweeps, SFPs, Failed Breakouts.
- **RSI / MACD Divergence** — Reversals, Wedges.
- **CVD** — Liquidity patterns.
- **Open Interest** — Compression patterns.
- **Funding** — Liquidity setups.
- **Higher Timeframe Support & Resistance** — relevant to all patterns.

Do not begin with references and then search for a pattern, price or level.

#### 2. Determine Invalidation Level

Where would the inherited trade thesis be proven wrong? Stops should invalidate the thesis rather than simply protect the position.

#### 3. Determine Profit Objectives: TP1 & TP2

Where should the inherited thesis naturally expect to travel? Objectives should reflect the chart and the analysis rather than arbitrary reward multiples. They may derive from support/resistance, liquidity, measured moves, pattern projections, or remaining upside visible on the chart. For each target, include a Risk:Reward calculation. Do not force objectives beyond logical market destinations.

#### 4. Assigned Grade

Assign a Trade Grade after Entry, Invalidation and Profit Objectives are identified. Trade Grade measures the **quality of the trade opportunity at the current location** with the proposed setup in mind — not pattern completion. Do not reward confirmation if confirmation has already consumed most of the move.

Grade on: Remaining Upside, Risk Definition, Reward-to-Risk, Entry Location, Pattern Maturity, Market Logic, Confluence, Market Context (does BTC/ETH or broader structure support, weaken or delay the setup?).

| Grade | Meaning | Requires |
|---|---|---|
| **A** | Opportunity-rich | Strong upside remaining; clearly defined invalidation; attractive R:R; entry belongs naturally to the inherited Entry Mode; pattern developed enough to justify participation but not so late that most of the move has occurred; strong market logic |
| **B** | Opportunity-present | Acceptable upside remaining; reasonably clear invalidation; acceptable R:R; entry valid but not ideal; some confirmation present but some opportunity already consumed |
| **C** | Opportunity-poor | Most of the expected move already occurred; weak R:R; entry late or crowded; stop placement may be unclear; pattern may be valid but trade quality is poor |
| **D** | No Trade | Entry unclear; invalidation unclear; R:R unattractive; insufficient upside; setup requires forcing an entry |

> A fully confirmed pattern may still receive a **C** if the move is already extended. A developing pattern may receive an **A** if risk is clearly defined and upside remains substantial.

##### No Trade Rule

It is acceptable to conclude that no attractive trade currently exists. A valid pattern does not imply a valid trade. Do not force a trade simply because a pattern exists. If no quality trade exists, classify as No Trade and explain why.

---

## PHASE 5 — TRADE MANAGEMENT

### Intermarket Context Rule: BTC and ETH

Where relevant, explain how Bitcoin or Ethereum behaviour may strengthen, weaken or delay the pattern thesis. Intermarket analysis is supplementary and should not override the asset's own observed structure. Do not assume correlation. Only discuss BTC or ETH when their behaviour is likely to materially influence the setup. The objective is not to forecast Bitcoin, but to identify how changes in BTC/ETH may affect the probability and timing of the trade thesis.

### Intermarket Correlation Bands (COR → Label)

Measure the coin's correlation to BTC with **COR** — the Pearson correlation of returns vs BTC over the chosen interval (the dashboard uses 15-minute candles, `COR (15M)`; same calculation as the Market Scanner's `cor5m`). The **label describes the degree of BTC dependency, not market direction** — the directional read (is BTC strong or weak right now, and what that means for the coin) belongs in the accompanying note, never the label.

| COR | Label | Interpretation |
|---|---|---|
| **+0.80 to +1.00** | 🟢 **Risk On** | **Strong BTC dependency.** BTC is the primary driver and the coin is likely to follow broader market direction. |
| **+0.60 to +0.79** | 🟡 **Moderate** | **BTC dominates, but local structure matters.** The coin generally follows BTC, though coin-specific factors can influence performance. |
| **+0.30 to +0.59** | 🟠 **Partial** | **BTC matters, but the coin has room for its own narrative.** Local order flow and catalysts can meaningfully affect price action. |
| **0.00 to +0.29** | ⚪ **Neutral** | **Coin driven primarily by its own order flow.** BTC direction offers limited information and local structure takes precedence. |
| **−0.20 to 0.00** | 🔵 **Risk Off** | **BTC direction offers little information.** The coin behaves largely independently of broader market moves. |
| **< −0.20** | 🟣 **Inverse** | **Coin may strengthen when BTC weakens.** Negative correlation is uncommon and should be treated with caution, as it is often unstable. |

The label is **derived from the COR value**, never hand-assigned. The dashboard implements this lookup (`_cor_band()`); the JSON stores only the measured `cor` (and `cor_tf`), so the rendered label can never disagree with this table.

---

## APPENDIX — OUTPUT FORMAT

### Market Structure
- **Market Structure:** 2 bullets
- **Volatility State:** 1 bullet
- **Market Bias:** Bullish, Bearish, or Neutral (with relevant icon)

Focus on what is observable and why it matters.

### Pattern Candidates Ranked by Opportunity

Present only the top three patterns. For each:
- **Pattern:** one line
- **Pattern Maturity:** one line
- **Classification:** one line
- **Entry Mode:** one line
- **Entry Quality:** one line
- **Pattern Grade:** one line
- **Evidence:** max 5 bullets, market logic. Each bullet: what is observed + why it matters.
- **Missing features:** max 3 bullets. Only what prevents the pattern from progressing.
- **Confluence:** max 3 bullets. Only factors that materially strengthen the setup.
- **Trade Grade:** one letter (A/B/C/D), state the grade and the reason.
  - *Example:* A — developing structure, clear invalidation below the second low, and strong upside remains before the neckline / next resistance.
- **Summary:** max 2 sentences. What is present; what is still missing. Avoid repeating Evidence or Confluence.

### Trade Setup

Only provide a Trade Setup if a valid opportunity exists.
- **Trade Status:** one line
- **Entry Price or Zone:** state price or range; in one line explain why this location naturally belongs to the pattern.
- **Stop Loss:** in one line, state what thesis is invalidated.
- **TP1:** state price. Correlate to R:R. State the implication, not just the ratio.
- **TP2:** state price. Correlate to R:R. State the implication, not just the ratio.
- Focus on the primary pattern objective.
- **Supporting Tools:** list whatever tools were actually used to define setup numbers (may be from the Technical Analysis References Guide).
- **Trade Execution Commentary:** max 2 bullets — why this trade location is attractive; what would invalidate the opportunity.

---

## COMMUNICATION RULES

### Insight Rule
Pre-crunch every number. The reader never performs the interpretation. Every reading must immediately state its implication. The number is evidence; the sentence explains why it matters.

### Confidence Rule
State only what can be observed. Use: *suggests, indicates, supports, appears.* Avoid: *will, definitely, certain.* Never assume intent or future direction.

### Comparison Rule
Do not compare setups against other analyses run in other sessions. Reference BTC or ETH only when correlation is materially relevant.

### Writing Style
Write for an experienced trader with 30 seconds to read the findings. Every statement should answer: What do I see? Why does it matter? What is missing?

Avoid: long narratives, storytelling, educational commentary, indicator-by-indicator descriptions, repetition.

### Final Check
Before submitting: rewrite raw readings into implications; remove repetition; remove filler; remove educational commentary; keep only observations that improve pattern recognition or trade execution.
