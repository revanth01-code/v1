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

export const GoalDetails: React.FC = () => {
  const { goalId } = useParams<{ goalId: string }>();
  const navigate = useNavigate();

  const { data: goal, isLoading, error } = useQuery({
    queryKey: ['goal', goalId],
    queryFn: () => goalsService.getGoal(goalId || ''),
    enabled: !!goalId,
    retry: 1,
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
                <span className="text-secondary">Inflation-Adjusted target</span>
                <span className="font-semibold text-primary">{formatINR(goal.inflation_adjusted_target)}</span>
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
        </div>

        {/* Right Side: Recommended Funds */}
        <div className="recommended-funds-panel">
          <h3 className="panel-section-title mb-3">Fund Portfolio Recommendations</h3>
          {Object.entries(goal.recommended_funds).length > 0 ? (
            <div className="fund-category-recommendations-list">
              {Object.entries(goal.recommended_funds).map(([category, funds]) => {
                const percentage = goal.fund_category_mix[category] || 0;
                if (percentage === 0) return null;

                return (
                  <div key={category} className="fund-category-block card p-3 mb-3">
                    <div className="category-block-header d-flex justify-content-between align-items-center mb-3">
                      <h4 className="font-semibold m-0 text-primary">{formatCategoryName(category)}</h4>
                      <span className="status-pill status-neutral status-sm">{percentage}% mix</span>
                    </div>

                    {funds && funds.length > 0 ? (
                      <div className="category-funds-list">
                        {funds.map((fund) => (
                          <div key={fund.scheme_code} className="recommended-fund-row p-2.5 card border-neutral-subtle mb-2 bg-surface">
                            <div className="fund-info-meta">
                              <span className="fund-code-text text-secondary text-xs">Code: {fund.scheme_code}</span>
                              <h5 className="fund-name-row font-medium text-primary mt-0.5">{fund.scheme_name}</h5>
                            </div>
                            <div className="fund-nav-row d-flex justify-content-between align-items-center mt-2.5">
                              <div>
                                <span className="text-secondary text-xs">NAV: </span>
                                <span className="font-semibold text-primary">₹{fund.latest_nav}</span>
                                <span className="text-secondary text-xs"> ({fund.nav_date})</span>
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
                      <p className="text-secondary text-xs">
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
        </div>
      </div>
    </div>
  );
};
