-- Install as the database owner. The runtime can call the reservation function only.
CREATE TABLE IF NOT EXISTS sentinel_demo.iaf_usage (
    utc_day date PRIMARY KEY,
    calls integer NOT NULL CHECK (calls BETWEEN 1 AND 30)
);
REVOKE ALL ON sentinel_demo.iaf_usage FROM PUBLIC, sentinel_hosted;
CREATE OR REPLACE FUNCTION sentinel_demo.reserve_iaf_call()
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    today date := (pg_catalog.clock_timestamp() AT TIME ZONE 'UTC')::date;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(4224092);
    IF COALESCE((SELECT calls FROM sentinel_demo.iaf_usage WHERE utc_day = today), 0) >= 30
      OR COALESCE((SELECT sum(calls) FROM sentinel_demo.iaf_usage
                   WHERE utc_day >= date_trunc('month', today)::date AND utc_day <= today), 0) >= 300 THEN
        RETURN false;
    END IF;
    INSERT INTO sentinel_demo.iaf_usage(utc_day, calls) VALUES (today, 1)
        ON CONFLICT (utc_day) DO UPDATE SET calls = iaf_usage.calls + 1;
    RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION sentinel_demo.reserve_iaf_call() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sentinel_demo.reserve_iaf_call() TO sentinel_hosted;
