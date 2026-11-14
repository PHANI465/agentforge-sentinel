// Browser-run suites. The default "legacy" run is the original 19 single-investigator
// cases, started exactly as before. "trace" (G3C-B) starts a separate stack whose API is
// the test-only three-role factory around the unchanged production app. "documents"
// (DOC01 Part C) starts the same stack as legacy; launch.mjs registers the real document
// worker and a fresh owned store through the environment the production API reads.
const LEGACY_MATCH = "**/workbench.pw.ts";
const TRACE_MATCH = "**/trace.pw.ts";
const DOCUMENTS_MATCH = "**/documents.pw.ts";
export const TRACE_APP = "g3c_trace_browser:create_app";

export function resolveSuite(value) {
  if (value === undefined || value === "" || value === "legacy") return "legacy";
  if (value === "trace") return "trace";
  if (value === "documents") return "documents";
  throw new Error("unknown_e2e_suite");
}

export function stackStartArgs(suite, stacksDir) {
  const args = ["start", "--parent-dir", stacksDir, "--timeout", "120", "--scorer", "rule", "--model-fixtures"];
  return suite === "trace" ? [...args, "--app", TRACE_APP] : args;
}

export function testMatchFor(suite) {
  if (suite === "documents") return DOCUMENTS_MATCH;
  return suite === "trace" ? TRACE_MATCH : LEGACY_MATCH;
}
