/* frontend/src/services/simulationService.ts */
import { apiClient } from './apiClient';
import type { SimulationInput, SimulationResult, WhatIfComparisonResponse } from '../types/api';

export const simulationService = {
  async runSimulation(payload: SimulationInput): Promise<SimulationResult> {
    const res = await apiClient.post<SimulationResult>('/simulation/run', payload);
    return res.data;
  },

  async compareWhatIf(payload: {
    current_plan: SimulationInput;
    what_if_plan: SimulationInput;
  }): Promise<WhatIfComparisonResponse> {
    const res = await apiClient.post<WhatIfComparisonResponse>('/simulation/what-if', payload);
    return res.data;
  },
};
