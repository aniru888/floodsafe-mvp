"""
SOS Service — Offline-first emergency message fanout.

Receives SOS messages queued offline on the frontend and broadcasts them to
a list of recipients (Safety Circle members + emergency contacts) via SMS/WhatsApp.

Design principles:
- Accept raw phone numbers (not user IDs) — recipients include non-registered contacts
- Track every delivery attempt — no silent fallbacks (CLAUDE.md Rule #14)
- Return per-recipient status for transparency
- WhatsApp via Meta Cloud API (primary), SMS via Twilio (fallback)
"""

import logging
from typing import List, Dict, Optional
from ...core.phone_utils import normalize_phone
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_MakePoint
from geoalchemy2.elements import WKTElement

from ...infrastructure.models import SOSMessage, User
from ...core.config import settings
from .notification_service import get_twilio_client
from .whatsapp.meta_client import send_text_message_sync, is_meta_whatsapp_enabled

logger = logging.getLogger(__name__)


class SOSService:
    """
    Emergency SOS message broadcasting service.

    Sends SOS alerts to a list of phone numbers via WhatsApp (Meta) or SMS (Twilio).
    Tracks delivery status per recipient and stores results in DB.
    """

    def __init__(self, db: Session):
        self.db = db
        self.client = get_twilio_client()

    def is_configured(self) -> bool:
        """Check if any notification channel is available (Meta WhatsApp or Twilio SMS)."""
        whatsapp_ok = is_meta_whatsapp_enabled()
        sms_ok = self.client is not None and bool(settings.TWILIO_SMS_NUMBER)
        return whatsapp_ok or sms_ok

    def send_sos(
        self,
        user_id: UUID,
        message: str,
        recipients: List[Dict[str, str]],
        channel: str = "sms",
        location: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """
        Send SOS message to multiple recipients via SMS or WhatsApp.

        Args:
            user_id: UUID of user sending SOS
            message: Emergency message content (max 500 chars)
            recipients: List of {phone: str, name: str} dicts
            channel: 'sms' or 'whatsapp'
            location: Optional {lat: float, lng: float} dict

        Returns:
            {
                "id": UUID,
                "status": "sent" | "partial" | "failed",
                "total": int,
                "sent": int,
                "failed": int,
                "results": [{phone, name, status, channel, error}]
            }

        Raises:
            ValueError: If Twilio not configured or invalid input
        """
        if not self.is_configured():
            raise ValueError(
                "No notification channel configured. Set META_WHATSAPP_TOKEN + "
                "META_PHONE_NUMBER_ID for WhatsApp, or TWILIO_* vars for SMS."
            )

        if not recipients:
            raise ValueError("At least one recipient required")

        if channel not in ["sms", "whatsapp"]:
            raise ValueError("Channel must be 'sms' or 'whatsapp'")

        # Validate channel is configured
        if channel == "sms" and not settings.TWILIO_SMS_NUMBER:
            raise ValueError("SMS channel not configured (TWILIO_SMS_NUMBER missing)")
        if channel == "whatsapp" and not is_meta_whatsapp_enabled():
            raise ValueError("WhatsApp channel not configured (META_WHATSAPP_TOKEN missing)")

        # Create SOS message record (status = 'sending')
        location_geom = None
        if location and "lat" in location and "lng" in location:
            location_geom = WKTElement(
                f"POINT({location['lng']} {location['lat']})",
                srid=4326
            )

        sos_record = SOSMessage(
            user_id=user_id,
            message=message[:500],  # Enforce max length
            location=location_geom,
            recipients_json=recipients,  # Store original recipient list
            channel=channel,
            status="sending",
            sent_count=0,
            failed_count=0,
        )
        self.db.add(sos_record)
        self.db.commit()
        self.db.refresh(sos_record)

        # Send to each recipient
        results = []
        sent_count = 0
        failed_count = 0
        error_log_lines = []

        for recipient in recipients:
            phone = recipient.get("phone")
            name = recipient.get("name", "Unknown")

            if not phone:
                error_log_lines.append(f"Recipient {name}: No phone number provided")
                results.append({
                    "phone": None,
                    "name": name,
                    "status": "failed",
                    "channel": channel,
                    "error": "No phone number"
                })
                failed_count += 1
                continue

            # Normalize phone number
            try:
                normalized_phone = normalize_phone(phone)
            except Exception as e:
                error_log_lines.append(f"Recipient {name} ({phone}): Invalid phone - {e}")
                results.append({
                    "phone": phone,
                    "name": name,
                    "status": "failed",
                    "channel": channel,
                    "error": f"Invalid phone: {str(e)}"
                })
                failed_count += 1
                continue

            # Send message
            try:
                if channel == "whatsapp":
                    self._send_whatsapp(normalized_phone, message)
                else:
                    self._send_sms(normalized_phone, message)

                results.append({
                    "phone": normalized_phone,
                    "name": name,
                    "status": "sent",
                    "channel": channel,
                })
                sent_count += 1
                logger.info(f"Sent {channel} SOS to {name} ({normalized_phone})")

            except Exception as e:
                error_msg = str(e)
                error_log_lines.append(f"Recipient {name} ({normalized_phone}): {error_msg}")
                results.append({
                    "phone": normalized_phone,
                    "name": name,
                    "status": "failed",
                    "channel": channel,
                    "error": error_msg
                })
                failed_count += 1
                logger.error(f"Failed to send {channel} SOS to {name} ({normalized_phone}): {e}")

        # Update SOS record with final status
        overall_status = "sent" if failed_count == 0 else ("partial" if sent_count > 0 else "failed")
        sos_record.status = overall_status
        sos_record.sent_count = sent_count
        sos_record.failed_count = failed_count
        sos_record.sent_at = datetime.utcnow()
        sos_record.error_log = "\n".join(error_log_lines) if error_log_lines else None

        # Store per-recipient results in JSON
        sos_record.recipients_json = results

        self.db.commit()
        self.db.refresh(sos_record)

        return {
            "id": sos_record.id,
            "status": overall_status,
            "total": len(recipients),
            "sent": sent_count,
            "failed": failed_count,
            "results": results,
        }

    def _send_whatsapp(self, phone: str, message: str):
        """Send WhatsApp message via Meta Cloud API (sync)."""
        if not is_meta_whatsapp_enabled():
            raise RuntimeError("Meta WhatsApp not configured")

        success = send_text_message_sync(phone, message)
        if not success:
            raise RuntimeError("Meta Graph API send failed")

    def _send_sms(self, phone: str, message: str):
        """Send SMS via Twilio."""
        if not self.client:
            raise RuntimeError("Twilio client not initialized")

        if not settings.TWILIO_SMS_NUMBER:
            raise RuntimeError("SMS number not configured")

        self.client.messages.create(
            body=message,
            from_=settings.TWILIO_SMS_NUMBER,
            to=phone
        )
