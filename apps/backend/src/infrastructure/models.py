from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, Integer, Text, Index, text, BigInteger, ARRAY, Date, func
from sqlalchemy.dialects.postgresql import UUID, JSON, JSONB
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.ext.hybrid import hybrid_property
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from .database import Base
import uuid
from datetime import date, datetime

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Authentication fields
    google_id = Column(String, unique=True, nullable=True, index=True)
    phone_verified = Column(Boolean, default=False)
    auth_provider = Column(String, default='local')  # 'google', 'phone', 'local'

    # Email/Password authentication
    password_hash = Column(String, nullable=True)  # NULL for OAuth/Phone users
    email_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # Gamification
    points = Column(Integer, default=0)
    level = Column(Integer, default=1)
    reports_count = Column(Integer, default=0)
    verified_reports_count = Column(Integer, default=0)
    badges = Column(String, default="[]") # JSON string

    # Reputation system
    reputation_score = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    last_activity_date = Column(DateTime, nullable=True)

    # Privacy controls
    leaderboard_visible = Column(Boolean, default=True)
    profile_public = Column(Boolean, default=True)
    display_name = Column(String, nullable=True)

    # Profile fields
    phone = Column(String, nullable=True)
    profile_photo_url = Column(String, nullable=True)
    language = Column(String, default="english")

    # Notification preferences
    notification_push = Column(Boolean, default=True)
    notification_sms = Column(Boolean, default=True)
    notification_whatsapp = Column(Boolean, default=False)
    notification_email = Column(Boolean, default=True)
    alert_preferences = Column(String, default='{"watch":true,"advisory":true,"warning":true,"emergency":true}') # JSON string

    # FCM Push Notification token
    fcm_token = Column(String, nullable=True)  # Firebase Cloud Messaging device token
    fcm_token_updated_at = Column(DateTime, nullable=True)

    # Onboarding & City Preference
    city_preference = Column(String, nullable=True)  # 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore'
    profile_complete = Column(Boolean, default=False)
    onboarding_step = Column(Integer, nullable=True)  # 1-5, tracks current step if incomplete
    tour_completed_at = Column(DateTime, nullable=True)  # When user finished app tour

    # Role enhancement - timestamps for role transitions
    verified_reporter_since = Column(DateTime, nullable=True)  # When became verified_reporter
    moderator_since = Column(DateTime, nullable=True)  # When became moderator

    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    saved_routes = relationship("SavedRoute", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

class Sensor(Base):
    __tablename__ = "sensors"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location = Column(Geometry('POINT', srid=4326))
    status = Column(String, default="active")
    last_ping = Column(DateTime, nullable=True)
    readings = relationship("Reading", back_populates="sensor")

    # IoT enhancements (added via migrate_add_iot_enhancements.py)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(100), nullable=True)  # Human-readable name e.g., "Home Bucket Sensor"
    api_key_hash = Column(String(128), unique=True, nullable=True, index=True)  # SHA256 hash for auth
    hardware_type = Column(String(64), default="ESP32S3_GROVE_VL53L0X")
    firmware_version = Column(String(16), nullable=True)

    @hybrid_property
    def latitude(self):
        """Extract latitude from PostGIS POINT geometry"""
        if self.location is not None:
            session = object_session(self)
            if session:
                result = session.scalar(ST_Y(self.location))
                return float(result) if result is not None else None
        return None

    @hybrid_property
    def longitude(self):
        """Extract longitude from PostGIS POINT geometry"""
        if self.location is not None:
            session = object_session(self)
            if session:
                result = session.scalar(ST_X(self.location))
                return float(result) if result is not None else None
        return None

class Reading(Base):
    __tablename__ = "readings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id"))
    water_level = Column(Float)  # Legacy field - keeps backward compatibility
    timestamp = Column(DateTime, default=datetime.utcnow)
    sensor = relationship("Sensor", back_populates="readings")

    # IoT enhancements for ESP32 sensor data (added via migrate_add_iot_enhancements.py)
    water_segments = Column(Integer, nullable=True)  # 0-20 from Grove water sensor
    distance_mm = Column(Float, nullable=True)  # VL53L0X raw distance measurement
    water_height_mm = Column(Float, nullable=True)  # Calculated water height
    water_percent_strips = Column(Float, nullable=True)  # Percentage from strip sensor
    water_percent_distance = Column(Float, nullable=True)  # Percentage from distance sensor
    is_warning = Column(Boolean, default=False)  # WARNING status flag
    is_flood = Column(Boolean, default=False)  # FLOOD status flag

    __table_args__ = (
        Index('idx_readings_sensor_timestamp', 'sensor_id', 'timestamp'),
    )

class Report(Base):
    __tablename__ = "reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    description = Column(String)
    location = Column(Geometry('POINT', srid=4326))
    media_url = Column(String, nullable=True)
    media_type = Column(String, default="image")
    media_metadata = Column(String, default="{}") # JSON string
    timestamp = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)
    verification_score = Column(Integer, default=0)
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    quality_score = Column(Float, default=0.0)
    verified_at = Column(DateTime, nullable=True)

    # Community reporting fields
    phone_number = Column(String(20), nullable=True)
    phone_verified = Column(Boolean, default=False)
    water_depth = Column(String(20), nullable=True)  # ankle, knee, waist, impassable
    vehicle_passability = Column(String(30), nullable=True)  # all, high-clearance, none
    iot_validation_score = Column(Integer, default=0)  # 0-100
    nearby_sensor_ids = Column(String, default="[]")  # JSON array
    prophet_prediction_match = Column(Boolean, nullable=True)  # Future: Prophet integration

    # Photo location verification
    location_verified = Column(Boolean, default=True)  # False if photo GPS doesn't match reported location

    # Safe routing fields (auto-populated by database trigger)
    risk_polygon = Column(Geometry('POLYGON', srid=4326), nullable=True)
    risk_radius_meters = Column(Integer, default=100)

    # Archive field - reports auto-archive after 3 days, or can be manually archived
    archived_at = Column(DateTime, nullable=True)  # NULL = not archived, set = archived timestamp

    # Admin report fields
    admin_created = Column(Boolean, default=False)  # True for admin-created reports
    source = Column(String(50), nullable=True)       # "field_observation"|"government_data"|"phone_report"

    # ML pipeline enrichment fields
    weather_snapshot = Column(JSONB, nullable=True)
    road_segment_id = Column(UUID(as_uuid=True), nullable=True)
    road_name = Column(String, nullable=True)
    road_type = Column(String, nullable=True)

    # FHI enrichment columns
    fhi_score = Column(Float, nullable=True)
    fhi_level = Column(String, nullable=True)
    fhi_components = Column(JSONB, nullable=True)
    nearest_hotspot_id = Column(String, nullable=True)
    nearest_hotspot_distance = Column(Float, nullable=True)
    historical_episode_count = Column(Integer, default=0)

    @hybrid_property
    def latitude(self):
        """Extract latitude from PostGIS POINT geometry"""
        if self.location is not None:
            session = object_session(self)
            if session:
                result = session.scalar(ST_Y(self.location))
                return float(result) if result is not None else None
        return None

    @hybrid_property
    def longitude(self):
        """Extract longitude from PostGIS POINT geometry"""
        if self.location is not None:
            session = object_session(self)
            if session:
                result = session.scalar(ST_X(self.location))
                return float(result) if result is not None else None
        return None

class FloodZone(Base):
    __tablename__ = "flood_zones"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    risk_level = Column(String)
    geometry = Column(Geometry('POLYGON', srid=4326))

class WatchArea(Base):
    __tablename__ = "watch_areas"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    name = Column(String)
    location = Column(Geometry('POINT', srid=4326))
    radius = Column(Float, default=1000.0) # meters
    created_at = Column(DateTime, default=datetime.utcnow)

    # Community intelligence columns
    road_segment_id = Column(UUID(as_uuid=True), nullable=True)
    road_name = Column(String, nullable=True)
    snapped_location = Column(Geometry('POINT', srid=4326), nullable=True)
    fhi_score = Column(Float, nullable=True)
    fhi_level = Column(String, nullable=True)
    fhi_components = Column(JSONB, nullable=True)
    fhi_updated_at = Column(DateTime, nullable=True)
    weather_snapshot = Column(JSONB, nullable=True)
    is_personal_hotspot = Column(Boolean, default=False)
    hotspot_ref = Column(UUID(as_uuid=True), nullable=True)
    city = Column(String, nullable=True)
    visibility = Column(String, default='circles')
    source = Column(String, default='map')
    updated_at = Column(DateTime, server_default=func.now())
    alert_radius = Column(Float, default=300.0)
    historical_episode_count = Column(Integer, default=0)
    nearest_cluster_id = Column(UUID(as_uuid=True), nullable=True)

    @hybrid_property
    def latitude(self):
        """Extract latitude from PostGIS POINT geometry"""
        if self.location is not None:
            session = object_session(self)
            if session:
                result = session.scalar(ST_Y(self.location))
                return float(result) if result is not None else None
        return None

    @hybrid_property
    def longitude(self):
        """Extract longitude from PostGIS POINT geometry"""
        if self.location is not None:
            session = object_session(self)
            if session:
                result = session.scalar(ST_X(self.location))
                return float(result) if result is not None else None
        return None

class DailyRoute(Base):
    """Daily route model for storing user's regular commute routes"""
    __tablename__ = "daily_routes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)  # e.g., "Home to Work"
    origin_latitude = Column(Float, nullable=False)
    origin_longitude = Column(Float, nullable=False)
    destination_latitude = Column(Float, nullable=False)
    destination_longitude = Column(Float, nullable=False)
    transport_mode = Column(String, default='driving')  # driving, walking, metro, combined
    notify_on_flood = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @hybrid_property
    def origin_lat(self):
        return self.origin_latitude

    @hybrid_property
    def origin_lng(self):
        return self.origin_longitude

    @hybrid_property
    def dest_lat(self):
        return self.destination_latitude

    @hybrid_property
    def dest_lng(self):
        return self.destination_longitude

class Alert(Base):
    """Alert model for notifying users about flood reports in their watch areas."""
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    watch_area_id = Column(UUID(as_uuid=True), ForeignKey("watch_areas.id", ondelete="CASCADE"), nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReputationHistory(Base):
    __tablename__ = "reputation_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False)
    points_change = Column(Integer, default=0)
    new_total = Column(Integer, nullable=False)
    reason = Column(String, nullable=True)
    extra_metadata = Column(String, default="{}") # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)


class RoleHistory(Base):
    """Audit trail for role changes - tracks promotions/demotions with reason."""
    __tablename__ = "role_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    old_role = Column(String(50), nullable=False)
    new_role = Column(String(50), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # NULL for auto-promotion
    reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Badge(Base):
    __tablename__ = "badges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    icon = Column(String, default="🏆")
    category = Column(String, default="achievement")
    requirement_type = Column(String, nullable=False)
    requirement_value = Column(Integer, nullable=False)
    points_reward = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserBadge(Base):
    __tablename__ = "user_badges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    badge_id = Column(UUID(as_uuid=True), ForeignKey("badges.id", ondelete="CASCADE"), nullable=False)
    earned_at = Column(DateTime, default=datetime.utcnow)


class RefreshToken(Base):
    """Stores refresh tokens for JWT authentication with rotation support"""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked = Column(Boolean, default=False)

    # Relationship
    user = relationship("User", back_populates="refresh_tokens")


class EmailVerificationToken(Base):
    """Stores email verification tokens for email confirmation"""
    __tablename__ = "email_verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)  # NULL = unused, set = when token was used

    # Relationship
    user = relationship("User", back_populates="verification_tokens")


class PasswordResetToken(Base):
    """Stores password reset tokens for forgot-password flow"""
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="password_reset_tokens")


class SavedRoute(Base):
    """Saved route bookmarks for quick access to frequently used routes"""
    __tablename__ = "saved_routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    origin_latitude = Column(Float, nullable=False)
    origin_longitude = Column(Float, nullable=False)
    origin_name = Column(String(255), nullable=True)
    destination_latitude = Column(Float, nullable=False)
    destination_longitude = Column(Float, nullable=False)
    destination_name = Column(String(255), nullable=True)
    transport_mode = Column(String(20), default="driving")
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="saved_routes")


class ReportVote(Base):
    """Track user votes on reports for deduplication - prevents multiple votes per user"""
    __tablename__ = "report_votes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    vote_type = Column(String(10), nullable=False)  # 'upvote' or 'downvote'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_report_votes_user_report', 'user_id', 'report_id', unique=True),
    )


class Comment(Base):
    """Comments on flood reports for community discussion"""
    __tablename__ = "comments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    comment_type = Column(String(20), default="community")  # "community"|"admin_verification"|"admin_rejection"

    __table_args__ = (
        Index('ix_comments_report_created', 'report_id', 'created_at'),
    )


class ExternalAlert(Base):
    """
    External flood alerts aggregated from multiple sources:
    - IMD (India Meteorological Department)
    - CWC (Central Water Commission)
    - RSS news feeds
    - Twitter/X
    - Telegram channels
    """
    __tablename__ = "external_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, index=True)  # 'imd', 'cwc', 'twitter', 'rss', 'telegram'
    source_id = Column(String(255), nullable=True, unique=True)  # Original ID for deduplication
    source_name = Column(String(100), nullable=True)  # Display name: "Hindustan Times", "IMD Delhi"
    city = Column(String(50), nullable=False, index=True)  # 'delhi', 'bangalore'
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=True)  # 'low', 'moderate', 'high', 'severe'
    url = Column(String(2048), nullable=True)  # Link to original source
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    raw_data = Column(JSON, nullable=True)  # Store original API/RSS response
    expires_at = Column(DateTime, nullable=True)  # When alert becomes stale
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('ix_external_alerts_city_created', 'city', 'created_at'),
        Index('ix_external_alerts_source_city', 'source', 'city'),
    )


class WhatsAppSession(Base):
    """
    WhatsApp conversation state for interactive flows.
    Tracks user's position in multi-step conversations (e.g., account linking).
    Sessions expire after 30 minutes of inactivity.
    """
    __tablename__ = "whatsapp_sessions"

    phone = Column(String(20), primary_key=True)  # E.164 format: +919876543210
    state = Column(String(50), default="idle")  # idle, awaiting_choice, awaiting_email, sos_active
    data = Column(JSON, default={})  # Arbitrary session data (email attempts, temp values, etc.)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Linked user
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # States:
    # - idle: Ready for new command
    # - awaiting_choice: User asked "1. Create account" or "2. Submit anonymously"
    # - awaiting_email: User chose to create account, waiting for email
    # - sos_active: User in active SOS flow (location pending)


# ============================================================================
# SAFETY CIRCLES — Family/community group notification system
# ============================================================================

class SafetyCircle(Base):
    """
    A Safety Circle is a group (family, school, apartment, etc.) where members
    get notified when any member creates a flood report.

    Circle types and their default max_members:
    - family: 20, school: 500, apartment: 200, neighborhood: 1000, custom: 50
    """
    __tablename__ = "safety_circles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    circle_type = Column(String(30), nullable=False, default="custom")  # family, school, apartment, neighborhood, custom
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invite_code = Column(String(12), unique=True, nullable=False)  # 8-char alphanumeric for easy sharing
    max_members = Column(Integer, nullable=False, default=50)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members = relationship("CircleMember", back_populates="circle", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_safety_circles_created_by', 'created_by'),
        Index('ix_safety_circles_is_active', 'is_active', postgresql_where=text('is_active = TRUE')),
    )


class CircleMember(Base):
    """
    A member of a Safety Circle. Can be a registered FloodSafe user (user_id set)
    or a non-registered contact (only phone/email set, user_id is NULL).

    When a non-registered contact later registers and joins via invite code,
    their existing row is upgraded by setting user_id.

    Roles: creator (full admin), admin (can manage members), member (receives notifications)
    """
    __tablename__ = "circle_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circle_id = Column(UUID(as_uuid=True), ForeignKey("safety_circles.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # NULL for non-registered
    phone = Column(String(20), nullable=True)  # E.164 format: +919876543210
    email = Column(String(255), nullable=True)
    display_name = Column(String(100), nullable=True)  # Provided by adder, or falls back to user.display_name
    role = Column(String(10), nullable=False, default="member")  # creator, admin, member
    is_muted = Column(Boolean, default=False)  # Per-member mute toggle for this circle
    notify_whatsapp = Column(Boolean, default=True)
    notify_sms = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    circle = relationship("SafetyCircle", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        # Registered users can only be in a circle once (partial unique index)
        Index('uq_circle_registered_user', 'circle_id', 'user_id', unique=True, postgresql_where=text('user_id IS NOT NULL')),
        Index('ix_circle_members_circle_id', 'circle_id'),
        Index('ix_circle_members_user_id', 'user_id'),
        Index('ix_circle_members_phone', 'phone'),
        # CHECK constraint: at least one identifier must be present
        # (enforced at DB level via migration, SQLAlchemy doesn't support CHECK directly here)
    )


class CircleAlert(Base):
    """
    A notification record created when a circle member files a flood report.
    One CircleAlert per member per report per circle.

    Tracks whether the external notification (WhatsApp/SMS) was actually sent,
    to support Rule #14 (no silent fallbacks) — failed notifications are visible.
    """
    __tablename__ = "circle_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circle_id = Column(UUID(as_uuid=True), ForeignKey("safety_circles.id", ondelete="CASCADE"), nullable=False)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    reporter_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    member_id = Column(UUID(as_uuid=True), ForeignKey("circle_members.id", ondelete="CASCADE"), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False)
    notification_sent = Column(Boolean, default=False)  # Whether WhatsApp/SMS was actually dispatched
    notification_channel = Column(String(20), nullable=True)  # 'whatsapp', 'sms', 'email', or NULL if not sent
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_circle_alerts_member_id', 'member_id'),
        Index('ix_circle_alerts_circle_id', 'circle_id'),
        Index('ix_circle_alerts_report_id', 'report_id'),
        Index('ix_circle_alerts_unread', 'is_read', postgresql_where=text('is_read = FALSE')),
        Index('ix_circle_alerts_created_at', 'created_at'),
    )


class SOSMessage(Base):
    """
    An SOS emergency message sent by a user to their safety contacts.
    Queued on the frontend when offline, sent via Twilio when online.
    Tracks per-recipient delivery status in recipients_json.

    Design: Accepts raw phone numbers (not user IDs) because recipients include
    non-registered contacts (Safety Circle phone-only members, emergency contacts).
    """
    __tablename__ = "sos_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message = Column(String(500), nullable=False)
    location = Column(Geometry("POINT", srid=4326), nullable=True)
    recipients_json = Column(JSON, nullable=False)  # [{phone, name, status, channel, error?}]
    channel = Column(String(20), nullable=False, default="sms")  # 'sms' or 'whatsapp'
    status = Column(String(20), nullable=False, default="queued")  # queued/sending/sent/partial/failed
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)  # Newline-separated error messages
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_sos_messages_user_id', 'user_id'),
        Index('ix_sos_messages_created_at', 'created_at'),
        Index('ix_sos_messages_status', 'status'),
    )


class AdminAuditLog(Base):
    """
    Audit trail for admin panel actions.
    Tracks all admin operations for accountability and compliance.
    """
    __tablename__ = "admin_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)  # 'ban_user', 'verify_report', 'award_badge', etc.
    target_type = Column(String(50), nullable=True)  # 'user', 'report', 'badge'
    target_id = Column(String(255), nullable=True)  # UUID string of target entity
    details = Column(Text, nullable=True)  # JSON string with additional context
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_admin_audit_log_admin_id', 'admin_id'),
        Index('ix_admin_audit_log_action', 'action'),
        Index('ix_admin_audit_log_created_at', 'created_at'),
    )


class AdminInvite(Base):
    """Invite codes for multi-admin onboarding."""
    __tablename__ = "admin_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), unique=True, nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email_hint = Column(String(255), nullable=True)
    used_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CityRoad(Base):
    """OSM road network segments for report road-snapping and hotspot discovery."""
    __tablename__ = "city_roads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city = Column(String, nullable=False, index=True)
    osm_id = Column(BigInteger, nullable=True)
    name = Column(String, nullable=True)
    road_type = Column(String, nullable=False)
    is_underpass = Column(Boolean, default=False)
    is_bridge = Column(Boolean, default=False)
    geometry = Column(Geometry('GEOMETRY', srid=4326), nullable=False)
    elevation_avg = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CandidateHotspot(Base):
    """Community-discovered flood-prone locations from clustered verified reports."""
    __tablename__ = "candidate_hotspots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city = Column(String, nullable=False, index=True)
    road_segment_id = Column(UUID(as_uuid=True), ForeignKey("city_roads.id"), nullable=True)
    centroid = Column(Geometry('POINT', srid=4326), nullable=False)
    road_name = Column(String, nullable=True)
    report_count = Column(Integer, nullable=False)
    report_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    avg_water_depth = Column(String, nullable=True)
    avg_weather = Column(JSONB, nullable=True)
    date_first_report = Column(DateTime, nullable=True)
    date_last_report = Column(DateTime, nullable=True)
    status = Column(String, default="candidate", index=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    promoted_to_hotspot_name = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Community intelligence columns
    submitted_by = Column(UUID(as_uuid=True), nullable=True)
    submission_type = Column(String, default='automated')
    pin_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    pin_count = Column(Integer, default=0)
    avg_fhi = Column(Float, nullable=True)
    fhi_history_summary = Column(JSONB, nullable=True)
    groundsource_cluster_id = Column(UUID(as_uuid=True), nullable=True)
    historical_episode_count = Column(Integer, default=0)


class HistoricalFloodEpisode(Base):
    __tablename__ = "historical_flood_episodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city = Column(String(50), nullable=False, index=True)
    centroid = Column(Geometry('POINT', srid=4326), nullable=False)
    avg_area_km2 = Column(Float, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    article_count = Column(Integer, default=1)
    source_event_ids = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @hybrid_property
    def latitude(self):
        if self.centroid is not None:
            session = object_session(self)
            if session:
                return session.scalar(self.centroid.ST_Y())
        return None

    @hybrid_property
    def longitude(self):
        if self.centroid is not None:
            session = object_session(self)
            if session:
                return session.scalar(self.centroid.ST_X())
        return None


class GroundsourceCluster(Base):
    __tablename__ = "groundsource_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city = Column(String(50), nullable=False)
    centroid = Column(Geometry('POINT', srid=4326), nullable=False)
    episode_count = Column(Integer, nullable=False)
    total_article_count = Column(Integer, nullable=False)
    first_episode = Column(Date, nullable=False)
    last_episode = Column(Date, nullable=False)
    recency_score = Column(Float, nullable=True)
    avg_area_km2 = Column(Float, nullable=True)
    nearest_hotspot_name = Column(String, nullable=True)
    nearest_hotspot_distance_m = Column(Float, nullable=True)
    overlap_status = Column(String(20), nullable=False)
    confidence = Column(String(10), nullable=True)
    infra_signal = Column(String(20), nullable=True)
    admin_status = Column(String(20), default='pending')
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WatchAreaFhiHistory(Base):
    __tablename__ = "watch_area_fhi_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watch_area_id = Column(UUID(as_uuid=True), ForeignKey("watch_areas.id", ondelete="CASCADE"), nullable=False)
    fhi_score = Column(Float, nullable=False)
    fhi_level = Column(String(20), nullable=False)
    fhi_components = Column(JSONB, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

