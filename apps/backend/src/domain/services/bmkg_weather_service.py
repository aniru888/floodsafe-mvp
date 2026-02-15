"""
BMKG Weather Service for Yogyakarta.

Fetches weather forecast data from Indonesia's BMKG (Badan Meteorologi, Klimatologi, dan Geofisika).
Provides 3-hourly forecasts for 3 days with flash flood risk detection.

API: https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=34.71.01.1001
Auth: None required (public API, 60 req/min rate limit)
License: Must credit BMKG as data source

Coverage: Yogyakarta city district-level forecasts (adm4 codes).
Update frequency: Twice daily.
Forecast entries: 8 per day (every 3 hours) for 3 days.

Usage:
    service = get_bmkg_weather_service()
    conditions = await service.get_current_conditions(lat, lng)
    forecast = await service.get_forecast()
"""

import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

from src.domain.services.nea_weather_service import haversine_distance

logger = logging.getLogger(__name__)

# BMKG API base URL for weather forecasts
BMKG_FORECAST_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

# Yogyakarta city adm4 codes for district-level coverage
# Each adm4 code covers a kelurahan (village/ward) in Kota Yogyakarta
YOGYAKARTA_ADM4_CODES = [
    {"code": "34.71.01.1001", "name": "Tegalrejo", "lat": -7.7736, "lng": 110.3572},
    {"code": "34.71.02.1004", "name": "Gedongtengen", "lat": -7.7893, "lng": 110.3592},
    {"code": "34.71.03.1002", "name": "Gondokusuman", "lat": -7.7806, "lng": 110.3838},
    {"code": "34.71.04.1003", "name": "Kotagede", "lat": -7.8122, "lng": 110.3968},
    {"code": "34.71.05.1001", "name": "Kraton", "lat": -7.8052, "lng": 110.3567},
]

# Cache TTL: 30 min (BMKG updates twice daily, 30 min is conservative)
CACHE_TTL_SECONDS = 1800

# Weather conditions that indicate flash flood risk
BMKG_FLOOD_CONDITIONS = {
    "Heavy Rain", "Thunderstorm",
    "Hujan Lebat", "Hujan Petir",
    "Heavy Thundery Showers",
}


@dataclass
class BMKGCurrentConditions:
    """Current weather conditions from nearest BMKG forecast entry."""
    temperature_c: float
    humidity_pct: float
    weather_desc: str          # English condition text
    weather_desc_id: str       # Indonesian condition text
    wind_speed_kmh: float
    cloud_cover_pct: int
    location_name: str         # District/village name
    timestamp: str


@dataclass
class BMKGForecastEntry:
    """A single 3-hourly forecast entry from BMKG."""
    datetime_local: str
    datetime_utc: str
    temperature_c: float
    humidity_pct: float
    weather_desc: str          # English
    weather_desc_id: str       # Indonesian
    wind_speed_kmh: float
    cloud_cover_pct: int
    flash_flood_risk: bool     # True if heavy rain / thunderstorm


@dataclass
class BMKGForecast:
    """3-day BMKG forecast with flash flood risk flags."""
    location_name: str
    province: str
    lat: float
    lng: float
    entries: List[BMKGForecastEntry]
    high_risk_entries: List[BMKGForecastEntry]  # Filtered to risky entries only


class BMKGWeatherService:
    """
    Fetches weather forecast data from BMKG Indonesia for Yogyakarta.

    Finds the nearest district-level forecast to a given coordinate
    and returns current conditions or multi-day forecast with flash flood risk flags.
    """

    def __init__(self, timeout_seconds: float = 15.0):
        self._timeout = timeout_seconds
        self._cache: Dict[str, Tuple[dict, float]] = {}  # key -> (data, timestamp)

    async def get_current_conditions(
        self, lat: float, lng: float
    ) -> Optional[BMKGCurrentConditions]:
        """
        Get current weather conditions from nearest BMKG forecast point.

        Uses the nearest 3-hour forecast entry to the current time as
        "current conditions" (BMKG doesn't have real-time observations API).

        Args:
            lat: Latitude (should be within Yogyakarta bounds)
            lng: Longitude

        Returns:
            BMKGCurrentConditions or None if unavailable
        """
        try:
            # Find nearest district
            nearest = self._find_nearest_district(lat, lng)
            data = await self._fetch_bmkg_data(
                nearest["code"], f"bmkg_forecast_{nearest['code']}"
            )
            if not data:
                return None

            entries = self._parse_forecast_entries(data)
            if not entries:
                return None

            # Find the entry closest to current time
            now = datetime.now(timezone.utc)
            closest = min(entries, key=lambda e: abs(
                datetime.fromisoformat(e.datetime_utc.replace(" ", "T") + "Z" if "Z" not in e.datetime_utc and "+" not in e.datetime_utc else e.datetime_utc.replace(" ", "T")).timestamp()
                - now.timestamp()
            ))

            location_name = self._get_location_name(data)

            return BMKGCurrentConditions(
                temperature_c=closest.temperature_c,
                humidity_pct=closest.humidity_pct,
                weather_desc=closest.weather_desc,
                weather_desc_id=closest.weather_desc_id,
                wind_speed_kmh=closest.wind_speed_kmh,
                cloud_cover_pct=closest.cloud_cover_pct,
                location_name=location_name,
                timestamp=closest.datetime_utc,
            )

        except Exception as e:
            logger.error(f"[BMKG] Failed to get current conditions: {e}")
            return None

    async def get_forecast(self) -> Optional[BMKGForecast]:
        """
        Get 3-day BMKG forecast for Yogyakarta city center.

        Returns all forecast entries with flash flood risk flags for entries
        that predict heavy rain or thunderstorms.

        Returns:
            BMKGForecast or None if unavailable
        """
        try:
            # Use central Yogyakarta district
            central = YOGYAKARTA_ADM4_CODES[0]
            data = await self._fetch_bmkg_data(
                central["code"], f"bmkg_forecast_{central['code']}"
            )
            if not data:
                return None

            entries = self._parse_forecast_entries(data)
            if not entries:
                return None

            location_name = self._get_location_name(data)
            province = self._get_province(data)
            lat, lng = self._get_coordinates(data)

            high_risk = [e for e in entries if e.flash_flood_risk]

            return BMKGForecast(
                location_name=location_name,
                province=province,
                lat=lat,
                lng=lng,
                entries=entries,
                high_risk_entries=high_risk,
            )

        except Exception as e:
            logger.error(f"[BMKG] Failed to get forecast: {e}")
            return None

    def _find_nearest_district(self, lat: float, lng: float) -> dict:
        """Find nearest BMKG district to given coordinates."""
        nearest = YOGYAKARTA_ADM4_CODES[0]
        min_dist = float("inf")
        for district in YOGYAKARTA_ADM4_CODES:
            dist = haversine_distance(lat, lng, district["lat"], district["lng"])
            if dist < min_dist:
                min_dist = dist
                nearest = district
        return nearest

    def _parse_forecast_entries(self, data: dict) -> List[BMKGForecastEntry]:
        """Parse all forecast entries from BMKG response."""
        entries: List[BMKGForecastEntry] = []
        try:
            data_list = data.get("data", [])
            if not data_list:
                return entries

            # cuaca is a nested array: [ [day1_entries], [day2_entries], ... ]
            cuaca = data_list[0].get("cuaca", [])
            for day_entries in cuaca:
                for entry in day_entries:
                    weather_en = entry.get("weather_desc_en", "")
                    weather_id = entry.get("weather_desc", "")
                    # Wind speed from BMKG is in m/s → convert to km/h
                    ws_ms = entry.get("ws", 0) or 0
                    ws_kmh = round(ws_ms * 3.6, 1)

                    is_risky = weather_en in BMKG_FLOOD_CONDITIONS or weather_id in BMKG_FLOOD_CONDITIONS

                    entries.append(BMKGForecastEntry(
                        datetime_local=entry.get("local_datetime", ""),
                        datetime_utc=entry.get("utc_datetime", ""),
                        temperature_c=float(entry.get("t", 0) or 0),
                        humidity_pct=float(entry.get("hu", 0) or 0),
                        weather_desc=weather_en,
                        weather_desc_id=weather_id,
                        wind_speed_kmh=ws_kmh,
                        cloud_cover_pct=int(entry.get("tcc", 0) or 0),
                        flash_flood_risk=is_risky,
                    ))
        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"[BMKG] Failed to parse forecast entries: {e}")

        return entries

    def _get_location_name(self, data: dict) -> str:
        """Extract location name from BMKG response."""
        try:
            lokasi = data.get("lokasi", {})
            kecamatan = lokasi.get("kecamatan", "")
            desa = lokasi.get("desa", "")
            if kecamatan and desa:
                return f"{desa}, {kecamatan}"
            return kecamatan or desa or "Yogyakarta"
        except Exception:
            return "Yogyakarta"

    def _get_province(self, data: dict) -> str:
        """Extract province from BMKG response."""
        try:
            return data.get("lokasi", {}).get("provinsi", "Daerah Istimewa Yogyakarta")
        except Exception:
            return "Daerah Istimewa Yogyakarta"

    def _get_coordinates(self, data: dict) -> Tuple[float, float]:
        """Extract lat/lng from BMKG response."""
        try:
            lokasi = data.get("lokasi", {})
            return float(lokasi.get("lat", -7.797)), float(lokasi.get("lon", 110.361))
        except Exception:
            return -7.797, 110.361

    async def _fetch_bmkg_data(
        self, adm4_code: str, cache_key: str
    ) -> Optional[dict]:
        """
        Fetch BMKG forecast data with caching.

        Args:
            adm4_code: BMKG administrative code (e.g. "34.71.01.1001")
            cache_key: Cache key string

        Returns:
            Parsed JSON response or None if unavailable
        """
        now = datetime.now(timezone.utc).timestamp()

        # Check cache
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_data

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    BMKG_FORECAST_URL,
                    params={"adm4": adm4_code},
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            self._cache[cache_key] = (data, now)
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"[BMKG] API returned HTTP {e.response.status_code} for {adm4_code}")
            return None
        except httpx.TimeoutException:
            logger.error(f"[BMKG] API request timed out for {adm4_code}")
            return None
        except Exception as e:
            logger.error(f"[BMKG] Failed to fetch data for {adm4_code}: {e}")
            return None

    def clear_cache(self):
        """Clear the forecast data cache."""
        self._cache.clear()


# Singleton
_bmkg_service: Optional[BMKGWeatherService] = None


def get_bmkg_weather_service() -> BMKGWeatherService:
    """Get or create the singleton BMKG weather service."""
    global _bmkg_service
    if _bmkg_service is None:
        _bmkg_service = BMKGWeatherService()
    return _bmkg_service
