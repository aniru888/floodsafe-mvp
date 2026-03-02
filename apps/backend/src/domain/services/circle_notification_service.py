"""
Circle Notification Service — Fan-out notifications when circle members create reports.

Design decisions:
- D1: Synchronous (matches AlertService pattern, Twilio calls are blocking anyway)
- D2: Dedup against watch area alerts (don't double-notify registered users)
- D3: Throttle WhatsApp/SMS at 50 per circle per report (CircleAlerts unlimited)
- D8: No silent fallbacks — every failure tracked in NotificationResult
"""

import logging
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...infrastructure.models import (
    SafetyCircle,
    CircleMember,
    CircleAlert,
    Alert,
    User,
)
from ...domain.models import NotificationResult
from .notification_service import get_twilio_client
from .circle_service import CircleService
from ...core.config import settings
from .whatsapp.meta_client import send_text_message_sync, is_meta_whatsapp_enabled

logger = logging.getLogger(__name__)

# Max WhatsApp/SMS messages per circle per report (D3)
MAX_EXTERNAL_NOTIFICATIONS_PER_CIRCLE = 50


class CircleNotificationService:
    """Sends notifications to Safety Circle members when a report is created.

    All methods are synchronous (D1).
    """

    def __init__(self, db: Session):
        self.db = db
        self.twilio_client = get_twilio_client()  # For SMS only

    def is_whatsapp_configured(self) -> bool:
        """Check if Meta WhatsApp is available for sending."""
        return is_meta_whatsapp_enabled()

    def is_sms_configured(self) -> bool:
        """Check if Twilio SMS is available."""
        return self.twilio_client is not None and bool(settings.TWILIO_SMS_NUMBER)

    def notify_circles_for_report(
        self,
        report_id: UUID,
        reporter_user_id: UUID,
        latitude: float,
        longitude: float,
        description: str,
    ) -> NotificationResult:
        """Fan-out notifications to all circles the reporter belongs to.

        Returns NotificationResult tracking every success AND failure (D8).
        """
        result = NotificationResult()

        # 1. Find all circles where reporter is a member
        reporter_circles = (
            self.db.query(SafetyCircle)
            .join(CircleMember, CircleMember.circle_id == SafetyCircle.id)
            .filter(
                CircleMember.user_id == reporter_user_id,
                SafetyCircle.is_active == True,
            )
            .all()
        )

        if not reporter_circles:
            return result  # Not in any circles

        result.circles_count = len(reporter_circles)

        # Get reporter name for messages
        reporter = self.db.query(User).filter(User.id == reporter_user_id).first()
        reporter_name = (
            reporter.display_name or reporter.username if reporter else "A member"
        )

        # 2. Collect user_ids already notified via watch area alerts (D2 dedup)
        already_notified_user_ids = set()
        existing_alerts = (
            self.db.query(Alert.user_id)
            .filter(Alert.report_id == report_id)
            .all()
        )
        for (uid,) in existing_alerts:
            already_notified_user_ids.add(uid)

        # 3. Process each circle
        for circle in reporter_circles:
            self._process_circle(
                circle=circle,
                report_id=report_id,
                reporter_user_id=reporter_user_id,
                reporter_name=reporter_name,
                description=description,
                already_notified_user_ids=already_notified_user_ids,
                result=result,
            )

        logger.info(
            f"Circle notifications for report {report_id}: "
            f"circles={result.circles_count}, alerts={result.alerts_created}, "
            f"whatsapp={result.whatsapp_sent}/{result.whatsapp_failed}, "
            f"sms={result.sms_sent}/{result.sms_failed}, "
            f"muted={result.skipped_muted}, dedup={result.skipped_dedup}, "
            f"throttled={result.skipped_throttle}"
        )

        return result

    def _process_circle(
        self,
        circle: SafetyCircle,
        report_id: UUID,
        reporter_user_id: UUID,
        reporter_name: str,
        description: str,
        already_notified_user_ids: set,
        result: NotificationResult,
    ) -> None:
        """Process a single circle: create alerts + send notifications."""
        # Get all OTHER members (not the reporter)
        # Note: NULL != value is NULL in SQL, so we must explicitly include NULL user_ids
        members = (
            self.db.query(CircleMember)
            .filter(
                CircleMember.circle_id == circle.id,
                or_(
                    CircleMember.user_id != reporter_user_id,
                    CircleMember.user_id.is_(None),
                ),
            )
            .all()
        )

        # Also exclude non-registered members that are the reporter
        # (reporter might have phone/email entries without user_id)

        external_sent_count = 0  # Track per-circle for throttle (D3)

        # Build message
        message = (
            f"\U0001f6a8 {reporter_name} reported flooding near your area.\n"
            f"Circle: {circle.name}\n"
            f"Details: {description[:100]}\n"
            f"Open FloodSafe for more details."
        )

        for member in members:
            # Skip muted members
            if member.is_muted:
                result.skipped_muted += 1
                continue

            # ALWAYS create CircleAlert record (in-app display)
            alert_record = CircleAlert(
                circle_id=circle.id,
                report_id=report_id,
                reporter_user_id=reporter_user_id,
                member_id=member.id,
                message=message,
                is_read=False,
                notification_sent=False,
                notification_channel="in_app",
            )
            self.db.add(alert_record)
            result.alerts_created += 1

            # D2: Skip WhatsApp/SMS if registered user already notified via watch area
            if member.user_id and member.user_id in already_notified_user_ids:
                result.skipped_dedup += 1
                self.db.flush()
                continue

            # D3: Check throttle cap for this circle
            if external_sent_count >= MAX_EXTERNAL_NOTIFICATIONS_PER_CIRCLE:
                result.skipped_throttle += 1
                self.db.flush()
                continue

            # Try WhatsApp/SMS for members with phone numbers
            can_send = self.is_whatsapp_configured() or self.is_sms_configured()
            if member.phone and can_send:
                sent = self._try_send_external(
                    member=member,
                    alert_record=alert_record,
                    message=message,
                    result=result,
                )
                if sent:
                    external_sent_count += 1
            elif member.phone and not can_send:
                # D8: Explicitly track that no channel is configured
                result.errors.append(
                    f"No WhatsApp/SMS channel configured — cannot send to "
                    f"{member.phone[:4]}***"
                )

            self.db.flush()

        # Commit all CircleAlert records for this circle
        self.db.commit()

    def _try_send_external(
        self,
        member: CircleMember,
        alert_record: CircleAlert,
        message: str,
        result: NotificationResult,
    ) -> bool:
        """Try sending WhatsApp, fall back to SMS. Returns True if any succeeded.

        Every failure is tracked (D8).
        """
        phone = member.phone

        # Try WhatsApp first
        if member.notify_whatsapp:
            success, error = self._send_whatsapp(phone, message)
            if success:
                result.whatsapp_sent += 1
                alert_record.notification_sent = True
                alert_record.notification_channel = "whatsapp"
                return True
            else:
                result.whatsapp_failed += 1
                result.errors.append(f"WhatsApp to {phone[:4]}***: {error}")

        # Fall back to SMS
        if member.notify_sms:
            success, error = self._send_sms(phone, message)
            if success:
                result.sms_sent += 1
                alert_record.notification_sent = True
                alert_record.notification_channel = "sms"
                return True
            else:
                result.sms_failed += 1
                result.errors.append(f"SMS to {phone[:4]}***: {error}")

        return False

    def _send_whatsapp(self, phone: str, message: str) -> tuple[bool, str]:
        """Send WhatsApp message via Meta Cloud API (sync). Returns (success, error_message)."""
        try:
            if not is_meta_whatsapp_enabled():
                return False, "Meta WhatsApp not configured"

            success = send_text_message_sync(phone, message)
            if not success:
                return False, "Meta Graph API send failed"
            return True, ""
        except Exception as e:
            return False, str(e)

    def _send_sms(self, phone: str, message: str) -> tuple[bool, str]:
        """Send SMS message. Returns (success, error_message)."""
        try:
            if not self.twilio_client:
                return False, "Twilio not configured"

            if not settings.TWILIO_SMS_NUMBER:
                return False, "SMS number not configured"

            self.twilio_client.messages.create(
                body=message,
                from_=settings.TWILIO_SMS_NUMBER,
                to=phone,
            )
            return True, ""
        except Exception as e:
            return False, str(e)
