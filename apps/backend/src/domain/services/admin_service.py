"""
Admin service — business logic for FloodSafe admin panel.
Handles dashboard stats, user management, report moderation, and analytics.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case

from src.infrastructure.models import (
    User, Report, Badge, UserBadge, ReputationHistory,
    RoleHistory, AdminAuditLog, SafetyCircle, ExternalAlert,
    Comment, ReportVote, AdminInvite
)
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

logger = logging.getLogger(__name__)


# =============================================================================
# AUDIT LOGGING
# =============================================================================

def log_admin_action(
    db: Session,
    admin_id: UUID,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AdminAuditLog:
    """Create an audit log entry for an admin action.
    NOTE: Does NOT commit. Caller must commit the transaction."""
    entry = AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


# =============================================================================
# DASHBOARD STATISTICS
# =============================================================================

def get_dashboard_stats(db: Session) -> Dict[str, Any]:
    """Get platform-wide statistics for the admin dashboard."""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    total_users = db.query(func.count(User.id)).scalar() or 0
    new_users_7d = db.query(func.count(User.id)).filter(
        User.created_at >= seven_days_ago
    ).scalar() or 0

    total_reports = db.query(func.count(Report.id)).scalar() or 0
    reports_7d = db.query(func.count(Report.id)).filter(
        Report.timestamp >= seven_days_ago
    ).scalar() or 0

    verified_reports = db.query(func.count(Report.id)).filter(
        Report.verified == True
    ).scalar() or 0
    unverified_reports = db.query(func.count(Report.id)).filter(
        Report.verified == False,
        Report.archived_at == None
    ).scalar() or 0

    # Role distribution
    role_counts = db.query(
        User.role, func.count(User.id)
    ).group_by(User.role).all()
    roles = {role: count for role, count in role_counts}

    # Active reporters (reported in last 7 days)
    active_reporters = db.query(func.count(func.distinct(Report.user_id))).filter(
        Report.timestamp >= seven_days_ago
    ).scalar() or 0

    # Safety circles
    total_circles = db.query(func.count(SafetyCircle.id)).scalar() or 0

    # Badges awarded
    total_badges_awarded = db.query(func.count(UserBadge.id)).scalar() or 0

    # Comments
    total_comments = db.query(func.count(Comment.id)).scalar() or 0

    return {
        "users": {
            "total": total_users,
            "new_7d": new_users_7d,
            "roles": roles,
            "active_reporters_7d": active_reporters,
        },
        "reports": {
            "total": total_reports,
            "new_7d": reports_7d,
            "verified": verified_reports,
            "pending_verification": unverified_reports,
        },
        "community": {
            "safety_circles": total_circles,
            "badges_awarded": total_badges_awarded,
            "comments": total_comments,
        },
        "generated_at": now.isoformat(),
    }


# =============================================================================
# USER MANAGEMENT
# =============================================================================

ALLOWED_SORT_FIELDS = {"created_at", "username", "email", "role", "points", "reputation_score"}


# =============================================================================
# REPORT CREATION (ADMIN)
# =============================================================================

# City bounding boxes for coordinate validation
CITY_BOUNDS = {
    "delhi": {"min_lat": 28.40, "max_lat": 28.88, "min_lng": 76.84, "max_lng": 77.35},
    "bangalore": {"min_lat": 12.75, "max_lat": 13.20, "min_lng": 77.35, "max_lng": 77.80},
    "yogyakarta": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
    "singapore": {"min_lat": 1.15, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    "indore": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
}


def validate_city_bounds(lat: float, lng: float, city: str) -> bool:
    """Validate that coordinates fall within the city's bounding box."""
    bounds = CITY_BOUNDS.get(city)
    if not bounds:
        return False
    return (bounds["min_lat"] <= lat <= bounds["max_lat"] and
            bounds["min_lng"] <= lng <= bounds["max_lng"])


def admin_create_report(
    db: Session, admin_id: UUID, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a report as admin — no photo required, auto-verified."""
    # Validate coordinates within city bounds
    if not validate_city_bounds(data["latitude"], data["longitude"], data["city"]):
        return {"error": f"Coordinates ({data['latitude']}, {data['longitude']}) are outside {data['city']} bounds"}

    # Create PostGIS point
    point = from_shape(Point(data["longitude"], data["latitude"]), srid=4326)

    report = Report(
        user_id=admin_id,
        description=data["description"],
        location=point,
        media_url=None,  # No photo required
        verified=True,
        verified_at=datetime.utcnow(),
        admin_created=True,
        source=data.get("source", "field_observation"),
        water_depth=data.get("water_depth"),
        vehicle_passability=data.get("vehicle_passability"),
        quality_score=75.0,  # Admin reports get a default quality score
    )
    db.add(report)

    log_admin_action(
        db, admin_id, "create_report", "report", None,
        json.dumps({"city": data["city"], "source": data.get("source"), "description": data["description"][:100]})
    )

    db.commit()
    db.refresh(report)
    return {"success": True, "report_id": str(report.id), "message": "Admin report created"}


def upsert_admin_comment(
    db: Session, report_id: UUID, admin_id: UUID, notes: str, comment_type: str
) -> Comment:
    """Create or update an admin verification comment on a report."""
    existing = db.query(Comment).filter(
        Comment.report_id == report_id,
        Comment.comment_type.in_(["admin_verification", "admin_rejection"])
    ).first()

    if existing:
        existing.content = notes
        existing.comment_type = comment_type
        existing.created_at = datetime.utcnow()
        return existing
    else:
        comment = Comment(
            report_id=report_id,
            user_id=admin_id,
            content=notes,
            comment_type=comment_type,
        )
        db.add(comment)
        return comment


def list_users_filtered(
    db: Session,
    role: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    per_page: int = 20,
) -> Dict[str, Any]:
    """List users with optional filtering, searching, and pagination."""
    # Validate sort field against allowlist
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "created_at"

    query = db.query(User)

    if role:
        query = query.filter(User.role == role)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term),
                User.display_name.ilike(search_term),
            )
        )

    # Sorting
    sort_col = getattr(User, sort_by, User.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "users": [_user_to_dict(u) for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


def get_user_detail(db: Session, user_id: UUID) -> Optional[Dict[str, Any]]:
    """Get full user detail for admin view."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # Get user's badges
    user_badges = db.query(UserBadge, Badge).join(
        Badge, UserBadge.badge_id == Badge.id
    ).filter(UserBadge.user_id == user_id).all()

    # Get recent role history
    role_history = db.query(RoleHistory).filter(
        RoleHistory.user_id == user_id
    ).order_by(desc(RoleHistory.created_at)).limit(10).all()

    detail = _user_to_dict(user)
    detail["badges_detail"] = [
        {
            "badge_key": badge.key,
            "badge_name": badge.name,
            "badge_icon": badge.icon,
            "earned_at": ub.earned_at.isoformat() if ub.earned_at else None,
        }
        for ub, badge in user_badges
    ]
    detail["role_history"] = [
        {
            "old_role": rh.old_role,
            "new_role": rh.new_role,
            "reason": rh.reason,
            "created_at": rh.created_at.isoformat() if rh.created_at else None,
        }
        for rh in role_history
    ]
    return detail


def ban_user(
    db: Session, user_id: UUID, admin_id: UUID, reason: str
) -> Dict[str, Any]:
    """Ban a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    if user.role == "admin":
        return {"error": "Cannot ban an admin user"}

    # Store old role, set to 'banned'
    old_role = user.role
    user.role = "banned"

    # Create role history entry
    role_entry = RoleHistory(
        user_id=user_id,
        old_role=old_role,
        new_role="banned",
        changed_by=admin_id,
        reason=reason,
    )
    db.add(role_entry)

    # Audit log
    log_admin_action(db, admin_id, "ban_user", "user", str(user_id), reason)

    db.commit()
    return {"success": True, "message": f"User {user.username} has been banned"}


def unban_user(
    db: Session, user_id: UUID, admin_id: UUID
) -> Dict[str, Any]:
    """Unban a user account — restores to 'user' role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    if user.role != "banned":
        return {"error": "User is not banned"}

    user.role = "user"

    role_entry = RoleHistory(
        user_id=user_id,
        old_role="banned",
        new_role="user",
        changed_by=admin_id,
        reason="Unbanned by admin",
    )
    db.add(role_entry)

    log_admin_action(db, admin_id, "unban_user", "user", str(user_id))
    db.commit()
    return {"success": True, "message": f"User {user.username} has been unbanned"}


def update_user_role(
    db: Session, user_id: UUID, admin_id: UUID, new_role: str, reason: str
) -> Dict[str, Any]:
    """Change a user's role with audit trail."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    old_role = user.role
    user.role = new_role

    # Timestamps for role transitions
    if new_role == "verified_reporter":
        user.verified_reporter_since = user.verified_reporter_since or datetime.utcnow()
    elif new_role == "moderator":
        user.moderator_since = user.moderator_since or datetime.utcnow()

    role_entry = RoleHistory(
        user_id=user_id,
        old_role=old_role,
        new_role=new_role,
        changed_by=admin_id,
        reason=reason,
    )
    db.add(role_entry)

    log_admin_action(
        db, admin_id, "change_role", "user", str(user_id),
        json.dumps({"old": old_role, "new": new_role, "reason": reason})
    )

    db.commit()
    return {"success": True, "old_role": old_role, "new_role": new_role}


def delete_user(
    db: Session, user_id: UUID, admin_id: UUID, reason: str
) -> Dict[str, Any]:
    """Delete a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    if user.role == "admin":
        return {"error": "Cannot delete an admin user"}

    username = user.username
    log_admin_action(
        db, admin_id, "delete_user", "user", str(user_id),
        json.dumps({"username": username, "reason": reason})
    )

    db.delete(user)
    db.commit()
    return {"success": True, "message": f"User {username} has been deleted"}


# =============================================================================
# REPORT MODERATION
# =============================================================================

def list_reports_filtered(
    db: Session,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Dict[str, Any]:
    """List reports with filtering and pagination."""
    query = db.query(Report)

    if status == "verified":
        query = query.filter(Report.verified == True)
    elif status == "unverified":
        query = query.filter(Report.verified == False, Report.archived_at == None)
    elif status == "archived":
        query = query.filter(Report.archived_at != None)

    if search:
        query = query.filter(Report.description.ilike(f"%{search}%"))

    query = query.order_by(desc(Report.timestamp))
    total = query.count()
    reports = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "reports": [_report_to_dict(r) for r in reports],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


def admin_verify_report(
    db: Session, report_id: UUID, admin_id: UUID, verified: bool, reason: Optional[str] = None
) -> Dict[str, Any]:
    """Verify or reject a report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        return {"error": "Report not found"}

    report.verified = verified
    if verified:
        report.verified_at = datetime.utcnow()

    action = "verify_report" if verified else "reject_report"
    log_admin_action(db, admin_id, action, "report", str(report_id), reason)
    db.commit()
    return {"success": True, "verified": verified}


def admin_archive_report(
    db: Session, report_id: UUID, admin_id: UUID
) -> Dict[str, Any]:
    """Force-archive a report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        return {"error": "Report not found"}

    report.archived_at = datetime.utcnow()
    log_admin_action(db, admin_id, "archive_report", "report", str(report_id))
    db.commit()
    return {"success": True, "message": "Report archived"}


def admin_delete_report(
    db: Session, report_id: UUID, admin_id: UUID, reason: str
) -> Dict[str, Any]:
    """Delete a report permanently."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        return {"error": "Report not found"}

    log_admin_action(
        db, admin_id, "delete_report", "report", str(report_id),
        json.dumps({"description": report.description[:100], "reason": reason})
    )
    db.delete(report)
    db.commit()
    return {"success": True, "message": "Report deleted"}


# =============================================================================
# BADGE & AMBASSADOR MANAGEMENT
# =============================================================================

def admin_create_badge(
    db: Session, admin_id: UUID, badge_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a new badge."""
    existing = db.query(Badge).filter(Badge.key == badge_data["key"]).first()
    if existing:
        return {"error": f"Badge with key '{badge_data['key']}' already exists"}

    badge = Badge(
        key=badge_data["key"],
        name=badge_data["name"],
        description=badge_data.get("description", ""),
        icon=badge_data.get("icon", "🏆"),
        category=badge_data.get("category", "achievement"),
        requirement_type=badge_data.get("requirement_type", "manual"),
        requirement_value=badge_data.get("requirement_value", 0),
        points_reward=badge_data.get("points_reward", 0),
    )
    db.add(badge)
    log_admin_action(db, admin_id, "create_badge", "badge", badge_data["key"])
    db.commit()
    db.refresh(badge)
    return {"success": True, "badge": _badge_to_dict(badge)}


def admin_update_badge(
    db: Session, badge_id: UUID, admin_id: UUID, updates: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing badge."""
    badge = db.query(Badge).filter(Badge.id == badge_id).first()
    if not badge:
        return {"error": "Badge not found"}

    for field in ["name", "description", "icon", "category", "points_reward", "is_active"]:
        if field in updates:
            setattr(badge, field, updates[field])

    log_admin_action(db, admin_id, "update_badge", "badge", str(badge_id))
    db.commit()
    db.refresh(badge)
    return {"success": True, "badge": _badge_to_dict(badge)}


def admin_award_badge(
    db: Session, admin_id: UUID, user_id: UUID, badge_id: UUID
) -> Dict[str, Any]:
    """Award a badge to a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    badge = db.query(Badge).filter(Badge.id == badge_id).first()
    if not badge:
        return {"error": "Badge not found"}

    existing = db.query(UserBadge).filter(
        UserBadge.user_id == user_id, UserBadge.badge_id == badge_id
    ).first()
    if existing:
        return {"error": "User already has this badge"}

    user_badge = UserBadge(user_id=user_id, badge_id=badge_id)
    db.add(user_badge)

    # Award points
    if badge.points_reward > 0:
        user.points += badge.points_reward

    log_admin_action(
        db, admin_id, "award_badge", "user_badge",
        json.dumps({"user_id": str(user_id), "badge_id": str(badge_id)})
    )
    db.commit()
    return {"success": True, "message": f"Badge '{badge.name}' awarded to {user.username}"}


def get_ambassador_candidates(db: Session, min_reputation: int = 50) -> List[Dict[str, Any]]:
    """Get users who qualify as ambassador candidates based on reputation."""
    candidates = db.query(User).filter(
        User.reputation_score >= min_reputation,
        User.role == "user",
        User.reports_count >= 3,
    ).order_by(desc(User.reputation_score)).limit(50).all()

    return [_user_to_dict(u) for u in candidates]


def promote_to_ambassador(
    db: Session, user_id: UUID, admin_id: UUID
) -> Dict[str, Any]:
    """Promote a user to verified_reporter (ambassador) role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    if user.role in ("verified_reporter", "moderator", "admin"):
        return {"error": f"User already has role: {user.role}"}

    old_role = user.role
    user.role = "verified_reporter"
    user.verified_reporter_since = datetime.utcnow()

    role_entry = RoleHistory(
        user_id=user_id,
        old_role=old_role,
        new_role="verified_reporter",
        changed_by=admin_id,
        reason="Promoted to ambassador via admin panel",
    )
    db.add(role_entry)

    log_admin_action(db, admin_id, "promote_ambassador", "user", str(user_id))
    db.commit()
    return {"success": True, "message": f"User {user.username} promoted to ambassador"}


# =============================================================================
# ANALYTICS
# =============================================================================

def get_analytics_reports(db: Session, days: int = 30) -> Dict[str, Any]:
    """Get report analytics over time."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Daily report counts
    daily = db.query(
        func.date(Report.timestamp).label("date"),
        func.count(Report.id).label("count"),
        func.sum(case((Report.verified == True, 1), else_=0)).label("verified"),
    ).filter(
        Report.timestamp >= cutoff
    ).group_by(
        func.date(Report.timestamp)
    ).order_by(
        func.date(Report.timestamp)
    ).all()

    return {
        "period_days": days,
        "daily": [
            {
                "date": str(d.date),
                "count": d.count,
                "verified": int(d.verified or 0),
            }
            for d in daily
        ],
    }


def get_analytics_users(db: Session, days: int = 30) -> Dict[str, Any]:
    """Get user growth analytics over time."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    daily = db.query(
        func.date(User.created_at).label("date"),
        func.count(User.id).label("count"),
    ).filter(
        User.created_at >= cutoff
    ).group_by(
        func.date(User.created_at)
    ).order_by(
        func.date(User.created_at)
    ).all()

    return {
        "period_days": days,
        "daily": [
            {"date": str(d.date), "count": d.count}
            for d in daily
        ],
    }


def get_analytics_cities(db: Session) -> Dict[str, Any]:
    """Get per-city user and report breakdown."""
    city_users = db.query(
        User.city_preference, func.count(User.id)
    ).filter(
        User.city_preference != None
    ).group_by(User.city_preference).all()

    return {
        "cities": {
            city: {"users": count}
            for city, count in city_users
        }
    }


# =============================================================================
# SYSTEM & AUDIT
# =============================================================================

def get_audit_log(
    db: Session, page: int = 1, per_page: int = 50
) -> Dict[str, Any]:
    """Get paginated admin audit log."""
    query = db.query(AdminAuditLog).order_by(desc(AdminAuditLog.created_at))
    total = query.count()
    entries = query.offset((page - 1) * per_page).limit(per_page).all()

    # Get admin usernames
    admin_ids = list(set(e.admin_id for e in entries if e.admin_id))
    admin_map = {}
    if admin_ids:
        admins = db.query(User).filter(User.id.in_(admin_ids)).all()
        admin_map = {str(a.id): a.username for a in admins}

    return {
        "entries": [
            {
                "id": str(e.id),
                "admin_id": str(e.admin_id) if e.admin_id else None,
                "admin_username": admin_map.get(str(e.admin_id), "Unknown"),
                "action": e.action,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# =============================================================================
# HELPERS
# =============================================================================

def _user_to_dict(user: User) -> Dict[str, Any]:
    """Convert User model to dictionary for admin API responses."""
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "auth_provider": user.auth_provider,
        "points": user.points,
        "level": user.level,
        "reputation_score": user.reputation_score,
        "reports_count": user.reports_count,
        "verified_reports_count": user.verified_reports_count,
        "streak_days": user.streak_days,
        "city_preference": user.city_preference,
        "profile_complete": user.profile_complete,
        "leaderboard_visible": user.leaderboard_visible,
        "profile_photo_url": user.profile_photo_url,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def _report_to_dict(report: Report) -> Dict[str, Any]:
    """Convert Report model to dictionary for admin API responses."""
    return {
        "id": str(report.id),
        "user_id": str(report.user_id) if report.user_id else None,
        "description": report.description,
        "media_url": report.media_url,
        "verified": report.verified,
        "verification_score": report.verification_score,
        "upvotes": report.upvotes,
        "downvotes": report.downvotes,
        "quality_score": report.quality_score,
        "water_depth": report.water_depth,
        "vehicle_passability": report.vehicle_passability,
        "timestamp": report.timestamp.isoformat() if report.timestamp else None,
        "verified_at": report.verified_at.isoformat() if report.verified_at else None,
        "archived_at": report.archived_at.isoformat() if report.archived_at else None,
    }


def _badge_to_dict(badge: Badge) -> Dict[str, Any]:
    """Convert Badge model to dictionary."""
    return {
        "id": str(badge.id),
        "key": badge.key,
        "name": badge.name,
        "description": badge.description,
        "icon": badge.icon,
        "category": badge.category,
        "requirement_type": badge.requirement_type,
        "requirement_value": badge.requirement_value,
        "points_reward": badge.points_reward,
        "is_active": badge.is_active,
    }


# =============================================================================
# INVITE MANAGEMENT
# =============================================================================

def create_invite(
    db: Session,
    admin_id: UUID,
    email_hint: Optional[str] = None,
) -> "AdminInvite":
    """Generate a one-time admin invite code (48h expiry)."""
    import secrets
    code = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=48)

    invite = AdminInvite(
        code=code,
        created_by=admin_id,
        email_hint=email_hint,
        expires_at=expires_at,
    )
    db.add(invite)
    return invite


def list_invites(db: Session) -> List[Dict[str, Any]]:
    """List all admin invites with creator/redeemer info."""
    invites = db.query(AdminInvite).order_by(AdminInvite.created_at.desc()).all()

    # Batch-load usernames to avoid N+1 queries
    user_ids = set()
    for inv in invites:
        if inv.created_by:
            user_ids.add(inv.created_by)
        if inv.used_by:
            user_ids.add(inv.used_by)
    user_map: Dict[UUID, str] = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.username for u in users}

    result = []
    for inv in invites:
        result.append({
            "id": str(inv.id),
            "code": inv.code,
            "email_hint": inv.email_hint,
            "created_by_username": user_map.get(inv.created_by, "unknown") if inv.created_by else "unknown",
            "used_by_username": user_map.get(inv.used_by) if inv.used_by else None,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "is_expired": inv.expires_at < datetime.utcnow() if inv.expires_at else True,
            "is_used": inv.used_by is not None,
        })
    return result


def revoke_invite(db: Session, code: str) -> None:
    """Delete an unused invite code. Raises if not found or already used."""
    invite = db.query(AdminInvite).filter(AdminInvite.code == code).first()
    if not invite:
        raise ValueError("Invite not found")
    if invite.used_by:
        raise ValueError("Cannot revoke — invite already used")
    db.delete(invite)


def redeem_invite(
    db: Session,
    code: str,
    email: str,
    password: str,
) -> User:
    """
    Redeem an invite code: validate, find user, set admin role + password_hash.
    Raises ValueError with descriptive message on failure.
    """
    from src.domain.services.security import hash_password

    invite = db.query(AdminInvite).filter(AdminInvite.code == code).first()
    if not invite or invite.used_by is not None:
        raise ValueError("Invalid or already-used invite code")
    if invite.expires_at < datetime.utcnow():
        raise ValueError("Invite code has expired")
    if invite.email_hint and invite.email_hint.lower() != email.lower():
        raise ValueError("This invite is restricted to a different email")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise ValueError("No FloodSafe account found with this email. Please sign up first.")

    user.role = "admin"
    user.password_hash = hash_password(password)
    invite.used_by = user.id
    return user
