-- backend/app/db/migrations/009_goal_sip_day.sql

-- Add optional recurring SIP payment day (1-28) to goals table.
ALTER TABLE public.goals
  ADD COLUMN IF NOT EXISTS sip_day INTEGER CHECK (sip_day IS NULL OR (sip_day >= 1 AND sip_day <= 28));
