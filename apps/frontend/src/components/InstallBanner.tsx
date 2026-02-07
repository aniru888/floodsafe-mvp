import { useState, useEffect } from 'react';
import { Download, X, Smartphone } from 'lucide-react';
import { Button } from './ui/button';
import { useInstallPrompt } from '../contexts/InstallPromptContext';
import { toast } from 'sonner';

const INSTALL_BANNER_DISMISSED_KEY = 'floodsafe_install_banner_dismissed';
const INSTALL_BANNER_DISMISSED_EXPIRY = 7 * 24 * 60 * 60 * 1000; // 7 days

/**
 * Check if the banner was recently dismissed
 */
function wasDismissedRecently(): boolean {
    if (typeof localStorage === 'undefined') return false;

    const dismissed = localStorage.getItem(INSTALL_BANNER_DISMISSED_KEY);
    if (!dismissed) return false;

    const dismissedTime = parseInt(dismissed, 10);
    const now = Date.now();

    // If more than 7 days have passed, show again
    if (now - dismissedTime > INSTALL_BANNER_DISMISSED_EXPIRY) {
        localStorage.removeItem(INSTALL_BANNER_DISMISSED_KEY);
        return false;
    }

    return true;
}

/**
 * Detect if this is an iOS device (handled separately by IOSInstallBanner)
 */
function isIOS(): boolean {
    if (typeof navigator === 'undefined') return false;
    const ua = navigator.userAgent;
    return /iPad|iPhone|iPod/.test(ua) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

/**
 * InstallBanner - Shows install prompt for Android and Desktop browsers
 *
 * This component uses the InstallPromptContext to trigger the native
 * browser install prompt. For iOS, see IOSInstallBanner.
 *
 * Features:
 * - Auto-shows after 5 seconds when install is available
 * - 7-day dismissal window
 * - Triggers native Chrome/Edge/Firefox install dialog
 */
export function InstallBanner() {
    const { canInstall, promptInstall, isPrompting, isInstalled } = useInstallPrompt();
    const [showBanner, setShowBanner] = useState(false);

    useEffect(() => {
        // Don't show on iOS (handled by IOSInstallBanner)
        if (isIOS()) {
            return;
        }

        // Don't show if already installed
        if (isInstalled) {
            return;
        }

        // Don't show if can't install (no deferred prompt)
        if (!canInstall) {
            return;
        }

        // Don't show if dismissed recently
        if (wasDismissedRecently()) {
            return;
        }

        // Delay showing the banner to not be intrusive on first load
        const timer = setTimeout(() => {
            setShowBanner(true);
        }, 5000); // Show after 5 seconds

        return () => clearTimeout(timer);
    }, [canInstall, isInstalled]);

    const handleDismiss = () => {
        setShowBanner(false);
        // Save dismissal time
        localStorage.setItem(INSTALL_BANNER_DISMISSED_KEY, Date.now().toString());
    };

    const handleInstall = async () => {
        const accepted = await promptInstall();
        if (accepted) {
            toast.success('FloodSafe installed! Check your apps.', { duration: 4000 });
            setShowBanner(false);
        } else {
            // User dismissed, but don't hide banner immediately
            // They might change their mind
        }
    };

    if (!showBanner || !canInstall) return null;

    return (
        <div className="fixed bottom-20 left-4 right-4 bg-primary text-primary-foreground p-4 rounded-xl shadow-lg z-50 animate-in slide-in-from-bottom-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center">
                        <img
                            src="/pwa-192x192.png"
                            alt="FloodSafe"
                            className="w-8 h-8 rounded"
                            onError={(e) => {
                                // Fallback icon if image fails to load
                                (e.target as HTMLImageElement).style.display = 'none';
                            }}
                        />
                        <Smartphone className="w-6 h-6 text-white/80 hidden first:block" />
                    </div>
                    <div>
                        <p className="font-medium">Install FloodSafe</p>
                        <p className="text-sm opacity-80">
                            Get quick access and offline support
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
                    onClick={handleInstall}
                    disabled={isPrompting}
                    className="flex-1 bg-primary-foreground text-primary hover:bg-primary-foreground/90"
                >
                    <Download className="w-4 h-4 mr-2" />
                    {isPrompting ? 'Installing...' : 'Install App'}
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
