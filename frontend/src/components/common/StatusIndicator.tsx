/* frontend/src/components/common/StatusIndicator.tsx */
import React from 'react';

type StatusType = 'feasible' | 'borderline' | 'infeasible' | 'building' | 'complete' | string;

interface StatusIndicatorProps {
  status: StatusType;
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  label,
  size = 'md',
}) => {
  const normStatus = status.toLowerCase();
  
  let className = 'status-pill';
  let displayLabel = label || status;
  
  if (normStatus === 'feasible' || normStatus === 'complete') {
    className += ' status-success';
    displayLabel = label || (normStatus === 'feasible' ? 'Feasible' : 'Complete');
  } else if (normStatus === 'borderline') {
    className += ' status-warning';
    displayLabel = label || 'Borderline';
  } else if (normStatus === 'infeasible') {
    className += ' status-danger';
    displayLabel = label || 'Infeasible';
  } else if (normStatus === 'building') {
    className += ' status-info';
    displayLabel = label || 'Building';
  } else {
    className += ' status-neutral';
  }

  if (size === 'sm') {
    className += ' status-sm';
  }

  return <span className={className}>{displayLabel}</span>;
};
