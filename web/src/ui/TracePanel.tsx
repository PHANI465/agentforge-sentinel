import { useEffect, useRef, useState } from "react";
import type { SentinelClient } from "../api/client";
import type { Claim, InvestigationTrace, RoleAttempt, RoleOutput, ToolResult, WorkflowTrace } from "../api/trace";
import {
  attemptStatusLabel,
  checkText,
  countOrUnknown,
  deadlineLabel,
  dispositionLabel,
  elapsedText,
  factName,
  failureText,
  roleLabel,
  terminalLabel,
  usageText,
  workflowStatusLabel,
} from "../api/traceFormat";

/**
 * Read-only investigation trace (HTTP v1.2). It only ever GETs the trace route: it never
 * investigates, recovers, approves or executes. Each response is applied only if its token,
 * case, workflow selection and request generation are still current.
 */
export type TraceState =
  | { phase: "idle" }
  | { phase: "denied" }
  | { phase: "unavailable" }
  // `history` is the previous workflow list of the same session and case, kept visible while
  // another workflow of that case loads; it is never carried to another case or token.
  | { phase: "loading"; history?: InvestigationTrace | null }
  | {
      phase: "failed";
      message: string;
      ambiguous: boolean;
      selectionMissing: boolean;
      history?: InvestigationTrace | null;
    }
  | { phase: "ready"; trace: InvestigationTrace };

export interface TraceControl {
  state: TraceState;
  /** null follows the newest workflow; an id keeps that workflow selected. */
  workflowId: string | null;
  select: (workflowId: string | null) => void;
  retry: () => void;
}

export function useTrace({
  client,
  token,
  caseId,
  canRead,
  refreshKey,
}: {
  client: SentinelClient;
  token: string;
  caseId: string | null;
  canRead: boolean;
  refreshKey: number;
}): TraceControl {
  const [state, setState] = useState<TraceState>({ phase: "idle" });
  const [choice, setChoice] = useState<{ caseId: string | null; workflowId: string | null }>({
    caseId: null,
    workflowId: null,
  });
  const [retries, setRetries] = useState(0);
  const generation = useRef(0);
  const last = useRef<{ token: string; caseId: string; trace: InvestigationTrace } | null>(null);
  // A selection belongs to one case; another case always starts at its newest workflow.
  const workflowId = choice.caseId === caseId ? choice.workflowId : null;

  useEffect(() => {
    const current = ++generation.current;
    if (!caseId) {
      setState({ phase: "idle" });
      return;
    }
    if (!canRead) {
      setState({ phase: "denied" });
      return;
    }
    if (typeof client.trace !== "function") {
      setState({ phase: "unavailable" });
      return;
    }
    // Old private content is cleared before any new read; only the same session's list of
    // this case's workflows stays visible while one of them loads.
    const history = last.current && last.current.token === token && last.current.caseId === caseId
      ? last.current.trace
      : null;
    if (!history) last.current = null;
    setState({ phase: "loading", history });
    const controller = new AbortController();
    void client.trace(token, caseId, workflowId, controller.signal).then((result) => {
      if (controller.signal.aborted || current !== generation.current) return;
      if (result.ok) {
        // A body for another case (or another selected workflow) is never shown here.
        const selected = result.data.selected?.workflow.id ?? null;
        if (result.data.case_id !== caseId || (workflowId !== null && selected !== workflowId)) {
          setState({ phase: "failed", message: "The trace response did not match this case. Try again.", ambiguous: true, selectionMissing: false });
          return;
        }
        last.current = { token, caseId, trace: result.data };
        setState({ phase: "ready", trace: result.data });
        return;
      }
      if (result.status === 405) {
        setState({ phase: "unavailable" });
        return;
      }
      setState({
        phase: "failed",
        message: result.status === 404 && workflowId !== null
          ? "That workflow is not available for this case."
          : result.status === 404
            ? "No investigation trace is available for this case."
            : result.message,
        ambiguous: result.ambiguous,
        selectionMissing: result.status === 404 && workflowId !== null,
        history,
      });
    });
    return () => {
      controller.abort();
    };
  }, [client, token, caseId, canRead, workflowId, refreshKey, retries]);

  return {
    state,
    workflowId,
    select: (next) => setChoice({ caseId, workflowId: next }),
    retry: () => setRetries((value) => value + 1),
  };
}

export function TracePanel({
  control,
  caseRevision,
  evidenceIds,
}: {
  control: TraceControl;
  caseRevision: number;
  evidenceIds: ReadonlySet<string>;
}) {
  const { state, workflowId, select, retry } = control;
  return (
    <section className="case trace" id="trace" aria-labelledby="trace-heading">
      <h2 id="trace-heading">Investigation trace</h2>
      <p className="meta">
        Read-only record of the three-role workflow. Nothing here approves or executes an action.
      </p>
      {state.phase === "denied" ? <p>This session cannot read investigation traces.</p> : null}
      {state.phase === "unavailable" ? <p>This server does not provide investigation traces.</p> : null}
      {state.phase === "loading" || state.phase === "failed" ? (
        state.history && state.history.workflow_count > 0 ? (
          <WorkflowHistory
            trace={state.history}
            explicit={workflowId !== null}
            selectedId={workflowId ?? state.history.workflows[0]?.id ?? null}
            onSelect={select}
          />
        ) : null
      ) : null}
      {state.phase === "loading" ? <p role="status">Loading the investigation trace.</p> : null}
      {state.phase === "failed" ? (
        <div role="alert">
          <p>{state.message}</p>
          <div className="actions">
            {state.selectionMissing ? (
              <button type="button" onClick={() => select(null)}>
                Show the newest workflow
              </button>
            ) : (
              <button type="button" onClick={retry}>
                Retry
              </button>
            )}
          </div>
        </div>
      ) : null}
      {state.phase === "ready" ? (
        <TraceBody
          trace={state.trace}
          caseRevision={caseRevision}
          explicit={workflowId !== null}
          evidenceIds={evidenceIds}
          onSelect={select}
          onRefresh={retry}
        />
      ) : null}
    </section>
  );
}

function TraceBody({
  trace,
  caseRevision,
  explicit,
  evidenceIds,
  onSelect,
  onRefresh,
}: {
  trace: InvestigationTrace;
  caseRevision: number;
  explicit: boolean;
  evidenceIds: ReadonlySet<string>;
  onSelect: (workflowId: string | null) => void;
  onRefresh: () => void;
}) {
  const newest = trace.workflows[0]?.id ?? null;
  const selected = trace.selected;
  return (
    <>
      <p>
        Read at {trace.read_at} for case revision {trace.case_revision}.{" "}
        <button type="button" className="secondary" onClick={onRefresh}>
          Refresh trace
        </button>
      </p>
      {trace.case_revision !== caseRevision ? (
        <p className="hold">
          This trace snapshot was read at case revision {trace.case_revision}; the case shown above is at revision{" "}
          {caseRevision}. Refresh the trace to read them together.
        </p>
      ) : null}
      {trace.workflow_count === 0 ? (
        trace.legacy_investigator_runs > 0 ? (
          <p>
            This case was investigated by the single investigator ({trace.legacy_investigator_runs}{" "}
            {trace.legacy_investigator_runs === 1 ? "run" : "runs"}, listed under Investigation above). There is no
            three-role workflow trace.
          </p>
        ) : (
          <p>No three-role workflow has been recorded for this case.</p>
        )
      ) : (
        <WorkflowHistory
          trace={trace}
          explicit={explicit}
          selectedId={trace.selected?.workflow.id ?? null}
          onSelect={onSelect}
        />
      )}
      {selected ? (
        <SelectedWorkflow
          selected={selected}
          isNewest={selected.workflow.id === newest}
          evidenceIds={evidenceIds}
        />
      ) : null}
    </>
  );
}

function WorkflowHistory({
  trace,
  explicit,
  selectedId,
  onSelect,
}: {
  trace: InvestigationTrace;
  explicit: boolean;
  selectedId: string | null;
  onSelect: (workflowId: string | null) => void;
}) {
  const capped = trace.workflows.length < trace.workflow_count;
  return (
    <div className="block">
      <h3>Workflows</h3>
      <p className="meta">
        {capped
          ? `Showing the newest ${trace.workflows.length} of ${trace.workflow_count} workflows. Older workflows are not listed here.`
          : `${trace.workflow_count} ${trace.workflow_count === 1 ? "workflow" : "workflows"}, newest first.`}
      </p>
      {explicit ? (
        <p>
          <button type="button" className="secondary" onClick={() => onSelect(null)}>
            Follow the newest workflow
          </button>
        </p>
      ) : null}
      <div className="table-wrap">
        <table className="data">
          <caption>Workflow history</caption>
          <thead>
            <tr>
              <th scope="col">Case revision</th>
              <th scope="col">Status</th>
              <th scope="col">Outcome</th>
              <th scope="col">Started</th>
              <th scope="col">View</th>
            </tr>
          </thead>
          <tbody>
            {trace.workflows.map((item, index) => (
              <tr key={item.id} className={item.id === selectedId ? "selected-record" : undefined}>
                <td>{item.case_revision}</td>
                <td>
                  {workflowStatusLabel(item.status)}
                  {item.terminal_by === "recovery" ? ", recovered" : ""}
                </td>
                <td>{item.disposition_kind ?? "not yet recorded"}{item.inconclusive_code ? ` (${item.inconclusive_code})` : ""}</td>
                <td>{item.started_at}</td>
                <td>
                  <button
                    type="button"
                    className="secondary"
                    aria-pressed={item.id === selectedId}
                    aria-label={`View workflow at case revision ${item.case_revision}${index === 0 ? " (newest)" : ""}`}
                    onClick={() => onSelect(index === 0 ? null : item.id)}
                  >
                    {item.id === selectedId ? "Shown" : "View"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SelectedWorkflow({
  selected,
  isNewest,
  evidenceIds,
}: {
  selected: WorkflowTrace;
  isNewest: boolean;
  evidenceIds: ReadonlySet<string>;
}) {
  const workflow = selected.workflow;
  const toolIds = new Set(selected.tool_results.map((item) => item.id));
  const deadline = deadlineLabel(workflow.deadline_status);
  const terminal = terminalLabel(workflow);
  return (
    <div className="block" aria-labelledby="selected-workflow-heading">
      <h3 id="selected-workflow-heading">
        {isNewest ? "Newest workflow" : "Earlier workflow"}: {workflowStatusLabel(workflow.status)}
      </h3>
      {!isNewest ? (
        <p className="hold">
          This is an earlier workflow. It is history only; any current proposal is shown under Proposed action above.
        </p>
      ) : null}
      <p>Case revision {workflow.case_revision}. Started {workflow.started_at}. Deadline {workflow.deadline_at}.</p>
      {workflow.finished_at ? <p>Finished {workflow.finished_at}.</p> : null}
      {deadline ? <p className={workflow.deadline_status === "before_deadline" ? undefined : "hold"}>{deadline}</p> : null}
      {terminal ? <p>{terminal}</p> : null}
      <p>
        <strong>Server outcome:</strong> {dispositionLabel(workflow.disposition)}
      </p>
      {workflow.disposition && workflow.disposition.kind !== "inconclusive" ? (
        <p className="meta">
          This is the coordinator&apos;s recommendation, not an approval. A human decides under Proposed action.
          Claims: {workflow.disposition.supported_claims} supported, {workflow.disposition.unsupported_claims} not
          supported.
        </p>
      ) : null}
      <p>
        {countOrUnknown(workflow.recorded_role_invocations, "Recorded role attempts")}.{" "}
        {countOrUnknown(workflow.recorded_tool_calls, "Executed tool calls")}.
      </p>
      <UsageSummaryView selected={selected} />
      <h4>Role attempts</h4>
      {selected.attempts.length === 0 ? (
        <p>No role attempt was recorded in this workflow.</p>
      ) : (
        <ol className="attempts">
          {selected.attempts.map((attempt) => (
            <li key={attempt.agent_run_id}>
              <Attempt attempt={attempt} evidenceIds={evidenceIds} toolIds={toolIds} />
            </li>
          ))}
        </ol>
      )}
      <h4>Tool results</h4>
      {selected.tool_results.length === 0 ? <p>No tool result was recorded.</p> : <ToolTable results={selected.tool_results} />}
      <Limits limits={selected.limits} />
      <Steps selected={selected} />
      <details className="tech">
        <summary>Technical identifiers</summary>
        <p className="meta hash">Workflow {workflow.id}</p>
        <p className="meta hash">
          Config {workflow.config.name} {workflow.config.version} {workflow.config.sha256}
        </p>
        <p className="meta hash">
          Tool profile {workflow.tool_profile.name} {workflow.tool_profile.version} {workflow.tool_profile.sha256}
        </p>
        <p className="meta hash">Input snapshot {workflow.input_snapshot_sha256}</p>
        {workflow.disposition?.basis_run_id ? (
          <p className="meta hash">Basis run {workflow.disposition.basis_run_id}</p>
        ) : null}
      </details>
    </div>
  );
}

function UsageSummaryView({ selected }: { selected: WorkflowTrace }) {
  const usage = selected.usage_summary;
  return (
    <p className="meta">
      {usage.reported_attempts > 0
        ? `Adapter-reported tokens over ${usage.reported_attempts} reported ${usage.reported_attempts === 1 ? "attempt" : "attempts"}: ${usage.input_tokens ?? "unknown"} input, ${usage.output_tokens ?? "unknown"} output. `
        : "No attempt reported token usage. "}
      Not applicable: {usage.not_applicable_attempts}. Unknown or not recorded: {usage.unknown_attempts}. Token counts
      are not billing, and attempts are not provider calls.
    </p>
  );
}

function Attempt({
  attempt,
  evidenceIds,
  toolIds,
}: {
  attempt: RoleAttempt;
  evidenceIds: ReadonlySet<string>;
  toolIds: ReadonlySet<string>;
}) {
  const failure = failureText(attempt.failure_code, attempt.failure_source);
  return (
    <article className="attempt" aria-label={`${roleLabel(attempt.role)} attempt ${attempt.attempt}`}>
      <h5>
        {roleLabel(attempt.role)}, attempt {attempt.attempt}: {attemptStatusLabel(attempt)}
        {attempt.basis ? " (basis of the outcome)" : ""}
      </h5>
      {failure ? <p className="alert-score">{failure}</p> : null}
      {attempt.worker_unresolved ? (
        <p>
          When the coordinator stopped waiting, this call&apos;s worker had not returned. That record does not say whether
          it is still running now.
        </p>
      ) : null}
      <p className="meta">
        Started {attempt.started_at}
        {attempt.finished_at ? `, ended ${attempt.finished_at}` : ", no end recorded"}. {elapsedText(attempt.elapsed_ms)}{" "}
        {usageText(attempt.usage)}
      </p>
      {attempt.output ? (
        <Output
          output={attempt.output}
          checks={attempt.claim_checks}
          evidenceIds={evidenceIds}
          toolIds={toolIds}
        />
      ) : attempt.status === "completed" ? null : (
        <p>No role output was recorded for this attempt.</p>
      )}
      {attempt.finding ? (
        <div>
          <p>
            <strong>Server-rendered finding:</strong> {attempt.finding.operation}, reason {attempt.finding.reason_code}
          </p>
          <p className="rationale">{attempt.finding.rationale}</p>
        </div>
      ) : null}
      <details className="tech">
        <summary>Attempt identifiers</summary>
        <p className="meta hash">Run {attempt.agent_run_id}</p>
        <p className="meta hash">
          Role config {attempt.config.name} {attempt.config.version} {attempt.config.sha256}
        </p>
        {attempt.output_sha256 ? <p className="meta hash">Output {attempt.output_sha256}</p> : null}
      </details>
    </article>
  );
}

function Output({
  output,
  checks,
  evidenceIds,
  toolIds,
}: {
  output: RoleOutput;
  checks: RoleAttempt["claim_checks"];
  evidenceIds: ReadonlySet<string>;
  toolIds: ReadonlySet<string>;
}) {
  const claims = output.role === "reviewer" ? [] : output.claims;
  return (
    <div>
      {output.role === "investigator" ? (
        <p>
          Role proposal (untrusted): {output.operation}, reason {output.reason_code}.
        </p>
      ) : null}
      {output.role === "reviewer" ? (
        <p>
          Reviewer verdict: {output.verdict}
          {output.challenged_claims.length > 0 ? `, challenged claims ${output.challenged_claims.join(", ")}` : ""}
          {output.reasons.length > 0 ? `, reasons ${output.reasons.join(", ")}` : ""}. A reviewer verdict is not a human
          approval.
        </p>
      ) : null}
      {claims.length > 0 ? (
        <>
          <p className="meta">
            Claims made by the role (untrusted).{" "}
            {checks === null ? "The server's checks of these claims were not recorded." : "Each shows the server's recorded check."}
          </p>
          <ol className="claims" start={0}>
            {claims.map((claim, index) => (
              <li key={index}>
                <ClaimText claim={claim} evidenceIds={evidenceIds} toolIds={toolIds} />{" "}
                <span className="meta">{checkText(checks?.find((item) => item.index === index), checks !== null)}</span>
              </li>
            ))}
          </ol>
        </>
      ) : null}
      {output.role === "evidence_analyst" && output.missing.length > 0 ? (
        <p>Reported as unavailable: {output.missing.map(factName).join(", ")}.</p>
      ) : null}
      {output.role !== "reviewer" && output.tool_requests.length > 0 ? (
        <p>
          Requested tools:{" "}
          {output.tool_requests.map((item) => `${item.tool}${item.window ? ` (${item.window})` : ""}`).join(", ")}.
        </p>
      ) : null}
      {output.note !== null ? (
        <div>
          <p className="meta">Role note (untrusted text):</p>
          <p className="rationale">{output.note}</p>
        </div>
      ) : null}
    </div>
  );
}

function ClaimText({
  claim,
  evidenceIds,
  toolIds,
}: {
  claim: Claim;
  evidenceIds: ReadonlySet<string>;
  toolIds: ReadonlySet<string>;
}) {
  if (claim.kind === "missing") return <span>{factName(claim.fact)} is not available.</span>;
  const relation = claim.relation === "eq" ? "=" : claim.relation === "gte" ? "≥" : "≤";
  const known = claim.cite.kind === "evidence" ? evidenceIds.has(claim.cite.id) : toolIds.has(claim.cite.id);
  const label = claim.cite.kind === "evidence" ? "case evidence" : "tool result";
  const target = claim.cite.kind === "evidence" ? `evidence-${claim.cite.id}` : `tool-result-${claim.cite.id}`;
  return (
    <span>
      {factName(claim.fact)} {relation} {String(claim.value)}, citing{" "}
      {known ? <a href={`#${target}`}>{label}</a> : <span>{label} not shown here</span>}.
    </span>
  );
}

function ToolTable({ results }: { results: ToolResult[] }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <caption>Tool results, in recorded order</caption>
        <thead>
          <tr>
            <th scope="col">Tool</th>
            <th scope="col">Status</th>
            <th scope="col">Values</th>
          </tr>
        </thead>
        <tbody>
          {results.map((item) => (
            <tr key={item.id} id={`tool-result-${item.id}`}>
              <td>
                {item.tool}
                {item.window ? ` (${item.window})` : ""}
              </td>
              <td>
                {item.status}
                {item.denial ? `: ${item.denial.replace(/_/g, " ")}` : ""}
              </td>
              <td>
                {Object.keys(item.values).length === 0
                  ? "none"
                  : Object.entries(item.values)
                      .map(([name, value]) => `${factName(name)} ${String(value)}`)
                      .join("; ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Limits({ limits }: { limits: Record<string, number> | null }) {
  return (
    <>
      <h4>Recorded limits</h4>
      {limits === null ? (
        <p>This server does not know this workflow&apos;s recorded limits. Unknown limits are not unlimited.</p>
      ) : (
        <>
          <p className="meta">
            Limits of the workflow&apos;s recorded configuration. Limits ending in &quot;per process&quot; apply to one API
            process, not to an account or provider.
          </p>
          <div className="table-wrap">
            <table className="data">
              <caption>Workflow limits</caption>
              <tbody>
                {Object.entries(limits).map(([name, value]) => (
                  <tr key={name}>
                    <th scope="row">{factName(name)}</th>
                    <td>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

function Steps({ selected }: { selected: WorkflowTrace }) {
  return (
    <details className="tech">
      <summary>Recorded steps ({selected.steps.length})</summary>
      <p className="meta">
        In stored sequence order. Gaps in the sequence are possible. The final step&apos;s elapsed time is a stored marker
        of 0, not a duration.
      </p>
      <div className="table-wrap">
        <table className="data">
          <caption>Workflow steps</caption>
          <thead>
            <tr>
              <th scope="col">Seq</th>
              <th scope="col">Kind</th>
              <th scope="col">State</th>
              <th scope="col">Role</th>
              <th scope="col">Detail</th>
              <th scope="col">Elapsed since start</th>
              <th scope="col">At</th>
            </tr>
          </thead>
          <tbody>
            {selected.steps.map((step) => (
              <tr key={step.seq}>
                <td>{step.seq}</td>
                <td>{step.kind.replace(/_/g, " ")}</td>
                <td>{step.state.replace(/_/g, " ")}</td>
                <td>
                  {step.role ? roleLabel(step.role) : ""}
                  {step.attempt !== null ? `, attempt ${step.attempt}` : ""}
                </td>
                <td>
                  {[step.tool, step.failure_code, step.worker_unresolved ? "worker unresolved" : null,
                    step.checks.length > 0 ? `${step.checks.length} checks` : null]
                    .filter(Boolean)
                    .join(", ")}
                </td>
                <td>{step.kind === "workflow_terminated" ? "stored marker" : `${step.elapsed_ms} ms`}</td>
                <td>{step.at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
