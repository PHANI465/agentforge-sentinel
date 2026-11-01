-- Three-role investigation workflow (G3B, ADR 0007). Scoped like every other table; the
-- runtime role may insert/update workflows and only append steps.

-- One coordinator attempt on a case. body holds the validated agents-1.0 WorkflowRecord.
CREATE TABLE agent_workflows (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    case_id uuid NOT NULL REFERENCES cases (id),
    case_revision integer NOT NULL CHECK (case_revision >= 1),
    status text NOT NULL CHECK (status IN ('running', 'completed', 'inconclusive')),
    started_at timestamptz NOT NULL,
    deadline_at timestamptz NOT NULL CHECK (deadline_at > started_at),
    finished_at timestamptz,
    terminal_by text CHECK (terminal_by IN ('coordinator', 'recovery')),
    body jsonb NOT NULL,
    -- running <=> no finish time and no terminal actor (the WorkflowRecord lifecycle rule).
    CHECK ((status = 'running') = (finished_at IS NULL AND terminal_by IS NULL)),
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);
-- At most one running workflow per case.
CREATE UNIQUE INDEX agent_workflows_one_running ON agent_workflows (case_id)
    WHERE status = 'running';

-- Append-only coordinator events. body is the StepRecord; payload the validated role output
-- or tool result (never raw provider output, prompts or credentials).
CREATE TABLE agent_steps (
    seq bigserial PRIMARY KEY,
    id uuid NOT NULL UNIQUE,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    workflow_id uuid NOT NULL REFERENCES agent_workflows (id),
    case_id uuid NOT NULL REFERENCES cases (id),
    step_seq integer NOT NULL CHECK (step_seq BETWEEN 1 AND 64),
    body jsonb NOT NULL,
    payload jsonb,
    UNIQUE (workflow_id, step_seq)
);

CREATE FUNCTION agent_steps_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'agent_steps is append-only' USING ERRCODE = 'insufficient_privilege';
END;
$$;
CREATE TRIGGER agent_steps_no_update BEFORE UPDATE OR DELETE ON agent_steps
    FOR EACH ROW EXECUTE FUNCTION agent_steps_append_only();
CREATE TRIGGER agent_steps_no_truncate BEFORE TRUNCATE ON agent_steps
    FOR EACH STATEMENT EXECUTE FUNCTION agent_steps_append_only();

-- Role runs of a workflow keep the frozen v1 AgentRun body; the link lives in columns.
ALTER TABLE agent_runs ADD COLUMN workflow_id uuid REFERENCES agent_workflows (id);
ALTER TABLE agent_runs ADD COLUMN attempt smallint CHECK (attempt BETWEEN 1 AND 2);
-- Insertion order breaks started_at ties (sequential roles can share a clock reading), so
-- CaseDetail lists every historical run in a deterministic order.
ALTER TABLE agent_runs ADD COLUMN seq bigserial;
