"""
NEA Real-time Weather Service for Singapore.

Fetches weather data from Singapore's National Environment Agency (NEA) via data.gov.sg.
Provides 5-minute interval rainfall data — 60x better temporal resolution than Open-Meteo (hourly).

API: https://api-open.data.gov.sg/v2/real-time/api/rainfall
Auth: Optional API key for higher rate limits
License: Singapore Open Data Licence

Station coverage: 61 rain gauges across Singapore with lat/lng coordinates.
Reading type: "TB1 Rainfall 5 Minute Total F" in mm.

Usage in FHI calculator:
    service = NEAWeatherService()
    rainfall = await service.get_nearest_rainfall(lat, lng)
    # Returns rainfall in mm/h equivalent from nearest station
"""

import httpx
import asyncio
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

from src.core.config import settings

logger = logging.getLogger(__name__)

NEA_RAINFALL_URL = "https://api-open.data.gov.sg/v2/real-time/api/rainfall"
NEA_HUMIDITY_URL = "https://api-open.data.gov.sg/v2/real-time/api/relative-humidity"
NEA_TEMPERATURE_URL = "https://api-open.data.gov.sg/v2/real-time/api/air-temperature"
NEA_TWO_HOUR_FORECAST_URL = "https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast"

# Cache TTL in seconds (5 minutes — matches NEA data refresh interval)
CACHE_TTL_SECONDS = 300

# Forecast cache TTL (15 minutes — forecast updates every 30 min)
FORECAST_CACHE_TTL_SECONDS = 900

# Maximum distance (km) to consider a station as "nearby"
MAX_STATION_DISTANCE_KM = 15.0

# Weather conditions that indicate flash flood risk
FLASH_FLOOD_CONDITIONS = {
    "Heavy Thundery Showers",
    "Heavy Thundery Showers with Gusty Winds",
    "Thundery Showers",
    "Heavy Rain",
    "Heavy Showers",
}


@dataclass
class NEAStation:
    """NEA rain gauge station."""
    station_id: str
    name: str
    lat: float
    lng: float


@dataclass
class NEARainfallReading:
    """Rainfall reading from an NEA station."""
    station_id: str
    value_mm: float  # 5-minute rainfall total in mm
    timestamp: str


@dataclass
class NEARainfallResult:
    """Result of NEA rainfall query for a location."""
    station_id: str
    station_name: str
    distance_km: float
    rainfall_5min_mm: float
    rainfall_1h_mm: Optional[float]  # Estimated hourly equivalent
    timestamp: str
    data_source: str  # Always "nea"


@dataclass
class NEACurrentConditions:
    """Current temperature and humidity from nearest NEA stations."""
    temperature_c: Optional[float]
    humidity_pct: Optional[float]
    temp_station_name: Optional[str]
    humidity_station_name: Optional[str]
    timestamp: str


@dataclass
class NEAForecastArea:
    """A single forecast area from NEA 2-hour forecast."""
    name: str
    condition: str
    flash_flood_risk: bool
    lat: float
    lng: float


@dataclass
class NEATwoHourForecast:
    """NEA 2-hour weather forecast result."""
    valid_period_start: str
    valid_period_end: str
    areas: List[NEAForecastArea]
    high_risk_areas: List[str]  # Area names with flash flood risk
    update_timestamp: str


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.

    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth's radius in km
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class NEAWeatherService:
    """
    Fetches real-time rainfall data from NEA Singapore.

    Finds the nearest rain gauge station to a given coordinate and returns
    the latest 5-minute rainfall reading.
    """

    def __init__(self, timeout_seconds: float = 15.0):
        self._timeout = timeout_seconds
        self._cache: Dict[str, Tuple[dict, float]] = {}  # key -> (data, timestamp)

    async def get_nearest_rainfall(
        self, lat: float, lng: float
    ) -> Optional[NEARainfallResult]:
        """
        Get rainfall from the nearest NEA station to the given coordinates.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            NEARainfallResult with nearest station data, or None if unavailable
        """
        try:
            data = await self._fetch_rainfall_data()
            if not data:
                return None

            stations = self._parse_stations(data)
            readings = self._parse_readings(data)

            if not stations or not readings:
                logger.info("[NEA] No stations or readings available")
                return None

            # Find nearest station
            nearest_station, distance = self._find_nearest_station(lat, lng, stations)
            if not nearest_station or distance > MAX_STATION_DISTANCE_KM:
                logger.info(
                    f"[NEA] No station within {MAX_STATION_DISTANCE_KM}km of ({lat:.4f}, {lng:.4f})"
                )
                return None

            # Get latest reading for that station
            reading = readings.get(nearest_station.station_id)
            if reading is None:
                logger.info(f"[NEA] No reading for station {nearest_station.station_id}")
                return None

            # Estimate hourly rainfall from 5-min reading (multiply by 12)
            rainfall_1h_estimate = reading.value_mm * 12

            return NEARainfallResult(
                station_id=nearest_station.station_id,
                station_name=nearest_station.name,
                distance_km=round(distance, 2),
                rainfall_5min_mm=reading.value_mm,
                rainfall_1h_mm=round(rainfall_1h_estimate, 2),
                timestamp=reading.timestamp,
                data_source="nea",
            )

        except Exception as e:
            logger.error(f"[NEA] Failed to get rainfall: {e}")
            return None

    async def _fetch_rainfall_data(self) -> Optional[dict]:
        """Fetch rainfall data from NEA API with caching."""
        return await self._fetch_nea_data(NEA_RAINFALL_URL, "nea_rainfall")

    def _parse_stations(self, data: dict) -> List[NEAStation]:
        """Parse station metadata from NEA response."""
        stations = []
        try:
            station_list = data.get("data", {}).get("stations", [])
            for s in station_list:
                station_id = s.get("id", "")
                name = s.get("name", "")
                location = s.get("location", {})
                lat = location.get("latitude")
                lng = location.get("longitude")
                if station_id and lat is not None and lng is not None:
                    stations.append(NEAStation(
                        station_id=station_id,
                        name=name,
                        lat=float(lat),
                        lng=float(lng),
                    ))
        except (KeyError, TypeError) as e:
            logger.error(f"[NEA] Failed to parse stations: {e}")

        return stations

    def _parse_readings(self, data: dict) -> Dict[str, NEARainfallReading]:
        """
        Parse latest rainfall readings from NEA response.

        Returns dict of station_id -> NEARainfallReading for the most recent timestamp.
        """
        readings: Dict[str, NEARainfallReading] = {}
        try:
            readings_data = data.get("data", {}).get("readings", [])
            if not readings_data:
                return readings

            # Get the latest timestamp's readings
            latest = readings_data[-1] if readings_data else {}
            timestamp = latest.get("timestamp", "")
            station_readings = latest.get("data", [])

            for r in station_readings:
                station_id = r.get("stationId", "")
                value = r.get("value")
                if station_id and value is not None:
                    readings[station_id] = NEARainfallReading(
                        station_id=station_id,
                        value_mm=float(value),
                        timestamp=timestamp,
                    )
        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"[NEA] Failed to parse readings: {e}")

        return readings

    def _find_nearest_station(
        self, lat: float, lng: float, stations: List[NEAStation]
    ) -> Tuple[Optional[NEAStation], float]:
        """
        Find the nearest station to the given coordinates.

        Returns:
            Tuple of (nearest_station, distance_km)
        """
        nearest = None
        min_distance = float("inf")

        for station in stations:
            dist = haversine_distance(lat, lng, station.lat, station.lng)
            if dist < min_distance:
                min_distance = dist
                nearest = station

        return nearest, min_distance

    def clear_cache(self):
        """Clear the rainfall data cache."""
        self._cache.clear()

    async def get_current_conditions(
        self, lat: float, lng: float
    ) -> Optional[NEACurrentConditions]:
        """
        Get current temperature and humidity from nearest NEA stations.

        Fetches from separate humidity and temperature APIs, finds nearest
        station for each (they may be different stations).

        Args:
            lat: Latitude (should be within Singapore bounds)
            lng: Longitude

        Returns:
            NEACurrentConditions with temperature and humidity, or None if unavailable
        """
        try:
            # Fetch both in parallel
            humidity_data, temp_data = await asyncio.gather(
                self._fetch_nea_data(NEA_HUMIDITY_URL, "nea_humidity"),
                self._fetch_nea_data(NEA_TEMPERATURE_URL, "nea_temperature"),
                return_exceptions=True,
            )

            temperature_c = None
            temp_station_name = None
            humidity_pct = None
            humidity_station_name = None
            timestamp = ""

            # Parse temperature
            if isinstance(temp_data, dict):
                stations = self._parse_stations(temp_data)
                readings = self._parse_readings(temp_data)
                if stations and readings:
                    nearest, dist = self._find_nearest_station(lat, lng, stations)
                    if nearest and dist <= MAX_STATION_DISTANCE_KM:
                        reading = readings.get(nearest.station_id)
                        if reading:
                            temperature_c = round(reading.value_mm, 1)  # value_mm holds the numeric value
                            temp_station_name = nearest.name
                            timestamp = reading.timestamp

            # Parse humidity
            if isinstance(humidity_data, dict):
                stations = self._parse_stations(humidity_data)
                readings = self._parse_readings(humidity_data)
                if stations and readings:
                    nearest, dist = self._find_nearest_station(lat, lng, stations)
                    if nearest and dist <= MAX_STATION_DISTANCE_KM:
                        reading = readings.get(nearest.station_id)
                        if reading:
                            humidity_pct = round(reading.value_mm, 1)
                            humidity_station_name = nearest.name
                            if not timestamp:
                                timestamp = reading.timestamp

            if temperature_c is None and humidity_pct is None:
                return None

            return NEACurrentConditions(
                temperature_c=temperature_c,
                humidity_pct=humidity_pct,
                temp_station_name=temp_station_name,
                humidity_station_name=humidity_station_name,
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"[NEA] Failed to get current conditions: {e}")
            return None

    async def get_two_hour_forecast(self) -> Optional[NEATwoHourForecast]:
        """
        Get NEA 2-hour weather forecast for all Singapore areas.

        Returns area-specific weather conditions and flags areas with
        flash flood risk (Thundery Showers, Heavy Rain, etc.).

        Returns:
            NEATwoHourForecast with all areas and risk flags, or None if unavailable
        """
        try:
            data = await self._fetch_nea_data(
                NEA_TWO_HOUR_FORECAST_URL, "nea_2hr_forecast",
                cache_ttl=FORECAST_CACHE_TTL_SECONDS,
            )
            if not data:
                return None

            # Parse area metadata (name + coordinates)
            area_metadata = {}
            for area in data.get("data", {}).get("area_metadata", []):
                name = area.get("name", "")
                location = area.get("label_location", {})
                lat = location.get("latitude")
                lng = location.get("longitude")
                if name and lat is not None and lng is not None:
                    area_metadata[name] = (float(lat), float(lng))

            # Parse forecasts from latest item
            items = data.get("data", {}).get("items", [])
            if not items:
                logger.info("[NEA] No forecast items available")
                return None

            latest = items[-1]
            valid_period = latest.get("valid_period", {})
            update_timestamp = latest.get("update_timestamp", "")
            forecasts = latest.get("forecasts", [])

            areas: List[NEAForecastArea] = []
            high_risk_areas: List[str] = []

            for fc in forecasts:
                area_name = fc.get("area", "")
                condition = fc.get("forecast", "")

                if not area_name or not condition:
                    continue

                coords = area_metadata.get(area_name, (1.35, 103.82))  # Default to central SG
                is_risky = condition in FLASH_FLOOD_CONDITIONS

                areas.append(NEAForecastArea(
                    name=area_name,
                    condition=condition,
                    flash_flood_risk=is_risky,
                    lat=coords[0],
                    lng=coords[1],
                ))

                if is_risky:
                    high_risk_areas.append(area_name)

            return NEATwoHourForecast(
                valid_period_start=valid_period.get("start", ""),
                valid_period_end=valid_period.get("end", ""),
                areas=areas,
                high_risk_areas=high_risk_areas,
                update_timestamp=update_timestamp,
            )

        except Exception as e:
            logger.error(f"[NEA] Failed to get 2-hour forecast: {e}")
            return None

    async def _fetch_nea_data(
        self, url: str, cache_key: str, cache_ttl: float = CACHE_TTL_SECONDS
    ) -> Optional[dict]:
        """
        Generic NEA API fetch with caching.

        Reusable for any data.gov.sg v2 real-time endpoint.
        """
        now = datetime.now(timezone.utc).timestamp()

        # Check cache
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if now - cached_time < cache_ttl:
                return cached_data

        try:
            headers = {"Accept": "application/json"}
            if settings.NEA_API_KEY:
                headers["x-api-key"] = settings.NEA_API_KEY

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            self._cache[cache_key] = (data, now)
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"[NEA] {cache_key}: API returned HTTP {e.response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error(f"[NEA] {cache_key}: API request timed out")
            return None
        except Exception as e:
            logger.error(f"[NEA] {cache_key}: Failed to fetch data: {e}")
            return None


# Singleton
_nea_service: Optional[NEAWeatherService] = None


def get_nea_weather_service() -> NEAWeatherService:
    """Get or create the singleton NEA weather service."""
    global _nea_service
    if _nea_service is None:
        _nea_service = NEAWeatherService()
    return _nea_service
