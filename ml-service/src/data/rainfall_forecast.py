"""
Open-Meteo Rainfall Forecast Fetcher.

API: https://api.open-meteo.com/v1/forecast
Free, no API key required.

CRITICAL: This fetcher does NOT return zeros for missing data.
If data is unavailable, it raises RainfallForecastError.
"""

import httpx
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
import logging
from dataclasses import dataclass, asdict
import asyncio
import time

from .validation import MeteorologicalValidator, ValidationError

logger = logging.getLogger(__name__)


class RainfallForecastError(Exception):
    """Raised when rainfall forecast data is unavailable or invalid."""
    pass


class RainfallDataValidationError(Exception):
    """Raised when forecast data fails validation checks."""
    pass


@dataclass
class RainfallForecast:
    """Validated rainfall forecast data."""
    latitude: float
    longitude: float
    rain_forecast_24h: float  # mm
    rain_forecast_48h: float  # mm
    rain_forecast_72h: float  # mm
    rain_forecast_total_3d: float  # mm
    probability_max_3d: float  # 0-100%
    hourly_max: float  # mm/h (peak intensity)
    fetched_at: datetime
    source: str = "open-meteo"

    def validate(self) -> None:
        """
        Validate forecast data is within expected ranges.

        Raises:
            RainfallDataValidationError: If validation fails
        """
        # Validate coordinates
        coord_result = MeteorologicalValidator.validate_coordinates(
            self.latitude, self.longitude
        )
        if not coord_result.is_valid:
            raise RainfallDataValidationError(
                f"Invalid coordinates: {'; '.join(coord_result.errors)}"
            )

        # Validate precipitation values
        precip_fields = [
            ('rain_forecast_24h', 'daily'),
            ('rain_forecast_48h', 'daily'),
            ('rain_forecast_72h', 'daily'),
            ('rain_forecast_total_3d', 'total'),
        ]

        all_errors = []
        all_warnings = []

        for field_name, period in precip_fields:
            value = getattr(self, field_name)
            result = MeteorologicalValidator.validate_precipitation(
                value, field_name, period
            )
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        # Validate hourly intensity
        intensity_result = MeteorologicalValidator.validate_intensity(
            self.hourly_max, "hourly_max"
        )
        all_errors.extend(intensity_result.errors)
        all_warnings.extend(intensity_result.warnings)

        # Validate probability
        prob_result = MeteorologicalValidator.validate_probability(
            self.probability_max_3d, "probability_max_3d"
        )
        all_errors.extend(prob_result.errors)
        all_warnings.extend(prob_result.warnings)

        # Log warnings
        for warning in all_warnings:
            logger.warning(f"Forecast validation warning: {warning}")

        # Raise if errors found
        if all_errors:
            raise RainfallDataValidationError(
                f"Forecast validation failed: {'; '.join(all_errors)}"
            )

    def get_intensity_category(self) -> str:
        """
        Classify using IMD (India Meteorological Department) standards.

        Returns:
            Category: light/moderate/heavy/very_heavy/extremely_heavy
        """
        daily = self.rain_forecast_24h

        if daily < 7.5:
            return "light"
        elif daily < 35.5:
            return "moderate"
        elif daily < 64.4:
            return "heavy"
        elif daily < 124.4:
            return "very_heavy"
        else:
            return "extremely_heavy"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['fetched_at'] = self.fetched_at.isoformat()
        data['intensity_category'] = self.get_intensity_category()
        return data


class RainfallForecastFetcher:
    """Fetch rainfall forecasts from Open-Meteo API."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    CACHE_TTL_SECONDS = 3600  # 1 hour
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 1.0

    # Open-Meteo parameters
    HOURLY_PARAMS = ["precipitation", "rain", "showers"]
    DAILY_PARAMS = ["precipitation_sum", "precipitation_hours", "precipitation_probability_max"]

    def __init__(self, timeout_seconds: float = 30.0, cache_enabled: bool = True):
        """
        Initialize fetcher.

        Args:
            timeout_seconds: HTTP request timeout
            cache_enabled: Enable in-memory caching
        """
        self._cache: Dict[str, Tuple[RainfallForecast, datetime]] = {}
        self._timeout = timeout_seconds
        self._cache_enabled = cache_enabled

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 3,
        force_refresh: bool = False
    ) -> RainfallForecast:
        """
        Get rainfall forecast for a location.

        Args:
            latitude: Latitude in degrees (-90 to 90)
            longitude: Longitude in degrees (-180 to 180)
            forecast_days: Number of days to forecast (1-16)
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            RainfallForecast object with validated data

        Raises:
            RainfallForecastError: If data unavailable or API fails
            RainfallDataValidationError: If data fails validation

        Example:
            >>> fetcher = RainfallForecastFetcher()
            >>> forecast = fetcher.get_forecast(28.6139, 77.2090)
            >>> print(f"Next 24h: {forecast.rain_forecast_24h}mm")
            >>> print(f"Category: {forecast.get_intensity_category()}")
        """
        # Validate inputs
        if not (1 <= forecast_days <= 16):
            raise RainfallForecastError(
                f"forecast_days must be 1-16 (got {forecast_days})"
            )

        coord_result = MeteorologicalValidator.validate_coordinates(latitude, longitude)
        if not coord_result.is_valid:
            raise RainfallForecastError(
                f"Invalid coordinates: {'; '.join(coord_result.errors)}"
            )

        # Check cache
        cache_key = f"{latitude:.4f},{longitude:.4f},{forecast_days}"
        if not force_refresh and self._cache_enabled:
            cached_forecast = self._get_from_cache(cache_key)
            if cached_forecast is not None:
                logger.info(f"Cache hit for rainfall forecast: {cache_key}")
                return cached_forecast

        # Fetch with retry logic
        forecast = self._fetch_with_retry(latitude, longitude, forecast_days)

        # Validate
        try:
            forecast.validate()
        except RainfallDataValidationError as e:
            logger.error(f"Forecast validation failed: {e}")
            raise

        # Cache
        if self._cache_enabled:
            self._save_to_cache(cache_key, forecast)

        logger.info(
            f"Fetched rainfall forecast for ({latitude:.4f}, {longitude:.4f}): "
            f"24h={forecast.rain_forecast_24h:.1f}mm, "
            f"3d_total={forecast.rain_forecast_total_3d:.1f}mm, "
            f"category={forecast.get_intensity_category()}"
        )

        return forecast

    def _fetch_with_retry(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int
    ) -> RainfallForecast:
        """
        Fetch with exponential backoff retry.

        Args:
            latitude: Latitude
            longitude: Longitude
            forecast_days: Forecast days

        Returns:
            RainfallForecast

        Raises:
            RainfallForecastError: If all retries fail
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._fetch_data(latitude, longitude, forecast_days)
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Fetch attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.MAX_RETRIES} fetch attempts failed")

        raise RainfallForecastError(
            f"Failed to fetch forecast after {self.MAX_RETRIES} attempts: {last_error}"
        )

    def _fetch_data(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int
    ) -> RainfallForecast:
        """
        Fetch data from Open-Meteo API.

        Args:
            latitude: Latitude
            longitude: Longitude
            forecast_days: Forecast days

        Returns:
            RainfallForecast

        Raises:
            RainfallForecastError: If API call fails
        """
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'forecast_days': forecast_days,
            'hourly': ','.join(self.HOURLY_PARAMS),
            'daily': ','.join(self.DAILY_PARAMS),
            'timezone': 'UTC',
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException as e:
            raise RainfallForecastError(f"API request timeout: {e}")
        except httpx.HTTPStatusError as e:
            raise RainfallForecastError(f"API HTTP error {e.response.status_code}: {e}")
        except httpx.RequestError as e:
            raise RainfallForecastError(f"API request failed: {e}")
        except Exception as e:
            raise RainfallForecastError(f"Unexpected error during API call: {e}")

        # Parse response
        try:
            forecast = self._parse_response(data, latitude, longitude)
        except Exception as e:
            raise RainfallForecastError(f"Failed to parse API response: {e}")

        return forecast

    def _parse_response(
        self,
        data: Dict,
        latitude: float,
        longitude: float
    ) -> RainfallForecast:
        """
        Parse Open-Meteo API response.

        Args:
            data: API response JSON
            latitude: Requested latitude
            longitude: Requested longitude

        Returns:
            RainfallForecast

        Raises:
            RainfallForecastError: If required data missing
        """
        # Extract hourly data
        hourly = data.get('hourly')
        if not hourly:
            raise RainfallForecastError("API response missing 'hourly' data")

        # Extract daily data
        daily = data.get('daily')
        if not daily:
            raise RainfallForecastError("API response missing 'daily' data")

        # Get hourly precipitation (combine all sources)
        hourly_precip = self._combine_hourly_precipitation(hourly)

        if not hourly_precip:
            raise RainfallForecastError("No hourly precipitation data in API response")

        # Calculate daily forecasts
        rain_24h = sum(hourly_precip[:24]) if len(hourly_precip) >= 24 else None
        rain_48h = sum(hourly_precip[24:48]) if len(hourly_precip) >= 48 else None
        rain_72h = sum(hourly_precip[48:72]) if len(hourly_precip) >= 72 else None

        # CRITICAL: Raise error if data is missing (NO ZEROS)
        if rain_24h is None:
            raise RainfallForecastError("Insufficient hourly data for 24h forecast")
        if rain_48h is None:
            raise RainfallForecastError("Insufficient hourly data for 48h forecast")
        if rain_72h is None:
            raise RainfallForecastError("Insufficient hourly data for 72h forecast")

        # Total 3-day
        rain_total_3d = sum(hourly_precip[:72]) if len(hourly_precip) >= 72 else None
        if rain_total_3d is None:
            raise RainfallForecastError("Insufficient hourly data for 3-day total")

        # Hourly maximum intensity
        hourly_max = max(hourly_precip[:72]) if len(hourly_precip) >= 72 else 0.0

        # Probability (from daily data)
        prob_list = daily.get('precipitation_probability_max', [])
        if not prob_list:
            # If probability data not available, default to 0 (not an error)
            probability_max_3d = 0.0
            logger.warning("No precipitation probability data available, defaulting to 0%")
        else:
            probability_max_3d = max(prob_list[:3]) if len(prob_list) >= 3 else prob_list[0]

        # Create forecast object
        forecast = RainfallForecast(
            latitude=latitude,
            longitude=longitude,
            rain_forecast_24h=rain_24h,
            rain_forecast_48h=rain_48h,
            rain_forecast_72h=rain_72h,
            rain_forecast_total_3d=rain_total_3d,
            probability_max_3d=float(probability_max_3d),
            hourly_max=hourly_max,
            fetched_at=datetime.utcnow(),
            source="open-meteo"
        )

        return forecast

    def _combine_hourly_precipitation(self, hourly: Dict) -> List[float]:
        """
        Combine all precipitation sources (precipitation, rain, showers).

        Open-Meteo provides multiple precipitation variables. We combine them.

        Args:
            hourly: Hourly data from API response

        Returns:
            List of hourly precipitation values (mm/h)
        """
        # Get all available precipitation arrays
        precip_arrays = []

        for param in self.HOURLY_PARAMS:
            values = hourly.get(param)
            if values is not None:
                # Convert None to 0.0
                precip_arrays.append([v if v is not None else 0.0 for v in values])

        if not precip_arrays:
            return []

        # Combine by taking maximum at each hour
        # (rain and showers can overlap, take max to avoid double counting)
        combined = []
        max_length = max(len(arr) for arr in precip_arrays)

        for i in range(max_length):
            values_at_hour = [
                arr[i] for arr in precip_arrays if i < len(arr)
            ]
            combined.append(max(values_at_hour) if values_at_hour else 0.0)

        return combined

    def _get_from_cache(self, cache_key: str) -> Optional[RainfallForecast]:
        """
        Get forecast from cache if valid.

        Args:
            cache_key: Cache key

        Returns:
            Cached forecast or None if not found/expired
        """
        if cache_key not in self._cache:
            return None

        forecast, cached_at = self._cache[cache_key]

        # Check if cache is still valid
        age_seconds = (datetime.utcnow() - cached_at).total_seconds()
        if age_seconds > self.CACHE_TTL_SECONDS:
            del self._cache[cache_key]
            logger.debug(f"Cache expired for {cache_key} (age: {age_seconds:.0f}s)")
            return None

        return forecast

    def _save_to_cache(self, cache_key: str, forecast: RainfallForecast) -> None:
        """
        Save forecast to cache.

        Args:
            cache_key: Cache key
            forecast: Forecast to cache
        """
        self._cache[cache_key] = (forecast, datetime.utcnow())
        logger.debug(f"Cached forecast: {cache_key}")

    def clear_cache(self) -> int:
        """
        Clear all cached forecasts.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} cached forecasts")
        return count

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        now = datetime.utcnow()
        valid_count = 0
        expired_count = 0

        for forecast, cached_at in self._cache.values():
            age_seconds = (now - cached_at).total_seconds()
            if age_seconds <= self.CACHE_TTL_SECONDS:
                valid_count += 1
            else:
                expired_count += 1

        return {
            'total_entries': len(self._cache),
            'valid_entries': valid_count,
            'expired_entries': expired_count,
            'ttl_seconds': self.CACHE_TTL_SECONDS,
        }
