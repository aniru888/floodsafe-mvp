"""
AI Chat Service — Multi-turn conversational flood assistant.

Provides a stateful chatbot for FloodSafe users with:
- Conversation memory (LRU, 200 conversations, 30min TTL, 5-turn sliding window)
- FloodSafe-aware system prompt with city/FHI/weather context
- Shared rate limiting with llama_service (same Groq free tier)
- Graceful degradation when rate-limited or API unavailable
"""
import logging
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import httpx

from ...core.config import settings
from .llama_service import (
    _check_rate_limit,
    _get_api_config,
    _record_request,
    is_llama_enabled,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

_MAX_CONVERSATIONS = 200
_CONVERSATION_TTL_SECONDS = 30 * 60  # 30 minutes
_MAX_TURNS = 5  # sliding window: keep last 5 turns (10 messages)


class ConversationMemory:
    """
    In-memory LRU store for chat conversation histories.

    Stores up to MAX_CONVERSATIONS conversations.
    Each conversation holds up to MAX_TURNS (user+assistant pairs).
    Entries expire after TTL seconds of inactivity.
    """

    def __init__(
        self,
        max_conversations: int = _MAX_CONVERSATIONS,
        ttl_seconds: int = _CONVERSATION_TTL_SECONDS,
        max_turns: int = _MAX_TURNS,
    ) -> None:
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_conversations = max_conversations
        self._ttl_seconds = ttl_seconds
        self._max_turns = max_turns

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        return time.time() - entry["last_active"] > self._ttl_seconds

    def get(self, conversation_id: str) -> Optional[List[Dict[str, str]]]:
        """Return message history for a conversation, or None if missing/expired."""
        entry = self._store.get(conversation_id)
        if entry is None:
            return None
        if self._is_expired(entry):
            del self._store[conversation_id]
            return None
        # Move to end (most recently used)
        self._store.move_to_end(conversation_id)
        return entry["messages"]

    def set(self, conversation_id: str, messages: List[Dict[str, str]]) -> None:
        """Upsert message history, enforcing sliding window and LRU eviction."""
        # Enforce sliding window: keep last max_turns pairs (2*max_turns messages)
        max_messages = self._max_turns * 2
        if len(messages) > max_messages:
            messages = messages[-max_messages:]

        self._store[conversation_id] = {
            "messages": messages,
            "last_active": time.time(),
        }
        self._store.move_to_end(conversation_id)

        # Evict oldest entry if over capacity
        while len(self._store) > self._max_conversations:
            self._store.popitem(last=False)

    def new_id(self) -> str:
        """Generate a fresh conversation ID."""
        return str(uuid.uuid4())


# Module-level singleton
_memory = ConversationMemory()

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_CHAT_SYSTEM_PROMPT = """You are FloodBot, a helpful urban flood assistant for FloodSafe — a nonprofit flood monitoring platform serving Delhi, Bangalore, Indore (India), Yogyakarta (Indonesia), and Singapore.

You help residents understand current flood conditions, plan safe routes, interpret flood risk scores, and take practical action.

TONE AND STYLE:
- Be concise, practical, and reassuring. Max 3-4 sentences per reply.
- Use plain language. Avoid jargon. Think "helpful neighbour", not "emergency broadcast".
- NEVER say: "evacuate", "life-threatening", "catastrophic", "disaster", "emergency" unless the user explicitly asks about extreme scenarios.
- For urban flooding: waterlogging = temporary puddles and slow drains on roads, NOT river floods.

WHAT YOU KNOW:
- FloodSafe tracks 499 flood hotspots across 5 cities with live FHI (Flood Hazard Index) scores.
- FHI scale: 0.0-0.3 = Low (green), 0.3-0.6 = Moderate (yellow), 0.6-0.8 = High (orange), 0.8-1.0 = Extreme (red).
- FHI combines: rainfall (35%), intensity (18%), soil saturation (12%), antecedent rainfall (12%), recent reports (8%), elevation risk (15%).
- Users can report flood sightings, join safety circles, and get alerts for their watch areas.

CONTEXT INJECTION:
If context is provided at the start of the conversation, use it to personalise your response. Do not repeat raw numbers unless helpful.

If asked something outside your knowledge (e.g., specific road closures you don't have data for), say so honestly and suggest checking local traffic apps."""

# ---------------------------------------------------------------------------
# Main chat function
# ---------------------------------------------------------------------------


async def chat(
    message: str,
    city: str,
    conversation_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send a message to the AI chatbot and receive a reply.

    Manages conversation memory, injects city/FHI context into the system
    prompt, and calls the Groq/Llama API with a sliding-window history.

    Args:
        message: The user's message text.
        city: City key (e.g. "delhi", "singapore") for context.
        conversation_id: Existing conversation ID to continue, or None to start new.
        context: Optional dict with live context data (fhi_score, risk_level,
                 precipitation_mm, active_alerts, etc.) to inject into the prompt.

    Returns:
        Dict with keys:
            reply (str): The assistant's response.
            conversation_id (str): ID to pass on the next call.
            rate_limited (bool): True if the API was not called due to rate limits.
    """
    # Resolve or create conversation
    if conversation_id:
        history = _memory.get(conversation_id)
        if history is None:
            # Expired or unknown — start fresh with same ID
            history = []
    else:
        conversation_id = _memory.new_id()
        history = []

    # Build system prompt with context
    system_content = _build_system_prompt(city, context)

    # Check if the API is available
    if not is_llama_enabled():
        fallback_reply = _fallback_reply(message)
        _append_turn(history, message, fallback_reply)
        _memory.set(conversation_id, history)
        return {
            "reply": fallback_reply,
            "conversation_id": conversation_id,
            "rate_limited": False,
        }

    if not _check_rate_limit():
        logger.warning("AI chat rate limited — returning static response")
        fallback_reply = (
            "I'm temporarily unavailable due to high demand. "
            "Please check the map for live flood conditions and try again in a few minutes."
        )
        _append_turn(history, message, fallback_reply)
        _memory.set(conversation_id, history)
        return {
            "reply": fallback_reply,
            "conversation_id": conversation_id,
            "rate_limited": True,
        }

    # Build messages list for API call
    api_messages = [{"role": "system", "content": system_content}]
    api_messages.extend(history)
    api_messages.append({"role": "user", "content": message})

    # Call the API
    base_url, api_key, model = _get_api_config()
    reply = await _call_chat_api(base_url, api_key, model, api_messages)

    if reply is None:
        # Try fallback if primary failed
        if base_url == settings.LLAMA_API_URL and settings.LLAMA_FALLBACK_API_KEY:
            reply = await _call_chat_api(
                settings.LLAMA_FALLBACK_URL,
                settings.LLAMA_FALLBACK_API_KEY,
                settings.LLAMA_FALLBACK_MODEL,
                api_messages,
            )

    if reply is None:
        reply = (
            "I'm having trouble connecting right now. "
            "Please check the FloodSafe map for live conditions in your area."
        )

    _append_turn(history, message, reply)
    _memory.set(conversation_id, history)

    return {
        "reply": reply,
        "conversation_id": conversation_id,
        "rate_limited": False,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_system_prompt(city: str, context: Optional[Dict[str, Any]]) -> str:
    """Append live context data to the base system prompt."""
    prompt = _CHAT_SYSTEM_PROMPT

    city_display = {
        "delhi": "Delhi, India",
        "bangalore": "Bangalore, India",
        "indore": "Indore, India",
        "yogyakarta": "Yogyakarta, Indonesia",
        "singapore": "Singapore",
    }.get(city.lower(), city.title())

    prompt += f"\n\nCURRENT SESSION:\nCity: {city_display}"

    if context:
        fhi = context.get("fhi_score")
        risk = context.get("risk_level")
        rain = context.get("precipitation_mm")
        alerts = context.get("active_alerts")
        location = context.get("location_name")

        if location:
            prompt += f"\nUser location: {location}"
        if fhi is not None:
            prompt += f"\nCurrent FHI: {fhi:.2f}/1.00"
        if risk:
            prompt += f"\nRisk level: {risk.upper()}"
        if rain is not None and rain > 0:
            prompt += f"\nRecent rainfall: {rain:.1f}mm"
        if alerts is not None and alerts > 0:
            prompt += f"\nActive official alerts: {alerts}"

    return prompt


def _append_turn(
    history: List[Dict[str, str]],
    user_message: str,
    assistant_reply: str,
) -> None:
    """Append a user/assistant turn to the history list in-place."""
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_reply})


async def _call_chat_api(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """
    Call an OpenAI-compatible chat completions endpoint.

    Returns the assistant reply text, or None on failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 300,
                    "temperature": 0.5,
                },
                timeout=8.0,
            )

        if response.status_code != 200:
            logger.warning(
                "Chat API returned %d: %s",
                response.status_code,
                response.text[:200],
            )
            return None

        data = response.json()
        _record_request()
        choices = data.get("choices", [])
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "").strip()
        return content or None

    except httpx.TimeoutException:
        logger.warning("Chat API timed out (>8s)")
        return None
    except Exception as e:
        logger.error("Chat API error: %s", e)
        return None


def _fallback_reply(message: str) -> str:
    """Static fallback when AI is disabled."""
    msg_lower = message.lower()
    if any(w in msg_lower for w in ["flood", "water", "rain", "risk"]):
        return (
            "FloodBot is currently offline. "
            "Please check the map tab for live flood hotspot conditions in your city."
        )
    return (
        "FloodBot is currently offline. "
        "You can still use the map, reports, and alerts features in the app."
    )
