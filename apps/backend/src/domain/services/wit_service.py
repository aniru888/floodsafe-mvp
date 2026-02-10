"""
Wit.ai NLU Service — Natural Language Understanding for WhatsApp Bot.

Provides intent classification and entity extraction for Hindi/English/Hinglish
text messages. Used as an enhancement layer on top of keyword matching.

Meta's Wit.ai is free, supports Hindi natively, and responds in <100ms.
"""
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)

# Wit.ai API endpoint
WIT_API_URL = "https://api.wit.ai/message"
WIT_API_VERSION = "20240101"

# Minimum confidence to trust Wit.ai intent classification
WIT_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class WitIntent:
    """Parsed Wit.ai classification result."""
    name: str                         # Intent name (e.g., "check_risk")
    confidence: float                 # 0.0 to 1.0
    location: Optional[str] = None   # Extracted location entity
    severity: Optional[str] = None   # Extracted severity entity
    raw_text: str = ""               # Original user text


# Map Wit.ai intent names to internal command identifiers
INTENT_MAP = {
    "check_risk": "risk",
    "report_flood": "report",
    "get_warnings": "warnings",
    "check_status": "status",
    "get_help": "help",
    "get_my_areas": "my_areas",
    "greet": "welcome",
}


def is_wit_enabled() -> bool:
    """Check if Wit.ai is configured and enabled."""
    return bool(settings.WIT_AI_TOKEN) and settings.WIT_AI_ENABLED


async def classify_message(text: str) -> Optional[WitIntent]:
    """
    Classify a text message using Wit.ai NLU.

    Sends the raw text to Wit.ai and returns structured intent + entities.
    Returns None if Wit.ai is disabled, unreachable, or confidence is too low.

    Args:
        text: Raw message text from user (Hindi, English, or Hinglish)

    Returns:
        WitIntent with classified intent and extracted entities, or None
    """
    if not is_wit_enabled():
        return None

    if not text or not text.strip():
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                WIT_API_URL,
                params={"v": WIT_API_VERSION, "q": text.strip()[:280]},
                headers={
                    "Authorization": f"Bearer {settings.WIT_AI_TOKEN}",
                    "Accept": "application/json",
                },
                timeout=5.0,
            )

            if response.status_code != 200:
                logger.warning(f"Wit.ai API returned {response.status_code}")
                return None

            data = response.json()

    except httpx.TimeoutException:
        logger.warning("Wit.ai API timeout (>5s)")
        return None
    except Exception as e:
        logger.error(f"Wit.ai API error: {e}")
        return None

    return _parse_wit_response(data, text)


def _parse_wit_response(data: dict, original_text: str) -> Optional[WitIntent]:
    """
    Parse Wit.ai JSON response into a WitIntent.

    Wit.ai response format:
    {
        "text": "...",
        "intents": [{"id": "...", "name": "check_risk", "confidence": 0.95}],
        "entities": {
            "wit$location:location": [{"body": "Minto Bridge", "confidence": 0.88, ...}],
            "severity:severity": [{"value": "high", "confidence": 0.72, ...}]
        }
    }
    """
    # Extract top intent
    intents = data.get("intents", [])
    if not intents:
        logger.debug(f"Wit.ai: no intent detected for '{original_text[:50]}'")
        return None

    top_intent = intents[0]
    intent_name = top_intent.get("name", "")
    confidence = top_intent.get("confidence", 0.0)

    # Check confidence threshold
    if confidence < WIT_CONFIDENCE_THRESHOLD:
        logger.debug(
            f"Wit.ai: low confidence {confidence:.2f} for intent '{intent_name}' "
            f"(threshold: {WIT_CONFIDENCE_THRESHOLD})"
        )
        return None

    # Extract location entity (Wit.ai built-in or custom)
    location = None
    entities = data.get("entities", {})

    # Check multiple possible location entity keys
    for key in ("wit$location:location", "location:location", "wit$location"):
        if key in entities and entities[key]:
            location_entity = entities[key][0]
            location = location_entity.get("resolved", {}).get("values", [{}])[0].get("name")
            if not location:
                location = location_entity.get("body")
            break

    # Extract severity entity (custom)
    severity = None
    for key in ("severity:severity", "severity"):
        if key in entities and entities[key]:
            severity = entities[key][0].get("value")
            break

    result = WitIntent(
        name=intent_name,
        confidence=confidence,
        location=location,
        severity=severity,
        raw_text=original_text,
    )

    logger.info(
        f"Wit.ai: intent='{intent_name}' confidence={confidence:.2f} "
        f"location='{location}' severity='{severity}'"
    )

    return result


def get_mapped_command(intent: WitIntent) -> Optional[str]:
    """
    Map a Wit.ai intent to an internal command string.

    Returns the mapped command name, or None if the intent isn't recognized.
    """
    return INTENT_MAP.get(intent.name)
