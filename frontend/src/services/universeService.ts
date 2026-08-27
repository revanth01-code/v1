/* frontend/src/services/universeService.ts */
import { apiClient } from './apiClient';
import type { AssetOut } from '../types/api';

export const universeService = {
  async getAssets(params?: { asset_class?: string; subcategory?: string }): Promise<AssetOut[]> {
    const res = await apiClient.get<AssetOut[]>('/universe/assets', { params });
    return res.data;
  },

  async getAssetDetail(identifier: string): Promise<AssetOut> {
    const res = await apiClient.get<AssetOut>(`/universe/assets/${identifier}`);
    return res.data;
  },

  async getRecommendations(riskLevel: string): Promise<Record<string, AssetOut[]>> {
    const res = await apiClient.get<Record<string, AssetOut[]>>('/universe/recommendations', {
      params: { risk_level: riskLevel },
    });
    return res.data;
  },
};
