# AlphaEarth Data Fetcher

## Overview

The `AlphaEarthFetcher` class provides access to Google's AlphaEarth embeddings via Google Earth Engine (GEE). AlphaEarth offers 64-dimensional pre-computed embeddings at 10-meter resolution, derived from satellite imagery.

**Dataset:** `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
**Resolution:** 10 meters
**Bands:** A00 through A63 (64 dimensions)
**Frequency:** Annual updates

## Use Cases for Flood Modeling

1. **Terrain Classification** - Embeddings capture land use patterns (urban, agricultural, water bodies)
2. **Feature Extraction** - Use as input features for LSTM/ensemble models
3. **Risk Profiling** - Compare embeddings of flood-prone vs safe areas
4. **Change Detection** - Track terrain changes across years

## Setup

### 1. GEE Authentication

```python
import ee

# One-time browser authentication
ee.Authenticate()

# Initialize with FloodSafe project
ee.Initialize(project='gen-lang-client-0669818939')
```

### 2. Import the Fetcher

```python
from src.data.alphaearth import alphaearth_fetcher
```

## Basic Usage

### Get Embedding at a Single Point

```python
# Delhi center coordinates
lat, lng = 28.6139, 77.2090

# Fetch 64-dimensional embedding
embedding = alphaearth_fetcher.get_embedding_at_point(lat, lng, year=2023)

print(embedding.shape)  # Output: (64,)
print(embedding[:5])    # First 5 dimensions: [0.23, -0.45, 0.67, ...]
```

**Parameters:**
- `lat` (float): Latitude
- `lng` (float): Longitude
- `year` (int): Year to fetch (default: 2023)
- `buffer_radius_m` (float): Buffer radius for sampling (default: 10.0m)

**Returns:** `np.ndarray` of shape `(64,)`

### Get Aggregated Embedding for a Region

```python
# Delhi NCR bounds (lat_min, lng_min, lat_max, lng_max)
bounds = (28.4, 76.8, 28.9, 77.4)

# Get mean embedding for entire region
avg_embedding = alphaearth_fetcher.get_aggregated_embedding(
    bounds=bounds,
    year=2023,
    method='mean',  # Options: 'mean', 'median', 'stdDev'
    scale=100       # Resolution in meters
)

print(avg_embedding.shape)  # Output: (64,)
```

**Parameters:**
- `bounds` (tuple): `(lat_min, lng_min, lat_max, lng_max)`
- `year` (int): Year to fetch (default: 2023)
- `method` (str): Aggregation method - `'mean'`, `'median'`, or `'stdDev'` (default: `'mean'`)
- `scale` (int): Resolution for aggregation in meters (default: 100)

**Returns:** `np.ndarray` of shape `(64,)`

**Use Cases:**
- Summarize terrain characteristics for a city/neighborhood
- Compare embeddings between different regions
- Generate region-level features for ML models

### Get Spatial Embeddings as a Grid

```python
# Small region for testing (avoid exceeding GEE pixel limits)
small_bounds = (28.6, 77.2, 28.65, 77.25)

# Get embeddings at every pixel
embeddings_grid = alphaearth_fetcher.get_region_embeddings(
    bounds=small_bounds,
    year=2023,
    scale=100  # 100m resolution (use larger for bigger regions)
)

print(embeddings_grid.shape)  # Output: (H, W, 64)
# Example: (56, 62, 64) = 56 rows x 62 cols x 64 embedding dimensions
```

**Parameters:**
- `bounds` (tuple): `(lat_min, lng_min, lat_max, lng_max)`
- `year` (int): Year to fetch (default: 2023)
- `scale` (int): Resolution in meters (default: 100)

**Returns:** `np.ndarray` of shape `(H, W, 64)` where H=height in pixels, W=width in pixels

**Warning:** Large regions at fine resolution can exceed GEE's 10M pixel limit. Use coarser scale (e.g., 100-500m) for large regions.

## Advanced Usage

### Caching Behavior

The fetcher automatically caches downloaded data for 7 days (configurable via `settings.CACHE_TTL_ALPHAEARTH`).

```python
# First call - fetches from GEE
embedding1 = alphaearth_fetcher.get_embedding_at_point(28.6139, 77.2090)

# Second call - loads from cache (instant)
embedding2 = alphaearth_fetcher.get_embedding_at_point(28.6139, 77.2090)

# Force refresh from GEE
embedding3 = alphaearth_fetcher.fetch(
    bounds=(28.6, 77.2, 28.62, 77.22),
    force_refresh=True,
    year=2023
)
```

Cache location: `./cache/alphaearth/`

### Clear Cache

```python
# Clear all cached AlphaEarth data
count = alphaearth_fetcher.clear_cache()
print(f"Deleted {count} cache files")
```

### Compare Embeddings Across Years

```python
# Track terrain changes over time
embedding_2020 = alphaearth_fetcher.get_aggregated_embedding(bounds, year=2020)
embedding_2023 = alphaearth_fetcher.get_aggregated_embedding(bounds, year=2023)

# Calculate change magnitude
change = np.linalg.norm(embedding_2023 - embedding_2020)
print(f"Terrain change magnitude: {change:.3f}")
```

## Integration with ML Models

### Feature Engineering

```python
import numpy as np
from src.data.alphaearth import alphaearth_fetcher

def extract_features_for_location(lat, lng, year=2023):
    """Extract AlphaEarth features for a flood report location."""

    # Get point embedding
    point_emb = alphaearth_fetcher.get_embedding_at_point(lat, lng, year)

    # Get neighborhood embedding (500m radius)
    bounds = (lat - 0.005, lng - 0.005, lat + 0.005, lng + 0.005)
    region_emb = alphaearth_fetcher.get_aggregated_embedding(bounds, year, method='mean')
    region_std = alphaearth_fetcher.get_aggregated_embedding(bounds, year, method='stdDev')

    # Combine features
    features = np.concatenate([point_emb, region_emb, region_std])  # Shape: (192,)

    return features

# Example: Extract features for all flood reports
flood_reports = [
    {"lat": 28.6139, "lng": 77.2090},
    {"lat": 28.7041, "lng": 77.1025},
]

feature_matrix = []
for report in flood_reports:
    features = extract_features_for_location(report["lat"], report["lng"])
    feature_matrix.append(features)

X = np.array(feature_matrix)  # Shape: (N_reports, 192)
```

### LSTM Input Preparation

```python
def prepare_lstm_features(bounds, years, scale=100):
    """Prepare temporal sequence of AlphaEarth embeddings for LSTM."""

    sequences = []
    for year in years:
        embedding = alphaearth_fetcher.get_aggregated_embedding(
            bounds=bounds,
            year=year,
            method='mean',
            scale=scale
        )
        sequences.append(embedding)

    # Stack into sequence: (time_steps, features)
    sequence = np.stack(sequences, axis=0)
    return sequence

# Example: 5-year sequence for Delhi
delhi_bounds = (28.4, 76.8, 28.9, 77.4)
years = [2019, 2020, 2021, 2022, 2023]

lstm_input = prepare_lstm_features(delhi_bounds, years)
print(lstm_input.shape)  # Output: (5, 64)
```

### Spatial Flood Risk Mapping

```python
import matplotlib.pyplot as plt

def create_risk_map(bounds, year=2023, scale=100):
    """Create a spatial map using AlphaEarth embeddings."""

    # Get spatial embeddings
    embeddings = alphaearth_fetcher.get_region_embeddings(
        bounds=bounds,
        year=year,
        scale=scale
    )  # Shape: (H, W, 64)

    # Use PCA or model to reduce to risk score
    # For now, use first principal component as proxy
    risk_scores = embeddings[:, :, 0]  # Shape: (H, W)

    # Visualize
    plt.figure(figsize=(10, 8))
    plt.imshow(risk_scores, cmap='RdYlBu_r', aspect='auto')
    plt.colorbar(label='Risk Score (proxy)')
    plt.title(f'Spatial Risk Map - Year {year}')
    plt.xlabel('Longitude (pixels)')
    plt.ylabel('Latitude (pixels)')
    plt.savefig(f'risk_map_{year}.png', dpi=150, bbox_inches='tight')

    return risk_scores

# Generate risk map for Delhi
delhi_bounds = (28.5, 77.1, 28.7, 77.3)
risk_map = create_risk_map(delhi_bounds, year=2023, scale=200)
```

## Error Handling

```python
from src.data.base import DataFetchError

try:
    embedding = alphaearth_fetcher.get_embedding_at_point(
        lat=28.6139,
        lng=77.2090,
        year=2030  # Invalid future year
    )
except DataFetchError as e:
    print(f"Fetch failed: {e}")
    # Fall back to alternative data source or use default values
    embedding = np.zeros(64)
```

## Performance Tips

### 1. Batch Processing

```python
# Process multiple points efficiently
points = [(28.6, 77.2), (28.7, 77.1), (28.8, 77.3)]

# Instead of individual calls:
# embeddings = [fetcher.get_embedding_at_point(lat, lng) for lat, lng in points]

# Use a region query with sampling (more efficient):
bounds = (28.5, 77.0, 28.9, 77.4)
region_data = alphaearth_fetcher.get_region_embeddings(bounds, scale=100)

# Then index into the grid for each point
```

### 2. Scale Selection

| Region Size | Recommended Scale |
|-------------|-------------------|
| Single point | 10m (default) |
| Neighborhood (<1 km²) | 50-100m |
| City district (1-10 km²) | 100-200m |
| Entire city (>10 km²) | 200-500m |

### 3. Cache Management

```python
# Clear cache periodically (weekly cron job)
if datetime.now().weekday() == 0:  # Monday
    alphaearth_fetcher.clear_cache()
```

## Configuration

Configuration in `src/core/config.py`:

```python
class Settings:
    # GEE Dataset
    GEE_ALPHAEARTH: str = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"

    # Cache TTL
    CACHE_TTL_ALPHAEARTH: int = 7  # days

    # GEE Limits
    MAX_PIXELS_PER_REQUEST: int = 10_000_000
    REQUEST_RETRY_COUNT: int = 3
    REQUEST_TIMEOUT_SECONDS: int = 300
```

## References

- [Google AlphaEarth Dataset](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL)
- [GEE Python API](https://developers.google.com/earth-engine/guides/python_install)
- FloodSafe ML Agent: `@ml-data` context

## Next Steps

1. **Combine with DEM data** - Stack AlphaEarth embeddings with elevation for richer features
2. **Train classifier** - Use embeddings to classify flood-prone vs safe areas
3. **Temporal analysis** - Track terrain changes across multiple years
4. **Feature selection** - Identify which embedding dimensions are most predictive

---

**Status:** Production Ready
**Last Updated:** 2025-12-10
**Maintainer:** FloodSafe ML Team
