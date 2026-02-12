"""
Twilio-based notification service for WhatsApp and SMS alerts.

Implements INotificationService interface for sending flood alerts
to users via their preferred channels (WhatsApp, SMS).

Features:
- Respects user notification preferences
- Supports both WhatsApp and SMS channels
- Broadcast emergency to all users in a geographic area
- Graceful fallback when Twilio is not configured
"""
import logging
from typing import Optional, List
from uuid import UUID
from ...core.phone_utils import normalize_phone

from sqlalchemy.orm import Session
from sqlalchemy import text

from .interfaces import INotificationService
from ...infrastructure.models import User, WatchArea
from ...core.config import settings

logger = logging.getLogger(__name__)

# Lazy import Twilio to allow app to start without it installed
_twilio_client = None


def get_twilio_client():
    """Lazy-load Twilio client to avoid import errors when not configured."""
    global _twilio_client

    if _twilio_client is not None:
        return _twilio_client

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not configured - notifications disabled")
        return None

    try:
        from twilio.rest import Client
        _twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully")
        return _twilio_client
    except ImportError:
        logger.error("Twilio package not installed - run: pip install twilio")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        return None


class TwilioNotificationService(INotificationService):
    """
    Twilio-based implementation of INotificationService.

    Sends notifications via WhatsApp or SMS based on user preferences.
    Falls back gracefully when Twilio is not configured.
    """

    def __init__(self, db: Session):
        self.db = db
        self.client = get_twilio_client()

    def is_configured(self) -> bool:
        """Check if Twilio is properly configured and ready."""
        return self.client is not None and bool(settings.TWILIO_WHATSAPP_NUMBER)

    async def send_alert(self, user_id: UUID, message: str, channel: str = "whatsapp") -> bool:
        """
        Send an alert to a specific user via their preferred channel.

        Args:
            user_id: The UUID of the user to notify
            message: The alert message content
            channel: 'whatsapp' or 'sms'

        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning(f"Twilio not configured - skipping notification to user {user_id}")
            return False

        # Fetch user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User {user_id} not found")
            return False

        # Check user notification preferences
        if channel == "whatsapp" and not user.notification_whatsapp:
            logger.debug(f"User {user_id} has WhatsApp notifications disabled")
            return False
        if channel == "sms" and not user.notification_sms:
            logger.debug(f"User {user_id} has SMS notifications disabled")
            return False

        # Get phone number
        if not user.phone:
            logger.warning(f"User {user_id} has no phone number")
            return False

        # Normalize phone number (ensure it has country code)
        phone = normalize_phone(user.phone)

        try:
            if channel == "whatsapp":
                self._send_whatsapp(phone, message)
            else:
                self._send_sms(phone, message)

            logger.info(f"Sent {channel} notification to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send {channel} to user {user_id}: {e}")
            return False

    async def broadcast_emergency(self, geofence_polygon: dict, message: str) -> int:
        """
        Send emergency alert to all users with watch areas intersecting the polygon.

        Args:
            geofence_polygon: GeoJSON polygon defining the affected area
            message: The emergency message content

        Returns:
            Number of users notified
        """
        if not self.is_configured():
            logger.warning("Twilio not configured - skipping emergency broadcast")
            return 0

        # Find all users with watch areas in the affected polygon
        # Using PostGIS ST_Intersects for spatial query
        try:
            # Query users with watch areas intersecting the polygon
            query = text("""
                SELECT DISTINCT u.id, u.phone, u.notification_whatsapp, u.notification_sms
                FROM users u
                JOIN watch_areas wa ON wa.user_id = u.id
                WHERE ST_Intersects(
                    wa.location::geography,
                    ST_GeomFromGeoJSON(:geojson)::geography
                )
                AND u.phone IS NOT NULL
                AND (u.notification_whatsapp = true OR u.notification_sms = true)
            """)

            import json
            result = self.db.execute(query, {'geojson': json.dumps(geofence_polygon)})
            users = result.fetchall()

            notified_count = 0
            for user_row in users:
                user_id, phone, pref_whatsapp, pref_sms = user_row
                phone = normalize_phone(phone)

                try:
                    if pref_whatsapp:
                        self._send_whatsapp(phone, message)
                        notified_count += 1
                    elif pref_sms:
                        self._send_sms(phone, message)
                        notified_count += 1
                except Exception as e:
                    logger.error(f"Failed to send emergency to {user_id}: {e}")

            logger.info(f"Emergency broadcast sent to {notified_count} users")
            return notified_count

        except Exception as e:
            logger.error(f"Failed to execute broadcast query: {e}")
            return 0

    async def notify_watch_area_users(self, watch_area_ids: List[UUID], message: str) -> int:
        """
        Send notification to all users who own the specified watch areas.

        This is called by AlertService after creating Alert records.

        Args:
            watch_area_ids: List of watch area UUIDs that are affected
            message: The alert message

        Returns:
            Number of users notified
        """
        if not self.is_configured():
            logger.warning("Twilio not configured - skipping watch area notifications")
            return 0

        if not watch_area_ids:
            return 0

        # Get unique users from watch areas
        watch_areas = self.db.query(WatchArea).filter(
            WatchArea.id.in_(watch_area_ids)
        ).all()

        user_ids_seen = set()
        notified_count = 0

        for wa in watch_areas:
            if wa.user_id in user_ids_seen:
                continue
            user_ids_seen.add(wa.user_id)

            if await self.send_alert(wa.user_id, message, channel="whatsapp"):
                notified_count += 1

        return notified_count

    def _send_whatsapp(self, phone: str, message: str):
        """Send WhatsApp message via Twilio."""
        if not self.client:
            raise RuntimeError("Twilio client not initialized")

        self.client.messages.create(
            body=message,
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{phone}"
        )

    def _send_sms(self, phone: str, message: str):
        """Send SMS via Twilio."""
        if not self.client:
            raise RuntimeError("Twilio client not initialized")

        if not settings.TWILIO_SMS_NUMBER:
            logger.warning("SMS number not configured - cannot send SMS")
            raise RuntimeError("SMS number not configured")

        self.client.messages.create(
            body=message,
            from_=settings.TWILIO_SMS_NUMBER,
            to=phone
        )


# Singleton instance for easy access
_notification_service_instance: Optional[TwilioNotificationService] = None


def get_notification_service(db: Session) -> TwilioNotificationService:
    """Get or create notification service instance."""
    return TwilioNotificationService(db)
