import { useCallback, useEffect, useState } from 'react';
import { Capacitor } from '@capacitor/core';
import { getFirebaseMessaging, getToken, onMessage } from '../lib/firebase';
import { fetchJson } from '../lib/api/client';

const VAPID_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY;

export function usePushNotifications() {
    const [permission, setPermission] = useState<NotificationPermission>(
        'Notification' in window ? Notification.permission : 'denied'
    );
    const [token, setToken] = useState<string | null>(null);

    const registerToken = useCallback(async (fcmToken: string) => {
        try {
            await fetchJson('/push/register-token', {
                method: 'POST',
                body: JSON.stringify({ token: fcmToken }),
            });
            setToken(fcmToken);
        } catch (error) {
            console.error('Failed to register FCM token:', error);
        }
    }, []);

    const requestPermission = useCallback(async () => {
        if (Capacitor.isNativePlatform()) {
            // Native path — use Capacitor push plugin (future task)
            console.log('Native push: use @capacitor/push-notifications');
            return;
        }

        // Web path — Firebase Messaging
        const messaging = getFirebaseMessaging();
        if (!messaging) return;

        try {
            const perm = await Notification.requestPermission();
            setPermission(perm);

            if (perm === 'granted' && VAPID_KEY) {
                const fcmToken = await getToken(messaging, { vapidKey: VAPID_KEY });
                if (fcmToken) {
                    await registerToken(fcmToken);
                }
            }
        } catch (error) {
            console.error('Failed to get push permission:', error);
        }
    }, [registerToken]);

    // Listen for foreground messages
    useEffect(() => {
        if (Capacitor.isNativePlatform()) return;

        const messaging = getFirebaseMessaging();
        if (!messaging) return;

        const unsubscribe = onMessage(messaging, (payload) => {
            console.log('Foreground push received:', payload);
            if (payload.notification) {
                new Notification(
                    payload.notification.title || 'FloodSafe Alert',
                    { body: payload.notification.body }
                );
            }
        });

        return () => unsubscribe();
    }, []);

    // Re-register token on every app open (Firebase recommendation)
    useEffect(() => {
        if (permission === 'granted' && VAPID_KEY && !Capacitor.isNativePlatform()) {
            const messaging = getFirebaseMessaging();
            if (messaging) {
                getToken(messaging, { vapidKey: VAPID_KEY })
                    .then((t) => { if (t) registerToken(t); })
                    .catch(console.error);
            }
        }
    }, [permission, registerToken]);

    return { permission, token, requestPermission };
}
