/* Firebase Cloud Messaging background handler.
 * This runs in a separate SW scope from Workbox.
 * It handles push notifications when the app tab is closed/background.
 *
 * NOTE: Firebase config must be updated here when env vars change.
 * These values come from Firebase Console > Project Settings > General.
 */
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');

firebase.initializeApp({
    apiKey: self.__FIREBASE_CONFIG__?.apiKey || '',
    authDomain: self.__FIREBASE_CONFIG__?.authDomain || 'gen-lang-client-0669818939.firebaseapp.com',
    projectId: self.__FIREBASE_CONFIG__?.projectId || 'gen-lang-client-0669818939',
    storageBucket: self.__FIREBASE_CONFIG__?.storageBucket || 'gen-lang-client-0669818939.appspot.com',
    messagingSenderId: self.__FIREBASE_CONFIG__?.messagingSenderId || '',
    appId: self.__FIREBASE_CONFIG__?.appId || '',
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
