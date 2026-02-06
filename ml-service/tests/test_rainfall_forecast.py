"""
Unit Tests for Rainfall Forecast Fetcher.

Tests the Open-Meteo rainfall forecast integration including:
- Successful API calls
- Data validation
- Cache behavior
- Retry logic
- IMD intensity classification
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import httpx

from src.data.rainfall_forecast import (
    RainfallForecast,
    RainfallForecastFetcher,
    RainfallForecastError,
    RainfallDataValidationError,
)
from src.data.validation import MeteorologicalValidator, ValidationResult


# --- Fixtures ---

@pytest.fixture
def sample_api_response():
    """Sample successful API response from Open-Meteo."""
    # Generate 72 hours of hourly data
    hourly_precip = [0.1] * 24 + [2.5] * 24 + [1.0] * 24  # 24h, 48h, 72h

    return {
        'latitude': 28.6139,
        'longitude': 77.2090,
        'timezone': 'UTC',
        'hourly': {
            'time': [(datetime.utcnow() + timedelta(hours=i)).isoformat() for i in range(72)],
            'precipitation': hourly_precip,
            'rain': [0.0] * 72,
            'showers': [0.0] * 72,
        },
        'daily': {
            'time': [(datetime.utcnow() + timedelta(days=i)).isoformat() for i in range(3)],
            'precipitation_sum': [2.4, 60.0, 24.0],
            'precipitation_hours': [8, 18, 12],
            'precipitation_probability_max': [30, 80, 50],
        }
    }


@pytest.fixture
def sample_extreme_response():
    """API response with extreme rainfall values."""
    # Very heavy rainfall (200mm in 24h)
    hourly_precip = [8.3] * 24 + [5.0] * 24 + [2.0] * 24

    return {
        'latitude': 28.6139,
        'longitude': 77.2090,
        'timezone': 'UTC',
        'hourly': {
            'time': [(datetime.utcnow() + timedelta(hours=i)).isoformat() for i in range(72)],
            'precipitation': hourly_precip,
            'rain': [0.0] * 72,
            'showers': [0.0] * 72,
        },
        'daily': {
            'time': [(datetime.utcnow() + timedelta(days=i)).isoformat() for i in range(3)],
            'precipitation_sum': [199.2, 120.0, 48.0],
            'precipitation_hours': [24, 24, 18],
            'precipitation_probability_max': [95, 90, 70],
        }
    }


@pytest.fixture
def sample_invalid_response():
    """API response with invalid data (negative rainfall in all sources)."""
    # All precipitation sources must be negative for the test to work
    # (since _combine_hourly_precipitation takes the max of all sources)
    hourly_precip_negative = [-5.0] * 24 + [2.0] * 24 + [1.0] * 24

    return {
        'latitude': 28.6139,
        'longitude': 77.2090,
        'timezone': 'UTC',
        'hourly': {
            'time': [(datetime.utcnow() + timedelta(hours=i)).isoformat() for i in range(72)],
            'precipitation': hourly_precip_negative,  # Only source with data
            # Don't include 'rain' and 'showers' - they would override negatives with max()
        },
        'daily': {
            'time': [(datetime.utcnow() + timedelta(days=i)).isoformat() for i in range(3)],
            'precipitation_sum': [-120.0, 48.0, 24.0],
            'precipitation_hours': [24, 18, 12],
            'precipitation_probability_max': [80, 60, 40],
        }
    }


@pytest.fixture
def fetcher():
    """Create a RainfallForecastFetcher instance."""
    return RainfallForecastFetcher(timeout_seconds=10.0)


# --- Test: Successful Fetch ---

def test_successful_fetch(fetcher, sample_api_response):
    """Test successful API call returns valid forecast."""
    with patch('httpx.Client') as mock_client_class:
        # Mock HTTP client
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # Fetch forecast
        forecast = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)

        # Assertions
        assert isinstance(forecast, RainfallForecast)
        assert forecast.latitude == 28.6139
        assert forecast.longitude == 77.2090

        # Check calculated values
        assert forecast.rain_forecast_24h == pytest.approx(2.4, rel=0.1)  # 0.1 * 24
        assert forecast.rain_forecast_48h == pytest.approx(60.0, rel=0.1)  # 2.5 * 24
        assert forecast.rain_forecast_72h == pytest.approx(24.0, rel=0.1)  # 1.0 * 24
        assert forecast.rain_forecast_total_3d == pytest.approx(86.4, rel=0.1)

        assert forecast.probability_max_3d == 80.0  # Max of [30, 80, 50]
        assert forecast.hourly_max == pytest.approx(2.5, rel=0.1)

        assert forecast.source == "open-meteo"
        assert isinstance(forecast.fetched_at, datetime)

        # Verify API was called correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == fetcher.BASE_URL
        assert call_args[1]['params']['latitude'] == 28.6139
        assert call_args[1]['params']['longitude'] == 77.2090


# --- Test: Validation Negative Rainfall ---

def test_validation_negative_rainfall(fetcher, sample_invalid_response):
    """Test that negative rainfall values are rejected."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.json.return_value = sample_invalid_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # Should raise validation error
        # The negative hourly values will be summed to create negative daily totals,
        # which should fail validation
        with pytest.raises(RainfallDataValidationError) as exc_info:
            fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)

        # Check error message mentions negative value or impossible
        error_msg = str(exc_info.value).lower()
        assert "negative" in error_msg or "impossible" in error_msg


# --- Test: Cache Behavior ---

def test_cache_behavior(fetcher, sample_api_response):
    """Test that second call uses cache (no API call)."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # First call - should hit API
        forecast1 = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)
        assert mock_client.get.call_count == 1

        # Second call - should use cache
        forecast2 = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)
        assert mock_client.get.call_count == 1  # No additional API call

        # Both forecasts should be identical
        assert forecast1.rain_forecast_24h == forecast2.rain_forecast_24h
        assert forecast1.rain_forecast_total_3d == forecast2.rain_forecast_total_3d
        assert forecast1.fetched_at == forecast2.fetched_at


def test_cache_force_refresh(fetcher, sample_api_response):
    """Test force_refresh bypasses cache."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # First call
        forecast1 = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)
        assert mock_client.get.call_count == 1

        # Second call with force_refresh=True
        forecast2 = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3, force_refresh=True)
        assert mock_client.get.call_count == 2  # Second API call made


def test_cache_expiration(fetcher, sample_api_response):
    """Test cache expires after TTL."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # First call
        forecast1 = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)
        assert mock_client.get.call_count == 1

        # Manually expire cache by modifying cached_at
        cache_key = "28.6139,77.2090,3"
        if cache_key in fetcher._cache:
            forecast, cached_at = fetcher._cache[cache_key]
            # Set cached_at to 2 hours ago (beyond TTL)
            fetcher._cache[cache_key] = (forecast, datetime.utcnow() - timedelta(hours=2))

        # Second call - should fetch fresh data
        forecast2 = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)
        assert mock_client.get.call_count == 2  # Cache expired, new call made


# --- Test: Retry on Failure ---

def test_retry_on_failure(fetcher, sample_api_response):
    """Test retry logic with exponential backoff."""
    with patch('httpx.Client') as mock_client_class, \
         patch('time.sleep') as mock_sleep:  # Mock sleep to speed up test

        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # First two calls fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=Mock(), response=Mock(status_code=500)
        )

        mock_response_success = Mock()
        mock_response_success.json.return_value = sample_api_response
        mock_response_success.raise_for_status = Mock()

        mock_client.get.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]

        # Should succeed after retries
        forecast = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)

        # Verify 3 API calls were made
        assert mock_client.get.call_count == 3

        # Verify exponential backoff sleep calls
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)  # First retry: 1s
        mock_sleep.assert_any_call(2.0)  # Second retry: 2s

        # Forecast should be valid
        assert isinstance(forecast, RainfallForecast)


def test_retry_all_fail(fetcher):
    """Test that error is raised if all retries fail."""
    with patch('httpx.Client') as mock_client_class, \
         patch('time.sleep'):

        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # All calls fail
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable", request=Mock(), response=Mock(status_code=503)
        )
        mock_client.get.return_value = mock_response_fail

        # Should raise error after max retries
        with pytest.raises(RainfallForecastError) as exc_info:
            fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)

        assert "Failed to fetch forecast after 3 attempts" in str(exc_info.value)


# --- Test: Intensity Classification ---

def test_intensity_classification_light():
    """Test IMD light rainfall classification (<7.5mm)."""
    forecast = RainfallForecast(
        latitude=28.6139,
        longitude=77.2090,
        rain_forecast_24h=5.0,
        rain_forecast_48h=3.0,
        rain_forecast_72h=2.0,
        rain_forecast_total_3d=10.0,
        probability_max_3d=40.0,
        hourly_max=1.5,
        fetched_at=datetime.utcnow()
    )

    assert forecast.get_intensity_category() == "light"


def test_intensity_classification_moderate():
    """Test IMD moderate rainfall classification (7.5-35.5mm)."""
    forecast = RainfallForecast(
        latitude=28.6139,
        longitude=77.2090,
        rain_forecast_24h=20.0,
        rain_forecast_48h=15.0,
        rain_forecast_72h=10.0,
        rain_forecast_total_3d=45.0,
        probability_max_3d=60.0,
        hourly_max=3.0,
        fetched_at=datetime.utcnow()
    )

    assert forecast.get_intensity_category() == "moderate"


def test_intensity_classification_heavy():
    """Test IMD heavy rainfall classification (35.5-64.4mm)."""
    forecast = RainfallForecast(
        latitude=28.6139,
        longitude=77.2090,
        rain_forecast_24h=50.0,
        rain_forecast_48h=40.0,
        rain_forecast_72h=30.0,
        rain_forecast_total_3d=120.0,
        probability_max_3d=80.0,
        hourly_max=6.0,
        fetched_at=datetime.utcnow()
    )

    assert forecast.get_intensity_category() == "heavy"


def test_intensity_classification_very_heavy():
    """Test IMD very heavy rainfall classification (64.4-124.4mm)."""
    forecast = RainfallForecast(
        latitude=28.6139,
        longitude=77.2090,
        rain_forecast_24h=100.0,
        rain_forecast_48h=80.0,
        rain_forecast_72h=60.0,
        rain_forecast_total_3d=240.0,
        probability_max_3d=90.0,
        hourly_max=10.0,
        fetched_at=datetime.utcnow()
    )

    assert forecast.get_intensity_category() == "very_heavy"


def test_intensity_classification_extremely_heavy():
    """Test IMD extremely heavy rainfall classification (>124.4mm)."""
    forecast = RainfallForecast(
        latitude=28.6139,
        longitude=77.2090,
        rain_forecast_24h=150.0,
        rain_forecast_48h=120.0,
        rain_forecast_72h=80.0,
        rain_forecast_total_3d=350.0,
        probability_max_3d=95.0,
        hourly_max=15.0,
        fetched_at=datetime.utcnow()
    )

    assert forecast.get_intensity_category() == "extremely_heavy"


# --- Test: Edge Cases ---

def test_invalid_coordinates():
    """Test that invalid coordinates are rejected."""
    fetcher = RainfallForecastFetcher()

    # Invalid latitude
    with pytest.raises(RainfallForecastError) as exc_info:
        fetcher.get_forecast(95.0, 77.2090)
    assert "Invalid coordinates" in str(exc_info.value)

    # Invalid longitude
    with pytest.raises(RainfallForecastError) as exc_info:
        fetcher.get_forecast(28.6139, 200.0)
    assert "Invalid coordinates" in str(exc_info.value)


def test_invalid_forecast_days():
    """Test that invalid forecast_days parameter is rejected."""
    fetcher = RainfallForecastFetcher()

    # Too few days
    with pytest.raises(RainfallForecastError) as exc_info:
        fetcher.get_forecast(28.6139, 77.2090, forecast_days=0)
    assert "forecast_days must be 1-16" in str(exc_info.value)

    # Too many days
    with pytest.raises(RainfallForecastError) as exc_info:
        fetcher.get_forecast(28.6139, 77.2090, forecast_days=20)
    assert "forecast_days must be 1-16" in str(exc_info.value)


def test_missing_hourly_data(fetcher):
    """Test error handling when API response lacks hourly data."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Response without hourly data
        mock_response = Mock()
        mock_response.json.return_value = {
            'latitude': 28.6139,
            'longitude': 77.2090,
            'daily': {
                'time': [(datetime.utcnow() + timedelta(days=i)).isoformat() for i in range(3)],
                'precipitation_sum': [10.0, 20.0, 15.0],
            }
        }
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        with pytest.raises(RainfallForecastError) as exc_info:
            fetcher.get_forecast(28.6139, 77.2090)

        assert "missing 'hourly' data" in str(exc_info.value)


def test_cache_clear(fetcher, sample_api_response):
    """Test cache clearing."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # Fetch to populate cache
        fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)
        assert len(fetcher._cache) == 1

        # Clear cache
        count = fetcher.clear_cache()
        assert count == 1
        assert len(fetcher._cache) == 0


def test_cache_stats(fetcher, sample_api_response):
    """Test cache statistics."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # Fetch some forecasts
        fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)
        fetcher.get_forecast(28.7041, 77.1025, forecast_days=3)

        stats = fetcher.get_cache_stats()
        assert stats['total_entries'] == 2
        assert stats['valid_entries'] == 2
        assert stats['expired_entries'] == 0
        assert stats['ttl_seconds'] == 3600


def test_forecast_to_dict():
    """Test RainfallForecast.to_dict() method."""
    forecast = RainfallForecast(
        latitude=28.6139,
        longitude=77.2090,
        rain_forecast_24h=50.0,
        rain_forecast_48h=40.0,
        rain_forecast_72h=30.0,
        rain_forecast_total_3d=120.0,
        probability_max_3d=80.0,
        hourly_max=6.0,
        fetched_at=datetime(2024, 7, 15, 12, 0, 0)
    )

    data = forecast.to_dict()

    assert data['latitude'] == 28.6139
    assert data['longitude'] == 77.2090
    assert data['rain_forecast_24h'] == 50.0
    assert data['intensity_category'] == "heavy"
    assert data['fetched_at'] == "2024-07-15T12:00:00"


# --- Test: Extreme Weather Scenarios ---

def test_extreme_rainfall_warning(fetcher, sample_extreme_response):
    """Test that extreme rainfall generates warnings but doesn't fail."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.json.return_value = sample_extreme_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        # Should succeed with warnings logged
        forecast = fetcher.get_forecast(28.6139, 77.2090, forecast_days=3)

        assert forecast.rain_forecast_24h > 150.0
        assert forecast.get_intensity_category() == "extremely_heavy"


def test_timeout_error(fetcher):
    """Test handling of API timeout."""
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Simulate timeout
        mock_client.get.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(RainfallForecastError) as exc_info:
            fetcher.get_forecast(28.6139, 77.2090)

        assert "timeout" in str(exc_info.value).lower()
