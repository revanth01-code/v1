/* frontend/src/pages/WhatIfLab.tsx */
import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { goalsService } from '../services/goalsService';
import { simulationService } from '../services/simulationService';
import { Card } from '../components/common/Card';
import { SliderField } from '../components/common/SliderField';
import { StatusIndicator } from '../components/common/StatusIndicator';
import { InfoTooltip } from '../components/common/InfoTooltip';
import { formatINR } from '../utils/currency';
import { 
  Sliders, 
  TrendingUp, 
  AlertTriangle, 
  HelpCircle,
  Activity,
  ShieldAlert,
  Flame,
  UserCheck
} from 'lucide-react';
import type { SimulationInput, SimulationResult, GoalOut } from '../types/api';

export const WhatIfLab: React.FC = () => {
  const { data: goals, isLoading: goalsLoading } = useQuery({
    queryKey: ['goals'],
    queryFn: () => goalsService.getGoals(),
  });

  const [selectedGoalId, setSelectedGoalId] = useState<string>('default');
  const [selectedGoal, setSelectedGoal] = useState<GoalOut | null>(null);

  // Scenario parameters state
  const [targetAmount, setTargetAmount] = useState(1000000);
  const [monthlyContribution, setMonthlyContribution] = useState(15000);
  const [lumpsumAmount, setLumpsumAmount] = useState(100000);
  const [durationMonths, setDurationMonths] = useState(60); // default 5 years
  const [inflationPct, setInflationPct] = useState(6.0);
  const [equityPct, setEquityPct] = useState(50.0);
  const [riskLevel, setRiskLevel] = useState<'low' | 'mid' | 'high' | 'custom'>('custom');
  
  // What-if specific additions
  const [sipPauseMonths, setSipPauseMonths] = useState(0);
  const [sipReducePct, setSipReducePct] = useState(0);
  
  // Predefined Stress Scenarios state
  const [stressScenario, setStressScenario] = useState<SimulationInput['stress_scenario']>('none');

  // Outputs
  const [results, setResults] = useState<{
    current_plan: SimulationResult;
    what_if_plan: SimulationResult;
  } | null>(null);
  const [simulating, setSimulating] = useState(false);

  // Sync selected goal details
  useEffect(() => {
    if (selectedGoalId === 'default' || !goals) {
      setSelectedGoal(null);
      // Reset to default baseline values
      setTargetAmount(1000000);
      setMonthlyContribution(15000);
      setLumpsumAmount(100000);
      setDurationMonths(60);
      setInflationPct(6.0);
      setEquityPct(50.0);
      setRiskLevel('custom');
      setSipPauseMonths(0);
      setSipReducePct(0);
      setStressScenario('none');
    } else {
      const g = (goals as GoalOut[]).find((x: GoalOut) => x.id === selectedGoalId);
      if (g) {
        setSelectedGoal(g);
        setTargetAmount(g.target_amount);
        setMonthlyContribution(g.monthly_contribution);
        setLumpsumAmount(g.lumpsum_amount);
        
        // Calculate goal duration in months from target_date
        const targetDate = new Date(g.target_date);
        const today = new Date();
        const diffMonths = Math.max(
          (targetDate.getFullYear() - today.getFullYear()) * 12 +
            (targetDate.getMonth() - today.getMonth()),
          1
        );
        setDurationMonths(diffMonths);
        setInflationPct(g.inflation_rate_pct || 6.0);
        
        // Map risk levels to default equity percentage
        if (g.risk_level === 'low') setEquityPct(20.0);
        else if (g.risk_level === 'high') setEquityPct(80.0);
        else setEquityPct(50.0);
        
        setRiskLevel('custom');
        setSipPauseMonths(0);
        setSipReducePct(0);
        setStressScenario('none');
      }
    }
  }, [selectedGoalId, goals]);

  // Run What-if Comparison Simulation
  const runWhatIfSimulation = async () => {
    setSimulating(true);
    try {
      // Calculate target date strings for API
      const currentTargetDate = new Date();
      if (selectedGoal) {
        currentTargetDate.setTime(new Date(selectedGoal.target_date).getTime());
      } else {
        currentTargetDate.setMonth(currentTargetDate.getMonth() + durationMonths);
      }
      
      const whatIfTargetDate = new Date();
      whatIfTargetDate.setMonth(whatIfTargetDate.getMonth() + durationMonths);

      // Baseline parameters
      const currentPlanInput: SimulationInput = {
        lumpsum_amount: selectedGoal ? selectedGoal.lumpsum_amount : 100000,
        monthly_contribution: selectedGoal ? selectedGoal.monthly_contribution : 15000,
        target_amount: selectedGoal ? selectedGoal.target_amount : 1000000,
        target_date: currentTargetDate.toISOString().split('T')[0],
        risk_level: selectedGoal ? (selectedGoal.risk_level as any) : 'mid',
        inflation_pct: selectedGoal ? selectedGoal.inflation_rate_pct : 6.0,
        stress_scenario: 'none',
        sip_pause_start: 0,
        sip_pause_duration: 0,
        sip_reduce_pct: 0,
        sip_reduce_start: 0,
        sip_reduce_duration: 0,
      };

      // Scenario parameters
      const whatIfPlanInput: SimulationInput = {
        lumpsum_amount: lumpsumAmount,
        monthly_contribution: monthlyContribution,
        target_amount: targetAmount,
        target_date: whatIfTargetDate.toISOString().split('T')[0],
        risk_level: riskLevel,
        equity_pct: equityPct,
        debt_pct: 100.0 - equityPct,
        inflation_pct: inflationPct,
        stress_scenario: stressScenario,
        sip_pause_start: sipPauseMonths > 0 ? 1 : 0,
        sip_pause_duration: sipPauseMonths,
        sip_reduce_pct: sipReducePct,
        sip_reduce_start: sipReducePct > 0 ? 1 : 0,
        sip_reduce_duration: sipReducePct > 0 ? 12 : 0, // default 12 months reduction
      };

      const data = await simulationService.compareWhatIf({
        current_plan: currentPlanInput,
        what_if_plan: whatIfPlanInput,
      });
      
      setResults(data);
    } catch (err) {
      // Handle error
    } finally {
      setSimulating(false);
    }
  };

  useEffect(() => {
    runWhatIfSimulation();
  }, [
    selectedGoal,
    targetAmount,
    monthlyContribution,
    lumpsumAmount,
    durationMonths,
    inflationPct,
    equityPct,
    sipPauseMonths,
    sipReducePct,
    stressScenario,
  ]);

  if (goalsLoading) {
    return <div className="skeleton skeleton-banner m-4" />;
  }

  return (
    <div className="what-if-lab-container">
      <div className="page-header-row mb-4">
        <div>
          <h2>What-If Lab & Stress Tester</h2>
          <p className="text-secondary">Simulate temporary changes and stress scenarios stochastically. No changes are saved to your plan.</p>
        </div>
      </div>

      {/* Baseline Selector */}
      <div className="card p-3 mb-4 bg-surface border-none d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div className="d-flex align-items-center">
          <Sliders className="text-primary me-2 flex-shrink-0" />
          <label htmlFor="goal_select" className="form-label mb-0 font-semibold text-sm">Compare against Saved Goal:</label>
        </div>
        <select
          id="goal_select"
          className="form-control w-auto"
          value={selectedGoalId}
          onChange={(e) => setSelectedGoalId(e.target.value)}
        >
          <option value="default">Default Baseline (₹10L Target, 5 Years)</option>
          {(goals as GoalOut[])?.map((g: GoalOut) => (
            <option key={g.id} value={g.id}>{g.name} (₹{(g.target_amount / 100000).toFixed(1)}L)</option>
          ))}
        </select>
      </div>

      <div className="goal-creator-grid">
        {/* Left Side: What-If Adjusters */}
        <div className="form-card-panel">
          <Card title="Scenario Adjustments">
            <div className="form-sections d-flex flex-column gap-3">
              <div>
                <h4 className="text-xs font-bold text-secondary uppercase tracking-wider mb-2">Target Sizing</h4>
                <SliderField
                  label="Target Goal Amount (₹)"
                  min={10000}
                  max={10000000}
                  step={50000}
                  value={targetAmount}
                  onChange={setTargetAmount}
                  formatValue={formatINR}
                />
                <SliderField
                  label="Timeline Horizon (Months)"
                  min={6}
                  max={240}
                  step={6}
                  value={durationMonths}
                  onChange={setDurationMonths}
                  formatValue={(v) => `${v} Mo (${(v / 12).toFixed(1)} Yrs)`}
                />
              </div>

              <hr className="divider-dark" />

              <div>
                <h4 className="text-xs font-bold text-secondary uppercase tracking-wider mb-2">Funding Metrics</h4>
                <SliderField
                  label="Monthly SIP Contribution (₹)"
                  min={0}
                  max={500000}
                  step={5000}
                  value={monthlyContribution}
                  onChange={setMonthlyContribution}
                  formatValue={formatINR}
                />
                <SliderField
                  label="One-Time Lumpsum Funding (₹)"
                  min={0}
                  max={5000000}
                  step={20000}
                  value={lumpsumAmount}
                  onChange={setLumpsumAmount}
                  formatValue={formatINR}
                />
              </div>

              <hr className="divider-dark" />

              <div>
                <h4 className="text-xs font-bold text-secondary uppercase tracking-wider mb-2">Asset Allocation & Inflation</h4>
                <SliderField
                  label="Asset Mix: Equity vs Debt (%)"
                  min={0}
                  max={100}
                  step={5}
                  value={equityPct}
                  onChange={setEquityPct}
                  formatValue={(v) => `${v}% Equity / ${100 - v}% Debt`}
                />
                <SliderField
                  label={
                    <span className="d-flex align-items-center">
                      Expected Inflation Rate (%)
                      <InfoTooltip term="Inflation Rate" explanation="Inflation means things generally become more expensive over time. We use it to estimate what your goal may cost in the future." />
                    </span>
                  }
                  min={0}
                  max={15}
                  step={0.5}
                  value={inflationPct}
                  onChange={setInflationPct}
                  formatValue={(v) => `${v}% p.a.`}
                />
              </div>

              <hr className="divider-dark" />

              <div>
                <h4 className="text-xs font-bold text-secondary uppercase tracking-wider mb-2">Temporary Interruptions</h4>
                <SliderField
                  label="Pause Monthly SIP (Months)"
                  min={0}
                  max={24}
                  step={3}
                  value={sipPauseMonths}
                  onChange={setSipPauseMonths}
                  formatValue={(v) => v === 0 ? 'No Pause' : `Pause first ${v} months`}
                />
                <SliderField
                  label="Reduce Monthly SIP (Percentage %)"
                  min={0}
                  max={100}
                  step={10}
                  value={sipReducePct}
                  onChange={setSipReducePct}
                  formatValue={(v) => v === 0 ? 'No Reduction' : `Reduce by ${v}%`}
                />
              </div>

              <hr className="divider-dark" />

              <div>
                <h4 className="text-xs font-bold text-secondary uppercase tracking-wider mb-2 d-flex align-items-center">
                  <Activity size={14} className="text-danger me-1" />
                  Predefined Stress Tests
                </h4>
                <div className="stress-scenarios-grid d-flex flex-wrap gap-2 mt-2">
                  {[
                    { id: 'none', label: 'No Stress', icon: UserCheck, color: 'btn-secondary' },
                    { id: 'market_downturn', label: '2008 Crash (-20% / Vol)', icon: ShieldAlert, color: 'btn-danger' },
                    { id: 'high_inflation', label: 'High Inflation (+3%)', icon: Flame, color: 'btn-warning' },
                    { id: 'low_return', label: 'Low Returns (-3% p.a.)', icon: AlertTriangle, color: 'btn-warning' },
                  ].map((x) => {
                    const Icon = x.icon;
                    return (
                      <button
                        key={x.id}
                        type="button"
                        className={`btn btn-sm ${stressScenario === x.id ? 'btn-primary' : 'btn-ghost border-neutral-subtle'}`}
                        onClick={() => setStressScenario(x.id as any)}
                      >
                        <Icon size={12} className="me-1" />
                        <span>{x.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Side: Projections Preview */}
        <div className="projections-panel">
          <Card title="Stochastic Simulation Output" className="bg-surface-dark-subtle border-none">
            {simulating && (
              <div className="checking-overlay">
                <span className="spinner-border spinner-border-sm me-2" />
                <span>Recalculating 2,000 trials...</span>
              </div>
            )}

            {results ? (
              <div className="simulation-details">
                <div className="comparison-columns grid grid-cols-2 gap-4">
                  {/* Current Plan Column */}
                  <div className="current-plan-col">
                    <span className="text-secondary text-2xs uppercase tracking-wider block font-semibold">Baseline Plan</span>
                    
                    <div className="sim-status-row mb-2 mt-1">
                      <StatusIndicator status={results.current_plan.prob_success >= 85 ? 'highly_feasible' : (results.current_plan.prob_success >= 60 ? 'feasible' : (results.current_plan.prob_success >= 30 ? 'borderline' : 'unlikely'))} size="sm" />
                    </div>

                    <div className="stat-summary-rows-simple mt-2 d-flex flex-column gap-2">
                      <div className="row-val">
                        <span className="text-secondary text-2xs block d-flex align-items-center">
                          Success Probability
                          <InfoTooltip term="Success Probability" explanation="Success probability is an estimate of how likely the current plan is to reach your target under the assumptions used by InvestPlan. It is an estimate, not a guarantee." />
                        </span>
                        <span className="font-bold text-sm text-primary">{results.current_plan.prob_success}%</span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block">Median Final Corpus</span>
                        <span className="font-semibold text-sm text-primary">{formatINR(results.current_plan.median_corpus)}</span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block d-flex align-items-center">
                          Inflation-Adjusted Target
                          <InfoTooltip term="Inflation-Adjusted Target" explanation="The estimated future cost of your goal, calculated by increasing your current target amount by the expected inflation rate over time." />
                        </span>
                        <span className="font-semibold text-sm text-secondary">{formatINR(results.current_plan.adjusted_target)}</span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block">Shortfall Risk (%)</span>
                        <span className="font-semibold text-sm text-danger">{results.current_plan.prob_shortfall}%</span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block">Expected Shortfall</span>
                        <span className="font-semibold text-sm text-danger">{formatINR(results.current_plan.expected_shortfall)}</span>
                      </div>
                    </div>
                  </div>

                  {/* What-If Plan Column */}
                  <div className="what-if-plan-col border-l border-dark pl-4 bg-surface-dark-only p-2.5 rounded-lg border border-primary-dark">
                    <span className="text-primary text-2xs uppercase tracking-wider block font-bold">What-If Plan</span>
                    
                    <div className="sim-status-row mb-2 mt-1">
                      <StatusIndicator status={results.what_if_plan.prob_success >= 85 ? 'highly_feasible' : (results.what_if_plan.prob_success >= 60 ? 'feasible' : (results.what_if_plan.prob_success >= 30 ? 'borderline' : 'unlikely'))} size="sm" />
                    </div>

                    <div className="stat-summary-rows-simple mt-2 d-flex flex-column gap-2">
                      <div className="row-val">
                        <span className="text-secondary text-2xs block d-flex align-items-center">
                          Success Probability
                          <InfoTooltip term="Success Probability" explanation="Success probability is an estimate of how likely the current plan is to reach your target under the assumptions used by InvestPlan. It is an estimate, not a guarantee." />
                        </span>
                        <span className={`font-bold text-sm ${results.what_if_plan.prob_success >= results.current_plan.prob_success ? 'text-success' : 'text-danger'}`}>
                          {results.what_if_plan.prob_success}%
                        </span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block">Median Final Corpus</span>
                        <span className="font-semibold text-sm text-primary">{formatINR(results.what_if_plan.median_corpus)}</span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block d-flex align-items-center">
                          Inflation-Adjusted Target
                          <InfoTooltip term="Inflation-Adjusted Target" explanation="The estimated future cost of your goal, calculated by increasing your current target amount by the expected inflation rate over time." />
                        </span>
                        <span className="font-semibold text-sm text-secondary">{formatINR(results.what_if_plan.adjusted_target)}</span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block">Shortfall Risk (%)</span>
                        <span className="font-semibold text-sm text-danger">{results.what_if_plan.prob_shortfall}%</span>
                      </div>
                      <div className="row-val">
                        <span className="text-secondary text-2xs block">Expected Shortfall</span>
                        <span className="font-semibold text-sm text-danger">{formatINR(results.what_if_plan.expected_shortfall)}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Stochastic Corpus Spread rendering */}
                <hr className="divider-dark my-4" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-secondary mb-2 d-flex align-items-center">
                  <TrendingUp size={14} className="me-1 text-primary" />
                  Stochastic Market Performance Spread
                </h4>
                <div className="market-spread-box p-3 rounded-lg bg-surface-dark-only border border-dark">
                  <div className="d-flex justify-content-between text-2xs text-secondary mb-1">
                    <span>Downside (10th Percentile Market)</span>
                    <span className="font-semibold text-danger">{formatINR(results.what_if_plan.downside_percentile_10)}</span>
                  </div>
                  <div className="d-flex justify-content-between text-xs text-primary mb-1 font-semibold">
                    <span>Median Path (50th Percentile Market)</span>
                    <span className="font-bold text-accent">{formatINR(results.what_if_plan.median_corpus)}</span>
                  </div>
                  <div className="d-flex justify-content-between text-2xs text-secondary">
                    <span>Upside (90th Percentile Market)</span>
                    <span className="font-semibold text-success">{formatINR(results.what_if_plan.upside_percentile_90)}</span>
                  </div>
                </div>

                <div className="alert alert-neutral bg-surface mt-3 text-xs text-secondary border border-dark rounded-lg p-2.5">
                  <p className="m-0 leading-relaxed">{results.what_if_plan.message}</p>
                </div>
              </div>
            ) : (
              <div className="sim-empty-state text-center p-4">
                <HelpCircle size={40} className="text-secondary mb-2" />
                <p className="text-secondary text-sm">Recalculating stochastics...</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
