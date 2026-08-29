import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Info } from 'lucide-react';
import './InfoTooltip.css';

interface InfoTooltipProps {
  term: string;
  explanation: string;
}

export const InfoTooltip: React.FC<InfoTooltipProps> = ({ term, explanation }) => {
  const [isVisible, setIsVisible] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  
  const [coords, setCoords] = useState({ top: -9999, left: -9999 });
  const [position, setPosition] = useState<'top' | 'bottom'>('top');
  const [alignment, setAlignment] = useState<'center' | 'left' | 'right'>('center');

  const showTooltip = () => setIsVisible(true);
  const hideTooltip = () => setIsVisible(false);
  
  const toggleTooltip = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsVisible((prev) => !prev);
  };

  const updatePosition = () => {
    if (wrapperRef.current && isVisible) {
      const rect = wrapperRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      
      let top = rect.top;
      let left = rect.left + rect.width / 2;
      let pos: 'top' | 'bottom' = 'top';
      let align: 'center' | 'left' | 'right' = 'center';

      // Check vertical bounds
      if (rect.top < 150) {
        pos = 'bottom';
        top = rect.bottom;
      }

      // Check horizontal bounds
      if (left < 140) {
        align = 'left';
      } else if (left > viewportWidth - 140) {
        align = 'right';
      }

      setCoords({ left, top });
      setPosition(pos);
      setAlignment(align);
    }
  };

  useEffect(() => {
    updatePosition();
    if (isVisible) {
      window.addEventListener('scroll', updatePosition, true);
      window.addEventListener('resize', updatePosition);
    }
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isVisible]);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        const target = event.target as Element;
        if (!target.closest('.info-tooltip-popover')) {
          setIsVisible(false);
        }
      }
    };

    if (isVisible) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isVisible]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsVisible(false);
      }
    };
    if (isVisible) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isVisible]);

  const popoverContent = (
    <div 
      className={`info-tooltip-popover pos-${position} align-${alignment} ${isVisible ? 'visible' : ''}`}
      role="tooltip"
      aria-hidden={!isVisible}
      style={{ top: coords.top, left: coords.left }}
    >
      <span className="info-tooltip-title">{term}</span>
      <span className="info-tooltip-text">{explanation}</span>
    </div>
  );

  return (
    <div 
      className="info-tooltip-wrapper" 
      ref={wrapperRef}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
    >
      <button
        type="button"
        className="info-tooltip-button"
        onClick={toggleTooltip}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            toggleTooltip(e);
          }
        }}
        aria-label={`More information about ${term}`}
        aria-expanded={isVisible}
      >
        <Info size={14} />
      </button>
      {createPortal(popoverContent, document.body)}
    </div>
  );
};
