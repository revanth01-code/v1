/* frontend/src/services/dashboardService.ts */
import { apiClient } from './apiClient';
import type { DashboardOut } from '../types/api';

export const dashboardService = {
  async getSummary(): Promise<DashboardOut> {
    const response = await apiClient.get<DashboardOut>('/dashboard');
    return response.data;
  },
};
