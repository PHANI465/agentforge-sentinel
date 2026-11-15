export const maximumBytes = 10 * 1024 * 1024;
export const maximumPages = 40;
export const maximumCharacters = 240_000;

const labeledAmounts = [
  ['Opening balance', /^(?:opening|beginning|previous) balance\b/i, 'The amount reported at the start of the statement period.'],
  ['Closing balance', /^(?:closing|ending|new) balance\b/i, 'The amount reported at the end of the statement period.'],
  ['Amount due', /^(?:total amount due|amount due|balance due|total due|total payable)\b/i, 'The amount the issuer says remains payable. Check the due date and whether any payments have posted.'],
  ['Subtotal', /^sub[ -]?total\b/i, 'An intermediate total, usually before taxes, discounts or other adjustments.'],
  ['Listed tax', /^(?:total tax|sales tax|vat|gst|tax)\b/i, 'A tax amount reported by the issuer. Rates and taxable items may appear separately.'],
  ['Listed total', /^(?:grand total|invoice total|total)\b/i, 'A total reported on this page. Compare its label and currency with the source.'],
  ['Deposits or credits', /^(?:total )?(?:deposits|credits|payments received)\b/i, 'Incoming amounts or credits as labeled by the issuer.'],
  ['Withdrawals or debits', /^(?:total )?(?:withdrawals|debits|purchases)\b/i, 'Outgoing amounts or debits as labeled by the issuer.'],
  ['Fees or charges', /^(?:total )?(?:fees|service charges)\b/i, 'Fees the issuer reports. Check what each fee covers before comparing it with other totals.'],
];

const money = /^[\s:]*((?:(?:[A-Z]{3}|[$€£¥₹])\s*)?\(?[+−-]?\d+(?:[., '\u00a0]\d+)*\)?(?:\s*(?:[A-Z]{3}|[$€£¥₹]))?)\s*$/u;
const terminology = [
  ['Due date', /\bdue date\b|\bpayment due\b/i, 'The date by which the issuer asks for payment.'],
  ['Statement period', /\bstatement period\b|\bperiod covered\b/i, 'The range of dates this statement says it covers.'],
  ['Transaction date and posting date', /\bposting date\b|\bposted date\b/i, 'The date activity appears in the ledger can differ from the date the purchase took place.'],
  ['Reversal or refund', /\breversal\b|\brefund\b/i, 'A reversal or refund may offset an earlier entry. Check which entry it refers to.'],
];

export function pageLines(items) {
  const lines = [];
  let current = [];
  for (const item of items) {
    if (typeof item.str !== 'string') continue;
    current.push(item.str);
    if (item.hasEOL) {
      lines.push(current.join(' ').replace(/\s+/gu, ' ').trim());
      current = [];
    }
  }
  if (current.length) lines.push(current.join(' ').replace(/\s+/gu, ' ').trim());
  return lines.filter(Boolean);
}

export function explain(pages) {
  const readable = pages.filter(page => page.lines.length);
  const amountFindings = [];
  const termFindings = new Map();
  const amountsSeen = new Set();
  const openingText = readable.slice(0, 3).flatMap(page => page.lines.slice(0, 12)).join(' ');
  const kind = /\b(?:bank statement|account statement|opening balance|closing balance)\b/i.test(openingText)
    ? 'Statement'
    : /\binvoice\b/i.test(openingText) ? 'Invoice' : /\btransaction report\b/i.test(openingText) ? 'Transaction report' : 'PDF text review';

  for (const page of readable) {
    for (const line of page.lines) {
      for (const [title, label, description] of labeledAmounts) {
        const prefix = line.match(label);
        if (!prefix) continue;
        const amount = line.slice(prefix[0].length).match(money)?.[1];
        const key = JSON.stringify([title, amount]);
        if (amount && !amountsSeen.has(key) && amountFindings.length < 12) {
          amountsSeen.add(key);
          amountFindings.push({title, description, amount, line, page: page.number});
        }
        break;
      }
      for (const [title, pattern, description] of terminology) {
        if (!termFindings.has(title) && pattern.test(line)) {
          termFindings.set(title, {title, description, line, page: page.number});
        }
      }
    }
  }
  return {
    kind,
    readable: readable.length,
    missing: pages.filter(page => !page.lines.length).map(page => page.number),
    findings: [...amountFindings, ...termFindings.values()],
    excerpts: readable.map(page => ({page: page.number, text: page.lines.join('\n').slice(0, 1000)})),
  };
}
