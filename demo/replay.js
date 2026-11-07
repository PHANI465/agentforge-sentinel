/* DEMO01 recorded replay. Reads only ./data/recorded-case.json and ./data/manifest.json
 * from this folder. It sends no request to a backend, model or provider, and the controls
 * only move between recorded frames. Every recorded value is rendered as DOM text (never
 * parsed as HTML); the only links are to records inside this page. */
"use strict";

(function () {
  const DATA_URL = "data/recorded-case.json";
  const MANIFEST_URL = "data/manifest.json";
  const SCHEMA = "sentinel.demo01.recorded-replay.v1";
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  const ALLOWED_ATTRS = new Set(["id", "role", "tabindex", "type", "title", "scope",
    "hidden", "colspan", "lang"]);

  const NARRATIVE = {
    ingest: "The capture program posted five synthetic debits for one synthetic account to " +
      "POST /v1/transactions. The production rule scorer scored each one at ingest time, " +
      "using only history already ingested. The first four stayed below the threshold; the " +
      "large final debit, with two debits in the hour before it, reached the threshold and " +
      "raised an alert.",
    case_opened: "In the same database transaction as the alert, the server opened a case " +
      "and attached two evidence items computed from stored records. Their snapshot hash is " +
      "pinned on the case together with the scorer, action policy, workflow and tool profile " +
      "versions. No approval or action exists.",
    analyst: "The capture program asked for an investigation at revision 1. The " +
      "deterministic three-role workflow claimed the case. The server ran the baseline read " +
      "tools itself; the evidence analyst then restated facts with citations and asked for " +
      "follow-up tools, which the server ran and recorded, including unavailable results.",
    investigator: "The investigator chose one enumerated operation and reason code and cited " +
      "the facts behind it. The server, not a role, checked every claim against the stored " +
      "evidence and tool results.",
    reviewer: "The reviewer saw the server's claim checks and accepted. The coordinator " +
      "recorded a recommendation and moved the case to awaiting approval. Deterministic " +
      "adapters call no provider, so token usage is not applicable rather than zero.",
    proposal: "The server built the exact action intent from stored records: the target " +
      "transaction and amount come from the database, not from role output. The intent is " +
      "bound to the case revision and evidence snapshot by its SHA-256. Nothing is approved.",
    approval: "Scripted step: the capture program, holding the analyst session, sent the " +
      "decision \u201capproved\u201d for this exact intent. This is not a human review. " +
      "The approval is bound to the intent hash and expires after the policy time limit. " +
      "No action has run yet.",
    execution: "The capture program executed the approved intent once. Under lock the server " +
      "re-checked authority, the intent binding and the approval window, consumed the " +
      "approval, recorded exactly one simulated action and closed the case. No external " +
      "system was contacted.",
    replay: "The capture program retried with the same idempotency key. The server returned " +
      "the original action marked replayed and executed nothing again. The simulated action " +
      "count stays at one.",
    audit: "Each state change wrote an audit event in the same transaction as the change. A " +
      "final trace read returned the same stored workflow: reading never changes a case.",
  };

  const state = { fx: null, index: 0, records: new Map(), digest: null, manifest: null };

  // ---- safe DOM construction ------------------------------------------------------------

  function h(tag, props) {
    const node = document.createElement(tag);
    if (props) {
      for (const key of Object.keys(props)) {
        const value = props[key];
        if (value === null || value === undefined || value === false) continue;
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = String(value);
        else if (key === "on") {
          for (const ev of Object.keys(value)) node.addEventListener(ev, value[ev]);
        } else if (ALLOWED_ATTRS.has(key) || key.startsWith("aria-") ||
                   key.startsWith("data-")) {
          node.setAttribute(key, value === true ? "" : String(value));
        } else {
          throw new Error("attribute not allowed: " + key);
        }
      }
    }
    for (let i = 2; i < arguments.length; i += 1) appendKid(node, arguments[i]);
    return node;
  }

  function appendKid(node, kid) {
    if (kid === null || kid === undefined || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach((k) => appendKid(node, k)); return; }
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }

  function mono(value, cls) {
    return h("code", { class: "mono" + (cls ? " " + cls : "") },
      value === null || value === undefined ? "null" : String(value));
  }

  function shortId(id) {
    return typeof id === "string" && id.length > 8 ? "\u2026" + id.slice(-6) : String(id);
  }

  /* A link to a record shown in this page; plain text when the record is unknown. */
  function recLink(id, label) {
    const entry = typeof id === "string" && UUID.test(id) ? state.records.get(id) : null;
    const text = label || shortId(id);
    if (!entry) return h("span", { class: "dangling", title: "not a recorded record" }, text);
    const link = h("a", { class: "reclink", title: entry.label + " " + id }, text);
    link.href = "#rec-" + id;  // a fragment of a record in this page, never a remote URL
    link.addEventListener("click", (event) => {
      event.preventDefault();
      showRecord(id);
    });
    return link;
  }

  function anchor(id) {
    return { id: "rec-" + id, tabindex: "-1" };
  }

  function time(value) {
    if (typeof value !== "string") return "\u2014";
    const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]00:00)$/.exec(value);
    return m ? m[1] + " " + m[2] + (m[3] ? m[3].slice(0, 4) : "") + " UTC" : value;
  }

  function ms(value) { return Date.parse(value); }

  function relative(fromIso, toIso) {
    const diff = Math.round((ms(toIso) - ms(fromIso)) / 1000);
    const sign = diff < 0 ? "\u2212" : "+";
    let s = Math.abs(diff);
    const d = Math.floor(s / 86400); s -= d * 86400;
    const hr = Math.floor(s / 3600); s -= hr * 3600;
    const mi = Math.floor(s / 60); s -= mi * 60;
    const parts = [];
    if (d) parts.push(d + "d");
    if (hr) parts.push(hr + "h");
    if (mi) parts.push(mi + "m");
    if (!d && !hr) parts.push(s + "s");
    return sign + parts.join(" ");
  }

  function money(amount) {
    if (!amount || typeof amount.minor_units !== "number") return "\u2014";
    const exp = amount.currency_exponent || 0;
    const neg = amount.minor_units < 0;
    const digits = String(Math.abs(amount.minor_units)).padStart(exp + 1, "0");
    const whole = digits.slice(0, digits.length - exp).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    const frac = exp ? "." + digits.slice(digits.length - exp) : "";
    return (neg ? "\u2212" : "") + whole + frac + " " + String(amount.currency);
  }

  function artifact(ref) {
    if (!ref) return "\u2014";
    return h("span", { class: "artifact" }, h("span", { class: "artifact-name" },
      String(ref.name) + " " + String(ref.version)), " ", mono(String(ref.sha256).slice(0, 12) +
      "\u2026", "dim"));
  }

  function dl(rows, cls) {
    return h("dl", { class: "kv" + (cls ? " " + cls : "") }, rows.filter(Boolean).map((r) =>
      h("div", { class: "kv-row" }, h("dt", null, r[0]), h("dd", null, r[1]))));
  }

  function card(title, body, opts) {
    const o = opts || {};
    const props = Object.assign({ class: "card" + (o.cls ? " " + o.cls : "") },
      o.id ? anchor(o.id) : {});
    return h("section", props, h("h3", { class: "card-title" }, title,
      o.tag ? h("span", { class: "tag" + (o.tagCls ? " " + o.tagCls : "") }, o.tag) : null),
    body);
  }

  function check(ok, text) {
    return h("li", { class: ok ? "ok" : "bad" }, h("span", { class: "mark", "aria-hidden":
      "true" }, ok ? "\u2713" : "\u2717"), h("span", { class: "visually-hidden" },
      ok ? "Holds: " : "Does not hold: "), text);
  }

  function json(value) {
    return h("pre", { class: "json" }, JSON.stringify(value, null, 2));
  }

  function raw(label, value) {
    return h("details", { class: "raw" }, h("summary", null, label), json(value));
  }

  function table(head, rows, caption) {
    return h("div", { class: "table-wrap" }, h("table", null,
      caption ? h("caption", null, caption) : null,
      h("thead", null, h("tr", null, head.map((c) => h("th", { scope: "col" }, c)))),
      h("tbody", null, rows)));
  }

  // ---- record index and navigation ------------------------------------------------------

  function indexRecords(fx) {
    const r = fx.records;
    const add = (id, stage, label) => { if (typeof id === "string") state.records.set(id, { stage, label }); };
    r.ingests.forEach((i) => add(i.transaction.id, "ingest", "transaction"));
    add(r.alert.id, "case_opened", "alert");
    add(r.case_opened.id, "case_opened", "case");
    r.evidence.forEach((e) => add(e.id, "case_opened", "evidence"));
    add(r.workflow.id, "analyst", "workflow");
    r.tool_results.forEach((t) => add(t.id, "analyst", "tool result"));
    const roleStage = { evidence_analyst: "analyst", investigator: "investigator",
      reviewer: "reviewer" };
    r.attempts.forEach((a) => add(a.agent_run_id, roleStage[a.role], a.role + " attempt"));
    add(r.intent.id, "proposal", "action intent");
    add(r.approval.id, "approval", "approval");
    add(r.execution.action.id, "execution", "simulated action");
    r.audit.forEach((e) => add(e.id, "audit", "audit event"));
  }

  function frameIndexOf(stage) {
    return state.fx.frames.findIndex((f) => f.stage === stage);
  }

  function showRecord(id) {
    const entry = state.records.get(id);
    if (!entry) return;
    go(frameIndexOf(entry.stage), { focus: false });
    const target = document.getElementById("rec-" + id);
    if (target) {
      const holder = target.closest("details");
      if (holder) holder.open = true;
      target.classList.add("flash");
      window.setTimeout(() => target.classList.remove("flash"), 1600);
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "center" });
    }
    history.replaceState(null, "", "#rec-" + id);
  }

  function go(index, opts) {
    const o = opts || {};
    const frames = state.fx.frames;
    const next = Math.max(0, Math.min(frames.length - 1, index));
    state.index = next;
    render();
    if (!o.keepHash) history.replaceState(null, "", "#frame-" + frames[next].index);
    if (o.focus) document.getElementById("frame-title").focus({ preventScroll: false });
  }

  /* Deep links: #frame-N or #rec-<id>. Other fragments (the skip link) change nothing. */
  function fromHash(initial) {
    const hash = window.location.hash;
    const f = /^#frame-(\d{1,2})$/.exec(hash);
    if (f) return go(Number(f[1]) - 1, { keepHash: true });
    const rec = /^#rec-([0-9a-f-]{36})$/.exec(hash);
    if (rec && state.records.has(rec[1])) return showRecord(rec[1]);
    if (initial === true) go(0, { keepHash: true });
    return undefined;
  }

  // ---- frame renderers ------------------------------------------------------------------

  function txnRow(i, alertAt) {
    const t = i.transaction;
    const s = i.scoring;
    return h("tr", Object.assign({ class: s.alerted ? "hit" : "" }, anchor(t.id)),
      h("td", null, mono(t.external_id)),
      h("td", null, time(t.occurred_at), h("span", { class: "dim block" },
        relative(alertAt, t.occurred_at) + " vs alerted debit")),
      h("td", { class: "num" }, money(t.amount)),
      h("td", { class: "num" }, String(s.prior_count_1h)),
      h("td", { class: "num" }, mono(s.score)),
      h("td", null, s.alerted ? h("strong", { class: "hit-tag" }, "alert") : "below threshold"));
  }

  function renderIngest(r, p) {
    const alertAt = r.ingests[r.ingests.length - 1].transaction.occurred_at;
    const rc = p.scorer.rule_config || {};
    const currency = state.fx.scenario.currency;
    const cutoff = rc.large_amount_minor && rc.large_amount_minor[currency];
    return [
      table(["External id", "Occurred", "Amount", "Prior in 1h", "Rule score", "Result"],
        r.ingests.map((i) => txnRow(i, alertAt)),
        "Five synthetic debits, one synthetic account, in ingest order"),
      card("How the rule baseline scores", [
        h("p", null, "Rule scorer ", artifact(p.scorer.artifact), ". The score is a " +
          "heuristic, not a fraud probability."),
        h("ul", { class: "plain" },
          cutoff !== undefined ? h("li", null, "+" + rc.large_amount_points + " when the " +
            "amount is at least " + money({ minor_units: cutoff, currency_exponent: 2,
            currency: currency })) : null,
          rc.velocity_points_per_prior !== undefined ? h("li", null, "+" +
            rc.velocity_points_per_prior + " per earlier transaction in the prior hour (at " +
            "most +" + rc.velocity_points_cap + ")") : null,
          h("li", null, "Alert at or above " + p.scorer.threshold)),
      ], { cls: "note" }),
    ];
  }

  function evidenceCard(e) {
    return card("Evidence " + shortId(e.id), dl([
      ["Source", mono(e.source)],
      ["Reference", mono(e.source_ref)],
      ["Facts", e.facts.map((f) => h("span", { class: "fact" }, mono(f.name), " = ",
        mono(JSON.stringify(f.value))))],
      ["Observed", time(e.observed_at)],
      ["Available", time(e.available_at)],
      ["Content SHA-256", mono(e.content_sha256, "hash")],
    ]), { id: e.id });
  }

  function renderCaseOpened(r) {
    const c = r.case_opened;
    const a = r.alert;
    return [
      h("div", { class: "grid2" },
        card("Alert " + shortId(a.id), dl([
          ["Transaction", recLink(a.transaction_id)],
          ["Rule score", [mono(a.score), " (threshold " + a.threshold + ", " +
            a.score_semantics + ")"]],
          ["Raised", time(a.created_at)],
        ]), { id: a.id }),
        card("Case " + shortId(c.id), dl([
          ["State", mono(c.state)], ["Revision", mono(c.revision)],
          ["Created", time(c.created_at)],
          ["Evidence", c.evidence_ids.map((id) => recLink(id))],
        ]), { id: c.id })),
      card("Pins recorded on the case", dl([
        ["Dataset", artifact(c.pins.dataset)], ["Scorer", artifact(c.pins.scorer)],
        ["Threshold policy", artifact(c.pins.threshold_policy)],
        ["Action policy", artifact(c.pins.policy)],
        ["Workflow", artifact(c.pins.agent_config)], ["Tool profile", artifact(c.pins.tool_config)],
        ["Evidence snapshot", mono(c.pins.evidence_snapshot_sha256, "hash")],
      ]), { cls: "note" }),
      h("div", { class: "grid2" }, r.evidence.map(evidenceCard)),
    ];
  }

  /* Stored steps whose workflow state is one of `states`, in stored order. */
  function stepsIn(r, states) {
    return r.steps.filter((s) => states.indexOf(s.state) !== -1);
  }

  function stepList(steps) {
    return h("ol", { class: "steps" }, steps.map((s) => h("li", { class: "step step-" + s.kind },
      h("span", { class: "step-seq" }, "#" + s.seq),
      h("span", { class: "step-kind" }, s.kind.replace(/_/g, " ")),
      h("span", { class: "step-state" }, s.state),
      s.role ? h("span", { class: "step-role" }, s.role) : null,
      s.tool ? h("span", { class: "step-tool" }, s.tool) : null,
      s.tool_result_id ? recLink(s.tool_result_id, "result " + shortId(s.tool_result_id)) : null,
      h("span", { class: "dim step-at" }, time(s.at)))));
  }

  function toolCard(t) {
    const values = Object.keys(t.values || {});
    return card(t.tool + (t.window ? " (" + t.window + ")" : ""), dl([
      ["Status", mono(t.status, t.status === "ok" ? "good" : "warn")],
      t.denial ? ["Denial", mono(t.denial)] : null,
      ["Values", values.length ? values.map((k) => h("span", { class: "fact" }, mono(k), " = ",
        mono(JSON.stringify(t.values[k])))) : h("span", { class: "dim" }, "none recorded")],
      t.evidence_ids.length ? ["From evidence", t.evidence_ids.map((id) => recLink(id))] : null,
      ["As of", time(t.as_of)], ["Result id", mono(t.id, "hash")],
    ]), { id: t.id, tag: t.status, tagCls: t.status === "ok" ? "tag-good" : "tag-warn" });
  }

  function claimList(claims, checks) {
    return h("ol", { class: "claims" }, claims.map((c, i) => {
      const k = checks ? checks.find((x) => x.index === i) : null;
      return h("li", null, mono(c.fact), " " + c.relation + " ", mono(JSON.stringify(c.value)),
        " \u2014 cites ", recLink(c.cite.id, c.cite.kind.replace("_", " ") + " " +
          shortId(c.cite.id)),
        k ? h("span", { class: "tag " + (k.status === "supported" ? "tag-good" : "tag-warn") },
          k.status + (k.reason ? " (" + k.reason + ")" : "")) : null);
    }));
  }

  function attempt(r, role) {
    return r.attempts.find((a) => a.role === role);
  }

  function usageText(u) {
    if (!u) return "unknown";
    if (u.source === "not_applicable") return "not applicable (no provider call)";
    if (u.source === "unknown") return "unknown";
    return (u.input_tokens === null ? "unknown" : u.input_tokens) + " in / " +
      (u.output_tokens === null ? "unknown" : u.output_tokens) + " out (adapter reported)";
  }

  function attemptCard(a, extra) {
    return card(a.role.replace("_", " ") + " attempt " + a.attempt, [dl([
      ["Status", mono(a.status)], ["Adapter", artifact(a.config)],
      ["Started", time(a.started_at)], ["Finished", time(a.finished_at)],
      ["Elapsed", a.elapsed_ms === null ? "unknown" : a.elapsed_ms + " ms"],
      ["Usage", usageText(a.usage)],
      ["Output SHA-256", mono(a.output_sha256, "hash")],
    ]), extra, raw("Recorded role output", a.output)], { id: a.agent_run_id });
  }

  function renderAnalyst(r) {
    const w = r.workflow;
    const a = attempt(r, "evidence_analyst");
    const out = a.output || {};
    return [
      card("Workflow " + shortId(w.id), dl([
        ["Config", artifact(w.config)], ["Tool profile", artifact(w.tool_profile)],
        ["Claimed at revision", mono(w.case_revision)],
        ["Input snapshot", mono(w.input_snapshot_sha256, "hash")],
        ["Started", time(w.started_at)], ["Deadline", time(w.deadline_at)],
      ]), { id: w.id }),
      card("Steps up to the investigator", stepList(stepsIn(r, ["gathering", "analyst", "analyst_tools"]))),
      attemptCard(a, [
        h("h4", null, "Claims restated with citations"), claimList(out.claims || [], null),
        h("h4", null, "Reported missing"), h("p", null, (out.missing || []).length ?
          out.missing.map((m) => mono(m)) : "none"),
        h("h4", null, "Follow-up tools requested"),
        h("p", null, (out.tool_requests || []).length ? out.tool_requests.map((t) =>
          mono(t.tool + (t.window ? " " + t.window : ""))) : "none")]),
      h("h3", { class: "section-title" }, "Tool results recorded by the server"),
      h("div", { class: "grid2" }, r.tool_results.map(toolCard)),
    ];
  }

  function renderInvestigator(r) {
    const a = attempt(r, "investigator");
    const out = a.output || {};
    return [
      card("Proposed by the investigator", dl([
        ["Operation", mono(out.operation)], ["Reason code", mono(out.reason_code)],
      ]), { cls: "note" }),
      attemptCard(a, [h("h4", null, "Claims and the server's checks"),
        claimList(out.claims || [], a.claim_checks)]),
      card("Steps", stepList(stepsIn(r, ["investigator", "verifying"]))),
    ];
  }

  function renderReviewer(r) {
    const a = attempt(r, "reviewer");
    const inv = attempt(r, "investigator");
    const d = r.workflow.disposition;
    const u = r.usage_summary;
    return [
      card("Disposition", dl([
        ["Kind", mono(d.kind)], ["Operation", mono(d.operation)],
        ["Reason code", mono(d.reason_code)],
        ["Supported / unsupported claims", d.supported_claims + " / " + d.unsupported_claims],
        ["Basis attempt", recLink(d.basis_run_id, "investigator " + shortId(d.basis_run_id))],
        ["Finished", time(r.workflow.finished_at)],
        ["Recorded role invocations", String(r.workflow.recorded_role_invocations)],
        ["Recorded tool calls", String(r.workflow.recorded_tool_calls)],
      ]), { cls: "note" }),
      inv.finding ? card("Server-rendered rationale", h("blockquote", { class: "rationale" },
        String(inv.finding.rationale)), { tag: "stored text" }) : null,
      attemptCard(a, dl([["Verdict", mono((a.output || {}).verdict)]])),
      card("Usage across attempts", dl([
        ["Provider-reported attempts", String(u.reported_attempts)],
        ["Not applicable", String(u.not_applicable_attempts)],
        ["Unknown", String(u.unknown_attempts)],
        ["Input / output tokens", (u.input_tokens === null ? "not applicable" : u.input_tokens) +
          " / " + (u.output_tokens === null ? "not applicable" : u.output_tokens)],
      ])),
      card("Steps", stepList(stepsIn(r, ["reviewer", "done"]))),
    ];
  }

  function renderProposal(r) {
    const i = r.intent;
    const c = r.case_after_investigation;
    const p = i.parameters;
    return [
      card("Action intent " + shortId(i.id), dl([
        ["Operation", mono(p.operation)],
        ["Target transaction", recLink(p.transaction_id)],
        p.amount ? ["Amount", money(p.amount)] : null,
        p.reason_code ? ["Reason code", mono(p.reason_code)] : null,
        ["Case revision", mono(i.case_revision)],
        ["Evidence snapshot", mono(i.evidence_snapshot_sha256, "hash")],
        ["Action policy", artifact(i.policy)],
        ["Intent SHA-256", mono(i.intent_sha256, "hash")],
      ]), { id: i.id, tag: "server-built" }),
      card("Checks this page re-ran on the recorded values", h("ul", { class: "checks" },
        check(i.evidence_snapshot_sha256 === r.case_opened.pins.evidence_snapshot_sha256,
          "intent is bound to the evidence snapshot pinned when the case opened"),
        check(i.case_revision === c.revision && c.state === "awaiting_approval",
          "intent is bound to the current case revision, awaiting approval"),
        check(p.transaction_id === r.alert.transaction_id,
          "target is the alerted transaction"),
        check(p.operation === r.workflow.disposition.operation,
          "operation equals the workflow disposition"))),
    ];
  }

  function renderApproval(r) {
    const a = r.approval;
    const ttl = Math.round((ms(a.expires_at) - ms(a.decided_at)) / 1000);
    return [
      card("Approval " + shortId(a.id), dl([
        ["Decision", mono(a.decision)],
        ["Sent by", [mono(a.actor), " (" + a.actor_kind + " session, scripted)"]],
        ["Intent", recLink(a.intent_id)],
        ["Intent SHA-256", mono(a.intent_sha256, "hash")],
        ["Decided", time(a.decided_at)],
        ["Expires", time(a.expires_at) + " (" + ttl + " s window)"],
        ["Consumed", a.consumed_at ? time(a.consumed_at) : "not yet"],
      ]), { id: a.id, tag: "scripted", tagCls: "tag-scripted" }),
      card("What this step is not", h("p", null, "No person reviewed this case. The capture " +
        "program sent this decision through POST /v1/approvals so the stored path from " +
        "approval to simulated action could be recorded. This page has no approve control."),
      { cls: "warnnote" }),
      card("Checks this page re-ran on the recorded values", h("ul", { class: "checks" },
        check(a.intent_id === r.intent.id && a.intent_sha256 === r.intent.intent_sha256,
          "approval names the exact intent and its hash"),
        check(ms(a.decided_at) >= ms(r.workflow.finished_at),
          "decision recorded after the workflow finished"))),
    ];
  }

  function actionCard(x, title) {
    const a = x.action;
    return card(title, dl([
      ["Action", mono(a.id, "hash")], ["Mode", mono(a.mode)], ["State", mono(a.state)],
      ["Approval", recLink(a.approval_id)], ["Intent", recLink(a.intent_id)],
      ["Idempotency key", mono(a.idempotency_key, "hash")],
      ["Created", time(a.created_at)], ["Completed", time(a.completed_at)],
      ["Replayed", mono(x.replayed)],
    ]), title.startsWith("Simulated") ? { id: a.id, tag: "simulated" } : { tag: "replayed" });
  }

  function renderExecution(r) {
    const a = r.execution.action;
    return [
      actionCard(r.execution, "Simulated action " + shortId(a.id)),
      card("Checks this page re-ran on the recorded values", h("ul", { class: "checks" },
        check(a.approval_id === r.approval.id && a.intent_sha256 === r.approval.intent_sha256,
          "action is bound to the approval and the intent hash"),
        check(ms(a.created_at) >= ms(r.approval.decided_at) &&
          ms(a.created_at) <= ms(r.approval.expires_at), "executed inside the approval window"),
        check(r.approval.consumed_at_final === a.created_at,
          "the approval was consumed by this action"),
        check(r.case_final.state === "closed", "case closed"))),
    ];
  }

  function renderReplay(r) {
    const first = r.execution.action;
    const again = r.replay.action;
    return [
      actionCard(r.replay, "Response to the retry"),
      card("Checks this page re-ran on the recorded values", h("ul", { class: "checks" },
        check(again.id === first.id, "the retry returned the original action id"),
        check(r.replay.replayed === true && r.execution.replayed === false,
          "only the retry is marked replayed"),
        check(again.idempotency_key === first.idempotency_key, "same idempotency key"))),
    ];
  }

  function renderAudit(r) {
    const ft = r.final_trace_read;
    return [
      table(["#", "Event", "Actor", "Kind", "Case rev", "Occurred", "Outcome"],
        r.audit.map((e, i) => h("tr", anchor(e.id), h("td", { class: "num" }, String(i + 1)),
          h("td", null, mono(e.event_type)), h("td", null, mono(e.actor)),
          h("td", null, e.actor_kind), h("td", { class: "num" }, String(e.case_revision)),
          h("td", null, time(e.occurred_at)), h("td", null, e.outcome))),
        "Audit events for the case, in stored order"),
      card("Final trace read", dl([
        ["Read at", time(ft.read_at)], ["Case", mono(ft.case_state + " (revision " +
          ft.case_revision + ")")],
        ["Workflow", recLink(ft.workflow_id)], ["Stored steps", String(ft.steps)],
      ])),
    ];
  }

  const RENDER = { ingest: renderIngest, case_opened: renderCaseOpened, analyst: renderAnalyst,
    investigator: renderInvestigator, reviewer: renderReviewer, proposal: renderProposal,
    approval: renderApproval, execution: renderExecution, replay: renderReplay,
    audit: renderAudit };

  // ---- page chrome ----------------------------------------------------------------------

  function renderRail() {
    const rail = document.getElementById("rail");
    rail.replaceChildren(...state.fx.frames.map((f, i) => h("li", null,
      h("button", { type: "button", class: "rail-btn", "data-index": i,
        on: { click: () => go(i) } },
        h("span", { class: "rail-no" }, String(f.index).padStart(2, "0")),
        h("span", { class: "rail-label" }, f.title)))));
  }

  function renderLedger(o, previous) {
    const row = (label, value, key) => {
      const changed = previous && key && previous[key] !== o[key];
      return h("div", { class: "kv-row" + (changed ? " changed" : "") }, h("dt", null, label),
        h("dd", null, mono(value), changed ? h("span", { class: "visually-hidden" },
          " (changed)") : null));
    };
    document.getElementById("ledger").replaceChildren(
      row("Case state", o.case_state, "case_state"),
      row("Case revision", o.case_revision, "case_revision"),
      row("Action intents", o.action_intents, "action_intents"),
      row("Approvals", o.approvals, "approvals"),
      row("Simulated actions", o.simulated_actions, "simulated_actions"),
      row("Audit events", o.audit_events, "audit_events"),
      row("Transactions", o.transactions, "transactions"),
      row("Observed", time(o.observed_at)));
  }

  function renderTech(frame) {
    const body = document.getElementById("frame-tech-body");
    body.replaceChildren(
      h("p", null, "Requests the capture program sent for this frame. They are part of the " +
        "recording; this page sends none."),
      h("ul", { class: "requests" }, frame.requests.map((q) => h("li", null,
        mono(q.method, "method"), " ", mono(q.path), " ", mono(q.status, "dim")))),
      raw("Observation used for this frame", state.fx.observations[frame.observation]));
  }

  function render() {
    const fx = state.fx;
    const frame = fx.frames[state.index];
    const total = fx.frames.length;
    document.getElementById("frame-no").textContent = "Frame " + frame.index + " of " + total;
    document.getElementById("frame-title").textContent = frame.title;
    document.getElementById("frame-narrative").textContent = NARRATIVE[frame.stage] || "";
    const renderer = RENDER[frame.stage];
    document.getElementById("frame-body").replaceChildren(...[].concat(
      renderer ? renderer(fx.records, fx.provenance) : []).filter(Boolean));
    renderTech(frame);
    const prevFrame = state.index > 0 ? fx.frames[state.index - 1] : null;
    renderLedger(fx.observations[frame.observation],
      prevFrame ? fx.observations[prevFrame.observation] : null);
    document.querySelectorAll(".rail-btn").forEach((b, i) => {
      if (i === state.index) b.setAttribute("aria-current", "step");
      else b.removeAttribute("aria-current");
      b.classList.toggle("done", i < state.index);
    });
    document.getElementById("prev").disabled = state.index === 0;
    document.getElementById("next").disabled = state.index === total - 1;
    document.getElementById("position").textContent = frame.index + " / " + total;
    document.getElementById("announce").textContent = "Frame " + frame.index + " of " + total +
      ": " + frame.title;
    document.title = "Sentinel Recorded Replay \u2013 " + "frame " + frame.index + " of " + total;
  }

  function renderProvenance() {
    const p = state.fx.provenance;
    const m = state.manifest;
    let hashText;
    if (state.digest === null) hashText = "not computed (needs a secure context, such as " +
      "the loopback server in demo/README.md)";
    else if (!m) hashText = state.digest + " (manifest unavailable)";
    else hashText = state.digest + (state.digest === m.sha256 ? " \u2014 matches the manifest"
      : " \u2014 DOES NOT match the manifest " + m.sha256);
    const roleRows = Object.keys(p.workflow.roles).map((k) => [k.replace("_", " "),
      artifact(p.workflow.roles[k])]);
    const rr = p.runtime_role;
    document.getElementById("provenance").replaceChildren(
      h("p", { class: "notice" }, state.fx.notice),
      h("div", { class: "grid2" },
        card("Capture", dl([
          ["Generator", mono(p.generator)],
          ["Generator commit", [mono(p.generator_commit, "hash"),
            p.generator_tree_clean ? " (clean tree)" : " (UNCLEAN tree)"]],
          ["Content identity", p.content_identity && p.content_identity.files ?
            [mono(p.content_identity.sha256, "hash"), " (" +
              Object.keys(p.content_identity.files).length + " generator and src/ files, " +
              "CRLF canonicalized to LF)"] : "not recorded"],
          ["Tested application", [mono(p.tested_application_reference, "hash"),
            p.src_identical_to_tested_application ? " (src/ identical)" :
              " (src/ differs)"]],
          ["Captured", time(p.capture_started_at) + " to " + time(p.capture_finished_at)],
          ["API version", mono(p.api_version)], ["HTTP", p.http_path],
          ["Database", p.database + (rr.postgres_server_version ? " (PostgreSQL " +
            rr.postgres_server_version + ")" : "")],
          ["Runtime role", "restricted runtime role" + (rr.session_issuance_refused ?
            "; refused to issue sessions" : "") + (rr.superuser === false ? "; not superuser" :
            "")],
          ["Data SHA-256", mono(hashText, "hash")],
        ])),
        card("Scenario and adapters", dl([
          ["Scenario", [mono(state.fx.scenario.id), " \u2014 ", state.fx.scenario.description]],
          ["Scorer", [mono(p.scorer.mode), " ", artifact(p.scorer.artifact)]],
          ["Workflow", artifact(p.workflow.config)],
          ...roleRows,
          ["Adapters", p.workflow.adapters],
          ["Tool profile", artifact(p.workflow.tool_profile)],
        ]))),
      h("div", { class: "grid3" },
        card("Operator actions", h("ul", { class: "plain" }, p.operator_actions.map((x) =>
          h("li", null, x)))),
        card("Scripted steps", h("ul", { class: "plain" }, p.scripted_steps.map((x) =>
          h("li", null, x))), { tag: "scripted", tagCls: "tag-scripted" }),
        card("Exercised", h("ul", { class: "plain" }, p.exercised.map((x) =>
          h("li", null, x))))),
      card("Limitations", h("ul", { class: "plain" }, p.limitations.map((x) =>
        h("li", null, x))), { cls: "warnnote" }));
    const banner = document.getElementById("integrity");
    if (m && state.digest !== null && state.digest !== m.sha256) {
      banner.hidden = false;
      banner.className = "integrity bad";
      banner.textContent = "The loaded data does not match the published manifest hash. " +
        "Treat it as unverified.";
    }
  }

  function fail(message) {
    document.getElementById("frame-no").textContent = "Not loaded";
    document.getElementById("frame-title").textContent = "The recording could not be shown";
    document.getElementById("frame-narrative").textContent = message;
    document.getElementById("prev").disabled = true;
    document.getElementById("next").disabled = true;
  }

  function wellFormed(fx) {
    return fx && fx.schema === SCHEMA && Array.isArray(fx.frames) && fx.frames.length === 10 &&
      fx.records && fx.observations && fx.provenance &&
      fx.frames.every((f) => RENDER[f.stage] && fx.observations[f.observation]);
  }

  async function sha256Hex(buffer) {
    if (!window.crypto || !window.crypto.subtle) return null;
    const digest = await window.crypto.subtle.digest("SHA-256", buffer);
    return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  async function load() {
    let buffer;
    try {
      const response = await fetch(DATA_URL, { cache: "no-store", credentials: "omit" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      buffer = await response.arrayBuffer();
    } catch (error) {
      fail("The recorded data could not be read from this folder. Serve the demo/ folder " +
        "with a local static server (see demo/README.md); opening the file directly is not " +
        "supported by browsers for data files.");
      return;
    }
    let fx;
    try {
      fx = JSON.parse(new TextDecoder("utf-8").decode(buffer));
    } catch (error) {
      fail("The recorded data is not valid JSON.");
      return;
    }
    if (!wellFormed(fx)) {
      fail("The recorded data does not have the expected DEMO01 shape.");
      return;
    }
    try {
      const response = await fetch(MANIFEST_URL, { cache: "no-store", credentials: "omit" });
      state.manifest = response.ok ? await response.json() : null;
    } catch (error) {
      state.manifest = null;
    }
    try {
      state.digest = await sha256Hex(buffer);
    } catch (error) {
      state.digest = null;
    }
    state.fx = fx;
    indexRecords(fx);
    renderRail();
    renderProvenance();
    document.getElementById("prev").addEventListener("click", () => go(state.index - 1));
    document.getElementById("next").addEventListener("click", () => go(state.index + 1));
    document.addEventListener("keydown", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const tag = event.target && event.target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (event.key === "ArrowRight") { event.preventDefault(); go(state.index + 1); }
      else if (event.key === "ArrowLeft") { event.preventDefault(); go(state.index - 1); }
      else if (event.key === "Home" && tag !== "SUMMARY") { event.preventDefault(); go(0); }
      else if (event.key === "End" && tag !== "SUMMARY") {
        event.preventDefault(); go(state.fx.frames.length - 1);
      }
    });
    window.addEventListener("hashchange", () => fromHash(false));
    fromHash(true);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
})();
