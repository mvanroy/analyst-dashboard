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
const SCRIPT_VERSION = '2026-07-10-trading-cycles-v1';

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
    if (body.action === 'bybit') return _appendBybit(body);   // Bybit-pull journal (2nd tab)
    if (body.action === 'open_positions') return _syncOpenPositions(body.rows || []);
    if (body.action === 'repair_bybit') return _repairBybitJournalEndpoint();
    if (body.action === 'replace_cycle') return _replaceCycle(body);
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

/** Web-app GET: returns the "Bybit Journal" rows as JSON so Trade Analytics can read the
 *  manual judgment columns (Set Up Type, Market Bias, etc.) that don't exist in Bybit's API.
 *  Columns are matched by HEADER TEXT (row BYBIT_R1 - 1), so the read survives any extra or
 *  inserted columns (e.g. a leading "#" column) rather than assuming a fixed column order. */
function doGet(e) {
  try {
    var cycle = e && e.parameter && e.parameter.cycle ? Number(e.parameter.cycle) : 2;
    var sh = _cycleSheet(cycle);
    if (!sh) return _json({ ok: true, rows: [], features: _features() });
    var last = sh.getLastRow(), lastCol = sh.getLastColumn();
    if (last < BYBIT_R1 || lastCol < 1) return _json({ ok: true, rows: [], features: _features() });
    var norm = function (s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim().toLowerCase(); };
    var headers = sh.getRange(BYBIT_R1 - 1, 1, 1, lastCol).getValues()[0];
    var colOf = {};
    for (var i = 0; i < BYBIT_SCHEMA.length; i++) {
      var want = norm(BYBIT_SCHEMA[i][0]);
      for (var c = 0; c < headers.length; c++) {
        if (norm(headers[c]) === want) { colOf[BYBIT_SCHEMA[i][1]] = c; break; }
      }
    }
    var vals = sh.getRange(BYBIT_R1, 1, last - BYBIT_R1 + 1, lastCol).getValues();
    var rows = [];
    for (var r = 0; r < vals.length; r++) {
      var o = {};
      for (var key in colOf) o[key] = vals[r][colOf[key]];
      if (o.trade_id !== '' && o.trade_id != null) rows.push(o);
    }
    return _json({ ok: true, rows: rows, features: _features() });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function _features() {
  return {
    script_version: SCRIPT_VERSION,
    bybit_journal: true,
    open_positions: true,
    trade_origin: true,
    trading_cycles: true,
    cycle_1_gid: CYCLE_1_GID,
    cycle_2_gid: CYCLE_2_GID,
    cycle_2_cutoff_ms: CYCLE_2_CUTOFF_MS,
  };
}

// =========================================================================
//  Bybit-pull journal — a second "Bybit Journal" tab, populated by the
//  Sync from Bybit (journal/sync_bybit.py). Run setupBybitJournal() once.
// =========================================================================
var BYBIT_SHEET = 'Bybit Journal';  // legacy name; cycle tabs are addressed only by ID
var BYBIT_R1 = 4;  // first data row (1: info strip, 2: section bands, 3: column headers)
var CYCLE_1_GID = 1304074642;
var CYCLE_2_GID = 1842282429;
var CYCLE_2_CUTOFF_MS = 1783666800000;  // 10 Jul 2026, 5:00 PM Melbourne
var LEGACY_CYCLE_1_POSITIONS = [
  { coin: 'EDENUSDT', long_short: 'Long', opened_ts: 1783647072852 },
  { coin: 'XCNUSDT',  long_short: 'Long', opened_ts: 1783647192431 },
];

function _cycleSheet(cycle) {
  var gid = Number(cycle) === 1 ? CYCLE_1_GID : Number(cycle) === 2 ? CYCLE_2_GID : 0;
  if (!gid) throw new Error('cycle must be 1 or 2');
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetById(gid);
  if (!sh) throw new Error('Configured Cycle ' + cycle + ' tab was not found');
  return sh;
}

function _isLegacyCycle1(body) {
  var opened = Number(body.opened_ts);
  for (var i = 0; i < LEGACY_CYCLE_1_POSITIONS.length; i++) {
    var p = LEGACY_CYCLE_1_POSITIONS[i];
    if (String(body.coin || '') === p.coin && String(body.long_short || '') === p.long_short &&
        isFinite(opened) && Math.abs(opened - p.opened_ts) <= 120000) return true;
  }
  return false;
}

function _cycleForTrade(body) {
  var closed = Number(body.closed_ts);
  if (!isFinite(closed) || closed <= 0) throw new Error('closed_ts is required for cycle routing');
  if (_isLegacyCycle1(body)) return 1;
  return closed >= CYCLE_2_CUTOFF_MS ? 2 : 1;
}

// [ Header, payloadKey, section, dropdownKey, kind ]   kind: data | manual | formula | id
var BYBIT_SCHEMA = [
  ['#',                               'row_no',          'entry', null,          'formula'],
  ['Entry Date\n(dd/mm/yyyy)',        'entry_date',      'entry', null,          'data'],
  ['Market (Coin)',                   'coin',            'entry', null,          'data'],
  ['Trade Origin',                     'trade_origin',    'entry', null,          'manual'],
  ['Market Bias',                     'market_bias',     'entry', null,          'manual'],
  ['Set Up Type',                     'setup_type',      'entry', null,          'manual'],
  ['Entry Rationale',                 'entry_rationale', 'entry', null,          'manual'],
  ['Strategy',                        'strategy',        'entry', null,          'manual'],
  ['Set Up Grade',                    'setup_grade',     'entry', 'setup_grade', 'manual'],
  ['Long/Short',                      'long_short',      'entry', 'long_short',  'data'],
  ['Position Size ($)',               'position_size',   'entry', null,          'data'],
  ['Entry Price ($)',                 'entry_price',     'entry', null,          'data'],
  ['Risk Reward',                     'risk_reward',     'exit',  null,          'manual'],
  ['Exit Price ($)',                  'exit_price',      'exit',  null,          'data'],
  ['Trade Screenshot',                'screenshot',      'exit',  null,          'manual'],
  ['Reason for Cutting\nThe Trade',   'cut_reason',      'mgmt',  'cut_reason',  'manual'],
  ['Cut Result',                      'cut_result',      'mgmt',  'cut_result',  'manual'],
  ['P/L Gross ($)',                   'pl_gross',        'perf',  null,          'data'],
  ['Fees ($)',                        'fees',            'perf',  null,          'data'],
  ['Net P/L ($)',                     'pl_net',          'perf',  null,          'data'],
  ['Win / Loss',                      'win_loss',        'perf',  null,          'formula'],
  ['Cumulative P/L ($)',              'cum_pl',          'perf',  null,          'formula'],
  ['Trade ID',                        'trade_id',        'id',    null,          'id'],
];

var BYBIT_GROUPS = [   // [ label, section, band colour ]
  ['Trade Entry',       'entry', '#33336b'],
  ['Trade Exit',        'exit',  '#33336b'],
  ['Trade Management',  'mgmt',  '#33336b'],
  ['Trade Performance', 'perf',  '#1a9e90'],
];
var BYBIT_COLHEAD = { entry: '#4f6cb0', exit: '#4f6cb0', mgmt: '#4f6cb0', perf: '#2bb3a3', id: '#9aa0a6' };
var BYBIT_DD = {
  long_short:  ['Long', 'Short'],
  setup_grade: ['Low', 'Medium', 'High'],
  cut_reason:  ['Discretionary cut', 'Time duration cut', 'FTA base cut'],
  cut_result:  ['SL hit', 'TP hit'],
};
var BYBIT_MONEY = ['position_size', 'pl_gross', 'fees', 'pl_net', 'cum_pl'];  // $ amounts, 2dp
var BYBIT_PRICE = ['entry_price', 'exit_price'];                              // prices, up to 6dp

function _colLetter(n) { var s = ''; while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }
function _bCol(key) { for (var i = 0; i < BYBIT_SCHEMA.length; i++) if (BYBIT_SCHEMA[i][1] === key) return i + 1; return -1; }

/** Run once from the editor: builds the formatted "Bybit Journal" tab. */
function setupBybitJournal() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(BYBIT_SHEET) || ss.insertSheet(BYBIT_SHEET);
  sh.clear();
  try { sh.getBandings().forEach(function (b) { b.remove(); }); } catch (e) {}
  var n = BYBIT_SCHEMA.length;

  // Row 1 — info strip
  sh.getRange(1, 1).setValue('Account Size ($)').setFontWeight('bold');
  sh.getRange(1, 2).setBackground('#fff2cc');
  sh.getRange(1, 6).setValue('Start Date (auto)').setFontWeight('bold');
  var entryDateL = _colLetter(_bCol('entry_date'));
  sh.getRange(1, 7).setFormula('=IFERROR(TEXT(MIN(' + entryDateL + BYBIT_R1 + ':' + entryDateL + '1000),"dd/mm/yyyy"),"")').setBackground('#bfe9e4');
  sh.getRange(1, 11).setValue('Key').setFontWeight('bold');
  sh.getRange(1, 12).setValue('Do not alter — this autocalculates').setBackground('#bfe9e4').setFontStyle('italic');

  // Row 2 — section bands
  for (var g = 0; g < BYBIT_GROUPS.length; g++) {
    var sec = BYBIT_GROUPS[g][1], first = -1, last = -1;
    for (var i = 0; i < n; i++) if (BYBIT_SCHEMA[i][2] === sec) { if (first < 0) first = i + 1; last = i + 1; }
    if (first < 0) continue;
    sh.getRange(2, first, 1, last - first + 1).merge().setValue(BYBIT_GROUPS[g][0])
      .setBackground(BYBIT_GROUPS[g][2]).setFontColor('#ffffff').setFontWeight('bold')
      .setHorizontalAlignment('center').setVerticalAlignment('middle');
  }

  // Row 3 — column headers
  for (var i = 0; i < n; i++) {
    sh.getRange(3, i + 1).setValue(BYBIT_SCHEMA[i][0])
      .setBackground(BYBIT_COLHEAD[BYBIT_SCHEMA[i][2]] || '#4f6cb0').setFontColor('#ffffff')
      .setFontWeight('bold').setWrap(true).setHorizontalAlignment('center').setVerticalAlignment('middle');
  }
  sh.setRowHeight(3, 46);

  // Data area (rows 4..1000): dropdowns, number formats, performance tint
  var rows = 1000 - BYBIT_R1 + 1;
  for (var i = 0; i < n; i++) {
    var c = i + 1, key = BYBIT_SCHEMA[i][1], dk = BYBIT_SCHEMA[i][3], rng = sh.getRange(BYBIT_R1, c, rows, 1);
    if (dk && BYBIT_DD[dk]) rng.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(BYBIT_DD[dk], true).setAllowInvalid(true).build());
    if (BYBIT_MONEY.indexOf(key) >= 0) rng.setNumberFormat('$#,##0.00');
    if (BYBIT_PRICE.indexOf(key) >= 0) rng.setNumberFormat('$#,##0.00####');
    if (key === 'row_no') rng.setNumberFormat('0');
    if (key === 'entry_date') rng.setNumberFormat('dd/mm/yyyy');
    if (BYBIT_SCHEMA[i][2] === 'perf') rng.setBackground('#dff3f1');
  }

  // zebra banding across the non-performance columns
  try { sh.getRange(BYBIT_R1, 1, rows, _bCol('cut_result')).applyRowBanding(SpreadsheetApp.BandingTheme.LIGHT_GREY, false, false); } catch (e) {}

  sh.setFrozenRows(3);   // freeze the header rows (column-freeze can't cross the merged bands)
  sh.hideColumns(_bCol('trade_id'));
  for (var c = 1; c <= n; c++) sh.autoResizeColumn(c);
  _bybitColors(sh);
  SpreadsheetApp.getUi().alert('"Bybit Journal" tab is ready — ' + n + ' columns. Now run the Sync from Bybit.');
}

/** Conditional formatting: Long/Win green, Short/Loss red. Safe to run anytime (doesn't touch data). */
function _bybitColors(sh) {
  var ls = sh.getRange(BYBIT_R1, _bCol('long_short'), 1000, 1);
  var wl = sh.getRange(BYBIT_R1, _bCol('win_loss'), 1000, 1);
  function rule(range, text, bg, fg) {
    return SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(text).setBackground(bg).setFontColor(fg).setBold(true).setRanges([range]).build();
  }
  var rules = sh.getConditionalFormatRules();
  rules.push(rule(ls, 'Long',  '#c6efce', '#006100'));
  rules.push(rule(ls, 'Short', '#ffc7ce', '#9c0006'));
  rules.push(rule(wl, 'W',     '#c6efce', '#006100'));
  rules.push(rule(wl, 'L',     '#ffc7ce', '#9c0006'));
  sh.setConditionalFormatRules(rules);
}

/** Run this on an existing Bybit Journal to apply the Long/Short + Win/Loss colours. */
function colorBybitJournal() {
  _bybitColors(_cycleSheet(1));
  _bybitColors(_cycleSheet(2));
  SpreadsheetApp.getUi().alert('Long/Short and Win/Loss colours applied.');
}

function _dateKey(v) {
  if (!v) return '';
  if (Object.prototype.toString.call(v) === '[object Date]') {
    return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  var d = new Date(String(v).slice(0, 10) + 'T00:00:00');
  if (!isNaN(d.getTime())) return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  return String(v).slice(0, 10);
}

function _numKey(v) {
  var n = Number(v);
  return isNaN(n) ? '' : String(Math.round(n * 1000000) / 1000000);
}

function _legacyBybitKeyFromRow(row) {
  return [
    _dateKey(row[_bCol('entry_date') - 1]),
    String(row[_bCol('coin') - 1] || ''),
    String(row[_bCol('long_short') - 1] || ''),
    _numKey(row[_bCol('position_size') - 1]),
    _numKey(row[_bCol('entry_price') - 1]),
    _numKey(row[_bCol('exit_price') - 1]),
    _numKey(row[_bCol('pl_net') - 1])
  ].join('|');
}

function _legacyBybitKeyFromBody(body) {
  return [
    _dateKey(body.entry_date),
    String(body.coin || ''),
    String(body.long_short || ''),
    _numKey(body.position_size),
    _numKey(body.entry_price),
    _numKey(body.exit_price),
    _numKey(body.pl_net)
  ].join('|');
}

function repairBybitJournal() {
  _repairBybitJournalEndpoint();
}

function _repairBybitJournalEndpoint() {
  var sh = _cycleSheet(2);
  var lastRow = sh.getLastRow();
  if (lastRow < BYBIT_R1) return _json({ ok: true, repaired_rows: 0 });
  var rows = lastRow - BYBIT_R1 + 1;
  var rowNoCol = _bCol('row_no');
  var vals = [];
  for (var i = 0; i < rows; i++) vals.push([i + 1]);
  sh.getRange(BYBIT_R1, rowNoCol, rows, 1).setNumberFormat('0').setValues(vals);
  sh.getRange(BYBIT_R1, _bCol('entry_date'), rows, 1).setNumberFormat('dd/mm/yyyy');
  return _json({ ok: true, repaired_rows: rows });
}

/** Append one Bybit-pulled trade (de-duped by trade_id); sets Win/Loss + Cumulative formulas. */
function _appendBybit(body) {
  var cycle = _cycleForTrade(body);
  var sh = _cycleSheet(cycle);
  var idCol = _bCol('trade_id'), lastRow = sh.getLastRow();
  if (lastRow >= BYBIT_R1) {
    var existing = sh.getRange(BYBIT_R1, 1, lastRow - BYBIT_R1 + 1, sh.getLastColumn()).getValues();
    var incomingLegacyKey = _legacyBybitKeyFromBody(body);
    for (var k = 0; k < existing.length; k++) {
      if (String(existing[k][idCol - 1]) === String(body.trade_id)) return _json({ ok: true, dup: true, cycle: cycle });
      if (_legacyBybitKeyFromRow(existing[k]) === incomingLegacyKey) return _json({ ok: true, dup: true, legacy: true, cycle: cycle });
    }
  }
  var row = BYBIT_SCHEMA.map(function (s) {
    if (s[4] === 'formula') return '';
    var v = body[s[1]];
    if (v === undefined || v === null || v === '') return '';
    if (s[1] === 'entry_date') return new Date(v + 'T00:00:00');  // ISO -> real date
    return v;
  });
  sh.appendRow(row);
  var r = sh.getLastRow(), netL = _colLetter(_bCol('pl_net'));
  sh.getRange(r, _bCol('row_no')).setNumberFormat('0').setValue(r - BYBIT_R1 + 1);
  sh.getRange(r, _bCol('win_loss')).setFormula('=IF(' + netL + r + '="","",IF(' + netL + r + '>0,"W",IF(' + netL + r + '<0,"L","B")))');
  sh.getRange(r, _bCol('cum_pl')).setFormula('=SUM(' + netL + '$' + BYBIT_R1 + ':' + netL + r + ')');
  return _json({ ok: true, row: r, cycle: cycle });
}

/** Replace only the data rows in one cycle tab. Header/template rows and formatting remain intact. */
function _replaceCycle(body) {
  var cycle = Number(body.cycle);
  var rows = body.rows;
  if ((cycle !== 1 && cycle !== 2) || !Array.isArray(rows)) {
    return _json({ ok: false, error: 'replace_cycle requires cycle 1 or 2 and a rows array' });
  }
  var lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    var sh = _cycleSheet(cycle);
    var lastRow = sh.getLastRow();
    if (lastRow >= BYBIT_R1) {
      sh.getRange(BYBIT_R1, 1, lastRow - BYBIT_R1 + 1, Math.max(sh.getLastColumn(), BYBIT_SCHEMA.length)).clearContent();
    }
    var out = rows.map(function (bodyRow) {
      return BYBIT_SCHEMA.map(function (s) {
        if (s[4] === 'formula') return '';
        var v = bodyRow[s[1]];
        if (v === undefined || v === null || v === '') return '';
        if (s[1] === 'entry_date') return new Date(String(v).slice(0, 10) + 'T00:00:00');
        return v;
      });
    });
    if (out.length) sh.getRange(BYBIT_R1, 1, out.length, BYBIT_SCHEMA.length).setValues(out);
    var netL = _colLetter(_bCol('pl_net'));
    for (var i = 0; i < out.length; i++) {
      var r = BYBIT_R1 + i;
      sh.getRange(r, _bCol('row_no')).setNumberFormat('0').setValue(i + 1);
      sh.getRange(r, _bCol('win_loss')).setFormula('=IF(' + netL + r + '="","",IF(' + netL + r + '>0,"W",IF(' + netL + r + '<0,"L","B")))');
      sh.getRange(r, _bCol('cum_pl')).setFormula('=SUM(' + netL + '$' + BYBIT_R1 + ':' + netL + r + ')');
    }
    SpreadsheetApp.flush();
    return _json({ ok: true, cycle: cycle, replaced_rows: out.length });
  } finally {
    lock.releaseLock();
  }
}

// =========================================================================
//  Current open positions — a live snapshot tab in the same journal workbook.
//  Manual columns such as Trade Origin are preserved across syncs by position_id.
// =========================================================================
var OPEN_SHEET = 'Open Positions';
var OPEN_R1 = 3;

// [ Header, payloadKey, kind ] kind: data | manual | id
var OPEN_SCHEMA = [
  ['Position ID',        'position_id',   'id'],
  ['Opened At',          'opened_at',     'data'],
  ['Market (Coin)',      'coin',          'data'],
  ['Long/Short',         'long_short',    'data'],
  ['Position Size ($)',  'position_size', 'data'],
  ['Notional (USDT)',    'notional',      'data'],
  ['Leverage',           'leverage',      'data'],
  ['Entry Price ($)',    'entry_price',   'data'],
  ['Mark Price ($)',     'mark_price',    'data'],
  ['Liq Price ($)',      'liq_price',     'data'],
  ['Take Profit',        'take_profit',   'data'],
  ['Stop Loss',          'stop_loss',     'data'],
  ['Unrealized P&L ($)', 'unrealized_pnl','data'],
  ['Unrealized P&L %',   'unrealized_pct','data'],
  ['Live R',             'live_r',        'data'],
  ['Target R',           'target_r',      'data'],
  ['Status',             'status',        'data'],
  ['Trade Origin',       'trade_origin',  'manual'],
  ['Setup Type',         'setup_type',    'manual'],
  ['Notes',              'notes',         'manual'],
  ['Last Synced',        'last_synced',   'data'],
];

function _oCol(key) { for (var i = 0; i < OPEN_SCHEMA.length; i++) if (OPEN_SCHEMA[i][1] === key) return i + 1; return -1; }

function setupOpenPositions() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(OPEN_SHEET) || ss.insertSheet(OPEN_SHEET);
  _buildOpenPositions(sh);
}

function _buildOpenPositions(sh) {
  sh.clear();
  var n = OPEN_SCHEMA.length;
  sh.getRange(1, 1).setValue('Current Open Positions').setFontWeight('bold').setFontSize(14);
  sh.getRange(1, 3).setValue('Manual columns are preserved when the same position stays open.').setFontStyle('italic');
  for (var i = 0; i < n; i++) {
    var kind = OPEN_SCHEMA[i][2];
    var color = kind === 'manual' ? '#0e9f6e' : kind === 'id' ? '#9aa0a6' : '#4f6cb0';
    sh.getRange(2, i + 1).setValue(OPEN_SCHEMA[i][0])
      .setBackground(color).setFontColor('#ffffff').setFontWeight('bold')
      .setWrap(true).setHorizontalAlignment('center').setVerticalAlignment('middle');
  }
  sh.setFrozenRows(2);
  sh.hideColumns(_oCol('position_id'));
  var rows = 1000 - OPEN_R1 + 1;
  ['position_size', 'notional', 'unrealized_pnl'].forEach(function (key) {
    sh.getRange(OPEN_R1, _oCol(key), rows, 1).setNumberFormat('$#,##0.00');
  });
  ['entry_price', 'mark_price', 'liq_price', 'take_profit', 'stop_loss'].forEach(function (key) {
    sh.getRange(OPEN_R1, _oCol(key), rows, 1).setNumberFormat('$#,##0.00####');
  });
  sh.getRange(OPEN_R1, _oCol('unrealized_pct'), rows, 1).setNumberFormat('0.00%');
  sh.getRange(OPEN_R1, _oCol('opened_at'), rows, 1).setNumberFormat('yyyy-mm-dd hh:mm');
  sh.getRange(OPEN_R1, _oCol('last_synced'), rows, 1).setNumberFormat('yyyy-mm-dd hh:mm');
  for (var c = 1; c <= n; c++) sh.autoResizeColumn(c);
}

function _existingOpenManual(sh) {
  var lastRow = sh.getLastRow();
  var map = {};
  if (lastRow < OPEN_R1) return map;
  var idCol = _oCol('position_id');
  var vals = sh.getRange(OPEN_R1, 1, lastRow - OPEN_R1 + 1, sh.getLastColumn()).getValues();
  var manualKeys = [];
  for (var i = 0; i < OPEN_SCHEMA.length; i++) if (OPEN_SCHEMA[i][2] === 'manual') manualKeys.push(OPEN_SCHEMA[i][1]);
  vals.forEach(function (row) {
    var id = String(row[idCol - 1] || '');
    if (!id) return;
    map[id] = {};
    manualKeys.forEach(function (key) { map[id][key] = row[_oCol(key) - 1]; });
  });
  return map;
}

function _syncOpenPositions(rows) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(OPEN_SHEET);
  if (!sh) { sh = ss.insertSheet(OPEN_SHEET); _buildOpenPositions(sh); }
  var manualById = _existingOpenManual(sh);
  var lastRow = sh.getLastRow();
  if (lastRow >= OPEN_R1) sh.getRange(OPEN_R1, 1, lastRow - OPEN_R1 + 1, sh.getLastColumn()).clearContent();
  var now = new Date();
  var out = [];
  rows.forEach(function (body) {
    var id = String(body.position_id || '');
    var manual = manualById[id] || {};
    out.push(OPEN_SCHEMA.map(function (s) {
      if (s[2] === 'manual') return manual[s[1]] || body[s[1]] || '';
      if (s[1] === 'opened_at') return body.opened_at ? new Date(body.opened_at) : '';
      if (s[1] === 'last_synced') return now;
      var v = body[s[1]];
      return (v === undefined || v === null) ? '' : v;
    }));
  });
  if (out.length) sh.getRange(OPEN_R1, 1, out.length, OPEN_SCHEMA.length).setValues(out);
  return _json({ ok: true, open_positions: out.length });
}
