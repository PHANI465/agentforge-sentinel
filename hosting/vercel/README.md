# Sentinel public workbench on Vercel

The production project uses the existing `web` root in Vercel. Release packages contain
FastAPI, the existing Vite app built for `/workbench/`, and the public PDF and replay site.
The Python app runs the rule scorer and deterministic three-role workflow. PostgreSQL
uses the free Neon resource `sentinel-demo-db`.

## Release

Run from the repository root. The stage directory must be fresh and outside the checkout.
Only the listed app sources, locked runtime dependencies and deliberate static files are
packaged. Keep GitHub auto-deploy disabled for this Vercel project so a web-only build
cannot replace the verified combined release.

```powershell
./hosting/vercel/package.ps1 -Destination '<new-release-parent>/web'
Set-Location '<new-release-parent>'
vercel deploy --prod --yes --archive=tgz --project agentforge-sentinel --scope pgavara1-3079s-projects
```

The packager refuses changes in the checkout and builds from a Git archive of the
resolved commit. It installs the locked web dependencies inside a fresh directory,
scans the output and writes `web-manifest.json` beside the upload directory. Verify
its source commit and file digests before using the package to stage a release.

For the request-limit release on an existing demo database, apply
[request-limits.sql](request-limits.sql) as the schema owner before staging.
Use the dedicated demo database, through a private connection. The migration
adds a table and one restricted function. The previous deployment continues to
work after migration, so rollback can target the prior ready deployment without
dropping the table. Bootstrap on a new database already installs the function.

Stage with `vercel deploy --prod --skip-domain` and keep the prior production
deployment ID. Verify the staging URL, run the hosted browser smoke and check
nosniff, anti-framing and no-store headers. Promote that deployment and recheck
the live alias. If the production checks fail, roll back to the recorded ID.

Pass the browser smoke an HTTPS origin and the installed modules directory:

```powershell
node hosting/vercel/smoke.mjs https://agentforge-sentinel.vercel.app web/node_modules
```

## Session authority and limits

`bootstrap.py` uses a one-time operator connection to apply the existing migrations,
create the repository's restricted runtime role and install `guest.sql` on a dedicated
demo database. Pass it `SENTINEL_HOSTED_OPERATOR_URL` and a private, new
`SENTINEL_HOSTED_RUNTIME_FILE` outside the deployment stage. Configure the resulting
connection only as the sensitive production variable `SENTINEL_HOSTED_DATABASE_URL`.
Do not deploy the bootstrap script, the credentials file, or an operator variable.

The guest-issuance function locks across instances and issues at most 100 sessions in
24 hours and 1,000 total until operator review. Tokens expire after 30 minutes. Guests
can investigate, approve and execute only in their own case scope. They cannot ingest
arbitrary transactions or submit documents to the API. The registration endpoint
returns a token only after all five canned transactions are seeded. This cap limits
resource usage but a single visitor could use multiple admissions. Synthetic records
are retained until operator cleanup.

The shared request limiter adds three guest starts and eight IAF requests per
visitor IP or IPv6 /64 each hour. API requests use 120 per visitor and 90 per
valid session each minute. Per-route global counters bound storage and admission.
Only Vercel's proxy-generated address header is trusted in hosting. The database
stores a keyed address digest for the active window. Every permitted guest or
IAF request still faces its pre-existing global quota. Limits use fixed windows
and apply across instances. Shared network addresses share allowances.

Rate-limit refusals use HTTP 429 with Retry-After. Admission failures return a
generic 503. The application request log does not capture guard refusals outside
the wrapped API, so track rates using hosted response status by route. Before
increasing traffic, verify limiter contention and budgets with an owned test.

PDFs use the static browser tool. This deployment deliberately uses no server parser,
paid model or account access. It is a public synthetic research demo.
