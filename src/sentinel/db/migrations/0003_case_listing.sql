-- Session-scoped case listing (C01): keyset pagination on (created_at DESC, id DESC).
ALTER TABLE cases ADD COLUMN created_at timestamptz;
UPDATE cases SET created_at = (body ->> 'created_at')::timestamptz;
ALTER TABLE cases ALTER COLUMN created_at SET NOT NULL;
CREATE INDEX cases_session_listing ON cases (tenant_id, session_id, created_at DESC, id DESC);
CREATE INDEX cases_session_state ON cases (tenant_id, session_id, state, created_at DESC, id DESC);
