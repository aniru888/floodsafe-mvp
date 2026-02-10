"""
WhatsApp Command Handlers

Async handlers for RISK, WARNINGS, MY AREAS, and HELP commands.
Each handler calls internal APIs and formats responses using templates.
"""
import logging
from typing import Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from ....core.config import settings
from ....infrastructure.models import User, WatchArea, Report
from .message_templates import (
    TemplateKey, get_message, get_user_language,
    format_risk_factors, format_alerts_list, format_watch_areas
)
from ..llama_service import generate_risk_summary, is_llama_enabled

logger = logging.getLogger(__name__)


# Internal API base URL (localhost or Docker internal)
def _get_api_base() -> str:
    """Get base URL for internal API calls."""
    # When running in the same process, use localhost
    return "http://localhost:8000/api"


async def geocode_location(
    place_name: str,
    city: str = "delhi"
) -> Optional[Tuple[float, float, str]]:
    """
    Geocode a place name to coordinates.

    Args:
        place_name: Place to search for
        city: City context (default: delhi)

    Returns:
        Tuple of (latitude, longitude, formatted_name) or None if not found
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{_get_api_base()}/search/locations/",
                params={"q": place_name, "city": city, "limit": 1},
                timeout=10.0
            )

            if response.status_code != 200:
                logger.warning(f"Geocode failed: {response.status_code}")
                return None

            results = response.json()
            if not results:
                return None

            first = results[0]
            return (
                first.get("latitude"),
                first.get("longitude"),
                first.get("name", place_name)
            )

    except Exception as e:
        logger.error(f"Geocode error: {e}")
        return None


async def handle_risk_command(
    db: Session,
    user: Optional[User],
    place_name: Optional[str] = None,
    last_location: Optional[Tuple[float, float]] = None
) -> str:
    """
    Handle RISK command - check flood risk at location.

    Args:
        db: Database session
        user: Current user (may be None)
        place_name: Optional place name to geocode
        last_location: Last known location from session (lat, lng)

    Returns:
        Formatted response message
    """
    language = get_user_language(user)

    # Determine coordinates
    latitude, longitude, location_name = None, None, None

    if place_name:
        # Geocode the place name
        result = await geocode_location(place_name)
        if not result:
            return get_message(
                TemplateKey.LOCATION_NOT_FOUND,
                language,
                query=place_name
            )
        latitude, longitude, location_name = result
    elif last_location:
        latitude, longitude = last_location
        location_name = f"Your location ({latitude:.4f}, {longitude:.4f})"
    else:
        return get_message(TemplateKey.RISK_NO_LOCATION, language)

    # Call risk-at-point API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_get_api_base()}/hotspots/risk-at-point",
                params={"lat": latitude, "lng": longitude},
                timeout=15.0
            )

            if response.status_code != 200:
                logger.warning(f"Risk API failed: {response.status_code}")
                # Return a generic low risk response
                return get_message(
                    TemplateKey.RISK_LOW,
                    language,
                    location=location_name
                )

            data = response.json()

    except Exception as e:
        logger.error(f"Risk API error: {e}")
        return get_message(
            TemplateKey.RISK_LOW,
            language,
            location=location_name
        )

    # Parse risk level
    risk_level = data.get("risk_level", "low").lower()
    fhi = data.get("fhi", 0.0)
    is_hotspot = data.get("is_hotspot", False)

    # Build factors
    factors = format_risk_factors(
        elevation=data.get("elevation"),
        rainfall=data.get("precipitation_mm"),
        drainage="Known waterlogging spot" if is_hotspot else "Normal drainage",
        is_hotspot=is_hotspot,
        language=language
    )

    # Select template based on risk level
    if risk_level in ["high", "extreme"] or fhi > 0.6:
        template = TemplateKey.RISK_HIGH
    elif risk_level == "moderate" or fhi > 0.3:
        template = TemplateKey.RISK_MODERATE
    else:
        template = TemplateKey.RISK_LOW

    template_response = get_message(
        template,
        language,
        location=location_name,
        factors=factors
    )

    # Optionally append AI-generated summary from Meta Llama API
    if is_llama_enabled() and latitude and longitude:
        try:
            summary = await generate_risk_summary(
                latitude=latitude,
                longitude=longitude,
                location_name=location_name or "Unknown",
                risk_level=risk_level,
                fhi_score=fhi,
                precipitation_mm=data.get("precipitation_mm", 0.0),
                elevation=data.get("elevation"),
                is_hotspot=is_hotspot,
                language=language,
            )
            if summary:
                template_response += f"\n\n---\nAI Summary: {summary}"
        except Exception as e:
            logger.debug(f"Llama summary generation failed: {e}")

    return template_response


async def handle_warnings_command(
    db: Session,
    user: Optional[User],
    city: str = "Delhi NCR"
) -> str:
    """
    Handle WARNINGS command - get official flood alerts.

    Args:
        db: Database session
        user: Current user (may be None)
        city: City name (default: Delhi NCR)

    Returns:
        Formatted response message
    """
    language = get_user_language(user)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{_get_api_base()}/alerts/unified",
                params={"city": "delhi", "sources": "official", "limit": 5},
                timeout=15.0
            )

            if response.status_code != 200:
                logger.warning(f"Alerts API failed: {response.status_code}")
                return get_message(
                    TemplateKey.WARNINGS_NONE,
                    language,
                    city=city
                )

            data = response.json()

    except Exception as e:
        logger.error(f"Alerts API error: {e}")
        return get_message(
            TemplateKey.WARNINGS_NONE,
            language,
            city=city
        )

    alerts = data.get("alerts", [])

    if not alerts:
        return get_message(
            TemplateKey.WARNINGS_NONE,
            language,
            city=city
        )

    # Format alerts list
    formatted_alerts = format_alerts_list(alerts, language)
    updated = "Just now"  # Could parse from response

    return get_message(
        TemplateKey.WARNINGS_ACTIVE,
        language,
        city=city,
        alerts=formatted_alerts,
        updated=updated
    )


async def handle_my_areas_command(
    db: Session,
    user: Optional[User]
) -> str:
    """
    Handle MY AREAS command - show user's watch areas with risk levels.

    Args:
        db: Database session
        user: Current user (must be linked)

    Returns:
        Formatted response message
    """
    language = get_user_language(user)

    if not user:
        return get_message(TemplateKey.ACCOUNT_NOT_LINKED, language)

    # Fetch watch areas from database directly (same process)
    watch_areas = db.query(WatchArea).filter(
        WatchArea.user_id == user.id
    ).all()

    if not watch_areas:
        return get_message(TemplateKey.MY_AREAS_EMPTY, language)

    # Build areas list with risk info
    areas_data = []
    for wa in watch_areas:
        # Get recent reports near this area
        recent_count = db.query(Report).filter(
            Report.created_at >= "now() - interval '24 hours'"
        ).count()  # Simplified - would need spatial query

        # Determine risk level (would call risk API in production)
        areas_data.append({
            "name": wa.name,
            "label": "",  # Could add "Home", "Work" labels
            "risk_level": "low",  # Would call risk API
            "recent_reports": 0  # Simplified
        })

    # Format areas list
    areas_list = format_watch_areas(areas_data, language)

    return get_message(
        TemplateKey.MY_AREAS,
        language,
        areas_list=areas_list
    )


async def handle_help_command(
    user: Optional[User]
) -> str:
    """
    Handle HELP command - show all available commands.

    Args:
        user: Current user (may be None)

    Returns:
        Formatted help message
    """
    language = get_user_language(user)
    return get_message(TemplateKey.HELP, language)


async def handle_status_command(
    db: Session,
    user: Optional[User],
    phone: str
) -> str:
    """
    Handle STATUS command - show user's account status.

    Args:
        db: Database session
        user: Current user (may be None)
        phone: Phone number

    Returns:
        Formatted status message
    """
    language = get_user_language(user)

    if user:
        email = user.email or "Not set"
        watch_areas_count = db.query(WatchArea).filter(
            WatchArea.user_id == user.id
        ).count()
        reports_count = db.query(Report).filter(
            Report.user_id == user.id
        ).count()

        status_info = f"""Signed in as: {email}
Phone: {phone}
Watch Areas: {watch_areas_count}
Reports Submitted: {reports_count}

You'll receive alerts for flooding near your watch areas."""
    else:
        status_info = f"""Not linked to FloodSafe account.
Phone: {phone}

Your reports will be submitted anonymously.
Reply LINK to connect your account."""

    return get_message(
        TemplateKey.STATUS,
        language,
        status_info=status_info
    )


def get_readable_location(latitude: float, longitude: float) -> str:
    """
    Get a human-readable location description.

    For now, returns coordinates. In production, would reverse geocode.
    """
    # Simple coordinate display
    # TODO: Implement reverse geocoding for better UX
    return f"({latitude:.4f}, {longitude:.4f})"
