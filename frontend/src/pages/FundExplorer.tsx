/* frontend/src/pages/FundExplorer.tsx */
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fundService } from '../services/fundService';
import { Card } from '../components/common/Card';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { TrendingUp, AlertCircle, Info, Calendar, X } from 'lucide-react';

export const FundExplorer: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeCategory, setActiveCategory] = useState<string>('largecap');
  const [selectedSchemeCode, setSelectedSchemeCode] = useState<string | null>(null);

  // Check for ?scheme=123 in url
  useEffect(() => {
    const scheme = searchParams.get('scheme');
    if (scheme) {
      setSelectedSchemeCode(scheme);
    }
  }, [searchParams]);

  const categories = [
    { key: 'largecap', name: 'Large Cap' },
    { key: 'flexicap', name: 'Flexi Cap' },
    { key: 'midcap', name: 'Mid & Small Cap' },
    { key: 'debt', name: 'Debt & Liquid' },
  ];

  // Fetch list of funds in the selected category
  const { data: funds, isLoading: fundsLoading, error: fundsError } = useQuery({
    queryKey: ['funds', activeCategory],
    queryFn: () => fundService.getFundsByCategory(activeCategory, 15),
  });

  // Fetch details & historical data for the selected fund scheme
  const { data: fundDetail, isLoading: detailLoading, error: detailError } = useQuery({
    queryKey: ['fundDetail', selectedSchemeCode],
    queryFn: () => fundService.getFundDetail(selectedSchemeCode || ''),
    enabled: !!selectedSchemeCode,
    retry: false,
  });

  const selectFund = (schemeCode: string) => {
    setSelectedSchemeCode(schemeCode);
    setSearchParams({ scheme: schemeCode });
  };

  const closeDetail = () => {
    setSelectedSchemeCode(null);
    setSearchParams({});
  };

  // Keep historical NAV series ordered chronologically (oldest to newest) for chart plotting
  const chartData = fundDetail?.historical_nav 
    ? [...fundDetail.historical_nav].reverse().slice(-60) // Show last 60 data points for speed/readability
    : [];

  return (
    <div className="fund-explorer-container">
      <div className="page-header-row mb-4">
        <div>
          <h2>Fund Explorer</h2>
          <p className="text-secondary">Track live direct-growth mutual fund schemes synced from AMFI indexes.</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="explorer-tabs-container mb-3">
        {categories.map((cat) => (
          <button
            key={cat.key}
            onClick={() => {
              setActiveCategory(cat.key);
              closeDetail();
            }}
            className={`tab-btn ${activeCategory === cat.key ? 'tab-btn-active' : ''}`}
          >
            {cat.name}
          </button>
        ))}
      </div>

      <div className="explorer-split-grid">
        {/* Left Pane: Scheme List */}
        <div className="schemes-list-panel">
          <Card title={`${categories.find(c => c.key === activeCategory)?.name} Schemes`}>
            {fundsLoading && (
              <div className="skeleton-loading-container">
                <div className="skeleton skeleton-row-short mb-2" />
                <div className="skeleton skeleton-row-short mb-2" />
                <div className="skeleton skeleton-row-short mb-2" />
              </div>
            )}

            {fundsError && (
              <div className="alert alert-danger">
                <AlertCircle size={16} className="me-2" />
                <span>Failed to fetch scheme lists.</span>
              </div>
            )}

            {funds && funds.length > 0 ? (
              <div className="funds-directory">
                {funds.map((fund) => (
                  <div
                    key={fund.scheme_code}
                    onClick={() => selectFund(fund.scheme_code)}
                    className={`fund-directory-row ${selectedSchemeCode === fund.scheme_code ? 'row-active' : ''}`}
                  >
                    <div className="fund-row-meta">
                      <span className="fund-code-text text-secondary text-xs">Code: {fund.scheme_code}</span>
                      <h4 className="font-semibold text-primary m-0 mt-0.5">{fund.scheme_name}</h4>
                    </div>
                    <div className="fund-row-nav text-right">
                      <span className="font-semibold text-primary">₹{fund.latest_nav}</span>
                      <span className="text-secondary text-xs d-block">{fund.nav_date}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              !fundsLoading && <p className="text-secondary text-center p-3">No schemes in this category found.</p>
            )}
          </Card>
        </div>

        {/* Right Pane: Historical NAV Details */}
        <div className="scheme-details-chart-panel">
          {selectedSchemeCode ? (
            <Card className="chart-preview-card">
              {detailLoading && (
                <div className="chart-skeleton-loading text-center p-5">
                  <span className="spinner-border text-primary me-2" role="status" />
                  <span>Fetching historical chart points...</span>
                </div>
              )}

              {detailError && (
                <div className="alert alert-danger">
                  <AlertCircle size={16} className="me-2" />
                  <span>Failed to load details. Scheme might be missing from cached database.</span>
                </div>
              )}

              {fundDetail && !detailLoading && (
                <div className="chart-details-body">
                  <div className="chart-header-row d-flex justify-content-between align-items-start mb-4">
                    <div>
                      <span className="text-secondary text-xs">Code: {fundDetail.scheme_code} | {fundDetail.category.toUpperCase()}</span>
                      <h3 className="font-semibold text-primary m-0 mt-1">{fundDetail.scheme_name}</h3>
                    </div>
                    <button className="btn btn-ghost btn-sm p-1" onClick={closeDetail}>
                      <X size={20} />
                    </button>
                  </div>

                  <div className="nav-highlight-row d-flex gap-4 mb-4">
                    <div className="highlight-cell">
                      <span className="text-secondary text-xs">Current NAV Value</span>
                      <h2 className="font-bold text-accent mt-0.5">₹{fundDetail.latest_nav}</h2>
                    </div>
                    <div className="highlight-cell">
                      <span className="text-secondary text-xs">NAV Date</span>
                      <h4 className="font-semibold text-primary mt-1 d-flex align-items-center">
                        <Calendar size={14} className="me-1 text-secondary" />
                        {fundDetail.nav_date}
                      </h4>
                    </div>
                  </div>

                  {/* NAV Trend Graph */}
                  <div className="nav-trend-chart-container mb-4">
                    {fundDetail.historical_nav_available && chartData.length > 0 ? (
                      <div style={{ width: '100%', height: 260 }}>
                        <ResponsiveContainer>
                          <LineChart data={chartData} margin={{ top: 5, right: 5, left: -25, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                            <XAxis 
                              dataKey="date" 
                              tick={{ fontSize: 9 }} 
                              stroke="#888888"
                              reversed // Dates in API are descending, reverse them to plot chronologically
                            />
                            <YAxis tick={{ fontSize: 9 }} stroke="#888888" domain={['auto', 'auto']} />
                            <Tooltip 
                              contentStyle={{ 
                                backgroundColor: 'var(--bg-surface-dark)', 
                                borderColor: 'var(--border-color-dark)',
                                color: 'var(--text-light)',
                                fontSize: 11
                              }}
                            />
                            <Line 
                              type="monotone" 
                              dataKey="nav" 
                              stroke="var(--accent-color)" 
                              strokeWidth={2}
                              dot={false}
                              activeDot={{ r: 6 }} 
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <div className="chart-degrade-state p-4 text-center border-neutral-subtle card bg-surface-dark-subtle">
                        <TrendingUp size={36} className="text-secondary mx-auto mb-2" />
                        <h4 className="text-primary font-semibold">Historical Chart Unavailable</h4>
                        <p className="text-secondary text-xs mt-1">
                          The historical NAV endpoint is currently down or caching. You can still verify the current active NAV above.
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="info-tip-row bg-accent-light p-2.5 rounded">
                    <Info size={16} className="text-accent flex-shrink-0 me-2" />
                    <p className="text-xs text-accent-dark m-0">
                      Calculations are based on Direct Mutual Funds, which bypass agent commissions to offer lower expense ratios.
                    </p>
                  </div>
                </div>
              )}
            </Card>
          ) : (
            <Card className="chart-empty-card text-center p-5 d-flex flex-column align-items-center justify-content-center">
              <TrendingUp size={44} className="text-secondary mb-2" />
              <h3>Select a Fund Scheme</h3>
              <p className="text-secondary text-sm">
                Explore the mutual funds list on the left to see live pricing charts and details.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
