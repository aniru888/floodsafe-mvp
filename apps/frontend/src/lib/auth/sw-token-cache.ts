/**
 * Service Worker Token Cache
 *
 * Caches the auth access token in IndexedDB so the service worker
 * can access it for Background Sync operations (like SOS flush).
 *
 * localStorage is NOT accessible from service workers, so we duplicate
 * the token to IndexedDB on every login/refresh.
 *
 * Call syncTokenToSW() after:
 * - Successful login
 * - Token refresh
 * - Session restore
 */

const AUTH_DB_NAME = 'floodsafe-auth';
const AUTH_DB_VERSION = 1;
const AUTH_STORE_NAME = 'tokens';

function openAuthDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(AUTH_DB_NAME, AUTH_DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(AUTH_STORE_NAME)) {
                db.createObjectStore(AUTH_STORE_NAME, { keyPath: 'key' });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

/**
 * Cache the access token in IndexedDB for service worker access.
 * Call after login, token refresh, or session restore.
 */
export async function syncTokenToSW(accessToken: string | null): Promise<void> {
    try {
        const db = await openAuthDB();
        const tx = db.transaction(AUTH_STORE_NAME, 'readwrite');
        const store = tx.objectStore(AUTH_STORE_NAME);

        if (accessToken) {
            store.put({ key: 'access_token', value: accessToken });
        } else {
            store.delete('access_token');
        }

        await new Promise<void>((resolve, reject) => {
            tx.oncomplete = () => { db.close(); resolve(); };
            tx.onerror = () => { db.close(); reject(tx.error); };
        });
    } catch {
        // IndexedDB not available — SW won't be able to send authenticated requests
        // This is acceptable since SW Background Sync is a best-effort enhancement
    }
}

/**
 * Clear the cached token (call on logout).
 */
export async function clearSWTokenCache(): Promise<void> {
    await syncTokenToSW(null);
}
