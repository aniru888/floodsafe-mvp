import { useEffect, useRef, useState, useCallback } from 'react';
import { useMap } from '../lib/map/useMap';
import { useSensors, useReports, useHistoricalFloods, useHotspots, useFloodHubGauges, useFloodHubInundation, Sensor, Report } from '../lib/api/hooks';
// usePredictionGrid removed - ensemble models not trained (see line 95-105)
import maplibregl from 'maplibre-gl';
import { Button } from './ui/button';
import { Plus, Minus, Navigation, Layers, Train, AlertCircle, MapPin, History, Droplets, Waves, Camera } from 'lucide-react';
import MapLegend from './MapLegend';
import SearchBar from './SearchBar';
import HistoricalFloodsPanel from './HistoricalFloodsPanel';
import { useCurrentCity, useCityContext } from '../contexts/CityContext';
import { useAuth } from '../contexts/AuthContext';
import { useNavigation } from '../contexts/NavigationContext';
import { isWithinCityBounds, getAvailableCities, getCityConfig, getCityKeyFromCoordinates, CITIES, type CityKey } from '../lib/map/cityConfigs';
import { RouteOption, MetroStation } from '../types';
import { toast } from 'sonner';
import { parseReportDescription, generateTagHtml } from '../lib/tagParser';

interface MapComponentProps {
    className?: string;
    title?: string;
    showControls?: boolean;
    showCitySelector?: boolean;
    targetLocation?: { lat: number; lng: number } | null;
    onLocationReached?: () => void;
    // Navigation routing props
    navigationRoutes?: RouteOption[];
    selectedRouteId?: string;
    navigationOrigin?: { lat: number; lng: number };
    navigationDestination?: { lat: number; lng: number };
    nearbyMetros?: MetroStation[];
    floodZones?: GeoJSON.FeatureCollection;
    onMetroClick?: (station: MetroStation) => void;
}

interface LayersVisibility {
    flood: boolean;
    sensors: boolean;
    reports: boolean;
    routes: boolean;
    metro: boolean;
    predictions: boolean;  // ML flood hotspot predictions
    hotspots: boolean;     // 90 Delhi waterlogging hotspots (62 MCD + 28 OSM)
    floodhub: boolean;     // Google Flood Forecasting inundation extent
    pubCCTVs: boolean;     // PUB flood monitoring CCTVs (Singapore only)
}

interface MapBounds {
    minLng: number;
    minLat: number;
    maxLng: number;
    maxLat: number;
}

export default function MapComponent({
    className,
    title,
    showControls,
    showCitySelector,
    targetLocation,
    onLocationReached,
    navigationRoutes,
    selectedRouteId,
    navigationOrigin,
    navigationDestination,
    nearbyMetros,
    floodZones,
    onMetroClick
}: MapComponentProps) {
    const mapContainer = useRef<HTMLDivElement>(null);
    const city = useCurrentCity();
    const { setCity, syncCityToUser } = useCityContext();
    const { user } = useAuth();
    const { state: navState } = useNavigation();
    const { map, isLoaded } = useMap(mapContainer, city);
    const { data: sensors } = useSensors();
    const { data: reports } = useReports();
    const { data: historicalFloods } = useHistoricalFloods(city);
    const [layersVisible, setLayersVisible] = useState<LayersVisibility>({
        flood: true,
        sensors: true,
        reports: true,
        routes: true,
        metro: true,
        predictions: true,  // ON by default per user decision
        hotspots: true,     // Waterlogging hotspots ON by default
        floodhub: true,     // Google Flood Forecasting inundation ON by default
        pubCCTVs: false,    // PUB CCTVs OFF by default
    });
    const [_mapBounds, setMapBounds] = useState<MapBounds | null>(null);
    const [showHistoricalPanel, setShowHistoricalPanel] = useState(false);

    // User location tracking state
    const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
    const [isTrackingLocation, setIsTrackingLocation] = useState(false);
    const geolocationWatchId = useRef<number | null>(null);
    const alertedHotspotsRef = useRef<Set<string>>(new Set());
    const animationFrameRef = useRef<number | null>(null);

    // Cities with hotspot data available
    const HOTSPOT_CITIES = ['delhi', 'bangalore', 'yogyakarta', 'singapore'];
    const hasHotspots = HOTSPOT_CITIES.includes(city);
    // ML predictions (ensemble) are Delhi-only and currently disabled
    const isDelhiCity = city === 'delhi';

    // Fetch ML predictions for heatmap (only for Delhi)
    // DISABLED: Ensemble models (LSTM/GNN/LightGBM) are not trained yet
    // This prevents 404 console errors from /api/predictions/grid
    // Re-enable when ensemble models are trained and available
    const _predictionGrid = null;
    // const { data: _predictionGrid } = usePredictionGrid({
    //     bounds: mapBounds,
    //     resolutionKm: 2.0, // 2km resolution for performance
    //     horizonDays: 0,    // Today only
    //     enabled: isDelhiCity && layersVisible.predictions && !!mapBounds,
    // });

    // Fetch waterlogging hotspots (cities with data: Delhi + Yogyakarta)
    const { data: hotspotsData, error: hotspotsError } = useHotspots({
        enabled: hasHotspots,
        includeRainfall: true,
        city,
    });

    // Fetch Google Flood Forecasting gauge data for current city
    const { data: floodHubGauges } = useFloodHubGauges(city);

    // Find the highest-severity gauge with an inundation polygon available
    const activeInundationGauge = (floodHubGauges ?? []).find(
        g => g.severity !== 'NO_FLOODING' && g.severity !== 'UNKNOWN' && g.inundation_map_set
    );
    const inundationPolygonId = activeInundationGauge?.inundation_map_set?.HIGH
        ?? activeInundationGauge?.inundation_map_set?.MEDIUM
        ?? activeInundationGauge?.inundation_map_set?.LOW
        ?? null;
    const { data: inundationGeoJSON } = useFloodHubInundation(inundationPolygonId);

    const [isChangingCity, setIsChangingCity] = useState(false);
    const [mapStyleReady, setMapStyleReady] = useState(false);
    const availableCities = showCitySelector ? getAvailableCities() : [];
    const currentCityConfig = getCityConfig(city);

    const handleCityChange = (newCity: string) => {
        setIsChangingCity(true);
        // Type-safe city change with validation
        setCity(newCity as CityKey);
        // Give the map time to reinitialize
        setTimeout(() => setIsChangingCity(false), 500);
    };

    // Proximity alert configuration
    const PROXIMITY_ALERT_RADIUS_METERS = 500; // Alert when within 500m of hotspot
    const HIGH_RISK_LEVELS = ['high', 'extreme']; // FHI levels that trigger alerts

    // Haversine distance calculation (in meters)
    const calculateDistance = useCallback((lat1: number, lng1: number, lat2: number, lng2: number): number => {
        const R = 6371000; // Earth's radius in meters
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }, []);

    // Show "Coming Soon" message when switching to non-Delhi city with predictions enabled
    useEffect(() => {
        if (!isDelhiCity && layersVisible.predictions) {
            const cityName = city.charAt(0).toUpperCase() + city.slice(1);
            toast.info(`Flood predictions coming soon for ${cityName}`, {
                description: 'ML predictions are currently available only for Delhi',
                duration: 4000,
            });
            // Auto-disable predictions layer for non-Delhi cities
            setLayersVisible(prev => ({ ...prev, predictions: false }));
        }
    }, [city, isDelhiCity, layersVisible.predictions]);

    // Show error toast when hotspots fail to load
    useEffect(() => {
        if (hotspotsError && hasHotspots) {
            toast.error('Failed to load waterlogging hotspots', {
                description: 'Some flood risk data may be unavailable',
                duration: 5000,
            });
        }
    }, [hotspotsError, hasHotspots]);

    // Start continuous location tracking when component mounts
    useEffect(() => {
        if (!('geolocation' in navigator)) {
            console.warn('Geolocation not supported');
            return;
        }

        // Start watching position
        const watchId = navigator.geolocation.watchPosition(
            (position) => {
                const { latitude, longitude } = position.coords;
                setUserLocation({ lat: latitude, lng: longitude });
                setIsTrackingLocation(true);
            },
            (error) => {
                console.warn('Geolocation error:', error.message);
                setIsTrackingLocation(false);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 5000 // Cache position for 5 seconds
            }
        );

        geolocationWatchId.current = watchId;

        // Cleanup on unmount
        return () => {
            if (geolocationWatchId.current !== null) {
                navigator.geolocation.clearWatch(geolocationWatchId.current);
                geolocationWatchId.current = null;
            }
        };
    }, []);

    // Register navigation arrow image on map (must run before user-location effect)
    useEffect(() => {
        if (!map || !isLoaded) return;
        try {
            if (!map.isStyleLoaded() || map.hasImage('nav-arrow')) return;

            // Draw a 64x64 chevron arrow pointing UP (north=0)
            const size = 64;
            const canvas = document.createElement('canvas');
            canvas.width = size;
            canvas.height = size;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            // Chevron shape: pointed top, notched bottom
            ctx.beginPath();
            ctx.moveTo(size / 2, 4);           // Top center (tip)
            ctx.lineTo(size - 6, size - 10);   // Bottom right
            ctx.lineTo(size / 2, size - 20);   // Bottom notch center
            ctx.lineTo(6, size - 10);          // Bottom left
            ctx.closePath();

            // Fill blue with white stroke
            ctx.fillStyle = '#2563eb';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 3;
            ctx.lineJoin = 'round';
            ctx.stroke();

            const imageData = ctx.getImageData(0, 0, size, size);
            map.addImage('nav-arrow', imageData, { pixelRatio: 2 });
        } catch {
            // Map may be transitioning styles (city switch)
        }
    }, [map, isLoaded]);

    // Add/update user location layer on map
    useEffect(() => {
        if (!map || !isLoaded || !userLocation) return;

        try {
            if (!map.isStyleLoaded()) return;

            const userLocationGeoJSON: GeoJSON.FeatureCollection = {
                type: 'FeatureCollection',
                features: [{
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [userLocation.lng, userLocation.lat]
                    },
                    properties: { heading: navState.heading ?? 0 }
                }]
            };

            const existingSource = map.getSource('user-location') as maplibregl.GeoJSONSource;
            if (existingSource) {
                // Update existing source
                existingSource.setData(userLocationGeoJSON);
            } else {
                // Create source and layers
                map.addSource('user-location', {
                    type: 'geojson',
                    data: userLocationGeoJSON
                });

                // Outer pulsing ring (animated via CSS)
                map.addLayer({
                    id: 'user-location-pulse',
                    type: 'circle',
                    source: 'user-location',
                    paint: {
                        'circle-radius': 20,
                        'circle-color': '#3b82f6',
                        'circle-opacity': 0.3,
                        'circle-stroke-width': 0
                    }
                });

                // Middle ring
                map.addLayer({
                    id: 'user-location-ring',
                    type: 'circle',
                    source: 'user-location',
                    paint: {
                        'circle-radius': 12,
                        'circle-color': '#3b82f6',
                        'circle-opacity': 0.2,
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#3b82f6',
                        'circle-stroke-opacity': 0.5
                    }
                });

                // Inner solid dot
                map.addLayer({
                    id: 'user-location-dot',
                    type: 'circle',
                    source: 'user-location',
                    paint: {
                        'circle-radius': 8,
                        'circle-color': '#3b82f6',
                        'circle-opacity': 1,
                        'circle-stroke-width': 3,
                        'circle-stroke-color': '#ffffff'
                    }
                });

                // Navigation glow (visible only during active navigation)
                map.addLayer({
                    id: 'user-location-nav-glow',
                    type: 'circle',
                    source: 'user-location',
                    layout: { 'visibility': 'none' },
                    paint: {
                        'circle-radius': 24,
                        'circle-color': '#3b82f6',
                        'circle-opacity': 0.15,
                        'circle-blur': 0.8
                    }
                });

                // Navigation direction arrow (visible only during active navigation)
                if (map.hasImage('nav-arrow')) {
                    map.addLayer({
                        id: 'user-location-arrow',
                        type: 'symbol',
                        source: 'user-location',
                        layout: {
                            'icon-image': 'nav-arrow',
                            'icon-size': 1,
                            'icon-rotate': ['get', 'heading'],
                            'icon-rotation-alignment': 'map',
                            'icon-allow-overlap': true,
                            'icon-ignore-placement': true,
                            'visibility': 'none'
                        }
                    });
                }

                // Start pulsing animation
                let pulseRadius = 15;
                let pulseOpacity = 0.4;
                let growing = true;

                const animatePulse = () => {
                    // Guard: Check map is still valid and layer exists
                    if (!map || !map.getStyle || typeof map.getLayer !== 'function') {
                        animationFrameRef.current = null;
                        return;
                    }

                    try {
                        if (!map.getLayer('user-location-pulse')) {
                            animationFrameRef.current = null;
                            return;
                        }

                        if (growing) {
                            pulseRadius += 0.5;
                            pulseOpacity -= 0.015;
                            if (pulseRadius >= 30) growing = false;
                        } else {
                            pulseRadius -= 0.5;
                            pulseOpacity += 0.015;
                            if (pulseRadius <= 15) growing = true;
                        }

                        map.setPaintProperty('user-location-pulse', 'circle-radius', pulseRadius);
                        map.setPaintProperty('user-location-pulse', 'circle-opacity', Math.max(0.1, Math.min(0.4, pulseOpacity)));

                        animationFrameRef.current = requestAnimationFrame(animatePulse);
                    } catch {
                        // Layer might be removed or map transitioning, stop animation
                        animationFrameRef.current = null;
                        return;
                    }
                };

                // Cancel any previous animation before starting new one
                if (animationFrameRef.current) {
                    cancelAnimationFrame(animationFrameRef.current);
                }
                animationFrameRef.current = requestAnimationFrame(animatePulse);
            }

            // Toggle between pulsing dot (browsing) and direction arrow (navigating)
            const isNav = navState.isNavigating && navState.heading !== null;
            const dotVis = isNav ? 'none' : 'visible';
            const arrowVis = isNav ? 'visible' : 'none';

            if (map.getLayer('user-location-pulse'))
                map.setLayoutProperty('user-location-pulse', 'visibility', dotVis);
            if (map.getLayer('user-location-ring'))
                map.setLayoutProperty('user-location-ring', 'visibility', dotVis);
            if (map.getLayer('user-location-dot'))
                map.setLayoutProperty('user-location-dot', 'visibility', dotVis);
            if (map.getLayer('user-location-nav-glow'))
                map.setLayoutProperty('user-location-nav-glow', 'visibility', arrowVis);
            if (map.getLayer('user-location-arrow'))
                map.setLayoutProperty('user-location-arrow', 'visibility', arrowVis);
        } catch (error) {
            console.warn('Could not update user location layer:', error);
        }

        // Cleanup: Cancel animation frame on unmount or when dependencies change
        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
                animationFrameRef.current = null;
            }
        };
    }, [map, isLoaded, userLocation, navState.isNavigating, navState.heading]);

    // Check proximity to high-risk hotspots and show alerts
    useEffect(() => {
        if (!userLocation || !hotspotsData?.features || !hasHotspots) return;

        hotspotsData.features.forEach((feature) => {
            const props = feature.properties;
            const hotspotId = String(props?.id || props?.name || '');
            const fhiLevel = props?.fhi_level?.toLowerCase() || '';
            const hotspotName = props?.name || 'Unknown hotspot';

            // Skip if not high risk or already alerted
            if (!HIGH_RISK_LEVELS.includes(fhiLevel)) return;
            if (alertedHotspotsRef.current.has(hotspotId)) return;

            // Get hotspot coordinates
            if (feature.geometry.type !== 'Point') return;
            const [hotspotLng, hotspotLat] = feature.geometry.coordinates;

            // Calculate distance
            const distance = calculateDistance(
                userLocation.lat,
                userLocation.lng,
                hotspotLat,
                hotspotLng
            );

            // Alert if within proximity threshold
            if (distance <= PROXIMITY_ALERT_RADIUS_METERS) {
                alertedHotspotsRef.current.add(hotspotId);

                const distanceText = distance < 100
                    ? 'very close'
                    : `${Math.round(distance)}m away`;

                const fhiColor = props?.fhi_color || (fhiLevel === 'extreme' ? '#ef4444' : '#f97316');

                toast.warning(
                    `Flood Risk Alert: ${hotspotName}`,
                    {
                        description: `You are ${distanceText} from a ${fhiLevel.toUpperCase()} flood risk area. Exercise caution.`,
                        duration: 8000,
                        icon: '🚨',
                        style: {
                            borderLeft: `4px solid ${fhiColor}`,
                        },
                    }
                );
            }
        });
    }, [userLocation, hotspotsData, hasHotspots, calculateDistance, PROXIMITY_ALERT_RADIUS_METERS, HIGH_RISK_LEVELS]);

    // Reset alerted hotspots when city changes or user moves far away
    useEffect(() => {
        // Clear alerts when switching cities
        alertedHotspotsRef.current.clear();
    }, [city]);

    // Force resize when the component mounts or className changes
    useEffect(() => {
        if (map) {
            map.resize();
        }
    }, [map, className]);

    // Track map bounds for prediction grid (debounced)
    useEffect(() => {
        if (!map || !isLoaded) return;

        // Verify map is functional - check isStyleLoaded() to prevent sourceCaches race
        try {
            if (!map.isStyleLoaded() || !map.getStyle()?.sources) return;
        } catch {
            return;
        }

        const updateBounds = () => {
            try {
                const bounds = map.getBounds();
                setMapBounds({
                    minLng: bounds.getWest(),
                    minLat: bounds.getSouth(),
                    maxLng: bounds.getEast(),
                    maxLat: bounds.getNorth(),
                });
            } catch (error) {
                console.log('Could not get map bounds:', error);
            }
        };

        // Set initial bounds
        updateBounds();

        // Update bounds on map move (debounced)
        let timeoutId: ReturnType<typeof setTimeout>;
        const handleMoveEnd = () => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(updateBounds, 500); // Debounce 500ms
        };

        map.on('moveend', handleMoveEnd);

        return () => {
            map.off('moveend', handleMoveEnd);
            clearTimeout(timeoutId);
        };
    }, [map, isLoaded]);

    // Track when map style is fully ready (solves timing issues with hotspots)
    useEffect(() => {
        if (!map || !isLoaded) {
            setMapStyleReady(false);
            return;
        }

        const checkStyleReady = () => {
            try {
                if (map.isStyleLoaded() && map.getStyle()?.sources) {
                    console.log('✅ Map style fully ready');
                    setMapStyleReady(true);
                    return true;
                }
            } catch {
                return false;
            }
            return false;
        };

        // Check immediately
        if (checkStyleReady()) return;

        // Otherwise wait for style to load
        console.log('⏳ Waiting for map style to be ready...');
        const onStyleLoad = () => {
            if (checkStyleReady()) {
                map.off('styledata', onStyleLoad);
                map.off('load', onStyleLoad);
            }
        };

        map.on('styledata', onStyleLoad);
        map.on('load', onStyleLoad);

        // Also poll as backup (some edge cases miss events)
        const pollInterval = setInterval(() => {
            if (checkStyleReady()) {
                clearInterval(pollInterval);
            }
        }, 200);

        return () => {
            map.off('styledata', onStyleLoad);
            map.off('load', onStyleLoad);
            clearInterval(pollInterval);
        };
    }, [map, isLoaded]);

    useEffect(() => {
        if (!map || !isLoaded || !mapStyleReady) return;

        // Map style is confirmed ready at this point
        try {
            const style = map.getStyle();
            if (!style || !style.sources) {
                console.log('Map style check failed, skipping layer update');
                return;
            }
        } catch (e) {
            console.log('Map not ready yet:', e);
            return;
        }

        try {
            // 1. Add Sensors Source & Layer (Existing)
            if (sensors && !map.getSource('sensors')) {
            map.addSource('sensors', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: sensors.map((sensor: Sensor) => ({
                        type: 'Feature',
                        geometry: {
                            type: 'Point',
                            coordinates: [sensor.longitude, sensor.latitude]
                        },
                        properties: {
                            id: sensor.id,
                            status: sensor.status,
                            last_ping: sensor.last_ping
                        }
                    }))
                }
            });

            map.addLayer({
                id: 'sensors-layer',
                type: 'circle',
                source: 'sensors',
                paint: {
                    'circle-radius': 8,
                    'circle-color': [
                        'match',
                        ['get', 'status'],
                        'active', '#22c55e', // Green
                        'warning', '#f97316', // Orange
                        'critical', '#ef4444', // Red
                        '#9ca3af' // Gray default
                    ],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });
        }

        // 2. Add Community Reports Source & Layer
        if (reports) {
            const reportsGeoJSON = {
                type: 'FeatureCollection' as const,
                features: reports.map((report: Report) => ({
                    type: 'Feature' as const,
                    geometry: {
                        type: 'Point' as const,
                        coordinates: [report.longitude, report.latitude]
                    },
                    properties: {
                        id: report.id,
                        description: report.description,
                        verified: report.verified,
                        phone_verified: report.phone_verified,
                        water_depth: report.water_depth || 'unknown',
                        vehicle_passability: report.vehicle_passability || 'unknown',
                        iot_validation_score: report.iot_validation_score,
                        timestamp: report.timestamp
                    }
                }))
            };

            const existingSource = map.getSource('reports') as maplibregl.GeoJSONSource;
            if (existingSource) {
                // Update existing source with new data
                existingSource.setData(reportsGeoJSON);
            } else {
                // Create source and layers for first time
                map.addSource('reports', {
                    type: 'geojson',
                    data: reportsGeoJSON
                });

            // Add outer glow/halo for verified reports
            map.addLayer({
                id: 'reports-halo-layer',
                type: 'circle',
                source: 'reports',
                paint: {
                    'circle-radius': 16,
                    'circle-color': [
                        'case',
                        ['get', 'verified'], '#22c55e', // Green for verified
                        '#f59e0b' // Amber for unverified
                    ],
                    'circle-opacity': 0.2,
                    'circle-blur': 0.5
                }
            });

            // Main report markers
            map.addLayer({
                id: 'reports-layer',
                type: 'circle',
                source: 'reports',
                paint: {
                    'circle-radius': 10,
                    'circle-color': [
                        'match',
                        ['get', 'water_depth'],
                        'ankle', '#3b82f6', // Blue - low
                        'knee', '#f59e0b', // Amber - moderate
                        'waist', '#f97316', // Orange - high
                        'impassable', '#ef4444', // Red - critical
                        '#6b7280' // Gray - unknown
                    ],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': [
                        'case',
                        ['get', 'verified'], '#22c55e', // Green border for verified
                        '#ffffff' // White border for unverified
                    ],
                    'circle-opacity': 0.9
                }
            });

            // Add click handler to show popup with report details
            map.on('click', 'reports-layer', (e: maplibregl.MapMouseEvent) => {
                const features = map.queryRenderedFeatures(e.point, { layers: ['reports-layer'] });
                if (!features || features.length === 0) return;

                const feature = features[0];
                // Type-safe geometry access with guard
                if (!feature.geometry || feature.geometry.type !== 'Point') return;
                const coordinates = (feature.geometry as GeoJSON.Point).coordinates.slice() as [number, number];
                const props = feature.properties;

                // Create popup HTML with safe property access
                const waterDepth = props.water_depth || 'unknown';
                const vehiclePassability = (props.vehicle_passability || 'unknown').replace('-', ' ');
                const iotScore = props.iot_validation_score ?? 0;
                const rawDescription = props.description || 'No description provided';
                const { tags: reportTags, description } = parseReportDescription(rawDescription);
                const tagHtml = generateTagHtml(reportTags);

                // Parse timestamp as UTC (backend stores UTC but without 'Z' suffix)
                const parseUTCTimestamp = (timestamp: string) => {
                    // If timestamp doesn't have timezone info, treat as UTC
                    if (!timestamp.endsWith('Z') && !timestamp.includes('+') && !timestamp.includes('-', 10)) {
                        return new Date(timestamp + 'Z');
                    }
                    return new Date(timestamp);
                };

                // Calculate relative time
                const getRelativeTime = (timestamp: string) => {
                    const now = new Date();
                    const then = parseUTCTimestamp(timestamp);
                    const diffMs = now.getTime() - then.getTime();
                    const diffMins = Math.floor(diffMs / 60000);
                    const diffHours = Math.floor(diffMins / 60);
                    const diffDays = Math.floor(diffHours / 24);

                    if (diffMins < 1) return 'Just now';
                    if (diffMins < 60) return `${diffMins}m ago`;
                    if (diffHours < 24) return `${diffHours}h ago`;
                    if (diffDays < 7) return `${diffDays}d ago`;
                    return then.toLocaleDateString();
                };

                const popupHTML = `
                    <div class="p-3 min-w-[200px]" style="max-width: min(300px, calc(100vw - 32px))">
                        <div class="flex items-center gap-2 mb-2">
                            <h3 class="font-bold text-sm">Community Report</h3>
                            ${props.verified ? '<span class="text-xs bg-green-500 text-white px-2 py-0.5 rounded">✓ Verified</span>' : '<span class="text-xs bg-amber-500 text-white px-2 py-0.5 rounded">Pending</span>'}
                        </div>
                        ${tagHtml ? `<div class="mb-2" style="display:flex;flex-wrap:wrap;">${tagHtml}</div>` : ''}
                        <p class="text-sm text-foreground mb-2 line-clamp-3">${description}</p>
                        <div class="text-xs space-y-1 text-muted-foreground border-t pt-2">
                            <div class="flex justify-between">
                                <span><strong>Water:</strong> <span class="capitalize">${waterDepth}</span></span>
                                <span><strong>Vehicle:</strong> <span class="capitalize">${vehiclePassability}</span></span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span><strong>IoT Score:</strong> ${iotScore}/100</span>
                                ${props.phone_verified ? '<span class="text-green-600">📱 Verified</span>' : ''}
                            </div>
                            <p class="text-muted-foreground/60 text-[10px] mt-1">${getRelativeTime(props.timestamp)} · ${parseUTCTimestamp(props.timestamp).toLocaleString()}</p>
                        </div>
                    </div>
                `;

                new maplibregl.Popup({ offset: 15 })
                    .setLngLat(coordinates)
                    .setHTML(popupHTML)
                    .addTo(map);
            });

            // Change cursor on hover
            map.on('mouseenter', 'reports-layer', () => {
                map.getCanvas().style.cursor = 'pointer';
            });

            map.on('mouseleave', 'reports-layer', () => {
                map.getCanvas().style.cursor = '';
            });
            }
        }

        // 2b. Historical Flood Events - Now shown as info panel instead of map markers
        // (See HistoricalFloodsPanel component - toggled via History button)

        // 2c. Add Waterlogging Hotspots Layer (Delhi + Yogyakarta with live FHI risk)
        if (hotspotsData && hasHotspots) {
            // Wrap in try-catch to handle race conditions during city switch
            try {
                // mapStyleReady is already checked at effect level, no need to re-check here
                const hotspotsGeoJSON = {
                    type: 'FeatureCollection' as const,
                    features: hotspotsData.features
                };

                const existingSource = map.getSource('hotspots') as maplibregl.GeoJSONSource;
                if (existingSource) {
                    // Update existing source with new data
                    existingSource.setData(hotspotsGeoJSON);
                } else {
                    // Create source and layers for first time
                    map.addSource('hotspots', {
                        type: 'geojson',
                        data: hotspotsGeoJSON
                    });

                // Add halo/glow effect for hotspots - FHI color primary, fallback to ML risk
                map.addLayer({
                    id: 'hotspots-halo',
                    type: 'circle',
                    source: 'hotspots',
                    layout: {
                        'visibility': 'visible'
                    },
                    paint: {
                        'circle-radius': 18,
                        'circle-color': [
                            'case',
                            ['has', 'fhi_color'], ['get', 'fhi_color'],
                            ['has', 'risk_color'], ['get', 'risk_color'],
                            '#9ca3af'
                        ],
                        'circle-opacity': 0.25,
                        'circle-blur': 0.8
                    }
                });

                // Main hotspot markers - FHI color primary (live weather), fallback to ML risk
                map.addLayer({
                    id: 'hotspots-layer',
                    type: 'circle',
                    source: 'hotspots',
                    layout: {
                        'visibility': 'visible'
                    },
                    paint: {
                        'circle-radius': 8,
                        'circle-color': [
                            'case',
                            ['has', 'fhi_color'], ['get', 'fhi_color'],
                            ['has', 'risk_color'], ['get', 'risk_color'],
                            '#9ca3af'
                        ],
                        'circle-stroke-width': [
                            'case',
                            ['==', ['get', 'verified'], true], 2.5,  // Thicker for verified (MCD)
                            1.5  // Thinner for unverified (OSM)
                        ],
                        'circle-stroke-color': [
                            'case',
                            ['==', ['get', 'verified'], true], '#ffffff',  // White for verified (MCD)
                            '#94a3b8'  // Slate-400 for unverified (OSM)
                        ],
                        'circle-opacity': 0.9
                    }
                });

                // Hotspot name + risk level labels
                map.addLayer({
                    id: 'hotspots-labels',
                    type: 'symbol',
                    source: 'hotspots',
                    layout: {
                        'text-field': [
                            'concat',
                            ['get', 'name'],
                            ' - ',
                            ['upcase', ['coalesce', ['get', 'fhi_level'], ['get', 'risk_level']]]
                        ],
                        'text-font': ['Open Sans Regular'],
                        'text-size': 10,
                        'text-offset': [0, 1.8],
                        'text-anchor': 'top',
                        'text-max-width': 10,
                        'text-allow-overlap': false,
                        'visibility': 'visible'
                    },
                    paint: {
                        'text-color': '#1f2937',
                        'text-halo-color': '#ffffff',
                        'text-halo-width': 1.5
                    }
                });

                // Add click handler for hotspots
                map.on('click', 'hotspots-layer', (e: maplibregl.MapMouseEvent) => {
                    const features = map.queryRenderedFeatures(e.point, { layers: ['hotspots-layer'] });
                    if (!features || features.length === 0) return;

                    const feature = features[0];
                    if (!feature.geometry || feature.geometry.type !== 'Point') return;
                    const coordinates = (feature.geometry as GeoJSON.Point).coordinates.slice() as [number, number];
                    const props = feature.properties;

                    // Parse risk probability for display (ML Risk)
                    const riskPct = Math.round((props.risk_probability || 0) * 100);
                    const riskLevel = props.risk_level || 'Unknown';
                    const riskColor = props.risk_color || '#94a3b8';

                    // Parse FHI (Flood Hazard Index - Live)
                    const fhiScore = props.fhi_score ?? null;
                    const fhiLevel = props.fhi_level || null;
                    const fhiColor = props.fhi_color || '#9ca3af';
                    const fhiPct = fhiScore !== null ? Math.round(fhiScore * 100) : null;
                    const elevation = props.elevation_m ?? null;

                    // Use FHI color as primary indicator color
                    const primaryColor = fhiColor || riskColor;

                    // Source-aware verification label (multi-city)
                    const sourceLabels: Record<string, string> = {mcd_reports:'MCD',PUB:'PUB',BBMP:'BBMP',local_reports:'Official'};
                    const sourceLabel = sourceLabels[props.source as string] || 'Gov';

                    const popupHTML = `
                        <div class="p-3 min-w-[200px]" style="max-width: min(320px, calc(100vw - 32px))">
                            <div class="flex items-center gap-2 mb-2">
                                <div class="w-3 h-3 rounded-full" style="background-color: ${primaryColor}"></div>
                                <h3 class="font-bold text-sm">Waterlogging Hotspot</h3>
                            </div>
                            <p class="text-sm font-medium text-foreground mb-2">${props.name || 'Unknown Location'}</p>

                            <!-- FHI Section (PRIMARY - Live Weather) -->
                            ${fhiScore !== null ? `
                            <div class="text-xs space-y-1 text-muted-foreground pt-2 pb-2">
                                <div class="flex items-center justify-between mb-1">
                                    <span class="text-muted-foreground flex items-center gap-1">
                                        <span class="w-2 h-2 rounded-full animate-pulse" style="background-color: ${fhiColor}"></span>
                                        Live Flood Risk
                                    </span>
                                    <span class="px-2 py-0.5 rounded text-xs font-bold" style="background-color: ${fhiColor}20; color: ${fhiColor}">
                                        ${fhiLevel ? fhiLevel.toUpperCase() : 'N/A'}
                                    </span>
                                </div>
                                <div class="flex items-center gap-2">
                                    <div class="flex-1 bg-muted rounded-full h-2.5">
                                        <div
                                            class="h-2.5 rounded-full transition-all"
                                            style="width: ${fhiPct}%; background-color: ${fhiColor}"
                                        ></div>
                                    </div>
                                    <span class="text-sm font-bold" style="color: ${fhiColor}">
                                        ${fhiPct}%
                                    </span>
                                </div>
                                ${elevation !== null ? `<div class="text-xs text-muted-foreground/60 mt-1">Elevation: ${elevation.toFixed(1)}m</div>` : ''}
                                <div class="text-xs mt-1 ${props.verified ? 'text-green-600' : 'text-amber-600'}">
                                    ${props.verified ? '✓ ' + sourceLabel + ' Verified' : '⚠ ML Predicted (OSM)'}
                                </div>
                                <p class="text-muted-foreground/60 text-[10px] italic mt-1">Based on current weather conditions</p>
                            </div>
                            ` : ''}

                            <!-- ML Risk Score Section (Secondary - Static) -->
                            <div class="text-xs space-y-1 text-muted-foreground ${fhiScore !== null ? 'mt-2 pt-2 border-t border-border' : 'pt-2'}">
                                <div class="flex justify-between items-center">
                                    <span class="text-muted-foreground/60">Base Risk (ML)</span>
                                    <span class="px-1.5 py-0.5 rounded text-[10px] font-medium" style="background-color: ${riskColor}15; color: ${riskColor}">${riskLevel.toUpperCase()}</span>
                                </div>
                                <div class="flex items-center gap-2">
                                    <div class="flex-1 bg-muted rounded-full h-1.5">
                                        <div class="h-1.5 rounded-full transition-all" style="width: ${riskPct}%; background-color: ${riskColor}"></div>
                                    </div>
                                    <span class="text-xs" style="color: ${riskColor}">${riskPct}%</span>
                                </div>
                                <p class="text-muted-foreground/60 text-[9px] italic">Terrain & land cover baseline</p>
                            </div>

                            <!-- Zone Info -->
                            ${props.zone ? `
                            <div class="text-xs text-muted-foreground mt-2 pt-2 border-t">
                                <strong>Zone:</strong> ${props.zone}
                            </div>
                            ` : ''}
                        </div>
                    `;

                    new maplibregl.Popup({ offset: 15 })
                        .setLngLat(coordinates)
                        .setHTML(popupHTML)
                        .addTo(map);
                });

                // Change cursor on hover
                map.on('mouseenter', 'hotspots-layer', () => {
                    map.getCanvas().style.cursor = 'pointer';
                });

                map.on('mouseleave', 'hotspots-layer', () => {
                    map.getCanvas().style.cursor = '';
                });
            }
            } catch (e) {
                // Handle race condition during city switch (sourceCaches undefined)
                console.warn('Hotspots layer update skipped - map transitioning:', e);
            }
        }

        // 3. Add Navigation Routes
        if (!map.getSource('navigation-routes')) {
            map.addSource('navigation-routes', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: []
                }
            });

            // Route casing — darker outline behind the route line (Google Maps style)
            map.addLayer({
                id: 'routes-casing-layer',
                type: 'line',
                source: 'navigation-routes',
                layout: { 'line-join': 'round', 'line-cap': 'round', 'visibility': 'visible' },
                paint: {
                    'line-color': [
                        'match', ['get', 'type'],
                        'safe', '#15803d',       // green-700 (darker outline)
                        'balanced', '#1d4ed8',   // blue-700
                        'fast', '#c2410c',       // orange-700
                        '#555555'
                    ],
                    'line-width': ['case', ['==', ['get', 'id'], selectedRouteId || ''], 12, 5],
                    'line-opacity': ['case', ['==', ['get', 'id'], selectedRouteId || ''], 1.0, 0.4]
                }
            });

            map.addLayer({
                id: 'routes-layer',
                type: 'line',
                source: 'navigation-routes',
                layout: {
                    'line-join': 'round',
                    'line-cap': 'round',
                    'visibility': 'visible'  // Toggle effect controls visibility
                },
                paint: {
                    'line-color': [
                        'match',
                        ['get', 'type'],
                        'safe', '#22c55e',       // Green
                        'balanced', '#3b82f6',   // Blue
                        'fast', '#f97316',       // Orange
                        '#888888'                // Default gray
                    ],
                    'line-width': [
                        'case',
                        ['==', ['get', 'id'], selectedRouteId || ''],
                        8,  // Selected route (wider for casing effect)
                        3   // Others are thinner
                    ],
                    'line-opacity': [
                        'case',
                        ['==', ['get', 'id'], selectedRouteId || ''],
                        1.0,  // Selected route is fully opaque
                        0.6   // Others are semi-transparent
                    ]
                }
            });
        }

        // Update navigation routes data
        if (navigationRoutes && navigationRoutes.length > 0) {
            const source = map.getSource('navigation-routes') as maplibregl.GeoJSONSource;
            if (source) {
                const features = navigationRoutes.map(route => ({
                    type: 'Feature' as const,
                    properties: {
                        id: route.id,
                        type: route.type,
                        distance: route.distance_meters,
                        duration: route.duration_seconds,
                        safety_score: route.safety_score
                    },
                    geometry: route.geometry
                }));

                source.setData({
                    type: 'FeatureCollection',
                    features
                });

                // Update casing + route paint properties when selectedRouteId changes
                if (map.getLayer('routes-casing-layer')) {
                    map.setPaintProperty('routes-casing-layer', 'line-width',
                        ['case', ['==', ['get', 'id'], selectedRouteId || ''], 12, 5]);
                    map.setPaintProperty('routes-casing-layer', 'line-opacity',
                        ['case', ['==', ['get', 'id'], selectedRouteId || ''], 1.0, 0.4]);
                }
                if (map.getLayer('routes-layer')) {
                    map.setPaintProperty('routes-layer', 'line-width',
                        ['case', ['==', ['get', 'id'], selectedRouteId || ''], 8, 3]);
                    map.setPaintProperty('routes-layer', 'line-opacity',
                        ['case', ['==', ['get', 'id'], selectedRouteId || ''], 1.0, 0.6]);
                }
            }
        }

        // 4. Add Origin/Destination Markers
        if (!map.getSource('navigation-markers')) {
            map.addSource('navigation-markers', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: []
                }
            });

            // Origin marker (green)
            map.addLayer({
                id: 'navigation-origin',
                type: 'circle',
                source: 'navigation-markers',
                filter: ['==', 'type', 'origin'],
                paint: {
                    'circle-radius': 10,
                    'circle-color': '#22c55e',
                    'circle-stroke-width': 3,
                    'circle-stroke-color': '#ffffff'
                }
            });

            // Destination marker (red)
            map.addLayer({
                id: 'navigation-destination',
                type: 'circle',
                source: 'navigation-markers',
                filter: ['==', 'type', 'destination'],
                paint: {
                    'circle-radius': 10,
                    'circle-color': '#ef4444',
                    'circle-stroke-width': 3,
                    'circle-stroke-color': '#ffffff'
                }
            });
        }

        // Update origin/destination markers
        if (navigationOrigin || navigationDestination) {
            const source = map.getSource('navigation-markers') as maplibregl.GeoJSONSource;
            if (source) {
                const features = [];
                if (navigationOrigin) {
                    features.push({
                        type: 'Feature' as const,
                        properties: { type: 'origin' },
                        geometry: {
                            type: 'Point' as const,
                            coordinates: [navigationOrigin.lng, navigationOrigin.lat]
                        }
                    });
                }
                if (navigationDestination) {
                    features.push({
                        type: 'Feature' as const,
                        properties: { type: 'destination' },
                        geometry: {
                            type: 'Point' as const,
                            coordinates: [navigationDestination.lng, navigationDestination.lat]
                        }
                    });
                }

                source.setData({
                    type: 'FeatureCollection',
                    features
                });
            }
        }

        // 5. Add Nearby Metro Stations
        if (!map.getSource('nearby-metros')) {
            map.addSource('nearby-metros', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: []
                }
            });

            map.addLayer({
                id: 'nearby-metros-layer',
                type: 'circle',
                source: 'nearby-metros',
                layout: {
                    'visibility': 'visible'  // Toggle effect controls visibility
                },
                paint: {
                    'circle-radius': 8,
                    'circle-color': ['get', 'color'],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });

            // Add metro station labels
            map.addLayer({
                id: 'nearby-metros-labels',
                type: 'symbol',
                source: 'nearby-metros',
                layout: {
                    'text-field': ['get', 'name'],
                    'text-font': ['Open Sans Regular'],
                    'text-size': 11,
                    'text-offset': [0, 1.5],
                    'visibility': 'visible'  // Toggle effect controls visibility
                },
                paint: {
                    'text-color': '#000000',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 2
                }
            });

            // Add click handler for metro stations
            map.on('click', 'nearby-metros-layer', (e) => {
                const features = map.queryRenderedFeatures(e.point, { layers: ['nearby-metros-layer'] });
                if (features && features.length > 0 && onMetroClick) {
                    const feature = features[0];
                    const station: MetroStation = {
                        id: feature.properties?.id,
                        name: feature.properties?.name,
                        line: feature.properties?.line,
                        color: feature.properties?.color,
                        lat: feature.properties?.lat,
                        lng: feature.properties?.lng,
                        distance_meters: feature.properties?.distance_meters,
                        walking_minutes: feature.properties?.walking_minutes
                    };
                    onMetroClick(station);
                }
            });

            map.on('mouseenter', 'nearby-metros-layer', () => {
                map.getCanvas().style.cursor = 'pointer';
            });

            map.on('mouseleave', 'nearby-metros-layer', () => {
                map.getCanvas().style.cursor = '';
            });
        }

        // Update nearby metros data
        if (nearbyMetros && nearbyMetros.length > 0) {
            const source = map.getSource('nearby-metros') as maplibregl.GeoJSONSource;
            if (source) {
                const features = nearbyMetros.map(station => ({
                    type: 'Feature' as const,
                    properties: {
                        id: station.id,
                        name: station.name,
                        line: station.line,
                        color: station.color,
                        lat: station.lat,
                        lng: station.lng,
                        distance_meters: station.distance_meters,
                        walking_minutes: station.walking_minutes
                    },
                    geometry: {
                        type: 'Point' as const,
                        coordinates: [station.lng, station.lat]
                    }
                }));

                source.setData({
                    type: 'FeatureCollection',
                    features
                });
            }
        }

        // 6. Add Flood Zones overlay from route calculation
        if (!map.getSource('route-flood-zones')) {
            map.addSource('route-flood-zones', {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: [] }
            });

            // Insert flood zones below routes layer
            map.addLayer({
                id: 'route-flood-zones-layer',
                type: 'fill',
                source: 'route-flood-zones',
                layout: {
                    'visibility': 'visible'
                },
                paint: {
                    'fill-color': '#ef4444',
                    'fill-opacity': 0.5  // Increased from 0.3 for better visibility
                }
            }, 'routes-layer'); // Insert below routes layer

            // Add border for better visibility
            map.addLayer({
                id: 'route-flood-zones-border',
                type: 'line',
                source: 'route-flood-zones',
                layout: {
                    'visibility': 'visible'
                },
                paint: {
                    'line-color': '#dc2626',
                    'line-width': 2,
                    'line-opacity': 0.6
                }
            }, 'routes-layer');
        }

        // Update flood zones data
        if (floodZones) {
            const source = map.getSource('route-flood-zones') as maplibregl.GeoJSONSource;
            if (source) {
                source.setData(floodZones);
            }
        }

        // 7. Google Flood Forecasting Inundation Layer
        // Renders flood extent polygons from Google's API when active flooding detected
        if (!map.getSource('floodhub-inundation')) {
            map.addSource('floodhub-inundation', {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: [] }
            });

            // Fill layer — severity color derived from the active gauge
            map.addLayer({
                id: 'floodhub-inundation-fill',
                type: 'fill',
                source: 'floodhub-inundation',
                layout: { 'visibility': 'visible' },
                paint: {
                    'fill-color': activeInundationGauge?.severity === 'EXTREME' ? '#dc2626'
                        : activeInundationGauge?.severity === 'SEVERE' ? '#ea580c'
                        : '#ca8a04',
                    'fill-opacity': activeInundationGauge?.severity === 'EXTREME' ? 0.5
                        : activeInundationGauge?.severity === 'SEVERE' ? 0.4
                        : 0.3
                }
            }, 'routes-layer');

            // Border for clarity
            map.addLayer({
                id: 'floodhub-inundation-border',
                type: 'line',
                source: 'floodhub-inundation',
                layout: { 'visibility': 'visible' },
                paint: {
                    'line-color': activeInundationGauge?.severity === 'EXTREME' ? '#991b1b'
                        : activeInundationGauge?.severity === 'SEVERE' ? '#9a3412'
                        : '#854d0e',
                    'line-width': 2,
                    'line-opacity': 0.7
                }
            }, 'routes-layer');
        }

        // Update inundation data when available
        if (inundationGeoJSON) {
            const source = map.getSource('floodhub-inundation') as maplibregl.GeoJSONSource;
            if (source) {
                source.setData(inundationGeoJSON);
            }
        } else {
            // Clear inundation when no active flooding
            const source = map.getSource('floodhub-inundation') as maplibregl.GeoJSONSource;
            if (source) {
                source.setData({ type: 'FeatureCollection', features: [] });
            }
        }

        // ===== PUB INFRASTRUCTURE LAYERS (Singapore only) =====
        if (city === 'singapore') {
            // CCTV Cameras (48 flood monitoring cameras)
            if (!map.getSource('pub-cctv')) {
                map.addSource('pub-cctv', {
                    type: 'geojson',
                    data: '/singapore-pub-cctv.geojson',
                });
                map.addLayer({
                    id: 'pub-cctv-layer',
                    type: 'circle',
                    source: 'pub-cctv',
                    layout: {
                        'visibility': layersVisible.pubCCTVs ? 'visible' : 'none',
                    },
                    paint: {
                        'circle-radius': 5,
                        'circle-color': '#8b5cf6',
                        'circle-stroke-color': '#6d28d9',
                        'circle-stroke-width': 1.5,
                        'circle-opacity': 0.8,
                    },
                });
            }

            // Click handler for PUB CCTV layer
            map.on('click', 'pub-cctv-layer', (e: maplibregl.MapMouseEvent) => {
                const features = map.queryRenderedFeatures(e.point, { layers: ['pub-cctv-layer'] });
                if (!features || features.length === 0) return;
                const props = features[0].properties;
                const coords = (features[0].geometry as GeoJSON.Point).coordinates.slice() as [number, number];
                new maplibregl.Popup({ offset: 10, maxWidth: '260px' })
                    .setLngLat(coords)
                    .setHTML(`
                        <div class="p-2">
                            <div class="flex items-center gap-2 mb-1">
                                <div class="w-2.5 h-2.5 rounded-full bg-violet-500"></div>
                                <span class="font-bold text-xs">PUB Flood CCTV</span>
                            </div>
                            <p class="text-xs text-muted-foreground">${props.ref_name || 'Unknown'}</p>
                            <p class="text-xs text-muted-foreground">Catchment: ${props.catchment || 'N/A'}</p>
                            <p class="text-xs text-muted-foreground">ID: ${props.cctv_id || props.CCTVID || 'N/A'}</p>
                            <div class="border-t border-border mt-2 pt-2">
                                <p class="text-xs text-amber-600 mb-1">Camera feed not publicly accessible</p>
                                <a href="https://app.pub.gov.sg/waterlevel/pages/LargeMap.aspx"
                                   target="_blank" rel="noopener"
                                   class="text-xs text-blue-500 hover:underline block">
                                    View PUB Flood Monitoring Portal &rarr;
                                </a>
                            </div>
                        </div>
                    `)
                    .addTo(map);
            });

            // Cursor changes for PUB CCTV layer
            map.on('mouseenter', 'pub-cctv-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
            map.on('mouseleave', 'pub-cctv-layer', () => { map.getCanvas().style.cursor = ''; });
        }

        } catch (error) {
            console.error('Error updating map layers:', error);
        }

    }, [map, isLoaded, mapStyleReady, sensors, reports, hotspotsData, hasHotspots, navigationRoutes, selectedRouteId, navigationOrigin, navigationDestination, nearbyMetros, floodZones, onMetroClick, inundationGeoJSON, activeInundationGauge]);

    // Auto-zoom map to fit routes when calculated
    useEffect(() => {
        if (!map || !isLoaded || !navigationRoutes || navigationRoutes.length === 0) return;

        // Verify map is functional - check isStyleLoaded() to prevent sourceCaches race
        try {
            if (!map.isStyleLoaded() || !map.getStyle()?.sources) return;
        } catch {
            return;
        }

        try {
            const allCoords: [number, number][] = [];

        // Collect all coordinates from all routes
        navigationRoutes.forEach(route => {
            if (route.geometry?.coordinates) {
                route.geometry.coordinates.forEach(coord => {
                    allCoords.push(coord as [number, number]);
                });
            }
        });

        // Add origin and destination markers
        if (navigationOrigin) {
            allCoords.push([navigationOrigin.lng, navigationOrigin.lat]);
        }
        if (navigationDestination) {
            allCoords.push([navigationDestination.lng, navigationDestination.lat]);
        }

        // If we have coordinates, fit the map to show them all
        if (allCoords.length > 0) {
            const bounds = allCoords.reduce((b, coord) => {
                return b.extend(coord as maplibregl.LngLatLike);
            }, new maplibregl.LngLatBounds(allCoords[0], allCoords[0]));

            map.fitBounds(bounds, {
                padding: { top: 100, bottom: 250, left: 50, right: 50 },
                duration: 1000,
                maxZoom: 15 // Don't zoom in too much
            });
        }
        } catch (error) {
            console.error('Error auto-zooming map:', error);
        }
    }, [map, isLoaded, navigationRoutes, navigationOrigin, navigationDestination]);

    // ML Prediction Heatmap Layer removed - not needed for current implementation
    // Hotspots layer provides better visual feedback for flood risk areas

    // Toggle layer visibility
    useEffect(() => {
        if (!map || !isLoaded) return;

        // Verify map is functional - check isStyleLoaded() to prevent sourceCaches race
        try {
            if (!map.isStyleLoaded() || !map.getStyle()?.sources) return;
        } catch {
            return;
        }

        // Toggle flood layer
        try {
            if (map.getLayer('flood-layer')) {
            map.setLayoutProperty('flood-layer', 'visibility', layersVisible.flood ? 'visible' : 'none');
        }

        // Toggle sensors layer
        if (map.getLayer('sensors-layer')) {
            map.setLayoutProperty('sensors-layer', 'visibility', layersVisible.sensors ? 'visible' : 'none');
        }

        // Toggle reports layers
        if (map.getLayer('reports-halo-layer')) {
            map.setLayoutProperty('reports-halo-layer', 'visibility', layersVisible.reports ? 'visible' : 'none');
        }
        if (map.getLayer('reports-layer')) {
            map.setLayoutProperty('reports-layer', 'visibility', layersVisible.reports ? 'visible' : 'none');
        }

        // Toggle routes layer (casing + main line)
        if (map.getLayer('routes-casing-layer')) {
            map.setLayoutProperty('routes-casing-layer', 'visibility', layersVisible.routes ? 'visible' : 'none');
        }
        if (map.getLayer('routes-layer')) {
            map.setLayoutProperty('routes-layer', 'visibility', layersVisible.routes ? 'visible' : 'none');
        }

        // Toggle metro layers (with error handling for missing layers)
        try {
            // Metro lines from useMap.ts
            if (map.getLayer('metro-lines-layer')) {
                map.setLayoutProperty('metro-lines-layer', 'visibility', layersVisible.metro ? 'visible' : 'none');
            }
            if (map.getLayer('metro-stations-layer')) {
                map.setLayoutProperty('metro-stations-layer', 'visibility', layersVisible.metro ? 'visible' : 'none');
            }
            if (map.getLayer('metro-station-names-layer')) {
                map.setLayoutProperty('metro-station-names-layer', 'visibility', layersVisible.metro ? 'visible' : 'none');
            }
            // Nearby metro stations from MapComponent
            if (map.getLayer('nearby-metros-layer')) {
                map.setLayoutProperty('nearby-metros-layer', 'visibility', layersVisible.metro ? 'visible' : 'none');
            }
            if (map.getLayer('nearby-metros-labels')) {
                map.setLayoutProperty('nearby-metros-labels', 'visibility', layersVisible.metro ? 'visible' : 'none');
            }
        } catch (error) {
            console.warn('Metro layers not available:', error);
        }

        // Heatmap removed - FHI hotspots provide better spatial variation

        // Historical floods - now shown as info panel, not map layer

        // Toggle hotspots layers
        if (map.getLayer('hotspots-halo')) {
            map.setLayoutProperty('hotspots-halo', 'visibility', layersVisible.hotspots ? 'visible' : 'none');
        }
        if (map.getLayer('hotspots-layer')) {
            map.setLayoutProperty('hotspots-layer', 'visibility', layersVisible.hotspots ? 'visible' : 'none');
        }
        if (map.getLayer('hotspots-labels')) {
            map.setLayoutProperty('hotspots-labels', 'visibility', layersVisible.hotspots ? 'visible' : 'none');
        }

        // Toggle FloodHub inundation layers
        if (map.getLayer('floodhub-inundation-fill')) {
            map.setLayoutProperty('floodhub-inundation-fill', 'visibility', layersVisible.floodhub ? 'visible' : 'none');
        }
        if (map.getLayer('floodhub-inundation-border')) {
            map.setLayoutProperty('floodhub-inundation-border', 'visibility', layersVisible.floodhub ? 'visible' : 'none');
        }
        // PUB CCTV layer (Singapore only)
        if (map.getLayer('pub-cctv-layer')) {
            map.setLayoutProperty('pub-cctv-layer', 'visibility', layersVisible.pubCCTVs ? 'visible' : 'none');
        }
        } catch (error) {
            console.error('Error toggling layer visibility:', error);
        }
    }, [map, isLoaded, layersVisible]);

    const handleZoomIn = () => {
        if (map) map.zoomIn();
    };

    const handleZoomOut = () => {
        if (map) map.zoomOut();
    };

    // Update city context and optionally sync to profile based on GPS location
    const updateCityFromLocation = async (lat: number, lng: number) => {
        const detectedCity = getCityKeyFromCoordinates(lng, lat);
        if (detectedCity && detectedCity !== city) {
            setCity(detectedCity);
            // Sync to user profile if logged in
            if (user?.id) {
                try {
                    await syncCityToUser(user.id, detectedCity);
                    toast.success(`Switched to ${CITIES[detectedCity].displayName}`, {
                        description: 'Your area has been updated based on your location',
                        duration: 3000,
                    });
                } catch (error) {
                    console.error('Failed to sync city preference:', error);
                    // Still update locally even if sync fails
                }
            }
        }
    };

    const handleMyLocation = () => {
        if (!map) return;

        // Use tracked location if available (faster response)
        if (userLocation) {
            const { lat, lng } = userLocation;

            // Detect city from GPS and update context if different
            updateCityFromLocation(lat, lng);

            // Check if user is within current city bounds
            const isWithinBounds = isWithinCityBounds(lng, lat, city);
            const cityConfig = getCityConfig(city);

            if (!isWithinBounds) {
                toast.warning(`Outside ${cityConfig.displayName}`, {
                    description: 'Your location is outside the flood monitoring area',
                    duration: 4000,
                });
            }

            map.flyTo({
                center: [lng, lat],
                zoom: 15,
                duration: 1500
            });

            toast.success('Location found', {
                description: isTrackingLocation ? 'Live tracking active' : 'Showing last known position',
                duration: 2000,
            });
            return;
        }

        // Fallback: Request location if not tracking yet
        if ('geolocation' in navigator) {
            toast.loading('Finding your location...', { id: 'location-search' });

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { longitude, latitude } = position.coords;
                    setUserLocation({ lat: latitude, lng: longitude });

                    // Detect city from GPS and update context if different
                    updateCityFromLocation(latitude, longitude);

                    // Check if user is within current city bounds
                    const isWithinBounds = isWithinCityBounds(longitude, latitude, city);
                    const cityConfig = getCityConfig(city);

                    if (!isWithinBounds) {
                        toast.warning(`Outside ${cityConfig.displayName}`, {
                            description: 'Your location is outside the flood monitoring area',
                            duration: 4000,
                        });
                    }

                    map.flyTo({
                        center: [longitude, latitude],
                        zoom: 15,
                        duration: 1500
                    });

                    toast.dismiss('location-search');
                    toast.success('Location found', { duration: 2000 });
                },
                (error) => {
                    console.error('Error getting location:', error);
                    toast.dismiss('location-search');
                    toast.error('Unable to get location', {
                        description: 'Please enable location permissions in your browser',
                        duration: 5000,
                    });
                },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        } else {
            toast.error('Geolocation not supported', {
                description: 'Your browser does not support location services',
                duration: 5000,
            });
        }
    };

    const toggleLayers = () => {
        setLayersVisible(prev => ({
            ...prev,
            flood: !prev.flood
        }));
    };

    // Handle search location selection
    const handleSearchLocationSelect = useCallback((lat: number, lng: number, name: string) => {
        if (!map || !isLoaded) return;

        try {
            // Update the search-result source with the selected location
            const source = map.getSource('search-result') as maplibregl.GeoJSONSource;
            if (source) {
                source.setData({
                    type: 'FeatureCollection',
                    features: [{
                        type: 'Feature',
                        geometry: {
                            type: 'Point',
                            coordinates: [lng, lat]
                        },
                        properties: {
                            name: name
                        }
                    }]
                });
            }

            // Fly to the selected location with smooth animation
            map.flyTo({
                center: [lng, lat],
                zoom: 15,
                duration: 1500,
                essential: true
            });
        } catch (error) {
            console.log('Could not update search location:', error);
        }
    }, [map, isLoaded]);

    // Clear search marker when city changes
    useEffect(() => {
        if (!map || !isLoaded) return;

        // Verify map is functional - check isStyleLoaded() to prevent sourceCaches race
        try {
            if (!map.isStyleLoaded() || !map.getStyle()?.sources) return;
        } catch {
            return;
        }

        try {
            const source = map.getSource('search-result') as maplibregl.GeoJSONSource;
            if (source) {
                source.setData({
                    type: 'FeatureCollection',
                    features: []
                });
            }
        } catch (error) {
            // Map might be in transition state during city change
            console.log('Could not clear search marker:', error);
        }
    }, [city, map, isLoaded]);

    // Fly to target location when targetLocation prop changes
    useEffect(() => {
        if (!targetLocation || !isLoaded || !map) return;

        // Fly to the target location with smooth animation
        map.flyTo({
            center: [targetLocation.lng, targetLocation.lat],
            zoom: 16,
            duration: 2000,
            essential: true
        });

        // Add a temporary marker at the target location
        const marker = new maplibregl.Marker({ color: '#ef4444' })
            .setLngLat([targetLocation.lng, targetLocation.lat])
            .addTo(map);

        // Call callback after animation completes
        const callbackTimer = setTimeout(() => {
            onLocationReached?.();
        }, 2100);

        // Cleanup function to remove marker and clear timeout
        return () => {
            clearTimeout(callbackTimer);
            marker.remove();
        };
    }, [targetLocation, isLoaded, map, onLocationReached]);

    return (
        <div className="relative w-full h-full">
            {/* Header: Title + City Selector row, then Search Bar */}
            {title && !showHistoricalPanel && (
                <div className="absolute pointer-events-auto flex flex-col gap-2 left-3 right-3 md:left-6 md:right-auto md:max-w-sm" style={{ top: '12px', zIndex: 100 }}>
                    <div className="flex items-center gap-2">
                        <div className="bg-card shadow-lg rounded-xl px-3 py-1.5 flex-1 min-w-0">
                            <h1 className="text-sm font-semibold text-foreground truncate">{title}</h1>
                            <p className="text-[10px] text-muted-foreground">Real-time flood monitoring</p>
                        </div>
                        {showCitySelector && availableCities.length > 0 && (
                            <div className="bg-card shadow-lg rounded-xl px-2.5 py-1.5 border border-border shrink-0">
                                <div className="flex items-center gap-1.5">
                                    <MapPin className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                                    <select
                                        id="city-selector"
                                        name="city"
                                        value={city}
                                        onChange={(e) => handleCityChange(e.target.value)}
                                        disabled={isChangingCity}
                                        className="bg-transparent text-foreground font-semibold text-xs border-none focus:outline-none focus:ring-0 cursor-pointer pr-4 disabled:opacity-50"
                                    >
                                        {availableCities.map((cityKey) => {
                                            const config = getCityConfig(cityKey);
                                            return (
                                                <option key={cityKey} value={cityKey}>
                                                    {config.displayName}
                                                </option>
                                            );
                                        })}
                                    </select>
                                </div>
                            </div>
                        )}
                    </div>
                    {/* Search Bar below header row */}
                    {showCitySelector && (
                        <SearchBar
                            onLocationSelect={handleSearchLocationSelect}
                            cityKey={city}
                            placeholder={`Search in ${currentCityConfig.displayName}...`}
                            className="w-full md:w-72"
                        />
                    )}
                </div>
            )}
            {isChangingCity && (
                <div className="absolute inset-0 bg-background/90 flex items-center justify-center" style={{ zIndex: 90 }}>
                    <div className="bg-card shadow-xl rounded-xl p-6 flex flex-col items-center gap-3 border border-border">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                        <p className="text-sm font-medium text-foreground">
                            Loading {currentCityConfig.displayName} flood atlas...
                        </p>
                    </div>
                </div>
            )}
            <div ref={mapContainer} className={`${className} relative`} style={{ width: '100%', height: '100%', minHeight: '300px', zIndex: 1 }} />

            {/* Map Controls Overlay */}
            {showControls && isLoaded && (
                <>
                    {/* Map Controls - Right side, compact on mobile */}
                    <div className="absolute right-2 md:right-4 flex flex-col gap-1.5 md:gap-2 max-h-[calc(100vh-200px)] overflow-y-auto" style={{ bottom: 'calc(144px + env(safe-area-inset-bottom, 0px))', zIndex: 60 }} data-tour-id="map-layers">
                        <Button
                            size="icon"
                            onClick={handleZoomIn}
                            className="!bg-card !text-foreground shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 border border-border !opacity-100 hover:!bg-secondary"
                            title="Zoom in"
                        >
                            <Plus className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={handleZoomOut}
                            className="!bg-card !text-foreground shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 border border-border !opacity-100 hover:!bg-secondary"
                            title="Zoom out"
                        >
                            <Minus className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={handleMyLocation}
                            className="!bg-primary hover:!bg-primary/90 !text-white shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100"
                            title="My location"
                        >
                            <Navigation className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={toggleLayers}
                            className={`${layersVisible.flood ? '!bg-green-500 hover:!bg-green-600 !text-white' : '!bg-card/90 backdrop-blur-sm !text-foreground border border-border hover:!bg-secondary'} shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100`}
                            title="Toggle flood layer"
                        >
                            <Layers className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={() => setLayersVisible(prev => ({ ...prev, metro: !prev.metro }))}
                            className={`${layersVisible.metro ? '!bg-primary hover:!bg-primary/90 !text-white' : '!bg-card/90 backdrop-blur-sm !text-foreground border border-border hover:!bg-secondary'} shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100`}
                            title="Toggle metro routes"
                        >
                            <Train className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={() => setLayersVisible(prev => ({ ...prev, reports: !prev.reports }))}
                            className={`${layersVisible.reports ? '!bg-primary hover:!bg-primary/90 !text-white' : '!bg-card/90 backdrop-blur-sm !text-foreground border border-border hover:!bg-secondary'} shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100`}
                            title="Toggle community reports"
                        >
                            <AlertCircle className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={() => setShowHistoricalPanel(prev => !prev)}
                            className={`${showHistoricalPanel ? '!bg-primary hover:!bg-primary/90 !text-white' : '!bg-card/90 backdrop-blur-sm !text-foreground border border-border hover:!bg-secondary'} shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100`}
                            title="View historical flood events (1967-2023)"
                        >
                            <History className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={() => setLayersVisible(prev => ({ ...prev, hotspots: !prev.hotspots }))}
                            className={`${layersVisible.hotspots ? '!bg-green-500 hover:!bg-green-600 !text-white' : '!bg-card/90 backdrop-blur-sm !text-foreground border border-border hover:!bg-secondary'} shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100`}
                            title="Toggle waterlogging hotspots"
                        >
                            <Droplets className="h-4 w-4" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={() => setLayersVisible(prev => ({ ...prev, floodhub: !prev.floodhub }))}
                            className={`${layersVisible.floodhub ? '!bg-blue-500 hover:!bg-blue-600 !text-white' : '!bg-card/90 backdrop-blur-sm !text-foreground border border-border hover:!bg-secondary'} shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100`}
                            title="Toggle flood extent forecast (Google FloodHub)"
                        >
                            <Waves className="h-4 w-4" />
                        </Button>
                        {city === 'singapore' && (
                            <Button
                                size="icon"
                                onClick={() => setLayersVisible(prev => ({ ...prev, pubCCTVs: !prev.pubCCTVs }))}
                                className={`${layersVisible.pubCCTVs ? '!bg-violet-500 hover:!bg-violet-600 !text-white' : '!bg-card/90 backdrop-blur-sm !text-foreground border border-border hover:!bg-secondary'} shadow-lg rounded-full w-9 h-9 md:w-10 md:h-10 !opacity-100`}
                                title="Toggle PUB flood CCTVs (48)"
                            >
                                <Camera className="h-4 w-4" />
                            </Button>
                        )}
                    </div>

                    {/* Map Legend - Bottom Right (shifts up when live navigation is active) */}
                    <div className="absolute" style={{
                        bottom: navState.isNavigating
                            ? 'calc(280px + env(safe-area-inset-bottom, 0px))'
                            : 'calc(144px + env(safe-area-inset-bottom, 0px))',
                        right: '56px',
                        zIndex: 60
                    }}>
                        <MapLegend className="max-w-xs" />
                    </div>
                </>
            )}

            {/* Historical Floods Info Panel - Overlay */}
            <HistoricalFloodsPanel
                floods={historicalFloods?.features?.map((f) => ({
                    id: f.properties.id || '',
                    date: f.properties.date || '',
                    districts: f.properties.districts || '',
                    severity: f.properties.severity || 'minor',
                    fatalities: f.properties.fatalities || 0,
                    injured: f.properties.injured || 0,
                    displaced: f.properties.displaced || 0,
                    duration_days: f.properties.duration_days,
                    main_cause: f.properties.main_cause || '',
                })) || []}
                onClose={() => setShowHistoricalPanel(false)}
                isOpen={showHistoricalPanel}
                cityName={currentCityConfig.displayName}
                comingSoonMessage={historicalFloods?.metadata?.message}
            />
        </div>
    );
}
