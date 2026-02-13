from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Tuple
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, field

# ============================================================================
# BASE MODELS (Full entity representations matching infrastructure layer)
# ============================================================================

class User(BaseModel):
    """User entity with gamification features"""
    id: UUID = Field(default_factory=uuid4)
    username: str
    email: str
    role: str = "user"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Gamification fields
    points: int = 0
    level: int = 1
    reports_count: int = 0
    verified_reports_count: int = 0
    badges: str = "[]"  # JSON string array

    # Reputation system
    reputation_score: int = 0
    streak_days: int = 0
    last_activity_date: Optional[datetime] = None

    # Privacy controls
    leaderboard_visible: bool = True
    profile_public: bool = True
    display_name: Optional[str] = None

    # Profile fields
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    language: str = "english"

    # Notification preferences
    notification_push: bool = True
    notification_sms: bool = True
    notification_whatsapp: bool = False
    notification_email: bool = True
    alert_preferences: str = '{"watch":true,"advisory":true,"warning":true,"emergency":true}'  # JSON string

    model_config = ConfigDict(from_attributes=True)


class Sensor(BaseModel):
    """IoT Sensor entity"""
    id: UUID = Field(default_factory=uuid4)
    location_lat: float
    location_lng: float
    status: str = "active"
    last_ping: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Reading(BaseModel):
    """Water level reading from sensor"""
    id: UUID = Field(default_factory=uuid4)
    sensor_id: UUID
    water_level: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class Report(BaseModel):
    """Flood report from user"""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    description: str
    location_lat: float
    location_lng: float
    media_url: Optional[str] = None
    media_type: str = "image"  # image, video
    media_metadata: str = "{}"  # JSON string
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    verified: bool = False
    verification_score: int = 0  # Computed from upvotes/user reputation
    upvotes: int = 0
    downvotes: int = 0
    quality_score: float = 0.0
    verified_at: Optional[datetime] = None

    # Community reporting fields
    phone_number: Optional[str] = None
    phone_verified: bool = False
    water_depth: Optional[str] = None  # ankle, knee, waist, impassable
    vehicle_passability: Optional[str] = None  # all, high-clearance, none
    iot_validation_score: int = 0  # 0-100 score from IoT sensor validation
    nearby_sensor_ids: str = "[]"  # JSON array of nearby sensor UUIDs
    prophet_prediction_match: Optional[bool] = None  # Future: matches Prophet forecast

    # Photo location verification
    location_verified: bool = True  # False if photo GPS doesn't match reported location

    model_config = ConfigDict(from_attributes=True)


class FloodZone(BaseModel):
    """Flood risk zone polygon"""
    id: UUID = Field(default_factory=uuid4)
    name: str
    risk_level: str  # low, medium, high, critical
    geometry: dict  # GeoJSON

    model_config = ConfigDict(from_attributes=True)


class WatchArea(BaseModel):
    """User-defined area to monitor for flood alerts"""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    location_lat: float
    location_lng: float
    radius: float = 1000.0  # meters
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# REQUEST DTOs (For API input validation)
# ============================================================================

class UserCreate(BaseModel):
    """Request DTO for user registration"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    role: str = "user"

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Request DTO for updating user profile"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    language: Optional[str] = None
    notification_push: Optional[bool] = None
    notification_sms: Optional[bool] = None
    notification_whatsapp: Optional[bool] = None
    notification_email: Optional[bool] = None
    alert_preferences: Optional[str] = None  # JSON string

    # Privacy controls
    leaderboard_visible: Optional[bool] = None
    profile_public: Optional[bool] = None
    display_name: Optional[str] = Field(None, min_length=3, max_length=50)

    # Onboarding & City Preference
    city_preference: Optional[str] = Field(None, pattern="^(bangalore|delhi|yogyakarta)$")
    profile_complete: Optional[bool] = None
    onboarding_step: Optional[int] = Field(None, ge=1, le=5)

    model_config = ConfigDict(from_attributes=True)


class WatchAreaCreate(BaseModel):
    """Request DTO for creating a watch area"""
    user_id: UUID
    name: str = Field(..., min_length=3, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius: float = Field(default=1000.0, ge=100, le=10000)  # 100m to 10km

    model_config = ConfigDict(from_attributes=True)


class ReportCreate(BaseModel):
    """Request DTO for creating flood report"""
    user_id: UUID
    description: str = Field(..., min_length=10, max_length=500)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    media_type: str = "image"

    # Community reporting fields
    phone_number: str = Field(..., min_length=10, max_length=20)
    phone_verification_token: Optional[str] = None
    water_depth: Optional[str] = Field(None, pattern="^(ankle|knee|waist|impassable)$")
    vehicle_passability: Optional[str] = Field(None, pattern="^(all|high-clearance|none)$")

    model_config = ConfigDict(from_attributes=True)


class SensorCreate(BaseModel):
    """Request DTO for registering a new sensor"""
    location_lat: float = Field(..., ge=-90, le=90)
    location_lng: float = Field(..., ge=-180, le=180)
    status: str = "active"

    model_config = ConfigDict(from_attributes=True)


class SensorReading(BaseModel):
    """Request DTO for IoT sensor data ingestion"""
    sensor_id: UUID
    water_level: float = Field(..., ge=0)  # Water level in meters
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# RESPONSE DTOs (For API output)
# ============================================================================

class UserResponse(BaseModel):
    """Response DTO for user data (excludes sensitive fields)"""
    id: UUID
    username: str
    email: str
    role: str
    created_at: datetime
    points: int
    level: int
    reports_count: int
    verified_reports_count: int
    badges: List[str]  # Parsed JSON array

    # Reputation system
    reputation_score: int = 0
    streak_days: int = 0
    last_activity_date: Optional[datetime] = None

    # Privacy controls
    leaderboard_visible: bool = True
    profile_public: bool = True
    display_name: Optional[str] = None

    # Profile fields
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    language: str = "english"

    # Notification preferences
    notification_push: bool = True
    notification_sms: bool = True
    notification_whatsapp: bool = False
    notification_email: bool = True
    alert_preferences: dict  # Parsed JSON object

    # Onboarding & City Preference
    city_preference: Optional[str] = None
    profile_complete: bool = False
    onboarding_step: Optional[int] = None
    tour_completed_at: Optional[datetime] = None

    @field_validator('badges', mode='before')
    @classmethod
    def parse_badges(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v

    @field_validator('alert_preferences', mode='before')
    @classmethod
    def parse_alert_preferences(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {"watch": True, "advisory": True, "warning": True, "emergency": True}
        return v

    model_config = ConfigDict(from_attributes=True)


class ReportResponse(BaseModel):
    """Response DTO for flood report"""
    id: UUID
    description: str
    latitude: float
    longitude: float
    media_url: Optional[str]
    verified: bool
    verification_score: int
    upvotes: int
    downvotes: int = 0  # Community feedback
    comment_count: int = 0  # Number of comments on this report
    timestamp: datetime

    # Community reporting fields (phone_number excluded for privacy)
    phone_verified: bool
    water_depth: Optional[str]
    vehicle_passability: Optional[str]
    iot_validation_score: int

    # Photo location verification
    location_verified: bool = True

    # Archive field - NULL means active, timestamp means archived
    archived_at: Optional[datetime] = None

    # User's vote status (populated when user is authenticated)
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None

    # ML classification results (extracted from media_metadata)
    ml_classification: Optional[str] = None  # 'flood' or 'no_flood'
    ml_confidence: Optional[float] = None  # 0.0 to 1.0
    ml_is_flood: Optional[bool] = None
    ml_needs_review: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# COMMUNITY FEEDBACK DTOs (Voting and Comments)
# ============================================================================

class VoteResponse(BaseModel):
    """Response DTO for vote actions"""
    message: str
    report_id: UUID
    upvotes: int
    downvotes: int
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None (if toggled off)

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    """Request DTO for creating a comment"""
    content: str = Field(..., min_length=1, max_length=500)

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    """Response DTO for a comment"""
    id: UUID
    report_id: UUID
    user_id: UUID
    username: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SensorResponse(BaseModel):
    """Response DTO for sensor data"""
    id: UUID
    latitude: float
    longitude: float
    status: str
    last_ping: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ReadingResponse(BaseModel):
    """Response DTO for water level reading"""
    id: UUID
    sensor_id: UUID
    water_level: float
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyResponse(BaseModel):
    """Response DTO for generated API key - shown only once"""
    sensor_id: UUID
    api_key: str  # Plaintext key - SHOW ONCE, then only hash is stored
    message: str


class SensorWithOwnerResponse(BaseModel):
    """Extended sensor response including IoT enhancements"""
    id: UUID
    latitude: float
    longitude: float
    status: str
    last_ping: Optional[datetime]
    name: Optional[str]
    hardware_type: Optional[str]
    firmware_version: Optional[str]
    has_api_key: bool  # True if api_key_hash is set

    model_config = ConfigDict(from_attributes=True)


class WatchAreaResponse(BaseModel):
    """Response DTO for watch area"""
    id: UUID
    user_id: UUID
    name: str
    latitude: float
    longitude: float
    radius: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyRouteCreate(BaseModel):
    """Request DTO for creating a daily route"""
    user_id: UUID
    name: str = Field(..., min_length=3, max_length=100)
    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    transport_mode: str = Field(default='driving', pattern="^(driving|walking|metro|combined)$")
    notify_on_flood: bool = True

    model_config = ConfigDict(from_attributes=True)


class DailyRouteResponse(BaseModel):
    """Response DTO for daily route"""
    id: UUID
    user_id: UUID
    name: str
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    transport_mode: str
    notify_on_flood: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ROUTING MODELS (Safe route navigation)
# ============================================================================

class LocationPoint(BaseModel):
    """Geographic coordinate point"""
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)

    model_config = ConfigDict(from_attributes=True)


class RouteRequest(BaseModel):
    """Request DTO for route calculation"""
    origin: LocationPoint
    destination: LocationPoint
    city: str = "BLR"
    mode: str = "driving"
    avoid_risk_levels: Optional[List[str]] = ["critical", "warning"]

    model_config = ConfigDict(from_attributes=True)


class RouteInstruction(BaseModel):
    """Turn-by-turn navigation instruction"""
    text: str
    distance_meters: float
    duration_seconds: Optional[float] = None
    maneuver: str
    location: List[float]

    model_config = ConfigDict(from_attributes=True)


class RouteOption(BaseModel):
    """Single route option with safety information"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    city_code: str
    geometry: dict
    distance_meters: float
    duration_seconds: Optional[float] = None
    safety_score: int
    risk_level: str
    flood_intersections: int
    instructions: Optional[List[RouteInstruction]] = None

    model_config = ConfigDict(from_attributes=True)


class RouteResponse(BaseModel):
    """Response containing multiple route options"""
    routes: List[RouteOption]
    city: str
    warnings: List[str] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ROUTE COMPARISON MODELS (Normal vs FloodSafe route analysis)
# ============================================================================

class RiskBreakdown(BaseModel):
    """Breakdown of risk factors along a route"""
    # Current data sources
    active_reports: int = 0
    sensor_warnings: int = 0

    # ML sources (scalable slots for future integration)
    ml_high_risk_zones: int = 0
    ml_extreme_risk_zones: int = 0
    ml_max_probability: float = 0.0
    ml_avg_probability: float = 0.0

    # Future expansion
    historical_flood_frequency: int = 0
    current_rain_intensity_mm: float = 0.0
    forecast_rain_24h_mm: float = 0.0

    # Aggregate
    total_flood_zones_avoided: int = 0
    overall_risk_score: int = 0

    model_config = ConfigDict(from_attributes=True)


class StuckTimeEstimate(BaseModel):
    """Estimated time if user gets stuck on flooded route"""
    min_stuck_minutes: int = 0
    avg_stuck_minutes: int = 0
    worst_case_minutes: int = 0
    severity_level: str = "none"  # none, ankle, knee, waist, impassable, warning, critical
    risk_factors: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class NetTimeSaved(BaseModel):
    """Net time saved by taking FloodSafe route"""
    vs_average_stuck: float = 0.0  # minutes saved vs average case
    vs_worst_case: float = 0.0     # minutes saved vs worst case

    model_config = ConfigDict(from_attributes=True)


class FloodImpact(BaseModel):
    """Individual flood zone impact on a route"""
    lat: float
    lng: float
    severity: str
    type: str  # report, sensor, ml_prediction
    penalty_seconds: int = 0

    model_config = ConfigDict(from_attributes=True)


class NormalRouteOption(BaseModel):
    """Normal route (fastest) with flood analysis"""
    id: str
    type: str = "normal"
    geometry: dict
    distance_meters: float
    duration_seconds: float
    adjusted_duration_seconds: float  # Duration accounting for flood delays
    safety_score: int
    flood_intersections: int
    flood_impacts: List[FloodImpact] = []
    instructions: List[RouteInstruction] = []

    model_config = ConfigDict(from_attributes=True)


class RouteComparisonRequest(BaseModel):
    """Request DTO for route comparison"""
    origin: LocationPoint
    destination: LocationPoint
    mode: str = "driving"
    city: str = "BLR"

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# HOTSPOT ANALYSIS MODELS (for route planning)
# =============================================================================

class NearbyHotspot(BaseModel):
    """A waterlogging hotspot near a route"""
    id: int
    name: str
    fhi_level: str  # 'low' | 'moderate' | 'high' | 'extreme'
    fhi_color: str
    fhi_score: float = 0.0
    distance_to_route_m: float = 0.0
    estimated_delay_seconds: int = 0
    must_avoid: bool = False  # True if HIGH or EXTREME (HARD AVOID)

    model_config = ConfigDict(from_attributes=True)


class HotspotAnalysis(BaseModel):
    """
    Complete hotspot analysis for a route.

    Used in RouteComparisonResponse to show waterlogging risk.
    Only populated for Delhi routes (where hotspot data exists).
    """
    total_hotspots_nearby: int = 0
    hotspots_to_avoid: int = 0  # HIGH/EXTREME count (HARD AVOID)
    hotspots_with_warnings: int = 0  # MODERATE count
    highest_fhi_score: Optional[float] = None
    highest_fhi_level: Optional[str] = None
    total_delay_seconds: int = 0
    route_is_safe: bool = True  # False if any HARD AVOID hotspots
    must_reroute: bool = False  # True if route should be rejected
    nearby_hotspots: List[NearbyHotspot] = []
    warning_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RouteComparisonResponse(BaseModel):
    """Response containing route comparison analysis"""
    # Route options
    normal_route: Optional[NormalRouteOption] = None
    floodsafe_route: Optional[RouteOption] = None

    # Comparison metrics
    time_penalty_seconds: float = 0
    distance_difference_meters: float = 0
    flood_zones_avoided: int = 0

    # Risk analysis
    risk_breakdown: RiskBreakdown
    stuck_time_estimate: StuckTimeEstimate
    net_time_saved: NetTimeSaved

    # Recommendation
    recommendation: str = ""

    # Hotspot analysis (Delhi only - where hotspot data exists)
    hotspot_analysis: Optional[HotspotAnalysis] = None

    # Flood zones GeoJSON for map display
    flood_zones: dict = {}

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# ENHANCED ROUTING MODELS (3-Route Comparison System)
# =============================================================================

class TrafficLevel(str, Enum):
    """Traffic congestion level from Mapbox annotations"""
    LOW = "low"
    MODERATE = "moderate"
    HEAVY = "heavy"
    SEVERE = "severe"


class RouteType(str, Enum):
    """Route type identifier"""
    FASTEST = "fastest"
    METRO = "metro"
    SAFEST = "safest"


class TurnInstruction(BaseModel):
    """Turn-by-turn navigation instruction"""
    instruction: str
    distance_meters: int
    duration_seconds: int
    maneuver_type: str  # "turn", "depart", "arrive", "continue"
    maneuver_modifier: str  # "left", "right", "straight", "slight left"
    street_name: Optional[str] = None
    coordinates: Tuple[float, float]  # [lng, lat]

    model_config = ConfigDict(from_attributes=True)


class FastestRouteOption(BaseModel):
    """Fastest route with traffic analysis"""
    id: str
    type: str = "fastest"
    geometry: dict  # GeoJSON LineString
    coordinates: List[Tuple[float, float]]  # Decoded for deviation check
    distance_meters: int
    duration_seconds: int
    hotspot_count: int = 0
    traffic_level: str = "moderate"
    safety_score: int = 100
    is_recommended: bool = False
    warnings: List[str] = []
    instructions: List[TurnInstruction] = []

    model_config = ConfigDict(from_attributes=True)


class MetroSegment(BaseModel):
    """Single segment of metro route (walking or metro ride)"""
    type: str  # "walking" | "metro"
    geometry: Optional[dict] = None
    coordinates: Optional[List[Tuple[float, float]]] = None
    duration_seconds: int
    distance_meters: Optional[int] = None
    line: Optional[str] = None
    line_color: Optional[str] = None
    from_station: Optional[str] = None
    to_station: Optional[str] = None
    stops: Optional[int] = None
    instructions: List[TurnInstruction] = []

    model_config = ConfigDict(from_attributes=True)


class MetroRouteOption(BaseModel):
    """Metro-based route with walking segments"""
    id: str
    type: str = "metro"
    segments: List[MetroSegment]
    total_duration_seconds: int
    total_distance_meters: int
    metro_line: str
    metro_color: str
    affected_stations: List[str] = []
    is_recommended: bool = False

    model_config = ConfigDict(from_attributes=True)


class SafestRouteOption(BaseModel):
    """Safest route avoiding hotspots"""
    id: str
    type: str = "safest"
    geometry: dict
    coordinates: List[Tuple[float, float]]
    distance_meters: int
    duration_seconds: int
    hotspot_count: int = 0
    safety_score: int = 100
    detour_km: float = 0.0
    detour_minutes: int = 0
    is_recommended: bool = False
    hotspots_avoided: List[str] = []
    instructions: List[TurnInstruction] = []

    model_config = ConfigDict(from_attributes=True)


class EnhancedRouteComparisonResponse(BaseModel):
    """Enhanced 3-route comparison response"""
    routes: dict  # {fastest, metro, safest}
    recommendation: dict  # {route_type, reason}
    hotspot_analysis: Optional[dict] = None
    flood_zones: dict = {}

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# SAFETY CIRCLES — Family/community group notification system
# ============================================================================

class CircleType(str, Enum):
    FAMILY = "family"
    SCHOOL = "school"
    APARTMENT = "apartment"
    NEIGHBORHOOD = "neighborhood"
    CUSTOM = "custom"


class CircleRole(str, Enum):
    CREATOR = "creator"
    ADMIN = "admin"
    MEMBER = "member"


# --- Request DTOs ---

class SafetyCircleCreate(BaseModel):
    """Create a new Safety Circle."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    circle_type: CircleType = CircleType.CUSTOM

    model_config = ConfigDict(from_attributes=True)


class SafetyCircleUpdate(BaseModel):
    """Update an existing Safety Circle."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(from_attributes=True)


class CircleMemberAdd(BaseModel):
    """Add a member to a circle. At least one of user_id, phone, or email required."""
    user_id: Optional[UUID] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    display_name: Optional[str] = Field(None, max_length=100)
    role: CircleRole = CircleRole.MEMBER

    @model_validator(mode="after")
    def check_at_least_one_identifier(self):
        if not self.user_id and not self.phone and not self.email:
            raise ValueError("At least one of user_id, phone, or email must be provided")
        return self

    model_config = ConfigDict(from_attributes=True)


class CircleMemberUpdate(BaseModel):
    """Update member settings. Admins can change role; members can change own prefs."""
    role: Optional[CircleRole] = None
    is_muted: Optional[bool] = None
    notify_whatsapp: Optional[bool] = None
    notify_sms: Optional[bool] = None
    notify_email: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class JoinCircleRequest(BaseModel):
    """Join a circle via invite code."""
    invite_code: str = Field(..., min_length=6, max_length=12)


# --- Response DTOs ---

class SafetyCircleResponse(BaseModel):
    """Safety Circle summary (without member details)."""
    id: UUID
    name: str
    description: Optional[str] = None
    circle_type: str
    created_by: UUID
    invite_code: str
    max_members: int
    is_active: bool
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CircleMemberResponse(BaseModel):
    """A member of a Safety Circle."""
    id: UUID
    circle_id: UUID
    user_id: Optional[UUID] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str
    is_muted: bool
    notify_whatsapp: bool
    notify_sms: bool
    notify_email: bool
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafetyCircleDetailResponse(SafetyCircleResponse):
    """Safety Circle with full member list."""
    members: List[CircleMemberResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CircleAlertResponse(BaseModel):
    """A notification for a circle member about a flood report."""
    id: UUID
    circle_id: UUID
    circle_name: str = ""
    report_id: UUID
    reporter_name: Optional[str] = None
    message: str
    is_read: bool
    notification_sent: bool = False
    notification_channel: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Notification Result (Rule #14: no silent fallbacks) ---

@dataclass
class NotificationResult:
    """
    Tracks every success and failure during circle notification dispatch.
    Returned from notify_circles_for_report() — never swallowed.
    The API response includes this summary so the user sees what happened.
    """
    circles_count: int = 0
    alerts_created: int = 0
    whatsapp_sent: int = 0
    whatsapp_failed: int = 0
    sms_sent: int = 0
    sms_failed: int = 0
    skipped_muted: int = 0
    skipped_dedup: int = 0
    skipped_throttle: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dict for API response."""
        return {
            "circles_notified": self.circles_count,
            "members_alerted": self.alerts_created,
            "whatsapp_sent": self.whatsapp_sent,
            "whatsapp_failed": self.whatsapp_failed,
            "sms_sent": self.sms_sent,
            "sms_failed": self.sms_failed,
            "skipped_muted": self.skipped_muted,
            "skipped_dedup": self.skipped_dedup,
            "skipped_throttle": self.skipped_throttle,
            "has_errors": len(self.errors) > 0,
        }
