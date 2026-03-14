import { createPortal } from 'react-dom';
import { useOnboardingBot } from '../../contexts/OnboardingBotContext';
import { X } from 'lucide-react';
import { Z } from '../../constants/z-index';

/**
 * BotCompanion — Floating 48px mascot avatar for the app tour phase.
 *
 * Position: fixed bottom-24 right-4 (clears BottomNav + install banner)
 * Z-index: 115 (above driver.js overlay at 110, below Toaster at 9999)
 * Click: toggles BotTooltip expand/collapse
 * X button: dismisses entire tour
 * Rendered via Portal to document.body.
 */
export function BotCompanion({ onClick }: { onClick: () => void }) {
    const { skipTour, state } = useOnboardingBot();

    if (state.phase !== 'app-tour') return null;

    return createPortal(
        <div
            className="fixed bottom-24 right-4 animate-in fade-in-0 zoom-in-75 duration-300"
            style={{ zIndex: Z.botCompanion }}
        >
            {/* Dismiss X button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    skipTour();
                }}
                className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-white shadow-md border border-gray-200 flex items-center justify-center hover:bg-gray-100 transition-colors"
                style={{ zIndex: Z.botCompanion + 1 }}
                title="Dismiss tour"
            >
                <X className="w-3 h-3 text-gray-500" />
            </button>

            {/* Avatar circle */}
            <button
                onClick={onClick}
                className="relative w-12 h-12 rounded-full bg-blue-500 shadow-lg flex items-center justify-center hover:bg-blue-600 active:scale-95 transition-all cursor-pointer"
            >
                {/* Pulse ring */}
                <span className="absolute inset-0 rounded-full bg-blue-400 animate-ping opacity-20" />
                <span className="text-xl relative">💧</span>
            </button>
        </div>,
        document.body,
    );
}
