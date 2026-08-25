/* frontend/src/services/goalsService.ts */
import { apiClient } from './apiClient';
import type { GoalCreate, GoalOut, GoalCheckResponse } from '../types/api';

export const goalsService = {
  async checkGoal(payload: GoalCreate): Promise<GoalCheckResponse> {
    const response = await apiClient.post<GoalCheckResponse>('/goals/check', payload);
    return response.data;
  },

  async createGoal(payload: GoalCreate): Promise<GoalOut> {
    const response = await apiClient.post<GoalOut>('/goals', payload);
    return response.data;
  },

  async getGoals(): Promise<GoalOut[]> {
    const response = await apiClient.get<GoalOut[]>('/goals');
    return response.data;
  },

  async getGoal(id: string): Promise<GoalOut> {
    const response = await apiClient.get<GoalOut>(`/goals/${id}`);
    return response.data;
  },
};
