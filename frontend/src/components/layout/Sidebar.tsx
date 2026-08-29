/* frontend/src/components/layout/Sidebar.tsx */
import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import {
  LayoutDashboard,
  Target,
  ShieldAlert,
  Hourglass,
  TrendingUp,
  User,
  LogOut,
  X,
  Sliders
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { logout, user } = useAuth();

  const menuItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Goals Planner', path: '/goals', icon: Target },
    { name: 'What-If Lab', path: '/what-if', icon: Sliders },
    { name: 'Emergency Fund', path: '/emergency-fund', icon: ShieldAlert },
    { name: 'Retirement Planner', path: '/retirement', icon: Hourglass },
    { name: 'Fund Explorer', path: '/funds', icon: TrendingUp },
    { name: 'Profile Settings', path: '/profile', icon: User },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && <div className="sidebar-overlay" onClick={onClose} />}

      <aside className={`sidebar-container ${isOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <Target className="logo-icon" />
            <span className="logo-text">InvestPlan</span>
          </div>
          <button className="sidebar-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `sidebar-link ${isActive ? 'sidebar-link-active' : ''}`
                }
                onClick={() => onClose()}
              >
                <Icon size={18} className="link-icon" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="user-badge">
            <div className="user-avatar">
              {user?.email ? user.email[0].toUpperCase() : 'U'}
            </div>
            <div className="user-info">
              <span className="user-email">{user?.email || 'User'}</span>
            </div>
          </div>
          <button className="sidebar-logout-btn" onClick={logout}>
            <LogOut size={16} className="logout-icon" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>
    </>
  );
};
