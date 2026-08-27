-- backend/app/db/migrations/008_goal_priority_rank.sql

-- Add user-defined numeric priority rank to goals.
-- Nullable: existing goals retain NULL until the user explicitly ranks them.
ALTER TABLE public.goals
  ADD COLUMN IF NOT EXISTS priority_rank INTEGER;

CREATE INDEX IF NOT EXISTS goals_priority_rank_idx ON public.goals(user_id, priority_rank);
