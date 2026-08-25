/* frontend/src/pages/CoachChat.tsx */
import React, { useState, useEffect, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { chatbotService } from '../services/chatbotService';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import type { ChatMessage } from '../types/api';
import { Send, Bot, User, RefreshCw } from 'lucide-react';

export const CoachChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: "Hello! I am your AI Financial Coach. I can analyze your saved profile metrics, safety nets, retirement projections, and active goals. Ask me questions like: 'Am I on track for my goals?', 'Do I have enough emergency coverage?', or 'How can I adjust my retirement savings?'",
    },
  ]);
  const [inputVal, setInputVal] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of conversation
  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const chatMutation = useMutation({
    mutationFn: (history: ChatMessage[]) => chatbotService.sendMessage(history),
    onSuccess: (data) => {
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
    },
    onError: (err: any) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Sorry, I encountered an error communicating with the server: ${err.message || 'Unknown error'}. Please try again shortly.`,
        },
      ]);
    },
  });

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim() || chatMutation.isPending) return;

    const userMessage: ChatMessage = { role: 'user', content: inputVal.trim() };
    const newHistory = [...messages, userMessage];
    
    setMessages(newHistory);
    setInputVal('');
    
    // Post complete history to the stateless API
    chatMutation.mutate(newHistory);
  };

  const handleClearChat = () => {
    setMessages([
      {
        role: 'assistant',
        content: "Reset complete. Ask me any questions about your current saved planners!",
      },
    ]);
  };

  return (
    <div className="coach-chat-page-container">
      <div className="page-header-row mb-4 justify-content-between align-items-center flex-wrap gap-2">
        <div>
          <h2>AI Financial Coach</h2>
          <p className="text-secondary">Ask questions regarding your financial profile, safety reserve, and savings plans.</p>
        </div>
        <Button variant="ghost" onClick={handleClearChat} className="btn-with-icon font-semibold btn-sm">
          <RefreshCw size={14} />
          <span>Clear History</span>
        </Button>
      </div>

      <Card className="chat-window-card">
        {/* Messages viewport */}
        <div className="chat-viewport">
          {messages.map((msg, index) => (
            <div key={index} className={`chat-message-row ${msg.role === 'user' ? 'message-user' : 'message-coach'}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? <User size={14} /> : <Bot size={14} />}
              </div>
              <div className="message-balloon">
                <p className="message-content-text">{msg.content}</p>
              </div>
            </div>
          ))}

          {chatMutation.isPending && (
            <div className="chat-message-row message-coach typing-row">
              <div className="message-avatar">
                <Bot size={14} />
              </div>
              <div className="message-balloon typing-balloon">
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input box */}
        <div className="chat-input-bar">
          <form onSubmit={handleSend} className="chat-form-box">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Ask the coach e.g. How is my emergency fund progress?"
              disabled={chatMutation.isPending}
              className="form-control chat-input-control"
            />
            <Button type="submit" variant="primary" className="chat-send-btn" disabled={!inputVal.trim() || chatMutation.isPending}>
              <Send size={16} />
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
};
