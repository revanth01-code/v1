/* frontend/src/pages/GoalDetails.tsx */
import React from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { goalsService } from '../services/goalsService';
import { Card } from '../components/common/Card';
import { StatusIndicator } from '../components/common/StatusIndicator';
import { Button } from '../components/common/Button';
import { formatINR } from '../utils/currency';
import { formatDate } from '../utils/date';
import { ArrowLeft, Calendar, TrendingUp, HelpCircle, Eye, AlertCircle } from 'lucide-react';
import { simulationService } from '../services/simulationService';
import { universeService } from '../services/universeService';

export const GoalDetails: React.FC = () => {
  const { goalId } = useParams<{ goalId: string }>();
  const navigate = useNavigate();

  const { data: goal, isLoading, error } = useQuery({
    queryKey: ['goal', goalId],
    queryFn: () => goalsService.getGoal(goalId || ''),
    enabled: !!goalId,
    retry: 1,
  });

  const { data: simResult } = useQuery({
    queryKey: ['goal-simulation', goalId],
    queryFn: () =>
      simulationService.runSimulation({
        lumpsum_amount: goal!.lumpsum_amount,
        monthly_contribution: goal!.monthly_contribution,
        target_amount: goal!.target_amount,
        target_date: goal!.target_date,
        risk_level: goal!.risk_level as any,
        inflation_pct: goal!.inflation_rate_pct || 6.0,
        stress_scenario: 'none',
        sip_pause_start: 0,
        sip_pause_duration: 0,
        sip_reduce_pct: 0,
        sip_reduce_start: 0,
        sip_reduce_duration: 0,
      }),
    enabled: !!goal,
  });

  const { data: recs } = useQuery({
    queryKey: ['universe-recommendations', goal?.risk_level],
    queryFn: () => universeService.getRecommendations(goal?.risk_level || 'mid'),
    enabled: !!goal,
  });

  if (isLoading) {
    return (
      <div className="skeleton-loading-container">
        <div className="skeleton skeleton-banner" />
        <div className="skeleton-grid-2">
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
        </div>
      </div>
    );
  }

  if (error || !goal) {
    return (
      <div className="error-state-box card p-4">
        <AlertCircle size={40} className="text-danger mb-2" />
        <h3>Failed to load goal details</h3>
        <p className="text-secondary">{error?.message || 'Goal not found'}</p>
        <Button onClick={() => navigate('/goals')} variant="secondary" className="mt-3">
          Back to List
        </Button>
      </div>
    );
  }

  // Convert categories names to display-friendly versions
  const formatCategoryName = (cat: string) => {
    if (cat === 'largecap') return 'Large Cap Equity';
    if (cat === 'flexicap') return 'Flexi Cap Equity';
    if (cat === 'midcap') return 'Mid/Small Cap Equity';
    if (cat === 'debt') return 'Debt / Liquid';
    return cat;
  };

  return (
    <div className="goal-detail-page">
      <div className="mb-4">
        <button onClick={() => navigate('/goals')} className="btn btn-ghost btn-sm btn-with-icon pl-0">
          <ArrowLeft size={16} />
          <span>Back to Goals</span>
        </button>
      </div>

      <div className="goal-detail-header-panel mb-4">
        <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div>
            <h2 className="goal-name-title">{goal.name}</h2>
            <p className="text-secondary text-sm">
              Saved Plan ID: <code>{goal.id}</code> | Created {formatDate(goal.created_at)}
            </p>
          </div>
          <StatusIndicator status={goal.feasibility_status} />
        </div>
      </div>

      <div className="goal-detail-grid">
        {/* Left Side: Parameters & Projections */}
        <div className="goal-metrics-panel">
          <Card title="Saved Projection Metrics">
            <div className="detail-rows">
              <div className="detail-row">
                <span className="text-secondary">Present target cost</span>
                <span className="font-semibold text-primary">{formatINR(goal.target_amount)}</span>
              </div>
              
              <div className="detail-row">
                <span className="text-secondary">Target maturity date</span>
                <span className="font-semibold text-primary d-flex align-items-center">
                  <Calendar size={14} className="me-1 text-secondary" />
                  {formatDate(goal.target_date)}
                </span>
              </div>

              <div className="detail-row">
                <span className="text-secondary">Funding mode</span>
                <span className="font-semibold text-primary text-capitalize">{goal.contribution_mode}</span>
              </div>

              <div className="detail-row">
                <span className="text-secondary">Monthly contribution</span>
                <span className="font-semibold text-primary">{formatINR(goal.monthly_contribution)}</span>
              </div>

              <div className="detail-row">
                <span className="text-secondary">Lumpsum contribution</span>
                <span className="font-semibold text-primary">{formatINR(goal.lumpsum_amount)}</span>
              </div>

              <hr className="divider-neutral my-3" />

              <div className="detail-row">
                <span className="text-secondary">Assumed annual return</span>
                <span className="font-semibold text-accent d-flex align-items-center">
                  <TrendingUp size={14} className="me-1 text-accent" />
                  {goal.expected_return_pct}% p.a. ({goal.risk_level.toUpperCase()} Risk)
                </span>
              </div>

              <div className="detail-row">
                <span className="text-secondary font-semibold">Inflation Scenario</span>
                <span className="font-semibold text-primary capitalize">{goal.inflation_scenario} ({goal.inflation_rate_pct}% p.a.)</span>
              </div>

              <div className="detail-row border-primary-dark pt-2 mt-2">
                <span className="text-primary font-bold">Inflation-Adjusted Target</span>
                <span className="font-bold text-primary">{formatINR(goal.inflation_adjusted_target)}</span>
              </div>

              <div className="detail-row font-semibold">
                <span className="text-secondary">Projected final value</span>
                <span className="text-success">{formatINR(goal.feasibility_details?.projected_value || 0)}</span>
              </div>
            </div>

            {goal.feasibility_details?.message && (
              <div className="alert alert-success bg-success-subtle text-success mt-4 mb-0">
                <p className="text-xs m-0">{goal.feasibility_details.message}</p>
              </div>
            )}
          </Card>

          {/* Goal Intelligence Info */}
          <Card title="Goal Intelligence Attributes" className="mt-4">
            <div className="detail-rows">
              <div className="detail-row">
                <span className="text-secondary">Goal Category</span>
                <span className="font-semibold text-primary capitalize">{goal.goal_type}</span>
              </div>
              <div className="detail-row">
                <span className="text-secondary">Priority</span>
                <span className="font-semibold text-primary capitalize">{goal.priority}</span>
              </div>
              <div className="detail-row">
                <span className="text-secondary">Importance</span>
                <span className="font-semibold text-primary capitalize">{goal.importance}</span>
              </div>
              <div className="detail-row">
                <span className="text-secondary">Deadline Flexibility</span>
                <span className="font-semibold text-primary capitalize">{goal.deadline_flexibility}</span>
              </div>
            </div>
          </Card>
 
          {/* Stochastic Projections Card */}
          {simResult && (
            <Card title="Monte Carlo Stochastic Projections" className="mt-4">
              <div className="detail-rows">
                <div className="detail-row">
                  <span className="text-secondary">Success Probability</span>
                  <span className="font-bold text-success text-sm">{simResult.prob_success}%</span>
                </div>
                <div className="detail-row">
                  <span className="text-secondary">Shortfall Probability</span>
                  <span className="font-semibold text-danger text-sm">{simResult.prob_shortfall}%</span>
                </div>
                
                <hr className="divider-neutral my-2" />
                
                <div className="detail-row flex-column align-items-start gap-1">
                  <span className="text-secondary text-2xs block">Downside (10th Percentile Market)</span>
                  <span className="font-semibold text-danger text-xs">{formatINR(simResult.downside_percentile_10)}</span>
                </div>
                <div className="detail-row flex-column align-items-start gap-1">
                  <span className="text-secondary text-xs block">Median Simulated Corpus</span>
                  <span className="font-semibold text-accent text-xs">{formatINR(simResult.median_corpus)}</span>
                </div>
                <div className="detail-row flex-column align-items-start gap-1">
                  <span className="text-secondary text-2xs block">Upside (90th Percentile Market)</span>
                  <span className="font-semibold text-success text-xs">{formatINR(simResult.upside_percentile_90)}</span>
                </div>

                {simResult.prob_shortfall > 0 && (
                  <>
                    <hr className="divider-neutral my-2" />
                    <div className="detail-row">
                      <span className="text-secondary">Median Shortfall</span>
                      <span className="font-semibold text-danger">{formatINR(simResult.median_shortfall)}</span>
                    </div>
                    <div className="detail-row">
                      <span className="text-secondary">Expected Shortfall</span>
                      <span className="font-semibold text-danger">{formatINR(simResult.expected_shortfall)}</span>
                    </div>
                  </>
                )}
              </div>
              <div className="alert alert-neutral bg-surface-dark-only mt-3 text-2xs text-secondary border border-dark rounded p-2">
                <p className="m-0 leading-normal">{simResult.message}</p>
                <p className="text-3xs text-secondary mt-1 m-0 italic">Disclaimer: Stochastic simulations represent statistical probability distributions, not financial return guarantees.</p>
              </div>
            </Card>
          )}

          {/* Allocation Mix Card */}
          <Card title="Asset Allocation Mix" className="mt-4">
            <p className="text-secondary text-xs mb-3">
              Your mix is optimized for a <strong>{goal.term_type === 'short_term' ? 'Short Term' : 'Long Term'}</strong> target at a <strong>{goal.risk_level.toUpperCase()}</strong> risk profile.
            </p>
            <div className="allocation-progress-bar-container">
              {Object.entries(goal.fund_category_mix).map(([category, percentage]) => (
                <div 
                  key={category} 
                  className={`bar-chunk-${category}`} 
                  style={{ width: `${percentage}%` }}
                  title={`${formatCategoryName(category)}: ${percentage}%`}
                />
              ))}
            </div>
            <div className="allocation-legend mt-3">
              {Object.entries(goal.fund_category_mix).map(([category, percentage]) => (
                <div key={category} className="legend-item">
                  <span className={`legend-dot bg-dot-${category}`} />
                  <span className="legend-label text-secondary text-xs">
                    {formatCategoryName(category)}: <strong>{percentage}%</strong>
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* Risk Engine Strategies Card */}
          {goal.strategies && (
            <Card title="Risk Engine Recommended Strategies" className="mt-4">
              <div className="strategy-cards d-flex flex-column gap-2">
                {Object.entries(goal.strategies).map(([name, s]: [string, any]) => {
                  const isCurrentSelected = name === (
                    goal.risk_level === 'low' ? 'conservative' : (
                      goal.risk_level === 'mid' ? 'moderate' : 'aggressive'
                    )
                  );
                  
                  return (
                    <div 
                      key={name} 
                      className={`strategy-card p-3 rounded-lg border bg-surface-dark-only ${isCurrentSelected ? 'border-primary' : 'border-dark'}`}
                    >
                      <div className="d-flex justify-content-between align-items-center">
                        <span className="text-xs font-bold capitalize text-primary">
                          {name} {isCurrentSelected && '(Selected)'}
                        </span>
                        <span className="text-xs font-semibold bg-primary-dark-subtle text-primary px-2 py-0.5 rounded">
                          {s.equity_pct}% Eq / {s.debt_pct}% Dt
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 mt-2 text-2xs text-secondary">
                        <div>
                          <span className="block text-secondary text-2xs">Volatility: {s.volatility}</span>
                          <span className="block text-secondary text-2xs">Liquidity: {s.liquidity}</span>
                        </div>
                        <div className="text-right">
                          <span className="block text-secondary text-2xs">Return: {s.expected_return_range}</span>
                          <span className="block text-primary text-2xs font-bold">Goal Success Prob: {s.success_probability}%</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </div>

        {/* Right Side: Portfolio Recommendations */}
        <div className="recommended-funds-panel">
          <h3 className="panel-section-title mb-3">Portfolio Recommendations</h3>
          
          <Card title="Direct Mutual Funds" className="mb-4 bg-surface border-none">
            {Object.entries(goal.recommended_funds).length > 0 ? (
              <div className="fund-category-recommendations-list">
                {Object.entries(goal.recommended_funds).map(([category, funds]) => {
                  const percentage = goal.fund_category_mix[category] || 0;
                  if (percentage === 0) return null;
  
                  return (
                    <div key={category} className="fund-category-block mb-3">
                      <div className="category-block-header d-flex justify-content-between align-items-center mb-2">
                        <h5 className="font-semibold m-0 text-primary text-xs">{formatCategoryName(category)}</h5>
                        <span className="status-pill status-neutral status-sm">{percentage}% mix</span>
                      </div>
  
                      {funds && funds.length > 0 ? (
                        <div className="category-funds-list">
                          {funds.map((fund) => (
                            <div key={fund.scheme_code} className="recommended-fund-row p-2.5 card border-neutral-subtle mb-2 bg-surface">
                              <div className="fund-info-meta">
                                <span className="fund-code-text text-secondary text-2xs">Code: {fund.scheme_code}</span>
                                <h5 className="fund-name-row font-medium text-primary mt-0.5 text-xs">{fund.scheme_name}</h5>
                              </div>
                              <div className="fund-nav-row d-flex justify-content-between align-items-center mt-2 text-2xs">
                                <div>
                                  <span className="text-secondary">NAV: </span>
                                  <span className="font-semibold text-primary">₹{fund.latest_nav}</span>
                                  <span className="text-secondary"> ({fund.nav_date})</span>
                                </div>
                                <Link 
                                  to={`/funds?scheme=${fund.scheme_code}`}
                                  className="btn btn-ghost btn-sm btn-with-icon text-accent font-semibold text-xs"
                                >
                                  <Eye size={12} />
                                  <span>Explore Graph</span>
                                </Link>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-secondary text-2xs">
                          Fund schemes currently refreshing. Explore categories in the Fund Explorer directly.
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="card p-4 text-center">
                <HelpCircle size={32} className="text-secondary mb-2" />
                <p className="text-secondary text-sm">Recommended portfolio details are currently fetching. Please reload.</p>
              </div>
            )}
          </Card>

          {recs && (
            <Card title="Alternative ETFs & Trusts" className="bg-surface border-none">
              <p className="text-secondary text-2xs mb-3">
                Diversify with ETFs and Trusts matching your risk level.
              </p>
              {Object.entries(recs).map(([assetClass, assets]) => (
                <div key={assetClass} className="mb-3">
                  <h5 className="font-bold text-xs uppercase tracking-wider text-secondary capitalize mb-2">{assetClass} Mix</h5>
                  {assets && assets.length > 0 ? (
                    <div className="category-funds-list">
                      {assets.map((asset) => (
                        <div key={asset.identifier} className="recommended-fund-row p-2.5 card border-neutral-subtle mb-2 bg-surface">
                          <div className="fund-info-meta">
                            <span className="fund-code-text text-secondary text-2xs block">Type: {asset.instrument_type.replace('_', ' ').toUpperCase()} | Liquidity: {asset.liquidity.toUpperCase()}</span>
                            <h5 className="fund-name-row font-semibold text-primary mt-0.5 text-xs">{asset.asset_name}</h5>
                          </div>
                          <div className="fund-nav-row d-flex justify-content-between align-items-center mt-2 text-2xs">
                            <div>
                              <span className="text-secondary">Price/NAV: </span>
                              <span className="font-semibold text-primary">
                                {asset.latest_price !== null ? formatINR(asset.latest_price) : 'N/A'}
                              </span>
                            </div>
                            <span className="text-secondary text-2xs font-semibold">{asset.tax_classification.replace('_', ' ').toUpperCase()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-secondary text-2xs">No alternative assets recommended for this class.</p>
                  )}
                </div>
              ))}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
