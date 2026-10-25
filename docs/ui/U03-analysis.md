# U03 model and analysis view

Status: contract and UI increment. Real browser-to-Postgres acceptance of the new routes is not done.

## Dependencies

- Application base: accepted U02 `5f2855553ac0a445d96914730a89fc3722682830` on `task/cursor-model-analysis`. Worktree: `E:/PHANI/sentinel-wt/cursor-model-analysis`. The accepted U02 checkout is unchanged.
- UI contract: `62def106af74821040ac54535b8efe87341ca10b`, read with `git show`. OpenAPI `contracts/http/openapi.v1.1.json` Git-blob SHA-256 `1f220a5628e3e261776c286c56b502b8d989184bd928bf219f30ebb6e451fd90`. Nine examples in `contracts/http/examples-v1.1/`. Semantics in `docs/api/README.md` at that commit.
- Backend C07 at that commit is not accepted and is not merged. No files under `src/sentinel/`, `contracts/`, or migrations were edited. Fixture bytes live in `web/src/fixtures/http-v1.1/` with `PROVENANCE.md`.

## What the analyst sees

The configured scorer comes only from `GET /v1/scoring`. It is separate from the investigator line. Each case still shows the scorer, semantics, score, and threshold stored on that record. A rule record stays a rule score when the server is in model mode, and a model record stays a model score when the server is in rule mode.

`uncalibrated_score` is labeled "Uncalibrated ranking" and "Not a fraud probability." `estimated_probability` on a model record is labeled "Recorded model score" and is also not called a fraud probability. The frozen threshold `4.0295386895426815e-06` is shown as `4.0295386895426815e-6`.

When scoring returns `results_id`, the page loads `GET /v1/model-results/{results_id}` and renders that body: the offline synthetic benchmark label, limitations, split windows and delayed-label text, baseline average precision beside trapezoidal precision-recall area, the frozen-threshold counts beside the daily top-k counts, uncertainty intervals, calibration bins, currency and scenario slices, and the reported precision-recall points. Scenario slices are captioned as offline hidden synthetic truth. Currency rows stay in their own table. The chart is those precision-recall points. No ROC series, live metric, or tenant total is added.

A reliability bin may leave `mean_score` or `fraud_rate` null, including an empty bin where both are null. Those cells say "not reported". A reported zero stays zero. `labels_observable_by_horizon` may be omitted; that is the same as null and the split table says "not reported". Omitting `lo`, `hi`, `n`, `mean_score`, or `fraud_rate`, or sending a non-number for those statistics, leaves the report unconfirmed. The frozen p1 example file is unchanged.

Stored model inputs, when the case payload includes them, show the feature values, transaction currency, and profile home currency separately.

## Failures

401, 403, network errors, and malformed bodies use the existing safe messages. Scoring 404 or 405 says the analysis view is unavailable. A missing results id says that model report is not on this server. None of those paths render the p1 fixture. A session without `read_case` does not call the routes. Sign-out unmounts the view. A response that belongs to an earlier token or session does not fill the current view. Tokens stay in memory. Server note text is inert.

`account_profile_missing` on ingest says the account has no profile and nothing was stored.

## What is not accepted yet

This increment does not start a model-mode API or seed profiles. `npm run test:e2e` still uses the accepted U02 rule-mode stack. On that stack the analysis view is unavailable, which is the expected older-route state. After Codex accepts a corrected C07 commit, a later step has to render these values from that API and Postgres and rerun the browser path.
