/* frontend/src/pages/GoalsList.tsx */
import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { goalsService } from '../services/goalsService';
import { Card } from '../components/common/Card';
import { StatusIndicator } from '../components/common/StatusIndicator';
import { Button } from '../components/common/Button';
import { formatINR } from '../utils/currency';
import { formatDate } from '../utils/date';
import { Target, Plus, Calendar, Coins, TrendingUp, AlertCircle } from 'lucide-react';

export const GoalsList: React.FC = () => {
  const { data: goals, isLoading, error, refetch } = useQuery({
    queryKey: ['goals'],
    queryFn: () => goalsService.getGoals(),
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

  if (error) {
    return (
      <div className="error-state-box card p-4">
        <AlertCircle size={40} className="text-danger mb-2" />
        <h3>Failed to load investment goals</h3>
        <p className="text-secondary">{error.message || 'Please check your connection.'}</p>
        <Button onClick={() => refetch()} variant="secondary" className="mt-3">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="goals-page-container">
      <div className="page-header-row mb-4">
        <div>
          <h2>Goals Planner</h2>
          <p className="text-secondary">Simulate and track customized investment milestones with automated feasibility check.</p>
        </div>
        <Link to="/goals/new" className="btn btn-primary btn-with-icon">
          <Plus size={16} />
          <span>New Goal</span>
        </Link>
      </div>

      {goals && goals.length > 0 ? (
        <div className="goals-grid">
          {goals.map((goal) => (
            <Card key={goal.id} className="goal-list-card">
              <div className="goal-card-header">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
                    {goal.priority_rank !== null && (
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, backgroundColor: 'var(--accent-color-light)', color: 'var(--accent-color)', padding: '0.1875rem 0.5rem', borderRadius: '4px' }}>
                        Rank #{goal.priority_rank}
                      </span>
                    )}
                    <span style={{ fontSize: '0.7rem', fontWeight: 600, backgroundColor: 'hsl(220, 12%, 93%)', color: 'var(--text-secondary)', padding: '0.1875rem 0.5rem', borderRadius: '4px', textTransform: 'capitalize' }}>
                      {goal.priority} Priority
                    </span>
                  </div>
                  <h3 className="goal-card-name">{goal.name}</h3>
                  <span className="text-secondary text-xs">Risk level: {goal.risk_level.toUpperCase()}</span>
                </div>
                <StatusIndicator status={goal.feasibility_status} />
              </div>

              <div className="goal-card-metrics-grid">
                <div className="metric-cell">
                  <span className="cell-label text-secondary text-xs">Target Goal</span>
                  <span className="cell-value font-semibold text-primary">{formatINR(goal.target_amount)}</span>
                </div>
                
                <div className="metric-cell">
                  <span className="cell-label text-secondary text-xs">Target Date</span>
                  <span className="cell-value font-semibold text-primary d-flex align-items-center">
                    <Calendar size={12} className="me-1 text-secondary" />
                    {formatDate(goal.target_date)}
                  </span>
                </div>

                <div className="metric-cell">
                  <span className="cell-label text-secondary text-xs">Contributions</span>
                  <span className="cell-value font-semibold text-primary d-flex align-items-center">
                    <Coins size={12} className="me-1 text-secondary" />
                    {goal.contribution_mode === 'sip' 
                      ? `${formatINR(goal.monthly_contribution)} / mo`
                      : goal.contribution_mode === 'lumpsum'
                      ? `${formatINR(goal.lumpsum_amount)} lumpsum`
                      : `${formatINR(goal.monthly_contribution)}/mo + ${formatINR(goal.lumpsum_amount)}`}
                  </span>
                </div>

                <div className="metric-cell">
                  <span className="cell-label text-secondary text-xs">Assumed Returns</span>
                  <span className="cell-value font-semibold text-primary d-flex align-items-center">
                    <TrendingUp size={12} className="me-1 text-secondary" />
                    {goal.expected_return_pct}% p.a.
                  </span>
                </div>
              </div>

              <div className="goal-card-actions">
                <Link to={`/goals/${goal.id}`} className="btn btn-secondary w-100">
                  View Recommendations & Projections
                </Link>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <div className="table-empty-state card p-5 text-center mt-3">
          <Target size={48} className="text-secondary mb-2" />
          <h3>No goals created yet</h3>
          <p className="text-secondary mb-4">
            Map out targets (e.g. buying a home, car downpayments) to verify feasibility against inflation adjustments.
          </p>
          <Link to="/goals/new" className="btn btn-primary btn-with-icon">
            <Plus size={16} />
            <span>Create Your First Goal</span>
          </Link>
        </div>
      )}
    </div>
  );
};
