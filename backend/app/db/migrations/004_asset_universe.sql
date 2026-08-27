-- backend/app/db/migrations/004_asset_universe.sql

CREATE TABLE IF NOT EXISTS asset_universe (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_name TEXT NOT NULL,
  asset_class TEXT NOT NULL,         -- equity, debt, diversifier
  subcategory TEXT NOT NULL,         -- large_cap, flexi_cap, mid_cap, small_cap, index_fund, elss, etf, liquid, overnight, ultra_short, money_market, short_duration, gold_etf, gold_fund, reit, invit
  instrument_type TEXT NOT NULL,     -- mutual_fund, etf, index, reit_trust, invit_trust
  identifier TEXT NOT NULL UNIQUE,    -- scheme_code or ticker (e.g. 122639 or GOLDBEES)
  data_source TEXT NOT NULL,         -- amfi, custom, nse, etc.
  liquidity TEXT NOT NULL,           -- high, medium, low
  tax_classification TEXT NOT NULL,   -- equity_tax, debt_tax, gold_tax
  latest_price NUMERIC NOT NULL DEFAULT 0,
  last_updated TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS asset_universe_class_idx ON asset_universe(asset_class);
CREATE INDEX IF NOT EXISTS asset_universe_subcategory_idx ON asset_universe(subcategory);

-- Pre-populate the Investment Universe with diverse reference assets
INSERT INTO asset_universe 
  (asset_name, asset_class, subcategory, instrument_type, identifier, data_source, liquidity, tax_classification, latest_price)
VALUES
  -- EQUITY MUTUAL FUNDS
  ('SBI Bluechip Fund (Direct Growth)', 'equity', 'large_cap', 'mutual_fund', '119777', 'amfi', 'high', 'equity_tax', 84.50),
  ('Parag Parikh Flexi Cap Fund (Direct Growth)', 'equity', 'flexi_cap', 'mutual_fund', '122639', 'amfi', 'high', 'equity_tax', 72.10),
  ('HDFC Mid-Cap Opportunities Fund (Direct Growth)', 'equity', 'mid_cap', 'mutual_fund', '119063', 'amfi', 'high', 'equity_tax', 156.40),
  ('Nippon India Small Cap Fund (Direct Growth)', 'equity', 'small_cap', 'mutual_fund', '120586', 'amfi', 'high', 'equity_tax', 142.80),
  ('UTI Nifty 50 Index Fund (Direct Growth)', 'equity', 'index_fund', 'mutual_fund', '120716', 'amfi', 'high', 'equity_tax', 180.20),
  ('Mirae Asset Tax Saver Fund (Direct Growth)', 'equity', 'elss', 'mutual_fund', '135798', 'amfi', 'medium', 'equity_tax', 45.90),
  
  -- EQUITY ETFS
  ('Nippon India ETF Nifty 50 BeES', 'equity', 'etf', 'etf', 'NIFTYBEES', 'custom', 'high', 'equity_tax', 265.10),
  
  -- DEBT / CASH FUNDS
  ('Aditya Birla Sun Life Liquid Fund (Direct Growth)', 'debt', 'liquid', 'mutual_fund', '119532', 'amfi', 'high', 'debt_tax', 380.50),
  ('SBI Overnight Fund (Direct Growth)', 'debt', 'overnight', 'mutual_fund', '143265', 'amfi', 'high', 'debt_tax', 1150.20),
  ('ICICI Prudential Ultra Short Term Fund (Direct Growth)', 'debt', 'ultra_short', 'mutual_fund', '120286', 'amfi', 'high', 'debt_tax', 25.10),
  ('HDFC Money Market Fund (Direct Growth)', 'debt', 'money_market', 'mutual_fund', '119159', 'amfi', 'high', 'debt_tax', 4950.40),
  ('Axis Short Term Fund (Direct Growth)', 'debt', 'short_duration', 'mutual_fund', '118825', 'amfi', 'high', 'debt_tax', 30.20),
  
  -- DIVERSIFIERS
  ('Nippon India ETF Gold BeES', 'diversifier', 'gold_etf', 'etf', 'GOLDBEES', 'custom', 'high', 'gold_tax', 62.80),
  ('SBI Gold Fund (Direct Growth)', 'diversifier', 'gold_fund', 'mutual_fund', '114841', 'amfi', 'high', 'gold_tax', 21.40),
  ('Embassy Office Parks REIT', 'diversifier', 'reit', 'reit_trust', 'EMBASSY', 'custom', 'medium', 'equity_tax', 345.00),
  ('PowerGrid Infrastructure Investment Trust', 'diversifier', 'invit', 'invit_trust', 'PGINVIT', 'custom', 'medium', 'equity_tax', 118.50)
ON CONFLICT (identifier) DO UPDATE SET 
  asset_name = EXCLUDED.asset_name,
  asset_class = EXCLUDED.asset_class,
  subcategory = EXCLUDED.subcategory,
  instrument_type = EXCLUDED.instrument_type,
  data_source = EXCLUDED.data_source,
  liquidity = EXCLUDED.liquidity,
  tax_classification = EXCLUDED.tax_classification;
