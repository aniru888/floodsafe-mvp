"""
Weather snapshot service for ML pipeline report enrichment.

Captures weather conditions at report creation time via Open-Meteo API.
Non-blocking: failures are logged but never block report creation.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherSnapshotService:
    """Captures weather conditions at report time for ML pipeline enrichment."""

    def __init__(self, timeout: float = 5.0):
        self._timeout = timeout

    async def get_snapshot(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        Fetch current weather conditions from Open-Meteo.

        Returns a flat dict of weather metrics, or None on failure.
        Failures are logged (CLAUDE.md Rule #14) but never block report creation.
        """
        params = {
            "latitude": lat,
            "longitude": lng,
            "hourly": "precipitation,temperature_2m,relative_humidity_2m,surface_pressure",
            "daily": "precipitation_sum,precipitation_probability_max",
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "auto",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(OPEN_METEO_FORECAST_URL, params=params)
                response.raise_for_status()
                data = response.json()

            return self._extract_snapshot(data)

        except httpx.TimeoutException:
            logger.error(f"Weather snapshot TIMEOUT for ({lat}, {lng}) after {self._timeout}s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Weather snapshot HTTP {e.response.status_code} for ({lat}, {lng}): {e}")
            return None
        except Exception as e:
            logger.error(f"Weather snapshot failed for ({lat}, {lng}): {e}")
            return None

    def _extract_snapshot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract flat weather metrics from Open-Meteo response."""
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})

        # Get hourly arrays
        precip_hourly = hourly.get("precipitation", [])
        temp_hourly = hourly.get("temperature_2m", [])
        humidity_hourly = hourly.get("relative_humidity_2m", [])
        pressure_hourly = hourly.get("surface_pressure", [])

        # Get daily arrays
        precip_daily = daily.get("precipitation_sum", [])
        precip_prob_daily = daily.get("precipitation_probability_max", [])

        # Current hour = last element of hourly data (or last available)
        current_precip = precip_hourly[-1] if precip_hourly else 0.0
        current_temp = temp_hourly[-1] if temp_hourly else None
        current_humidity = humidity_hourly[-1] if humidity_hourly else None
        current_pressure = pressure_hourly[-1] if pressure_hourly else None

        # Max hourly intensity in last 24 hours
        last_24h = precip_hourly[-24:] if len(precip_hourly) >= 24 else precip_hourly
        hourly_intensity_max = max(last_24h) if last_24h else 0.0

        # Rainfall accumulation: last 3 and 7 days from daily sums
        rainfall_3d = sum(precip_daily[-3:]) if len(precip_daily) >= 3 else sum(precip_daily)
        rainfall_7d = sum(precip_daily[-7:]) if len(precip_daily) >= 7 else sum(precip_daily)

        # Max daily probability
        max_prob = max(precip_prob_daily) if precip_prob_daily else 0

        return {
            "precipitation_mm": float(current_precip) if current_precip is not None else 0.0,
            "precipitation_probability": int(max_prob) if max_prob is not None else 0,
            "hourly_intensity_max": float(hourly_intensity_max) if hourly_intensity_max is not None else 0.0,
            "surface_pressure_hpa": float(current_pressure) if current_pressure is not None else None,
            "temperature_c": float(current_temp) if current_temp is not None else None,
            "relative_humidity": int(current_humidity) if current_humidity is not None else None,
            "rainfall_3d_mm": float(rainfall_3d),
            "rainfall_7d_mm": float(rainfall_7d),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
