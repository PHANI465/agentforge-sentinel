-- Every ingestion decision is recorded, alerting or not, so replays return the original outcome
-- (review R5). Rows ingested before this migration have no outcome and replay a null score.

CREATE TABLE scoring_outcomes (
    transaction_id uuid PRIMARY KEY REFERENCES transactions (id),
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    score double precision NOT NULL CHECK (score >= 0 AND score <= 1),
    alerted boolean NOT NULL,
    body jsonb NOT NULL
);
