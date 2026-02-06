/**
 * SOSButton — Offline-capable SOS emergency alert button.
 *
 * Sends SOS messages to Safety Circle members + emergency contacts via SMS/WhatsApp.
 * Works offline: messages queue in IndexedDB and send automatically when back online.
 *
 * Used in:
 * - EmergencyContactsModal (top of modal, above phone numbers)
 * - Potentially HomeScreen (quick action)
 */

import { useState, useCallback } from 'react';
import { Radio, Loader2, CheckCircle, WifiOff } from 'lucide-react';
import { toast } from 'sonner';
import { useSOSQueue, type SOSRecipient } from '../hooks/useSOSQueue';
import { useAuth } from '../contexts/AuthContext';
import { useLocationTracking } from '../contexts/LocationTrackingContext';
import { useMyCircles } from '../lib/api/hooks';
import { useOnlineStatus } from './OfflineIndicator';
import { cn } from '../lib/utils';

interface SOSButtonProps {
    /** Additional CSS classes */
    className?: string;
    /** Compact mode for inline use (e.g., HomeScreen quick action) */
    compact?: boolean;
}

/**
 * Gather SOS recipients from Safety Circles.
 * Returns phone+name pairs for all circle members with phone numbers.
 */
function getCircleRecipients(circles: Array<{ members?: Array<{ phone: string | null; display_name: string | null }> }> | undefined): SOSRecipient[] {
    if (!circles) return [];

    const seen = new Set<string>();
    const recipients: SOSRecipient[] = [];

    for (const circle of circles) {
        if (!circle.members) continue;
        for (const member of circle.members) {
            if (member.phone && !seen.has(member.phone)) {
                seen.add(member.phone);
                recipients.push({
                    phone: member.phone,
                    name: member.display_name || 'Circle member',
                });
            }
        }
    }

    return recipients;
}

export function SOSButton({ className, compact = false }: SOSButtonProps) {
    const { user } = useAuth();
    const { state: locationState } = useLocationTracking();
    const currentPosition = locationState.currentPosition;
    const { data: circles } = useMyCircles();
    const { queueSOS, pendingCount, isFlushing } = useSOSQueue();
    const { isOnline } = useOnlineStatus();
    const [sending, setSending] = useState(false);
    const [sent, setSent] = useState(false);

    const handleSOS = useCallback(async () => {
        if (sending || sent) return;

        // Gather recipients from Safety Circles
        const recipients = getCircleRecipients(circles as Array<{ members?: Array<{ phone: string | null; display_name: string | null }> }>);

        if (recipients.length === 0) {
            toast.error(
                'No contacts to alert. Add members with phone numbers to your Safety Circles first.',
                { id: 'sos-no-recipients' }
            );
            return;
        }

        setSending(true);

        try {
            const userName = user?.username || 'A FloodSafe user';
            const locationText = currentPosition
                ? `Location: ${currentPosition.lat.toFixed(5)}, ${currentPosition.lng.toFixed(5)}`
                : 'Location unavailable';
            const timestamp = new Date().toLocaleString();

            const message = `SOS from ${userName} — Flooding emergency! ${locationText}. Sent ${timestamp}. This is an automated alert from FloodSafe.`;

            await queueSOS(
                message,
                recipients,
                currentPosition,
                'sms'
            );

            setSent(true);
            // Reset sent state after 5 seconds
            setTimeout(() => setSent(false), 5000);
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Failed to queue SOS';
            toast.error(msg, { id: 'sos-error' });
        } finally {
            setSending(false);
        }
    }, [sending, sent, circles, user, currentPosition, queueSOS]);

    if (compact) {
        return (
            <button
                onClick={handleSOS}
                disabled={sending}
                className={cn(
                    'relative flex items-center gap-2 px-4 py-2 rounded-full font-semibold text-sm transition-all',
                    sent
                        ? 'bg-green-500 text-white'
                        : 'bg-red-500 text-white hover:bg-red-600 active:bg-red-700',
                    sending && 'opacity-70 cursor-not-allowed',
                    className
                )}
            >
                {sending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                ) : sent ? (
                    <CheckCircle className="w-4 h-4" />
                ) : (
                    <Radio className="w-4 h-4" />
                )}
                {sent ? 'SOS Sent' : 'Send SOS'}
                {pendingCount > 0 && !sent && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 bg-yellow-400 text-black text-xs rounded-full flex items-center justify-center font-bold">
                        {pendingCount}
                    </span>
                )}
            </button>
        );
    }

    return (
        <div className={cn('space-y-2', className)}>
            <button
                onClick={handleSOS}
                disabled={sending}
                className={cn(
                    'w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all min-h-[88px]',
                    sent
                        ? 'bg-green-50 border-green-300'
                        : 'bg-red-50 border-red-300 hover:bg-red-100 active:bg-red-200',
                    sending && 'opacity-70 cursor-not-allowed',
                    'shadow-sm hover:shadow-md'
                )}
            >
                {/* Icon */}
                <div className={cn(
                    'w-14 h-14 rounded-full flex items-center justify-center flex-shrink-0',
                    sent ? 'bg-green-500' : 'bg-red-500'
                )}>
                    {sending ? (
                        <Loader2 className="w-7 h-7 text-white animate-spin" />
                    ) : sent ? (
                        <CheckCircle className="w-7 h-7 text-white" />
                    ) : (
                        <Radio className="w-7 h-7 text-white" />
                    )}
                </div>

                {/* Text */}
                <div className="flex-1 text-left">
                    <div className={cn(
                        'font-bold text-lg',
                        sent ? 'text-green-700' : 'text-red-700'
                    )}>
                        {sending ? 'Sending SOS...' : sent ? 'SOS Alert Sent' : 'Send SOS Alert'}
                    </div>
                    <div className="text-sm text-gray-600">
                        {sent
                            ? `Alert sent to ${getCircleRecipients(circles as Array<{ members?: Array<{ phone: string | null; display_name: string | null }> }>).length} contacts`
                            : 'Alert all Safety Circle contacts via SMS'
                        }
                    </div>
                </div>

                {/* Status badge */}
                {!isOnline && !sent && (
                    <div className="flex items-center gap-1 px-2 py-1 bg-yellow-100 rounded-full flex-shrink-0">
                        <WifiOff className="w-3 h-3 text-yellow-700" />
                        <span className="text-xs font-medium text-yellow-700">Offline</span>
                    </div>
                )}

                {pendingCount > 0 && !sent && (
                    <div className="flex items-center gap-1 px-2 py-1 bg-yellow-100 rounded-full flex-shrink-0">
                        <span className="text-xs font-medium text-yellow-700">
                            {pendingCount} queued
                        </span>
                    </div>
                )}
            </button>

            {/* Offline explanation */}
            {!isOnline && (
                <p className="text-xs text-gray-500 text-center px-2">
                    You&apos;re offline. SOS will queue and send automatically when you reconnect.
                </p>
            )}
        </div>
    );
}
