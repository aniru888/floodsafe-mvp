import { useEffect, useRef } from 'react';
import { useOnboardingBot } from '../../contexts/OnboardingBotContext';
import { t } from '../../lib/onboarding-bot/translations';
import { Volume2, VolumeX, X } from 'lucide-react';
import type { OnboardingBotLanguage } from '../../types/onboarding-bot';

/**
 * BotInlineCard — Compact inline helper for the onboarding phase.
 *
 * Renders INSIDE the wizard step card (not floating).
 * Max 80px expanded, 32px collapsed pill.
 * Auto-collapses to pill after 5 seconds.
 * NO spotlight, NO portal — flows in document.
 */
export function BotInlineCard() {
    const {
        state,
        currentStep,
        skipTour,
        setLanguage,
        toggleVoice,
        setCardExpanded,
    } = useOnboardingBot();

    const collapseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Auto-collapse after 5 seconds
    useEffect(() => {
        if (!state.isCardExpanded) return;

        collapseTimerRef.current = setTimeout(() => {
            setCardExpanded(false);
        }, 5000);

        return () => {
            if (collapseTimerRef.current) clearTimeout(collapseTimerRef.current);
        };
    }, [state.isCardExpanded, state.currentStepIndex, setCardExpanded]);

    if (state.phase !== 'onboarding' || state.isDismissed || !currentStep) {
        return null;
    }

    const lang = state.language;
    const title = t(lang, currentStep.title);
    const message = t(lang, currentStep.message);
    const isWelcome = currentStep.id === 'onboarding-welcome';

    // Collapsed pill state
    if (!state.isCardExpanded) {
        return (
            <button
                onClick={() => setCardExpanded(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 mb-3 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-colors"
            >
                <span className="text-sm">💧</span>
                <span>{t(lang, 'bot.tapForTip')}</span>
            </button>
        );
    }

    // Expanded card
    return (
        <div className="mb-3 rounded-lg bg-blue-50 border border-blue-200 p-3 relative animate-in fade-in-0 slide-in-from-top-2 duration-300" style={{ maxHeight: '80px', overflow: 'hidden' }}>
            <div className="flex items-start gap-2">
                {/* Bot avatar */}
                <span className="text-lg flex-shrink-0 mt-0.5">💧</span>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    {isWelcome ? (
                        <div>
                            <p className="text-xs font-medium text-blue-900 leading-tight">{title}</p>
                            <div className="flex gap-1.5 mt-1">
                                <LanguageChip
                                    label={t(lang, 'lang.english')}
                                    active={lang === 'en'}
                                    onClick={() => setLanguage('en')}
                                />
                                <LanguageChip
                                    label={t(lang, 'lang.hindi')}
                                    active={lang === 'hi'}
                                    onClick={() => setLanguage('hi')}
                                />
                                <LanguageChip
                                    label={t(lang, 'lang.indonesian')}
                                    active={lang === 'id'}
                                    onClick={() => setLanguage('id')}
                                />
                            </div>
                        </div>
                    ) : (
                        <p className="text-xs text-blue-800 leading-tight line-clamp-2">{message}</p>
                    )}
                </div>

                {/* Controls */}
                <div className="flex items-center gap-0.5 flex-shrink-0">
                    <button
                        onClick={toggleVoice}
                        className="p-1 rounded text-blue-600 hover:bg-blue-100 transition-colors"
                        title={state.isVoiceEnabled ? 'Mute voice' : 'Enable voice'}
                    >
                        {state.isVoiceEnabled ? (
                            <Volume2 className="w-3.5 h-3.5" />
                        ) : (
                            <VolumeX className="w-3.5 h-3.5" />
                        )}
                    </button>
                    <button
                        onClick={skipTour}
                        className="p-1 rounded text-blue-400 hover:text-blue-600 hover:bg-blue-100 transition-colors"
                        title={t(lang, 'bot.skip')}
                    >
                        <X className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>
        </div>
    );
}

function LanguageChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                active
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-blue-700 border border-blue-300 hover:bg-blue-100'
            }`}
        >
            {label}
        </button>
    );
}
