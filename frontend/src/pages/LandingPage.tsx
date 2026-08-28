/* frontend/src/pages/LandingPage.tsx */
import React from 'react';
import { Link } from 'react-router-dom';
import { Target, Compass, Layers, TrendingUp, ShieldCheck } from 'lucide-react';
import './LandingPage.css';

export const LandingPage: React.FC = () => {
  const capabilities = [
    {
      icon: Compass,
      title: 'Goal Planning',
      description: 'Plan goals based on target amount, timeline, inflation, and contribution capacity.',
    },
    {
      icon: Layers,
      title: 'Strategic Prioritization',
      description: 'When managing multiple financial goals, decide what should receive priority instead of looking at them in a random or alphabetical order.',
    },
    {
      icon: TrendingUp,
      title: 'Investment Planning',
      description: 'Provide risk-aware strategies and investment projections based on your goals and personal investor profile.',
    },
    {
      icon: ShieldCheck,
      title: 'Financial Readiness',
      description: "Consider your overall financial situation and affordability rather than giving isolated investment suggestions.",
    },
  ];

  return (
    <div className="landing-container">
      {/* Header */}
      <header className="landing-header">
        <div className="landing-header-container">
          <div className="landing-logo">
            <Target className="landing-logo-icon" size={24} />
            <span>InvestPlan</span>
          </div>
          <nav className="landing-nav">
            <Link to="/login" className="btn btn-ghost btn-sm">
              Sign In
            </Link>
            <Link to="/signup" className="btn btn-primary btn-sm">
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main>
        {/* Hero Section */}
        <section className="landing-hero">
          <div className="landing-hero-content">
            <h1 className="landing-hero-title">
              Plan your money around what matters.
            </h1>
            <p className="landing-hero-subtitle">
              Set financial goals, understand what you can realistically afford, prioritize what matters most, and build an investment plan around your life.
            </p>
            <div className="landing-hero-ctas">
              <Link to="/signup" className="btn btn-primary">
                Get Started
              </Link>
              <Link to="/login" className="btn btn-secondary">
                Sign In
              </Link>
            </div>
          </div>
        </section>

        {/* Product Value Proposition Section */}
        <section className="landing-capabilities">
          <div className="landing-capabilities-container">
            <div className="landing-capabilities-header">
              <h2 className="landing-capabilities-title">Designed for Serious Planning</h2>
              <p className="landing-capabilities-subtitle">
                A structured, data-driven approach to map, analyze, and achieve your financial aspirations.
              </p>
            </div>

            <div className="landing-capabilities-grid">
              {capabilities.map((cap, index) => {
                const Icon = cap.icon;
                return (
                  <div key={index} className="landing-card">
                    <div className="landing-card-icon-container">
                      <Icon size={20} />
                    </div>
                    <h3 className="landing-card-title">{cap.title}</h3>
                    <p className="landing-card-desc">{cap.description}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="landing-footer-container">
          <div className="landing-footer-logo">
            <Target className="landing-logo-icon" size={18} />
            <span>InvestPlan</span>
          </div>
          <p className="landing-footer-text">
            © {new Date().getFullYear()} InvestPlan. All rights reserved. Built for professional goal-based wealth planning.
          </p>
        </div>
      </footer>
    </div>
  );
};
