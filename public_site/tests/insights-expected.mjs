/** Independently stated values for the browser's real-file run. Only the test imports this. */
export const expected = [
  ['statementgap', [['D02','flagged','-400.00 USD'], ['D03','flagged','4']]],
  ['statementcontrol', [['D02','passed','1300.00 USD'], ['D03','passed','4']]],
  ['ledger', [['D02','inconclusive','All four']]],
  ['ledgercontrol', [['D02','passed','1000.00 EUR']]],
  ['ambiguous', [['D02','inconclusive','Repeated fields']]],
  ['ambiguouscontrol', [['D02','passed','1236.00 EUR']]],
  ['purchase', [['D06','flagged','20.00 USD'], ['D07','flagged','150'], ['D09','flagged','differs']]],
  ['purchasecontrol', [['D06','passed','100.00 USD'], ['D07','passed','150'], ['D09','passed','match']]],
  ['duplicate', [['D04','flagged','INV-410']]],
  ['duplicatecontrol', [['D04','passed','No repeated'], ['D04','not-applicable','1 repeated file']]],
  ['settlement', [['D08','flagged','-20.00 USD']]],
  ['settlementcontrol', [['D08','passed','950.00 USD'], ['D08','passed','0.00 USD']]],
  ['policy', [['D10','flagged','9990.00 USD']]],
  ['policycontrol', [['D10','passed','No supplied related group']]],
];
