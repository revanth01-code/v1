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
import { InfoTooltip } from '../components/common/InfoTooltip';
import { formatINR } from '../utils/currency';
import { getMinGoalDate } from '../utils/date';
import {
  AlertTriangle,
  AlertCircle,
  ArrowLeft,
  Check,
  Target,
  Shield,
  TrendingUp,
  Lightbulb,
} from 'lucide-react';
import type { GoalCheckResponse } from '../types/api';

const goalSchema = z
  .object({
    name: z
      .string()
      .min(1, 'Goal name is required')
      .max(200, 'Name must be less than 200 characters'),

    target_amount: z
      .number({ message: 'Target amount is required' })
      .gt(0, 'Target must be greater than 0'),

    target_date: z.string().min(1, 'Target date is required'),

    contribution_mode: z.enum(['sip', 'lumpsum', 'both']),

    monthly_contribution: z
      .number()
      .min(0, 'Contribution cannot be negative'),

    lumpsum_amount: z
      .number()
      .min(0, 'Lumpsum amount cannot be negative'),

    risk_level: z.enum(['low', 'mid', 'high']),
    
    goal_type: z.enum([
      'vacation',
      'house',
      'car',
      'education',
      'wedding',
      'retirement',
      'healthcare',
      'custom',
    ]),
    
    priority: z.enum(['low', 'medium', 'high']),
    
    deadline_flexibility: z.enum(['flexible', 'semi-flexible', 'inflexible']),
    
    importance: z.enum(['optional', 'important', 'mandatory']),
    
    inflation_scenario: z.enum(['conservative', 'expected', 'high']),
    
    inflation_rate_override: z
      .number()
      .min(0, 'Cannot be negative')
      .nullable()
      .optional(),
  })
  .refine(
    (data) => {
      if (
        data.contribution_mode === 'sip' &&
        data.monthly_contribution <= 0
      ) {
        return false;
      }

      return true;
    },
    {
      message:
        "Monthly contribution must be greater than 0 when mode is 'SIP'",
      path: ['monthly_contribution'],
    }
  )
  .refine(
    (data) => {
      if (
        data.contribution_mode === 'lumpsum' &&
        data.lumpsum_amount <= 0
      ) {
        return false;
      }

      return true;
    },
    {
      message:
        "Lumpsum amount must be greater than 0 when mode is 'Lumpsum'",
      path: ['lumpsum_amount'],
    }
  )
  .refine(
    (data) => {
      if (
        data.contribution_mode === 'both' &&
        data.monthly_contribution <= 0 &&
        data.lumpsum_amount <= 0
      ) {
        return false;
      }

      return true;
    },
    {
      message:
        'At least one of monthly contribution or lumpsum must be greater than 0',
      path: ['monthly_contribution'],
    }
  );

type GoalFormData = z.infer<typeof goalSchema>;

export const GoalCreateEdit: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [simulationResult, setSimulationResult] =
    useState<GoalCheckResponse | null>(null);

  const [checking, setChecking] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [feasibilityError, setFeasibilityError] =
    useState<any | null>(null);

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
      target_date: new Date(
        Date.now() + 5 * 365 * 24 * 60 * 60 * 1000
      )
        .toISOString()
        .split('T')[0],
      contribution_mode: 'sip',
      monthly_contribution: 15000,
      lumpsum_amount: 0,
      risk_level: 'mid',
      goal_type: 'custom',
      priority: 'medium',
      deadline_flexibility: 'flexible',
      importance: 'important',
      inflation_scenario: 'expected',
      inflation_rate_override: null,
    },
  });

  const formValues = watch();

  // Run simulation query when inputs change
  useEffect(() => {
    if (
      !formValues.name ||
      formValues.target_amount <= 0 ||
      !formValues.target_date
    )
      return;

    if (
      formValues.contribution_mode === 'sip' &&
      formValues.monthly_contribution <= 0
    )
      return;

    if (
      formValues.contribution_mode === 'lumpsum' &&
      formValues.lumpsum_amount <= 0
    )
      return;

    if (
      formValues.contribution_mode === 'both' &&
      formValues.monthly_contribution <= 0 &&
      formValues.lumpsum_amount <= 0
    )
      return;

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
          goal_type: formValues.goal_type,
          priority: formValues.priority,
          deadline_flexibility: formValues.deadline_flexibility,
          importance: formValues.importance,
          inflation_scenario: formValues.inflation_scenario,
          inflation_rate_override: formValues.inflation_rate_override || null,
        };

        const result = await goalsService.checkGoal(payload);
        setSimulationResult(result);
      } catch (err) {
        // Ignore simulator errors quietly
      } finally {
        setChecking(false);
      }
    }, 400);

    return () => clearTimeout(delayDebounce);
  }, [
    formValues.name,
    formValues.target_amount,
    formValues.target_date,
    formValues.contribution_mode,
    formValues.monthly_contribution,
    formValues.lumpsum_amount,
    formValues.risk_level,
    formValues.goal_type,
    formValues.priority,
    formValues.deadline_flexibility,
    formValues.importance,
    formValues.inflation_scenario,
    formValues.inflation_rate_override,
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

    // Make sure nullable fields are correctly clean
    const cleaned = {
      ...data,
      inflation_rate_override: data.inflation_rate_override || null,
    };

    saveMutation.mutate(cleaned);
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
        <button
          onClick={() => navigate('/goals')}
          className="btn btn-ghost btn-sm btn-with-icon pl-0"
        >
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
                label={
                  <>
                    Goal Name
                    <InfoTooltip term="Goal Name" explanation="Give your goal a name so you can easily identify it later." />
                  </>
                }
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
                  render={({ field }) => {
                    const [inputValue, setInputValue] = React.useState(
                      field.value !== undefined && field.value !== null
                        ? field.value.toLocaleString('en-IN')
                        : ''
                    );

                    React.useEffect(() => {
                      setInputValue(
                        field.value !== undefined && field.value !== null
                          ? field.value.toLocaleString('en-IN')
                          : ''
                      );
                    }, [field.value]);

                    const handleChange = (
                      e: React.ChangeEvent<HTMLInputElement>
                    ) => {
                      const rawValue = e.target.value
                        .replace(/,/g, '')
                        .replace(/[^\d]/g, '');

                      setInputValue(
                        rawValue
                          ? Number(rawValue).toLocaleString('en-IN')
                          : ''
                      );

                      if (rawValue === '') {
                        field.onChange(0);
                      } else {
                        field.onChange(Number(rawValue));
                      }
                    };

                    const isInvalid =
                      field.value < 5000 || field.value > 10000000;

                    return (
                      <div className="form-group">
                        <label className="form-label">
                          Target Amount
                          <InfoTooltip term="Target Amount" explanation="The total amount of money you need to achieve this goal." />
                        </label>

                        <div className="currency-input-wrapper">
                          <span className="currency-symbol">₹</span>
                          <input
                            type="text"
                            inputMode="numeric"
                            className="form-control"
                            value={inputValue}
                            onChange={handleChange}
                          />
                        </div>

                        <div className="d-flex justify-content-between text-secondary text-xs mt-1">
                          <span>Min ₹5,000</span>
                          <span>Max ₹1,00,00,000</span>
                        </div>

                        {isInvalid && (
                          <div className="text-danger text-xs mt-1">
                            {field.value < 5000
                              ? 'Target amount must be at least ₹5,000'
                              : 'Target amount cannot exceed ₹1,00,00,000'}
                          </div>
                        )}

                        {errors.target_amount?.message && (
                          <div className="text-danger text-xs mt-1">
                            {errors.target_amount.message}
                          </div>
                        )}
                      </div>
                    );
                  }}
                />

                <InputField
                  label={
                    <>
                      Target Date
                      <InfoTooltip term="Target Date" explanation="The date by which you want to have enough money for this goal." />
                    </>
                  }
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
                    <InfoTooltip term="Risk Level" explanation="Risk level describes how much investment value may fluctuate. Lower-risk strategies usually have smaller fluctuations but may offer lower expected returns. Higher-risk strategies can fluctuate more in exchange for potentially higher returns." />
                  </label>

                  <select
                    id="risk_level"
                    className="form-control"
                    {...register('risk_level')}
                  >
                    <option value="low">
                      Low (7% returns - Debt heavy)
                    </option>
                    <option value="mid">
                      Mid (10% returns - Balance mix)
                    </option>
                    <option value="high">
                      High (13% returns - Equity heavy)
                    </option>
                  </select>
                </div>

                <div className="form-group">
                  <label
                    htmlFor="contribution_mode"
                    className="form-label"
                  >
                    How will you fund this?
                    <InfoTooltip term="How will you fund this?" explanation="Choose how you plan to save: monthly installments (SIP), a one-time lumpsum, or both." />
                  </label>

                  <select
                    id="contribution_mode"
                    className="form-control"
                    {...register('contribution_mode')}
                  >
                    <option value="sip">Monthly SIP</option>
                    <option value="lumpsum">
                      One-time Lumpsum
                    </option>
                    <option value="both">
                      Both (SIP + Lumpsum)
                    </option>
                  </select>
                </div>
              </div>

              <div className="form-row-2 mt-2">
                {formValues.contribution_mode !== 'lumpsum' && (
                  <Controller
                    name="monthly_contribution"
                    control={control}
                    render={({ field }) => {
                      const [inputValue, setInputValue] =
                        React.useState(
                          field.value !== undefined &&
                            field.value !== null
                            ? field.value.toLocaleString('en-IN')
                            : ''
                        );

                      React.useEffect(() => {
                        setInputValue(
                          field.value !== undefined &&
                            field.value !== null
                            ? field.value.toLocaleString('en-IN')
                            : ''
                        );
                      }, [field.value]);

                      const handleChange = (
                        e: React.ChangeEvent<HTMLInputElement>
                      ) => {
                        const rawValue = e.target.value
                          .replace(/,/g, '')
                          .replace(/[^\d]/g, '');

                        setInputValue(
                          rawValue
                            ? Number(rawValue).toLocaleString('en-IN')
                            : ''
                        );

                        if (rawValue === '') {
                          field.onChange(0);
                        } else {
                          field.onChange(Number(rawValue));
                        }
                      };

                      const isInvalid =
                        field.value < 0 ||
                        field.value > 10000000;

                      return (
                        <div className="form-group">
                          <label className="form-label">
                            Monthly Contribution
                            <InfoTooltip term="Monthly Contribution" explanation="The amount you plan to invest every month towards this goal." />
                          </label>

                          <div className="currency-input-wrapper">
                            <span className="currency-symbol">₹</span>
                            <input
                              type="text"
                              inputMode="numeric"
                              className="form-control"
                              value={inputValue}
                              onChange={handleChange}
                            />
                          </div>

                          <div className="d-flex justify-content-between text-secondary text-xs mt-1">
                            <span>Min ₹0</span>
                            <span>Max ₹1,00,00,000</span>
                          </div>

                          {isInvalid && (
                            <div className="text-danger text-xs mt-1">
                              Monthly contribution cannot exceed
                              ₹1,00,00,000
                            </div>
                          )}

                          {errors.monthly_contribution?.message && (
                            <div className="text-danger text-xs mt-1">
                              {errors.monthly_contribution.message}
                            </div>
                          )}
                        </div>
                      );
                    }}
                  />
                )}

                {formValues.contribution_mode !== 'sip' && (
                  <Controller
                    name="lumpsum_amount"
                    control={control}
                    render={({ field }) => (
                      <SliderField
                        label={
                          <>
                            Lumpsum Amount (₹)
                            <InfoTooltip term="Lumpsum Amount" explanation="A one-time initial investment you can make right now towards this goal." />
                          </>
                        }
                        min={0}
                        max={10000000}
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

              <hr className="divider-dark my-4" />
              <h4 className="section-title mb-3 d-flex align-items-center">
                <Shield size={16} className="me-2 text-primary" />
                Goal Intelligence Settings
              </h4>

              <div className="form-row-2">
                <div className="form-group">
                  <label htmlFor="goal_type" className="form-label">
                    Goal Category
                    <InfoTooltip term="Goal Category" explanation="Categorizing your goal helps us apply the right default inflation rate (e.g., education costs rise faster than general items)." />
                  </label>
                  <select id="goal_type" className="form-control" {...register('goal_type')}>
                    <option value="custom">Custom (6% base inflation)</option>
                    <option value="education">Education (8% base inflation)</option>
                    <option value="house">Real Estate / House (6% base inflation)</option>
                    <option value="healthcare">Healthcare (8% base inflation)</option>
                    <option value="wedding">Wedding (7% base inflation)</option>
                    <option value="car">Vehicle / Car (5% base inflation)</option>
                    <option value="retirement">Retirement (6% base inflation)</option>
                    <option value="vacation">Vacation / Travel (7% base inflation)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="priority" className="form-label">
                    Goal Priority
                    <InfoTooltip term="Goal Priority" explanation="Tells FinPilot which goals are most important. If your available funds are limited, higher priority goals will receive funding first." />
                  </label>
                  <select id="priority" className="form-control" {...register('priority')}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
              </div>

              <div className="form-row-2 mt-2">
                <div className="form-group">
                  <label htmlFor="deadline_flexibility" className="form-label">
                    Deadline Flexibility
                    <InfoTooltip term="Deadline Flexibility" explanation="How strict your target date is. Flexible goals have a higher chance of success as they can wait for markets to recover." />
                  </label>
                  <select id="deadline_flexibility" className="form-control" {...register('deadline_flexibility')}>
                    <option value="flexible">Flexible (+/- 12 months)</option>
                    <option value="semi-flexible">Semi-Flexible (+/- 6 months)</option>
                    <option value="inflexible">Inflexible (Fixed Target Date)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="importance" className="form-label">
                    Goal Importance
                    <InfoTooltip term="Goal Importance" explanation="Tells us how critical this goal is, so we can prioritize it in your overall financial plan." />
                  </label>
                  <select id="importance" className="form-control" {...register('importance')}>
                    <option value="optional">Optional / Luxury</option>
                    <option value="important">Important / Standard</option>
                    <option value="mandatory">Mandatory / Critical</option>
                  </select>
                </div>
              </div>

              <div className="form-row-2 mt-2">
                <div className="form-group">
                  <label htmlFor="inflation_scenario" className="form-label">
                    Inflation Scenario
                    <InfoTooltip term="Inflation Scenario" explanation="Different goals experience different inflation. Education costs often rise faster than general inflation. We adjust the base rate based on the scenario." />
                  </label>
                  <select id="inflation_scenario" className="form-control" {...register('inflation_scenario')}>
                    <option value="expected">Expected Scenario (Base)</option>
                    <option value="conservative">Conservative Scenario (Base - 2%)</option>
                    <option value="high">High Inflation Scenario (Base + 2%)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="inflation_rate_override" className="form-label">
                    Inflation Override (% p.a.)
                    <InfoTooltip term="Inflation Override" explanation="Use a specific percentage if you know exactly how fast the cost of your goal will rise." />
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    id="inflation_rate_override"
                    placeholder="Leave empty to use scenario defaults"
                    className="form-control"
                    {...register('inflation_rate_override', { valueAsNumber: true })}
                  />
                  {errors.inflation_rate_override?.message && (
                    <p className="form-error-text mt-1">{errors.inflation_rate_override.message}</p>
                  )}
                </div>
              </div>

              {serverError && (
                <div className="alert alert-danger mt-3">
                  <AlertCircle size={16} className="me-2" />
                  <span>{serverError}</span>
                </div>
              )}

              {feasibilityError && (
                <div className="suggestions-container mt-3 card p-3 border-danger-subtle bg-danger-subtle">
                  <h4 className="text-danger d-flex align-items-center text-sm font-semibold">
                    <AlertTriangle size={16} className="me-2" />
                    How to fix your plan (Capacity Recommendations):
                  </h4>
                  <p className="text-secondary text-xs mt-1">
                    Your current monthly SIP of {formatINR(formValues.monthly_contribution)} fails to meet the target cost.
                  </p>

                  <div className="suggestion-action-rows mt-2">
                    {feasibilityError.suggested_monthly_sip && (
                      <div className="suggestion-row d-flex justify-content-between align-items-center bg-surface-dark-subtle p-2 rounded">
                        <p className="m-0 text-xs text-secondary">
                          Increase monthly contribution to:{' '}
                          <strong className="text-primary text-sm font-bold block mt-1">
                            {formatINR(feasibilityError.suggested_monthly_sip)}
                          </strong>
                          <span className="text-secondary text-2xs block mt-1">
                            Difference: +{formatINR(feasibilityError.contribution_difference || 0)} / mo
                          </span>
                        </p>

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
                      <div className="suggestion-row mt-2 d-flex justify-content-between align-items-center bg-surface-dark-subtle p-2 rounded">
                        <p className="m-0 text-xs text-secondary">
                          Extend timeline to{' '}
                          <strong className="text-primary text-sm font-bold block mt-1">
                            {feasibilityError.suggested_extended_months} months
                          </strong>
                        </p>

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
                <Button
                  type="submit"
                  variant="primary"
                  className="w-100 font-semibold"
                  isLoading={saveMutation.isPending}
                >
                  Save & Lock Goal
                </Button>
              </div>
            </form>
          </Card>
        </div>

        {/* Right Side: Projections Preview */}
        <div className="projections-panel">
          <Card
            title="Interactive Simulation Preview"
            className="bg-surface-dark-subtle border-none"
          >
            {checking && (
              <div className="checking-overlay">
                <span className="spinner-border spinner-border-sm me-2" />
                <span>Simulating...</span>
              </div>
            )}

            {simulationResult ? (
              <div className="simulation-details">
                <div className="sim-status-row mb-3">
                  <span className="text-secondary text-sm">
                    Feasibility Status
                  </span>

                  <StatusIndicator
                    status={simulationResult.feasibility.status}
                  />
                </div>

                <div className="detail-rows">
                  <div className="detail-row">
                    <span className="text-secondary">Assumed annual return</span>
                    <span className="font-semibold text-primary">
                      {formValues.risk_level === 'low'
                        ? '7.0%'
                        : formValues.risk_level === 'mid'
                          ? '10.0%'
                          : '13.0%'}{' '}
                      p.a.
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="text-secondary">Duration</span>
                    <span className="font-semibold text-primary">
                      {simulationResult.feasibility.months} months
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="text-secondary font-semibold">Target Cost (Current)</span>
                    <span className="font-semibold text-secondary">
                      {formatINR(formValues.target_amount)}
                    </span>
                  </div>

                  <div className="detail-row border-primary-dark pt-2 mt-2">
                    <span className="text-primary font-bold">
                      Inflation-Adjusted Target
                      <InfoTooltip term="Inflation-Adjusted Target" explanation="The estimated future cost of your goal, calculated by increasing your current target amount by the expected inflation rate over time." />
                    </span>
                    <span className="font-bold text-primary">
                      {formatINR(simulationResult.feasibility.inflation_adjusted_target)}
                    </span>
                  </div>

                  <div className="detail-row bg-surface-dark-only p-2 rounded-lg mt-1 mb-2">
                    <span className="text-secondary text-xs">Inflation Impact (Currency)</span>
                    <span className="font-semibold text-danger text-xs">
                      +{formatINR(simulationResult.feasibility.inflation_adjusted_target - formValues.target_amount)}
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="text-secondary">Projected value</span>
                    <span className="font-semibold text-accent">
                      {formatINR(simulationResult.feasibility.projected_value)}
                    </span>
                  </div>
                </div>

                {/* Guardrail warn messages */}
                {!simulationResult.guardrail.allowed &&
                  simulationResult.guardrail.warning && (
                    <div className="alert alert-warning mt-3 bg-warning-subtle text-warning">
                      <AlertTriangle
                        size={16}
                        className="me-2 flex-shrink-0"
                      />
                      <p className="text-xs m-0">
                        {simulationResult.guardrail.warning}
                      </p>
                    </div>
                  )}

                {/* Feasibility Alert Message */}
                {['unlikely', 'at_risk'].includes(simulationResult.feasibility.status) && (
                  <div className="shortfall-info mt-3 alert alert-danger bg-danger-subtle border-danger-subtle">
                    <div className="d-flex align-items-center">
                      <AlertCircle size={16} className="me-2 flex-shrink-0" />
                      <p className="text-sm m-0 font-semibold">
                        Funding Gap:{' '}
                        <strong>
                          {formatINR(simulationResult.feasibility.shortfall || 0)}
                        </strong>
                      </p>
                    </div>
                    {simulationResult.feasibility.message && (
                      <p className="text-xs mt-2 m-0 text-secondary">
                        {simulationResult.feasibility.message}
                      </p>
                    )}
                  </div>
                )}

                {simulationResult.feasibility.status === 'borderline' && (
                  <div className="shortfall-info mt-3 alert alert-warning bg-warning-subtle border-warning-subtle">
                    <div className="d-flex align-items-center">
                      <AlertCircle size={16} className="me-2 flex-shrink-0 text-warning" />
                      <p className="text-sm m-0 text-warning font-semibold">
                        Funding Gap: {formatINR(simulationResult.feasibility.shortfall || 0)}
                      </p>
                    </div>
                    <p className="text-xs text-secondary mt-2 m-0">
                      {simulationResult.feasibility.message}
                    </p>
                  </div>
                )}

                {/* SIP Suggestion Block — shown when plan is infeasible */}
                {['unlikely', 'at_risk', 'borderline'].includes(simulationResult.feasibility.status) &&
                  simulationResult.feasibility.suggested_monthly_sip &&
                  formValues.contribution_mode !== 'lumpsum' && (
                    <div className="sip-suggestion-card mt-3 p-3 rounded-lg" style={{
                      background: 'linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(139,92,246,0.08) 100%)',
                      border: '1px solid rgba(99,102,241,0.35)',
                    }}>
                      <div className="d-flex align-items-center mb-2" style={{ gap: '8px' }}>
                        <span style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          width: 28, height: 28, borderRadius: '50%',
                          background: 'rgba(99,102,241,0.18)',
                          flexShrink: 0,
                        }}>
                          <Lightbulb size={14} style={{ color: '#818cf8' }} />
                        </span>
                        <span className="text-xs font-bold" style={{ color: '#818cf8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                          SIP Suggestion to Make Plan Feasible
                        </span>
                      </div>

                      <p className="text-xs m-0 mb-2" style={{ color: 'var(--text-secondary, #94a3b8)', lineHeight: 1.6 }}>
                        Your current monthly SIP of{' '}
                        <strong style={{ color: 'var(--text-primary, #e2e8f0)' }}>
                          {formatINR(formValues.monthly_contribution)}
                        </strong>{' '}
                        is not enough to reach your goal by the target date. If you increase it to:
                      </p>

                      <div className="d-flex align-items-center justify-content-between p-2 rounded mb-2" style={{
                        background: 'rgba(99,102,241,0.15)',
                        border: '1px solid rgba(99,102,241,0.25)',
                      }}>
                        <div className="d-flex align-items-center" style={{ gap: '8px' }}>
                          <TrendingUp size={16} style={{ color: '#34d399', flexShrink: 0 }} />
                          <div>
                            <div className="font-bold" style={{ color: '#34d399', fontSize: '1.1rem' }}>
                              {formatINR(simulationResult.feasibility.suggested_monthly_sip)}
                            </div>
                            <div className="text-2xs" style={{ color: 'var(--text-secondary, #94a3b8)' }}>
                              +{formatINR(
                                simulationResult.feasibility.suggested_monthly_sip -
                                formValues.monthly_contribution
                              )}{' '}
                              more per month
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => applySIPSuggestion(simulationResult.feasibility.suggested_monthly_sip!)}
                          className="btn btn-sm"
                          style={{
                            background: 'rgba(99,102,241,0.25)',
                            border: '1px solid rgba(99,102,241,0.5)',
                            color: '#818cf8',
                            fontWeight: 600,
                            fontSize: '0.75rem',
                            padding: '4px 12px',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            whiteSpace: 'nowrap',
                          }}
                          onMouseEnter={e => {
                            (e.currentTarget as HTMLButtonElement).style.background = 'rgba(99,102,241,0.45)';
                            (e.currentTarget as HTMLButtonElement).style.color = '#e0e7ff';
                          }}
                          onMouseLeave={e => {
                            (e.currentTarget as HTMLButtonElement).style.background = 'rgba(99,102,241,0.25)';
                            (e.currentTarget as HTMLButtonElement).style.color = '#818cf8';
                          }}
                        >
                          Apply this SIP
                        </button>
                      </div>

                      <p className="text-2xs m-0" style={{ color: 'var(--text-secondary, #64748b)', lineHeight: 1.5 }}>
                        💡 Applying this amount will update your monthly contribution and re-run the simulation automatically.
                      </p>
                    </div>
                  )}

                {['feasible', 'highly_feasible'].includes(simulationResult.feasibility.status) && (
                  <div className="alert alert-success mt-3 bg-success-subtle text-success d-flex align-items-center">
                    <Check size={16} className="me-2" />
                    <span className="text-xs font-semibold">
                      {simulationResult.feasibility.message || 'Your plan covers the inflation-adjusted target cost! Ready to lock.'}
                    </span>
                  </div>
                )}

                {/* Risk Engine Strategy Options rendering */}
                {simulationResult.strategies && (
                  <div className="strategies-preview mt-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-secondary mb-2 d-flex align-items-center">
                      <Shield size={14} className="me-1 text-primary" />
                      Risk Engine Strategy Projections
                    </h4>
                    <div className="strategy-cards d-flex flex-column gap-2">
                      {Object.entries(simulationResult.strategies).map(([name, s]: [string, any]) => {
                        const isCurrentSelected = name === (
                          formValues.risk_level === 'low' ? 'conservative' : (
                            formValues.risk_level === 'mid' ? 'moderate' : 'aggressive'
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
                  </div>
                )}
              </div>
            ) : (
              <div className="sim-empty-state text-center p-4">
                <Target size={40} className="text-secondary mb-2" />
                <p className="text-secondary text-sm">
                  Fill in a goal name and target parameters to generate live projections.
                </p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};