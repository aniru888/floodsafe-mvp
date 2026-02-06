# FloodSafe ML Data Fetchers

Data fetching layer for Google Earth Engine (GEE) and external sources.

## Overview

All data fetchers inherit from `BaseDataFetcher` which provides:
- Automatic caching (configurable TTL)
- Error handling with custom exceptions
- Consistent interface across sources

## Available Fetchers

### 1. PrecipitationFetcher

**Source**: UCSB-CHG/CHIRPS/DAILY
**Resolution**: 0.05° (~5.5km)
**Coverage**: Global, 1981-present
**Update**: Daily

```python
from src.data import PrecipitationFetcher
from datetime import datetime, timedelta

fetcher = PrecipitationFetcher()

# Get raw daily data
delhi_bounds = (28.4, 76.8, 28.9, 77.4)  # (lat_min, lng_min, lat_max, lng_max)
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

df = fetcher.fetch(delhi_bounds, start_date, end_date)
# Returns: DataFrame with [date, precipitation_mm]

# Get aggregated features
features = fetcher.get_rainfall_features(
    bounds=delhi_bounds,
    reference_date=end_date,
    lookback_days=7
)
# Returns: {
#   'rainfall_24h': float,      # Last 24h rainfall (mm)
#   'rainfall_3d': float,        # Last 3 days cumulative (mm)
#   'rainfall_7d': float,        # Last 7 days cumulative (mm)
#   'max_daily_7d': float,       # Max daily in last 7 days (mm)
#   'wet_days_7d': int          # Days with >1mm rain
# }
```

### 2. ERA5Fetcher

**Source**: ECMWF/ERA5_LAND/DAILY_AGGR
**Resolution**: 0.1° (~11km)
**Coverage**: Global, 1950-present
**Update**: Daily (5-day lag)

```python
from src.data import ERA5Fetcher
from datetime import datetime, timedelta

fetcher = ERA5Fetcher()

# Get raw daily data
delhi_bounds = (28.4, 76.8, 28.9, 77.4)
# Note: ERA5 has ~5 day lag
end_date = datetime.now() - timedelta(days=6)
start_date = end_date - timedelta(days=7)

df = fetcher.fetch(delhi_bounds, start_date, end_date)
# Returns: DataFrame with [date, temperature_2m_k, total_precipitation_m,
#                         surface_runoff_m, soil_moisture_m3m3]

# Get aggregated weather features
features = fetcher.get_weather_features(
    bounds=delhi_bounds,
    reference_date=end_date,
    lookback_days=7
)
# Returns: {
#   'temperature_mean': float,    # Mean temp (°C)
#   'temperature_min': float,     # Min temp (°C)
#   'temperature_max': float,     # Max temp (°C)
#   'precipitation_sum': float,   # Total precip (mm)
#   'soil_moisture_mean': float,  # Mean soil moisture (m³/m³)
#   'runoff_sum': float          # Total runoff (mm)
# }

# Get latest conditions
latest = fetcher.get_latest_conditions(delhi_bounds)
# Returns: {
#   'temperature_c': float,
#   'precipitation_mm': float,
#   'soil_moisture': float,
#   'runoff_mm': float
# }
```

### 3. AlphaEarthFetcher

**Source**: GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL
**Resolution**: 10m
**Coverage**: Global
**Bands**: 64-dimensional embeddings (A00-A63)

```python
from src.data import alphaearth_fetcher

# Get embeddings for a region
embeddings = alphaearth_fetcher.fetch(
    bounds=(28.4, 76.8, 28.9, 77.4),
    year=2023
)
```

### 4. DEMFetcher

**Source**: USGS/SRTMGL1_003
**Resolution**: 30m
**Coverage**: Global (60°N - 56°S)

```python
from src.data import dem_fetcher

# Get elevation data
elevation = dem_fetcher.fetch(
    bounds=(28.4, 76.8, 28.9, 77.4)
)
```

### 5. SurfaceWaterFetcher

**Source**: JRC/GSW1_4/GlobalSurfaceWater
**Resolution**: 30m
**Coverage**: Global, 1984-2021

```python
from src.data import surface_water_fetcher

# Get historical water occurrence
water_data = surface_water_fetcher.fetch(
    bounds=(28.4, 76.8, 28.9, 77.4)
)
```

## Architecture

```
BaseDataFetcher (Abstract)
├── Caching logic (pickle-based)
├── Error handling (DataFetchError)
└── Cache TTL management

PrecipitationFetcher
├── source_name: "precipitation"
├── cache_ttl_days: 1
└── Methods:
    ├── fetch() -> DataFrame
    └── get_rainfall_features() -> Dict

ERA5Fetcher
├── source_name: "era5"
├── cache_ttl_days: 1
└── Methods:
    ├── fetch() -> DataFrame
    ├── get_weather_features() -> Dict
    └── get_latest_conditions() -> Dict
```

## Caching

All fetchers use automatic file-based caching:

```python
# Cache location: ./cache/{source_name}/{hash}.pkl

# Force refresh (bypass cache)
df = fetcher.fetch(bounds, start_date, end_date, force_refresh=True)

# Clear all cache for a source
fetcher.clear_cache()

# Disable caching
fetcher = PrecipitationFetcher(cache_enabled=False)
```

## Error Handling

```python
from src.data import DataFetchError

try:
    df = fetcher.fetch(bounds, start_date, end_date)
except DataFetchError as e:
    print(f"Failed to fetch data: {e}")
```

## GEE Authentication

Before using any fetchers, ensure GEE is authenticated:

```python
import ee

# One-time setup
ee.Authenticate()

# Every session (automatic in fetchers)
ee.Initialize(project='gen-lang-client-0669818939')
```

## Configuration

Settings in `src/core/config.py`:

```python
# Dataset IDs
GEE_PRECIPITATION = 'UCSB-CHG/CHIRPS/DAILY'
GEE_ERA5_LAND = 'ECMWF/ERA5_LAND/DAILY_AGGR'

# Cache TTLs
CACHE_TTL_PRECIPITATION = 1  # days
CACHE_TTL_ERA5 = 1  # days

# Request limits
MAX_PIXELS_PER_REQUEST = 10_000_000
REQUEST_RETRY_COUNT = 3
REQUEST_TIMEOUT_SECONDS = 300
```

## Testing

Run the test suite:

```bash
cd apps/ml-service
python examples/test_data_fetchers.py
```

## Usage in Models

Typical workflow for model training:

```python
from src.data import PrecipitationFetcher, ERA5Fetcher
from datetime import datetime, timedelta

# Initialize fetchers
precip_fetcher = PrecipitationFetcher()
era5_fetcher = ERA5Fetcher()

# Define region and dates
delhi_bounds = (28.4, 76.8, 28.9, 77.4)
end_date = datetime(2024, 7, 15)
start_date = end_date - timedelta(days=30)

# Fetch raw data
precip_df = precip_fetcher.fetch(delhi_bounds, start_date, end_date)
era5_df = era5_fetcher.fetch(delhi_bounds, start_date, end_date)

# Get features for specific date
features = {}
features.update(precip_fetcher.get_rainfall_features(
    delhi_bounds, end_date, lookback_days=7
))
features.update(era5_fetcher.get_weather_features(
    delhi_bounds, end_date, lookback_days=7
))

# Use features in model
# X = features_to_array(features)
# y_pred = model.predict(X)
```

## Real-time Predictions

For real-time flood prediction:

```python
from datetime import datetime

# Get latest data
reference_date = datetime.now()

# Note: ERA5 has 5-day lag, so adjust
era5_date = reference_date - timedelta(days=6)

# Combine features
features = {}

# Precipitation (up-to-date)
features.update(precip_fetcher.get_rainfall_features(
    bounds, reference_date, lookback_days=7
))

# ERA5 weather (5-day lag)
features.update(era5_fetcher.get_weather_features(
    bounds, era5_date, lookback_days=7
))

# Make prediction
risk_score = model.predict(features)
```

## Data Quality

### CHIRPS Precipitation
- High accuracy in tropics/subtropics
- Validated against rain gauges
- May underestimate in mountainous regions

### ERA5-Land
- Reanalysis product (model + observations)
- 5-day production lag
- Good for historical analysis
- Use with caution for real-time forecasting

## Coordinate System

All fetchers use **EPSG:4326** (WGS84):
- Bounds format: `(lat_min, lng_min, lat_max, lng_max)`
- Latitude: -90 to +90
- Longitude: -180 to +180

## Best Practices

1. **Use appropriate lookback periods**:
   - Precipitation: 7-14 days (monsoon memory)
   - ERA5: 7-30 days (seasonal patterns)

2. **Handle missing data**:
   ```python
   if df.empty:
       # Use default/fallback values
       features = get_default_features()
   ```

3. **Respect GEE quotas**:
   - Enable caching (default)
   - Batch requests when possible
   - Monitor `MAX_PIXELS_PER_REQUEST`

4. **Account for data lags**:
   - CHIRPS: ~1 day lag
   - ERA5: ~5 day lag

5. **Validate bounds**:
   ```python
   lat_min, lng_min, lat_max, lng_max = bounds
   assert -90 <= lat_min < lat_max <= 90
   assert -180 <= lng_min < lng_max <= 180
   ```

## Future Enhancements

- [ ] IMD rainfall data (when API available)
- [ ] GloFAS river discharge
- [ ] Sentinel-1 SAR for flood mapping
- [ ] Near real-time precipitation (GPM IMERG)
- [ ] Soil type and permeability data
- [ ] River network topology
