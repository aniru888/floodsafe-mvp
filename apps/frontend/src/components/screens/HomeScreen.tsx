import { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import {
    MapPin, Users, AlertTriangle, Bell, Shield, Phone, Camera,
    Navigation, ChevronRight, AlertCircle, Droplets,
    Maximize2, Target, RefreshCw, Share2, ThumbsUp, Settings, MapPinned
} from 'lucide-react';
import { FloodAlert } from '../../types';
import MapComponent from '../MapComponent';
import { useSensors, useReports, useUsers, useActiveReporters, useNearbyReporters, useLocationDetails, useWatchAreas, useDailyRoutes, Report } from '../../lib/api/hooks';
import { toast } from 'sonner';
import { ReportDetailModal } from '../ReportDetailModal';
import { EmergencyContactsModal } from '../EmergencyContactsModal';
import { cn } from '../../lib/utils';
import { getNestedArray, hasLocationData } from '../../lib/safe-access';
import { detectCityFromCoordinates, getCityKeyFromCoordinates, type CityKey } from '../../lib/map/cityConfigs';
import { useAuth } from '../../contexts/AuthContext';
import { useCityContext } from '../../contexts/CityContext';
import { CITIES } from '../../lib/map/cityConfigs';
import { VerificationReminderBanner } from '../VerificationReminderBanner';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '../ui/dialog';

interface HomeScreenProps {
    onAlertClick: (alert: FloodAlert) => void;
    onNavigateToMap?: () => void;
    onNavigateToReport?: () => void;
    onNavigateToAlerts?: () => void;
    onNavigateToProfile?: () => void;
    onNavigateToMapWithRoute?: (destination: [number, number]) => void;
}

// Refresh interval options - Updated as per requirement: 15s, 2m, 10m (default)
const REFRESH_INTERVALS = {
    '15s': 15000,
    '2m': 120000,
    '10m': 600000,
} as const;

type RefreshInterval = keyof typeof REFRESH_INTERVALS;
type CityFilter = 'all' | CityKey;

export function HomeScreen({
    onAlertClick,
    onNavigateToMap,
    onNavigateToReport,
    onNavigateToAlerts,
    onNavigateToProfile,
    onNavigateToMapWithRoute
}: HomeScreenProps) {
    const { user } = useAuth();
    const { city: currentCity, setCity, syncCityToUser } = useCityContext();
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [refreshInterval, setRefreshInterval] = useState<RefreshInterval>('10m'); // Default 10 minutes
    const [cityFilter, setCityFilter] = useState<CityFilter>(() => {
        // Initialize with user's city preference, fallback to 'all'
        return (user?.city_preference as CityFilter) || 'all';
    });
    const [selectedLocation, setSelectedLocation] = useState<{ lat: number; lng: number } | null>(null);
    const [mapTargetLocation, setMapTargetLocation] = useState<{ lat: number; lng: number } | null>(null);
    const [selectedReport, setSelectedReport] = useState<Report | null>(null);
    const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);

    // Update city filter when user's city preference changes
    useEffect(() => {
        if (user?.city_preference) {
            setCityFilter(user.city_preference as CityFilter);
        }
    }, [user?.city_preference]);

    // User's current location from geolocation API
    const [userLocation, setUserLocation] = useState<{ latitude: number; longitude: number } | null>(null);

    // Get user's GPS location with retry mechanism
    useEffect(() => {
        if (!navigator.geolocation) {
            // Browser doesn't support geolocation - use city context for fallback
            const fallbackCoords = currentCity === 'bangalore'
                ? { latitude: 12.9716, longitude: 77.5946 }
                : { latitude: 28.6139, longitude: 77.2090 };
            setUserLocation(fallbackCoords);
            return;
        }

        const setLocationFromPosition = (position: GeolocationPosition) => {
            setUserLocation({
                latitude: position.coords.latitude,
                longitude: position.coords.longitude
            });
        };

        const applyFallback = () => {
            // Use current city from CityContext (not database preference)
            const fallbackCoords = currentCity === 'bangalore'
                ? { latitude: 12.9716, longitude: 77.5946 }
                : { latitude: 28.6139, longitude: 77.2090 };
            setUserLocation(fallbackCoords);
        };

        // Progressive retry strategy for geolocation
        // Initial: high accuracy, 10s timeout
        // Retry 1: lower accuracy, 20s timeout
        // Retry 2: accept cached, 5s timeout (quick check)
        // Fallback: use city center

        const attemptGeolocation = (attemptNumber: number) => {
            const options: PositionOptions[] = [
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },   // Attempt 1
                { enableHighAccuracy: false, timeout: 20000, maximumAge: 120000 }, // Attempt 2
                { enableHighAccuracy: false, timeout: 5000, maximumAge: 600000 },  // Attempt 3 (cached OK)
            ];

            const currentOptions = options[attemptNumber] || options[options.length - 1];

            navigator.geolocation.getCurrentPosition(
                setLocationFromPosition,
                (error) => {
                    if (error.code === error.TIMEOUT && attemptNumber < 2) {
                        // Retry with next strategy
                        if (attemptNumber === 0) {
                            toast.info('Getting your location... This may take a moment.');
                        }
                        attemptGeolocation(attemptNumber + 1);
                    } else {
                        // Final failure - use fallback
                        console.warn('Geolocation failed after retries:', error.message);
                        toast.info('Using approximate location. Move outdoors for better accuracy.');
                        applyFallback();
                    }
                },
                currentOptions
            );
        };

        attemptGeolocation(0);
    }, [currentCity]);

    const { data: sensors, refetch: refetchSensors } = useSensors();
    const { data: reports, refetch: refetchReports } = useReports();
    const { data: _users } = useUsers();
    const { data: activeReportersData } = useActiveReporters();
    const { data: nearbyReportersData } = useNearbyReporters(
        userLocation?.latitude ?? 0,
        userLocation?.longitude ?? 0,
        5.0
    );
    const { data: locationDetails } = useLocationDetails(
        selectedLocation?.lat || null,
        selectedLocation?.lng || null,
        500 // 500 meter radius
    );

    // Fetch user's watch areas and daily routes
    const { data: userWatchAreas = [] } = useWatchAreas(user?.id);
    const { data: userDailyRoutes = [] } = useDailyRoutes(user?.id);

    // Transform sensors into alerts with location info
    const activeAlerts: FloodAlert[] = (sensors ?? [])
        .filter(s => s.status !== 'active')
        .map(s => ({
            id: s.id,
            level: s.status === 'critical' ? 'critical' : 'warning',
            location: `Sensor ${s.id.substring(0, 8)}`,
            description: `Water level is ${s.status}.`,
            timeUntil: 'Now',
            confidence: 90,
            isActive: true,
            color: s.status === 'critical' ? 'red' : 'orange',
            coordinates: [s.longitude, s.latitude] as [number, number],
            timestamp: s.last_ping || undefined, // Use sensor's last_ping as timestamp
        }));

    // Filter alerts by city
    const filteredAlerts = cityFilter === 'all'
        ? activeAlerts
        : activeAlerts.filter(alert => {
            const cityKey = getCityKeyFromCoordinates(alert.coordinates[0], alert.coordinates[1]);
            return cityKey === cityFilter;
        });

    // Filter reports by city
    const filteredReports = cityFilter === 'all'
        ? reports
        : reports?.filter(report => {
            const cityKey = getCityKeyFromCoordinates(report.longitude, report.latitude);
            return cityKey === cityFilter;
        }) || [];

    // Community stats with proper logic
    const _activeReporters = activeReportersData?.count || 0; // Users with reports in past 7 days
    const _nearbyReporters = nearbyReportersData?.count || 0; // Users who reported within 5km

    // Use authenticated user's data
    // Note: reports_count would need to be fetched from backend separately
    const _userImpact = {
        reports: 0, // TODO: Fetch from backend /api/reports/user/{id}/count
        helped: 0,
    };

    // Determine risk level based on filtered alerts (user's city)
    // Aligned with userAreaRiskLevel thresholds for consistency
    const riskLevel = filteredAlerts.length === 0 ? 'low' :
                      filteredAlerts.some(a => a.level === 'critical') ? 'severe' :
                      filteredAlerts.length > 3 ? 'high' :
                      filteredAlerts.length > 1 ? 'moderate' : 'low';

    const _riskColors = {
        low: 'bg-green-500',
        moderate: 'bg-yellow-500',
        high: 'bg-orange-500',
        severe: 'bg-red-500'
    };

    const riskLabels = {
        low: 'LOW FLOOD RISK',
        moderate: 'MODERATE FLOOD RISK',
        high: 'HIGH FLOOD RISK',
        severe: 'SEVERE FLOOD RISK'
    };

    // Dynamic user area data - Use first watch area or current city from context
    // Now reactive to city changes (dropdown + GPS location)
    const userAreaName = userWatchAreas.length > 0
        ? userWatchAreas[0].name
        : currentCity
            ? CITIES[currentCity]?.displayName || 'Your Area'
            : 'Your Area';

    // Calculate risk level for user's area (using filtered alerts)
    // Aligned with header riskLevel thresholds for consistency
    const userAreaAlerts = filteredAlerts.length; // Alerts in user's selected city
    const hasCriticalAlert = filteredAlerts.some(a => a.level === 'critical');
    const userAreaRiskLevel = userAreaAlerts === 0 ? 'Low Risk' :
                              hasCriticalAlert ? 'Severe Risk' :
                              userAreaAlerts > 3 ? 'High Risk' :
                              userAreaAlerts > 1 ? 'Moderate Risk' : 'Low Risk';

    // Calculate time to next alert (find nearest future alert in user's city)
    const now = new Date();
    const nextAlertTime = filteredAlerts.length > 0
        ? (() => {
            // Calculate based on alert timestamps for user's selected city
            const alertTimes = filteredAlerts
                .filter(a => a.timestamp) // Only alerts with timestamps
                .map(a => new Date(a.timestamp!))
                .filter(t => t > now);
            if (alertTimes.length === 0) return 'Active now';

            const nextAlert = Math.min(...alertTimes.map(t => t.getTime()));
            const hoursUntil = Math.round((nextAlert - now.getTime()) / (1000 * 60 * 60));
            return hoursUntil === 0 ? 'Active now' : `${hoursUntil} hr${hoursUntil > 1 ? 's' : ''} ahead`;
          })()
        : 'No alerts';

    // User's daily routes count (from backend)
    const userRoutesCount = userDailyRoutes.length;

    // Auto-refresh with configurable interval
    useEffect(() => {
        const intervalMs = REFRESH_INTERVALS[refreshInterval];

        const interval = setInterval(() => {
            setIsRefreshing(true);
            Promise.all([refetchSensors(), refetchReports()])
                .finally(() => {
                    setTimeout(() => setIsRefreshing(false), 1000);
                });
        }, intervalMs);

        return () => clearInterval(interval);
    }, [refreshInterval, refetchSensors, refetchReports]);

    const handleRefresh = () => {
        setIsRefreshing(true);
        Promise.all([refetchSensors(), refetchReports()])
            .finally(() => {
                setTimeout(() => setIsRefreshing(false), 1000);
                toast.success('Data refreshed successfully');
            });
    };

    const handleSOS = () => {
        setEmergencyModalOpen(true);
    };

    const handleViewDetails = () => {
        if (filteredAlerts.length > 0) {
            onAlertClick(filteredAlerts[0]);
        } else {
            toast.info('No active alerts in your area');
        }
    };

    const handleSetAlerts = () => {
        onNavigateToAlerts?.();
        toast.success('Opening alert settings');
    };

    const handleAreaDetails = () => {
        toast.info(`Viewing ${userAreaName} area details`);
    };

    const handleViewAllAlerts = () => {
        onNavigateToAlerts?.();
    };

    // Handle city dropdown change - update filter, context, and optionally sync to profile
    const handleCityFilterChange = async (value: string) => {
        const newFilter = value as CityFilter;
        setCityFilter(newFilter);

        // If selecting a specific city (not 'all'), also update CityContext and sync to profile
        if (newFilter !== 'all' && (newFilter === 'delhi' || newFilter === 'bangalore')) {
            setCity(newFilter);
            // Sync to user profile if logged in
            if (user?.id) {
                try {
                    await syncCityToUser(user.id, newFilter);
                    toast.success(`City preference updated to ${CITIES[newFilter].displayName}`);
                } catch (error) {
                    console.error('Failed to sync city preference:', error);
                    // Still update locally even if sync fails
                }
            }
        }
    };

    const handleNavigateRoutes = (alert?: FloodAlert) => {
        if (alert) {
            // Navigate to FloodAtlasScreen with destination from alert
            onNavigateToMapWithRoute?.(alert.coordinates);
            toast.info(`Opening navigation to plan safe routes avoiding ${alert.location}`, {
                duration: 4000,
            });
        } else {
            // Navigate to FloodAtlasScreen without preset destination
            onNavigateToMap?.();
            toast.success('Opening safe route navigation');
        }
    };

    const handleShare = async (alert: FloodAlert) => {
        const shareText = `⚠️ Flood Alert: ${alert.location}\n\n${alert.description}\n\n📍 Location: ${alert.coordinates[1].toFixed(4)}, ${alert.coordinates[0].toFixed(4)}\n\nStay safe! - via FloodSafe`;
        const shareUrl = `https://floodsafe.app/alert/${alert.id}`;

        // Try Web Share API first (mobile-friendly)
        if (navigator.share) {
            try {
                await navigator.share({
                    title: `Flood Alert: ${alert.location}`,
                    text: shareText,
                    url: shareUrl,
                });
                toast.success('Alert shared successfully');
            } catch (err) {
                // User cancelled or share failed
                if ((err as Error).name !== 'AbortError') {
                    // Fallback to clipboard
                    await copyToClipboard(shareText);
                }
            }
        } else {
            // Fallback to clipboard for desktop
            await copyToClipboard(shareText);
        }
    };

    const copyToClipboard = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text);
            toast.success('Alert copied to clipboard!');
        } catch {
            toast.error('Failed to copy alert');
        }
    };

    const handleThankReporter = () => {
        toast.success('Thank you sent to reporter!');
    };

    const handleJoinAmbassadors = () => {
        onNavigateToProfile?.();
        toast.success('Opening ambassador program');
    };

    const _handleViewLeaderboard = () => {
        onNavigateToProfile?.();
        toast.info('Viewing community leaderboard');
    };

    const handleFullscreenMap = () => {
        onNavigateToMap?.();
        toast.info('Opening full Flood Atlas');
    };

    const handleCenterMap = () => {
        toast.info('Centering map on your location');
    };

    const handleLocateAlert = (lat: number, lng: number, locationName: string) => {
        setMapTargetLocation({ lat, lng }); // Trigger map pan
        setSelectedLocation({ lat, lng });
        toast.info(`Locating ${locationName} on map`);
    };

    // Parse timestamp as UTC (backend stores UTC but without 'Z' suffix)
    const parseUTCTimestamp = (timestamp: string) => {
        if (!timestamp) return new Date();
        // If timestamp doesn't have timezone info, treat as UTC
        if (!timestamp.endsWith('Z') && !timestamp.includes('+') && !timestamp.includes('-', 10)) {
            return new Date(timestamp + 'Z');
        }
        return new Date(timestamp);
    };

    const formatTimeAgo = (timestamp: string | null | undefined) => {
        if (!timestamp) return 'Just now';

        const now = new Date();
        const time = parseUTCTimestamp(timestamp);
        const diff = now.getTime() - time.getTime();
        const minutes = Math.floor(diff / 60000);

        if (minutes < 0) return 'Just now'; // Future timestamp edge case
        if (minutes < 1) return 'Just now';
        if (minutes === 1) return '1 min ago';
        if (minutes < 60) return `${minutes} min ago`;

        const hours = Math.floor(minutes / 60);
        if (hours === 1) return '1 hour ago';
        if (hours < 24) return `${hours} hours ago`;

        const days = Math.floor(hours / 24);
        if (days === 1) return '1 day ago';
        if (days < 7) return `${days} days ago`;

        return time.toLocaleDateString();
    };

    // Gradient risk colors using inline styles (Tailwind JIT doesn't generate these)
    const riskGradientStyles: Record<string, React.CSSProperties> = {
        low: { background: 'linear-gradient(to right, #10b981, #059669)' },      // emerald-500 to emerald-600
        moderate: { background: 'linear-gradient(to right, #f59e0b, #d97706)' }, // amber-500 to amber-600
        high: { background: 'linear-gradient(to right, #f97316, #ea580c)' },     // orange-500 to orange-600
        severe: { background: 'linear-gradient(to right, #ef4444, #dc2626)' }    // red-500 to red-600
    };

    // Dynamic button text colors matching risk level
    const _riskButtonColors = {
        low: 'text-emerald-600',
        moderate: 'text-amber-600',
        high: 'text-orange-600',
        severe: 'text-red-600'
    };

    return (
        <div className="h-full flex flex-col bg-background overflow-y-auto">
            {/* Email Verification Reminder Banner (for unverified email users) */}
            <VerificationReminderBanner />

            {/* Dynamic Risk Header */}
            <div style={riskGradientStyles[riskLevel]} className="text-white px-4 py-4 flex-shrink-0">
                <div className="max-w-5xl mx-auto flex items-center justify-between gap-2">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 text-lg font-bold">
                            <AlertTriangle className="w-5 h-5" />
                            {riskLabels[riskLevel]}
                        </div>
                        <div className="text-sm opacity-90 mt-1">
                            Next 12 hours • {userAreaName}
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={handleViewDetails}
                            className="bg-white/20 backdrop-blur px-3 py-1 rounded-lg text-sm hover:bg-white/30 transition-colors min-h-[44px]"
                        >
                            View Details
                        </button>
                        <button
                            onClick={handleSetAlerts}
                            className="bg-card px-3 py-1 rounded-lg text-sm font-medium hover:bg-muted transition-colors min-h-[44px]"
                            style={{ color: riskLevel === 'low' ? '#059669' : riskLevel === 'moderate' ? '#d97706' : riskLevel === 'high' ? '#ea580c' : '#dc2626' }}
                        >
                            Set Alerts
                        </button>
                    </div>
                </div>
            </div>

            {/* Main Content — desktop 2-col grid, mobile single column */}
            <div className="max-w-5xl mx-auto w-full px-4 py-4 space-y-4 flex-1">

                {/* Desktop grid: left = status cards + actions, right = map */}
                <div className="md:grid md:grid-cols-2 md:gap-4 space-y-3 md:space-y-0">

                    {/* LEFT COLUMN: Area + Stats + Quick Actions */}
                    <div className="space-y-3">
                        {/* Your Area Card */}
                        <div className="bg-card text-card-foreground rounded-xl border shadow-sm p-4">
                            <div className="flex items-center gap-2 text-muted-foreground text-xs font-medium uppercase tracking-wider mb-3">
                                <MapPin className="w-4 h-4" />
                                <span>Your Area</span>
                            </div>
                            <h3 className="font-semibold text-foreground text-lg leading-tight">{userAreaName}</h3>
                            <div className="flex items-center justify-between mt-3">
                                <span className={cn(
                                    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold",
                                    userAreaRiskLevel === 'Low Risk' && 'bg-emerald-50 text-emerald-600',
                                    userAreaRiskLevel === 'Moderate Risk' && 'bg-amber-50 text-amber-600',
                                    userAreaRiskLevel === 'High Risk' && 'bg-orange-50 text-orange-600',
                                    userAreaRiskLevel === 'Severe Risk' && 'bg-red-50 text-red-600'
                                )}>
                                    <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                                    {userAreaRiskLevel}
                                </span>
                                <button
                                    onClick={handleAreaDetails}
                                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors min-h-[44px]"
                                >
                                    Details <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>

                        {/* Alerts & Safety - Side by Side */}
                        <div className="flex gap-3">
                            {/* Alerts Card */}
                            <div className="flex-1 bg-card text-card-foreground rounded-xl border shadow-sm p-4">
                                <div className="flex items-center gap-2 text-muted-foreground text-xs font-medium uppercase tracking-wider mb-2">
                                    <Bell className="w-4 h-4" />
                                    <span>Alerts</span>
                                </div>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-3xl font-bold text-foreground">{filteredAlerts.length}</span>
                                    <span className="text-muted-foreground text-sm">Active</span>
                                </div>
                                <p className="text-xs text-muted-foreground/70 mt-1">{nextAlertTime}</p>
                                <button
                                    onClick={handleViewAllAlerts}
                                    className="flex items-center gap-1 text-sm text-primary hover:text-primary/80 mt-3 font-medium transition-colors min-h-[44px]"
                                >
                                    View All <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>

                            {/* Safety Card */}
                            <div className="flex-1 bg-card text-card-foreground rounded-xl border shadow-sm p-4">
                                <div className="flex items-center gap-2 text-muted-foreground text-xs font-medium uppercase tracking-wider mb-2">
                                    <Shield className="w-4 h-4" />
                                    <span>Safe Routes</span>
                                </div>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-3xl font-bold text-foreground">{userRoutesCount}</span>
                                    <span className="text-muted-foreground text-sm">Saved</span>
                                </div>
                                <p className="text-xs text-muted-foreground/70 mt-1">{userRoutesCount > 0 ? 'Ready to navigate' : 'Plan safe routes'}</p>
                                <button
                                    onClick={() => handleNavigateRoutes()}
                                    className="flex items-center gap-1 text-sm text-primary hover:text-primary/80 mt-3 font-medium transition-colors min-h-[44px]"
                                >
                                    {userRoutesCount > 0 ? 'Navigate' : 'Plan Route'} <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>

                        {/* Quick Actions - Single Card with Dividers */}
                        <div className="bg-card text-card-foreground rounded-xl border shadow-sm overflow-hidden">
                            <div className="grid grid-cols-3 divide-x divide-border">
                                {/* SOS Button */}
                                <button
                                    onClick={handleSOS}
                                    className="flex flex-col items-center gap-2 py-4 hover:bg-red-50 transition-colors min-h-[88px]"
                                >
                                    <div className="w-12 h-12 rounded-full bg-red-500 flex items-center justify-center shadow-lg shadow-red-500/30">
                                        <Phone className="w-5 h-5 text-white" />
                                    </div>
                                    <span className="text-xs font-semibold text-red-600">SOS</span>
                                </button>

                                {/* Report Button */}
                                <button
                                    onClick={onNavigateToReport}
                                    className="flex flex-col items-center gap-2 py-4 hover:bg-blue-50 transition-colors min-h-[88px]"
                                >
                                    <div
                                        className="w-12 h-12 rounded-full flex items-center justify-center shadow-lg"
                                        style={{ backgroundColor: '#3b82f6', boxShadow: '0 10px 15px -3px rgba(59, 130, 246, 0.3)' }}
                                    >
                                        <Camera className="w-5 h-5 text-white" />
                                    </div>
                                    <span className="text-xs font-semibold text-blue-600">Report</span>
                                </button>

                                {/* Routes Button */}
                                <button
                                    onClick={() => handleNavigateRoutes()}
                                    className="flex flex-col items-center gap-2 py-4 hover:bg-emerald-50 transition-colors min-h-[88px]"
                                >
                                    <div
                                        className="w-12 h-12 rounded-full flex items-center justify-center shadow-lg"
                                        style={{ backgroundColor: '#10b981', boxShadow: '0 10px 15px -3px rgba(16, 185, 129, 0.3)' }}
                                    >
                                        <Navigation className="w-5 h-5 text-white" />
                                    </div>
                                    <span className="text-xs font-medium text-muted-foreground">Routes</span>
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* RIGHT COLUMN: Map Preview (stacks below on mobile) */}
                    <div className="bg-card text-card-foreground rounded-xl border shadow-sm overflow-hidden">
                        <div className="relative h-48 sm:h-56 md:h-full md:min-h-[20rem]">
                            <MapComponent
                                className="w-full h-full"
                                targetLocation={mapTargetLocation}
                                onLocationReached={() => setMapTargetLocation(null)}
                            />

                            {/* Floating indicators */}
                            <div className="absolute top-3 left-3 bg-green-500 text-white px-2 py-1 rounded-full text-xs animate-pulse">
                                Sensor Active
                            </div>
                            <div className="absolute top-10 right-6 bg-yellow-500 text-white p-2 rounded-full">
                                <Droplets className="w-3 h-3" />
                            </div>
                            {filteredAlerts.length > 0 && (
                                <div className="absolute bottom-12 left-8 bg-red-500 text-white p-2 rounded-full animate-pulse">
                                    <AlertCircle className="w-3 h-3" />
                                </div>
                            )}

                            {/* Map controls - Vertical stack on the right */}
                            <div className="absolute bottom-3 right-3 flex flex-col gap-2">
                                <button
                                    onClick={handleFullscreenMap}
                                    className="bg-card p-2 rounded-lg shadow-sm border hover:bg-secondary transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                                    aria-label="Open full Flood Atlas"
                                    title="Zoom / Full Map"
                                >
                                    <Maximize2 className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={handleCenterMap}
                                    className="bg-card p-2 rounded-lg shadow-sm border hover:bg-secondary transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                                    aria-label="Center on my location"
                                    title="My Location"
                                >
                                    <Target className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Live Updates Feed with Auto-Refresh Settings */}
                <div className="bg-card text-card-foreground rounded-xl border shadow-sm flex flex-col overflow-hidden">
                    <div className="px-4 py-3 border-b flex-shrink-0">
                        <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-foreground flex items-center gap-2">
                                Recent Updates
                                <RefreshCw className={cn('w-4 h-4 text-primary', isRefreshing && 'animate-spin')} />
                            </h3>
                            <button
                                onClick={handleRefresh}
                                className="text-xs text-primary hover:text-primary/80 min-h-[44px] px-2 flex items-center gap-1"
                            >
                                Refresh
                            </button>
                        </div>
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                            <Select value={refreshInterval} onValueChange={(value) => setRefreshInterval(value as RefreshInterval)}>
                                <SelectTrigger className="w-auto min-w-[5rem] h-8 text-xs bg-secondary border">
                                    <Settings className="w-3 h-3 mr-1" />
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="15s">15 sec</SelectItem>
                                    <SelectItem value="2m">2 min</SelectItem>
                                    <SelectItem value="10m">10 min</SelectItem>
                                </SelectContent>
                            </Select>
                            <Select value={cityFilter} onValueChange={handleCityFilterChange}>
                                <SelectTrigger className="w-auto min-w-[5.5rem] h-8 text-xs bg-secondary border">
                                    <MapPin className="w-3 h-3 mr-1" />
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Cities</SelectItem>
                                    <SelectItem value="delhi">Delhi</SelectItem>
                                    <SelectItem value="bangalore">Bangalore</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="divide-y divide-border overflow-y-auto max-h-80">
                        {/* Sensor Alerts with Location and Locate Button */}
                        {filteredAlerts.length > 0 ? (
                            filteredAlerts.slice(0, 2).map((alert, _index) => (
                                <div key={alert.id} className="p-3">
                                    <div className="flex items-start gap-3">
                                        <div className={cn(
                                            'p-2 rounded-full flex-shrink-0',
                                            alert.level === 'critical' ? 'bg-red-100 text-red-600' : 'bg-yellow-100 text-yellow-600'
                                        )}>
                                            <AlertTriangle className="w-4 h-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="text-xs text-muted-foreground">{formatTimeAgo(alert.timestamp)}</div>
                                            <div className="font-medium text-sm mt-1 text-foreground">
                                                {alert.level === 'critical' ? 'High' : 'Moderate'} water detected - {alert.location}
                                            </div>
                                            <div className="text-sm text-muted-foreground">
                                                {alert.description}
                                            </div>
                                            {/* Location Display */}
                                            <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                                                <MapPin className="w-3 h-3" />
                                                <span>
                                                    {detectCityFromCoordinates(alert.coordinates[0], alert.coordinates[1])}
                                                    {' · '}
                                                    {alert.coordinates[1].toFixed(4)}, {alert.coordinates[0].toFixed(4)}
                                                </span>
                                            </div>
                                            <div className="flex gap-2 mt-2 flex-wrap">
                                                <button
                                                    onClick={() => onAlertClick(alert)}
                                                    className="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded-lg hover:bg-blue-100 transition-colors min-h-[44px]"
                                                >
                                                    View
                                                </button>
                                                <button
                                                    onClick={() => handleLocateAlert(alert.coordinates[1], alert.coordinates[0], alert.location)}
                                                    className="text-xs bg-purple-50 text-purple-600 px-2 py-1 rounded-lg hover:bg-purple-100 transition-colors min-h-[44px] flex items-center gap-1"
                                                >
                                                    <MapPinned className="w-3 h-3" />
                                                    Locate
                                                </button>
                                                <button
                                                    onClick={() => handleShare(alert)}
                                                    className="text-xs bg-secondary text-muted-foreground px-2 py-1 rounded-lg hover:bg-secondary/80 transition-colors min-h-[44px]"
                                                >
                                                    <Share2 className="w-3 h-3 inline mr-1" />
                                                    Share
                                                </button>
                                                <button
                                                    onClick={() => handleNavigateRoutes(alert)}
                                                    className="text-xs bg-green-50 text-green-600 px-2 py-1 rounded-lg hover:bg-green-100 transition-colors min-h-[44px]"
                                                >
                                                    Alt Routes
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ))
                        ) : null}

                        {/* Community Reports with Location and Locate Button */}
                        {filteredReports && filteredReports.length > 0 ? (
                            filteredReports.slice(0, 2).map((report) => (
                                <div key={report.id} className="p-3">
                                    <div className="flex items-start gap-3">
                                        <div className={cn(
                                            'p-2 rounded-full flex-shrink-0',
                                            report.verified ? 'bg-green-100 text-green-600' : 'bg-yellow-100 text-yellow-600'
                                        )}>
                                            <Users className="w-4 h-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="text-xs text-muted-foreground">{formatTimeAgo(report.timestamp)}</div>
                                            <div className="font-medium text-sm mt-1 text-foreground">
                                                {report.verified ? 'Community Report Verified' : 'Community Report'}
                                            </div>
                                            <div className="text-sm text-muted-foreground line-clamp-2">
                                                {report.description}
                                            </div>
                                            {/* Location Display */}
                                            <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                                                <MapPin className="w-3 h-3" />
                                                <span>
                                                    {detectCityFromCoordinates(report.longitude, report.latitude)}
                                                    {' · '}
                                                    {report.latitude.toFixed(4)}, {report.longitude.toFixed(4)}
                                                </span>
                                            </div>
                                            <div className="flex gap-2 mt-2 flex-wrap">
                                                <button
                                                    onClick={(e) => {
                                                    e.stopPropagation();
                                                    console.log('View clicked, setting report:', report?.id);
                                                    setSelectedReport(report);
                                                }}
                                                    className="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded-lg hover:bg-blue-100 transition-colors min-h-[44px]"
                                                >
                                                    View
                                                </button>
                                                <button
                                                    onClick={() => handleLocateAlert(report.latitude, report.longitude, 'Report Location')}
                                                    className="text-xs bg-purple-50 text-purple-600 px-2 py-1 rounded-lg hover:bg-purple-100 transition-colors min-h-[44px] flex items-center gap-1"
                                                >
                                                    <MapPinned className="w-3 h-3" />
                                                    Locate
                                                </button>
                                                {!report.verified && (
                                                    <button
                                                        onClick={handleThankReporter}
                                                        className="text-xs bg-amber-50 text-amber-600 px-2 py-1 rounded-lg hover:bg-amber-100 transition-colors min-h-[44px]"
                                                    >
                                                        <ThumbsUp className="w-3 h-3 inline mr-1" />
                                                        Thank
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ))
                        ) : null}

                        {/* All Clear Message */}
                        {filteredAlerts.length === 0 && (!filteredReports || filteredReports.length === 0) && (
                            <div className="p-4">
                                <div className="flex items-start gap-3">
                                    <div className="bg-green-100 text-green-600 p-2 rounded-full">
                                        <Shield className="w-4 h-4" />
                                    </div>
                                    <div className="flex-1">
                                        <div className="text-xs text-muted-foreground">Just now</div>
                                        <div className="font-medium text-sm mt-1 text-foreground">
                                            All Systems Normal
                                        </div>
                                        <div className="text-sm text-muted-foreground">
                                            No flood alerts in your area. Stay safe!
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Join Ambassadors Widget — with photo accent */}
                <div className="relative rounded-xl shadow-sm overflow-hidden flex-shrink-0">
                    {/* Photo background with overlay */}
                    <img
                        src="/images/community-umbrella.jpg"
                        alt=""
                        className="absolute inset-0 w-full h-full object-cover"
                    />
                    <div className="absolute inset-0" style={{ background: 'linear-gradient(to right, rgba(37, 99, 235, 0.75), rgba(59, 130, 246, 0.6))' }} />
                    <div className="relative z-10 p-4">
                        <div className="flex items-center gap-3">
                            <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
                                <Users className="w-6 h-6 text-white" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="font-semibold text-white">Join Ambassadors</div>
                                <div className="text-sm text-white/80">Help your community stay safe</div>
                            </div>
                            <button
                                onClick={handleJoinAmbassadors}
                                className="bg-white text-blue-600 px-4 py-2 rounded-lg font-medium text-sm hover:bg-white/90 transition-colors min-h-[44px] flex-shrink-0"
                            >
                                Join
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Location Details Dialog */}
            <Dialog open={selectedLocation !== null} onOpenChange={(open) => !open && setSelectedLocation(null)}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Location Details</DialogTitle>
                        <DialogDescription>
                            Reports and sensor data at this location
                        </DialogDescription>
                    </DialogHeader>

                    {locationDetails && (
                        <div className="space-y-4">
                            {hasLocationData(locationDetails.location) && (
                                <div className="text-sm text-muted-foreground">
                                    <div className="flex items-center gap-2">
                                        <MapPin className="w-4 h-4" />
                                        <span>
                                            {locationDetails.location.latitude.toFixed(4)}, {locationDetails.location.longitude.toFixed(4)}
                                        </span>
                                    </div>
                                    <div className="mt-1">
                                        Search Radius: {locationDetails.location.radius_meters || 500}m
                                    </div>
                                </div>
                            )}

                            <div>
                                <h4 className="font-semibold mb-2">
                                    Total Reports: {locationDetails.total_reports || 0}
                                </h4>

                                {getNestedArray(locationDetails, ['reports']).length > 0 ? (
                                    <div className="space-y-2">
                                        {getNestedArray(locationDetails, ['reports']).map((report: any) => (
                                            <Card key={report.id} className="p-3">
                                                <div className="flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <div className="text-sm font-medium">{report.description}</div>
                                                        <div className="text-xs text-muted-foreground mt-1">
                                                            {formatTimeAgo(report.timestamp)}
                                                        </div>
                                                        {report.verified && (
                                                            <Badge className="mt-1 bg-green-500 text-white text-xs">Verified</Badge>
                                                        )}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {report.upvotes} upvotes
                                                    </div>
                                                </div>
                                            </Card>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No reports at this location</p>
                                )}
                            </div>

                            <div>
                                <h4 className="font-semibold mb-2">
                                    Reporters ({getNestedArray(locationDetails, ['reporters']).length})
                                </h4>

                                {getNestedArray(locationDetails, ['reporters']).length > 0 ? (
                                    <div className="space-y-2">
                                        {getNestedArray(locationDetails, ['reporters']).map((reporter: any) => (
                                            <Card key={reporter.id} className="p-3">
                                                <div className="flex items-center justify-between">
                                                    <div>
                                                        <div className="font-medium text-sm">{reporter.username}</div>
                                                        <div className="text-xs text-muted-foreground">
                                                            Level {reporter.level} • {reporter.reports_count} total reports • {reporter.verified_reports_count} verified
                                                        </div>
                                                    </div>
                                                </div>
                                            </Card>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No reporter information available</p>
                                )}
                            </div>

                            <button
                                onClick={() => {
                                    onNavigateToMap?.();
                                    setSelectedLocation(null);
                                }}
                                className="w-full bg-primary text-primary-foreground py-2 rounded-lg hover:bg-primary/90 transition-colors min-h-[44px]"
                            >
                                View on Full Map
                            </button>
                        </div>
                    )}

                    {!locationDetails && selectedLocation && (
                        <div className="text-center py-8">
                            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">Loading location details...</p>
                        </div>
                    )}
                </DialogContent>
            </Dialog>

            {/* Report Detail Modal */}
            <ReportDetailModal
                report={selectedReport}
                isOpen={selectedReport !== null}
                onClose={() => setSelectedReport(null)}
                onLocate={(lat, lng) => handleLocateAlert(lat, lng, 'Report Location')}
            />

            {/* Emergency Contacts Modal */}
            <EmergencyContactsModal
                isOpen={emergencyModalOpen}
                onClose={() => setEmergencyModalOpen(false)}
            />

        </div>
    );
}
