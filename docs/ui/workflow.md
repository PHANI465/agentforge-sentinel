# Analyst UI workflow

Owned by Cursor. The API contract is accepted C01 `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`.

From `web/`:

```
npm ci
npm test
npm run typecheck
npm run build
npm run dev
```

`npm run dev` serves the workbench and proxies `/healthz` and `/v1` to `SENTINEL_API_ORIGIN`. The default is `http://127.0.0.1:8000`, the same default as `scripts/smoke_thin_path.py`. The browser uses same-origin requests. The session token is typed into the page and kept in memory.

Ordinary UI tests use the frozen HTTP examples and a fake client. They do not call a model. Browser tests against disposable Postgres wait for accepted C02 and are not part of these commands.

No AgentForge UI source is reused. `web/package-lock.json` is the frontend lock. Backend checks stay on the Python helper; this workflow is the frontend addition for the integrator to wire beside them.
