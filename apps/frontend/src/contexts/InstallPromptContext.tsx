import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

/**
 * Interface for BeforeInstallPromptEvent
 * This event fires when the browser determines the PWA is installable
 */
interface BeforeInstallPromptEvent extends Event {
    readonly platforms: string[];
    readonly userChoice: Promise<{
        outcome: 'accepted' | 'dismissed';
        platform: string;
    }>;
    prompt(): Promise<void>;
}

interface InstallPromptContextType {
    /** Whether the app can be installed (deferred prompt available) */
    canInstall: boolean;
    /** Whether the app is already installed as PWA */
    isInstalled: boolean;
    /** Trigger the native install prompt. Returns true if accepted. */
    promptInstall: () => Promise<boolean>;
    /** Whether the install prompt is currently showing */
    isPrompting: boolean;
}

const InstallPromptContext = createContext<InstallPromptContextType | undefined>(undefined);

interface InstallPromptProviderProps {
    children: ReactNode;
}

/**
 * Check if the app is running as an installed PWA
 */
function checkIfInstalled(): boolean {
    if (typeof window === 'undefined') return false;

    // Check display-mode: standalone
    if (window.matchMedia('(display-mode: standalone)').matches) {
        return true;
    }

    // Check navigator.standalone (iOS)
    if ('standalone' in navigator && (navigator as Navigator & { standalone?: boolean }).standalone) {
        return true;
    }

    return false;
}

/**
 * Check if this is an iOS device (which doesn't support beforeinstallprompt)
 */
function isIOS(): boolean {
    if (typeof navigator === 'undefined') return false;
    const ua = navigator.userAgent;
    return /iPad|iPhone|iPod/.test(ua) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

/**
 * InstallPromptProvider - Handles the beforeinstallprompt event for Android/Desktop
 *
 * The beforeinstallprompt event fires when the browser thinks the user might want
 * to install the PWA. We capture and defer this event so we can trigger it later
 * from our custom UI (banner or settings button).
 *
 * iOS Safari doesn't support this event - see IOSInstallBanner for iOS handling.
 */
export function InstallPromptProvider({ children }: InstallPromptProviderProps) {
    const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
    const [isInstalled, setIsInstalled] = useState(false);
    const [isPrompting, setIsPrompting] = useState(false);

    useEffect(() => {
        // Check if already installed
        setIsInstalled(checkIfInstalled());

        // Skip on iOS (handled separately by IOSInstallBanner)
        if (isIOS()) {
            return;
        }

        // Listen for beforeinstallprompt event
        const handleBeforeInstallPrompt = (e: Event) => {
            // Prevent Chrome's default mini-infobar
            e.preventDefault();
            // Store the event for later use
            setDeferredPrompt(e as BeforeInstallPromptEvent);
            console.log('[PWA] Install prompt captured and deferred');
        };

        // Listen for app installed event
        const handleAppInstalled = () => {
            setIsInstalled(true);
            setDeferredPrompt(null);
            console.log('[PWA] App was installed');
        };

        window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
        window.addEventListener('appinstalled', handleAppInstalled);

        // Also check for display-mode changes (e.g., user opens installed PWA)
        const mediaQuery = window.matchMedia('(display-mode: standalone)');
        const handleDisplayModeChange = () => {
            if (mediaQuery.matches) {
                setIsInstalled(true);
                setDeferredPrompt(null);
            }
        };
        mediaQuery.addEventListener('change', handleDisplayModeChange);

        return () => {
            window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
            window.removeEventListener('appinstalled', handleAppInstalled);
            mediaQuery.removeEventListener('change', handleDisplayModeChange);
        };
    }, []);

    /**
     * Trigger the native install prompt
     * Returns true if the user accepted, false if dismissed
     */
    const promptInstall = useCallback(async (): Promise<boolean> => {
        if (!deferredPrompt) {
            console.warn('[PWA] No deferred prompt available');
            return false;
        }

        setIsPrompting(true);

        try {
            // Show the install prompt
            await deferredPrompt.prompt();

            // Wait for user response
            const { outcome } = await deferredPrompt.userChoice;
            console.log('[PWA] User choice:', outcome);

            // Clear the deferred prompt (can only be used once)
            setDeferredPrompt(null);

            if (outcome === 'accepted') {
                setIsInstalled(true);
                return true;
            }

            return false;
        } catch (error) {
            console.error('[PWA] Error showing install prompt:', error);
            return false;
        } finally {
            setIsPrompting(false);
        }
    }, [deferredPrompt]);

    const value: InstallPromptContextType = {
        canInstall: deferredPrompt !== null && !isInstalled,
        isInstalled,
        promptInstall,
        isPrompting
    };

    return (
        <InstallPromptContext.Provider value={value}>
            {children}
        </InstallPromptContext.Provider>
    );
}

/**
 * Hook to access install prompt functionality
 *
 * @example
 * const { canInstall, promptInstall } = useInstallPrompt();
 *
 * if (canInstall) {
 *   return <button onClick={promptInstall}>Install App</button>
 * }
 */
export function useInstallPrompt(): InstallPromptContextType {
    const context = useContext(InstallPromptContext);
    if (context === undefined) {
        throw new Error('useInstallPrompt must be used within an InstallPromptProvider');
    }
    return context;
}
