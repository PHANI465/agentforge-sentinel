// A small transport check, not a complete TypeScript/JSON Schema validator.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const path = new URL("../contracts/examples/transaction.v1.json", import.meta.url);
const transaction = JSON.parse(readFileSync(path, "utf8"));
assert.equal(transaction.schema_version, "1.0");
assert.equal(transaction.synthetic, true);
assert.ok(Number.isSafeInteger(transaction.amount.minor_units));
assert.ok(transaction.amount.minor_units > 0);
assert.equal(transaction.amount.currency_exponent, 2);
assert.equal(transaction.amount.currency, "USD");
assert.ok(transaction.occurred_at.endsWith("Z"));
const largestAllowedAmount = 9_000_000_000_000;
assert.ok(Number.isSafeInteger(largestAllowedAmount));
assert.equal(JSON.parse(JSON.stringify({ amount: largestAllowedAmount })).amount,
             largestAllowedAmount);
assert.deepEqual(JSON.parse(JSON.stringify(transaction)), transaction);
console.log("JavaScript transport checks passed for the synthetic transaction and money bound.");
