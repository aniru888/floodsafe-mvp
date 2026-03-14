import type { LineString } from 'geojson';

export type AlertLevel = 'safe' | 'watch' | 'advisory' | 'warning' | 'emergency';
export type AlertColor = 'green' | 'yellow' | 'orange' | 'red' | 'black';

export interface FloodAlert {
    id: string;
    level: 'critical' | 'warning' | 'watch' | 'safe';
    location: string;
    description: string;
    timeUntil: string;
    confidence: number;
    isActive: boolean;
    color: 'red' | 'orange' | 'yellow' | 'green';
    coordinates: [number, number];
    timestamp?: string; // Sensor last_ping timestamp
}

export type WaterDepth = 'ankle' | 'knee' | 'waist' | 'impassable';
export type VehiclePassability = 'all' | 'high-clearance' | 'none';

// ============================================================================
// ROUTING TYPES (Safe route navigation)
// ============================================================================

export interface LocationPoint {
    lng: number;
    lat: number;
}

export type TransportMode = 'driving' | 'walking' | 'metro' | 'combined';
export type RouteType = 'safe' | 'fast' | 'balanced' | 'metro';
export type RiskLevel = 'low' | 'medium' | 'high';

export interface RouteRequest {
    origin: LocationPoint;
    destination: LocationPoint;
    city: 'BLR' | 'DEL' | 'YGY' | 'SIN' | 'IDR';
    mode: TransportMode;
    avoid_risk_levels?: string[];
}

export interface RouteInstruction {
    text: string;
    distance_meters: number;
    duration_seconds?: number;
    maneuver: string;
    location: [number, number]; // [lng, lat]
}

export interface RouteOption {
    id: string;
    type: RouteType;
    city_code: string;
    geometry: LineString;
    distance_meters: number;
    duration_seconds?: number;
    safety_score: number; // 0-100
    risk_level: RiskLevel;
    flood_intersections: number;
    instructions?: RouteInstruction[];
}

export interface RouteResponse {
    routes: RouteOption[];
    city: string;
    warnings: string[];
}

export interface MetroStation {
    id: string;
    name: string;
    line: string;
    color: string;
    lat: number;
    lng: number;
    distance_meters: number;
    walking_minutes: number;
}

export interface RouteCalculationRequest {
    origin: { lat: number; lng: number };
    destination: { lat: number; lng: number };
    mode: 'driving' | 'walking' | 'cycling' | 'metro' | 'combined';
    city: string;
    avoid_ml_risk?: boolean;
}

export interface RouteCalculationResponse {
    routes: RouteOption[];
    flood_zones: GeoJSON.FeatureCollection;
}

// User type - used across the application
export interface User {
    id: string;
    username: string;
    email?: string;  // Optional for phone-auth users
    phone?: string;
    profile_photo_url?: string;
    role: string;
    created_at?: string;  // Optional since auth endpoint may not return it
    points: number;
    level: number;
    reports_count?: number;  // Optional since auth endpoint may not return it
    verified_reports_count?: number;  // Optional since auth endpoint may not return it
    badges?: string[];
    reputation_score?: number;  // Added for auth users
    // Profile-specific optional fields
    language?: string;
    notification_push?: boolean;
    notification_sms?: boolean;
    notification_whatsapp?: boolean;
    notification_email?: boolean;
    alert_preferences?: {
        watch: boolean;
        advisory: boolean;
        warning: boolean;
        emergency: boolean;
    };
    // Onboarding & City Preference
    city_preference?: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore';
    profile_complete?: boolean;
    onboarding_step?: number;  // 1-5, tracks current step if incomplete
    // Privacy settings
    leaderboard_visible?: boolean;
    profile_public?: boolean;
    display_name?: string | null;
}

// Daily Route types for user's regular commute routes
export interface DailyRoute {
    id: string;
    user_id: string;
    name: string;
    origin_latitude: number;
    origin_longitude: number;
    destination_latitude: number;
    destination_longitude: number;
    transport_mode: 'driving' | 'walking' | 'metro' | 'combined';
    notify_on_flood: boolean;
    created_at: string;
}

export interface DailyRouteCreate {
    user_id: string;
    name: string;
    origin_latitude: number;
    origin_longitude: number;
    destination_latitude: number;
    destination_longitude: number;
    transport_mode?: 'driving' | 'walking' | 'metro' | 'combined';
    notify_on_flood?: boolean;
}

// Location-related types for MapPicker
export interface LocationCoordinates {
    latitude: number;
    longitude: number;
}

export interface LocationData extends LocationCoordinates {
    accuracy: number;
}

export interface LocationWithAddress extends LocationData {
    locationName: string;
}

// Map Picker types
export interface MapPickerProps {
    isOpen: boolean;
    onClose: () => void;
    initialLocation: LocationData | null;
    onLocationSelect: (location: LocationWithAddress) => void;
}

export interface GeocodingResult {
    display_name: string;
    lat: string;
    lon: string;
    address?: {
        road?: string;
        neighbourhood?: string;
        suburb?: string;
        city?: string;
        town?: string;
        village?: string;
        state?: string;
        country?: string;
    };
}

// ============================================================================
// UNIFIED SEARCH TYPES
// ============================================================================

export type SearchIntent = 'location' | 'report' | 'user' | 'mixed' | 'empty';

export interface SearchLocationResult {
    type: 'location';
    display_name: string;
    lat: number;
    lng: number;
    address: Record<string, string>;
    importance: number;
    formatted_name: string;
}

export interface SearchReportResult {
    type: 'report';
    id: string;
    description: string;
    lat: number | null;
    lng: number | null;
    water_depth: string | null;
    vehicle_passability: string | null;
    verified: boolean;
    timestamp: string | null;
    media_url: string | null;
    highlight: string;
}

export interface SearchUserResult {
    type: 'user';
    id: string;
    username: string;
    display_name: string | null;
    points: number;
    level: number;
    reports_count: number;
    profile_photo_url: string | null;
}

export interface SearchSuggestion {
    type: 'tip' | 'action' | 'popular';
    text: string;
    options?: string[];
    action?: string;
    data?: SearchLocationResult;
}

export interface UnifiedSearchResponse {
    query: string;
    intent: SearchIntent;
    locations: SearchLocationResult[];
    reports: SearchReportResult[];
    users: SearchUserResult[];
    suggestions: SearchSuggestion[];
}

export interface TrendingSearchResponse {
    trending: string[];
    recent_areas: string[];
}

// Photo capture types for geotagged report photos
export interface PhotoGps {
    lat: number;
    lng: number;
}

// ML Flood Image Classification result (from YOLOv8 classifier)
export interface FloodClassificationResult {
    classification: 'flood' | 'no_flood';
    confidence: number;  // 0.0-1.0
    flood_probability: number;  // 0.0-1.0
    is_flood: boolean;  // True if flood_probability >= threshold (0.3)
    needs_review: boolean;  // True if probability in uncertain range (0.3-0.7)
    verification_score: number;  // 0-100 score for report quality
    probabilities: {
        flood: number;
        no_flood: number;
    };
}

export interface PhotoData {
    file: File;
    gps: PhotoGps;
    source: 'camera' | 'gallery';
    isLocationVerified: boolean; // true if within 100m of reported location
    previewUrl: string;
    // ML classification results (optional - may not be available)
    mlClassification?: FloodClassificationResult | null;
    mlValidating?: boolean;  // True while ML classification is in progress
    mlFailed?: boolean;  // True if ML classification failed (service unavailable)
}

export interface PhotoCaptureProps {
    reportedLocation: LocationData | null;
    onPhotoCapture: (photo: PhotoData | null) => void;
    photo: PhotoData | null;
}

// ============================================================================
// WATCH AREA TYPES (for onboarding & alerts)
// ============================================================================

export interface WatchArea {
    id: string;
    user_id: string;
    name: string;
    latitude: number;
    longitude: number;
    radius: number;
    created_at: string;
}

export interface WatchAreaCreate {
    user_id: string;
    name: string;
    latitude: number;
    longitude: number;
    radius?: number;  // defaults to 1000m
}

// ============================================================================
// ONBOARDING TYPES
// ============================================================================

// Onboarding form state (local, not persisted)
export interface OnboardingFormState {
    currentStep: number;  // 1-5

    // Step 1: City
    city: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore' | null;

    // Step 2: Profile
    username: string;
    phone: string;

    // Step 3: Watch Areas (accumulated)
    watchAreas: WatchAreaCreate[];

    // Step 4: Daily Routes (accumulated)
    dailyRoutes: DailyRouteCreate[];

    // Validation
    errors: Record<string, string>;
    isSubmitting: boolean;
}

export type OnboardingAction =
    | { type: 'SET_CITY'; payload: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore' }
    | { type: 'SET_PROFILE'; payload: { username: string; phone: string } }
    | { type: 'ADD_WATCH_AREA'; payload: WatchAreaCreate }
    | { type: 'REMOVE_WATCH_AREA'; payload: number }  // index
    | { type: 'ADD_DAILY_ROUTE'; payload: DailyRouteCreate }
    | { type: 'REMOVE_DAILY_ROUTE'; payload: number }  // index
    | { type: 'NEXT_STEP' }
    | { type: 'PREV_STEP' }
    | { type: 'SET_STEP'; payload: number }
    | { type: 'SET_ERROR'; payload: { field: string; message: string } }
    | { type: 'CLEAR_ERRORS' }
    | { type: 'SET_SUBMITTING'; payload: boolean };

// ============================================================================
// FLOOD PREDICTION TYPES (ML Hotspot Visualization)
// ============================================================================

export type FloodRiskLevel = 'low' | 'moderate' | 'high' | 'extreme';

// ============================================================================
// FLOOD HAZARD INDEX (FHI) TYPES - Live weather-based hazard assessment
// ============================================================================

export type FHILevel = 'low' | 'moderate' | 'high' | 'extreme';

export interface FHIComponents {
    P: number;  // Precipitation (0-1)
    I: number;  // Intensity (0-1)
    S: number;  // Soil saturation (0-1)
    A: number;  // Antecedent conditions (0-1)
    R: number;  // Runoff potential (0-1)
    E: number;  // Elevation risk (0-1)
}

export interface FHIConfidence {
    precipitation: 'high' | 'medium' | 'low';
    intensity: 'high' | 'medium' | 'low';
    saturation: 'high' | 'medium' | 'low';
    overall: 'high' | 'medium' | 'low';
    notes: string[];
}

export interface FloodHazardIndex {
    fhi_score: number;        // 0.0-1.0 (with safety factor)
    fhi_score_raw?: number;   // 0.0-1.0 (without safety factor)
    fhi_level: FHILevel;      // Risk classification
    fhi_color: string;        // Hex color for UI (#22c55e, #eab308, #f97316, #ef4444)
    elevation_m: number;      // Elevation in meters
    components?: FHIComponents;  // Breakdown (optional, available on single hotspot)
    monsoon_modifier?: number;   // 1.0 or 1.2 during monsoon season
    is_urban_calibrated?: boolean;  // Whether urban calibration was applied
    confidence?: FHIConfidence;     // Confidence indicators
}

export interface FHIResponse extends FloodHazardIndex {
    precipitation_24h_mm: number;
    precipitation_48h_mm: number;
    precipitation_72h_mm: number;
    precipitation_corrected_24h_mm: number;  // With 1.2x safety factor
    soil_moisture_raw: number;    // Raw API value (not used for urban)
    saturation_proxy: number;     // Hybrid urban saturation proxy
    surface_pressure_hpa: number;
    is_monsoon: boolean;
}

export interface PredictionGridFeature {
    type: 'Feature';
    geometry: {
        type: 'Point';
        coordinates: [number, number]; // [lng, lat]
    };
    properties: {
        flood_probability: number; // 0.0 - 1.0
        risk_level: FloodRiskLevel;
    };
}

export interface PredictionGridResponse {
    type: 'FeatureCollection';
    features: PredictionGridFeature[];
    metadata: {
        generated_at: string;
        model: string;
        grid_points: number;
        resolution_km: number;
        horizon_days: number;
        bounds: {
            min_lat: number;
            max_lat: number;
            min_lng: number;
            max_lng: number;
        };
    };
}

// ============================================================================
// ROUTE COMPARISON TYPES (Normal vs FloodSafe route analysis)
// ============================================================================

export type FloodSeverity = 'none' | 'ankle' | 'knee' | 'waist' | 'impassable' | 'warning' | 'critical';

export interface RiskBreakdown {
    // Current data sources
    active_reports: number;
    sensor_warnings: number;

    // ML sources (scalable slots)
    ml_high_risk_zones: number;
    ml_extreme_risk_zones: number;
    ml_max_probability: number;
    ml_avg_probability: number;

    // Future expansion
    historical_flood_frequency: number;
    current_rain_intensity_mm: number;
    forecast_rain_24h_mm: number;

    // Aggregate
    total_flood_zones_avoided: number;
    overall_risk_score: number;
}

export interface StuckTimeEstimate {
    min_stuck_minutes: number;
    avg_stuck_minutes: number;
    worst_case_minutes: number;
    severity_level: FloodSeverity;
    risk_factors: string[];
}

export interface NetTimeSaved {
    vs_average_stuck: number;  // minutes saved vs average case
    vs_worst_case: number;     // minutes saved vs worst case
}

export interface FloodImpact {
    lat: number;
    lng: number;
    severity: string;
    type: 'report' | 'sensor' | 'ml_prediction';
    penalty_seconds: number;
}

export interface NormalRouteOption {
    id: string;
    type: 'normal';
    geometry: GeoJSON.LineString;
    distance_meters: number;
    duration_seconds: number;
    adjusted_duration_seconds: number;  // Duration accounting for flood delays
    safety_score: number;
    flood_intersections: number;
    flood_impacts: FloodImpact[];
    instructions: RouteInstruction[];
}

export interface RouteComparisonRequest {
    origin: { lat: number; lng: number };
    destination: { lat: number; lng: number };
    mode: 'driving' | 'walking' | 'cycling';
    city: string;
}

// =============================================================================
// HOTSPOT ANALYSIS TYPES (for route planning)
// Uses FHILevel from FLOOD HAZARD INDEX section above
// =============================================================================

export interface NearbyHotspot {
    id: number;
    name: string;
    fhi_level: FHILevel;
    fhi_color: string;
    fhi_score: number;
    distance_to_route_m: number;
    estimated_delay_seconds: number;
    must_avoid: boolean;  // True if HIGH or EXTREME (HARD AVOID)
}

export interface HotspotAnalysis {
    // Counts
    total_hotspots_on_normal: number;
    total_hotspots_on_safe: number;
    hotspots_avoided: number;
    critical_hotspots_avoided: number;  // HIGH/EXTREME count

    // FHI levels
    highest_fhi_normal: number | null;
    highest_fhi_safe: number | null;

    // Safety status
    normal_route_safe: boolean;  // False if any HARD AVOID hotspots
    safe_route_safe: boolean;
    must_reroute: boolean;  // True if normal route has HARD AVOID hotspots

    // User messaging
    warning_message: string | null;

    // Nearby hotspots (top 5 on normal route)
    nearby_hotspots: NearbyHotspot[];
}

export interface RouteComparisonResponse {
    // Route options
    normal_route: NormalRouteOption | null;
    floodsafe_route: RouteOption | null;

    // Comparison metrics
    time_penalty_seconds: number;
    distance_difference_meters: number;
    flood_zones_avoided: number;

    // Risk analysis
    risk_breakdown: RiskBreakdown;
    stuck_time_estimate: StuckTimeEstimate;
    net_time_saved: NetTimeSaved;

    // Recommendation
    recommendation: string;

    // Hotspot analysis (Delhi only - null for other cities)
    hotspot_analysis: HotspotAnalysis | null;

    // Flood zones GeoJSON for map display
    flood_zones: GeoJSON.FeatureCollection;
}

// ============================================================================
// UNIFIED ALERTS TYPES (Enhanced Alerts Section)
// ============================================================================

export type AlertSource = 'imd' | 'cwc' | 'twitter' | 'rss' | 'telegram' | 'floodsafe' | 'gdelt' | 'gdacs';
export type AlertType = 'external' | 'community';
export type AlertSeverity = 'low' | 'moderate' | 'high' | 'severe';
export type AlertSourceFilter = 'all' | 'official' | 'news' | 'social' | 'community' | 'floodhub' | 'circles';

export interface UnifiedAlert {
    id: string;
    type: AlertType;
    source: AlertSource;
    source_name?: string;
    title: string;
    message: string;
    severity?: AlertSeverity;
    latitude?: number;
    longitude?: number;
    url?: string;
    created_at: string;
}

export interface AlertSourceMeta {
    name: string;
    count: number;
    enabled: boolean;
}

export interface UnifiedAlertsResponse {
    alerts: UnifiedAlert[];
    sources: Record<string, AlertSourceMeta>;
    total: number;
    city: string;
}

// ============================================================================
// ENHANCED ROUTE TYPES (3-Route Comparison + Live Navigation)
// ============================================================================

export type TrafficLevel = 'low' | 'moderate' | 'heavy' | 'severe';

// Turn instruction for navigation
export interface TurnInstruction {
    instruction: string;
    distance_meters: number;
    duration_seconds: number;
    maneuver_type: string;
    maneuver_modifier: string;
    street_name: string;
    coordinates: [number, number];
}

// Fastest route option (driving-traffic)
export interface FastestRouteOption {
    id: string;
    type: 'fastest';
    geometry: GeoJSON.LineString;
    coordinates: [number, number][];
    distance_meters: number;
    duration_seconds: number;
    hotspot_count: number;
    traffic_level: TrafficLevel;
    safety_score: number;
    is_recommended: boolean;
    warnings: string[];
    instructions: TurnInstruction[];
}

// Metro segment (walking or metro)
export interface MetroSegment {
    type: 'walking' | 'metro';
    geometry?: GeoJSON.LineString;
    coordinates?: [number, number][];
    duration_seconds: number;
    distance_meters?: number;
    line?: string;
    line_color?: string;
    from_station?: string;
    to_station?: string;
    stops?: number;
    instructions?: TurnInstruction[];
}

// Metro route option
export interface MetroRouteOption {
    id: string;
    type: 'metro';
    segments: MetroSegment[];
    total_duration_seconds: number;
    total_distance_meters: number;
    metro_line: string;
    metro_color: string;
    affected_stations: string[];
    is_recommended: boolean;
}

// Safest route option (FloodSafe routing)
export interface SafestRouteOption {
    id: string;
    type: 'safest';
    geometry: GeoJSON.LineString;
    coordinates: [number, number][];
    distance_meters: number;
    duration_seconds: number;
    hotspot_count: number;
    safety_score: number;
    detour_km: number;
    detour_minutes: number;
    is_recommended: boolean;
    hotspots_avoided: string[];
    instructions: TurnInstruction[];
}

// Enhanced routes container
export interface EnhancedRoutes {
    fastest: FastestRouteOption | null;
    metro: MetroRouteOption | null;
    safest: SafestRouteOption | null;
}

// Route recommendation
export interface RouteRecommendation {
    route_type: 'fastest' | 'metro' | 'safest';
    reason: string;
}

// Enhanced comparison response
export interface EnhancedRouteComparisonResponse {
    routes: EnhancedRoutes;
    recommendation: RouteRecommendation;
    hotspot_analysis: HotspotAnalysis | null;
    flood_zones: GeoJSON.FeatureCollection;
}

// Watch area risk assessment
export interface WatchAreaRiskAssessment {
    watch_area_id: string;
    watch_area_name: string;
    latitude: number;
    longitude: number;
    radius: number;
    average_fhi: number;
    max_fhi: number;
    max_fhi_level: 'low' | 'moderate' | 'high' | 'extreme';
    is_at_risk: boolean;
    risk_flag_reason: string | null;
    nearby_hotspots_count: number;
    critical_hotspots_count: number;
    last_calculated: string;
}

// ============================================================================
// GOOGLE FLOODHUB TYPES (Flood Forecasting for Delhi Yamuna River)
// ============================================================================

export type FloodHubSeverity = 'EXTREME' | 'SEVERE' | 'ABOVE_NORMAL' | 'NO_FLOODING' | 'UNKNOWN';

export type FloodHubForecastTrend = 'RISE' | 'FALL' | 'NO_CHANGE';

export interface FloodHubGauge {
    gauge_id: string;
    site_name: string;
    river: string;
    latitude: number;
    longitude: number;
    severity: FloodHubSeverity;
    issued_time: string;
    source: string;
    has_model?: boolean;
    quality_verified?: boolean;
    forecast_trend?: FloodHubForecastTrend | null;
    inundation_map_set?: Record<string, string> | null; // {HIGH: polygonId, MEDIUM: ..., LOW: ...}
}

export interface FloodHubForecastPoint {
    timestamp: string;
    water_level: number | null;  // null during dry season (NaN from Google API)
    is_forecast: boolean;
}

export interface FloodHubForecast {
    gauge_id: string;
    site_name: string;
    forecasts: FloodHubForecastPoint[];
    danger_level: number;
    warning_level: number;
    extreme_danger_level?: number | null;
    gauge_value_unit?: string; // "METERS" or "CUBIC_METERS_PER_SECOND"
}

export interface FloodHubStatus {
    enabled: boolean;
    message?: string;
    overall_severity?: FloodHubSeverity;
    gauge_count?: number;
    alerts_by_severity?: Record<string, number>;
    last_updated?: string;
}

export interface FloodHubSignificantEvent {
    start_time: string;
    end_time?: string | null;
    minimum_end_time?: string | null;
    affected_country_codes: string[];
    affected_population?: number | null;
    area_km2?: number | null;
    gauge_ids: string[];
    event_polygon_id?: string | null;
}

// ============================================================================
// SAFETY CIRCLES TYPES (Family & Community Group Notifications)
// ============================================================================

export type CircleType = 'family' | 'school' | 'apartment' | 'neighborhood' | 'custom';
export type CircleRole = 'creator' | 'admin' | 'member';

export interface SafetyCircle {
    id: string;
    name: string;
    description: string | null;
    circle_type: CircleType;
    created_by: string;
    invite_code: string;
    max_members: number;
    member_count: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface CircleMember {
    id: string;
    circle_id: string;
    user_id: string | null;
    phone: string | null;
    email: string | null;
    display_name: string | null;
    role: CircleRole;
    is_muted: boolean;
    notify_whatsapp: boolean;
    notify_sms: boolean;
    notify_email: boolean;
    joined_at: string;
    invited_by: string | null;
}

export interface SafetyCircleDetail extends SafetyCircle {
    members: CircleMember[];
    user_role: CircleRole;
}

export interface CircleAlert {
    id: string;
    circle_id: string;
    report_id: string;
    reporter_user_id: string;
    member_id: string;
    message: string;
    is_read: boolean;
    notification_sent: boolean;
    notification_channel: string;
    created_at: string;
    circle_name: string;
    reporter_name: string;
}

export interface SafetyCircleCreate {
    name: string;
    description?: string;
    circle_type: CircleType;
}

export interface SafetyCircleUpdate {
    name?: string;
    description?: string;
}

export interface CircleMemberAdd {
    user_id?: string;
    phone?: string;
    email?: string;
    display_name?: string;
}

export interface CircleMemberUpdate {
    role?: CircleRole;
    is_muted?: boolean;
    notify_whatsapp?: boolean;
    notify_sms?: boolean;
    notify_email?: boolean;
}

export interface JoinCircleRequest {
    invite_code: string;
}

export interface CircleAlertsResponse {
    alerts: CircleAlert[];
    total: number;
}

export interface CircleUnreadCount {
    count: number;
}

export interface BulkAddResult {
    added: number;
    skipped: number;
    errors: string[];
}

// ============================================================================
// AI RISK SUMMARY TYPES (Llama/Groq AI-generated risk narratives)
// ============================================================================

export interface RiskSummaryResponse {
    risk_summary: string | null;
    enabled: boolean;
    risk_level: string;
    fhi_score: number;
    language: string;
    weather_unavailable?: boolean;
}

// ─── Community Intelligence Types ───────────────

export interface GroundsourceEpisode {
  id: string;
  city: string;
  latitude: number;
  longitude: number;
  area_km2?: number;
  date_start: string;
  date_end?: string;
  article_count: number;
}

export interface GroundsourceCluster {
  id: string;
  city: string;
  latitude: number;
  longitude: number;
  episode_count: number;
  radius_m?: number;
  date_first?: string;
  date_last?: string;
  overlap_status: string;
  nearest_hotspot_name?: string;
  confidence: string;
  label?: string;
}

export interface HistoricalStats {
  city: string;
  total_episodes: number;
  total_clusters: number;
  date_range_start?: string;
  date_range_end?: string;
  confirmed_clusters: number;
  missed_clusters: number;
}

export interface PersonalPin {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  city?: string;
  fhi_score?: number;
  fhi_level?: string;
  historical_episode_count: number;
  visibility: string;
  alert_radius_label?: string;
  snap_distance_m?: number;
  created_at: string;
}

export interface FhiHistoryEntry {
  fhi_score: number;
  fhi_level: string;
  recorded_at: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatResponse {
  reply: string;
  conversation_id: string;
  rate_limited: boolean;
}

export interface AddressRiskResult {
  address: string;
  latitude: number;
  longitude: number;
  fhi: Record<string, unknown>;
  historical_episodes: number;
  summary?: string;
}
