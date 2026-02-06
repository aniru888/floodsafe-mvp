"""
SOS API Router — Emergency message fanout endpoint.

Single endpoint: POST /api/sos/send
Receives offline-queued SOS messages and fans them out to recipients via Twilio.

Authentication REQUIRED (user must be logged in to send SOS).
Location is optional (user might not have GPS).
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.infrastructure.models import User
from src.api.deps import get_current_user
from src.domain.services.sos_service import SOSService

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request / Response Schemas
# ═══════════════════════════════════════════════════════════════


class LocationSchema(BaseModel):
    """GPS coordinates (optional — user might not have GPS)."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")

    model_config = ConfigDict(from_attributes=True)


class RecipientSchema(BaseModel):
    """SOS recipient with phone number and optional display name."""
    phone: str = Field(..., min_length=10, max_length=20, description="Phone number (E.164 or 10-digit)")
    name: Optional[str] = Field(None, max_length=100, description="Display name")

    model_config = ConfigDict(from_attributes=True)


class SOSSendRequest(BaseModel):
    """Request to send an SOS message to multiple recipients."""
    message: str = Field(..., min_length=10, max_length=500, description="Emergency message")
    location: Optional[LocationSchema] = Field(None, description="GPS coordinates (optional)")
    recipients: List[RecipientSchema] = Field(..., min_items=1, max_items=50, description="1-50 recipients")
    channel: str = Field("sms", pattern="^(sms|whatsapp)$", description="Delivery channel: sms or whatsapp")

    model_config = ConfigDict(from_attributes=True)


class RecipientResultSchema(BaseModel):
    """Delivery result for a single recipient."""
    phone: Optional[str] = Field(None, description="Normalized phone number (E.164)")
    name: str = Field(..., description="Display name")
    status: str = Field(..., pattern="^(sent|failed)$", description="Delivery status")
    channel: str = Field(..., description="Delivery channel used")
    error: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(from_attributes=True)


class SOSSendResponse(BaseModel):
    """Response from SOS send operation with per-recipient results."""
    id: UUID = Field(..., description="SOS message UUID")
    status: str = Field(..., pattern="^(sent|partial|failed)$", description="Overall status")
    total: int = Field(..., ge=0, description="Total recipients")
    sent: int = Field(..., ge=0, description="Successfully sent")
    failed: int = Field(..., ge=0, description="Failed to send")
    results: List[RecipientResultSchema] = Field(..., description="Per-recipient delivery results")

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════


@router.post("/send", response_model=SOSSendResponse)
async def send_sos(
    request: SOSSendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send emergency SOS message to multiple recipients via SMS or WhatsApp.

    **Authentication:** Required (Bearer token)

    **Use case:** Frontend queues SOS when offline, sends when back online.
    Recipients include Safety Circle members + emergency contacts (may be non-registered).

    **Request:**
    ```json
    {
      "message": "Emergency: Flooding at my location, need help!",
      "location": {"lat": 28.6139, "lng": 77.209},
      "recipients": [
        {"phone": "+911234567890", "name": "Mom"},
        {"phone": "+919876543210", "name": "Dad"}
      ],
      "channel": "sms"
    }
    ```

    **Response:**
    ```json
    {
      "id": "uuid",
      "status": "sent",
      "total": 2,
      "sent": 2,
      "failed": 0,
      "results": [
        {"phone": "+911234567890", "name": "Mom", "status": "sent", "channel": "sms"},
        {"phone": "+919876543210", "name": "Dad", "status": "sent", "channel": "sms"}
      ]
    }
    ```

    **Status:**
    - `sent`: All recipients received message
    - `partial`: Some succeeded, some failed
    - `failed`: All failed (Twilio misconfigured or no valid phone numbers)

    **Errors:**
    - 400: Twilio not configured, invalid channel, or validation error
    - 401: Unauthorized (no token or expired)
    - 500: Unexpected server error
    """
    try:
        service = SOSService(db)

        # Convert Pydantic models to dicts for service
        recipients_data = [{"phone": r.phone, "name": r.name or "Unknown"} for r in request.recipients]
        location_data = None
        if request.location:
            location_data = {"lat": request.location.lat, "lng": request.location.lng}

        result = service.send_sos(
            user_id=user.id,
            message=request.message,
            recipients=recipients_data,
            channel=request.channel,
            location=location_data,
        )

        logger.info(
            f"SOS sent by user {user.id}: {result['sent']}/{result['total']} succeeded, "
            f"status={result['status']}"
        )

        return SOSSendResponse(**result)

    except ValueError as e:
        # Configuration or validation errors
        logger.warning(f"SOS validation error for user {user.id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error sending SOS for user {user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to send SOS. Please try again or contact support."
        )
