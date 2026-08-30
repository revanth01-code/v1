-- Add recommendation_score column to public.asset_metrics
ALTER TABLE public.asset_metrics 
  ADD COLUMN IF NOT EXISTS recommendation_score NUMERIC CHECK (
    recommendation_score IS NULL OR (recommendation_score >= 0 AND recommendation_score <= 100)
  );

-- Create an index optimized for ranking queries (descending order, nulls last)
CREATE INDEX IF NOT EXISTS asset_metrics_recommendation_score_idx 
  ON public.asset_metrics (recommendation_score DESC NULLS LAST);
