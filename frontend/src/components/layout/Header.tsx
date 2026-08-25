/* frontend/src/components/layout/Header.tsx */
import React from 'react';
import { Menu, Target } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

interface HeaderProps {
  onToggleSidebar: () => void;
  title?: string;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar, title = 'Goal-Based Investment Platform' }) => {
  const { user } = useAuth();

  return (
    <header className="header-container">
      <div className="header-left">
        <button className="header-toggle-btn" onClick={onToggleSidebar}>
          <Menu size={20} />
        </button>
        <div className="header-logo-mobile">
          <Target className="logo-icon-sm" />
          <span className="logo-text-sm">InvestPlan</span>
        </div>
        <h1 className="header-page-title">{title}</h1>
      </div>
      
      <div className="header-right">
        <div className="header-user-display">
          <span className="header-user-greeting">Welcome,</span>
          <span className="header-user-email">{user?.email}</span>
        </div>
      </div>
    </header>
  );
};
