/* frontend/src/pages/Login.tsx */
import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '../hooks/useAuth';
import { InputField } from '../components/common/InputField';
import { Button } from '../components/common/Button';
import { Target } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormData = z.infer<typeof loginSchema>;

export const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const from = location.state?.from?.pathname || '/';

  const onSubmit = async (data: LoginFormData) => {
    setServerError(null);
    setSubmitting(true);
    try {
      await login(data);
      navigate(from, { replace: true });
    } catch (error: any) {
      setServerError(error.message || 'Invalid email or password');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-box">
      <div className="auth-header">
        <div className="auth-logo">
          <Target className="logo-icon-lg" />
          <h2>FinPilot</h2>
        </div>
        <p className="auth-subtitle">Sign in to manage your investment goals</p>
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

        <Button type="submit" variant="primary" isLoading={submitting} className="w-100 mt-3">
          Sign In
        </Button>
      </form>

      <div className="auth-footer">
        <p>
          Don't have an account?{' '}
          <Link to="/signup" className="auth-link">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
};
