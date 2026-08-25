/* frontend/src/services/profileService.ts */
import { apiClient } from './apiClient';
import type { ProfileCreate, ProfileUpdate, ProfileOut } from '../types/api';

export const profileService = {
  async getProfile(): Promise<ProfileOut> {
    const response = await apiClient.get<ProfileOut>('/profile');
    return response.data;
  },

  async createProfile(payload: ProfileCreate): Promise<ProfileOut> {
    const response = await apiClient.post<ProfileOut>('/profile', payload);
    return response.data;
  },

  async updateProfile(payload: ProfileUpdate): Promise<ProfileOut> {
    const response = await apiClient.put<ProfileOut>('/profile', payload);
    return response.data;
  },
};
