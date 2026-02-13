from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import UUID
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel, Field
import logging

from ..infrastructure.database import get_db
from ..infrastructure import models
from ..domain.models import UserCreate, UserUpdate, UserResponse
from .deps import get_current_user, get_current_admin_user
from geoalchemy2.functions import ST_DWithin, ST_MakePoint

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# SECURE PROFILE ENDPOINTS (use JWT, not URL param)
# ============================================================================

@router.get("/me/profile", response_model=UserResponse)
async def get_my_profile(
    current_user: models.User = Depends(get_current_user)
):
    """
    Get authenticated user's full profile.
    Requires authentication via Bearer token.
    """
    return current_user


@router.post("/me/tour-complete")
async def mark_tour_complete(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark the onboarding app tour as completed for the current user."""
    try:
        current_user.tour_completed_at = datetime.utcnow()
        db.commit()
        db.refresh(current_user)
        return {"success": True, "tour_completed_at": str(current_user.tour_completed_at)}
    except Exception as e:
        logger.error(f"Error marking tour complete: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to mark tour complete")


@router.patch("/me/profile", response_model=UserResponse)
async def update_my_profile(
    user_update: UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update authenticated user's profile.
    Users can only update their own profile.
    Role changes are ignored (users cannot change their own role).
    """
    try:
        # Get update data, excluding unset fields
        update_data = user_update.model_dump(exclude_unset=True)

        # SECURITY: Remove role from updates - users cannot change their own role
        if "role" in update_data:
            del update_data["role"]

        # Check for unique constraints if username or email is being updated
        if "username" in update_data:
            existing = db.query(models.User).filter(
                models.User.username == update_data["username"],
                models.User.id != current_user.id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Username already taken")

        if "email" in update_data:
            existing = db.query(models.User).filter(
                models.User.email == update_data["email"],
                models.User.id != current_user.id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")

        # Apply updates
        for field, value in update_data.items():
            setattr(current_user, field, value)

        db.commit()
        db.refresh(current_user)

        return current_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update profile")


# ============================================================================
# USER CRUD ENDPOINTS
# ============================================================================

@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    """
    try:
        # Check if user already exists
        existing_user = db.query(models.User).filter(
            (models.User.email == user.email) | (models.User.username == user.username)
        ).first()

        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already registered")

        new_user = models.User(
            username=user.username,
            email=user.email,
            role=user.role
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return new_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create user")

@router.get("/", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db)):
    """
    List all users.
    """
    try:
        users = db.query(models.User).all()
        return users
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get user profile by ID.
    """
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user")

@router.get("/stats/active-reporters", response_model=dict)
def get_active_reporters_count(db: Session = Depends(get_db)):
    """
    Get count of users who have made reports in the past 7 days.
    Active reporters must have reports_count > 0 AND have made at least one report in past week.
    """
    try:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        # Get users who have made reports in the past 7 days
        active_reporter_ids = db.query(models.Report.user_id).filter(
            models.Report.timestamp >= seven_days_ago
        ).distinct().all()

        active_reporter_ids = [uid[0] for uid in active_reporter_ids]

        # Count users with reports_count > 0 AND who made reports recently
        count = db.query(models.User).filter(
            and_(
                models.User.reports_count > 0,
                models.User.id.in_(active_reporter_ids) if active_reporter_ids else False
            )
        ).count()

        return {"count": count, "period_days": 7}
    except Exception as e:
        logger.error(f"Error counting active reporters: {e}")
        raise HTTPException(status_code=500, detail="Failed to count active reporters")

@router.get("/stats/nearby-reporters", response_model=dict)
def get_nearby_reporters_count(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0, le=50),
    db: Session = Depends(get_db)
):
    """
    Get count of users who have made reports within radius_km of the given location.
    Uses PostGIS ST_DWithin for efficient spatial queries.
    Radius is in kilometers, converted to meters for PostGIS.
    """
    try:
        radius_meters = radius_km * 1000  # Convert km to meters

        # Create a point for the query location (PostGIS format: POINT(lng lat))
        query_point = ST_MakePoint(longitude, latitude)

        # Find all reports within radius
        nearby_reports = db.query(models.Report.user_id).filter(
            ST_DWithin(
                models.Report.location,
                query_point,
                radius_meters,
                True  # Use spheroid for accurate distance calculation
            )
        ).distinct().all()

        nearby_user_ids = [uid[0] for uid in nearby_reports]

        # Count unique users who made those reports
        count = len(nearby_user_ids)

        return {
            "count": count,
            "radius_km": radius_km,
            "center": {"latitude": latitude, "longitude": longitude}
        }
    except Exception as e:
        logger.error(f"Error counting nearby reporters: {e}")
        raise HTTPException(status_code=500, detail="Failed to count nearby reporters")

@router.get("/leaderboard/top", response_model=List[UserResponse])
def get_leaderboard(limit: int = 10, db: Session = Depends(get_db)):
    """
    Get top users by points.
    """
    try:
        users = db.query(models.User).order_by(models.User.points.desc()).limit(limit).all()
        return users
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")

@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile and preferences.
    Requires authentication. Users can only update their own profile.
    Admins can update any user's profile.
    """
    try:
        # SECURITY: Authorization check - users can only update their own profile
        if str(current_user.id) != str(user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Can only update your own profile"
            )

        # Find the user to update
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update only the fields that are provided (not None)
        update_data = user_update.model_dump(exclude_unset=True)

        # SECURITY: Non-admins cannot change role
        if "role" in update_data and current_user.role != "admin":
            del update_data["role"]

        # Check for unique constraints if username or email is being updated
        if "username" in update_data:
            existing = db.query(models.User).filter(
                models.User.username == update_data["username"],
                models.User.id != user_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Username already taken")

        if "email" in update_data:
            existing = db.query(models.User).filter(
                models.User.email == update_data["email"],
                models.User.id != user_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")

        # Apply updates
        for field, value in update_data.items():
            setattr(user, field, value)

        db.commit()
        db.refresh(user)

        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update user")


# ============================================================================
# ADMIN ROLE MANAGEMENT
# ============================================================================

class RoleUpdateRequest(BaseModel):
    """Request body for updating a user's role."""
    new_role: str = Field(..., pattern="^(user|verified_reporter|moderator|admin)$")
    reason: str = Field(..., min_length=10, max_length=500)


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    role_update: RoleUpdateRequest,
    admin: models.User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update a user's role. Admin only.
    Creates audit trail entry in role_history table.
    """
    try:
        # Find the target user
        target_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent admins from changing their own role (safety measure)
        if target_user.id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")

        old_role = target_user.role
        new_role = role_update.new_role

        # No-op if role is the same
        if old_role == new_role:
            return target_user

        # Create audit trail entry
        role_history = models.RoleHistory(
            user_id=user_id,
            old_role=old_role,
            new_role=new_role,
            changed_by=admin.id,
            reason=role_update.reason
        )
        db.add(role_history)

        # Update role
        target_user.role = new_role

        # Set timestamps for role transitions
        if new_role == "verified_reporter" and not target_user.verified_reporter_since:
            target_user.verified_reporter_since = datetime.utcnow()
        elif new_role == "moderator" and not target_user.moderator_since:
            target_user.moderator_since = datetime.utcnow()

        db.commit()
        db.refresh(target_user)

        logger.info(f"Admin {admin.id} changed user {user_id} role: {old_role} -> {new_role}")
        return target_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update user role")
