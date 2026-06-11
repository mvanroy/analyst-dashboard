# Trade Journal — Google Sheets setup (Phase 1, append-only)

One-time, ~5 minutes. No Google Cloud account or service account needed.

## 1. Create the sheet
- Make a new Google Sheet (call it e.g. "Orion Trade Journal").

## 2. Add the script
- In the sheet: **Extensions → Apps Script**.
- Delete any starter code, paste the entire contents of [`apps_script.gs`](apps_script.gs), **Save**.

## 3. Build the layout
- In the Apps Script editor toolbar, pick the **`setupSheet`** function and click **Run**.
- Authorise when prompted (it's your own script on your own sheet).
- A "Trades" tab appears with colour-banded headers, frozen Date + Symbol columns, and dropdowns.

## 4. Deploy as a web app
- **Deploy → New deployment → ⚙ → Web app**.
- **Execute as:** Me
- **Who has access:** Anyone
- **Deploy**, then **copy the Web app URL** (ends in `/exec`).

## 5. Point the app at it
- Open `journal_config.json` in the project root and paste your URL:
  ```json
  { "webhook_url": "https://script.google.com/macros/s/XXXX/exec", "token": "" }
  ```
- (Optional) For a little extra safety, set a `TOKEN` string at the top of `apps_script.gs`,
  re-deploy, and put the same value in `"token"` here.

That's it — the **Push to Journal** button in the calculator now appends a planned-trade row.

> If you change the columns later, edit `SCHEMA` in `apps_script.gs`, run `setupSheet` again,
> and **create a new deployment version** (Deploy → Manage deployments → Edit → New version).

## Columns
- **🟦 Plan** (blue) — auto from the calculator on every push.
- **🟦 Analyst** (teal) — auto from the `/trade` analysis (pushed trades only; blank for Blank-Calc trades).
- **🟩 Classify** (green) — Market environment / Setup type / Entry rationale → **you fill in** (dropdowns provided).
- **🟧 Execution** (amber) — reserved for the Phase-2 Bybit sync.
- **🟩 Outcome** (green) — derived once execution data lands.
- **🟪 Reflection** (purple) — Confidence / Emotional state / Mistakes-Lessons / Tags → you fill in.
