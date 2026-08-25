/* frontend/src/services/authService.ts */
import { apiClient } from './apiClient';
import type { SignUpInput, LoginInput, AuthSession, UserOut } from '../types/api';

export const authService = {
  async signUp(payload: SignUpInput): Promise<AuthSession | { message: string; requiresConfirmation: boolean }> {
    try {
      const response = await apiClient.post('/auth/signup', payload);
      // Backend signs up and either returns the session immediately or accepts with 202
      if (response.status === 202) {
        return {
          message: response.data.detail || 'Account created — check your email to confirm before logging in.',
          requiresConfirmation: true
        };
      }
      return response.data.session;
    } catch (error: any) {
      // Backend wraps verification messages inside AppErrors
      if (error.status === 202) {
        return {
          message: error.message,
          requiresConfirmation: true
        };
      }
      throw error;
    }
  },

  async login(payload: LoginInput): Promise<AuthSession> {
    const response = await apiClient.post('/auth/login', payload);
    return response.data.session;
  },

  async logout(): Promise<void> {
    await apiClient.post('/auth/logout');
  },

  async me(): Promise<{ user: UserOut }> {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },
};
