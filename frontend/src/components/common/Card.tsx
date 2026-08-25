/* frontend/src/components/common/Card.tsx */
import React from 'react';
import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  title?: string;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ children, title, className = '' }) => {
  return (
    <div className={`card ${className}`}>
      {title && (
        <div className="card-header-inner">
          <h3 className="card-title-text">{title}</h3>
        </div>
      )}
      <div className="card-body-inner">{children}</div>
    </div>
  );
};
