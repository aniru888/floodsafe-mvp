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
import json
import logging
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional

import httpx
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
    send_onboarding_city_buttons,
    send_onboarding_city_2_buttons,
    send_extended_menu,
    send_circles_menu_buttons,
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
RATE_LIMIT_CACHE_MAX = 10_000
_rate_limit_cache: OrderedDict[str, list[datetime]] = OrderedDict()

# Message deduplication (prevents duplicate processing on Meta retries)
DEDUP_TTL_SECONDS = 300  # 5 minutes
DEDUP_MAX_ENTRIES = 5_000
_dedup_cache: OrderedDict[str, float] = OrderedDict()  # wamid -> timestamp


def _check_rate_limit(phone: str) -> bool:
    """Check rate limit for phone number. LRU-evicts at 10K entries."""
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    if phone not in _rate_limit_cache:
        _rate_limit_cache[phone] = []
        # Evict oldest entries when cache exceeds cap
        while len(_rate_limit_cache) > RATE_LIMIT_CACHE_MAX:
            _rate_limit_cache.popitem(last=False)
    else:
        # Move to end (most recently used)
        _rate_limit_cache.move_to_end(phone)
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


def _is_duplicate_message(message_id: str) -> bool:
    """Check if message was already processed (dedup on wamid). Returns True if duplicate."""
    if not message_id:
        return False
    now = time.time()
    # Evict expired entries (older than TTL)
    while _dedup_cache:
        oldest_key, oldest_ts = next(iter(_dedup_cache.items()))
        if now - oldest_ts > DEDUP_TTL_SECONDS:
            _dedup_cache.popitem(last=False)
        else:
            break
    # Cap entries
    while len(_dedup_cache) > DEDUP_MAX_ENTRIES:
        _dedup_cache.popitem(last=False)
    if message_id in _dedup_cache:
        return True
    _dedup_cache[message_id] = now
    return False


# City detection from coordinates (reuses CITY_BOUNDS from search.py)
CITY_BOUNDS = {
    "delhi": {"min_lat": 28.40, "max_lat": 28.88, "min_lng": 76.84, "max_lng": 77.35},
    "bangalore": {"min_lat": 12.75, "max_lat": 13.20, "min_lng": 77.35, "max_lng": 77.80},
    "yogyakarta": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
    "singapore": {"min_lat": 1.15, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    "indore": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
}


def _detect_city_from_coords(lat: float, lng: float) -> Optional[str]:
    """Detect city from GPS coordinates using bounding boxes. Returns city name or None."""
    for city, bounds in CITY_BOUNDS.items():
        if (bounds["min_lat"] <= lat <= bounds["max_lat"]
                and bounds["min_lng"] <= lng <= bounds["max_lng"]):
            return city
    return None


def _get_session_data(session: WhatsAppSession, key: str, default=None):
    """
    Safely get a value from session.data with validation.

    Logs warning if session.data is corrupted and resets to empty dict.
    """
    if session.data is None:
        session.data = {}
        return default
    if not isinstance(session.data, dict):
        logger.warning(f"Session data corrupted (type={type(session.data).__name__}), resetting")
        session.data = {}
        return default
    return session.data.get(key, default)


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

    # Process each entry — wrapped in try-except to prevent Meta retry storms on 500s
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue

                value = change.get("value", {})
                messages = value.get("messages", [])
                contacts = value.get("contacts", [])

                for message in messages:
                    await _process_message(db, message, contacts)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)

    # Always return 200 to acknowledge receipt (prevents Meta retry storms)
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

    # Dedup: skip if we already processed this message (Meta retries)
    if _is_duplicate_message(message_id):
        logger.debug(f"Skipping duplicate message: {message_id}")
        return

    # Skip group messages (only handle 1:1 conversations)
    if message.get("context", {}).get("group_id") or message.get("group_id"):
        logger.debug("Skipping group message")
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
            photo_prompt = {
                "hi": "फोटो मिल गई! अब कृपया अपना स्थान भेजें:\n\n"
                      "1. + आइकन पर टैप करें\n"
                      "2. 'Location' चुनें\n"
                      "3. अपना स्थान भेजें",
                "id": "Foto diterima! Sekarang kirim lokasi Anda:\n\n"
                      "1. Ketuk ikon +\n"
                      "2. Pilih 'Lokasi'\n"
                      "3. Kirim lokasi Anda saat ini",
            }.get(language, "Photo received! Now please share your location:\n\n"
                           "1. Tap the + icon\n"
                           "2. Select 'Location'\n"
                           "3. Send your current location")
            await meta_send_text(phone, photo_prompt)
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

    if session.state == "onboarding_location":
        # User typed a place name during onboarding — fuzzy search
        await _handle_onboarding_location_text(db, session, phone, user, text, language)
        return

    if session.state == "search_results":
        # User is selecting from fuzzy search results (1, 2, 3)
        await _handle_search_result_selection(db, session, phone, user, text, language)
        return

    if session.state == "adding_watch_area":
        # User typed a place name for watch area
        await _handle_watch_area_text(db, session, phone, user, text, language)
        return

    if session.state == "creating_circle":
        # User typed a circle name
        await _handle_create_circle_name(db, session, phone, user, text, language)
        return

    if session.state == "joining_circle":
        # User typed an invite code
        await _handle_join_circle_code(db, session, phone, user, text, language)
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
        if not await meta_send_text(phone, response):
            logger.error(f"SEND FAILED risk result to ***{phone[-4:]}")
        return

    if text_lower in ("warnings", "alerts", "alert", "warning"):
        response = await handle_warnings_command(db, user)
        if not await meta_send_text(phone, response):
            logger.error(f"SEND FAILED warnings to ***{phone[-4:]}")
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

    # E4: Circle management commands
    if text_lower in ("circles", "my circles", "mycircles"):
        await _handle_circles_command(db, phone, user, language)
        return

    if text_lower.startswith("create"):
        circle_name = text[6:].strip()
        if not user:
            await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
            return
        if circle_name:
            await _handle_create_circle_name(db, session, phone, user, circle_name, language)
        else:
            session.state = "creating_circle"
            session.updated_at = datetime.utcnow()
            db.commit()
            prompt = {"hi": "अपनी सर्कल का नाम बताएं:", "id": "Masukkan nama lingkaran Anda:"}.get(language, "What name for your circle?")
            await meta_send_text(phone, prompt)
        return

    if text_lower.startswith("join"):
        invite_code = text[4:].strip()
        if not user:
            await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
            return
        if invite_code:
            await _handle_join_circle_code(db, session, phone, user, invite_code, language)
        else:
            session.state = "joining_circle"
            session.updated_at = datetime.utcnow()
            db.commit()
            prompt = {"hi": "आमंत्रण कोड दर्ज करें:", "id": "Masukkan kode undangan:"}.get(language, "Enter the invite code:")
            await meta_send_text(phone, prompt)
        return

    # E7: Invite command
    if text_lower.startswith("invite"):
        await _handle_invite_command(db, phone, user, text, language)
        return

    # Default: welcome/onboarding flow
    await _handle_welcome(db, session, phone, user, language)


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

    # Onboarding: user shared location during city/location step
    if session.state in ("onboarding_city", "onboarding_location"):
        detected_city = _detect_city_from_coords(latitude, longitude)
        city = detected_city or _get_session_data(session, "onboarding_city", "delhi")
        location_name = get_readable_location(latitude, longitude)
        await _complete_onboarding(db, session, phone, user, latitude, longitude,
                                   location_name, city, language)
        return

    # Adding watch area: user shared GPS
    if session.state == "adding_watch_area":
        location_name = get_readable_location(latitude, longitude)
        await _complete_watch_area(db, session, phone, user, latitude, longitude,
                                   location_name, language)
        return

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
        phone_masked = f"***{phone[-4:]}" if len(phone) >= 4 else "***"
        logger.warning(f"Photo download failed for {phone_masked}, resetting session")
        session.state = "idle"
        if session.data:
            session.data.pop("pending_lat", None)
            session.data.pop("pending_lng", None)
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(
            phone,
            "Failed to download your photo. Please try sending it again, "
            "along with your location."
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
    from ..infrastructure.storage import get_storage_service, StorageError

    # Classify photo with ML (process_sos_with_photo expects a URL, but
    # for Meta we have raw bytes — we need to use the classifier directly)
    classification = None
    try:
        from ..domain.services.whatsapp.photo_handler import classify_flood_image
        classification = await classify_flood_image(photo_bytes)
    except Exception as e:
        logger.warning(f"ML classification failed: {e}")

    # Upload photo to Supabase Storage for permanent URL
    media_url = None
    storage_path = None
    try:
        storage = get_storage_service()
        user_id_str = str(user.id) if user else f"anonymous_{phone[-4:]}"
        media_url, storage_path = await storage.upload_image(
            content=photo_bytes,
            filename=f"whatsapp_report_{int(time.time())}.jpg",
            content_type="image/jpeg",
            user_id=user_id_str,
        )
        logger.info(f"Uploaded WhatsApp photo to storage: {storage_path}")
    except StorageError as e:
        logger.error(f"Photo storage upload failed: {e}")
        # Continue without media_url — report still has ML classification + location
    except Exception as e:
        logger.error(f"Unexpected storage error: {e}")

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
        if media_url:
            media_metadata["media_url"] = media_url
        if storage_path:
            media_metadata["storage_path"] = storage_path

    report = Report(
        location=f"POINT({longitude} {latitude})",
        description=description,
        verified=verified,
        location_verified=True,
        water_depth="impassable" if (classification and classification.is_flood) else "unknown",
        user_id=user.id if user else None,
        phone_number=phone,
        media_url=media_url,
        media_metadata=json.dumps(media_metadata) if media_metadata else None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Trigger alerts
    alerts_count = 0
    try:
        alert_service = AlertService(db)
        alerts_count = alert_service.check_watch_areas_for_report(
            report.id, latitude, longitude, user.id if user else None
        )
    except Exception as e:
        logger.error(f"Alert creation failed for report {report.id}: {e}", exc_info=True)

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

    phone_masked = f"***{phone[-4:]}" if len(phone) >= 4 else "***"
    if not await meta_send_text(phone, response):
        logger.error(f"SEND FAILED report confirmation to {phone_masked}: {response[:50]}")
    if not await send_after_report_buttons(phone, language):
        logger.warning(f"Button send failed to {phone_masked}, sending plain text fallback")
        await meta_send_text(phone, "Reply: RISK to check risk, REPORT to report another, or HELP for menu.")


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

    alerts_count = 0
    try:
        alert_service = AlertService(db)
        alerts_count = alert_service.check_watch_areas_for_report(
            report.id, lat, lng, user.id if user else None
        )
    except Exception as e:
        logger.error(f"Alert creation failed for report {report.id}: {e}", exc_info=True)

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
    if not await meta_send_text(phone, response):
        phone_masked = f"***{phone[-4:]}" if len(phone) >= 4 else "***"
        logger.error(f"SEND FAILED no-photo report confirmation to {phone_masked}")


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
        link_msg = {
            "hi": "बढ़िया! अपना अकाउंट लिंक करने के लिए अपना ईमेल भेजें।\n\n"
                  "अगर FloodSafe अकाउंट है तो वही ईमेल भेजें।\n"
                  "नहीं तो हम नया अकाउंट बना देंगे।",
            "id": "Bagus! Kirim email Anda untuk menghubungkan akun.\n\n"
                  "Jika sudah punya akun FloodSafe, gunakan email tersebut.\n"
                  "Jika belum, kami akan membuat akun baru.",
        }.get(language, "Great! To link your account, please reply with your email address.\n\n"
                        "If you already have a FloodSafe account, use that email.\n"
                        "If not, we'll create a new account for you.")
        await meta_send_text(phone, link_msg)
        return

    if choice in ("2", "stay_anonymous"):
        session.state = "idle"
        session.data = {}
        session.updated_at = datetime.utcnow()
        db.commit()
        anon_msg = {
            "hi": "ठीक है! आपकी रिपोर्ट गुमनाम रहेगी।\n\n"
                  "कभी भी LINK भेजकर अकाउंट जोड़ सकते हैं।",
            "id": "Baik! Laporan Anda akan tetap anonim.\n\n"
                  "Balas LINK kapan saja untuk menghubungkan akun.",
        }.get(language, "Got it! Your reports will remain anonymous.\n\n"
                        "You can reply LINK anytime to connect your account.")
        await meta_send_text(phone, anon_msg)
        return

    # Invalid choice — re-prompt
    reprompt = {
        "hi": "कृपया भेजें:\n1 = अकाउंट बनाएं\n2 = गुमनाम रहें",
        "id": "Balas dengan:\n1 = Buat akun\n2 = Tetap anonim",
    }.get(language, "Please reply with:\n1 = Create/link account\n2 = Stay anonymous")
    await meta_send_text(phone, reprompt)


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


# =============================================================================
# B1: WELCOME / ONBOARDING FLOW
# =============================================================================

async def _handle_welcome(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    language: str,
):
    """Handle welcome — onboarding for new users, extended menu for returning users."""
    if user and session.user_id:
        # Returning user — extended menu
        wb_msg = {
            "hi": "वापसी पर स्वागत है! क्या करना चाहेंगे?",
            "id": "Selamat datang kembali! Apa yang ingin Anda lakukan?",
        }.get(language, "Welcome back! What would you like to do?")
        await meta_send_text(phone, wb_msg)
        await send_extended_menu(phone, language)
    else:
        # New user — onboarding
        onb_msg = {
            "hi": "FloodSafe में आपका स्वागत है!\n\n"
                  "बाढ़ से सुरक्षित रहने में मदद करता हूं। सेटअप करते हैं:",
            "id": "Selamat datang di FloodSafe!\n\n"
                  "Saya membantu Anda tetap aman dari banjir. Mari kita siapkan:",
        }.get(language, "Welcome to FloodSafe!\n\n"
                        "I help you stay safe from floods. Let me set you up:")
        await meta_send_text(phone, onb_msg)
        session.state = "onboarding_city"
        session.updated_at = datetime.utcnow()
        db.commit()
        await send_onboarding_city_buttons(phone, language)


# =============================================================================
# B6: FUZZY LOCATION SEARCH
# =============================================================================

async def _search_location(place_name: str, city: str = "delhi") -> list:
    """Search for a location using the internal search API. Returns list of results."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8000/api/search/locations/",
                params={"q": place_name, "city": city, "limit": 3},
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.warning(f"Location search failed: {e}")
    return []


async def _handle_onboarding_location_text(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle text input during onboarding location step — fuzzy search."""
    try:
        city = _get_session_data(session, "onboarding_city", "delhi")

        # Bug #9: Parse Google Maps URLs to extract coordinates or place name
        search_text = text
        extracted_coords = None
        if "google.com/maps" in text or "maps.google" in text or "goo.gl/maps" in text:
            import re
            # Try extracting coordinates (@lat,lng pattern)
            coord_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', text)
            if coord_match:
                extracted_coords = (float(coord_match.group(1)), float(coord_match.group(2)))
            else:
                # Try extracting place name from /search/QUERY/ or /place/QUERY/
                place_match = re.search(r'/(?:search|place)/([^/@]+)', text)
                if place_match:
                    from urllib.parse import unquote
                    search_text = unquote(place_match.group(1)).replace('+', ' ')

        if extracted_coords:
            lat, lng = extracted_coords
            await _complete_onboarding(db, session, phone, user, lat, lng, f"Location ({lat:.4f}, {lng:.4f})", city, language)
            return

        results = await _search_location(search_text, city)

        if len(results) == 1:
            # Single confident result — use it
            r = results[0]
            lat, lng = r.get("latitude"), r.get("longitude")
            name = r.get("name", text)
            await _complete_onboarding(db, session, phone, user, lat, lng, name, city, language)
        elif len(results) > 1:
            # Multiple results — present choices
            lines = ["I found these locations:\n"]
            session.data = session.data or {}
            session.data["search_results"] = []
            for i, r in enumerate(results, 1):
                name = r.get("name", "Unknown")
                lines.append(f"{i}. {name}")
                session.data["search_results"].append({
                    "name": name,
                    "lat": r.get("latitude"),
                    "lng": r.get("longitude"),
                })
            lines.append("\nReply with the number (1-3)")
            session.data["search_return_state"] = "onboarding_location"
            session.state = "search_results"
            session.updated_at = datetime.utcnow()
            db.commit()
            await meta_send_text(phone, "\n".join(lines))
        else:
            # No results
            nf_msg = {
                "hi": f'स्थान नहीं मिला: "{search_text}"\n\n'
                      "अधिक विशिष्ट नाम लिखें, या GPS location भेजें।",
                "id": f'Lokasi tidak ditemukan: "{search_text}"\n\n'
                      "Coba nama tempat lebih spesifik, atau kirim lokasi GPS.",
            }.get(language, f'Location not found: "{search_text}"\n\n'
                            "Try a more specific place name, or share your GPS location.")
            await meta_send_text(phone, nf_msg)
    except Exception as e:
        logger.error(f"Onboarding location text handler failed: {e}")
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            db.rollback()
        await meta_send_text(phone, get_message(TemplateKey.SESSION_ERROR, language))


async def _handle_search_result_selection(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle number selection from fuzzy search results."""
    try:
        choice = int(text.strip())
    except ValueError:
        await meta_send_text(phone, "Please reply with a number (1-3).")
        return

    results = _get_session_data(session, "search_results", [])
    return_state = _get_session_data(session, "search_return_state", "idle")

    if not results or choice < 1 or choice > len(results):
        await meta_send_text(phone, f"Please reply with a number between 1 and {len(results)}.")
        return

    selected = results[choice - 1]
    lat, lng, name = selected["lat"], selected["lng"], selected["name"]

    if return_state == "onboarding_location":
        city = _get_session_data(session, "onboarding_city", "delhi")
        await _complete_onboarding(db, session, phone, user, lat, lng, name, city, language)
    elif return_state == "adding_watch_area":
        await _complete_watch_area(db, session, phone, user, lat, lng, name, language)
    else:
        # Fallback — use as risk check location
        session.data = session.data or {}
        session.data["last_lat"] = lat
        session.data["last_lng"] = lng
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(phone, f"Location set: {name}")


# =============================================================================
# B4: ACCOUNT CREATION + ONBOARDING COMPLETION
# =============================================================================

async def _complete_onboarding(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    lat: float,
    lng: float,
    location_name: str,
    city: str,
    language: str,
):
    """Complete onboarding: create account + first watch area."""
    from ..domain.services.auth_service import AuthService

    # Create account if needed
    if not user:
        try:
            auth_service = AuthService()
            user = auth_service.get_or_create_phone_user(phone=phone, db=db)
            # Set preferences
            if user.auth_provider == "phone":
                user.auth_provider = "whatsapp"
            user.city_preference = city
            user.notification_whatsapp = True
            user.phone_verified = True
            db.commit()
        except Exception as e:
            logger.error(f"Onboarding account creation failed: {e}")
            session.state = "idle"
            session.updated_at = datetime.utcnow()
            db.commit()
            await meta_send_text(phone, get_message(TemplateKey.SESSION_ERROR, language))
            return

    # Create first watch area
    from ..infrastructure.models import WatchArea
    try:
        watch_area = WatchArea(
            user_id=user.id,
            name=location_name,
            location=f"POINT({lng} {lat})",
            radius=1000,
        )
        db.add(watch_area)
        db.commit()
    except Exception as e:
        logger.warning(f"Watch area creation during onboarding failed: {e}")

    # Update session
    session.user_id = user.id
    session.state = "idle"
    session.data = {"last_lat": lat, "last_lng": lng, "city": city}
    session.updated_at = datetime.utcnow()
    db.commit()

    done_msg = {
        "hi": f"सब सेट! {location_name} के पास बाढ़ की रिपोर्ट होने पर अलर्ट मिलेगा।\n\n"
              f"और watch spots जोड़ सकते हैं। HELP लिखें सभी commands के लिए।",
        "id": f"Siap! Anda akan diberitahu saat banjir dilaporkan dekat {location_name}.\n\n"
              f"Anda bisa menambah area pantauan kapan saja. Ketik HELP untuk semua perintah.",
    }.get(language, f"All set! I'll alert you when flooding is reported near {location_name}.\n\n"
                    f"You can add more watch spots anytime. Type HELP for all commands.")
    await meta_send_text(phone, done_msg)
    await send_menu_buttons(phone, language)


# =============================================================================
# C1: WATCH AREA MANAGEMENT
# =============================================================================

async def _handle_watch_area_text(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle text input when adding a watch area — fuzzy search."""
    city = _get_session_data(session, "city", "delhi")
    if user and hasattr(user, "city_preference") and user.city_preference:
        city = user.city_preference

    results = await _search_location(text, city)

    if len(results) == 1:
        r = results[0]
        await _complete_watch_area(db, session, phone, user,
                                   r["latitude"], r["longitude"], r.get("name", text), language)
    elif len(results) > 1:
        lines = ["I found these locations:\n"]
        session.data = session.data or {}
        session.data["search_results"] = []
        for i, r in enumerate(results, 1):
            name = r.get("name", "Unknown")
            lines.append(f"{i}. {name}")
            session.data["search_results"].append({
                "name": name, "lat": r.get("latitude"), "lng": r.get("longitude"),
            })
        lines.append("\nReply with the number (1-3)")
        session.data["search_return_state"] = "adding_watch_area"
        session.state = "search_results"
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(phone, "\n".join(lines))
    else:
        await meta_send_text(
            phone,
            f'Location not found: "{text}"\n\nTry a more specific name or share GPS location.'
        )


async def _complete_watch_area(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    lat: float,
    lng: float,
    name: str,
    language: str,
):
    """Create a watch area and confirm."""
    if not user:
        await meta_send_text(phone, "Please link your account first. Reply LINK.")
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        return

    from ..infrastructure.models import WatchArea
    try:
        wa = WatchArea(user_id=user.id, name=name, location=f"POINT({lng} {lat})", radius=1000)
        db.add(wa)
        db.commit()
    except Exception as e:
        logger.error(f"Watch area creation failed: {e}")
        await meta_send_text(phone, "Failed to create watch spot. Please try again.")
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        return

    # Count user's watch areas
    count = db.query(WatchArea).filter(WatchArea.user_id == user.id).count()

    session.state = "idle"
    session.updated_at = datetime.utcnow()
    db.commit()

    await meta_send_text(
        phone,
        f"Watch spot added: {name}\n"
        f"I'll alert you when flooding is reported nearby.\n\n"
        f"Total watch spots: {count}"
    )


# =============================================================================
# E4/E7: CIRCLE LISTING & INVITE COMMANDS
# =============================================================================

async def _handle_circles_command(
    db: Session,
    phone: str,
    user: Optional[User],
    language: str,
):
    """E4: List user's safety circles with member counts and invite codes."""
    if not user:
        await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
        return

    from ..domain.services.circle_service import CircleService
    try:
        circle_service = CircleService(db)
        circles_data = circle_service.get_user_circles(user.id)
    except Exception as e:
        logger.error(f"Failed to fetch circles: {e}")
        await meta_send_text(phone, get_message(TemplateKey.ERROR, language))
        return

    if not circles_data:
        no_circles = {
            "hi": "अभी कोई सर्कल नहीं। नई सर्कल बनाएं या आमंत्रण कोड से जुड़ें।",
            "id": "Belum ada lingkaran. Buat lingkaran baru atau bergabung dengan kode undangan.",
        }.get(language, "No circles yet. Create one or join with an invite code.")
        await meta_send_text(phone, no_circles)
        await send_circles_menu_buttons(phone, language)
        return

    # Format circles list
    lines = []
    for i, entry in enumerate(circles_data[:10], 1):
        circle = entry["circle"]
        count = entry["member_count"]
        role = "Creator" if circle.created_by == user.id else "Member"
        if language == "hi":
            role = "निर्माता" if circle.created_by == user.id else "सदस्य"
        elif language == "id":
            role = "Pembuat" if circle.created_by == user.id else "Anggota"

        line = f"{i}. {circle.name} ({count} {'anggota' if language == 'id' else 'सदस्य' if language == 'hi' else 'members'}) — {role}"
        if circle.created_by == user.id and circle.invite_code:
            line += f"\n   {'Kode' if language == 'id' else 'कोड' if language == 'hi' else 'Code'}: {circle.invite_code}"
        lines.append(line)

    circles_list = "\n\n".join(lines)
    msg = get_message(
        TemplateKey.CIRCLES_LIST,
        language,
        count=len(circles_data),
        circles_list=circles_list,
    )
    await meta_send_text(phone, msg)
    await send_circles_menu_buttons(phone, language)


async def _handle_invite_command(
    db: Session,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """E7: Share a circle invite code as a forwardable WhatsApp message."""
    if not user:
        await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
        return

    from ..domain.services.circle_service import CircleService
    try:
        circle_service = CircleService(db)
        circles_data = circle_service.get_user_circles(user.id)
    except Exception as e:
        logger.error(f"Failed to fetch circles for invite: {e}")
        await meta_send_text(phone, get_message(TemplateKey.ERROR, language))
        return

    if not circles_data:
        no_circles = {
            "hi": "आपकी कोई सर्कल नहीं है। पहले एक बनाएं: CREATE [नाम]",
            "id": "Anda belum punya lingkaran. Buat dulu: CREATE [nama]",
        }.get(language, "You don't have any circles. Create one first: CREATE [name]")
        await meta_send_text(phone, no_circles)
        return

    # Check if user specified a circle number: "INVITE 1" or "INVITE 2"
    arg = text[6:].strip()
    target_circle = None

    if arg and arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(circles_data):
            target_circle = circles_data[idx]["circle"]
    elif not arg:
        # No number specified — use first circle user created
        for entry in circles_data:
            if entry["circle"].created_by == user.id:
                target_circle = entry["circle"]
                break
        if not target_circle:
            # User is not creator of any circle — show list
            await _handle_circles_command(db, phone, user, language)
            return

    if not target_circle:
        invalid = {
            "hi": f"अमान्य नंबर। 1 से {len(circles_data)} के बीच चुनें।",
            "id": f"Nomor tidak valid. Pilih antara 1 dan {len(circles_data)}.",
        }.get(language, f"Invalid number. Choose between 1 and {len(circles_data)}.")
        await meta_send_text(phone, invalid)
        return

    if not target_circle.invite_code:
        no_code = {
            "hi": "इस सर्कल में आमंत्रण कोड नहीं है।",
            "id": "Lingkaran ini tidak memiliki kode undangan.",
        }.get(language, "This circle doesn't have an invite code.")
        await meta_send_text(phone, no_code)
        return

    # Send the forwardable invite message
    msg = get_message(
        TemplateKey.CIRCLE_INVITE_SHARE,
        language,
        name=target_circle.name,
        code=target_circle.invite_code,
    )
    await meta_send_text(phone, msg)


# =============================================================================
# E5/E6: CIRCLE MANAGEMENT HANDLERS
# =============================================================================

async def _handle_create_circle_name(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle circle name input for creation."""
    if not user:
        await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        return

    from ..domain.services.circle_service import CircleService
    try:
        circle_service = CircleService(db)
        circle = circle_service.create_circle(
            user_id=user.id,
            name=text.strip(),
            description=None,
            circle_type="custom",
        )
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(
            phone,
            get_message(TemplateKey.CIRCLE_CREATED, language, name=circle.name, code=circle.invite_code),
        )
    except Exception as e:
        logger.error(f"Circle creation failed: {e}")
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        await meta_send_text(phone, get_message(TemplateKey.ERROR, language))


async def _handle_join_circle_code(
    db: Session,
    session: WhatsAppSession,
    phone: str,
    user: Optional[User],
    text: str,
    language: str,
):
    """Handle invite code input for joining a circle."""
    if not user:
        await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        return

    invite_code = text.strip().upper()
    from ..domain.services.circle_service import CircleService
    try:
        circle_service = CircleService(db)
        result = circle_service.join_by_invite_code(invite_code, user.id)
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        if result:
            circle_name = result.name if hasattr(result, "name") else "the circle"
            await meta_send_text(
                phone,
                get_message(TemplateKey.CIRCLE_JOINED, language, name=circle_name),
            )
        else:
            await meta_send_text(phone, get_message(TemplateKey.CIRCLE_INVALID_CODE, language))
    except Exception as e:
        error_msg = str(e).lower()
        session.state = "idle"
        session.updated_at = datetime.utcnow()
        db.commit()
        if "already" in error_msg:
            await meta_send_text(phone, get_message(TemplateKey.CIRCLE_ALREADY_MEMBER, language))
        elif "invalid" in error_msg or "not found" in error_msg:
            await meta_send_text(phone, get_message(TemplateKey.CIRCLE_INVALID_CODE, language))
        else:
            logger.error(f"Circle join failed: {e}")
            await meta_send_text(phone, get_message(TemplateKey.ERROR, language))


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
            {
                "hi": "Flooding report karne ke liye:\n\n"
                      "1. Flooding ki photo lein\n"
                      "2. + > Location > Apna location bhejein\n"
                      "3. Dono ek saath bhejein!",
                "id": "Untuk melaporkan banjir:\n\n"
                      "1. Ambil foto banjir\n"
                      "2. Ketuk + > Lokasi > Kirim lokasi saat ini\n"
                      "3. Kirim keduanya bersamaan!\n\n"
                      "Kami akan verifikasi dengan AI dan memberitahu orang sekitar.",
            }.get(language, "To report flooding:\n\n"
                           "1. Take a photo of the flooding\n"
                           "2. Tap + > Location > Send current location\n"
                           "3. Send both together!\n\n"
                           "We'll verify with AI and alert nearby people.")
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
    # Onboarding city buttons
    elif button_id.startswith("city_"):
        city_map = {
            "city_delhi": "delhi", "city_bangalore": "bangalore",
            "city_yogyakarta": "yogyakarta", "city_singapore": "singapore",
            "city_indore": "indore",
        }
        if button_id == "city_more":
            await send_onboarding_city_2_buttons(phone, language)
        elif button_id in city_map:
            city = city_map[button_id]
            session.data = session.data or {}
            session.data["onboarding_city"] = city
            session.state = "onboarding_location"
            session.updated_at = datetime.utcnow()
            db.commit()
            city_display = city.title()
            city_msg = {
                "hi": f"ठीक है! आप {city_display} में हैं।\n\n"
                      f"अपना location भेजें ताकि मैं बाढ़-प्रवण क्षेत्र खोज सकूं।\n"
                      f"या जगह का नाम लिखें",
                "id": f"Oke! Anda di {city_display}.\n\n"
                      f"Kirim lokasi Anda agar saya bisa menemukan area rawan banjir.\n"
                      f"Atau ketik nama tempat (mis. \"Malioboro\")",
            }.get(language, f"Got it! You're in {city_display}.\n\n"
                            f"Share your location so I can find flood-prone areas near you.\n"
                            f"Or type a place name (e.g., \"Connaught Place\")")
            await meta_send_text(phone, city_msg)
    # Extended menu buttons
    elif button_id == "my_watch_spots":
        if not user:
            await meta_send_text(phone, "Link your account to manage watch spots. Reply LINK.")
            return
        response = await handle_my_areas_command(db, user)
        await meta_send_text(phone, response)
    elif button_id == "my_reports":
        if not user:
            await meta_send_text(phone, "Link your account to view your reports. Reply LINK.")
            return
        # Show user's reports count
        from ..infrastructure.models import Report
        count = db.query(Report).filter(Report.user_id == user.id).count()
        await meta_send_text(
            phone,
            f"You have {count} reports.\n"
            f"View details in the FloodSafe app."
        )
    elif button_id == "settings":
        if not user:
            await meta_send_text(phone, "Link your account to manage settings. Reply LINK.")
            return
        city = getattr(user, "city_preference", "Not set") or "Not set"
        lang_display = {"hi": "Hindi", "id": "Indonesia"}.get(language, "English")
        wa_alerts = "ON" if user.notification_whatsapp else "OFF"
        from ..infrastructure.models import WatchArea as WA
        spots = db.query(WA).filter(WA.user_id == user.id).count()
        await meta_send_text(
            phone,
            f"YOUR SETTINGS\n\n"
            f"City: {city.title() if city != 'Not set' else city}\n"
            f"Language: {lang_display}\n"
            f"WhatsApp Alerts: {wa_alerts}\n"
            f"Watch Spots: {spots}\n\n"
            f"Reply:\n"
            f"- \"LANGUAGE hindi\" to change language\n"
            f"- \"CITY bangalore\" to change city\n"
            f"- \"ALERTS OFF\" to disable alerts"
        )
    # Circle buttons
    elif button_id == "create_circle":
        if not user:
            await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
            return
        session.state = "creating_circle"
        session.updated_at = datetime.utcnow()
        db.commit()
        prompt = {"hi": "अपनी सर्कल का नाम बताएं:", "id": "Masukkan nama lingkaran Anda:"}.get(language, "What name for your circle?")
        await meta_send_text(phone, prompt)
    elif button_id == "join_circle":
        if not user:
            await meta_send_text(phone, get_message(TemplateKey.CIRCLE_NOT_LINKED, language))
            return
        session.state = "joining_circle"
        session.updated_at = datetime.utcnow()
        db.commit()
        prompt = {"hi": "आमंत्रण कोड दर्ज करें:", "id": "Masukkan kode undangan:"}.get(language, "Enter the invite code:")
        await meta_send_text(phone, prompt)
    else:
        logger.warning(f"Unknown Meta button: {button_id}")
        await _handle_welcome(db, session, phone, user, language)
