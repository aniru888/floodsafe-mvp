"""
Flood Hazard Index (FHI) Calculator.

IMPORTANT: This is a CUSTOM HEURISTIC formula, NOT from published academic research.
The weights (0.35, 0.18, etc.) are empirically tuned for Delhi conditions.
See CLAUDE.md @hotspots for documentation.

FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T_modifier

Components:
- P (35%): Precipitation forecast (with probability-based correction)
- I (18%): Intensity (hourly max)
- S (12%): Soil Saturation from Open-Meteo (hybrid urban-calibrated)
- A (12%): Antecedent conditions
- R (8%): Runoff Potential (pressure-based)
- E (15%): Elevation Risk (inverted: low elevation = high risk)
- T_modifier: 1.2 during monsoon (June-Sept), else 1.0

Key Calibrations for Urban Delhi:
1. Probability-based correction: 1.5x to 2.25x based on forecast confidence
2. Rain-gate: If <5mm in 3 days, cap FHI at LOW (no flood without rain)
3. Soil Saturation Proxy: Hybrid 70% antecedent + 30% soil moisture
"""

import httpx
import asyncio
from datetime import datetime
from typing import Dict, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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

    # Per-city elevation bounds (meters) for E component normalization
    # Each city needs its own range to properly normalize low vs high elevation risk
    CITY_ELEVATION_BOUNDS = {
        "delhi":      {"min": 190, "max": 320},
        "bangalore":  {"min": 800, "max": 960},
        "yogyakarta": {"min": 50,  "max": 400},
        "singapore":  {"min": 0,   "max": 160},
        "indore":     {"min": 530, "max": 620},
    }
    # Fallback for unknown cities
    DEFAULT_ELEV_MIN = 0
    DEFAULT_ELEV_MAX = 500

    # Monsoon months
    MONSOON_MONTHS = [6, 7, 8, 9]  # June-September
    MONSOON_MODIFIER = 1.2

    # Cache settings
    CACHE_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, timeout_seconds: float = 10.0):
        """Initialize FHI calculator."""
        self._timeout = timeout_seconds
        self._cache: Dict[str, tuple] = {}  # (FHIResult, timestamp)

    async def calculate_fhi(
        self, lat: float, lng: float, city: str = "delhi"
    ) -> FHIResult:
        """
        Calculate FHI for a location with probability-based correction and rain-gate.

        Now correctly splits past (observed) vs forecast (predicted) data:
        - Past 72h: Used for Antecedent (A) and Soil Saturation (S) — what already happened
        - Forecast 72h: Used for Precipitation (P) and Intensity (I) — what's coming

        Args:
            lat: Latitude
            lng: Longitude
            city: City name for per-city calibration (elevation bounds, etc.)

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
            # Fetch data in parallel
            elevation, weather = await asyncio.gather(
                self._fetch_elevation(lat, lng),
                self._fetch_weather(lat, lng),
            )

            # Extract weather components
            # With past_days=3 + forecast_days=3, hourly arrays are 144 entries:
            # [0:72] = past 3 days (observed), [72:144] = forecast 3 days (predicted)
            hourly = weather.get("hourly", {})
            daily = weather.get("daily", {})

            precip_all = hourly.get("precipitation", [0] * 144)
            soil_moisture_all = hourly.get("soil_moisture_0_to_7cm", [0.2] * 144)
            surface_pressure_all = hourly.get("surface_pressure", [1013] * 144)

            # Split into past (observed) and forecast (predicted)
            past_hours = min(72, len(precip_all) // 2) if len(precip_all) > 72 else 0
            precip_past = precip_all[:past_hours] if past_hours > 0 else []
            precip_forecast = precip_all[past_hours:] if past_hours > 0 else precip_all
            soil_moisture_past = soil_moisture_all[:past_hours] if past_hours > 0 else []
            surface_pressure_forecast = surface_pressure_all[past_hours:] if past_hours > 0 else surface_pressure_all

            # Extract precipitation probability from daily forecast data
            precip_prob_values = daily.get("precipitation_probability_max", [])
            # Only use forecast days (last 3 of 6 daily values)
            forecast_probs = precip_prob_values[3:] if len(precip_prob_values) > 3 else precip_prob_values
            precip_prob_max = max([p for p in forecast_probs if p is not None], default=50)

            # Calculate probability-based correction factor
            # Range: 1.5x (0% prob) to 2.25x (100% prob)
            prob_boost = 1 + (precip_prob_max / 100) * self.PROB_BOOST_MULTIPLIER
            correction_factor = self.BASE_PRECIP_CORRECTION * prob_boost

            # Rain-gate uses BOTH past observed + forecast predicted rainfall
            precip_past_clean = [p if p is not None else 0.0 for p in precip_past]
            precip_forecast_clean = [p if p is not None else 0.0 for p in precip_forecast[:72]]
            past_3d_total = sum(precip_past_clean)
            forecast_3d_total = sum(precip_forecast_clean)
            # Rain-gate: check if there's meaningful rain in either past or forecast
            rain_total_for_gate = max(past_3d_total, forecast_3d_total)

            # Calculate components with split past/forecast data
            components = self._calculate_components(
                elevation=elevation,
                precip_forecast=precip_forecast,
                precip_past=precip_past,
                soil_moisture_past=soil_moisture_past,
                surface_pressure=surface_pressure_forecast,
                precip_prob_max=precip_prob_max,
                city=city,
            )

            # Monsoon modifier
            month = datetime.now().month
            T_modifier = self.MONSOON_MODIFIER if month in self.MONSOON_MONTHS else 1.0

            # Calculate weighted FHI
            fhi_raw = sum(
                self.WEIGHTS[k] * v for k, v in components.items()
            ) * T_modifier

            # Clamp to [0, 1]
            fhi_score = min(1.0, max(0.0, fhi_raw))

            # RAIN-GATE: If negligible rain in both past and forecast, cap FHI at LOW
            # Physically justified: low pressure and elevation don't cause flooding without rain
            rain_gated = False
            if rain_total_for_gate < self.MIN_RAIN_THRESHOLD_MM:
                fhi_score = min(fhi_score, self.LOW_FHI_CAP)
                rain_gated = True
                logger.info(
                    f"Rain-gate applied: past={past_3d_total:.1f}mm, "
                    f"forecast={forecast_3d_total:.1f}mm < {self.MIN_RAIN_THRESHOLD_MM}mm"
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
            )

            # Cache result
            self._save_to_cache(cache_key, result)

            logger.info(
                f"FHI calculated for ({lat:.4f}, {lng:.4f}, city={city}): "
                f"score={fhi_score:.3f}, level={level}, "
                f"correction={correction_factor:.2f}x, rain_gated={rain_gated}, "
                f"past_rain={past_3d_total:.1f}mm, forecast_rain={forecast_3d_total:.1f}mm"
            )

            return result

        except Exception as e:
            logger.error(f"FHI calculation failed for ({lat:.4f}, {lng:.4f}): {e}")
            raise FHICalculationError(f"Failed to calculate FHI: {e}")

    def _calculate_components(
        self,
        elevation: float,
        precip_forecast: list,
        precip_past: list,
        soil_moisture_past: list,
        surface_pressure: list,
        precip_prob_max: float = 50.0,
        city: str = "delhi",
        is_urban: bool = True,
    ) -> Dict[str, float]:
        """
        Calculate normalized FHI components (0-1).

        Key design decisions:
        1. P and I use FORECAST data (what's coming) with probability correction
        2. A and S use PAST OBSERVED data (what already fell) — NO correction needed
        3. Probability correction only applies to forecast-based components (P, I)
           to avoid triple-counting uncertainty
        4. Elevation bounds are per-city, not hardcoded to Delhi

        Args:
            elevation: Elevation in meters
            precip_forecast: List of hourly forecast precipitation (mm/h), up to 72h
            precip_past: List of hourly past observed precipitation (mm/h), up to 72h
            soil_moisture_past: List of past soil moisture (m³/m³)
            surface_pressure: List of forecast surface pressure (hPa)
            precip_prob_max: Maximum precipitation probability (0-100%)
            city: City name for per-city calibration
            is_urban: Whether to apply urban calibration (default True)

        Returns:
            Dictionary with P, I, S, A, R, E components
        """
        # Clean None values
        precip_forecast = [p if p is not None else 0.0 for p in precip_forecast]
        precip_past = [p if p is not None else 0.0 for p in precip_past]
        soil_moisture_past = [s if s is not None else 0.2 for s in soil_moisture_past]
        surface_pressure = [p if p is not None else 1013.0 for p in surface_pressure]

        # --- FORECAST-BASED COMPONENTS (P, I) ---
        # These use predicted rainfall with probability correction

        # Calculate probability-based correction factor (only for forecast components)
        prob_boost = 1 + (precip_prob_max / 100) * self.PROB_BOOST_MULTIPLIER
        correction_factor = self.BASE_PRECIP_CORRECTION * prob_boost

        # Forecast precipitation totals (next 72h)
        fc_24h = sum(precip_forecast[:24]) if len(precip_forecast) >= 24 else sum(precip_forecast)
        fc_48h = sum(precip_forecast[24:48]) if len(precip_forecast) >= 48 else 0
        fc_72h = sum(precip_forecast[48:72]) if len(precip_forecast) >= 72 else 0

        # P: Precipitation forecast (weighted 24h/48h/72h) with correction
        fc_24h_corrected = fc_24h * correction_factor
        fc_48h_corrected = fc_48h * correction_factor
        fc_72h_corrected = fc_72h * correction_factor
        P = min(1.0,
                0.5 * (fc_24h_corrected / self.PRECIP_THRESHOLD_MM) +
                0.3 * (fc_48h_corrected / self.PRECIP_THRESHOLD_MM) +
                0.2 * (fc_72h_corrected / self.PRECIP_THRESHOLD_MM)
        )

        # I: Intensity (hourly max from forecast) with correction
        hourly_max = max(precip_forecast[:24]) if precip_forecast else 0
        hourly_max_corrected = hourly_max * correction_factor
        I = min(1.0, hourly_max_corrected / self.INTENSITY_THRESHOLD_MM_H)

        # --- PAST-OBSERVED COMPONENTS (A, S) ---
        # These use actual observed data — NO correction factor needed

        # Past precipitation totals (last 72h observed)
        past_3d = sum(precip_past)

        # A: Antecedent conditions — actual observed 3-day rainfall (no correction!)
        A = min(1.0, past_3d / self.ANTECEDENT_THRESHOLD_MM)

        # S: Saturation Component (HYBRID URBAN-CALIBRATED)
        # Uses OBSERVED past rainfall and soil moisture, not forecast
        antecedent_proxy = min(1.0, past_3d / self.URBAN_SATURATION_THRESHOLD_MM)
        avg_soil = (
            sum(soil_moisture_past[-24:]) / min(24, len(soil_moisture_past))
            if soil_moisture_past else 0.2
        )
        soil_norm = min(1.0, avg_soil / self.SOIL_SATURATION_MAX)

        if is_urban:
            S = 0.7 * antecedent_proxy + 0.3 * soil_norm
        else:
            S = 0.3 * antecedent_proxy + 0.7 * soil_norm

        # --- PHYSICAL COMPONENTS (R, E) ---

        # R: Runoff Potential (pressure-based, from forecast)
        avg_pressure = sum(surface_pressure[:24]) / 24 if surface_pressure else 1013
        R = min(1.0, max(0.0, (self.PRESSURE_BASELINE_HPA - avg_pressure) / 30.0))

        # E: Elevation Risk (per-city bounds, inverted: low elevation = high risk)
        city_key = city.lower().strip()
        bounds = self.CITY_ELEVATION_BOUNDS.get(city_key, {
            "min": self.DEFAULT_ELEV_MIN,
            "max": self.DEFAULT_ELEV_MAX,
        })
        elev_min = bounds["min"]
        elev_max = bounds["max"]
        elev_range = elev_max - elev_min
        if elev_range > 0:
            elev_clamped = max(elev_min, min(elev_max, elevation))
            E = 1 - (elev_clamped - elev_min) / elev_range
        else:
            E = 0.5  # Flat terrain — neutral risk

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
        Fetch elevation from Open-Meteo.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Elevation in meters
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                self.ELEVATION_URL,
                params={"latitude": lat, "longitude": lng}
            )
            response.raise_for_status()
            data = response.json()

            elevation_list = data.get("elevation", [220])
            return elevation_list[0] if elevation_list else 220

    async def _fetch_weather(self, lat: float, lng: float) -> Dict:
        """
        Fetch weather data from Open-Meteo.

        Requests both past 3 days (observed) and forecast 3 days (predicted).
        Past data is used for antecedent conditions (A) and soil saturation (S).
        Forecast data is used for precipitation (P) and intensity (I).

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
            "daily": "precipitation_probability_max",  # For probability-based correction
            "past_days": 3,       # Observed past data for antecedent/saturation
            "forecast_days": 3,   # Forecast data for precipitation/intensity
            "timezone": "auto",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(self.FORECAST_URL, params=params)
            response.raise_for_status()
            return response.json()

    def _get_from_cache(self, cache_key: str) -> Optional[FHIResult]:
        """Get result from cache if valid."""
        if cache_key not in self._cache:
            return None

        result, cached_at = self._cache[cache_key]

        # Check if cache is still valid
        age_seconds = (datetime.now() - cached_at).total_seconds()
        if age_seconds > self.CACHE_TTL_SECONDS:
            del self._cache[cache_key]
            logger.debug(f"FHI cache expired for {cache_key}")
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


async def calculate_fhi_for_location(
    lat: float, lng: float, city: str = "delhi"
) -> Dict:
    """
    Calculate FHI for a location (convenience function).

    Args:
        lat: Latitude
        lng: Longitude
        city: City name for per-city calibration

    Returns:
        Dictionary with FHI result, or default values if calculation fails
    """
    calculator = get_fhi_calculator()

    try:
        result = await calculator.calculate_fhi(lat, lng, city=city)
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
