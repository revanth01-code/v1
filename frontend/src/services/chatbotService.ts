/* frontend/src/services/chatbotService.ts */
import { apiClient } from './apiClient';
import type { ChatMessage, ChatResponse } from '../types/api';

export const chatbotService = {
  async sendMessage(messages: ChatMessage[]): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/chatbot/message', { messages });
    return response.data;
  },
};
