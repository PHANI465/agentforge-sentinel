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
Set-Location web
npm ci
npm run typecheck
$env:VITE_SENTINEL_HOSTED_DEMO = '1'
node node_modules/vite/bin/vite.js build --base /workbench/
Remove-Item Env:VITE_SENTINEL_HOSTED_DEMO
Set-Location ..
./hosting/vercel/package.ps1 -Destination '<new-release-parent>/web'
Set-Location '<new-release-parent>'
vercel deploy --prod --yes --archive=tgz --project agentforge-sentinel --scope pgavara1-3079s-projects
```

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

PDFs use the static browser tool. This deployment deliberately uses no server parser,
paid model or account access. It is a public synthetic research demo.
