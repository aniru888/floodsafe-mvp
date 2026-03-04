"""
Google FloodHub Service - API client for Google's Flood Forecasting API.

Provides flood forecasting data for India (Delhi region primarily).
This is a direct API proxy with in-memory TTL caching.

NO DATABASE STORAGE - data is fetched fresh from Google API.

API Reference: https://developers.google.com/flood-forecasting/rest
Authentication: API key as query parameter (?key=...)
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date, timedelta, timezone
import logging
import math
import xml.etree.ElementTree as ET
import httpx
from src.core.circuit_breaker import floodhub_breaker
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FloodHubAPIError(Exception):
    """Explicit error for FloodHub API failures - NO SILENT FALLBACKS."""
    pass


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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
    has_model: bool = False
    quality_verified: bool = False
    forecast_trend: Optional[str] = None  # RISE, FALL, NO_CHANGE
    inundation_map_set: Optional[dict] = None  # {level: polygon_id}


class ForecastPoint(BaseModel):
    """Single point in a forecast time series."""
    timestamp: datetime
    water_level: Optional[float] = None  # value in meters or m³/s, None when NaN (dry season)
    is_forecast: bool = True


class GaugeForecast(BaseModel):
    """Forecast for a gauge."""
    gauge_id: str
    site_name: str
    forecasts: List[ForecastPoint]
    danger_level: float
    warning_level: float
    extreme_danger_level: Optional[float] = None
    gauge_value_unit: str = "METERS"  # METERS or CUBIC_METERS_PER_SECOND


class FloodHubStatus(BaseModel):
    """Overall FloodHub status for a region."""
    enabled: bool
    message: Optional[str] = None
    overall_severity: Optional[str] = None
    gauge_count: Optional[int] = None
    alerts_by_severity: Optional[Dict[str, int]] = None
    last_updated: Optional[str] = None


class SignificantEvent(BaseModel):
    """A significant flood event predicted by the system."""
    start_time: datetime
    end_time: Optional[datetime] = None
    minimum_end_time: Optional[datetime] = None
    affected_country_codes: List[str] = []
    affected_population: Optional[int] = None
    area_km2: Optional[float] = None
    gauge_ids: List[str] = []
    event_polygon_id: Optional[str] = None


class GaugeModel(BaseModel):
    """Hydrological model metadata and thresholds for a gauge."""
    gauge_id: str
    gauge_model_id: Optional[str] = None
    gauge_value_unit: str = "METERS"
    quality_verified: bool = False
    warning_level: float = 0
    danger_level: float = 0
    extreme_danger_level: Optional[float] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class FloodHubService:
    """
    Google Flood Forecasting API client with TTL caching.

    Architecture:
    - Direct proxy to Google Flood Forecasting API v1
    - API key authentication via query parameter
    - In-memory TTL cache (configurable per data type)
    - Explicit error handling - raises FloodHubAPIError on failures
    """

    BASE_URL = "https://floodforecasting.googleapis.com/v1"

    # Cache TTLs by data type
    CACHE_TTL_GAUGES_MIN = 10
    CACHE_TTL_STATUS_MIN = 10
    CACHE_TTL_FORECAST_MIN = 15
    CACHE_TTL_MODELS_MIN = 60  # thresholds rarely change
    CACHE_TTL_INUNDATION_MIN = 30  # polygons change slowly
    CACHE_TTL_EVENTS_MIN = 15

    REQUEST_TIMEOUT_SECONDS = 30

    # Gauge search bucket sizes (API limits)
    FORECAST_BUCKET_SIZE = 500
    MODEL_BUCKET_SIZE = 50

    # City bounding boxes for filtering region-wide results
    CITY_BOUNDS = {
        "delhi": {
            "lat_min": 28.0,   # Expanded to Delhi NCR (aligned with GDACS bounds)
            "lat_max": 29.2,
            "lng_min": 76.5,
            "lng_max": 77.8,
            "region_code": "IN",
            "country_code": "IN",
        },
        "bangalore": {
            "lat_min": 12.75,
            "lat_max": 13.20,
            "lng_min": 77.35,
            "lng_max": 77.80,
            "region_code": "IN",
            "country_code": "IN",
        },
        "yogyakarta": {
            "lat_min": -7.95,
            "lat_max": -7.65,
            "lng_min": 110.30,
            "lng_max": 110.50,
            "region_code": "ID",
            "country_code": "ID",
        },
        "singapore": {
            "lat_min": 1.15,
            "lat_max": 1.47,
            "lng_min": 103.60,
            "lng_max": 104.05,
            "region_code": "SG",
            "country_code": "SG",
        },
        "indore": {
            "lat_min": 22.52,
            "lat_max": 22.85,
            "lng_min": 75.72,
            "lng_max": 75.97,
            "region_code": "IN",
            "country_code": "IN",
        },
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize service with optional API key."""
        self.api_key = api_key
        self.enabled = bool(api_key)
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self.client: Optional[httpx.AsyncClient] = None

        if self.enabled and api_key:
            # No auth headers — key goes as query param per Google docs
            self.client = httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT_SECONDS)
            logger.info("FloodHubService initialized with API key")
        else:
            logger.info("FloodHubService disabled - no API key configured")

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _get_cached(self, cache_key: str, ttl_minutes: int) -> Optional[Any]:
        """Get data from cache if not expired."""
        if cache_key not in self._cache:
            return None
        data, cached_at = self._cache[cache_key]
        if datetime.now(timezone.utc) - cached_at < timedelta(minutes=ttl_minutes):
            logger.debug(f"Cache hit for {cache_key}")
            return data
        del self._cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, data: Any) -> None:
        """Store data in cache with current timestamp."""
        self._cache[cache_key] = (data, datetime.now(timezone.utc))
        logger.debug(f"Cached {cache_key}")

    def _auth_params(self) -> Dict[str, str]:
        """Return query params dict with API key."""
        return {"key": self.api_key} if self.api_key else {}

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    async def _paginated_post(self, url: str, body: dict, result_key: str) -> list:
        """Execute a paginated POST request, collecting all pages."""
        if floodhub_breaker.is_open:
            raise FloodHubAPIError("FloodHub circuit open — too many recent failures")

        all_items: list = []
        page_token: Optional[str] = None

        try:
            while True:
                request_body = {**body}
                if page_token:
                    request_body["pageToken"] = page_token

                response = await self.client.post(  # type: ignore[union-attr]
                    url, params=self._auth_params(), json=request_body,
                )
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    raise FloodHubAPIError(f"API error: {data['error']}")

                all_items.extend(data.get(result_key, []))

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            floodhub_breaker.record_success()
            return all_items
        except FloodHubAPIError:
            floodhub_breaker.record_failure()
            raise
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            floodhub_breaker.record_failure()
            raise FloodHubAPIError(f"FloodHub API error: {e}") from e

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    def _filter_by_bounds(self, items: list, bounds: dict,
                          lat_key: str = "latitude", lng_key: str = "longitude",
                          location_wrapper: Optional[str] = None) -> list:
        """Filter items to a bounding box."""
        result = []
        for item in items:
            loc = item.get(location_wrapper, item) if location_wrapper else item
            lat = loc.get(lat_key, 0)
            lng = loc.get(lng_key, 0)
            if bounds["lat_min"] <= lat <= bounds["lat_max"] and bounds["lng_min"] <= lng <= bounds["lng_max"]:
                result.append(item)
        return result

    async def get_region_gauges(self, region_code: str) -> list:
        """Fetch all gauges for a region (e.g. 'IN', 'ID')."""
        if not self.enabled or self.client is None:
            return []

        cache_key = f"{region_code.lower()}_gauges_raw"
        cached = self._get_cached(cache_key, self.CACHE_TTL_GAUGES_MIN)
        if cached is not None:
            return cached

        try:
            gauges = await self._paginated_post(
                f"{self.BASE_URL}/gauges:searchGaugesByArea",
                body={
                    "regionCode": region_code,
                    "pageSize": 10000,
                    "includeNonQualityVerified": False,
                },
                result_key="gauges",
            )
            self._set_cached(cache_key, gauges)
            logger.info(f"Fetched {len(gauges)} {region_code} gauges from Google API")
            return gauges
        except httpx.HTTPStatusError as e:
            logger.error(f"FloodHub gauges HTTP error for {region_code}: {e.response.status_code}")
            raise FloodHubAPIError(f"Google API returned {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"FloodHub gauges request error for {region_code}: {e}")
            raise FloodHubAPIError(f"Network error connecting to FloodHub: {e}")

    async def get_region_flood_statuses(self, region_code: str) -> list:
        """Fetch all flood statuses for a region."""
        if not self.enabled or self.client is None:
            return []

        cache_key = f"{region_code.lower()}_statuses_raw"
        cached = self._get_cached(cache_key, self.CACHE_TTL_STATUS_MIN)
        if cached is not None:
            return cached

        try:
            statuses = await self._paginated_post(
                f"{self.BASE_URL}/floodStatus:searchLatestFloodStatusByArea",
                body={
                    "regionCode": region_code,
                    "pageSize": 10000,
                    "includeNonQualityVerified": False,
                },
                result_key="floodStatuses",
            )
            self._set_cached(cache_key, statuses)
            logger.info(f"Fetched {len(statuses)} {region_code} flood statuses")
            return statuses
        except httpx.HTTPStatusError as e:
            logger.error(f"FloodHub status HTTP error for {region_code}: {e.response.status_code}")
            raise FloodHubAPIError(f"Google API returned {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"FloodHub status request error for {region_code}: {e}")
            raise FloodHubAPIError(f"Network error: {e}")

    async def get_city_gauges(self, city: str) -> List[GaugeStatus]:
        """
        Fetch gauges for any supported city.
        Routes to correct region code and filters by city bounds.
        Returns empty list with log message if city not supported.
        """
        city_lower = city.lower()
        if city_lower not in self.CITY_BOUNDS:
            logger.warning(f"FloodHub: unsupported city '{city}' — no bounds configured")
            return []

        bounds = self.CITY_BOUNDS[city_lower]
        region_code = bounds["region_code"]

        if not self.enabled or self.client is None:
            return []

        cache_key = f"{city_lower}_gauges"
        cached = self._get_cached(cache_key, self.CACHE_TTL_GAUGES_MIN)
        if cached is not None:
            return cached

        try:
            # Step 1: Get all region gauges, filter to city bounds
            all_gauges = await self.get_region_gauges(region_code)
            city_gauges = self._filter_by_bounds(all_gauges, bounds, location_wrapper="location")

            if not city_gauges:
                logger.info(f"No gauges found in {city} region (region={region_code})")
                self._set_cached(cache_key, [])
                return []

            # Step 2: Get all region flood statuses, build lookup by gauge_id
            all_statuses = await self.get_region_flood_statuses(region_code)
            status_map = {s["gaugeId"]: s for s in all_statuses}

            # Step 3: Combine gauge metadata + flood status
            result = []
            for gauge in city_gauges:
                gauge_id = gauge["gaugeId"]
                status = status_map.get(gauge_id, {})

                inundation = None
                imap_set = status.get("inundationMapSet")
                if imap_set and imap_set.get("inundationMaps"):
                    inundation = {}
                    for imap in imap_set["inundationMaps"]:
                        inundation[imap.get("level", "UNKNOWN")] = imap.get("serializedPolygonId", "")

                issued_str = status.get("issuedTime", "")
                if issued_str:
                    issued_time = datetime.fromisoformat(issued_str.replace("Z", "+00:00"))
                else:
                    issued_time = datetime.now(timezone.utc)

                result.append(GaugeStatus(
                    gauge_id=gauge_id,
                    site_name=gauge.get("siteName", "") or "Unknown Station",
                    river=gauge.get("river", "") or "Unknown River",
                    latitude=gauge.get("location", {}).get("latitude", 0),
                    longitude=gauge.get("location", {}).get("longitude", 0),
                    severity=status.get("severity", "UNKNOWN"),
                    issued_time=issued_time,
                    source=gauge.get("source", "Unknown"),
                    has_model=gauge.get("hasModel", False),
                    quality_verified=gauge.get("qualityVerified", False),
                    forecast_trend=status.get("forecastTrend"),
                    inundation_map_set=inundation,
                ))

            self._set_cached(cache_key, result)
            logger.info(f"Fetched {len(result)} {city} gauges from FloodHub")
            return result

        except FloodHubAPIError:
            raise
        except Exception as e:
            logger.error(f"FloodHub city gauge fetch failed for {city}: {e}")
            raise FloodHubAPIError(f"Failed to fetch {city} gauges: {e}")

    async def get_city_events(self, city: str) -> list:
        """Get significant events for a city's country. Returns events filtered by country code."""
        city_lower = city.lower()
        if city_lower not in self.CITY_BOUNDS:
            return []
        country_code = self.CITY_BOUNDS[city_lower]["country_code"]
        all_events = await self.get_significant_events()
        # get_significant_events already filters to "IN" — re-filter for the actual country
        # We need to fetch unfiltered events for non-IN cities
        return [e for e in all_events if country_code in e.affected_country_codes]

    async def get_gauge_forecast(self, gauge_id: str) -> Optional[GaugeForecast]:
        """
        Fetch forecast for a specific gauge.

        Uses queryGaugeForecasts with a 7-day window.
        Also fetches gauge model for thresholds.
        """
        if not self.enabled or self.client is None:
            return None

        cache_key = f"forecast_{gauge_id}"
        cached = self._get_cached(cache_key, self.CACHE_TTL_FORECAST_MIN)
        if cached is not None:
            return cached

        try:
            # Fetch forecasts (last 7 days of issued forecasts)
            today = date.today()
            week_ago = today - timedelta(days=7)

            response = await self.client.get(
                f"{self.BASE_URL}/gauges:queryGaugeForecasts",
                params={
                    **self._auth_params(),
                    "gaugeIds": gauge_id,
                    "issuedTimeStart": week_ago.isoformat(),
                    "issuedTimeEnd": (today + timedelta(days=1)).isoformat(),
                },
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise FloodHubAPIError(f"API error: {data['error']}")

            # Parse forecasts — response structure:
            # {"forecasts": {"gaugeId": {"forecasts": [Forecast, ...]}}}
            # Note: double-nested "forecasts" key per Google API spec
            forecasts_dict = data.get("forecasts", {})
            gauge_entry = forecasts_dict.get(gauge_id, {})
            # Handle both dict (correct) and list (fallback) shapes
            if isinstance(gauge_entry, dict):
                gauge_forecasts_raw = gauge_entry.get("forecasts", [])
            elif isinstance(gauge_entry, list):
                gauge_forecasts_raw = gauge_entry
            else:
                gauge_forecasts_raw = []

            if not gauge_forecasts_raw:
                logger.info(f"No forecasts returned for gauge {gauge_id}")
                return None

            # Take the most recently issued forecast (filter to dicts only)
            valid_forecasts = [f for f in gauge_forecasts_raw if isinstance(f, dict)]
            if not valid_forecasts:
                logger.info(f"No valid forecast entries for gauge {gauge_id}")
                return None
            latest_forecast = max(valid_forecasts, key=lambda f: f.get("issuedTime", ""))

            # Build forecast points from forecastRanges
            forecast_points: List[ForecastPoint] = []
            issued_time_str = latest_forecast.get("issuedTime", "")
            issued_time = None
            if issued_time_str:
                issued_time = datetime.fromisoformat(issued_time_str.replace("Z", "+00:00"))

            for fr in latest_forecast.get("forecastRanges", []):
                if not isinstance(fr, dict):
                    continue
                start_str = fr.get("forecastStartTime", "")
                if not start_str:
                    continue
                ts = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                raw_value = fr.get("value")
                # Google API returns NaN during dry season — not JSON-serializable
                value = None if raw_value is None or (isinstance(raw_value, float) and math.isnan(raw_value)) else raw_value

                # Determine if this is a forecast or observation
                is_forecast = True
                if issued_time and ts < issued_time:
                    is_forecast = False

                forecast_points.append(ForecastPoint(
                    timestamp=ts,
                    water_level=value,
                    is_forecast=is_forecast,
                ))

            # Sort by timestamp
            forecast_points.sort(key=lambda p: p.timestamp)

            # Fetch gauge model for thresholds
            model = await self._get_single_gauge_model(gauge_id)

            # Find gauge site name from cached gauges
            site_name = "Unknown Station"
            all_gauges = await self.get_region_gauges("IN")
            for g in all_gauges:
                if g.get("gaugeId") == gauge_id:
                    site_name = g.get("siteName", "") or "Unknown Station"
                    break

            result = GaugeForecast(
                gauge_id=gauge_id,
                site_name=site_name,
                forecasts=forecast_points,
                danger_level=model.danger_level if model else 0,
                warning_level=model.warning_level if model else 0,
                extreme_danger_level=model.extreme_danger_level if model else None,
                gauge_value_unit=model.gauge_value_unit if model else "METERS",
            )

            self._set_cached(cache_key, result)
            logger.info(f"Fetched forecast for gauge {gauge_id}: {len(forecast_points)} points")
            return result

        except FloodHubAPIError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Gauge or forecast not found — return None so router sends 404
                logger.info(f"No forecast found for gauge {gauge_id} (HTTP 404)")
                return None
            logger.error(f"FloodHub forecast HTTP error: {e.response.status_code}")
            raise FloodHubAPIError(f"Failed to fetch forecast: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"FloodHub forecast request error: {e}")
            raise FloodHubAPIError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"FloodHub forecast unexpected error: {e}")
            raise FloodHubAPIError(f"Unexpected error: {e}")

    async def get_overall_status(self) -> FloodHubStatus:
        """Get aggregated status for Delhi region."""
        if not self.enabled:
            return FloodHubStatus(
                enabled=False,
                message="FloodHub API not configured",
            )

        try:
            gauges = await self.get_city_gauges("delhi")

            if not gauges:
                return FloodHubStatus(
                    enabled=True,
                    message="No gauges available for Delhi",
                    overall_severity="UNKNOWN",
                    gauge_count=0,
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

            latest_update = max(g.issued_time for g in gauges)

            return FloodHubStatus(
                enabled=True,
                overall_severity=overall_severity,
                gauge_count=len(gauges),
                alerts_by_severity=severity_counts,
                last_updated=latest_update.isoformat(),
            )

        except FloodHubAPIError:
            raise
        except Exception as e:
            logger.error(f"Error computing overall status: {e}")
            raise FloodHubAPIError(f"Failed to compute status: {e}")

    # ------------------------------------------------------------------
    # New capabilities
    # ------------------------------------------------------------------

    async def _get_single_gauge_model(self, gauge_id: str) -> Optional[GaugeModel]:
        """Fetch model metadata (thresholds) for a single gauge."""
        models = await self.get_gauge_models([gauge_id])
        return models[0] if models else None

    async def get_gauge_models(self, gauge_ids: List[str]) -> List[GaugeModel]:
        """
        Fetch hydrological model metadata for gauges (thresholds).
        Max 50 per request — auto-buckets.
        """
        if not self.enabled or self.client is None:
            return []

        # Check cache for each gauge
        uncached_ids = []
        cached_models: List[GaugeModel] = []
        for gid in gauge_ids:
            cached = self._get_cached(f"model_{gid}", self.CACHE_TTL_MODELS_MIN)
            if cached is not None:
                cached_models.append(cached)
            else:
                uncached_ids.append(gid)

        if not uncached_ids:
            return cached_models

        try:
            fetched_models: List[GaugeModel] = []

            # Bucket into groups of 50
            for i in range(0, len(uncached_ids), self.MODEL_BUCKET_SIZE):
                bucket = uncached_ids[i:i + self.MODEL_BUCKET_SIZE]
                params = {**self._auth_params()}
                # Multiple "names" params for batch get
                names_list = [f"gaugeModels/{gid}" for gid in bucket]

                response = await self.client.get(
                    f"{self.BASE_URL}/gaugeModels:batchGet",
                    params={**params, "names": names_list},
                )
                response.raise_for_status()
                data = response.json()

                for gm in data.get("gaugeModels", []):
                    thresholds = gm.get("thresholds", {})
                    unit_raw = gm.get("gaugeValueUnit", "GAUGE_VALUE_UNIT_UNSPECIFIED")
                    unit = "CUBIC_METERS_PER_SECOND" if "CUBIC" in unit_raw else "METERS"

                    model = GaugeModel(
                        gauge_id=gm.get("gaugeId", ""),
                        gauge_model_id=gm.get("gaugeModelId"),
                        gauge_value_unit=unit,
                        quality_verified=gm.get("qualityVerified", False),
                        warning_level=thresholds.get("warningLevel", 0),
                        danger_level=thresholds.get("dangerLevel", 0),
                        extreme_danger_level=thresholds.get("extremeDangerLevel"),
                    )
                    fetched_models.append(model)
                    self._set_cached(f"model_{model.gauge_id}", model)

            return cached_models + fetched_models

        except httpx.HTTPStatusError as e:
            logger.warning(f"Gauge models HTTP error: {e.response.status_code}")
            return cached_models  # Return what we have from cache
        except httpx.RequestError as e:
            logger.warning(f"Gauge models request error: {e}")
            return cached_models
        except Exception as e:
            logger.warning(f"Gauge models unexpected error: {e}")
            return cached_models

    async def get_inundation_polygon(self, polygon_id: str) -> Optional[dict]:
        """
        Fetch an inundation polygon and convert from KML to GeoJSON.
        Returns a GeoJSON FeatureCollection.
        """
        if not self.enabled or self.client is None:
            return None

        cache_key = f"inundation_{polygon_id}"
        cached = self._get_cached(cache_key, self.CACHE_TTL_INUNDATION_MIN)
        if cached is not None:
            return cached

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/serializedPolygons/{polygon_id}",
                params=self._auth_params(),
            )
            response.raise_for_status()
            data = response.json()

            kml_string = data.get("kml", "")
            if not kml_string:
                return None

            geojson = self._kml_to_geojson(kml_string)
            self._set_cached(cache_key, geojson)
            return geojson

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Polygon doesn't exist — return None so router sends 404
                logger.info(f"Inundation polygon not found: {polygon_id}")
                return None
            logger.error(f"Inundation polygon HTTP error: {e.response.status_code}")
            raise FloodHubAPIError(f"Failed to fetch inundation: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Inundation polygon request error: {e}")
            raise FloodHubAPIError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Inundation polygon error: {e}")
            raise FloodHubAPIError(f"Failed to parse inundation: {e}")

    @staticmethod
    def _kml_to_geojson(kml_string: str) -> dict:
        """
        Convert a KML string to a GeoJSON FeatureCollection.
        Handles Polygon and MultiGeometry elements.
        Uses stdlib xml.etree — no external dependency needed.
        """
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        root = ET.fromstring(kml_string)

        features = []

        # Find all <coordinates> within <Polygon> elements
        for polygon in root.iter("{http://www.opengis.net/kml/2.2}Polygon"):
            coords_el = polygon.find(
                ".//kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns
            )
            if coords_el is None:
                coords_el = polygon.find(
                    ".//{http://www.opengis.net/kml/2.2}coordinates"
                )
            if coords_el is None or not coords_el.text:
                continue

            ring = []
            for coord_str in coords_el.text.strip().split():
                parts = coord_str.split(",")
                if len(parts) >= 2:
                    lng, lat = float(parts[0]), float(parts[1])
                    ring.append([lng, lat])

            if len(ring) >= 3:
                # Ensure ring is closed
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                features.append({
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [ring],
                    },
                })

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    async def get_significant_events(self) -> List[SignificantEvent]:
        """
        Fetch current significant flood events.
        These are predicted high-probability, high-impact events.
        """
        if not self.enabled or self.client is None:
            return []

        cache_key = "significant_events"
        cached = self._get_cached(cache_key, self.CACHE_TTL_EVENTS_MIN)
        if cached is not None:
            return cached

        try:
            # Paginated POST
            raw_events = await self._paginated_post(
                f"{self.BASE_URL}/significantEvents:search",
                body={},
                result_key="significantEvents",
            )

            events = []
            for raw in raw_events:
                interval = raw.get("eventInterval", {})

                # Parse times
                start_str = interval.get("startTime", "")
                start_time = (
                    datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    if start_str else datetime.now(timezone.utc)
                )

                end_time = None
                end_str = interval.get("endTime", "")
                if end_str:
                    end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

                min_end_time = None
                min_end_str = interval.get("minimumEndTime", "")
                if min_end_str:
                    min_end_time = datetime.fromisoformat(min_end_str.replace("Z", "+00:00"))

                events.append(SignificantEvent(
                    start_time=start_time,
                    end_time=end_time,
                    minimum_end_time=min_end_time,
                    affected_country_codes=raw.get("affectedCountryCodes", []),
                    affected_population=raw.get("affectedPopulation"),
                    area_km2=raw.get("areaKm2"),
                    gauge_ids=raw.get("gaugeIds", []),
                    event_polygon_id=raw.get("eventPolygonId"),
                ))

            # Cache all events (filtering by country happens in get_city_events)
            self._set_cached(cache_key, events)
            logger.info(f"Fetched {len(events)} significant events globally")
            return events

        except httpx.HTTPStatusError as e:
            logger.error(f"Significant events HTTP error: {e.response.status_code}")
            raise FloodHubAPIError(f"Failed to fetch events: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Significant events request error: {e}")
            raise FloodHubAPIError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Significant events error: {e}")
            raise FloodHubAPIError(f"Unexpected error: {e}")


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
