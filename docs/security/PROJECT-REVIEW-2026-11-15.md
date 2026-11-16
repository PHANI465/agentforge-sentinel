# Sentinel security and readiness review

Reviewed November 15, 2026 against **d583118a4d01af6c1df3a6aa36f928d6a7712603**.
This is a source/configuration review with targeted tests and read-only public checks,
not a complete penetration test or a certification of safety. Findings below remain open;
this task changes documentation, not application behavior or the deployed service.

**Assessment:** a useful, functioning research/portfolio demo with meaningful safeguards.
Address dependency advisories and public-service hardening next. Do not turn the local
parser into a customer upload service without stronger isolation and lifecycle controls.
No account takeover, cross-session disclosure or real credential leak was demonstrated
by this review. That statement is limited to the checks actually performed.

## Scope and trust boundaries

| Area | Reviewed evidence | Limit of this review |
| --- | --- | --- |
| Browser documents | File limits, PDF.js settings, Office extraction, worker cancellation, inert rendering, source/amount checks; real-file Chromium suite | No parser fuzzing, browser-engine audit or Safari/Firefox qualification |
| Hosted demo and IAF | Hosting wrapper, guest and IAF SQL, package script, public response headers, fixed passage selection | No production database access, new guest admission, paid provider call, load test or account/configuration audit |
| API and storage | Authentication, tenant/session predicates, grants, approvals, idempotency, traces, local document bridge | Targeted tests, not a line-by-line audit of every query and recovery branch |
| Local worker | Protocol, containment/recovery design, separately locked dependencies | Worker process tests not rerun; no hostile file corpus or OS sandbox assessment |
| ML and evaluation | Frozen p1 protocol/selection, trusted artifact loading, data and evaluation limits | No retraining, protected final-case evaluation, customer data or independent fraud-quality study |
| Release and supply chain | Lockfiles, vendored package provenance, tracked-file pattern scan, workflow and release source | No full Git-history/untracked-file secret scan; cloud permissions and all build-system dependencies not audited |

Browser documents do not flow into IAF, casework or OpenAI. Hosted casework uses synthetic
data and deterministic roles. The separate local upload API processes files through
MarkItDown-related worker dependencies. These are different attack surfaces.

## Prioritized findings

### SEC-01 — Known dependency advisories need a reviewed upgrade

**Priority: high maintenance action. Confirmed version matches; exploitability varies.**

OSV queries covered **289 unique package/version identities** from both Python locks,
the web lock and the two recorded browser parser versions. After correcting the initial
fflate inventory from a guessed 0.8.2 to documented 0.8.3, **8 package/version pairs**
matched advisories. Alias records are not separate vulnerabilities.

`npm audit --package-lock-only --ignore-scripts --json` independently returned exit 1:
three affected dependency nodes, two labeled critical and one moderate. Those npm labels
describe dependencies and transitive effects, not three demonstrated Sentinel exploits.

| Locked dependency | Context and required triage | Published patched version(s) |
| --- | --- | --- |
| `opentelemetry-api 1.45.1` | Present in the no-dev runtime export. Advisory concerns costly parsing of specially crafted trace context; no reachable Sentinel exploit was demonstrated. | `1.45.2` |
| `certifi 2026.7.22` | Both locks. Root application no-dev export does not include it; worker and developer dependency exposure still matters. The October 9 holdback excludes the later trust-store correction. | `2026.10.18` |
| `pytest 8.4.2` | Development/test tooling; unsafe temporary-directory handling. This is not a deployed web route. Current `<9` requirement needs a deliberate compatibility update. | `9.0.3` |
| `soupsieve 2.10 / 3.0.4` | Alternative worker-lock resolutions. Selector denial-of-service advisories; reachability through allowed worker formats was not established. | `4.0.0` covers all three reported advisories |
| `vitest / @vitest/mocker 3.2.7` | Development tooling: mock registration and file-read advisories. Do not expose test/dev servers publicly. | Mocker `4.1.12` or `5.0.3`; resolve a compatible Vitest toolchain |
| `tinypool 1.1.1` | Test-worker dependency. Prototype-pollution gadget advisories require attack prerequisites; not proof of browser-site RCE. | `2.1.2` covers both reported issues |

Sources: [OpenTelemetry advisory](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-mf5v-w3w3-f6cg),
[certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
[pytest advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g),
[Soup Sieve advisory](https://github.com/facelessuser/soupsieve/security/advisories/GHSA-mmhr-3c5m-f64f),
[Vitest advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8),
[Tinypool advisory](https://github.com/tinylibs/tinypool/security/advisories/GHSA-85c8-ppgw-ccpr).

**Action:** update the runtime dependency first, then separately resolve the worker and
test-tool upgrades. Review exceptions to old date holdbacks instead of treating old versions
as automatically safer. Do not run `npm audit fix --force` blindly. Preserve frozen app
contracts/model artifacts and rerun their gates after resolving dependencies. Scan deployed
requirements, vendored assets and build dependencies as separate inventories.

**Acceptance:** known applicable advisories are patched or have a documented, reviewed
non-exposure decision; locked installation, app and worker tests, schema checks, file-browser
tests and a staging smoke pass. No advisory was fixed by this documentation change.

### SEC-02 — Missing anti-framing response headers

**Priority: medium for the public demo; confirmed configuration gap.**

Read-only GETs to `/`, `/workbench/index.html` and `/iaf.html` returned neither
`Content-Security-Policy` nor `X-Frame-Options` response headers. The static reviewer does
have a restrictive **meta** CSP; it is not correct to say there is no CSP anywhere.
However, meta CSP cannot enforce `frame-ancestors`. The workbench hosting configuration
only adds `nosniff` and `no-referrer`. HTTPS/HSTS was present.

Source: [Vercel headers](../../hosting/vercel/vercel.json),
[reviewer meta policy](../../public_site/static/index.html).

**Impact:** pages are not explicitly protected against hostile framing. This can support
UI deception; no clickjacking exploit or stolen token was demonstrated.

**Action:** serve `frame-ancestors 'none'` (or an explicitly required embedding allowlist)
as an HTTP CSP header, add suitable `X-Frame-Options`, and apply `nosniff` and a referrer
policy consistently. Design the full workbench CSP against its actual script/style needs.
Check PDF workers and charts on staging; do not paste an untested policy into production.
Verify framing refusal from an unrelated test origin. [OWASP CSP guidance](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html).

### SEC-03 — Global caps are not visitor fairness or request rate limits

**Priority: medium, hosted availability. Source-confirmed limitation; no live exhaustion test.**

[Guest admission](../../hosting/vercel/guest.sql) correctly serializes its global limits
of 100 sessions/day and 1,000 stored sessions. [IAF quota](../../hosting/vercel/iaf-quota.sql)
also serializes 30 optional model calls/day and 300/month. A caller can nevertheless consume
a shared allowance. `Sec-Fetch-Site: same-origin` in the [wrapper](../../hosting/vercel/app.py)
is useful browser metadata, not authentication for non-browser callers. It must not be
treated as a bot-proof gate. No app-wide per-visitor/per-session request limiter was found.
Cloud firewall configuration was not inspected, so this is not a claim that Vercel has no defenses.

**Action:** retain global cost caps, add bounded per-client and per-session admission and
route limits, consider an abuse challenge, and monitor refusals. Use trusted proxy identity
rules rather than arbitrary forwarded headers. Test fairness and simultaneous admissions
against an owned staging service. Avoid sending load to the current public demo.
[OWASP resource-consumption guidance](https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/).

### SEC-04 — Release packaging does not enforce source/build correspondence

**Priority: medium, release integrity; source-confirmed gap.**

[package.ps1](../../hosting/vercel/package.ps1) archives backend paths from Git HEAD, but
copies hosting files, `public_site/static` and `web/dist` from the working filesystem.
It neither refuses a dirty/untracked source tree nor binds the built UI to that HEAD.
An accidental file in the static tree could be published; a stale `web/dist` could ship
under a newer source label. Existing manual release checks reduce this risk, but the
script does not enforce them. No evidence was found that the current release contains
private files or the wrong UI.

**Action:** release from a clean checkout with an allowlisted tracked-file manifest,
build the UI inside that checkout, verify build/source digests and scan the final package.
Add negative tests for dirty source, stale build and an unexpected static file. Preserve
manual deployment until an equivalent combined-release pipeline is verified.

### SEC-05 — Local parser containment is not a hostile-upload sandbox

**Priority: high before customer/server-upload expansion; already documented scope limit.**

The worker has size/time/process limits, recovery records and in-process restrictions.
Its Windows job object and POSIX resource limits do not provide OS-level filesystem and
network isolation. See [DOC01 boundary](DOC01-document-upload.md) and
[worker protocol](../documents/DOC01-worker-protocol-v0.1.md). The current public deployment
constructs `DocumentService(None)` and does not grant hosted visitors document analysis.
Browser review does not invoke this server parser.

**Action before public server uploads:** dedicated unprivileged sandbox per job, no outbound
network by default, no database/provider secrets, read-only runtime, narrow writable scratch,
resource limits, verified teardown, storage quotas and deletion evidence. Treat parser output
as untrusted even after isolation. [OWASP file-upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

### SEC-06 — Process-local admission cannot enforce a deployment-wide quota

**Priority: medium now; required before scaling expensive work.**

[Agent capacity](../../src/sentinel/agents/capacity.py) is explicitly process-local.
[DocumentService](../../src/sentinel/documents.py) likewise uses an in-process analysis
semaphore; shared recovery records do not constitute a global concurrency lease. Adding
API instances multiplies these capacities. Document cleanup, missing-PID launch records,
session quotas and retention need operational handling.

**Action:** use durable admission leases or a queue with bounded worker concurrency before
enabling expensive multi-instance provider/parser jobs. Specify lease expiry, recovery,
idempotent retries and per-tenant budgets; test worker and API restarts. Do not equate
increasing serverless instances with demonstrated capacity.

## Additional readiness gaps

- **Tenant defense in depth.** Application queries enforce scope and runtime grants restrict
  operations, but migrations do not enable database row-level security. A stolen runtime
  credential has broader row access than a user's bearer session. Before customer tenancy,
  choose/test RLS or stronger storage separation, including pooled-connection context reset.
  This is not evidence of a current API tenant bypass. [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).
- **Sensitive caching.** Token issuance and IAF explicitly use `no-store`; ordinary authenticated
  API responses do not set it in application code. The live unauthenticated `/v1/session`
  401 returned `public, max-age=0, must-revalidate`. No authenticated response cache leak was
  tested or observed. Add/test explicit private/no-store handling before private data.
- **Retention is not token expiry.** Synthetic session rows remain until operator cleanup.
  Local expired handles are not an autonomous deletion schedule. Define deletion of source,
  derived results, logs, backup copies and expired sessions separately; verify actual removal.
- **Database waiting and reads.** The coordinator has bounded SQL handling; ordinary reads,
  session admission and non-coordinator operations do not all share that mechanism. Add measured
  request/statement/lock/connection budgets and pagination before large tenant histories.
- **Browser resource limits.** Office ZIP expansion runs in a worker, but XML DOM parsing is on
  the main thread. Its bounded input does not establish a worst-case memory/latency guarantee;
  the UI's timeout cannot interrupt synchronous DOM work. Qualify deeply nested/malformed
  files, mobile memory and other browsers before raising limits.
- **Model trust.** Registered artifact hashes and trusted-root checks protect the accepted
  artifact. Never accept uploaded `joblib`/pickle models. A hash is not independent trust if
  an attacker can replace both the artifact and its approved manifest.
  [scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html).
- **CI and environment drift.** The repository contains a pinned backend workflow, but current
  docs say hosted Actions are disabled. A read-only CLI check could not authenticate, so the
  live Actions setting was not independently reconfirmed. Local passes are not hosted CI.
  Windows/native tests do not establish identical Vercel Python 3.12 behavior for every path.
- **Operational hygiene.** Rotate secrets on suspected exposure; do not share `.agent`, `.env`,
  session files or worktree caches. Keep reviewed failed evidence, but set an owner-approved
  retention policy for large temporary files. Low disk space has already affected past gates.
- **Evidence quality.** The earlier document browser run with an unexplained token-scan hit
  remains unresolved history; later clean scans do not explain it. See the Part C handoff/review.
- **Product/ML claims.** Supported document layouts and synthetic evaluation do not establish
  real fraud accuracy, document authenticity, financial loss prevented or regulatory compliance.
  A model reviewer is not an independent human evaluator. Keep Reports measurement and live
  agent quality evaluation explicitly unfinished.

## Safeguards confirmed in the reviewed paths

- Bearer tokens are random, hashed in storage, expire and are kept in UI memory. Service
  scope comes from authenticated records, not a model's choice of tenant.
- Parameterized values, restricted runtime grants, safe error/log fields and tenant/session
  queries protect important boundaries. A scoped parent lookup also protects related-ID reads;
  not every unscoped-looking internal query is independently exploitable.
- Approval binds to a case/intention revision; idempotent execution consumes approval once.
  Reviewer agreement is not human approval. All actions remain simulated.
- Browser text is rendered inertly, formulas are not executed, PDF eval is disabled, archives
  and outputs have limits, and cancel/context changes fence late results.
- IAF selects an allowed public passage ID. It does not emit arbitrary model narrative,
  receive document text, execute tools or authorize actions. Its database quota is shared
  across instances and failures fall back to library retrieval.
- The hosted service uses a dedicated guest-issuance function rather than an owner connection;
  its SQL functions fix `search_path` and revoke PUBLIC execution.

## Checks performed and evidence

Evidence is private in `.agent/security-review/` of the review worktree.

| Check | Actual outcome |
| --- | --- |
| Current source/configuration inspection | Named boundary files above; application unchanged |
| 5 read-only public GETs | Reviewer, workbench, IAF and health 200; unauthenticated session 401; headers recorded |
| OSV package inventory | 289 identities; 8 matched package/version pairs after fflate correction; metadata only sent externally |
| npm audit | Exit 1, three dependency nodes; no install/fix command run |
| Tracked text credential-pattern scan | 1,210 files under the size/type limits; four password-URL matches in three deliberate test files; no actual secret identified by these patterns |
| Node financial/evidence tests | 56 passed, zero skipped |
| Windows API/scope/approval/runtime-grant tests | 51 passed, zero skipped; owned disposable PostgreSQL; no external database |
| Windows Chromium file-to-browser suite | Passed 22 typed assertions across 14 scenarios, 24-file manifest, extra PDF/Word cases, malformed ZIP refusal, source focus, cancellation, layout, network and storage checks |

The initial incorrect fflate inventory is retained beside the corrected report; it is not
an outstanding fflate finding. Documented PDF.js 6.5.438 and fflate 0.8.3 had no OSV match
in this query. An empty advisory result is not proof of safety. The credential scan did
not cover every format, encoding, Git revision or deployment log.

This review does not claim a fresh full backend gate, Ubuntu run, worker gate, provider
quality evaluation, production load test or complete security audit. Browser/doc visual
verification outcomes are recorded in the accompanying review handoff.

## Recommended order

1. **Dependency remediation** with runtime/dev/worker exposure tracked separately.
2. **Public hardening**: anti-framing, sensitive-response cache policy, route fairness and monitoring.
3. **Release integrity**: clean source/build manifest, package scan, staging and verified rollback.
4. **Real-document validation** on permitted data with independent labels and field-level evidence.
5. **Customer-readiness design**: identity, tenant separation, sandbox, quotas, deletion, backup restore.
6. **Scale only after measurement**; keep the current demo caps until owned tests justify a change.
