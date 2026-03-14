"""
AI Chat API — Conversational flood assistant, address risk, and alert explanation.

Endpoints:
  POST /api/ai/chat             — multi-turn conversational AI
  GET  /api/ai/address-risk     — geocode address + FHI context + AI narrative
  GET  /api/ai/alert-summary/{alert_id} — plain-language explanation of an external alert
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..api.deps import get_current_user_optional, check_rate_limit
from ..domain.services import ai_chat_service
from ..domain.services.llama_service import (
    _check_rate_limit as _llm_rate_ok,
    _get_api_config,
    _record_request,
    is_llama_enabled,
)
from ..infrastructure.database import get_db
from ..infrastructure.models import ExternalAlert, User

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    city: str = Field(..., description="City key: delhi | bangalore | indore | yogyakarta | singapore")
    conversation_id: Optional[str] = Field(None, description="Continue existing conversation")
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional live context: fhi_score, risk_level, precipitation_mm, active_alerts, location_name",
    )


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    rate_limited: bool


class AddressRiskResponse(BaseModel):
    address: str
    latitude: Optional[float]
    longitude: Optional[float]
    geocoded: bool
    fhi_score: Optional[float]
    risk_level: Optional[str]
    ai_narrative: Optional[str]


class AlertSummaryResponse(BaseModel):
    alert_id: str
    title: str
    source: str
    severity: Optional[str]
    ai_summary: Optional[str]


# ---------------------------------------------------------------------------
# Endpoint: POST /chat
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    data: ChatRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> ChatResponse:
    """
    Multi-turn conversational AI for flood risk assistance.

    Rate-limited to 20 requests per minute per IP.
    Conversation memory is maintained server-side for 30 minutes.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"ai_chat:{client_ip}", max_requests=20, window_seconds=60)

    result = await ai_chat_service.chat(
        message=data.message,
        city=data.city,
        conversation_id=data.conversation_id,
        context=data.context,
    )

    return ChatResponse(
        reply=result["reply"],
        conversation_id=result["conversation_id"],
        rate_limited=result["rate_limited"],
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /address-risk
# ---------------------------------------------------------------------------


@router.get("/address-risk", response_model=AddressRiskResponse)
async def address_risk(
    request: Request,
    address: str = Query(..., min_length=2, max_length=500, description="Address or place name to look up"),
    city: str = Query("delhi", description="City key for context"),
) -> AddressRiskResponse:
    """
    Geocode an address, compute FHI context from the nearest hotspot data,
    and generate an AI plain-language risk narrative for that location.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"ai_address:{client_ip}", max_requests=10, window_seconds=60)

    # Step 1: Geocode via Nominatim (no key needed, low-volume usage acceptable)
    lat, lng, geocoded = await _geocode_address(address, city)

    # Step 2: If geocoded, fetch FHI context from the ML service hotspot data
    fhi_score: Optional[float] = None
    risk_level: Optional[str] = None

    if geocoded and lat is not None and lng is not None:
        fhi_score, risk_level = await _get_fhi_for_point(lat, lng, city)

    # Step 3: Generate AI narrative
    ai_narrative: Optional[str] = None
    if is_llama_enabled() and _llm_rate_ok():
        ai_narrative = await _generate_address_narrative(
            address=address,
            city=city,
            lat=lat,
            lng=lng,
            fhi_score=fhi_score,
            risk_level=risk_level,
        )

    return AddressRiskResponse(
        address=address,
        latitude=lat,
        longitude=lng,
        geocoded=geocoded,
        fhi_score=fhi_score,
        risk_level=risk_level,
        ai_narrative=ai_narrative,
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /alert-summary/{alert_id}
# ---------------------------------------------------------------------------


@router.get("/alert-summary/{alert_id}", response_model=AlertSummaryResponse)
async def alert_summary(
    alert_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> AlertSummaryResponse:
    """
    Return a plain-language AI explanation of an external flood alert.

    Looks up the alert from the external_alerts table and generates
    a concise, jargon-free summary suitable for non-expert users.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"ai_alert:{client_ip}", max_requests=15, window_seconds=60)

    alert = db.query(ExternalAlert).filter(ExternalAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    ai_summary: Optional[str] = None
    if is_llama_enabled() and _llm_rate_ok():
        ai_summary = await _generate_alert_summary(alert)

    return AlertSummaryResponse(
        alert_id=str(alert.id),
        title=alert.title,
        source=alert.source_name or alert.source,
        severity=alert.severity,
        ai_summary=ai_summary,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _geocode_address(
    address: str, city: str
) -> tuple[Optional[float], Optional[float], bool]:
    """
    Geocode an address string using Nominatim.

    Returns (latitude, longitude, geocoded_bool).
    Falls back gracefully — returns (None, None, False) on failure.
    """
    city_country = {
        "delhi": "India",
        "bangalore": "India",
        "indore": "India",
        "yogyakarta": "Indonesia",
        "singapore": "Singapore",
    }.get(city.lower(), "")

    query = f"{address}, {city_country}".strip(", ")

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "FloodSafe/1.0 flood-risk-lookup"}
        ) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                timeout=5.0,
            )

        if resp.status_code == 200:
            results = resp.json()
            if results:
                lat = float(results[0]["lat"])
                lng = float(results[0]["lon"])
                return lat, lng, True

    except Exception as e:
        logger.warning("Geocoding failed for '%s': %s", address, e)

    return None, None, False


async def _get_fhi_for_point(
    lat: float, lng: float, city: str
) -> tuple[Optional[float], Optional[str]]:
    """
    Fetch FHI score and risk level for the nearest hotspot to the given point.

    Calls the ML service hotspot endpoint; returns (None, None) gracefully on failure.
    """
    from ..core.config import settings

    if not getattr(settings, "ML_SERVICE_URL", ""):
        return None, None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{settings.ML_SERVICE_URL}/api/v1/hotspots/all",
                params={"include_rainfall": "true", "city": city.lower()},
            )

        if resp.status_code != 200:
            return None, None

        features = resp.json().get("features", [])
        if not features:
            return None, None

        # Find the nearest hotspot
        best_fhi: Optional[float] = None
        best_level: Optional[str] = None
        best_dist = float("inf")

        for feat in features:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            f_lng, f_lat = coords[0], coords[1]
            dist = (f_lat - lat) ** 2 + (f_lng - lng) ** 2
            if dist < best_dist:
                best_dist = dist
                props = feat.get("properties", {})
                best_fhi = props.get("fhi_score")
                best_level = props.get("fhi_level") or props.get("risk_level")

        return best_fhi, best_level

    except Exception as e:
        logger.warning("FHI point lookup failed: %s", e)
        return None, None


async def _generate_address_narrative(
    address: str,
    city: str,
    lat: Optional[float],
    lng: Optional[float],
    fhi_score: Optional[float],
    risk_level: Optional[str],
) -> Optional[str]:
    """Generate a brief AI risk narrative for a geocoded address."""
    lines = [f"Location: {address}, {city.title()}"]
    if fhi_score is not None:
        lines.append(f"Flood Hazard Index: {fhi_score:.2f}/1.00")
    if risk_level:
        lines.append(f"Risk Level: {risk_level.upper()}")
    if lat is not None:
        lines.append(f"Coordinates: {lat:.4f}, {lng:.4f}")
    if not fhi_score and not risk_level:
        lines.append("Live flood data not currently available for this location.")

    user_message = "\n".join(lines)
    system = (
        "You are a practical urban flood advisor for FloodSafe. "
        "Write 2 sentences explaining current flood risk at this location. "
        "Be concise and practical. Never use alarmist language."
    )

    base_url, api_key, model = _get_api_config()
    return await _simple_llm_call(base_url, api_key, model, system, user_message)


async def _generate_alert_summary(alert: ExternalAlert) -> Optional[str]:
    """Generate a plain-language explanation of an external flood alert."""
    lines = [
        f"Alert from: {alert.source_name or alert.source}",
        f"Title: {alert.title}",
        f"Severity: {alert.severity or 'unspecified'}",
        f"Details: {alert.message[:500]}",
    ]
    user_message = "\n".join(lines)
    system = (
        "You are a practical urban flood advisor for FloodSafe. "
        "In 2-3 sentences, explain what this official alert means for everyday urban commuters. "
        "Translate technical language into plain advice. Never be alarmist."
    )

    base_url, api_key, model = _get_api_config()
    return await _simple_llm_call(base_url, api_key, model, system, user_message)


async def _simple_llm_call(
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user_message: str,
) -> Optional[str]:
    """Single-turn LLM call, returns text or None on failure."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
                timeout=6.0,
            )

        if resp.status_code != 200:
            logger.warning("LLM single call returned %d", resp.status_code)
            return None

        data = resp.json()
        _record_request()
        choices = data.get("choices", [])
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "").strip()
        return content or None

    except httpx.TimeoutException:
        logger.warning("LLM single call timed out")
        return None
    except Exception as e:
        logger.error("LLM single call error: %s", e)
        return None
