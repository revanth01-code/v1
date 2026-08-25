/* frontend/src/services/emergencyService.ts */
import { apiClient } from './apiClient';
import type { EmergencyFundCreate, EmergencyFundUpdate, EmergencyFundOut } from '../types/api';

export const emergencyService = {
  async getPlan(): Promise<EmergencyFundOut> {
    const response = await apiClient.get<EmergencyFundOut>('/emergency-fund');
    return response.data;
  },

  async createPlan(payload: EmergencyFundCreate): Promise<EmergencyFundOut> {
    const response = await apiClient.post<EmergencyFundOut>('/emergency-fund', payload);
    return response.data;
  },

  async updatePlan(payload: EmergencyFundUpdate): Promise<EmergencyFundOut> {
    const response = await apiClient.put<EmergencyFundOut>('/emergency-fund', payload);
    return response.data;
  },
};
