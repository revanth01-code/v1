/* frontend/src/services/retirementService.ts */
import { apiClient } from './apiClient';
import type { RetirementCreate, RetirementUpdate, RetirementOut } from '../types/api';

export const retirementService = {
  async getPlan(): Promise<RetirementOut> {
    const response = await apiClient.get<RetirementOut>('/retirement');
    return response.data;
  },

  async createPlan(payload: RetirementCreate): Promise<RetirementOut> {
    const response = await apiClient.post<RetirementOut>('/retirement', payload);
    return response.data;
  },

  async updatePlan(payload: RetirementUpdate): Promise<RetirementOut> {
    const response = await apiClient.put<RetirementOut>('/retirement', payload);
    return response.data;
  },
};
