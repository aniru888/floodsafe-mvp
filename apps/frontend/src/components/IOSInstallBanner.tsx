import { useState, useEffect } from 'react';
import { Share, Plus, X } from 'lucide-react';
import { Button } from './ui/button';

const IOS_INSTALL_DISMISSED_KEY = 'floodsafe_ios_install_dismissed';
const IOS_INSTALL_DISMISSED_EXPIRY = 7 * 24 * 60 * 60 * 1000; // 7 days

/**
 * Detects if the user is on iOS Safari (not in standalone/PWA mode)
 */
function isIOSSafari(): boolean {
    if (typeof window === 'undefined' || typeof navigator === 'undefined') {
        return false;
    }

    const ua = navigator.userAgent;

    // Check if iOS
    const isIOS = /iPad|iPhone|iPod/.test(ua) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

    if (!isIOS) return false;

    // Check if Safari (not Chrome/Firefox/etc on iOS)
    const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|OPiOS|EdgiOS/.test(ua);

    // Check if already in standalone mode (installed as PWA)
    const isStandalone = 'standalone' in navigator && (navigator as Navigator & { standalone?: boolean }).standalone;

    // Also check display-mode media query
    const isDisplayStandalone = window.matchMedia('(display-mode: standalone)').matches;

    return isSafari && !isStandalone && !isDisplayStandalone;
}

/**
 * Check if the banner was recently dismissed
 */
function wasDismissedRecently(): boolean {
    if (typeof localStorage === 'undefined') return false;

    const dismissed = localStorage.getItem(IOS_INSTALL_DISMISSED_KEY);
    if (!dismissed) return false;

    const dismissedTime = parseInt(dismissed, 10);
    const now = Date.now();

    // If more than 7 days have passed, show again
    if (now - dismissedTime > IOS_INSTALL_DISMISSED_EXPIRY) {
        localStorage.removeItem(IOS_INSTALL_DISMISSED_KEY);
        return false;
    }

    return true;
}

/**
 * IOSInstallBanner - Shows iOS-specific install instructions
 *
 * iOS Safari doesn't support the beforeinstallprompt event, so we need to
 * show manual instructions for adding to home screen.
 */
export function IOSInstallBanner() {
    const [showBanner, setShowBanner] = useState(false);
    const [showInstructions, setShowInstructions] = useState(false);

    useEffect(() => {
        // Only show on iOS Safari and if not dismissed recently
        if (isIOSSafari() && !wasDismissedRecently()) {
            // Delay showing the banner to not be intrusive on first load
            const timer = setTimeout(() => {
                setShowBanner(true);
            }, 5000); // Show after 5 seconds

            return () => clearTimeout(timer);
        }
    }, []);

    const handleDismiss = () => {
        setShowBanner(false);
        setShowInstructions(false);
        // Save dismissal time
        localStorage.setItem(IOS_INSTALL_DISMISSED_KEY, Date.now().toString());
    };

    const handleShowInstructions = () => {
        setShowInstructions(true);
    };

    if (!showBanner) return null;

    if (showInstructions) {
        return (
            <div className="fixed inset-0 bg-black/50 z-[200] flex items-end justify-center p-4">
                <div className="bg-card rounded-t-2xl w-full max-w-md p-6 animate-in slide-in-from-bottom-4">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-foreground">
                            Install FloodSafe
                        </h3>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleDismiss}
                            className="h-8 w-8 p-0"
                        >
                            <X className="w-5 h-5" />
                        </Button>
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-start gap-4">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
                                1
                            </div>
                            <div className="flex-1">
                                <p className="text-foreground font-medium">
                                    Tap the Share button
                                </p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Look for <Share className="inline w-4 h-4 mx-1" /> at the bottom of your screen
                                </p>
                            </div>
                        </div>

                        <div className="flex items-start gap-4">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
                                2
                            </div>
                            <div className="flex-1">
                                <p className="text-foreground font-medium">
                                    Scroll down and tap "Add to Home Screen"
                                </p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Look for <Plus className="inline w-4 h-4 mx-1" /> Add to Home Screen
                                </p>
                            </div>
                        </div>

                        <div className="flex items-start gap-4">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
                                3
                            </div>
                            <div className="flex-1">
                                <p className="text-foreground font-medium">
                                    Tap "Add" to install
                                </p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    FloodSafe will appear on your home screen
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="mt-6 flex gap-3">
                        <Button
                            variant="outline"
                            className="flex-1"
                            onClick={handleDismiss}
                        >
                            Maybe later
                        </Button>
                        <Button
                            className="flex-1 bg-primary hover:bg-primary/90"
                            onClick={handleDismiss}
                        >
                            Got it
                        </Button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed bottom-20 left-4 right-4 bg-primary text-primary-foreground p-4 rounded-xl shadow-lg z-50 animate-in slide-in-from-bottom-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center">
                        <img
                            src="/pwa-192x192.png"
                            alt="FloodSafe"
                            className="w-8 h-8 rounded"
                        />
                    </div>
                    <div>
                        <p className="font-medium">Install FloodSafe</p>
                        <p className="text-sm opacity-80">
                            Add to your home screen for quick access
                        </p>
                    </div>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDismiss}
                    className="h-8 w-8 p-0 text-white hover:bg-white/20"
                >
                    <X className="w-4 h-4" />
                </Button>
            </div>
            <div className="flex gap-2 mt-3">
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleShowInstructions}
                    className="flex-1 bg-primary-foreground text-primary hover:bg-primary-foreground/90"
                >
                    <Plus className="w-4 h-4 mr-2" />
                    Install App
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDismiss}
                    className="text-white hover:bg-white/20"
                >
                    Not now
                </Button>
            </div>
        </div>
    );
}
