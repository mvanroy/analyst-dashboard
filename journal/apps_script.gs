/**
 * Orion Trade Journal — Google Apps Script web app.
 *
 * SETUP (one time):
 *   1. Open your Google Sheet → Extensions → Apps Script.
 *   2. Paste this whole file, Save.
 *   3. Run ▸ setupSheet  (authorise when prompted). This builds the "Trades" tab:
 *      headers, colour-banded sections, frozen key columns, and dropdowns.
 *   4. Deploy ▸ New deployment ▸ Web app
 *        Execute as: Me   |   Who has access: Anyone
 *      Copy the /exec URL and paste it into journal_config.json in the app.
 *   (Optional) set TOKEN below to a secret string and put the same value in journal_config.json.
 */

const SHEET_NAME = 'Trades';
const TOKEN = '';  // optional shared secret; if set, pushes must include the same token

// [ Header, payloadKey, section, dropdownKey ]
const SCHEMA = [
  ['Date/time planned', 'planned_at',      'plan',     null],
  ['Symbol',            'symbol',          'plan',     null],
  ['Direction',         'direction',       'plan',     'direction'],
  ['Sizing mode',       'sizing_mode',     'plan',     'sizing_mode'],
  ['Entry',             'entry',           'plan',     null],
  ['Stop',              'stop',            'plan',     null],
  ['TP1',               'tp1',             'plan',     null],
  ['TP2',               'tp2',             'plan',     null],
  ['R:R TP1',           'rr_tp1',          'plan',     null],
  ['R:R TP2',           'rr_tp2',          'plan',     null],
  ['Position size',     'position_size',   'plan',     null],
  ['Notional (USDT)',   'notional',        'plan',     null],
  ['Leverage',          'leverage',        'plan',     null],
  ['Margin',            'margin',          'plan',     null],
  ['Risk $',            'risk_usd',        'plan',     null],
  ['Risk %',            'risk_pct',        'plan',     null],
  ['Account balance',   'account_balance', 'plan',     null],
  ['Liq price',         'liq_price',       'plan',     null],
  ['Liq buffer',        'liq_buffer',      'plan',     null],
  ['Setup score',       'setup_score',     'plan',     null],
  ['Live price at push','live_price',      'plan',     null],

  ['Analyst bias',         'analyst_bias',         'analyst', null],
  ['Analyst market state', 'analyst_market_state', 'analyst', null],
  ['Analyst phase',        'analyst_phase',        'analyst', null],
  ['Analyst setup',        'analyst_setup',        'analyst', null],
  ['Analyst verdict',      'analyst_verdict',      'analyst', null],

  ['Market environment','market_environment','classify','market_environment'],
  ['Setup type',        'setup_type',        'classify','setup_type'],
  ['Entry rationale',   'entry_rationale',   'classify',null],

  ['Actual entry', 'actual_entry', 'exec', null],
  ['Actual exit',  'actual_exit',  'exec', null],
  ['Actual size',  'actual_size',  'exec', null],
  ['Fees',         'fees',         'exec', null],
  ['Funding',      'funding',      'exec', null],
  ['Opened at',    'opened_at',    'exec', null],
  ['Closed at',    'closed_at',    'exec', null],
  ['Duration',     'duration',     'exec', null],
  ['Liquidated',   'liquidated',   'exec', null],

  ['Realized P&L',   'realized_pnl',   'outcome', null],
  ['Outcome',        'outcome',        'outcome', 'outcome'],
  ['Realized R',     'realized_r',     'outcome', null],
  ['Plan adherence', 'plan_adherence', 'outcome', null],
  ['Status',         'status',         'outcome', 'status'],

  ['Confidence',         'confidence',       'reflect', 'confidence'],
  ['Emotional state',    'emotional_state',  'reflect', 'emotional_state'],
  ['Mistakes / Lessons', 'mistakes_lessons', 'reflect', null],
  ['Chart screenshot',   'chart_link',       'reflect', null],
  ['Tags',               'tags',             'reflect', null],
];

// header colours per section (white bold text on these)
const SECTION_COLOR = {
  plan:     '#4c8dff',  // blue   — the plan (auto from calculator)
  analyst:  '#2bb3a3',  // teal   — analyst's read (auto, pushed trades only)
  classify: '#0e9f6e',  // green  — your classification (manual)
  exec:     '#e0a33e',  // amber  — execution (Bybit, phase 2)
  outcome:  '#16a34a',  // green  — outcome (derived)
  reflect:  '#8b5cf6',  // purple — reflection (manual)
};

const DROPDOWNS = {
  direction:          ['Long', 'Short'],
  sizing_mode:        ['Risk', 'Exposure'],
  market_environment: ['Trending', 'Counter-trend', 'Range', 'High-volatility'],
  setup_type:         ['Fib retracement', 'Bullish divergence', 'Short of resistance',
                       'A/VWAP', 'Reclaim breakout', 'Retest mean reversion'],
  outcome:            ['Win', 'Loss', 'Breakeven'],
  status:             ['Planned', 'Open', 'Closed'],
  confidence:         ['1', '2', '3', '4', '5'],
  emotional_state:    ['Calm', 'Confident', 'FOMO', 'Anxious', 'Revenge', 'Hesitant', 'Bored'],
};

function _ensureSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
}

function _buildSheet(sh) {
  const headers = SCHEMA.map(function (s) { return s[0]; });
  sh.getRange(1, 1, 1, headers.length).setValues([headers]);
  for (var i = 0; i < SCHEMA.length; i++) {
    var color = SECTION_COLOR[SCHEMA[i][2]] || '#444444';
    sh.getRange(1, i + 1).setBackground(color).setFontColor('#ffffff')
      .setFontWeight('bold').setWrap(true).setVerticalAlignment('middle');
    var dk = SCHEMA[i][3];
    if (dk && DROPDOWNS[dk]) {
      var rule = SpreadsheetApp.newDataValidation()
        .requireValueInList(DROPDOWNS[dk], true).setAllowInvalid(true).build();  // warn, don't reject
      sh.getRange(2, i + 1, 2000, 1).setDataValidation(rule);
    }
  }
  sh.setRowHeight(1, 42);
  sh.setFrozenRows(1);
  sh.setFrozenColumns(2);  // Date/time + Symbol stay visible
  sh.autoResizeColumns(1, headers.length);
}

/** Run this once from the editor to lay out the journal. */
function setupSheet() {
  var sh = _ensureSheet();
  _buildSheet(sh);
  SpreadsheetApp.getUi().alert('Journal ready — ' + SCHEMA.length + ' columns on the "' + SHEET_NAME + '" tab.');
}

/** Web-app endpoint: the app POSTs a trade here and we append a row. */
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (TOKEN && body.token !== TOKEN) return _json({ ok: false, error: 'bad token' });
    var sh = _ensureSheet();
    if (sh.getLastRow() < 1) _buildSheet(sh);  // first run: lay it out
    var row = SCHEMA.map(function (s) {
      var v = body[s[1]];
      return (v === undefined || v === null) ? '' : v;
    });
    sh.appendRow(row);
    return _json({ ok: true, row: sh.getLastRow() });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
