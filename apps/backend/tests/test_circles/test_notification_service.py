"""
Tests for CircleNotificationService — fan-out, dedup, throttle, and error tracking.

Tests D1 (sync), D2 (dedup), D3 (throttle), D8 (no silent fallbacks).
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock

from src.domain.services.circle_service import CircleService
from src.domain.services.circle_notification_service import (
    CircleNotificationService,
    MAX_EXTERNAL_NOTIFICATIONS_PER_CIRCLE,
)
from src.infrastructure.models import CircleAlert
from .conftest import create_test_report, create_watch_area_alert


class TestNotificationFanOut:
    """Test that notifications fan out to all circle members."""

    def test_notify_creates_alerts_for_all_members(self, db_session, test_user, test_user2, test_user3):
        """Reporter creates report → all other circle members get CircleAlert."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id, name="Family", description=None, circle_type="family"
        )
        service.add_member(circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id)
        service.add_member(circle_id=circle.id, adder_id=test_user.id, user_id=test_user3.id)

        report_id = create_test_report(db_session, test_user.id, "Flooding at CP")

        with patch("src.domain.services.circle_notification_service.get_twilio_client", return_value=None):
            notif_service = CircleNotificationService(db_session)
            result = notif_service.notify_circles_for_report(
                report_id=report_id,
                reporter_user_id=test_user.id,
                latitude=28.63,
                longitude=77.22,
                description="Flooding at CP",
            )

        assert result.circles_count == 1
        assert result.alerts_created == 2  # user2 + user3 (not reporter)

    def test_reporter_does_not_get_own_alert(self, db_session, test_user, test_user2):
        """Reporter should NOT receive an alert for their own report."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id, name="Test", description=None, circle_type="custom"
        )
        service.add_member(circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id)

        report_id = create_test_report(db_session, test_user.id)

        with patch("src.domain.services.circle_notification_service.get_twilio_client", return_value=None):
            notif_service = CircleNotificationService(db_session)
            result = notif_service.notify_circles_for_report(
                report_id=report_id,
                reporter_user_id=test_user.id,
                latitude=28.63, longitude=77.22, description="Test",
            )

        assert result.alerts_created == 1  # Only user2


class TestDeduplication:
    """Test D2 — dedup against watch area alerts."""

    def test_skips_whatsapp_for_already_notified_user(self, db_session, test_user, test_user2):
        """If user2 already has a watch area alert for this report, skip WhatsApp/SMS."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id, name="Test", description=None, circle_type="custom"
        )
        service.add_member(
            circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id
        )

        report_id = create_test_report(db_session, test_user.id)
        # Simulate existing watch area alert for user2
        create_watch_area_alert(db_session, test_user2.id, report_id)

        with patch("src.domain.services.circle_notification_service.get_twilio_client", return_value=None):
            notif_service = CircleNotificationService(db_session)
            result = notif_service.notify_circles_for_report(
                report_id=report_id,
                reporter_user_id=test_user.id,
                latitude=28.63, longitude=77.22, description="Test",
            )

        assert result.alerts_created == 1  # CircleAlert still created (in-app)
        assert result.skipped_dedup == 1  # WhatsApp/SMS skipped


class TestMutedMembers:
    """Test that muted members are skipped."""

    def test_muted_members_skipped(self, db_session, test_user, test_user2):
        """Muted members should not receive any notification."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id, name="Test", description=None, circle_type="custom"
        )
        member = service.add_member(
            circle_id=circle.id, adder_id=test_user.id, user_id=test_user2.id
        )
        service.update_member(
            circle_id=circle.id, member_id=member.id,
            updater_id=test_user2.id, is_muted=True
        )

        report_id = create_test_report(db_session, test_user.id)

        with patch("src.domain.services.circle_notification_service.get_twilio_client", return_value=None):
            notif_service = CircleNotificationService(db_session)
            result = notif_service.notify_circles_for_report(
                report_id=report_id,
                reporter_user_id=test_user.id,
                latitude=28.63, longitude=77.22, description="Test",
            )

        assert result.alerts_created == 0
        assert result.skipped_muted == 1


class TestNoSilentFallbacks:
    """Test D8 — every failure is tracked, nothing silently swallowed."""

    def test_twilio_not_configured_tracked_in_errors(self, db_session, test_user):
        """When no notification channel is configured, errors are tracked."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id, name="Test", description=None, circle_type="custom"
        )
        # Add phone member (non-registered) — needs notify_sms=True for SMS fallback path
        service.add_member(
            circle_id=circle.id, adder_id=test_user.id,
            phone="9999999999", display_name="Contact"
        )

        report_id = create_test_report(db_session, test_user.id)

        # Disable Meta WhatsApp (primary channel) so SMS fallback is attempted
        with patch("src.domain.services.circle_notification_service.is_meta_whatsapp_enabled", return_value=False):
            with patch("src.domain.services.circle_notification_service.get_twilio_client", return_value=None):
                notif_service = CircleNotificationService(db_session)
                result = notif_service.notify_circles_for_report(
                    report_id=report_id,
                    reporter_user_id=test_user.id,
                    latitude=28.63, longitude=77.22, description="Test",
                )

        assert result.alerts_created == 1  # In-app alert still created
        assert len(result.errors) > 0  # Failures recorded
        # Verify failures are tracked, not silently swallowed
        error_text = " ".join(result.errors)
        assert "cannot send" in error_text or "not configured" in error_text

    def test_notification_result_to_dict(self):
        """NotificationResult.to_dict() returns complete summary."""
        from src.domain.models import NotificationResult
        result = NotificationResult(
            circles_count=2,
            alerts_created=5,
            whatsapp_sent=3,
            whatsapp_failed=1,
            sms_sent=1,
            errors=["WhatsApp to +919***:  error"],
        )
        d = result.to_dict()

        assert d["circles_notified"] == 2
        assert d["members_alerted"] == 5
        assert d["whatsapp_sent"] == 3
        assert d["whatsapp_failed"] == 1
        assert d["has_errors"] is True


class TestWhatsAppIntegration:
    """Test WhatsApp/SMS sending with mocked Twilio client."""

    def test_whatsapp_success(self, db_session, test_user):
        """Successful WhatsApp send updates CircleAlert record."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id, name="Test", description=None, circle_type="custom"
        )
        service.add_member(
            circle_id=circle.id, adder_id=test_user.id,
            phone="+919876543299", display_name="Contact",
        )

        report_id = create_test_report(db_session, test_user.id)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(sid="SM123")

        with patch("src.domain.services.circle_notification_service.get_twilio_client", return_value=mock_client):
            with patch("src.domain.services.circle_notification_service.settings") as mock_settings:
                mock_settings.TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155551234"
                mock_settings.TWILIO_SMS_NUMBER = "+14155551234"
                notif_service = CircleNotificationService(db_session)
                result = notif_service.notify_circles_for_report(
                    report_id=report_id,
                    reporter_user_id=test_user.id,
                    latitude=28.63, longitude=77.22, description="Test",
                )

        assert result.whatsapp_sent == 1
        assert result.whatsapp_failed == 0

        # Verify CircleAlert record has notification_sent=True
        alert = db_session.query(CircleAlert).first()
        assert alert is not None
        assert alert.notification_sent is True
        assert alert.notification_channel == "whatsapp"

    def test_whatsapp_fails_falls_back_to_sms(self, db_session, test_user):
        """If WhatsApp (Meta) fails, fall back to SMS (Twilio)."""
        service = CircleService(db_session)
        circle = service.create_circle(
            user_id=test_user.id, name="Test", description=None, circle_type="custom"
        )
        service.add_member(
            circle_id=circle.id, adder_id=test_user.id,
            phone="+919876543299", display_name="Contact",
        )

        report_id = create_test_report(db_session, test_user.id)

        # Mock Meta WhatsApp to be enabled but send fails
        # Mock Twilio for SMS success
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(sid="SM456")

        with patch("src.domain.services.circle_notification_service.is_meta_whatsapp_enabled", return_value=True):
            with patch("src.domain.services.circle_notification_service.send_text_message_sync", return_value=False):
                with patch("src.domain.services.circle_notification_service.get_twilio_client", return_value=mock_client):
                    with patch("src.domain.services.circle_notification_service.settings") as mock_settings:
                        mock_settings.TWILIO_SMS_NUMBER = "+14155551234"
                        notif_service = CircleNotificationService(db_session)
                        result = notif_service.notify_circles_for_report(
                            report_id=report_id,
                            reporter_user_id=test_user.id,
                            latitude=28.63, longitude=77.22, description="Test",
                        )

        assert result.whatsapp_failed == 1
        assert result.sms_sent == 1
        assert len(result.errors) == 1  # WhatsApp failure tracked
