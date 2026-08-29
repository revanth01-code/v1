/* frontend/src/pages/CoachChat.tsx */
import React from 'react';
import { ChatPanel } from '../components/coach/ChatPanel';

export const CoachChat: React.FC = () => {
  return (
    <div className="coach-chat-page-container">
      <div className="page-header-row mb-4">
        <div>
          <h2>AI Financial Coach</h2>
          <p className="text-secondary">
            Ask questions regarding your financial profile, safety reserve, and savings plans.
          </p>
        </div>
      </div>
      <div className="chat-window-card-wrapper">
        <ChatPanel />
      </div>
    </div>
  );
};
