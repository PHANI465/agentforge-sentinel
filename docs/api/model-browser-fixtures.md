# Model browser fixtures (I01)

Audience: Cursor (I02 real-model browser tests) and reviewers.

- **Status:** I01 fixture and lifecycle contract, for Codex review.
- **Dependencies:** C07 `275509a` (accepted backend) and U03 `a5716e2` (accepted p1 frontend), merged as integration commit `5488a61` on `task/claude-model-browser-fixtures`.
- **Builds on:** the C02 stack in `docs/api/browser-fixtures.md`, whose lifecycle, ownership, cleanup and token rules all still apply. Only the differences are listed here.
- **Contracts unchanged:** the public HTTP contracts (`contracts/http/openapi.v1.json` and `openapi.v1.1.json`, plus all examples) and the p1 report and artifact.

## Environment

Run `uv sync --locked --extra dev --extra ml` in the backend checkout. Rule-only stacks still work without the ml extra. Model mode or model fixtures without it fail at startup, and the stack then cleans up as for any failed start.

## Lifecycle additions

```powershell
uv run --locked python tests/support/browser_stack.py start [--parent-dir DIR] [--scorer rule|model] [--model-fixtures]
uv run --locked python tests/support/browser_stack.py restart-api --manifest PATH [--scorer rule|model]
```

- **`--scorer`:** selects the API's scorer through the production `SENTINEL_SCORER`. `model` maps to `model:hgb_balanced@p1`, the only registered model; no artifact path or other value can be passed. The default is `rule`, as before.
- **`--model-fixtures`:** seeds the model scenarios below and an `ingest_only` token. `--scorer model` implies it. Without either flag, a stack is seeded exactly as in C02.
- **`restart-api --scorer X`:** a real process restart (new PID, identity-checked stop) into the other registered mode. Without `--scorer`, the mode is kept.
  - This is the only way to switch modes; there is no HTTP mode-selection route.
  - Stored outcomes and cases keep their own scorer identity, and replays return them unchanged.
- **`restart-db`:** unchanged. Model outcomes, inputs and audit persist across both restarts.
- **`start` output:** the line now ends with `scorer=rule|model`. It still prints no tokens.
- **`status` output is unchanged** (`{"api":..,"database":..}`, exactly as in C02). Read the current mode from the manifest's `api.scorer`, which `start` and `restart-api` keep current.

## Database roles

- **Setup** (migrate, `grant-runtime`, sessions, profiles, disclosures, scenario seeding) uses the cluster owner. This connection is `database_url` in the manifest, as in C02, and `inspect_case.py` keeps using it.
- **The API process** (in every mode, including rule) connects as `sentinel_browser_runtime`. That is the C05 least-privilege runtime role, created by `sentinel.db.roles.grant_runtime` and recorded as `api.database_user`.
  - The cluster uses trust authentication on 127.0.0.1, so there is no password and no new secret.
  - The runtime role cannot issue sessions or write profiles or disclosures. It cannot alter schema or audit.

## Manifest additions (private `stack.json`)

| Field | Content |
| --- | --- |
| `api.scorer` | current `SENTINEL_SCORER` value: `rule` or `model:hgb_balanced@p1` |
| `api.database_user` | `sentinel_browser_runtime` |
| `model_fixtures` | `true` when the model scenarios were seeded |
| `tokens.ingest_only` (secret) | analyst scope, same actor, capability `ingest_transaction` only (with model fixtures) |
| `sessions.ingest_only` | its tenant, session, actor and capabilities |
| `scenarios.model_*` | the records below |

Token hygiene is unchanged from C02: read tokens only from the manifest, never log them or put them in URLs, storage or traces, and never copy the manifest into artifacts.

## Model scenarios

All model scenarios belong to the `analyst` session. Account IDs are UUIDv5 values of `acct:<label>`, and external IDs are `i01-<label>`, where the label is the scenario name, or `name-ordinal` for an on-demand `seed`. The seeding service holds the accepted registered scorer. Profiles and disclosures are loaded through the accepted operator methods, one hour before the decision.

Every profile opens exactly 400 days before its transaction's `occurred_at`, and f1 counts whole days. All inputs and scores are therefore identical on every run; only timestamps differ.

| Name | Seeded state | Browser path and exact results |
| --- | --- | --- |
| `model_alert` | **Recorded model case**, open, rev 1. A USD-home account (profile opened 400 days earlier) with one fraud disclosure (disclosed 2 days earlier, recorded 1 hour earlier). Ingested: a GBP 250000-minor debit. | `GET /v1/cases/{case_id}` → 200, `scoring_kind: model`, `score_semantics: uncalibrated_score`, score **0.61962960122**, threshold **4.0295386895426815e-06**, alerted. `pins.scorer` is `hgb_balanced` / `p1` / sha `6c2982d1…`. Stored `inputs`: `values` as in the next table; `currency` GBP; `history_rows` 0; `disclosures_used` 1; `profile_home_currency` USD. `model` is the C07 provenance: `results_id` p1, `threshold_source` `validation_frozen_threshold`. POSTing `request_body` again, in **either mode**, returns 201 `replayed: true` with exactly the stored scoring. The full stored values are in the record's `expected_scoring`. |
| `model_missing_profile` | Nothing stored; this account has no profile. | **Model mode:** POST `request_body` → 422 `{"error":"account_profile_missing"}`. No transaction, outcome, alert or case is stored, and `inspect_case.py --external-id i01-model_missing_profile` finds none. (In rule mode the rule would score and store it, so run this check in model mode.) |
| `model_live_alert` | A provisioned USD-home account (opened 400 days before `request_body.occurred_at`) with no history. | **Model mode:** POST `request_body` (the account's first ingestion) → 201 with `scoring` equal to `expected_scoring`: kind `model`, score **0.802130558706**, alerted, `inputs.values` as in the next table, `history_rows` 0, `disclosures_used` 0. A new open case is pinned to `hgb_balanced`. Each further fresh ingestion needs `seed --scenario model_live_alert --ordinal N`. |

The **recorded rule case** for comparison is C02's `open_case`: `scoring_kind: rule`, `score_semantics: heuristic`, score 0.6, threshold 0.5, `pins.scorer` the rule. Its scoring has no `model` or `inputs` keys, in either API mode. Every C02 scenario is a rule case, seeded by the rule scorer.

`values` (f1, in protocol order):

| Feature | `model_alert` | `model_live_alert` |
| --- | --- | --- |
| amount_minor | 250000 | 250000 |
| is_credit | 0 | 0 |
| is_foreign_currency | 1 | 0 |
| account_age_days | 400 | 400 |
| count_1h, count_24h, small_count_1h | 0, 0, 0 | 0, 0, 0 |
| same_currency_sum_24h, credit_sum_24h | 0, 0 | 0, 0 |
| seconds_since_prev, amount_to_median_bps | -1, -1 (no history) | -1, -1 |
| prior_known_fraud | 1 | 0 |

These scores come from running the accepted artifact, not from hand-set numbers. `model_live_alert.expected_scoring` is computed at seeding by C03's `compute` and the loaded pipeline (the server's own code path), and the fixture tests check it against the live API. The model also alerts this body at every account age from 0 to 3650 days (minimum 0.0105), so `alerted` does not hinge on the age. Scores are uncalibrated rankings, not probabilities.

## Routes and permissions (unchanged production behavior)

- `GET /v1/scoring`:
  - `analyst`, `read_only`, `second_actor` → 200, with `mode` `rule` or `model` following the current API mode;
  - `ingest_only` → 403 `permission_denied`;
  - no token → 401.
- `GET /v1/model-results/p1`:
  - `read_case` tokens → 200, with the frozen C04 report labeled `offline synthetic benchmark`, `synthetic: true`;
  - `ingest_only` → 403;
  - an unknown ID → 404 `not_found`.

  The response is identical in both modes. The frozen values are the p1 report fields, including `frozen_threshold` 4.0295386895426815e-06.
- `other_session` → 404 `not_found` for `model_alert`'s case, audit and investigation, and the case is absent from its list and overview.

## Scorer switch scenario

1. `start --scorer model`, then check `/v1/scoring` (model), `model_alert` and `model_live_alert`.
2. `restart-api --scorer rule`. `/v1/scoring` now reports rule / heuristic. `model_alert`'s case still shows model identity and pins. Replaying its `request_body` returns the stored model scoring (`replayed: true`). A new rule ingestion has no `model` or `inputs`.
3. `restart-api --scorer model` restores model mode. Rule records stay rule.

## Failure behavior

- A start or restart whose API cannot bind its scorer exits during startup. Examples are a missing ml extra, a corrupted packaged identity, or an unregistered value, which can only come from internal tests. `start` then reports the error and cleans up as in C02, or keeps the recovery manifest if cleanup cannot be verified.
- A failed `restart-api` leaves the database running, and the manifest records no live API PID. Run `stop`, or `restart-api` again.
