// Local, dependency-free evidence boundary. No file parsing, storage or network access.
// Provenance binds a calculation to an adapter's observations; it does not authenticate
// an issuer or prove that the adapter extracted the document correctly.
export const evidenceLimits = Object.freeze({documents: 10, bytesPerDocument: 10_000_000,
  totalBytes: 20_000_000, facts: 2000, excerptCharacters: 1200});
const currencies = Object.freeze({USD: 2, EUR: 2, GBP: 2, CAD: 2, AUD: 2,
  NZD: 2, CHF: 2, INR: 2, JPY: 0, KWD: 3});
const fields = ['opening_balance', 'total_credits', 'total_debits', 'closing_balance'];
const admitted = new WeakSet();
const idPattern = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const fail = code => { throw new Error(code); };
const id = value => typeof value === 'string' && idPattern.test(value);
const validCurrency = value => typeof value === 'string' && Object.hasOwn(currencies, value);
const integer = (value, max) => Number.isSafeInteger(value) && value > 0 && value <= max;

function shape(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      ![Object.prototype, null].includes(Object.getPrototypeOf(value)) ||
      Object.keys(value).length !== keys.length ||
      !keys.every(key => Object.hasOwn(value, key))) fail('invalid_shape');
}

function text(value, max) {
  return typeof value === 'string' && value.length > 0 && value.length <= max &&
    !/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/u.test(value);
}

export function moneyToMinor(amount, currency) {
  if (!validCurrency(currency) || typeof amount !== 'string' ||
      !/^-?(?:0|[1-9]\d{0,11})(?:\.\d{1,3})?$/.test(amount)) fail('invalid_money');
  const negative = amount.startsWith('-');
  const [whole, fraction = ''] = (negative ? amount.slice(1) : amount).split('.');
  const digits = currencies[currency];
  if (fraction.length > digits) fail('invalid_money_precision');
  const magnitude = BigInt(whole + fraction.padEnd(digits, '0'));
  return negative ? -magnitude : magnitude;
}

export function minorToMoney(minor, currency) {
  if (typeof minor !== 'bigint' || !validCurrency(currency)) fail('invalid_money');
  const digits = currencies[currency];
  const absolute = (minor < 0n ? -minor : minor).toString().padStart(digits + 1, '0');
  return (minor < 0n ? '-' : '') + (digits
    ? absolute.slice(0, -digits) + '.' + absolute.slice(-digits) : absolute);
}

function location(value, document) {
  if (document.format === 'pdf') {
    shape(value, ['page', 'line']);
    if (!integer(value.page, 40) || !integer(value.line, 10000)) fail('invalid_location');
  } else if (document.format === 'xlsx') {
    shape(value, ['sheet', 'row', 'column']);
    if (!text(value.sheet, 128) || !integer(value.row, 10000) ||
        !integer(value.column, 16384)) fail('invalid_location');
  } else {
    shape(value, ['block']);
    if (!integer(value.block, 10000)) fail('invalid_location');
  }
  return Object.freeze({...value});
}

export function createEvidenceReview(input) {
  shape(input, ['reviewId', 'documents', 'facts']);
  if (!id(input.reviewId) || !Array.isArray(input.documents) || !input.documents.length ||
      input.documents.length > evidenceLimits.documents || !Array.isArray(input.facts) ||
      input.facts.length > evidenceLimits.facts) fail('invalid_review');
  const documentMap = new Map();
  let bytes = 0;
  const documents = input.documents.map(document => {
    shape(document, ['id', 'sha256', 'format', 'bytes']);
    if (!id(document.id) || documentMap.has(document.id) ||
        !['pdf', 'xlsx', 'docx'].includes(document.format) ||
        typeof document.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(document.sha256) ||
        !integer(document.bytes, evidenceLimits.bytesPerDocument)) fail('invalid_document');
    bytes += document.bytes;
    if (bytes > evidenceLimits.totalBytes) fail('document_budget_exceeded');
    const copy = Object.freeze({...document});
    documentMap.set(copy.id, copy);
    return copy;
  });
  const ids = new Set();
  const facts = input.facts.map(fact => {
    shape(fact, ['id', 'documentId', 'statementId', 'field', 'currency', 'amount',
      'certainty', 'location', 'excerpt']);
    const document = documentMap.get(fact.documentId);
    if (!id(fact.id) || ids.has(fact.id) || !document || !id(fact.statementId) ||
        !fields.includes(fact.field) || !validCurrency(fact.currency) ||
        !['extracted', 'user_confirmed', 'uncertain'].includes(fact.certainty) ||
        !text(fact.excerpt, evidenceLimits.excerptCharacters)) fail('invalid_fact');
    if (fact.amount === null) {
      if (fact.certainty !== 'uncertain') fail('invalid_fact');
    } else {
      moneyToMinor(fact.amount, fact.currency);
    }
    ids.add(fact.id);
    return Object.freeze({...fact, location: location(fact.location, document)});
  });
  const review = Object.freeze({version: 1, reviewId: input.reviewId,
    documents: Object.freeze(documents), facts: Object.freeze(facts)});
  admitted.add(review);
  return review;
}

// Checks the four PRINTED statement summary fields, not the completeness of rows,
// the issuer's authenticity, transaction legitimacy, or a fraud probability.
export function reconcileStatement(review, scope) {
  if (!admitted.has(review)) fail('unvalidated_review');
  shape(scope, ['documentId', 'statementId', 'currency']);
  const {documentId, statementId, currency} = scope;
  if (!id(documentId) || !id(statementId) || !validCurrency(currency) ||
      !review.documents.some(document => document.id === documentId)) fail('invalid_scope');
  const relevant = review.facts.filter(fact => fact.documentId === documentId &&
    fact.statementId === statementId && fact.currency === currency);
  const evidenceIds = Object.freeze(relevant.map(fact => fact.id));
  const result = (status, reason, calculation = null) => Object.freeze({
    rule: 'statement-summary-reconciliation-v1', reviewId: review.reviewId,
    documentId, statementId, currency, status, reason, evidenceIds, calculation,
  });
  if (fields.some(field => relevant.filter(fact => fact.field === field).length > 1)) {
    return result('inconclusive', 'ambiguous_summary_fields');
  }
  if (fields.some(field => !relevant.some(fact => fact.field === field))) {
    return result('inconclusive', 'missing_summary_fields');
  }
  if (relevant.some(fact => fact.certainty === 'uncertain' || fact.amount === null)) {
    return result('inconclusive', 'uncertain_summary_fields');
  }
  const [opening, credits, debits, closing] = fields.map(field =>
    moneyToMinor(relevant.find(fact => fact.field === field).amount, currency));
  if (credits < 0n || debits < 0n) return result('inconclusive', 'unsupported_signed_totals');
  const calculated = opening + credits - debits;
  const difference = closing - calculated;
  const calculation = Object.freeze({
    formula: 'opening_balance + total_credits - total_debits',
    calculatedClosing: minorToMoney(calculated, currency),
    printedClosing: minorToMoney(closing, currency),
    signedDifference: minorToMoney(difference, currency),
    tolerance: minorToMoney(0n, currency),
  });
  return result(difference === 0n ? 'passed' : 'flagged',
    difference === 0n ? 'printed_summary_balances' : 'printed_summary_difference', calculation);
}
