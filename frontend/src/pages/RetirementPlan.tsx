/* frontend/src/pages/RetirementPlan.tsx */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { retirementService } from '../services/retirementService';
import { Card } from '../components/common/Card';
import { InputField } from '../components/common/InputField';
import { Button } from '../components/common/Button';
import { StatusIndicator } from '../components/common/StatusIndicator';
import { formatINR } from '../utils/currency';
import { Hourglass, CheckCircle2, Info } from 'lucide-react';

const retirementSchema = z.object({
  current_age: z.number().int().min(18, 'Must be at least 18').max(100, 'Max 100'),
  retirement_age: z.number().int().min(18, 'Must be at least 18').max(100, 'Max 100'),
  life_expectancy: z.number().int().min(1, 'Must be at least 1').max(120, 'Max 120'),
  existing_retirement_corpus: z.number().min(0, 'Cannot be negative'),
  planned_monthly_contribution: z.number().min(0, 'Cannot be negative'),
  inflation_pct: z.number().min(0, 'Cannot be negative'),
  pre_retirement_return_pct: z.number().min(0, 'Cannot be negative'),
  post_retirement_return_pct: z.number().min(0, 'Cannot be negative'),
}).refine((data) => data.retirement_age > data.current_age, {
  message: "Retirement age must be greater than current age",
  path: ["retirement_age"],
}).refine((data) => data.life_expectancy > data.retirement_age, {
  message: "Life expectancy must be greater than retirement age",
  path: ["life_expectancy"],
});

type RetirementFormData = z.infer<typeof retirementSchema>;

export const RetirementPlan: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const { data: plan, isLoading, error } = useQuery({
    queryKey: ['retirementPlan'],
    queryFn: () => retirementService.getPlan(),
    retry: false,
  });

  const isNew = error && (error as any).status === 404;
  const isProfileMissing = error && (error as any).status === 422;

  const { register, handleSubmit, formState: { errors } } = useForm<RetirementFormData>({
    resolver: zodResolver(retirementSchema),
    values: plan ? {
      current_age: plan.current_age,
      retirement_age: plan.retirement_age,
      life_expectancy: plan.life_expectancy,
      existing_retirement_corpus: plan.existing_retirement_corpus,
      planned_monthly_contribution: plan.planned_monthly_contribution,
      inflation_pct: plan.inflation_pct,
      pre_retirement_return_pct: plan.pre_retirement_return_pct,
      post_retirement_return_pct: plan.post_retirement_return_pct,
    } : {
      current_age: 30,
      retirement_age: 60,
      life_expectancy: 85,
      existing_retirement_corpus: 100000,
      planned_monthly_contribution: 15000,
      inflation_pct: 6,
      pre_retirement_return_pct: 11,
      post_retirement_return_pct: 7,
    },
  });


  const planMutation = useMutation({
    mutationFn: (data: RetirementFormData) => {
      if (isNew) {
        return retirementService.createPlan(data);
      }
      return retirementService.updatePlan(data);
    },
    onSuccess: (updatedPlan) => {
      queryClient.setQueryData(['retirementPlan'], updatedPlan);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setSuccess(true);
      setServerError(null);
      setTimeout(() => setSuccess(false), 3000);
    },
    onError: (err: any) => {
      setServerError(err.message || 'Failed to save retirement plan.');
    },
  });

  const onSubmit = (data: RetirementFormData) => {
    setServerError(null);
    planMutation.mutate(data);
  };

  if (isLoading) {
    return (
      <div className="skeleton-loading-container">
        <div className="skeleton skeleton-banner" />
        <div className="skeleton skeleton-card mt-3" />
      </div>
    );
  }

  if (isProfileMissing) {
    return (
      <div className="error-state-box card p-5 text-center mt-3">
        <Hourglass size={48} className="text-warning mb-2" />
        <h3>Set Up Financial Profile First</h3>
        <p className="text-secondary mb-4">
          Retirement projections are based on inflating your current monthly expenses. Create your onboarding profile first.
        </p>
        <Button onClick={() => navigate('/profile')} variant="primary">
          Setup Profile
        </Button>
      </div>
    );
  }

  return (
    <div className="retirement-page">
      <div className="page-header-row mb-4">
        <div>
          <h2>Retirement Planner</h2>
          <p className="text-secondary">Determine safety-net sizing requirements and map monthly contribution timelines.</p>
        </div>
      </div>

      <div className="retirement-grid">
        {/* Left Side: Parameters Form */}
        <div className="retirement-form-panel">
          <Card title={isNew ? 'Create Retirement Map' : 'Adjust Plan Variables'}>
            {success && (
              <div className="alert alert-success d-flex align-items-center mb-3">
                <CheckCircle2 size={16} className="me-2" />
                <span>Retirement plan saved successfully!</span>
              </div>
            )}
            {serverError && <div className="alert alert-danger mb-3">{serverError}</div>}

            <form onSubmit={handleSubmit(onSubmit)}>
              <div className="form-row-3">
                <InputField
                  label="Current Age"
                  type="number"
                  error={errors.current_age?.message}
                  disabled={planMutation.isPending}
                  {...register('current_age', { valueAsNumber: true })}
                />

                <InputField
                  label="Retire Age"
                  type="number"
                  error={errors.retirement_age?.message}
                  disabled={planMutation.isPending}
                  {...register('retirement_age', { valueAsNumber: true })}
                />

                <InputField
                  label="Life Expectancy"
                  type="number"
                  error={errors.life_expectancy?.message}
                  disabled={planMutation.isPending}
                  {...register('life_expectancy', { valueAsNumber: true })}
                />
              </div>

              <div className="form-row-2">
                <InputField
                  label="Existing Corpus (₹)"
                  type="number"
                  error={errors.existing_retirement_corpus?.message}
                  disabled={planMutation.isPending}
                  {...register('existing_retirement_corpus', { valueAsNumber: true })}
                />

                <InputField
                  label="Planned Monthly SIP (₹)"
                  type="number"
                  error={errors.planned_monthly_contribution?.message}
                  disabled={planMutation.isPending}
                  {...register('planned_monthly_contribution', { valueAsNumber: true })}
                />
              </div>

              <div className="form-row-3">
                <InputField
                  label="Inflation Rate (%)"
                  type="number"
                  step="0.1"
                  error={errors.inflation_pct?.message}
                  disabled={planMutation.isPending}
                  {...register('inflation_pct', { valueAsNumber: true })}
                />

                <InputField
                  label="Pre-Retire Return (%)"
                  type="number"
                  step="0.1"
                  error={errors.pre_retirement_return_pct?.message}
                  disabled={planMutation.isPending}
                  {...register('pre_retirement_return_pct', { valueAsNumber: true })}
                />

                <InputField
                  label="Post-Retire Return (%)"
                  type="number"
                  step="0.1"
                  error={errors.post_retirement_return_pct?.message}
                  disabled={planMutation.isPending}
                  {...register('post_retirement_return_pct', { valueAsNumber: true })}
                />
              </div>

              <div className="form-actions mt-4">
                <Button type="submit" variant="primary" className="w-100" isLoading={planMutation.isPending}>
                  {isNew ? 'Initialize Retirement Plan' : 'Save Adjustments'}
                </Button>
              </div>
            </form>
          </Card>
        </div>

        {/* Right Side: Projections Preview */}
        <div className="retirement-summary-panel">
          {!isNew && plan ? (
            <Card title="Pension Calculations" className="bg-surface-dark-subtle border-none">
              <div className="metric-row-inline mb-4">
                <div>
                  <span className="text-secondary text-sm">Feasibility Status</span>
                  <div className="mt-1">
                    <StatusIndicator status={plan.feasibility_status} />
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-secondary text-sm">Monthly Expenses</span>
                  <h4 className="font-semibold text-primary mt-1">{formatINR(plan.current_monthly_expense)} / mo</h4>
                </div>
              </div>

              <div className="detail-rows">
                <div className="detail-row">
                  <span className="text-secondary">Years to Retirement</span>
                  <span className="font-semibold text-primary">{plan.years_to_retirement} Years</span>
                </div>

                <div className="detail-row">
                  <span className="text-secondary">Years in Retirement</span>
                  <span className="font-semibold text-primary">{plan.years_in_retirement} Years</span>
                </div>

                <div className="detail-row">
                  <span className="text-secondary">Target Corpus Sizing</span>
                  <span className="font-semibold text-accent">{formatINR(plan.required_corpus)}</span>
                </div>

                <div className="detail-row">
                  <span className="text-secondary">Projected Final Value</span>
                  <span className="font-semibold text-success">
                    {formatINR(plan.feasibility_details.projected_value)}
                  </span>
                </div>

                {['unlikely', 'at_risk'].includes(plan.feasibility_details.status) && (
                   <div className="detail-row text-danger font-semibold">
                     <span>Estimated Shortfall</span>
                     <span>{formatINR(plan.feasibility_details.shortfall || 0)}</span>
                   </div>
                 )}
               </div>
 
               {['unlikely', 'at_risk'].includes(plan.feasibility_details.status) && (
                 <div className="suggestions-container mt-4 card p-3 border-danger-subtle bg-danger-subtle">
                   <h4 className="text-danger m-0 text-sm">Recommendations to close shortfall:</h4>
                  <ul className="mt-2 text-xs text-secondary pl-4">
                    {plan.feasibility_details.suggested_monthly_sip && (
                      <li className="mb-1">
                        Increase monthly contribution to: <strong>{formatINR(plan.feasibility_details.suggested_monthly_sip)}</strong>
                      </li>
                    )}
                    {plan.feasibility_details.suggested_extended_months && (
                      <li>
                        Extend retirement date by <strong>{Math.ceil(plan.feasibility_details.suggested_extended_months / 12)} years</strong>
                      </li>
                    )}
                  </ul>
                </div>
              )}

              <div className="info-tip-row mt-4">
                <Info size={16} className="text-secondary flex-shrink-0 me-2" />
                <p className="text-xs text-secondary m-0">
                  Target Corpus calculates growing annuity present value as of retirement date, inflating expenses to match inflation assumptions.
                </p>
              </div>
            </Card>
          ) : (
            <Card title="Projections Preview" className="bg-surface-dark-subtle border-none text-center p-4">
              <Hourglass size={40} className="text-secondary mb-2 mx-auto" />
              <p className="text-secondary text-sm">Save variables on the left to review target corpus size and timeline indicators.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
