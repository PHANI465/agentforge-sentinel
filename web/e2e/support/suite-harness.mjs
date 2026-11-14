// Regression checks for the browser-run suite switch (no process is started).
import assert from "node:assert/strict";
import { resolveSuite, stackStartArgs, testMatchFor, TRACE_APP } from "./suite.mjs";

const legacy = ["start", "--parent-dir", "D", "--timeout", "120", "--scorer", "rule", "--model-fixtures"];
assert.equal(resolveSuite(undefined), "legacy");
assert.equal(resolveSuite(""), "legacy");
assert.equal(resolveSuite("legacy"), "legacy");
assert.equal(resolveSuite("trace"), "trace");
assert.throws(() => resolveSuite("all"), /unknown_e2e_suite/);
assert.deepEqual(stackStartArgs("legacy", "D"), legacy); // the original 19-case start, unchanged
assert.deepEqual(stackStartArgs("trace", "D"), [...legacy, "--app", TRACE_APP]);
assert.equal(TRACE_APP, "g3c_trace_browser:create_app");
assert.equal(testMatchFor("legacy"), "**/workbench.pw.ts");
assert.equal(testMatchFor("trace"), "**/trace.pw.ts");
assert.equal(resolveSuite("documents"), "documents");
assert.deepEqual(stackStartArgs("documents", "D"), legacy); // documents: the legacy start
assert.equal(testMatchFor("documents"), "**/documents.pw.ts");
console.log("Browser suite switch checks passed (legacy start unchanged; trace adds only --app; documents reuses the legacy start).");
