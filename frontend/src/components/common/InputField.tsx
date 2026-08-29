/* frontend/src/components/common/InputField.tsx */
import { forwardRef } from 'react';
import type { InputHTMLAttributes } from 'react';

interface InputFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string | React.ReactNode;
  error?: string;
  helperText?: string;
}

export const InputField = forwardRef<HTMLInputElement, InputFieldProps>(
  ({ label, error, helperText, className = '', id, ...props }, ref) => {
    return (
      <div className={`form-group ${error ? 'has-error' : ''} ${className}`}>
        {label && (
          <label htmlFor={id} className="form-label">
            {label}
          </label>
        )}
        <input ref={ref} id={id} className="form-control" {...props} />
        {error && <p className="form-error-text">{error}</p>}
        {!error && helperText && <p className="form-helper-text">{helperText}</p>}
      </div>
    );
  }
);

InputField.displayName = 'InputField';
