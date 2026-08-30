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
          <span className="logo-text-sm">FinPilot</span>
        </div>
        <h1 className="header-page-title">{title}</h1>
      </div>
      
      <div className="header-right">
        <div className="header-user-display" style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div className="user-avatar" style={{ width: '32px', height: '32px', borderRadius: '50%', backgroundColor: 'var(--accent-color-light)', color: 'var(--accent-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: '0.875rem' }}>
            {user?.email ? user.email[0].toUpperCase() : 'U'}
          </div>
          <span className="header-user-email" style={{ fontWeight: 600 }}>{user?.email}</span>
        </div>
      </div>
    </header>
  );
};
