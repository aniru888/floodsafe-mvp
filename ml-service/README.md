# FloodSafe ML Service

Ensemble machine learning service for flood prediction using Google Earth Engine datasets.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   ENSEMBLE MODEL                            │
├─────────────────────────────────────────────────────────────┤
│  ARIMA (20%) + Prophet (30%) + LSTM+Attention (50%)       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              FEATURE VECTOR (79 dimensions)                 │
├─────────────────────────────────────────────────────────────┤
│  • AlphaEarth Embeddings (64): Satellite terrain features   │
│  • Terrain (6): Elevation, slope, aspect                   │
│  • Precipitation (5): 24h, 3d, 7d rainfall                 │
│  • Temporal (4): Seasonality, monsoon indicator            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (GEE)                       │
├─────────────────────────────────────────────────────────────┤
│  • GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL                     │
│  • USGS/SRTMGL1_003 (SRTM DEM)                            │
│  • JRC/GSW1_4/GlobalSurfaceWater                           │
│  • UCSB-CHG/CHIRPS/DAILY                                   │
│  • ECMWF/ERA5_LAND/DAILY_AGGR                              │
│  • ESA/WorldCover/v200                                     │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Setup Environment

```bash
cd apps/ml-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure GEE Authentication

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set:
# GCP_PROJECT_ID=gen-lang-client-0669818939
# GEE_SERVICE_ACCOUNT_KEY=./credentials/gee-service-account.json

# Or use OAuth flow (one-time)
python -c "import ee; ee.Authenticate()"
```

### 3. Run Service

```bash
# Development
uvicorn src.main:app --reload --port 8002

# Production
uvicorn src.main:app --host 0.0.0.0 --port 8002 --workers 4
```

### 4. Access API

- Docs: http://localhost:8002/api/v1/docs
- Health: http://localhost:8002/api/v1/predictions/health

## API Endpoints

### POST /api/v1/predictions/forecast

Get 7-day flood probability forecast for a location.

**Request:**
```json
{
  "latitude": 28.6315,
  "longitude": 77.2167,
  "horizon_days": 7,
  "include_uncertainty": true
}
```

**Response:**
```json
{
  "latitude": 28.6315,
  "longitude": 77.2167,
  "predictions": [
    {
      "date": "2024-07-16",
      "flood_probability": 0.32,
      "risk_level": "moderate"
    }
  ],
  "model_contributions": {
    "ARIMA-Flood": [0.28, ...],
    "Prophet-Flood": [0.35, ...],
    "LSTM-Attention-Flood": [0.31, ...]
  },
  "metadata": {
    "model": "Ensemble-Flood",
    "generated_at": "2024-07-15T10:30:00",
    "feature_dim": 79
  }
}
```

### POST /api/v1/predictions/risk-assessment

Get static flood risk assessment for a location.

**Request:**
```json
{
  "latitude": 28.6315,
  "longitude": 77.2167,
  "radius_km": 5.0
}
```

**Response:**
```json
{
  "risk_level": "moderate",
  "risk_score": 0.45,
  "factors": {
    "elevation_factor": 0.5,
    "slope_factor": 0.6,
    "water_history_factor": 0.3,
    "built_area_factor": 0.7,
    "drainage_factor": 0.4
  },
  "recommendations": [
    "Standard monsoon precautions advised",
    "High urbanization increases runoff - check local drain capacity"
  ]
}
```

## Data Exploration

Run Jupyter notebooks to explore datasets:

```bash
cd notebooks
jupyter notebook

# Run in order:
# 1. 01_gee_connection.ipynb - Verify GEE access
# 2. 02_alphaearth_exploration.ipynb - Explore embeddings
# 3. 03_precipitation_analysis.ipynb - Rainfall patterns
# 4. 04_terrain_features.ipynb - DEM and water history
```

## Model Training

```python
from src.models.ensemble import create_default_ensemble
from src.features.extractor import FeatureExtractor
import numpy as np

# Create ensemble
ensemble = create_default_ensemble()

# Extract features (example)
extractor = FeatureExtractor()
# ... load training data ...

# Train ensemble
ensemble.fit(X_train, y_train, epochs=100)

# Save
ensemble.save("./models/ensemble")
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_models/test_arima.py
```

## Docker Deployment

```bash
# Build image
docker build -t floodsafe-ml:latest .

# Run container
docker run -p 8002:8002 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/cache:/app/cache \
  -e GCP_PROJECT_ID=gen-lang-client-0669818939 \
  floodsafe-ml:latest
```

## Project Structure

```
apps/ml-service/
├── src/
│   ├── core/           # Config, settings
│   ├── data/           # GEE data fetchers
│   ├── embeddings/     # (Deprecated, merged into data/)
│   ├── features/       # Feature extraction
│   ├── models/         # ARIMA, Prophet, LSTM, Ensemble
│   ├── evaluation/     # Metrics, backtesting
│   └── api/            # FastAPI endpoints
├── notebooks/          # Jupyter exploration
├── tests/              # Pytest tests
├── models/             # Saved model weights (.gitignore)
├── cache/              # Data cache (.gitignore)
├── requirements.txt
├── Dockerfile
└── README.md
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | `gen-lang-client-0669818939` |
| `GEE_SERVICE_ACCOUNT_KEY` | Path to GEE service account JSON | None (uses OAuth) |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `MODEL_CACHE_DIR` | Directory for saved models | `./models` |
| `DATA_CACHE_DIR` | Directory for data cache | `./cache` |
| `CACHE_TTL_ALPHAEARTH` | AlphaEarth cache TTL (days) | `7` |
| `CACHE_TTL_DEM` | DEM cache TTL (days) | `365` |
| `CACHE_TTL_PRECIPITATION` | Precipitation cache TTL (days) | `1` |

## Performance

- **Inference Time**: ~2-5 seconds per prediction (includes GEE queries)
- **Cache Hit**: ~100ms per prediction
- **Feature Dimension**: 79
- **Model Weights**: ~50MB (LSTM), ~5MB (ARIMA+Prophet)

## Limitations

- **Geographic Scope**: Currently optimized for Delhi NCR
- **Temporal Resolution**: Daily predictions (not hourly)
- **Cold Start**: First prediction requires GEE data fetch (~5s)
- **GEE Quotas**: Cached to avoid hitting limits

## Contributing

1. Add new data fetchers in `src/data/`
2. Inherit from `BaseDataFetcher`
3. Implement caching and error handling
4. Add tests in `tests/test_data/`
5. Update feature extractor if needed

## License

MIT License - FloodSafe Nonprofit Project
