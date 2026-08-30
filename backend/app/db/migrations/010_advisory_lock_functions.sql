-- backend/app/db/migrations/010_advisory_lock_functions.sql

-- Atomic RPC function to start a sync run, using a transaction-level advisory lock to prevent race conditions.
CREATE OR REPLACE FUNCTION public.try_start_sync(p_sync_type text)
RETURNS text AS $$
DECLARE
  v_sync_id text;
  v_running_exists boolean;
BEGIN
  -- 1. Acquire transaction-level advisory lock to serialize start requests.
  -- This lock is automatically released when the transaction ends (RPC finishes).
  IF NOT pg_try_advisory_xact_lock(8877665544) THEN
    RETURN NULL; -- Lock unavailable, concurrent start in progress
  END IF;

  -- 2. Check if a running sync already exists for the type (active for less than 1 hour).
  -- This acts as a fallback/safety window to recover automatically if a server crashed.
  SELECT EXISTS (
    SELECT 1 FROM public.mf_sync_status 
    WHERE sync_type = p_sync_type 
      AND status = 'running' 
      AND started_at > (now() - interval '1 hour')
  ) INTO v_running_exists;

  IF v_running_exists THEN
    RETURN NULL; -- Sync is already active
  END IF;

  -- 3. Atomically insert and transition to 'running' status.
  v_sync_id := gen_random_uuid()::text;
  INSERT INTO public.mf_sync_status (id, sync_type, status, started_at)
  VALUES (v_sync_id, p_sync_type, 'running', now())
  RETURNING id INTO v_sync_id;

  RETURN v_sync_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
