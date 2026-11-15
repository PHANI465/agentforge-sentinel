# Public document insights

Open the static site's home page and choose **Review a document**. The examples page
has synthetic scenarios and matching controls, plus the original January and May
2025 U.S. Treasury reports. The capabilities page lists the evidence each check needs.

Choose one text PDF, XLSX, or DOCX to review it. For related records, select up to
10 files together. Use **Comparison settings** to select a vendor baseline obtained
independently or enter your approval threshold, currency and window. Changes to file
selection or settings clear results. The next review uses the current inputs.

Results show flagged, passed, inconclusive, and unavailable checks. Open a source
location to see the PDF page and line, worksheet row and column, or Word block.
On desktop the source sits beside the findings. On narrow screens it opens next to
the selected finding. The source control moves focus to the excerpt and the return
button moves it back. Charts include numeric tables.

Files stay in browser memory. The site requests its scripts and any samples the
visitor chooses. Clear removes the selected files, settings and results. Cancel
stops the current review. Neither the synthetic workbench nor IAF receives the
document review inputs.

## Statement layouts

Give the statement an explicit Account and Period. Use an explicit Currency field
or consistent ISO currency codes on the four available printed summary amounts.
Recognized labels cover opening or beginning balance, deposits or credits,
withdrawals or debits, and closing or ending balance. Amounts may use conventional
English grouping and decimal points. Supply `Number format: decimal comma` for
dot grouping and a comma decimal separator. Parentheses indicate negative balances.
Credited and debited summary amounts are unsigned magnitudes.

Printed summary reconciliation checks four amounts for one account, period and
currency. For row reconciliation, a supported table has `Date Description Credit
Debit Balance` as its header, an ISO date for each row, explicit numeric credit,
debit and running balance fields, and an `End transactions` marker. Use printed
row order. Repeated supported page headers are allowed. A passed row check covers
the visible detected rows and their printed summary.

## Packet records

The packet reader accepts one typed record per document. Add labeled fields to
searchable text or a Word table. In an Excel sheet use label and value cells in the
same row. A record requires these fields.

| Field | Example |
| --- | --- |
| Record type | Invoice |
| Record ID | INV-410 |
| Vendor ID | NORTHWIND-LAB |
| Currency | USD |
| Total due | 24000.00 |
| Purchase order | PO-220 |
| Item VALVE-KIT | 200 ea 120.00 |

The accepted record types are Invoice, Purchase order, Delivery receipt, Payment
record, Credit note, Payment reversal, and Vendor baseline. Use matching explicit
identifiers and currency across the files. Invoice and order item rows contain an item
ID, integer quantity, unit, and unit price. Delivery rows contain item ID, quantity and
unit, with the same purchase order reference. Payment records, credits and reversals
require Invoice reference and Amount. Reversals also require Reverses payment. The
remittance check compares Payment destination fields using the selected vendor
baseline. Approval policy groups require Invoice date and Group reference.

The parser supports the layouts shown in the sample library. Unrecognized layouts,
conflicting fields and missing references can leave checks incomplete. Use the
record previews to review what the browser extracted. The source panel shows
text excerpts. Image-only scans and visual forgery analysis require other tools.

For implementation details and verification see
[the delivery record](../handoff/SOL-document-insights.md).
