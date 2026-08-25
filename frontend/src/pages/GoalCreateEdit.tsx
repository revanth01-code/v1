/* frontend/src/pages/GoalCreateEdit.tsx */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { goalsService } from '../services/goalsService';
import { Card } from '../components/common/Card';
import { InputField } from '../components/common/InputField';
import { SliderField } from '../components/common/SliderField';
import { Button } from '../components/common/Button';
import { StatusIndicator } from '../components/common/StatusIndicator';
import { formatINR } from '../utils/currency';
import { getMinGoalDate } from '../utils/date';
import { AlertTriangle, AlertCircle, ArrowLeft, Check, Target } from 'lucide-react';
import type { GoalCheckResponse } from '../types/api';

const goalSchema = z.object({
  name: z.string().min(1, 'Goal name is required').max(200, 'Name must be less than 200 characters'),
  target_amount: z.number({ message: 'Target amount is required' }).gt(0, 'Target must be greater than 0'),
  target_date: z.string().min(1, 'Target date is required'),
  contribution_mode: z.enum(['sip', 'lumpsum', 'both']),
  monthly_contribution: z.number().min(0, 'Contribution cannot be negative'),
  lumpsum_amount: z.number().min(0, 'Lumpsum amount cannot be negative'),
  risk_level: z.enum(['low', 'mid', 'high']),
}).refine((data) => {
  if (data.contribution_mode === 'sip' && data.monthly_contribution <= 0) {
    return false;
  }
  return true;
}, {
  message: "Monthly contribution must be greater than 0 when mode is 'SIP'",
  path: ["monthly_contribution"],
}).refine((data) => {
  if (data.contribution_mode === 'lumpsum' && data.lumpsum_amount <= 0) {
    return false;
  }
  return true;
}, {
  message: "Lumpsum amount must be greater than 0 when mode is 'Lumpsum'",
  path: ["lumpsum_amount"],
}).refine((data) => {
  if (data.contribution_mode === 'both' && data.monthly_contribution <= 0 && data.lumpsum_amount <= 0) {
    return false;
  }
  return true;
}, {
  message: "At least one of monthly contribution or lumpsum must be greater than 0",
  path: ["monthly_contribution"],
});

type GoalFormData = z.infer<typeof goalSchema>;

export const GoalCreateEdit: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [simulationResult, setSimulationResult] = useState<GoalCheckResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [feasibilityError, setFeasibilityError] = useState<any | null>(null);

  const {
    register,
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<GoalFormData>({
    resolver: zodResolver(goalSchema),
    defaultValues: {
      name: '',
      target_amount: 1000000,
      target_date: new Date(Date.now() + 5 * 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 5 years out
      contribution_mode: 'sip',
      monthly_contribution: 15000,
      lumpsum_amount: 0,
      risk_level: 'mid',
    },
  });

  const formValues = watch();

  // Run simulation query when inputs change
  useEffect(() => {
    // Validate basics before querying simulator to avoid spamming network errors
    if (!formValues.name || formValues.target_amount <= 0 || !formValues.target_date) return;
    if (formValues.contribution_mode === 'sip' && formValues.monthly_contribution <= 0) return;
    if (formValues.contribution_mode === 'lumpsum' && formValues.lumpsum_amount <= 0) return;
    if (formValues.contribution_mode === 'both' && formValues.monthly_contribution <= 0 && formValues.lumpsum_amount <= 0) return;

    const delayDebounce = setTimeout(async () => {
      setChecking(true);
      try {
        const payload = {
          name: formValues.name,
          target_amount: formValues.target_amount,
          target_date: formValues.target_date,
          contribution_mode: formValues.contribution_mode,
          monthly_contribution: formValues.monthly_contribution,
          lumpsum_amount: formValues.lumpsum_amount,
          risk_level: formValues.risk_level,
        };
        const result = await goalsService.checkGoal(payload);
        setSimulationResult(result);
      } catch (err) {
        // Ignore simulator errors quietly
      } finally {
        setChecking(false);
      }
    }, 400); // Debounce inputs

    return () => clearTimeout(delayDebounce);
  }, [
    formValues.name,
    formValues.target_amount,
    formValues.target_date,
    formValues.contribution_mode,
    formValues.monthly_contribution,
    formValues.lumpsum_amount,
    formValues.risk_level,
  ]);

  const saveMutation = useMutation({
    mutationFn: (data: GoalFormData) => goalsService.createGoal(data),
    onSuccess: (newGoal) => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      navigate(`/goals/${newGoal.id}`);
    },
    onError: (err: any) => {
      if (err.status === 422 && err.feasibility) {
        // Goal infeasible error carried inside custom layout
        setFeasibilityError(err.feasibility);
        setServerError(err.message);
      } else {
        setServerError(err.message || 'Failed to create goal.');
      }
    },
  });

  const onSubmit = (data: GoalFormData) => {
    setServerError(null);
    setFeasibilityError(null);
    saveMutation.mutate(data);
  };

  const applySIPSuggestion = (amount: number) => {
    setValue('monthly_contribution', amount);
  };

  const applyExtendedDateSuggestion = (months: number) => {
    const today = new Date();
    today.setMonth(today.getMonth() + months);
    const dateStr = today.toISOString().split('T')[0];
    setValue('target_date', dateStr);
  };

  return (
    <div className="goal-create-page">
      <div className="mb-4">
        <button onClick={() => navigate('/goals')} className="btn btn-ghost btn-sm btn-with-icon pl-0">
          <ArrowLeft size={16} />
          <span>Back to Goals</span>
        </button>
      </div>

      <div className="goal-creator-grid">
        {/* Left Side: Parameters Form */}
        <div className="form-card-panel">
          <Card title="Goal Planner & Calculator">
            <form onSubmit={handleSubmit(onSubmit)}>
              <InputField
                label="Goal Name"
                type="text"
                id="name"
                placeholder="e.g. Dream House Downpayment"
                error={errors.name?.message}
                {...register('name')}
              />

              <div className="form-row-2">
                <Controller
                  name="target_amount"
                  control={control}
                  render={({ field }) => (
                    <SliderField
                      label="Target Amount"
                      min={50000}
                      max={100000000}
                      step={50000}
                      value={field.value}
                      onChange={field.onChange}
                      formatValue={formatINR}
                      error={errors.target_amount?.message}
                    />
                  )}
                />

                <InputField
                  label="Target Date"
                  type="date"
                  id="target_date"
                  min={getMinGoalDate()}
                  error={errors.target_date?.message}
                  {...register('target_date')}
                />
              </div>

              <div className="form-row-2">
                <div className="form-group">
                  <label htmlFor="risk_level" className="form-label">
                    Risk Level
                  </label>
                  <select
                    id="risk_level"
                    className="form-control"
                    {...register('risk_level')}
                  >
                    <option value="low">Low (7% returns - Debt heavy)</option>
                    <option value="mid">Mid (10% returns - Balance mix)</option>
                    <option value="high">High (13% returns - Equity heavy)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="contribution_mode" className="form-label">
                    How will you fund this?
                  </label>
                  <select
                    id="contribution_mode"
                    className="form-control"
                    {...register('contribution_mode')}
                  >
                    <option value="sip">Monthly SIP</option>
                    <option value="lumpsum">One-time Lumpsum</option>
                    <option value="both">Both (SIP + Lumpsum)</option>
                  </select>
                </div>
              </div>

              {/* Dynamic inputs based on mode */}
              <div className="form-row-2 mt-2">
                {formValues.contribution_mode !== 'lumpsum' && (
                  <Controller
                    name="monthly_contribution"
                    control={control}
                    render={({ field }) => (
                      <SliderField
                        label="Monthly Contribution (₹)"
                        min={0}
                        max={1000000}
                        step={1000}
                        value={field.value}
                        onChange={field.onChange}
                        formatValue={formatINR}
                        error={errors.monthly_contribution?.message}
                      />
                    )}
                  />
                )}

                {formValues.contribution_mode !== 'sip' && (
                  <Controller
                    name="lumpsum_amount"
                    control={control}
                    render={({ field }) => (
                      <SliderField
                        label="Lumpsum Amount (₹)"
                        min={0}
                        max={50000000}
                        step={10000}
                        value={field.value}
                        onChange={field.onChange}
                        formatValue={formatINR}
                        error={errors.lumpsum_amount?.message}
                      />
                    )}
                  />
                )}
              </div>

              {serverError && (
                <div className="alert alert-danger mt-3">
                  <AlertCircle size={16} className="me-2" />
                  <span>{serverError}</span>
                </div>
              )}

              {feasibilityError && (
                <div className="suggestions-container mt-3 card p-3 border-danger-subtle bg-danger-subtle">
                  <h4 className="text-danger d-flex align-items-center">
                    <AlertTriangle size={16} className="me-2" />
                    How to fix your plan:
                  </h4>
                  <div className="suggestion-action-rows mt-2">
                    {feasibilityError.suggested_monthly_sip && (
                      <div className="suggestion-row">
                        <p>Increase monthly contribution to: <strong>{formatINR(feasibilityError.suggested_monthly_sip)}</strong></p>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => applySIPSuggestion(feasibilityError.suggested_monthly_sip)}
                        >
                          Apply suggestion
                        </button>
                      </div>
                    )}
                    {feasibilityError.suggested_extended_months && (
                      <div className="suggestion-row mt-2">
                        <p>Extend timeline to <strong>{feasibilityError.suggested_extended_months} months</strong></p>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => applyExtendedDateSuggestion(feasibilityError.suggested_extended_months)}
                        >
                          Apply suggestion
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="form-actions mt-4">
                <Button type="submit" variant="primary" className="w-100" isLoading={saveMutation.isPending}>
                  Save & Lock Goal
                </Button>
              </div>
            </form>
          </Card>
        </div>

        {/* Right Side: Projections Preview */}
        <div className="projections-panel">
          <Card title="Interactive Simulation Preview" className="bg-surface-dark-subtle border-none">
            {checking && (
              <div className="checking-overlay">
                <span className="spinner-border spinner-border-sm me-2" />
                <span>Simulating...</span>
              </div>
            )}

            {simulationResult ? (
              <div className="simulation-details">
                <div className="sim-status-row mb-3">
                  <span className="text-secondary text-sm">Feasibility Status</span>
                  <StatusIndicator status={simulationResult.feasibility.status} />
                </div>

                <div className="detail-rows">
                  <div className="detail-row">
                    <span className="text-secondary">Assumed annual return</span>
                    <span className="font-semibold text-primary">
                      {formValues.risk_level === 'low' ? '7.0%' : formValues.risk_level === 'mid' ? '10.0%' : '13.0%'} p.a.
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="text-secondary">Duration</span>
                    <span className="font-semibold text-primary">{simulationResult.feasibility.months} months</span>
                  </div>

                  <div className="detail-row">
                    <span className="text-secondary">Target inflated cost</span>
                    <span className="font-semibold text-primary">
                      {formatINR(simulationResult.feasibility.inflation_adjusted_target)}
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="text-secondary">Projected value</span>
                    <span className="font-semibold text-primary text-accent">
                      {formatINR(simulationResult.feasibility.projected_value)}
                    </span>
                  </div>
                </div>

                {/* Guardrail warn messages */}
                {!simulationResult.guardrail.allowed && simulationResult.guardrail.warning && (
                  <div className="alert alert-warning mt-3 bg-warning-subtle text-warning">
                    <AlertTriangle size={16} className="me-2 flex-shrink-0" />
                    <p className="text-xs m-0">{simulationResult.guardrail.warning}</p>
                  </div>
                )}

                {simulationResult.feasibility.status === 'infeasible' && (
                  <div className="shortfall-info mt-3 text-danger">
                    <p className="text-sm m-0">
                      Shortfall: <strong>{formatINR(simulationResult.feasibility.shortfall || 0)}</strong>
                    </p>
                    {simulationResult.feasibility.message && (
                      <p className="text-xs text-secondary mt-1">{simulationResult.feasibility.message}</p>
                    )}
                  </div>
                )}
                
                {simulationResult.feasibility.status === 'borderline' && (
                  <div className="shortfall-info mt-3 text-warning">
                    <p className="text-xs text-secondary m-0">{simulationResult.feasibility.message}</p>
                  </div>
                )}

                {simulationResult.feasibility.status === 'feasible' && (
                  <div className="alert alert-success mt-3 bg-success-subtle text-success d-flex align-items-center">
                    <Check size={16} className="me-2" />
                    <span className="text-xs">Your plan covers the inflation adjusted target! Ready to save.</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="sim-empty-state text-center p-4">
                <Target size={40} className="text-secondary mb-2" />
                <p className="text-secondary text-sm">Fill in a goal name and target parameters to generate live projections.</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
