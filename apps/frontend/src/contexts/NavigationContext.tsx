import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useVoiceGuidance } from './VoiceGuidanceContext';
import { haversineDistance, isOffRoute, findNextInstruction, findNearbyHotspots, getRemainingRoute, calculateBearing } from '../lib/geo/distance';
import { useHotspots } from '../lib/api/hooks';
import { useCurrentCity } from './CityContext';
import { getCityCode } from '../lib/cityUtils';

interface TurnInstruction {
    instruction: string;
    distance_meters: number;
    duration_seconds: number;
    maneuver_type: string;
    maneuver_modifier: string;
    street_name: string;
    coordinates: [number, number];
}

interface ActiveRoute {
    id: string;
    type: 'fastest' | 'metro' | 'safest';
    coordinates: [number, number][];
    instructions: TurnInstruction[];
    destination: { lat: number; lng: number };
    totalDistanceMeters: number;
    totalDurationSeconds: number;
}

interface NavigationState {
    isNavigating: boolean;
    activeRoute: ActiveRoute | null;
    currentPosition: { lat: number; lng: number } | null;
    currentInstruction: TurnInstruction | null;
    distanceToNextTurn: number;
    distanceRemaining: number;
    etaSeconds: number;
    isOffRoute: boolean;
    isRecalculating: boolean;
    nearbyHotspots: Array<{ id: number; name: string; fhi_level: string; fhi_color: string; distanceMeters: number }>;
    remainingRouteCoordinates: [number, number][]; // Trimmed route for display (from current position to destination)
    lastMatchedSegmentIdx: number; // Track progress along route to prevent GPS-jump snapping
    heading: number | null; // Degrees clockwise from north (0-360), null when unknown
}

interface NavigationContextValue {
    state: NavigationState;
    startNavigation: (route: ActiveRoute) => void;
    stopNavigation: () => void;
    recalculateRoute: () => Promise<void>;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

const DEVIATION_THRESHOLD_METERS = 50;
const HOTSPOT_ALERT_RADIUS_METERS = 400;
const RECALCULATION_COOLDOWN_MS = 5000;
const TURN_ANNOUNCEMENT_DISTANCE_METERS = 100;

export function NavigationProvider({ children }: { children: React.ReactNode }) {
    const city = useCurrentCity();
    const { speak } = useVoiceGuidance();
    const hasHotspots = ['delhi', 'yogyakarta', 'singapore'].includes(city);
    const { data: hotspotsData } = useHotspots({ enabled: hasHotspots, city });

    const [state, setState] = useState<NavigationState>({
        isNavigating: false,
        activeRoute: null,
        currentPosition: null,
        currentInstruction: null,
        distanceToNextTurn: 0,
        distanceRemaining: 0,
        etaSeconds: 0,
        isOffRoute: false,
        isRecalculating: false,
        nearbyHotspots: [],
        remainingRouteCoordinates: [],
        lastMatchedSegmentIdx: 0,
        heading: null,
    });

    const watchIdRef = useRef<number | null>(null);
    const lastRecalcTimeRef = useRef<number>(0);
    const recalculatingRef = useRef<boolean>(false); // Prevent race conditions
    const spokenInstructionsRef = useRef<Set<string>>(new Set());
    const alertedHotspotsRef = useRef<Set<number>>(new Set());
    const prevPositionRef = useRef<{ lat: number; lng: number } | null>(null);

    const startNavigation = useCallback((route: ActiveRoute) => {
        setState(prev => ({
            ...prev,
            isNavigating: true,
            activeRoute: route,
            isOffRoute: false,
            distanceRemaining: route.totalDistanceMeters,
            etaSeconds: route.totalDurationSeconds,
            remainingRouteCoordinates: route.coordinates, // Full route at start
            lastMatchedSegmentIdx: 0, // Start from beginning of route
        }));

        spokenInstructionsRef.current.clear();
        alertedHotspotsRef.current.clear();

        speak('Navigation started. Follow the route shown on map.', 'high');
        toast.success('Navigation started');
    }, [speak]);

    const stopNavigation = useCallback(() => {
        // CRITICAL: Always clear GPS watch first to prevent memory leaks
        if (watchIdRef.current !== null) {
            navigator.geolocation.clearWatch(watchIdRef.current);
            watchIdRef.current = null;
        }

        // Reset all refs
        recalculatingRef.current = false;
        spokenInstructionsRef.current.clear();
        alertedHotspotsRef.current.clear();
        prevPositionRef.current = null;

        // Reset full state (not spread) for clean stop
        setState({
            isNavigating: false,
            activeRoute: null,
            currentPosition: null,
            currentInstruction: null,
            distanceToNextTurn: 0,
            distanceRemaining: 0,
            etaSeconds: 0,
            isOffRoute: false,
            isRecalculating: false,
            nearbyHotspots: [],
            remainingRouteCoordinates: [],
            lastMatchedSegmentIdx: 0,
            heading: null,
        });

        speak('Navigation ended.', 'high');
        toast.info('Navigation stopped');
    }, [speak]);

    const recalculateRoute = useCallback(async () => {
        const now = Date.now();
        if (now - lastRecalcTimeRef.current < RECALCULATION_COOLDOWN_MS) {
            return; // Cooldown not elapsed
        }
        lastRecalcTimeRef.current = now;

        if (!state.activeRoute || !state.currentPosition) return;

        setState(prev => ({ ...prev, isRecalculating: true }));

        try {
            const response = await fetch('/api/routes/recalculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_position: state.currentPosition,
                    destination: state.activeRoute.destination,
                    route_type: state.activeRoute.type,
                    city: getCityCode(city),
                }),
            });

            if (!response.ok) throw new Error('Recalculation failed');

            const data = await response.json();

            if (data.route) {
                setState(prev => ({
                    ...prev,
                    activeRoute: {
                        ...prev.activeRoute!,
                        coordinates: data.route.coordinates,
                        instructions: data.route.instructions,
                        totalDistanceMeters: data.route.distance_meters,
                        totalDurationSeconds: data.route.duration_seconds,
                    },
                    isOffRoute: false,
                    isRecalculating: false,
                    distanceRemaining: data.route.distance_meters,
                    etaSeconds: data.route.duration_seconds,
                    remainingRouteCoordinates: data.route.coordinates, // New route from current position
                    lastMatchedSegmentIdx: 0, // Reset segment tracking for new route
                }));

                speak('Route recalculated. Follow the new route.', 'high');
                toast.info('Route recalculated');
                spokenInstructionsRef.current.clear();
            }
        } catch (error) {
            console.error('Route recalculation error:', error);
            setState(prev => ({
                ...prev,
                isRecalculating: false,
                isOffRoute: false  // Reset to prevent infinite recalculation loop
            }));
            toast.error('Could not recalculate route. Continuing on original route.');
        } finally {
            recalculatingRef.current = false;
        }
    }, [state.activeRoute, state.currentPosition, city, speak]);

    // GPS tracking during navigation
    useEffect(() => {
        if (!state.isNavigating || !state.activeRoute) {
            if (watchIdRef.current !== null) {
                navigator.geolocation.clearWatch(watchIdRef.current);
                watchIdRef.current = null;
            }
            return;
        }

        watchIdRef.current = navigator.geolocation.watchPosition(
            (position) => {
                const currentPos = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                };

                // Extract heading: prefer native GPS heading, fallback to computed bearing
                let heading: number | null = null;
                const nativeHeading = position.coords.heading;
                if (nativeHeading !== null && !isNaN(nativeHeading) && nativeHeading >= 0) {
                    heading = nativeHeading;
                } else if (prevPositionRef.current) {
                    // Only compute bearing if moved >= 3m (avoids jitter when stationary)
                    const moved = haversineDistance(
                        prevPositionRef.current.lat, prevPositionRef.current.lng,
                        currentPos.lat, currentPos.lng
                    );
                    if (moved >= 3) {
                        heading = calculateBearing(
                            prevPositionRef.current.lat, prevPositionRef.current.lng,
                            currentPos.lat, currentPos.lng
                        );
                    }
                }

                // Update prev position ref when we've moved significantly
                if (!prevPositionRef.current ||
                    haversineDistance(prevPositionRef.current.lat, prevPositionRef.current.lng,
                                     currentPos.lat, currentPos.lng) >= 3) {
                    prevPositionRef.current = currentPos;
                }

                setState(prev => {
                    if (!prev.activeRoute) return prev;

                    // Check if off route
                    const offRoute = isOffRoute(
                        currentPos.lat,
                        currentPos.lng,
                        prev.activeRoute.coordinates,
                        DEVIATION_THRESHOLD_METERS
                    );

                    // Find next instruction
                    const nextInstr = findNextInstruction(
                        currentPos.lat,
                        currentPos.lng,
                        prev.activeRoute.instructions
                    );

                    // Calculate remaining distance to destination
                    const destDist = haversineDistance(
                        currentPos.lat, currentPos.lng,
                        prev.activeRoute.destination.lat,
                        prev.activeRoute.destination.lng
                    );

                    // Check for nearby hotspots
                    let nearbyHotspots: any[] = [];
                    if (hotspotsData?.features) {
                        const hotspots = hotspotsData.features.map(f => ({
                            id: f.properties.id,
                            name: f.properties.name,
                            fhi_level: f.properties.fhi_level || 'moderate',
                            fhi_color: f.properties.fhi_color || '#9ca3af',
                            coordinates: f.geometry.coordinates as [number, number],
                        }));
                        nearbyHotspots = findNearbyHotspots(
                            currentPos.lat, currentPos.lng,
                            hotspots,
                            HOTSPOT_ALERT_RADIUS_METERS
                        );
                    }

                    // Compute remaining route for display (windowed segment search prevents GPS-jump straight lines)
                    const remainingResult = getRemainingRoute(
                        currentPos.lat,
                        currentPos.lng,
                        prev.activeRoute.coordinates,
                        prev.lastMatchedSegmentIdx,
                    );

                    return {
                        ...prev,
                        currentPosition: currentPos,
                        currentInstruction: nextInstr?.instruction || null,
                        distanceToNextTurn: nextInstr?.distanceToNext || 0,
                        distanceRemaining: destDist,
                        etaSeconds: Math.round(destDist / 10), // Rough estimate: 10 m/s avg speed
                        isOffRoute: offRoute,
                        nearbyHotspots,
                        remainingRouteCoordinates: remainingResult.coordinates,
                        lastMatchedSegmentIdx: remainingResult.segmentIdx,
                        heading: heading ?? prev.heading, // Retain previous heading when stationary
                    };
                });
            },
            (error) => {
                console.error('GPS error during navigation:', error);
            },
            {
                enableHighAccuracy: true,
                maximumAge: 5000,
                timeout: 10000,
            }
        );

        return () => {
            if (watchIdRef.current !== null) {
                navigator.geolocation.clearWatch(watchIdRef.current);
                watchIdRef.current = null;
            }
        };
    }, [state.isNavigating, state.activeRoute, hotspotsData]);

    // Handle off-route detection -> auto recalculate
    useEffect(() => {
        if (state.isOffRoute && !state.isRecalculating && !recalculatingRef.current) {
            recalculatingRef.current = true;
            recalculateRoute();
        }
    }, [state.isOffRoute, state.isRecalculating, recalculateRoute]);

    // Voice announcements for turns
    useEffect(() => {
        if (!state.currentInstruction || !state.isNavigating) return;

        const instrKey = `${state.currentInstruction.coordinates[0]}-${state.currentInstruction.coordinates[1]}`;

        if (state.distanceToNextTurn <= TURN_ANNOUNCEMENT_DISTANCE_METERS &&
            !spokenInstructionsRef.current.has(instrKey)) {
            spokenInstructionsRef.current.add(instrKey);
            speak(`In ${Math.round(state.distanceToNextTurn)} meters, ${state.currentInstruction.instruction}`);
        }
    }, [state.currentInstruction, state.distanceToNextTurn, state.isNavigating, speak]);

    // Voice announcements for hotspot proximity
    useEffect(() => {
        if (!state.isNavigating) return;

        for (const hotspot of state.nearbyHotspots) {
            if (!alertedHotspotsRef.current.has(hotspot.id)) {
                alertedHotspotsRef.current.add(hotspot.id);
                const level = hotspot.fhi_level.toUpperCase();
                speak(`Warning: Approaching ${hotspot.name}. ${level} flood risk ahead.`, 'high');
                toast.warning(`Approaching ${hotspot.name}`, {
                    description: `${level} flood risk - ${Math.round(hotspot.distanceMeters)}m away`,
                });
            }
        }
    }, [state.nearbyHotspots, state.isNavigating, speak]);

    return (
        <NavigationContext.Provider value={{ state, startNavigation, stopNavigation, recalculateRoute }}>
            {children}
        </NavigationContext.Provider>
    );
}

export function useNavigation() {
    const context = useContext(NavigationContext);
    if (!context) {
        throw new Error('useNavigation must be used within NavigationProvider');
    }
    return context;
}
