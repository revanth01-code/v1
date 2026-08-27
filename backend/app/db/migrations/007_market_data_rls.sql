-- backend/app/db/migrations/007_market_data_rls.sql

-- ============================================================================
-- 1. ENABLE ROW LEVEL SECURITY FOR MARKET CACHE TABLES
-- ============================================================================
ALTER TABLE public.asset_historical_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_metrics ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 2. CREATE READ-ONLY RLS POLICIES FOR AUTHENTICATED USERS
-- ============================================================================
DROP POLICY IF EXISTS "Allow authenticated read access to observations" ON public.asset_historical_observations;
CREATE POLICY "Allow authenticated read access to observations" 
  ON public.asset_historical_observations 
  FOR SELECT 
  TO authenticated 
  USING (true);

DROP POLICY IF EXISTS "Allow authenticated read access to metrics" ON public.asset_metrics;
CREATE POLICY "Allow authenticated read access to metrics" 
  ON public.asset_metrics 
  FOR SELECT 
  TO authenticated 
  USING (true);
