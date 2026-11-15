-- Installed by the schema owner in a dedicated synthetic demo database.
CREATE SCHEMA IF NOT EXISTS sentinel_demo;
REVOKE ALL ON SCHEMA sentinel_demo FROM PUBLIC;
CREATE OR REPLACE FUNCTION sentinel_demo.issue_session(
    token_hash text, guest_tenant uuid, guest_session uuid, guest_actor uuid
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    now_at timestamptz := pg_catalog.clock_timestamp();
BEGIN
    -- Serialize admission in the database, including concurrent Vercel instances.
    PERFORM pg_catalog.pg_advisory_xact_lock(4224091);
    IF (SELECT count(*) FROM public.api_sessions) >= 1000 OR
       (SELECT count(*) FROM public.api_sessions WHERE created_at > now_at - interval '24 hours') >= 100 THEN
        RETURN false;
    END IF;
    INSERT INTO public.api_sessions (
        token_sha256, tenant_id, session_id, actor_id, actor_kind, capabilities, created_at, expires_at
    ) VALUES (
        token_hash, guest_tenant, guest_session, guest_actor, 'human',
        ARRAY['read_case', 'approve_action', 'execute_simulated_action'], now_at, now_at + interval '30 minutes'
    );
    RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION sentinel_demo.issue_session(text, uuid, uuid, uuid) FROM PUBLIC;
GRANT USAGE ON SCHEMA sentinel_demo TO sentinel_hosted;
GRANT EXECUTE ON FUNCTION sentinel_demo.issue_session(text, uuid, uuid, uuid) TO sentinel_hosted;
