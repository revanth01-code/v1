/* frontend/src/components/coach/ChatPanel.tsx */
import React, { useState, useEffect, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { chatbotService } from '../../services/chatbotService';
import { Button } from '../common/Button';
import type { ChatMessage } from '../../types/api';
import { Send, Bot, User, RefreshCw } from 'lucide-react';

const INITIAL_MESSAGE: ChatMessage = {
  role: 'assistant',
  content:
    "Hello! I am your AI Financial Coach. I can analyze your saved profile metrics, safety nets, retirement projections, and active goals. Ask me questions like: 'Am I on track for my goals?', 'Do I have enough emergency coverage?', or 'How can I adjust my retirement savings?'",
};

const RESET_MESSAGE: ChatMessage = {
  role: 'assistant',
  content: 'Reset complete. Ask me any questions about your current saved planners!',
};

interface ChatPanelProps {
  /** When true, the panel renders in compact floating mode (narrower, fixed height). */
  compact?: boolean;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ compact = false }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [inputVal, setInputVal] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

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
          content: `Sorry, I encountered an error: ${err.message || 'Unknown error'}. Please try again shortly.`,
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
    chatMutation.mutate(newHistory);
  };

  const handleClearChat = () => {
    setMessages([RESET_MESSAGE]);
  };

  return (
    <div className={`chat-panel-root${compact ? ' chat-panel-compact' : ''}`}>
      {/* Header / Clear button row */}
      <div className="chat-panel-header">
        <div className="chat-panel-title-row">
          <Bot size={15} />
          <span>AI Financial Coach</span>
        </div>
        <button
          type="button"
          className="chat-panel-clear-btn"
          onClick={handleClearChat}
          aria-label="Clear conversation history"
          title="Clear history"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Message viewport */}
      <div className="chat-viewport">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`chat-message-row ${msg.role === 'user' ? 'message-user' : 'message-coach'}`}
          >
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

      {/* Input bar */}
      <div className="chat-input-bar">
        <form onSubmit={handleSend} className="chat-form-box">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Ask the coach a question…"
            disabled={chatMutation.isPending}
            className="form-control chat-input-control"
          />
          <Button
            type="submit"
            variant="primary"
            className="chat-send-btn"
            disabled={!inputVal.trim() || chatMutation.isPending}
          >
            <Send size={16} />
          </Button>
        </form>
      </div>
    </div>
  );
};
