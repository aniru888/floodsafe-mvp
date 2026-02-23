/**
 * Firebase configuration for FloodSafe Phone Authentication.
 *
 * Firebase Phone Auth (free tier: 10,000 verifications/month)
 *
 * Setup instructions:
 * 1. Create a Firebase project at https://console.firebase.google.com
 * 2. Enable Phone Authentication in Authentication > Sign-in method
 * 3. Add your domain to authorized domains
 * 4. Copy the config values to your .env file
 */

import { initializeApp, FirebaseApp } from 'firebase/app';
import {
    getAuth,
    Auth,
    RecaptchaVerifier,
    signInWithPhoneNumber,
    ConfirmationResult,
} from 'firebase/auth';
import { getMessaging, getToken, onMessage, type Messaging } from 'firebase/messaging';

// Firebase configuration from environment variables
const firebaseConfig = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
    appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
};

// Singleton instances
let firebaseApp: FirebaseApp | null = null;
let firebaseAuth: Auth | null = null;
let recaptchaVerifier: RecaptchaVerifier | null = null;

/**
 * Check if Firebase is configured.
 */
export function isFirebaseConfigured(): boolean {
    return !!(
        firebaseConfig.apiKey &&
        firebaseConfig.authDomain &&
        firebaseConfig.projectId
    );
}

/**
 * Initialize Firebase app (singleton).
 */
export function getFirebaseApp(): FirebaseApp | null {
    if (!isFirebaseConfigured()) {
        console.warn('Firebase is not configured. Phone auth will not work.');
        return null;
    }

    if (!firebaseApp) {
        firebaseApp = initializeApp(firebaseConfig);
    }

    return firebaseApp;
}

/**
 * Get Firebase Auth instance (singleton).
 */
export function getFirebaseAuth(): Auth | null {
    const app = getFirebaseApp();
    if (!app) return null;

    if (!firebaseAuth) {
        firebaseAuth = getAuth(app);
    }

    return firebaseAuth;
}

/**
 * Set up reCAPTCHA verifier for phone auth.
 * Must be called before sending OTP.
 *
 * @param containerId - ID of the HTML element to render reCAPTCHA in
 * @param onSuccess - Callback when reCAPTCHA is solved
 * @param onError - Callback when reCAPTCHA fails
 */
export function setupRecaptcha(
    containerId: string,
    onSuccess?: () => void,
    onError?: (error: Error) => void
): RecaptchaVerifier | null {
    const auth = getFirebaseAuth();
    if (!auth) {
        onError?.(new Error('Firebase not configured'));
        return null;
    }

    // Clean up existing verifier
    if (recaptchaVerifier) {
        recaptchaVerifier.clear();
        recaptchaVerifier = null;
    }

    try {
        recaptchaVerifier = new RecaptchaVerifier(auth, containerId, {
            size: 'invisible', // Use invisible reCAPTCHA
            callback: () => {
                onSuccess?.();
            },
            'expired-callback': () => {
                onError?.(new Error('reCAPTCHA expired'));
            },
        });

        return recaptchaVerifier;
    } catch (error) {
        onError?.(error as Error);
        return null;
    }
}

/**
 * Send OTP to phone number.
 *
 * @param phoneNumber - Phone number in E.164 format (e.g., +919876543210)
 * @returns ConfirmationResult to verify OTP later
 */
export async function sendOTP(phoneNumber: string): Promise<ConfirmationResult | null> {
    const auth = getFirebaseAuth();
    if (!auth) {
        throw new Error('Firebase not configured. Cannot send OTP.');
    }

    if (!recaptchaVerifier) {
        throw new Error('reCAPTCHA not set up. Call setupRecaptcha first.');
    }

    // Ensure phone number is in E.164 format
    let formattedPhone = phoneNumber.trim();
    if (!formattedPhone.startsWith('+')) {
        // Assume India if no country code
        formattedPhone = '+91' + formattedPhone.replace(/^0+/, '');
    }

    try {
        const confirmationResult = await signInWithPhoneNumber(
            auth,
            formattedPhone,
            recaptchaVerifier
        );

        return confirmationResult;
    } catch (error) {
        console.error('Error sending OTP:', error);
        throw error;
    }
}

/**
 * Verify OTP and get Firebase ID token.
 *
 * @param confirmationResult - Result from sendOTP
 * @param otp - The 6-digit OTP code
 * @returns Firebase ID token for backend verification
 */
export async function verifyOTP(
    confirmationResult: ConfirmationResult,
    otp: string
): Promise<string> {
    try {
        const userCredential = await confirmationResult.confirm(otp);
        const idToken = await userCredential.user.getIdToken();

        return idToken;
    } catch (error) {
        console.error('Error verifying OTP:', error);
        throw error;
    }
}

/**
 * Sign out from Firebase.
 * Call this when logging out from your app.
 */
export async function firebaseSignOut(): Promise<void> {
    const auth = getFirebaseAuth();
    if (auth) {
        await auth.signOut();
    }
}

/**
 * Clean up reCAPTCHA verifier.
 * Call this when unmounting the component.
 */
export function cleanupRecaptcha(): void {
    if (recaptchaVerifier) {
        recaptchaVerifier.clear();
        recaptchaVerifier = null;
    }
}

// ── Firebase Cloud Messaging (Push Notifications) ──

let messagingInstance: Messaging | null = null;

/**
 * Get Firebase Cloud Messaging instance.
 * Returns null if browser doesn't support notifications or firebase isn't initialized.
 */
export function getFirebaseMessaging(): Messaging | null {
    if (messagingInstance) return messagingInstance;

    const app = getFirebaseApp();
    if (!app) return null;

    // Check browser support
    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
        console.warn('Push notifications not supported in this browser');
        return null;
    }

    try {
        messagingInstance = getMessaging(app);
        return messagingInstance;
    } catch (error) {
        console.error('Failed to initialize Firebase Messaging:', error);
        return null;
    }
}

export { getToken, onMessage };

// Export types for consumers
export type { ConfirmationResult, Messaging };
