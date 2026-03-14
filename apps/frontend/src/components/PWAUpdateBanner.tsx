import { useEffect } from 'react';
import { useRegisterSW } from 'virtual:pwa-register/react';
import { Download, X } from 'lucide-react';
import { Button } from './ui/button';

/**
 * PWAUpdateBanner - Handles PWA service worker registration and shows offline-ready toast
 *
 * With 'autoUpdate' strategy, the service worker automatically updates without user action.
 * This component now only shows a brief "offline ready" toast when the PWA is cached.
 *
 * Update checks happen every 15 minutes for faster deployment visibility.
 */
export function PWAUpdateBanner() {
    const {
        offlineReady: [offlineReady, setOfflineReady],
    } = useRegisterSW({
        onRegisteredSW(swUrl, registration) {
            // Check for updates every 15 minutes (faster than default 1 hour)
            if (registration) {
                setInterval(() => {
                    registration.update();
                }, 15 * 60 * 1000);
            }

            // Auto-reload when new service worker takes control
            // This ensures new deploys take effect on first refresh (not requiring two)
            let refreshing = false;
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                if (refreshing) return; // Prevent infinite reload loops
                refreshing = true;
                console.log('[PWA] New service worker active — reloading for fresh assets');
                window.location.reload();
            });
        },
        onRegisterError(error) {
            console.error('[PWA] Service worker registration failed:', error);
        },
    });

    // Auto-dismiss offline ready message after 5 seconds
    useEffect(() => {
        if (offlineReady) {
            const timer = setTimeout(() => {
                setOfflineReady(false);
            }, 5000);
            return () => clearTimeout(timer);
        }
    }, [offlineReady, setOfflineReady]);

    // Show offline ready toast
    if (offlineReady) {
        return (
            <div className="fixed top-16 md:top-4 left-4 right-4 md:left-auto md:right-4 md:w-80 bg-green-600 text-white p-3 rounded-lg shadow-lg z-50 flex items-center justify-between animate-in slide-in-from-top-4">
                <div className="flex items-center gap-3">
                    <Download className="w-5 h-5" />
                    <div>
                        <p className="text-sm font-medium">Ready for offline use</p>
                        <p className="text-xs opacity-80">FloodSafe works without internet</p>
                    </div>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setOfflineReady(false)}
                    className="h-8 text-white hover:bg-green-700"
                >
                    <X className="w-4 h-4" />
                </Button>
            </div>
        );
    }

    // With autoUpdate, no manual update banner needed - SW updates automatically on page load
    return null;
}
