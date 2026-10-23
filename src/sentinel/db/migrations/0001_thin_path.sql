-- Thin integrated path. Every row carries tenant/session scope; services filter on both.
-- body holds the validated v1 contract JSON; key columns exist for constraints and lookups.

CREATE TABLE api_sessions (
    token_sha256 text PRIMARY KEY CHECK (token_sha256 ~ '^[0-9a-f]{64}$'),
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
    capabilities text[] NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > created_at)
);

CREATE TABLE transactions (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    external_id text NOT NULL,
    account_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL CHECK (ingested_at >= occurred_at),
    input_sha256 text NOT NULL,
    body jsonb NOT NULL,
    UNIQUE (tenant_id, session_id, external_id)
);
CREATE INDEX transactions_velocity ON transactions (tenant_id, session_id, account_id, occurred_at);

CREATE TABLE alerts (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    transaction_id uuid NOT NULL UNIQUE REFERENCES transactions (id),
    body jsonb NOT NULL
);

CREATE TABLE cases (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    alert_id uuid NOT NULL UNIQUE REFERENCES alerts (id),
    revision integer NOT NULL CHECK (revision >= 1),
    state text NOT NULL
        CHECK (state IN ('open', 'investigating', 'awaiting_approval', 'closed', 'inconclusive')),
    body jsonb NOT NULL
);

CREATE TABLE evidence_items (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    case_id uuid NOT NULL REFERENCES cases (id),
    body jsonb NOT NULL
);

CREATE TABLE agent_runs (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    case_id uuid NOT NULL REFERENCES cases (id),
    status text NOT NULL,
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    finding jsonb,
    body jsonb NOT NULL
);
-- At most one in-flight investigation per case.
CREATE UNIQUE INDEX agent_runs_one_running ON agent_runs (case_id) WHERE status = 'running';

CREATE TABLE action_intents (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    case_id uuid NOT NULL REFERENCES cases (id),
    case_revision integer NOT NULL,
    agent_run_id uuid NOT NULL REFERENCES agent_runs (id),
    intent_sha256 text NOT NULL,
    body jsonb NOT NULL,
    UNIQUE (case_id, case_revision)
);

CREATE TABLE approvals (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    intent_id uuid NOT NULL UNIQUE REFERENCES action_intents (id),
    decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
    consumed_at timestamptz,
    body jsonb NOT NULL,
    CHECK (consumed_at IS NULL OR decision = 'approved')
);

CREATE TABLE simulated_actions (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    approval_id uuid NOT NULL UNIQUE REFERENCES approvals (id),
    idempotency_key uuid NOT NULL,
    intent_sha256 text NOT NULL,
    body jsonb NOT NULL,
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE audit_events (
    seq bigserial PRIMARY KEY,
    id uuid NOT NULL UNIQUE,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    case_id uuid NOT NULL REFERENCES cases (id),
    body jsonb NOT NULL
);

-- Append-only for application roles. A database owner can still drop this trigger,
-- so this is not a tamper-proof log.
CREATE FUNCTION audit_events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only' USING ERRCODE = 'insufficient_privilege';
END;
$$;
CREATE TRIGGER audit_events_no_update BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_append_only();
CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only();
