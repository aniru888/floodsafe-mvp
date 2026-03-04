"""
Meta Llama API Service — AI-Generated Flood Risk Summaries.

Generates natural language risk narratives from structured FHI data,
combining multiple data sources (rainfall, elevation, hotspot status,
nearby reports) into actionable prose in Hindi or English.

Uses Meta's Llama API (OpenAI SDK compatible) with Groq as fallback.
Both are free and add zero RAM to the backend.
"""
import logging
import time
from typing import Optional

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)

# Response cache: {cache_key: (timestamp, summary)}
_summary_cache: dict[str, tuple[float, str]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour — FHI data changes hourly

# Rate limiting — Groq free tier: 120 req/min, 2000 req/day, 10K tokens/min
# Soft limits with buffer to avoid hitting hard walls
_request_timestamps: list[float] = []
RATE_LIMIT_PER_MINUTE = 100  # buffer below 120 hard limit
RATE_LIMIT_PER_DAY = 1800  # buffer below 2000 hard limit
RATE_LIMIT_WARN_THRESHOLD = 0.8  # warn at 80% usage


def is_llama_enabled() -> bool:
    """Check if Llama API is configured and enabled."""
    if not settings.LLAMA_ENABLED:
        return False
    return bool(settings.META_LLAMA_API_KEY or settings.LLAMA_FALLBACK_API_KEY)


def _check_rate_limit() -> bool:
    """Check if we're within Groq rate limits. Returns True if allowed."""
    now = time.time()

    # Prune timestamps older than 24 hours
    _request_timestamps[:] = [t for t in _request_timestamps if t > now - 86400]

    # Check daily limit
    daily_count = len(_request_timestamps)
    if daily_count >= RATE_LIMIT_PER_DAY:
        logger.warning(
            "Llama/Groq daily rate limit reached (%d/%d) — returning template-only",
            daily_count, RATE_LIMIT_PER_DAY,
        )
        return False

    # Check per-minute limit
    minute_count = sum(1 for t in _request_timestamps if t > now - 60)
    if minute_count >= RATE_LIMIT_PER_MINUTE:
        logger.warning(
            "Llama/Groq per-minute rate limit reached (%d/%d)",
            minute_count, RATE_LIMIT_PER_MINUTE,
        )
        return False

    # Warn at 80% daily usage
    if daily_count >= int(RATE_LIMIT_PER_DAY * RATE_LIMIT_WARN_THRESHOLD):
        logger.warning(
            "Llama/Groq daily usage at %d/%d (%.0f%%)",
            daily_count, RATE_LIMIT_PER_DAY,
            (daily_count / RATE_LIMIT_PER_DAY) * 100,
        )

    return True


def _record_request() -> None:
    """Record a successful API request timestamp for rate tracking."""
    _request_timestamps.append(time.time())


def _get_api_config() -> tuple[str, str, str]:
    """
    Get API URL, key, and model based on available configuration.

    Returns:
        Tuple of (base_url, api_key, model_name)
    """
    if settings.META_LLAMA_API_KEY:
        return (
            settings.LLAMA_API_URL,
            settings.META_LLAMA_API_KEY,
            settings.LLAMA_MODEL,
        )
    # Fallback to Groq
    return (
        settings.LLAMA_FALLBACK_URL,
        settings.LLAMA_FALLBACK_API_KEY,
        settings.LLAMA_FALLBACK_MODEL,
    )


def _build_cache_key(lat: float, lng: float, language: str) -> str:
    """Build cache key from location and language."""
    return f"{lat:.4f},{lng:.4f},{language}"


def _get_cached_summary(cache_key: str) -> Optional[str]:
    """Get cached summary if still valid."""
    if cache_key in _summary_cache:
        timestamp, summary = _summary_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            logger.debug(f"Llama cache hit for {cache_key}")
            return summary
        # Expired — remove
        del _summary_cache[cache_key]
    return None


def _cache_summary(cache_key: str, summary: str) -> None:
    """Cache a summary with current timestamp."""
    _summary_cache[cache_key] = (time.time(), summary)

    # Evict old entries if cache grows too large (>500 entries)
    if len(_summary_cache) > 500:
        cutoff = time.time() - CACHE_TTL_SECONDS
        expired = [k for k, (t, _) in list(_summary_cache.items()) if t < cutoff]
        for k in expired:
            del _summary_cache[k]


SYSTEM_PROMPT = """You are a practical urban advisor for FloodSafe, a nonprofit flood monitoring app serving Delhi, Bangalore, Indore (India), Yogyakarta (Indonesia), and Singapore.

Write a 2-3 sentence summary of current conditions at the user's location. Base your response ONLY on the data provided.

TONE RULES:
- These are URBAN cities. Flooding = waterlogged roads, slow drains, traffic delays. Not river floods or natural disasters.
- NEVER use: "evacuate", "seek shelter", "life-threatening", "catastrophic", "devastating", "immediate danger", "emergency".
- If rainfall is 0mm and FHI is low, say conditions are clear. Do NOT invent risks that aren't in the data.
- Think like a helpful traffic radio host, not a disaster warning.

SCALE YOUR RESPONSE TO THE DATA:
- Low risk / dry: "No flooding concerns. Conditions are clear."
- Moderate: "Some waterlogging possible. Allow extra travel time."
- High: "Waterlogging likely on low-lying roads. Avoid underpasses."
- Extreme: "Major waterlogging. Roads may be impassable. Consider delaying travel or using alternate routes."

FORMAT: Plain text only. End with one practical tip. Use "monsoon" for Indian cities, "musim hujan" for Indonesian, "rainfall" for Singapore."""

SYSTEM_PROMPT_HI = """Tum FloodSafe ke practical urban advisor ho — Delhi, Bangalore, Indore (India), Yogyakarta (Indonesia), aur Singapore ke liye nonprofit flood monitoring app.

User ki location ke baare mein 2-3 sentence ka summary likho. Sirf diye gaye data ke basis pe bolo.

TONE RULES:
- Ye URBAN cities hain. Yahan flooding matlab waterlogged roads, slow drains, traffic delays. River floods ya natural disasters nahi.
- KABHI mat use karo: "evacuate", "shelter lo", "jaan ka khatra", "tabahi", "emergency".
- Agar rainfall 0mm hai aur FHI low hai, to bolo conditions clear hain. Data mein jo nahi hai wo mat banao.
- Ek helpful traffic radio host ki tarah bolo, emergency broadcast ki tarah nahi.

RISK LEVELS:
- Low / dry: "Koi flooding ka khatra nahi. Conditions clear hain."
- Moderate: "Thodi waterlogging ho sakti hai. Travel mein extra time rakho."
- High: "Low-lying roads pe waterlogging hone ki sambhavna. Underpasses avoid karo."
- Extreme: "Major waterlogging. Roads impassable ho sakti hain. Travel delay karo ya alternate route lo."

FORMAT: Sirf plain text. Ek practical tip ke saath khatam karo. Hindi mein jawab do, technical terms English mein rakh sakte ho."""


async def generate_risk_summary(
    latitude: float,
    longitude: float,
    location_name: str,
    risk_level: str,
    fhi_score: float,
    precipitation_mm: float = 0.0,
    elevation: Optional[float] = None,
    is_hotspot: bool = False,
    nearby_reports: int = 0,
    active_alerts: int = 0,
    language: str = "en",
) -> Optional[str]:
    """
    Generate an AI risk summary using Meta Llama API.

    Combines structured flood data into a natural language narrative.
    Returns None if Llama is disabled, unavailable, or times out.

    Args:
        latitude: GPS latitude
        longitude: GPS longitude
        location_name: Human-readable location name
        risk_level: "low", "moderate", "high", or "extreme"
        fhi_score: Flood Hazard Index (0.0 to 1.0)
        precipitation_mm: Current/recent rainfall in mm
        elevation: Elevation in meters (if available)
        is_hotspot: Whether this is a known flood hotspot
        nearby_reports: Number of recent citizen flood reports nearby
        active_alerts: Number of active official alerts
        language: "en" or "hi"

    Returns:
        Natural language risk summary string, or None
    """
    if not is_llama_enabled():
        return None

    # Check cache first
    cache_key = _build_cache_key(latitude, longitude, language)
    cached = _get_cached_summary(cache_key)
    if cached:
        return cached

    # Check rate limits before making API call
    if not _check_rate_limit():
        return None

    # Build the data context for the LLM
    context_parts = [
        f"Location: {location_name}",
        f"Risk Level: {risk_level.upper()}",
        f"Flood Hazard Index: {fhi_score:.2f}/1.00",
    ]
    if precipitation_mm > 0:
        context_parts.append(f"Current Rainfall: {precipitation_mm:.1f}mm in last 24h")
    if risk_level.lower() == "unknown":
        context_parts[1] = "Risk Level: Weather data temporarily unavailable — describe general area conditions only"
    if elevation is not None:
        context_parts.append(f"Elevation: {elevation:.0f}m")
    if is_hotspot:
        context_parts.append("Known flood hotspot: YES (history of waterlogging)")
    if nearby_reports > 0:
        context_parts.append(f"Recent citizen flood reports nearby: {nearby_reports}")
    if active_alerts > 0:
        context_parts.append(f"Active official flood alerts: {active_alerts}")

    user_message = "\n".join(context_parts)
    system_prompt = SYSTEM_PROMPT_HI if language == "hi" else SYSTEM_PROMPT

    # Call the API
    base_url, api_key, model = _get_api_config()

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
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
                timeout=5.0,
            )

            if response.status_code != 200:
                logger.warning(
                    f"Llama API returned {response.status_code}: "
                    f"{response.text[:200]}"
                )
                # Try fallback if primary failed and fallback is available
                if (
                    base_url == settings.LLAMA_API_URL
                    and settings.LLAMA_FALLBACK_API_KEY
                ):
                    return await _try_fallback(user_message, system_prompt, cache_key)
                return None

            data = response.json()
            _record_request()

    except httpx.TimeoutException:
        logger.warning("Llama API timeout (>5s)")
        # Try fallback
        if base_url == settings.LLAMA_API_URL and settings.LLAMA_FALLBACK_API_KEY:
            return await _try_fallback(user_message, system_prompt, cache_key)
        return None
    except Exception as e:
        logger.error(f"Llama API error: {e}")
        return None

    # Parse response
    summary = _extract_summary(data)
    if summary:
        _cache_summary(cache_key, summary)

    return summary


async def _try_fallback(
    user_message: str, system_prompt: str, cache_key: str
) -> Optional[str]:
    """Try the Groq fallback API."""
    if not _check_rate_limit():
        return None
    logger.info("Trying Groq fallback for Llama summary")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.LLAMA_FALLBACK_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLAMA_FALLBACK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLAMA_FALLBACK_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
                timeout=5.0,
            )

            if response.status_code != 200:
                logger.warning(f"Groq fallback returned {response.status_code}")
                return None

            data = response.json()
            _record_request()
            summary = _extract_summary(data)
            if summary:
                _cache_summary(cache_key, summary)
            return summary

    except Exception as e:
        logger.error(f"Groq fallback error: {e}")
        return None


def _extract_summary(data: dict) -> Optional[str]:
    """Extract summary text from OpenAI-compatible chat completion response."""
    try:
        choices = data.get("choices", [])
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        # Clean up: remove any leading/trailing whitespace and quotes
        summary = content.strip().strip('"').strip()
        if not summary:
            return None
        return summary
    except (KeyError, IndexError) as e:
        logger.error(f"Failed to parse Llama response: {e}")
        return None
