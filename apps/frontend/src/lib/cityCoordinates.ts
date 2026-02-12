/**
 * City coordinates for FloodSafe location fallback.
 *
 * When GPS is unavailable (desktop browsers, timeout), we fall back
 * to the user's city preference center coordinates.
 */

export interface CityInfo {
  lat: number;
  lng: number;
  name: string;
  /** Full display name for UI */
  displayName: string;
  /** Approximate radius in km for "within city" checks */
  radiusKm: number;
}

/**
 * City coordinates for supported cities.
 * Key is lowercase city identifier matching user.city_preference.
 */
export const CITY_COORDINATES: Record<string, CityInfo> = {
  delhi: {
    lat: 28.6139,
    lng: 77.209,
    name: "Delhi",
    displayName: "Delhi NCR",
    radiusKm: 30,
  },
  bangalore: {
    lat: 12.9716,
    lng: 77.5946,
    name: "Bangalore",
    displayName: "Bengaluru",
    radiusKm: 25,
  },
  mumbai: {
    lat: 19.076,
    lng: 72.8777,
    name: "Mumbai",
    displayName: "Mumbai",
    radiusKm: 25,
  },
  chennai: {
    lat: 13.0827,
    lng: 80.2707,
    name: "Chennai",
    displayName: "Chennai",
    radiusKm: 20,
  },
  kolkata: {
    lat: 22.5726,
    lng: 88.3639,
    name: "Kolkata",
    displayName: "Kolkata",
    radiusKm: 20,
  },
  hyderabad: {
    lat: 17.385,
    lng: 78.4867,
    name: "Hyderabad",
    displayName: "Hyderabad",
    radiusKm: 25,
  },
  yogyakarta: {
    lat: -7.7956,
    lng: 110.3695,
    name: "Yogyakarta",
    displayName: "Yogyakarta",
    radiusKm: 15,
  },
};

/** Default city when none specified */
export const DEFAULT_CITY = "delhi";

/**
 * Get city center coordinates from city preference.
 *
 * @param cityPreference - City preference string (e.g., "delhi", "Delhi")
 * @returns City info with lat/lng, or null if city not found
 */
export function getCityCenter(
  cityPreference: string | undefined | null
): CityInfo | null {
  if (!cityPreference) return null;

  const normalized = cityPreference.toLowerCase().trim();
  return CITY_COORDINATES[normalized] || null;
}

/**
 * Get city center coordinates with Delhi as fallback.
 *
 * @param cityPreference - City preference string
 * @returns City info (always returns a value, defaults to Delhi)
 */
export function getCityCenterOrDefault(
  cityPreference: string | undefined | null
): CityInfo {
  const city = getCityCenter(cityPreference);
  return city || CITY_COORDINATES[DEFAULT_CITY];
}

/**
 * Get simple lat/lng object for map centering.
 *
 * @param cityPreference - City preference string
 * @returns {lat, lng} object or null
 */
export function getCityLatLng(
  cityPreference: string | undefined | null
): { lat: number; lng: number } | null {
  const city = getCityCenter(cityPreference);
  if (!city) return null;
  return { lat: city.lat, lng: city.lng };
}

/**
 * Check if coordinates are within a city's approximate bounds.
 *
 * Uses simple distance check from city center.
 *
 * @param lat - Latitude
 * @param lng - Longitude
 * @param cityPreference - City to check against
 * @returns true if within city bounds
 */
export function isWithinCity(
  lat: number,
  lng: number,
  cityPreference: string | undefined | null
): boolean {
  const city = getCityCenter(cityPreference);
  if (!city) return false;

  // Approximate distance calculation (good enough for city-level)
  const latDiff = Math.abs(lat - city.lat);
  const lngDiff = Math.abs(lng - city.lng);

  // 1 degree latitude ≈ 111 km
  // 1 degree longitude ≈ 111 km * cos(lat) ≈ 95 km at 28°N (Delhi)
  const distanceKm = Math.sqrt(
    Math.pow(latDiff * 111, 2) + Math.pow(lngDiff * 95, 2)
  );

  return distanceKm <= city.radiusKm;
}
