import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import type {
    OnboardingBotLanguage,
    TourPhase,
    TourStep,
    OnboardingBotState,
    OnboardingBotContextValue,
} from '../types/onboarding-bot';
import { onboardingSteps, buildAppTourSteps, wizardStepToBotIndex } from '../lib/onboarding-bot/tourSteps';
import { t, languageToVoiceCode } from '../lib/onboarding-bot/translations';
import { useVoiceGuidance } from './VoiceGuidanceContext';
import { useLanguage } from './LanguageContext';
import { fetchJson } from '../lib/api/client';

const OnboardingBotContext = createContext<OnboardingBotContextValue | null>(null);

const LS_DISMISSED = 'floodsafe_bot_dismissed';
const LS_COMPLETED = 'floodsafe_tour_completed';

export function OnboardingBotProvider({ children }: { children: React.ReactNode }) {
    const { speak, stop: stopVoice } = useVoiceGuidance();
    const { language } = useLanguage();
    const navigateRef = useRef<((tab: string) => void) | null>(null);

    const [internalState, setInternalState] = useState<Omit<OnboardingBotState, 'language'>>({
        phase: 'idle',
        currentStepIndex: 0,
        isVoiceEnabled: true,
        isCardExpanded: true,
        isDismissed: localStorage.getItem(LS_DISMISSED) === 'true',
    });

    // Bridge: expose language from LanguageContext as part of state (backward-compatible)
    const state: OnboardingBotState = { ...internalState, language };

    const [appTourSteps, setAppTourSteps] = useState<TourStep[]>([]);

    // Get current step list based on phase
    const steps = state.phase === 'onboarding' ? onboardingSteps
        : state.phase === 'app-tour' ? appTourSteps
        : [];

    const currentStep = steps[state.currentStepIndex] || null;

    // Speak the current step message
    const speakCurrentStep = useCallback((step: TourStep | null, lang: OnboardingBotLanguage) => {
        if (!step) return;
        const voiceKey = step.voiceText || step.message;
        const text = t(lang, voiceKey);
        speak(text, { language: languageToVoiceCode(lang), priority: 'high' });
    }, [speak]);

    // Start a tour phase
    const startTour = useCallback((phase: TourPhase) => {
        if (internalState.isDismissed && phase === 'onboarding') return;

        if (phase === 'app-tour' && navigateRef.current) {
            const built = buildAppTourSteps(navigateRef.current);
            setAppTourSteps(built);
            // Run initial step's onBefore to navigate to the correct screen
            if (built[0]?.onBefore) {
                built[0].onBefore();
            }
        }

        setInternalState(prev => ({
            ...prev,
            phase,
            currentStepIndex: 0,
            isCardExpanded: true,
            isDismissed: false,
        }));
    }, [internalState.isDismissed]);

    // Navigate steps
    const nextStep = useCallback(async () => {
        const nextIndex = state.currentStepIndex + 1;
        const targetSteps = state.phase === 'onboarding' ? onboardingSteps : appTourSteps;

        if (nextIndex >= targetSteps.length) {
            // Tour complete
            stopVoice();
            localStorage.setItem(LS_COMPLETED, 'true');

            // Sync to backend (fire-and-forget)
            try {
                await fetchJson('/api/users/me/tour-complete', { method: 'POST' });
            } catch {
                // Non-critical — localStorage is the primary flag
            }

            setInternalState(prev => ({ ...prev, phase: 'idle', currentStepIndex: 0 }));
            return;
        }

        const nextStepDef = targetSteps[nextIndex];

        // Run onBefore hook
        if (nextStepDef?.onBefore) {
            await nextStepDef.onBefore();
        }

        setInternalState(prev => ({
            ...prev,
            currentStepIndex: nextIndex,
            isCardExpanded: true,
        }));
    }, [state.currentStepIndex, state.phase, appTourSteps, stopVoice]);

    const prevStep = useCallback(async () => {
        if (state.currentStepIndex <= 0) return;
        const prevIndex = state.currentStepIndex - 1;
        const targetSteps = state.phase === 'onboarding' ? onboardingSteps : appTourSteps;
        const prevStepDef = targetSteps[prevIndex];

        if (prevStepDef?.onBefore) {
            await prevStepDef.onBefore();
        }

        setInternalState(prev => ({
            ...prev,
            currentStepIndex: prevIndex,
            isCardExpanded: true,
        }));
    }, [state.currentStepIndex, state.phase, appTourSteps]);

    const skipTour = useCallback(() => {
        stopVoice();
        localStorage.setItem(LS_DISMISSED, 'true');
        setInternalState(prev => ({
            ...prev,
            phase: 'idle',
            isDismissed: true,
            currentStepIndex: 0,
        }));
    }, [stopVoice]);

    const toggleVoice = useCallback(() => {
        setInternalState(prev => {
            if (prev.isVoiceEnabled) {
                stopVoice();
            }
            return { ...prev, isVoiceEnabled: !prev.isVoiceEnabled };
        });
    }, [stopVoice]);

    const setCardExpanded = useCallback((expanded: boolean) => {
        setInternalState(prev => ({ ...prev, isCardExpanded: expanded }));
    }, []);

    const registerNavigation = useCallback((fn: (tab: string) => void) => {
        navigateRef.current = fn;
    }, []);

    // Sync onboarding wizard step with bot step index
    const syncOnboardingStep = useCallback((wizardStep: number) => {
        if (state.phase !== 'onboarding') return;
        const botIndex = wizardStepToBotIndex(wizardStep);
        setInternalState(prev => ({
            ...prev,
            currentStepIndex: botIndex,
            isCardExpanded: true,
        }));
    }, [state.phase]);

    // Speak when step changes (voice enabled)
    useEffect(() => {
        if (state.phase === 'idle' || !state.isVoiceEnabled || !currentStep) return;
        speakCurrentStep(currentStep, language);
    }, [state.currentStepIndex, state.phase, state.isVoiceEnabled, language, currentStep, speakCurrentStep]);

    // Keyboard shortcuts: Escape to skip
    useEffect(() => {
        if (state.phase === 'idle') return;

        const handleKeydown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                skipTour();
            } else if (e.key === 'ArrowRight' && state.phase === 'app-tour') {
                nextStep();
            } else if (e.key === 'ArrowLeft' && state.phase === 'app-tour') {
                prevStep();
            }
        };

        window.addEventListener('keydown', handleKeydown);
        return () => window.removeEventListener('keydown', handleKeydown);
    }, [state.phase, skipTour, nextStep, prevStep]);

    return (
        <OnboardingBotContext.Provider value={{
            state,
            steps,
            currentStep,
            startTour,
            nextStep,
            prevStep,
            skipTour,
            toggleVoice,
            setCardExpanded,
            registerNavigation,
            syncOnboardingStep,
        }}>
            {children}
        </OnboardingBotContext.Provider>
    );
}

export function useOnboardingBot() {
    const context = useContext(OnboardingBotContext);
    if (!context) {
        throw new Error('useOnboardingBot must be used within OnboardingBotProvider');
    }
    return context;
}
