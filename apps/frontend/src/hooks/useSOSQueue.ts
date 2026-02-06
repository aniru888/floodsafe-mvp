/**
 * useSOSQueue — Offline-first SOS message queue using IndexedDB.
 *
 * Queues SOS messages when offline, auto-sends when connectivity returns.
 * Uses Background Sync API if available, falls back to online event listener.
 *
 * Flow:
 *   1. User taps SOS → queueSOS() saves to IndexedDB
 *   2. If online → flushQueue() sends immediately via /api/sos/send
 *   3. If offline → registers Background Sync (SW retries when online)
 *   4. Fallback: 'online' event listener triggers flushQueue()
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'sonner';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface SOSRecipient {
    phone: string;
    name: string;
}

export interface SOSQueueItem {
    id: string;
    message: string;
    recipients: SOSRecipient[];
    location: { lat: number; lng: number } | null;
    channel: 'sms' | 'whatsapp';
    timestamp: number;
    status: 'queued' | 'sending' | 'sent' | 'failed';
    error?: string;
    retryCount: number;
}

interface SOSQueueHook {
    /** Queue an SOS message (works offline) */
    queueSOS: (
        message: string,
        recipients: SOSRecipient[],
        location: { lat: number; lng: number } | null,
        channel?: 'sms' | 'whatsapp'
    ) => Promise<void>;
    /** Number of messages waiting to be sent */
    pendingCount: number;
    /** Manually flush the queue (sends all pending messages) */
    flushQueue: () => Promise<void>;
    /** Whether a flush is currently in progress */
    isFlushing: boolean;
    /** Timestamp of last successful send */
    lastSentAt: Date | null;
}

// ═══════════════════════════════════════════════════════════════
// IndexedDB Operations
// ═══════════════════════════════════════════════════════════════

const DB_NAME = 'floodsafe-sos';
const DB_VERSION = 1;
const STORE_NAME = 'sos-queue';
const MAX_QUEUE_SIZE = 50;
const MAX_RETRIES = 3;
const SYNC_TAG = 'flush-sos-queue';

function openDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                store.createIndex('status', 'status', { unique: false });
                store.createIndex('timestamp', 'timestamp', { unique: false });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function addToQueue(item: SOSQueueItem): Promise<void> {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).put(item);
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => { db.close(); reject(tx.error); };
    });
}

async function getPendingItems(): Promise<SOSQueueItem[]> {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const index = store.index('status');
        const request = index.getAll('queued');
        request.onsuccess = () => { db.close(); resolve(request.result); };
        request.onerror = () => { db.close(); reject(request.error); };
    });
}

async function updateItemStatus(
    id: string,
    status: SOSQueueItem['status'],
    error?: string
): Promise<void> {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const getReq = store.get(id);
        getReq.onsuccess = () => {
            const item = getReq.result;
            if (item) {
                item.status = status;
                if (error) item.error = error;
                if (status === 'sending') item.retryCount = (item.retryCount || 0) + 1;
                store.put(item);
            }
        };
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => { db.close(); reject(tx.error); };
    });
}

async function getQueueCount(): Promise<number> {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const index = tx.objectStore(STORE_NAME).index('status');
        const request = index.count('queued');
        request.onsuccess = () => { db.close(); resolve(request.result); };
        request.onerror = () => { db.close(); reject(request.error); };
    });
}

async function removeItem(id: string): Promise<void> {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).delete(id);
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => { db.close(); reject(tx.error); };
    });
}

// ═══════════════════════════════════════════════════════════════
// Background Sync Registration
// ═══════════════════════════════════════════════════════════════

async function registerBackgroundSync(): Promise<boolean> {
    try {
        const registration = await navigator.serviceWorker?.ready;
        if (registration && 'sync' in registration) {
            await (registration as ServiceWorkerRegistration & {
                sync: { register: (tag: string) => Promise<void> };
            }).sync.register(SYNC_TAG);
            return true;
        }
    } catch {
        // Background Sync not supported — fall back to online event
    }
    return false;
}

// ═══════════════════════════════════════════════════════════════
// Generate unique ID
// ═══════════════════════════════════════════════════════════════

function generateId(): string {
    return `sos-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// ═══════════════════════════════════════════════════════════════
// Hook
// ═══════════════════════════════════════════════════════════════

export function useSOSQueue(): SOSQueueHook {
    const [pendingCount, setPendingCount] = useState(0);
    const [isFlushing, setIsFlushing] = useState(false);
    const [lastSentAt, setLastSentAt] = useState<Date | null>(null);
    const flushingRef = useRef(false);

    // Refresh pending count
    const refreshCount = useCallback(async () => {
        try {
            const count = await getQueueCount();
            setPendingCount(count);
        } catch {
            // IndexedDB might not be available
        }
    }, []);

    // Load initial count
    useEffect(() => {
        refreshCount();
    }, [refreshCount]);

    // Flush queue — send all pending messages to backend
    const flushQueue = useCallback(async () => {
        if (flushingRef.current || !navigator.onLine) return;
        flushingRef.current = true;
        setIsFlushing(true);

        try {
            const pending = await getPendingItems();
            if (pending.length === 0) return;

            // Import API client dynamically to avoid circular deps
            const { fetchJson } = await import('../lib/api/client');

            let sentCount = 0;
            let failedCount = 0;

            for (const item of pending) {
                // Skip items that have exceeded retry limit
                if (item.retryCount >= MAX_RETRIES) {
                    await updateItemStatus(item.id, 'failed', 'Max retries exceeded');
                    failedCount++;
                    continue;
                }

                await updateItemStatus(item.id, 'sending');

                try {
                    await fetchJson('/sos/send', {
                        method: 'POST',
                        body: JSON.stringify({
                            message: item.message,
                            recipients: item.recipients,
                            location: item.location,
                            channel: item.channel,
                        }),
                    });

                    // Success — remove from queue
                    await removeItem(item.id);
                    sentCount++;
                } catch (error) {
                    const errorMsg = error instanceof Error ? error.message : 'Unknown error';
                    await updateItemStatus(item.id, 'queued', errorMsg);
                    failedCount++;
                }
            }

            if (sentCount > 0) {
                setLastSentAt(new Date());
                toast.success(
                    `SOS alert sent to ${sentCount} contact group${sentCount > 1 ? 's' : ''}`,
                    { id: 'sos-sent' }
                );
            }

            if (failedCount > 0) {
                toast.error(
                    `${failedCount} SOS message${failedCount > 1 ? 's' : ''} failed to send. Will retry.`,
                    { id: 'sos-failed' }
                );
            }
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Queue flush failed';
            toast.error(`SOS delivery error: ${msg}`, { id: 'sos-flush-error' });
        } finally {
            flushingRef.current = false;
            setIsFlushing(false);
            await refreshCount();
        }
    }, [refreshCount]);

    // Auto-flush when coming back online
    useEffect(() => {
        const handleOnline = () => {
            flushQueue();
        };

        window.addEventListener('online', handleOnline);
        return () => window.removeEventListener('online', handleOnline);
    }, [flushQueue]);

    // Listen for SW messages (Background Sync completion notifications)
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            if (event.data?.type === 'SOS_SYNC_COMPLETE') {
                refreshCount();
                if (event.data.sentCount > 0) {
                    setLastSentAt(new Date());
                }
            }
        };

        navigator.serviceWorker?.addEventListener('message', handleMessage);
        return () => {
            navigator.serviceWorker?.removeEventListener('message', handleMessage);
        };
    }, [refreshCount]);

    // Queue an SOS message
    const queueSOS = useCallback(async (
        message: string,
        recipients: SOSRecipient[],
        location: { lat: number; lng: number } | null,
        channel: 'sms' | 'whatsapp' = 'sms'
    ): Promise<void> => {
        const item: SOSQueueItem = {
            id: generateId(),
            message,
            recipients,
            location,
            channel,
            timestamp: Date.now(),
            status: 'queued',
            retryCount: 0,
        };

        // Enforce queue size limit
        const currentCount = await getQueueCount();
        if (currentCount >= MAX_QUEUE_SIZE) {
            toast.error('SOS queue is full. Please wait for pending messages to send.', {
                id: 'sos-queue-full',
            });
            return;
        }

        await addToQueue(item);
        await refreshCount();

        if (navigator.onLine) {
            // Online — send immediately
            await flushQueue();
        } else {
            // Offline — register Background Sync + show queued toast
            const synced = await registerBackgroundSync();
            toast.info(
                synced
                    ? 'SOS queued — will send automatically when online'
                    : 'SOS queued — will send when you reconnect',
                { id: 'sos-queued', duration: 5000 }
            );
        }
    }, [flushQueue, refreshCount]);

    return {
        queueSOS,
        pendingCount,
        flushQueue,
        isFlushing,
        lastSentAt,
    };
}
