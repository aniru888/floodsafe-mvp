import { useState, useEffect } from 'react';
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
import { LocationTrackingProvider } from './contexts/LocationTrackingContext';
import { FloodAlert } from './types';
import { JoinCircleModal } from './components/circles';
import { Toaster } from './components/ui/sonner';
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CityProvider } from './contexts/CityContext';
import { UserProvider } from './contexts/UserContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import { WebMCPProvider } from './components/WebMCPProvider';

const queryClient = new QueryClient();

type Screen = 'home' | 'map' | 'report' | 'alerts' | 'profile' | 'alert-detail' | 'privacy' | 'terms';

function FloodSafeApp() {
    const { isAuthenticated, isLoading: authLoading, user } = useAuth();
    const [activeTab, setActiveTab] = useState<Screen>('home');
    const [selectedAlert, setSelectedAlert] = useState<FloodAlert | null>(null);
    const [initialRouteDestination, setInitialRouteDestination] = useState<[number, number] | null>(null);
    const [shouldOpenNavigationPanel, setShouldOpenNavigationPanel] = useState(false);
    const [pendingInviteCode, setPendingInviteCode] = useState<string | null>(null);

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

            {/* Deep link: Join circle via ?join=CODE */}
            <JoinCircleModal
                isOpen={pendingInviteCode !== null}
                onClose={() => setPendingInviteCode(null)}
                initialCode={pendingInviteCode || ''}
            />

            <Toaster position="top-center" />
        </ResponsiveLayout>
    );
}

export default function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <AuthProvider>
                <UserProvider>
                    <CityProvider>
                        <InstallPromptProvider>
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
                        </InstallPromptProvider>
                    </CityProvider>
                </UserProvider>
            </AuthProvider>
        </QueryClientProvider>
    );
}
