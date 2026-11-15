import {minorToMoney} from './document-evidence.mjs';
import {check, decimal, validDate} from './observation-values.mjs';

// Version 1 uses explicit, human-readable record roles and references. Unrecognized,
// repeated or contradictory fields are excluded from automated matching.
const types = new Map([
  ['invoice', 'invoice'], ['purchase order', 'order'], ['delivery receipt', 'delivery'],
  ['payment record', 'payment'], ['credit note', 'credit'], ['payment reversal', 'reversal'],
  ['vendor baseline', 'baseline'],
]);
const knownFields = new Set(['record type', 'record id', 'vendor id', 'currency', 'invoice reference',
  'purchase order', 'invoice date', 'group reference', 'payment destination', 'total due',
  'amount', 'reverses payment']);
const identifier = text => typeof text === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,47}$/.test(text);

export function readPacketRecord(document, groups) {
  const groupsWithRole = groups.filter(group => group.lines.some(row => /^Record type\s*:/i.test(row.text)));
  if (!groupsWithRole.length) return {document, status: 'unrecognized'};
  const invalid = {document, status: 'incomplete'};
  if (groupsWithRole.length !== 1) return invalid;
  const fields = new Map();
  const items = new Map();
  const lines = groupsWithRole[0].lines;
  for (const row of lines) {
    const match = row.text.match(/^([^:]+)\s*:\s*(.+)$/);
    if (!match) continue;
    const label = match[1].trim().toLowerCase();
    const item = /^item (\S+)$/.exec(match[1].trim().replace(/^item /i, 'item '));
    if (item) {
      const [units, unit, price, ...extra] = match[2].split(/\s+/u);
      if (!identifier(item[1]) || items.size >= 100 || items.has(item[1]) || !/^[1-9]\d{0,7}$/.test(units) ||
          !identifier(unit) || extra.length) return invalid;
      items.set(item[1], {quantity: BigInt(units), unit, price, row});
    }
    if (!knownFields.has(label)) continue;
    if (fields.has(label)) return invalid;
    fields.set(label, {value: match[2], row});
  }
  const field = label => fields.get(label)?.value;
  const type = types.get(field('record type')?.toLowerCase());
  const id = field('record id');
  const vendor = field('vendor id');
  const currency = field('currency');
  const monetary = label => currency && field(label) !== undefined ? decimal(field(label), currency) : undefined;
  const total = monetary(type === 'invoice' ? 'total due' : 'amount');
  const invoice = field('invoice reference');
  const order = field('purchase order');
  const destination = field('payment destination');
  const date = field('invoice date');
  const group = field('group reference');
  const reverses = field('reverses payment');
  if (!type || !identifier(id) || !identifier(vendor) || !currency || decimal('0', currency) === undefined ||
      (invoice !== undefined && !identifier(invoice)) || (order !== undefined && !identifier(order)) ||
      (destination !== undefined && !identifier(destination)) ||
      (group !== undefined && !identifier(group)) || (date !== undefined && !validDate(date)) ||
      (type === 'invoice' && (total === undefined || total < 0n)) ||
      (['payment', 'credit', 'reversal'].includes(type) &&
        (!identifier(invoice) || total === undefined || total <= 0n)) ||
      (type === 'reversal' && !identifier(reverses))) return invalid;
  for (const item of items.values()) {
    item.rate = item.price === undefined ? undefined : decimal(item.price, currency);
    if (item.price !== undefined && (item.rate === undefined || item.rate < 0n)) return invalid;
  }
  return {version: 1, document, status: 'recognized', type, id, vendor, currency, total,
    invoice, order, destination, date, group, reverses, items, fields};
}

const row = (record, field = 'record id') => record.fields.get(field)?.row ?? record.fields.get('record id').row;
const money = (amount, record) => minorToMoney(amount, record.currency) + ' ' + record.currency;
const matching = (a, b) => a.vendor === b.vendor && a.currency === b.currency;
const invoiceMatch = (invoice, record) => matching(invoice, record) && invoice.id === record.invoice;
const orderMatch = (invoice, record) => matching(invoice, record) && Boolean(invoice.order) && invoice.order === record.id;
const groupBy = (list, key) => {
  const groups = new Map();
  for (const item of list) {
    const id = key(item);
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(item);
  }
  return [...groups.values()];
};
const recordKey = record => JSON.stringify([record.type, record.vendor, record.currency, record.id]);

function compareLines(invoice, records, conflicts, output) {
  const orders = records.filter(record => record.type === 'order' && orderMatch(invoice, record));
  const deliveries = records.filter(record => record.type === 'delivery' &&
    matching(invoice, record) && invoice.order && invoice.order === record.order);
  const sources = [row(invoice, 'purchase order')];
  const put = (id, state, detail) => output.push(check(id, state, detail, sources));
  const deliveryDisputed = conflicts.some(record => record.type === 'delivery' && matching(invoice, record) &&
    invoice.order && invoice.order === record.order);
  if (!invoice.items.size || !invoice.order) {
    put('D06', 'not-run', 'Invoice ' + invoice.id + ' needs a purchase order reference and item rows.');
    put('D07', 'not-run', 'A referenced purchase order and invoice item rows are needed to compare deliveries.');
    return;
  }
  if (orders.length !== 1) {
    put('D06', 'inconclusive', 'Exactly one matching purchase order is required for invoice ' + invoice.id + '.');
  }
  if (deliveryDisputed) put('D07', 'inconclusive', 'Resolve repeated delivery references before comparing quantities.');
  else if (!deliveries.length) put('D07', 'not-run', 'No matching delivery record was supplied for invoice ' + invoice.id + '.');
  for (const [itemId, item] of invoice.items) {
    const shared = records.some(other => other !== invoice && other.type === 'invoice' &&
      matching(other, invoice) && other.order === invoice.order && other.items.has(itemId));
    const order = orders[0]?.items.get(itemId);
    if (orders.length === 1) {
      if (!order || order.unit !== item.unit || order.rate === undefined || item.rate === undefined) {
        output.push(check('D06', 'inconclusive', 'Comparable units and prices are needed for item ' + itemId + '.', [item.row, row(orders[0])]));
      } else {
        const different = order.rate !== item.rate || order.quantity < item.quantity;
        output.push(check('D06', different ? 'flagged' : shared ? 'inconclusive' : 'passed',
          'Invoice ' + invoice.id + ' compared with purchase order ' + orders[0].id + ', item ' + itemId + '.',
          [item.row, order.row], [['Invoiced unit price', money(item.rate, invoice)],
            ['Ordered unit price', money(order.rate, invoice)],
            ['Unit price difference', money(item.rate - order.rate, invoice)],
            ['Quantity invoiced', String(item.quantity)], ['Quantity ordered', String(order.quantity)]]));
      }
    }
    if (deliveries.length && !deliveryDisputed) {
      const delivered = deliveries.flatMap(delivery => delivery.items.has(itemId) ? [delivery.items.get(itemId)] : []);
      if (shared) {
        output.push(check('D07', 'inconclusive', 'More than one invoice references this item. Allocate the delivered units before checking each invoice.', [item.row]));
      } else if (!delivered.length || delivered.some(line => line.unit !== item.unit)) {
        output.push(check('D07', 'inconclusive', 'Comparable delivery quantities are needed for item ' + itemId + '.', [item.row]));
      } else {
        const total = delivered.reduce((sum, line) => sum + line.quantity, 0n);
        output.push(check('D07', total < item.quantity ? 'flagged' : 'passed',
          'Supplied deliveries compared with invoice ' + invoice.id + ', item ' + itemId + '.',
          [item.row, ...delivered.map(line => line.row)], [['Quantity invoiced', String(item.quantity)],
            ['Quantity delivered', String(total)], ['Invoiced minus delivered', String(item.quantity - total)]]));
      }
    }
  }
}

function comparePayments(invoice, records) {
  const linked = records.filter(record => ['payment', 'credit', 'reversal'].includes(record.type) && invoiceMatch(invoice, record));
  if (!linked.length) return check('D08', 'not-run', 'No same-currency payment or credit was linked to invoice ' + invoice.id + '.');
  const evidence = [row(invoice, 'total due'), ...linked.map(record => row(record, 'amount'))];
  const payments = new Map();
  let paid = 0n;
  let credits = 0n;
  for (const record of linked) {
    if (record.type === 'payment') {
      payments.set(record.id, record.total);
      paid += record.total;
    } else if (record.type === 'credit') credits += record.total;
  }
  for (const reversal of linked.filter(record => record.type === 'reversal')) {
    const available = payments.get(reversal.reverses);
    if (available === undefined || reversal.total > available) {
      return check('D08', 'inconclusive', 'A reversal has no matching payment or exceeds it.', evidence);
    }
    payments.set(reversal.reverses, available - reversal.total);
    paid -= reversal.total;
  }
  const balance = invoice.total - credits - paid;
  return check('D08', balance < 0n ? 'flagged' : balance === 0n ? 'passed' : 'inconclusive',
    balance < 0n ? 'Linked payments and credits exceed the invoice amount.' :
      balance > 0n ? 'The supplied records show a remaining balance. Check for missing or pending payments.' :
        'The supplied payments and credits reconcile to the invoice amount.', evidence,
    [['Invoice amount', money(invoice.total, invoice)], ['Payments after reversals', money(paid, invoice)],
      ['Credits', money(credits, invoice)], ['Remaining balance', money(balance, invoice)]]);
}

function compareDestination(invoice, records, trusted) {
  const baselines = records.filter(record => record.type === 'baseline' && matching(record, invoice) &&
    record.document.id === trusted);
  if (baselines.length !== 1 || !invoice.destination || !baselines[0].destination) {
    return check('D09', 'not-run', 'Choose one matching vendor baseline as trusted and supply both payment destination identifiers.');
  }
  const baseline = baselines[0];
  const changed = invoice.destination !== baseline.destination;
  // Raw destination identifiers stay out of the default UI, including the source snippets.
  const masked = record => ({...row(record, 'payment destination'), text: 'Payment destination identifier (hidden)'});
  return check('D09', changed ? 'flagged' : 'passed', changed ?
    'The invoice destination differs from the selected baseline. Verify the change with a trusted vendor contact.' :
    'The supplied destination identifiers match.', [masked(invoice), masked(baseline)]);
}

function checkPolicy(invoices, policy) {
  if (!policy) return [check('D10', 'not-run', 'Enter your approval policy to check related invoices.')];
  const {currency, limit, days} = policy;
  const amount = typeof limit === 'string' ? decimal(limit, currency) : undefined;
  if (amount === undefined || amount <= 0n || !Number.isInteger(days) || days < 1 || days > 90) {
    return [check('D10', 'not-run', 'Use a supported currency, positive threshold and a 1–90 day window.')];
  }
  const threshold = minorToMoney(amount, currency);
  const results = [];
  const eligible = invoices.filter(record => record.currency === currency && record.group && record.date &&
    record.total > 0n && record.total < amount);
  for (const records of groupBy(eligible, record => JSON.stringify([record.vendor, record.group]))) {
    const sorted = [...records].sort((a, b) => a.date.localeCompare(b.date));
    for (let start = 0; start < sorted.length - 1; start++) {
      const window = sorted.slice(start).filter(record => Date.parse(record.date) - Date.parse(sorted[start].date) <= days * 86400000);
      const total = window.reduce((sum, record) => sum + record.total, 0n);
      if (window.length >= 2 && total >= amount) {
        results.push(check('D10', 'flagged', 'Related invoices individually below the policy threshold reach it together.',
          window.flatMap(record => [row(record, 'total due'), row(record, 'invoice date')]),
          [['Reference group', sorted[start].group], ['Invoices in window', String(window.length)],
            ['Combined amount', money(total, sorted[start])], ['User-entered threshold', threshold + ' ' + currency],
            ['Window in days', String(days)]]));
        break;
      }
    }
  }
  if (results.length) return results;
  const scoped = invoices.filter(record => record.currency === currency && record.group && record.date);
  return [check('D10', scoped.length >= 2 ? 'passed' : 'inconclusive',
    scoped.length >= 2 ? 'No supplied related group crosses the entered threshold under the below-limit rule.' :
      'At least two invoices with currency, group and date are needed.')];
}

export function comparePacket(input, {trusted, policy} = {}) {
  // Same file bytes are one piece of evidence, even when the filename is different.
  const reduced = new Map();
  for (const record of input) {
    if (!reduced.has(record.document.sha256) || record.document.id === trusted) {
      reduced.set(record.document.sha256, record);
    }
  }
  const recognized = [...reduced.values()].filter(record => record.status === 'recognized');
  if (input.length < 2) return [];
  const output = [];
  if (reduced.size < input.length) {
    output.push(check('D04', 'not-applicable',
      (input.length - reduced.size) + ' repeated file copies were excluded by byte identity.'));
  }
  const disputed = new Set();
  for (const group of groupBy(recognized, recordKey)) {
    if (group.length < 2) continue;
    disputed.add(recordKey(group[0]));
    const supported = ['invoice', 'payment'].includes(group[0].type);
    output.push(check(supported ? 'D04' : 'D12', 'flagged',
      'Distinct files repeat ' + group[0].type + ' reference ' + group[0].id +
        '. These records are held out of comparisons until the reference is resolved.',
      group.map(record => row(record))));
  }
  const records = recognized.filter(record => !disputed.has(recordKey(record)));
  const conflicts = recognized.filter(record => disputed.has(recordKey(record)));
  const invoices = records.filter(record => record.type === 'invoice');
  if (!output.some(result => result.id === 'D04' && result.status === 'flagged')) {
    const enough = recognized.filter(record => ['invoice','payment'].includes(record.type)).length >= 2;
    output.push(check('D04', enough ? 'passed' : 'not-run', enough ?
      'No repeated invoice or payment reference among the recognized, distinct records.' :
      'Supply at least two distinct invoice or payment records to compare references.'));
  }
  for (const invoice of invoices) {
    compareLines(invoice, records, conflicts, output);
    const duplicateLink = recognized.some(record => ['payment','credit','reversal'].includes(record.type) &&
      invoiceMatch(invoice, record) && disputed.has(recordKey(record)));
    output.push(duplicateLink ? check('D08', 'inconclusive', 'Resolve repeated settlement records before comparing payments.') :
      comparePayments(invoice, records));
    output.push(compareDestination(invoice, records, trusted));
  }
  const unmatched = records.filter(record => ['payment', 'credit', 'reversal'].includes(record.type) &&
    !invoices.some(invoice => invoiceMatch(invoice, record)));
  if (unmatched.length) output.push(check('D08', 'inconclusive',
    'Some settlement references have no matching invoice and currency in the supplied files.', unmatched.map(record => row(record, 'invoice reference')),
    [['Unmatched records', String(unmatched.length)]]));
  output.push(...checkPolicy(invoices, policy));
  return output;
}
