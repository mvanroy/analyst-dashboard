---
description: Run the Trade Setup Framework on a ticker and print the full Phase 1–5 verdict in chat.
argument-hint: [TICKER, e.g. HYPEUSDT]
---

Run a full **Trade Setup Framework** analysis on **$ARGUMENTS**.

1. Read `framework/trade_setup_framework.md` — this is the exact operating
   framework. Follow it precisely and in order (Phase 1 → 5). Read
   `framework/chart_pattern_library.md` for the pattern definitions, evidence
   tables, confluence, failure lens, and entry-mode logic it relies on. Stay
   hypothesis-neutral; never begin with a conclusion and work backwards.

2. Format the output **exactly** to the framework's Appendix output format:
   - **Market Structure** — Market State, Volatility State, Market Bias (with the
     2-bullet structure read and the volatility/bias notes).
   - **Pattern Candidates Ranked by Opportunity** — the top 3 patterns, each with
     Pattern, Maturity, Classification, Entry Mode, Entry Quality, Pattern Grade,
     Evidence (≤5, each leads with the implication), Missing features (≤3),
     Confluence (≤3), Trade Grade + reason, Summary (≤2 sentences).
   - **Trade Setup** per candidate (only where a valid opportunity exists) —
     Status, Entry Price/Zone, Stop Loss (what it invalidates), TP1 & TP2 (price,
     R:R, implication), Supporting Tools, Trade Execution Commentary (≤2 bullets).
   Rank by **opportunity (expected value)**, not maturity.

3. Gather the data the framework needs (Daily + 4H + execution-TF market
   structure, EMAs/AVWAP, RSI/MACD, volume behaviour, key S/R, current price,
   and the BTC series for the correlation read) from your market-data tools — the
   TradingView MCP and/or live exchange REST. If a required reading isn't
   available, say so explicitly rather than guessing.

4. **Derivatives (OI / Funding / CVD) — fetch when relevant and fold them into
   the patterns' Confluence / Evidence / Supporting Tools**, per the framework
   (market structure takes precedence; derivatives are supporting references, not
   a separate verdict box). Public REST, no auth:
   - **OI + Funding** — Bybit:
     `https://api.bybit.com/v5/market/tickers?category=linear&symbol=<SYM>` and
     `https://api.bybit.com/v5/market/open-interest?category=linear&symbol=<SYM>&intervalTime=4h&limit=24`.
   - **CVD** — Binance futures klines
     `https://fapi.binance.com/fapi/v1/klines?symbol=<SYM>&interval=1h&limit=168`:
     per bar `delta = 2*takerBuyBaseVol(idx9) − volume(idx5)`, `CVD = cumsum`.
   Assert the read (don't hedge): OI building into the move = conviction; funding
   stretched = crowded/late; CVD divergence = absorption/lack of real flow.

5. Output **only the written verdict in chat.** Do NOT produce JSON or modify any
   files — updating the dashboard is the separate `/push-dashboard` step
   (`framework/dashboard_json_contract.md`).

6. If you have a genuinely important insight that doesn't fit a framework field
   (e.g. BTC regime, event risk, a data caveat), add a short **Analyst Notes**
   section at the end. Only real signal — no filler.
