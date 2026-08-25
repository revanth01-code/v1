/* frontend/src/services/fundService.ts */
import { apiClient } from './apiClient';
import type { FundOut, FundDetailOut } from '../types/api';

export const fundService = {
  async getFundsByCategory(category: string, limit = 10): Promise<FundOut[]> {
    const response = await apiClient.get<FundOut[]>('/funds', {
      params: { category, limit },
    });
    return response.data;
  },

  async getFundDetail(schemeCode: string): Promise<FundDetailOut> {
    const response = await apiClient.get<FundDetailOut>(`/funds/${schemeCode}`);
    return response.data;
  },
};
