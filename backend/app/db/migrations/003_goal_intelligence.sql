-- backend/app/db/migrations/003_goal_intelligence.sql

-- Part 1: Add new financial metrics to financial_profile
ALTER TABLE financial_profile 
  ADD COLUMN IF NOT EXISTS essential_expenses NUMERIC NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS emi_obligations NUMERIC NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS mandatory_commitments NUMERIC NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS emergency_fund_contribution NUMERIC NOT NULL DEFAULT 0;

-- Part 2: Add Goal Intelligence & Risk Engine fields to goals
ALTER TABLE goals 
  ADD COLUMN IF NOT EXISTS goal_type TEXT NOT NULL DEFAULT 'custom',
  ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium',
  ADD COLUMN IF NOT EXISTS deadline_flexibility TEXT NOT NULL DEFAULT 'flexible',
  ADD COLUMN IF NOT EXISTS importance TEXT NOT NULL DEFAULT 'important',
  ADD COLUMN IF NOT EXISTS inflation_scenario TEXT NOT NULL DEFAULT 'expected',
  ADD COLUMN IF NOT EXISTS inflation_rate_pct NUMERIC NOT NULL DEFAULT 6,
  ADD COLUMN IF NOT EXISTS inflation_rate_override NUMERIC;

-- Part 3: Add database indexes to speed up multi-goal capacity joins & queries
CREATE INDEX IF NOT EXISTS goals_user_id_idx ON goals(user_id);
CREATE INDEX IF NOT EXISTS goals_goal_type_idx ON goals(goal_type);
CREATE INDEX IF NOT EXISTS financial_profile_user_id_idx ON financial_profile(user_id);
