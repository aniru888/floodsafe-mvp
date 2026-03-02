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
from typing import Optional

import httpx

from ....core.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v22.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


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
                    return True

                # 4xx = client error, don't retry
                if 400 <= response.status_code < 500:
                    logger.warning(
                        f"Meta Graph API client error {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    return False

                # 5xx = server error, retry
                logger.warning(
                    f"Meta Graph API server error {response.status_code} "
                    f"(attempt {attempt + 1}/{max_retries + 1}): "
                    f"{response.text[:200]}"
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
}


def _get_buttons(set_name: str, language: str = "en") -> list[dict]:
    """Get button list formatted for send_interactive_buttons()."""
    source = BUTTON_SETS_HI if language == "hi" else BUTTON_SETS
    buttons = source.get(set_name, BUTTON_SETS.get(set_name, []))
    return [{"id": bid, "title": title} for bid, title in buttons]


async def send_welcome_buttons(to: str, language: str = "en") -> bool:
    """Send welcome message with main menu buttons."""
    return await send_interactive_buttons(
        to,
        body_text=(
            "FloodSafe में आपका स्वागत है!\nबाढ़ रिपोर्ट करें, जोखिम जांचें, या अलर्ट देखें।"
            if language == "hi" else
            "Welcome to FloodSafe!\nReport floods, check risk, or view alerts."
        ),
        buttons=_get_buttons("welcome", language),
        footer="FloodSafe",
    )


async def send_after_location_buttons(to: str, language: str = "en") -> bool:
    """Send buttons after receiving location (add photo / skip / cancel)."""
    return await send_interactive_buttons(
        to,
        body_text=(
            "📍 Location मिल गया!\n\nफोटो भेजें बेहतर verification के लिए, या बिना फोटो submit करें।"
            if language == "hi" else
            "📍 Location received!\n\nSend a photo for better verification, or submit without one."
        ),
        buttons=_get_buttons("after_location", language),
    )


async def send_after_report_buttons(to: str, language: str = "en") -> bool:
    """Send buttons after flood report is submitted."""
    return await send_interactive_buttons(
        to,
        body_text=(
            "और कुछ करना चाहते हैं?"
            if language == "hi" else
            "What would you like to do next?"
        ),
        buttons=_get_buttons("after_report", language),
    )


async def send_risk_result_buttons(to: str, language: str = "en") -> bool:
    """Send buttons after risk check result."""
    return await send_interactive_buttons(
        to,
        body_text=(
            "और कुछ जांचना है?"
            if language == "hi" else
            "Need anything else?"
        ),
        buttons=_get_buttons("risk_result", language),
    )


async def send_account_choice_buttons(to: str, language: str = "en") -> bool:
    """Send account creation choice buttons (create / stay anonymous)."""
    return await send_interactive_buttons(
        to,
        body_text=(
            "क्या आप FloodSafe अकाउंट बनाना चाहते हैं?\n\n"
            "1. नया अकाउंट बनाएं\n2. गुमनाम रहें"
            if language == "hi" else
            "Would you like to create a FloodSafe account?\n\n"
            "1. Create a new account\n2. Stay anonymous"
        ),
        buttons=_get_buttons("account_choice", language),
    )


async def send_menu_buttons(to: str, language: str = "en") -> bool:
    """Send general menu buttons."""
    return await send_interactive_buttons(
        to,
        body_text=(
            "मैं आपकी कैसे मदद कर सकता हूं?"
            if language == "hi" else
            "How can I help you?"
        ),
        buttons=_get_buttons("menu", language),
        footer="FloodSafe",
    )
