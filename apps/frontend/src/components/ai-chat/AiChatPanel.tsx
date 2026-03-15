/**
 * AiChatPanel — Slide-up AI chat panel.
 *
 * Mobile: full-width, slides up from bottom, height ~70vh.
 * Desktop (md+): fixed 400px wide, anchored to bottom-right.
 *
 * Manages local message list and conversationId state.
 * Uses useAiChat() mutation from TanStack Query.
 * Detects "what if" scenario queries and offers inline simulation.
 */

import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { X, Send, Loader2, Bot, CloudRain } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Z } from '../../constants/z-index';
import { useAiChat, useSimulateFhi } from '../../lib/api/hooks';
import type { ChatMessage as ChatMessageType } from '../../types';
import { ChatMessage } from './ChatMessage';
import { QuickActions } from './QuickActions';

interface AiChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  city: string;
  latitude?: number;
  longitude?: number;
}

const WELCOME_MESSAGE: ChatMessageType = {
  role: 'assistant',
  content:
    'Hello! I\'m the FloodSafe AI assistant. I can help you check flood risk for your area, find evacuation routes, or answer questions about current conditions. How can I help you today?',
  timestamp: Date.now(),
};

const SCENARIOS = [
  { key: 'light', label: 'Light Rain', sublabel: '15mm' },
  { key: 'heavy', label: 'Heavy Monsoon', sublabel: '50mm' },
  { key: 'extreme', label: 'Extreme Storm', sublabel: '100mm' },
] as const;

const isScenarioQuery = (text: string) =>
  /what.?if|scenario|simulate|hypothetical|rain.*heavy|heavy.*rain/i.test(text);

export function AiChatPanel({ isOpen, onClose, city, latitude, longitude }: AiChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([WELCOME_MESSAGE]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [inputValue, setInputValue] = useState('');
  const [showScenarioPicker, setShowScenarioPicker] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutate: sendMessage, isPending } = useAiChat();
  const { mutate: simulateFhi, isPending: isSimulating } = useSimulateFhi();

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const handleScenarioSelect = (scenario: string) => {
    if (!latitude || !longitude) {
      const msg: ChatMessageType = {
        role: 'assistant',
        content: 'I need your location to simulate flood risk. Please allow location access and try again.',
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, msg]);
      setShowScenarioPicker(false);
      return;
    }

    simulateFhi(
      { latitude, longitude, city, scenario },
      {
        onSuccess: (data) => {
          const resultMsg: ChatMessageType = {
            role: 'assistant',
            content: `${data.description}\n\n⚠️ ${data.disclaimer}`,
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, resultMsg]);
          setShowScenarioPicker(false);
        },
        onError: () => {
          const errorMsg: ChatMessageType = {
            role: 'assistant',
            content: 'Simulation unavailable — weather data could not be fetched. Please try again later.',
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, errorMsg]);
          setShowScenarioPicker(false);
        },
      },
    );
  };

  const handleSend = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isPending || isSimulating) return;

    const userMessage: ChatMessageType = {
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');

    // Detect scenario queries → show inline picker
    if (isScenarioQuery(trimmed)) {
      const promptMsg: ChatMessageType = {
        role: 'assistant',
        content: 'Choose a rainfall scenario to see how it would affect your area:',
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, promptMsg]);
      setShowScenarioPicker(true);
      return;
    }

    sendMessage(
      { message: trimmed, city, conversation_id: conversationId, latitude, longitude },
      {
        onSuccess: (data) => {
          setConversationId(data.conversation_id);
          const assistantMessage: ChatMessageType = {
            role: 'assistant',
            content: data.rate_limited
              ? 'I\'m receiving a lot of requests right now. Please try again in a moment.'
              : data.reply,
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, assistantMessage]);
        },
        onError: () => {
          const errorMessage: ChatMessageType = {
            role: 'assistant',
            content: 'Something went wrong. Please check your connection and try again.',
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, errorMessage]);
        },
      },
    );
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(inputValue);
    }
  };

  const isBusy = isPending || isSimulating;

  return (
    <>
      {/* Backdrop — mobile only, closes panel on tap */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 md:hidden"
          style={{ zIndex: Z.aiPanel - 1 }}
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={cn(
          'fixed flex flex-col bg-card border shadow-2xl',
          // Mobile: full width, slides up from bottom
          'left-0 right-0 bottom-0 rounded-t-2xl',
          // Desktop: 400px side panel anchored above BottomNav equivalent
          'md:left-auto md:right-4 md:bottom-4 md:w-[400px] md:rounded-2xl',
          // Slide transition
          'transition-transform duration-300 ease-in-out',
          isOpen ? 'translate-y-0' : 'translate-y-full md:translate-y-full',
        )}
        style={{
          zIndex: Z.aiPanel,
          height: '70vh',
          maxHeight: '600px',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3 px-4 py-3 border-b rounded-t-2xl md:rounded-t-2xl flex-shrink-0"
          style={{ background: 'linear-gradient(to right, #10b981, #059669)' }}
        >
          <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-bold text-white leading-none">FloodSafe AI</h2>
            <p className="text-[10px] text-white/70 mt-0.5">{city.charAt(0).toUpperCase() + city.slice(1)} — flood intelligence</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 rounded-md flex items-center justify-center hover:bg-white/20 transition-colors text-white flex-shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto px-3 py-3 min-h-0">
          {messages.map((msg, idx) => (
            <ChatMessage key={idx} message={msg} />
          ))}

          {/* Scenario picker — inline after "what if" query */}
          {showScenarioPicker && (
            <div className="flex items-start mb-3">
              <div className="max-w-[85%] space-y-2">
                {SCENARIOS.map((s) => (
                  <button
                    key={s.key}
                    onClick={() => handleScenarioSelect(s.key)}
                    disabled={isSimulating}
                    className="w-full flex items-center gap-2 rounded-xl border border-border px-3 py-2 text-left hover:bg-muted transition-colors disabled:opacity-50"
                  >
                    <CloudRain className="w-4 h-4 text-blue-500 shrink-0" />
                    <div>
                      <span className="text-xs font-medium text-foreground">{s.label}</span>
                      <span className="text-[10px] text-muted-foreground ml-1">({s.sublabel})</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Typing indicator while waiting */}
          {isBusy && (
            <div className="flex items-start mb-3">
              <div className="max-w-[85%] rounded-2xl rounded-bl-sm px-3 py-2 bg-muted flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  {isSimulating ? 'Simulating...' : 'Thinking...'}
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick actions */}
        <div className="px-3 pt-2 pb-1 border-t flex-shrink-0">
          <QuickActions onSelect={(text) => handleSend(text)} />
        </div>

        {/* Input row */}
        <div className="px-3 pb-3 pt-2 flex gap-2 flex-shrink-0">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about flood conditions..."
            disabled={isBusy}
            className={cn(
              'flex-1 h-10 rounded-full border px-4 text-sm',
              'bg-background text-foreground',
              'placeholder:text-muted-foreground',
              'focus:outline-none focus:ring-2 focus:ring-primary/50',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-shadow',
            )}
          />
          <button
            onClick={() => handleSend(inputValue)}
            disabled={isBusy || !inputValue.trim()}
            aria-label="Send message"
            className={cn(
              'w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0',
              'text-white',
              'hover:opacity-90 active:opacity-80',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors',
            )}
            style={{ backgroundColor: '#10b981' }}
          >
            {isBusy ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </>
  );
}
