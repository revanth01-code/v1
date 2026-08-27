/* frontend/src/components/common/StatusIndicator.tsx */
import React from 'react';

type StatusType = 'highly_feasible' | 'feasible' | 'borderline' | 'at_risk' | 'unlikely' | 'infeasible' | 'building' | 'complete' | string;

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
  
  if (normStatus === 'highly_feasible') {
    className += ' status-success border border-success-subtle';
    displayLabel = label || 'Highly Feasible';
  } else if (normStatus === 'feasible' || normStatus === 'complete') {
    className += ' status-success';
    displayLabel = label || (normStatus === 'feasible' ? 'Feasible' : 'Complete');
  } else if (normStatus === 'borderline') {
    className += ' status-warning';
    displayLabel = label || 'Borderline';
  } else if (normStatus === 'at_risk') {
    className += ' status-warning border border-danger-subtle';
    displayLabel = label || 'At Risk';
  } else if (normStatus === 'unlikely' || normStatus === 'infeasible') {
    className += ' status-danger';
    displayLabel = label || (normStatus === 'unlikely' ? 'Unlikely' : 'Infeasible');
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
