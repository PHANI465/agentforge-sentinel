"""Thin integrated path over Postgres: ingest -> rule score -> alert/case -> investigation ->
human approval -> simulated action, with an audit event at each step.

Every query filters on the TrustedContext tenant AND session. Missing or foreign records are
indistinguishable (not_found). Case transitions use compare-and-set on revision.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import psycopg
from psycopg.types.json import Jsonb

from sentinel import db, scoring
from sentinel.contracts.http_v1 import CASE_STATES
from sentinel.contracts.guards import (
    ContractViolation, require_evidence_snapshot, require_executable_approval,
    require_execution_authority,
)
from sentinel.contracts.v1 import (
    ActionIntent, AgentRun, Alert, Approval, ApprovalDecisionInput, AuditEvent, Case, CasePins,
    EscalateParameters, EvidenceItem, ExecuteActionInput, Fact, HoldParameters,
    InvestigationFinding, RunBudget, Scope, ScoringOutcome, SimulatedAction, Transaction,
    TransactionInput,
    TrustedContext, canonical_digest, evidence_content_digest, evidence_snapshot_digest,
    intent_digest,
)
from sentinel.investigators import InvestigationView, Investigator, InvestigatorError

SYSTEM_ACTOR = uuid.uuid5(uuid.NAMESPACE_URL, "sentinel:system:ingest")
# A running investigation older than its timeout plus this grace is presumed lost.
RECOVERY_GRACE = timedelta(seconds=30)


class ServiceError(Exception):
    """Safe code-only error; status is the HTTP status the API should return."""

    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.code = code
        self.status = status


MAX_CURSOR_LENGTH = 200


def encode_cursor(created_at: datetime, case_id) -> str:
    raw = json.dumps([created_at.astimezone(timezone.utc).isoformat(), str(case_id)],
                     separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Opaque position only; it carries no authority (queries stay session-scoped)."""
    try:
        if len(cursor) > MAX_CURSOR_LENGTH:
            raise ValueError
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        created, case_id = json.loads(raw)
        when = datetime.fromisoformat(created)
        if when.tzinfo is None:
            raise ValueError
        return when, uuid.UUID(case_id)
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError):
        raise ServiceError("invalid_cursor", 422) from None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _dump(model) -> Jsonb:
    return Jsonb(model.model_dump(mode="json"))


def _scoped(ctx: TrustedContext) -> tuple[uuid.UUID, uuid.UUID]:
    return ctx.scope.tenant_id, ctx.scope.session_id


def _require(ctx: TrustedContext, capability: str, human: bool = False) -> None:
    if capability not in ctx.capabilities or (human and ctx.actor_kind != "human"):
        raise ServiceError("permission_denied", 403)


@dataclass
class Sentinel:
    database_url: str
    investigator: Investigator
    clock: Callable[[], datetime] = utc_now

    # ---- authentication -------------------------------------------------------------------

    def create_session(self, capabilities: frozenset[str], *, actor_kind: str = "human",
                       tenant_id: uuid.UUID | None = None, ttl: timedelta = timedelta(hours=8),
                       ) -> tuple[str, TrustedContext]:
        """Issue a random bearer token. Only its SHA-256 is stored; the caller shows it once."""
        token = secrets.token_urlsafe(32)
        ctx = TrustedContext(
            scope=Scope(tenant_id=tenant_id or uuid.uuid4(), session_id=uuid.uuid4()),
            actor_id=uuid.uuid4(), actor_kind=actor_kind, capabilities=capabilities)
        now = self.clock()
        with db.connect(self.database_url) as conn:
            conn.execute(
                "INSERT INTO api_sessions (token_sha256, tenant_id, session_id, actor_id,"
                " actor_kind, capabilities, created_at, expires_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (token_digest(token), *_scoped(ctx), ctx.actor_id, actor_kind,
                 sorted(capabilities), now, now + ttl))
        return token, ctx

    def authenticate(self, token: str) -> TrustedContext:
        with db.connect(self.database_url) as conn:
            row = conn.execute(
                "SELECT * FROM api_sessions WHERE token_sha256 = %s AND expires_at > %s",
                (token_digest(token), self.clock())).fetchone()
        if row is None:
            raise ServiceError("unauthenticated", 401)
        return TrustedContext(
            scope=Scope(tenant_id=row["tenant_id"], session_id=row["session_id"]),
            actor_id=row["actor_id"], actor_kind=row["actor_kind"],
            capabilities=frozenset(row["capabilities"]))

    # ---- ingestion and scoring ------------------------------------------------------------

    def ingest(self, ctx: TrustedContext, data: TransactionInput) -> dict:
        _require(ctx, "ingest_transaction")
        input_sha = canonical_digest("sentinel.transaction-input.v1", data.model_dump(mode="json"))
        tenant, session = _scoped(ctx)
        account_key = f"{tenant}:{session}:{data.account_id}"
        for _ in range(2):
            try:
                with db.connect(self.database_url) as conn, conn.transaction():
                    # One decision per account at a time, so each sees exactly the history
                    # committed before its decision time, which is read after the lock (R3).
                    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                                 (account_key,))
                    now = self.clock()
                    if data.occurred_at > now:
                        raise ServiceError("future_event_time", 422)
                    return self._ingest(conn, ctx, data, input_sha, now)
            except psycopg.errors.UniqueViolation:
                continue  # a concurrent identical external_id won; re-read it
        raise ServiceError("conflict", 409)

    def _ingest(self, conn, ctx, data, input_sha, now) -> dict:
        tenant, session = _scoped(ctx)
        existing = conn.execute(
            "SELECT id, input_sha256 FROM transactions"
            " WHERE tenant_id = %s AND session_id = %s AND external_id = %s",
            (tenant, session, data.external_id)).fetchone()
        if existing is not None:
            if existing["input_sha256"] != input_sha:
                raise ServiceError("idempotency_conflict", 409)
            return self._ingest_result(conn, ctx, existing["id"], replayed=True)
        # Events in [t-1h, t) that were available (ingested) by the decision time. Events at
        # exactly t are excluded regardless of arrival order.
        prior = conn.execute(
            "SELECT count(*) AS n FROM transactions WHERE tenant_id = %s AND session_id = %s"
            " AND account_id = %s AND occurred_at >= %s AND occurred_at < %s"
            " AND ingested_at <= %s",
            (tenant, session, data.account_id, data.occurred_at - timedelta(hours=1),
             data.occurred_at, now)).fetchone()["n"]
        txn = Transaction(**data.model_dump(), id=uuid.uuid4(), scope=ctx.scope, ingested_at=now,
                          dataset=scoring.DATASET)
        conn.execute(
            "INSERT INTO transactions (id, tenant_id, session_id, external_id, account_id,"
            " occurred_at, ingested_at, input_sha256, body)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (txn.id, tenant, session, txn.external_id, txn.account_id, txn.occurred_at,
             txn.ingested_at, input_sha, _dump(txn)))
        score = scoring.rule_score(txn, prior)
        outcome = ScoringOutcome(
            transaction_id=txn.id, scope=ctx.scope, scored_at=now, features_as_of=now,
            scorer=scoring.SCORER, features=scoring.FEATURES,
            threshold_policy=scoring.THRESHOLD_POLICY, scoring_kind="rule",
            score_semantics="heuristic", score=score, threshold=scoring.THRESHOLD,
            alerted=score >= scoring.THRESHOLD, prior_count_1h=prior)
        conn.execute("INSERT INTO scoring_outcomes (transaction_id, tenant_id, session_id, score,"
                     " alerted, body) VALUES (%s, %s, %s, %s, %s, %s)",
                     (txn.id, tenant, session, score, outcome.alerted, _dump(outcome)))
        if not outcome.alerted:
            return self._ingest_result(conn, ctx, txn.id, replayed=False)
        alert = Alert(
            id=uuid.uuid4(), scope=ctx.scope, transaction_id=txn.id, created_at=now,
            features_as_of=now, scorer=scoring.SCORER, features=scoring.FEATURES,
            threshold_policy=scoring.THRESHOLD_POLICY, scoring_kind="rule",
            score_semantics="heuristic", score=score, threshold=scoring.THRESHOLD)
        conn.execute("INSERT INTO alerts (id, tenant_id, session_id, transaction_id, body)"
                     " VALUES (%s, %s, %s, %s, %s)", (alert.id, tenant, session, txn.id,
                                                      _dump(alert)))
        case_id = uuid.uuid4()
        evidence = tuple(self._evidence(ctx, case_id, txn, now, source, ref, name, value)
                         for source, ref, name, value in (
                             ("synthetic_transaction", f"transactions:{txn.id}",
                              "amount_minor", txn.amount.minor_units),
                             ("historical_aggregate", f"velocity-1h:{txn.id}",
                              "transaction_count_1h", prior)))
        case = Case(
            id=case_id, scope=ctx.scope, alert_id=alert.id, revision=1, state="open",
            pins=CasePins(dataset=scoring.DATASET, scorer=scoring.SCORER,
                          threshold_policy=scoring.THRESHOLD_POLICY, policy=scoring.ACTION_POLICY,
                          agent_config=self.investigator.config, tool_config=scoring.TOOL_PROFILE,
                          evidence_snapshot_sha256=evidence_snapshot_digest(evidence)),
            evidence_ids=tuple(item.id for item in evidence), created_at=now, updated_at=now)
        conn.execute("INSERT INTO cases (id, tenant_id, session_id, alert_id, revision, state,"
                     " created_at, body) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                     (case.id, tenant, session, alert.id, 1, "open", case.created_at,
                      _dump(case)))
        for item in evidence:
            conn.execute("INSERT INTO evidence_items (id, tenant_id, session_id, case_id, body)"
                         " VALUES (%s, %s, %s, %s, %s)",
                         (item.id, tenant, session, case.id, _dump(item)))
        correlation = uuid.uuid4()
        for event_type in ("transaction_received", "alert_raised"):
            self._audit(conn, ctx, case, correlation, SYSTEM_ACTOR, "system", event_type,
                        "success", now)
        return self._ingest_result(conn, ctx, txn.id, replayed=False)

    @staticmethod
    def _evidence(ctx, case_id, txn, now, source, ref, name, value) -> EvidenceItem:
        draft = dict(id=uuid.uuid4(), scope=ctx.scope, case_id=case_id, source=source,
                     source_ref=ref, observed_at=txn.occurred_at, available_at=now,
                     facts=(Fact(name=name, value=value),), content_sha256="0" * 64)
        digest = evidence_content_digest(EvidenceItem(**draft))
        return EvidenceItem(**{**draft, "content_sha256": digest})

    def _ingest_result(self, conn, ctx, txn_id, *, replayed: bool) -> dict:
        tenant, session = _scoped(ctx)
        row = conn.execute(
            "SELECT t.body AS txn, s.body AS scoring, a.body AS alert, c.body AS case_body"
            " FROM transactions t LEFT JOIN scoring_outcomes s ON s.transaction_id = t.id"
            " LEFT JOIN alerts a ON a.transaction_id = t.id"
            " LEFT JOIN cases c ON c.alert_id = a.id"
            " WHERE t.id = %s AND t.tenant_id = %s AND t.session_id = %s",
            (txn_id, tenant, session)).fetchone()
        # Ingested before migration 0002: no recorded outcome, so no score is invented.
        score = row["scoring"]["score"] if row["scoring"] else None
        return {"transaction": row["txn"], "rule_score": score, "scoring": row["scoring"],
                "alert": row["alert"], "case": row["case_body"], "replayed": replayed}

    # ---- reads -----------------------------------------------------------------------------

    def _case(self, conn, ctx, case_id, *, lock: bool = False) -> Case:
        tenant, session = _scoped(ctx)
        row = conn.execute(
            "SELECT body FROM cases WHERE id = %s AND tenant_id = %s AND session_id = %s"
            + (" FOR UPDATE" if lock else ""), (case_id, tenant, session)).fetchone()
        if row is None:
            raise ServiceError("not_found", 404)
        return Case.model_validate(row["body"])

    def _rows(self, conn, ctx, table: str, case_id) -> list[dict]:
        tenant, session = _scoped(ctx)
        order = "seq" if table == "audit_events" else "id"
        return [row["body"] for row in conn.execute(
            f"SELECT body FROM {table} WHERE case_id = %s AND tenant_id = %s"
            f" AND session_id = %s ORDER BY {order}", (case_id, tenant, session))]

    def get_case(self, ctx: TrustedContext, case_id: uuid.UUID) -> dict:
        _require(ctx, "read_case")
        tenant, session = _scoped(ctx)
        with db.connect(self.database_url) as conn:
            case = self._case(conn, ctx, case_id)
            alert = conn.execute("SELECT body FROM alerts WHERE id = %s", (case.alert_id,)
                                 ).fetchone()["body"]
            txn = conn.execute("SELECT body FROM transactions WHERE id = %s",
                               (alert["transaction_id"],)).fetchone()["body"]
            scored = conn.execute("SELECT body FROM scoring_outcomes WHERE transaction_id = %s",
                                  (alert["transaction_id"],)).fetchone()
            runs = conn.execute(
                "SELECT body, finding FROM agent_runs WHERE case_id = %s AND tenant_id = %s"
                " AND session_id = %s ORDER BY started_at", (case.id, tenant, session)).fetchall()
            intents = conn.execute(
                "SELECT i.id, i.body, i.intent_sha256, ap.body AS approval, sa.body AS action"
                " FROM action_intents i LEFT JOIN approvals ap ON ap.intent_id = i.id"
                " LEFT JOIN simulated_actions sa ON sa.approval_id = ap.id"
                " WHERE i.case_id = %s AND i.tenant_id = %s AND i.session_id = %s"
                " ORDER BY i.case_revision", (case.id, tenant, session)).fetchall()
            evidence = self._rows(conn, ctx, "evidence_items", case.id)
        return {
            "case": case.model_dump(mode="json"), "alert": alert, "transaction": txn,
            "scoring": scored["body"] if scored else None, "evidence": evidence,
            "agent_runs": [{"run": r["body"], "finding": r["finding"]} for r in runs],
            "action_intents": [{"intent": i["body"], "intent_sha256": i["intent_sha256"],
                                "approval": i["approval"], "action": i["action"]}
                               for i in intents],
        }

    def list_cases(self, ctx: TrustedContext, *, limit: int, state: str | None = None,
                   cursor: str | None = None) -> dict:
        """Own-session cases, newest first; created_at ties are broken by id (keyset)."""
        _require(ctx, "read_case")
        tenant, session = _scoped(ctx)
        where, params = ["c.tenant_id = %s", "c.session_id = %s"], [tenant, session]
        if state is not None:
            where.append("c.state = %s")
            params.append(state)
        if cursor is not None:
            created_at, case_id = decode_cursor(cursor)
            where.append("(c.created_at, c.id) < (%s, %s)")
            params.extend([created_at, case_id])
        with db.connect(self.database_url) as conn:
            rows = conn.execute(
                "SELECT c.created_at, c.body AS case_body, a.body AS alert, t.body AS txn"
                " FROM cases c JOIN alerts a ON a.id = c.alert_id"
                " JOIN transactions t ON t.id = a.transaction_id"
                f" WHERE {' AND '.join(where)} ORDER BY c.created_at DESC, c.id DESC"
                " LIMIT %s", (*params, limit + 1)).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        items = [{
            "id": r["case_body"]["id"], "state": r["case_body"]["state"],
            "revision": r["case_body"]["revision"], "created_at": r["case_body"]["created_at"],
            "updated_at": r["case_body"]["updated_at"], "alert_id": r["alert"]["id"],
            "transaction_id": r["txn"]["id"], "external_id": r["txn"]["external_id"],
            "amount": r["txn"]["amount"], "direction": r["txn"]["direction"],
            "score": r["alert"]["score"], "threshold": r["alert"]["threshold"],
            "scoring_kind": r["alert"]["scoring_kind"],
            "score_semantics": r["alert"]["score_semantics"],
        } for r in rows]
        last = rows[-1] if more else None
        next_cursor = encode_cursor(last["created_at"], last["case_body"]["id"]) if last else None
        return {"items": items, "next_cursor": next_cursor, "limit": limit}

    def session_view(self, token: str) -> dict:
        with db.connect(self.database_url) as conn:
            row = conn.execute(
                "SELECT tenant_id, session_id, actor_id, actor_kind, capabilities, expires_at"
                " FROM api_sessions WHERE token_sha256 = %s AND expires_at > %s",
                (token_digest(token), self.clock())).fetchone()
        if row is None:
            raise ServiceError("unauthenticated", 401)
        return {**row, "capabilities": sorted(row["capabilities"])}

    def overview(self, ctx: TrustedContext) -> dict:
        _require(ctx, "read_case")
        scope = _scoped(ctx)
        where = "WHERE tenant_id = %s AND session_id = %s"
        with db.connect(self.database_url) as conn:
            by_state = {r["state"]: r["n"] for r in conn.execute(
                f"SELECT state, count(*) AS n FROM cases {where} GROUP BY state", scope)}
            counts = {table: conn.execute(f"SELECT count(*) AS n FROM {table} {where}",
                                          scope).fetchone()["n"]
                      for table in ("transactions", "alerts", "simulated_actions")}
        return {"cases_by_state": {state: by_state.get(state, 0) for state in CASE_STATES},
                **counts,
                "investigator": {"name": self.investigator.config.name,
                                 "version": self.investigator.config.version}}

    def get_audit(self, ctx: TrustedContext, case_id: uuid.UUID) -> list[dict]:
        _require(ctx, "read_case")
        with db.connect(self.database_url) as conn:
            self._case(conn, ctx, case_id)
            return self._rows(conn, ctx, "audit_events", case_id)

    # ---- investigation ---------------------------------------------------------------------

    def investigate(self, ctx: TrustedContext, case_id: uuid.UUID, expected_revision: int,
                    ) -> dict:
        run, view = self.begin_investigation(ctx, case_id, expected_revision)
        try:
            finding: InvestigationFinding | None = self.investigator.investigate(view)
            failure = None
        except InvestigatorError as error:
            finding, failure = None, error.code
        self.finish_investigation(ctx, run, finding, failure)
        return self.get_case(ctx, case_id)

    def begin_investigation(self, ctx, case_id, expected_revision) -> tuple[AgentRun,
                                                                             InvestigationView]:
        """Transaction 1: claim the case (open -> investigating) and record a running run."""
        _require(ctx, "read_case", human=True)
        with db.connect(self.database_url) as conn:
            with conn.transaction():
                case = self._case(conn, ctx, case_id, lock=True)
                now = self.clock()
                if case.revision != expected_revision:
                    raise ServiceError("stale_case_revision", 409)
                busy = case.state == "investigating"
                # Recovery or expiry (if any) commits with this block; the client re-reads.
                recovered = busy and self._recover_lost_run(conn, ctx, case, now)
                expired = (case.state == "awaiting_approval"
                           and self._expire_lapsed_approval(conn, ctx, case, now) is not None)
            if busy:
                raise ServiceError("investigation_recovered" if recovered
                                   else "investigation_in_progress", 409)
            if expired:
                raise ServiceError("approval_expired", 409)
            return self._claim(conn, ctx, case)

    def _claim(self, conn, ctx, case: Case) -> tuple[AgentRun, InvestigationView]:
        with conn.transaction():
            expected_revision = case.revision
            case = self._case(conn, ctx, case.id, lock=True)
            now = self.clock()
            if case.revision != expected_revision:
                raise ServiceError("stale_case_revision", 409)
            if case.state != "open":
                raise ServiceError("case_not_investigable", 409)
            if case.pins.agent_config != self.investigator.config:
                raise ServiceError("stale_agent_config", 409)
            evidence = tuple(EvidenceItem.model_validate(body)
                             for body in self._rows(conn, ctx, "evidence_items", case.id))
            try:
                require_evidence_snapshot(ctx, case, evidence, now)
            except ContractViolation as violation:
                raise ServiceError(str(violation), 409) from None
            alert = Alert.model_validate(conn.execute(
                "SELECT body FROM alerts WHERE id = %s", (case.alert_id,)).fetchone()["body"])
            txn = Transaction.model_validate(conn.execute(
                "SELECT body FROM transactions WHERE id = %s",
                (alert.transaction_id,)).fetchone()["body"])
            claimed = self._transition(conn, case, "investigating", now)
            run = AgentRun(
                id=uuid.uuid4(), scope=ctx.scope, case_id=case.id,
                case_revision=claimed.revision, role="investigator",
                principal_id=self.investigator.principal_id, config=self.investigator.config,
                tool_profile=case.pins.tool_config,
                input_snapshot_sha256=case.pins.evidence_snapshot_sha256,
                budget=RunBudget(timeout_seconds=self.investigator.timeout_seconds),
                status="running")
            conn.execute("INSERT INTO agent_runs (id, tenant_id, session_id, case_id, status,"
                         " started_at, body) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                         (run.id, *_scoped(ctx), case.id, "running", now, _dump(run)))
            self._audit(conn, ctx, claimed, uuid.uuid4(), ctx.actor_id, "human",
                        "investigation_started", "success", now)
        facts = {fact.name: fact.value for item in evidence for fact in item.facts}
        view = InvestigationView(facts=facts, currency=txn.amount.currency,
                                 large_amount=scoring.is_large_amount(txn),
                                 rule_score=alert.score, threshold=alert.threshold)
        return run, view

    def finish_investigation(self, ctx, run: AgentRun, finding: InvestigationFinding | None,
                             failure: str | None) -> None:
        """Transaction 2: record the outcome; on success the server builds the action intent."""
        now = self.clock()
        with db.connect(self.database_url) as conn, conn.transaction():
            case = self._case(conn, ctx, run.case_id, lock=True)
            if case.state != "investigating" or case.revision != run.case_revision:
                raise ServiceError("investigation_superseded", 409)
            if finding is None:
                self._fail_run(conn, ctx, case, run, failure or "invalid_output", now)
                return
            done = AgentRun.model_validate({**run.model_dump(), "status": "completed"})
            conn.execute("UPDATE agent_runs SET status = 'completed', finished_at = %s,"
                         " finding = %s, body = %s WHERE id = %s",
                         (now, _dump(finding), _dump(done), run.id))
            awaiting = self._transition(conn, case, "awaiting_approval", now)
            txn_row = conn.execute(
                "SELECT t.body FROM transactions t JOIN alerts a ON a.transaction_id = t.id"
                " WHERE a.id = %s", (case.alert_id,)).fetchone()
            txn = Transaction.model_validate(txn_row["body"])
            if finding.operation == "simulated_hold":
                parameters = HoldParameters(operation="simulated_hold", transaction_id=txn.id,
                                            amount=txn.amount)
            else:
                parameters = EscalateParameters(operation="escalate", transaction_id=txn.id,
                                                reason_code=finding.reason_code)
            intent = ActionIntent(
                id=uuid.uuid4(), scope=ctx.scope, case_id=case.id,
                case_revision=awaiting.revision,
                evidence_snapshot_sha256=case.pins.evidence_snapshot_sha256,
                policy=case.pins.policy, parameters=parameters)
            conn.execute("INSERT INTO action_intents (id, tenant_id, session_id, case_id,"
                         " case_revision, agent_run_id, intent_sha256, body)"
                         " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                         (intent.id, *_scoped(ctx), case.id, awaiting.revision, run.id,
                          intent_digest(intent), _dump(intent)))
            self._audit(conn, ctx, awaiting, uuid.uuid4(), run.principal_id, "agent",
                        "investigation_completed", "success", now)

    def _fail_run(self, conn, ctx, case, run, code, now) -> None:
        failed = AgentRun.model_validate({**run.model_dump(), "status": "failed",
                                          "failure_code": code})
        conn.execute("UPDATE agent_runs SET status = 'failed', finished_at = %s, body = %s"
                     " WHERE id = %s", (now, _dump(failed), run.id))
        reopened = self._transition(conn, case, "open", now)
        self._audit(conn, ctx, reopened, uuid.uuid4(), run.principal_id, "agent",
                    "investigation_completed", "failure", now)

    def _recover_lost_run(self, conn, ctx, case, now) -> bool:
        """Reopen a case whose run outlived its budget, e.g. after a server crash."""
        row = conn.execute("SELECT body, started_at FROM agent_runs WHERE case_id = %s"
                           " AND status = 'running'", (case.id,)).fetchone()
        if row is None:
            return False
        run = AgentRun.model_validate(row["body"])
        if row["started_at"] + timedelta(seconds=run.budget.timeout_seconds) + RECOVERY_GRACE > now:
            return False
        self._fail_run(conn, ctx, case, run, "timeout", now)
        return True

    def _expire_lapsed_approval(self, conn, ctx, case: Case, now) -> Case | None:
        """Reopen a case whose current intent's approval lapsed unused (review R8). The old
        approval is never revived: it stays bound to the superseded case revision."""
        row = conn.execute(
            "SELECT ap.body FROM action_intents i JOIN approvals ap ON ap.intent_id = i.id"
            " WHERE i.case_id = %s AND i.case_revision = %s", (case.id, case.revision)).fetchone()
        if row is None:
            return None
        approval = Approval.model_validate(row["body"])
        if (approval.decision != "approved" or approval.consumed_at is not None
                or now < approval.expires_at):
            return None
        reopened = self._transition(conn, case, "open", now)
        self._audit(conn, ctx, reopened, uuid.uuid4(), SYSTEM_ACTOR, "system", "approval_expired",
                    "success", now)
        return reopened

    # ---- approval and simulated execution --------------------------------------------------

    def record_approval(self, ctx: TrustedContext, data: ApprovalDecisionInput) -> dict:
        _require(ctx, "approve_action", human=True)
        tenant, session = _scoped(ctx)
        try:
            with db.connect(self.database_url) as conn, conn.transaction():
                row = conn.execute(
                    "SELECT body, intent_sha256 FROM action_intents WHERE id = %s"
                    " AND tenant_id = %s AND session_id = %s",
                    (data.action_intent_id, tenant, session)).fetchone()
                if row is None:
                    raise ServiceError("not_found", 404)
                intent = ActionIntent.model_validate(row["body"])
                case = self._case(conn, ctx, intent.case_id, lock=True)
                # Decision/expiry times are taken after the lock wait, so a delayed request
                # never returns an approval that is already expired.
                now = self.clock()
                if case.state != "awaiting_approval" or case.revision != intent.case_revision:
                    raise ServiceError("stale_case_revision", 409)
                approval = Approval(
                    id=uuid.uuid4(), intent=intent, intent_sha256=row["intent_sha256"],
                    actor_id=ctx.actor_id, decision=data.decision, decided_at=now,
                    expires_at=now + timedelta(seconds=scoring.APPROVAL_TTL_SECONDS))
                conn.execute("INSERT INTO approvals (id, tenant_id, session_id, intent_id,"
                             " decision, body) VALUES (%s, %s, %s, %s, %s, %s)",
                             (approval.id, tenant, session, intent.id, data.decision,
                              _dump(approval)))
                if data.decision == "rejected":
                    case = self._transition(conn, case, "closed", now)
                self._audit(conn, ctx, case, uuid.uuid4(), ctx.actor_id, "human",
                            "approval_recorded", "success", now)
        except psycopg.errors.UniqueViolation:
            raise ServiceError("approval_exists", 409) from None
        return approval.model_dump(mode="json")

    def execute_action(self, ctx: TrustedContext, data: ExecuteActionInput) -> dict:
        for _ in range(2):
            try:
                return self._execute(ctx, data)
            except psycopg.errors.UniqueViolation:
                continue  # concurrent use of this idempotency key; re-read the winner
        raise ServiceError("conflict", 409)

    def _execute(self, ctx, data) -> dict:
        tenant, session = _scoped(ctx)
        code: str | None = None
        with db.connect(self.database_url) as conn:
            with conn.transaction():
                # Lock order: approval, then case.
                row = conn.execute(
                    "SELECT a.body, i.intent_sha256 FROM approvals a"
                    " JOIN action_intents i ON i.id = a.intent_id"
                    " WHERE a.id = %s AND a.tenant_id = %s AND a.session_id = %s"
                    " FOR UPDATE OF a", (data.approval_id, tenant, session)).fetchone()
                if row is None:
                    raise ServiceError("not_found", 404)
                approval = Approval.model_validate(row["body"])
                case = self._case(conn, ctx, approval.intent.case_id, lock=True)
                # Validity is judged after every lock wait, never before (review R2).
                now = self.clock()
                existing = conn.execute(
                    "SELECT approval_id, body FROM simulated_actions"
                    " WHERE tenant_id = %s AND idempotency_key = %s",
                    (tenant, data.idempotency_key)).fetchone()
                try:
                    if existing is not None:
                        if existing["approval_id"] != data.approval_id:
                            raise ServiceError("idempotency_conflict", 409)
                        # A replay needs current authority, not fresh preconditions (R4).
                        require_execution_authority(ctx, approval)
                        return {"action": existing["body"], "replayed": True}
                    require_executable_approval(
                        ctx, approval, now=now, current_case=case,
                        current_intent_sha256=row["intent_sha256"],
                        active_policy=scoring.ACTION_POLICY)
                except ContractViolation as violation:
                    code = str(violation)
                if code is None:
                    return self._perform(conn, ctx, approval, case, data, now)
            # The denial is recorded in its own transaction; nothing above was changed.
            with conn.transaction():
                case = self._case(conn, ctx, case.id, lock=True)
                self._audit(conn, ctx, case, uuid.uuid4(), ctx.actor_id, ctx.actor_kind,
                            "action_denied", "denied", now)
                if code == "approval_outside_validity" and case.state == "awaiting_approval":
                    self._expire_lapsed_approval(conn, ctx, case, now)
        status = 403 if code in {"action_permission_denied", "approver_mismatch"} else 409
        raise ServiceError(code, status)

    def _perform(self, conn, ctx, approval, case, data, now) -> dict:
        consumed = Approval.model_validate({**approval.model_dump(), "consumed_at": now})
        updated = conn.execute("UPDATE approvals SET consumed_at = %s, body = %s"
                               " WHERE id = %s AND consumed_at IS NULL",
                               (now, _dump(consumed), approval.id))
        if updated.rowcount != 1:
            raise ServiceError("approval_not_available", 409)
        # The record itself is the simulated effect; no external system is contacted.
        action = SimulatedAction(
            id=uuid.uuid4(), intent=approval.intent, approval_id=approval.id,
            intent_sha256=approval.intent_sha256, idempotency_key=data.idempotency_key,
            state="succeeded", created_at=now, completed_at=now)
        conn.execute("INSERT INTO simulated_actions (id, tenant_id, session_id, approval_id,"
                     " idempotency_key, intent_sha256, body) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                     (action.id, *_scoped(ctx), approval.id, data.idempotency_key,
                      action.intent_sha256, _dump(action)))
        closed = self._transition(conn, case, "closed", now)
        self._audit(conn, ctx, closed, uuid.uuid4(), ctx.actor_id, "human", "action_succeeded",
                    "success", now)
        return {"action": action.model_dump(mode="json"), "replayed": False}

    # ---- shared steps ----------------------------------------------------------------------

    def _transition(self, conn, case: Case, state: str, now: datetime) -> Case:
        """Compare-and-set: succeeds only if the stored revision and state are unchanged."""
        nxt = Case.model_validate({**case.model_dump(), "state": state,
                                   "revision": case.revision + 1, "updated_at": now})
        updated = conn.execute(
            "UPDATE cases SET revision = %s, state = %s, body = %s"
            " WHERE id = %s AND revision = %s AND state = %s",
            (nxt.revision, state, _dump(nxt), case.id, case.revision, case.state))
        if updated.rowcount != 1:
            raise ServiceError("stale_case_revision", 409)
        return nxt

    def _audit(self, conn, ctx, case: Case, correlation, actor_id, actor_kind, event_type,
               outcome, occurred_at) -> None:
        event = AuditEvent(
            id=uuid.uuid4(), scope=ctx.scope, case_id=case.id, case_revision=case.revision,
            correlation_id=correlation, actor_id=actor_id, actor_kind=actor_kind,
            event_type=event_type, outcome=outcome, occurred_at=occurred_at,
            recorded_at=max(occurred_at, self.clock()))
        conn.execute("INSERT INTO audit_events (id, tenant_id, session_id, case_id, body)"
                     " VALUES (%s, %s, %s, %s, %s)",
                     (event.id, *_scoped(ctx), case.id, _dump(event)))
