# DEMO01: recorded synthetic replay

A static page that steps through **one recorded synthetic case** as the unchanged Sentinel
service stored it: rule score, alert and case, pinned evidence, the three-role
investigation trace, the server-built action intent, a scripted approval, one simulated
action, its idempotent retry and the audit trail.

It needs no key, login or backend. The page loads only `data/recorded-case.json` and
`data/manifest.json` from this folder. It never calls `/v1`, a health check, a model or a
provider. Its controls move between recorded frames and change nothing.

Labels on every frame: **recorded, synthetic, rule baseline, deterministic roles, scripted
approval, simulated action**. The rule score is a heuristic, not a fraud probability, and
this is not live inference. The approval was sent by the capture program, not by a person
reviewing the case.

## Open it

From the repository root, start a static server that only listens on loopback:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory demo
```

Open `http://127.0.0.1:8765/` and stop the server with Ctrl+C in the same terminal. The
data files cannot be loaded from a `file://` page, so use the server. Serving over loopback
also lets the page compute the data file's SHA-256 and compare it with the manifest.

## Two-minute walkthrough

1. **Frame 1, ingest.** Five synthetic debits for one synthetic account. The table shows
   each rule score at ingest time. Only the large final debit, with two debits in the hour
   before it, reaches the 0.5 threshold.
2. **Frame 2, case opened.** The alert, the case at revision 1 and its two evidence items.
   The pins record the scorer, threshold, action policy, workflow, tool profile and the
   evidence snapshot hash. The ledger on the right shows zero approvals and zero actions.
3. **Frames 3 to 5, three roles.** The server runs the read tools. The evidence analyst
   cites facts, the investigator proposes `simulated_hold`, the server checks every
   claim, and the reviewer accepts. Citation links jump to the evidence or tool result
   they name. Usage reads "not applicable": the deterministic adapters call no provider.
4. **Frame 6, proposal.** The server builds the exact intent from stored records. The
   page re-checks the intent against the evidence pin, case revision and target.
5. **Frame 7, scripted approval.** Labelled scripted. The approvals count changes to one;
   simulated actions stay at zero.
6. **Frames 8 and 9, execution and retry.** One simulated action. The retry with the same
   idempotency key returns the same action marked replayed; the count stays at one.
7. **Frame 10, audit.** Six audit events in stored order, and a final trace read showing the
   same workflow.

Use the keyboard: Left and Right arrows step through the frames, and Home and End go to the
first and last frame. "Technical details" lists the requests the capture program sent for
that frame, and the projected JSON. The footer gives provenance: generator commit, the recorded
content identity, the tested application reference, the data hash, the scenario, adapter identities and the limitations.

## Regenerate, validate, QA

```sh
uv run --locked python scripts/build_recorded_demo.py validate     # no database
uv run --locked python scripts/build_recorded_demo.py capture      # needs local PostgreSQL
node demo/tests/browser_qa.mjs --node-modules <an existing node_modules with playwright>
```

`capture` runs on a committed tree. It starts its own disposable PostgreSQL cluster under the
git-ignored `.agent/demo01/`, stops it and removes it. It writes the public fixture only after
validation and a scan for the real session token. The raw capture stays private. A failed
capture writes nothing public; it never substitutes fixture data. `validate` also checks
that the generator and `src/` bytes in this checkout still match the digests recorded at
capture (CRLF read as LF). It needs no Git history. If they differ, re-run `capture`. The browser QA script uses
an already installed Playwright and Chromium. It serves this folder from its own loopback
server and closes that server afterwards. See `docs/demo/DEMO01.md` for provenance and
evidence.
