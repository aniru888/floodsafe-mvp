import { createPortal } from 'react-dom';
import { useOnboardingBot } from '../../contexts/OnboardingBotContext';
import { useLanguage } from '../../contexts/LanguageContext';
import { t } from '../../lib/onboarding-bot/translations';
import { Volume2, VolumeX, ChevronLeft, ChevronRight } from 'lucide-react';
import type { OnboardingBotLanguage } from '../../types/onboarding-bot';

const LANGUAGES: { code: OnboardingBotLanguage; label: string }[] = [
    { code: 'en', label: 'EN' },
    { code: 'hi', label: 'HI' },
    { code: 'id', label: 'ID' },
];

/**
 * BotTooltip — Chat bubble with controls for the app tour phase.
 *
 * Position: anchored above the companion on mobile (bottom-40 right-4).
 * Max dimensions: 280px wide, 180px tall (desktop) / 160px (mobile).
 * Controls: Next (primary), Back (if >step 0), Skip (ghost), voice toggle, language selector.
 * Rendered via Portal to document.body.
 */
export function BotTooltip({ visible }: { visible: boolean }) {
    const {
        state,
        steps,
        currentStep,
        nextStep,
        prevStep,
        skipTour,
        toggleVoice,
    } = useOnboardingBot();
    const { language: lang, setLanguage } = useLanguage();

    if (state.phase !== 'app-tour' || !visible || !currentStep) return null;
    const title = t(lang, currentStep.title);
    const message = t(lang, currentStep.message);
    const stepNum = state.currentStepIndex + 1;
    const totalSteps = steps.length;
    const isLast = state.currentStepIndex === steps.length - 1;
    const isFirst = state.currentStepIndex === 0;

    return createPortal(
        <div
            className="fixed bottom-40 right-4 w-[280px] max-h-[180px] sm:max-h-[180px] bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden animate-in fade-in-0 slide-in-from-bottom-4 duration-300"
            style={{ zIndex: 115 }}
        >
            {/* Header */}
            <div className="px-3 pt-3 pb-1">
                <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-sm flex-shrink-0">💧</span>
                        <h3 className="text-sm font-semibold text-gray-900 leading-tight truncate">{title}</h3>
                    </div>
                    <div className="flex items-center gap-0.5 flex-shrink-0">
                        {/* Language selector */}
                        {LANGUAGES.map(({ code, label }) => (
                            <button
                                key={code}
                                onClick={() => setLanguage(code)}
                                className={`px-2 py-1 rounded text-[11px] font-semibold transition-colors ${
                                    lang === code
                                        ? 'bg-blue-500 text-white'
                                        : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                                }`}
                                title={t(lang, `lang.${code === 'en' ? 'english' : code === 'hi' ? 'hindi' : 'indonesian'}`)}
                            >
                                {label}
                            </button>
                        ))}
                        {/* Voice toggle */}
                        <button
                            onClick={toggleVoice}
                            className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                            title={state.isVoiceEnabled ? 'Mute' : 'Unmute'}
                        >
                            {state.isVoiceEnabled ? (
                                <Volume2 className="w-3.5 h-3.5" />
                            ) : (
                                <VolumeX className="w-3.5 h-3.5" />
                            )}
                        </button>
                    </div>
                </div>
                <p className="text-xs text-gray-600 mt-1 leading-relaxed line-clamp-3">{message}</p>
            </div>

            {/* Footer: progress + controls */}
            <div className="px-3 py-2 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
                <span className="text-[10px] text-gray-400 font-medium">
                    {stepNum} {t(lang, 'bot.stepOf')} {totalSteps}
                </span>

                <div className="flex items-center gap-1">
                    <button
                        onClick={skipTour}
                        className="px-2 py-1 text-[10px] text-gray-400 hover:text-gray-600 transition-colors"
                    >
                        {t(lang, 'bot.skip')}
                    </button>

                    {!isFirst && (
                        <button
                            onClick={prevStep}
                            className="p-1 rounded text-gray-500 hover:bg-gray-200 transition-colors"
                        >
                            <ChevronLeft className="w-3.5 h-3.5" />
                        </button>
                    )}

                    <button
                        onClick={nextStep}
                        className="flex items-center gap-0.5 px-2.5 py-1 rounded-md bg-blue-500 text-white text-[11px] font-medium hover:bg-blue-600 active:scale-95 transition-all"
                    >
                        {isLast ? t(lang, 'bot.done') : t(lang, 'bot.next')}
                        {!isLast && <ChevronRight className="w-3 h-3" />}
                    </button>
                </div>
            </div>
        </div>,
        document.body,
    );
}
