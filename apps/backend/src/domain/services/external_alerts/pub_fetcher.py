"""
PUB Flood Alerts Fetcher - Fetches real-time flood alerts from Singapore's PUB (Public Utilities Board).

PUB is Singapore's national water agency. Their flood alert API provides real-time
notifications when flooding is observed, with geocoded locations and severity levels.

API: https://api-open.data.gov.sg/v2/real-time/api/weather/flood-alerts
Auth: Optional API key for higher rate limits (header: x-api-key)
License: Singapore Open Data Licence

Each alert record contains:
- severity: Extreme / Severe / Moderate / Minor
- area.circle: [latitude, longitude, radius_km] for geolocation
- area.areaDesc: Street-level location description
- msgType: "Alert" (new) or "Cancel" (resolves earlier alert)
- description + instruction: Human-readable flood details

This fetcher only activates for city="singapore".
"""

import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

from .base_fetcher import BaseFetcher, ExternalAlertCreate
from src.core.config import settings

logger = logging.getLogger(__name__)

PUB_FLOOD_ALERTS_URL = "https://api-open.data.gov.sg/v2/real-time/api/weather/flood-alerts"

# Alerts older than this are ignored
MAX_ALERT_AGE_HOURS = 24


class PUBFetcher(BaseFetcher):
    """
    Fetches real-time flood alerts from Singapore's PUB.

    Only active for city="singapore". Returns geocoded alerts with
    severity mapping: Extreme->severe, Severe->high, Moderate->moderate, Minor->low.
    """

    # PUB severity -> FloodSafe severity
    SEVERITY_MAP = {
        "extreme": "severe",
        "severe": "high",
        "moderate": "moderate",
        "minor": "low",
    }

    def get_source_name(self) -> str:
        return "pub"

    def is_enabled(self) -> bool:
        # PUB API is public — no API key required (key only for higher rate limits)
        return True

    async def fetch(self, city: str) -> list[ExternalAlertCreate]:
        """
        Fetch flood alerts from PUB for Singapore.

        Args:
            city: City identifier — only processes "singapore"

        Returns:
            List of ExternalAlertCreate objects from active PUB alerts
        """
        if city.lower() != "singapore":
            return []

        self.log_fetch_start(city)

        try:
            alerts = await self._fetch_pub_alerts()
            self.log_fetch_complete(city, len(alerts))
            return alerts
        except Exception as e:
            self.log_fetch_error(city, e)
            return []

    async def _fetch_pub_alerts(self) -> list[ExternalAlertCreate]:
        """Fetch and parse PUB flood alert API response."""
        headers = {"Accept": "application/json"}

        # Add API key if configured (for higher rate limits)
        if settings.PUB_API_KEY:
            headers["x-api-key"] = settings.PUB_API_KEY

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    PUB_FLOOD_ALERTS_URL,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"[PUB] API returned status {resp.status}")
                        return []

                    data = await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"[PUB] HTTP request failed: {e}")
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> list[ExternalAlertCreate]:
        """
        Parse PUB API response into ExternalAlertCreate objects.

        Response structure:
        {
            "code": 0,
            "data": {
                "records": {
                    "datetime": [...],
                    "readings": [...]
                }
            }
        }

        Each reading contains alert records with area.circle for geolocation.
        """
        alerts = []

        try:
            records = data.get("data", {}).get("records", {})
            readings = records.get("readings", [])

            if not readings:
                logger.info("[PUB] No active flood alerts (readings array empty)")
                return []

            for reading in readings:
                parsed = self._parse_reading(reading)
                if parsed:
                    alerts.append(parsed)

        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"[PUB] Failed to parse response: {e}")

        return alerts

    def _parse_reading(self, reading: dict) -> Optional[ExternalAlertCreate]:
        """Parse a single alert reading into ExternalAlertCreate."""
        try:
            msg_type = reading.get("msgType", "")

            # Skip cancellation messages — they resolve earlier alerts
            if msg_type == "Cancel":
                logger.debug(f"[PUB] Skipping cancel message: {reading.get('identifier')}")
                return None

            # Check alert age
            datetime_str = reading.get("datetime", "")
            if datetime_str:
                try:
                    alert_time = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                    age = datetime.now(timezone.utc) - alert_time
                    if age > timedelta(hours=MAX_ALERT_AGE_HOURS):
                        return None
                except (ValueError, TypeError):
                    pass  # If we can't parse the time, include the alert anyway

            # Extract severity
            raw_severity = reading.get("severity", "")
            severity = self.SEVERITY_MAP.get(raw_severity.lower(), "moderate")

            # Extract location from area.circle [lat, lng, radius_km]
            area = reading.get("area", {})
            area_desc = area.get("areaDesc", "")
            circle = area.get("circle", [])

            lat = None
            lng = None
            if isinstance(circle, list) and len(circle) >= 2:
                try:
                    lat = float(circle[0])
                    lng = float(circle[1])
                except (ValueError, TypeError, IndexError):
                    pass

            # Build title and message
            headline = reading.get("headline", "")
            description = reading.get("description", "")
            instruction = reading.get("instruction", "")

            title = headline or f"PUB Flood Alert: {area_desc}" if area_desc else "PUB Flood Alert"
            message_parts = []
            if description:
                message_parts.append(description)
            if instruction:
                message_parts.append(f"Action: {instruction}")
            if area_desc and area_desc not in (headline or ""):
                message_parts.append(f"Location: {area_desc}")
            message = "\n".join(message_parts) or title

            # Use PUB identifier for dedup, fallback to content hash
            identifier = reading.get("identifier", "")
            source_id = identifier if identifier else self.generate_source_id(
                "pub", datetime_str, area_desc, raw_severity
            )

            # Set expiry: 6 hours from alert time (PUB alerts are ephemeral)
            expires_at = None
            if datetime_str:
                try:
                    alert_time = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                    expires_at = alert_time + timedelta(hours=6)
                except (ValueError, TypeError):
                    expires_at = datetime.now(timezone.utc) + timedelta(hours=6)

            return ExternalAlertCreate(
                source="pub",
                source_id=source_id,
                source_name="PUB Singapore",
                city="singapore",
                title=self.truncate_text(title, 500),
                message=self.truncate_text(self.clean_html(message), 2000),
                severity=severity,
                latitude=lat,
                longitude=lng,
                raw_data=reading,
                expires_at=expires_at,
            )

        except Exception as e:
            logger.error(f"[PUB] Failed to parse reading: {e}")
            return None
