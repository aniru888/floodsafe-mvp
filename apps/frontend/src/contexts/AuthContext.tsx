/**
 * Authentication Context for FloodSafe.
 *
 * Provides authentication state and methods throughout the app.
 * Supports Google OAuth and Phone + OTP authentication.
 */

import {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    ReactNode,
} from 'react';
import { TokenStorage } from '../lib/auth/token-storage';
import {
    isFirebaseConfigured,
    setupRecaptcha,
    sendOTP,
    verifyOTP,
    firebaseSignOut,
    cleanupRecaptcha,
    ConfirmationResult,
} from '../lib/firebase';
import { API_BASE_URL } from '../lib/api/config';

// User type matching backend response
export interface AuthUser {
    id: string;
    username: string;
    email: string | null;
    phone: string | null;
    role: string;
    auth_provider: string;
    profile_photo_url: string | null;
    points: number;
    level: number;
    reputation_score: number;
    // Verification status
    email_verified: boolean;
    phone_verified: boolean;
    // Onboarding & City Preference
    city_preference: string | null;
    profile_complete: boolean;
    onboarding_step: number | null;
}

// Auth context type
interface AuthContextType {
    // State
    user: AuthUser | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;

    // Email/Password Auth
    registerWithEmail: (email: string, password: string, username?: string) => Promise<void>;
    loginWithEmail: (email: string, password: string) => Promise<void>;

    // Google Auth
    loginWithGoogle: (idToken: string) => Promise<void>;

    // Phone Auth
    isFirebaseReady: boolean;
    sendPhoneOTP: (phoneNumber: string) => Promise<void>;
    verifyPhoneOTP: (otp: string) => Promise<void>;
    phoneConfirmation: ConfirmationResult | null;

    // Session
    logout: () => Promise<void>;
    refreshSession: () => Promise<boolean>;
    refreshUser: () => Promise<void>;
    clearError: () => void;
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token refresh interval (refresh 1 minute before expiry)
const REFRESH_BUFFER_SECONDS = 60;

interface AuthProviderProps {
    children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [phoneConfirmation, setPhoneConfirmation] = useState<ConfirmationResult | null>(null);

    const isAuthenticated = !!user;
    const isFirebaseReady = isFirebaseConfigured();

    // Clear error
    const clearError = useCallback(() => {
        setError(null);
    }, []);

    // Fetch current user profile
    const fetchUser = useCallback(async (): Promise<AuthUser | null> => {
        const accessToken = TokenStorage.getAccessToken();
        if (!accessToken) return null;

        try {
            const response = await fetch(`${API_BASE_URL}/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            });

            if (!response.ok) {
                if (response.status === 401) {
                    // Token invalid, try refresh
                    const refreshed = await refreshSession();
                    if (refreshed) {
                        return fetchUser(); // Retry with new token
                    }
                }
                return null;
            }

            const userData = await response.json();
            return userData;
        } catch (err) {
            console.error('Error fetching user:', err);
            return null;
        }
    }, []);

    // Refresh session with refresh token
    const refreshSession = useCallback(async (): Promise<boolean> => {
        const refreshToken = TokenStorage.getRefreshToken();
        if (!refreshToken) return false;

        try {
            const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: refreshToken }),
            });

            if (!response.ok) {
                // Refresh token invalid, clear everything
                TokenStorage.clearTokens();
                setUser(null);
                return false;
            }

            const tokens = await response.json();
            TokenStorage.setTokens(tokens.access_token, tokens.refresh_token);

            return true;
        } catch (err) {
            console.error('Error refreshing session:', err);
            TokenStorage.clearTokens();
            setUser(null);
            return false;
        }
    }, []);

    // Initialize auth state on mount
    useEffect(() => {
        const initAuth = async () => {
            setIsLoading(true);

            // Check if we have stored tokens
            if (TokenStorage.hasTokens()) {
                // Check if access token is expired
                if (TokenStorage.isAccessTokenExpired()) {
                    // Try to refresh
                    const refreshed = await refreshSession();
                    if (!refreshed) {
                        setIsLoading(false);
                        return;
                    }
                }

                // Fetch user profile
                const userData = await fetchUser();
                if (userData) {
                    setUser(userData);
                }
            }

            setIsLoading(false);
        };

        initAuth();
    }, [fetchUser, refreshSession]);

    // Set up automatic token refresh
    useEffect(() => {
        if (!isAuthenticated) return;

        const checkAndRefresh = async () => {
            const expiresIn = TokenStorage.getAccessTokenExpiresIn();

            if (expiresIn > 0 && expiresIn <= REFRESH_BUFFER_SECONDS) {
                await refreshSession();
            }
        };

        // Check every 30 seconds
        const interval = setInterval(checkAndRefresh, 30000);

        return () => clearInterval(interval);
    }, [isAuthenticated, refreshSession]);

    // Email/Password - Register
    const registerWithEmail = useCallback(async (email: string, password: string, username?: string) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/auth/register/email`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email,
                    password,
                    username: username || undefined,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Registration failed');
            }

            const tokens = await response.json();
            TokenStorage.setTokens(tokens.access_token, tokens.refresh_token);

            // Fetch user profile
            const userData = await fetchUser();
            if (userData) {
                setUser(userData);
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Registration failed';
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [fetchUser]);

    // Email/Password - Login
    const loginWithEmail = useCallback(async (email: string, password: string) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/auth/login/email`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Invalid email or password');
            }

            const tokens = await response.json();
            TokenStorage.setTokens(tokens.access_token, tokens.refresh_token);

            // Fetch user profile
            const userData = await fetchUser();
            if (userData) {
                setUser(userData);
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Login failed';
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [fetchUser]);

    // Google authentication
    const loginWithGoogle = useCallback(async (idToken: string) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/auth/google`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id_token: idToken }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Google authentication failed');
            }

            const tokens = await response.json();
            TokenStorage.setTokens(tokens.access_token, tokens.refresh_token);

            // Fetch user profile
            const userData = await fetchUser();
            if (userData) {
                setUser(userData);
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Authentication failed';
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [fetchUser]);

    // Phone OTP - Step 1: Send OTP
    const sendPhoneOTP = useCallback(async (phoneNumber: string) => {
        if (!isFirebaseReady) {
            throw new Error('Firebase is not configured. Phone auth is unavailable.');
        }

        setError(null);

        try {
            // Set up reCAPTCHA if not already done
            // The container must exist in the DOM
            const recaptchaContainer = document.getElementById('recaptcha-container');
            if (!recaptchaContainer) {
                throw new Error('reCAPTCHA container not found. Add <div id="recaptcha-container"></div> to your page.');
            }

            setupRecaptcha('recaptcha-container');

            // Send OTP
            const confirmation = await sendOTP(phoneNumber);
            if (confirmation) {
                setPhoneConfirmation(confirmation);
            } else {
                throw new Error('Failed to send OTP');
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to send OTP';
            setError(message);
            throw err;
        }
    }, [isFirebaseReady]);

    // Phone OTP - Step 2: Verify OTP
    const verifyPhoneOTP = useCallback(async (otp: string) => {
        if (!phoneConfirmation) {
            throw new Error('No pending phone verification. Call sendPhoneOTP first.');
        }

        setIsLoading(true);
        setError(null);

        try {
            // Verify with Firebase and get ID token
            const firebaseIdToken = await verifyOTP(phoneConfirmation, otp);

            // Exchange Firebase token for our JWT
            const response = await fetch(`${API_BASE_URL}/auth/phone/verify`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id_token: firebaseIdToken }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Phone verification failed');
            }

            const tokens = await response.json();
            TokenStorage.setTokens(tokens.access_token, tokens.refresh_token);

            // Fetch user profile
            const userData = await fetchUser();
            if (userData) {
                setUser(userData);
            }

            // Clear phone confirmation
            setPhoneConfirmation(null);
            cleanupRecaptcha();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Verification failed';
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [phoneConfirmation, fetchUser]);

    // Refresh user profile (useful when verification status changes)
    const refreshUser = useCallback(async () => {
        const userData = await fetchUser();
        if (userData) {
            setUser(userData);
        }
    }, [fetchUser]);

    // Logout
    const logout = useCallback(async () => {
        setIsLoading(true);

        try {
            const refreshToken = TokenStorage.getRefreshToken();

            if (refreshToken) {
                // Revoke refresh token on server
                await fetch(`${API_BASE_URL}/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ refresh_token: refreshToken }),
                }).catch(() => {
                    // Ignore errors - we're logging out anyway
                });
            }

            // Unregister FCM push token (best-effort, before token is cleared)
            const accessToken = TokenStorage.getAccessToken();
            if (accessToken) {
                await fetch(`${API_BASE_URL}/push/register-token`, {
                    method: 'DELETE',
                    headers: { Authorization: `Bearer ${accessToken}` },
                }).catch(() => {});
            }

            // Sign out from Firebase if used
            await firebaseSignOut().catch(() => {});

            // Clear local state
            TokenStorage.clearTokens();
            setUser(null);
            setPhoneConfirmation(null);
            cleanupRecaptcha();
        } finally {
            setIsLoading(false);
        }
    }, []);

    const value: AuthContextType = {
        user,
        isAuthenticated,
        isLoading,
        error,
        registerWithEmail,
        loginWithEmail,
        loginWithGoogle,
        isFirebaseReady,
        sendPhoneOTP,
        verifyPhoneOTP,
        phoneConfirmation,
        logout,
        refreshSession,
        refreshUser,
        clearError,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

/**
 * Hook to access auth context.
 * Must be used within an AuthProvider.
 */
export function useAuth(): AuthContextType {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}

/**
 * Hook to check if user is authenticated.
 * Useful for conditional rendering.
 */
export function useIsAuthenticated(): boolean {
    const { isAuthenticated } = useAuth();
    return isAuthenticated;
}

/**
 * Hook to get current user.
 * Returns null if not authenticated.
 */
export function useCurrentUser(): AuthUser | null {
    const { user } = useAuth();
    return user;
}
