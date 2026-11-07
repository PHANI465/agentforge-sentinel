# AN01 r3: proposed resolutions of the six open decisions, and a report-query measurement plan

Audience: Codex, who decides whether the AN01 S1 contract can be frozen; then the backend and frontend implementers.

- **Status: revision r3.1.** It answers the review `task/coordination:docs/reviews/AN01-r3-b436c5e.md` (R50–R52) on the same branch, after `b436c5e`. It is a proposal: nothing is accepted, implemented or exposed. No route, migration, capability, contract document, script, lockfile, UI or CI change. AN01-M1 is not run.
- **Base:** main `c2140ce`, with the AN01-r2 documents (`a8c164a`). The review's supported policy decisions are applied as stated in §1.
- **Companion files:**
  - [AN01-zone-table.json](AN01-zone-table.json): the pinned zone table, now padded per R50;
  - [derive_an01_zones.py](derive_an01_zones.py): derives that table under review;
  - [check_an01_r3.py](check_an01_r3.py): recomputes every *derived* number below.

## 0. What r3.1 changes

| Finding | Change | Section |
| --- | --- | --- |
| R50 | The public UTC request domain is now kept apart from the padded local-date lookup range. The table covers every containing date and next-midnight sentinel. Lookups are strict, and date mode is validated after conversion. Both edges get known answers in all five zones, and the checker covers the whole domain. New digest | §2 |
| R51 | The measured unit is a complete report operation under one budget, and every SQL and control statement is enumerated and hashed. The plan is staged commands, each inside the unchanged 2,700 s cap, with an honest total bound. One index configuration is chosen jointly for both platforms. Phase E becomes a matched design comparison at N\*. Missing evidence means "not demonstrated" | §8 |
| R52 | Connection acquisition gets its own disclosed policy, outside the budget. The report budget starts after acquisition, with a report-specific ROLLBACK reserve. Admission and quarantine are finite and separate from the workflow registry. Refusal controls are separated from submitted-statement controls, with feasible budgets and proof of submission | §5, §8.3 |
| Policy | Opt-in v1.3 with explicit legacy-client incompatibility. Selectable CLI choices are separated from the unchanged default grants. Cursor counts must be coherent. The nudge now reads "Received {n} minutes ago". The cutoff applies to ingestion timestamps | §3, §4, §7 |

## How each number is labelled

| Label | Meaning |
| --- | --- |
| **derived** | Follows from the encoding, schema or committed data. `check_an01_r3.py` recomputes it, and it needs no performance measurement |
| **measured once** | Observed on this laptop by the command given; a fact about that environment only |
| **provisional** | A design number that no measurement supports. It stays provisional until AN01-M1 (§8) runs completely and Codex accepts the result |
| **policy** | A product choice, not a performance claim |

## 1. Summary of the proposed decisions

| # | Question | Proposed resolution | Label |
| --- | --- | --- | --- |
| 1 | Zone data | Runtime uses a committed five-zone midnight table, never host `zoneinfo`. Lookup dates are padded to 1999-12-31 .. 2038-01-02 for the UTC domain `[2000-01-01, 2038-01-01)`. IANA 2026e, sha256 `24e41cec…`. Lookups are strict | derived + measured once |
| 2 | Capability and version | **Opt-in** v1.3 adds `read_report` and freezes v1.2. This is **conditional compatibility**: strict legacy clients are incompatible with sessions that carry the new value. The CLI separates supported choices (five values) from the default grant (the unchanged four) | policy |
| 3 | Cursor | Unsigned, at most 256 characters (worst case 228). Canonical UUID and timestamp, exact integers (not bool), filter binding, and `0 <= with_outcome <= matching <= cap` | derived + policy |
| 4 | Limits and budget | A disclosed connection policy outside the budget. One monotonic report budget starts after acquisition, with a report ROLLBACK reserve. Admission and quarantine are finite and report-specific. The cap of 200,000 and budget of 5,000 ms stay **provisional** | provisional |
| 5 | Indexes | `transactions (tenant_id, session_id, occurred_at, id)`, plus a candidate `simulated_actions (tenant_id, session_id)`. Both are chosen by one joint cross-platform rule in AN01-M1. No generated columns | measurement-gated |
| 6 | Staleness wording | The cutoff filters **ingestion timestamps**. "Received {n} minutes ago" is timed from receipt with a 5-minute nudge, and is kept separate from the server's `read_at` | policy |

## 2. Decision 1: zone data, request domain and lookup range (R50)

### 2.1 Facts

- **The lock.** `tzdata` 2026.5 is locked only for `sys_platform == 'win32'` (`uv.lock`, as a dependency of `psycopg`).
- **Native Ubuntu** (WSL, Python 3.11.14): there is no `tzdata` module, and `zoneinfo` uses `/usr/share/zoneinfo` (Ubuntu `tzdata 2026e-0ubuntu0.24.04.1`).
- **Windows** (Python 3.11.3): `zoneinfo` uses the locked wheel, IANA 2026e.
- So the two platforms reach the same release today by different routes, and a host update can change Linux.

### 2.2 Two ranges, kept apart

| Range | Value | Role |
| --- | --- | --- |
| **Public request domain** | UTC instants `[2000-01-01T00:00:00Z, 2038-01-01T00:00:00Z)` | The only thing a request is validated against |
| **Lookup range** | Local dates `[1999-12-31, 2038-01-02]`, inclusive, in every zone | The dates the server may need to look up while serving a valid request. It is padding, not a request bound |

**Why the padding is needed** (derived; `derive_an01_zones.py` computes this from zoneinfo, and the checker from the table):
- **New York:** the lower edge 2000-01-01T00:00Z is local 1999-12-31 19:00. Its first bucket is local date **1999-12-31**, which starts at 1999-12-31T05:00Z.
- **Kolkata and Tokyo:** the last valid instant, 2037-12-31T23:59:59.999999Z, is local **2038-01-01**. Its bucket ends at the **2038-01-02** midnight: 2038-01-01T18:30Z in Kolkata and 2038-01-01T15:00Z in Tokyo.
- **UTC and London:** need 2000-01-01 through the 2038-01-01 sentinel. New York's upper sentinel is 2038-01-01T05:00Z.

The r3 table covered only 2000-01-01 .. 2038-01-01, so it missed New York's lower date and the Kolkata/Tokyo upper sentinel. Its checker extended the last offset by one day without proof. One shared padded range covers every zone.

### 2.3 Proposal

1. **Pin the table.** The committed table [AN01-zone-table.json](AN01-zone-table.json) has:
   - `lookup_dates` `[1999-12-31, 2038-01-02]`;
   - `request_domain_utc` recorded separately;
   - for each zone, ranges of `[first local date, UTC offset at local midnight, seconds]`;
   - sha256 `24e41cecb475453bb35e166abfc250610670593fd6ff0f324e0095eae274e165`, under domain `sentinel.report-zones.an01-s1.v2\n` over `{lookup_dates, ranges}`.
2. **Strict lookups.** The start of local date D is `D 00:00 UTC − offset(D)`, but only for D inside `lookup_dates`.
   - Outside that range the lookup is an error, and the request gets 422 `invalid_request`. It is never clamped, extrapolated from the last offset, or indexed below 0.
   - Host zone data, the `tzdata` wheel and PostgreSQL's `TimeZone` are never consulted at runtime.
3. **Validation order.** Validate after conversion. **Instant mode:**
   - parse `from` and `to`;
   - require `LOWER <= from < to <= UPPER` and the length limit.
   - Bucket lookups then always fall inside the table. The checker proves this for every window start in the domain.
4. **Date mode:**
   - require 1 to 92 local dates;
   - convert `date_from` and `date_to` by strict lookup, so a date outside the table is refused;
   - then require the *converted* instants to satisfy `LOWER <= from` and `to <= UPPER`.
   - Known answers:
     - New York `[1999-12-31, 2000-01-01)` is refused, because it converts to 1999-12-31T05:00Z, before `LOWER`;
     - New York `[2000-01-01, 2000-01-02)` is accepted;
     - Tokyo `[2037-12-31, 2038-01-01)` is accepted;
     - Tokyo `[2038-01-01, 2038-01-02)` is refused, because its converted end 2038-01-01T15:00Z is after `UPPER`;
     - Tokyo `[2038-01-02, 2038-01-03)` is refused at lookup, with no extrapolation.
5. **Edge buckets.** A bucket's `day_seconds` is its full local day, from the table. For New York's 1999-12-31 bucket that is 86,400 s, with `covered_seconds` 18,000, clipped to the domain. The day may extend outside the request domain, which is exactly why the table is padded.
6. **Provenance:** `tz_data = "an01-zones IANA 2026e sha256:24e41cec…"`.
7. **Changing the table** (a new tz release, or a wider allow-list) is a reviewed change:
   - run `derive_an01_zones.py --check` on Windows and native Linux;
   - on a difference, regenerate with `--write`, bump `report_version`, and get it reviewed.

   This is a manual command, **not** a gate test: a host with different zone data must neither fail nor skip the strict gate.
8. **Platform-independent gate test.** The implementation's unit test loads the table, recomputes its digest, and asserts the invariants and edge answers that `check_an01_r3.py` asserts here.
9. **No lockfile change.**

### 2.4 Evidence

**Measured once:**
- `derive_an01_zones.py --check` reports "matches the committed table" on Windows (tzdata wheel 2026e) and native Ubuntu (system zoneinfo 2026e).
- Both report the same digest `24e41cec…`, and both platforms' zoneinfo give the same required dates per zone.

**Derived** (`check_an01_r3.py`, 59 PASS, table only):
- **Edge answers.** Every zone's lower and upper edge known answers hold (the four edge rows in §2.2).
- **Whole domain.** All whole-hour window starts in the whole UTC domain, plus 1 µs before every local midnight and both edges, were checked. That is about 333,000 starts per zone, with windows `[t, min(t + 92 days, UPPER))`. There were zero uncovered lookups.
  - At most 93 local dates are touched in UTC, Kolkata and Tokyo, and 94 in London and New York, so the 376-row daily bound holds over the whole domain.
  - The r3 checker's sample stopped at 2037-09-01.
- **Strictness.** Lookups of 1999-12-30 and 2038-01-03 are refused, and an instant before the table has no containing date: there is no negative index.
- **Date mode.** The known answers above hold. Every accepted 1-date and 92-date request, from every start date, converts with in-table lookups.
- **r2 known answers are unchanged:** New York 2026-03-08 and 2026-11-01, London 2026-03-29 and 2026-10-25, and Kolkata 2026-10-01 starting at 09-30T18:30Z.

**Failing first.** `check_an01_r3.py --coverage-only --table <b436c5e table>` fails exactly seven explicit checks, with no import or exception failures:
- New York's lower edge (2 checks);
- the Kolkata and Tokyo upper sentinels (2 checks each);
- the whole-domain coverage check, with 4,621 uncovered window starts.

The unchanged b436c5e checker still passes the b436c5e table (23/23), which shows the gap it missed. The evidence is in the branch's ignored `.agent/an01-r3-fix/`.

**Rejected:**
- Locking `tzdata` on all platforms: a lockfile change, and the version drifts with lock refreshes.
- PostgreSQL zone data: a second rule source.
- Shrinking the request domain to fit the old table: it would still need padding in some zone at one edge.

## 3. Decision 2: capability and version compatibility

**Facts:**
- `Capability` (`src/sentinel/contracts/http_v1.py:21`) and `TrustedContext.capabilities` (`src/sentinel/contracts/v1.py:71`) are closed sets of four values.
- `Sentinel.authenticate` (`src/sentinel/service.py:172`) validates `api_sessions.capabilities` (`text[]`, no CHECK) into `TrustedContext`. An unknown stored value fails validation and is never a grant.
- There is one `/v1/session` route and no version negotiation. `scripts/export_http_contract.py` freezes v1 and v1.1 by SHA, and v1.2 is active.
- `web/src/api/client.ts:121` (`acceptSession`) accepts any capability strings.
- **CLI:** `ALL_CAPABILITIES` (`src/sentinel/cli.py:14`) is used for **both** the argparse `choices` (`:24`) and the default grant (`:76`).

**Proposal:**
1. **Opt-in v1.3.** It adds:
   - `Capability` widened by `read_report`;
   - `GET /v1/reports/{report_id}`;
   - the errors 413 `report_too_large`, 503 `report_timeout` and 409 `report_capacity_exhausted` (§5.3);
   - the reused 422 `invalid_cursor`.

   v1.2 freezes by SHA, following the v1.1 pattern. v1, v1.1 and v1.2 are never edited.
2. **Conditional compatibility, stated plainly.** This is **not** an unconditionally backwards-compatible enum addition.
   - A default session is unchanged, so every v1.x client keeps working with it.
   - A session issued `read_report` returns a value outside the v1.0–v1.2 enum, so **strict legacy clients are incompatible with such sessions**.
   - v1.3 says clients should ignore capability values they do not recognize. Sentinel's web client already does. An unknown client-side string never authorizes anything: the server enforces authority per route.
   - Operators issue `read_report` only to clients that follow v1.3, and the `create-session --help` text says so.
3. **CLI: choices and defaults separated.**
   - `SUPPORTED_CAPABILITIES` holds the five values, including `read_report`, and drives argparse `choices`.
   - `DEFAULT_CAPABILITIES` holds exactly today's four values and is used when no `--capability` is given.
   - Repeated `--capability` flags give exactly the listed set, for example `--capability read_case --capability read_report`.

   Removing `read_report` from a single shared constant would make it unselectable, so the two constants are required. There is no backfill and no HTTP issuance, and the runtime role keeps only SELECT on `api_sessions`.
4. **The server keeps closed validation.** `TrustedContext` is widened by exactly `read_report` in the same change.
   - Turning today's failure on an unknown stored value into a typed 401 is a separate hardening item. It is not in S1, and current behaviour is unchanged.

**Rejected:**
- Filtering `/v1/session` per client: no negotiation exists.
- A separate report-access route: it splits one authority view.
- A major version: the change is opt-in and additive for default sessions.

**Acceptance cases** (added to r2 A9):
- a plain `create-session` grants exactly the four defaults;
- `--capability read_report` is accepted, and its session has exactly the listed set;
- a v1.3 `/v1/session` example with `read_report` validates against v1.3 and is not added to the frozen v1.2 examples;
- a web-client unit test pins that an unknown capability is ignored.

## 4. Decision 3: cursor integrity

Cursors stay unsigned, as in r2 §2.

1. **At most 256 characters (derived).** The worst case is 228 at the 200,000 cap, and 231 for any count up to 9,999,999. Over-long input gets 422 `invalid_cursor` before any decoding.
2. **Strict, coherent members.** Every rule below must hold, or the request gets 422 `invalid_cursor`:
   - exactly six members;
   - the report ID is `"rows.transactions"`;
   - the digest is 64 lowercase hex characters and equals the request's recomputed `filter_digest`;
   - `last_occurred_at` matches `YYYY-MM-DDTHH:MM:SS.ffffffZ` exactly and lies inside `[from, to)`;
   - `last_id` is a canonical lowercase UUID;
   - both counts are **exact integers** (`type(v) is int`; JSON `true` and `false` are refused);
   - the counts satisfy **`0 <= with_outcome <= matching <= cap`**.
3. **The UI never takes a cursor from navigation.** It uses only the `next_cursor` of the response it is showing.
4. **Scope comes only from authentication.** A forged cursor only selects a different page of the caller's own rows, or makes the caller's own change flag wrong.

**No HMAC.** It would add a server secret, with storage, rotation, sharing across processes and leak handling, to protect a value with no authority.

**Revisit trigger:** a cursor that references stored state, such as the deferred held snapshot. The control is then a server-side ownership check, not a signature.

## 5. Decision 4: connection, budget, admission and cleanup (R52)

### 5.1 Facts about the existing helpers (`src/sentinel/agents/budget.py`)

- **Connecting is synchronous.** `open_connection` (`:357`) calls `psycopg.connect` synchronously, with `connect_timeout` in whole seconds and at least `LIBPQ_MIN_EFFECTIVE_S` = 2. It refuses outright when that does not fit the remaining budget.
  - `bounded_call` wraps only operations on an **already-open** connection.
  - So the existing pattern gives connection acquisition **no** absolute monotonic deadline. The review's fault-injected connector returned after 2,344 ms against a 2,100 ms deadline.
- **Statement minimum.** `MIN_DB_MS` = 100: a statement budget below 100 ms is refused, never armed.
- **ROLLBACK waits only to the end of its own phase.** `BoundedTransaction.rollback` (`:463`) waits at most `min(cap, available(phase))`, so a working-phase transaction gets no reserve for it.
- **The quarantine is shared with workflows.** `QUARANTINE` (`:76`, `:103`) is one process-wide registry, filled by `_Lease.retire` inside `bounded_call`. The coordinator refuses new workflows while `QUARANTINE.count() >= max_live_workflows_per_process` (default 1; `coordinator.py:745`).
  - Reusing `bounded_call` unchanged would let one abandoned report connection block investigations.
- **Ordinary connections.** `db.connect` uses `CONNECT_TIMEOUT_SECONDS = 10` (`src/sentinel/db/__init__.py:13`).

### 5.2 Proposal

The review's preferred option: a separate connection policy, then one report budget starting after acquisition. No production change is made now. Items marked *(implementation)* are code changes for the later, separately reviewed S1 implementation.

1. **Connection acquisition is outside the report budget, and disclosed as such.**
   - The report connection uses `psycopg.connect(url, connect_timeout=2, …)`, and single-host URLs only (`single_host`).
   - Its duration is measured and logged, but it is **not** counted in the report budget, and **no absolute bound on acquisition is claimed**.
   - libpq applies `connect_timeout` per connection attempt. DNS resolution and multiple addresses for one host name are not bounded by it.
   - Connection waits are bounded in number, not duration, by admission: the slot is taken before connecting (point 4).
   - **Rejected:** a separately bounded connect, such as a connect thread with an abandonment registry. It would need its own late-operation capacity design and proof, which S1 does not need for a loopback local database.
2. **One report deadline per request, started immediately after the connection returns.** It is monotonic, with total `B` (provisional 5,000 ms) and a **report ROLLBACK reserve `R`** (provisional 250 ms). `R` is report-specific: the workflow's 5 s terminal reserve is not inherited.
   - **Work phase:** ends at `B − R`. Each statement, including the first, is armed by `SET LOCAL statement_timeout/lock_timeout = floor(work_end − now)`. Below `MIN_DB_MS`, that statement is **not submitted** (refused before submission).
   - **Statement waits:** each statement's reply is awaited at most until `work_end` (`bounded_call`).
   - **ROLLBACK:** sent after the last statement, or on any error. It is awaited until `B`, the reserve end. *(implementation: the existing `rollback` waits only to its own phase end, so the report path must measure ROLLBACK against `B`.)*
3. **The transaction.**
   - The connection attributes `isolation_level = REPEATABLE READ` and `read_only = True` make psycopg's implicit `BEGIN` carry both.
   - `read_at` is read from the application clock just before the first armed statement, which establishes the snapshot.
   - The transaction always ends with **ROLLBACK, never COMMIT**.
4. **Finite admission, per process.**
   - At most `M` report operations may be active at once (provisional 2), counted from **before** the connection attempt.
   - At most `Q` connections may sit in the **report quarantine** (provisional 2).
   - A request arriving at either limit is refused with 409 `report_capacity_exhausted` (new, draft). Nothing is connected or submitted, and no wait is taken. This follows the existing `agent_capacity_exhausted` convention.
5. **A separate quarantine registry.** Retired report connections go into a report-specific registry, so workflow admission never counts them and report admission never counts workflow connections. *(implementation: `bounded_call`/`_Lease` would take the registry as a parameter, defaulting to today's `QUARANTINE`. That is a reviewed change to `budget.py`, with workflow behaviour unchanged.)*
6. **Cleanup ownership.**
   - **Normal path:** the request code owns the connection and closes it after ROLLBACK, including after an answered error.
   - **Retired connections:** a connection retired by a no-reply is owned by its lease. The last user to leave, whether the SQL worker or the cancel helper, closes it once and releases it from the report registry. This is the existing R37 mechanism, and the socket is shut down at retirement.
   - **Process exit** closes all remaining sockets. The server cleans up its backends independently.

### 5.3 What each outcome means

| Outcome | When | Statement submitted? | Connection | HTTP |
| --- | --- | --- | --- | --- |
| Admission refused | `M` active or `Q` quarantined | none, and no connection attempt | none | 409 `report_capacity_exhausted` |
| Connection failed | connect error, or libpq timeout | none | none | the existing database-error path; **not** `report_timeout` |
| Refused before submission | work budget below 100 ms before any statement | **no** (that statement) | ROLLBACK, closed | 503 `report_timeout` |
| Server cancelled | `statement_timeout` fired, and the server answered | yes | ROLLBACK, closed | 503 `report_timeout` |
| Lock timeout | `lock_timeout` fired, and the server answered | yes | ROLLBACK, closed | 503 `report_timeout` |
| No reply | no reply by `work_end` | yes, or uncertain | retired to the report quarantine | 503 `report_timeout` |
| ROLLBACK unanswered | every statement answered; no ROLLBACK reply by `B` | — | retired | 200 with the report, because every read was answered in its snapshot |

- The server log records which row applied. The DTO does not, and it adds no timing field.
- **What the budget bounds:** this process's database work and its waiting, from acquisition to ROLLBACK.
- **What it does not bound:** connection acquisition, authentication, parsing, serialization, network transfer, the browser, server-side cancel latency, or when a quarantined connection finally closes. Neither the API nor the UI promises a response time.

### 5.4 Limits, with labels

| Limit | Value | Label |
| --- | --- | --- |
| Window length | 92 × 86,400 s, or 92 local dates | policy |
| Output rows | totals ≤ 4; daily ≤ 94 buckets and ≤ 376 rows; quality 7; workload 1; drilldown ≤ 100 per page | derived (whole domain) |
| Cursor length | 256 characters | derived |
| Connection timeout | 2 s per libpq attempt, outside the budget | policy, measured in M1 |
| Matching-row cap | 200,000 (413 above it) | **provisional** |
| Report budget `B` | 5,000 ms | **provisional** |
| ROLLBACK reserve `R` | 250 ms | **provisional** |
| Admission `M` and quarantine `Q` | 2 and 2 per process | **provisional** |
| Memory and temp files | not bounded by S1 | stated gap; M1 measures spills |
| Workload rows | not covered by the transaction cap; bounded only by `B` | stated gap; M1 measures it |

## 6. Decision 5: index strategy

**Query paths against the existing schema** (migrations 0001–0005):

| Report part | Existing support | Gap |
| --- | --- | --- |
| Event-time window, keyset `(occurred_at, id)` | `transactions_velocity` does not lead on `occurred_at` | **index needed** |
| Outcome and alert joins | `scoring_outcomes` PK, `alerts.transaction_id UNIQUE`, `cases.alert_id UNIQUE` | none |
| Cases created in window | `cases_session_listing (tenant, session, created_at DESC, id DESC)` | none |
| Open now by state | `cases_session_state` | none |
| Actions completed in window | only `UNIQUE (tenant_id, idempotency_key)`, and `completed_at` is in JSONB | tenant-wide scan; candidate index |

**Proposal: one draft migration, `0006`.**
- **`transactions_session_time (tenant_id, session_id, occurred_at, id)`.**
- **Candidate `simulated_actions_session (tenant_id, session_id)`.** An expression index on `(body->>'completed_at')::timestamptz` is impossible, because that cast is not `IMMUTABLE`.
- **Both are chosen by the joint rule in §8.4**, one configuration for both platforms.
- **No generated amount columns.** Adding one rewrites the table under `ACCESS EXCLUSIVE`. The §8 phase E design comparison can only *open a separate review*.
- **Plain `CREATE INDEX` in the migration transaction,** as in 0003. M1 records build time.

## 7. Decision 6: UI wording

1. **The cutoff is a filter on ingestion timestamps.** When `as_of` is earlier than `read_at`, the header shows:
   - **"Cutoff: includes rows stamped ingested at or before {as_of}. Rows stamped earlier can still commit later, so a later read may show more. Server read at {read_at}."**
   - There is no "old" label.
   - The workload section adds: **"Case states are as of the server read time, not the cutoff."**
2. **Receipt age.** The client stores `performance.now()` when the response arrives, and never computes browser wall clock minus `read_at`.
   - The header always shows **"Server read at {read_at}"**.
   - After **5 minutes** (policy, a reversible UI constant, not a freshness guarantee) it adds **"Received {n} minutes ago. Data may have changed since. Refresh."**
   - It never says "live", "current", "real time" or "up to date".
3. **Detected change overrides both,** with no timer. This happens when two displayed responses for the same filters carry different consistency pairs, or when a page reports `row_set_changed`.

These are vocabulary decisions for the later UI slice. No UI is changed or assigned.

## 8. AN01-M1: bounded report-query measurement plan (R51)

**Purpose:** measure the draft S1 report operations on synthetic data so that the cap, `B`, `R`, `M`/`Q` and the index choice can become *measured on one laptop*. It is not a capacity claim, and **this plan is not run**.

### 8.1 The measured unit: one complete report operation

One **operation** is everything one request does after admission. The connection is timed separately and is outside `B`. The operation's elapsed time runs from the implicit `BEGIN` to the ROLLBACK reply, under one budget `B`.

**Control statements** (fixed text, hashed):
- `K0` is psycopg's `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`, sent before the first statement.
- `Ka` is `SELECT set_config('statement_timeout', $1, true), set_config('lock_timeout', $1, true)`, sent before **every** SQL statement.
- `Kr` is `ROLLBACK`.

**The seven operations and their ordered sequences** (each `S` is preceded by its `Ka`):

| Operation | Sequence | SQL statements |
| --- | --- | --- |
| `totals` | K0, G guard, P consistency pair, Q currency totals, Kr | 3 |
| `daily_utc` | K0, G, P, Q daily (boundary instants as parameters), Kr | 3 |
| `daily_ny` | as `daily_utc`, with New York boundaries (DST-length days) | 3 |
| `workload` | K0, Q1 created in window by state, Q2 actions completed, Q3 open now by state and age, Kr | 3 (no guard: there is no transaction set) |
| `quality` | K0, G, P, Q1 the four count checks, Q2 lag quantiles (`percentile_disc`), Kr | 4 |
| `drill_first` | K0, G, P, Q page (`LIMIT limit+1`, joins), Kr | 3 |
| `drill_cursor` | K0, G, P, Q page after a mid-set cursor, Kr | 3 |

That is 22 SQL statements and 3 control texts.

**Hashes.**
- Each statement's SHA-256 is taken over its exact UTF-8 text with placeholders. Each operation has a digest over its ordered statement digests.
- The later implementation must reproduce identical digests, checked by a unit test, or M1 is repeated.
- Every statement carries a constant tag comment, `/* an01-m1:<op>:<S> */`, so a server-side observer can prove submission (§8.3 phase C).

**Measurement budget.** Phases A, B, D and E run every operation under a measurement budget of `B` = 10,000 ms, with `R` = 250 ms, so that slow operations are observed rather than cut off at the provisional 5,000 ms. The decision rules compare the results against the provisional `B`. Phase C sets its own budgets.

**Repetitions per cell:** one warm-up (recorded, not used), then **5 timed operations**, then **one separate EXPLAIN pass**.
- The EXPLAIN pass runs `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for each SQL statement of the operation, in its own read-only transaction, after the timed runs.
- It is never part of a timed run, but its time is counted in the stage's command budget.
- Per-statement EXPLAIN times are **diagnostics only**. Every decision uses complete-operation times.

### 8.2 Data (synthetic, deterministic)

- **Generation and loading.** Generated from a fixed seed, and loaded by `COPY` as the schema owner into test-owned clusters.
  - It is labelled an operator fixture, like r2's R14, and does not go through the API.
  - Every body is contract-valid, with the distribution of r3 §8.2: currencies 40/25/20/15, a tail at `MAX_MINOR_UNITS`, 70% debit, 92 days from 2026-07-01, lag 1–60 s with 0.5% over 1 h, 99.9% with an outcome, 2% alerted with cases, and 0.5% with actions.
- **Two datasets per platform, each in its own owned cluster:**
  - **D1:** one tenant with five measured sessions of 10,000, 50,000, 100,000, 200,000 and 200,001 rows, 560,001 in total. Each session is the others' background, and the report says so.
  - **D2:** D1 plus 800,000 rows in eight other tenants, 1,360,001 in total.
- **Preflight** refuses to start with less than 8 GB free, or if the clusters would exceed 4 GB together.

### 8.3 Phases

| Phase | On | Cells | Operation runs |
| --- | --- | --- | --- |
| **A, index** | D2, 200k session, variants A (existing), B (+transactions), C (B + simulated_actions) | 3 × 7 operations | 3 × 7 × 6 = 126, plus 21 EXPLAIN passes |
| **B, cap curve** | The **common** variant; D1 and D2; sessions 10k, 50k, 100k and 200k. Filters for the six transaction operations: base, `as_of` excluding about 90%, single currency. Workload has base only | 2 × 4 × (6 × 3 + 1) = 152 cells | 912, plus 152 EXPLAIN passes |
| **B-guard** | D2, 200,001 session, six transaction operations | 6 cells | 6 × 5 = 30, each expected to return 413 |
| **C, controls** | D2, 200k, common variant | see below | 37, plus 1 drain check and 1 admission-refusal request |
| **D, two clients** | D2, 200k: `quality` and `drill_first`, 2 concurrent clients | 1 cell | 20 |
| **E, design comparison** | D2, the selected **N\*** session: `totals` and `daily_utc` under the JSON design, and under a measurement-only **shadow table** with real `currency`, `direction` and `minor_units` columns (same rows, filters, index and statements otherwise) | 2 × 2 | 24, plus 4 EXPLAIN passes |

**Phase C keeps refusal controls separate from submitted controls.** The connection is acquired before the budget starts, so the 2 s connect minimum does not apply to these budgets.

| Control | Budget | Expected | Proof |
| --- | --- | --- | --- |
| C1, refusal before submission | `B` = 300 and 349 ms, so the work budget (`B − R`) is 50 and 99 ms (×5 each) | Refused at the first `Ka`, because the work budget is below `MIN_DB_MS` 100. 503, no statement sent | The client's statement counter is 0, and an owner observer sees no tagged statement |
| C2, submitted and cancelled by the server | `B` = 400, 700 and 1,250 ms (`R` = 250, so a work budget of at least 150 ms) | The tagged control statement `SELECT pg_sleep(5) /* an01-m1:C2 */` runs inside the report transaction, and `statement_timeout` → QueryCanceled is answered. The connection is closed normally, not quarantined. ×5 each | The observer sees the tagged statement `active` before the deadline. Measured: deadline-to-error latency |
| C3, submitted and lock timeout | The same three budgets (×3 each) | The owner holds `ACCESS EXCLUSIVE` on `transactions`, and `totals` is submitted: LockNotAvailable or QueryCanceled, recorded as whichever fired | The observer sees the tagged statement waiting on the lock |
| C4, submitted with the reply withheld | `B` = 1,250 ms (×3) | An owned loopback relay between client and server stops forwarding server-to-client bytes after the tagged statement. NoReply at `work_end`; the connection is retired into the **report** registry | The relay logs that it forwarded the statement. After the third run, `Q` = 2 is full, and the **next request is refused with 409 before connecting**. After the relay closes, the registry drains to 0 |

Phase C totals 10 + 15 + 9 + 3 = 37 operation runs, plus 1 drain check and 1 admission-refusal request. These test the measurement harness's copy of the §5.2 design. Equivalence with production code is an implementation-review item.

### 8.4 Schedule, joint selection and pre-registered rules

**Staged commands.** Each stage is a separate command inside the **unchanged 2,700 s command cap**. Existing verification and application timeouts are not changed.
- **Inside each stage**, on one monotonic clock from the command's start:
  - setup (cluster start, generation, COPY, ANALYZE and index builds) is capped at 900 s, and counts toward the same clock;
  - **no new operation or EXPLAIN pass starts after 2,300 s**;
  - one operation runs at most about 12.3 s (a 2 s connect, plus 10 s of work, plus a 0.25 s reserve);
  - a 300 s cleanup reserve follows.

  So 2,300 + 13 + 300 = 2,613 s is less than 2,700 s.
- **Checkpoint:** a checkpoint file records completed cells and every digest.
- **Owned recovery:** `recover --run-dir` stops only clusters carrying this run's ownership marker, and prints what it kept.
- **No automatic resume, and no retries.** An unstarted cell is listed as **not run**, never estimated. Failed cells are kept.

| Step | Where | What |
| --- | --- | --- |
| S1 | Windows, then native Ubuntu | Prepare D2 (variant A) |
| S2 | Windows, then native Ubuntu | Phase A, including index build times |
| S3 | offline | Select the **one common** configuration from both phase A records (rule 1) |
| S4 | Windows, then native Ubuntu | Prepare D1, and apply the common configuration to D1 and D2 |
| S5a | Windows, then native Ubuntu | Phase B on D1 |
| S5b | Windows, then native Ubuntu | Phase B on D2, and B-guard |
| S6 | Windows, then native Ubuntu | Phases C and D |
| S7 | offline | Select **N\*** from both phase B records (rule 2) |
| S8 | Windows, then native Ubuntu | Phase E at N\* |
| S9 | offline | Final report, then `cleanup` on each platform |

- **Heavy slot.** All platform stages run one at a time in the one heavy slot, never on both platforms together.
- **Worst-case total.** Each platform has seven stages (S1, S2, S4, S5a, S5b, S6 and S8). Seven stages × 2 platforms × 2,700 s = 37,800 s, plus about 600 s for the offline steps and cleanup. That is **at most about 10.7 hours**, and is expected to be far less. A stage that runs out of time leaves its unstarted cells not run; it is not silently extended.

**Pre-registered rules.** These are fixed before any run, and are applied to complete operations.
1. **Common index configuration (S3).**
   - Variant B is adopted if, on **at least one** platform, it turns the transaction-window plan from a sequential scan into an index scan or halves a transaction operation's median, **and** on the other platform no operation's median is more than 10% slower than under A.
   - C's extra index is added only if, under the same two-platform condition, it improves the `workload` median by at least 10% of `B` (500 ms).
   - Otherwise the variant is A or B.
   - One configuration is then used everywhere. An unmeasured variant can never be chosen, and there is no per-platform tuning.
2. **Matching-row cap (S7).** N\* is the largest measured session size for which, **on both platforms**, in **both** datasets, for **every** operation cell:
   - all 5 timed **complete-operation** times are at most 40% of `B` (2,000 ms);
   - no run timed out.

   In addition, every B-guard cell must return 413 within `B`.
   - If N\* is below 200,000, propose N\*.
   - If 10,000 fails, propose a design change instead of a cap.
   - Per-statement times never qualify a size.
3. **Budget, reserve and admission.**
   - `B` stays 5,000 ms unless the C2 or C3 median deadline-to-error latency exceeds 10% of that cell's budget, or the D maximum exceeds `B − R`.
   - `R` stays 250 ms unless any C2 or C3 ROLLBACK exceeds 50% of `R`.
   - `M` and `Q` stay 2 unless C4's admission or drain checks fail.
   - Any trigger opens a re-review and never quietly changes a number.
4. **Spills.** Any temp-file spill at N\* is reported, and S1 acceptance then needs an explicit `work_mem` statement.
5. **The phase E design comparison.** It compares the JSON design with a columns design on matched rows, filters, index and statements, at **N\***.
   - Only if the columns design's median operation time is at most 50% of the JSON design's on **both** platforms does it open a separate review of generated columns.
   - It is reported as the difference between two designs. It assigns **no causal percentage** to JSON extraction, which also differs in row width and pages.
   - No generated column is assigned by M1.
6. **Mandatory evidence, or "not demonstrated."**
   - Mandatory: all phase A cells on both platforms, every phase B cell at every size up to a candidate N\*, the B-guard cells, and C1–C4 on both platforms.
   - A limit whose mandatory evidence is missing, failed or not run is **not demonstrated** and stays provisional. A size with any missing cell cannot be N\*.
   - D and E are mandatory for their own rules only.
7. **What the result is called.** "Measured on one laptop, warm cache, synthetic distribution": an input to Codex's contract decision, never a guarantee.

### 8.5 Not measured by AN01-M1

- cold-cache behaviour, beyond a single labelled after-restart sample;
- concurrent ingestion;
- more than two clients;
- other hardware;
- the network beyond loopback;
- browser rendering;
- Linux browsers;
- distributions unlike the generator's;
- production equivalence of the harness's copy of the §5.2 controls.

### 8.6 Proposed ownership when assigned

- **Owned:** `scripts/benchmark_reports.py`, `tests/test_report_benchmark.py` (generator validity and determinism, caps, statement digests, stage and checkpoint behaviour, ownership and cleanup, using a small N) and `docs/benchmarks/AN01-M1.md`.
- **Unchanged:** `src/`, contracts, migrations, locks, CI and the existing benchmark.
- **Effort.** Recommended assistant: Claude Opus 5.5 / High.

## 9. Scope of this branch

- **Files:** `AN01-decisions-r3.md`, `AN01-zone-table.json`, `derive_an01_zones.py`, `check_an01_r3.py`, one pointer line in each r2 document, and the branch handoff.
- **No production endpoint, migration, contract, capability, script, lockfile, CI or UI change.**
- **Still provisional:** the cap of 200,000, `B` 5,000 ms, `R` 250 ms, and `M`/`Q` of 2/2.
- **Policy:** the 5-minute nudge, the 2 s connect timeout, and the 92-day window.
