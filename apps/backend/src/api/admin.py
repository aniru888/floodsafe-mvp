"""
Admin panel API endpoints for FloodSafe.
Provides platform management capabilities for administrators.
Separate login endpoint with environment-variable credentials.
"""
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.infrastructure.models import User, Badge, AdminInvite, GroundsourceCluster, CandidateHotspot, WatchArea
from src.api.deps import get_current_admin_user
from src.core.config import settings
from src.domain.services.security import (
    create_access_token, create_refresh_token, verify_password, hash_password
)
from src.domain.services import admin_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class AdminLoginRequest(BaseModel):
    """Admin login credentials."""
    email: str = Field(..., description="Admin email address")
    password: str = Field(..., description="Admin password")


class AdminLoginResponse(BaseModel):
    """Admin login response with JWT tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RoleUpdateRequest(BaseModel):
    """Request to change a user's role."""
    new_role: str = Field(..., pattern="^(user|verified_reporter|moderator|admin|banned)$")
    reason: str = Field(..., min_length=5, max_length=500)


class BanRequest(BaseModel):
    """Request to ban a user."""
    reason: str = Field(..., min_length=5, max_length=500)


class DeleteRequest(BaseModel):
    """Request to delete a user or report."""
    reason: str = Field(..., min_length=5, max_length=500)


class VerifyReportRequest(BaseModel):
    """Request to verify or reject a report."""
    verified: bool
    reason: Optional[str] = None


class CreateBadgeRequest(BaseModel):
    """Request to create a new badge."""
    key: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field("", max_length=500)
    icon: str = Field("🏆", max_length=10)
    category: str = Field("achievement", max_length=50)
    requirement_type: str = Field("manual", max_length=50)
    requirement_value: int = Field(0, ge=0)
    points_reward: int = Field(0, ge=0)


class UpdateBadgeRequest(BaseModel):
    """Request to update a badge."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=10)
    category: Optional[str] = Field(None, max_length=50)
    points_reward: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class AwardBadgeRequest(BaseModel):
    """Request to award a badge to a user."""
    user_id: str = Field(..., description="Target user UUID")
    badge_id: str = Field(..., description="Badge UUID")


class AdminCreateReportRequest(BaseModel):
    """Admin request to create a report without photo."""
    description: str = Field(..., min_length=10, max_length=500)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str = Field(..., pattern="^(delhi|bangalore|yogyakarta|singapore|indore)$")
    water_depth: Optional[str] = Field(None, pattern="^(ankle|knee|waist|chest)$")
    vehicle_passability: Optional[str] = Field(None, pattern="^(all|large_vehicles|none)$")
    source: str = Field("field_observation", pattern="^(field_observation|government_data|phone_report)$")
    admin_notes: Optional[str] = Field(None, max_length=500)


class CreateInviteRequest(BaseModel):
    """Request to create an admin invite."""
    email_hint: Optional[str] = Field(None, description="Restrict invite to this email")


class CreateInviteResponse(BaseModel):
    """Response with generated invite link."""
    code: str
    invite_url: str
    email_hint: Optional[str]
    expires_at: str


class InviteListItem(BaseModel):
    """Invite item for listing."""
    id: str
    code: str
    email_hint: Optional[str]
    created_by_username: str
    used_by_username: Optional[str]
    expires_at: str
    created_at: str
    is_expired: bool
    is_used: bool


class AdminRegisterRequest(BaseModel):
    """Request to register as admin via invite code."""
    code: str = Field(..., min_length=10)
    email: str = Field(..., description="Must match existing FloodSafe account")
    password: str = Field(..., min_length=8, max_length=128)


class ClusterReviewRequest(BaseModel):
    """Request to promote or dismiss a Groundsource cluster."""
    action: str = Field(..., pattern="^(promote|dismiss)$", description="'promote' or 'dismiss'")
    dismiss_reason: Optional[str] = Field(None, max_length=500)


class PinRelocateRequest(BaseModel):
    """Request to relocate a personal pin to corrected coordinates."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    reason: str = Field(..., min_length=5, max_length=500)


# =============================================================================
# ADMIN LOGIN (separate from regular auth)
# =============================================================================

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest, req: Request, db: Session = Depends(get_db)):
    """
    Admin login with two-tier auth:
    1. DB-based: user.role == 'admin' + user.password_hash
    2. Env-var fallback: ADMIN_EMAIL + ADMIN_PASSWORD_HASH (bootstrap)
    """
    from src.api.deps import check_rate_limit

    check_rate_limit(f"admin_login:{req.client.host}", max_requests=5, window_seconds=300)

    # Reject empty credentials immediately
    if not request.email or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    admin_user = None

    # Tier 1: DB-based admin auth
    user = db.query(User).filter(User.email == request.email).first()
    if user and user.role == "admin" and user.password_hash:
        if verify_password(request.password, user.password_hash):
            admin_user = user

    # Tier 2: Env-var fallback (bootstrap / recovery)
    if not admin_user:
        if (settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD_HASH
                and request.email == settings.ADMIN_EMAIL
                and verify_password(request.password, settings.ADMIN_PASSWORD_HASH)):
            admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
            if admin_user and admin_user.role != "admin":
                admin_user.role = "admin"
                db.commit()

    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    access_token = create_access_token(data={"sub": str(admin_user.id)})
    refresh_token_str, _ = create_refresh_token(str(admin_user.id))

    return AdminLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(admin_user.id),
            "username": admin_user.username,
            "email": admin_user.email,
            "role": admin_user.role,
        },
    )


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Get platform-wide statistics for the admin dashboard."""
    return admin_service.get_dashboard_stats(db)


# =============================================================================
# USER MANAGEMENT
# =============================================================================

@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    search: Optional[str] = Query(None, description="Search username/email"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List all users with filtering, searching, and pagination."""
    return admin_service.list_users_filtered(
        db, role=role, search=search, sort_by=sort_by,
        sort_order=sort_order, page=page, per_page=per_page
    )


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Get full user detail including badges and role history."""
    detail = admin_service.get_user_detail(db, user_id)
    if not detail:
        raise HTTPException(status_code=404, detail="User not found")
    return detail


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    role_update: RoleUpdateRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Change a user's role with audit trail."""
    result = admin_service.update_user_role(
        db, user_id, admin.id, role_update.new_role, role_update.reason
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.patch("/users/{user_id}/ban")
async def ban_user(
    user_id: UUID,
    ban_req: BanRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Ban a user account."""
    result = admin_service.ban_user(db, user_id, admin.id, ban_req.reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.patch("/users/{user_id}/unban")
async def unban_user(
    user_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Unban a user account."""
    result = admin_service.unban_user(db, user_id, admin.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    delete_req: DeleteRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Delete a user account permanently."""
    result = admin_service.delete_user(db, user_id, admin.id, delete_req.reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# =============================================================================
# REPORT MODERATION
# =============================================================================

@router.post("/reports")
async def admin_create_report(
    req: AdminCreateReportRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Create a report as admin without photo requirement."""
    result = admin_service.admin_create_report(db, admin.id, req.model_dump())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/reports")
async def list_reports(
    status: Optional[str] = Query(None, description="Filter: verified/unverified/archived"),
    search: Optional[str] = Query(None, description="Search description"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List all reports with filtering and pagination."""
    return admin_service.list_reports_filtered(
        db, status=status, search=search, page=page, per_page=per_page
    )


@router.patch("/reports/{report_id}/verify")
async def verify_report(
    report_id: UUID,
    req: VerifyReportRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Verify or reject a report."""
    result = admin_service.admin_verify_report(db, report_id, admin.id, req.verified, req.reason)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.patch("/reports/{report_id}/archive")
async def archive_report(
    report_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Force-archive a report."""
    result = admin_service.admin_archive_report(db, report_id, admin.id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: UUID,
    delete_req: DeleteRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Delete a report permanently."""
    result = admin_service.admin_delete_report(db, report_id, admin.id, delete_req.reason)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =============================================================================
# BADGE & AMBASSADOR MANAGEMENT
# =============================================================================

@router.get("/badges")
async def list_badges(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List all badges."""
    badges = db.query(Badge).order_by(Badge.sort_order).all()
    return [admin_service._badge_to_dict(b) for b in badges]


@router.post("/badges")
async def create_badge(
    req: CreateBadgeRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Create a new badge."""
    result = admin_service.admin_create_badge(db, admin.id, req.model_dump())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.patch("/badges/{badge_id}")
async def update_badge(
    badge_id: UUID,
    req: UpdateBadgeRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Update an existing badge."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = admin_service.admin_update_badge(db, badge_id, admin.id, updates)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/badges/award")
async def award_badge(
    req: AwardBadgeRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Award a badge to a specific user."""
    result = admin_service.admin_award_badge(
        db, admin.id, UUID(req.user_id), UUID(req.badge_id)
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/ambassadors")
async def get_ambassador_candidates(
    min_reputation: int = Query(50, ge=0),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Get users who qualify as ambassador candidates."""
    return admin_service.get_ambassador_candidates(db, min_reputation)


@router.post("/ambassadors/{user_id}/promote")
async def promote_to_ambassador(
    user_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Promote a user to verified_reporter (ambassador) role."""
    result = admin_service.promote_to_ambassador(db, user_id, admin.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/reports")
async def get_analytics_reports(
    days: int = Query(30, ge=1, le=365),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Get report analytics over time."""
    return admin_service.get_analytics_reports(db, days)


@router.get("/analytics/users")
async def get_analytics_users(
    days: int = Query(30, ge=1, le=365),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Get user growth analytics over time."""
    return admin_service.get_analytics_users(db, days)


@router.get("/analytics/cities")
async def get_analytics_cities(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Get per-city statistics breakdown."""
    return admin_service.get_analytics_cities(db)


# =============================================================================
# SYSTEM & AUDIT LOG
# =============================================================================

@router.get("/system/health")
async def admin_health_check(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Extended health check for admin panel."""
    from sqlalchemy import text

    health = {
        "status": "healthy",
        "database": "unknown",
        "config": {
            "production_mode": settings.is_production,
            "cors_origins_count": len(settings.BACKEND_CORS_ORIGINS),
            "ml_enabled": settings.ML_ENABLED,
            "rss_feeds_enabled": settings.RSS_FEEDS_ENABLED,
            "whatsapp_configured": bool(settings.TWILIO_ACCOUNT_SID),
            "meta_whatsapp_configured": bool(settings.META_WHATSAPP_TOKEN),
            "floodhub_configured": bool(settings.GOOGLE_FLOODHUB_API_KEY),
            "sendgrid_configured": bool(settings.SENDGRID_API_KEY),
            "firebase_configured": bool(settings.FIREBASE_PROJECT_ID),
        },
    }

    try:
        db.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as e:
        health["database"] = f"error: {str(e)}"
        health["status"] = "degraded"

    return health


@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """View admin action audit trail."""
    return admin_service.get_audit_log(db, page, per_page)


# =============================================================================
# ADMIN INVITES
# =============================================================================

@router.post("/invites", response_model=CreateInviteResponse)
async def create_invite(
    request: CreateInviteRequest,
    req: Request,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Generate a one-time admin invite code (48h expiry)."""
    invite = admin_service.create_invite(db, admin.id, request.email_hint)

    admin_service.log_admin_action(
        db, admin.id, "create_invite",
        target_type="invite", target_id=invite.code,
        details=json.dumps({"email_hint": request.email_hint}),
        ip_address=req.client.host if req.client else None,
    )
    db.commit()

    frontend_url = getattr(settings, 'FRONTEND_URL', "https://floodsafe.live")
    invite_url = f"{frontend_url}/admin/register?code={invite.code}"

    return CreateInviteResponse(
        code=invite.code,
        invite_url=invite_url,
        email_hint=request.email_hint,
        expires_at=invite.expires_at.isoformat(),
    )


@router.get("/invites")
async def list_invites(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List all admin invites (active and used)."""
    return admin_service.list_invites(db)


@router.delete("/invites/{code}")
async def revoke_invite(
    code: str,
    req: Request,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Revoke an unused invite code."""
    try:
        admin_service.revoke_invite(db, code)
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e))

    admin_service.log_admin_action(
        db, admin.id, "revoke_invite",
        target_type="invite", target_id=code,
        ip_address=req.client.host if req.client else None,
    )
    db.commit()

    return {"status": "revoked"}


@router.post("/register")
async def register_admin(
    request: AdminRegisterRequest,
    req: Request,
    db: Session = Depends(get_db),
):
    """
    Redeem an invite code to become an admin.
    Public endpoint — no auth required, but needs valid invite code.
    """
    from src.api.deps import check_rate_limit
    check_rate_limit(f"admin_register:{req.client.host}", max_requests=5, window_seconds=300)

    try:
        user = admin_service.redeem_invite(db, request.code, request.email, request.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    admin_service.log_admin_action(
        db, user.id, "admin_registered",
        target_type="invite", target_id=request.code,
        details=json.dumps({"email": request.email}),
        ip_address=req.client.host if req.client else None,
    )
    db.commit()

    return {"status": "ok", "message": "Admin access granted. You can now log in at /admin/login."}


# =============================================================================
# GROUNDSOURCE CLUSTER MANAGEMENT
# =============================================================================

@router.get("/clusters")
async def list_clusters(
    city: Optional[str] = Query(None, description="Filter by city"),
    cluster_status: str = Query("pending", description="Filter by admin_status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List Groundsource clusters for admin review."""
    from sqlalchemy import func as sa_func

    query = db.query(GroundsourceCluster).filter(
        GroundsourceCluster.admin_status == cluster_status
    )
    if city:
        query = query.filter(GroundsourceCluster.city == city)

    total = query.count()
    clusters = (
        query.order_by(GroundsourceCluster.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for c in clusters:
        # Extract lat/lng from PostGIS geometry safely
        lat = db.scalar(sa_func.ST_Y(c.centroid)) if c.centroid is not None else None
        lng = db.scalar(sa_func.ST_X(c.centroid)) if c.centroid is not None else None
        items.append({
            "id": str(c.id),
            "city": c.city,
            "latitude": lat,
            "longitude": lng,
            "episode_count": c.episode_count,
            "total_article_count": c.total_article_count,
            "first_episode": c.first_episode.isoformat() if c.first_episode else None,
            "last_episode": c.last_episode.isoformat() if c.last_episode else None,
            "recency_score": c.recency_score,
            "avg_area_km2": c.avg_area_km2,
            "nearest_hotspot_name": c.nearest_hotspot_name,
            "nearest_hotspot_distance_m": c.nearest_hotspot_distance_m,
            "overlap_status": c.overlap_status,
            "confidence": c.confidence,
            "infra_signal": c.infra_signal,
            "admin_status": c.admin_status,
            "admin_notes": c.admin_notes,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.patch("/clusters/{cluster_id}/review")
async def review_cluster(
    cluster_id: UUID,
    req: ClusterReviewRequest,
    request: Request,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Promote or dismiss a Groundsource cluster.

    - promote: creates a CandidateHotspot from cluster data, sets admin_status='promoted'
    - dismiss: sets admin_status='dismissed', records reason in admin_notes
    """
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    cluster = db.query(GroundsourceCluster).filter(GroundsourceCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    if cluster.admin_status not in ("pending",):
        raise HTTPException(
            status_code=400,
            detail=f"Cluster has already been reviewed (status: {cluster.admin_status})",
        )

    if req.action == "promote":
        # Extract coordinates from PostGIS geometry
        from sqlalchemy import func as sa_func
        lat = db.scalar(sa_func.ST_Y(cluster.centroid))
        lng = db.scalar(sa_func.ST_X(cluster.centroid))

        if lat is None or lng is None:
            raise HTTPException(status_code=422, detail="Cluster centroid geometry is invalid")

        centroid_geom = from_shape(Point(lng, lat), srid=4326)

        candidate = CandidateHotspot(
            city=cluster.city,
            centroid=centroid_geom,
            report_count=cluster.total_article_count,
            date_first_report=datetime.combine(cluster.first_episode, datetime.min.time()) if cluster.first_episode else None,
            date_last_report=datetime.combine(cluster.last_episode, datetime.min.time()) if cluster.last_episode else None,
            status="candidate",
            reviewed_by=admin.id,
            reviewed_at=datetime.utcnow(),
            notes=(
                f"Promoted from Groundsource cluster {cluster_id}. "
                f"Episodes: {cluster.episode_count}, "
                f"Confidence: {cluster.confidence}, "
                f"Infra signal: {cluster.infra_signal}"
            ),
        )
        db.add(candidate)

        cluster.admin_status = "promoted"
        cluster.admin_notes = f"Promoted to CandidateHotspot by admin {admin.id}"

        admin_service.log_admin_action(
            db, admin.id, "promote_cluster",
            target_type="groundsource_cluster", target_id=str(cluster_id),
            details=json.dumps({"city": cluster.city, "confidence": cluster.confidence}),
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        db.refresh(candidate)

        return {
            "status": "promoted",
            "cluster_id": str(cluster_id),
            "candidate_hotspot_id": str(candidate.id),
        }

    else:  # dismiss
        cluster.admin_status = "dismissed"
        cluster.admin_notes = req.dismiss_reason or "Dismissed by admin"

        admin_service.log_admin_action(
            db, admin.id, "dismiss_cluster",
            target_type="groundsource_cluster", target_id=str(cluster_id),
            details=json.dumps({
                "city": cluster.city,
                "reason": req.dismiss_reason,
            }),
            ip_address=request.client.host if request.client else None,
        )
        db.commit()

        return {
            "status": "dismissed",
            "cluster_id": str(cluster_id),
        }


# =============================================================================
# PERSONAL PIN MANAGEMENT
# =============================================================================

@router.get("/pins")
async def list_personal_pins(
    city: Optional[str] = Query(None, description="Filter by city"),
    sort_by: Optional[str] = Query(
        None,
        description="Sort field: 'fhi' | 'date' | 'city'",
        pattern="^(fhi|date|city)$",
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    List all personal pins (is_personal_hotspot=TRUE watch areas) for admin review.
    Returns pin data enriched with owner username and email.
    """
    from sqlalchemy import func as sa_func

    query = (
        db.query(WatchArea, User)
        .join(User, WatchArea.user_id == User.id, isouter=True)
        .filter(WatchArea.is_personal_hotspot == True)  # noqa: E712
    )

    if city:
        query = query.filter(WatchArea.city == city)

    # Sorting
    if sort_by == "fhi":
        query = query.order_by(WatchArea.fhi_score.desc().nullslast())
    elif sort_by == "city":
        query = query.order_by(WatchArea.city.asc(), WatchArea.created_at.desc())
    else:  # default: date (most recent first)
        query = query.order_by(WatchArea.created_at.desc())

    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for wa, owner in rows:
        lat = db.scalar(sa_func.ST_Y(wa.location)) if wa.location is not None else None
        lng = db.scalar(sa_func.ST_X(wa.location)) if wa.location is not None else None
        items.append({
            "id": str(wa.id),
            "name": wa.name,
            "city": wa.city,
            "latitude": lat,
            "longitude": lng,
            "fhi_score": wa.fhi_score,
            "fhi_level": wa.fhi_level,
            "historical_episode_count": wa.historical_episode_count,
            "alert_radius": wa.alert_radius,
            "visibility": wa.visibility,
            "source": wa.source,
            "created_at": wa.created_at.isoformat() if wa.created_at else None,
            "fhi_updated_at": wa.fhi_updated_at.isoformat() if wa.fhi_updated_at else None,
            "owner": {
                "id": str(owner.id) if owner else None,
                "username": owner.username if owner else None,
                "email": owner.email if owner else None,
            },
        })

    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.patch("/pins/{pin_id}/relocate")
async def relocate_pin(
    pin_id: UUID,
    req: PinRelocateRequest,
    request: Request,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Admin correction: move a personal pin to new coordinates.
    Useful when a user's pin is placed on the wrong street or offset by GPS error.
    Writes an audit log entry for accountability.
    """
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    pin = db.query(WatchArea).filter(
        WatchArea.id == pin_id,
        WatchArea.is_personal_hotspot == True,  # noqa: E712
    ).first()
    if not pin:
        raise HTTPException(status_code=404, detail="Personal pin not found")

    old_location = {
        "latitude": db.scalar(__import__("sqlalchemy").func.ST_Y(pin.location)) if pin.location else None,
        "longitude": db.scalar(__import__("sqlalchemy").func.ST_X(pin.location)) if pin.location else None,
    }

    pin.location = from_shape(Point(req.longitude, req.latitude), srid=4326)
    # Reset snapped_location so the ML pipeline can re-snap on next update
    pin.snapped_location = None

    admin_service.log_admin_action(
        db, admin.id, "relocate_pin",
        target_type="watch_area", target_id=str(pin_id),
        details=json.dumps({
            "old_location": old_location,
            "new_latitude": req.latitude,
            "new_longitude": req.longitude,
            "reason": req.reason,
        }),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {
        "status": "relocated",
        "pin_id": str(pin_id),
        "new_latitude": req.latitude,
        "new_longitude": req.longitude,
    }
