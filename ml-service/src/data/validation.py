"""
Data Validation Module.

Provides validation utilities for weather and forecast data to ensure
data quality and detect anomalies before model consumption.

CRITICAL: This module enforces strict validation - invalid data is rejected,
never silently converted to zeros.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.is_valid

    def summary(self) -> str:
        """Get human-readable summary."""
        if self.is_valid:
            msg = "Validation passed"
            if self.warnings:
                msg += f" with {len(self.warnings)} warnings"
            return msg
        else:
            return f"Validation failed: {len(self.errors)} errors, {len(self.warnings)} warnings"


class MeteorologicalValidator:
    """
    Validator for meteorological data.

    Enforces physical constraints and detects anomalies in weather data.
    """

    # Physical limits for meteorological variables
    LIMITS = {
        # Temperature (Celsius)
        'temperature_min': -90.0,
        'temperature_max': 60.0,

        # Precipitation (mm)
        'precipitation_min': 0.0,
        'precipitation_max': 1000.0,  # Daily maximum ever recorded: ~1825mm (Reunion Island)

        # Precipitation intensity (mm/h)
        'intensity_min': 0.0,
        'intensity_max': 200.0,  # Extreme cloudbursts

        # Probability (%)
        'probability_min': 0.0,
        'probability_max': 100.0,

        # Humidity (%)
        'humidity_min': 0.0,
        'humidity_max': 100.0,

        # Wind speed (m/s)
        'wind_speed_min': 0.0,
        'wind_speed_max': 150.0,  # Category 5 hurricane

        # Pressure (hPa)
        'pressure_min': 850.0,
        'pressure_max': 1085.0,
    }

    # Warning thresholds (extreme but physically possible)
    WARNING_THRESHOLDS = {
        'daily_precip_extreme': 300.0,  # mm/day
        'hourly_intensity_extreme': 100.0,  # mm/h
        'temperature_extreme_low': -40.0,  # C
        'temperature_extreme_high': 50.0,  # C
    }

    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> ValidationResult:
        """
        Validate geographic coordinates.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        if not (-90 <= lat <= 90):
            errors.append(f"Invalid latitude: {lat} (must be -90 to 90)")

        if not (-180 <= lon <= 180):
            errors.append(f"Invalid longitude: {lon} (must be -180 to 180)")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def validate_precipitation(
        cls,
        value: float,
        variable_name: str = "precipitation",
        time_period: str = "daily"
    ) -> ValidationResult:
        """
        Validate precipitation value.

        Args:
            value: Precipitation amount (mm)
            variable_name: Name for error messages
            time_period: Time period (daily/hourly/total)

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Check negative values
        if value < cls.LIMITS['precipitation_min']:
            errors.append(f"{variable_name}: negative value {value}mm is impossible")

        # Check extreme values
        if value > cls.LIMITS['precipitation_max']:
            errors.append(
                f"{variable_name}: {value}mm exceeds physical maximum "
                f"({cls.LIMITS['precipitation_max']}mm)"
            )

        # Warnings for extreme but possible values
        if time_period == "daily" and value > cls.WARNING_THRESHOLDS['daily_precip_extreme']:
            warnings.append(
                f"{variable_name}: {value}mm is extremely high for 24h period "
                f"(>99.9th percentile globally)"
            )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def validate_intensity(cls, value: float, variable_name: str = "intensity") -> ValidationResult:
        """
        Validate precipitation intensity (mm/h).

        Args:
            value: Precipitation intensity (mm/h)
            variable_name: Name for error messages

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        if value < cls.LIMITS['intensity_min']:
            errors.append(f"{variable_name}: negative value {value}mm/h is impossible")

        if value > cls.LIMITS['intensity_max']:
            errors.append(
                f"{variable_name}: {value}mm/h exceeds physical maximum "
                f"({cls.LIMITS['intensity_max']}mm/h)"
            )

        if value > cls.WARNING_THRESHOLDS['hourly_intensity_extreme']:
            warnings.append(
                f"{variable_name}: {value}mm/h indicates extreme cloudburst "
                f"(rare event)"
            )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def validate_probability(cls, value: float, variable_name: str = "probability") -> ValidationResult:
        """
        Validate probability value (0-100%).

        Args:
            value: Probability (0-100)
            variable_name: Name for error messages

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        if not (cls.LIMITS['probability_min'] <= value <= cls.LIMITS['probability_max']):
            errors.append(
                f"{variable_name}: {value}% outside valid range "
                f"[{cls.LIMITS['probability_min']}, {cls.LIMITS['probability_max']}]"
            )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def validate_temperature(
        cls,
        value: float,
        variable_name: str = "temperature"
    ) -> ValidationResult:
        """
        Validate temperature value.

        Args:
            value: Temperature (Celsius)
            variable_name: Name for error messages

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        if not (cls.LIMITS['temperature_min'] <= value <= cls.LIMITS['temperature_max']):
            errors.append(
                f"{variable_name}: {value}°C outside valid range "
                f"[{cls.LIMITS['temperature_min']}, {cls.LIMITS['temperature_max']}]"
            )

        if value < cls.WARNING_THRESHOLDS['temperature_extreme_low']:
            warnings.append(f"{variable_name}: {value}°C is extremely low")

        if value > cls.WARNING_THRESHOLDS['temperature_extreme_high']:
            warnings.append(f"{variable_name}: {value}°C is extremely high")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @staticmethod
    def validate_timestamp(timestamp: datetime, max_future_days: int = 16) -> ValidationResult:
        """
        Validate timestamp is reasonable.

        Args:
            timestamp: Datetime to validate
            max_future_days: Maximum days into future allowed

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        now = datetime.utcnow()

        # Check if too far in past
        if timestamp.year < 1900:
            errors.append(f"Timestamp {timestamp} is before 1900 (likely invalid)")

        # Check if too far in future
        days_ahead = (timestamp - now).days
        if days_ahead > max_future_days:
            errors.append(
                f"Timestamp {timestamp} is {days_ahead} days in future "
                f"(max forecast: {max_future_days} days)"
            )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def validate_forecast_data(
        cls,
        data: Dict[str, float],
        required_fields: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Validate complete forecast data dictionary.

        Args:
            data: Dictionary of forecast variables
            required_fields: List of required field names (None = no requirement)

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Check required fields
        if required_fields:
            missing = set(required_fields) - set(data.keys())
            if missing:
                errors.append(f"Missing required fields: {', '.join(missing)}")

        # Validate each field based on name patterns
        for key, value in data.items():
            if value is None:
                warnings.append(f"{key}: null value")
                continue

            try:
                # Precipitation fields
                if any(x in key.lower() for x in ['rain', 'precip', 'precipitation']):
                    if 'intensity' in key.lower() or 'hourly' in key.lower():
                        result = cls.validate_intensity(value, key)
                    else:
                        result = cls.validate_precipitation(value, key)

                    errors.extend(result.errors)
                    warnings.extend(result.warnings)

                # Probability fields
                elif 'probability' in key.lower() or 'prob' in key.lower():
                    result = cls.validate_probability(value, key)
                    errors.extend(result.errors)
                    warnings.extend(result.warnings)

                # Temperature fields
                elif 'temp' in key.lower():
                    result = cls.validate_temperature(value, key)
                    errors.extend(result.errors)
                    warnings.extend(result.warnings)

            except Exception as e:
                warnings.append(f"{key}: validation error - {str(e)}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


class DataQualityChecker:
    """
    Data quality checks for time series data.

    Detects missing values, outliers, and suspicious patterns.
    """

    @staticmethod
    def check_missing_values(
        data: Dict[str, List[float]],
        max_missing_ratio: float = 0.3
    ) -> ValidationResult:
        """
        Check for missing values in time series data.

        Args:
            data: Dictionary of time series (key -> list of values)
            max_missing_ratio: Maximum allowed ratio of None values

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        for key, values in data.items():
            if not values:
                errors.append(f"{key}: empty time series")
                continue

            none_count = sum(1 for v in values if v is None)
            ratio = none_count / len(values)

            if ratio > max_missing_ratio:
                errors.append(
                    f"{key}: {ratio*100:.1f}% missing values "
                    f"(max allowed: {max_missing_ratio*100:.1f}%)"
                )
            elif ratio > 0.1:
                warnings.append(
                    f"{key}: {ratio*100:.1f}% missing values"
                )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @staticmethod
    def check_constant_values(
        data: Dict[str, List[float]],
        min_unique_ratio: float = 0.1
    ) -> ValidationResult:
        """
        Check for suspiciously constant time series.

        Args:
            data: Dictionary of time series
            min_unique_ratio: Minimum ratio of unique values

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        for key, values in data.items():
            if not values:
                continue

            # Filter out None values
            valid_values = [v for v in values if v is not None]
            if not valid_values:
                continue

            unique_count = len(set(valid_values))
            ratio = unique_count / len(valid_values)

            if ratio < min_unique_ratio:
                warnings.append(
                    f"{key}: only {unique_count} unique values in {len(valid_values)} points "
                    f"(suspiciously constant)"
                )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
