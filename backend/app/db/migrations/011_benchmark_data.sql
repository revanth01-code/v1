CREATE TABLE IF NOT EXISTS public.benchmark_historical_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  index_name TEXT NOT NULL,
  observation_date DATE NOT NULL,
  close_value NUMERIC NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  CONSTRAINT benchmark_obs_name_date_unique UNIQUE (index_name, observation_date)
);

CREATE INDEX IF NOT EXISTS benchmark_obs_name_date_idx
  ON public.benchmark_historical_observations(index_name, observation_date);

-- Which subcategory maps to which benchmark index — kept as data, not
-- hardcoded in Python, so it can be adjusted without a deploy.
CREATE TABLE IF NOT EXISTS public.benchmark_mapping (
  subcategory TEXT PRIMARY KEY,
  index_name TEXT NOT NULL
);

INSERT INTO public.benchmark_mapping (subcategory, index_name) VALUES
  ('large_cap', 'NIFTY 100'),
  ('flexi_cap', 'NIFTY 500'),
  ('mid_cap', 'NIFTY MIDCAP 150'),
  ('small_cap', 'NIFTY SMALLCAP 250'),
  ('index_fund', 'NIFTY 50'),
  ('elss', 'NIFTY 500'),
  ('etf', 'NIFTY 50')
ON CONFLICT (subcategory) DO UPDATE SET index_name = EXCLUDED.index_name;
-- Deliberately no entries for debt/gold/reit/invit subcategories —
-- those are treated as "no benchmark available" by design, not an oversight.