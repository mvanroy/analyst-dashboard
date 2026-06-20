---
description: Convert the latest /trade verdict into the Trade Dashboard data file (analyses/<SYMBOL>.json).
---

Convert the most recent `/trade` analysis in this conversation into the Trade
Dashboard's data file.

1. Read `framework/dashboard_json_contract.md` and follow it **exactly** — it
   defines the v3 schema (`market_structure`, `intermarket`, `pattern_candidates`),
   the field-by-field mapping, and the derivation rules. `analyses_demo/<SYMBOL>.json`
   is the canonical example to match.

2. Use the analysis **already produced above in this session.** If there is no
   `/trade` verdict in this conversation, stop and ask the user to run
   `/trade <SYMBOL>` first — do not invent or re-run an analysis.

3. Build `analyses/<SYMBOL>.json` per the contract:
   - narrative fields (summary, evidence, notes, confluence) **verbatim** from the
     verdict — never rewritten,
   - computed fields by the rules: `meta.analysis_time` in **Melbourne** time,
     `intermarket.cor` measured via `scanner._pearson` (15m vs BTC), `t1/t2.rr`
     computed from the levels, candidates sorted by opportunity,
   - `framework_version` = `"Trade Setup Framework v1"`, `schema_version` = 2.

4. Write the file, then **validate it parses** as JSON:
   `python3 -c "import json; json.load(open('analyses/<SYMBOL>.json'))"`

5. Confirm the path you wrote, then tell the user:
   *"Done — open the Trade Dashboard and click **Run**."*
