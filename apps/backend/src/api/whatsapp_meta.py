"""
Meta WhatsApp Cloud API Webhook Handler.

Runs IN PARALLEL with the existing Twilio webhook (/api/whatsapp).
Zero risk to existing functionality — this is a completely separate endpoint.

Meta Cloud API differences from Twilio:
- JSON payloads (not form-encoded)
- Messages sent via Graph API POST (not TwiML XML response)
- Webhook verification via GET challenge-response
- Media downloaded via Graph API (not Twilio Basic Auth)
- Signature validation via X-Hub-Signature-256 header (HMAC-SHA256)

Endpoint: /api/whatsapp-meta
"""
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from ..infrastructure.database import get_db
from ..infrastructure.models import User, WhatsAppSession
from ..core.config import settings
from ..core.phone_utils import normalize_phone
from ..domain.services.whatsapp.meta_client import (
    is_meta_whatsapp_enabled,
    send_text_message as meta_send_text,
    send_interactive_buttons as meta_send_buttons,
    download_media as meta_download_media,
    mark_as_read,
    send_welcome_buttons,
    send_after_location_buttons,
    send_after_report_buttons,
    send_risk_result_buttons,
    send_account_choice_buttons,
    send_menu_buttons,
)
from ..domain.services.whatsapp import (
    TemplateKey, get_message, get_user_language,
    process_sos_with_photo, get_severity_from_classification,
    handle_risk_command, handle_warnings_command, handle_my_areas_command,
    handle_help_command, handle_status_command, get_readable_location,
)
from ..domain.services.wit_service import classify_message, get_mapped_command, is_wit_enabled

router = APIRouter()
logger = logging.getLogger(__name__)

# Session timeout (30 minutes)
SESSION_TIMEOUT_MINUTES = 30

# Rate limiting (shared format with Twilio webhook)
RATE_LIMIT_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 60
_rate_limit_cache: dict[str, list[datetime]] = {}


def _check_rate_limit(phone: str) -> bool:
    """Check rate limit for phone number."""
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    if phone not in _rate_limit_cache:
        _rate_limit_cache[phone] = []
    _rate_limit_cache[phone] = [t for t in _rate_limit_cache[phone] if t > window_start]
    if len(_rate_limit_cache[phone]) >= RATE_LIMIT_MESSAGES:
        return False
    _rate_limit_cache[phone].append(now)
    return True


def _validate_signature(request: Request, body: bytes) -> bool:
    """
    Validate Meta webhook signature using X-Hub-Signature-256.

    Meta signs payloads with HMAC-SHA256 using the app secret.
    """
    if not settings.META_APP_SECRET:
        logger.error("META_APP_SECRET not configured — rejecting webhook for security")
        return False

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header")
        return False

    expected_signature = signature_header[7:]  # Remove "sha256=" prefix
    computed_signature = hmac.new(
        settings.META_APP_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


def _get_or_create_session(db: Session, phone: str) -> WhatsAppSession:
    """Get existing session or create new one."""
    session = db.query(WhatsAppSession).filter(WhatsAppSession.phone == phone).first()
    if session:
        if session.updated_at < datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            session.state = "idle"
            session.data = {}
            db.commit()
        return session
    session = WhatsAppSession(phone=phone, state="idle", data={})
    db.add(session)
    db.commit()
    return session


def _find_user_by_phone(db: Session, phone: str) -> Optional[User]:
    """Find user by phone number (single query using normalized E.164)."""
    normalized = normalize_phone(phone)
    return db.query(User).filter(User.phone == normalized).first()


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

@router.get("/health")
async def whatsapp_meta_health():
    """Health check for Meta WhatsApp integration.

    Returns status of Meta WhatsApp config, ML classifier, and Wit.ai.
    """
    # Meta WhatsApp config
    meta_ok = is_meta_whatsapp_enabled()

    # ML classifier
    ml_available = False
    if settings.ML_ENABLED:
        try:
            from ..domain.ml.tflite_classifier import get_classifier
            get_classifier()
            ml_available = True
        except Exception:
            pass

    # Wit.ai NLU
    wit_ok = is_wit_enabled()

    status = "healthy" if meta_ok else "degraded"

    return {
        "status": status,
        "meta_whatsapp": {
            "enabled": meta_ok,
            "phone_number_id": bool(settings.META_PHONE_NUMBER_ID),
            "token_set": bool(settings.META_WHATSAPP_TOKEN),
        },
        "ml_classifier": {
            "enabled": settings.ML_ENABLED,
            "available": ml_available,
        },
        "wit_ai": {
            "enabled": wit_ok,
        },
    }


# =============================================================================
# WEBHOOK ENDPOINTS
# =============================================================================

@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification endpoint.

    Meta sends a GET request with hub.mode=subscribe, hub.verify_token,
    and hub.challenge. We must return the challenge if the token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        logger.info("Meta webhook verified successfully")
        return int(hub_challenge) if hub_challenge else ""

    logger.warning(f"Meta webhook verification failed: mode={hub_mode}")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def handle_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Main Meta WhatsApp Cloud API webhook handler.

    Receives JSON messages from Meta and processes them.
    Sends responses via Graph API (not in HTTP response body).
    Always returns 200 to acknowledge receipt.
    """
    if not is_meta_whatsapp_enabled():
        return {"status": "disabled"}

    # Read raw body for signature validation
    body = await request.body()

    # Validate signature
    if not _validate_signature(request, body):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse JSON
    try:
        data = await request.json()
    except Exception:
        logger.warning("Invalid JSON in Meta webhook payload")
        return {"status": "ok"}

    # Meta sends a "object" field — must be "whatsapp_business_account"
    if data.get("object") != "whatsapp_business_account":
        return {"status": "ok"}

    # Process each entry
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue

            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])

            for message in messages:
                await _process_message(db, message, contacts)

    return {"status": "ok"}


async def _process_message(
    db: Session,
    message: dict,
    contacts: list,
):
    """
    Process a single incoming WhatsApp message.

    Message types: text, image, location, interactive (button replies).
    """
    phone = message.get("from", "")
    message_id = message.get("id", "")
    msg_type = message.get("type", "")
    timestamp = message.get("timestamp", "")

    if not phone:
        return

    # Format phone with + prefix for consistency
    if not phone.startswith("+"):
        phone = f"+{phone}"

    phone_masked = f"***{phone[-4:]}" if len(phone) >= 4 else "***"
    logger.info(f"Meta webhook: phone={phone_masked}, type={msg_type}")

    # Rate limiting
    if not _check_rate_limit(phone):
        await meta_send_text(phone, "You're sending too many messages. Please wait a minute.")
        return

    # Mark as read
    if message_id:
        await mark_as_read(message_id)

    # Get session and user
    try:
        session = _get_or_create_session(db, phone)
        user = (session.user_id and db.query(User).filter(User.id == session.user_id).first())
        if not user:
            user = _find_user_by_phone(db, phone)
            if user:
                session.user_id = user.id
                db.commit()
    except Exception as e:
        logger.error(f"DB error for {phone_masked}: {e}")
        db.rollback()
        await meta_send_text(phone, "Sorry, we're experiencing technical difficulties.")
        return

    language = get_user_language(user)

    # ===========================================
    # ROUTE BY MESSAGE TYPE
    # ===========================================

    if msg_type == "interactive":
        # Button reply
        interactive = message.get("interactive", {})
        if interactive.get("type") == "button_reply":
            button_id = interactive.get("button_reply", {}).get("id", "")
            await _handle_button(db, session, phone, user, button_id, language)
            return

    if msg_type == "location":
        # Location message
        location = message.get("location", {})
        lat = location.get("latitude")
        lng = location.get("longitude")
        if lat is not None and lng is not None:
            await _handle_location(db, session, phone, user, lat, lng, language)
        return

    if msg_type == "image":
        # Image message
        image = message.get("image", {})
        media_id = image.get("id")
        caption = image.get("caption", "")

        # Check if we have a pending location
        if session.data and "pending_lat" in session.data:
            await _handle_photo_for_pending_location(
                db, session, phone, user, media_id, language
            )
        else:
            # Store image, prompt for location
            session.data = session.data or {}
            session.data["pending_media_id"] = media_id
            session.updated_at = datetime.utcnow()
            db.commit()
            await meta_send_text(
                phone,
                get_message(TemplateKey.RISK_NO_LOCATION, language) if language == 'hi' else
                "Photo received! Now please share your location:\n\n"
                "1. Tap the + icon\n"
                "2. Select 'Location'\n"
                "3. Send your current location"
            )
        return

    if msg_type == "text":
        text = message.get("text", {}).get("body", "").strip()
        await _handle_text(db, session, phone, user, text, language)
        return

    # Unknown message type — send welcome
    await meta_send_text(phone, get_message(TemplateKey.WELCOME, language))


async def _handle_text(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle text message — Wit.ai NLU + keyword fallback."""
    text_lower = text.lower()

    # Handle session states (onboarding flow)
    if session.state == "awaiting_choice":
        await _handle_account_choice(db, session, phone, user, text, language)
        return

    if session.state == "awaiting_email":
        await _handle_email_input(db, session, phone, user, text, language)
        return

    if session.state == "awaiting_photo":
        if text_lower == "skip":
            await _finalize_without_photo(db, session, phone, user, language)
        else:
            await meta_send_text(
                phone,
                get_message(TemplateKey.REPORT_NO_PHOTO, language)
            )
        return

    # Wit.ai NLU (for natural language — skip for known keywords)
    if is_wit_enabled() and not text_lower.startswith(("risk", "warnings", "alerts", "help", "menu", "status")):
        wit_result = await classify_message(text)
        if wit_result:
            mapped = get_mapped_command(wit_result)
            if mapped == "risk":
                place_name = wit_result.location
                last_loc = None
                if not place_name and session.data and "last_lat" in session.data:
                    last_loc = (session.data["last_lat"], session.data["last_lng"])
                response = await handle_risk_command(db, user, place_name, last_loc)
                await meta_send_text(phone, response)
                return
            elif mapped == "warnings":
                response = await handle_warnings_command(db, user)
                await meta_send_text(phone, response)
                return
            elif mapped == "my_areas":
                response = await handle_my_areas_command(db, user)
                await meta_send_text(phone, response)
                return
            elif mapped == "help":
                response = await handle_help_command(user)
                await meta_send_text(phone, response)
                return
            elif mapped == "status":
                response = await handle_status_command(db, user, phone)
                await meta_send_text(phone, response)
                return

    # Keyword matching (same as Twilio webhook)
    if text_lower.startswith("risk"):
        place_name = text[4:].strip() if len(text) > 4 else None
        last_loc = None
        if session.data and "last_lat" in session.data:
            last_loc = (session.data["last_lat"], session.data["last_lng"])
        response = await handle_risk_command(db, user, place_name, last_loc)
        await meta_send_text(phone, response)
        return

    if text_lower in ("warnings", "alerts", "alert", "warning"):
        response = await handle_warnings_command(db, user)
        await meta_send_text(phone, response)
        return

    if text_lower in ("my areas", "myareas", "areas", "my area", "watch areas"):
        response = await handle_my_areas_command(db, user)
        await meta_send_text(phone, response)
        return

    if text_lower in ("help", "?", "commands", "menu"):
        response = await handle_help_command(user)
        await meta_send_text(phone, response)
        return

    if text_lower in ("status", "info", "account"):
        response = await handle_status_command(db, user, phone)
        await meta_send_text(phone, response)
        return

    if text_lower in ("sos", "emergency", "flood"):
        await meta_send_text(
            phone,
            "To send an SOS alert, please share your location:\n"
            "1. Tap the + icon\n"
            "2. Select 'Location'\n"
            "3. Send your current location"
        )
        return

    if text_lower == "link":
        if user:
            await meta_send_text(
                phone,
                f"Your WhatsApp is already linked to {user.email}.\n"
                f"No action needed!"
            )
            return
        session.state = "awaiting_choice"
        session.updated_at = datetime.utcnow()
        db.commit()
        await send_account_choice_buttons(phone, language)
        return

    if text_lower == "stop":
        if user:
            user.notification_whatsapp = False
            db.commit()
            await meta_send_text(
                phone,
                "You've unsubscribed from WhatsApp alerts.\n"
                "You can still use the FloodSafe app.\n\n"
                "Reply START to re-subscribe."
            )
        else:
            await meta_send_text(
                phone,
                "You've been unsubscribed from WhatsApp alerts.\n"
                "Reply START to re-subscribe."
            )
        return

    if text_lower == "start":
        if user:
            user.notification_whatsapp = True
            db.commit()
            await meta_send_text(
                phone,
                "Welcome back! You're subscribed to flood alerts.\n"
                "Send a photo + your location to report flooding."
            )
        else:
            await meta_send_text(phone, get_message(TemplateKey.WELCOME, language))
            await send_welcome_buttons(phone, language)
        return

    # Default: welcome message with interactive buttons
    await meta_send_text(phone, get_message(TemplateKey.WELCOME, language))
    await send_welcome_buttons(phone, language)


async def _handle_location(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    latitude: float,
    longitude: float,
    language: str,
):
    """Handle location message — check for pending media or prompt for photo."""
    session.data = session.data or {}
    session.data["last_lat"] = latitude
    session.data["last_lng"] = longitude

    # Check for pending media (user sent photo first)
    pending_media_id = session.data.get("pending_media_id")
    if pending_media_id:
        del session.data["pending_media_id"]
        # Download and process photo
        photo_bytes = await meta_download_media(pending_media_id)
        if photo_bytes:
            await _create_report_with_photo(
                db, session, phone, user, latitude, longitude,
                photo_bytes, language
            )
            return

    # No photo — prompt for one
    session.state = "awaiting_photo"
    session.data["pending_lat"] = latitude
    session.data["pending_lng"] = longitude
    session.updated_at = datetime.utcnow()
    db.commit()

    await send_after_location_buttons(phone, language)


async def _handle_photo_for_pending_location(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    media_id: str,
    language: str,
):
    """Handle photo when we have a pending location."""
    lat = session.data.get("pending_lat")
    lng = session.data.get("pending_lng")

    if not lat or not lng:
        session.state = "idle"
        db.commit()
        await meta_send_text(phone, get_message(TemplateKey.WELCOME, language))
        return

    photo_bytes = await meta_download_media(media_id)
    if photo_bytes:
        await _create_report_with_photo(
            db, session, phone, user, lat, lng, photo_bytes, language
        )
    else:
        await meta_send_text(
            phone,
            "Failed to download your photo. Please try sending it again."
        )


async def _create_report_with_photo(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    latitude: float,
    longitude: float,
    photo_bytes: bytes,
    language: str,
):
    """Create a flood report with photo and ML classification."""
    from ..infrastructure.models import Report
    from ..domain.services.alert_service import AlertService

    # Classify photo with ML (process_sos_with_photo expects a URL, but
    # for Meta we have raw bytes — we need to use the classifier directly)
    classification = None
    try:
        from ..domain.services.whatsapp.photo_handler import classify_flood_image
        classification = await classify_flood_image(photo_bytes)
    except Exception as e:
        logger.warning(f"ML classification failed: {e}")

    # Build description
    if classification and classification.is_flood:
        description = f"[SOS WhatsApp-Meta] Flood verified by AI ({int(classification.confidence * 100)}%)"
    elif classification:
        description = "[SOS WhatsApp-Meta] Photo submitted (AI: no flood detected)"
    else:
        description = "[SOS WhatsApp-Meta] Photo submitted (ML unavailable)"

    verified = True
    if classification and not classification.is_flood:
        verified = False

    # Build media metadata from classification (same pattern as Twilio webhook)
    media_metadata = None
    if classification:
        media_metadata = {
            "ml_classification": classification.classification,
            "ml_confidence": classification.confidence,
            "is_flood": classification.is_flood,
            "needs_review": classification.needs_review,
        }

    report = Report(
        location=f"POINT({longitude} {latitude})",
        description=description,
        verified=verified,
        location_verified=True,
        water_depth="impassable" if (classification and classification.is_flood) else "unknown",
        user_id=user.id if user else None,
        phone_number=phone,
        media_metadata=media_metadata,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Trigger alerts
    alert_service = AlertService(db)
    alerts_count = alert_service.check_watch_areas_for_report(
        report.id, latitude, longitude, user.id if user else None
    )

    # Reset session
    session.state = "idle"
    session.data = {"last_lat": latitude, "last_lng": longitude}
    session.updated_at = datetime.utcnow()
    db.commit()

    # Send response
    location_name = get_readable_location(latitude, longitude)
    if classification and classification.is_flood:
        confidence_pct = int(classification.confidence * 100)
        severity = get_severity_from_classification(classification)
        response = get_message(
            TemplateKey.REPORT_FLOOD_DETECTED,
            language,
            location=location_name,
            confidence=confidence_pct,
            severity=severity,
            alerts_count=alerts_count,
        )
    elif classification:
        response = get_message(
            TemplateKey.REPORT_NO_FLOOD,
            language,
            location=location_name,
        )
    else:
        response = get_message(
            TemplateKey.ML_UNAVAILABLE,
            language,
            location=location_name,
            alerts_count=alerts_count,
        )

    await meta_send_text(phone, response)
    await send_after_report_buttons(phone, language)


async def _finalize_without_photo(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    language: str,
):
    """Submit report without photo (SKIP)."""
    from ..infrastructure.models import Report
    from ..domain.services.alert_service import AlertService

    lat = session.data.get("pending_lat")
    lng = session.data.get("pending_lng")

    if not lat or not lng:
        session.state = "idle"
        db.commit()
        await meta_send_text(phone, "Nothing to skip.")
        return

    location_name = get_readable_location(lat, lng)

    report = Report(
        location=f"POINT({lng} {lat})",
        description=f"[SOS WhatsApp-Meta] Location-only report from {phone}",
        verified=True,
        location_verified=True,
        water_depth="unknown",
        user_id=user.id if user else None,
        phone_number=phone,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    alert_service = AlertService(db)
    alerts_count = alert_service.check_watch_areas_for_report(
        report.id, lat, lng, user.id if user else None
    )

    session.state = "idle"
    session.data = {"last_lat": lat, "last_lng": lng}
    session.updated_at = datetime.utcnow()
    db.commit()

    response = get_message(
        TemplateKey.REPORT_NO_PHOTO_SKIP,
        language,
        location=location_name,
        alerts_count=alerts_count,
    )
    await meta_send_text(phone, response)


async def _handle_account_choice(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle user's choice to create account or stay anonymous."""
    choice = text.strip()

    if choice in ("1", "create_account"):
        session.state = "awaiting_email"
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(
            phone,
            "Great! To link your account, please reply with your email address.\n\n"
            "If you already have a FloodSafe account, use that email.\n"
            "If not, we'll create a new account for you."
            if language == "en" else
            "बढ़िया! अपना अकाउंट लिंक करने के लिए अपना ईमेल भेजें।\n\n"
            "अगर FloodSafe अकाउंट है तो वही ईमेल भेजें।\n"
            "नहीं तो हम नया अकाउंट बना देंगे।"
        )
        return

    if choice in ("2", "stay_anonymous"):
        session.state = "idle"
        session.data = {}
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(
            phone,
            "Got it! Your reports will remain anonymous.\n\n"
            "You can reply LINK anytime to connect your account."
            if language == "en" else
            "ठीक है! आपकी रिपोर्ट गुमनाम रहेगी।\n\n"
            "कभी भी LINK भेजकर अकाउंट जोड़ सकते हैं।"
        )
        return

    # Invalid choice — re-prompt
    await meta_send_text(
        phone,
        "Please reply with:\n1 = Create/link account\n2 = Stay anonymous"
        if language == "en" else
        "कृपया भेजें:\n1 = अकाउंट बनाएं\n2 = गुमनाम रहें"
    )


async def _handle_email_input(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle email input for account linking/creation."""
    email = text.strip().lower()

    # Cancel
    if email == "cancel":
        session.state = "idle"
        session.data = {}
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(
            phone,
            "Account linking cancelled.\n"
            "Your reports will remain anonymous.\n\n"
            "Reply LINK anytime to try again."
        )
        return

    # Basic email validation
    if not email or "@" not in email or "." not in email:
        await meta_send_text(
            phone,
            "That doesn't look like a valid email address.\n"
            "Please reply with your email (e.g., name@example.com)\n\n"
            "Or reply CANCEL to skip account linking."
        )
        return

    # Check if email exists
    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        # Email already linked to different phone
        if existing_user.phone and existing_user.phone != phone:
            await meta_send_text(
                phone,
                f"This email is already linked to a different phone number.\n"
                f"Please log in to FloodSafe app to update your phone number.\n\n"
                f"Or reply with a different email."
            )
            return

        # Link existing account to this phone
        existing_user.phone = phone
        existing_user.notification_whatsapp = True
        session.user_id = existing_user.id
        session.state = "idle"

        # Read pending_report_id BEFORE clearing session.data
        pending_report_id = session.data.get("pending_report_id") if session.data else None
        session.data = {}
        session.updated_at = datetime.utcnow()
        db.commit()

        # Link pending report if exists
        if pending_report_id:
            from uuid import UUID
            from ..infrastructure.models import Report
            report = db.query(Report).filter(Report.id == UUID(pending_report_id)).first()
            if report and not report.user_id:
                report.user_id = existing_user.id
                db.commit()

        await meta_send_text(
            phone,
            f"Account linked successfully!\n\n"
            f"Your WhatsApp ({phone}) is now connected to {email}.\n"
            f"Future reports will be linked to your account."
        )
        await send_welcome_buttons(phone, language)
        return

    # Create new account
    import uuid as uuid_mod
    new_user = User(
        id=uuid_mod.uuid4(),
        email=email,
        phone=phone,
        auth_provider="whatsapp",
        phone_verified=True,
        notification_whatsapp=True,
        profile_complete=False,
    )
    db.add(new_user)
    db.commit()

    session.user_id = new_user.id
    session.state = "idle"

    # Read pending_report_id BEFORE clearing session.data
    pending_report_id = session.data.get("pending_report_id") if session.data else None
    session.data = {}
    session.updated_at = datetime.utcnow()
    db.commit()

    # Link pending report if exists
    if pending_report_id:
        from uuid import UUID
        from ..infrastructure.models import Report
        report = db.query(Report).filter(Report.id == UUID(pending_report_id)).first()
        if report and not report.user_id:
            report.user_id = new_user.id
            db.commit()

    await meta_send_text(
        phone,
        f"Account created!\n\n"
        f"Email: {email}\n"
        f"WhatsApp: {phone}\n\n"
        f"Log into the FloodSafe app to complete your profile and set up watch areas."
    )
    await send_welcome_buttons(phone, language)


async def _handle_button(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    button_id: str,
    language: str,
):
    """Handle interactive button reply."""
    if button_id == "report_flood":
        await meta_send_text(
            phone,
            "To report flooding:\n\n"
            "1. Take a photo of the flooding\n"
            "2. Tap + > Location > Send current location\n"
            "3. Send both together!\n\n"
            "We'll verify with AI and alert nearby people."
            if language == "en" else
            "Flooding report karne ke liye:\n\n"
            "1. Flooding ki photo lein\n"
            "2. + > Location > Apna location bhejein\n"
            "3. Dono ek saath bhejein!"
        )
    elif button_id == "check_risk":
        last_lat = session.data.get("last_lat") if session.data else None
        last_lng = session.data.get("last_lng") if session.data else None
        if last_lat and last_lng:
            response = await handle_risk_command(db, user, None, (last_lat, last_lng))
            await meta_send_text(phone, response)
        else:
            await meta_send_text(
                phone,
                "Send your location to check flood risk.\n"
                "Or type: RISK <place name>\n"
                "Example: RISK Connaught Place"
            )
    elif button_id == "view_alerts":
        response = await handle_warnings_command(db, user)
        await meta_send_text(phone, response)
    elif button_id == "add_photo":
        if session.data and "pending_lat" in session.data:
            session.state = "awaiting_photo"
            session.updated_at = datetime.utcnow()
            db.commit()
            await meta_send_text(phone, "Send your photo now!")
        else:
            await meta_send_text(phone, "Send your location first, then the photo.")
    elif button_id == "submit_anyway":
        await _finalize_without_photo(db, session, phone, user, language)
    elif button_id in ("cancel", "menu"):
        session.state = "idle"
        last_lat = session.data.get("last_lat") if session.data else None
        last_lng = session.data.get("last_lng") if session.data else None
        session.data = {}
        if last_lat:
            session.data["last_lat"] = last_lat
            session.data["last_lng"] = last_lng
        session.updated_at = datetime.utcnow()
        db.commit()
        await send_menu_buttons(phone, language)
    elif button_id == "report_another":
        await meta_send_text(
            phone,
            "Send your location + photo to report another flood."
        )
    elif button_id == "create_account":
        await _handle_account_choice(db, session, phone, user, "1", language)
    elif button_id == "stay_anonymous":
        await _handle_account_choice(db, session, phone, user, "2", language)
    else:
        logger.warning(f"Unknown Meta button: {button_id}")
        await meta_send_text(phone, get_message(TemplateKey.WELCOME, language))
