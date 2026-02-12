"""
Safety Circles Service — CRUD operations for family/community group notifications.

Handles circle creation, member management, invite codes, and alert queries.
All methods are synchronous (matching AlertService pattern, see plan D1).
"""

import secrets
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...infrastructure.models import SafetyCircle, CircleMember, CircleAlert, User
from ...core.phone_utils import normalize_phone as _normalize_phone, is_valid_e164

logger = logging.getLogger(__name__)

# Max members per circle type (plan section 1.1)
MAX_MEMBERS_BY_TYPE = {
    "family": 20,
    "school": 500,
    "apartment": 200,
    "neighborhood": 1000,
    "custom": 50,
}

class CircleServiceError(Exception):
    """Base exception for circle service errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class CircleService:
    """Service for Safety Circle CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    # ── Invite Code ──────────────────────────────────────────────

    def generate_invite_code(self) -> str:
        """Generate a unique 8-char alphanumeric invite code.

        Retries up to 5 times on collision (plan edge case).
        """
        for attempt in range(5):
            # Generate enough chars and take first 8 alphanumeric
            raw = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:8].upper()
            if len(raw) < 8:
                raw = raw + secrets.token_hex(4).upper()[:8 - len(raw)]
            exists = (
                self.db.query(SafetyCircle.id)
                .filter(SafetyCircle.invite_code == raw)
                .first()
            )
            if not exists:
                return raw
        raise CircleServiceError(
            "Failed to generate unique invite code after 5 attempts", status_code=500
        )

    # ── Phone Validation (D4) ────────────────────────────────────

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number to E.164 format. Delegates to shared utility."""
        return _normalize_phone(phone)

    @staticmethod
    def validate_phone(phone: str) -> tuple[bool, str]:
        """Validate phone format. Returns (is_valid, error_message)."""
        normalized = _normalize_phone(phone)
        if not is_valid_e164(normalized):
            return False, f"Invalid phone number format: must be 10+ digits, got '{phone}'"
        return True, ""

    # ── Circle CRUD ──────────────────────────────────────────────

    def create_circle(
        self,
        user_id: UUID,
        name: str,
        description: Optional[str],
        circle_type: str,
    ) -> SafetyCircle:
        """Create a new Safety Circle and auto-add creator as 'creator' role."""
        max_members = MAX_MEMBERS_BY_TYPE.get(circle_type, 50)
        invite_code = self.generate_invite_code()

        circle = SafetyCircle(
            name=name,
            description=description,
            circle_type=circle_type,
            created_by=user_id,
            invite_code=invite_code,
            max_members=max_members,
            is_active=True,
        )
        self.db.add(circle)
        self.db.flush()  # Get circle.id for member FK

        # Auto-add creator as 'creator' role
        creator_member = CircleMember(
            circle_id=circle.id,
            user_id=user_id,
            role="creator",
        )
        self.db.add(creator_member)
        self.db.commit()
        self.db.refresh(circle)

        logger.info(f"Circle created: {circle.id} ({circle_type}) by user {user_id}")
        return circle

    def get_user_circles(self, user_id: UUID) -> list[dict]:
        """List all circles where user is a member.

        Returns circle data enriched with member_count.
        """
        circles = (
            self.db.query(SafetyCircle)
            .join(CircleMember, CircleMember.circle_id == SafetyCircle.id)
            .filter(
                CircleMember.user_id == user_id,
                SafetyCircle.is_active == True,
            )
            .all()
        )

        results = []
        for circle in circles:
            member_count = (
                self.db.query(func.count(CircleMember.id))
                .filter(CircleMember.circle_id == circle.id)
                .scalar()
            )
            results.append({
                "circle": circle,
                "member_count": member_count,
            })
        return results

    def get_circle_with_members(
        self, circle_id: UUID, user_id: UUID
    ) -> dict:
        """Get circle detail with all members. Verifies requestor membership."""
        circle = self.db.query(SafetyCircle).filter(SafetyCircle.id == circle_id).first()
        if not circle:
            raise CircleServiceError("Circle not found", status_code=404)

        # Verify requestor is a member
        membership = (
            self.db.query(CircleMember)
            .filter(
                CircleMember.circle_id == circle_id,
                CircleMember.user_id == user_id,
            )
            .first()
        )
        if not membership:
            raise CircleServiceError("You are not a member of this circle", status_code=403)

        members = (
            self.db.query(CircleMember)
            .filter(CircleMember.circle_id == circle_id)
            .all()
        )

        member_count = len(members)

        return {
            "circle": circle,
            "members": members,
            "member_count": member_count,
            "user_role": membership.role,
        }

    def update_circle(
        self, circle_id: UUID, user_id: UUID, name: Optional[str], description: Optional[str]
    ) -> SafetyCircle:
        """Update circle name/description. Requires admin+ role."""
        self._require_role(circle_id, user_id, min_role="admin")

        circle = self.db.query(SafetyCircle).filter(SafetyCircle.id == circle_id).first()
        if not circle:
            raise CircleServiceError("Circle not found", status_code=404)

        if name is not None:
            circle.name = name
        if description is not None:
            circle.description = description
        circle.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(circle)
        return circle

    def delete_circle(self, circle_id: UUID, user_id: UUID) -> None:
        """Delete circle. Only creator can delete."""
        self._require_role(circle_id, user_id, min_role="creator")

        circle = self.db.query(SafetyCircle).filter(SafetyCircle.id == circle_id).first()
        if not circle:
            raise CircleServiceError("Circle not found", status_code=404)

        self.db.delete(circle)  # CASCADE deletes members + alerts
        self.db.commit()
        logger.info(f"Circle {circle_id} deleted by user {user_id}")

    # ── Member Management ────────────────────────────────────────

    def add_member(
        self,
        circle_id: UUID,
        adder_id: UUID,
        user_id: Optional[UUID] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        role: str = "member",
    ) -> CircleMember:
        """Add a member to a circle.

        - adder must be admin+
        - Validates phone (D4)
        - Checks max_members
        - Deduplicates (registered user can only be in circle once)
        - Auto-links phone/email to registered user if match found
        """
        self._require_role(circle_id, adder_id, min_role="admin")

        circle = self.db.query(SafetyCircle).filter(SafetyCircle.id == circle_id).first()
        if not circle:
            raise CircleServiceError("Circle not found", status_code=404)

        # Check max members
        current_count = (
            self.db.query(func.count(CircleMember.id))
            .filter(CircleMember.circle_id == circle_id)
            .scalar()
        )
        if current_count >= circle.max_members:
            raise CircleServiceError(
                f"Circle has reached maximum capacity ({circle.max_members} members)",
                status_code=409,
            )

        # Validate phone if provided (D4)
        normalized_phone = None
        if phone:
            is_valid, error_msg = self.validate_phone(phone)
            if not is_valid:
                raise CircleServiceError(error_msg, status_code=422)
            normalized_phone = self.normalize_phone(phone)

        # Auto-link: if phone or email matches a registered user, set user_id
        if not user_id and (normalized_phone or email):
            matched_user = self._find_user_by_contact(normalized_phone, email)
            if matched_user:
                user_id = matched_user.id
                if not display_name:
                    display_name = matched_user.display_name or matched_user.username

        # Deduplicate: registered users can only be in a circle once
        if user_id:
            existing = (
                self.db.query(CircleMember)
                .filter(
                    CircleMember.circle_id == circle_id,
                    CircleMember.user_id == user_id,
                )
                .first()
            )
            if existing:
                raise CircleServiceError(
                    "This user is already a member of this circle", status_code=409
                )

        member = CircleMember(
            circle_id=circle_id,
            user_id=user_id,
            phone=normalized_phone,
            email=email,
            display_name=display_name,
            role=role,
            invited_by=adder_id,
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)

        logger.info(
            f"Member added to circle {circle_id}: "
            f"user_id={user_id}, phone={normalized_phone}, email={email}"
        )
        return member

    def add_members_bulk(
        self,
        circle_id: UUID,
        adder_id: UUID,
        members_data: list[dict],
    ) -> dict:
        """Bulk add members. Returns summary of successes and failures.

        Never silently skips — every failure is tracked (D8).
        """
        self._require_role(circle_id, adder_id, min_role="admin")

        added = []
        errors = []

        for i, data in enumerate(members_data):
            try:
                member = self.add_member(
                    circle_id=circle_id,
                    adder_id=adder_id,
                    user_id=data.get("user_id"),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    display_name=data.get("display_name"),
                    role=data.get("role", "member"),
                )
                added.append(member)
            except CircleServiceError as e:
                identifier = data.get("phone") or data.get("email") or data.get("user_id") or f"entry #{i}"
                errors.append(f"{identifier}: {e.message}")

        return {
            "added": added,
            "added_count": len(added),
            "error_count": len(errors),
            "errors": errors,
        }

    def remove_member(
        self, circle_id: UUID, member_id: UUID, remover_id: UUID
    ) -> None:
        """Remove a member from a circle.

        - Admin+ can remove anyone except creator
        - Members can remove themselves (leave)
        """
        member = (
            self.db.query(CircleMember)
            .filter(CircleMember.id == member_id, CircleMember.circle_id == circle_id)
            .first()
        )
        if not member:
            raise CircleServiceError("Member not found", status_code=404)

        # Can't remove the creator
        if member.role == "creator":
            raise CircleServiceError(
                "Cannot remove the circle creator. Delete the circle instead.",
                status_code=403,
            )

        # Check permissions: self-removal or admin+
        is_self = member.user_id and member.user_id == remover_id
        if not is_self:
            self._require_role(circle_id, remover_id, min_role="admin")

        self.db.delete(member)
        self.db.commit()
        logger.info(f"Member {member_id} removed from circle {circle_id} by {remover_id}")

    def update_member(
        self,
        circle_id: UUID,
        member_id: UUID,
        updater_id: UUID,
        role: Optional[str] = None,
        is_muted: Optional[bool] = None,
        notify_whatsapp: Optional[bool] = None,
        notify_sms: Optional[bool] = None,
        notify_email: Optional[bool] = None,
    ) -> CircleMember:
        """Update member settings.

        - Role changes require admin+
        - Mute/notification prefs: self or admin+
        """
        member = (
            self.db.query(CircleMember)
            .filter(CircleMember.id == member_id, CircleMember.circle_id == circle_id)
            .first()
        )
        if not member:
            raise CircleServiceError("Member not found", status_code=404)

        is_self = member.user_id and member.user_id == updater_id
        is_admin = self._check_role(circle_id, updater_id, min_role="admin")

        if not is_self and not is_admin:
            raise CircleServiceError("Permission denied", status_code=403)

        # Role changes require admin+
        if role is not None:
            if not is_admin:
                raise CircleServiceError("Only admins can change member roles", status_code=403)
            if member.role == "creator":
                raise CircleServiceError("Cannot change the creator's role", status_code=403)
            member.role = role

        # Notification prefs: self or admin
        if is_muted is not None:
            member.is_muted = is_muted
        if notify_whatsapp is not None:
            member.notify_whatsapp = notify_whatsapp
        if notify_sms is not None:
            member.notify_sms = notify_sms
        if notify_email is not None:
            member.notify_email = notify_email

        self.db.commit()
        self.db.refresh(member)
        return member

    # ── Join / Leave ─────────────────────────────────────────────

    def join_by_invite_code(self, invite_code: str, user_id: UUID) -> CircleMember:
        """Join a circle via invite code.

        Auto-merges with non-registered entry if phone/email matches (plan edge case).
        """
        circle = (
            self.db.query(SafetyCircle)
            .filter(
                SafetyCircle.invite_code == invite_code.upper(),
                SafetyCircle.is_active == True,
            )
            .first()
        )
        if not circle:
            raise CircleServiceError("Invalid invite code", status_code=404)

        # Check if already a member (registered user)
        existing = (
            self.db.query(CircleMember)
            .filter(
                CircleMember.circle_id == circle.id,
                CircleMember.user_id == user_id,
            )
            .first()
        )
        if existing:
            raise CircleServiceError("You are already a member of this circle", status_code=409)

        # Check max members
        current_count = (
            self.db.query(func.count(CircleMember.id))
            .filter(CircleMember.circle_id == circle.id)
            .scalar()
        )
        if current_count >= circle.max_members:
            raise CircleServiceError(
                f"This circle has reached maximum capacity ({circle.max_members} members)",
                status_code=409,
            )

        # Auto-merge: check if there's a non-registered entry matching this user's phone/email
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            merge_candidate = self._find_merge_candidate(circle.id, user)
            if merge_candidate:
                # Upgrade non-registered entry to registered user
                merge_candidate.user_id = user_id
                if not merge_candidate.display_name:
                    merge_candidate.display_name = user.display_name or user.username
                self.db.commit()
                self.db.refresh(merge_candidate)
                logger.info(
                    f"User {user_id} merged with existing member {merge_candidate.id} "
                    f"in circle {circle.id}"
                )
                return merge_candidate

        # Create new membership
        member = CircleMember(
            circle_id=circle.id,
            user_id=user_id,
            display_name=user.display_name or user.username if user else None,
            role="member",
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)

        logger.info(f"User {user_id} joined circle {circle.id} via invite code")
        return member

    def leave_circle(self, circle_id: UUID, user_id: UUID) -> None:
        """Leave a circle. Creator cannot leave (must delete instead)."""
        member = (
            self.db.query(CircleMember)
            .filter(
                CircleMember.circle_id == circle_id,
                CircleMember.user_id == user_id,
            )
            .first()
        )
        if not member:
            raise CircleServiceError("You are not a member of this circle", status_code=404)

        if member.role == "creator":
            raise CircleServiceError(
                "Circle creators cannot leave. Delete the circle instead.",
                status_code=403,
            )

        self.db.delete(member)
        self.db.commit()
        logger.info(f"User {user_id} left circle {circle_id}")

    # ── Circle Alerts ────────────────────────────────────────────

    def get_user_circle_alerts(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """Get circle alerts for all circles the user is a member of.

        Returns alerts enriched with circle name and reporter info.
        """
        # Get member IDs for this user across all circles
        member_ids = (
            self.db.query(CircleMember.id)
            .filter(CircleMember.user_id == user_id)
            .scalar_subquery()
        )

        alerts = (
            self.db.query(CircleAlert, SafetyCircle.name, User.display_name, User.username)
            .join(SafetyCircle, CircleAlert.circle_id == SafetyCircle.id)
            .join(User, CircleAlert.reporter_user_id == User.id)
            .filter(CircleAlert.member_id.in_(member_ids))
            .order_by(CircleAlert.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "alert": alert,
                "circle_name": circle_name,
                "reporter_name": display_name or username,
            }
            for alert, circle_name, display_name, username in alerts
        ]

    def get_unread_alert_count(self, user_id: UUID) -> int:
        """Get count of unread circle alerts for the user."""
        member_ids = (
            self.db.query(CircleMember.id)
            .filter(CircleMember.user_id == user_id)
            .scalar_subquery()
        )

        count = (
            self.db.query(func.count(CircleAlert.id))
            .filter(
                CircleAlert.member_id.in_(member_ids),
                CircleAlert.is_read == False,
            )
            .scalar()
        )
        return count or 0

    def mark_alert_read(self, alert_id: UUID, user_id: UUID) -> None:
        """Mark a single circle alert as read. Verifies ownership."""
        alert = self.db.query(CircleAlert).filter(CircleAlert.id == alert_id).first()
        if not alert:
            raise CircleServiceError("Alert not found", status_code=404)

        # Verify the user owns this alert (is the member)
        member = (
            self.db.query(CircleMember)
            .filter(CircleMember.id == alert.member_id, CircleMember.user_id == user_id)
            .first()
        )
        if not member:
            raise CircleServiceError("Permission denied", status_code=403)

        alert.is_read = True
        self.db.commit()

    def mark_all_alerts_read(self, user_id: UUID) -> int:
        """Mark all unread circle alerts as read. Returns count updated."""
        member_ids = (
            self.db.query(CircleMember.id)
            .filter(CircleMember.user_id == user_id)
            .all()
        )
        member_id_list = [m[0] for m in member_ids]

        if not member_id_list:
            return 0

        count = (
            self.db.query(CircleAlert)
            .filter(
                CircleAlert.member_id.in_(member_id_list),
                CircleAlert.is_read == False,
            )
            .update({CircleAlert.is_read: True}, synchronize_session="fetch")
        )
        self.db.commit()
        return count

    # ── Private Helpers ──────────────────────────────────────────

    def _require_role(self, circle_id: UUID, user_id: UUID, min_role: str) -> CircleMember:
        """Verify user has at least the required role in the circle.

        Role hierarchy: creator > admin > member
        """
        member = (
            self.db.query(CircleMember)
            .filter(
                CircleMember.circle_id == circle_id,
                CircleMember.user_id == user_id,
            )
            .first()
        )
        if not member:
            raise CircleServiceError("You are not a member of this circle", status_code=403)

        role_hierarchy = {"member": 0, "admin": 1, "creator": 2}
        required_level = role_hierarchy.get(min_role, 0)
        user_level = role_hierarchy.get(member.role, 0)

        if user_level < required_level:
            raise CircleServiceError(
                f"Requires {min_role} role or higher", status_code=403
            )
        return member

    def _check_role(self, circle_id: UUID, user_id: UUID, min_role: str) -> bool:
        """Check if user has at least the required role. Returns bool (no exception)."""
        try:
            self._require_role(circle_id, user_id, min_role)
            return True
        except CircleServiceError:
            return False

    def _find_user_by_contact(
        self, phone: Optional[str], email: Optional[str]
    ) -> Optional[User]:
        """Find a registered user by phone or email for auto-linking."""
        if phone:
            user = self.db.query(User).filter(User.phone == phone).first()
            if user:
                return user
        if email:
            user = self.db.query(User).filter(User.email == email).first()
            if user:
                return user
        return None

    def _find_merge_candidate(self, circle_id: UUID, user: User) -> Optional[CircleMember]:
        """Find a non-registered circle member that matches the joining user's phone/email.

        This handles the case: admin adds grandma by phone → grandma registers → joins via code.
        """
        if user.phone:
            normalized = self.normalize_phone(user.phone)
            candidate = (
                self.db.query(CircleMember)
                .filter(
                    CircleMember.circle_id == circle_id,
                    CircleMember.phone == normalized,
                    CircleMember.user_id.is_(None),
                )
                .first()
            )
            if candidate:
                return candidate

        if user.email:
            candidate = (
                self.db.query(CircleMember)
                .filter(
                    CircleMember.circle_id == circle_id,
                    CircleMember.email == user.email,
                    CircleMember.user_id.is_(None),
                )
                .first()
            )
            if candidate:
                return candidate

        return None
