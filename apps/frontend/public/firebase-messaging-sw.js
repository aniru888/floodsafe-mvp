/* Firebase Cloud Messaging background handler.
 * This runs in a separate SW scope from Workbox.
 * It handles push notifications when the app tab is closed/background.
 *
 * IMPORTANT: These Firebase config values are public identifiers (NOT secrets).
 * They are the same values visible in any browser's source tab.
 * When Firebase is fully configured, update apiKey, messagingSenderId, and appId
 * with values from Firebase Console > Project Settings > General > Your apps.
 *
 * NOTE: Service workers cannot access import.meta.env or window objects.
 * Config must be hardcoded here — this is the Firebase-recommended pattern.
 */
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');

firebase.initializeApp({
    apiKey: 'AIzaSyDx22KzFutYSJgATaYiq-6oNVCti7S-KTw',
    authDomain: 'gen-lang-client-0669818939.firebaseapp.com',
    projectId: 'gen-lang-client-0669818939',
    storageBucket: 'gen-lang-client-0669818939.firebasestorage.app',
    messagingSenderId: '967834121532',
    appId: '1:967834121532:web:1206e23fcffb1528789a39',
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
    const title = payload.notification?.title || 'FloodSafe Alert';
    const options = {
        body: payload.notification?.body || 'You have a new flood alert',
        icon: '/pwa-192x192.png',
        badge: '/pwa-192x192.png',
        data: payload.data || {},
        tag: 'floodsafe-alert',  // Replaces previous notification with same tag
    };

    self.registration.showNotification(title, options);
});

// Handle notification click — open the app
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const url = event.notification.data?.click_url || '/';
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Focus existing window if open
                for (const client of clientList) {
                    if (client.url.includes('floodsafe') && 'focus' in client) {
                        return client.focus();
                    }
                }
                // Otherwise open new window
                return self.clients.openWindow(url);
            })
    );
});
