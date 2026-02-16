"""
OpenWeatherMap Weather Service for Yogyakarta.

Uses One Call 3.0 API for minutely precipitation (60 data points for next hour)
and hourly forecasts (48h). Provides better temporal resolution than Open-Meteo
for tropical cities with bursty rainfall.

API: https://api.openweathermap.org/data/3.0/onecall
Auth: API key required (free tier: 1,000 calls/day)
Docs: https://openweathermap.org/api/one-call-3

Usage in FHI calculator:
    service = get_owm_weather_service()
    result = await service.get_weather(lat, lng)
    # Returns hourly precip + minutely data for intensity calculation
"""

import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

from src.core.config import settings

logger = logging.getLogger(__name__)

OWM_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"

# Cache TTL in seconds (10 minutes — matches OWM update frequency)
CACHE_TTL_SECONDS = 600


@dataclass
class OWMWeatherResult:
    """Weather data from OpenWeatherMap One Call 3.0."""
    hourly_precip: List[float]      # Hourly precipitation (mm) for up to 48 hours
    minutely_precip: List[float]    # Minutely precipitation (mm) for next 60 minutes
    hourly_max_intensity: float     # Max hourly precipitation (mm/h) in next 24h
    minutely_max_intensity: float   # Max minutely precipitation extrapolated to mm/h
    temperature_c: Optional[float]  # Current temperature
    humidity_pct: Optional[float]   # Current humidity
    pressure_hpa: Optional[float]   # Current pressure
    alerts: List[dict]              # Government weather alerts (if any)
    timestamp: str
    data_source: str = "owm"


class OWMWeatherService:
    """
    Fetches weather data from OpenWeatherMap One Call 3.0 API.

    Key advantage over Open-Meteo: minutely precipitation data for next hour,
    which captures bursty tropical rainfall that hourly resolution misses.
    """

    def __init__(self, timeout_seconds: float = 15.0):
        self._timeout = timeout_seconds
        self._cache: Dict[str, Tuple[OWMWeatherResult, float]] = {}

    async def get_weather(
        self, lat: float, lng: float
    ) -> Optional[OWMWeatherResult]:
        """
        Get weather data from OWM One Call 3.0.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            OWMWeatherResult with hourly + minutely precipitation, or None if unavailable
        """
        if not settings.OPENWEATHERMAP_API_KEY:
            logger.debug("[OWM] No API key configured, skipping")
            return None

        # Check cache (keyed by 4-decimal lat/lng)
        cache_key = f"owm_{lat:.4f}_{lng:.4f}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            params = {
                "lat": lat,
                "lon": lng,
                "appid": settings.OPENWEATHERMAP_API_KEY,
                "units": "metric",
                "exclude": "daily",  # We don't need daily (Open-Meteo handles 72h)
            }

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(OWM_ONECALL_URL, params=params)
                response.raise_for_status()
                data = response.json()

            result = self._parse_response(data)
            if result:
                self._save_to_cache(cache_key, result)

            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("[OWM] Invalid API key (401 Unauthorized)")
            elif e.response.status_code == 429:
                logger.warning("[OWM] Rate limit exceeded (429)")
            else:
                logger.error(f"[OWM] API returned HTTP {e.response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error("[OWM] API request timed out")
            return None
        except Exception as e:
            logger.error(f"[OWM] Failed to fetch weather: {e}")
            return None

    def _parse_response(self, data: dict) -> Optional[OWMWeatherResult]:
        """Parse OWM One Call 3.0 response into OWMWeatherResult."""
        try:
            # Current conditions
            current = data.get("current", {})
            temperature_c = current.get("temp")
            humidity_pct = current.get("humidity")
            pressure_hpa = current.get("pressure")

            # Hourly precipitation (48 data points)
            hourly_data = data.get("hourly", [])
            hourly_precip = []
            for h in hourly_data:
                rain = h.get("rain", {}).get("1h", 0.0)
                hourly_precip.append(rain)

            # Minutely precipitation (60 data points for next hour)
            minutely_data = data.get("minutely", [])
            minutely_precip = []
            for m in minutely_data:
                minutely_precip.append(m.get("precipitation", 0.0))

            # Calculate max intensities
            hourly_max = max(hourly_precip[:24]) if hourly_precip else 0.0
            # Minutely is in mm/min → multiply by 60 for mm/h equivalent
            minutely_max_per_min = max(minutely_precip) if minutely_precip else 0.0
            minutely_max_hourly = minutely_max_per_min * 60.0

            # Government weather alerts
            alerts = data.get("alerts", [])
            parsed_alerts = []
            for alert in alerts:
                parsed_alerts.append({
                    "sender": alert.get("sender_name", ""),
                    "event": alert.get("event", ""),
                    "description": alert.get("description", ""),
                    "start": alert.get("start"),
                    "end": alert.get("end"),
                })

            timestamp = datetime.now(timezone.utc).isoformat()

            result = OWMWeatherResult(
                hourly_precip=hourly_precip,
                minutely_precip=minutely_precip,
                hourly_max_intensity=hourly_max,
                minutely_max_intensity=minutely_max_hourly,
                temperature_c=temperature_c,
                humidity_pct=humidity_pct,
                pressure_hpa=pressure_hpa,
                alerts=parsed_alerts,
                timestamp=timestamp,
            )

            logger.info(
                f"[OWM] Weather fetched: hourly_max={hourly_max:.1f}mm/h, "
                f"minutely_max={minutely_max_hourly:.1f}mm/h (extrapolated), "
                f"alerts={len(parsed_alerts)}"
            )

            return result

        except Exception as e:
            logger.error(f"[OWM] Failed to parse response: {e}")
            return None

    def _get_from_cache(self, cache_key: str) -> Optional[OWMWeatherResult]:
        """Get result from cache if valid."""
        if cache_key not in self._cache:
            return None

        result, cached_at = self._cache[cache_key]
        now = datetime.now(timezone.utc).timestamp()

        if now - cached_at > CACHE_TTL_SECONDS:
            del self._cache[cache_key]
            return None

        return result

    def _save_to_cache(self, cache_key: str, result: OWMWeatherResult) -> None:
        """Save result to cache."""
        now = datetime.now(timezone.utc).timestamp()
        self._cache[cache_key] = (result, now)

    def clear_cache(self):
        """Clear the weather data cache."""
        self._cache.clear()


# Singleton
_owm_service: Optional[OWMWeatherService] = None


def get_owm_weather_service() -> OWMWeatherService:
    """Get or create the singleton OWM weather service."""
    global _owm_service
    if _owm_service is None:
        _owm_service = OWMWeatherService()
    return _owm_service
