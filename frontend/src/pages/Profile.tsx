/* frontend/src/pages/Profile.tsx */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { profileService } from '../services/profileService';
import { Card } from '../components/common/Card';
import { InputField } from '../components/common/InputField';
import { Button } from '../components/common/Button';
import { formatINR } from '../utils/currency';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

const profileUpdateSchema = z.object({
  monthly_income: z.number().min(0, 'Must be positive'),
  monthly_expenses: z.number().min(0, 'Must be positive'),
  existing_savings: z.number().min(0, 'Must be positive'),
  existing_investments: z.number().min(0, 'Must be positive'),
  dependents: z.number().int().min(0, 'Must be positive'),
  employment_type: z.string().min(1, 'Required'),
  essential_expenses: z.number().min(0, 'Must be positive'),
  emi_obligations: z.number().min(0, 'Must be positive'),
  mandatory_commitments: z.number().min(0, 'Must be positive'),
  emergency_fund_contribution: z.number().min(0, 'Must be positive'),
});

type ProfileUpdateFormData = z.infer<typeof profileUpdateSchema>;

export const Profile: React.FC = () => {
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ['profile'],
    queryFn: () => profileService.getProfile(),
  });

  const { register, handleSubmit, formState: { errors } } = useForm<ProfileUpdateFormData>({
    resolver: zodResolver(profileUpdateSchema),
    values: profile ? {
      monthly_income: profile.monthly_income,
      monthly_expenses: profile.monthly_expenses,
      existing_savings: profile.existing_savings,
      existing_investments: profile.existing_investments,
      dependents: profile.dependents,
      employment_type: profile.employment_type || 'Salaried',
      essential_expenses: profile.essential_expenses || 0,
      emi_obligations: profile.emi_obligations || 0,
      mandatory_commitments: profile.mandatory_commitments || 0,
      emergency_fund_contribution: profile.emergency_fund_contribution || 0,
    } : undefined,
  });

  const updateMutation = useMutation({
    mutationFn: (data: ProfileUpdateFormData) => profileService.updateProfile(data),
    onSuccess: (updatedProfile) => {
      queryClient.setQueryData(['profile'], updatedProfile);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    },
    onError: (err: any) => {
      setServerError(err.message || 'Failed to update profile.');
    },
  });

  const onSubmit = (data: ProfileUpdateFormData) => {
    setServerError(null);
    updateMutation.mutate(data);
  };

  if (isLoading) {
    return (
      <div className="skeleton-loading-container">
        <div className="skeleton skeleton-banner" />
        <div className="skeleton skeleton-card mt-3" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-state-box card p-4">
        <AlertCircle size={40} className="text-danger mb-2" />
        <h3>Failed to load profile settings</h3>
        <p className="text-secondary">{error.message || 'Profile not set up yet.'}</p>
      </div>
    );
  }

  return (
    <div className="profile-page-container">
      <div className="page-header-row mb-4">
        <div>
          <h2>Profile Settings</h2>
          <p className="text-secondary">Keep your financial metrics updated to adjust calculated recommendations.</p>
        </div>
      </div>

      <div className="profile-grid">
        <div className="profile-form-panel">
          <Card title="Update Financial Metrics">
            {success && (
              <div className="alert alert-success d-flex align-items-center">
                <CheckCircle2 size={16} className="me-2" />
                <span>Profile updated successfully!</span>
              </div>
            )}
            {serverError && <div className="alert alert-danger">{serverError}</div>}

            <form onSubmit={handleSubmit(onSubmit)}>
              <h4 className="section-title mb-3">Core Income & Asset Metrics</h4>
              <div className="form-row-2">
                <InputField
                  label="Monthly Income (₹)"
                  type="number"
                  error={errors.monthly_income?.message}
                  disabled={updateMutation.isPending}
                  {...register('monthly_income', { valueAsNumber: true })}
                />
                <InputField
                  label="Monthly Expenses (₹)"
                  type="number"
                  error={errors.monthly_expenses?.message}
                  disabled={updateMutation.isPending}
                  {...register('monthly_expenses', { valueAsNumber: true })}
                />
              </div>

              <div className="form-row-2">
                <InputField
                  label="Existing Savings (₹)"
                  type="number"
                  error={errors.existing_savings?.message}
                  disabled={updateMutation.isPending}
                  {...register('existing_savings', { valueAsNumber: true })}
                />
                <InputField
                  label="Existing Investments (₹)"
                  type="number"
                  error={errors.existing_investments?.message}
                  disabled={updateMutation.isPending}
                  {...register('existing_investments', { valueAsNumber: true })}
                />
              </div>

              <div className="form-row-2">
                <InputField
                  label="Number of Dependents"
                  type="number"
                  error={errors.dependents?.message}
                  disabled={updateMutation.isPending}
                  {...register('dependents', { valueAsNumber: true })}
                />
                <div className="form-group">
                  <label htmlFor="employment_type" className="form-label">
                    Employment Type
                  </label>
                  <select
                    id="employment_type"
                    className="form-control"
                    disabled={updateMutation.isPending}
                    {...register('employment_type')}
                  >
                    <option value="Salaried">Salaried</option>
                    <option value="Self-Employed">Self Employed</option>
                    <option value="Business Owner">Business Owner</option>
                    <option value="Unemployed">Retired/Student/Unemployed</option>
                  </select>
                </div>
              </div>

              <hr className="divider-dark my-4" />
              <h4 className="section-title mb-3">Capacity Engine Allocations (Monthly)</h4>

              <div className="form-row-2">
                <InputField
                  label="Essential Expenses (Rent, Bills, Food) (₹)"
                  type="number"
                  error={errors.essential_expenses?.message}
                  disabled={updateMutation.isPending}
                  {...register('essential_expenses', { valueAsNumber: true })}
                />
                <InputField
                  label="EMI & Debt Obligations (₹)"
                  type="number"
                  error={errors.emi_obligations?.message}
                  disabled={updateMutation.isPending}
                  {...register('emi_obligations', { valueAsNumber: true })}
                />
              </div>

              <div className="form-row-2">
                <InputField
                  label="Mandatory Commitments (Insurance, Fees) (₹)"
                  type="number"
                  error={errors.mandatory_commitments?.message}
                  disabled={updateMutation.isPending}
                  {...register('mandatory_commitments', { valueAsNumber: true })}
                />
                <InputField
                  label="Emergency Fund Monthly Contribution (₹)"
                  type="number"
                  error={errors.emergency_fund_contribution?.message}
                  disabled={updateMutation.isPending}
                  {...register('emergency_fund_contribution', { valueAsNumber: true })}
                />
              </div>

              <div className="form-actions mt-3">
                <Button type="submit" variant="primary" isLoading={updateMutation.isPending}>
                  Save Changes
                </Button>
              </div>
            </form>
          </Card>
        </div>

        <div className="profile-summary-panel">
          <Card title="Financial Context Summary" className="bg-surface-dark-subtle border-none">
            <div className="summary-stat-group">
              <div className="stat-item-inner">
                <span className="text-secondary text-sm">Monthly Net Surplus</span>
                <h3 className={`stat-value-large ${profile && profile.monthly_surplus >= 0 ? 'text-success' : 'text-danger'}`}>
                  {profile ? formatINR(profile.monthly_surplus) : '₹0'}
                </h3>
                <p className="text-secondary text-xs mt-1">
                  Surplus is calculated as Income minus Expenses, representing your capacity to fund goals.
                </p>
              </div>
            </div>

            <hr className="divider-dark my-4" />

            <div className="summary-stat-group bg-surface-dark-only p-3 rounded-lg border border-primary-dark">
              <div className="stat-item-inner">
                <span className="text-primary text-sm font-semibold">Available Investment Capacity</span>
                <h3 className="stat-value-large text-primary mt-1">
                  {profile ? formatINR(profile.available_capacity) : '₹0'}
                </h3>
                <p className="text-secondary text-xs mt-1">
                  Calculated as: Income - Essential Expenses - EMI Obligations - Mandatory Commitments - Emergency Fund Contribution. This is your safe multi-goal budget.
                </p>
              </div>
            </div>

            <hr className="divider-dark my-4" />

            <div className="stat-summary-rows">
              <div className="summary-row-item">
                <span className="text-secondary">Existing Liquid Net Worth</span>
                <span className="font-semibold text-primary">
                  {profile ? formatINR(profile.existing_savings + profile.existing_investments) : '₹0'}
                </span>
              </div>
              <div className="summary-row-item">
                <span className="text-secondary">Savings-to-Income Ratio</span>
                <span className="font-semibold text-primary">
                  {profile && profile.monthly_income > 0 
                    ? `${((profile.existing_savings / profile.monthly_income) * 100).toFixed(0)}%`
                    : '0%'}
                </span>
              </div>
              <div className="summary-row-item">
                <span className="text-secondary">Dependents count</span>
                <span className="font-semibold text-primary">{profile?.dependents || 0}</span>
              </div>
              <div className="summary-row-item">
                <span className="text-secondary">Employment</span>
                <span className="font-semibold text-primary">{profile?.employment_type || 'Unspecified'}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
