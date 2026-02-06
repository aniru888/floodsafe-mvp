# Rainfall Forecast - Quick Start Guide

## Installation

No installation needed - uses existing dependencies (`httpx` already in `requirements.txt`).

## Basic Usage

```python
from src.data.rainfall_forecast import RainfallForecastFetcher

# Initialize
fetcher = RainfallForecastFetcher()

# Get forecast for Delhi
forecast = fetcher.get_forecast(
    latitude=28.6139,
    longitude=77.2090,
    forecast_days=3
)

# Access data
print(f"Next 24h: {forecast.rain_forecast_24h:.1f}mm")
print(f"Category: {forecast.get_intensity_category()}")
print(f"Probability: {forecast.probability_max_3d}%")
```

## Run Tests

```bash
cd apps/ml-service
python -m pytest tests/test_rainfall_forecast.py -v
```

Expected output: `20 passed`

## Live Demo

```bash
python examples/test_rainfall_forecast.py
```

Fetches real forecasts for 5 Indian cities.

## IMD Intensity Categories

| Category | mm/24h |
|----------|--------|
| Light | < 7.5 |
| Moderate | 7.5 - 35.5 |
| Heavy | 35.5 - 64.4 |
| Very Heavy | 64.4 - 124.4 |
| Extremely Heavy | > 124.4 |

## Error Handling

```python
from src.data.rainfall_forecast import (
    RainfallForecastError,
    RainfallDataValidationError
)

try:
    forecast = fetcher.get_forecast(lat, lon)
except RainfallDataValidationError:
    # Invalid data - DO NOT use zeros
    raise
except RainfallForecastError:
    # API failure - retry later
    pass
```

## Files Created

```
apps/ml-service/
├── src/data/
│   ├── validation.py              # 416 lines
│   └── rainfall_forecast.py       # 513 lines
├── tests/
│   └── test_rainfall_forecast.py  # 579 lines (20 tests)
├── examples/
│   └── test_rainfall_forecast.py  # Live demo
└── docs/
    └── RAINFALL_FORECAST_INTEGRATION.md  # Full docs
```

## Key Features

- Real-time Open-Meteo API integration
- Strict validation (NO zeros for missing data)
- IMD intensity classification
- 1-hour cache TTL
- Exponential backoff retry (3 attempts)
- 20 comprehensive unit tests

## Performance

- API call: ~500ms
- Cached call: <1ms
- Cache TTL: 1 hour
- Max retries: 3 (with 1s, 2s delays)

## Documentation

Full documentation: `docs/RAINFALL_FORECAST_INTEGRATION.md`

## Support

For questions, see implementation summary: `RAINFALL_FORECAST_IMPLEMENTATION.md`
