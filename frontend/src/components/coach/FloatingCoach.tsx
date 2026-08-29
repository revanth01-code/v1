/* frontend/src/components/coach/FloatingCoach.tsx */
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { MessageSquare, X } from 'lucide-react';
import { ChatPanel } from './ChatPanel';

export const FloatingCoach: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const toggle = () => setIsOpen((prev) => !prev);
  const close = () => setIsOpen(false);

  // Close when pressing Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen]);

  // Trap focus inside panel when open (click-outside to close)
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        close();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  return createPortal(
    <>
      {/* Floating Chat Panel */}
      <div
        ref={panelRef}
        className={`floating-coach-panel${isOpen ? ' floating-coach-panel--open' : ''}`}
        role="dialog"
        aria-label="AI Financial Coach"
        aria-hidden={!isOpen}
      >
        {/* Panel close bar */}
        <div className="floating-coach-panel-topbar">
          <span className="floating-coach-panel-topbar-title">AI Financial Coach</span>
          <button
            type="button"
            className="floating-coach-panel-close-btn"
            onClick={close}
            aria-label="Close AI Financial Coach"
          >
            <X size={16} />
          </button>
        </div>

        {/* Chat content — only mount when open so it doesn't run while hidden */}
        {isOpen && <ChatPanel compact />}
      </div>

      {/* Floating launcher button */}
      <button
        ref={triggerRef}
        type="button"
        className={`floating-coach-btn${isOpen ? ' floating-coach-btn--active' : ''}`}
        onClick={toggle}
        aria-label="Open AI Financial Coach"
        aria-expanded={isOpen}
        aria-controls="floating-coach-panel"
      >
        {isOpen ? <X size={20} /> : <MessageSquare size={20} />}
        {!isOpen && <span className="floating-coach-btn-label">AI Coach</span>}
      </button>
    </>,
    document.body
  );
};
