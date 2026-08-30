-- backend/app/db/migrations/009_mf_sync_status.sql

-- ============================================================================
-- 1. CREATE MF SYNC STATUS LOGGING TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.mf_sync_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    sync_type TEXT NOT NULL
        CHECK (sync_type IN ('latest_nav', 'historical_backfill')),

    status TEXT NOT NULL
        CHECK (status IN ('running', 'success', 'failed')),

    started_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    completed_at TIMESTAMPTZ,

    records_processed INTEGER NOT NULL DEFAULT 0
        CHECK (records_processed >= 0),

    records_failed INTEGER NOT NULL DEFAULT 0
        CHECK (records_failed >= 0),

    error_message TEXT,

    duration_seconds NUMERIC
        CHECK (duration_seconds >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- ============================================================================
-- 2. ENABLE ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE public.mf_sync_status ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS
    "Allow authenticated read access to sync status"
ON public.mf_sync_status;

CREATE POLICY "Allow authenticated read access to sync status"
    ON public.mf_sync_status
    FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- 3. INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS mf_sync_status_type_status_idx
    ON public.mf_sync_status(sync_type, status);

CREATE INDEX IF NOT EXISTS mf_sync_status_type_completed_idx
    ON public.mf_sync_status(sync_type, completed_at DESC);

CREATE INDEX IF NOT EXISTS mf_sync_status_started_at_idx
    ON public.mf_sync_status(started_at DESC);