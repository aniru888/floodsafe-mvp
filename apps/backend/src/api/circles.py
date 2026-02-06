"""
Safety Circles API Router — Family & community group notifications.

16 endpoints for circle CRUD, member management, invite codes, and alert queries.
All endpoints require authentication via Bearer token.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.infrastructure.models import User
from src.api.deps import get_current_user
from src.domain.services.circle_service import CircleService, CircleServiceError
from src.domain.models import (
    SafetyCircleCreate,
    SafetyCircleUpdate,
    SafetyCircleResponse,
    SafetyCircleDetailResponse,
    CircleMemberAdd,
    CircleMemberResponse,
    CircleMemberUpdate,
    CircleAlertResponse,
    JoinCircleRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _circle_to_response(circle, member_count: int) -> dict:
    """Convert SQLAlchemy circle to response dict."""
    return {
        "id": circle.id,
        "name": circle.name,
        "description": circle.description,
        "circle_type": circle.circle_type,
        "created_by": circle.created_by,
        "invite_code": circle.invite_code,
        "max_members": circle.max_members,
        "is_active": circle.is_active,
        "member_count": member_count,
        "created_at": circle.created_at,
        "updated_at": circle.updated_at,
    }


def _member_to_response(member) -> dict:
    """Convert SQLAlchemy member to response dict."""
    return {
        "id": member.id,
        "circle_id": member.circle_id,
        "user_id": member.user_id,
        "phone": member.phone,
        "email": member.email,
        "display_name": member.display_name,
        "role": member.role,
        "is_muted": member.is_muted,
        "notify_whatsapp": member.notify_whatsapp,
        "notify_sms": member.notify_sms,
        "notify_email": member.notify_email,
        "joined_at": member.joined_at,
    }


def _handle_service_error(e: CircleServiceError):
    """Convert CircleServiceError to HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=e.message)


# ═══════════════════════════════════════════════════════════════
# Circle CRUD
# ═══════════════════════════════════════════════════════════════


@router.post("/", response_model=SafetyCircleResponse)
async def create_circle(
    data: SafetyCircleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new Safety Circle. Creator is auto-added as first member."""
    try:
        service = CircleService(db)
        circle = service.create_circle(
            user_id=user.id,
            name=data.name,
            description=data.description,
            circle_type=data.circle_type.value,
        )
        member_count = 1  # Creator just added
        return _circle_to_response(circle, member_count)
    except CircleServiceError as e:
        _handle_service_error(e)


@router.get("/", response_model=list[SafetyCircleResponse])
async def list_my_circles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all circles the current user is a member of."""
    service = CircleService(db)
    results = service.get_user_circles(user.id)
    return [_circle_to_response(r["circle"], r["member_count"]) for r in results]


@router.get("/{circle_id}", response_model=SafetyCircleDetailResponse)
async def get_circle_detail(
    circle_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get circle detail with all members. Requires membership."""
    try:
        service = CircleService(db)
        result = service.get_circle_with_members(circle_id, user.id)
        circle = result["circle"]
        members = result["members"]
        return {
            **_circle_to_response(circle, result["member_count"]),
            "members": [_member_to_response(m) for m in members],
        }
    except CircleServiceError as e:
        _handle_service_error(e)


@router.put("/{circle_id}", response_model=SafetyCircleResponse)
async def update_circle(
    circle_id: UUID,
    data: SafetyCircleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update circle name/description. Requires admin+ role."""
    try:
        service = CircleService(db)
        circle = service.update_circle(circle_id, user.id, data.name, data.description)
        from sqlalchemy import func
        from src.infrastructure.models import CircleMember
        count = db.query(func.count(CircleMember.id)).filter(
            CircleMember.circle_id == circle_id
        ).scalar()
        return _circle_to_response(circle, count)
    except CircleServiceError as e:
        _handle_service_error(e)


@router.delete("/{circle_id}")
async def delete_circle(
    circle_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete circle. Only creator can delete."""
    try:
        service = CircleService(db)
        service.delete_circle(circle_id, user.id)
        return {"message": "Circle deleted successfully"}
    except CircleServiceError as e:
        _handle_service_error(e)


# ═══════════════════════════════════════════════════════════════
# Member Management
# ═══════════════════════════════════════════════════════════════


@router.post("/{circle_id}/members", response_model=CircleMemberResponse)
async def add_member(
    circle_id: UUID,
    data: CircleMemberAdd,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a member to a circle. Requires admin+ role."""
    try:
        service = CircleService(db)
        member = service.add_member(
            circle_id=circle_id,
            adder_id=user.id,
            user_id=data.user_id,
            phone=data.phone,
            email=data.email,
            display_name=data.display_name,
            role=data.role.value if data.role else "member",
        )
        return _member_to_response(member)
    except CircleServiceError as e:
        _handle_service_error(e)


@router.post("/{circle_id}/members/bulk")
async def add_members_bulk(
    circle_id: UUID,
    members: list[CircleMemberAdd],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk add members. Returns summary with successes and failures (D8)."""
    try:
        service = CircleService(db)
        members_data = [
            {
                "user_id": m.user_id,
                "phone": m.phone,
                "email": m.email,
                "display_name": m.display_name,
                "role": m.role.value if m.role else "member",
            }
            for m in members
        ]
        result = service.add_members_bulk(circle_id, user.id, members_data)
        return {
            "added": [_member_to_response(m) for m in result["added"]],
            "added_count": result["added_count"],
            "error_count": result["error_count"],
            "errors": result["errors"],
        }
    except CircleServiceError as e:
        _handle_service_error(e)


@router.delete("/{circle_id}/members/{member_id}")
async def remove_member(
    circle_id: UUID,
    member_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a member. Admin+ can remove anyone (except creator), members can remove self."""
    try:
        service = CircleService(db)
        service.remove_member(circle_id, member_id, user.id)
        return {"message": "Member removed successfully"}
    except CircleServiceError as e:
        _handle_service_error(e)


@router.patch("/{circle_id}/members/{member_id}", response_model=CircleMemberResponse)
async def update_member(
    circle_id: UUID,
    member_id: UUID,
    data: CircleMemberUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update member settings. Role changes need admin+, notification prefs self or admin+."""
    try:
        service = CircleService(db)
        member = service.update_member(
            circle_id=circle_id,
            member_id=member_id,
            updater_id=user.id,
            role=data.role.value if data.role else None,
            is_muted=data.is_muted,
            notify_whatsapp=data.notify_whatsapp,
            notify_sms=data.notify_sms,
            notify_email=data.notify_email,
        )
        return _member_to_response(member)
    except CircleServiceError as e:
        _handle_service_error(e)


# ═══════════════════════════════════════════════════════════════
# Join / Leave
# ═══════════════════════════════════════════════════════════════


@router.post("/join", response_model=CircleMemberResponse)
async def join_circle(
    data: JoinCircleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Join a circle via invite code."""
    try:
        service = CircleService(db)
        member = service.join_by_invite_code(data.invite_code, user.id)
        return _member_to_response(member)
    except CircleServiceError as e:
        _handle_service_error(e)


@router.post("/{circle_id}/leave")
async def leave_circle(
    circle_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Leave a circle. Creator cannot leave (must delete instead)."""
    try:
        service = CircleService(db)
        service.leave_circle(circle_id, user.id)
        return {"message": "Left circle successfully"}
    except CircleServiceError as e:
        _handle_service_error(e)


# ═══════════════════════════════════════════════════════════════
# Circle Alerts
# ═══════════════════════════════════════════════════════════════


@router.get("/alerts", response_model=list[CircleAlertResponse])
async def get_circle_alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get circle alerts for all circles the user is a member of."""
    service = CircleService(db)
    results = service.get_user_circle_alerts(user.id, limit=limit, offset=offset)
    return [
        {
            "id": r["alert"].id,
            "circle_id": r["alert"].circle_id,
            "circle_name": r["circle_name"],
            "report_id": r["alert"].report_id,
            "reporter_name": r["reporter_name"],
            "message": r["alert"].message,
            "is_read": r["alert"].is_read,
            "notification_sent": r["alert"].notification_sent,
            "notification_channel": r["alert"].notification_channel,
            "created_at": r["alert"].created_at,
        }
        for r in results
    ]


@router.patch("/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single circle alert as read."""
    try:
        service = CircleService(db)
        service.mark_alert_read(alert_id, user.id)
        return {"message": "Alert marked as read"}
    except CircleServiceError as e:
        _handle_service_error(e)


@router.patch("/alerts/read-all")
async def mark_all_alerts_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all unread circle alerts as read."""
    service = CircleService(db)
    count = service.mark_all_alerts_read(user.id)
    return {"message": f"Marked {count} alerts as read", "count": count}


@router.get("/alerts/unread-count")
async def get_unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get count of unread circle alerts."""
    service = CircleService(db)
    count = service.get_unread_alert_count(user.id)
    return {"count": count}
