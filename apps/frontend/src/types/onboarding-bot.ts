export type OnboardingBotLanguage = 'en' | 'hi' | 'id';

export type TourPhase = 'onboarding' | 'app-tour' | 'idle';

export interface TourStep {
    id: string;
    phase: TourPhase;
    /** CSS selector for spotlight target (app tour only) */
    element?: string;
    /** Translation key for title */
    title: string;
    /** Translation key for message body */
    message: string;
    /** Translation key for voice text (fallback to message) */
    voiceText?: string;
    /** Tooltip position relative to spotlit element */
    position?: 'top' | 'bottom' | 'left' | 'right' | 'center';
    /** Whether to use driver.js spotlight overlay (false for onboarding, true for app tour) */
    useSpotlight: boolean;
    /** Pause advancement until user action */
    waitForAction?: boolean;
    /** Hook before step activates (e.g. navigate to a screen) */
    onBefore?: () => void | Promise<void>;
    /** Hook after step deactivates */
    onAfter?: () => void | Promise<void>;
}

export interface OnboardingBotState {
    phase: TourPhase;
    language: OnboardingBotLanguage;
    currentStepIndex: number;
    isVoiceEnabled: boolean;
    isCardExpanded: boolean;
    isDismissed: boolean;
}

export interface OnboardingBotContextValue {
    state: OnboardingBotState;
    steps: TourStep[];
    currentStep: TourStep | null;
    startTour: (phase: TourPhase, language?: OnboardingBotLanguage) => void;
    nextStep: () => void;
    prevStep: () => void;
    skipTour: () => void;
    setLanguage: (lang: OnboardingBotLanguage) => void;
    toggleVoice: () => void;
    setCardExpanded: (expanded: boolean) => void;
    registerNavigation: (fn: (tab: string) => void) => void;
    /** Sync onboarding wizard step with bot */
    syncOnboardingStep: (wizardStep: number) => void;
}
