import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { haversineDistance, findNearbyHotspots } from '../lib/geo/distance';
import { useHotspots } from '../lib/api/hooks';
import { useCurrentCity } from './CityContext';

interface LocationTrackingState {
    isTracking: boolean;
    isEnabled: boolean;
    currentPosition: { lat: number; lng: number } | null;
    nearbyHotspots: Array<{
        id: number;
        name: string;
        fhi_level: string;
        fhi_color: string;
        distanceMeters: number;
    }>;
}

interface LocationTrackingContextValue {
    state: LocationTrackingState;
    setEnabled: (enabled: boolean) => void;
}

const LocationTrackingContext = createContext<LocationTrackingContextValue | null>(null);

const PROXIMITY_RADIUS_METERS = 400;
const ALERT_COOLDOWN_DISTANCE_METERS = 1000; // User must move 1km before re-alerting

export function LocationTrackingProvider({ children }: { children: React.ReactNode }) {
    const city = useCurrentCity();
    const hasHotspots = ['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore'].includes(city);
    const { data: hotspotsData } = useHotspots({ enabled: hasHotspots, city });

    const [state, setState] = useState<LocationTrackingState>({
        isTracking: false,
        isEnabled: false, // Disabled by default (user must opt-in)
        currentPosition: null,
        nearbyHotspots: [],
    });

    const watchIdRef = useRef<number | null>(null);
    const alertedHotspotsRef = useRef<Map<number, { lat: number; lng: number }>>(new Map());

    const setEnabled = useCallback((enabled: boolean) => {
        setState(prev => ({ ...prev, isEnabled: enabled }));
        localStorage.setItem('floodsafe_location_tracking_enabled', String(enabled));

        if (enabled) {
            toast.success('Background location tracking enabled');
        } else {
            toast.info('Background location tracking disabled');
        }
    }, []);

    // Load preference from localStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem('floodsafe_location_tracking_enabled');
        if (saved !== null) {
            setState(prev => ({ ...prev, isEnabled: saved === 'true' }));
        }
    }, []);

    // Start/stop GPS tracking based on isEnabled
    useEffect(() => {
        // Only track if:
        // 1. Feature is enabled
        // 2. City has hotspot data (Delhi, Yogyakarta)
        // 3. Not already tracking
        if (state.isEnabled && hasHotspots && !state.isTracking) {
            setState(prev => ({ ...prev, isTracking: true }));

            watchIdRef.current = navigator.geolocation.watchPosition(
                (position) => {
                    const currentPos = {
                        lat: position.coords.latitude,
                        lng: position.coords.longitude,
                    };

                    setState(prev => {
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
                                currentPos.lat,
                                currentPos.lng,
                                hotspots,
                                PROXIMITY_RADIUS_METERS
                            );
                        }

                        return {
                            ...prev,
                            currentPosition: currentPos,
                            nearbyHotspots,
                        };
                    });
                },
                (error) => {
                    console.error('Background GPS error:', error);
                    // Don't show error toast on permission denial (user may have rejected)
                    if (error.code !== error.PERMISSION_DENIED) {
                        toast.error('Location tracking error');
                    }
                },
                {
                    enableHighAccuracy: true,
                    maximumAge: 5000, // Reuse cached positions to save battery
                    timeout: 10000,
                }
            );
        } else if ((!state.isEnabled || !hasHotspots) && state.isTracking) {
            // Stop tracking when disabled or when city doesn't have hotspot data
            if (watchIdRef.current !== null) {
                navigator.geolocation.clearWatch(watchIdRef.current);
                watchIdRef.current = null;
            }
            setState(prev => ({ ...prev, isTracking: false, nearbyHotspots: [] }));
        }

        return () => {
            if (watchIdRef.current !== null) {
                navigator.geolocation.clearWatch(watchIdRef.current);
                watchIdRef.current = null;
            }
        };
    }, [state.isEnabled, state.isTracking, hasHotspots, hotspotsData]);

    // Alert for nearby hotspots (with cooldown)
    useEffect(() => {
        if (!state.isTracking || !state.currentPosition) return;

        for (const hotspot of state.nearbyHotspots) {
            const previousAlertLocation = alertedHotspotsRef.current.get(hotspot.id);

            // Only alert if:
            // 1. Never alerted for this hotspot, OR
            // 2. User has moved more than cooldown distance since last alert
            const shouldAlert = !previousAlertLocation ||
                haversineDistance(
                    state.currentPosition.lat,
                    state.currentPosition.lng,
                    previousAlertLocation.lat,
                    previousAlertLocation.lng
                ) > ALERT_COOLDOWN_DISTANCE_METERS;

            if (shouldAlert) {
                alertedHotspotsRef.current.set(hotspot.id, {
                    lat: state.currentPosition.lat,
                    lng: state.currentPosition.lng,
                });

                const level = hotspot.fhi_level.toUpperCase();
                toast.warning(`Nearby: ${hotspot.name}`, {
                    description: `${level} flood risk - ${Math.round(hotspot.distanceMeters)}m away`,
                    duration: 5000,
                });
            }
        }

        // Clean up alerted hotspots that are no longer nearby
        const nearbyHotspotIds = new Set(state.nearbyHotspots.map(h => h.id));
        for (const [id] of alertedHotspotsRef.current) {
            if (!nearbyHotspotIds.has(id)) {
                alertedHotspotsRef.current.delete(id);
            }
        }
    }, [state.nearbyHotspots, state.isTracking, state.currentPosition]);

    return (
        <LocationTrackingContext.Provider value={{ state, setEnabled }}>
            {children}
        </LocationTrackingContext.Provider>
    );
}

export function useLocationTracking() {
    const context = useContext(LocationTrackingContext);
    if (!context) {
        throw new Error('useLocationTracking must be used within LocationTrackingProvider');
    }
    return context;
}

