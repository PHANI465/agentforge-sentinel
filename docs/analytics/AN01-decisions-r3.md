# AN01 r3: proposed resolutions of the six open decisions, and a report-query measurement plan

Audience: Codex, as the reviewer who decides whether the AN01 S1 contract can be frozen; then
the backend and frontend implementers.

- **Status:** proposal for review. Nothing here is accepted, implemented or exposed. No
  route, migration, capability, contract document or lockfile changes in this branch.
- **Base:** main `c2140ce`, which contains tested integration `871e31d` and the AN01-r2
  documents unchanged (`a8c164a`).
- **Answers:** the six questions in [design §13](AN01-workspace-design.md#13-open-questions-for-review),
  plus the review note to separate a PostgreSQL statement/cancel budget from a guaranteed
  request deadline ([Parallel-batch review](../reviews/Parallel-batch-830f018.md), "AN01
  decisions still needed").
- **Companion files:**
  - [AN01-zone-table.json](AN01-zone-table.json): the proposed pinned zone table;
  - [derive_an01_zones.py](derive_an01_zones.py): derives that table under review;
  - [check_an01_r3.py](check_an01_r3.py): recomputes every *derived* number below.

## How each number is labelled

| Label | Meaning |
| --- | --- |
| **derived** | Follows from the encoding, schema or committed data. `check_an01_r3.py` recomputes it, and it needs no performance measurement |
| **measured once** | Observed on this laptop by the command given; a fact about that environment only |
| **provisional** | A design number that no measurement supports yet. It stays provisional until the AN01-M1 plan (§8) runs and Codex accepts its result |
| **policy** | A product choice. It is not a performance claim |

## 1. Summary of the proposed decisions

| # | Question | Proposed resolution | Label |
| --- | --- | --- | --- |
| 1 | Zone data pinning | Runtime uses a **committed five-zone midnight table** (IANA 2026e, sha256 `dd1b19c9…`), never host `zoneinfo`. Deriving it under review on both platforms gives identical bytes. No lockfile change | derived + measured once |
| 2 | Capability and version compatibility | **Additive HTTP contract v1.3** widens `Capability` by `read_report`, and v1.2 freezes. Clients must ignore capability values they do not know; Sentinel's web client already does. The server keeps closed validation. `/v1/session` is not filtered | policy |
| 3 | Cursor integrity | **Unsigned**, with strict member validation, a **derived 256-character limit** (worst case 228), and a UI that only uses cursors from its own last response | derived + policy |
| 4 | Query limits | Separate **database budget** (statement/lock timeout plus the client stopping its wait) from any response deadline. Reuse the accepted `BoundedTransaction` pattern and end with ROLLBACK. The 200,000-row cap and the 5,000 ms budget stay provisional until AN01-M1 | provisional |
| 5 | Index strategy | One draft migration: `transactions (tenant_id, session_id, occurred_at, id)`, plus a candidate `simulated_actions (tenant_id, session_id)` that AN01-M1 decides. **No generated columns** in S1 | proposal, measurement-gated |
| 6 | UI staleness wording | Two separate signals. An earlier `as_of` is a **chosen cutoff**, never "old". Result age is measured on the **browser's monotonic clock since receipt**, never as browser wall clock minus `read_at`. A 5-minute nudge is policy | policy |

## 2. Decision 1: time-zone data pinning

**Facts:**
- **The lock:** `tzdata` 2026.5 is locked only with the marker `sys_platform == 'win32'` (`uv.lock`, as a dependency of `psycopg`).
- **Native Ubuntu** (WSL, Python 3.11.14): `import tzdata` fails, and `zoneinfo.TZPATH` starts with `/usr/share/zoneinfo`, which is Ubuntu package `tzdata 2026e-0ubuntu0.24.04.1`.
- **Windows** (Python 3.11.3): `TZPATH` is empty, and `zoneinfo` uses the locked wheel, IANA 2026e.
- So the two platforms reach the same IANA release today by different routes, and a host update can change Linux at any time.

**Proposal:**
1. **Pin the table.** Commit the derived table [AN01-zone-table.json](AN01-zone-table.json): 3 KB, the five allow-listed zones, local dates 2000-01-01 to 2038-01-01. Each row is `[first local date, UTC offset at local midnight in seconds]`, and the digest is `dd1b19c9c191d33f94758cf81bab82ac5d29c68b9717e5f58897ac2e024749a5`, with domain `sentinel.report-zones.an01-s1\n`.
2. **Use only the table at runtime.** The server computes the start of local date D as `D 00:00 UTC − offset(D)` from the table, and passes those instants to SQL, as r2 §6 already requires. Host zone data, the `tzdata` wheel and PostgreSQL's `TimeZone` are never consulted at runtime, so no platform or host update can change a report.
3. **Report provenance.** `tz_data` becomes `"an01-zones IANA 2026e sha256:dd1b19c9…"` instead of the host's version.
4. **Changing the table** (a future tz release, or a wider allow-list) is a reviewed change:
   - run `derive_an01_zones.py --check` on Windows and on native Linux;
   - on a difference, regenerate the table, bump `report_version`, and get it reviewed.

   This is a manual review command, **not** a gate test. A host whose zone database is missing or newer must neither fail nor skip the strict gate (the skip policy allows exactly one skip).
5. **Gate tests stay platform-independent.** The implementation's unit test loads the table, recomputes its digest, and asserts its invariants: ordered ranges, and day lengths only 82,800, 86,400 or 90,000 s. `check_an01_r3.py` already performs those checks here.
6. **Keep the window bound** `[2000-01-01T00:00:00Z, 2038-01-01T00:00:00Z)`, because it is exactly the range the table covers.
7. **No lockfile change.** It is not needed, which avoids new dependency resolution.

**Evidence:**
- **Measured once:** `derive_an01_zones.py --check` reports "matches the committed table" on both Windows (tzdata wheel 2026e) and native Ubuntu (system zoneinfo 2026e), with the same digest.
- **Derived** (`check_an01_r3.py`, from the table alone):
  - every local midnight in the five zones exists, and is unambiguous by construction of the derivation;
  - London and New York have 38 days of 82,800 s and 38 of 90,000 s;
  - the r2 known answers hold: New York 2026-03-08 and 2026-11-01, London 2026-03-29 and 2026-10-25, and Kolkata 2026-10-01 starting at 09-30T18:30Z;
  - **an exhaustive check over 2000–2037** shows a 92-day instant window touches at most 93 local dates in UTC, Kolkata and Tokyo, and 94 in London and New York, so the r2 bound of 376 daily rows holds. r2 had checked only 2026.

**Rejected:**
- Locking `tzdata` for all platforms: a lockfile change and new resolution, and it still yields a version that drifts with every lock refresh.
- Using PostgreSQL's zone data: a second rule source, with r2 §6's nonexistent and ambiguous-time issue.

## 3. Decision 2: capability and version compatibility

**Facts:**
- **Server types.** `Capability` (`src/sentinel/contracts/http_v1.py:21`) and `TrustedContext.capabilities` (`src/sentinel/contracts/v1.py:71`) are closed `Literal` sets of the four current values.
- **Validation happens at authentication.** `Sentinel.authenticate` (`src/sentinel/service.py:172`) builds `TrustedContext` from `api_sessions.capabilities`. That column is `text[]` with **no** CHECK, so an unknown stored value fails validation there and is never treated as a grant.
- **There is one `/v1/session` route and no version negotiation** (no header or media type selects v1.1 or v1.2). `scripts/export_http_contract.py` keeps v1 and v1.1 frozen by SHA, with v1.2 as the active revision.
- **The web client** (`web/src/api/client.ts:121`, `acceptSession`) accepts any capability strings, and checks only that each is a string. It already tolerates an unknown value.

**Proposal:**
1. **A new additive contract version, v1.3.** It contains:
   - `Capability` widened by `read_report`;
   - the S1 route `GET /v1/reports/{report_id}`;
   - the new errors 413 `report_too_large` and 503 `report_timeout`;
   - the reused 422 `invalid_cursor`.

   v1.2 then freezes by SHA, following the existing v1.1 pattern. The v1, v1.1 and v1.2 documents are never edited.
2. **Compatibility rule, stated in v1.3** (the documents are prose plus OpenAPI):
   - The server emits only values in its own version's enum.
   - Clients must treat `capabilities` as a set and **ignore values they do not recognize**. An unknown value grants nothing to the client; authority is enforced by the server per route.
   - A v1.0–v1.2 client that validates the enum strictly is incompatible with a session issued `read_report`. Operators must not issue `read_report` to sessions such clients use, and the `create-session --help` text says so.
3. **Issuance is unchanged from r2:**
   - only the operator CLI issues `read_report`;
   - it is not in `ALL_CAPABILITIES`;
   - repeated `--capability` flags give exactly the listed set;
   - no backfill, and no HTTP issuance.

   The runtime role still has only SELECT on `api_sessions`.
4. **The server keeps closed validation.** `TrustedContext` is widened by exactly `read_report` in the same change, so an unknown stored value still never authorizes.
   - Turning today's validation failure on an unknown stored value into a typed 401 is a separate hardening item. It is not part of S1, and it changes no current behaviour.

**Rejected:**
- Filtering `read_report` out of `/v1/session` for old clients: there is no negotiation to know which client is asking, and filtering would hide the permission from the UI that needs it.
- A separate "report access" route that keeps the enum frozen: it splits one authority view in two, for no safety gain.
- A major version bump: the change is additive.

**Acceptance cases added** (to r2's A9):
- a v1.3 `/v1/session` example containing `read_report` validates against v1.3 and is not added to the frozen v1.2 examples;
- a web-client unit test shows an unknown capability string is ignored rather than rejected (this behaviour exists today; the test pins it).

## 4. Decision 3: cursor integrity

**Proposal: keep cursors unsigned (r2 §2), tightened in four ways:**

1. **Length limit 256 characters (derived, not provisional).**
   - The encoding is fixed: the report ID, a 64-hex digest, a 27-character timestamp, a 36-character UUID and two counts.
   - The worst case is 228 characters at the 200,000 cap, and 231 for any count up to 9,999,999. So 256 holds even if AN01-M1 raises the cap by 50×.
   - Page-1 counts never exceed the cap, because a larger set is refused with 413 before any page is produced.
   - This replaces r2's provisional 400. `check_an01_r3.py` recomputes it.
2. **Strict members.** Each member must match exactly or the request gets 422 `invalid_cursor`:
   - `last_occurred_at` must match the normalized `YYYY-MM-DDTHH:MM:SS.ffffffZ` form, and lie inside the request window;
   - `last_id` must be a lowercase canonical UUID;
   - the counts must be integers in `0..cap`;
   - the digest must equal the request's recomputed `filter_digest`.
3. **The UI never takes a cursor from navigation.** No URL, history state or storage. It uses only the `next_cursor` of the response it is displaying, so a crafted link cannot hand an analyst a cursor that suppresses `row_set_changed`.
4. **The server documents** that a cursor's counts only feed the caller's own change flag, and that scope always comes from the token.

**Why not an HMAC:**
- The cursor carries no authority (r2 §2 tampering analysis): a forged one only selects a different page of the caller's own scoped rows.
- Signing would add a server secret. That brings storage, rotation, sharing across API processes and restarts, and a leak-handling story. Sentinel has none of that infrastructure, and adding it is not worth a protection with nothing to protect.

**Revisit trigger:** if a cursor ever references stored state, such as the deferred held snapshot (r2 §5), the server must check that state's session ownership. That ownership check, not a signature, is the control.

## 5. Decision 4: limits, and what the budget does and does not bound

### 5.1 Budget semantics (the review's requested distinction)

- **The S1 report budget is a database budget on this server process's monotonic clock.** It is not a promise about when the client receives a response.
- **It reuses the accepted pattern** in `src/sentinel/agents/budget.py`, `BoundedTransaction` (G3A design §3.2, R34 and R37):
  - one deadline is read after authentication, before the report connection is opened;
  - `connect_timeout` is derived from the remaining budget (whole seconds, at least 2, per the existing rule);
  - before every statement, `statement_timeout` and `lock_timeout` are set by `SET LOCAL` to `floor(end − now)` ms;
  - below the minimum, the request is refused and never armed with 0, which PostgreSQL would read as "no timeout";
  - the process stops waiting for a reply at the budget (`bounded_call`). A connection whose statement went unanswered is quarantined and never reused.
- **The report transaction ends with ROLLBACK, never COMMIT.**
  - It is `READ ONLY`, so there is nothing to commit.
  - This removes the CommitUncertain case entirely: `budget.py` notes that PostgreSQL disables `statement_timeout` before commit processing.
- **What 503 `report_timeout` means:** "this server stopped working on and waiting for the report's database work within its budget".
- **What the budget does not bound:**
  - the authentication query on its own connection;
  - request parsing;
  - JSON serialization;
  - network transfer;
  - the browser;
  - how quickly the PostgreSQL server notices a cancel;
  - when a quarantined connection is finally closed.

  Neither the API nor the UI says "results within 5 s".
- **The response DTO adds no timing field.** Measured elapsed time belongs to the AN01-M1 record, not to the contract.

### 5.2 The limits, with labels

| Limit | Value | Label | Basis |
| --- | --- | --- | --- |
| Window length | 92 × 86,400 s, or 92 local dates | policy | Product scope; it bounds output shape, not work |
| Output rows | totals ≤ 4; daily ≤ 94 buckets and ≤ 376 rows; quality 7; workload 1; drilldown ≤ 100 per page | derived | `check_an01_r3.py` (exhaustive over 2000–2037 for the daily bounds) |
| Cursor length | 256 characters | derived | §4 |
| Matching-row cap | 200,000 (413 above it) | **provisional** | Unmeasured. PERF01 measured the existing API, not report SQL, and cannot support it |
| Database budget | 5,000 ms per request | **provisional** | Unmeasured. The semantics of §5.1 are the proposal; the number is not |
| Per-process quarantine | the existing coordinator limit pattern | proposal | It is reused, not re-specified; AN01-M1 records how many connections cancel tests retire |
| Memory and temp files | not bounded by S1 | stated gap | `work_mem` applies per sort node; `temp_file_limit` is a superuser setting. AN01-M1 measures spills |

## 6. Decision 5: index strategy

**Query paths against the existing schema** (`src/sentinel/db/migrations/0001`–`0005`):

| Report part | Existing support | Gap |
| --- | --- | --- |
| Event-time window, keyset `(occurred_at, id)` | `transactions_velocity (tenant, session, account, occurred_at)` does not lead on `occurred_at` | **needs an index** |
| Outcome and alert joins | `scoring_outcomes` PK `transaction_id`; `alerts.transaction_id UNIQUE`; `cases.alert_id UNIQUE` | none |
| Cases created in window | `cases_session_listing (tenant, session, created_at DESC, id DESC)` | none (backward range scan) |
| Open now by state | `cases_session_state (tenant, session, state, created_at DESC, id DESC)` | none |
| Actions completed in window | only `UNIQUE (tenant_id, idempotency_key)`, and `completed_at` is in JSONB | **tenant-wide scan**; candidate index |

**Proposal: one draft migration, `0006`.**
- **`CREATE INDEX transactions_session_time ON transactions (tenant_id, session_id, occurred_at, id)`.**
  - It serves the window range and the drilldown order directly.
  - `ingested_at`, amount and direction stay heap filters. No covering columns, because every report reads `body` anyway.
- **Candidate `CREATE INDEX simulated_actions_session ON simulated_actions (tenant_id, session_id)`.**
  - It is included only if AN01-M1 shows the tenant-wide path costs more than 10% of the budget at the measured cap.
  - An expression index on `(body->>'completed_at')::timestamptz` is not possible, because that cast is not `IMMUTABLE`.
- **No generated amount or direction columns in S1.**
  - Adding a stored generated column rewrites the table under `ACCESS EXCLUSIVE`.
  - The benefit, avoiding JSONB extraction, is unmeasured.
  - AN01-M1 includes an extraction-cost probe. Only if extraction exceeds half of the report time at the cap is a separate generated-column decision opened.
- **Plain `CREATE INDEX` inside the migration's transaction**, matching 0003. It blocks writes while it builds, which is acceptable for the local synthetic product. AN01-M1 records build time at 1,000,000 rows.

## 7. Decision 6: UI staleness wording

There are two different situations, and r2's single "old as_of" state conflated them.

**1. An earlier cutoff is a filter, not staleness.**
- When the request's `as_of` is earlier than `read_at`, the header shows: **"Availability cutoff: {as_of}. Rows stored after this are excluded. Read at {read_at} (server time)."**
- There is no age threshold and no "old" or "out of date" label: the analyst chose it.
- The workload section keeps: **"Case states are as of the read time, not the cutoff."**

**2. Result age uses the browser's monotonic clock since the response arrived.**
- The client records `performance.now()` on receipt. It never compares the browser's wall clock with the server's `read_at`; clock skew is the lesson of G3C/R40.
- After **5 minutes (policy, a UI constant, not a data guarantee)** the header adds: **"Read {n} minutes ago. Data may have changed since. Refresh."**
- Before that it shows only "Read at {read_at} (server time)".
- The text never says "live", "current", "real time" or "up to date".

**3. Detected change overrides both.**
- When two displayed responses for the same filters carry different consistency pairs, or a page reports `row_set_changed`, the r2 "changed" text is shown immediately, with no timer.

These strings replace r2 §10's "Old as_of" row. Making them accessible (live region, not colour alone) follows r2 §10.

## 8. AN01-M1: bounded report-query measurement plan

**Purpose:** measure the *draft S1 report SQL* on synthetic data, so that the matching-row cap, the database budget and the index choice of §5–§6 can move from provisional to measured. It is one local measurement, like PERF01: not a capacity claim, not production hardware, and not tuning. **This plan is not run by this branch.**

### 8.1 What is measured

1. **The exact statements.**
   - The candidate SQL for each S1 report (`currency_totals`, `daily` UTC and New York, `workload`, `quality`, the drilldown's first page and a mid-set cursor page), plus the guard count and consistency pair.
   - They live in one measurement module, and each statement's SHA-256 is recorded.
   - The later S1 implementation must use byte-identical statements, which a unit test compares against the recorded digests, or AN01-M1 is repeated. This keeps the measurement bound to what ships.
2. **How it runs.** As the runtime role, in `REPEATABLE READ, READ ONLY`, through the §5.1 bounded-transaction path ending in ROLLBACK. That is a measurement-only copy that changes no `src/` code.
3. **The metrics:**
   - client elapsed time (`time.perf_counter`, including connect);
   - per statement, `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` in a separate pass: execution time, plan shape (index or seq scan), shared hits and reads, and sort method, including any external merge;
   - the `pg_stat_database.temp_bytes` delta per cell;
   - the server version and `work_mem`, `shared_buffers`, `jit` and `max_parallel_workers_per_gather`, all recorded and left at their defaults.

### 8.2 Data (synthetic, deterministic)

- **Owner and storage.** Generated from a fixed seed and loaded by `COPY` as the schema owner into a **disposable, test-owned cluster**, using the same ownership and cleanup discipline as the test `database_url` cluster.
- **It is labelled an operator fixture**, like r2's R14. It does not go through the API: 10^6 API requests would measure ingestion, which PERF01 covers, instead of report SQL.
- **Every body is contract-valid:**
  - USD 40%, INR 25%, GBP 20% and JPY 15%;
  - correct exponents, and `0 < minor_units ≤ MAX_MINOR_UNITS`, including a tail at the maximum;
  - 70% debit and 30% credit;
  - `occurred_at` uniform over the 92 days from 2026-07-01;
  - lag 1–60 s, with 0.5% over 1 h;
  - outcomes present for 99.9% (the rest score-unknown);
  - 2% alerted, each with an alert and a case in a mix of states;
  - 0.5% with succeeded simulated actions and a `completed_at`.
- **Sizes:**
  - the measured session holds N ∈ {10,000, 50,000, 100,000, 200,000}, plus 200,001 for the 413 guard path;
  - background rows in other sessions and tenants number B ∈ {0, 800,000}, so the total is at most 1,000,001.
- **Preflight refuses to start** with less than 5 GB of free disk, or if the generated cluster would exceed 3 GB.

### 8.3 Phases, in order, with hard caps

| Phase | Cells | Executions |
| --- | --- | --- |
| A, index choice | N 200,000, B 800,000. Variants: (A) existing indexes, (B) plus `transactions_session_time`, (C) B plus `simulated_actions_session`. All reports, base filters | 3 variants × 7 statements × (1 warm-up + 5) = 126 |
| B, cap curve | The chosen variant; N in {10k, 50k, 100k, 200k} × B in {0, 800k}. Filters: base; `as_of` excluding about 90% (index-scanned rows discarded in the heap); a single currency; New York `tz` (daily only) | at most 8 × 7 × 4 × 6 = 1,344, with inapplicable filters skipped and counted |
| C, refusal and cancellation | 413 at 200,001 (×5). A forced budget of 50, 100 and 250 ms on `quality` and `daily` at 200k (×5 each): time from deadline to error, whether the connection was quarantined, and that the next request on a fresh connection succeeds. A lock-wait case, where the owner holds `ACCESS EXCLUSIVE` on `transactions` in another connection (×3): `lock_timeout` → 503 | 5 + 30 + 3 = 38 |
| D, two clients | 2 concurrent closed-loop clients at N 200k, B 800k (quality + drilldown), 10 requests each | 20 |
| E, extraction probe | `currency_totals` against an id-only aggregate over the same rows at 200k (×5) | 10 |

- **Caps:**
  - every execution has a measurement budget of 10,000 ms, so slow cells are observed beyond the provisional 5,000;
  - **2,400 s of active measurement per platform**, inside the 2,700 s command cap, after which no new cell starts;
  - unstarted cells are listed as not run, never estimated;
  - setup (generation, COPY, index builds, with each index's build time recorded) is timed separately and capped at 900 s.
- **No retries.** A failed cell is kept as failed.
- **Platforms:** Windows, then native Ubuntu, **sequentially in the one heavy slot**, with the same seed and statement digests. Each platform's record names its exact commit and clean-tree state.
- **Cleanup:** the cluster is stopped and removed. On failure the state is kept and a recovery command printed, following PERF01.
- **Out of bounds:** no network, provider, auth, account, browser, final cases, ML holdout or agent-evaluation data, and no paid usage.

### 8.4 Pre-registered decision rules

These are written before any run, so the result cannot choose its own rule.

1. **Index.** Adopt variant B if, at N 200k and B 800k, it changes the transaction window plan from a sequential scan to an index scan, or halves the median time of any transaction report. Add variant C's index only by the 10% rule in §6.
2. **Matching-row cap.** N\* is the largest measured N for which, on the slower platform, with background 800k and the chosen indexes, **every** report and filter cell's maximum database time is at most 40% of the provisional budget (2,000 ms).
   - If N\* is less than 200,000, propose N\*.
   - If 10,000 fails, report it and propose a design change (the curated reporting role or pre-aggregation) instead of any cap.
   - The 200,001 guard cell must refuse with 413 within the budget.
3. **Budget.** The 5,000 ms ceiling stays unless the median deadline-to-error latency of phase C exceeds 10% of the budget, or phase D's maximum exceeds the budget. Either outcome opens a re-review; it does not quietly change the number.
4. **Spills.** Any temp-file spill at N\* is reported with its report and size, and S1 acceptance then needs an explicit `work_mem` statement.
5. **Generated columns.** These are considered only if phase E shows JSONB extraction is more than half of `currency_totals` time at N\*.
6. **What the result is called.** The limits become **"measured on one laptop, warm cache, synthetic distribution"** and stay labelled that way. They are inputs to Codex's contract decision, not guarantees.

### 8.5 Not measured by AN01-M1 (stated in its report)

- cold-cache behaviour (OS caches are not dropped, and a single after-restart sample is labelled);
- concurrent ingestion load;
- more than two report clients;
- production or other hardware;
- the network beyond loopback, and the browser rendering of 376 rows;
- Linux browser execution;
- data distributions unlike the generator's.

### 8.6 Proposed ownership when assigned

- **Owned:** `scripts/benchmark_reports.py`, `tests/test_report_benchmark.py` (generator determinism and contract validity, caps, statement digests, cleanup, using a small N) and `docs/benchmarks/AN01-M1.md`.
- **Unchanged:** `src/`, contracts, migrations, lockfiles, CI and the existing benchmark.
- **Effort.** Recommended assistant: Claude Opus 5.5 / High. It needs careful cleanup, cap and honesty handling, not maximum effort.

## 9. What this branch changes, and what review should check

- **New files:** `AN01-decisions-r3.md`, `AN01-zone-table.json`, `derive_an01_zones.py` and `check_an01_r3.py`.
- **Pointer lines** in the two r2 documents' open-question sections. The r2 text is otherwise unchanged.
- **No production endpoint, migration, contract, capability, lockfile, CI or UI change.**
- **For review:**
  - whether v1.3 additive versioning and the "ignore unknown capabilities" rule are acceptable;
  - whether the AN01-M1 grid, caps and decision rules are the right ones before it is assigned;
  - whether a 5-minute UI nudge is wanted at all.
