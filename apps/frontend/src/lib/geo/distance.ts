/**
 * Geospatial distance and route utilities for FloodSafe navigation
 */

/**
 * Format duration in seconds to human-readable string
 * @param seconds - Duration in seconds
 * @returns Formatted string like "15 min" or "1 hr 20 min"
 */
export function formatDuration(seconds: number): string {
    if (seconds < 60) return '< 1 min';

    const minutes = Math.round(seconds / 60);

    if (minutes < 60) {
        return `${minutes} min`;
    }

    const hours = Math.floor(minutes / 60);
    const remainingMins = minutes % 60;

    if (remainingMins === 0) {
        return `${hours} hr`;
    }

    return `${hours} hr ${remainingMins} min`;
}

/**
 * Format distance in meters to human-readable string
 * @param meters - Distance in meters
 * @returns Formatted string like "5.2 km" or "850 m"
 */
export function formatDistance(meters: number): string {
    if (meters < 1000) {
        return `${Math.round(meters)} m`;
    }
    return `${(meters / 1000).toFixed(1)} km`;
}

/**
 * Calculate distance between two points using Haversine formula
 * @param lat1 - Latitude of first point
 * @param lng1 - Longitude of first point
 * @param lat2 - Latitude of second point
 * @param lng2 - Longitude of second point
 * @returns Distance in meters
 */
export function haversineDistance(
    lat1: number,
    lng1: number,
    lat2: number,
    lng2: number
): number {
    const R = 6371000; // Earth's radius in meters
    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

/**
 * Convert degrees to radians
 */
function toRad(deg: number): number {
    return deg * (Math.PI / 180);
}

/**
 * Calculate initial bearing from point 1 to point 2 (forward azimuth)
 * @returns Bearing in degrees clockwise from north (0-360)
 */
export function calculateBearing(
    lat1: number,
    lng1: number,
    lat2: number,
    lng2: number
): number {
    const dLng = toRad(lng2 - lng1);
    const y = Math.sin(dLng) * Math.cos(toRad(lat2));
    const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
              Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLng);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

/**
 * Find hotspots within proximity radius of a location
 * @param userLat - User's latitude
 * @param userLng - User's longitude
 * @param hotspots - Array of hotspot objects with coordinates
 * @param proximityMeters - Proximity radius in meters (default 400m)
 * @returns Array of nearby hotspots with distance, sorted by distance
 */
export function findNearbyHotspots(
    userLat: number,
    userLng: number,
    hotspots: Array<{
        coordinates: [number, number];
        id: number;
        name: string;
        fhi_level: string;
        fhi_color: string;
    }>,
    proximityMeters: number = 400
) {
    return hotspots
        .map(h => ({
            id: h.id,
            name: h.name,
            fhi_level: h.fhi_level,
            fhi_color: h.fhi_color,
            distanceMeters: haversineDistance(
                userLat,
                userLng,
                h.coordinates[1],
                h.coordinates[0]
            )
        }))
        .filter(h => h.distanceMeters <= proximityMeters && h.fhi_level !== 'low')
        .sort((a, b) => a.distanceMeters - b.distanceMeters);
}

/**
 * Check if user is off the planned route
 * @param userLat - User's current latitude
 * @param userLng - User's current longitude
 * @param routeCoords - Array of route coordinates [lng, lat]
 * @param thresholdMeters - Deviation threshold in meters (default 50m)
 * @returns True if user is off route beyond threshold
 */
export function isOffRoute(
    userLat: number,
    userLng: number,
    routeCoords: [number, number][],
    thresholdMeters: number = 50
): boolean {
    if (routeCoords.length === 0) return false;

    let minDistance = Infinity;

    for (const [lng, lat] of routeCoords) {
        const dist = haversineDistance(userLat, userLng, lat, lng);
        if (dist < minDistance) {
            minDistance = dist;
        }
        if (minDistance < thresholdMeters) {
            return false;
        }
    }

    return minDistance > thresholdMeters;
}

/**
 * Find the next turn instruction based on user's current position
 * @param userLat - User's current latitude
 * @param userLng - User's current longitude
 * @param instructions - Array of turn instructions with coordinates
 * @returns Next instruction and distance to it, or null if none
 */
export function findNextInstruction(
    userLat: number,
    userLng: number,
    instructions: Array<{
        coordinates: [number, number];
        instruction: string;
        distance_meters: number;
    }>
): { instruction: any; distanceToNext: number } | null {
    if (instructions.length === 0) return null;

    let closestIdx = 0;
    let minDist = Infinity;

    // Find the instruction closest to user
    for (let i = 0; i < instructions.length; i++) {
        const [lng, lat] = instructions[i].coordinates;
        const dist = haversineDistance(userLat, userLng, lat, lng);
        if (dist < minDist) {
            minDist = dist;
            closestIdx = i;
        }
    }

    // Return next instruction (not the one we're at)
    const nextIdx = minDist < 50 ? closestIdx + 1 : closestIdx;
    if (nextIdx >= instructions.length) {
        return {
            instruction: instructions[instructions.length - 1],
            distanceToNext: 0
        };
    }

    const next = instructions[nextIdx];
    const [lng, lat] = next.coordinates;
    const distanceToNext = haversineDistance(userLat, userLng, lat, lng);

    return { instruction: next, distanceToNext };
}

/**
 * Project a point onto a line segment and return the closest point on the segment.
 * Uses vector math for accurate projection with parametric line representation.
 *
 * @param pointLat - Point latitude to project
 * @param pointLng - Point longitude to project
 * @param segStartLng - Segment start longitude
 * @param segStartLat - Segment start latitude
 * @param segEndLng - Segment end longitude
 * @param segEndLat - Segment end latitude
 * @returns Projected point [lng, lat] on the segment
 */
export function projectPointOntoSegment(
    pointLat: number,
    pointLng: number,
    segStartLng: number,
    segStartLat: number,
    segEndLng: number,
    segEndLat: number
): [number, number] {
    // Vector from segment start to point
    const dx = pointLng - segStartLng;
    const dy = pointLat - segStartLat;

    // Vector from segment start to segment end
    const segDx = segEndLng - segStartLng;
    const segDy = segEndLat - segStartLat;

    // Segment length squared (avoid sqrt for performance)
    const segLengthSq = segDx * segDx + segDy * segDy;

    if (segLengthSq === 0) {
        // Segment is a point (start equals end)
        return [segStartLng, segStartLat];
    }

    // Project point onto line using dot product
    // t represents position along segment: 0 = start, 1 = end
    let t = (dx * segDx + dy * segDy) / segLengthSq;

    // Clamp t to [0, 1] to stay within segment bounds
    t = Math.max(0, Math.min(1, t));

    // Calculate projected point using parametric form: P = A + t*(B-A)
    return [
        segStartLng + t * segDx,
        segStartLat + t * segDy
    ];
}

/**
 * Find the closest point on the route to the user's current position
 * using line segment interpolation for smooth snapping.
 *
 * Returns the remaining route from the projected point to destination,
 * prepended with the user's current position for smooth display.
 *
 * Uses a search window around the last known segment to prevent GPS
 * inaccuracy from snapping to far-away segments (which would truncate
 * the displayed route into a near-straight line).
 *
 * @param userLat - User's current latitude
 * @param userLng - User's current longitude
 * @param routeCoords - Full route coordinates [lng, lat][]
 * @param lastSegmentIdx - Last known segment index for windowed search (prevents GPS jump)
 * @returns Object with remaining coordinates and the matched segment index
 */
export function getRemainingRoute(
    userLat: number,
    userLng: number,
    routeCoords: [number, number][],
    lastSegmentIdx: number = 0,
): { coordinates: [number, number][]; segmentIdx: number } {
    if (routeCoords.length === 0) return { coordinates: [], segmentIdx: 0 };
    if (routeCoords.length === 1) return { coordinates: [[userLng, userLat], ...routeCoords], segmentIdx: 0 };

    // Search window: only look forward from last known position (+ small lookback for GPS jitter)
    // This prevents inaccurate GPS from snapping to a segment near the end of the route
    const LOOKBACK = 3;   // Allow small backward jump for GPS correction
    const LOOKAHEAD = 40; // Look ahead up to 40 segments (~500-1000m on detailed routes)
    const searchStart = Math.max(0, lastSegmentIdx - LOOKBACK);
    const searchEnd = Math.min(routeCoords.length - 1, lastSegmentIdx + LOOKAHEAD);

    let closestSegmentIdx = lastSegmentIdx;
    let minDistance = Infinity;
    let closestProjectedPoint: [number, number] = [userLng, userLat];

    // Find the route SEGMENT closest to user within the search window
    for (let i = searchStart; i < searchEnd; i++) {
        const [startLng, startLat] = routeCoords[i];
        const [endLng, endLat] = routeCoords[i + 1];

        // Project user position onto this segment
        const projected = projectPointOntoSegment(
            userLat, userLng,
            startLng, startLat,
            endLng, endLat
        );

        // Calculate distance from user to projected point
        const dist = haversineDistance(userLat, userLng, projected[1], projected[0]);

        if (dist < minDistance) {
            minDistance = dist;
            closestSegmentIdx = i;
            closestProjectedPoint = projected;
        }
    }

    // Safety: if user is very far from the windowed match (>300m), do a full scan
    // This handles route recalculation or GPS re-acquisition after tunnel/signal loss
    if (minDistance > 300) {
        for (let i = 0; i < routeCoords.length - 1; i++) {
            const [startLng, startLat] = routeCoords[i];
            const [endLng, endLat] = routeCoords[i + 1];

            const projected = projectPointOntoSegment(
                userLat, userLng,
                startLng, startLat,
                endLng, endLat
            );

            const dist = haversineDistance(userLat, userLng, projected[1], projected[0]);

            if (dist < minDistance) {
                minDistance = dist;
                closestSegmentIdx = i;
                closestProjectedPoint = projected;
            }
        }
    }

    // Build remaining route:
    // 1. User's current position (for smooth line from user marker)
    // 2. Projected point on route segment (snap point)
    // 3. All points from segment end to destination
    const coordinates: [number, number][] = [
        [userLng, userLat],            // Current user position
        closestProjectedPoint,          // Smooth snap point on route
        ...routeCoords.slice(closestSegmentIdx + 1)  // Rest of route
    ];

    return { coordinates, segmentIdx: closestSegmentIdx };
}
