import { useState, useEffect, useCallback } from 'react';
import { WifiOff, Wifi, RefreshCw, X } from 'lucide-react';
import { Button } from './ui/button';
import { useQueryClient } from '@tanstack/react-query';

const LAST_SYNC_KEY = 'floodsafe_last_sync';

/**
 * Formats a relative time string (e.g., "2 minutes ago")
 */
function formatRelativeTime(date: Date): string {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);

    if (diffSec < 60) return 'Just now';
    if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`;
    if (diffHour < 24) return `${diffHour} hour${diffHour === 1 ? '' : 's'} ago`;
    return date.toLocaleDateString();
}

/**
 * Hook to detect online/offline status with proper event handling
 */
export function useOnlineStatus() {
    const [isOnline, setIsOnline] = useState(() =>
        typeof navigator !== 'undefined' ? navigator.onLine : true
    );
    const [lastSyncTime, setLastSyncTime] = useState<Date | null>(() => {
        if (typeof localStorage === 'undefined') return null;
        const saved = localStorage.getItem(LAST_SYNC_KEY);
        return saved ? new Date(saved) : null;
    });

    // Update last sync time when going online
    const updateLastSync = useCallback(() => {
        const now = new Date();
        setLastSyncTime(now);
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem(LAST_SYNC_KEY, now.toISOString());
        }
    }, []);

    useEffect(() => {
        const handleOnline = () => {
            setIsOnline(true);
            updateLastSync();
        };

        const handleOffline = () => {
            setIsOnline(false);
        };

        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

        // Initial sync time if online
        if (navigator.onLine && !lastSyncTime) {
            updateLastSync();
        }

        return () => {
            window.removeEventListener('online', handleOnline);
            window.removeEventListener('offline', handleOffline);
        };
    }, [updateLastSync, lastSyncTime]);

    return { isOnline, lastSyncTime, updateLastSync };
}

interface OfflineIndicatorProps {
    /** Optional: Use external control instead of auto-detection */
    isOffline?: boolean;
    /** Optional: Custom last update string */
    lastUpdate?: string;
    /** Optional: Custom retry handler */
    onRetry?: () => void;
}

/**
 * OfflineIndicator - Shows a banner when the user is offline
 *
 * Can be used in two modes:
 * 1. Auto-detection (default): Uses navigator.onLine and event listeners
 * 2. Controlled mode: Pass isOffline prop to control visibility externally
 */
export function OfflineIndicator({
    isOffline: externalIsOffline,
    lastUpdate: externalLastUpdate,
    onRetry: externalOnRetry
}: OfflineIndicatorProps) {
    const queryClient = useQueryClient();
    const { isOnline, lastSyncTime, updateLastSync } = useOnlineStatus();
    const [dismissed, setDismissed] = useState(false);
    const [isRetrying, setIsRetrying] = useState(false);
    const [showReconnected, setShowReconnected] = useState(false);
    const [wasOffline, setWasOffline] = useState(false);

    // Use external control if provided, otherwise use auto-detection
    const isOffline = externalIsOffline !== undefined ? externalIsOffline : !isOnline;

    // Track transition from offline to online
    useEffect(() => {
        if (wasOffline && !isOffline) {
            setShowReconnected(true);
            setDismissed(false);
            // Auto-hide reconnected message after 3 seconds
            const timer = setTimeout(() => {
                setShowReconnected(false);
            }, 3000);
            return () => clearTimeout(timer);
        }
        setWasOffline(isOffline);
    }, [isOffline, wasOffline]);

    // Reset dismissed state when going offline again
    useEffect(() => {
        if (isOffline) {
            setDismissed(false);
            setShowReconnected(false);
        }
    }, [isOffline]);

    const handleRetry = useCallback(async () => {
        setIsRetrying(true);
        try {
            if (externalOnRetry) {
                externalOnRetry();
            } else {
                // Invalidate all queries to trigger refetch
                await queryClient.invalidateQueries();
                updateLastSync();
            }
        } finally {
            setIsRetrying(false);
        }
    }, [externalOnRetry, queryClient, updateLastSync]);

    const lastUpdateText = externalLastUpdate ??
        (lastSyncTime ? formatRelativeTime(lastSyncTime) : 'Unknown');

    // Show reconnected message
    if (showReconnected && !isOffline) {
        return (
            <div className="fixed bottom-20 left-4 right-4 bg-green-600 text-white p-3 rounded-lg shadow-lg z-50 flex items-center justify-between animate-in slide-in-from-bottom-4">
                <div className="flex items-center gap-3">
                    <Wifi className="w-5 h-5" />
                    <p className="text-sm font-medium">Back online</p>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowReconnected(false)}
                    className="h-8 text-white hover:bg-green-700"
                >
                    <X className="w-4 h-4" />
                </Button>
            </div>
        );
    }

    // Don't show if online or dismissed
    if (!isOffline || dismissed) return null;

    return (
        <div className="fixed bottom-20 left-4 right-4 bg-foreground text-background p-3 rounded-lg shadow-lg z-50 flex items-center justify-between animate-in slide-in-from-bottom-4">
            <div className="flex items-center gap-3">
                <WifiOff className="w-5 h-5 text-red-400" />
                <div>
                    <p className="text-sm font-medium">You are offline</p>
                    <p className="text-xs text-muted-foreground/60">Last sync: {lastUpdateText}</p>
                </div>
            </div>
            <div className="flex items-center gap-2">
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleRetry}
                    disabled={isRetrying}
                    className="h-8"
                >
                    <RefreshCw className={`w-3 h-3 mr-2 ${isRetrying ? 'animate-spin' : ''}`} />
                    {isRetrying ? 'Retrying...' : 'Retry'}
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDismissed(true)}
                    className="h-8 text-muted-foreground/60 hover:text-white"
                >
                    <X className="w-4 h-4" />
                </Button>
            </div>
        </div>
    );
}
