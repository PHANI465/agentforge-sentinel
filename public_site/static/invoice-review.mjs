const cash = '(?:[$€£]|USD |EUR |GBP )\\s*(?:\\d{1,3}(?:,\\d{3})+|\\d{1,12})(?:\\.\\d{2})?';
const tableHeader = /\b(?:qty|quantity|hours)\b\s+(?:unit price|rate)\s+(?:line total|total|amount)\s*$/i;
const rowPattern = new RegExp('^(.+?)\\s+(\\d{1,8}(?:\\.\\d{1,4})?)\\s+(' + cash + ')\\s+(' + cash + ')$', 'iu');
const exactCash = new RegExp('^' + cash + '$', 'iu');
const subtotalPattern = /^(?:reported\s+)?sub[ -]?total\s*:/i;
const taxPattern = /^(?:sales )?(?:tax|vat|gst)(?:\s*\(\d+(?:\.\d+)?%\))?\s*:/i;
const duePattern = /^(?:reported\s+)?(?:total due|grand total|invoice total|total amount due|amount due)\s*:/i;
const notesStart = /^(?:remittance notes|payment terms|updated banking instructions|payment instructions|vendor|bill to|thank you)\b/i;

function toMoney(text) {
  const amount = text.trim().match(/^([$€£]|USD|EUR|GBP)\s*(\d[\d,]*)(?:\.(\d{2}))?$/iu);
  if (!amount || !exactCash.test(text.trim())) return null;
  return {
    unit: amount[1].toUpperCase(),
    cents: BigInt(amount[2].replaceAll(',', '')) * 100n + BigInt(amount[3] ?? 0),
  };
}

function format(cents, unit) {
  const whole = (cents / 100n).toLocaleString('en-US');
  const decimal = String(cents % 100n).padStart(2, '0');
  return unit + (unit.length === 1 ? '' : ' ') + whole + '.' + decimal;
}

function namedAmount(line, pattern) {
  return pattern.test(line) ? toMoney(line.replace(pattern, '')) : null;
}

function sameUnit(a, b) {
  return a && b && a.unit === b.unit;
}

function discrepancy(left, right, unit) {
  return format(left >= right ? left - right : right - left, unit);
}

function multiplication(quantity, rate) {
  const [whole, fraction = ''] = quantity.split('.');
  const scale = 10n ** BigInt(fraction.length);
  return (BigInt(whole + fraction) * rate + scale / 2n) / scale;
}

function arithmetic(lines, add) {
  const header = lines.findIndex(line => tableHeader.test(line));
  if (header === -1) return;
  const rows = [];
  let index = header + 1;
  let complete = true;
  for (; index < lines.length; index += 1) {
    const line = lines[index];
    if (subtotalPattern.test(line) || duePattern.test(line) || notesStart.test(line)) break;
    const match = rowPattern.exec(line);
    if (!match) {
      complete = false;
      continue;
    }
    const [, item, quantity, unitPrice, printedTotal] = match;
    const rate = toMoney(unitPrice);
    const printed = toMoney(printedTotal);
    if (!sameUnit(rate, printed)) {
      complete = false;
      continue;
    }
    const calculated = multiplication(quantity, rate.cents);
    rows.push(printed);
    if (calculated !== printed.cents) {
      add('line-math', 'Line item does not add up',
        quantity + ' × ' + format(rate.cents, rate.unit) + ' gives ' + format(calculated, rate.unit) +
        '. The row lists ' + format(printed.cents, rate.unit) + ', a difference of ' +
        discrepancy(calculated, printed.cents, rate.unit) + '.', line, item.slice(0, 120));
    }
  }

  const [subtotalLine = '', taxLine = '', dueLine = ''] = lines.slice(index, index + 3);
  const subtotal = namedAmount(subtotalLine, subtotalPattern);
  const tax = namedAmount(taxLine, taxPattern);
  const due = namedAmount(dueLine, duePattern);
  if (complete && rows.length && subtotal && rows.every(amount => sameUnit(amount, subtotal))) {
    const sum = rows.reduce((value, amount) => value + amount.cents, 0n);
    if (sum !== subtotal.cents) {
      add('subtotal-math', 'Subtotal differs from the listed rows',
        'The printed line totals on this page add up to ' + format(sum, subtotal.unit) + '. The reported subtotal is ' +
        format(subtotal.cents, subtotal.unit) + ', a difference of ' +
        discrepancy(sum, subtotal.cents, subtotal.unit) + '.', subtotalLine);
    }
  }
  if (sameUnit(subtotal, tax) && sameUnit(tax, due)) {
    const sum = subtotal.cents + tax.cents;
    if (sum !== due.cents) {
      add('total-math', 'Total due differs from subtotal plus tax',
        'The printed subtotal and tax add up to ' + format(sum, due.unit) + '. The reported total due is ' +
        format(due.cents, due.unit) + ', a difference of ' + discrepancy(sum, due.cents, due.unit) + '.',
        [subtotalLine, taxLine, dueLine].join(' · '));
    }
  }
}

function paymentTerms(lines, add) {
  const invoice = lines.map(line => line.match(/^invoice\s+#?([a-z0-9-]+)\b/i)?.[1]).find(Boolean);
  const due = lines.map(line => namedAmount(line, duePattern)).find(Boolean);
  const index = lines.findIndex(line => /^remittance notes\b/i.test(line));
  if (index < 0) return;
  const notes = lines.slice(index, index + 5).join(' ');
  const statedLimit = notes.match(new RegExp('(' + cash + ')\\s+(?:(?:dual|single|manager)[ -])?approval\\s+(?:threshold|limit)\\b', 'iu'))?.[1];
  const requested = notes.match(new RegExp('\\b(?:remit|pay)\\s+(' + cash + ')', 'iu'))?.[1];
  const related = notes.match(new RegExp('\\b(?:sequential|related|second) invoice\\s+#?([\\w-]+)\\s+for\\s+(' + cash + ')', 'iu'));
  const limit = statedLimit && toMoney(statedLimit);
  const current = (requested && toMoney(requested)) || due;
  const next = related && toMoney(related[2]);
  if (sameUnit(limit, current) && current.cents > 0n && limit.cents > current.cents && (limit.cents - current.cents) * 100n <= limit.cents) {
    const combined = sameUnit(current, next) && invoice && invoice.toUpperCase() !== related[1].toUpperCase() &&
      next.cents > 0n && next.cents < limit.cents && current.cents + next.cents >= limit.cents;
    const near = 'The current amount, ' + format(current.cents, current.unit) +
      ', is ' + format(limit.cents - current.cents, current.unit) + ' below the stated ' +
      format(limit.cents, current.unit) + ' approval threshold.';
    add('approval-limit', combined ? 'Related invoices may need joint approval' : 'Amount is close to the stated approval threshold',
      combined
        ? near + ' The notes cite another ' + format(next.cents, next.unit) +
          ' invoice, bringing the combined amount to ' + format(current.cents + next.cents, current.unit) +
          '. Confirm both invoices and the policy in the purchasing system.'
        : near + ' Check the approval policy and related invoices.',
      combined ? 'Related invoice ' + related[1] + ' · Stated approval threshold ' + statedLimit : 'Stated approval threshold ' + statedLimit);
  }
  if (/\bvendor address (?:matches|is the same as)\b.{0,60}\bemployee\b/i.test(notes)) {
    add('address-overlap', 'Vendor and employee address overlap is reported',
      'The remittance notes say the vendor address matches an employee record. Confirm the match in your trusted vendor and HR records.',
      'The remittance notes report a vendor and employee address match.');
  }
}

function remittance(lines, add) {
  const paymentChange = lines.find(line => /^(?:updated|new|changed)\s+(?:bank(?:ing)?|ach|wire|remittance|payment)\s+(?:instructions|details|account)\b/i.test(line));
  const vendor = lines.find(line => /^vendor(?: name)?\s*:/i.test(line));
  const beneficiary = lines.find(line => /^(?:beneficiary|payee)(?: name)?\s*:/i.test(line));
  const routing = lines.find(line => /^\s*(?:(?:aba|ach)\s+)?routing(?: number)?\s*:/i.test(line));
  const email = lines.find(line => /^contact email\s*:/i.test(line));
  if (paymentChange) {
    add('payment-change', 'Invoice asks to change payment instructions',
      'The invoice asks for updated banking details. Confirm any change using a contact already on file before sending a payment.',
      'Updated payment instructions are printed on the invoice.');
  }
  const name = line => line.replace(/^[^:]+:\s*/, '').replace(/\s+\((?:synthetic test entity|mismatch with vendor name)\)\s*$/i, '').trim();
  const simplify = value => value.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
  if (vendor && beneficiary && simplify(name(vendor)) && simplify(name(beneficiary)) &&
      simplify(name(vendor)) !== simplify(name(beneficiary))) {
    add('payee-name', 'Beneficiary name differs from the vendor',
      'Vendor: ' + name(vendor) + '. Beneficiary: ' + name(beneficiary) +
      '. A different legal name can have a legitimate explanation. Confirm it against the approved vendor record.',
      'Vendor and beneficiary name fields.');
  }
  const digits = routing?.match(/routing(?: number)?\s*:\s*(\d{9})\b/i)?.[1];
  if (digits) {
    const weights = [3, 7, 1];
    const sum = [...digits].reduce((value, digit, index) => value + Number(digit) * weights[index % 3], 0);
    const placeholder = /^0+$/.test(digits);
    if (placeholder || sum % 10 !== 0) {
      add('routing-format', 'US routing number needs verification',
        placeholder ? 'The routing number is all zeros. Confirm it against the approved payment record.' :
          'The number fails a US routing checksum check. Confirm it against the approved payment record.',
        'Routing number field (digits hidden).');
    }
  }
  if (email && paymentChange) {
    add('email-verify', 'Verify the sender independently',
      'The contact email accompanies a request to change banking details. Compare the sender’s domain with the one on your approved vendor record.',
      'Contact email and banking instructions.');
  }
}

export function invoiceEvidence(pages) {
  const checks = [];
  for (const {number: page, lines} of pages) {
    // QA annotations explain fixtures. They are excluded from the invoice checks.
    const annotation = lines.findIndex(line => /^synthetic benchmark artifact\b/i.test(line));
    const body = annotation < 0 ? lines : lines.slice(0, annotation);
    const add = (code, title, description, line, item) => {
      if (checks.length < 24 && !checks.some(check => check.code === code && check.page === page && check.line === line)) {
        checks.push({code, title, description, line, item, page});
      }
    };
    arithmetic(body, add);
    paymentTerms(body, add);
    remittance(body, add);
  }
  return checks;
}
