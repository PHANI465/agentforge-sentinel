import assert from 'node:assert/strict';
import test from 'node:test';
import {analyzeDocuments} from '../static/document-checks.mjs';

const options = {reviewId: 'review_test'};
const doc = (index, lines) => ({descriptor: {id: 'doc_' + index, sha256: String(index).repeat(64),
  format: 'pdf', bytes: 500}, pages: [{number: 1, lines}]});
const record = (type, id, ...lines) => ['Record type: ' + type, 'Record ID: ' + id, 'Vendor ID: VENDOR',
  'Currency: USD', ...lines];
const invoice = (id, ...extra) => record('Invoice', id, 'Total due: 10.00', ...extra);
const statement = (account, dates, ...summary) => ['Statement', 'Account: ' + account,
  'Period: ' + dates, 'Currency: USD', ...summary];

test('statement periods and account boundaries cannot complete one another', () => {
  const first = statement('A', '2026-07', 'Opening balance: 100.00', 'Total credits: 20.00');
  const second = statement('B', '2026-08', 'Total debits: 10.00', 'Closing balance: 110.00');
  const result = analyzeDocuments([doc(1, [...first, ...second])], options);
  assert.deepEqual(result.documents[0].checks.map(row => [row.id, row.status]),
    [['D02','inconclusive'], ['D02','inconclusive']]);
});

test('a dollar symbol alone does not determine which currency applies', () => {
  const result = analyzeDocuments([doc(1, ['Statement', 'Account: A', 'Period: 2026-09',
    'Opening balance: $100', 'Total credits: $20.00', 'Total debits: $10.00',
    'Closing balance: $110.00'])], options);
  assert.equal(result.documents[0].checks[0].status, 'inconclusive');
});

test('an unallocated delivery cannot justify two distinct invoices', () => {
  const lines = ['Purchase order: PO1', 'Item A: 2 ea 5.00'];
  const delivery = record('Delivery receipt', 'DN3', 'Purchase order: PO1', 'Item A: 2 ea');
  const result = analyzeDocuments([doc(1, invoice('INV1', ...lines)),
    doc(2, invoice('INV2', ...lines)), doc(3, delivery)], options);
  assert.deepEqual(result.comparisons.filter(row => row.id === 'D07').map(row => row.status),
    ['inconclusive', 'inconclusive']);
});

test('a repeated payment ID stops reconciliation instead of double counting', () => {
  const payment = record('Payment record', 'PAY', 'Invoice reference: INV1', 'Amount: 10.00');
  const result = analyzeDocuments([doc(1, invoice('INV1')), doc(2, payment), doc(3, payment)], options);
  assert.equal(result.comparisons.find(row => row.id === 'D04').status, 'flagged');
  assert.equal(result.comparisons.find(row => row.id === 'D08').status, 'inconclusive');
});

test('a payment linked in a different currency stays unmatched', () => {
  const payment = record('Payment record', 'PAY', 'Invoice reference: INV1', 'Amount: 10.00');
  payment[3] = 'Currency: EUR';
  const result = analyzeDocuments([doc(1, invoice('INV1')), doc(2, payment)], options);
  assert.deepEqual(result.comparisons.filter(row => row.id === 'D08').map(row => row.status),
    ['not-run', 'inconclusive']);
});

test('a partial payment is identified as an unresolved balance', () => {
  const payment = record('Payment record', 'PAY', 'Invoice reference: INV1', 'Amount: 4.00');
  const result = analyzeDocuments([doc(1, invoice('INV1')), doc(2, payment)], options);
  const check = result.comparisons.find(row => row.id === 'D08');
  assert.equal(check.status, 'inconclusive');
  assert.deepEqual(check.values.find(([label]) => label === 'Remaining balance'), ['Remaining balance', '6.00 USD']);
});
