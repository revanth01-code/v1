/* frontend/src/utils/currency.ts */

export const formatINR = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return '₹0.00';
  
  // Format to standard Indian numbering system (Lakh, Crore)
  const formatter = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  });
  
  return formatter.format(value);
};

export const formatLargeNumber = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return '0';
  if (value >= 10000000) {
    return `${(value / 10000000).toFixed(2)} Cr`;
  }
  if (value >= 100000) {
    return `${(value / 100000).toFixed(2)} L`;
  }
  return value.toLocaleString('en-IN');
};
