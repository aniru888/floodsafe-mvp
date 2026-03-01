import { useState, useEffect, useRef } from 'react';
import { Analytics } from '@vercel/analytics/react';
import { Routes, Route } from 'react-router-dom';
import { ResponsiveLayout } from './components/ResponsiveLayout';
import { HomeScreen } from './components/screens/HomeScreen';
import { FloodAtlasScreen } from './components/screens/FloodAtlasScreen';
import { ReportScreen } from './components/screens/ReportScreen';
import { ProfileScreen } from './components/screens/ProfileScreen';
import { LoginScreen } from './components/screens/LoginScreen';
import { OnboardingScreen } from './components/screens/OnboardingScreen';
import { AlertsScreen } from './components/screens/AlertsScreen';
import { AlertDetailScreen } from './components/screens/Placeholders';
import { PrivacyPolicyScreen } from './components/screens/PrivacyPolicyScreen';
import { TermsScreen } from './components/screens/TermsScreen';
import { EmailVerifiedScreen } from './components/screens/EmailVerifiedScreen';
import { OfflineIndicator } from './components/OfflineIndicator';
import { PWAUpdateBanner } from './components/PWAUpdateBanner';
import { IOSInstallBanner } from './components/IOSInstallBanner';
import { InstallBanner } from './components/InstallBanner';
import { InstallPromptProvider } from './contexts/InstallPromptContext';
import { VoiceGuidanceProvider } from './contexts/VoiceGuidanceContext';
import { LocationTrackingProvider } from './contexts/LocationTrackingContext';
import { FloodAlert } from './types';
import { JoinCircleModal } from './components/circles';
import { Toaster } from './components/ui/sonner';
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { CityProvider } from './contexts/CityContext';
import { UserProvider, useUser } from './contexts/UserContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LanguageProvider, useLanguage, toShortCode } from './contexts/LanguageContext';
import { fetchJson } from './lib/api/client';
import { User } from './types';
import { Loader2 } from 'lucide-react';
import { WebMCPProvider } from './components/WebMCPProvider';
import { NavigationProvider } from './contexts/NavigationContext';
import { OnboardingBotProvider, useOnboardingBot } from './contexts/OnboardingBotContext';
import { OnboardingBot } from './components/onboarding-bot/OnboardingBot';
import { usePushNotifications } from './hooks/usePushNotifications';

const queryClient = new QueryClient();

type Screen = 'home' | 'map' | 'report' | 'alerts' | 'profile' | 'alert-detail' | 'privacy' | 'terms';

/** Registers FCM push token for authenticated users. Renders nothing. */
function PushNotificationRegistrar() {
    const { permission, requestPermission } = usePushNotifications();

    useEffect(() => {
        if (permission === 'default') {
            requestPermission();
        }
    }, [permission, requestPermission]);

    return null;
}

/**
 * Syncs LanguageContext <-> user.language in DB.
 * - On user load: DB wins for returning users (non-default language).
 * - New users: localStorage value (set on LoginScreen) takes precedence.
 *
 * Uses /users/me/profile (full profile endpoint) because /auth/me (AuthUser)
 * does not include the language field.
 */
function LanguageSyncBridge() {
    const { userId } = useUser();
    const { language, setLanguage } = useLanguage();
    const hasSyncedRef = useRef(false);

    const { data: profile } = useQuery({
        queryKey: ['user', 'profile', userId],
        queryFn: () => fetchJson<User>('/users/me/profile'),
        enabled: !!userId,
        staleTime: 5 * 60 * 1000, // 5 min — same as ProfileScreen
    });

    // On profile load: sync DB → context (DB wins for returning users)
    useEffect(() => {
        if (!profile || hasSyncedRef.current) return;
        hasSyncedRef.current = true;

        const dbLang = toShortCode(profile.language);
        // DB wins if user has a non-default language set
        if (profile.language && profile.language !== 'english' && dbLang !== language) {
            setLanguage(dbLang);
        }
    }, [profile, language, setLanguage]);

    // Reset sync flag on logout
    useEffect(() => {
        if (!userId) hasSyncedRef.current = false;
    }, [userId]);

    return null;
}

function FloodSafeApp() {
    const { isAuthenticated, isLoading: authLoading, user } = useAuth();
    const { registerNavigation, startTour } = useOnboardingBot();
    const [activeTab, setActiveTab] = useState<Screen>('home');
    const [selectedAlert, setSelectedAlert] = useState<FloodAlert | null>(null);
    const [initialRouteDestination, setInitialRouteDestination] = useState<[number, number] | null>(null);
    const [shouldOpenNavigationPanel, setShouldOpenNavigationPanel] = useState(false);
    const [pendingInviteCode, setPendingInviteCode] = useState<string | null>(null);

    // Register setActiveTab so the bot can navigate between screens during app tour
    useEffect(() => {
        registerNavigation((tab: string) => setActiveTab(tab as Screen));
    }, [registerNavigation]);

    // Auto-start app tour after onboarding completion (flagged by OnboardingScreen)
    useEffect(() => {
        if (user?.profile_complete && localStorage.getItem('floodsafe_start_app_tour') === 'true') {
            localStorage.removeItem('floodsafe_start_app_tour');
            // Small delay to let the main app render first
            const timer = setTimeout(() => startTour('app-tour'), 1000);
            return () => clearTimeout(timer);
        }
    }, [user?.profile_complete, startTour]);

    // Deep link: check URL for ?join=CODE on mount
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const inviteCode = params.get('join');
        if (inviteCode) {
            if (isAuthenticated) {
                setPendingInviteCode(inviteCode);
                setActiveTab('alerts');
            } else {
                // Store for after login
                sessionStorage.setItem('pendingInviteCode', inviteCode);
            }
            // Clean URL
            const url = new URL(window.location.href);
            url.searchParams.delete('join');
            window.history.replaceState({}, '', url.toString());
        }
    }, []);

    // Process stored invite code after login
    useEffect(() => {
        if (isAuthenticated && !pendingInviteCode) {
            const stored = sessionStorage.getItem('pendingInviteCode');
            if (stored) {
                sessionStorage.removeItem('pendingInviteCode');
                setPendingInviteCode(stored);
                setActiveTab('alerts');
            }
        }
    }, [isAuthenticated]);

    const handleAlertClick = (alert: FloodAlert) => {
        setSelectedAlert(alert);
        setActiveTab('alert-detail');
    };

    const handleBackFromDetail = () => {
        setSelectedAlert(null);
        setActiveTab('home');
    };

    const handleBackFromReport = () => {
        setActiveTab('home');
    };

    const handleReportSubmit = () => {
        setActiveTab('home');
    };

    const handleNotificationClick = () => {
        setActiveTab('alerts');
    };

    const handleProfileClick = () => {
        setActiveTab('profile');
    };

    const handleNavigateToMap = () => {
        setActiveTab('map');
    };

    const handleNavigateToMapAndPlanRoute = () => {
        setShouldOpenNavigationPanel(true);
        setActiveTab('map');
    };

    const handleNavigateToReport = () => {
        setActiveTab('report');
    };

    const handleNavigateToAlerts = () => {
        setActiveTab('alerts');
    };

    const handleNavigateToProfile = () => {
        setActiveTab('profile');
    };

    const handleNavigateToMapWithRoute = (destination: [number, number]) => {
        setInitialRouteDestination(destination);
        setActiveTab('map');
    };

    // Show loading screen while checking auth
    if (authLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-cyan-50">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                    <p className="text-gray-600">Loading FloodSafe...</p>
                </div>
            </div>
        );
    }

    // Show login screen if not authenticated
    if (!isAuthenticated) {
        return (
            <>
                <LoginScreen />
                <Toaster position="top-center" />
            </>
        );
    }

    // Show onboarding if profile not complete
    if (user && !user.profile_complete) {
        return (
            <>
                <OnboardingScreen onComplete={() => {
                    // Force refresh to update user state
                    window.location.reload();
                }} />
                <Toaster position="top-center" />
            </>
        );
    }

    const renderScreen = () => {
        switch (activeTab) {
            case 'home':
                return <HomeScreen
                    onAlertClick={handleAlertClick}
                    onNavigateToMap={handleNavigateToMap}
                    onNavigateToMapAndPlanRoute={handleNavigateToMapAndPlanRoute}
                    onNavigateToReport={handleNavigateToReport}
                    onNavigateToAlerts={handleNavigateToAlerts}
                    onNavigateToProfile={handleNavigateToProfile}
                    onNavigateToMapWithRoute={handleNavigateToMapWithRoute}
                />;
            case 'alert-detail':
                return selectedAlert ? (
                    <AlertDetailScreen alert={selectedAlert} onBack={handleBackFromDetail} />
                ) : (
                    <HomeScreen
                        onAlertClick={handleAlertClick}
                        onNavigateToMap={handleNavigateToMap}
                        onNavigateToMapAndPlanRoute={handleNavigateToMapAndPlanRoute}
                        onNavigateToReport={handleNavigateToReport}
                        onNavigateToAlerts={handleNavigateToAlerts}
                        onNavigateToProfile={handleNavigateToProfile}
                        onNavigateToMapWithRoute={handleNavigateToMapWithRoute}
                    />
                );
            case 'map':
                return <FloodAtlasScreen
                    initialDestination={initialRouteDestination}
                    onClearInitialDestination={() => setInitialRouteDestination(null)}
                    openNavigationPanel={shouldOpenNavigationPanel}
                    onClearOpenNavigationPanel={() => setShouldOpenNavigationPanel(false)}
                />;
            case 'report':
                return <ReportScreen onBack={handleBackFromReport} onSubmit={handleReportSubmit} />;
            case 'alerts':
                return <AlertsScreen />;
            case 'profile':
                return <ProfileScreen onNavigate={(screen) => setActiveTab(screen)} />;
            case 'privacy':
                return <PrivacyPolicyScreen />;
            case 'terms':
                return <TermsScreen />;
            default:
                return <HomeScreen
                    onAlertClick={handleAlertClick}
                    onNavigateToMap={handleNavigateToMap}
                    onNavigateToMapAndPlanRoute={handleNavigateToMapAndPlanRoute}
                    onNavigateToReport={handleNavigateToReport}
                    onNavigateToAlerts={handleNavigateToAlerts}
                    onNavigateToProfile={handleNavigateToProfile}
                    onNavigateToMapWithRoute={handleNavigateToMapWithRoute}
                />;
        }
    };

    return (
        <ResponsiveLayout
            activeTab={activeTab}
            onTabChange={(tab) => setActiveTab(tab as Screen)}
            onNotificationClick={handleNotificationClick}
            onProfileClick={handleProfileClick}
        >
            {renderScreen()}

            {/* PWA Components (PWAUpdateBanner is at root level for immediate SW registration) */}
            <OfflineIndicator />
            <IOSInstallBanner />
            <InstallBanner />

            {/* Push Notification Registration — prompts permission + registers FCM token */}
            <PushNotificationRegistrar />

            {/* Deep link: Join circle via ?join=CODE */}
            <JoinCircleModal
                isOpen={pendingInviteCode !== null}
                onClose={() => setPendingInviteCode(null)}
                initialCode={pendingInviteCode || ''}
            />

            {/* Onboarding Bot — floating companion for app tour */}
            <OnboardingBot />

            <Toaster position="top-center" />
        </ResponsiveLayout>
    );
}

export default function App() {
    return (
        <>
            <Analytics />
            <LanguageProvider>
            <QueryClientProvider client={queryClient}>
            <AuthProvider>
                <UserProvider>
                    <LanguageSyncBridge />
                    <CityProvider>
                        <InstallPromptProvider>
                            <VoiceGuidanceProvider>
                            <NavigationProvider>
                            <OnboardingBotProvider>
                            <LocationTrackingProvider>
                                {/* WebMCP: AI agent bridge for real-time debugging */}
                                <WebMCPProvider />

                                {/* PWA Update Banner - renders at root level so SW registers immediately */}
                                <PWAUpdateBanner />

                                <Routes>
                                    {/* Email verification callback - accessible without auth */}
                                    <Route path="/email-verified" element={
                                        <>
                                            <EmailVerifiedScreen />
                                            <Toaster position="top-center" />
                                        </>
                                    } />
                                    {/* All other routes go to the main app */}
                                    <Route path="*" element={<FloodSafeApp />} />
                                </Routes>
                            </LocationTrackingProvider>
                            </OnboardingBotProvider>
                            </NavigationProvider>
                            </VoiceGuidanceProvider>
                        </InstallPromptProvider>
                    </CityProvider>
                </UserProvider>
            </AuthProvider>
        </QueryClientProvider>
        </LanguageProvider>
        </>
    );
}
