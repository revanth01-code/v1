-- backend/app/db/migrations/005_unified_schema_update.sql

-- ============================================================================
-- 1. EXTEND FINANCIAL PROFILE SCHEMA (Capacity Engine metrics)
-- ============================================================================
ALTER TABLE public.financial_profile 
  ADD COLUMN IF NOT EXISTS essential_expenses NUMERIC NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS emi_obligations NUMERIC NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS mandatory_commitments NUMERIC NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS emergency_fund_contribution NUMERIC NOT NULL DEFAULT 0;

-- ============================================================================
-- 2. EXTEND GOALS SCHEMA (Intelligence & Inflation parameters)
-- ============================================================================
ALTER TABLE public.goals 
  ADD COLUMN IF NOT EXISTS goal_type TEXT NOT NULL DEFAULT 'custom',
  ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium',
  ADD COLUMN IF NOT EXISTS deadline_flexibility TEXT NOT NULL DEFAULT 'flexible',
  ADD COLUMN IF NOT EXISTS importance TEXT NOT NULL DEFAULT 'important',
  ADD COLUMN IF NOT EXISTS inflation_scenario TEXT NOT NULL DEFAULT 'expected',
  ADD COLUMN IF NOT EXISTS inflation_rate_pct NUMERIC NOT NULL DEFAULT 6,
  ADD COLUMN IF NOT EXISTS inflation_rate_override NUMERIC,
  ADD COLUMN IF NOT EXISTS strategies JSONB;

-- ============================================================================
-- 3. CREATE NORMALIZED ASSET UNIVERSE TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.asset_universe (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_name TEXT NOT NULL,
  asset_class TEXT NOT NULL,          -- equity, debt, diversifier
  subcategory TEXT NOT NULL,          -- large_cap, flexi_cap, gold_etf, reit, liquid, etc.
  instrument_type TEXT NOT NULL,      -- mutual_fund, etf, index, reit_trust, invit_trust
  identifier TEXT NOT NULL UNIQUE,     -- scheme_code or ticker symbol (e.g. '122639' or 'GOLDBEES')
  data_source TEXT NOT NULL,          -- amfi, custom, nse, etc.
  liquidity TEXT NOT NULL,            -- high, medium, low
  
  -- Tax intelligence properties (extensible tax rules)
  tax_classification TEXT NOT NULL,    -- descriptive type (e.g. 'equity', 'debt', 'gold')
  tax_rule_key TEXT,                   -- optional rule engine key (to be populated later in Part 4)
  tax_metadata JSONB DEFAULT '{}',     -- extensible rule options, lock-in periods, effective dates

  -- Pricing & Data Quality (nullable values to avoid defaulting missing quotes to 0)
  latest_price NUMERIC,                
  data_status VARCHAR(20) DEFAULT 'unavailable' CHECK (data_status IN ('fresh', 'recent', 'aging', 'stale', 'unavailable')),
  last_fetched TIMESTAMP WITH TIME ZONE,
  last_updated TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Table-specific trigger function to update public.asset_universe.last_updated
CREATE OR REPLACE FUNCTION public.set_asset_universe_last_updated()
RETURNS TRIGGER as $$
BEGIN
  NEW.last_updated = timezone('utc'::text, now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS asset_universe_set_last_updated ON public.asset_universe;
CREATE TRIGGER asset_universe_set_last_updated
  BEFORE UPDATE ON public.asset_universe
  FOR EACH ROW
  EXECUTE FUNCTION public.set_asset_universe_last_updated();

-- ============================================================================
-- 4. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
ALTER TABLE public.asset_universe ENABLE ROW LEVEL SECURITY;

-- Safely drop old policies if they exist before creating the new authenticated-only policy
DROP POLICY IF EXISTS "Allow public read access to asset universe" ON public.asset_universe;
DROP POLICY IF EXISTS "Allow authenticated read access to asset universe" ON public.asset_universe;

-- Create policy allowing SELECT queries ONLY to authenticated users
CREATE POLICY "Allow authenticated read access to asset universe" 
  ON public.asset_universe 
  FOR SELECT 
  TO authenticated 
  USING (true);

-- ============================================================================
-- 5. PERFORMANCE INDEXES
-- ============================================================================
-- Note: financial_profile(user_id) is NOT indexed here because it is defined
-- as UNIQUE, which automatically indexes it in Postgres.
CREATE INDEX IF NOT EXISTS goals_user_id_idx ON public.goals(user_id);
CREATE INDEX IF NOT EXISTS goals_goal_type_idx ON public.goals(goal_type);
CREATE INDEX IF NOT EXISTS asset_universe_class_idx ON public.asset_universe(asset_class);
CREATE INDEX IF NOT EXISTS asset_universe_subcategory_idx ON public.asset_universe(subcategory);
