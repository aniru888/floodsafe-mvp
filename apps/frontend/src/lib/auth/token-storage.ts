/**
 * Secure token storage for FloodSafe authentication.
 *
 * Tokens are stored in memory by default (most secure against XSS).
 * LocalStorage is used as fallback for persistence across page refreshes.
 *
 * Security considerations:
 * - Access tokens are short-lived (15 min)
 * - Refresh tokens enable silent re-authentication
 * - Memory storage prevents XSS access to tokens
 * - Token is also cached in IndexedDB for service worker Background Sync access
 */

import { syncTokenToSW, clearSWTokenCache } from './sw-token-cache';

// In-memory storage (most secure, but lost on page refresh)
let accessToken: string | null = null;
let refreshToken: string | null = null;

// Storage keys for localStorage persistence
const ACCESS_TOKEN_KEY = 'floodsafe_access_token';
const REFRESH_TOKEN_KEY = 'floodsafe_refresh_token';

/**
 * Decode JWT payload without verification (for reading expiry).
 * WARNING: This does not verify the token - only use for client-side logic.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;

        const payload = parts[1];
        // Add padding for base64 decoding
        const padded = payload + '='.repeat((4 - payload.length % 4) % 4);
        const decoded = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));

        return JSON.parse(decoded);
    } catch {
        return null;
    }
}

export const TokenStorage = {
    /**
     * Get the current access token.
     * Tries memory first, then localStorage.
     */
    getAccessToken(): string | null {
        if (accessToken) return accessToken;

        // Try localStorage fallback
        const stored = localStorage.getItem(ACCESS_TOKEN_KEY);
        if (stored) {
            accessToken = stored;
            return stored;
        }

        return null;
    },

    /**
     * Set the access token.
     * Stores in both memory and localStorage.
     */
    setAccessToken(token: string): void {
        accessToken = token;
        localStorage.setItem(ACCESS_TOKEN_KEY, token);
        // Cache in IndexedDB for service worker Background Sync (SOS queue)
        syncTokenToSW(token).catch(() => {});
    },

    /**
     * Get the current refresh token.
     * Tries memory first, then localStorage.
     */
    getRefreshToken(): string | null {
        if (refreshToken) return refreshToken;

        // Try localStorage fallback
        const stored = localStorage.getItem(REFRESH_TOKEN_KEY);
        if (stored) {
            refreshToken = stored;
            return stored;
        }

        return null;
    },

    /**
     * Set the refresh token.
     * Stores in both memory and localStorage.
     */
    setRefreshToken(token: string): void {
        refreshToken = token;
        localStorage.setItem(REFRESH_TOKEN_KEY, token);
    },

    /**
     * Clear all stored tokens.
     * Call this on logout.
     */
    clearTokens(): void {
        accessToken = null;
        refreshToken = null;
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        // Clear IndexedDB token cache for service worker
        clearSWTokenCache().catch(() => {});
    },

    /**
     * Check if the access token is expired.
     * Returns true if expired or no token exists.
     */
    isAccessTokenExpired(): boolean {
        const token = this.getAccessToken();
        if (!token) return true;

        const payload = decodeJwtPayload(token);
        if (!payload || typeof payload.exp !== 'number') return true;

        // Add 30 second buffer to account for clock skew
        const expiryTime = payload.exp * 1000; // Convert to milliseconds
        const now = Date.now();
        const buffer = 30 * 1000; // 30 seconds

        return now >= (expiryTime - buffer);
    },

    /**
     * Check if we have any tokens stored (might need refresh).
     */
    hasTokens(): boolean {
        return !!(this.getAccessToken() || this.getRefreshToken());
    },

    /**
     * Get token expiry time in seconds from now.
     * Returns 0 if no token or already expired.
     */
    getAccessTokenExpiresIn(): number {
        const token = this.getAccessToken();
        if (!token) return 0;

        const payload = decodeJwtPayload(token);
        if (!payload || typeof payload.exp !== 'number') return 0;

        const expiryTime = payload.exp * 1000;
        const remaining = expiryTime - Date.now();

        return Math.max(0, Math.floor(remaining / 1000));
    },

    /**
     * Store both tokens at once (convenience method).
     */
    setTokens(access: string, refresh: string): void {
        this.setAccessToken(access);
        this.setRefreshToken(refresh);
    },
};

export default TokenStorage;
