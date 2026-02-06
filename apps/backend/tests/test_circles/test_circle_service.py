"""
Tests for CircleService — CRUD, member management, invite codes, and alerts.

Tests the service layer in isolation using SQLite in-memory DB.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock

from src.domain.services.circle_service import CircleService, CircleServiceError
from src.infrastructure.models import CircleAlert
from .conftest import create_test_report


class TestCircleCreation:
    """Test circle creation and invite code generation."""

    def test_create_circle_basic(self, db_session, test_user):
        """Create a family circle — should auto-add creator."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="My Family",
            description="Family safety circle",
            circle_type="family",
        )

        assert circle.name == "My Family"
        assert circle.circle_type == "family"
        assert circle.max_members == 20  # family limit
        assert circle.is_active is True
        assert len(circle.invite_code) >= 6  # 6-8 chars alphanumeric
        assert circle.invite_code.isalnum()
        assert circle.created_by == test_user.id

        # Creator auto-added as member
        members = circle.members
        assert len(members) == 1
        assert members[0].user_id == test_user.id
        assert members[0].role == "creator"

    def test_create_circle_types_have_correct_max_members(self, db_session, test_user):
        """Each circle type should have its own max_members limit."""
        service = CircleService(db_session)

        expected = {
            "family": 20,
            "school": 500,
            "apartment": 200,
            "neighborhood": 1000,
            "custom": 50,
        }

        for circle_type, expected_max in expected.items():
            circle = service.create_circle(
                user_id=test_user.id,
                name=f"Test {circle_type}",
                description=None,
                circle_type=circle_type,
            )
            assert circle.max_members == expected_max, (
                f"{circle_type} should have max_members={expected_max}"
            )

    def test_invite_code_is_unique(self, db_session, test_user):
        """Each circle should get a unique invite code."""
        service = CircleService(db_session)
        codes = set()
        for i in range(5):
            circle = service.create_circle(
                user_id=test_user.id,
                name=f"Circle {i}",
                description=None,
                circle_type="custom",
            )
            codes.add(circle.invite_code)
        assert len(codes) == 5  # All unique


class TestMemberManagement:
    """Test adding, removing, and updating members."""

    def _create_circle(self, service, user_id):
        return service.create_circle(
            user_id=user_id,
            name="Test Circle",
            description=None,
            circle_type="family",
        )

    def test_add_member_by_phone(self, db_session, test_user):
        """Add a non-registered member by phone number."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        member = service.add_member(
            circle_id=circle.id,
            adder_id=test_user.id,
            phone="9876543299",
            display_name="Grandma",
        )

        assert member.phone == "+919876543299"  # Normalized to E.164
        assert member.display_name == "Grandma"
        assert member.role == "member"
        assert member.user_id is None  # Not a registered user

    def test_add_member_by_user_id(self, db_session, test_user, test_user2):
        """Add a registered user as member."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        member = service.add_member(
            circle_id=circle.id,
            adder_id=test_user.id,
            user_id=test_user2.id,
        )

        assert member.user_id == test_user2.id
        assert member.role == "member"

    def test_add_duplicate_member_fails(self, db_session, test_user, test_user2):
        """Cannot add the same registered user twice."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        service.add_member(circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id)

        with pytest.raises(CircleServiceError) as exc_info:
            service.add_member(circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id)
        assert exc_info.value.status_code == 409
        assert "already a member" in exc_info.value.message

    def test_phone_validation_rejects_invalid(self, db_session, test_user):
        """Invalid phone numbers should be rejected with 422."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        with pytest.raises(CircleServiceError) as exc_info:
            service.add_member(
                circle_id=circle.id,
                adder_id=test_user.id,
                phone="123",  # Too short
            )
        assert exc_info.value.status_code == 422
        assert "Invalid phone" in exc_info.value.message

    def test_max_members_enforced(self, db_session, test_user):
        """Cannot exceed max_members limit."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        # Family circle has max_members=20, creator already counts as 1
        # Add 19 more to hit the limit
        for i in range(19):
            service.add_member(
                circle_id=circle.id,
                adder_id=test_user.id,
                phone=f"98765{str(i).zfill(5)}",
                display_name=f"Member {i}",
            )

        # 21st should fail
        with pytest.raises(CircleServiceError) as exc_info:
            service.add_member(
                circle_id=circle.id,
                adder_id=test_user.id,
                phone="9999999999",
            )
        assert exc_info.value.status_code == 409
        assert "maximum capacity" in exc_info.value.message

    def test_remove_member(self, db_session, test_user, test_user2):
        """Admin can remove a member."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        member = service.add_member(
            circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id
        )

        service.remove_member(circle.id, member.id, test_user.id)

        # Verify member count
        result = service.get_circle_with_members(circle.id, test_user.id)
        assert result["member_count"] == 1  # Only creator left

    def test_cannot_remove_creator(self, db_session, test_user):
        """Creator cannot be removed."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        # Find creator member
        result = service.get_circle_with_members(circle.id, test_user.id)
        creator_member = [m for m in result["members"] if m.role == "creator"][0]

        with pytest.raises(CircleServiceError) as exc_info:
            service.remove_member(circle.id, creator_member.id, test_user.id)
        assert exc_info.value.status_code == 403
        assert "creator" in exc_info.value.message.lower()

    def test_non_admin_cannot_add_members(self, db_session, test_user, test_user2):
        """Regular members cannot add other members."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        # Add user2 as regular member
        service.add_member(circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id)

        # user2 (member) tries to add someone — should fail
        with pytest.raises(CircleServiceError) as exc_info:
            service.add_member(
                circle_id=circle.id,
                adder_id=test_user2.id,
                phone="9999999999",
            )
        assert exc_info.value.status_code == 403

    def test_update_member_mute(self, db_session, test_user, test_user2):
        """Member can mute themselves."""
        service = CircleService(db_session)
        circle = self._create_circle(service, test_user.id)

        member = service.add_member(
            circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id
        )

        updated = service.update_member(
            circle_id=circle.id,
            member_id=member.id,
            updater_id=test_user2.id,
            is_muted=True,
        )

        assert updated.is_muted is True


class TestJoinAndLeave:
    """Test joining via invite code and leaving circles."""

    def test_join_by_invite_code(self, db_session, test_user, test_user2):
        """User can join a circle via invite code."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Open Circle",
            description=None,
            circle_type="custom",
        )

        member = service.join_by_invite_code(circle.invite_code, test_user2.id)

        assert member.user_id == test_user2.id
        assert member.role == "member"

    def test_join_invalid_code_fails(self, db_session, test_user):
        """Invalid invite code returns 404."""
        service = CircleService(db_session)

        with pytest.raises(CircleServiceError) as exc_info:
            service.join_by_invite_code("INVALID1", test_user.id)
        assert exc_info.value.status_code == 404
        assert "Invalid invite code" in exc_info.value.message

    def test_join_twice_fails(self, db_session, test_user, test_user2):
        """Cannot join the same circle twice."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Test",
            description=None,
            circle_type="custom",
        )

        service.join_by_invite_code(circle.invite_code, test_user2.id)

        with pytest.raises(CircleServiceError) as exc_info:
            service.join_by_invite_code(circle.invite_code, test_user2.id)
        assert exc_info.value.status_code == 409

    def test_auto_merge_on_join(self, db_session, test_user, test_user2):
        """When a user joins and their phone matches an existing non-registered entry, merge.

        The add_member auto-link feature will match phones at add time, so we use
        a phone number that doesn't match any user, then have user2 register later
        and join via invite code.
        """
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Family",
            description=None,
            circle_type="family",
        )

        # Admin adds a phone that doesn't match any registered user yet
        # (test_user2 phone is +919876543211 — use a different number)
        member = service.add_member(
            circle_id=circle.id,
            adder_id=test_user.id,
            phone="+919000000000",  # no registered user has this phone
            display_name="Son",
        )
        original_member_id = member.id
        assert member.user_id is None  # Not linked — no user has +919000000000

        # Now simulate: user2's phone gets updated to match, then they join via invite
        # Actually, let's test the merge by updating user2's phone to match, then joining
        test_user2.phone = "+919000000000"
        db_session.commit()

        # User2 joins via invite code → should merge with existing phone entry
        merged = service.join_by_invite_code(circle.invite_code, test_user2.id)

        assert merged.id == original_member_id  # Same member record, merged
        assert merged.user_id == test_user2.id  # Now linked

    def test_leave_circle(self, db_session, test_user, test_user2):
        """Member can leave a circle."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Test",
            description=None,
            circle_type="custom",
        )
        service.join_by_invite_code(circle.invite_code, test_user2.id)

        service.leave_circle(circle.id, test_user2.id)

        # Verify only creator remains
        result = service.get_circle_with_members(circle.id, test_user.id)
        assert result["member_count"] == 1

    def test_creator_cannot_leave(self, db_session, test_user):
        """Creator cannot leave their own circle."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="My Circle",
            description=None,
            circle_type="custom",
        )

        with pytest.raises(CircleServiceError) as exc_info:
            service.leave_circle(circle.id, test_user.id)
        assert exc_info.value.status_code == 403
        assert "creator" in exc_info.value.message.lower()


class TestPhoneValidation:
    """Test phone number normalization and validation (D4)."""

    def test_normalize_10_digit_indian(self):
        assert CircleService.normalize_phone("9876543210") == "+919876543210"

    def test_normalize_with_leading_zero(self):
        assert CircleService.normalize_phone("09876543210") == "+919876543210"

    def test_normalize_with_plus(self):
        assert CircleService.normalize_phone("+919876543210") == "+919876543210"

    def test_normalize_with_spaces_and_dashes(self):
        assert CircleService.normalize_phone("98765-432 10") == "+919876543210"

    def test_validate_valid_phone(self):
        is_valid, error = CircleService.validate_phone("9876543210")
        assert is_valid is True
        assert error == ""

    def test_validate_short_phone_fails(self):
        is_valid, error = CircleService.validate_phone("12345")
        assert is_valid is False
        assert "Invalid phone" in error


class TestBulkAdd:
    """Test bulk member addition (D8 — no silent failures)."""

    def test_bulk_add_mixed_results(self, db_session, test_user, test_user2):
        """Bulk add with one success and one failure — both tracked."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Test",
            description=None,
            circle_type="custom",
        )

        # Add user2 first so the second entry will be a duplicate
        service.add_member(circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id)

        result = service.add_members_bulk(
            circle_id=circle.id,
            adder_id=test_user.id,
            members_data=[
                {"phone": "9999999999", "display_name": "New Member"},
                {"user_id": test_user2.id, "display_name": "Duplicate"},  # Will fail
            ],
        )

        assert result["added_count"] == 1
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1
        assert "already a member" in result["errors"][0]


class TestCircleAlerts:
    """Test circle alert queries and read/unread tracking."""

    def test_get_unread_count(self, db_session, test_user, test_user2):
        """Unread count should reflect actual unread circle alerts."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Test",
            description=None,
            circle_type="custom",
        )
        # Add user2 as member
        member = service.add_member(
            circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id
        )

        # Create a fake report
        report_id = create_test_report(db_session, test_user.id)

        # Create circle alert for user2
        alert = CircleAlert(
            circle_id=circle.id,
            report_id=report_id,
            reporter_user_id=test_user.id,
            member_id=member.id,
            message="Test alert",
            is_read=False,
        )
        db_session.add(alert)
        db_session.commit()

        count = service.get_unread_alert_count(test_user2.id)
        assert count == 1

    def test_mark_alert_read(self, db_session, test_user, test_user2):
        """Marking an alert as read should decrement unread count."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Test",
            description=None,
            circle_type="custom",
        )
        member = service.add_member(
            circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id
        )

        report_id = create_test_report(db_session, test_user.id)

        alert = CircleAlert(
            circle_id=circle.id,
            report_id=report_id,
            reporter_user_id=test_user.id,
            member_id=member.id,
            message="Test alert",
            is_read=False,
        )
        db_session.add(alert)
        db_session.commit()

        service.mark_alert_read(alert.id, test_user2.id)

        count = service.get_unread_alert_count(test_user2.id)
        assert count == 0

    def test_mark_all_alerts_read(self, db_session, test_user, test_user2):
        """Mark all alerts read for a user."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id,
            name="Test",
            description=None,
            circle_type="custom",
        )
        member = service.add_member(
            circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id
        )

        report_id = create_test_report(db_session, test_user.id)

        for i in range(3):
            a = CircleAlert(
                circle_id=circle.id,
                report_id=report_id,
                reporter_user_id=test_user.id,
                member_id=member.id,
                message=f"Alert {i}",
                is_read=False,
            )
            db_session.add(a)
        db_session.commit()

        count = service.mark_all_alerts_read(test_user2.id)
        assert count == 3
        assert service.get_unread_alert_count(test_user2.id) == 0
