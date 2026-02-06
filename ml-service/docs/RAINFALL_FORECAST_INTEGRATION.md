# Rainfall Forecast Integration

Real-time rainfall forecast integration for FloodSafe using Open-Meteo API.

## Overview

The rainfall forecast module fetches 3-day precipitation forecasts from the Open-Meteo API, validates the data against meteorological standards, and provides IMD (India Meteorological Department) intensity classification.

### Key Features

- ✅ **Real-time forecasts** - Free Open-Meteo API (no API key required)
- ✅ **Strict validation** - Rejects invalid data (no silent zeros)
- ✅ **IMD classification** - Indian standard intensity categories
- ✅ **Caching** - 1-hour TTL to reduce API calls
- ✅ **Retry logic** - Exponential backoff (3 attempts)
- ✅ **Type safety** - Full type hints and dataclasses

## Files

```
apps/ml-service/
├── src/data/
│   ├── rainfall_forecast.py       # Main fetcher
│   └── validation.py               # Validation module
├── tests/
│   └── test_rainfall_forecast.py  # 20 unit tests
└── examples/
    └── test_rainfall_forecast.py  # Live demo script
```

## Installation

Dependencies already in `requirements.txt`:
- `httpx>=0.24.0` - HTTP client

## Quick Start

### Basic Usage

```python
from src.data.rainfall_forecast import RainfallForecastFetcher

# Initialize fetcher
fetcher = RainfallForecastFetcher()

# Get forecast for Delhi
forecast = fetcher.get_forecast(
    latitude=28.6139,
    longitude=77.2090,
    forecast_days=3
)

# Access data
print(f"Next 24h: {forecast.rain_forecast_24h}mm")
print(f"Category: {forecast.get_intensity_category()}")
print(f"Peak intensity: {forecast.hourly_max}mm/h")
```

### Run Live Example

```bash
cd apps/ml-service
python examples/test_rainfall_forecast.py
```

## API Reference

### RainfallForecastFetcher

Main class for fetching rainfall forecasts.

#### Constructor

```python
RainfallForecastFetcher(
    timeout_seconds: float = 30.0,
    cache_enabled: bool = True
)
```

**Parameters:**
- `timeout_seconds` - HTTP request timeout (default: 30s)
- `cache_enabled` - Enable in-memory caching (default: True)

#### Methods

##### `get_forecast()`

```python
def get_forecast(
    latitude: float,
    longitude: float,
    forecast_days: int = 3,
    force_refresh: bool = False
) -> RainfallForecast
```

**Parameters:**
- `latitude` - Latitude in degrees (-90 to 90)
- `longitude` - Longitude in degrees (-180 to 180)
- `forecast_days` - Forecast horizon (1-16 days)
- `force_refresh` - Bypass cache

**Returns:** `RainfallForecast` object

**Raises:**
- `RainfallForecastError` - API failure or missing data
- `RainfallDataValidationError` - Invalid data (e.g., negative rainfall)

##### `clear_cache()`

```python
def clear_cache() -> int
```

Clears all cached forecasts. Returns count of entries cleared.

##### `get_cache_stats()`

```python
def get_cache_stats() -> Dict
```

Returns cache statistics:
```python
{
    'total_entries': 5,
    'valid_entries': 5,
    'expired_entries': 0,
    'ttl_seconds': 3600
}
```

### RainfallForecast

Dataclass containing validated forecast data.

#### Attributes

```python
@dataclass
class RainfallForecast:
    latitude: float                 # Location latitude
    longitude: float                # Location longitude
    rain_forecast_24h: float        # Rainfall 0-24h (mm)
    rain_forecast_48h: float        # Rainfall 24-48h (mm)
    rain_forecast_72h: float        # Rainfall 48-72h (mm)
    rain_forecast_total_3d: float   # Total 3-day (mm)
    probability_max_3d: float       # Max probability 0-100%
    hourly_max: float               # Peak intensity (mm/h)
    fetched_at: datetime            # Fetch timestamp (UTC)
    source: str                     # Data source ("open-meteo")
```

#### Methods

##### `validate()`

```python
def validate() -> None
```

Validates forecast data. Raises `RainfallDataValidationError` if invalid.

##### `get_intensity_category()`

```python
def get_intensity_category() -> str
```

Returns IMD intensity category based on 24h forecast:

| Category | mm/24h | Description |
|----------|--------|-------------|
| `light` | < 7.5 | Light rain |
| `moderate` | 7.5-35.5 | Moderate rain |
| `heavy` | 35.5-64.4 | Heavy rain |
| `very_heavy` | 64.4-124.4 | Very heavy rain |
| `extremely_heavy` | > 124.4 | Extremely heavy rain |

##### `to_dict()`

```python
def to_dict() -> Dict
```

Converts to dictionary (includes `intensity_category`).

## Validation Module

### MeteorologicalValidator

Static validation methods for weather data.

#### Methods

##### `validate_coordinates()`

```python
@staticmethod
def validate_coordinates(lat: float, lon: float) -> ValidationResult
```

Validates geographic coordinates.

##### `validate_precipitation()`

```python
@classmethod
def validate_precipitation(
    value: float,
    variable_name: str = "precipitation",
    time_period: str = "daily"
) -> ValidationResult
```

Validates precipitation amount (0-1000mm).

##### `validate_intensity()`

```python
@classmethod
def validate_intensity(
    value: float,
    variable_name: str = "intensity"
) -> ValidationResult
```

Validates precipitation intensity (0-200mm/h).

##### `validate_probability()`

```python
@classmethod
def validate_probability(
    value: float,
    variable_name: str = "probability"
) -> ValidationResult
```

Validates probability (0-100%).

### ValidationResult

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def summary() -> str
```

## Error Handling

### Exception Hierarchy

```
Exception
├── RainfallForecastError
│   ├── API timeout
│   ├── HTTP errors
│   ├── Missing data
│   └── Invalid coordinates
└── RainfallDataValidationError
    ├── Negative rainfall
    ├── Invalid coordinates
    └── Out-of-range values
```

### Example Error Handling

```python
from src.data.rainfall_forecast import (
    RainfallForecastFetcher,
    RainfallForecastError,
    RainfallDataValidationError
)

fetcher = RainfallForecastFetcher()

try:
    forecast = fetcher.get_forecast(28.6139, 77.2090)

except RainfallDataValidationError as e:
    # Invalid data returned by API
    logger.error(f"Invalid forecast data: {e}")
    # DO NOT use zeros - raise alert or use fallback model

except RainfallForecastError as e:
    # API failure or missing data
    logger.error(f"Failed to fetch forecast: {e}")
    # Retry later or use alternative source

except Exception as e:
    # Unexpected error
    logger.error(f"Unexpected error: {e}")
    raise
```

## Caching Strategy

### In-Memory Cache

- **TTL:** 1 hour (3600 seconds)
- **Key:** `"{latitude:.4f},{longitude:.4f},{forecast_days}"`
- **Behavior:** Automatic expiration and cleanup

### Cache Lifecycle

```python
# First call - hits API
forecast1 = fetcher.get_forecast(28.6139, 77.2090)

# Second call within 1 hour - uses cache
forecast2 = fetcher.get_forecast(28.6139, 77.2090)

# Force refresh - bypasses cache
forecast3 = fetcher.get_forecast(28.6139, 77.2090, force_refresh=True)
```

## Retry Logic

Exponential backoff with 3 attempts:

1. **Attempt 1** - Immediate
2. **Attempt 2** - Wait 1s
3. **Attempt 3** - Wait 2s

```python
# Configured via class constants
RainfallForecastFetcher.MAX_RETRIES = 3
RainfallForecastFetcher.RETRY_DELAY_SECONDS = 1.0
```

## Testing

### Run Unit Tests

```bash
cd apps/ml-service
python -m pytest tests/test_rainfall_forecast.py -v
```

### Test Coverage

20 tests covering:

1. **Successful fetch** - API returns valid data
2. **Validation negative rainfall** - Rejects negative values
3. **Cache behavior** - Second call uses cache
4. **Cache force refresh** - Bypasses cache
5. **Cache expiration** - Expired entries refetched
6. **Retry on failure** - Exponential backoff works
7. **Retry all fail** - Error raised after max retries
8. **Intensity classification light** - IMD <7.5mm
9. **Intensity classification moderate** - IMD 7.5-35.5mm
10. **Intensity classification heavy** - IMD 35.5-64.4mm
11. **Intensity classification very_heavy** - IMD 64.4-124.4mm
12. **Intensity classification extremely_heavy** - IMD >124.4mm
13. **Invalid coordinates** - Rejects lat>90, lon>180
14. **Invalid forecast_days** - Rejects <1 or >16
15. **Missing hourly data** - API response incomplete
16. **Cache clear** - Clears all entries
17. **Cache stats** - Returns correct statistics
18. **Forecast to_dict** - Serialization works
19. **Extreme rainfall warning** - Logs warnings
20. **Timeout error** - Handles API timeout

### Test Output

```
============================= test session starts =============================
tests/test_rainfall_forecast.py::test_successful_fetch PASSED            [  5%]
tests/test_rainfall_forecast.py::test_validation_negative_rainfall PASSED [ 10%]
...
======================== 20 passed, 1 warning in 7.24s ========================
```

## Integration with ML Pipeline

### Feature Extraction

```python
from src.data.rainfall_forecast import RainfallForecastFetcher
from src.features.extractor import FeatureExtractor

fetcher = RainfallForecastFetcher()
extractor = FeatureExtractor()

# Get forecast
forecast = fetcher.get_forecast(28.6139, 77.2090)

# Add to feature vector
features = {
    'rain_forecast_24h': forecast.rain_forecast_24h,
    'rain_forecast_48h': forecast.rain_forecast_48h,
    'rain_forecast_72h': forecast.rain_forecast_72h,
    'rain_intensity_max': forecast.hourly_max,
    'rain_probability': forecast.probability_max_3d / 100.0,  # Normalize to 0-1
}
```

### Alert Service Integration

```python
from src.data.rainfall_forecast import RainfallForecastFetcher

fetcher = RainfallForecastFetcher()

def check_rainfall_alert(lat: float, lon: float) -> bool:
    """Check if heavy rainfall alert needed."""
    forecast = fetcher.get_forecast(lat, lon)

    category = forecast.get_intensity_category()

    # Alert on heavy or worse
    return category in ['heavy', 'very_heavy', 'extremely_heavy']
```

## Data Source

### Open-Meteo API

- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Model:** ECMWF IFS (Integrated Forecasting System)
- **Resolution:** 0.25° (~25km)
- **Coverage:** Global
- **Update frequency:** Every 6 hours
- **License:** Free for non-commercial use
- **Documentation:** https://open-meteo.com/en/docs

### API Response Structure

```json
{
  "latitude": 28.6139,
  "longitude": 77.2090,
  "hourly": {
    "time": ["2024-07-15T00:00", "2024-07-15T01:00", ...],
    "precipitation": [0.1, 0.2, 0.5, ...],
    "rain": [0.0, 0.1, 0.3, ...],
    "showers": [0.0, 0.0, 0.2, ...]
  },
  "daily": {
    "time": ["2024-07-15", "2024-07-16", "2024-07-17"],
    "precipitation_sum": [12.5, 45.2, 8.3],
    "precipitation_hours": [8, 16, 6],
    "precipitation_probability_max": [60, 85, 40]
  }
}
```

## Best Practices

### ✅ DO

- Always handle `RainfallForecastError` and `RainfallDataValidationError`
- Use caching to minimize API calls
- Log validation warnings for extreme values
- Check `get_intensity_category()` for alerts
- Validate coordinates before calling API

### ❌ DON'T

- Don't ignore validation errors and use zeros
- Don't call API in tight loops (use cache)
- Don't assume data is always available
- Don't skip error handling
- Don't use invalid coordinates

## Troubleshooting

### "Invalid coordinates" error

**Cause:** Latitude or longitude out of range

**Solution:** Validate coordinates (-90 ≤ lat ≤ 90, -180 ≤ lon ≤ 180)

### "Failed to fetch forecast after 3 attempts"

**Cause:** API unreachable or rate limited

**Solution:**
1. Check internet connection
2. Verify API endpoint is accessible
3. Increase timeout: `RainfallForecastFetcher(timeout_seconds=60)`
4. Wait and retry (rate limiting)

### "API response missing 'hourly' data"

**Cause:** API returned incomplete response

**Solution:**
1. Check API status: https://open-meteo.com/
2. Retry with `force_refresh=True`
3. Use alternative data source

### Validation warnings for extreme values

**Cause:** Forecast predicts unusually high rainfall

**Solution:** Warnings are informational - data is still valid. Log and monitor.

## Future Enhancements

- [ ] Ensemble forecasts (multiple models)
- [ ] Probabilistic forecasts (quantiles)
- [ ] Sub-hourly intensity data
- [ ] Historical forecast accuracy tracking
- [ ] Alternative API fallback (IMD, ECMWF)
- [ ] Persistent caching (Redis)
- [ ] GraphQL API endpoint

## References

- **Open-Meteo API:** https://open-meteo.com/en/docs
- **IMD Rainfall Classification:** https://mausam.imd.gov.in/
- **ECMWF IFS Model:** https://www.ecmwf.int/en/forecasts

## License

Part of FloodSafe (Nonprofit flood monitoring platform).

## Support

For issues or questions:
- File issue: `apps/ml-service/` component
- Contact: ML team
