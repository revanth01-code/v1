/* frontend/src/layouts/AuthLayout.tsx */
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export const AuthLayout: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="layout-loading">
        <div className="layout-loading-inner">
          <div className="spinner-border" role="status" aria-hidden="true" />
          <span className="layout-loading-text">Loading...</span>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    // If already authenticated, redirect to root dashboard
    return <Navigate to="/" replace />;
  }

  return (
    <div className="auth-layout-container">
      <div className="auth-card-wrapper">
        <Outlet />
      </div>
    </div>
  );
};
