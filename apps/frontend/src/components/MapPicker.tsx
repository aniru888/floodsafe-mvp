import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import maplibregl from 'maplibre-gl';
import { useCurrentCity } from '../contexts/CityContext';
import { getCityConfig, isWithinCityBounds } from '../lib/map/cityConfigs';
import type { MapPickerProps, LocationWithAddress, GeocodingResult } from '../types';
// Sheet removed - using custom fixed panel to avoid z-index stacking issues
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';
import { Plus, Minus, Navigation, MapPin, Check, X, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import 'maplibre-gl/dist/maplibre-gl.css';

// Debounce utility for reverse geocoding
function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value);

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);

    return debouncedValue;
}

// Inner component - only renders when sheet is open to avoid map conflicts
interface MapContentProps {
    initialLocation: MapPickerProps['initialLocation'];
    onLocationSelect: MapPickerProps['onLocationSelect'];
    onClose: () => void;
}

function MapContent({ initialLocation, onLocationSelect, onClose }: MapContentProps) {
    const mapContainer = useRef<HTMLDivElement>(null);
    const mapRef = useRef<maplibregl.Map | null>(null);
    const city = useCurrentCity();
    const markerRef = useRef<maplibregl.Marker | null>(null);

    const cityConfig = getCityConfig(city);

    // Location state
    const [selectedCoords, setSelectedCoords] = useState<[number, number] | null>(
        initialLocation ? [initialLocation.longitude, initialLocation.latitude] : null
    );

    // Geocoding state
    const [locationName, setLocationName] = useState<string>('');
    const [isGeocoding, setIsGeocoding] = useState(false);
    const [geocodingError, setGeocodingError] = useState<string | null>(null);

    // Map loading states
    const [mapLoadError, setMapLoadError] = useState(false);
    const [isLoaded, setIsLoaded] = useState(false);

    // Debounce coordinates to avoid excessive API calls
    const debouncedCoords = useDebounce(selectedCoords, 500);

    // Set to true to disable map API for layout testing
    const DISABLE_MAP_FOR_LAYOUT_TESTING = false;

    // Initialize map with OpenStreetMap tiles (no PMTiles conflict)
    useEffect(() => {
        if (DISABLE_MAP_FOR_LAYOUT_TESTING) {
            // Skip map initialization, just set loaded state for layout testing
            setIsLoaded(true);
            setSelectedCoords(cityConfig.center);
            return;
        }

        if (!mapContainer.current || mapRef.current) return;

        const targetCoords = initialLocation
            ? [initialLocation.longitude, initialLocation.latitude] as [number, number]
            : cityConfig.center;

        try {
            const map = new maplibregl.Map({
                container: mapContainer.current,
                style: {
                    version: 8,
                    sources: {
                        'osm': {
                            type: 'raster',
                            tiles: [
                                'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
                                'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
                                'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png'
                            ],
                            tileSize: 256,
                            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        }
                    },
                    layers: [
                        {
                            id: 'osm-tiles',
                            type: 'raster',
                            source: 'osm',
                            minzoom: 0,
                            maxzoom: 19
                        }
                    ]
                },
                center: targetCoords,
                zoom: 14
            });

            map.on('load', () => {
                setIsLoaded(true);

                // Create draggable marker
                const marker = new maplibregl.Marker({
                    color: '#ef4444',
                    draggable: true
                })
                    .setLngLat(targetCoords)
                    .addTo(map);

                marker.on('dragend', () => {
                    const lngLat = marker.getLngLat();
                    handleLocationUpdate(lngLat.lng, lngLat.lat);
                });

                markerRef.current = marker;
                setSelectedCoords(targetCoords);
            });

            map.on('click', (e: maplibregl.MapMouseEvent) => {
                const { lng, lat } = e.lngLat;
                handleLocationUpdate(lng, lat);

                if (markerRef.current) {
                    markerRef.current.setLngLat([lng, lat]);
                }
            });

            map.on('error', (e) => {
                console.error('Map error:', e);
                setMapLoadError(true);
            });

            mapRef.current = map;
        } catch (error) {
            console.error('Failed to initialize map:', error);
            setMapLoadError(true);
        }

        return () => {
            if (markerRef.current) {
                markerRef.current.remove();
                markerRef.current = null;
            }
            if (mapRef.current) {
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, []);

    // Map load timeout
    useEffect(() => {
        if (isLoaded) return;

        const timeout = setTimeout(() => {
            if (!isLoaded && !mapLoadError) {
                setMapLoadError(true);
                toast.error('Map is taking too long to load. Please check your internet connection.');
            }
        }, 15000);

        return () => clearTimeout(timeout);
    }, [isLoaded, mapLoadError]);

    const map = mapRef.current;

    // Handle location update with bounds validation
    const handleLocationUpdate = (longitude: number, latitude: number) => {
        if (!isWithinCityBounds(longitude, latitude, city)) {
            toast.error(`Location is outside ${cityConfig.displayName} bounds`);
            setGeocodingError(`Location must be within ${cityConfig.displayName}`);
            return;
        }

        setSelectedCoords([longitude, latitude]);
        setGeocodingError(null);
    };

    // Reverse geocoding
    useEffect(() => {
        if (!debouncedCoords) return;

        const [lng, lat] = debouncedCoords;

        const reverseGeocode = async () => {
            setIsGeocoding(true);
            setGeocodingError(null);

            try {
                // Note: Don't use custom headers as they trigger CORS preflight which Nominatim doesn't support
                const response = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`
                );

                if (!response.ok) {
                    throw new Error(`Geocoding request failed: ${response.status}`);
                }

                const data: GeocodingResult = await response.json();

                const parts = [];
                if (data.address?.road) parts.push(data.address.road);
                if (data.address?.suburb) parts.push(data.address.suburb);
                if (data.address?.city) parts.push(data.address.city);

                const formattedName = parts.length > 0
                    ? parts.join(', ')
                    : data.display_name;

                setLocationName(formattedName);
            } catch (error) {
                console.error('Reverse geocoding error:', error);
                setGeocodingError('Unable to fetch location name');
                setLocationName(`${lat.toFixed(6)}, ${lng.toFixed(6)}`);
            } finally {
                setIsGeocoding(false);
            }
        };

        reverseGeocode();
    }, [debouncedCoords]);

    // Zoom controls
    const handleZoomIn = useCallback(() => {
        if (map) map.zoomIn();
    }, [map]);

    const handleZoomOut = useCallback(() => {
        if (map) map.zoomOut();
    }, [map]);

    // My Location button
    const handleMyLocation = useCallback(() => {
        if (!map) return;

        if ('geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { longitude, latitude } = position.coords;

                    if (!isWithinCityBounds(longitude, latitude, city)) {
                        toast.error(`Your location is outside ${cityConfig.displayName} bounds`);
                        return;
                    }

                    map.flyTo({
                        center: [longitude, latitude],
                        zoom: 16,
                        duration: 2000
                    });

                    if (markerRef.current) {
                        markerRef.current.setLngLat([longitude, latitude]);
                    }

                    handleLocationUpdate(longitude, latitude);
                },
                (error) => {
                    console.error('Geolocation error:', error);
                    toast.error('Unable to get your location. Please enable location permissions.');
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        } else {
            toast.error('Geolocation is not supported by your browser.');
        }
    }, [map, city, cityConfig]);

    // Handle confirm
    const handleConfirm = () => {
        if (!selectedCoords) {
            toast.error('Please select a location on the map');
            return;
        }

        if (geocodingError) {
            toast.error('Please select a valid location');
            return;
        }

        const [longitude, latitude] = selectedCoords;

        const locationData: LocationWithAddress = {
            latitude,
            longitude,
            accuracy: 10,
            locationName: locationName || `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
        };

        onLocationSelect(locationData);
        onClose();
        toast.success('Location selected successfully');
    };

    // Cleanup marker on unmount
    useEffect(() => {
        return () => {
            if (markerRef.current) {
                markerRef.current.remove();
                markerRef.current = null;
            }
        };
    }, []);

    return (
        <div className="flex flex-col h-full">
            {/* Header - Fixed height */}
            <div className="shrink-0 px-4 pt-4 pb-2 border-b flex items-center justify-between bg-card">
                <div>
                    <h2 className="flex items-center gap-2 font-semibold text-foreground">
                        <MapPin className="h-5 w-5 text-destructive" />
                        Select Location on Map
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        Click or drag the marker to select a location in {cityConfig.displayName}
                    </p>
                </div>
                <button
                    onClick={onClose}
                    className="p-2 hover:bg-muted rounded-full"
                    aria-label="Close"
                >
                    <X className="h-5 w-5" />
                </button>
            </div>

            {/* Map Container - Flexible height, takes remaining space */}
            <div className="flex-1 relative min-h-[200px] bg-muted">
                <div
                    ref={mapContainer}
                    className="w-full h-full"
                />

                {/* Map Loading State */}
                {!isLoaded && !mapLoadError && (
                    <div className="absolute inset-0 bg-muted flex flex-col items-center justify-center z-40">
                        <Skeleton className="w-full h-full" />
                        <div className="absolute flex flex-col items-center gap-2">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                            <p className="text-sm text-muted-foreground">Loading flood atlas map...</p>
                        </div>
                    </div>
                )}

                {/* Map Load Error State */}
                {mapLoadError && (
                    <div className="absolute inset-0 bg-muted flex flex-col items-center justify-center z-40 p-6">
                        <AlertCircle className="h-16 w-16 text-destructive mb-4" />
                        <p className="text-lg font-semibold text-foreground mb-2">Failed to Load Map</p>
                        <p className="text-sm text-muted-foreground text-center mb-4">
                            The map couldn't load. Please check your internet connection and try again.
                        </p>
                        <Button
                            onClick={() => {
                                setMapLoadError(false);
                                setIsLoaded(false);
                                // Force re-mount by closing and reopening would be handled by parent
                                window.location.reload();
                            }}
                            variant="outline"
                        >
                            Retry
                        </Button>
                    </div>
                )}

                {/* Map Controls */}
                {isLoaded && (
                    <div className="absolute bottom-4 right-4 flex flex-col gap-2 z-50">
                        <Button
                            size="icon"
                            onClick={handleZoomIn}
                            className="!bg-card !hover:bg-secondary !text-foreground shadow-xl rounded-full w-11 h-11 border-2 border-border"
                            title="Zoom in"
                        >
                            <Plus className="h-5 w-5" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={handleZoomOut}
                            className="!bg-card !hover:bg-secondary !text-foreground shadow-xl rounded-full w-11 h-11 border-2 border-border"
                            title="Zoom out"
                        >
                            <Minus className="h-5 w-5" />
                        </Button>
                        <Button
                            size="icon"
                            onClick={handleMyLocation}
                            className="!bg-primary !hover:bg-primary/90 !text-white shadow-xl rounded-full w-11 h-11"
                            title="My location"
                        >
                            <Navigation className="h-5 w-5" />
                        </Button>
                    </div>
                )}
            </div>

            {/* Footer - Compact, scrollable if needed */}
            <div className="shrink-0 px-3 py-2 border-t bg-card space-y-2 max-h-[30vh] overflow-y-auto">
                <div className="space-y-0.5">
                    <p className="text-xs font-medium text-muted-foreground">Selected Location:</p>
                    {isGeocoding ? (
                        <Skeleton className="h-5 w-full" />
                    ) : (
                        <p className="text-sm font-semibold text-foreground line-clamp-2">
                            {locationName || 'Click on the map to select'}
                        </p>
                    )}
                    {selectedCoords && (
                        <p className="text-[10px] text-muted-foreground/60">
                            {selectedCoords[1].toFixed(5)}, {selectedCoords[0].toFixed(5)}
                        </p>
                    )}
                    {geocodingError && (
                        <p className="text-xs text-destructive">{geocodingError}</p>
                    )}
                </div>

                <div className="flex gap-2">
                    <Button
                        onClick={onClose}
                        variant="outline"
                        size="sm"
                        className="flex-1 h-9"
                    >
                        <X className="h-3 w-3 mr-1" />
                        Cancel
                    </Button>
                    <Button
                        onClick={handleConfirm}
                        disabled={!selectedCoords || !!geocodingError || isGeocoding}
                        size="sm"
                        className="flex-1 h-9 bg-primary hover:bg-primary/90"
                    >
                        <Check className="h-3 w-3 mr-1" />
                        Confirm
                    </Button>
                </div>
            </div>
        </div>
    );
}

// Main component - handles open/close and conditionally renders MapContent
export default function MapPicker({ isOpen, onClose, initialLocation, onLocationSelect }: MapPickerProps) {
    if (!isOpen) return null;

    // Use Portal to render at document.body
    // Position BETWEEN TopNav (56px) and BottomNav (80px) to avoid z-index conflicts
    // z-index 110/111 must be ABOVE NavigationPanel Sheet (z-[100]) so MapPicker is visible
    // Using inline styles because Tailwind JIT may not generate arbitrary values
    return createPortal(
        <>
            {/* Overlay - positioned between nav bars */}
            <div
                style={{ position: 'fixed', top: 56, left: 0, right: 0, bottom: 'calc(64px + env(safe-area-inset-bottom, 0px))', backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 190 }}
                onClick={onClose}
            />
            {/* Side Panel - fits between TopNav and BottomNav */}
            <div
                style={{ position: 'fixed', top: 56, left: 0, bottom: 'calc(64px + env(safe-area-inset-bottom, 0px))', width: 'min(350px, 90vw)', zIndex: 191 }}
                className="bg-card shadow-xl flex flex-col rounded-br-lg overflow-hidden"
            >
                <MapContent
                    initialLocation={initialLocation}
                    onLocationSelect={onLocationSelect}
                    onClose={onClose}
                />
            </div>
        </>,
        document.body
    );
}
