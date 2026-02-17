"""
Flood Hazard Index (FHI) Calculator.

IMPORTANT: This is a CUSTOM HEURISTIC formula, NOT from published academic research.
The weights (0.35, 0.18, etc.) are empirically tuned for Delhi conditions.
See CLAUDE.md @hotspots for documentation.

FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T_modifier

Components:
- P (35%): Precipitation forecast (with probability-based correction + ceiling-only percentiles)
- I (18%): Intensity (hourly max)
- S (12%): Soil Saturation (70% Antecedent Precipitation Index + 30% ERA5 soil moisture)
- A (12%): Antecedent conditions (3-day burst)
- R (8%): Runoff Potential (pressure-based)
- E (15%): Elevation Risk (inverted: low elevation = high risk)
- T_modifier: per-city wet season modifier

Key Calibrations:
1. Probability-based correction: 1.0x-2.25x based on forecast confidence (per-city)
2. Rain-gate: If <threshold mm in 3 days, cap FHI at LOW (no flood without rain)
3. Antecedent Precipitation Index (API): 14-day exponential decay (replaces crude 3-day proxy)
   - Uses past_days=14 in Open-Meteo call (same request, no extra API calls)
   - Per-city decay constant k: Delhi 0.92, Bangalore 0.88, Yogyakarta 0.85, Singapore 0.80
4. Ceiling-only percentiles for P component: monthly P95 can RAISE threshold, never lower it
   - Reduces monsoon cry-wolf without affecting dry months
5. Singapore triple advantage: NEA real-time + SG percentiles + fast drainage decay (k=0.80)
"""

import httpx
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Retry configuration
MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY = 0.5  # seconds
MAX_RETRY_DELAY = 5.0   # seconds


class FHICalculationError(Exception):
    """Raised when FHI calculation fails."""
    pass


@dataclass
class FHIResult:
    """FHI calculation result."""
    fhi_score: float  # 0.0-1.0
    fhi_level: str  # low, moderate, high, extreme
    fhi_color: str  # hex color
    elevation_m: float
    components: Dict[str, float]  # P, I, S, A, R, E
    monsoon_modifier: float
    rain_gated: bool = False  # Whether FHI was capped due to low rainfall
    correction_factor: float = 1.5  # Applied correction factor
    precip_prob_max: float = 50.0  # Max precipitation probability
    data_source: str = "open-meteo"  # Weather data source ("open-meteo" or "nea")

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "fhi_score": round(self.fhi_score, 3),
            "fhi_level": self.fhi_level,
            "fhi_color": self.fhi_color,
            "elevation_m": round(self.elevation_m, 1),
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "monsoon_modifier": self.monsoon_modifier,
            "rain_gated": self.rain_gated,
            "correction_factor": round(self.correction_factor, 2),
            "precip_prob_max": round(self.precip_prob_max, 0),
            "data_source": self.data_source,
        }


class FHICalculator:
    """Calculate Flood Hazard Index for locations."""

    # Open-Meteo endpoints
    ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    # Weights for FHI formula
    WEIGHTS = {
        "P": 0.35,  # Precipitation
        "I": 0.18,  # Intensity
        "S": 0.12,  # Soil saturation
        "A": 0.12,  # Antecedent conditions
        "R": 0.08,  # Runoff potential
        "E": 0.15,  # Elevation risk
    }

    # Thresholds
    PRECIP_THRESHOLD_MM = 64.4  # IMD "heavy" rainfall
    INTENSITY_THRESHOLD_MM_H = 50.0  # Extreme hourly
    SOIL_SATURATION_MAX = 0.5  # m³/m³
    ANTECEDENT_THRESHOLD_MM = 150.0  # 3-day total
    PRESSURE_BASELINE_HPA = 1013  # Standard pressure

    # Urban calibration constants - empirically tuned for Delhi (no formal validation study)
    BASE_PRECIP_CORRECTION = 1.5       # Conservative baseline (up from 1.2)
    PROB_BOOST_MULTIPLIER = 0.5        # Conservative prob scaling (max 2.25x total)
    MIN_RAIN_THRESHOLD_MM = 5.0        # Rain-gate: below this = LOW risk
    LOW_FHI_CAP = 0.15                 # Cap for dry conditions
    URBAN_SATURATION_THRESHOLD_MM = 50.0  # 3-day rain for urban drainage saturation

    # Number of past days to fetch from Open-Meteo for Antecedent Precipitation Index
    PAST_DAYS = 14

    # City-aware calibration: elevation, wet season, thresholds, correction factors, API decay
    # Cities without explicit overrides inherit class-level defaults (Delhi-tuned)
    CITY_CALIBRATION = {
        "delhi": {
            "elev_min": 190, "elev_max": 320,
            "wet_months": [6, 7, 8, 9],  # June-September (Indian monsoon)
            "urban_fraction": 0.75,
            "default_elev": 220,
            "rain_gate_mm": 5.0,
            "fhi_cache_ttl_seconds": 3600,  # 1 hour (Open-Meteo forecast)
            "api_decay_k": 0.92,            # Slow drainage, clay soils, monsoonal
            "api_threshold": 80.0,          # mm — API value above which soil is saturated
            # Uses class defaults for correction/thresholds (tuned for Delhi)
        },
        "bangalore": {
            "elev_min": 800, "elev_max": 1000,
            "wet_months": [6, 7, 8, 9, 10],  # June-October
            "urban_fraction": 0.65,
            "default_elev": 920,
            "rain_gate_mm": 5.0,
            "fhi_cache_ttl_seconds": 3600,  # 1 hour (Open-Meteo forecast)
            "api_decay_k": 0.88,            # Better runoff at 920m elevation
            "api_threshold": 90.0,
        },
        "yogyakarta": {
            "elev_min": 75, "elev_max": 200,
            "wet_months": [10, 11, 12, 1, 2, 3],  # Oct-March (Indonesian wet season)
            "urban_fraction": 0.55,
            "default_elev": 114,
            "rain_gate_mm": 15.0,  # Higher for tropical: filter light drizzle
            "fhi_cache_ttl_seconds": 1800,  # 30 min (OWM updates every 10 min, future)
            "precip_correction": 1.1,       # Slight boost (Open-Meteo underestimates tropics)
            "prob_boost_multiplier": 0.3,
            "precip_threshold_mm": 80.0,    # Yogyakarta heavy = 60-80mm/day
            "intensity_threshold_mm_h": 60.0,  # Yogyakarta intense = 40-60mm/h
            "antecedent_threshold_mm": 175.0,  # Moderate drainage infrastructure
            "elev_weight_scale": 0.8,       # Elevation matters more (hilly terrain)
            "monsoon_modifier": 1.15,       # Wet season is significant
            "weather_source": "owm",        # Use OWM when API key configured
            "api_decay_k": 0.85,            # Tropical evapotranspiration, volcanic soils
            "api_threshold": 70.0,
        },
        "singapore": {
            "elev_min": 0, "elev_max": 165,  # Bukit Timah = 163m
            "wet_months": [11, 12, 1, 2],  # NE monsoon Nov-Feb
            "urban_fraction": 0.95,
            "default_elev": 15,
            "rain_gate_mm": 25.0,           # SG gets 20mm+ routinely in monsoon
            "fhi_cache_ttl_seconds": 300,   # 5 min (match NEA refresh)
            "precip_correction": 1.0,       # SG has reliable NEA data, no boost needed
            "prob_boost_multiplier": 0.25,  # Max 1.25x (not 2.25x)
            "precip_threshold_mm": 100.0,   # PUB heavy rain = 70-100mm/day
            "intensity_threshold_mm_h": 70.0,  # PUB flash flood = 50-70mm/h
            "antecedent_threshold_mm": 200.0,  # Excellent SG drainage
            "elev_weight_scale": 0.5,       # Halve E contribution (flat city)
            "monsoon_modifier": 1.1,        # Monsoon is daily life, less dramatic
            "nea_extrapolation_factor": 6.0,  # ×6 (not ×12) for bursty tropical showers
            "api_decay_k": 0.80,            # World-class drainage, rapid canal flush
            "api_threshold": 100.0,
        },
    }

    # City bounding boxes for auto-detection from coordinates
    CITY_BOUNDS = {
        "delhi": {"min_lat": 28.40, "max_lat": 28.88, "min_lng": 76.84, "max_lng": 77.35},
        "bangalore": {"min_lat": 12.75, "max_lat": 13.20, "min_lng": 77.35, "max_lng": 77.80},
        "yogyakarta": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
        "singapore": {"min_lat": 1.15, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    }

    # Legacy defaults (Delhi) for backwards compatibility
    DELHI_ELEV_MIN = 190
    DELHI_ELEV_MAX = 320
    MONSOON_MONTHS = [6, 7, 8, 9]
    MONSOON_MODIFIER = 1.2

    # Cache settings
    CACHE_TTL_SECONDS = 3600  # 1 hour

    # Class-level cache for percentile data (loaded once per city, never expires)
    _percentile_data: Dict[str, Dict] = {}

    def __init__(self, timeout_seconds: float = 15.0):
        """Initialize FHI calculator."""
        self._timeout = timeout_seconds
        self._cache: Dict[str, tuple] = {}  # (FHIResult, timestamp)

    @staticmethod
    def compute_api(daily_precip: List[float], k: float = 0.90) -> float:
        """Compute Antecedent Precipitation Index with exponential decay.

        API_t = k * API_{t-1} + P_t

        Args:
            daily_precip: List of daily precipitation in mm, oldest to newest.
            k: Decay constant (0-1). Higher = slower drainage/more moisture retention.
               Delhi 0.92, Bangalore 0.88, Yogyakarta 0.85, Singapore 0.80.

        Returns:
            API value in mm (higher = wetter antecedent conditions)
        """
        api = 0.0
        for p in daily_precip:
            api = k * api + (p if p is not None else 0.0)
        return api

    def _get_monthly_p95(self, city: str, month: int) -> float:
        """Get P95 daily precipitation for city/month from pre-computed percentile data.

        Returns 0.0 if percentile data is unavailable (ceiling-only logic means
        0.0 will never activate — max(0.0, fixed_threshold) = fixed_threshold).
        """
        if city not in self._percentile_data:
            data_dir = Path(__file__).parent.parent.parent.parent / "data"
            path = data_dir / f"{city}_climate_percentiles.json"
            if path.exists():
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    self._percentile_data[city] = raw.get("monthly", {})
                    logger.info(f"Loaded climate percentiles for {city} from {path.name}")
                except Exception as e:
                    logger.warning(f"Failed to load percentiles for {city}: {e}")
                    self._percentile_data[city] = {}
            else:
                logger.warning(f"No percentile data for {city} at {path} — using fixed thresholds")
                self._percentile_data[city] = {}

        month_data = self._percentile_data[city].get(str(month), {})
        return month_data.get("P95", 0.0)

    def _detect_city(self, lat: float, lng: float) -> str:
        """Detect city from coordinates using bounding boxes. Returns 'delhi' as default."""
        for city, bounds in self.CITY_BOUNDS.items():
            if (bounds["min_lat"] <= lat <= bounds["max_lat"] and
                    bounds["min_lng"] <= lng <= bounds["max_lng"]):
                return city
        return "delhi"  # Default calibration

    def _get_calibration(self, city: str) -> dict:
        """Get calibration constants for a city."""
        return self.CITY_CALIBRATION.get(city, self.CITY_CALIBRATION["delhi"])

    async def _fetch_with_retry(
        self,
        url: str,
        params: Dict[str, Any],
        max_attempts: int = MAX_RETRY_ATTEMPTS,
    ) -> Dict[str, Any]:
        """
        Fetch from Open-Meteo API with exponential backoff retry.

        Handles:
        - HTTP 429 (Too Many Requests) - rate limiting
        - HTTP 503 (Service Unavailable) - temporary outages
        - Timeout exceptions - network delays
        - Other transient HTTP errors

        Args:
            url: API endpoint URL
            params: Query parameters
            max_attempts: Maximum retry attempts (default 3)

        Returns:
            JSON response as dictionary

        Raises:
            FHICalculationError: If all retries exhausted
        """
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, params=params)

                    # Handle rate limiting specifically
                    if response.status_code == 429:
                        wait_time = min(2 ** attempt, MAX_RETRY_DELAY)
                        logger.warning(
                            f"Open-Meteo rate limited (429), waiting {wait_time:.1f}s "
                            f"(attempt {attempt + 1}/{max_attempts})"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    # Handle service unavailable
                    if response.status_code == 503:
                        wait_time = min(2 ** attempt, MAX_RETRY_DELAY)
                        logger.warning(
                            f"Open-Meteo service unavailable (503), waiting {wait_time:.1f}s "
                            f"(attempt {attempt + 1}/{max_attempts})"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    response.raise_for_status()
                    return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < max_attempts - 1:
                    wait_time = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.debug(
                        f"Open-Meteo timeout, retrying in {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_time)
                continue

            except httpx.HTTPStatusError as e:
                last_error = e
                # Don't retry client errors (4xx except 429)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise FHICalculationError(f"Client error: {e.response.status_code}")

                if attempt < max_attempts - 1:
                    wait_time = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.debug(
                        f"Open-Meteo HTTP error {e.response.status_code}, retrying in {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    wait_time = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.debug(f"Open-Meteo request failed: {e}, retrying in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                continue

        raise FHICalculationError(f"Failed after {max_attempts} attempts: {last_error}")

    async def calculate_fhi(self, lat: float, lng: float) -> FHIResult:
        """
        Calculate FHI for a location with probability-based correction and rain-gate.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            FHIResult with score, level, color, components, and calibration metadata

        Raises:
            FHICalculationError: If calculation fails
        """
        # Check cache
        cache_key = f"{lat:.4f},{lng:.4f}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            logger.info(f"FHI cache hit for ({lat:.4f}, {lng:.4f})")
            return cached_result

        try:
            # Detect city EARLY for per-city calibration (before correction factor)
            detected_city = self._detect_city(lat, lng)
            calibration = self._get_calibration(detected_city)

            # Fetch data in parallel
            elevation, weather = await asyncio.gather(
                self._fetch_elevation(lat, lng),
                self._fetch_weather(lat, lng),
            )

            # Extract weather components with past_days offset
            # With past_days=14: hourly arrays have 336 past + 72 forecast = 408 values
            # Daily arrays have 14 past + 3 forecast = 17 values
            hourly = weather.get("hourly", {})
            daily = weather.get("daily", {})

            past_hours = self.PAST_DAYS * 24  # 336
            past_daily_count = self.PAST_DAYS  # 14

            # Full arrays (past + forecast)
            precip_hourly_full = hourly.get("precipitation", [0] * (past_hours + 72))
            soil_moisture_full = hourly.get("soil_moisture_0_to_7cm", [0.2] * (past_hours + 72))
            surface_pressure_full = hourly.get("surface_pressure", [1013] * (past_hours + 72))

            # Extract FORECAST-ONLY portion (offset past historical hours)
            precip_hourly = precip_hourly_full[past_hours:]
            soil_moisture = soil_moisture_full[past_hours:]
            surface_pressure = surface_pressure_full[past_hours:]

            # Extract historical daily precipitation for API calculation
            daily_precip_all = daily.get("precipitation_sum", [])
            historical_daily_precip = daily_precip_all[:past_daily_count]

            # Fallback: if daily precipitation_sum unavailable, compute from hourly
            if not historical_daily_precip and len(precip_hourly_full) >= past_hours:
                logger.warning("daily precipitation_sum missing — computing from hourly data")
                historical_daily_precip = []
                for day_idx in range(self.PAST_DAYS):
                    start = day_idx * 24
                    end = start + 24
                    day_vals = precip_hourly_full[start:end]
                    day_sum = sum(v if v is not None else 0.0 for v in day_vals)
                    historical_daily_precip.append(day_sum)

            # Extract precipitation probability from FORECAST-ONLY daily data
            daily_prob_all = daily.get("precipitation_probability_max", [])
            forecast_prob = daily_prob_all[past_daily_count:]  # Skip past days
            precip_prob_max = max([p for p in forecast_prob if p is not None], default=50)

            # Clean forecast precipitation data (None → 0.0)
            precip_hourly_clean = [p if p is not None else 0.0 for p in precip_hourly]

            # For Singapore: try NEA real-time rainfall (5-min resolution, 60x better)
            data_source = "open-meteo"
            if detected_city == "singapore":
                try:
                    from src.domain.services.nea_weather_service import get_nea_weather_service
                    nea_service = get_nea_weather_service()
                    nea_extrapolation = calibration.get("nea_extrapolation_factor", 6.0)
                    nea_result = await nea_service.get_nearest_rainfall(
                        lat, lng, extrapolation_factor=nea_extrapolation
                    )
                    if nea_result and nea_result.rainfall_1h_mm is not None:
                        # Override precipitation with NEA real-time data
                        # Use NEA hourly estimate for the first 24h, keep Open-Meteo for 48h/72h
                        nea_hourly = nea_result.rainfall_1h_mm
                        precip_hourly_clean[:24] = [nea_hourly] * 24
                        data_source = "nea"
                        logger.info(
                            f"NEA rainfall applied for Singapore: {nea_hourly:.1f}mm/h "
                            f"(station {nea_result.station_id}, {nea_result.distance_km}km away)"
                        )
                except Exception as e:
                    logger.warning(f"NEA rainfall failed, using Open-Meteo fallback: {e}")
                    data_source = "open-meteo-fallback"

            # For Yogyakarta: try OpenWeatherMap (minutely precip, better tropical resolution)
            elif detected_city == "yogyakarta" and calibration.get("weather_source") == "owm":
                try:
                    from src.domain.services.owm_weather_service import get_owm_weather_service
                    owm_service = get_owm_weather_service()
                    owm_result = await owm_service.get_weather(lat, lng)
                    if owm_result and owm_result.hourly_precip:
                        # Override hourly precip with OWM data (up to 48h)
                        owm_hours = min(len(owm_result.hourly_precip), 48)
                        precip_hourly_clean[:owm_hours] = owm_result.hourly_precip[:owm_hours]
                        data_source = "owm"
                        logger.info(
                            f"OWM rainfall applied for Yogyakarta: "
                            f"hourly_max={owm_result.hourly_max_intensity:.1f}mm/h, "
                            f"minutely_max={owm_result.minutely_max_intensity:.1f}mm/h, "
                            f"alerts={len(owm_result.alerts)}"
                        )
                except Exception as e:
                    logger.warning(f"OWM weather failed for Yogyakarta, using Open-Meteo fallback: {e}")
                    data_source = "open-meteo-fallback"

            # Calculate 3-day precipitation AFTER any source overrides (NEA, OWM)
            precip_24h = sum(precip_hourly_clean[:24]) if len(precip_hourly_clean) >= 24 else 0
            precip_48h = sum(precip_hourly_clean[24:48]) if len(precip_hourly_clean) >= 48 else 0
            precip_72h = sum(precip_hourly_clean[48:72]) if len(precip_hourly_clean) >= 72 else 0
            precip_3d_raw = precip_24h + precip_48h + precip_72h

            # Per-city correction factor (for metadata — actual math uses _calculate_components)
            base_correction = calibration.get("precip_correction", self.BASE_PRECIP_CORRECTION)
            boost_mult = calibration.get("prob_boost_multiplier", self.PROB_BOOST_MULTIPLIER)
            prob_boost = 1 + (precip_prob_max / 100) * boost_mult
            correction_factor = base_correction * prob_boost

            # Calculate components with per-city calibration and CLEANED precipitation
            components = self._calculate_components(
                elevation=elevation,
                precip_hourly=precip_hourly_clean,
                soil_moisture=soil_moisture,
                surface_pressure=surface_pressure,
                precip_prob_max=precip_prob_max,
                calibration=calibration,
                historical_daily_precip=historical_daily_precip,
                city=detected_city,
            )

            # City-aware wet season modifier (per-city)
            month = datetime.now().month
            city_monsoon_mod = calibration.get("monsoon_modifier", self.MONSOON_MODIFIER)
            T_modifier = city_monsoon_mod if month in calibration["wet_months"] else 1.0

            # Calculate weighted FHI
            fhi_raw = sum(
                self.WEIGHTS[k] * v for k, v in components.items()
            ) * T_modifier

            # Clamp to [0, 1]
            fhi_score = min(1.0, max(0.0, fhi_raw))

            # RAIN-GATE: If negligible rain, cap FHI at LOW
            # Physically justified: low pressure and elevation don't cause flooding without rain
            # Threshold is per-city: tropical cities need higher threshold to filter drizzle
            rain_gated = False
            rain_threshold = calibration.get("rain_gate_mm", self.MIN_RAIN_THRESHOLD_MM)
            if precip_3d_raw < rain_threshold:
                fhi_score = min(fhi_score, self.LOW_FHI_CAP)
                rain_gated = True
                logger.info(
                    f"Rain-gate applied ({detected_city}): {precip_3d_raw:.1f}mm < {rain_threshold}mm threshold"
                )

            # Determine level and color
            if fhi_score < 0.2:
                level, color = "low", "#22c55e"  # green-500
            elif fhi_score < 0.4:
                level, color = "moderate", "#eab308"  # yellow-500
            elif fhi_score < 0.7:
                level, color = "high", "#f97316"  # orange-500
            else:
                level, color = "extreme", "#ef4444"  # red-500

            result = FHIResult(
                fhi_score=fhi_score,
                fhi_level=level,
                fhi_color=color,
                elevation_m=elevation,
                components=components,
                monsoon_modifier=T_modifier,
                rain_gated=rain_gated,
                correction_factor=correction_factor,
                precip_prob_max=precip_prob_max,
                data_source=data_source,
            )

            # Cache result
            self._save_to_cache(cache_key, result)

            logger.info(
                f"FHI calculated for ({lat:.4f}, {lng:.4f}): "
                f"score={fhi_score:.3f}, level={level}, city={detected_city}, "
                f"correction={correction_factor:.2f}x, rain_gated={rain_gated}, "
                f"source={data_source}"
            )

            return result

        except Exception as e:
            logger.error(f"FHI calculation failed for ({lat:.4f}, {lng:.4f}): {e}")
            raise FHICalculationError(f"Failed to calculate FHI: {e}")

    def _calculate_components(
        self,
        elevation: float,
        precip_hourly: list,
        soil_moisture: list,
        surface_pressure: list,
        precip_prob_max: float = 50.0,
        is_urban: bool = True,
        calibration: Optional[dict] = None,
        historical_daily_precip: Optional[List[float]] = None,
        city: str = "delhi",
    ) -> Dict[str, float]:
        """
        Calculate normalized FHI components (0-1) with probability-based correction.

        Urban Calibration:
        1. Apply probability-based correction (per-city) for forecast uncertainty
        2. S component: 70% Antecedent Precipitation Index (14-day decay) + 30% soil moisture
        3. Ceiling-only percentiles for P: monthly P95 can raise threshold, never lower it

        Args:
            elevation: Elevation in meters
            precip_hourly: List of hourly precipitation (mm/h) — FORECAST ONLY (72 values)
            soil_moisture: List of soil moisture (m³/m³) — FORECAST ONLY
            surface_pressure: List of surface pressure (hPa) — FORECAST ONLY
            precip_prob_max: Maximum precipitation probability (0-100%)
            is_urban: Whether to apply urban calibration (default True)
            calibration: Per-city calibration dict
            historical_daily_precip: 14 days of daily precipitation totals (oldest to newest)
            city: Detected city name for percentile lookup

        Returns:
            Dictionary with P, I, S, A, R, E components
        """
        # Filter out None values
        precip_hourly = [p if p is not None else 0.0 for p in precip_hourly]
        soil_moisture = [s if s is not None else 0.2 for s in soil_moisture]
        surface_pressure = [p if p is not None else 1013.0 for p in surface_pressure]

        # Per-city thresholds (fall back to class defaults for Delhi/Bangalore)
        fixed_precip_threshold = calibration.get("precip_threshold_mm", self.PRECIP_THRESHOLD_MM) if calibration else self.PRECIP_THRESHOLD_MM
        intensity_threshold = calibration.get("intensity_threshold_mm_h", self.INTENSITY_THRESHOLD_MM_H) if calibration else self.INTENSITY_THRESHOLD_MM_H
        antecedent_threshold = calibration.get("antecedent_threshold_mm", self.ANTECEDENT_THRESHOLD_MM) if calibration else self.ANTECEDENT_THRESHOLD_MM
        base_correction = calibration.get("precip_correction", self.BASE_PRECIP_CORRECTION) if calibration else self.BASE_PRECIP_CORRECTION
        boost_mult = calibration.get("prob_boost_multiplier", self.PROB_BOOST_MULTIPLIER) if calibration else self.PROB_BOOST_MULTIPLIER
        elev_weight_scale = calibration.get("elev_weight_scale", 1.0) if calibration else 1.0

        # Ceiling-only percentile: P95 can only RAISE threshold, never lower it
        # Reduces false alarms during peak wet months without affecting dry months
        current_month = datetime.now().month
        p95 = self._get_monthly_p95(city, current_month)
        precip_threshold = max(p95, fixed_precip_threshold)
        if p95 > fixed_precip_threshold:
            logger.debug(
                f"Ceiling-only P95 activated for {city} month {current_month}: "
                f"P95={p95:.1f}mm > fixed={fixed_precip_threshold:.1f}mm → threshold={precip_threshold:.1f}mm"
            )

        # Calculate raw precipitation totals (from forecast-only hourly data)
        precip_24h = sum(precip_hourly[:24]) if len(precip_hourly) >= 24 else 0
        precip_48h = sum(precip_hourly[24:48]) if len(precip_hourly) >= 48 else 0
        precip_72h = sum(precip_hourly[48:72]) if len(precip_hourly) >= 72 else 0
        precip_3d = precip_24h + precip_48h + precip_72h

        # Calculate probability-based correction factor (per-city)
        prob_boost = 1 + (precip_prob_max / 100) * boost_mult
        correction_factor = base_correction * prob_boost

        # Apply probability-based correction for forecast uncertainty
        precip_24h_corrected = precip_24h * correction_factor
        precip_48h_corrected = precip_48h * correction_factor
        precip_72h_corrected = precip_72h * correction_factor

        # P: Precipitation forecast (weighted 24h/48h/72h) with probability correction
        # Uses ceiling-only threshold (may be raised during peak wet months)
        P = min(1.0,
                0.5 * (precip_24h_corrected / precip_threshold) +
                0.3 * (precip_48h_corrected / precip_threshold) +
                0.2 * (precip_72h_corrected / precip_threshold)
        )

        # I: Intensity (hourly max) with probability correction
        hourly_max = max(precip_hourly[:24]) if precip_hourly else 0
        hourly_max_corrected = hourly_max * correction_factor
        I = min(1.0, hourly_max_corrected / intensity_threshold)

        # S: Saturation Component — Antecedent Precipitation Index (API) + ERA5 soil moisture
        # API captures 14-day exponential decay: recent rain weighted more than old rain
        # Soil moisture from ERA5 preserved at 30% for satellite-based signal
        api_k = calibration.get("api_decay_k", 0.90) if calibration else 0.90
        api_threshold = calibration.get("api_threshold", 80.0) if calibration else 80.0

        avg_soil = sum(soil_moisture[:24]) / 24 if soil_moisture else 0.2
        soil_norm = min(1.0, avg_soil / self.SOIL_SATURATION_MAX)

        if historical_daily_precip and len(historical_daily_precip) >= 3:
            # Use 14-day API (upgraded from crude 3-day proxy)
            api_value = self.compute_api(historical_daily_precip, k=api_k)
            api_norm = min(1.0, api_value / api_threshold)

            if is_urban:
                S = 0.7 * api_norm + 0.3 * soil_norm
            else:
                S = 0.3 * api_norm + 0.7 * soil_norm
        else:
            # Fallback: crude 3-day proxy (original behavior)
            logger.warning(f"API fallback: using crude 3-day proxy (got {len(historical_daily_precip or [])} days)")
            antecedent_proxy = min(1.0, precip_3d / self.URBAN_SATURATION_THRESHOLD_MM)
            if is_urban:
                S = 0.7 * antecedent_proxy + 0.3 * soil_norm
            else:
                S = 0.3 * antecedent_proxy + 0.7 * soil_norm

        # A: Antecedent conditions (total 3-day precipitation) with probability correction
        # Distinct from S: A measures short-term 3-day burst, S measures 14-day long-term wetness
        precip_3d_corrected = precip_3d * correction_factor
        A = min(1.0, precip_3d_corrected / antecedent_threshold)

        # R: Runoff Potential (pressure-based)
        avg_pressure = sum(surface_pressure[:24]) / 24 if surface_pressure else 1013
        # Lower pressure = higher runoff potential
        R = min(1.0, max(0.0, (self.PRESSURE_BASELINE_HPA - avg_pressure) / 30.0))

        # E: Elevation Risk (inverted: low elevation = high risk)
        # Use city-specific elevation bounds if calibration provided
        elev_min = calibration["elev_min"] if calibration else self.DELHI_ELEV_MIN
        elev_max = calibration["elev_max"] if calibration else self.DELHI_ELEV_MAX
        elev_range = elev_max - elev_min
        if elev_range <= 0:
            elev_range = 1  # Prevent division by zero
        elev_clamped = max(elev_min, min(elev_max, elevation))
        E_raw = 1 - (elev_clamped - elev_min) / elev_range
        E = min(1.0, E_raw * elev_weight_scale)  # Per-city scaling, clamped to [0,1]

        return {
            "P": P,
            "I": I,
            "S": S,
            "A": A,
            "R": R,
            "E": E,
        }

    async def _fetch_elevation(self, lat: float, lng: float) -> float:
        """
        Fetch elevation from Open-Meteo with automatic retry.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Elevation in meters (default 220m for Delhi if API fails)
        """
        try:
            data = await self._fetch_with_retry(
                self.ELEVATION_URL,
                params={"latitude": lat, "longitude": lng}
            )
            elevation_list = data.get("elevation", [220])
            return elevation_list[0] if elevation_list else 220
        except FHICalculationError:
            # Return city-appropriate default elevation
            city = self._detect_city(lat, lng)
            default_elev = self._get_calibration(city).get("default_elev", 220)
            logger.warning(f"Elevation fetch failed for ({lat:.4f}, {lng:.4f}), using default {default_elev}m ({city})")
            return float(default_elev)

    async def _fetch_weather(self, lat: float, lng: float) -> Dict:
        """
        Fetch weather data from Open-Meteo with automatic retry.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Weather data dictionary with hourly and daily data
        """
        params = {
            "latitude": lat,
            "longitude": lng,
            "hourly": "precipitation,soil_moisture_0_to_7cm,surface_pressure",
            "daily": "precipitation_probability_max,precipitation_sum",
            "past_days": self.PAST_DAYS,   # 14 days historical for API calculation
            "forecast_days": 3,
            "timezone": "auto",
        }

        return await self._fetch_with_retry(self.FORECAST_URL, params=params)

    def _get_from_cache(self, cache_key: str) -> Optional[FHIResult]:
        """Get result from cache if valid. Uses per-city TTL."""
        if cache_key not in self._cache:
            return None

        result, cached_at = self._cache[cache_key]

        # Per-city cache TTL: detect city from cache_key coordinates
        try:
            lat, lng = map(float, cache_key.split(","))
            city = self._detect_city(lat, lng)
            calibration = self._get_calibration(city)
            ttl = calibration.get("fhi_cache_ttl_seconds", self.CACHE_TTL_SECONDS)
        except (ValueError, KeyError):
            ttl = self.CACHE_TTL_SECONDS

        age_seconds = (datetime.now() - cached_at).total_seconds()
        if age_seconds > ttl:
            del self._cache[cache_key]
            logger.debug(f"FHI cache expired for {cache_key} (TTL={ttl}s)")
            return None

        return result

    def _save_to_cache(self, cache_key: str, result: FHIResult) -> None:
        """Save result to cache."""
        self._cache[cache_key] = (result, datetime.now())

    def clear_cache(self) -> int:
        """Clear cache and return number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} FHI cache entries")
        return count


# Singleton instance
_fhi_calculator: Optional[FHICalculator] = None


def get_fhi_calculator() -> FHICalculator:
    """Get singleton FHI calculator instance."""
    global _fhi_calculator
    if _fhi_calculator is None:
        _fhi_calculator = FHICalculator()
    return _fhi_calculator


async def calculate_fhi_for_location(lat: float, lng: float) -> Dict:
    """
    Calculate FHI for a location (convenience function).

    Args:
        lat: Latitude
        lng: Longitude

    Returns:
        Dictionary with FHI result, or default values if calculation fails
    """
    calculator = get_fhi_calculator()

    try:
        result = await calculator.calculate_fhi(lat, lng)
        return result.to_dict()
    except Exception as e:
        logger.warning(f"FHI calculation failed, returning defaults: {e}")
        # Return safe defaults on error
        return {
            "fhi_score": 0.25,
            "fhi_level": "unknown",
            "fhi_color": "#9ca3af",  # gray-400
            "elevation_m": 220.0,
            "components": {
                "P": 0.0,
                "I": 0.0,
                "S": 0.0,
                "A": 0.0,
                "R": 0.0,
                "E": 0.5,
            },
            "monsoon_modifier": 1.0,
            "rain_gated": False,
            "correction_factor": 1.5,
            "precip_prob_max": 50,
        }
