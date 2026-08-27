-- backend/app/db/migrations/006_portfolio_universe.sql

-- ============================================================================
-- 1. REUSABLE TRIGGER FUNCTIONS
-- ============================================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = timezone('utc'::text, now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. CREATE SCHEMAS & TABLES
-- ============================================================================

-- A. Asset Historical Observations Cache Table
CREATE TABLE IF NOT EXISTS public.asset_historical_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  identifier TEXT NOT NULL REFERENCES public.asset_universe(identifier) ON DELETE CASCADE,
  observation_date DATE NOT NULL,
  price_or_nav NUMERIC NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  CONSTRAINT asset_obs_ident_date_unique UNIQUE (identifier, observation_date)
);

CREATE INDEX IF NOT EXISTS asset_obs_ident_date_idx ON public.asset_historical_observations(identifier, observation_date);

-- B. Asset Performance Metrics Table
CREATE TABLE IF NOT EXISTS public.asset_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  identifier TEXT NOT NULL UNIQUE REFERENCES public.asset_universe(identifier) ON DELETE CASCADE,
  metrics JSONB NOT NULL DEFAULT '{}', -- returns_1y, returns_3y, volatility, sharpe, sortino, etc.
  source TEXT NOT NULL,
  calculation_version TEXT NOT NULL,
  data_start_date DATE NOT NULL,
  data_end_date DATE NOT NULL,
  historical_observation_count INTEGER NOT NULL,
  peer_count INTEGER NOT NULL,
  data_confidence TEXT NOT NULL CHECK (data_confidence IN ('HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT')),
  peer_reliability TEXT NOT NULL CHECK (peer_reliability IN ('HIGH', 'LOW', 'INSUFFICIENT')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Trigger to update public.asset_metrics.updated_at automatically on edits
DROP TRIGGER IF EXISTS asset_metrics_set_updated_at ON public.asset_metrics;
CREATE TRIGGER asset_metrics_set_updated_at
  BEFORE UPDATE ON public.asset_metrics
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

-- C. User Portfolio Holdings Snapshot Table
CREATE TABLE IF NOT EXISTS public.user_portfolio_holdings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  asset_name TEXT NOT NULL,
  identifier TEXT NOT NULL,
  asset_class TEXT NOT NULL,
  subcategory TEXT NOT NULL,
  quantity NUMERIC NOT NULL DEFAULT 0,
  invested_amount NUMERIC NOT NULL DEFAULT 0,
  current_value NUMERIC NOT NULL DEFAULT 0,
  average_cost NUMERIC NOT NULL DEFAULT 0,
  purchase_date DATE,
  data_status TEXT NOT NULL DEFAULT 'unverified' CHECK (data_status IN ('verified', 'unverified', 'inactive', 'unavailable')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  CONSTRAINT user_holdings_user_ident_unique UNIQUE (user_id, identifier)
);

ALTER TABLE public.user_portfolio_holdings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own holdings" 
  ON public.user_portfolio_holdings 
  FOR ALL 
  TO authenticated 
  USING (auth.uid() = user_id) 
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS user_portfolio_holdings_user_idx ON public.user_portfolio_holdings(user_id);

-- Trigger to update public.user_portfolio_holdings.updated_at automatically on edits
DROP TRIGGER IF EXISTS user_portfolio_holdings_set_updated_at ON public.user_portfolio_holdings;
CREATE TRIGGER user_portfolio_holdings_set_updated_at
  BEFORE UPDATE ON public.user_portfolio_holdings
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

-- D. User Portfolio Goal Allocations Table
CREATE TABLE IF NOT EXISTS public.portfolio_goal_allocations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  holding_id UUID NOT NULL REFERENCES public.user_portfolio_holdings(id) ON DELETE CASCADE,
  goal_id UUID NOT NULL REFERENCES public.goals(id) ON DELETE CASCADE,
  allocation_percentage NUMERIC NOT NULL CHECK (allocation_percentage > 0 AND allocation_percentage <= 100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  CONSTRAINT holding_goal_unique UNIQUE (holding_id, goal_id)
);

ALTER TABLE public.portfolio_goal_allocations ENABLE ROW LEVEL SECURITY;

-- Secure RLS: requires that BOTH the associated holding AND the goal belong to the authenticated user
CREATE POLICY "Users can manage own goal allocations" 
  ON public.portfolio_goal_allocations 
  FOR ALL 
  TO authenticated 
  USING (
    EXISTS (
      SELECT 1 FROM public.user_portfolio_holdings h 
      WHERE h.id = holding_id AND h.user_id = auth.uid()
    ) AND EXISTS (
      SELECT 1 FROM public.goals g 
      WHERE g.id = goal_id AND g.user_id = auth.uid()
    )
  ) 
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.user_portfolio_holdings h 
      WHERE h.id = holding_id AND h.user_id = auth.uid()
    ) AND EXISTS (
      SELECT 1 FROM public.goals g 
      WHERE g.id = goal_id AND g.user_id = auth.uid()
    )
  );

-- E. User Portfolio Transactions Table (Tax-ready structures)
CREATE TABLE IF NOT EXISTS public.portfolio_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  identifier TEXT NOT NULL,
  transaction_type TEXT NOT NULL CHECK (transaction_type IN ('buy', 'sell', 'sip', 'redeem')),
  quantity NUMERIC NOT NULL CHECK (quantity > 0),
  price NUMERIC NOT NULL CHECK (price >= 0),
  amount NUMERIC NOT NULL CHECK (amount >= 0),
  cost_basis NUMERIC,
  transaction_date DATE NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.portfolio_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own transactions" 
  ON public.portfolio_transactions 
  FOR ALL 
  TO authenticated 
  USING (auth.uid() = user_id) 
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS portfolio_transactions_user_date_idx ON public.portfolio_transactions(user_id, transaction_date);
