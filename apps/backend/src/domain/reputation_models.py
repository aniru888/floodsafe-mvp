from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4

# ============================================================================
# REPUTATION MODELS
# ============================================================================

class ReputationHistory(BaseModel):
    """Reputation history entry"""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    action: str
    points_change: int
    new_total: int
    reason: Optional[str] = None
    metadata: str = "{}"  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class Badge(BaseModel):
    """Badge definition"""
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    description: Optional[str] = None
    icon: str = "🏆"
    category: str = "achievement"
    requirement_type: str
    requirement_value: int
    points_reward: int = 0
    sort_order: int = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class UserBadge(BaseModel):
    """User's earned badge"""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    badge_id: UUID
    earned_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# RESPONSE DTOs
# ============================================================================

class ReputationSummaryResponse(BaseModel):
    """Complete reputation summary for a user"""
    user_id: UUID
    points: int
    level: int
    reputation_score: int
    accuracy_rate: float
    streak_days: int
    next_level_points: int
    badges_earned: int
    total_badges: int

    model_config = ConfigDict(from_attributes=True)


class ReputationHistoryResponse(BaseModel):
    """Response DTO for reputation history"""
    id: UUID
    action: str
    points_change: int
    new_total: int
    reason: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BadgeResponse(BaseModel):
    """Response DTO for badge"""
    id: UUID
    key: str
    name: str
    description: Optional[str]
    icon: str
    category: str
    points_reward: int

    model_config = ConfigDict(from_attributes=True)


class BadgeWithProgressResponse(BaseModel):
    """Badge with user's progress toward earning it"""
    badge: BadgeResponse
    earned: bool
    earned_at: Optional[datetime] = None
    current_value: Optional[int] = None
    required_value: Optional[int] = None
    progress_percent: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class LeaderboardEntryResponse(BaseModel):
    """Single leaderboard entry with privacy controls"""
    rank: int
    display_name: str
    profile_photo_url: Optional[str] = None
    points: int
    level: int
    reputation_score: int
    verified_reports: int
    badges_count: int
    is_anonymous: bool

    model_config = ConfigDict(from_attributes=True)


class LeaderboardResponse(BaseModel):
    """Complete leaderboard with entries"""
    leaderboard_type: str
    updated_at: datetime
    entries: List[LeaderboardEntryResponse]
    current_user_rank: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# REQUEST DTOs
# ============================================================================

class PrivacySettingsUpdate(BaseModel):
    """Request DTO for updating privacy settings"""
    leaderboard_visible: Optional[bool] = None
    profile_public: Optional[bool] = None
    display_name: Optional[str] = Field(None, min_length=3, max_length=50)

    model_config = ConfigDict(from_attributes=True)


class ReportVerificationRequest(BaseModel):
    """Request DTO for verifying a report"""
    verified: bool
    quality_score: Optional[float] = Field(None, ge=0, le=100)
    notes: Optional[str] = Field(None, max_length=500)  # Admin verification notes

    model_config = ConfigDict(from_attributes=True)
