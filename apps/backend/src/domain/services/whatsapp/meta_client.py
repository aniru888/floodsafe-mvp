"""
Meta WhatsApp Cloud API Client.

Sends messages via Meta's Graph API (replacing Twilio's TwiML response pattern).
Meta Cloud API is JSON-based: messages are sent via POST to Graph API,
not as response bodies.

Pricing: FREE inbound (service conversations) in India.
No Facebook Business verification needed to start (250 customers/day).
"""
import logging
from typing import Optional

import httpx

from ....core.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
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


async def download_media(media_id: str) -> Optional[bytes]:
    """
    Download media (photo) from Meta Graph API.

    Two-step process:
    1. GET media URL from Graph API
    2. Download the actual media file

    Args:
        media_id: Meta media ID from incoming message

    Returns:
        Media bytes, or None if download failed
    """
    try:
        async with httpx.AsyncClient() as client:
            # Step 1: Get media URL
            url_response = await client.get(
                f"{GRAPH_API_BASE}/{media_id}",
                headers={"Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}"},
                timeout=10.0,
            )

            if url_response.status_code != 200:
                logger.warning(
                    f"Meta media URL fetch failed: {url_response.status_code}"
                )
                return None

            media_url = url_response.json().get("url")
            if not media_url:
                logger.warning("No media URL in Meta response")
                return None

            # Step 2: Download actual media
            media_response = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}"},
                timeout=30.0,
            )

            if media_response.status_code != 200:
                logger.warning(
                    f"Meta media download failed: {media_response.status_code}"
                )
                return None

            return media_response.content

    except httpx.TimeoutException:
        logger.warning("Meta media download timeout")
        return None
    except Exception as e:
        logger.error(f"Meta media download error: {e}")
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


async def _send_request(url: str, payload: dict) -> bool:
    """
    Send a request to Meta Graph API.

    Args:
        url: API endpoint URL
        payload: JSON payload

    Returns:
        True if request succeeded (2xx), False otherwise
    """
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

            if response.status_code not in (200, 201):
                logger.warning(
                    f"Meta Graph API error {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return False

            return True

    except httpx.TimeoutException:
        logger.warning("Meta Graph API timeout")
        return False
    except Exception as e:
        logger.error(f"Meta Graph API error: {e}")
        return False
