/* frontend/src/pages/Signup.tsx */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '../hooks/useAuth';
import { InputField } from '../components/common/InputField';
import { Button } from '../components/common/Button';
import { Target, CheckCircle2 } from 'lucide-react';

const signupSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters long'),
  confirmPassword: z.string().min(8, 'Confirm password is required'),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});

type SignupFormData = z.infer<typeof signupSchema>;

export const Signup: React.FC = () => {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
  });

  const onSubmit = async (data: SignupFormData) => {
    setServerError(null);
    setSuccessMessage(null);
    setSubmitting(true);
    try {
      const result = await signUp({
        email: data.email,
        password: data.password,
      });
      
      if (result && result.requiresConfirmation) {
        setSuccessMessage(result.message);
      } else {
        navigate('/', { replace: true });
      }
    } catch (error: any) {
      setServerError(error.message || 'Error creating account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (successMessage) {
    return (
      <div className="auth-box text-center">
        <div className="auth-success-icon-container">
          <CheckCircle2 size={48} className="text-success" />
        </div>
        <h2 className="auth-success-title">Verify Your Email</h2>
        <p className="auth-success-text">{successMessage}</p>
        <div className="mt-4">
          <Link to="/login" className="btn btn-primary w-100">
            Proceed to Sign In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-box">
      <div className="auth-header">
        <div className="auth-logo">
          <Target className="logo-icon-lg" />
          <h2>InvestPlan</h2>
        </div>
        <p className="auth-subtitle">Create an account to begin planning your goals</p>
      </div>

      {serverError && <div className="alert alert-danger">{serverError}</div>}

      <form onSubmit={handleSubmit(onSubmit)} className="auth-form">
        <InputField
          label="Email Address"
          type="email"
          id="email"
          placeholder="e.g. name@example.com"
          error={errors.email?.message}
          disabled={submitting}
          {...register('email')}
        />

        <InputField
          label="Password"
          type="password"
          id="password"
          placeholder="••••••••"
          error={errors.password?.message}
          disabled={submitting}
          {...register('password')}
        />

        <InputField
          label="Confirm Password"
          type="password"
          id="confirmPassword"
          placeholder="••••••••"
          error={errors.confirmPassword?.message}
          disabled={submitting}
          {...register('confirmPassword')}
        />

        <Button type="submit" variant="primary" isLoading={submitting} className="w-100 mt-3">
          Create Account
        </Button>
      </form>

      <div className="auth-footer">
        <p>
          Already have an account?{' '}
          <Link to="/login" className="auth-link">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};
