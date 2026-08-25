/* frontend/src/pages/Onboarding.tsx */
import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { profileService } from '../services/profileService';
import { dashboardService } from '../services/dashboardService';
import { useAuth } from '../hooks/useAuth';
import { InputField } from '../components/common/InputField';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Target } from 'lucide-react';

const profileSchema = z.object({
  monthly_income: z.number({ message: 'Monthly income is required' }).min(0, 'Must be positive'),
  monthly_expenses: z.number({ message: 'Monthly expenses is required' }).min(0, 'Must be positive'),
  existing_savings: z.number({ message: 'Existing savings is required' }).min(0, 'Must be positive'),
  existing_investments: z.number({ message: 'Existing investments is required' }).min(0, 'Must be positive'),
  dependents: z.number({ message: 'Number of dependents is required' }).int().min(0, 'Must be positive'),
  employment_type: z.string().min(1, 'Employment type is required'),
});

type ProfileFormData = z.infer<typeof profileSchema>;

export const Onboarding: React.FC = () => {
  const { refreshUser, isAuthenticated, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => dashboardService.getSummary(),
    enabled: isAuthenticated,
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      monthly_income: undefined,
      monthly_expenses: undefined,
      existing_savings: 0,
      existing_investments: 0,
      dependents: 0,
      employment_type: 'Salaried',
    },
  });

  const onSubmit = async (data: ProfileFormData) => {
    setServerError(null);
    setSubmitting(true);
    try {
      await profileService.createProfile(data);
      await refreshUser();
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      navigate('/', { replace: true });
    } catch (error: any) {
      setServerError(error.message || 'Failed to save financial profile. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const isLoading = authLoading || (isAuthenticated && dashLoading);

  if (isLoading) {
    return (
      <div className="layout-loading">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (dashboard && dashboard.profile_complete) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="onboarding-container">
      <div className="onboarding-header">
        <Target className="logo-icon-lg mb-2" />
        <h2>Welcome to InvestPlan</h2>
        <p className="subtitle">Let's set up your financial profile to personalize your planners.</p>
      </div>

      <Card className="onboarding-card">
        {serverError && <div className="alert alert-danger">{serverError}</div>}

        <form onSubmit={handleSubmit(onSubmit)} className="onboarding-form">
          <div className="form-row-2">
            <InputField
              label="Monthly Income (₹)"
              type="number"
              id="monthly_income"
              placeholder="e.g. 75000"
              error={errors.monthly_income?.message}
              disabled={submitting}
              {...register('monthly_income', { valueAsNumber: true })}
            />

            <InputField
              label="Monthly Expenses (₹)"
              type="number"
              id="monthly_expenses"
              placeholder="e.g. 40000"
              error={errors.monthly_expenses?.message}
              disabled={submitting}
              {...register('monthly_expenses', { valueAsNumber: true })}
            />
          </div>

          <div className="form-row-2">
            <InputField
              label="Existing Savings (₹)"
              type="number"
              id="existing_savings"
              placeholder="e.g. 50000"
              error={errors.existing_savings?.message}
              disabled={submitting}
              {...register('existing_savings', { valueAsNumber: true })}
            />

            <InputField
              label="Existing Investments (₹)"
              type="number"
              id="existing_investments"
              placeholder="e.g. 150000"
              error={errors.existing_investments?.message}
              disabled={submitting}
              {...register('existing_investments', { valueAsNumber: true })}
            />
          </div>

          <div className="form-row-2">
            <InputField
              label="Number of Dependents"
              type="number"
              id="dependents"
              placeholder="0"
              error={errors.dependents?.message}
              disabled={submitting}
              {...register('dependents', { valueAsNumber: true })}
            />

            <div className="form-group">
              <label htmlFor="employment_type" className="form-label">
                Employment Type
              </label>
              <select
                id="employment_type"
                className="form-control"
                disabled={submitting}
                {...register('employment_type')}
              >
                <option value="Salaried">Salaried</option>
                <option value="Self-Employed">Self Employed</option>
                <option value="Business Owner">Business Owner</option>
                <option value="Unemployed">Retired/Student/Unemployed</option>
              </select>
              {errors.employment_type?.message && (
                <p className="form-error-text">{errors.employment_type.message}</p>
              )}
            </div>
          </div>

          <div className="onboarding-actions">
            <Button type="submit" variant="primary" isLoading={submitting} className="w-100 mt-2">
              Save and Continue to Dashboard
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
