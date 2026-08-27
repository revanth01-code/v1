/* frontend/src/types/api.ts */

export interface SignUpInput {
  email: string;
  password: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface UserOut {
  id: string;
  email: string | null;
}

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  expires_at: number | null;
  user: UserOut;
}

export interface ProfileCreate {
  monthly_income: number;
  monthly_expenses: number;
  existing_savings: number;
  existing_investments: number;
  dependents: number;
  employment_type?: string | null;
  essential_expenses?: number;
  emi_obligations?: number;
  mandatory_commitments?: number;
  emergency_fund_contribution?: number;
}

export interface ProfileUpdate {
  monthly_income?: number;
  monthly_expenses?: number;
  existing_savings?: number;
  existing_investments?: number;
  dependents?: number;
  employment_type?: string | null;
  essential_expenses?: number;
  emi_obligations?: number;
  mandatory_commitments?: number;
  emergency_fund_contribution?: number;
}

export interface ProfileOut {
  id: string;
  user_id: string;
  monthly_income: number;
  monthly_expenses: number;
  existing_savings: number;
  existing_investments: number;
  dependents: number;
  employment_type: string | null;
  essential_expenses: number;
  emi_obligations: number;
  mandatory_commitments: number;
  emergency_fund_contribution: number;
  available_capacity: number;
  monthly_surplus: number;
  created_at: string;
  updated_at: string;
}

export type ContributionMode = 'sip' | 'lumpsum' | 'both';
export type RiskLevel = 'low' | 'mid' | 'high';
export type TermType = 'short_term' | 'long_term';
export type FeasibilityStatus = 'highly_feasible' | 'feasible' | 'borderline' | 'at_risk' | 'unlikely';

export interface GoalCreate {
  name: string;
  target_amount: number;
  target_date: string; // YYYY-MM-DD
  contribution_mode: ContributionMode;
  monthly_contribution: number;
  lumpsum_amount: number;
  risk_level: RiskLevel;
  goal_type: string;
  priority: string;
  deadline_flexibility: string;
  importance: string;
  inflation_scenario: string;
  inflation_rate_override?: number | null;
}

export interface GuardrailResult {
  allowed: boolean;
  warning: string | null;
}

export interface FeasibilityResult {
  status: FeasibilityStatus;
  months: number;
  inflation_adjusted_target: number;
  projected_value: number;
  shortfall: number | null;
  suggested_monthly_sip: number | null;
  contribution_difference: number;
  suggested_extended_months: number | null;
  message: string | null;
}

export interface GoalStrategy {
  risk_level: string;
  equity_pct: number;
  debt_pct: number;
  expected_return_range: string;
  expected_return_pct: number;
  volatility: string;
  liquidity: string;
  success_probability: number;
}

export interface GoalCheckResponse {
  term_type: TermType;
  guardrail: GuardrailResult;
  feasibility: FeasibilityResult;
  strategies: Record<string, GoalStrategy> | null;
}

export interface FundOut {
  scheme_code: string;
  scheme_name: string;
  category: string;
  latest_nav: number;
  nav_date: string | null;
}

export interface GoalOut {
  id: string;
  user_id: string;
  name: string;
  target_amount: number;
  target_date: string;
  term_type: string;
  contribution_mode: string;
  monthly_contribution: number;
  lumpsum_amount: number;
  risk_level: string;
  fund_category_mix: Record<string, number>;
  expected_return_pct: number;
  inflation_adjusted_target: number;
  feasibility_status: string;
  feasibility_details: FeasibilityResult | null;
  status: string;
  created_at: string;
  updated_at: string;
  recommended_funds: Record<string, FundOut[]>;
  goal_type: string;
  priority: string;
  deadline_flexibility: string;
  importance: string;
  inflation_scenario: string;
  inflation_rate_pct: number;
  inflation_rate_override: number | null;
  strategies: Record<string, GoalStrategy> | null;
  priority_rank: number | null;
}

export interface EmergencyFundCreate {
  months_of_coverage: number;
  current_amount: number;
  monthly_contribution: number;
}

export interface EmergencyFundUpdate {
  months_of_coverage?: number;
  current_amount?: number;
  monthly_contribution?: number;
}

export interface EmergencyFundOut {
  id: string;
  user_id: string;
  months_of_coverage: number;
  current_amount: number;
  monthly_contribution: number;
  monthly_expenses: number;
  target_amount: number;
  time_to_target_months: number | null;
  status: 'building' | 'complete';
  created_at: string;
  updated_at: string;
}

export interface RetirementCreate {
  current_age: number;
  retirement_age: number;
  life_expectancy: number;
  existing_retirement_corpus: number;
  planned_monthly_contribution: number;
  inflation_pct: number;
  pre_retirement_return_pct: number;
  post_retirement_return_pct: number;
}

export interface RetirementUpdate {
  current_age?: number;
  retirement_age?: number;
  life_expectancy?: number;
  existing_retirement_corpus?: number;
  planned_monthly_contribution?: number;
  inflation_pct?: number;
  pre_retirement_return_pct?: number;
  post_retirement_return_pct?: number;
}

export interface RetirementOut {
  id: string;
  user_id: string;
  current_age: number;
  retirement_age: number;
  life_expectancy: number;
  existing_retirement_corpus: number;
  planned_monthly_contribution: number;
  inflation_pct: number;
  pre_retirement_return_pct: number;
  post_retirement_return_pct: number;
  current_monthly_expense: number;
  years_to_retirement: number;
  years_in_retirement: number;
  required_corpus: number;
  feasibility_status: string;
  feasibility_details: FeasibilityResult;
  created_at: string;
  updated_at: string;
}

export interface HistoricalNavPoint {
  date: string;
  nav: number;
}

export interface FundDetailOut extends FundOut {
  historical_nav: HistoricalNavPoint[];
  historical_nav_available: boolean;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
}

export interface ChatResponse {
  reply: string;
}

export interface GoalSummary {
  id: string;
  name: string;
  target_amount: number;
  target_date: string;
  feasibility_status: string;
}

export interface GoalsOverview {
  total: number;
  feasible: number;
  borderline: number;
  items: GoalSummary[];
}

export interface RetirementOverview {
  required_corpus: number;
  feasibility_status: string;
  years_to_retirement: number;
}

export interface EmergencyFundOverview {
  target_amount: number;
  current_amount: number;
  status: string;
}

export interface DashboardOut {
  profile_complete: boolean;
  goals: GoalsOverview;
  retirement: RetirementOverview | null;
  emergency_fund: EmergencyFundOverview | null;
  available_capacity: number;
  total_required_sip: number;
  alerts: string[];
}

export interface SimulationInput {
  lumpsum_amount: number;
  monthly_contribution: number;
  target_amount: number;
  target_date: string;
  risk_level: 'low' | 'mid' | 'high' | 'custom';
  equity_pct?: number;
  debt_pct?: number;
  inflation_pct: number;
  stress_scenario: 'none' | 'market_downturn' | 'high_inflation' | 'low_return' | 'sip_pause' | 'reduced_income' | 'increased_cost';
  sip_pause_start: number;
  sip_pause_duration: number;
  sip_reduce_pct: number;
  sip_reduce_start: number;
  sip_reduce_duration: number;
}

export interface SimulationResult {
  median_corpus: number;
  mean_corpus: number;
  downside_percentile_10: number;
  upside_percentile_90: number;
  prob_success: number;
  prob_shortfall: number;
  median_shortfall: number;
  expected_shortfall: number;
  purchasing_power_median: number;
  adjusted_target: number;
  message: string;
}

export interface WhatIfComparisonResponse {
  current_plan: SimulationResult;
  what_if_plan: SimulationResult;
}

export interface AssetOut {
  id: string;
  asset_name: string;
  asset_class: string;
  subcategory: string;
  instrument_type: string;
  identifier: string;
  data_source: string;
  liquidity: string;
  tax_classification: string;
  tax_rule_key?: string | null;
  tax_metadata?: Record<string, any>;
  latest_price: number | null;
  data_status: 'fresh' | 'recent' | 'aging' | 'stale' | 'unavailable';
  last_fetched: string | null;
  last_updated: string;
}
