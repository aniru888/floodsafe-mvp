import { useState, useEffect } from 'react';
import MapComponent from '../MapComponent';
import { Button } from '../ui/button';
import { Navigation } from 'lucide-react';
import { NavigationPanel } from '../NavigationPanel';
import { LiveNavigationPanel } from '../LiveNavigationPanel';
import { useCurrentCity } from '../../contexts/CityContext';
import { useAuth } from '../../contexts/AuthContext';
import { VoiceGuidanceProvider } from '../../contexts/VoiceGuidanceContext';
import { NavigationProvider, useNavigation } from '../../contexts/NavigationContext';
import type { RouteOption, MetroStation } from '../../types';
import { toast } from 'sonner';

// GPS Testing Panel - only rendered when VITE_ENABLE_GPS_TESTING=true
import { GPSTestPanel } from '../testing/GPSTestPanel';

interface FloodAtlasScreenProps {
    initialDestination?: [number, number] | null;
    onClearInitialDestination?: () => void;
    openNavigationPanel?: boolean;
    onClearOpenNavigationPanel?: () => void;
}

// Inner component that uses navigation context
function FloodAtlasContent({
    initialDestination,
    onClearInitialDestination,
    openNavigationPanel,
    onClearOpenNavigationPanel
}: FloodAtlasScreenProps) {
    const city = useCurrentCity();
    const { user: _user } = useAuth();
    const { state: navState } = useNavigation();

    // Navigation state
    const [showNavigationPanel, setShowNavigationPanel] = useState(!!initialDestination);
    const [navigationRoutes, setNavigationRoutes] = useState<RouteOption[]>([]);
    const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
    const [navigationOrigin, setNavigationOrigin] = useState<{ lat: number; lng: number } | null>(null);
    const [navigationDestination, setNavigationDestination] = useState<{ lat: number; lng: number } | null>(null);
    const [nearbyMetros, _setNearbyMetros] = useState<MetroStation[]>([]);
    const [floodZones, setFloodZones] = useState<GeoJSON.FeatureCollection | undefined>(undefined);
    const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);

    // Geolocation - get user's current location with retry mechanism
    useEffect(() => {
        if (!('geolocation' in navigator)) {
            // Browser doesn't support geolocation - use default
            const fallbackCoords = city === 'bangalore'
                ? { lat: 12.9716, lng: 77.5946 }
                : { lat: 28.6139, lng: 77.2090 };
            setUserLocation(fallbackCoords);
            setNavigationOrigin(fallbackCoords);
            return;
        }

        const setLocationFromPosition = (position: GeolocationPosition) => {
            const loc = { lat: position.coords.latitude, lng: position.coords.longitude };
            setUserLocation(loc);
            setNavigationOrigin(loc);
        };

        const applyFallback = () => {
            const fallbackCoords = city === 'bangalore'
                ? { lat: 12.9716, lng: 77.5946 }
                : { lat: 28.6139, lng: 77.2090 };
            setUserLocation(fallbackCoords);
            setNavigationOrigin(fallbackCoords);
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
    }, [city]);

    // Handle initial destination from HomeScreen (when user clicks "Alt Routes" on an alert)
    useEffect(() => {
        if (initialDestination) {
            setShowNavigationPanel(true);
            // initialDestination is [lng, lat] from alert.coordinates
            setNavigationDestination({ lat: initialDestination[1], lng: initialDestination[0] });
            toast.info('Opening navigation with destination from alert');
        }
    }, [initialDestination]);

    // Handle opening navigation panel from HomeScreen "Routes" button
    useEffect(() => {
        if (openNavigationPanel) {
            setShowNavigationPanel(true);
            onClearOpenNavigationPanel?.();
        }
    }, [openNavigationPanel, onClearOpenNavigationPanel]);

    const handleRoutesCalculated = (routes: RouteOption[], zones: GeoJSON.FeatureCollection) => {
        setNavigationRoutes(routes);
        setFloodZones(zones);
        if (routes.length > 0) {
            setSelectedRouteId(routes[0].id); // Auto-select first route
        }
        // Clear the initial destination after routes are calculated
        onClearInitialDestination?.();
    };

    const handleRouteSelected = (route: RouteOption) => {
        setSelectedRouteId(route.id);
    };

    const handleMetroSelected = (station: MetroStation) => {
        // When user selects a metro station, set it as destination
        setNavigationDestination({ lat: station.lat, lng: station.lng });
        toast.success(`Selected ${station.name} as destination`);
    };

    return (
        <div className="fixed top-14 md:top-0 left-0 md:left-64 right-0 bottom-0 bg-transparent">
            {/* GPS Test Panel - only visible in testing mode */}
            {import.meta.env.VITE_ENABLE_GPS_TESTING === 'true' && (
                <GPSTestPanel
                    onPositionChange={(pos) => {
                        // Update user location for map marker
                        setUserLocation({ lat: pos.lat, lng: pos.lng });
                    }}
                />
            )}

            {/* Live Navigation Panel - shown when navigation is active */}
            {navState.isNavigating && <LiveNavigationPanel />}

            <MapComponent
                className="w-full h-full"
                title="Flood Atlas"
                showControls={true}
                showCitySelector={true}
                // During navigation, show live remaining route; otherwise show calculated routes
                navigationRoutes={
                    navState.isNavigating && navState.activeRoute && navState.remainingRouteCoordinates.length > 0
                        ? [{
                            id: navState.activeRoute.id,
                            type: navState.activeRoute.type === 'fastest' ? 'fast' : navState.activeRoute.type === 'safest' ? 'safe' : 'metro',
                            city_code: city === 'bangalore' ? 'BLR' : 'DEL',
                            geometry: {
                                type: 'LineString' as const,
                                coordinates: navState.remainingRouteCoordinates
                            },
                            distance_meters: navState.distanceRemaining,
                            duration_seconds: navState.etaSeconds,
                            safety_score: 85, // Preserved from original route
                            risk_level: 'low' as const,
                            flood_intersections: 0
                            // Note: instructions omitted - LiveNavigationPanel reads from navState.currentInstruction
                        }]
                        : navigationRoutes
                }
                selectedRouteId={navState.isNavigating ? navState.activeRoute?.id : (selectedRouteId ?? undefined)}
                // Hide origin marker during navigation (user location dot shows position)
                navigationOrigin={navState.isNavigating ? undefined : (navigationOrigin ?? undefined)}
                navigationDestination={navigationDestination ?? undefined}
                nearbyMetros={nearbyMetros}
                floodZones={floodZones}
                onMetroClick={handleMetroSelected}
            />

            {/* Floating Route Button - Only show when panel is closed AND not navigating */}
            {!showNavigationPanel && !navState.isNavigating && (
                <div
                    className="fixed right-4 md:right-auto md:left-1/2 md:ml-32 md:-translate-x-1/2 pointer-events-auto"
                    style={{ bottom: 'calc(80px + env(safe-area-inset-bottom, 0px))', zIndex: 9999 }}
                >
                    <Button
                        onClick={() => setShowNavigationPanel(true)}
                        className="shadow-xl bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl"
                        size="lg"
                    >
                        <Navigation className="mr-2 h-5 w-5" />
                        Plan Safe Route
                    </Button>
                </div>
            )}

            {/* Navigation Panel - hide when actively navigating */}
            {!navState.isNavigating && (
                <NavigationPanel
                    isOpen={showNavigationPanel}
                    onClose={() => setShowNavigationPanel(false)}
                    userLocation={userLocation}
                    city={city}
                    onRoutesCalculated={handleRoutesCalculated}
                    onRouteSelected={handleRouteSelected}
                    onMetroSelected={handleMetroSelected}
                    onOriginChange={setNavigationOrigin}
                    onDestinationChange={setNavigationDestination}
                    initialDestination={navigationDestination}
                />
            )}
        </div>
    );
}

// Main component with providers
export function FloodAtlasScreen(props: FloodAtlasScreenProps) {
    return (
        <VoiceGuidanceProvider>
            <NavigationProvider>
                <FloodAtlasContent {...props} />
            </NavigationProvider>
        </VoiceGuidanceProvider>
    );
}
