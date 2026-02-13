import { useEffect, useRef } from 'react';
import { driver, type DriveStep, type Driver, type Config } from 'driver.js';
import 'driver.js/dist/driver.css';
import { useOnboardingBot } from '../../contexts/OnboardingBotContext';

const DRIVER_CONFIG: Config = {
    animate: true,
    overlayOpacity: 0.4,
    showButtons: [],
    disableActiveInteraction: false,
    allowClose: true,
    overlayColor: '#000',
    popoverClass: 'hidden',
    overlayClickBehavior: 'nextStep',
};

/**
 * BotSpotlight — driver.js wrapper for element highlighting.
 *
 * ONLY used during app-tour phase (NEVER during onboarding).
 * Highlights the element specified by currentStep.element CSS selector.
 * Uses driver.js with hidden default popover (we use BotTooltip instead).
 *
 * Features:
 * - Element wait: retries querySelector every 100ms up to 2s, then skips
 * - Resize handling: driver.refresh() on orientation change (debounced)
 * - Overlay opacity: 0.4 (lighter to keep context visible)
 * - User can still interact with spotlit element (disableActiveInteraction: false)
 */
export function BotSpotlight() {
    const { state, currentStep } = useOnboardingBot();
    const driverRef = useRef<Driver | null>(null);
    const resizeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Cleanup polling interval helper
    const clearPollInterval = () => {
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
        }
    };

    // Initialize driver instance
    useEffect(() => {
        if (state.phase !== 'app-tour') {
            if (driverRef.current) {
                driverRef.current.destroy();
                driverRef.current = null;
            }
            return;
        }

        driverRef.current = driver(DRIVER_CONFIG);

        return () => {
            driverRef.current?.destroy();
            driverRef.current = null;
            clearPollInterval();
        };
    }, [state.phase]);

    // Highlight current step element
    useEffect(() => {
        if (state.phase !== 'app-tour' || !driverRef.current) return;

        // Clear any in-flight polling from previous step
        clearPollInterval();

        if (!currentStep || !currentStep.useSpotlight || !currentStep.element) {
            // No spotlight for this step — destroy active highlight, re-init
            driverRef.current.destroy();
            driverRef.current = driver(DRIVER_CONFIG);
            return;
        }

        const selector = currentStep.element;

        // Check immediately
        const el = document.querySelector(selector);
        if (el) {
            highlightElement(selector);
            return;
        }

        // Poll for element (100ms intervals, max 2s)
        let elapsed = 0;
        pollIntervalRef.current = setInterval(() => {
            elapsed += 100;
            const found = document.querySelector(selector);
            if (found) {
                clearPollInterval();
                highlightElement(selector);
            } else if (elapsed >= 2000) {
                clearPollInterval();
                // Element not found — skip silently
            }
        }, 100);

        function highlightElement(sel: string) {
            if (!driverRef.current) return;
            const step: DriveStep = {
                element: sel,
                popover: {
                    title: '',
                    description: '',
                    popoverClass: 'hidden',
                },
            };
            driverRef.current.highlight(step);
        }

        return () => clearPollInterval();
    }, [state.phase, state.currentStepIndex, currentStep]);

    // Handle resize/orientation change
    useEffect(() => {
        if (state.phase !== 'app-tour') return;

        const handleResize = () => {
            if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current);
            resizeTimerRef.current = setTimeout(() => {
                driverRef.current?.refresh();
            }, 300);
        };

        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
            if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current);
        };
    }, [state.phase]);

    return null;
}
