export const catalog = {
  D01: ['Invoice arithmetic', 'Limited', 'Recognized quantity, price and total columns or explicit subtotal, adjustments and total.', 'Calculations cover recognized rows and printed amounts. Unclear rows can prevent subtotal review.'],
  D02: ['Statement summary', 'Available', 'Account, period, currency, and printed opening, credit, debit and closing amounts.', 'Compares the four printed amounts.'],
  D03: ['Statement transaction rows', 'Limited', 'Explicit transaction section with ISO dates, credit, debit and running balance per row.', 'Uses visible rows in printed order.'],
  D04: ['Repeated invoice or payment reference', 'Available', 'Recognized invoice or payment records with a vendor ID, reference and currency.', 'Matching file bytes count once. A repeated ID needs review before treating it as a duplicate charge.'],
  D05: ['Near-duplicate invoice', 'Planned', 'Vendor identity and comparable item descriptions, amounts and dates.', 'Similarity thresholds need validation.'],
  D06: ['Invoice versus purchase order', 'Available', 'Invoice and purchase order referencing the same PO and item, with matching units and currencies.', 'Compares unit prices and quantities in the supplied records.'],
  D07: ['Invoice versus delivery', 'Available', 'Recognized delivery records with explicit PO/item references and delivered quantities.', 'A difference can reflect a partial delivery or an omitted receipt.'],
  D08: ['Invoice versus payments', 'Available', 'The invoice and linked payments, credit notes or reversals in the same currency.', 'Compares the supplied amounts and keeps unmatched references visible.'],
  D09: ['Changed remittance details', 'Available', 'Invoice and a vendor baseline selected as trusted by the reviewer.', 'Compares supplied identifiers. Verify changes through a trusted contact.'],
  D10: ['Related invoices and an approval limit', 'Available', 'Reviewer-entered threshold, currency and window plus invoice dates and explicit group IDs.', 'Checks each invoice against the supplied policy and flags groups that cross the limit.'],
  D11: ['Financial summaries', 'Limited', 'Supported statement fields, workbook amount columns or recognized Treasury Table 2.', 'Amounts stay in their published units and currencies.'],
  D12: ['Conflicting document fields', 'Limited', 'Recognized invoice totals or repeated record IDs with conflicting typed values.', 'Flags internal inconsistencies for manual review.'],
};
export const checkStates = {
  flagged: 'Review flag', passed: 'Check passed', inconclusive: 'Inconclusive',
  'not-applicable': 'Not applicable', 'not-run': 'Not run',
};
