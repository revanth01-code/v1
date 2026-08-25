/* frontend/src/components/common/SliderField.tsx */
import React from 'react';

interface SliderFieldProps {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (value: number) => void;
  formatValue?: (value: number) => string;
  error?: string;
}

export const SliderField: React.FC<SliderFieldProps> = ({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  formatValue,
  error,
}) => {
  const displayVal = formatValue ? formatValue(value) : value;

  return (
    <div className="slider-group">
      <div className="slider-label-row">
        <label className="slider-label">{label}</label>
        <span className="slider-value-display">{displayVal}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="slider-control"
      />
      <div className="slider-min-max-row">
        <span>{formatValue ? formatValue(min) : min}</span>
        <span>{formatValue ? formatValue(max) : max}</span>
      </div>
      {error && <p className="form-error-text">{error}</p>}
    </div>
  );
};
