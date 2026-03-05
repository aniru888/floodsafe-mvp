import type { TourStep } from '../../types/onboarding-bot';

/**
 * Onboarding phase steps — inline card, NO spotlight overlay.
 * These map 1:1 with the OnboardingScreen wizard steps (1-based indexing).
 * Step index 0 = welcome/language picker (shown before wizard step 1).
 */
export const onboardingSteps: TourStep[] = [
    {
        id: 'onboarding-welcome',
        phase: 'onboarding',
        title: 'onboarding.welcome.title',
        message: 'onboarding.welcome.message',
        useSpotlight: false,
    },
    {
        id: 'onboarding-city',
        phase: 'onboarding',
        title: 'onboarding.city.title',
        message: 'onboarding.city.message',
        useSpotlight: false,
    },
    {
        id: 'onboarding-profile',
        phase: 'onboarding',
        title: 'onboarding.profile.title',
        message: 'onboarding.profile.message',
        useSpotlight: false,
    },
    {
        id: 'onboarding-watch-areas',
        phase: 'onboarding',
        title: 'onboarding.watchAreas.title',
        message: 'onboarding.watchAreas.message',
        useSpotlight: false,
    },
    {
        id: 'onboarding-routes',
        phase: 'onboarding',
        title: 'onboarding.routes.title',
        message: 'onboarding.routes.message',
        useSpotlight: false,
    },
    {
        id: 'onboarding-complete',
        phase: 'onboarding',
        title: 'onboarding.complete.title',
        message: 'onboarding.complete.message',
        useSpotlight: false,
    },
];

/**
 * Build app tour steps with navigation callbacks.
 * Must be called with `navigateTo` function that maps to App.tsx setActiveTab.
 */
export function buildAppTourSteps(navigateTo: (tab: string) => void): TourStep[] {
    const wait = (ms: number) => new Promise(r => setTimeout(r, ms));

    return [
        // ── Home Screen ────────────────────────────────────────
        {
            id: 'tour-home-intro',
            phase: 'app-tour',
            title: 'tour.home.title',
            message: 'tour.home.message',
            useSpotlight: false, // Companion-only intro
            position: 'center',
            onBefore: () => navigateTo('home'),
        },
        {
            id: 'tour-map-preview',
            phase: 'app-tour',
            element: '[data-tour-id="home-map-preview"]',
            title: 'tour.mapPreview.title',
            message: 'tour.mapPreview.message',
            useSpotlight: false,
            position: 'top',
        },
        {
            id: 'tour-recent-reports',
            phase: 'app-tour',
            element: '[data-tour-id="recent-reports"]',
            title: 'tour.recentReports.title',
            message: 'tour.recentReports.message',
            useSpotlight: false,
            position: 'top',
        },
        {
            id: 'tour-ai-insights',
            phase: 'app-tour',
            element: '[data-tour-id="ai-insights"]',
            title: 'tour.aiInsights.title',
            message: 'tour.aiInsights.message',
            useSpotlight: false,
            position: 'top',
        },
        {
            id: 'tour-emergency-contacts',
            phase: 'app-tour',
            element: '[data-tour-id="emergency-contacts"]',
            title: 'tour.emergencyContacts.title',
            message: 'tour.emergencyContacts.message',
            useSpotlight: false,
            position: 'top',
        },

        // ── Map Screen ─────────────────────────────────────────
        {
            id: 'tour-map-intro',
            phase: 'app-tour',
            title: 'tour.map.title',
            message: 'tour.map.message',
            useSpotlight: false,
            position: 'center',
            onBefore: async () => {
                navigateTo('map');
                await wait(400); // Wait for map render
            },
        },
        {
            id: 'tour-map-layers',
            phase: 'app-tour',
            element: '[data-tour-id="map-layers"]',
            title: 'tour.mapLayers.title',
            message: 'tour.mapLayers.message',
            useSpotlight: false,
            position: 'bottom',
        },
        {
            id: 'tour-routing',
            phase: 'app-tour',
            element: '[data-tour-id="routing-panel"]',
            title: 'tour.routing.title',
            message: 'tour.routing.message',
            useSpotlight: false,
            position: 'bottom',
        },

        // ── Report Screen ──────────────────────────────────────
        {
            id: 'tour-report',
            phase: 'app-tour',
            element: '[data-tour-id="report-form"]',
            title: 'tour.report.title',
            message: 'tour.report.message',
            useSpotlight: false,
            position: 'bottom',
            onBefore: async () => {
                navigateTo('report');
                await wait(300);
            },
        },

        // ── Alerts Screen ──────────────────────────────────────
        {
            id: 'tour-alerts',
            phase: 'app-tour',
            element: '[data-tour-id="unified-alerts"]',
            title: 'tour.alerts.title',
            message: 'tour.alerts.message',
            useSpotlight: false,
            position: 'bottom',
            onBefore: async () => {
                navigateTo('alerts');
                await wait(300);
            },
        },

        // ── Profile Screen (completion) ────────────────────────
        {
            id: 'tour-profile',
            phase: 'app-tour',
            element: '[data-tour-id="gamification-badges"]',
            title: 'tour.profile.title',
            message: 'tour.profile.message',
            useSpotlight: false,
            position: 'bottom',
            onBefore: async () => {
                navigateTo('profile');
                await wait(300);
            },
        },
    ];
}

/**
 * Map onboarding wizard step (1-5) to bot step index (0-5).
 * Index 0 = welcome (shown on wizard step 1), then 1:1 mapping.
 */
export function wizardStepToBotIndex(wizardStep: number): number {
    // Welcome shows on step 1, then city=1, profile=2, etc.
    return Math.max(0, Math.min(wizardStep, onboardingSteps.length - 1));
}
