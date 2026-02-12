/**
 * City-specific map configurations for FloodSafe
 *
 * Each city has its own:
 * - Geographic center and bounds
 * - PMTiles files for basemap and flood layers
 * - Metro/transit data files
 * - Default zoom and display settings
 */

export interface CityConfig {
    name: string;
    displayName: string;
    center: [number, number]; // [longitude, latitude]
    zoom: number;
    pitch?: number;
    maxZoom: number;
    minZoom: number;
    bounds: [[number, number], [number, number]]; // [[minLng, minLat], [maxLng, maxLat]]
    pmtiles: {
        basemap: string;
        flood: string;
    };
    metro?: {
        lines: string;
        stations: string;
    };
}

export const CITIES = {
    bangalore: {
        name: 'bangalore',
        displayName: 'Bangalore',
        center: [77.5777, 12.9776] as [number, number],
        zoom: 12.7,
        pitch: 45,
        maxZoom: 17,
        minZoom: 12,
        bounds: [
            [77.199861111, 12.600138889], // [minLng, minLat]
            [77.899861111, 13.400138889]  // [maxLng, maxLat]
        ] as [[number, number], [number, number]],
        pmtiles: {
            basemap: '/basemap.pmtiles',
            flood: '/tiles.pmtiles'
        },
        metro: {
            lines: '/metro-lines.geojson',
            stations: '/metro-stations.geojson'
        }
    },
    delhi: {
        name: 'delhi',
        displayName: 'Delhi',
        center: [77.2090, 28.6139] as [number, number],
        zoom: 12.5,
        pitch: 45,
        maxZoom: 17,
        minZoom: 12,
        bounds: [
            [76.94, 28.42],   // [minLng, minLat]
            [77.46, 28.88]    // [maxLng, maxLat]
        ] as [[number, number], [number, number]],
        pmtiles: {
            basemap: '/delhi-basemap.pmtiles',
            flood: '/delhi-tiles.pmtiles'
        },
        metro: {
            lines: '/delhi-metro-lines.geojson',
            stations: '/delhi-metro-stations.geojson'
        }
    },
    yogyakarta: {
        name: 'yogyakarta',
        displayName: 'Yogyakarta',
        center: [110.3695, -7.7956] as [number, number],
        zoom: 13,
        pitch: 45,
        maxZoom: 17,
        minZoom: 12,
        bounds: [
            [110.30, -7.95],   // [minLng, minLat]
            [110.50, -7.65]    // [maxLng, maxLat]
        ] as [[number, number], [number, number]],
        pmtiles: {
            basemap: '',  // No local PMTiles — uses online fallback (OpenFreeMap)
            flood: ''  // Deferred — flood DEM PMTiles generated later
        }
        // No metro — Yogyakarta doesn't have metro rail
    }
} as const;

export type CityKey = keyof typeof CITIES;

/**
 * Helper function to get city configuration by key
 */
export function getCityConfig(cityKey: CityKey): CityConfig {
    return CITIES[cityKey];
}

/**
 * Helper function to check if coordinates are within city bounds
 */
export function isWithinCityBounds(
    lng: number,
    lat: number,
    cityKey: CityKey
): boolean {
    const city = CITIES[cityKey];
    const [[minLng, minLat], [maxLng, maxLat]] = city.bounds;

    return (
        lng >= minLng &&
        lng <= maxLng &&
        lat >= minLat &&
        lat <= maxLat
    );
}

/**
 * Get all available city keys
 */
export function getAvailableCities(): CityKey[] {
    return Object.keys(CITIES) as CityKey[];
}

/**
 * Detect which city a coordinate belongs to based on bounds
 * Returns city display name or 'Unknown' if outside all known cities
 */
export function detectCityFromCoordinates(
    lng: number,
    lat: number
): string {
    // Check each city's bounds
    for (const cityKey of getAvailableCities()) {
        if (isWithinCityBounds(lng, lat, cityKey)) {
            return CITIES[cityKey].displayName;
        }
    }
    return 'Unknown';
}

/**
 * Get city key from coordinates (for filtering)
 * Returns city key or null if outside all known cities
 */
export function getCityKeyFromCoordinates(
    lng: number,
    lat: number
): CityKey | null {
    for (const cityKey of getAvailableCities()) {
        if (isWithinCityBounds(lng, lat, cityKey)) {
            return cityKey;
        }
    }
    return null;
}
