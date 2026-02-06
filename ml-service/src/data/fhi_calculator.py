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

    # Delhi elevation bounds (meters)
    DELHI_ELEV_MIN = 190
    DELHI_ELEV_MAX = 320

    # Monsoon months
    MONSOON_MONTHS = [6, 7, 8, 9]  # June-September
    MONSOON_MODIFIER = 1.2

    # Cache settings
    CACHE_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, timeout_seconds: float = 10.0):
        """Initialize FHI calculator."""
        self._timeout = timeout_seconds
        self._cache: Dict[str, tuple] = {}  # (FHIResult, timestamp)

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
            # Fetch data in parallel
            elevation, weather = await asyncio.gather(
                self._fetch_elevation(lat, lng),
                self._fetch_weather(lat, lng),
            )

            # Extract weather components
            hourly = weather.get("hourly", {})
            daily = weather.get("daily", {})

            precip_hourly = hourly.get("precipitation", [0] * 72)
            soil_moisture = hourly.get("soil_moisture_0_to_7cm", [0.2] * 72)
            surface_pressure = hourly.get("surface_pressure", [1013] * 72)

            # Extract precipitation probability from daily data
            precip_prob_values = daily.get("precipitation_probability_max", [])
            precip_prob_max = max([p for p in precip_prob_values if p is not None], default=50)

            # Calculate probability-based correction factor
            # Range: 1.5x (0% prob) to 2.25x (100% prob)
            prob_boost = 1 + (precip_prob_max / 100) * self.PROB_BOOST_MULTIPLIER
            correction_factor = self.BASE_PRECIP_CORRECTION * prob_boost

            # Calculate raw 3-day precipitation for rain-gate check
            precip_hourly_clean = [p if p is not None else 0.0 for p in precip_hourly]
            precip_24h = sum(precip_hourly_clean[:24]) if len(precip_hourly_clean) >= 24 else 0
            precip_48h = sum(precip_hourly_clean[24:48]) if len(precip_hourly_clean) >= 48 else 0
            precip_72h = sum(precip_hourly_clean[48:72]) if len(precip_hourly_clean) >= 72 else 0
            precip_3d_raw = precip_24h + precip_48h + precip_72h

            # Calculate components with probability-based correction
            components = self._calculate_components(
                elevation=elevation,
                precip_hourly=precip_hourly,
                soil_moisture=soil_moisture,
                surface_pressure=surface_pressure,
                precip_prob_max=precip_prob_max,
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

            # RAIN-GATE: If negligible rain, cap FHI at LOW
            # Physically justified: low pressure and elevation don't cause flooding without rain
            rain_gated = False
            if precip_3d_raw < self.MIN_RAIN_THRESHOLD_MM:
                fhi_score = min(fhi_score, self.LOW_FHI_CAP)
                rain_gated = True
                logger.info(
                    f"Rain-gate applied: {precip_3d_raw:.1f}mm < {self.MIN_RAIN_THRESHOLD_MM}mm threshold"
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
                f"FHI calculated for ({lat:.4f}, {lng:.4f}): "
                f"score={fhi_score:.3f}, level={level}, "
                f"correction={correction_factor:.2f}x, rain_gated={rain_gated}"
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
    ) -> Dict[str, float]:
        """
        Calculate normalized FHI components (0-1) with probability-based correction.

        Urban Calibration:
        1. Apply probability-based correction (1.5x to 2.25x) for forecast uncertainty
        2. Use hybrid saturation: 70% antecedent rainfall + 30% soil moisture

        Args:
            elevation: Elevation in meters
            precip_hourly: List of hourly precipitation (mm/h)
            soil_moisture: List of soil moisture (m³/m³)
            surface_pressure: List of surface pressure (hPa)
            precip_prob_max: Maximum precipitation probability (0-100%)
            is_urban: Whether to apply urban calibration (default True for Delhi)

        Returns:
            Dictionary with P, I, S, A, R, E components
        """
        # Filter out None values and convert to list
        precip_hourly = [p if p is not None else 0.0 for p in precip_hourly]
        soil_moisture = [s if s is not None else 0.2 for s in soil_moisture]
        surface_pressure = [p if p is not None else 1013.0 for p in surface_pressure]

        # Calculate raw precipitation totals
        precip_24h = sum(precip_hourly[:24]) if len(precip_hourly) >= 24 else 0
        precip_48h = sum(precip_hourly[24:48]) if len(precip_hourly) >= 48 else 0
        precip_72h = sum(precip_hourly[48:72]) if len(precip_hourly) >= 72 else 0
        precip_3d = precip_24h + precip_48h + precip_72h

        # Calculate probability-based correction factor
        # Range: 1.5x (0% prob) to 2.25x (100% prob)
        prob_boost = 1 + (precip_prob_max / 100) * self.PROB_BOOST_MULTIPLIER
        correction_factor = self.BASE_PRECIP_CORRECTION * prob_boost

        # Apply probability-based correction for forecast uncertainty
        precip_24h_corrected = precip_24h * correction_factor
        precip_48h_corrected = precip_48h * correction_factor
        precip_72h_corrected = precip_72h * correction_factor

        # P: Precipitation forecast (weighted 24h/48h/72h) with probability correction
        P = min(1.0,
                0.5 * (precip_24h_corrected / self.PRECIP_THRESHOLD_MM) +
                0.3 * (precip_48h_corrected / self.PRECIP_THRESHOLD_MM) +
                0.2 * (precip_72h_corrected / self.PRECIP_THRESHOLD_MM)
        )

        # I: Intensity (hourly max) with probability correction
        hourly_max = max(precip_hourly[:24]) if precip_hourly else 0
        hourly_max_corrected = hourly_max * correction_factor
        I = min(1.0, hourly_max_corrected / self.INTENSITY_THRESHOLD_MM_H)

        # S: Saturation Component (HYBRID URBAN-CALIBRATED)
        # For urban areas: 70% antecedent rainfall proxy + 30% soil moisture
        # This captures both drainage saturation and regional moisture conditions
        antecedent_proxy = min(1.0, precip_3d / self.URBAN_SATURATION_THRESHOLD_MM)
        avg_soil = sum(soil_moisture[:24]) / 24 if soil_moisture else 0.2
        soil_norm = min(1.0, avg_soil / self.SOIL_SATURATION_MAX)

        if is_urban:
            # Hybrid: 70% drainage proxy + 30% regional soil moisture
            S = 0.7 * antecedent_proxy + 0.3 * soil_norm
        else:
            # Rural: 30% drainage proxy + 70% soil moisture
            S = 0.3 * antecedent_proxy + 0.7 * soil_norm

        # A: Antecedent conditions (total 3-day precipitation) with probability correction
        precip_3d_corrected = precip_3d * correction_factor
        A = min(1.0, precip_3d_corrected / self.ANTECEDENT_THRESHOLD_MM)

        # R: Runoff Potential (pressure-based)
        avg_pressure = sum(surface_pressure[:24]) / 24 if surface_pressure else 1013
        # Lower pressure = higher runoff potential
        R = min(1.0, max(0.0, (self.PRESSURE_BASELINE_HPA - avg_pressure) / 30.0))

        # E: Elevation Risk (inverted: low elevation = high risk)
        elev_clamped = max(self.DELHI_ELEV_MIN, min(self.DELHI_ELEV_MAX, elevation))
        E = 1 - (elev_clamped - self.DELHI_ELEV_MIN) / (self.DELHI_ELEV_MAX - self.DELHI_ELEV_MIN)

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
            "forecast_days": 3,
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
