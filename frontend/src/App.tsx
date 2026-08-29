/* frontend/src/App.tsx */
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './hooks/useAuth';

// Layouts
import { AuthLayout } from './layouts/AuthLayout';
import { DashboardLayout } from './layouts/DashboardLayout';

// Pages
import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { Onboarding } from './pages/Onboarding';
import { Dashboard } from './pages/Dashboard';
import { Profile } from './pages/Profile';
import { GoalsList } from './pages/GoalsList';
import { GoalCreateEdit } from './pages/GoalCreateEdit';
import { GoalDetails } from './pages/GoalDetails';
import { EmergencyFund } from './pages/EmergencyFund';
import { RetirementPlan } from './pages/RetirementPlan';
import { FundExplorer } from './pages/FundExplorer';
import { WhatIfLab } from './pages/WhatIfLab';

import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: false,
      staleTime: 5000,
    },
  },
});

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <Routes>
            {/* Public Auth routes */}
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
            </Route>

            {/* Profile onboarding setup (private, but separate from full layout) */}
            <Route path="/onboarding" element={<Onboarding />} />

            {/* Private Dashboard routes */}
            <Route element={<DashboardLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/goals" element={<GoalsList />} />
              <Route path="/goals/new" element={<GoalCreateEdit />} />
              <Route path="/goals/:goalId" element={<GoalDetails />} />
              <Route path="/emergency-fund" element={<EmergencyFund />} />
              <Route path="/retirement" element={<RetirementPlan />} />
              <Route path="/funds" element={<FundExplorer />} />
              <Route path="/what-if" element={<WhatIfLab />} />
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
