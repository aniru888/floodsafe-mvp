import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { fetchJson, uploadFile } from './client';
import { API_BASE_URL } from './config';
import { User, GeocodingResult, DailyRoute, DailyRouteCreate, WatchArea, WatchAreaCreate, RouteCalculationRequest, RouteCalculationResponse, MetroStation, RouteOption, RouteComparisonRequest, RouteComparisonResponse, EnhancedRouteComparisonResponse, FastestRouteOption, SafestRouteOption, WatchAreaRiskAssessment, FloodHubStatus, FloodHubGauge, FloodHubForecast, FloodHubSignificantEvent, SafetyCircle, SafetyCircleDetail, SafetyCircleCreate, SafetyCircleUpdate, CircleMemberAdd, CircleMemberUpdate, CircleAlert, CircleAlertsResponse, CircleUnreadCount, JoinCircleRequest, BulkAddResult, RiskSummaryResponse, GroundsourceCluster, GroundsourceEpisode, HistoricalStats, PersonalPin, FhiHistoryEntry, ChatResponse, AddressRiskResult } from '../../types';
import { validateUsers, validateSensors, validateReports } from './validators';
import { getCityCode } from '../cityUtils';

// Types
export interface Sensor {
    id: string;
    location_lat: number; // Note: Backend returns latitude/longitude in response? Let's check DTO.
    // Wait, SensorResponse has latitude/longitude.
    latitude: number;
    longitude: number;
    status: string;
    last_ping?: string;
}

export interface Report {
    id: string;
    description: string;
    latitude: number;
    longitude: number;
    media_url?: string;
    verified: boolean;
    verification_score: number;
    upvotes: number;
    downvotes: number;  // Required field now
    timestamp: string;
    // OTP/Phone verification fields
    phone_verified?: boolean;
    water_depth?: string;
    vehicle_passability?: string;
    iot_validation_score?: number;
    // Gamification fields
    quality_score?: number;
    verified_at?: string;
    // Archive field - null means active, timestamp means archived
    archived_at?: string | null;
    // Community feedback fields
    comment_count?: number;
    user_vote?: 'upvote' | 'downvote' | null;  // User's current vote on this report
    // ML classification results (from backend)
    ml_classification?: string;  // 'flood' or 'no_flood'
    ml_confidence?: number;  // 0.0 to 1.0
    ml_is_flood?: boolean;
    ml_needs_review?: boolean;
    // Admin report fields
    admin_created?: boolean;
    source?: string;
}

export interface ReportCreate {
    user_id: string;
    description: string;
    latitude: number;
    longitude: number;
    image: File;  // Required by backend
    photo_latitude?: number;
    photo_longitude?: number;
    photo_location_verified?: boolean;
    water_depth?: string;
    vehicle_passability?: string;
}

// Re-export User from types for backwards compatibility
export type { User };

// Hooks

export function useSensors() {
    return useQuery({
        queryKey: ['sensors'],
        queryFn: async () => {
            const data = await fetchJson<unknown>('/sensors/');
            return validateSensors(data);
        },
        refetchInterval: 30000, // Default 30 second refresh
    });
}

export function useReports() {
    return useQuery({
        queryKey: ['reports'],
        queryFn: async () => {
            const data = await fetchJson<unknown>('/reports/');
            return validateReports(data);
        },
        refetchInterval: 30000, // Default 30 second refresh
    });
}

export function useUserReports(userId: string | undefined, limit: number = 50) {
    return useQuery({
        queryKey: ['reports', 'user', userId, limit],
        queryFn: async () => {
            const data = await fetchJson<unknown>(`/reports/user/${userId}?limit=${limit}`);
            return validateReports(data);
        },
        enabled: !!userId, // Only run if userId is provided
        staleTime: 30000, // Consider fresh for 30 seconds
    });
}

/**
 * Fetch user's archived reports (reports older than 3 days or explicitly archived)
 */
export function useArchivedReports(userId: string | undefined, limit: number = 50) {
    return useQuery({
        queryKey: ['reports', 'archived', userId, limit],
        queryFn: async () => {
            const data = await fetchJson<unknown>(`/reports/user/${userId}/archived?limit=${limit}`);
            return validateReports(data);
        },
        enabled: !!userId,
        staleTime: 60000, // Archived reports don't change often
    });
}

/**
 * Report statistics including active and archived counts
 */
export interface ReportStats {
    user_id: string;
    active_reports: number;
    archived_reports: number;
    total_reports: number;
    archive_days: number;
}

export function useReportStats(userId: string | undefined) {
    return useQuery({
        queryKey: ['reports', 'stats', userId],
        queryFn: async () => {
            return fetchJson<ReportStats>(`/reports/user/${userId}/stats`);
        },
        enabled: !!userId,
        staleTime: 30000,
    });
}

export function useUsers() {
    return useQuery({
        queryKey: ['users'],
        queryFn: async () => {
            const data = await fetchJson<unknown>('/users/');
            return validateUsers(data);
        },
    });
}

export interface ActiveReportersStats {
    count: number;
    period_days: number;
}

export interface NearbyReportersStats {
    count: number;
    radius_km: number;
    center: {
        latitude: number;
        longitude: number;
    };
}

export interface LocationDetails {
    location: {
        latitude: number;
        longitude: number;
        radius_meters: number;
    };
    total_reports: number;
    reports: Array<{
        id: string;
        description: string;
        latitude: number;
        longitude: number;
        verified: boolean;
        upvotes: number;
        timestamp: string;
        user_id: string;
    }>;
    reporters: Array<{
        id: string;
        username: string;
        reports_count: number;
        verified_reports_count: number;
        level: number;
    }>;
}

export function useActiveReporters() {
    return useQuery({
        queryKey: ['users', 'stats', 'active-reporters'],
        queryFn: () => fetchJson<ActiveReportersStats>('/users/stats/active-reporters'),
        refetchInterval: 600000, // Refresh every 10 minutes
    });
}

export function useNearbyReporters(latitude: number, longitude: number, radiusKm: number = 5.0) {
    return useQuery({
        queryKey: ['users', 'stats', 'nearby-reporters', latitude, longitude, radiusKm],
        queryFn: () => fetchJson<NearbyReportersStats>(
            `/users/stats/nearby-reporters?latitude=${latitude}&longitude=${longitude}&radius_km=${radiusKm}`
        ),
        refetchInterval: 600000, // Refresh every 10 minutes
        enabled: !!(latitude && longitude), // Only run if coordinates are provided
    });
}

export function useLocationDetails(latitude: number | null, longitude: number | null, radiusMeters: number = 500) {
    return useQuery({
        queryKey: ['reports', 'location', 'details', latitude, longitude, radiusMeters],
        queryFn: () => fetchJson<LocationDetails>(
            `/reports/location/details?latitude=${latitude}&longitude=${longitude}&radius_meters=${radiusMeters}`
        ),
        enabled: !!(latitude && longitude), // Only run if coordinates are provided
    });
}

// Alert types and hooks
export interface Alert {
    id: string;
    user_id: string;
    report_id: string;
    watch_area_id: string;
    message: string;
    is_read: boolean;
    created_at: string;
    report_latitude: number | null;
    report_longitude: number | null;
    watch_area_name: string | null;
}

export function useUserAlerts(userId: string | undefined, unreadOnly: boolean = false) {
    return useQuery({
        queryKey: ['alerts', 'user', userId, unreadOnly],
        queryFn: () => fetchJson<Alert[]>(`/alerts/user/${userId}?unread_only=${unreadOnly}`),
        enabled: !!userId,
        refetchInterval: 30000, // Check for new alerts every 30 seconds
    });
}

export function useUnreadAlertCount(userId: string | undefined) {
    return useQuery({
        queryKey: ['alerts', 'count', userId],
        queryFn: () => fetchJson<{ count: number }>(`/alerts/user/${userId}/count`),
        enabled: !!userId,
        refetchInterval: 30000,
    });
}

export function useMarkAlertRead() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ alertId, userId }: { alertId: string; userId: string }) => {
            return fetchJson(`/alerts/${alertId}/read?user_id=${userId}`, { method: 'POST' });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] });
        },
    });
}

export function useMarkAllAlertsRead() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (userId: string) => {
            return fetchJson(`/alerts/user/${userId}/read-all`, { method: 'POST' });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] });
        },
    });
}

export function useReportMutation() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (data: ReportCreate) => {
            const formData = new FormData();
            formData.append('user_id', data.user_id);
            formData.append('description', data.description);
            formData.append('latitude', data.latitude.toString());
            formData.append('longitude', data.longitude.toString());
            // Image is required by backend - throw error if missing
            if (!data.image) {
                throw new Error('Image is required for report submission');
            }
            formData.append('image', data.image);
            // Water depth and vehicle passability
            if (data.water_depth) {
                formData.append('water_depth', data.water_depth);
            }
            if (data.vehicle_passability) {
                formData.append('vehicle_passability', data.vehicle_passability);
            }
            // Photo GPS fields for verification
            if (data.photo_latitude !== undefined) {
                formData.append('photo_latitude', data.photo_latitude.toString());
            }
            if (data.photo_longitude !== undefined) {
                formData.append('photo_longitude', data.photo_longitude.toString());
            }
            if (data.photo_location_verified !== undefined) {
                formData.append('photo_location_verified', data.photo_location_verified.toString());
            }

            // Debug: Log what we're sending
            console.log('Submitting report with FormData:');
            for (const [key, value] of formData.entries()) {
                if (value instanceof File) {
                    console.log(`  ${key}: File(${value.name}, ${value.size} bytes, ${value.type})`);
                } else {
                    console.log(`  ${key}: ${value}`);
                }
            }

            return uploadFile('/reports/', formData);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['reports'] });
        },
    });
}

// ============================================================================
// ROUTING HOOKS (Safe route navigation)
// ============================================================================

export function useCalculateRoutes() {
    return useMutation({
        mutationFn: async (request: RouteCalculationRequest): Promise<RouteCalculationResponse> => {
            const response = await fetchJson<RouteCalculationResponse>('/routes/calculate', {
                method: 'POST',
                body: JSON.stringify(request),
            });
            return response;
        },
        retry: 1,
    });
}

export function useNearbyMetros(lat: number | null, lng: number | null, city: string = 'BLR', radius_km: number = 2.0) {
    return useQuery({
        queryKey: ['nearby-metros', lat, lng, city, radius_km],
        queryFn: async () => {
            if (!lat || !lng) return { metros: [], count: 0 };

            const response = await fetchJson<{ metros: MetroStation[]; count: number }>(
                `/routes/nearby-metros?lat=${lat}&lng=${lng}&city=${city}&radius_km=${radius_km}`
            );
            return response;
        },
        enabled: !!(lat && lng),
        staleTime: 5 * 60 * 1000, // 5 minutes - metro stations don't change often
        gcTime: 10 * 60 * 1000, // 10 minutes
    });
}

export function useWalkingRoute() {
    return useMutation({
        mutationFn: async (request: { origin: { lat: number; lng: number }; destination: { lat: number; lng: number } }): Promise<RouteOption> => {
            const response = await fetchJson<RouteOption>('/routes/walking-route', {
                method: 'POST',
                body: JSON.stringify(request),
            });
            return response;
        },
        retry: 1,
    });
}

// Deprecated: Use useCalculateRoutes instead
export function useRouteCalculation() {
    return useCalculateRoutes();
}

/**
 * Compare normal route vs FloodSafe route
 *
 * Returns both routes with comparison metrics including:
 * - Time penalty for taking the safe route
 * - Number of flood zones avoided
 * - Estimated stuck time if taking normal route
 * - Risk breakdown (reports, sensors, ML predictions)
 * - Recommendation message
 */
export function useCompareRoutes() {
    return useMutation({
        mutationFn: async (request: RouteComparisonRequest): Promise<RouteComparisonResponse> => {
            const response = await fetchJson<RouteComparisonResponse>('/routes/compare', {
                method: 'POST',
                body: JSON.stringify(request),
            });
            return response;
        },
        retry: 1,
    });
}

export function useGeocode(query: string, enabled: boolean = true, city?: string) {
    const CITY_COUNTRY_CODES: Record<string, string> = { yogyakarta: 'id', singapore: 'sg' };
    const countryCode = CITY_COUNTRY_CODES[city ?? ''] || 'in';
    return useQuery({
        queryKey: ['geocode', query, countryCode],
        queryFn: async (): Promise<GeocodingResult[]> => {
            if (!query || query.length < 3) {
                return [];
            }

            const response = await fetch(
                `https://nominatim.openstreetmap.org/search?` +
                `q=${encodeURIComponent(query)}&` +
                `format=json&` +
                `limit=5&` +
                `countrycodes=${countryCode}&` +
                `addressdetails=1`,
                {
                    headers: {
                        'User-Agent': 'FloodSafe-MVP/1.0'
                    }
                }
            );

            if (!response.ok) {
                throw new Error('Geocoding failed');
            }

            return response.json();
        },
        enabled: enabled && query.length >= 3,
        staleTime: 5 * 60 * 1000, // 5 minutes
        gcTime: 10 * 60 * 1000, // 10 minutes
    });
}

// ============================================================================
// UNIFIED SEARCH HOOKS
// ============================================================================

import type {
    UnifiedSearchResponse,
    TrendingSearchResponse,
    SearchLocationResult,
    SearchReportResult,
    SearchUserResult
} from '../../types';

export interface UnifiedSearchOptions {
    query: string;
    type?: 'all' | 'locations' | 'reports' | 'users';
    lat?: number;
    lng?: number;
    radius?: number;
    limit?: number;
    city?: string;
    enabled?: boolean;
}

/**
 * Unified search hook for locations, reports, and users
 * Uses backend /api/search/ endpoint with smart intent detection
 */
export function useUnifiedSearch(options: UnifiedSearchOptions) {
    const { query, type, lat, lng, radius = 5000, limit = 30, city, enabled = true } = options;

    return useQuery({
        queryKey: ['unified-search', query, type, lat, lng, radius, limit, city],
        queryFn: async (): Promise<UnifiedSearchResponse> => {
            const params = new URLSearchParams({
                q: query,
                limit: limit.toString()
            });

            // Only add city if explicitly provided
            if (city) params.append('city', city);
            if (type) params.append('type', type);
            if (lat !== undefined) params.append('lat', lat.toString());
            if (lng !== undefined) params.append('lng', lng.toString());
            if (radius) params.append('radius', radius.toString());

            const response = await fetchJson<UnifiedSearchResponse>(
                `/search/?${params.toString()}`
            );
            return response;
        },
        enabled: enabled && query.length >= 2,
        staleTime: 60 * 1000, // 1 minute — avoid refetching same query
        gcTime: 5 * 60 * 1000, // 5 minutes
        placeholderData: keepPreviousData, // Keep showing previous results while loading new ones
    });
}

/**
 * Get trending search terms and recent popular areas
 */
export function useTrendingSearches(limit: number = 5) {
    return useQuery({
        queryKey: ['trending-searches', limit],
        queryFn: async (): Promise<TrendingSearchResponse> => {
            const response = await fetchJson<TrendingSearchResponse>(
                `/search/suggestions/?limit=${limit}`
            );
            return response;
        },
        staleTime: 60 * 1000, // 1 minute
        gcTime: 5 * 60 * 1000, // 5 minutes
    });
}

/**
 * Search for locations only (optimized)
 * @param query - Search query
 * @param limit - Max results (default 5)
 * @param city - City to filter results ('delhi' | 'bangalore' | 'yogyakarta')
 * @param enabled - Whether to enable the query
 */
export function useLocationSearch(query: string, limit: number = 5, city?: string, enabled: boolean = true) {
    return useQuery({
        queryKey: ['location-search', query, limit, city],
        queryFn: async (): Promise<SearchLocationResult[]> => {
            const cityParam = city ? `&city=${city}` : '';
            const response = await fetchJson<SearchLocationResult[]>(
                `/search/locations/?q=${encodeURIComponent(query)}&limit=${limit}${cityParam}`
            );
            return response;
        },
        enabled: enabled && query.length >= 2,
        staleTime: 5 * 60 * 1000, // 5 minutes (locations don't change often)
        gcTime: 10 * 60 * 1000,
    });
}

/**
 * Search for reports by text (optimized)
 */
export function useReportSearch(
    query: string,
    options?: { lat?: number; lng?: number; radius?: number; limit?: number },
    enabled: boolean = true
) {
    const { lat, lng, radius = 5000, limit = 10 } = options || {};

    return useQuery({
        queryKey: ['report-search', query, lat, lng, radius, limit],
        queryFn: async (): Promise<SearchReportResult[]> => {
            const params = new URLSearchParams({
                q: query,
                limit: limit.toString()
            });

            if (lat !== undefined) params.append('lat', lat.toString());
            if (lng !== undefined) params.append('lng', lng.toString());
            if (radius) params.append('radius', radius.toString());

            const response = await fetchJson<SearchReportResult[]>(
                `/search/reports/?${params.toString()}`
            );
            return response;
        },
        enabled: enabled && query.length >= 2,
        staleTime: 30 * 1000, // 30 seconds (reports change frequently)
        gcTime: 5 * 60 * 1000,
    });
}

/**
 * Search for users by username (optimized)
 */
export function useUserSearch(query: string, limit: number = 10, enabled: boolean = true) {
    return useQuery({
        queryKey: ['user-search', query, limit],
        queryFn: async (): Promise<SearchUserResult[]> => {
            const response = await fetchJson<SearchUserResult[]>(
                `/search/users/?q=${encodeURIComponent(query)}&limit=${limit}`
            );
            return response;
        },
        enabled: enabled && query.length >= 2,
        staleTime: 60 * 1000, // 1 minute
        gcTime: 5 * 60 * 1000,
    });
}

// ============================================================================
// DAILY ROUTES HOOKS (User's regular commute routes for flood alerts)
// ============================================================================

/**
 * Get all daily routes for a user
 */
export function useDailyRoutes(userId: string | undefined) {
    return useQuery({
        queryKey: ['dailyRoutes', userId],
        queryFn: async (): Promise<DailyRoute[]> => {
            if (!userId) return [];
            const response = await fetchJson<DailyRoute[]>(`/daily-routes/user/${userId}`);
            return response;
        },
        enabled: !!userId,
        staleTime: 60 * 1000, // 1 minute (routes don't change often)
    });
}

/**
 * Create a new daily route for a user
 */
export function useCreateDailyRoute() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (route: DailyRouteCreate): Promise<DailyRoute> => {
            const response = await fetchJson<DailyRoute>('/daily-routes/', {
                method: 'POST',
                body: JSON.stringify(route),
            });
            return response;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['dailyRoutes'] });
        },
    });
}

/**
 * Update an existing daily route
 */
export function useUpdateDailyRoute() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ routeId, data }: { routeId: string; data: DailyRouteCreate }): Promise<DailyRoute> => {
            const response = await fetchJson<DailyRoute>(`/daily-routes/${routeId}`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            });
            return response;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['dailyRoutes'] });
        },
    });
}

/**
 * Delete a daily route
 */
export function useDeleteDailyRoute() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (routeId: string): Promise<void> => {
            await fetchJson(`/daily-routes/${routeId}`, {
                method: 'DELETE',
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['dailyRoutes'] });
        },
    });
}

// ============================================================================
// WATCH AREA HOOKS (for onboarding & alerts)
// ============================================================================

/**
 * Get all watch areas for a user
 */
export function useWatchAreas(userId: string | undefined) {
    return useQuery({
        queryKey: ['watchAreas', userId],
        queryFn: async (): Promise<WatchArea[]> => {
            if (!userId) return [];
            const response = await fetchJson<WatchArea[]>(`/watch-areas/user/${userId}`);
            return response;
        },
        enabled: !!userId,
        staleTime: 60 * 1000, // 1 minute
    });
}

/**
 * Create a new watch area
 */
export function useCreateWatchArea() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (watchArea: WatchAreaCreate): Promise<WatchArea> => {
            const response = await fetchJson<WatchArea>('/watch-areas/', {
                method: 'POST',
                body: JSON.stringify(watchArea),
            });
            return response;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['watchAreas'] });
        },
    });
}

/**
 * Delete a watch area
 */
export function useDeleteWatchArea() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (watchAreaId: string): Promise<void> => {
            await fetchJson(`/watch-areas/${watchAreaId}`, {
                method: 'DELETE',
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['watchAreas'] });
        },
    });
}

/**
 * Update user onboarding progress and profile information
 */
export function useUpdateUserOnboarding() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({
            userId,
            data
        }: {
            userId: string;
            data: {
                onboarding_step?: number;
                profile_complete?: boolean;
                username?: string;
                phone?: string;
                city_preference?: string;
                language?: string;
            }
        }): Promise<void> => {
            await fetchJson(`/users/${userId}`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['user'] });
        },
    });
}

// ============================================================================
// FLOOD PREDICTION HOOKS (ML Hotspot Visualization)
// ============================================================================

import type { PredictionGridResponse } from '../../types';

export interface PredictionGridOptions {
    /** Bounding box for the grid */
    bounds: {
        minLng: number;
        minLat: number;
        maxLng: number;
        maxLat: number;
    } | null;
    /** Grid resolution in km (default: 1.0) */
    resolutionKm?: number;
    /** Days ahead to predict (0 = today, default) */
    horizonDays?: number;
    /** Whether to enable the query */
    enabled?: boolean;
}

/**
 * Fetch flood prediction grid for heatmap visualization
 *
 * @param options - Grid options including bounds, resolution, and horizon
 * @returns GeoJSON FeatureCollection with flood probabilities at each grid point
 */
export function usePredictionGrid(options: PredictionGridOptions) {
    const {
        bounds,
        resolutionKm = 1.0,
        horizonDays = 0,
        enabled = true
    } = options;

    return useQuery({
        queryKey: ['prediction-grid', bounds, resolutionKm, horizonDays],
        queryFn: async (): Promise<PredictionGridResponse | null> => {
            if (!bounds) return null;

            const bbox = `${bounds.minLng},${bounds.minLat},${bounds.maxLng},${bounds.maxLat}`;
            const params = new URLSearchParams({
                bbox,
                resolution_km: resolutionKm.toString(),
                horizon_days: horizonDays.toString(),
            });

            const response = await fetchJson<PredictionGridResponse>(
                `/predictions/grid?${params.toString()}`
            );
            return response;
        },
        enabled: enabled && !!bounds,
        staleTime: 60 * 60 * 1000, // 1 hour - predictions don't change quickly
        gcTime: 2 * 60 * 60 * 1000, // 2 hours
        refetchOnWindowFocus: false, // Don't refetch on window focus
        retry: 2,
    });
}

/**
 * Check ML service health
 */
export function usePredictionHealth() {
    return useQuery({
        queryKey: ['prediction-health'],
        queryFn: async () => {
            const response = await fetchJson<{
                status: string;
                ml_service_enabled: boolean;
                ml_service_status?: string;
                model_status?: string;
            }>('/predictions/health');
            return response;
        },
        staleTime: 5 * 60 * 1000, // 5 minutes
        refetchOnWindowFocus: false,
    });
}

// ==================== HISTORICAL FLOODS ====================

import { getHistoricalFloods, HistoricalFloodsResponse } from './historical-floods';

/**
 * Fetch historical flood events for FloodAtlas.
 * Historical data from IFI-Impacts dataset (1967-2023).
 *
 * @param city - City code (default: 'delhi')
 * @returns GeoJSON FeatureCollection with historical flood events
 */
export function useHistoricalFloods(city: string = 'delhi') {
    return useQuery<HistoricalFloodsResponse, Error>({
        queryKey: ['historicalFloods', city],
        queryFn: () => getHistoricalFloods(city),
        staleTime: 1000 * 60 * 60 * 24, // 24 hours - historical data rarely changes
        gcTime: 1000 * 60 * 60 * 24 * 7, // 7 days cache
        // Enable for all cities - API returns "Coming soon" message for unsupported cities
        enabled: true,
    });
}

// ==================== SAVED ROUTES ====================

export interface SavedRoute {
    id: string;
    user_id: string;
    name: string;
    origin_latitude: number;
    origin_longitude: number;
    origin_name: string | null;
    destination_latitude: number;
    destination_longitude: number;
    destination_name: string | null;
    transport_mode: string;
    use_count: number;
    created_at: string;
    updated_at: string;
}

export interface SavedRouteCreate {
    user_id: string;
    name: string;
    origin_latitude: number;
    origin_longitude: number;
    origin_name?: string | null;
    destination_latitude: number;
    destination_longitude: number;
    destination_name?: string | null;
    transport_mode?: string;
}

/**
 * Get all saved routes for a user
 * Routes are ordered by use_count (most used first)
 */
export function useSavedRoutes(userId: string | undefined) {
    return useQuery({
        queryKey: ['saved-routes', userId],
        queryFn: async (): Promise<SavedRoute[]> => {
            if (!userId) return [];
            return fetchJson<SavedRoute[]>(`/saved-routes/user/${userId}`);
        },
        enabled: !!userId,
        staleTime: 60 * 1000, // 1 minute
        gcTime: 5 * 60 * 1000, // 5 minutes
    });
}

/**
 * Create a new saved route
 */
export function useCreateSavedRoute() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (route: SavedRouteCreate): Promise<SavedRoute> => {
            return fetchJson<SavedRoute>('/saved-routes/', {
                method: 'POST',
                body: JSON.stringify(route),
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['saved-routes'] });
        },
    });
}

/**
 * Delete a saved route
 */
export function useDeleteSavedRoute() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (routeId: string): Promise<void> => {
            await fetchJson(`/saved-routes/${routeId}`, {
                method: 'DELETE',
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['saved-routes'] });
        },
    });
}

/**
 * Increment the use count for a saved route
 * Call this when user loads a saved route for navigation
 */
export function useIncrementRouteUsage() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (routeId: string): Promise<SavedRoute> => {
            return fetchJson<SavedRoute>(`/saved-routes/${routeId}/increment`, {
                method: 'POST',
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['saved-routes'] });
        },
    });
}

// ============================================================================
// WATERLOGGING HOTSPOTS HOOKS (Delhi + Yogyakarta)
// ============================================================================

export interface HotspotFeature {
    type: 'Feature';
    geometry: {
        type: 'Point';
        coordinates: [number, number]; // [lng, lat]
    };
    properties: {
        id: number;
        name: string;
        zone: string;
        description?: string;
        risk_probability: number;
        risk_level: 'low' | 'moderate' | 'high' | 'extreme';
        risk_color: string;
        severity_history?: string;
        rainfall_24h_mm?: number;
        // FHI (Flood Hazard Index) - Live weather-based risk
        fhi_score?: number;         // 0.0-1.0 live hazard score
        fhi_level?: string;         // 'low' | 'moderate' | 'high' | 'extreme'
        fhi_color?: string;         // Hex color for FHI level
        elevation_m?: number;       // Elevation in meters
        // Source and verification status
        source?: 'mcd_reports' | 'osm_underpass' | 'user_report' | 'local_reports';  // Data source
        verified?: boolean;         // True for MCD-validated, False for ML-predicted
        osm_id?: number;            // OSM way/node ID for underpasses
    };
}

export interface HotspotsResponse {
    type: 'FeatureCollection';
    features: HotspotFeature[];
    metadata: {
        generated_at: string;
        total_hotspots: number;
        verified_count?: number;       // Count of MCD-validated hotspots
        unverified_count?: number;     // Count of ML-predicted hotspots
        composition?: {
            mcd_reports: number;
            osm_underpass: number;
        };
        current_rainfall_mm: number;
        model_available: boolean;
        risk_thresholds: {
            low: string;
            moderate: string;
            high: string;
            extreme: string;
        };
        // City-level XGBoost feature importance
        top_city_predictors?: Array<{
            feature: string;
            importance: number;
            label: string;
        }>;
    };
}

/**
 * Fetch all waterlogging hotspots for a city with current FHI risk levels
 *
 * Risk is dynamically calculated based on:
 * - Historical severity (always available)
 * - XGBoost model prediction (if trained)
 * - Current rainfall from CHIRPS (if available)
 *
 * @param options.includeRainfall - Whether to include current rainfall factor (default: false for faster loads)
 * @param options.enabled - Whether to enable the query (use to gate fetch for Delhi only)
 * @returns GeoJSON FeatureCollection with hotspot risk data
 */
export function useHotspots(options: {
    includeRainfall?: boolean;
    enabled?: boolean;
    city?: string;
} = {}) {
    const { includeRainfall = false, enabled = true, city } = options;
    return useQuery({
        queryKey: ['hotspots', city, includeRainfall],
        queryFn: async (): Promise<HotspotsResponse> => {
            const params = new URLSearchParams({
                include_rainfall: includeRainfall.toString(),
                ...(city ? { city } : {}),
            });
            const response = await fetchJson<HotspotsResponse>(
                `/hotspots/all?${params.toString()}`
            );
            return response;
        },
        staleTime: 30 * 60 * 1000, // 30 minutes - risk changes with rainfall
        gcTime: 60 * 60 * 1000, // 1 hour
        refetchOnWindowFocus: false,
        retry: 2,
        enabled, // Gate the fetch based on city
    });
}

/**
 * Check hotspots service health
 */
export function useHotspotsHealth() {
    return useQuery({
        queryKey: ['hotspots-health'],
        queryFn: async () => {
            const response = await fetchJson<{
                status: string;
                hotspots_loaded: boolean;
                total_hotspots: number;
                model_trained: boolean;
            }>('/hotspots/health');
            return response;
        },
        staleTime: 5 * 60 * 1000, // 5 minutes
        refetchOnWindowFocus: false,
    });
}

// ============================================================================
// UNIFIED ALERTS HOOKS (Enhanced Alerts Section)
// ============================================================================

import type { UnifiedAlertsResponse, AlertSourceFilter } from '../../types';

/**
 * Fetch unified alerts from all sources (IMD, News, Twitter, Community Reports)
 * Supports filtering by source type and city
 */
export function useUnifiedAlerts(city: string, sourceFilter: AlertSourceFilter = 'all') {
    return useQuery({
        queryKey: ['unified-alerts', city, sourceFilter],
        queryFn: () => fetchJson<UnifiedAlertsResponse>(
            `/alerts/unified?city=${city}&sources=${sourceFilter}`
        ),
        refetchInterval: 60000, // 1 minute
        staleTime: 30000, // 30 seconds
    });
}

/**
 * Trigger manual refresh of external alerts from APIs
 * Useful for pull-to-refresh functionality
 */
export function useRefreshExternalAlerts(city: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: () => fetchJson(`/external-alerts/refresh?city=${city}`, {
            method: 'POST'
        }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['unified-alerts', city] });
        },
    });
}

// ============================================================================
// ENHANCED SAFE ROUTE MAPPING HOOKS (3-Route Comparison + Live Navigation)
// ============================================================================

/**
 * Compare fastest, metro, and safest routes with FHI-based hotspot analysis
 * Enhanced version of useCompareRoutes with 3-way comparison
 */
export function useEnhancedCompareRoutes() {
    return useMutation({
        mutationFn: async (request: RouteComparisonRequest): Promise<EnhancedRouteComparisonResponse> => {
            return fetchJson<EnhancedRouteComparisonResponse>(
                '/routes/compare-enhanced',
                { method: 'POST', body: JSON.stringify(request) }
            );
        },
        retry: 1,
    });
}

/**
 * Recalculate route during live navigation
 * No retry for real-time navigation updates
 */
interface RecalculateRouteRequest {
    current_position: { lat: number; lng: number };
    destination: { lat: number; lng: number };
    route_type: 'fastest' | 'safest';
    city: string;
    mode?: string;
}

export function useRecalculateRoute() {
    return useMutation({
        mutationFn: async (request: RecalculateRouteRequest) => {
            return fetchJson<{ route: FastestRouteOption | SafestRouteOption; recalculated_at: string }>(
                '/routes/recalculate',
                { method: 'POST', body: JSON.stringify(request) }
            );
        },
        retry: 0, // No retry for live navigation
    });
}

/**
 * Fetch FHI-based risk assessment for all user's watch areas
 * Auto-refreshes every 5 minutes to keep risk levels current
 */
export function useWatchAreaRisks(userId: string | undefined) {
    return useQuery({
        queryKey: ['watch-area-risks', userId],
        queryFn: async (): Promise<WatchAreaRiskAssessment[]> => {
            if (!userId) return [];
            return fetchJson<WatchAreaRiskAssessment[]>(
                `/watch-areas/user/${userId}/risk-assessment`
            );
        },
        enabled: !!userId,
        refetchInterval: 5 * 60 * 1000, // 5 minutes
        staleTime: 2 * 60 * 1000, // 2 minutes
    });
}


// ============================================================================
// GAMIFICATION HOOKS
// ============================================================================

export interface BadgeInfo {
    key: string;
    name: string;
    description: string | null;
    icon: string;
    category: string;
    points_reward: number;
}

export interface EarnedBadge {
    badge: BadgeInfo;
    earned_at: string | null;
}

export interface BadgeProgress {
    badge: BadgeInfo;
    current_value: number;
    required_value: number;
    progress_percent: number;
}

export interface BadgesWithProgress {
    earned: EarnedBadge[];
    in_progress: BadgeProgress[];
}

export interface ReputationSummary {
    user_id: string;
    points: number;
    level: number;
    reputation_score: number;
    accuracy_rate: number;
    streak_days: number;
    next_level_points: number;
    badges_earned: number;
    total_badges: number;
}

export interface ReputationHistoryEntry {
    action: string;
    points_change: number;
    new_total: number;
    reason: string | null;
    created_at: string | null;
}

/**
 * Fetch current user's badges with progress on locked ones.
 * Requires authentication.
 */
export function useMyBadges() {
    return useQuery<BadgesWithProgress>({
        queryKey: ['gamification', 'badges', 'me'],
        queryFn: () => fetchJson('/gamification/me/badges'),
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}

/**
 * Fetch current user's reputation summary.
 * Requires authentication.
 */
export function useMyReputation() {
    return useQuery<ReputationSummary>({
        queryKey: ['gamification', 'reputation', 'me'],
        queryFn: () => fetchJson('/gamification/me/reputation'),
        staleTime: 5 * 60 * 1000,
    });
}

/**
 * Fetch current user's reputation history (point changes).
 * Requires authentication.
 */
export function useMyReputationHistory(limit = 20, offset = 0) {
    return useQuery<ReputationHistoryEntry[]>({
        queryKey: ['gamification', 'reputation', 'history', limit, offset],
        queryFn: () => fetchJson(`/gamification/me/reputation/history?limit=${limit}&offset=${offset}`),
        staleTime: 5 * 60 * 1000,
    });
}

/**
 * Fetch all available badges (public endpoint).
 * Useful for displaying badge catalog.
 */
export function useBadgesCatalog() {
    return useQuery<BadgeInfo[]>({
        queryKey: ['gamification', 'badges', 'catalog'],
        queryFn: () => fetchJson('/gamification/badges/catalog'),
        staleTime: 24 * 60 * 60 * 1000, // 24 hours - badges rarely change
    });
}

// ============================================================================
// LEADERBOARD HOOKS
// ============================================================================

export interface LeaderboardEntry {
    rank: number;
    display_name: string;
    profile_photo_url: string | null;
    points: number;
    level: number;
    reputation_score: number;
    verified_reports: number;
    badges_count: number;
    is_anonymous: boolean;
}

export interface LeaderboardResponse {
    leaderboard_type: string;
    updated_at: string;
    entries: LeaderboardEntry[];
    current_user_rank: number | null;
}

/**
 * Fetch leaderboard data with optional filtering by type.
 * Types: 'global' (all-time), 'weekly' (last 7 days), 'monthly' (last 30 days)
 * Pass userId to get current user's rank even if not in top N.
 */
export function useLeaderboard(
    type: 'global' | 'weekly' | 'monthly' = 'global',
    limit = 10,
    userId?: string
) {
    return useQuery<LeaderboardResponse>({
        queryKey: ['leaderboard', type, limit, userId],
        queryFn: () => {
            const params = new URLSearchParams({ type, limit: String(limit) });
            if (userId) params.append('user_id', userId);
            return fetchJson(`/leaderboards/?${params}`);
        },
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}

// ============================================================================
// COMMUNITY FEEDBACK HOOKS (Voting and Comments)
// ============================================================================

export interface VoteResponse {
    message: string;
    report_id: string;
    upvotes: number;
    downvotes: number;
    user_vote: 'upvote' | 'downvote' | null;
}

export interface Comment {
    id: string;
    report_id: string;
    user_id: string;
    username: string;
    content: string;
    created_at: string;
    comment_type?: string;  // "community"|"admin_verification"|"admin_rejection"
}

/**
 * Upvote a report (requires authentication).
 * Toggle behavior: upvote again to remove vote.
 * Switching from downvote changes vote type.
 */
export function useUpvoteReport() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (reportId: string): Promise<VoteResponse> => {
            return fetchJson(`/reports/${reportId}/upvote`, { method: 'POST' });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['reports'] });
        },
    });
}

/**
 * Downvote a report (requires authentication).
 * Toggle behavior: downvote again to remove vote.
 * Switching from upvote changes vote type.
 */
export function useDownvoteReport() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (reportId: string): Promise<VoteResponse> => {
            return fetchJson(`/reports/${reportId}/downvote`, { method: 'POST' });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['reports'] });
        },
    });
}

/**
 * Get comments for a specific report.
 * Returns comments ordered by creation time (oldest first).
 */
export function useComments(reportId: string | undefined) {
    return useQuery({
        queryKey: ['comments', reportId],
        queryFn: async (): Promise<Comment[]> => {
            if (!reportId) return [];
            return fetchJson(`/reports/${reportId}/comments`);
        },
        enabled: !!reportId,
        staleTime: 30 * 1000, // 30 seconds - comments update frequently
    });
}

/**
 * Get comment count for a report (lightweight endpoint).
 */
export function useCommentCount(reportId: string | undefined) {
    return useQuery({
        queryKey: ['comments', 'count', reportId],
        queryFn: async (): Promise<{ report_id: string; count: number }> => {
            if (!reportId) return { report_id: '', count: 0 };
            return fetchJson(`/reports/${reportId}/comments/count`);
        },
        enabled: !!reportId,
        staleTime: 60 * 1000, // 1 minute
    });
}

/**
 * Add a comment to a report (requires authentication).
 * Max 500 characters per comment.
 * Rate limited to 5 comments per minute.
 */
export function useAddComment() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ reportId, content }: { reportId: string; content: string }): Promise<Comment> => {
            return fetchJson(`/reports/${reportId}/comments`, {
                method: 'POST',
                body: JSON.stringify({ content }),
            });
        },
        onSuccess: (_, { reportId }) => {
            queryClient.invalidateQueries({ queryKey: ['comments', reportId] });
            queryClient.invalidateQueries({ queryKey: ['comments', 'count', reportId] });
            queryClient.invalidateQueries({ queryKey: ['reports'] });
        },
    });
}

/**
 * Delete a comment (requires authentication).
 * Only the comment author or admin can delete.
 */
export function useDeleteComment() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ commentId, reportId: _reportId }: { commentId: string; reportId: string }): Promise<void> => {
            await fetchJson(`/comments/${commentId}`, { method: 'DELETE' });
        },
        onSuccess: (_, { reportId }) => {
            queryClient.invalidateQueries({ queryKey: ['comments', reportId] });
            queryClient.invalidateQueries({ queryKey: ['comments', 'count', reportId] });
            queryClient.invalidateQueries({ queryKey: ['reports'] });
        },
    });
}

// ============================================================================
// FLOOD IMAGE CLASSIFICATION HOOKS (ML-based photo verification)
// ============================================================================

import type { FloodClassificationResult } from '../../types';

/**
 * Classify a flood image using the ML service (MobileNet classifier).
 *
 * Uses low threshold (0.3) to minimize false negatives - safety first.
 * If there's ANY reasonable chance the photo shows flooding, it's classified as flood.
 *
 * Call this when user captures/uploads a photo to provide immediate feedback.
 * This is a NON-BLOCKING enhancement - report submission works even if this fails.
 *
 * Proxies through backend to work in both local dev and Docker environments.
 *
 * @returns FloodClassificationResult with classification, confidence, and review flags
 */
export function useClassifyFloodImage() {
    return useMutation({
        mutationFn: async (file: File): Promise<FloodClassificationResult> => {
            const formData = new FormData();
            formData.append('image', file);

            // Create AbortController for explicit timeout
            // 45s is generous for mobile networks - ML classification can take 15-30s
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                controller.abort();
            }, 45000);

            try {
                // Use backend proxy instead of direct ML service call
                // This works in both local dev (localhost:8000) and Docker (backend service)
                const url = `${API_BASE_URL}/ml/classify-flood`;

                const response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal,
                    cache: 'no-store', // Bypass service worker cache
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Classification failed: ${errorText}`);
                }

                const result = await response.json();
                return result;
            } catch (error) {
                clearTimeout(timeoutId);

                // Provide clear error message for timeout
                if (error instanceof Error && error.name === 'AbortError') {
                    throw new Error('Classification timeout: slow network connection');
                }
                throw error;
            }
        },
        retry: 0, // Don't retry - this is a real-time UX enhancement, not critical
    });
}

// ============================================================================
// EMAIL VERIFICATION HOOKS
// ============================================================================

export interface VerificationStatus {
    email_verified: boolean;
    phone_verified: boolean;
    auth_provider: string;
}

/**
 * Get current verification status for the authenticated user.
 * Used by frontend to poll for verification completion after user clicks email link.
 *
 * @param options.enabled - Set to false to disable polling (e.g., when already verified)
 * @param options.pollInterval - Polling interval in ms (default: 5000 = 5 seconds)
 */
export function useVerificationStatus(options: {
    enabled?: boolean;
    pollInterval?: number;
} = {}) {
    const { enabled = true, pollInterval = 5000 } = options;

    return useQuery({
        queryKey: ['verification-status'],
        queryFn: () => fetchJson<VerificationStatus>('/auth/verification-status'),
        enabled,
        refetchInterval: enabled ? pollInterval : false,
        staleTime: 0, // Always consider stale to ensure fresh data when polling
    });
}

/**
 * Resend verification email to the current user.
 * Rate limited to 3 emails per hour on the backend.
 *
 * Call this when user clicks "Resend verification email" button.
 * The mutation will throw an error if rate limited (429 status).
 */
export function useResendVerificationEmail() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (): Promise<{ message: string }> => {
            return fetchJson('/auth/resend-verification', { method: 'POST' });
        },
        onSuccess: () => {
            // Invalidate verification status to trigger re-fetch
            queryClient.invalidateQueries({ queryKey: ['verification-status'] });
        },
    });
}

// ============================================================================
// GOOGLE FLOODHUB HOOKS (Flood Forecasting for supported cities)
// ============================================================================

/**
 * Get overall FloodHub status for a city.
 *
 * Returns enabled status and severity data.
 * - For Delhi: Returns current flood status from Google FloodHub API
 * - For other cities: Returns "Coming soon" message
 * - When API key not configured: Returns "Not configured" message
 *
 * NO SILENT FALLBACKS - errors are surfaced to frontend.
 *
 * @param city - City code (use 'DEL' for Delhi)
 */
export function useFloodHubStatus(city: string) {
    return useQuery({
        queryKey: ['floodhub-status', city],
        queryFn: async (): Promise<FloodHubStatus> => {
            const cityCode = getCityCode(city);
            return fetchJson<FloodHubStatus>(`/floodhub/status?city=${cityCode}`);
        },
        staleTime: 5 * 60 * 1000, // 5 minutes
        gcTime: 10 * 60 * 1000, // 10 minutes
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

/**
 * Get gauges with current flood status for a city.
 *
 * Returns empty array if FloodHub is disabled (no API key).
 * Throws error (502) if API request fails - NO SILENT FALLBACK.
 *
 * Each gauge includes:
 * - Location (lat/lng)
 * - Current severity level (EXTREME, SEVERE, ABOVE_NORMAL, NO_FLOODING)
 * - Last update time
 *
 * @param city - City key (delhi, bangalore, yogyakarta)
 */
export function useFloodHubGauges(city: string = 'delhi') {
    const cityCode = getCityCode(city);
    return useQuery({
        queryKey: ['floodhub-gauges', city],
        queryFn: async (): Promise<FloodHubGauge[]> => {
            return fetchJson<FloodHubGauge[]>(`/floodhub/gauges?city=${cityCode}`);
        },
        staleTime: 10 * 60 * 1000, // 10 minutes (matches backend cache TTL)
        gcTime: 20 * 60 * 1000, // 20 minutes
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

/**
 * Get 7-day forecast for a specific gauge.
 *
 * Returns forecast time series with water levels and threshold markers.
 * Use this when user selects a gauge to view detailed forecast chart.
 *
 * NO SILENT FALLBACK - returns 404 if forecast unavailable, 502 on API error.
 *
 * @param gaugeId - Gauge ID from useFloodHubGauges result (null to disable)
 */
export function useFloodHubForecast(gaugeId: string | null) {
    return useQuery({
        queryKey: ['floodhub-forecast', gaugeId],
        queryFn: async (): Promise<FloodHubForecast | null> => {
            if (!gaugeId) return null;
            return fetchJson<FloodHubForecast>(`/floodhub/forecast/${gaugeId}`);
        },
        enabled: !!gaugeId,
        staleTime: 15 * 60 * 1000, // 15 minutes (forecasts update less frequently)
        gcTime: 30 * 60 * 1000, // 30 minutes
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

/**
 * Get significant flood events for a city's country.
 * Empty during non-flood periods — this is normal.
 *
 * @param city - City key (delhi, bangalore, yogyakarta)
 */
export function useFloodHubEvents(city: string = 'delhi') {
    const cityCode = getCityCode(city);
    return useQuery({
        queryKey: ['floodhub-events', city],
        queryFn: async (): Promise<FloodHubSignificantEvent[]> => {
            return fetchJson<FloodHubSignificantEvent[]>(`/floodhub/events?city=${cityCode}`);
        },
        staleTime: 15 * 60 * 1000, // 15 minutes
        gcTime: 30 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

/**
 * Get inundation polygon as GeoJSON for MapLibre rendering.
 * @param polygonId - Polygon ID from gauge's inundation_map_set (null to disable)
 */
export function useFloodHubInundation(polygonId: string | null) {
    return useQuery({
        queryKey: ['floodhub-inundation', polygonId],
        queryFn: async () => {
            if (!polygonId) return null;
            return fetchJson<GeoJSON.FeatureCollection>(`/floodhub/inundation/${polygonId}`);
        },
        enabled: !!polygonId,
        staleTime: 30 * 60 * 1000, // 30 minutes (polygons change slowly)
        gcTime: 60 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

// ============================================================================
// SAFETY CIRCLES HOOKS (Family & Community Group Notifications)
// ============================================================================

/** Fetch all circles the current user belongs to. */
export function useMyCircles() {
    return useQuery({
        queryKey: ['circles'],
        queryFn: () => fetchJson<SafetyCircle[]>('/circles/'),
        staleTime: 60 * 1000,
        gcTime: 5 * 60 * 1000,
    });
}

/** Fetch circle detail with members list. */
export function useCircleDetail(circleId: string | null) {
    return useQuery({
        queryKey: ['circles', circleId],
        queryFn: () => fetchJson<SafetyCircleDetail>(`/circles/${circleId}`),
        enabled: !!circleId,
        staleTime: 30 * 1000,
        gcTime: 5 * 60 * 1000,
    });
}

/** Fetch circle alerts across all user's circles. */
export function useCircleAlerts(limit: number = 50, offset: number = 0) {
    return useQuery({
        queryKey: ['circle-alerts', limit, offset],
        queryFn: () => fetchJson<CircleAlertsResponse>(
            `/circles/alerts?limit=${limit}&offset=${offset}`
        ),
        staleTime: 30 * 1000,
        gcTime: 5 * 60 * 1000,
        refetchInterval: 60 * 1000,
    });
}

/** Fetch unread circle alert count (for badge display). */
export function useUnreadCircleAlertCount() {
    return useQuery({
        queryKey: ['circle-alerts-unread'],
        queryFn: () => fetchJson<CircleUnreadCount>('/circles/alerts/unread-count'),
        staleTime: 30 * 1000,
        refetchInterval: 60 * 1000,
    });
}

/** Create a new safety circle. */
export function useCreateCircle() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: SafetyCircleCreate) =>
            fetchJson<SafetyCircle>('/circles/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles'] });
        },
    });
}

/** Join a circle via invite code. */
export function useJoinCircle() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: JoinCircleRequest) =>
            fetchJson<SafetyCircle>('/circles/join', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles'] });
        },
    });
}

/** Add a member to a circle. */
export function useAddCircleMember(circleId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: CircleMemberAdd) =>
            fetchJson(`/circles/${circleId}/members`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles', circleId] });
        },
    });
}

/** Bulk add members to a circle. */
export function useBulkAddCircleMembers(circleId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (members: CircleMemberAdd[]) =>
            fetchJson<BulkAddResult>(`/circles/${circleId}/members/bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(members),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles', circleId] });
        },
    });
}

/** Remove a member from a circle. */
export function useRemoveCircleMember(circleId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (memberId: string) =>
            fetchJson(`/circles/${circleId}/members/${memberId}`, {
                method: 'DELETE',
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles', circleId] });
        },
    });
}

/** Update a member's settings (role, mute, notification prefs). */
export function useUpdateCircleMember(circleId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ memberId, data }: { memberId: string; data: CircleMemberUpdate }) =>
            fetchJson(`/circles/${circleId}/members/${memberId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles', circleId] });
        },
    });
}

/** Leave a circle. */
export function useLeaveCircle() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (circleId: string) =>
            fetchJson(`/circles/${circleId}/leave`, { method: 'POST' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles'] });
        },
    });
}

/** Delete a circle (creator only). */
export function useDeleteCircle() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (circleId: string) =>
            fetchJson(`/circles/${circleId}`, { method: 'DELETE' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles'] });
        },
    });
}

/** Mark a single circle alert as read. */
export function useMarkCircleAlertRead() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (alertId: string) =>
            fetchJson(`/circles/alerts/${alertId}/read`, { method: 'PATCH' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circle-alerts'] });
            queryClient.invalidateQueries({ queryKey: ['circle-alerts-unread'] });
        },
    });
}

/** Mark all circle alerts as read. */
export function useMarkAllCircleAlertsRead() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: () =>
            fetchJson('/circles/alerts/read-all', { method: 'PATCH' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circle-alerts'] });
            queryClient.invalidateQueries({ queryKey: ['circle-alerts-unread'] });
        },
    });
}

/** Update circle name/description (admin+). */
export function useUpdateCircle(circleId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: SafetyCircleUpdate) =>
            fetchJson(`/circles/${circleId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circles'] });
            queryClient.invalidateQueries({ queryKey: ['circles', circleId] });
        },
    });
}

// ============================================================================
// AI RISK SUMMARY HOOKS (Llama/Groq AI-generated risk narratives)
// ============================================================================

/**
 * Fetch AI-generated risk summary for a specific location.
 *
 * Uses the Groq-hosted Llama 3.1 model to generate natural language
 * risk narratives based on FHI score and weather conditions.
 *
 * Each watch area/route calls this independently for parallel fetching.
 * Backend caches for 1 hour; frontend staleTime is 10 minutes.
 *
 * @param lat - Latitude (null to disable)
 * @param lng - Longitude (null to disable)
 * @param language - 'en' or 'hi' (default: 'en')
 */
export function useRiskSummary(lat: number | null, lng: number | null, language = 'en', name?: string) {
    return useQuery({
        queryKey: ['risk-summary', lat, lng, language, name],
        queryFn: () => {
            const params = new URLSearchParams({
                lat: String(lat),
                lng: String(lng),
                language,
            });
            if (name) params.set('name', name);
            return fetchJson<RiskSummaryResponse>(`/hotspots/risk-summary?${params}`);
        },
        enabled: lat !== null && lng !== null,
        staleTime: 10 * 60 * 1000,     // 10 min (backend caches 1 hour)
        gcTime: 30 * 60 * 1000,         // 30 min garbage collection
        refetchOnWindowFocus: false,
        retry: 1,
    });
}


// ─── Singapore NEA Weather ────────────────────────────────────────────────────

export interface SGConditions {
    temperature_c: number | null;
    humidity_pct: number | null;
    temp_station_name: string | null;
    humidity_station_name: string | null;
    timestamp: string;
    data_source: string;
}

export interface SGForecastArea {
    name: string;
    condition: string;
    flash_flood_risk: boolean;
    lat: number;
    lng: number;
}

export interface SGForecast {
    valid_period: { start: string; end: string };
    areas: SGForecastArea[];
    high_risk_areas: string[];
    update_timestamp: string;
    data_source: string;
}

/**
 * Current temperature and humidity from nearest NEA station.
 * Singapore-only — returns null/disabled for other cities.
 */
export function useSGConditions(lat: number | null, lng: number | null, enabled = true) {
    return useQuery({
        queryKey: ['sg-conditions', lat, lng],
        queryFn: () => fetchJson<SGConditions>(
            `/rainfall/sg-conditions?lat=${lat}&lng=${lng}`
        ),
        enabled: enabled && lat !== null && lng !== null,
        staleTime: 5 * 60 * 1000,      // 5 min (matches NEA refresh)
        gcTime: 15 * 60 * 1000,         // 15 min garbage collection
        refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 min
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

/**
 * NEA 2-hour weather forecast with flash flood risk flags.
 * Singapore-only — no coordinates needed (covers all SG areas).
 */
export function useSGWeatherForecast(enabled = true) {
    return useQuery({
        queryKey: ['sg-forecast'],
        queryFn: () => fetchJson<SGForecast>('/rainfall/sg-forecast'),
        enabled,
        staleTime: 15 * 60 * 1000,      // 15 min (forecast updates every 30 min)
        gcTime: 30 * 60 * 1000,          // 30 min garbage collection
        refetchInterval: 15 * 60 * 1000, // Auto-refresh every 15 min
        refetchOnWindowFocus: false,
        retry: 1,
    });
}


// ─── Yogyakarta BMKG Weather ──────────────────────────────────────────────────

export interface YKConditions {
    temperature_c: number;
    humidity_pct: number;
    weather_desc: string;        // English
    weather_desc_id: string;     // Indonesian
    wind_speed_kmh: number;
    cloud_cover_pct: number;
    location_name: string;
    timestamp: string;
    data_source: string;
}

export interface YKForecastEntry {
    datetime_local: string;
    datetime_utc: string;
    temperature_c: number;
    humidity_pct: number;
    weather_desc: string;
    weather_desc_id: string;
    wind_speed_kmh: number;
    cloud_cover_pct: number;
    flash_flood_risk: boolean;
}

export interface YKForecast {
    location_name: string;
    province: string;
    lat: number;
    lng: number;
    entries: YKForecastEntry[];
    high_risk_entries: Array<{
        datetime_local: string;
        weather_desc: string;
        weather_desc_id: string;
    }>;
    data_source: string;
}

/**
 * Current temperature, humidity, and weather from nearest BMKG forecast district.
 * Yogyakarta-only — returns null/disabled for other cities.
 */
export function useYKConditions(lat: number | null, lng: number | null, enabled = true) {
    return useQuery({
        queryKey: ['yk-conditions', lat, lng],
        queryFn: () => fetchJson<YKConditions>(
            `/rainfall/yk-conditions?lat=${lat}&lng=${lng}`
        ),
        enabled: enabled && lat !== null && lng !== null,
        staleTime: 30 * 60 * 1000,      // 30 min (BMKG updates twice daily)
        gcTime: 60 * 60 * 1000,          // 1 hr garbage collection
        refetchInterval: 30 * 60 * 1000, // Auto-refresh every 30 min
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

/**
 * BMKG 3-day weather forecast with flash flood risk flags.
 * Yogyakarta-only — no coordinates needed (covers Yogyakarta city).
 */
export function useYKForecast(enabled = true) {
    return useQuery({
        queryKey: ['yk-forecast'],
        queryFn: () => fetchJson<YKForecast>('/rainfall/yk-forecast'),
        enabled,
        staleTime: 30 * 60 * 1000,      // 30 min
        gcTime: 60 * 60 * 1000,          // 1 hr garbage collection
        refetchInterval: 30 * 60 * 1000, // Auto-refresh every 30 min
        refetchOnWindowFocus: false,
        retry: 1,
    });
}

// ─── Community Intelligence Hooks ───────────────

export function useGroundsourceClusters(city: string) {
  return useQuery({
    queryKey: ['groundsource-clusters', city],
    queryFn: () => fetchJson<GroundsourceCluster[]>(
      `/historical-floods/groundsource/clusters?city=${city}`
    ),
    staleTime: 5 * 60 * 1000,
    enabled: !!city,
  });
}

export function useGroundsourceStats(city: string) {
  return useQuery({
    queryKey: ['groundsource-stats', city],
    queryFn: () => fetchJson<HistoricalStats>(
      `/historical-floods/groundsource/stats?city=${city}`
    ),
    staleTime: 10 * 60 * 1000,
    enabled: !!city,
  });
}

export function useNearbyEpisodes(lat: number, lng: number, radiusKm = 2) {
  return useQuery({
    queryKey: ['nearby-episodes', lat, lng, radiusKm],
    queryFn: () => fetchJson<GroundsourceEpisode[]>(
      `/historical-floods/groundsource/nearby?lat=${lat}&lng=${lng}&radius_km=${radiusKm}`
    ),
    staleTime: 5 * 60 * 1000,
    enabled: !!lat && !!lng,
  });
}

export function useMyPins() {
  return useQuery({
    queryKey: ['my-pins'],
    queryFn: () => fetchJson<PersonalPin[]>('/watch-areas/my-pins'),
    staleTime: 30 * 1000,
  });
}

export function useCreatePin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pin: { latitude: number; longitude: number; name: string; city: string; visibility?: string; alert_radius_label?: string }) =>
      fetchJson<PersonalPin>('/watch-areas/pin', { method: 'POST', body: JSON.stringify(pin) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-pins'] });
    },
  });
}

export function usePinFhiHistory(pinId: string) {
  return useQuery({
    queryKey: ['pin-fhi-history', pinId],
    queryFn: () => fetchJson<FhiHistoryEntry[]>(`/watch-areas/${pinId}/fhi-history`),
    enabled: !!pinId,
  });
}

export function useAiChat() {
  return useMutation({
    mutationFn: (params: { message: string; city: string; conversation_id?: string; latitude?: number; longitude?: number }) =>
      fetchJson<ChatResponse>('/ai/chat', { method: 'POST', body: JSON.stringify(params) }),
  });
}

export function useAddressRisk() {
  return useMutation({
    mutationFn: (params: { address: string; city: string }) =>
      fetchJson<AddressRiskResult>(`/ai/address-risk?address=${encodeURIComponent(params.address)}&city=${params.city}`),
  });
}

export function useAlertSummary(alertId: string) {
  return useQuery({
    queryKey: ['alert-summary', alertId],
    queryFn: () => fetchJson<{ alert_id: string; summary: string }>(`/ai/alert-summary/${alertId}`),
    staleTime: 60 * 60 * 1000,
    enabled: !!alertId,
  });
}
