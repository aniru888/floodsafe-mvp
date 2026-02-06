/**
 * Service Worker: SOS Background Sync Handler
 *
 * Imported into the Workbox-generated SW via importScripts.
 * Handles the 'flush-sos-queue' sync event to send queued SOS
 * messages when connectivity returns — even if the app is closed.
 *
 * IndexedDB access: The SW can read/write IndexedDB directly.
 * API calls: Uses fetch() with auth token from IndexedDB.
 */

// Constants (must match useSOSQueue.ts)
const SOS_DB_NAME = 'floodsafe-sos';
const SOS_DB_VERSION = 1;
const SOS_STORE_NAME = 'sos-queue';
const SOS_MAX_RETRIES = 3;

// API base URL — read from SW scope or default to production
function getApiBaseUrl() {
    // In production, the API URL is the Koyeb backend
    // In dev, it's localhost:8000
    // The SW doesn't have access to import.meta.env, so we check the origin
    const origin = self.location.origin;
    if (origin.includes('localhost') || origin.includes('127.0.0.1')) {
        return 'http://localhost:8000/api';
    }
    return 'https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api';
}

// ═══════════════════════════════════════════════════════════════
// IndexedDB helpers (duplicated here because SW can't import modules)
// ═══════════════════════════════════════════════════════════════

function openSosDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(SOS_DB_NAME, SOS_DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(SOS_STORE_NAME)) {
                const store = db.createObjectStore(SOS_STORE_NAME, { keyPath: 'id' });
                store.createIndex('status', 'status', { unique: false });
                store.createIndex('timestamp', 'timestamp', { unique: false });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function getPendingSosItems(db) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(SOS_STORE_NAME, 'readonly');
        const index = tx.objectStore(SOS_STORE_NAME).index('status');
        const request = index.getAll('queued');
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function updateSosItem(db, id, updates) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(SOS_STORE_NAME, 'readwrite');
        const store = tx.objectStore(SOS_STORE_NAME);
        const getReq = store.get(id);
        getReq.onsuccess = () => {
            const item = getReq.result;
            if (item) {
                Object.assign(item, updates);
                store.put(item);
            }
        };
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

function removeSosItem(db, id) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(SOS_STORE_NAME, 'readwrite');
        tx.objectStore(SOS_STORE_NAME).delete(id);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

// ═══════════════════════════════════════════════════════════════
// Auth token retrieval (from localStorage via IndexedDB or cache)
// ═══════════════════════════════════════════════════════════════

function getAuthToken() {
    // Try to get from the token storage IndexedDB
    // The app stores tokens in localStorage, but SW can't access localStorage.
    // Instead, we'll try to read from a dedicated IndexedDB store.
    // For the initial implementation, we use a simple approach:
    // The main thread caches the token in a known IDB location on each login.
    return new Promise((resolve) => {
        try {
            const request = indexedDB.open('floodsafe-auth', 1);
            request.onupgradeneeded = () => {
                request.result.createObjectStore('tokens', { keyPath: 'key' });
            };
            request.onsuccess = () => {
                const db = request.result;
                const tx = db.transaction('tokens', 'readonly');
                const store = tx.objectStore('tokens');
                const getReq = store.get('access_token');
                getReq.onsuccess = () => {
                    db.close();
                    resolve(getReq.result?.value || null);
                };
                getReq.onerror = () => {
                    db.close();
                    resolve(null);
                };
            };
            request.onerror = () => resolve(null);
        } catch {
            resolve(null);
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// Sync event handler
// ═══════════════════════════════════════════════════════════════

async function flushSosQueue() {
    const db = await openSosDB();
    const pending = await getPendingSosItems(db);

    if (pending.length === 0) {
        db.close();
        return;
    }

    const apiBase = getApiBaseUrl();
    const token = await getAuthToken();

    let sentCount = 0;
    let failedCount = 0;

    for (const item of pending) {
        if (item.retryCount >= SOS_MAX_RETRIES) {
            await updateSosItem(db, item.id, { status: 'failed', error: 'Max retries exceeded' });
            failedCount++;
            continue;
        }

        await updateSosItem(db, item.id, {
            status: 'sending',
            retryCount: (item.retryCount || 0) + 1,
        });

        try {
            const headers = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${apiBase}/sos/send`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    message: item.message,
                    recipients: item.recipients,
                    location: item.location,
                    channel: item.channel,
                }),
            });

            if (response.ok) {
                await removeSosItem(db, item.id);
                sentCount++;
            } else {
                const errorText = await response.text().catch(() => 'Unknown error');
                await updateSosItem(db, item.id, { status: 'queued', error: errorText });
                failedCount++;
            }
        } catch (error) {
            await updateSosItem(db, item.id, {
                status: 'queued',
                error: error.message || 'Network error',
            });
            failedCount++;
        }
    }

    db.close();

    // Notify open clients about sync completion
    const clients = await self.clients.matchAll({ type: 'window' });
    for (const client of clients) {
        client.postMessage({
            type: 'SOS_SYNC_COMPLETE',
            sentCount,
            failedCount,
        });
    }
}

// ═══════════════════════════════════════════════════════════════
// Register sync event listener
// ═══════════════════════════════════════════════════════════════

self.addEventListener('sync', (event) => {
    if (event.tag === 'flush-sos-queue') {
        event.waitUntil(flushSosQueue());
    }
});
