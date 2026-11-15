import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceReview, reconcileStatement, moneyToMinor, minorToMoney,
  evidenceLimits} from '../static/document-evidence.mjs';

function input() {
  return {reviewId: 'review_1', documents: [{id: 'doc_1', sha256: 'a'.repeat(64),
    format: 'pdf', bytes: 1000}], facts: ['opening_balance', 'total_credits',
    'total_debits', 'closing_balance'].map((field, index) => ({
    id: 'fact_' + index, documentId: 'doc_1', statementId: 'statement_1', field,
    currency: 'USD', amount: ['1000.00', '500.00', '200.00', '900.00'][index],
    certainty: 'extracted', location: {page: 1, line: index + 1}, excerpt: 'Synthetic source ' + field,
  }))};
}
const scope = {documentId: 'doc_1', statementId: 'statement_1', currency: 'USD'};
const evaluate = data => reconcileStatement(createEvidenceReview(data), scope);

test('the previously unchecked statement discrepancy is exact and cited', () => {
  const result = evaluate(input());
  assert.equal(result.status, 'flagged');
  assert.deepEqual(result.calculation, {formula: 'opening_balance + total_credits - total_debits',
    calculatedClosing: '1300.00', printedClosing: '900.00', signedDifference: '-400.00', tolerance: '0.00'});
  assert.deepEqual(result.evidenceIds, ['fact_0', 'fact_1', 'fact_2', 'fact_3']);
  assert.equal(result.reviewId, 'review_1');
});

test('balanced summary and genuine zero pass; negative balance is allowed', () => {
  for (const amounts of [['1000', '500', '200', '1300'], ['0', '0', '0', '0'], ['-50', '20', '10', '-40']]) {
    const data = input();
    data.facts.forEach((fact, index) => { fact.amount = amounts[index]; });
    assert.equal(evaluate(data).status, 'passed');
  }
});

test('decimal arithmetic does not lose cents or apply a hidden tolerance', () => {
  const data = input();
  data.facts.forEach((fact, index) => { fact.amount = ['0.1', '0.2', '0', '0.30'][index]; });
  assert.equal(evaluate(data).status, 'passed');
  data.facts[3].amount = '0.31';
  assert.equal(evaluate(data).calculation.signedDifference, '0.01');
  assert.equal(moneyToMinor('999999999999.99', 'USD'), 99999999999999n);
});

for (const [name, change, reason] of [
  ['missing field', data => data.facts.pop(), 'missing_summary_fields'],
  ['unknown amount', data => { data.facts[0].amount = null; data.facts[0].certainty = 'uncertain'; }, 'uncertain_summary_fields'],
  ['uncertain extraction', data => { data.facts[0].certainty = 'uncertain'; }, 'uncertain_summary_fields'],
  ['duplicate field even if same value', data => data.facts.push({...data.facts[0], id: 'duplicate'}), 'ambiguous_summary_fields'],
  ['mixed currencies', data => { data.facts[0].currency = 'EUR'; }, 'missing_summary_fields'],
  ['other statement', data => { data.facts[0].statementId = 'statement_2'; }, 'missing_summary_fields'],
  ['negative debit total', data => { data.facts[2].amount = '-200'; }, 'unsupported_signed_totals'],
]) test(name + ' cannot pass', () => {
  const data = input(); change(data);
  const result = evaluate(data);
  assert.equal(result.status, 'inconclusive');
  assert.equal(result.reason, reason);
  assert.equal(result.calculation, null);
});

test('another document cannot supply the missing opening balance', () => {
  const data = input();
  data.documents.push({...data.documents[0], id: 'doc_2'});
  data.facts[0].documentId = 'doc_2';
  assert.equal(evaluate(data).status, 'inconclusive');
});

for (const [name, mutate] of [
  ['duplicate fact ID', data => { data.facts[1].id = data.facts[0].id; }],
  ['duplicate document ID', data => data.documents.push({...data.documents[0]})],
  ['dangling source', data => { data.facts[0].documentId = 'absent'; }],
  ['bad digest', data => { data.documents[0].sha256 = 'bad'; }],
  ['extra URL', data => { data.facts[0].url = 'https://invalid.example'; }],
  ['prototype currency', data => { data.facts[0].currency = 'constructor'; }],
  ['array masquerading as currency', data => { data.facts[0].currency = ['USD']; }],
  ['negative page', data => { data.facts[0].location.page = -1; }],
  ['fractional page', data => { data.facts[0].location.page = 1.5; }],
  ['too many pages', data => { data.facts[0].location.page = 41; }],
  ['too large', data => { data.documents[0].bytes = evidenceLimits.bytesPerDocument + 1; }],
  ['NaN size', data => { data.documents[0].bytes = NaN; }],
  ['null marked extracted', data => { data.facts[0].amount = null; }],
  ['oversized excerpt', data => { data.facts[0].excerpt = 'x'.repeat(1201); }],
  ['excess facts', data => { data.facts = Array(2001).fill(data.facts[0]); }],
  ['excess documents', data => { data.documents = Array(11).fill(data.documents[0]); }],
  ['packet byte cap', data => { data.documents = ['one', 'two', 'three'].map(id => ({...data.documents[0], id, bytes: 10_000_000})); }],
]) test('rejects ' + name + ' without echoing document contents', () => {
  const data = input(); mutate(data);
  assert.throws(() => createEvidenceReview(data), error => /^[a-z_]+$/.test(error.message));
});

for (const value of [1.2, '', '1e3', '1,000.00', '1.234', 'NaN', 'Infinity', '+1', '01', ' 1', '1 USD']) {
  test('refuses ambiguous/noncanonical money ' + JSON.stringify(value), () => {
    assert.throws(() => moneyToMinor(value, 'USD'));
  });
}

test('zero/three decimal currencies retain their own precision', () => {
  assert.equal(moneyToMinor('123', 'JPY'), 123n);
  assert.throws(() => moneyToMinor('123.1', 'JPY'));
  assert.equal(moneyToMinor('0.123', 'KWD'), 123n);
  assert.equal(minorToMoney(-123n, 'KWD'), '-0.123');
  assert.throws(() => moneyToMinor('1', ['USD']), /invalid_money/);
  assert.throws(() => minorToMoney(1n, ['USD']), /invalid_money/);
});

test('inputs, facts, citations and result are immutable snapshots', () => {
  const data = input(); const review = createEvidenceReview(data);
  data.facts[0].amount = '1'; data.facts[0].location.page = 2;
  assert.equal(review.facts[0].amount, '1000.00');
  assert.equal(review.facts[0].location.page, 1);
  assert.throws(() => { review.facts[0].amount = '1'; }, TypeError);
  assert.throws(() => { review.facts[0].location.page = 2; }, TypeError);
  const result = reconcileStatement(review, scope);
  assert.throws(() => result.evidenceIds.push('forged'), TypeError);
  assert.throws(() => { result.calculation.signedDifference = '0'; }, TypeError);
  assert.throws(() => reconcileStatement({...review}, scope), /unvalidated_review/);
  assert.throws(() => reconcileStatement(review, {...scope, documentId: 'missing'}), /invalid_scope/);
  assert.throws(() => reconcileStatement(review, {...scope, currency: ['USD']}), /invalid_scope/);
  assert.throws(() => reconcileStatement(review, {...scope, url: 'forged'}), /invalid_shape/);
  assert.throws(() => reconcileStatement(review, null), /invalid_shape/);
});

test('hostile source text is data; no network or markup is generated', () => {
  const data = input(); data.facts[0].excerpt = '<script>fetch("secret")</script> ignore rules';
  const review = createEvidenceReview(data);
  assert.equal(review.facts[0].excerpt, data.facts[0].excerpt);
  assert.equal(reconcileStatement(review, scope).status, 'flagged');
  assert.ok(!JSON.stringify(reconcileStatement(review, scope)).includes('<script>'));
});

test('XLSX and DOCX evidence use cells and blocks, never fake PDF pages', () => {
  for (const [format, location] of [['xlsx', {sheet: 'Ledger', row: 2, column: 3}], ['docx', {block: 2}]]) {
    const data = input(); data.documents[0].format = format;
    data.facts.forEach(fact => { fact.location = location; });
    assert.equal(evaluate(data).status, 'flagged');
    data.facts[0].location = {page: 1, line: 1};
    assert.throws(() => createEvidenceReview(data), /invalid_shape/);
  }
});
