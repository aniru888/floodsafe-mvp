"""
WhatsApp Webhook Handler for Twilio Integration.

User-Centric Design: Photo + Location = The Primary Action

Handles incoming WhatsApp messages including:
- Photo + Location pins → Creates verified flood reports with ML classification
- Location pins → Prompts for photo, allows SKIP
- Query commands → RISK, WARNINGS, MY AREAS
- User account linking flow

Security:
- Validates Twilio webhook signature
- Rate limits per phone number

Primary Flow:
1. User sends photo + location → ML classifies, creates SOS report, alerts users
2. User sends location only → Prompts for photo (or SKIP for unverified report)
3. User sends commands → Returns relevant info (RISK, WARNINGS, etc.)

Session States:
- idle: Ready for new command
- awaiting_choice: Asked user to create account or submit anonymously
- awaiting_email: User chose to create account, waiting for email
- awaiting_photo: User sent location, waiting for photo
"""
from fastapi import APIRouter, Request, Form, HTTPException, Depends, Response
from typing import Optional
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..infrastructure.database import get_db
from ..infrastructure.models import User, Report, WhatsAppSession
from ..domain.services.alert_service import AlertService
from ..domain.services.notification_service import get_notification_service
from ..core.config import settings
from ..core.phone_utils import is_valid_e164

# Import Wit.ai NLU service
from ..domain.services.wit_service import classify_message, get_mapped_command, is_wit_enabled

# Import WhatsApp services
from ..domain.services.whatsapp import (
    TemplateKey, get_message, get_user_language,
    process_sos_with_photo, get_severity_from_classification, get_confidence_text,
    handle_risk_command, handle_warnings_command, handle_my_areas_command,
    handle_help_command, handle_status_command, get_readable_location,
    # Quick Reply Button functions
    send_welcome_with_buttons,
    send_after_location_buttons,
    send_after_report_buttons,
    send_risk_result_buttons,
    send_menu_buttons,
    send_text_message,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Session timeout (30 minutes)
SESSION_TIMEOUT_MINUTES = 30

# Rate limiting configuration
RATE_LIMIT_MESSAGES = 10  # Max messages per window
RATE_LIMIT_WINDOW_SECONDS = 60  # Window size in seconds
_rate_limit_cache: dict[str, list[datetime]] = {}

# =============================================================================
# HEALTH CHECK & UTILITY FUNCTIONS
# =============================================================================

def validate_phone_format(phone: str) -> bool:
    """Validate phone number is in E.164 format. Delegates to shared utility."""
    return is_valid_e164(phone)


def check_rate_limit(phone: str) -> bool:
    """
    Check if phone number has exceeded rate limit.

    Returns True if request is allowed, False if rate limited.
    Uses in-memory cache (production should use Redis).
    """
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)

    if phone not in _rate_limit_cache:
        _rate_limit_cache[phone] = []

    # Clean old entries outside the window
    _rate_limit_cache[phone] = [t for t in _rate_limit_cache[phone] if t > window_start]

    if len(_rate_limit_cache[phone]) >= RATE_LIMIT_MESSAGES:
        logger.warning(f"Rate limit exceeded for phone ***{phone[-4:]}")
        return False  # Rate limited

    _rate_limit_cache[phone].append(now)
    return True


def validate_coordinates(lat: float, lng: float) -> bool:
    """Validate latitude and longitude are within valid ranges."""
    return -90 <= lat <= 90 and -180 <= lng <= 180


def check_ml_status() -> str:
    """Check if ML service is enabled and configured."""
    # ML is now embedded in backend (no separate service)
    if not settings.ML_ENABLED:
        return "disabled"
    return "embedded"


def check_db_health(db: Session) -> str:
    """Check if database connection is healthy."""
    from sqlalchemy import text
    try:
        # Simple query to verify connection
        db.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return f"error: {str(e)[:50]}"


@router.get("/health")
def whatsapp_health(db: Session = Depends(get_db)):
    """
    Health check endpoint for WhatsApp integration.

    Verifies:
    - Twilio credentials are configured
    - Database connection works
    - ML is enabled (embedded)
    - Webhook URL is set

    Returns JSON status for each component.
    """
    ml_status = check_ml_status()
    db_status = check_db_health(db)

    return {
        "status": "healthy" if all([
            settings.TWILIO_ACCOUNT_SID,
            db_status == "ok"
        ]) else "degraded",
        "twilio_configured": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
        "database": db_status,
        "ml_service": ml_status,
        "webhook_url": settings.TWILIO_WEBHOOK_URL or "NOT_SET",
        "rate_limit": f"{RATE_LIMIT_MESSAGES} msgs/{RATE_LIMIT_WINDOW_SECONDS}s"
    }


def validate_twilio_signature(request: Request, form_data: dict) -> bool:
    """
    Validate that the request came from Twilio.

    Returns True if:
    - Twilio is not configured (development mode)
    - Signature validation passes
    """
    if not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_WEBHOOK_URL:
        logger.warning("Twilio signature validation skipped - auth token or webhook URL not configured")
        return True  # Allow in development

    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)

        signature = request.headers.get("X-Twilio-Signature", "")
        url = settings.TWILIO_WEBHOOK_URL

        # Convert form data to dict format Twilio expects
        params = {k: str(v) for k, v in form_data.items() if v is not None}

        if validator.validate(url, params, signature):
            return True

        logger.warning("Twilio signature validation failed")
        return False

    except ImportError:
        logger.error("Twilio package not installed - skipping validation")
        return True
    except Exception as e:
        logger.error(f"Error validating Twilio signature: {e}")
        return False


def get_or_create_session(db: Session, phone: str) -> WhatsAppSession:
    """Get existing session or create new one."""
    session = db.query(WhatsAppSession).filter(WhatsAppSession.phone == phone).first()

    if session:
        # Check if session expired
        if session.updated_at < datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            session.state = "idle"
            session.data = {}
            db.commit()
        return session

    # Create new session
    session = WhatsAppSession(phone=phone, state="idle", data={})
    db.add(session)
    db.commit()
    return session


def find_user_by_phone(db: Session, phone: str) -> Optional[User]:
    """Find user by phone number (with or without country code)."""
    # Try exact match first
    user = db.query(User).filter(User.phone == phone).first()
    if user:
        return user

    # Try with/without +91 prefix
    if phone.startswith("+91"):
        alt_phone = phone[3:]  # Remove +91
    else:
        alt_phone = f"+91{phone}"

    return db.query(User).filter(User.phone == alt_phone).first()


def create_sos_report(
    db: Session,
    latitude: float,
    longitude: float,
    phone: str,
    user: Optional[User] = None,
    media_url: Optional[str] = None,
    classification=None  # FloodClassification from photo_handler
) -> Report:
    """
    Create an SOS flood report from WhatsApp location.

    Args:
        db: Database session
        latitude: GPS latitude
        longitude: GPS longitude
        phone: Phone number
        user: Linked user (optional)
        media_url: Twilio media URL (optional)
        classification: ML classification result (optional)
    """
    # Build description based on ML classification
    if classification:
        if classification.is_flood:
            description = f"[SOS WhatsApp] Flood verified by AI ({int(classification.confidence * 100)}% confidence)"
        else:
            description = f"[SOS WhatsApp] Photo submitted (AI: no flood detected, pending review)"
    elif media_url:
        description = f"[SOS WhatsApp] Photo submitted (ML unavailable)"
    else:
        description = f"[SOS WhatsApp] Location-only report from {phone}"

    # Determine verification status based on photo and ML
    verified = True  # WhatsApp location is trusted
    if classification and not classification.is_flood:
        verified = False  # Needs human review

    # Build media metadata
    media_metadata = None
    if classification:
        media_metadata = {
            "ml_classification": classification.classification,
            "ml_confidence": classification.confidence,
            "is_flood": classification.is_flood,
            "needs_review": classification.needs_review,
            "media_url": media_url
        }
    elif media_url:
        media_metadata = {"media_url": media_url, "ml_unavailable": True}

    report = Report(
        location=f"POINT({longitude} {latitude})",  # PostGIS format: lng lat
        description=description,
        verified=verified,
        location_verified=True,  # WhatsApp location is GPS-accurate
        water_depth="impassable" if (classification and classification.is_flood) else "unknown",
        user_id=user.id if user else None,
        phone_number=phone,
        media_metadata=media_metadata
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    logger.info(f"Created SOS report {report.id} from WhatsApp at ({latitude}, {longitude}), ML={classification is not None}")
    return report


def generate_twiml_response(message: str) -> Response:
    """Generate TwiML XML response for Twilio."""
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""
    return Response(content=xml_content, media_type="application/xml")


@router.post("")
async def handle_whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: Optional[str] = Form(None),
    Latitude: Optional[float] = Form(None),
    Longitude: Optional[float] = Form(None),
    NumMedia: Optional[str] = Form("0"),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
    # Quick Reply Button parameters (from Content API)
    ButtonPayload: Optional[str] = Form(None),  # Button ID that was tapped
    ButtonText: Optional[str] = Form(None),      # Button label text
    db: Session = Depends(get_db)
):
    """
    Main WhatsApp webhook handler.

    Receives messages from Twilio and responds with TwiML.
    Handles photo+location (SOS), location-only, text commands, and user flows.

    Primary action: Photo + Location = Flood Report with ML verification
    """
    # Parse form data for validation
    form_data = await request.form()
    form_dict = dict(form_data)

    # Validate Twilio signature (security)
    if not validate_twilio_signature(request, form_dict):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Parse phone number (remove "whatsapp:" prefix)
    phone = From.replace("whatsapp:", "").strip()
    has_media = MediaUrl0 is not None and MediaContentType0 and MediaContentType0.startswith("image/")

    # Improved request logging (masked phone for privacy)
    phone_masked = f"***{phone[-4:]}" if len(phone) >= 4 else "***"
    msg_type = "button" if ButtonPayload else ("location+photo" if Latitude and has_media else
                                                "location" if Latitude else
                                                "photo" if has_media else "text")
    logger.info(
        f"WhatsApp webhook: phone={phone_masked}, type={msg_type}, "
        f"body={Body[:50] if Body else 'N/A'}"
    )

    # ===========================================
    # RATE LIMITING (10 messages per minute)
    # ===========================================
    if not check_rate_limit(phone):
        logger.warning(f"Rate limited: {phone_masked}")
        return generate_twiml_response(
            "You're sending too many messages. Please wait a minute and try again."
        )

    # ===========================================
    # INPUT VALIDATION
    # ===========================================
    # Validate coordinates if provided
    if Latitude is not None and Longitude is not None:
        if not validate_coordinates(Latitude, Longitude):
            logger.warning(f"Invalid coordinates from {phone_masked}: ({Latitude}, {Longitude})")
            return generate_twiml_response(
                "Invalid location coordinates. Please send a valid location pin."
            )

    # ===========================================
    # DATABASE OPERATIONS (with error handling)
    # ===========================================
    try:
        # Get or create session
        session = get_or_create_session(db, phone)

        # Check if user has linked account
        user = session.user_id and db.query(User).filter(User.id == session.user_id).first()
        if not user:
            user = find_user_by_phone(db, phone)
            if user:
                # Link user to session
                session.user_id = user.id
                db.commit()
    except Exception as e:
        logger.error(f"Database error for {phone_masked}: {e}")
        db.rollback()
        return generate_twiml_response(
            "Sorry, we're experiencing technical difficulties. Please try again in a moment."
        )

    # ===========================================
    # HANDLE BUTTON TAPS (Quick Reply Buttons)
    # ===========================================
    if ButtonPayload:
        logger.info(f"Button tap from {phone}: {ButtonPayload} (text: {ButtonText})")
        return await handle_button_tap(
            db, session, phone, user, ButtonPayload
        )

    # PRIMARY FLOW: Photo + Location (ideal case)
    if Latitude is not None and Longitude is not None:
        return await handle_location(
            db, session, phone, user, Latitude, Longitude,
            media_url=MediaUrl0 if has_media else None,
            media_content_type=MediaContentType0 if has_media else None
        )

    # Handle photo-only (no location) - prompt for location
    if has_media and Latitude is None:
        # Store photo URL in session for later
        session.data = {
            "pending_media_url": MediaUrl0,
            "pending_media_type": MediaContentType0
        }
        session.updated_at = datetime.utcnow()
        db.commit()

        language = get_user_language(user)
        return generate_twiml_response(
            get_message(TemplateKey.RISK_NO_LOCATION, language) if language == 'hi' else
            "Photo received! Now please share your location:\n\n"
            "1. Tap the + icon\n"
            "2. Select 'Location'\n"
            "3. Send your current location\n\n"
            "This helps us verify where the flooding is happening."
        )

    # Handle text commands
    body_lower = (Body or "").strip().lower()
    body_stripped = (Body or "").strip()
    language = get_user_language(user)

    # Check session state for conversation flow
    if session.state == "awaiting_choice":
        return await handle_account_choice(db, session, phone, Body)

    if session.state == "awaiting_email":
        return await handle_email_input(db, session, phone, Body)

    if session.state == "awaiting_photo":
        return await handle_awaiting_photo(db, session, phone, user, Body, has_media, MediaUrl0, MediaContentType0)

    # ===========================================
    # WIT.AI NLU — Natural Language Understanding
    # Attempts intent classification before keyword matching.
    # Falls through to keyword matching if Wit.ai is disabled,
    # unavailable, or confidence is below threshold.
    # ===========================================
    if is_wit_enabled() and body_stripped and not body_lower.startswith(("risk", "warnings", "alerts", "help", "menu", "status")):
        wit_result = await classify_message(body_stripped)
        if wit_result:
            mapped = get_mapped_command(wit_result)
            if mapped == "risk":
                place_name = wit_result.location
                last_location = None
                if not place_name and session.data and "last_lat" in session.data:
                    last_location = (session.data["last_lat"], session.data["last_lng"])
                response = await handle_risk_command(db, user, place_name, last_location)
                return generate_twiml_response(response)
            elif mapped == "warnings":
                response = await handle_warnings_command(db, user)
                return generate_twiml_response(response)
            elif mapped == "my_areas":
                response = await handle_my_areas_command(db, user)
                return generate_twiml_response(response)
            elif mapped == "help":
                response = await handle_help_command(user)
                return generate_twiml_response(response)
            elif mapped == "status":
                response = await handle_status_command(db, user, phone)
                return generate_twiml_response(response)
            elif mapped == "report":
                # User wants to report flooding via natural language
                return generate_twiml_response(
                    get_message(TemplateKey.WELCOME, language) if language == 'hi' else
                    "To report flooding, please share:\n\n"
                    "1. Take a photo of the flooding\n"
                    "2. Tap + → Location → Send current location\n"
                    "3. Send both together!\n\n"
                    "We'll verify with AI and alert nearby people."
                )
            # mapped == "welcome" or unknown → fall through to keyword matching

    # ===========================================
    # KEYWORD COMMANDS: RISK, WARNINGS, MY AREAS, HELP
    # ===========================================

    # RISK command (with optional place name)
    if body_lower.startswith("risk"):
        place_name = body_stripped[4:].strip() if len(body_stripped) > 4 else None
        last_location = None
        if session.data and "last_lat" in session.data:
            last_location = (session.data["last_lat"], session.data["last_lng"])
        response = await handle_risk_command(db, user, place_name, last_location)
        return generate_twiml_response(response)

    # WARNINGS command
    if body_lower in ["warnings", "alerts", "alert", "warning"]:
        response = await handle_warnings_command(db, user)
        return generate_twiml_response(response)

    # MY AREAS command
    if body_lower in ["my areas", "myareas", "areas", "my area", "watch areas"]:
        response = await handle_my_areas_command(db, user)
        return generate_twiml_response(response)

    # HELP command
    if body_lower in ["help", "?", "commands", "menu"]:
        response = await handle_help_command(user)
        return generate_twiml_response(response)

    # STATUS command
    if body_lower in ["status", "info", "account"]:
        response = await handle_status_command(db, user, phone)
        return generate_twiml_response(response)

    # SKIP command (for awaiting_photo state - handled above, but also as standalone)
    if body_lower == "skip":
        # If there's a pending location, create unverified report
        if session.data and "pending_lat" in session.data:
            return await finalize_report_without_photo(db, session, phone, user)
        return generate_twiml_response(
            "Nothing to skip. Send your location + photo to report flooding."
        )

    # ===========================================
    # LEGACY COMMANDS (kept for backwards compatibility)
    # ===========================================

    # SOS instruction (when no location sent)
    if body_lower in ["sos", "emergency", "flood"]:
        return generate_twiml_response(
            "To send an SOS alert, please share your location:\n"
            "1. Tap the + icon\n"
            "2. Select 'Location'\n"
            "3. Send your current location\n\n"
            "Your location will be used to alert nearby residents."
        )

    if body_lower in ["status", "info"]:
        if user:
            return generate_twiml_response(
                f"You're signed in as {user.email or user.phone}.\n"
                f"Your reports are linked to your FloodSafe account.\n\n"
                f"Send your location to submit an SOS report."
            )
        return generate_twiml_response(
            "You're not linked to a FloodSafe account.\n"
            "Your reports will be submitted anonymously.\n\n"
            "Reply LINK to connect your account."
        )

    if body_lower == "link":
        if user:
            return generate_twiml_response(
                f"Your WhatsApp is already linked to {user.email}.\n"
                f"No action needed!"
            )
        session.state = "awaiting_choice"
        session.updated_at = datetime.utcnow()
        db.commit()

        return generate_twiml_response(
            "Would you like to:\n\n"
            "1. Create a new FloodSafe account\n"
            "2. Link to an existing account\n\n"
            "Reply with 1 or 2"
        )

    if body_lower == "stop":
        # Opt-out handling
        if user:
            user.notification_whatsapp = False
            db.commit()
            return generate_twiml_response(
                "You've unsubscribed from WhatsApp alerts.\n"
                "You can still use the FloodSafe app.\n\n"
                "Reply START to re-subscribe."
            )
        return generate_twiml_response(
            "You've been unsubscribed from WhatsApp alerts.\n"
            "Reply START to re-subscribe."
        )

    if body_lower == "start":
        if user:
            user.notification_whatsapp = True
            db.commit()
            return generate_twiml_response(
                "Welcome back! You're subscribed to flood alerts.\n"
                "Send a photo + your location to report flooding."
            )
        # New user - use welcome template
        return generate_twiml_response(get_message(TemplateKey.WELCOME, language))

    # Default response - use welcome template (emphasizes photo + location)
    return generate_twiml_response(get_message(TemplateKey.WELCOME, language))


async def handle_location(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    latitude: float,
    longitude: float,
    media_url: Optional[str] = None,
    media_content_type: Optional[str] = None
) -> Response:
    """
    Handle incoming location pin - create SOS report.

    With photo: Process ML classification, create verified report
    Without photo: Prompt for photo (or allow SKIP)
    """
    language = get_user_language(user)
    location_name = get_readable_location(latitude, longitude)

    # Store location in session for future RISK command
    session.data = session.data or {}
    session.data["last_lat"] = latitude
    session.data["last_lng"] = longitude

    # Check if there's a pending photo from earlier (user sent photo first)
    if not media_url and session.data.get("pending_media_url"):
        media_url = session.data.get("pending_media_url")
        media_content_type = session.data.get("pending_media_type", "image/jpeg")
        # Clear pending media
        del session.data["pending_media_url"]
        if "pending_media_type" in session.data:
            del session.data["pending_media_type"]

    # ===========================================
    # CASE 1: Location WITHOUT photo - prompt for photo
    # ===========================================
    if not media_url:
        # Store location for when photo arrives
        session.state = "awaiting_photo"
        session.data["pending_lat"] = latitude
        session.data["pending_lng"] = longitude
        session.updated_at = datetime.utcnow()
        db.commit()

        return generate_twiml_response(
            get_message(TemplateKey.REPORT_NO_PHOTO, language)
        )

    # ===========================================
    # CASE 2: Location WITH photo - full ML flow
    # ===========================================
    logger.info(f"Processing photo+location report from {phone}")

    # Process photo with ML
    _, classification = await process_sos_with_photo(media_url, media_content_type or "image/jpeg")

    # Create report with ML metadata
    report = create_sos_report(
        db, latitude, longitude, phone, user=user,
        media_url=media_url,
        classification=classification
    )

    # Trigger alerts
    alert_service = AlertService(db)
    alerts_count = alert_service.check_watch_areas_for_report(
        report.id, latitude, longitude, user.id if user else None
    )

    # Send notifications
    notification_service = get_notification_service(db)
    if notification_service.is_configured():
        from ..infrastructure.models import Alert
        recent_alerts = db.query(Alert).filter(Alert.report_id == report.id).all()
        if recent_alerts:
            watch_area_ids = [a.watch_area_id for a in recent_alerts]
            await notification_service.notify_watch_area_users(
                watch_area_ids,
                f"FLOOD ALERT: SOS reported near your watch area. Check FloodSafe for details."
            )

    # Reset session (keep last location for RISK command)
    session.state = "idle"
    session.updated_at = datetime.utcnow()
    db.commit()

    # Build response based on ML classification
    if classification:
        if classification.is_flood:
            confidence_pct = int(classification.confidence * 100)
            severity = get_severity_from_classification(classification)
            return generate_twiml_response(
                get_message(
                    TemplateKey.REPORT_FLOOD_DETECTED,
                    language,
                    location=location_name,
                    confidence=confidence_pct,
                    severity=severity,
                    alerts_count=alerts_count
                )
            )
        else:
            return generate_twiml_response(
                get_message(
                    TemplateKey.REPORT_NO_FLOOD,
                    language,
                    location=location_name
                )
            )
    else:
        # ML unavailable
        return generate_twiml_response(
            get_message(
                TemplateKey.ML_UNAVAILABLE,
                language,
                location=location_name,
                alerts_count=alerts_count
            )
        )


async def handle_account_choice(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    body: Optional[str]
) -> Response:
    """Handle user's choice to create account or stay anonymous."""
    choice = (body or "").strip()

    if choice == "1":
        # Create/link account
        session.state = "awaiting_email"
        session.updated_at = datetime.utcnow()
        db.commit()

        return generate_twiml_response(
            "Great! To link your account, please reply with your email address.\n\n"
            "If you already have a FloodSafe account, use that email.\n"
            "If not, we'll create a new account for you."
        )

    if choice == "2":
        # Stay anonymous
        session.state = "idle"
        session.data = {}
        session.updated_at = datetime.utcnow()
        db.commit()

        return generate_twiml_response(
            "Got it! Your reports will remain anonymous.\n\n"
            "You can reply LINK anytime to connect your account.\n"
            "Share your location to send another SOS."
        )

    # Invalid choice
    return generate_twiml_response(
        "Please reply with:\n"
        "1 = Create/link account\n"
        "2 = Stay anonymous"
    )


async def handle_email_input(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    body: Optional[str]
) -> Response:
    """Handle email input for account linking."""
    email = (body or "").strip().lower()

    # Basic email validation
    if not email or "@" not in email or "." not in email:
        return generate_twiml_response(
            "That doesn't look like a valid email address.\n"
            "Please reply with your email (e.g., name@example.com)\n\n"
            "Or reply CANCEL to skip account linking."
        )

    if email == "cancel":
        session.state = "idle"
        session.data = {}
        session.updated_at = datetime.utcnow()
        db.commit()

        return generate_twiml_response(
            "Account linking cancelled.\n"
            "Your reports will remain anonymous.\n\n"
            "Reply LINK anytime to try again."
        )

    # Check if email exists
    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        # Link existing account to this phone
        if existing_user.phone and existing_user.phone != phone:
            # Email already linked to different phone
            return generate_twiml_response(
                f"This email is already linked to a different phone number.\n"
                f"Please log in to FloodSafe app to update your phone number.\n\n"
                f"Or reply with a different email."
            )

        # Update user's phone
        existing_user.phone = phone
        existing_user.notification_whatsapp = True
        session.user_id = existing_user.id
        session.state = "idle"

        # CRITICAL: Read pending_report_id BEFORE clearing session.data
        pending_report_id = session.data.get("pending_report_id")
        session.data = {}
        session.updated_at = datetime.utcnow()
        db.commit()

        # Update pending report if exists (read BEFORE clearing data above)
        if pending_report_id:
            from uuid import UUID
            report = db.query(Report).filter(Report.id == UUID(pending_report_id)).first()
            if report and not report.user_id:
                report.user_id = existing_user.id
                db.commit()

        return generate_twiml_response(
            f"Account linked successfully!\n\n"
            f"Your WhatsApp ({phone}) is now connected to {email}.\n"
            f"Future SOS reports will be linked to your account.\n\n"
            f"Share your location to send an SOS."
        )

    # Create new account
    import uuid
    new_user = User(
        id=uuid.uuid4(),
        email=email,
        phone=phone,
        auth_provider="whatsapp",
        phone_verified=True,  # WhatsApp number is verified by Twilio
        notification_whatsapp=True,
        profile_complete=False  # Need to complete onboarding in app
    )
    db.add(new_user)
    db.commit()

    session.user_id = new_user.id
    session.state = "idle"

    # CRITICAL: Read pending_report_id BEFORE clearing session.data
    pending_report_id = session.data.get("pending_report_id")
    session.data = {}
    session.updated_at = datetime.utcnow()
    db.commit()

    # Update pending report (read BEFORE clearing data above)
    if pending_report_id:
        from uuid import UUID
        report = db.query(Report).filter(Report.id == UUID(pending_report_id)).first()
        if report and not report.user_id:
            report.user_id = new_user.id
            db.commit()

    return generate_twiml_response(
        f"Account created!\n\n"
        f"Email: {email}\n"
        f"WhatsApp: {phone}\n\n"
        f"Log into the FloodSafe app to complete your profile and set up watch areas.\n\n"
        f"Share your location to send an SOS."
    )


async def handle_awaiting_photo(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    body: Optional[str],
    has_media: bool,
    media_url: Optional[str],
    media_content_type: Optional[str]
) -> Response:
    """
    Handle user response when we're awaiting a photo.

    User can:
    - Send a photo → Process with ML, complete report
    - Send SKIP → Create report without photo (unverified)
    - Send anything else → Remind them to send photo or SKIP
    """
    language = get_user_language(user)
    body_lower = (body or "").strip().lower()

    # Get pending location from session
    pending_lat = session.data.get("pending_lat")
    pending_lng = session.data.get("pending_lng")

    if not pending_lat or not pending_lng:
        # Session expired or corrupted - reset
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        return generate_twiml_response(
            get_message(TemplateKey.WELCOME, language)
        )

    location_name = get_readable_location(pending_lat, pending_lng)

    # CASE 1: User sent a photo
    if has_media and media_url:
        logger.info(f"Received photo for pending report from {phone}")

        # Process with ML
        _, classification = await process_sos_with_photo(
            media_url, media_content_type or "image/jpeg"
        )

        # Create the report
        report = create_sos_report(
            db, pending_lat, pending_lng, phone, user=user,
            media_url=media_url,
            classification=classification
        )

        # Trigger alerts
        alert_service = AlertService(db)
        alerts_count = alert_service.check_watch_areas_for_report(
            report.id, pending_lat, pending_lng, user.id if user else None
        )

        # Clear pending state but keep location for RISK
        session.state = "idle"
        del session.data["pending_lat"]
        del session.data["pending_lng"]
        session.data["last_lat"] = pending_lat
        session.data["last_lng"] = pending_lng
        session.updated_at = datetime.utcnow()
        db.commit()

        # Build response based on classification
        if classification and classification.is_flood:
            confidence_pct = int(classification.confidence * 100)
            severity = get_severity_from_classification(classification)
            return generate_twiml_response(
                get_message(
                    TemplateKey.REPORT_PHOTO_ADDED,
                    language,
                    location=location_name,
                    classification="FLOODING DETECTED",
                    confidence_text=f"{confidence_pct}% confidence",
                    alerts_count=alerts_count
                )
            )
        else:
            return generate_twiml_response(
                get_message(
                    TemplateKey.REPORT_PHOTO_ADDED,
                    language,
                    location=location_name,
                    classification="No flood detected",
                    confidence_text="Will be reviewed manually",
                    alerts_count=alerts_count
                )
            )

    # CASE 2: User sent SKIP
    if body_lower == "skip":
        return await finalize_report_without_photo(db, session, phone, user)

    # CASE 3: Anything else - remind user
    return generate_twiml_response(
        get_message(TemplateKey.REPORT_NO_PHOTO, language)
    )


async def finalize_report_without_photo(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User]
) -> Response:
    """
    Create an unverified report without photo.

    Called when user sends SKIP during awaiting_photo state.
    """
    language = get_user_language(user)

    # Get pending location
    pending_lat = session.data.get("pending_lat")
    pending_lng = session.data.get("pending_lng")

    if not pending_lat or not pending_lng:
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        return generate_twiml_response(
            "Nothing to skip. Send your location + photo to report flooding."
        )

    location_name = get_readable_location(pending_lat, pending_lng)

    # Create report without photo
    report = create_sos_report(
        db, pending_lat, pending_lng, phone, user=user
    )

    # Trigger alerts (fewer for unverified reports)
    alert_service = AlertService(db)
    alerts_count = alert_service.check_watch_areas_for_report(
        report.id, pending_lat, pending_lng, user.id if user else None
    )

    # Clear pending state but keep location for RISK
    session.state = "idle"
    del session.data["pending_lat"]
    del session.data["pending_lng"]
    session.data["last_lat"] = pending_lat
    session.data["last_lng"] = pending_lng
    session.updated_at = datetime.utcnow()
    db.commit()

    return generate_twiml_response(
        get_message(
            TemplateKey.REPORT_NO_PHOTO_SKIP,
            language,
            location=location_name,
            alerts_count=alerts_count
        )
    )


# =============================================================================
# QUICK REPLY BUTTON HANDLING
# =============================================================================

async def handle_button_tap(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    button_id: str
) -> Response:
    """
    Handle Quick Reply button taps.

    Routes button IDs to appropriate handlers and sends follow-up buttons.

    Button IDs:
    - report_flood: Start flood report flow
    - check_risk: Check flood risk
    - view_alerts: Show current warnings
    - add_photo: User wants to add photo to pending report
    - submit_anyway: Submit report without photo
    - cancel: Cancel current flow, show menu
    - menu: Show main menu
    - report_another: Start new report
    - check_my_location: Check risk at last known location
    """
    language = get_user_language(user)

    # Map button IDs to handlers
    if button_id == "report_flood":
        return await button_start_report_flow(db, session, phone, language)

    elif button_id == "check_risk":
        return await button_check_risk(db, session, phone, user, language)

    elif button_id == "view_alerts":
        return await button_view_alerts(db, user, phone, language)

    elif button_id == "add_photo":
        return await button_set_awaiting_photo(db, session, phone, language)

    elif button_id == "submit_anyway":
        return await button_submit_without_photo(db, session, phone, user)

    elif button_id == "cancel":
        return await button_show_menu(db, session, phone, language)

    elif button_id == "menu":
        return await button_show_menu(db, session, phone, language)

    elif button_id == "report_another":
        return await button_start_report_flow(db, session, phone, language)

    elif button_id == "check_my_location":
        return await button_check_my_location(db, session, phone, user, language)

    else:
        # Unknown button - show menu
        logger.warning(f"Unknown button ID: {button_id}")
        return await button_show_menu(db, session, phone, language)


async def button_start_report_flow(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    language: str
) -> Response:
    """
    Start the flood report flow.

    Tell user to send photo + location.
    """
    # Clear any pending state
    session.state = "idle"
    session.data = session.data or {}
    session.updated_at = datetime.utcnow()
    db.commit()

    # Send TwiML acknowledgment
    twiml = generate_twiml_response(
        "📸 To report flooding:\n\n"
        "1. Take a photo of the flooding\n"
        "2. Tap + → Location → Send current location\n"
        "3. Send photo + location together!\n\n"
        "We'll verify with AI and alert nearby people."
        if language == "en" else
        "📸 बाढ़ की रिपोर्ट करने के लिए:\n\n"
        "1. बाढ़ की फोटो लें\n"
        "2. + → Location → अपना स्थान भेजें\n"
        "3. फोटो + स्थान एक साथ भेजें!\n\n"
        "हम AI से verify करेंगे और पास के लोगों को alert करेंगे।"
    )

    return twiml


async def button_check_risk(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    language: str
) -> Response:
    """
    Check flood risk - ask for location or use last known.
    """
    # Check if we have a last known location
    last_lat = session.data.get("last_lat") if session.data else None
    last_lng = session.data.get("last_lng") if session.data else None

    if last_lat and last_lng:
        # Use last known location
        response = await handle_risk_command(db, user, None, (last_lat, last_lng))
        return generate_twiml_response(response)

    # Ask for location
    return generate_twiml_response(
        "🔍 To check flood risk:\n\n"
        "Send your location (tap + → Location)\n\n"
        "Or type a place name:\n"
        "Example: RISK Connaught Place"
        if language == "en" else
        "🔍 बाढ़ जोखिम जांचने के लिए:\n\n"
        "अपना स्थान भेजें (+ → Location पर tap करें)\n\n"
        "या जगह का नाम लिखें:\n"
        "उदाहरण: RISK कनॉट प्लेस"
    )


async def button_view_alerts(
    db: Session,
    user: Optional[User],
    phone: str,
    language: str
) -> Response:
    """
    Show current flood warnings.
    """
    response = await handle_warnings_command(db, user)
    return generate_twiml_response(response)


async def button_set_awaiting_photo(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    language: str
) -> Response:
    """
    User tapped "Add Photo" - ensure we're in awaiting_photo state.
    """
    # Check if there's a pending location
    if session.data and "pending_lat" in session.data:
        session.state = "awaiting_photo"
        session.updated_at = datetime.utcnow()
        db.commit()

        return generate_twiml_response(
            "📸 Send your photo now!\n\n"
            "Just take a photo of the flooding and send it.\n"
            "We'll add it to your location report."
            if language == "en" else
            "📸 अभी अपनी फोटो भेजें!\n\n"
            "बस बाढ़ की फोटो लें और भेजें।\n"
            "हम इसे आपकी स्थान रिपोर्ट में जोड़ देंगे।"
        )

    # No pending location - ask for both
    return generate_twiml_response(
        "📸 To add a photo:\n\n"
        "First send your location, then we'll ask for the photo.\n"
        "Or send both together (photo + location in one message)!"
        if language == "en" else
        "📸 फोटो जोड़ने के लिए:\n\n"
        "पहले अपना स्थान भेजें, फिर हम फोटो मांगेंगे।\n"
        "या दोनों एक साथ भेजें (एक मैसेज में फोटो + स्थान)!"
    )


async def button_submit_without_photo(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User]
) -> Response:
    """
    Submit the pending report without a photo.

    Same as typing SKIP.
    """
    return await finalize_report_without_photo(db, session, phone, user)


async def button_show_menu(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    language: str
) -> Response:
    """
    Show main menu.

    Clears any pending state and shows welcome/menu.
    """
    # Clear pending state
    session.state = "idle"
    if session.data:
        # Keep last location for risk checks
        last_lat = session.data.get("last_lat")
        last_lng = session.data.get("last_lng")
        session.data = {}
        if last_lat:
            session.data["last_lat"] = last_lat
            session.data["last_lng"] = last_lng
    session.updated_at = datetime.utcnow()
    db.commit()

    # Send menu with buttons
    # Note: We return TwiML first, then send buttons separately
    await send_menu_buttons(phone, language)

    return generate_twiml_response(
        "🏠 Main Menu"
        if language == "en" else
        "🏠 मुख्य मेनू"
    )


async def button_check_my_location(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    language: str
) -> Response:
    """
    Check risk at the user's last known location.
    """
    last_lat = session.data.get("last_lat") if session.data else None
    last_lng = session.data.get("last_lng") if session.data else None

    if last_lat and last_lng:
        response = await handle_risk_command(db, user, None, (last_lat, last_lng))
        return generate_twiml_response(response)

    # No last location
    return generate_twiml_response(
        "📍 No recent location found.\n\n"
        "Please send your location first:\n"
        "Tap + → Location → Send current location"
        if language == "en" else
        "📍 कोई हालिया स्थान नहीं मिला।\n\n"
        "कृपया पहले अपना स्थान भेजें:\n"
        "+ → Location → अपना वर्तमान स्थान भेजें"
    )
