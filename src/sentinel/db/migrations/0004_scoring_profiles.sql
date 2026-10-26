-- Decision-time inputs for the trained scorer (C07). Provisioned by the operator (CLI), never
-- through an HTTP route; the runtime role may only read them.

-- Account attributes f1 needs (home currency, opening time). Scoped like every other table.
CREATE TABLE account_profiles (
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    account_id uuid NOT NULL,
    home_currency text NOT NULL CHECK (home_currency IN ('USD', 'INR', 'GBP', 'JPY')),
    opened_at timestamptz NOT NULL,
    provisioned_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, session_id, account_id)
);

-- Disclosed fraud outcomes for an account's transactions, with the time they became known.
-- f1's prior_known_fraud counts only disclosures with disclosed_at <= the decision time.
CREATE TABLE fraud_disclosures (
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    external_id text NOT NULL,
    account_id uuid NOT NULL,
    is_fraud boolean NOT NULL,
    disclosed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, session_id, external_id)
);
CREATE INDEX fraud_disclosures_account
    ON fraud_disclosures (tenant_id, session_id, account_id, disclosed_at);
