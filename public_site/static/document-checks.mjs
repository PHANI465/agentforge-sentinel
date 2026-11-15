import {createEvidenceReview, moneyToMinor, minorToMoney, reconcileStatement} from './document-evidence.mjs';
import {explain} from './pdf-review.mjs';
import {treasurySummary} from './financial-metrics.mjs';
import {comparePacket, readPacketRecord} from './packet-checks.mjs';
import {check, decimal, normalize, validDate} from './observation-values.mjs';

const summaryFields = [
  [/^(?:opening|beginning|previous) balance$/i, 'opening_balance'],
  [/^(?:total )?(?:credits|deposits|money in)$/i, 'total_credits'],
  [/^(?:total )?(?:debits|withdrawals|money out)$/i, 'total_debits'],
  [/^(?:closing|ending|new) balance$/i, 'closing_balance'],
];
function columnIndex(letters) {
  return [...letters].reduce((result, letter) => result * 26 + letter.charCodeAt(0) - 64, 0);
}

export function sourceLines(document) {
  const {descriptor, workbook, word, pages} = document;
  const row = (text, location) => ({text, location, documentId: descriptor.id});
  if (workbook) return workbook.sheets.map(sheet => ({
    name: sheet.name,
    lines: sheet.rows.flatMap(({number, cells}) => {
      if (!cells.size || !/^[1-9]\d{0,3}$|^10000$/.test(number ?? '')) return [];
      const items = [...cells].sort(([left], [right]) => columnIndex(left) - columnIndex(right));
      const column = columnIndex(items[1]?.[0] ?? items[0][0]);
      if (column > 16384) return [];
      const values = items.map(([, value]) => normalize(value));
      // A two-cell label/value row is represented as a label and an observed value.
      const text = values.join(values.length === 2 && !values[0].endsWith(':') ? ': ' : ' ');
      return [row(text, {sheet: sheet.name, row: Number(number), column})];
    }),
  }));
  return [{lines: pages.flatMap(page => page.lines.map((line, index) =>
    row(line, word ? word.locations[index] : {page: page.number, line: index + 1}))), name: null}];
}

function scopeLines(lines) {
  const scopes = [];
  let scope = {lines: []};
  scopes.push(scope);
  for (const row of lines) {
    const account = row.text.match(/^Account(?: ID| number)?\s*:\s*(.{1,80})$/i)?.[1];
    const period = row.text.match(/^(?:Statement )?Period\s*:\s*(.{1,80})$/i)?.[1];
    // An explicit repeated account/period starts a new scope once amounts have appeared.
    // Repeated page headers with the same values continue the current summary.
    const conflict = (account && scope.account && account !== scope.account) ||
      (period && scope.period && period !== scope.period);
    if (conflict) {
      const earlier = scope;
      scope = {lines: [], account: period ? earlier.account : undefined};
      scopes.push(scope);
    }
    if (account) scope.account = account;
    if (period) scope.period = period;
    scope.lines.push(row);
  }
  return scopes;
}

function statementSummary(document, group, reviewId) {
  const scopes = scopeLines(group.lines).filter(scope => scope.lines.some(row =>
    summaryFields.some(([label]) => label.test(row.text.split(/:|\s(?=[A-Z]{3}\s[-($€£]?\d)/u)[0]))));
  return scopes.map(scope => {
    const candidates = scope.lines.flatMap(row => {
      const match = row.text.match(/^(.+?)(?:\s*:\s*|\s+(?=[A-Z]{3}\s))(.+)$/);
      const field = match && summaryFields.find(([label]) => label.test(match[1]))?.[1];
      return field ? [{row, field, value: match[2]}] : [];
    });
    const explicit = new Set(scope.lines.flatMap(({text}) => {
      const code = text.match(/^Currency\s*:\s*([A-Z]{3})$/i)?.[1]?.toUpperCase();
      return code ? [code] : [];
    }));
    const allCodes = new Set(explicit);
    for (const {value} of candidates) {
      for (const code of value.match(/\b[A-Z]{3}\b/g) ?? []) allCodes.add(code);
    }
    const currency = allCodes.size === 1 ? [...allCodes][0] : undefined;
    const comma = scope.lines.some(({text}) => /^Number format\s*:\s*decimal comma$/i.test(text));
    const groupLabel = group.name ? ' in ' + group.name : '';
    const insufficient = detail => [check('D02', 'inconclusive', detail + groupLabel,
      candidates.slice(0, 6).map(candidate => candidate.row))];
    if (candidates.length > 2000 || candidates.some(({row}) => row.location?.line > 10000)) {
      return insufficient('The printed summary exceeds the supported evidence limit.');
    }
    if (!scope.account || !scope.period || !currency) {
      return insufficient('A clear account, statement period and single currency are required.');
    }
    try { moneyToMinor('0', currency); }
    catch { return insufficient('This currency is outside the supported precision table.'); }
    const facts = candidates.map(({row, field, value}, index) => {
      const amount = decimal(value, currency, comma);
      return {id: 'fact_' + index, documentId: document.descriptor.id, statementId: 'statement',
        field, currency, amount: amount === undefined ? null : minorToMoney(amount, currency),
        certainty: amount === undefined ? 'uncertain' : 'extracted', location: row.location,
        excerpt: row.text.slice(0, 1200)};
    });
    const review = createEvidenceReview({reviewId, documents: [document.descriptor], facts});
    const result = reconcileStatement(review, {documentId: document.descriptor.id, statementId: 'statement', currency});
    const selected = result.evidenceIds.slice(0, 8).map(id => candidates[Number(id.slice(5))].row);
    if (!result.calculation) return insufficient({
      ambiguous_summary_fields: 'Repeated fields make the printed summary ambiguous.',
      missing_summary_fields: 'All four printed summary amounts are required.',
      uncertain_summary_fields: 'A printed amount or its number format is unclear.',
      unsupported_signed_totals: 'Credit and debit totals must be unsigned magnitudes.',
    }[result.reason]);
    const {calculatedClosing, printedClosing, signedDifference} = result.calculation;
    const minor = field => moneyToMinor(facts.find(fact => fact.field === field).amount, currency);
    const values = [
      ['Opening balance', minorToMoney(minor('opening_balance'), currency)],
      ['Credits', minorToMoney(minor('total_credits'), currency)],
      ['Debits', minorToMoney(minor('total_debits'), currency)],
      ['Net movement', minorToMoney(minor('total_credits') - minor('total_debits'), currency)],
      ['Calculated closing balance', calculatedClosing], ['Printed closing balance', printedClosing],
      ['Printed minus calculated', signedDifference],
    ].map(([label, value]) => [label, value + ' ' + currency]);
    const status = result.status === 'passed' ? 'The printed summary balances.' :
      'The printed closing balance differs from opening balance plus credits minus debits.';
    return [check('D02', result.status, status + groupLabel, selected, values),
      statementRows(scope.lines, currency, comma, minor)];
  }).flat();
}

function statementRows(lines, currency, comma, minor) {
  const start = lines.findIndex(({text}) => /^Date Description Credit Debit Balance$/i.test(text));
  if (start < 0) return check('D03', 'not-run', 'A supported running-balance table was not found.');
  let balance = minor('opening_balance');
  let credits = 0n;
  let debits = 0n;
  let rows = 0;
  const mismatches = [];
  let previous = '';
  let reachedEnd = false;
  for (const row of lines.slice(start + 1)) {
    if (/^End transactions$/i.test(row.text)) { reachedEnd = true; break; }
    if (/^(?:Date Description Credit Debit Balance|Page \d+ of \d+)$/i.test(row.text)) continue;
    const fields = row.text.match(/^(\d{4}-\d{2}-\d{2})\s+.+?\s+([-\d,.()]+)\s+([-\d,.()]+)\s+([-\d,.()]+)$/);
    if (!fields || !validDate(fields[1]) || fields[1] < previous) {
      return check('D03', 'inconclusive', 'A transaction row or its order could not be read.', [row]);
    }
    previous = fields[1];
    const [credit, debit, printed] = fields.slice(2).map(value => decimal(value, currency, comma));
    if (credit === undefined || debit === undefined || printed === undefined || credit < 0n || debit < 0n) {
      return check('D03', 'inconclusive', 'A credit, debit or balance could not be read.', [row]);
    }
    rows++;
    credits += credit;
    debits += debit;
    balance += credit - debit;
    if (balance !== printed && mismatches.length < 5) mismatches.push(row);
  }
  if (!rows || !reachedEnd) return check('D03', 'inconclusive', 'The transaction section has no rows or no end marker.');
  const totalsMatch = credits === minor('total_credits') && debits === minor('total_debits') &&
    balance === minor('closing_balance');
  const status = mismatches.length || !totalsMatch ? 'flagged' : 'passed';
  return check('D03', status, status === 'passed' ? 'Visible rows match the printed balances and totals.' :
    'Visible rows differ from one or more printed balances or totals.', mismatches.length ? mismatches : [lines[start]],
  [['Rows checked', String(rows)], ['Credits from rows', minorToMoney(credits, currency) + ' ' + currency],
    ['Debits from rows', minorToMoney(debits, currency) + ' ' + currency]]);
}

export function analyzeDocuments(documents, options) {
  const output = documents.map(document => {
    const groups = sourceLines(document);
    const snapshots = groups.flatMap(group => statementSummary(document, group, options.reviewId));
    const report = document.pages ? explain(document.pages) : null;
    return {descriptor: document.descriptor, report,
      summary: document.descriptor.format === 'pdf' ? treasurySummary(document.pages) : undefined,
      checks: snapshots.length ? snapshots : report?.kind === 'Statement'
        ? [check('D02', 'inconclusive', 'Four readable printed amounts and an explicit account, period and currency are required.')]
        : [],
      packet: readPacketRecord(document.descriptor, groups),
    };
  });
  return {documents: output, comparisons: comparePacket(output.map(item => item.packet), options)};
}
