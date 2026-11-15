import assert from 'node:assert/strict';
import {test} from 'node:test';
import {invoiceEvidence} from '../static/invoice-review.mjs';
import {maximumBytes} from '../static/pdf-review.mjs';

const inspect = (...lines) => invoiceEvidence([{number: 1, lines}]);
const codeList = findings => findings.map(finding => finding.code);

test('10 MB is a decimal upload cap', () => assert.equal(maximumBytes, 10_000_000));

test('invoice arithmetic uses separate printed row, subtotal and total comparisons', () => {
  const results = inspect('Service Hours Rate Amount', 'A 1.25 $120.00 $160.00', 'B 2 $40.00 $80.00',
    'Reported Subtotal: $250.00', 'Tax (10%): $25.00', 'Reported Total Due: $280.00');
  assert.deepEqual(codeList(results), ['line-math','subtotal-math','total-math']);
  assert.match(results[0].description, /\$150\.00/);
  assert.match(results[1].description, /\$240\.00/);
  assert.match(results[2].description, /\$275\.00/);
});

test('rounded fractional price and consistent totals do not produce flags', () => {
  assert.deepEqual(inspect('Item Qty Unit Price Total', 'Charge 0.25 $0.10 $0.03',
    'Subtotal: $0.03', 'Tax: $0.00', 'Total Due: $0.03'), []);
});

test('unreadable rows or unlike currency markers prevent subtotal claims', () => {
  assert.deepEqual(inspect('Item Qty Unit Price Total', 'A 2 USD 60.00 USD 120.00',
    'Unreadable line', 'Subtotal: $200.00'), []);
});

test('a stated threshold and cited second invoice are required for a combined finding', () => {
  assert.deepEqual(inspect('Invoice A', 'Remittance Notes: Please remit $999.00.'), []);
  const find = inspect('Invoice A', 'Remittance Notes: Please remit $999.00; related invoice B for $500.00.',
    'A $1,000.00 dual-approval threshold applies.');
  assert.deepEqual(codeList(find), ['approval-limit']);
  assert.match(find[0].description, /\$1,499\.00/);
  const splitUnit = inspect('Invoice A', 'Remittance Notes: Please remit $999.00; related invoice B for EUR 500.00.',
    'A $1,000.00 dual-approval threshold applies.');
  assert.doesNotMatch(splitUnit[0].description, /combined amount/);
});

test('evaluation annotations cannot produce findings', () => {
  assert.deepEqual(inspect('Invoice A', 'Synthetic Benchmark Artifact',
    'Updated banking instructions', 'Routing Number: 000000000'), []);
});

test('bank instructions are signals and account values are excluded from findings', () => {
  const findings = inspect('Vendor: Example Service Ltd', 'Beneficiary: Example Service Ltd',
    'New banking instructions', 'Routing Number: 000000000 | Account Number: 948374987438');
  assert.deepEqual(codeList(findings), ['payment-change','routing-format']);
  assert.doesNotMatch(JSON.stringify(findings), /000000000|948374987438/);
  assert.deepEqual(inspect('Routing Number: 021000021'), []);
});
