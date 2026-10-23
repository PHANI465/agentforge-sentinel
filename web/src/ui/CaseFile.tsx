import { useEffect, useRef } from "react";
import { allows, approvalExpired, currentIntent, earlierIntents } from "../api/case";
import {
  artifactLabel,
  eventLabel,
  factLabel,
  failureLabel,
  formatMoney,
  formatScore,
  investigatorLabel,
  operationLabel,
  scoreLabel,
  stateLabel,
} from "../api/format";
import type { AuditEvent, CaseDetail, SessionView } from "../api/types";

export function CaseFile({
  detail,
  audit,
  session,
  busy,
  replayed,
  onInvestigate,
  onDecide,
  onExecute,
}: {
  detail: CaseDetail;
  audit: AuditEvent[];
  session: SessionView;
  busy: boolean;
  replayed: boolean;
  onInvestigate: () => void;
  onDecide: (decision: "approved" | "rejected") => void;
  onExecute: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const intent = currentIntent(detail);
  const history = earlierIntents(detail);
  const scoring = detail.scoring;
  const scoreKind = scoring?.scoring_kind ?? detail.alert.scoring_kind;
  const scoreSemantics = scoring?.score_semantics ?? detail.alert.score_semantics;
  const score = scoring?.score ?? detail.alert.score;
  const threshold = scoring?.threshold ?? detail.alert.threshold;
  const flagged = typeof score === "number" && typeof threshold === "number" && score >= threshold;

  useEffect(() => {
    heading.current?.focus();
  }, [detail.case.id]);

  return (
    <article className="case" id="case" aria-labelledby="case-heading">
      <h2 id="case-heading" ref={heading} tabIndex={-1}>
        {stateLabel(detail.case.state)}
      </h2>
      <p className={detail.case.state === "awaiting_approval" ? "hold" : detail.case.state === "closed" ? "closed" : "meta"}>
        Revision {detail.case.revision}
      </p>
      <p className="amount">{formatMoney(detail.transaction.amount)}</p>
      <p className="meta">{detail.transaction.direction === "debit" ? "Debit" : "Credit"}</p>
      <p>Synthetic transaction {detail.transaction.external_id}</p>
      <p className={flagged ? "alert-score" : undefined}>
        {scoring ? scoreLabel(scoreKind, scoreSemantics) : "Score unknown"} {scoring ? formatScore(score) : ""}
        {scoring ? `, threshold ${formatScore(threshold)}` : ""}
        {scoring && flagged ? ", at or above threshold" : ""}
      </p>
      {scoring ? (
        <p className="meta">
          Scorer {artifactLabel(scoring.scorer)}. Features {artifactLabel(scoring.features)}. Threshold policy{" "}
          {artifactLabel(scoring.threshold_policy)}.
        </p>
      ) : (
        <p>No recorded scoring outcome is stored for this transaction.</p>
      )}
      <div className="block">
        <h3>Transaction</h3>
        <p>Account {detail.transaction.account_id}</p>
        <p>Occurred {detail.transaction.occurred_at}</p>
        <p>Ingested {detail.transaction.ingested_at}</p>
      </div>
      <div className="block">
        <h3>Evidence</h3>
        {detail.evidence.length === 0 ? <p>No evidence is attached.</p> : null}
        <ul>
          {detail.evidence.map((item) => (
            <li key={item.id}>
              <p>
                {item.source} from {item.source_ref}
              </p>
              <ul>
                {item.facts.map((fact) => (
                  <li key={`${item.id}-${fact.name}`}>{factLabel(fact.name, fact.value)}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </div>
      <div className="block">
        <h3>Investigation</h3>
        {detail.agent_runs.length === 0 ? <p>No investigation has been recorded.</p> : null}
        {detail.agent_runs.map((view) => (
          <div key={view.run.id}>
            <p>Run by {investigatorLabel(view.run.config)}</p>
            {view.run.status === "failed" ? <p>{failureLabel(view.run.failure_code)}</p> : null}
            {view.finding ? (
              <>
                <p>
                  {operationLabel(view.finding.operation)}, reason {view.finding.reason_code}
                </p>
                <p className="rationale">{view.finding.rationale}</p>
              </>
            ) : null}
          </div>
        ))}
      </div>
      <div className="block">
        <h3>Proposed action</h3>
        {intent ? <Proposal intent={intent} /> : <p>No action is proposed for revision {detail.case.revision}.</p>}
        {approvalExpired(audit) ? (
          <p>An earlier approval expired. Investigate this revision before making a new decision.</p>
        ) : null}
        <div className="actions">
          {detail.case.state === "open" && allows(session, "read_case", true) ? (
            <button type="button" onClick={onInvestigate} disabled={busy}>
              Investigate case
            </button>
          ) : null}
          {detail.case.state === "investigating" ? <p>Investigation in progress.</p> : null}
          {intent && !intent.approval && detail.case.state === "awaiting_approval" ? (
            allows(session, "approve_action", true) ? (
              <>
                <button type="button" onClick={() => onDecide("approved")} disabled={busy}>
                  Approve
                </button>
                <button type="button" className="secondary" onClick={() => onDecide("rejected")} disabled={busy}>
                  Reject
                </button>
              </>
            ) : (
              <p>This session cannot approve or reject actions.</p>
            )
          ) : null}
          {intent &&
          intent.approval?.decision === "approved" &&
          !intent.action &&
          detail.case.state === "awaiting_approval" ? (
            allows(session, "execute_simulated_action", true) ? (
              <button type="button" onClick={onExecute} disabled={busy}>
                Execute {operationLabel(intent.intent.parameters.operation).toLowerCase()}
              </button>
            ) : (
              <p>This session cannot execute simulated actions.</p>
            )
          ) : null}
        </div>
        {intent?.approval?.decision === "rejected" ? <p>This proposal was rejected.</p> : null}
        {intent?.action ? (
          <p>
            {operationLabel(intent.action.intent.parameters.operation)} of{" "}
            {formatMoney(intent.action.intent.parameters.amount)} was recorded
            {intent.action.mode === "simulated" ? " as a simulation" : ""}. State {intent.action.state}.
          </p>
        ) : null}
        {replayed ? <p>This execution was already recorded. No second action was created.</p> : null}
      </div>
      {history.length > 0 ? (
        <div className="block">
          <h3>Earlier proposals</h3>
          <ul>
            {history.map((item) => (
              <li key={item.intent.id}>
                Revision {item.intent.case_revision}: {operationLabel(item.intent.parameters.operation)} of{" "}
                {formatMoney(item.intent.parameters.amount)}
                {item.approval ? `, ${item.approval.decision}` : ""}
                {item.action ? ", executed" : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="block">
        <h3>Audit</h3>
        {audit.length === 0 ? <p>No audit events are recorded.</p> : null}
        <ol className="audit">
          {audit.map((event) => (
            <li key={event.id}>
              {eventLabel(event.event_type)} at revision {event.case_revision}, {event.outcome},{" "}
              {event.occurred_at}
            </li>
          ))}
        </ol>
      </div>
    </article>
  );
}

function Proposal({ intent }: { intent: NonNullable<ReturnType<typeof currentIntent>> }) {
  const parameters = intent.intent.parameters;
  return (
    <div>
      <p>
        {operationLabel(parameters.operation)} of {formatMoney(parameters.amount)} on transaction{" "}
        {parameters.transaction_id}
      </p>
      <p className="meta">
        Policy {artifactLabel(intent.intent.policy)}. Bound to revision {intent.intent.case_revision}.
      </p>
      <p className="meta hash">Evidence snapshot {intent.intent.evidence_snapshot_sha256}</p>
      {intent.approval ? (
        <p>
          Decision {intent.approval.decision}, expires {intent.approval.expires_at}
          {intent.approval.consumed_at ? `, consumed ${intent.approval.consumed_at}` : ""}
        </p>
      ) : (
        <p>Waiting for a human decision.</p>
      )}
    </div>
  );
}
