import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { dashboardService } from '../services/dashboardService';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { StatusIndicator } from '../components/common/StatusIndicator';
import { formatINR } from '../utils/currency';
import { formatDate } from '../utils/date';
import { 
  Target, 
  ShieldAlert, 
  Hourglass, 
  ArrowRight, 
  Plus, 
  TrendingUp, 
  MessageSquare,
  AlertCircle
} from 'lucide-react';

export const Dashboard: React.FC = () => {

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => dashboardService.getSummary(),
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="skeleton-loading-container">
        <div className="skeleton skeleton-banner" />
        <div className="skeleton-grid-3">
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
        </div>
        <div className="skeleton skeleton-table" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-state-box card p-4">
        <AlertCircle size={40} className="text-danger mb-2" />
        <h3>Failed to load dashboard data</h3>
        <p className="text-secondary">{error.message || 'Please try again later.'}</p>
        <Button onClick={() => refetch()} variant="secondary" className="mt-3">
          Retry
        </Button>
      </div>
    );
  }

  if (!data) return null;

  const { goals, retirement, emergency_fund } = data;

  return (
    <div className="dashboard-page-container">
      {/* Overview Metric Row */}
      <div className="dashboard-hero-row">
        <div className="hero-content">
          <h2>Financial Overview</h2>
          <p className="text-secondary">Keep track of your milestones and active portfolios</p>
        </div>
        <Link to="/goals/new" className="btn btn-primary btn-with-icon">
          <Plus size={16} />
          <span>New Goal</span>
        </Link>
      </div>

      <div className="dashboard-grid-3">
        {/* Goals Summary Card */}
        <Card title="Goals Track" className="dashboard-metric-card">
          <div className="metric-icon-row">
            <Target className="metric-icon text-accent" />
            <span className="metric-main-number">{goals.total}</span>
          </div>
          <div className="metric-detail-rows">
            <div className="metric-detail-row">
              <span className="text-secondary">Feasible:</span>
              <span className="badge-value text-success">{goals.feasible}</span>
            </div>
            <div className="metric-detail-row">
              <span className="text-secondary">Borderline:</span>
              <span className="badge-value text-warning">{goals.borderline}</span>
            </div>
          </div>
          <Link to="/goals" className="card-action-link mt-3">
            <span>Manage goals</span>
            <ArrowRight size={14} />
          </Link>
        </Card>

        {/* Emergency Fund Card */}
        <Card title="Emergency Fund" className="dashboard-metric-card">
          {emergency_fund ? (
            <>
              <div className="metric-icon-row">
                <ShieldAlert className="metric-icon text-warning" />
                <span className="metric-main-number">{formatINR(emergency_fund.current_amount)}</span>
              </div>
              <div className="metric-detail-rows">
                <div className="metric-detail-row">
                  <span className="text-secondary">Target Reserve:</span>
                  <span>{formatINR(emergency_fund.target_amount)}</span>
                </div>
                <div className="metric-detail-row">
                  <span className="text-secondary">Plan Status:</span>
                  <StatusIndicator status={emergency_fund.status} size="sm" />
                </div>
              </div>
              <Link to="/emergency-fund" className="card-action-link mt-3">
                <span>Configure planner</span>
                <ArrowRight size={14} />
              </Link>
            </>
          ) : (
            <div className="card-empty-setup-state">
              <ShieldAlert size={28} className="text-secondary mb-2" />
              <p>Reserve fund plan not set up yet.</p>
              <Link to="/emergency-fund" className="btn btn-secondary btn-sm mt-2">
                Configure Now
              </Link>
            </div>
          )}
        </Card>

        {/* Retirement Planner Card */}
        <Card title="Retirement Plan" className="dashboard-metric-card">
          {retirement ? (
            <>
              <div className="metric-icon-row">
                <Hourglass className="metric-icon text-success" />
                <span className="metric-main-number">{formatINR(retirement.required_corpus)}</span>
              </div>
              <div className="metric-detail-rows">
                <div className="metric-detail-row">
                  <span className="text-secondary">Years to Retire:</span>
                  <span>{retirement.years_to_retirement} years</span>
                </div>
                <div className="metric-detail-row">
                  <span className="text-secondary">Status:</span>
                  <StatusIndicator status={retirement.feasibility_status} size="sm" />
                </div>
              </div>
              <Link to="/retirement" className="card-action-link mt-3">
                <span>Configure planner</span>
                <ArrowRight size={14} />
              </Link>
            </>
          ) : (
            <div className="card-empty-setup-state">
              <Hourglass size={28} className="text-secondary mb-2" />
              <p>Retirement timeline not mapped yet.</p>
              <Link to="/retirement" className="btn btn-secondary btn-sm mt-2">
                Configure Now
              </Link>
            </div>
          )}
        </Card>
      </div>

      {/* Goals List Detail Panel */}
      <div className="dashboard-section-panel mt-4">
        <Card title="Active Investment Goals">
          {goals.items.length > 0 ? (
            <div className="table-responsive">
              <table className="table table-clean">
                <thead>
                  <tr>
                    <th>Goal Name</th>
                    <th>Target Amount</th>
                    <th>Target Date</th>
                    <th>Feasibility</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {goals.items.map((goal) => (
                    <tr key={goal.id}>
                      <td className="font-semibold">{goal.name}</td>
                      <td>{formatINR(goal.target_amount)}</td>
                      <td>{formatDate(goal.target_date)}</td>
                      <td>
                        <StatusIndicator status={goal.feasibility_status} size="sm" />
                      </td>
                      <td className="text-right">
                        <Link to={`/goals/${goal.id}`} className="btn btn-ghost btn-sm">
                          Details
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="table-empty-state">
              <Target size={36} className="text-secondary mb-2" />
              <h3>No investment goals saved yet</h3>
              <p className="text-secondary">Create a goal to run checks and receive fund recommendations</p>
              <Link to="/goals/new" className="btn btn-primary mt-3 btn-with-icon">
                <Plus size={16} />
                <span>Create Your First Goal</span>
              </Link>
            </div>
          )}
        </Card>
      </div>

      {/* Floating features quick helper links */}
      <div className="quick-access-banner mt-4">
        <div className="quick-access-item">
          <TrendingUp className="quick-icon text-accent" />
          <div className="quick-text">
            <h4>Mutual Funds Directory</h4>
            <p>Explore current Net Asset Values and historical fund performance charts.</p>
            <Link to="/funds" className="quick-link">Go to Explorer &rarr;</Link>
          </div>
        </div>
        <div className="quick-access-item">
          <MessageSquare className="quick-icon text-success" />
          <div className="quick-text">
            <h4>AI Financial Coach</h4>
            <p>Talk to our virtual helper to analyze your current saved targets.</p>
            <Link to="/coach" className="quick-link">Start Chatting &rarr;</Link>
          </div>
        </div>
      </div>
    </div>
  );
};
