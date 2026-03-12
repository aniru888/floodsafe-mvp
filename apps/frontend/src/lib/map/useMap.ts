import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { Protocol, PMTiles } from 'pmtiles';
import { toast } from 'sonner';
import { MAP_CONSTANTS, getMapConfig } from './config';
import { getCityConfig, type CityKey } from './cityConfigs';
import mapStyle from './styles.json';

// Global flag to track if the error handler has been added
let globalErrorHandlerAdded = false;

export function useMap(
    containerRef: React.RefObject<HTMLDivElement>,
    cityKey: CityKey = MAP_CONSTANTS.DEFAULT_CITY
) {
    const mapRef = useRef<maplibregl.Map | null>(null);
    const [isLoaded, setIsLoaded] = useState(false);
    const isCleaningUp = useRef(false);

    // Add global handler for unhandled promise rejections from MapLibre
    useEffect(() => {
        if (globalErrorHandlerAdded) return;
        globalErrorHandlerAdded = true;

        const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
            const errorMsg = event.reason?.message || String(event.reason);
            // Suppress MapLibre sourceCaches race condition errors during map destruction
            if (errorMsg.includes('sourceCaches') || errorMsg.includes('Cannot read properties of undefined')) {
                console.log('MapLibre cleanup race condition (safe to ignore):', errorMsg);
                event.preventDefault(); // Prevents the error from appearing in console
            }
        };

        window.addEventListener('unhandledrejection', handleUnhandledRejection);

        return () => {
            // Don't remove the handler - keep it for the lifetime of the app
            // to handle any late async errors
        };
    }, []);

    useEffect(() => {
        // Reset isLoaded when city changes to prevent accessing stale map
        setIsLoaded(false);
        isCleaningUp.current = false;

        if (!containerRef.current) return;

        // If map already exists, remove it before creating new one
        if (mapRef.current) {
            isCleaningUp.current = true;
            try {
                mapRef.current.remove();
            } catch (e) {
                console.log('Map cleanup warning (safe to ignore):', e);
            }
            mapRef.current = null;
            isCleaningUp.current = false;
        }

        const cityConfig = getCityConfig(cityKey);

        // Initialize PMTiles protocol
        const protocol = new Protocol();

        // Add basemap PMTiles for selected city (only if local file exists)
        if (cityConfig.pmtiles.basemap) {
            const basemapPMTiles = new PMTiles(cityConfig.pmtiles.basemap);
            protocol.add(basemapPMTiles);
        }

        // Add flood tiles PMTiles for selected city (only if available)
        if (cityConfig.pmtiles.flood) {
            const floodPMTiles = new PMTiles(cityConfig.pmtiles.flood);
            protocol.add(floodPMTiles);
        }

        // Register protocol with MapLibre - only if not already registered
        // This prevents errors in React Strict Mode or multiple map instances
        let protocolAdded = false;
        try {
            maplibregl.addProtocol('pmtiles', protocol.tile);
            protocolAdded = true;
        } catch (error) {
            // Protocol already registered - this is fine, reuse existing
            console.log('PMTiles protocol already registered, reusing existing');
        }

        // Build sources conditionally based on city capabilities
        const sources: Record<string, any> = {
            ...mapStyle.sources,
            // Override the basemap source — use local PMTiles if available, else online CDN
            'openmaptiles': cityConfig.pmtiles.basemap
                ? { type: 'vector' as const, url: `pmtiles://${cityConfig.pmtiles.basemap}` }
                : { type: 'vector' as const, url: 'https://tiles.openfreemap.org/planet' },
            // Add search result marker source
            'search-result': {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: [] }
            }
        };

        // Report CDN fallback — NO SILENT FALLBACKS (CLAUDE.md rule #14)
        if (!cityConfig.pmtiles.basemap) {
            console.info(`[Map] ${cityConfig.displayName}: No local basemap — using online CDN tiles`);
            toast.info(
                `${cityConfig.displayName}: Using online map tiles (no local data available)`,
                { id: 'map-cdn-fallback', duration: 5000 }
            );
        }

        if (!cityConfig.pmtiles.flood) {
            console.info(`[Map] ${cityConfig.displayName}: No flood overlay tiles available`);
        }

        // Add flood tiles source only if available
        if (cityConfig.pmtiles.flood) {
            sources['flood-tiles'] = {
                type: 'vector',
                url: `pmtiles://${cityConfig.pmtiles.flood}`,
                attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>'
            };
        }

        // Add metro sources only if city has metro
        if (cityConfig.metro) {
            sources['metro-lines'] = {
                type: 'geojson',
                data: cityConfig.metro.lines
            };
            sources['metro-stations'] = {
                type: 'geojson',
                data: cityConfig.metro.stations
            };
        }

        // Add alias label source for all cities (static GeoJSON, like metro)
        sources['alias-labels'] = {
            type: 'geojson',
            data: `/${cityKey}-alias-labels.geojson`
        };

        // Build layers conditionally
        const layers: any[] = [
            ...mapStyle.layers.filter(l => l.id !== 'railway-transit' && l.id !== 'railway'),
        ];

        // Add metro layers only if city has metro
        if (cityConfig.metro) {
            layers.push(
                {
                    id: 'metro-lines-layer',
                    type: 'line',
                    source: 'metro-lines',
                    layout: {
                        'visibility': 'visible',
                        'line-join': 'round',
                        'line-cap': 'round'
                    },
                    paint: {
                        'line-color': ['coalesce', ['get', 'colour'], ['get', 'color'], '#888888'],
                        'line-width': 4,
                        'line-opacity': 1
                    }
                },
                {
                    id: 'metro-stations-layer',
                    type: 'circle',
                    source: 'metro-stations',
                    layout: {
                        'visibility': 'visible'
                    },
                    paint: {
                        'circle-radius': 4,
                        'circle-color': '#ffffff',
                        'circle-stroke-width': 2,
                        'circle-stroke-color': ['coalesce', ['get', 'colour'], ['get', 'color'], '#888888']
                    }
                },
                {
                    id: 'metro-station-names-layer',
                    type: 'symbol',
                    source: 'metro-stations',
                    minzoom: 12,
                    layout: {
                        'visibility': 'visible',
                        'text-field': ['get', 'name'],
                        'text-font': ['Open Sans Bold'],
                        'text-size': 12,
                        'text-offset': [0, 1.5],
                        'text-anchor': 'top'
                    },
                    paint: {
                        'text-color': '#333333',
                        'text-halo-color': '#ffffff',
                        'text-halo-width': 2
                    }
                }
            );
        }

        // Add alias label layers — area/neighborhood names on map (3 tiers by zoom)
        layers.push(
            {
                id: 'alias-labels-tier1',
                type: 'symbol',
                source: 'alias-labels',
                filter: ['==', ['get', 'tier'], 1],
                minzoom: 12,
                layout: {
                    'text-field': ['get', 'name'],
                    'text-font': ['Open Sans Regular'],
                    'text-size': ['interpolate', ['linear'], ['zoom'], 12, 11, 15, 13],
                    'text-allow-overlap': false,
                    'text-padding': 8,
                    'text-anchor': 'center',
                    'text-max-width': 8,
                    'text-letter-spacing': 0.05,
                    'visibility': 'visible'
                },
                paint: {
                    'text-color': '#6b7280',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 1.5,
                    'text-opacity': 0.8
                }
            },
            {
                id: 'alias-labels-tier2',
                type: 'symbol',
                source: 'alias-labels',
                filter: ['==', ['get', 'tier'], 2],
                minzoom: 13,
                layout: {
                    'text-field': ['get', 'name'],
                    'text-font': ['Open Sans Regular'],
                    'text-size': ['interpolate', ['linear'], ['zoom'], 13, 10, 15, 12],
                    'text-allow-overlap': false,
                    'text-padding': 6,
                    'text-anchor': 'center',
                    'text-max-width': 8,
                    'visibility': 'visible'
                },
                paint: {
                    'text-color': '#9ca3af',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 1.2,
                    'text-opacity': 0.75
                }
            },
            {
                id: 'alias-labels-tier3',
                type: 'symbol',
                source: 'alias-labels',
                filter: ['==', ['get', 'tier'], 3],
                minzoom: 14.5,
                layout: {
                    'text-field': ['get', 'name'],
                    'text-font': ['Open Sans Regular'],
                    'text-size': 9,
                    'text-allow-overlap': false,
                    'text-padding': 4,
                    'text-anchor': 'center',
                    'text-max-width': 7,
                    'visibility': 'visible'
                },
                paint: {
                    'text-color': '#9ca3af',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 1.0,
                    'text-opacity': 0.7
                }
            }
        );

        // Add flood layer only if flood tiles available
        if (cityConfig.pmtiles.flood) {
            layers.push({
                id: 'flood-layer',
                type: 'fill',
                source: 'flood-tiles',
                'source-layer': 'stream_influence_water_difference',
                paint: {
                    'fill-color': [
                        'interpolate',
                        ['linear'],
                        ['get', 'VALUE'],
                        1, '#FFFFCC',
                        2, '#A1DAB4',
                        3, '#41B6C4',
                        4, '#225EA8'
                    ],
                    'fill-opacity': 0.25
                }
            });
        }

        // Always add search result layers
        layers.push(
            {
                id: 'search-marker-glow',
                type: 'circle',
                source: 'search-result',
                paint: {
                    'circle-radius': 20,
                    'circle-color': '#ef4444',
                    'circle-opacity': 0.3,
                    'circle-blur': 0.5
                }
            },
            {
                id: 'search-marker',
                type: 'circle',
                source: 'search-result',
                paint: {
                    'circle-radius': 10,
                    'circle-color': '#ef4444',
                    'circle-stroke-width': 3,
                    'circle-stroke-color': '#ffffff'
                }
            },
            {
                id: 'search-label',
                type: 'symbol',
                source: 'search-result',
                layout: {
                    'text-field': ['get', 'name'],
                    'text-font': ['Open Sans Bold'],
                    'text-size': 13,
                    'text-offset': [0, 2],
                    'text-anchor': 'top',
                    'text-max-width': 15
                },
                paint: {
                    'text-color': '#1f2937',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 2
                }
            }
        );

        // Use the comprehensive OpenMapTiles style with flood data overlay
        const style = {
            ...mapStyle,
            sources,
            layers
        };

        const map = new maplibregl.Map({
            container: containerRef.current,
            style: style as maplibregl.StyleSpecification,
            ...getMapConfig(cityKey)
        });

        map.on('load', () => {
            console.log('✅ Map loaded successfully');

            // Safely access map style with type guards
            const mapStyle = map.getStyle();
            if (mapStyle?.sources) {
                console.log('📋 Available sources:', Object.keys(mapStyle.sources));
            }

            if (mapStyle?.layers && Array.isArray(mapStyle.layers)) {
                console.log('📋 Available layers:', mapStyle.layers.map(l => l.id));

                // Debug: Check if railway layers exist
                const railwayLayers = mapStyle.layers.filter(l =>
                    typeof l.id === 'string' && l.id.includes('railway')
                );
                console.log('🚇 Railway layers found:', railwayLayers.map(l => l.id));
            }

            // Debug: Try to query features from transportation layer at current view
            setTimeout(() => {
                try {
                    const style = map.getStyle();
                    if (!style?.sources || typeof style.sources !== 'object') {
                        console.log('ℹ️ Map style not ready yet');
                        return;
                    }

                    const sourceKeys = Object.keys(style.sources);
                    const sourceKey = sourceKeys.find(key =>
                        typeof key === 'string' && (key.includes('basemap') || key.includes('openmaptiles'))
                    );

                    if (sourceKey) {
                        const source = map.getSource(sourceKey);
                        if (!source) {
                            console.log('ℹ️ Source not found:', sourceKey);
                            return;
                        }

                        const features = map.querySourceFeatures(sourceKey, {
                            sourceLayer: 'transportation'
                        });

                        if (features && Array.isArray(features) && features.length > 0) {
                            console.log('🚗 Transportation features sample:', features.slice(0, 5));
                            const transitFeatures = features.filter(f =>
                                f.properties && typeof f.properties === 'object' && f.properties.class === 'transit'
                            );
                            if (transitFeatures.length > 0) {
                                console.log('🚇 Transit features:', transitFeatures.length, transitFeatures.slice(0, 3));
                            }
                        }
                    } else {
                        console.log('ℹ️ No basemap source found for querying transportation features');
                    }
                } catch (error) {
                    console.log('ℹ️ Could not query transportation features:', error);
                }
            }, 2000);

            setIsLoaded(true);
        });

        map.on('error', (e) => {
            // Suppress cleanup race condition errors (sourceCaches undefined during map destruction)
            const errorMsg = e.error?.message || String(e);
            if (errorMsg.includes('sourceCaches') || isCleaningUp.current) {
                console.log('Map cleanup race condition (safe to ignore):', errorMsg);
                return;
            }
            console.error('❌ Map error:', e.error?.message || e.message || JSON.stringify(e));
            if (e.error?.message?.includes('404') || e.error?.message?.includes('Failed to fetch')) {
                toast.error(`Map resources for ${cityConfig.displayName} failed to load. Try refreshing.`, { id: 'map-resource-error' });
            }
        });

        mapRef.current = map;

        return () => {
            // Mark as cleaning up to suppress race condition errors
            isCleaningUp.current = true;

            // Only remove if map still exists (might already be removed on city change)
            if (mapRef.current) {
                try {
                    mapRef.current.remove();
                } catch (e) {
                    console.log('Map cleanup warning (safe to ignore):', e);
                }
                mapRef.current = null;
            }
            // Only remove protocol if we added it
            if (protocolAdded) {
                try {
                    maplibregl.removeProtocol('pmtiles');
                } catch (error) {
                    // Protocol might have been removed already - this is fine
                    console.log('PMTiles protocol already removed or never added');
                }
            }
        };
    }, [cityKey]); // Re-initialize map when city changes

    return { map: mapRef.current, isLoaded };
}
