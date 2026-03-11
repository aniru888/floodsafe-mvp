"""
Meta WhatsApp Cloud API Client.

Sends messages via Meta's Graph API (replacing Twilio's TwiML response pattern).
Meta Cloud API is JSON-based: messages are sent via POST to Graph API,
not as response bodies.

Pricing: FREE inbound (service conversations) in India.
No Facebook Business verification needed to start (250 customers/day).
"""
import asyncio
import logging
import time
from datetime import date
from typing import Optional

import httpx

from ....core.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v22.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Outbound rate limiting (Meta tier: 2,000/24hr, safe margin: 1,500)
OUTBOUND_DAILY_LIMIT = 1_500
OUTBOUND_WARNING_THRESHOLD = 1_400
_outbound_counter: dict = {"date": str(date.today()), "count": 0}


def is_meta_whatsapp_enabled() -> bool:
    """Check if Meta WhatsApp Cloud API is configured."""
    return (
        bool(settings.META_WHATSAPP_TOKEN)
        and bool(settings.META_PHONE_NUMBER_ID)
        and settings.META_WHATSAPP_ENABLED
    )


async def send_text_message(to: str, text: str) -> bool:
    """
    Send a text message via Meta Graph API.

    Args:
        to: Recipient phone number (E.164 format, e.g., "+919876543210")
        text: Message text

    Returns:
        True if sent successfully, False otherwise
    """
    url = f"{GRAPH_API_BASE}/{settings.META_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to.lstrip("+"),  # Meta expects without +
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    return await _send_request(url, payload)


async def send_interactive_buttons(
    to: str,
    body_text: str,
    buttons: list[dict],
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> bool:
    """
    Send interactive button message via Meta Graph API.

    Args:
        to: Recipient phone number
        body_text: Main message body
        buttons: List of button dicts with "id" and "title" keys
        header: Optional header text
        footer: Optional footer text

    Returns:
        True if sent successfully
    """
    url = f"{GRAPH_API_BASE}/{settings.META_PHONE_NUMBER_ID}/messages"

    # Meta allows max 3 buttons
    button_actions = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
        for b in buttons[:3]
    ]

    interactive = {
        "type": "button",
        "body": {"text": body_text},
        "action": {"buttons": button_actions},
    }

    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to.lstrip("+"),
        "type": "interactive",
        "interactive": interactive,
    }

    return await _send_request(url, payload)


async def send_location_request(to: str, body_text: str) -> bool:
    """
    Send a location request message.

    Args:
        to: Recipient phone number
        body_text: Message prompting user for location

    Returns:
        True if sent successfully
    """
    # Meta doesn't have a direct "request location" message type,
    # so we send a text message with instructions
    return await send_text_message(to, body_text)


async def download_media(media_id: str, max_retries: int = 2) -> Optional[bytes]:
    """
    Download media (photo) from Meta Graph API with retry.

    Two-step process with retry on 5xx/timeouts:
    1. GET media URL from Graph API
    2. Download the actual media file

    Args:
        media_id: Meta media ID from incoming message
        max_retries: Number of retry attempts (default 2)

    Returns:
        Media bytes, or None if download failed
    """
    backoff_delays = [1.0, 2.0]

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Get media URL
                url_response = await client.get(
                    f"{GRAPH_API_BASE}/{media_id}",
                    headers={"Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}"},
                    timeout=10.0,
                )

                if url_response.status_code != 200:
                    if 400 <= url_response.status_code < 500:
                        logger.warning(
                            f"Meta media URL fetch client error: {url_response.status_code}"
                        )
                        return None  # Don't retry 4xx
                    logger.warning(
                        f"Meta media URL fetch failed: {url_response.status_code} "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(backoff_delays[min(attempt, len(backoff_delays) - 1)])
                    continue

                media_url = url_response.json().get("url")
                if not media_url:
                    logger.warning("No media URL in Meta response")
                    return None  # Missing URL is not transient

                # Step 2: Download actual media
                media_response = await client.get(
                    media_url,
                    headers={"Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}"},
                    timeout=30.0,
                )

                if media_response.status_code != 200:
                    if 400 <= media_response.status_code < 500:
                        logger.warning(
                            f"Meta media download client error: {media_response.status_code}"
                        )
                        return None
                    logger.warning(
                        f"Meta media download server error: {media_response.status_code} "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(backoff_delays[min(attempt, len(backoff_delays) - 1)])
                    continue

                return media_response.content

        except httpx.TimeoutException:
            logger.warning(
                f"Meta media download timeout (attempt {attempt + 1}/{max_retries + 1})"
            )
        except Exception as e:
            logger.error(f"Meta media download error: {e}")
            return None  # Unknown errors don't retry

        if attempt < max_retries:
            await asyncio.sleep(backoff_delays[min(attempt, len(backoff_delays) - 1)])

    logger.error(f"Meta media download failed after {max_retries + 1} attempts")
    return None


async def mark_as_read(message_id: str) -> bool:
    """
    Mark a message as read (sends blue checkmarks).

    Args:
        message_id: The wamid of the message to mark as read

    Returns:
        True if marked successfully
    """
    url = f"{GRAPH_API_BASE}/{settings.META_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    return await _send_request(url, payload)


def _parse_meta_error(response) -> str:
    """Parse Meta Graph API structured error response for better logging."""
    try:
        data = response.json()
        error = data.get("error", {})
        if error:
            code = error.get("code", "?")
            subcode = error.get("error_subcode", "")
            msg = error.get("message", "")
            fbtrace = error.get("fbtrace_id", "")
            subcode_str = f", subcode={subcode}" if subcode else ""
            return f"code={code}{subcode_str}, message={msg[:150]}, fbtrace={fbtrace}"
    except Exception:
        pass
    return response.text[:200]


async def _send_request(url: str, payload: dict, max_retries: int = 2) -> bool:
    """
    Send a request to Meta Graph API with retry on 5xx/timeouts.

    Retries up to max_retries times with 1s, 2s backoff on server errors (5xx)
    and timeouts. Does NOT retry on 4xx (client errors like bad token/payload).

    Args:
        url: API endpoint URL
        payload: JSON payload
        max_retries: Number of retry attempts (default 2)

    Returns:
        True if request succeeded (2xx), False otherwise
    """
    backoff_delays = [1.0, 2.0]  # seconds between retries

    # Outbound rate limiting — reset counter on new day
    today = str(date.today())
    if _outbound_counter["date"] != today:
        _outbound_counter["date"] = today
        _outbound_counter["count"] = 0

    # Check if we're at the daily limit
    if _outbound_counter["count"] >= OUTBOUND_DAILY_LIMIT:
        # For read receipts, silently skip
        if payload.get("status") == "read":
            return True  # Don't fail read receipts
        logger.error(
            f"Outbound rate limit reached ({_outbound_counter['count']}/{OUTBOUND_DAILY_LIMIT}). "
            f"Message NOT sent."
        )
        return False

    # Warn when approaching limit
    if _outbound_counter["count"] >= OUTBOUND_WARNING_THRESHOLD:
        # Skip non-critical messages (read receipts) when approaching limit
        if payload.get("status") == "read":
            return True
        logger.warning(
            f"Outbound rate limit warning: {_outbound_counter['count']}/{OUTBOUND_DAILY_LIMIT}"
        )

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code in (200, 201):
                    _outbound_counter["count"] += 1
                    return True

                # Parse Meta's structured error for better logging
                error_detail = _parse_meta_error(response)

                # 4xx = client error, don't retry
                if 400 <= response.status_code < 500:
                    logger.warning(
                        f"Meta Graph API client error {response.status_code}: "
                        f"{error_detail}"
                    )
                    return False

                # 5xx = server error, retry
                logger.warning(
                    f"Meta Graph API server error {response.status_code} "
                    f"(attempt {attempt + 1}/{max_retries + 1}): "
                    f"{error_detail}"
                )

        except httpx.TimeoutException:
            logger.warning(
                f"Meta Graph API timeout (attempt {attempt + 1}/{max_retries + 1})"
            )
        except Exception as e:
            logger.error(f"Meta Graph API error: {e}")
            return False  # Unknown errors don't retry

        # Wait before retrying (if more attempts remain)
        if attempt < max_retries:
            delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
            await asyncio.sleep(delay)

    logger.error(f"Meta Graph API failed after {max_retries + 1} attempts")
    return False


# =============================================================================
# SYNCHRONOUS SEND (for circle_notification_service, sos_service)
# =============================================================================


def send_text_message_sync(to: str, text: str, max_retries: int = 2) -> bool:
    """
    Send a text message synchronously via Meta Graph API with retry.

    For use in synchronous service methods (CircleNotificationService, SOSService)
    that can't use async/await. Uses httpx.Client (not AsyncClient).

    Retries up to max_retries times with 1s, 2s backoff on 5xx/timeouts.

    Args:
        to: Recipient phone number (E.164 format)
        text: Message text
        max_retries: Number of retry attempts (default 2)

    Returns:
        True if sent successfully, False otherwise
    """
    url = f"{GRAPH_API_BASE}/{settings.META_PHONE_NUMBER_ID}/messages"
    backoff_delays = [1.0, 2.0]

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to.lstrip("+"),
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client() as client:
                response = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code in (200, 201):
                    return True

                # 4xx = client error, don't retry
                if 400 <= response.status_code < 500:
                    logger.warning(
                        f"Meta Graph API client error (sync) {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    return False

                # 5xx = server error, retry
                logger.warning(
                    f"Meta Graph API server error (sync) {response.status_code} "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )

        except httpx.TimeoutException:
            logger.warning(
                f"Meta Graph API timeout (sync) "
                f"(attempt {attempt + 1}/{max_retries + 1})"
            )
        except Exception as e:
            logger.error(f"Meta Graph API error (sync): {e}")
            return False  # Unknown errors don't retry

        if attempt < max_retries:
            delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
            time.sleep(delay)

    logger.error(f"Meta Graph API (sync) failed after {max_retries + 1} attempts")
    return False


# =============================================================================
# BILINGUAL BUTTON SETS (ported from button_sender.py)
# =============================================================================

# Button sets: (button_id, button_title) — Meta allows max 3 buttons, titles max 20 chars
BUTTON_SETS: dict[str, list[tuple[str, str]]] = {
    "welcome": [
        ("report_flood", "Report Flood"),
        ("check_risk", "Check Risk"),
        ("view_alerts", "View Alerts"),
    ],
    "after_location": [
        ("add_photo", "Add Photo"),
        ("submit_anyway", "Submit Anyway"),
        ("cancel", "Cancel"),
    ],
    "after_report": [
        ("check_risk", "Check Nearby"),
        ("report_flood", "Report Another"),
        ("menu", "Menu"),
    ],
    "risk_result": [
        ("report_flood", "Report Flood"),
        ("view_alerts", "View Alerts"),
        ("menu", "Menu"),
    ],
    "account_choice": [
        ("create_account", "Create Account"),
        ("stay_anonymous", "Stay Anonymous"),
    ],
    "menu": [
        ("report_flood", "Report Flood"),
        ("check_risk", "Check Risk"),
        ("view_alerts", "View Alerts"),
    ],
    "onboarding_city": [
        ("city_delhi", "Delhi"),
        ("city_bangalore", "Bangalore"),
        ("city_more", "More Cities"),
    ],
    "onboarding_city_2": [
        ("city_yogyakarta", "Yogyakarta"),
        ("city_singapore", "Singapore"),
        ("city_indore", "Indore"),
    ],
    "menu_extended_1": [
        ("report_flood", "Report Flood"),
        ("check_risk", "Check Risk"),
        ("view_alerts", "View Alerts"),
    ],
    "menu_extended_2": [
        ("my_watch_spots", "My Watch Spots"),
        ("my_reports", "My Reports"),
        ("settings", "Settings"),
    ],
    "circles_menu": [
        ("create_circle", "Create Circle"),
        ("join_circle", "Join Circle"),
        ("menu", "Back to Menu"),
    ],
}

BUTTON_SETS_HI: dict[str, list[tuple[str, str]]] = {
    "welcome": [
        ("report_flood", "बाढ़ रिपोर्ट"),
        ("check_risk", "जोखिम जांचें"),
        ("view_alerts", "अलर्ट"),
    ],
    "after_location": [
        ("add_photo", "फोटो जोड़ें"),
        ("submit_anyway", "बिना फोटो भेजें"),
        ("cancel", "रद्द करें"),
    ],
    "after_report": [
        ("check_risk", "आसपास जांचें"),
        ("report_flood", "और रिपोर्ट"),
        ("menu", "मेनू"),
    ],
    "risk_result": [
        ("report_flood", "बाढ़ रिपोर्ट"),
        ("view_alerts", "अलर्ट"),
        ("menu", "मेनू"),
    ],
    "account_choice": [
        ("create_account", "खाता बनाएं"),
        ("stay_anonymous", "गुमनाम रहें"),
    ],
    "menu": [
        ("report_flood", "बाढ़ रिपोर्ट"),
        ("check_risk", "जोखिम जांचें"),
        ("view_alerts", "अलर्ट"),
    ],
    "onboarding_city": [
        ("city_delhi", "दिल्ली"),
        ("city_bangalore", "बैंगलोर"),
        ("city_more", "और शहर"),
    ],
    "onboarding_city_2": [
        ("city_yogyakarta", "योग्याकार्ता"),
        ("city_singapore", "सिंगापुर"),
        ("city_indore", "इंदौर"),
    ],
    "menu_extended_1": [
        ("report_flood", "बाढ़ रिपोर्ट"),
        ("check_risk", "जोखिम जांचें"),
        ("view_alerts", "अलर्ट"),
    ],
    "menu_extended_2": [
        ("my_watch_spots", "मेरे Watch Spots"),
        ("my_reports", "मेरी रिपोर्ट"),
        ("settings", "सेटिंग्स"),
    ],
    "circles_menu": [
        ("create_circle", "सर्कल बनाएं"),
        ("join_circle", "सर्कल जॉइन करें"),
        ("menu", "मुख्य मेनू"),
    ],
}

BUTTON_SETS_ID: dict[str, list[tuple[str, str]]] = {
    "welcome": [
        ("report_flood", "Lapor Banjir"),
        ("check_risk", "Cek Risiko"),
        ("view_alerts", "Peringatan"),
    ],
    "after_location": [
        ("add_photo", "Tambah Foto"),
        ("submit_anyway", "Kirim Tanpa Foto"),
        ("cancel", "Batal"),
    ],
    "after_report": [
        ("check_risk", "Cek Sekitar"),
        ("report_flood", "Lapor Lagi"),
        ("menu", "Menu"),
    ],
    "risk_result": [
        ("report_flood", "Lapor Banjir"),
        ("view_alerts", "Peringatan"),
        ("menu", "Menu"),
    ],
    "account_choice": [
        ("create_account", "Buat Akun"),
        ("stay_anonymous", "Tetap Anonim"),
    ],
    "menu": [
        ("report_flood", "Lapor Banjir"),
        ("check_risk", "Cek Risiko"),
        ("view_alerts", "Peringatan"),
    ],
    "onboarding_city": [
        ("city_delhi", "Delhi"),
        ("city_bangalore", "Bangalore"),
        ("city_more", "Kota Lain"),
    ],
    "onboarding_city_2": [
        ("city_yogyakarta", "Yogyakarta"),
        ("city_singapore", "Singapura"),
        ("city_indore", "Indore"),
    ],
    "menu_extended_1": [
        ("report_flood", "Lapor Banjir"),
        ("check_risk", "Cek Risiko"),
        ("view_alerts", "Peringatan"),
    ],
    "menu_extended_2": [
        ("my_watch_spots", "Area Pantauan"),
        ("my_reports", "Laporan Saya"),
        ("settings", "Pengaturan"),
    ],
    "circles_menu": [
        ("create_circle", "Buat Lingkaran"),
        ("join_circle", "Gabung Lingkaran"),
        ("menu", "Menu Utama"),
    ],
}


def _get_buttons(set_name: str, language: str = "en") -> list[dict]:
    """Get button list formatted for send_interactive_buttons()."""
    source = {"hi": BUTTON_SETS_HI, "id": BUTTON_SETS_ID}.get(language, BUTTON_SETS)
    buttons = source.get(set_name, BUTTON_SETS.get(set_name, []))
    return [{"id": bid, "title": title} for bid, title in buttons]


async def send_welcome_buttons(to: str, language: str = "en") -> bool:
    """Send welcome message with main menu buttons."""
    body = {
        "hi": "FloodSafe में आपका स्वागत है!\nबाढ़ रिपोर्ट करें, जोखिम जांचें, या अलर्ट देखें।",
        "id": "Selamat datang di FloodSafe!\nLaporkan banjir, cek risiko, atau lihat peringatan.",
    }.get(language, "Welcome to FloodSafe!\nReport floods, check risk, or view alerts.")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("welcome", language),
        footer="FloodSafe",
    )


async def send_after_location_buttons(to: str, language: str = "en") -> bool:
    """Send buttons after receiving location (add photo / skip / cancel)."""
    body = {
        "hi": "📍 Location मिल गया!\n\nफोटो भेजें बेहतर verification के लिए, या बिना फोटो submit करें।",
        "id": "📍 Lokasi diterima!\n\nKirim foto untuk verifikasi lebih baik, atau kirim tanpa foto.",
    }.get(language, "📍 Location received!\n\nSend a photo for better verification, or submit without one.")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("after_location", language),
    )


async def send_after_report_buttons(to: str, language: str = "en") -> bool:
    """Send buttons after flood report is submitted."""
    body = {
        "hi": "और कुछ करना चाहते हैं?",
        "id": "Apa yang ingin Anda lakukan selanjutnya?",
    }.get(language, "What would you like to do next?")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("after_report", language),
    )


async def send_risk_result_buttons(to: str, language: str = "en") -> bool:
    """Send buttons after risk check result."""
    body = {
        "hi": "और कुछ जांचना है?",
        "id": "Ada yang lain?",
    }.get(language, "Need anything else?")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("risk_result", language),
    )


async def send_account_choice_buttons(to: str, language: str = "en") -> bool:
    """Send account creation choice buttons (create / stay anonymous)."""
    body = {
        "hi": "क्या आप FloodSafe अकाउंट बनाना चाहते हैं?\n\n1. नया अकाउंट बनाएं\n2. गुमनाम रहें",
        "id": "Apakah Anda ingin membuat akun FloodSafe?\n\n1. Buat akun baru\n2. Tetap anonim",
    }.get(language, "Would you like to create a FloodSafe account?\n\n1. Create a new account\n2. Stay anonymous")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("account_choice", language),
    )


async def send_menu_buttons(to: str, language: str = "en") -> bool:
    """Send general menu buttons."""
    body = {
        "hi": "मैं आपकी कैसे मदद कर सकता हूं?",
        "id": "Bagaimana saya bisa membantu?",
    }.get(language, "How can I help you?")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("menu", language),
        footer="FloodSafe",
    )


async def send_onboarding_city_buttons(to: str, language: str = "en") -> bool:
    """Send city selection buttons for new user onboarding."""
    body = {
        "hi": "आप किस शहर में हैं?",
        "id": "Anda di kota mana?",
    }.get(language, "Which city are you in?")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("onboarding_city", language),
    )


async def send_onboarding_city_2_buttons(to: str, language: str = "en") -> bool:
    """Send second page of city selection buttons."""
    body = {
        "hi": "अपना शहर चुनें:",
        "id": "Pilih kota Anda:",
    }.get(language, "Select your city:")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("onboarding_city_2", language),
    )


async def send_extended_menu(to: str, language: str = "en") -> bool:
    """Send extended menu as 2 messages (6 options)."""
    body1 = {
        "hi": "मैं आपकी कैसे मदद कर सकता हूं?",
        "id": "Apa yang ingin Anda lakukan?",
    }.get(language, "What would you like to do?")
    body2 = {
        "hi": "और विकल्प:",
        "id": "Opsi lainnya:",
    }.get(language, "More options:")
    result1 = await send_interactive_buttons(
        to,
        body_text=body1,
        buttons=_get_buttons("menu_extended_1", language),
        footer="FloodSafe",
    )
    result2 = await send_interactive_buttons(
        to,
        body_text=body2,
        buttons=_get_buttons("menu_extended_2", language),
    )
    return result1 and result2


async def send_circles_menu_buttons(to: str, language: str = "en") -> bool:
    """Send safety circles management buttons."""
    body = {
        "hi": "सेफ्टी सर्कल मैनेज करें:",
        "id": "Kelola lingkaran keselamatan Anda:",
    }.get(language, "Manage your safety circles:")
    return await send_interactive_buttons(
        to,
        body_text=body,
        buttons=_get_buttons("circles_menu", language),
    )
