/* frontend/src/layouts/DashboardLayout.tsx */
import React, { useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Sidebar } from '../components/layout/Sidebar';
import { Header } from '../components/layout/Header';

import { useQuery } from '@tanstack/react-query';
import { dashboardService } from '../services/dashboardService';

export const DashboardLayout: React.FC = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => dashboardService.getSummary(),
    enabled: isAuthenticated,
  });

  const isLoading = authLoading || (isAuthenticated && dashLoading);

  if (isLoading) {
    return (
      <div className="layout-loading">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Redirect to login page and keep track of where they wanted to go
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (dashboard && !dashboard.profile_complete) {
    // Force onboarding redirect if profile is not complete
    return <Navigate to="/onboarding" replace />;
  }

  // Derive page title from route
  const getPageTitle = (pathname: string) => {
    if (pathname === '/') return 'Dashboard';
    if (pathname.startsWith('/goals')) return 'Goals Planner';
    if (pathname === '/emergency-fund') return 'Emergency Fund Tracker';
    if (pathname === '/retirement') return 'Retirement Planner';
    if (pathname === '/funds') return 'Fund Explorer';
    if (pathname === '/coach') return 'AI Financial Coach';
    if (pathname === '/profile') return 'Profile Settings';
    return 'Goal-Based Investment Platform';
  };

  return (
    <div className="dashboard-layout-container">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="dashboard-content-wrapper">
        <Header 
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
          title={getPageTitle(location.pathname)}
        />
        <main className="dashboard-main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
