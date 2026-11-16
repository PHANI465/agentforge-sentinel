-- Additive and repeatable. Apply as the demo database owner before releasing app.py.
BEGIN;
CREATE TABLE IF NOT EXISTS sentinel_demo.request_limits (
    bucket text NOT NULL,
    subject text NOT NULL,
    expires_at timestamptz NOT NULL,
    hits integer NOT NULL CHECK (hits > 0),
    PRIMARY KEY (bucket, subject, expires_at)
);
CREATE INDEX IF NOT EXISTS request_limits_expiry ON sentinel_demo.request_limits (expires_at);
REVOKE ALL ON sentinel_demo.request_limits FROM PUBLIC, sentinel_hosted;

CREATE OR REPLACE FUNCTION sentinel_demo.reserve_request(
    route_group text, visitor text, bearer_digest text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    checked_at timestamptz;
    bucket_end timestamptz;
    visitor_limit integer;
    total_limit integer;
    session_subject text;
BEGIN
    IF visitor IS NULL OR visitor !~ '^[a-f0-9]{64}$' THEN
        RETURN false;
    END IF;
    -- Serialize only this short admission transaction, including cleanup and both counters.
    PERFORM pg_catalog.pg_advisory_xact_lock(4224093);
    checked_at := pg_catalog.clock_timestamp();
    CASE route_group
        WHEN 'guest' THEN
            bucket_end := date_bin('1 hour', checked_at, '2000-01-01 UTC'::timestamptz) + interval '1 hour';
            visitor_limit := 3;
            total_limit := 150;
        WHEN 'iaf' THEN
            bucket_end := date_bin('1 hour', checked_at, '2000-01-01 UTC'::timestamptz) + interval '1 hour';
            visitor_limit := 8;
            total_limit := 300;
        WHEN 'api' THEN
            bucket_end := date_bin('1 minute', checked_at, '2000-01-01 UTC'::timestamptz) + interval '1 minute';
            visitor_limit := 120;
            total_limit := 3000;
        ELSE RETURN false;
    END CASE;

    -- Invalid tokens never create their own buckets.
    IF route_group = 'api' AND bearer_digest IS NOT NULL THEN
        SELECT session_id::text INTO session_subject
        FROM public.api_sessions
        WHERE token_sha256 = bearer_digest AND expires_at > checked_at;
    END IF;
    DELETE FROM sentinel_demo.request_limits WHERE expires_at <= checked_at;
    IF EXISTS (
        SELECT 1 FROM sentinel_demo.request_limits
        WHERE bucket = route_group AND expires_at = bucket_end AND (
            (subject = 'all' AND hits >= total_limit)
            OR (subject = visitor AND hits >= visitor_limit)
            OR (subject = session_subject AND hits >= 90)
        )
    ) THEN
        RETURN false;
    END IF;
    INSERT INTO sentinel_demo.request_limits AS counts (bucket, subject, expires_at, hits)
    SELECT route_group, key, bucket_end, 1 FROM unnest(ARRAY['all', visitor, session_subject]) AS key
    WHERE key IS NOT NULL
    ON CONFLICT (bucket, subject, expires_at) DO UPDATE SET hits = counts.hits + 1;
    RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION sentinel_demo.reserve_request(text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sentinel_demo.reserve_request(text, text, text) TO sentinel_hosted;
COMMIT;
