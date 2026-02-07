/**
 * Login Screen for FloodSafe.
 *
 * "Civic Authority" design: Full-width dark brand bar at top for strong brand
 * presence, photo as contextual atmosphere (not hero), clean form below.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { AlertCircle, Loader2, Shield, Phone, ArrowRight, ArrowLeft, Check, Eye, EyeOff } from 'lucide-react';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

interface LoginScreenProps {
    onLoginSuccess?: () => void;
}

declare global {
    interface Window {
        google?: {
            accounts: {
                id: {
                    initialize: (config: {
                        client_id: string;
                        callback: (response: { credential: string }) => void;
                        auto_select?: boolean;
                        context?: string;
                    }) => void;
                    renderButton: (
                        element: HTMLElement,
                        options: {
                            theme?: 'outline' | 'filled_blue' | 'filled_black';
                            size?: 'large' | 'medium' | 'small';
                            width?: number;
                            text?: 'signin_with' | 'signin' | 'continue_with' | 'signup_with';
                            shape?: 'rectangular' | 'pill' | 'circle' | 'square';
                            logo_alignment?: 'left' | 'center';
                        }
                    ) => void;
                    prompt: () => void;
                };
            };
        };
    }
}

export function LoginScreen({ onLoginSuccess }: LoginScreenProps) {
    const { loginWithGoogle, registerWithEmail, loginWithEmail, isLoading, error, clearError } = useAuth();

    const [authMethod, setAuthMethod] = useState<'email' | 'phone'>('email');
    const [localError, setLocalError] = useState<string | null>(null);
    const [scriptStatus, setScriptStatus] = useState<'loading' | 'ready' | 'error'>('loading');
    const googleButtonRef = useRef<HTMLDivElement>(null);
    const initAttempted = useRef(false);

    // Email state
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isSignUp, setIsSignUp] = useState(false);

    // Phone state
    const [phoneNumber, setPhoneNumber] = useState('');
    const [countryCode, setCountryCode] = useState('+91');
    const [otpStep, setOtpStep] = useState(false);
    const [otp, setOtp] = useState(['', '', '', '', '', '']);
    const [countdown, setCountdown] = useState(0);
    const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

    useEffect(() => {
        clearError();
        setLocalError(null);
    }, [clearError, authMethod]);

    // ── Google Sign-In setup ──
    const handleGoogleCallback = useCallback(async (response: { credential: string }) => {
        try {
            setLocalError(null);
            await loginWithGoogle(response.credential);
            onLoginSuccess?.();
        } catch (err) {
            setLocalError(err instanceof Error ? err.message : 'Google sign-in failed');
        }
    }, [loginWithGoogle, onLoginSuccess]);

    const initializeGoogleSignIn = useCallback(() => {
        if (!window.google || !googleButtonRef.current || initAttempted.current) return;
        initAttempted.current = true;
        try {
            window.google.accounts.id.initialize({
                client_id: GOOGLE_CLIENT_ID,
                callback: handleGoogleCallback,
                auto_select: false,
                context: 'signin',
            });
            googleButtonRef.current.innerHTML = '';
            window.google.accounts.id.renderButton(googleButtonRef.current, {
                theme: 'outline',
                size: 'large',
                width: 300,
                text: 'signin_with',
                shape: 'rectangular',
                logo_alignment: 'left',
            });
        } catch {
            setScriptStatus('error');
            setLocalError('Failed to initialize Google Sign-In');
        }
    }, [handleGoogleCallback]);

    useEffect(() => {
        if (!GOOGLE_CLIENT_ID) {
            setScriptStatus('error');
            setLocalError('Google Sign-In is not configured');
            return;
        }
        if (window.google?.accounts?.id) {
            setScriptStatus('ready');
            return;
        }
        const existingScript = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
        if (existingScript) {
            const checkGoogle = setInterval(() => {
                if (window.google?.accounts?.id) { clearInterval(checkGoogle); setScriptStatus('ready'); }
            }, 100);
            setTimeout(() => { clearInterval(checkGoogle); if (!window.google?.accounts?.id) setScriptStatus('error'); }, 10000);
            return;
        }
        const script = document.createElement('script');
        script.src = 'https://accounts.google.com/gsi/client';
        script.async = true;
        script.defer = true;
        script.onload = () => {
            const checkGoogle = setInterval(() => {
                if (window.google?.accounts?.id) { clearInterval(checkGoogle); setScriptStatus('ready'); }
            }, 50);
            setTimeout(() => { clearInterval(checkGoogle); if (!window.google?.accounts?.id) setScriptStatus('error'); }, 5000);
        };
        script.onerror = () => setScriptStatus('error');
        document.head.appendChild(script);
    }, []);

    useEffect(() => {
        if (scriptStatus === 'ready' && googleButtonRef.current && !initAttempted.current) {
            initializeGoogleSignIn();
        }
    }, [scriptStatus, initializeGoogleSignIn]);

    useEffect(() => {
        if (authMethod === 'email' && scriptStatus === 'ready' && googleButtonRef.current) {
            const timer = setTimeout(() => {
                if (googleButtonRef.current && window.google?.accounts?.id) {
                    try {
                        window.google.accounts.id.initialize({
                            client_id: GOOGLE_CLIENT_ID,
                            callback: handleGoogleCallback,
                            auto_select: false,
                            context: 'signin',
                        });
                        googleButtonRef.current.innerHTML = '';
                        window.google.accounts.id.renderButton(googleButtonRef.current, {
                            theme: 'outline',
                            size: 'large',
                            width: 300,
                            text: 'signin_with',
                            shape: 'rectangular',
                            logo_alignment: 'left',
                        });
                    } catch (err) {
                        console.error('Google Sign-In render error:', err);
                    }
                }
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [authMethod, scriptStatus, handleGoogleCallback]);

    useEffect(() => {
        if (countdown > 0) {
            const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [countdown]);

    // ── Form handlers ──
    const handleEmailSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLocalError(null);
        if (!email || !email.includes('@')) { setLocalError('Please enter a valid email address'); return; }
        if (password.length < 8) { setLocalError('Password must be at least 8 characters'); return; }
        try {
            if (isSignUp) { await registerWithEmail(email, password); }
            else { await loginWithEmail(email, password); }
            onLoginSuccess?.();
        } catch (err) {
            if (err instanceof Error) setLocalError(err.message);
        }
    };

    const handlePhoneSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (phoneNumber.length >= 10) {
            setOtpStep(true);
            setCountdown(30);
            setTimeout(() => otpRefs.current[0]?.focus(), 100);
        }
    };

    const handleOtpChange = (index: number, value: string) => {
        const digit = value.replace(/[^0-9]/g, '').slice(-1);
        const newOtp = [...otp];
        newOtp[index] = digit;
        setOtp(newOtp);
        if (digit && index < 5) otpRefs.current[index + 1]?.focus();
    };

    const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace' && !otp[index] && index > 0) otpRefs.current[index - 1]?.focus();
    };

    const handleOtpPaste = (e: React.ClipboardEvent) => {
        e.preventDefault();
        const paste = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6);
        const newOtp = [...otp];
        paste.split('').forEach((digit, i) => { newOtp[i] = digit; });
        setOtp(newOtp);
        if (paste.length > 0) otpRefs.current[Math.min(paste.length, 5)]?.focus();
    };

    const isOtpComplete = otp.every(d => d !== '');
    const displayError = localError || error;

    return (
        <div className="min-h-screen w-full flex flex-col bg-background">

            {/* ════════════════════════════════════════════════════
                BRAND BAR — Full width, top of entire page
                Dark navy bg, white text. This IS the brand presence.
                ════════════════════════════════════════════════════ */}
            <header className="bg-primary text-primary-foreground shrink-0">
                <div className="max-w-5xl mx-auto px-5 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg border border-primary-foreground/20 flex items-center justify-center">
                            <Shield className="w-5 h-5" />
                        </div>
                        <div>
                            <h1 className="text-base font-bold tracking-tight leading-none">FloodSafe</h1>
                            <p className="text-xs text-primary-foreground/60 mt-0.5">Community flood monitoring</p>
                        </div>
                    </div>
                    <p className="hidden sm:block text-xs text-primary-foreground/50">
                        Delhi &middot; Bangalore
                    </p>
                </div>
                {/* Amber accent line — inspired by Indian government document borders */}
                <div className="h-0.5 bg-amber-500/80" />
            </header>

            {/* ════════════════════════════════════════════════════
                MAIN CONTENT — Photo + Form side by side (desktop)
                                Photo banner + Form stacked (mobile)
                ════════════════════════════════════════════════════ */}
            {/* Content: relative wrapper. Photo is absolute on desktop, static on mobile */}
            <div className="flex-1 relative">

                {/* ── Photo panel ── */}
                {/* Mobile: static 112px banner. Desktop: absolute left strip, full height */}
                <div className="relative md:absolute md:inset-y-0 md:left-0 md:w-80 h-28 md:h-auto overflow-hidden">
                    <img
                        src="/images/kolkata-flood.jpg"
                        alt="Monsoon flooding on a Kolkata street"
                        className="w-full h-full object-cover"
                    />
                    {/* Warm overlay */}
                    <div className="absolute inset-0 bg-gradient-to-b md:bg-gradient-to-r from-amber-900/20 via-transparent to-black/20" />
                    {/* Desktop-only photo caption */}
                    <div className="hidden md:flex absolute bottom-0 left-0 right-0 px-5 py-3 bg-black/50">
                        <p className="text-white/80 text-xs">
                            Kolkata — monsoon flooding disrupts daily commute
                        </p>
                    </div>
                </div>

                {/* ── Form panel ── */}
                {/* Desktop: ml-96 pushes form past the absolute photo */}
                <div className="md:ml-80 min-h-full flex items-start md:items-center justify-center px-6 sm:px-10 md:px-12 py-8 md:py-12 bg-card">
                    <div className="w-full max-w-sm">

                        {authMethod === 'email' ? (
                            <>
                                {/* Heading */}
                                <h2 className="text-2xl font-semibold text-foreground mb-1">
                                    {isSignUp ? 'Create your account' : 'Welcome back'}
                                </h2>
                                <p className="text-muted-foreground text-sm mb-6">
                                    {isSignUp
                                        ? 'Join the flood monitoring community'
                                        : 'Sign in to access alerts, routes & reports'}
                                </p>

                                {/* Error */}
                                {displayError && (
                                    <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-start gap-2">
                                        <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                                        <p className="text-sm text-destructive">{displayError}</p>
                                    </div>
                                )}

                                {/* Email form — tight spacing, no visual excess */}
                                <form onSubmit={handleEmailSubmit} className="space-y-3">
                                    <div>
                                        <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1">Email</label>
                                        <input
                                            id="email"
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            placeholder="you@example.com"
                                            className="w-full px-3.5 py-2.5 border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground bg-background focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
                                            autoComplete="email"
                                        />
                                    </div>
                                    <div>
                                        <label htmlFor="password" className="block text-sm font-medium text-foreground mb-1">Password</label>
                                        <div className="relative">
                                            <input
                                                id="password"
                                                type={showPassword ? 'text' : 'password'}
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                placeholder={isSignUp ? 'Min 8 characters' : 'Your password'}
                                                className="w-full px-3.5 py-2.5 pr-10 border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground bg-background focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
                                                autoComplete={isSignUp ? 'new-password' : 'current-password'}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground transition-colors"
                                            >
                                                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                            </button>
                                        </div>
                                    </div>
                                    <button
                                        type="submit"
                                        disabled={isLoading || !email || password.length < 8}
                                        className="w-full py-2.5 mt-1 bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground font-medium rounded-lg flex items-center justify-center gap-2 transition-all text-sm"
                                    >
                                        {isLoading ? (
                                            <><Loader2 className="w-4 h-4 animate-spin" />{isSignUp ? 'Creating...' : 'Signing in...'}</>
                                        ) : (
                                            <>{isSignUp ? 'Create Account' : 'Sign In'}<ArrowRight className="w-4 h-4" /></>
                                        )}
                                    </button>
                                </form>

                                {/* Divider */}
                                <div className="relative my-5">
                                    <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
                                    <div className="relative flex justify-center text-xs">
                                        <span className="bg-card px-3 text-muted-foreground">or</span>
                                    </div>
                                </div>

                                {/* Google Sign-In */}
                                <div>
                                    {scriptStatus === 'loading' && <div className="h-10 bg-secondary rounded-lg animate-pulse" />}
                                    {scriptStatus === 'error' && !displayError && (
                                        <div className="text-center p-2.5 bg-amber-50 rounded-lg border border-amber-200">
                                            <p className="text-xs text-amber-700">
                                                Google Sign-In unavailable.{' '}
                                                <button onClick={() => window.location.reload()} className="text-amber-600 underline">Refresh</button>
                                            </p>
                                        </div>
                                    )}
                                    {scriptStatus === 'ready' && (
                                        <div ref={googleButtonRef} className="flex justify-center" />
                                    )}
                                </div>

                                {/* Sign up/in toggle + phone link */}
                                <div className="mt-6 text-center text-sm space-y-2">
                                    <p className="text-muted-foreground">
                                        {isSignUp ? (
                                            <>Already have an account?{' '}
                                                <button type="button" onClick={() => setIsSignUp(false)} className="text-primary font-medium hover:underline">Sign in</button>
                                            </>
                                        ) : (
                                            <>Don&apos;t have an account?{' '}
                                                <button type="button" onClick={() => setIsSignUp(true)} className="text-primary font-medium hover:underline">Sign up</button>
                                            </>
                                        )}
                                    </p>
                                    <button
                                        type="button"
                                        onClick={() => setAuthMethod('phone')}
                                        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                                    >
                                        <Phone className="w-3 h-3" />
                                        Use phone number
                                    </button>
                                </div>
                            </>
                        ) : (
                            <>
                                {/* Phone auth view */}
                                <h2 className="text-2xl font-semibold text-foreground mb-1">Phone sign in</h2>
                                <p className="text-muted-foreground text-sm mb-6">We&apos;ll send you a verification code</p>

                                {displayError && (
                                    <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-start gap-2">
                                        <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                                        <p className="text-sm text-destructive">{displayError}</p>
                                    </div>
                                )}

                                {!otpStep ? (
                                    <form onSubmit={handlePhoneSubmit} className="space-y-4">
                                        <div className="flex border border-border rounded-lg overflow-hidden focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/10 transition-all bg-background">
                                            <select
                                                value={countryCode}
                                                onChange={(e) => setCountryCode(e.target.value)}
                                                className="px-3 py-2.5 bg-secondary border-r border-border text-foreground text-sm focus:outline-none font-medium"
                                            >
                                                <option value="+91">+91</option>
                                                <option value="+1">+1</option>
                                                <option value="+44">+44</option>
                                                <option value="+61">+61</option>
                                            </select>
                                            <input
                                                type="tel"
                                                value={phoneNumber}
                                                onChange={(e) => setPhoneNumber(e.target.value.replace(/[^0-9]/g, ''))}
                                                placeholder="Phone number"
                                                className="flex-1 px-3.5 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none text-sm bg-transparent"
                                                maxLength={10}
                                            />
                                        </div>
                                        <button
                                            type="submit"
                                            disabled={phoneNumber.length < 10}
                                            className="w-full py-2.5 bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground font-medium rounded-lg flex items-center justify-center gap-2 transition-all text-sm"
                                        >
                                            Send code<ArrowRight className="w-4 h-4" />
                                        </button>
                                    </form>
                                ) : (
                                    <div className="space-y-4">
                                        <button
                                            onClick={() => { setOtpStep(false); setOtp(['', '', '', '', '', '']); }}
                                            className="flex items-center gap-1.5 text-muted-foreground hover:text-primary text-sm transition-colors"
                                        >
                                            <ArrowLeft className="w-4 h-4" />Change number
                                        </button>
                                        <p className="text-sm text-muted-foreground">
                                            Code sent to <span className="font-medium text-foreground">{countryCode} {phoneNumber}</span>
                                        </p>
                                        <div className="flex gap-2 justify-center" onPaste={handleOtpPaste}>
                                            {otp.map((digit, index) => (
                                                <input
                                                    key={index}
                                                    ref={(el) => { otpRefs.current[index] = el; }}
                                                    type="text"
                                                    inputMode="numeric"
                                                    maxLength={1}
                                                    value={digit}
                                                    onChange={(e) => handleOtpChange(index, e.target.value)}
                                                    onKeyDown={(e) => handleOtpKeyDown(index, e)}
                                                    className={`w-10 h-12 text-center text-lg font-semibold border rounded-lg transition-all focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 ${
                                                        digit ? 'border-primary bg-primary/5' : 'border-border bg-secondary'
                                                    }`}
                                                />
                                            ))}
                                        </div>
                                        <p className="text-xs text-muted-foreground text-center">
                                            {countdown > 0 ? `Resend in ${countdown}s` : (
                                                <button onClick={() => setCountdown(30)} className="text-primary hover:underline">Resend code</button>
                                            )}
                                        </p>
                                        <button
                                            disabled={!isOtpComplete}
                                            className="w-full py-2.5 bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground font-medium rounded-lg flex items-center justify-center gap-2 transition-all text-sm"
                                        >
                                            Verify<Check className="w-4 h-4" />
                                        </button>
                                    </div>
                                )}
                                <div id="recaptcha-container" />
                                <button
                                    type="button"
                                    onClick={() => setAuthMethod('email')}
                                    className="w-full flex items-center justify-center gap-1.5 mt-6 text-sm text-muted-foreground hover:text-foreground transition-colors"
                                >
                                    <ArrowLeft className="w-3.5 h-3.5" />Back to email sign in
                                </button>
                            </>
                        )}

                        {/* Terms footer */}
                        <p className="text-center text-xs text-muted-foreground mt-6">
                            By continuing, you agree to our{' '}
                            <span className="text-primary hover:underline cursor-pointer">Terms</span>
                            {' '}&{' '}
                            <span className="text-primary hover:underline cursor-pointer">Privacy Policy</span>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default LoginScreen;
