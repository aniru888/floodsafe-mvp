/**
 * AiChatFab — Floating action button that opens/closes the AI chat panel.
 *
 * Position: fixed bottom-24 right-4 (sits above BottomNav at ~64px)
 * Z-index: Z.aiFab (170)
 *
 * Pulses when the city has active alerts to invite the user to ask the AI.
 */

import { MessageCircle, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Z } from '../../constants/z-index';

interface AiChatFabProps {
  isOpen: boolean;
  onToggle: () => void;
  hasAlerts?: boolean;
}

export function AiChatFab({ isOpen, onToggle, hasAlerts = false }: AiChatFabProps) {
  return (
    <button
      onClick={onToggle}
      aria-label={isOpen ? 'Close AI chat' : 'Open AI chat'}
      className={cn(
        'fixed bottom-24 right-4 w-14 h-14 rounded-full',
        'flex items-center justify-center',
        'transition-all duration-200 active:scale-95',
        'text-white shadow-lg',
        hasAlerts && !isOpen && 'ring-4 ring-emerald-300 animate-pulse',
      )}
      style={{
        zIndex: Z.aiFab,
        backgroundColor: '#10b981',
        boxShadow: '0 10px 15px -3px rgba(16, 185, 129, 0.4)',
      }}
    >
      {isOpen ? (
        <X className="w-6 h-6" />
      ) : (
        <MessageCircle className="w-6 h-6" />
      )}
    </button>
  );
}
