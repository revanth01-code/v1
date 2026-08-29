/* frontend/src/pages/EmergencyFund.tsx */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { emergencyService } from '../services/emergencyService';
import { Card } from '../components/common/Card';
import { InputField } from '../components/common/InputField';
import { SliderField } from '../components/common/SliderField';
import { Button } from '../components/common/Button';
import { StatusIndicator } from '../components/common/StatusIndicator';
import { InfoTooltip } from '../components/common/InfoTooltip';
import { formatINR } from '../utils/currency';
import { ShieldAlert, CheckCircle2, Info } from 'lucide-react';

const emergencyFundSchema = z.object({
  months_of_coverage: z.number().gt(0, 'Must cover at least some months'),
  current_amount: z.number().min(0, 'Cannot be negative'),
  monthly_contribution: z.number().min(0, 'Cannot be negative'),
});

type EmergencyFundFormData = z.infer<typeof emergencyFundSchema>;

export const EmergencyFund: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const { data: plan, isLoading, error } = useQuery({
    queryKey: ['emergencyFund'],
    queryFn: () => emergencyService.getPlan(),
    retry: false, // Let 404 resolve as error cleanly for setup layout
  });

  const isNew = error && (error as any).status === 404;

  const { register, handleSubmit, formState: { errors }, watch, setValue } = useForm<EmergencyFundFormData>({
    resolver: zodResolver(emergencyFundSchema),
    values: plan ? {
      months_of_coverage: plan.months_of_coverage,
      current_amount: plan.current_amount,
      monthly_contribution: plan.monthly_contribution,
    } : {
      months_of_coverage: 6,
      current_amount: 10000,
      monthly_contribution: 5000,
    },
  });

  const formValues = watch();

  const planMutation = useMutation({
    mutationFn: (data: EmergencyFundFormData) => {
      if (isNew) {
        return emergencyService.createPlan(data);
      }
      return emergencyService.updatePlan(data);
    },
    onSuccess: (updatedPlan) => {
      queryClient.setQueryData(['emergencyFund'], updatedPlan);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setSuccess(true);
      setServerError(null);
      setTimeout(() => setSuccess(false), 3000);
    },
    onError: (err: any) => {
      setServerError(err.message || 'Failed to save emergency plan.');
    },
  });

  const onSubmit = (data: EmergencyFundFormData) => {
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

  // Handle case where profile does not exist yet (backend throws 422 for profile required)
  const isProfileMissing = error && (error as any).status === 422;

  if (isProfileMissing) {
    return (
      <div className="error-state-box card p-5 text-center mt-3">
        <ShieldAlert size={48} className="text-warning mb-2" />
        <h3>Set Up Financial Profile First</h3>
        <p className="text-secondary mb-4">
          Emergency fund calculations require knowing your monthly living expenses. Complete your onboarding profile first.
        </p>
        <Button onClick={() => navigate('/profile')} variant="primary">
          Setup Profile
        </Button>
      </div>
    );
  }

  return (
    <div className="emergency-fund-page">
      <div className="page-header-row mb-4">
        <div>
          <h2>Emergency Fund Tracker</h2>
          <p className="text-secondary">Determine safety-net sizing requirements and map monthly contribution timelines.</p>
        </div>
      </div>

      <div className="emergency-grid">
        {/* Left Side: Planner Config Form */}
        <div className="emergency-form-panel">
          <Card title={isNew ? 'Initialize Safety Net Reserve' : 'Adjust Settings'}>
            {success && (
              <div className="alert alert-success d-flex align-items-center mb-3">
                <CheckCircle2 size={16} className="me-2" />
                <span>Emergency fund settings saved!</span>
              </div>
            )}
            {serverError && <div className="alert alert-danger mb-3">{serverError}</div>}

            <form onSubmit={handleSubmit(onSubmit)}>
              <div className="form-group mb-3">
                <SliderField
                  label={
                    <span className="d-flex align-items-center">
                      Target Coverage (Months)
                      <InfoTooltip term="Target Coverage" explanation="The number of months your emergency fund could cover your essential living expenses if your income were to stop." />
                    </span>
                  }
                  min={1}
                  max={24}
                  step={0.5}
                  value={formValues.months_of_coverage}
                  onChange={(val) => setValue('months_of_coverage', val)}
                  formatValue={(val) => `${val} Months`}
                  error={errors.months_of_coverage?.message}
                />
              </div>

              <div className="form-row-2">
                <InputField
                  label="Current Saved Reserve (₹)"
                  type="number"
                  error={errors.current_amount?.message}
                  disabled={planMutation.isPending}
                  {...register('current_amount', { valueAsNumber: true })}
                />

                <InputField
                  label="Monthly Savings Contribution (₹)"
                  type="number"
                  error={errors.monthly_contribution?.message}
                  disabled={planMutation.isPending}
                  {...register('monthly_contribution', { valueAsNumber: true })}
                />
              </div>

              <div className="form-actions mt-4">
                <Button type="submit" variant="primary" className="w-100" isLoading={planMutation.isPending}>
                  {isNew ? 'Create Safety Plan' : 'Save Adjustments'}
                </Button>
              </div>
            </form>
          </Card>
        </div>

        {/* Right Side: Projections Preview */}
        <div className="emergency-summary-panel">
          {!isNew && plan ? (
            <Card title="Safety Net Calculations" className="bg-surface-dark-subtle border-none">
              <div className="metric-row-inline mb-4">
                <div>
                  <span className="text-secondary text-sm">Target Status</span>
                  <div className="mt-1">
                    <StatusIndicator status={plan.status} />
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-secondary text-sm">Living Expenses</span>
                  <h4 className="font-semibold text-primary mt-1">{formatINR(plan.monthly_expenses)} / mo</h4>
                </div>
              </div>

              {/* Progress bar */}
              <div className="progress-group mb-4">
                <div className="d-flex justify-content-between text-xs text-secondary mb-1">
                  <span>Progress</span>
                  <span>{plan.target_amount > 0 ? `${((plan.current_amount / plan.target_amount) * 100).toFixed(0)}%` : '0%'}</span>
                </div>
                <div className="progress-bar-track">
                  <div 
                    className="progress-bar-fill bg-accent"
                    style={{ width: `${Math.min((plan.current_amount / plan.target_amount) * 100, 100)}%` }}
                  />
                </div>
              </div>

              <div className="detail-rows">
                <div className="detail-row">
                  <span className="text-secondary">
                    Safety Net Target
                    <InfoTooltip term="Safety Net Reserve" explanation="The total amount of liquid funds you should keep easily accessible for unforeseen emergencies, based on your monthly expenses." />
                  </span>
                  <span className="font-semibold text-primary">{formatINR(plan.target_amount)}</span>
                </div>

                <div className="detail-row">
                  <span className="text-secondary">Current Savings</span>
                  <span className="font-semibold text-primary">{formatINR(plan.current_amount)}</span>
                </div>

                <div className="detail-row">
                  <span className="text-secondary">Shortfall remaining</span>
                  <span className="font-semibold text-danger">
                    {formatINR(Math.max(plan.target_amount - plan.current_amount, 0))}
                  </span>
                </div>

                <div className="detail-row font-semibold">
                  <span className="text-secondary">Timeline to target</span>
                  <span className="text-accent">
                    {plan.time_to_target_months !== null 
                      ? `${plan.time_to_target_months} Months`
                      : 'Infinite (SIP is ₹0)'}
                  </span>
                </div>
              </div>

              <div className="info-tip-row mt-4">
                <Info size={16} className="text-secondary flex-shrink-0 me-2" />
                <p className="text-xs text-secondary m-0">
                  Calculated based on your profile expenses. If your living costs drop, your target adjusts dynamically!
                </p>
              </div>
            </Card>
          ) : (
            <Card title="Safety Net Matrix" className="bg-surface-dark-subtle border-none text-center p-4">
              <ShieldAlert size={40} className="text-secondary mb-2 mx-auto" />
              <p className="text-secondary text-sm">Configure coverage details on the left to map your safety net timeline.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
