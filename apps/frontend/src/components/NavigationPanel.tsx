import React, { useState, useEffect } from 'react';
import { Navigation, MapPin, Clock, Shield, Bike, Car, Footprints, Train, Bookmark, Star, Trash2, LocateFixed, GitCompare, Loader2, Play, MapPinned } from 'lucide-react';
import { Sheet, SheetContent } from './ui/sheet';
import { Button } from './ui/button';
import SmartSearchBar from './SmartSearchBar';
import MapPicker from './MapPicker';
import { useEnhancedCompareRoutes, useNearbyMetros, useSavedRoutes, useCreateSavedRoute, useDeleteSavedRoute, useIncrementRouteUsage } from '../lib/api/hooks';
import { RouteOption, MetroStation, EnhancedRouteComparisonResponse, FastestRouteOption, SafestRouteOption } from '../types';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { EnhancedRouteCard } from './EnhancedRouteCard';
import { useNavigation } from '../contexts/NavigationContext';

interface NavigationPanelProps {
    isOpen: boolean;
    onClose: () => void;
    userLocation: { lat: number; lng: number } | null;
    city: 'bangalore' | 'delhi' | 'yogyakarta';
    onRoutesCalculated: (routes: RouteOption[], floodZones: GeoJSON.FeatureCollection) => void;
    onRouteSelected: (route: RouteOption) => void;
    onMetroSelected: (station: MetroStation) => void;
    onOriginChange?: (origin: { lat: number; lng: number } | null) => void;
    onDestinationChange?: (destination: { lat: number; lng: number } | null) => void;
    initialDestination?: { lat: number; lng: number; name?: string } | null;
}

// Helper to convert TurnInstruction to RouteInstruction
function convertTurnInstructionsToRouteInstructions(turns: any[]): any[] {
    return turns.map((turn) => ({
        text: turn.instruction,
        distance_meters: turn.distance_meters,
        duration_seconds: turn.duration_seconds,
        maneuver: turn.maneuver_type,
        location: turn.coordinates,
    }));
}

export function NavigationPanel({
    isOpen,
    onClose,
    userLocation,
    city,
    onRoutesCalculated,
    onRouteSelected,
    onMetroSelected,
    onOriginChange,
    onDestinationChange,
    initialDestination,
}: NavigationPanelProps) {
    const { user } = useAuth();
    const { startNavigation } = useNavigation();
    const [origin, setOrigin] = useState<{ lat: number; lng: number; name: string } | null>(null);
    const [destination, setDestination] = useState<{ lat: number; lng: number; name: string } | null>(null);
    const [useCurrentLocation, setUseCurrentLocation] = useState(true);
    const [mode, setMode] = useState<'driving' | 'walking' | 'cycling'>('driving');
    const [_routes, setRoutes] = useState<RouteOption[]>([]);
    const [_selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
    const [avoidMLRisk, setAvoidMLRisk] = useState(false);
    const [comparison, setComparison] = useState<EnhancedRouteComparisonResponse | null>(null);
    const [selectedRouteType, setSelectedRouteType] = useState<'fastest' | 'metro' | 'safest' | null>(null);
    const [showOriginPicker, setShowOriginPicker] = useState(false);
    const [showDestPicker, setShowDestPicker] = useState(false);

    // Set origin from userLocation when using current location
    useEffect(() => {
        if (useCurrentLocation && userLocation) {
            setOrigin({
                lat: userLocation.lat,
                lng: userLocation.lng,
                name: 'Current Location'
            });
        }
    }, [userLocation, useCurrentLocation]);

    // Set destination from initialDestination prop (when coming from "Alt Routes" button)
    useEffect(() => {
        if (initialDestination && isOpen) {
            setDestination({
                lat: initialDestination.lat,
                lng: initialDestination.lng,
                name: initialDestination.name || `Location (${initialDestination.lat.toFixed(4)}, ${initialDestination.lng.toFixed(4)})`
            });
        }
    }, [initialDestination, isOpen]);

    // Notify parent of origin changes for map visualization
    useEffect(() => {
        onOriginChange?.(origin ? { lat: origin.lat, lng: origin.lng } : null);
    }, [origin, onOriginChange]);

    // Notify parent of destination changes for map visualization
    useEffect(() => {
        onDestinationChange?.(destination ? { lat: destination.lat, lng: destination.lng } : null);
    }, [destination, onDestinationChange]);

    const { mutate: compareRoutes, isPending: isCalculating } = useEnhancedCompareRoutes();
    const { data: metrosData } = useNearbyMetros(
        origin?.lat ?? null,
        origin?.lng ?? null,
        city === 'yogyakarta' ? 'YGY' : city === 'bangalore' ? 'BLR' : 'DEL'
    );

    const metros = metrosData?.metros ?? [];

    // Saved routes
    const { data: savedRoutes = [] } = useSavedRoutes(user?.id);
    const { mutate: createSavedRoute, isPending: isSaving } = useCreateSavedRoute();
    const { mutate: deleteSavedRoute } = useDeleteSavedRoute();
    const { mutate: incrementUsage } = useIncrementRouteUsage();

    const handleOriginSelect = (lat: number, lng: number, name: string) => {
        setOrigin({ lat, lng, name });
        setUseCurrentLocation(false);
    };

    const handleUseCurrentLocation = () => {
        if (userLocation) {
            setOrigin({
                lat: userLocation.lat,
                lng: userLocation.lng,
                name: 'Current Location'
            });
            setUseCurrentLocation(true);
            toast.success('Using current location as starting point');
        } else {
            toast.error('Unable to detect your location');
        }
    };

    const handleDestinationSelect = (lat: number, lng: number, name: string) => {
        setDestination({ lat, lng, name });
    };

    const handleOriginMapSelect = (location: { latitude: number; longitude: number; locationName: string }) => {
        handleOriginSelect(location.latitude, location.longitude, location.locationName || `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`);
        setShowOriginPicker(false);
    };

    const handleDestMapSelect = (location: { latitude: number; longitude: number; locationName: string }) => {
        handleDestinationSelect(location.latitude, location.longitude, location.locationName || `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`);
        setShowDestPicker(false);
    };

    const handleFindRoutes = () => {
        if (!origin) {
            toast.error('Please select a starting location');
            return;
        }

        if (!destination) {
            toast.error('Please select a destination');
            return;
        }

        compareRoutes(
            {
                origin: { lat: origin.lat, lng: origin.lng },
                destination: { lat: destination.lat, lng: destination.lng },
                mode,
                city: city === 'yogyakarta' ? 'YGY' : city === 'bangalore' ? 'BLR' : 'DEL',
            },
            {
                onSuccess: (data) => {
                    setComparison(data);
                    setSelectedRouteType(null);

                    // Build routes array for map display from enhanced comparison
                    const routesForMap: RouteOption[] = [];

                    // Add all available routes to map display
                    if (data.routes.fastest) {
                        routesForMap.push({
                            id: data.routes.fastest.id,
                            type: 'fast',
                            city_code: city === 'yogyakarta' ? 'YGY' : city === 'bangalore' ? 'BLR' : 'DEL',
                            geometry: data.routes.fastest.geometry,
                            distance_meters: data.routes.fastest.distance_meters,
                            duration_seconds: data.routes.fastest.duration_seconds,
                            safety_score: data.routes.fastest.safety_score,
                            risk_level: data.routes.fastest.safety_score >= 70 ? 'low' : data.routes.fastest.safety_score >= 40 ? 'medium' : 'high',
                            flood_intersections: data.routes.fastest.hotspot_count,
                            instructions: convertTurnInstructionsToRouteInstructions(data.routes.fastest.instructions),
                        });
                    }

                    if (data.routes.safest) {
                        routesForMap.push({
                            id: data.routes.safest.id,
                            type: 'safe',
                            city_code: city === 'yogyakarta' ? 'YGY' : city === 'bangalore' ? 'BLR' : 'DEL',
                            geometry: data.routes.safest.geometry,
                            distance_meters: data.routes.safest.distance_meters,
                            duration_seconds: data.routes.safest.duration_seconds,
                            safety_score: data.routes.safest.safety_score,
                            risk_level: 'low',
                            flood_intersections: data.routes.safest.hotspot_count,
                            instructions: convertTurnInstructionsToRouteInstructions(data.routes.safest.instructions),
                        });
                    }

                    setRoutes(routesForMap);

                    // Pass routes and flood zones to parent
                    if (routesForMap.length > 0) {
                        onRoutesCalculated(routesForMap, data.flood_zones);
                        toast.success('Route comparison ready');
                    } else {
                        toast.error('No routes found');
                    }
                },
                onError: (error) => {
                    toast.error('Failed to calculate routes');
                    console.error('Route calculation error:', error);
                },
            }
        );
    };

    const _handleRouteSelect = (route: RouteOption) => {
        setSelectedRouteId(route.id);
        onRouteSelected(route);
    };

    // Handle route selection from enhanced route cards
    const handleSelectRoute = (type: 'fastest' | 'metro' | 'safest') => {
        if (!comparison) return;

        setSelectedRouteType(type);

        if (type === 'fastest' && comparison.routes.fastest) {
            const route: RouteOption = {
                id: comparison.routes.fastest.id,
                type: 'fast',
                city_code: city === 'yogyakarta' ? 'YGY' : city === 'bangalore' ? 'BLR' : 'DEL',
                geometry: comparison.routes.fastest.geometry,
                distance_meters: comparison.routes.fastest.distance_meters,
                duration_seconds: comparison.routes.fastest.duration_seconds,
                safety_score: comparison.routes.fastest.safety_score,
                risk_level: comparison.routes.fastest.safety_score >= 70 ? 'low' : comparison.routes.fastest.safety_score >= 40 ? 'medium' : 'high',
                flood_intersections: comparison.routes.fastest.hotspot_count,
                instructions: convertTurnInstructionsToRouteInstructions(comparison.routes.fastest.instructions),
            };
            onRouteSelected(route);
            toast.info('Showing fastest route');
        } else if (type === 'metro' && comparison.routes.metro) {
            // For metro, we'll need to handle segment coordinates
            // For now, just show a toast
            toast.info('Metro route selected - navigation not yet supported');
        } else if (type === 'safest' && comparison.routes.safest) {
            const route: RouteOption = {
                id: comparison.routes.safest.id,
                type: 'safe',
                city_code: city === 'yogyakarta' ? 'YGY' : city === 'bangalore' ? 'BLR' : 'DEL',
                geometry: comparison.routes.safest.geometry,
                distance_meters: comparison.routes.safest.distance_meters,
                duration_seconds: comparison.routes.safest.duration_seconds,
                safety_score: comparison.routes.safest.safety_score,
                risk_level: 'low',
                flood_intersections: comparison.routes.safest.hotspot_count,
                instructions: convertTurnInstructionsToRouteInstructions(comparison.routes.safest.instructions),
            };
            onRouteSelected(route);
            toast.success('Showing safest route');
        }
    };

    // Handle Start Navigation button
    const handleStartNavigation = () => {
        if (!comparison || !selectedRouteType || !destination) {
            toast.error('Please select a route first');
            return;
        }

        // Prepare route for navigation context
        let routeToStart: FastestRouteOption | SafestRouteOption | null = null;
        if (selectedRouteType === 'fastest' && comparison.routes.fastest) {
            routeToStart = comparison.routes.fastest;
        } else if (selectedRouteType === 'safest' && comparison.routes.safest) {
            routeToStart = comparison.routes.safest;
        } else if (selectedRouteType === 'metro') {
            toast.error('Metro navigation not yet supported');
            return;
        }

        if (!routeToStart) {
            toast.error('Selected route not available');
            return;
        }

        // Convert to NavigationContext format
        startNavigation({
            id: routeToStart.id,
            type: selectedRouteType === 'fastest' ? 'fastest' : 'safest',
            coordinates: routeToStart.coordinates,
            instructions: routeToStart.instructions,
            destination: { lat: destination.lat, lng: destination.lng },
            totalDistanceMeters: routeToStart.distance_meters,
            totalDurationSeconds: routeToStart.duration_seconds,
        });

        // Close panel after starting navigation
        onClose();
        toast.success('Navigation started');
    };

    const handleMetroSelect = (station: MetroStation) => {
        onMetroSelected(station);
        toast.success(`Showing route to ${station.name}`);
    };

    const handleSaveRoute = () => {
        if (!user || !origin || !destination) {
            toast.error('Please select both origin and destination first');
            return;
        }

        createSavedRoute({
            user_id: user.id,
            name: `${origin.name} → ${destination.name}`,
            origin_latitude: origin.lat,
            origin_longitude: origin.lng,
            origin_name: origin.name,
            destination_latitude: destination.lat,
            destination_longitude: destination.lng,
            destination_name: destination.name,
            transport_mode: mode,
        }, {
            onSuccess: () => {
                toast.success('Route saved to favorites!');
            },
            onError: () => {
                toast.error('Failed to save route');
            }
        });
    };

    const handleLoadSavedRoute = (saved: any) => {
        // Set origin from saved route
        if (saved.origin_latitude && saved.origin_longitude) {
            setOrigin({
                lat: saved.origin_latitude,
                lng: saved.origin_longitude,
                name: saved.origin_name || 'Saved Origin'
            });
            setUseCurrentLocation(false);
        }

        // Set destination from saved route
        setDestination({
            lat: saved.destination_latitude,
            lng: saved.destination_longitude,
            name: saved.destination_name || saved.name
        });
        setMode(saved.transport_mode as 'driving' | 'walking' | 'cycling');

        // Increment usage count
        incrementUsage(saved.id);

        toast.info(`Loaded: ${saved.name}`);
    };

    const handleDeleteSavedRoute = (routeId: string, routeName: string) => {
        deleteSavedRoute(routeId, {
            onSuccess: () => {
                toast.success(`Deleted "${routeName}"`);
            },
            onError: () => {
                toast.error('Failed to delete route');
            }
        });
    };

    const formatDistance = (meters: number) => {
        if (meters < 1000) return `${Math.round(meters)}m`;
        return `${(meters / 1000).toFixed(1)}km`;
    };

    const _formatDuration = (seconds?: number) => {
        if (!seconds) return 'N/A';
        const minutes = Math.round(seconds / 60);
        if (minutes < 60) return `${minutes}min`;
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${hours}h ${mins}min`;
    };

    const _getSafetyColor = (score: number) => {
        if (score >= 75) return 'text-green-600';
        if (score >= 50) return 'text-yellow-600';
        if (score >= 25) return 'text-orange-600';
        return 'text-red-600';
    };

    const _getSafetyLabel = (score: number) => {
        if (score >= 75) return 'Safe';
        if (score >= 50) return 'Moderate';
        if (score >= 25) return 'Caution';
        return 'Unsafe';
    };

    const _getRouteTypeIcon = (type: string) => {
        switch (type) {
            case 'safe': return <Shield className="h-4 w-4 text-green-600" />;
            case 'balanced': return <Navigation className="h-4 w-4 text-blue-600" />;
            case 'fast': return <Clock className="h-4 w-4 text-orange-600" />;
            default: return <Navigation className="h-4 w-4" />;
        }
    };

    return (
        <>
        <Sheet open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
            <SheetContent
                side="bottom"
                className="p-0"
                style={{
                    maxHeight: '70vh',
                    display: 'flex',
                    flexDirection: 'column',
                    bottom: 'calc(64px + env(safe-area-inset-bottom, 0px))'
                }}
            >
                {/* Header */}
                <div
                    className="px-4 py-3 border-b border-border bg-card"
                    style={{ flexShrink: 0 }}
                >
                    <h2 className="flex items-center gap-2 font-semibold">
                        <Navigation className="h-5 w-5 text-blue-600" />
                        Plan Safe Route
                    </h2>
                </div>

                {/* Scrollable Content */}
                <div
                    className="px-4 pt-4 pb-20 space-y-4"
                    style={{ flex: 1, overflowY: 'auto' }}
                >
                    {/* Starting Location */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <label className="text-sm font-medium">Starting Location</label>
                            <div className="flex items-center gap-1">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleUseCurrentLocation}
                                    className={`text-xs h-7 ${useCurrentLocation ? 'text-green-600' : 'text-muted-foreground'}`}
                                >
                                    <LocateFixed className="h-3 w-3 mr-1" />
                                    GPS
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setShowOriginPicker(true)}
                                    className="text-xs h-7 text-blue-500"
                                >
                                    <MapPinned className="h-3 w-3 mr-1" />
                                    Pin on Map
                                </Button>
                            </div>
                        </div>
                        <SmartSearchBar
                            placeholder="Search for starting point..."
                            onLocationSelect={handleOriginSelect}
                            cityKey={city}
                            userLat={userLocation?.lat}
                            userLng={userLocation?.lng}
                        />
                        {origin && (
                            <div className="flex items-center gap-2 p-2 bg-green-50 rounded-lg border border-green-200">
                                <MapPin className="h-4 w-4 text-green-600 flex-shrink-0" />
                                <span className="text-sm text-green-800 truncate">
                                    {origin.name}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Destination Search */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <label className="text-sm font-medium">Destination</label>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowDestPicker(true)}
                                className="text-xs h-7 text-red-500"
                            >
                                <MapPinned className="h-3 w-3 mr-1" />
                                Pin on Map
                            </Button>
                        </div>
                        <SmartSearchBar
                            placeholder="Search for destination..."
                            onLocationSelect={handleDestinationSelect}
                            cityKey={city}
                            userLat={userLocation?.lat}
                            userLng={userLocation?.lng}
                        />
                        {destination && (
                            <div className="flex items-center gap-2 p-2 bg-red-50 rounded-lg border border-red-200">
                                <MapPin className="h-4 w-4 text-red-600 flex-shrink-0" />
                                <span className="text-sm text-red-800 truncate">
                                    {destination.name}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Transport Mode Selector */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Transport Mode</label>
                        <div className="flex gap-2">
                            <Button
                                variant={mode === 'driving' ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setMode('driving')}
                                className="flex-1"
                            >
                                <Car className="h-4 w-4 mr-2" />
                                Drive
                            </Button>
                            <Button
                                variant={mode === 'walking' ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setMode('walking')}
                                className="flex-1"
                            >
                                <Footprints className="h-4 w-4 mr-2" />
                                Walk
                            </Button>
                            <Button
                                variant={mode === 'cycling' ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setMode('cycling')}
                                className="flex-1"
                            >
                                <Bike className="h-4 w-4 mr-2" />
                                Bike
                            </Button>
                        </div>
                    </div>

                    {/* ML Risk Toggle (Placeholder) */}
                    <div className="flex items-center gap-2 p-3 bg-secondary rounded-lg opacity-50">
                        <input
                            type="checkbox"
                            disabled
                            checked={avoidMLRisk}
                            onChange={(e) => setAvoidMLRisk(e.target.checked)}
                            className="rounded"
                        />
                        <span className="text-sm text-muted-foreground">
                            Avoid AI-predicted flood zones (coming soon)
                        </span>
                    </div>

                    {/* Find Routes Button */}
                    <Button
                        onClick={handleFindRoutes}
                        disabled={!origin || !destination || isCalculating}
                        className="w-full"
                        size="lg"
                    >
                        {isCalculating ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Calculating Routes...
                            </>
                        ) : (
                            <>
                                <Navigation className="h-4 w-4 mr-2" />
                                Find Safe Routes
                            </>
                        )}
                    </Button>

                    {/* Route Comparison Results */}
                    {comparison && (
                        <div className="space-y-3">
                            <h3 className="font-medium flex items-center gap-2">
                                <GitCompare className="h-4 w-4" />
                                Route Comparison
                            </h3>
                            <EnhancedRouteCard
                                routes={comparison.routes}
                                recommendation={comparison.recommendation}
                                selectedType={selectedRouteType}
                                onSelectRoute={handleSelectRoute}
                            />

                            {/* Start Navigation Button */}
                            {selectedRouteType && selectedRouteType !== 'metro' && (
                                <Button
                                    onClick={handleStartNavigation}
                                    className="w-full bg-primary hover:bg-primary/90"
                                    size="lg"
                                >
                                    <Play className="h-4 w-4 mr-2" />
                                    Start Navigation
                                </Button>
                            )}
                        </div>
                    )}

                    {/* Nearby Metro Stations */}
                    {metros.length > 0 && (
                        <div className="space-y-3">
                            <h3 className="font-medium">Nearby Metro Stations</h3>
                            <div className="space-y-2">
                                {metros.slice(0, 5).map((station) => (
                                    <button
                                        key={station.id}
                                        onClick={() => handleMetroSelect(station)}
                                        className="w-full p-3 rounded-lg border border-border hover:border-border text-left transition-all"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-start gap-2">
                                                <Train
                                                    className="h-4 w-4 mt-0.5"
                                                    style={{ color: station.color }}
                                                />
                                                <div>
                                                    <div className="font-medium">{station.name}</div>
                                                    <div className="text-xs text-muted-foreground">{station.line}</div>
                                                </div>
                                            </div>
                                            <div className="text-right text-sm">
                                                <div className="font-medium">{formatDistance(station.distance_meters)}</div>
                                                <div className="text-xs text-muted-foreground">
                                                    {station.walking_minutes} min walk
                                                </div>
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Saved Routes */}
                    {savedRoutes.length > 0 && (
                        <div className="space-y-3">
                            <h3 className="font-medium flex items-center gap-2">
                                <Star className="h-4 w-4 text-yellow-500" />
                                Saved Routes
                            </h3>
                            <div className="space-y-2">
                                {savedRoutes.slice(0, 5).map((saved) => (
                                    <div
                                        key={saved.id}
                                        className="w-full p-3 rounded-lg border border-border hover:border-primary/50 transition-all"
                                    >
                                        <div className="flex items-center justify-between">
                                            <button
                                                onClick={() => handleLoadSavedRoute(saved)}
                                                className="flex items-center gap-2 flex-1 text-left"
                                            >
                                                <Bookmark className="h-4 w-4 text-blue-500 flex-shrink-0" />
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-medium text-sm truncate">{saved.name}</div>
                                                    <div className="text-xs text-muted-foreground">
                                                        Used {saved.use_count}x · {saved.transport_mode}
                                                    </div>
                                                </div>
                                            </button>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteSavedRoute(saved.id, saved.name);
                                                }}
                                                className="p-2 text-muted-foreground/60 hover:text-red-500 transition-colors"
                                                title="Delete saved route"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Save Current Route Button */}
                    {origin && destination && (
                        <Button
                            variant="outline"
                            onClick={handleSaveRoute}
                            disabled={isSaving}
                            className="w-full"
                        >
                            <Bookmark className="h-4 w-4 mr-2" />
                            {isSaving ? 'Saving...' : 'Save This Route'}
                        </Button>
                    )}
                </div>
            </SheetContent>

        </Sheet>

        {/* MapPickers OUTSIDE Sheet to escape Radix Dialog's modal pointer-event trap */}
        <MapPicker
            isOpen={showOriginPicker}
            onClose={() => setShowOriginPicker(false)}
            initialLocation={userLocation ? { latitude: userLocation.lat, longitude: userLocation.lng, accuracy: 10 } : null}
            onLocationSelect={handleOriginMapSelect}
        />
        <MapPicker
            isOpen={showDestPicker}
            onClose={() => setShowDestPicker(false)}
            initialLocation={origin ? { latitude: origin.lat, longitude: origin.lng, accuracy: 10 } : null}
            onLocationSelect={handleDestMapSelect}
        />
        </>
    );
}
