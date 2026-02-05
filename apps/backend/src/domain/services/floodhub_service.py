"""
Google FloodHub Service - API client for Google's Flood Forecasting API.

Provides flood forecasting data for Delhi's Yamuna River gauges.
This is a direct API proxy with in-memory TTL caching.

NO DATABASE STORAGE - data is fetched fresh from Google API.
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import logging
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FloodHubAPIError(Exception):
    """Explicit error for FloodHub API failures - NO SILENT FALLBACKS."""
    pass


class GaugeStatus(BaseModel):
    """Current flood status for a gauge."""
    gauge_id: str
    site_name: str
    river: str
    latitude: float
    longitude: float
    severity: str  # EXTREME, SEVERE, ABOVE_NORMAL, NO_FLOODING, UNKNOWN
    issued_time: datetime
    source: str


class ForecastPoint(BaseModel):
    """Single point in a forecast time series."""
    timestamp: datetime
    water_level: float
    is_forecast: bool  # True for predicted, False for historical


class GaugeForecast(BaseModel):
    """7-day forecast for a gauge."""
    gauge_id: str
    site_name: str
    forecasts: List[ForecastPoint]
    danger_level: float
    warning_level: float


class FloodHubStatus(BaseModel):
    """Overall FloodHub status for a region."""
    enabled: bool
    message: Optional[str] = None
    overall_severity: Optional[str] = None
    gauge_count: Optional[int] = None
    alerts_by_severity: Optional[Dict[str, int]] = None
    last_updated: Optional[str] = None


class FloodHubService:
    """
    Google FloodHub API client with TTL caching.

    Architecture:
    - Direct proxy to Google Flood Forecasting API
    - In-memory TTL cache (10 min) - no database storage
    - Explicit error handling - raises FloodHubAPIError on failures
    """

    BASE_URL = "https://floodforecasting.googleapis.com/v1"
    CACHE_TTL_MINUTES = 10
    REQUEST_TIMEOUT_SECONDS = 30

    # Delhi Yamuna River bounding box
    DELHI_BOUNDS = {
        "lat_min": 28.4,
        "lat_max": 28.9,
        "lng_min": 76.8,
        "lng_max": 77.4
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize service with optional API key."""
        self.api_key = api_key
        self.enabled = bool(api_key)
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self.client: Optional[httpx.AsyncClient] = None

        if self.enabled and api_key:
            self.client = httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT_SECONDS,
                headers={"X-Goog-Api-Key": api_key}
            )
            logger.info("FloodHubService initialized with API key")
        else:
            logger.info("FloodHubService disabled - no API key configured")

    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if not expired."""
        if cache_key not in self._cache:
            return None

        data, cached_at = self._cache[cache_key]
        if datetime.now(timezone.utc) - cached_at < timedelta(minutes=self.CACHE_TTL_MINUTES):
            logger.debug(f"Cache hit for {cache_key}")
            return data

        # Cache expired
        del self._cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, data: Any) -> None:
        """Store data in cache with current timestamp."""
        self._cache[cache_key] = (data, datetime.now(timezone.utc))
        logger.debug(f"Cached {cache_key}")

    async def get_delhi_gauges(self) -> List[GaugeStatus]:
        """
        Fetch all gauges in Delhi region with current flood status.

        Returns empty list if service is disabled (frontend shows "Not Configured").
        Raises FloodHubAPIError on API failures (NO SILENT FALLBACKS).
        """
        if not self.enabled or self.client is None:
            return []

        cache_key = "delhi_gauges"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            # Step 1: Search for gauges in Delhi region
            bounds = self.DELHI_BOUNDS
            search_url = f"{self.BASE_URL}/gauges:searchByArea"
            search_response = await self.client.get(
                search_url,
                params={
                    "regionCode": "IN",
                    "bounds.low.latitude": bounds["lat_min"],
                    "bounds.low.longitude": bounds["lng_min"],
                    "bounds.high.latitude": bounds["lat_max"],
                    "bounds.high.longitude": bounds["lng_max"],
                }
            )
            search_response.raise_for_status()
            gauges_data = search_response.json().get("gauges", [])

            if not gauges_data:
                logger.info("No gauges found in Delhi region")
                self._set_cached(cache_key, [])
                return []

            # Step 2: Get flood status for each gauge
            gauge_ids = [g["gaugeId"] for g in gauges_data]
            status_url = f"{self.BASE_URL}/floodStatus:batchGet"
            status_response = await self.client.post(
                status_url,
                json={"gaugeIds": gauge_ids}
            )
            status_response.raise_for_status()
            statuses = status_response.json().get("floodStatuses", [])

            # Map status by gauge ID
            status_map = {s["gaugeId"]: s for s in statuses}

            # Build result
            result = []
            for gauge in gauges_data:
                gauge_id = gauge["gaugeId"]
                status = status_map.get(gauge_id, {})

                result.append(GaugeStatus(
                    gauge_id=gauge_id,
                    site_name=gauge.get("siteName", "Unknown"),
                    river=gauge.get("river", "Unknown"),
                    latitude=gauge.get("gaugeLocation", {}).get("latitude", 0),
                    longitude=gauge.get("gaugeLocation", {}).get("longitude", 0),
                    severity=status.get("severity", "UNKNOWN"),
                    issued_time=datetime.fromisoformat(
                        status.get("issuedTime", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
                    ),
                    source=gauge.get("source", "Unknown")
                ))

            self._set_cached(cache_key, result)
            logger.info(f"Fetched {len(result)} Delhi gauges from FloodHub")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"FloodHub API HTTP error: {e.response.status_code}")
            raise FloodHubAPIError(f"Google FloodHub API returned {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"FloodHub API request error: {e}")
            raise FloodHubAPIError(f"Network error connecting to FloodHub: {e}")
        except Exception as e:
            logger.error(f"FloodHub API unexpected error: {e}")
            raise FloodHubAPIError(f"Unexpected error: {e}")

    async def get_gauge_forecast(self, gauge_id: str) -> Optional[GaugeForecast]:
        """
        Fetch 7-day forecast for a specific gauge.

        Returns None if service is disabled.
        Raises FloodHubAPIError on API failures.
        """
        if not self.enabled or self.client is None:
            return None

        cache_key = f"forecast_{gauge_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            forecast_url = f"{self.BASE_URL}/gauges/{gauge_id}/forecasts"
            response = await self.client.get(forecast_url)
            response.raise_for_status()
            data = response.json()

            forecasts = []
            for point in data.get("forecastPoints", []):
                forecasts.append(ForecastPoint(
                    timestamp=datetime.fromisoformat(
                        point["time"].replace("Z", "+00:00")
                    ),
                    water_level=point.get("waterLevel", 0),
                    is_forecast=point.get("isForecast", True)
                ))

            result = GaugeForecast(
                gauge_id=gauge_id,
                site_name=data.get("siteName", "Unknown"),
                forecasts=forecasts,
                danger_level=data.get("dangerLevel", 0),
                warning_level=data.get("warningLevel", 0)
            )

            self._set_cached(cache_key, result)
            logger.info(f"Fetched forecast for gauge {gauge_id}")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"FloodHub forecast HTTP error: {e.response.status_code}")
            raise FloodHubAPIError(f"Failed to fetch forecast: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"FloodHub forecast request error: {e}")
            raise FloodHubAPIError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"FloodHub forecast unexpected error: {e}")
            raise FloodHubAPIError(f"Unexpected error: {e}")

    async def get_overall_status(self) -> FloodHubStatus:
        """
        Get aggregated status for Delhi region.

        Returns status with enabled=False if service is disabled.
        """
        if not self.enabled:
            return FloodHubStatus(
                enabled=False,
                message="FloodHub API not configured"
            )

        try:
            gauges = await self.get_delhi_gauges()

            if not gauges:
                return FloodHubStatus(
                    enabled=True,
                    message="No gauges available for Delhi",
                    overall_severity="UNKNOWN",
                    gauge_count=0
                )

            # Count by severity
            severity_counts: Dict[str, int] = {}
            for gauge in gauges:
                severity_counts[gauge.severity] = severity_counts.get(gauge.severity, 0) + 1

            # Determine overall severity (highest)
            severity_priority = ["EXTREME", "SEVERE", "ABOVE_NORMAL", "NO_FLOODING", "UNKNOWN"]
            overall_severity = "UNKNOWN"
            for severity in severity_priority:
                if severity in severity_counts and severity_counts[severity] > 0:
                    overall_severity = severity
                    break

            # Latest update time
            latest_update = max(g.issued_time for g in gauges)

            return FloodHubStatus(
                enabled=True,
                overall_severity=overall_severity,
                gauge_count=len(gauges),
                alerts_by_severity=severity_counts,
                last_updated=latest_update.isoformat()
            )

        except FloodHubAPIError:
            # Re-raise API errors - NO SILENT FALLBACKS
            raise
        except Exception as e:
            logger.error(f"Error computing overall status: {e}")
            raise FloodHubAPIError(f"Failed to compute status: {e}")


# Singleton instance - initialized in main.py with config
floodhub_service: Optional[FloodHubService] = None


def init_floodhub_service(api_key: Optional[str] = None) -> FloodHubService:
    """Initialize the FloodHub service singleton."""
    global floodhub_service
    floodhub_service = FloodHubService(api_key=api_key)
    return floodhub_service


def get_floodhub_service() -> FloodHubService:
    """Get the FloodHub service singleton."""
    if floodhub_service is None:
        raise RuntimeError("FloodHubService not initialized. Call init_floodhub_service first.")
    return floodhub_service
