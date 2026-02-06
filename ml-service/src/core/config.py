"""
ML Service Configuration.

GCP Project: gen-lang-client-0669818939
"""

from pydantic_settings import BaseSettings
from typing import List, Optional, Tuple


class Settings(BaseSettings):
    """ML Service Settings."""

    PROJECT_NAME: str = "FloodSafe ML Service"
    API_V1_STR: str = "/api/v1"

    # GCP Configuration
    GCP_PROJECT_ID: str = "gen-lang-client-0669818939"
    GEE_SERVICE_ACCOUNT_KEY: Optional[str] = None  # Path to JSON key
    GEE_ENABLED: bool = False  # Disabled for local run to avoid auth prompt

    # Database (shared with main backend)
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/floodsafe"

    # Model Configuration
    # Use /tmp for HF Spaces (read-only filesystem except /tmp)
    MODEL_CACHE_DIR: str = "./models"  # Models are bundled, not cached
    DATA_CACHE_DIR: str = "/tmp/ml-cache"  # Runtime cache must be in /tmp for HF

    # Default Region (Delhi NCR)
    DEFAULT_LATITUDE: float = 28.6139
    DEFAULT_LONGITUDE: float = 77.2090
    DEFAULT_RADIUS_KM: float = 50.0

    # GEE Dataset IDs
    GEE_ALPHAEARTH: str = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"  # DEPRECATED - doesn't cover Delhi
    GEE_DYNAMIC_WORLD: str = "GOOGLE/DYNAMICWORLD/V1"  # Replacement for AlphaEarth
    GEE_SENTINEL2: str = "COPERNICUS/S2_SR_HARMONIZED"  # Spectral indices
    GEE_DEM: str = "USGS/SRTMGL1_003"
    GEE_SURFACE_WATER: str = "JRC/GSW1_4/GlobalSurfaceWater"
    GEE_PRECIPITATION: str = "UCSB-CHG/CHIRPS/DAILY"
    GEE_ERA5_LAND: str = "ECMWF/ERA5_LAND/DAILY_AGGR"
    GEE_LANDCOVER: str = "ESA/WorldCover/v200"

    # Cache TTL (days)
    CACHE_TTL_ALPHAEARTH: int = 7
    CACHE_TTL_DEM: int = 365
    CACHE_TTL_PRECIPITATION: int = 1
    CACHE_TTL_ERA5: int = 1
    CACHE_TTL_SURFACE_WATER: int = 30
    CACHE_TTL_LANDCOVER: int = 90

    # Rainfall Forecast (Open-Meteo)
    OPENMETEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPENMETEO_FORECAST_DAYS: int = 3
    OPENMETEO_CACHE_TTL_HOURS: int = 1
    RAINFALL_FORECAST_ENABLED: bool = True

    # GEE Quota Management
    MAX_PIXELS_PER_REQUEST: int = 30_000_000
    REQUEST_RETRY_COUNT: int = 3
    REQUEST_TIMEOUT_SECONDS: int = 300

    # Training Configuration
    LSTM_SEQUENCE_LENGTH: int = 30
    LSTM_HIDDEN_SIZE: int = 128
    LSTM_NUM_LAYERS: int = 2
    BATCH_SIZE: int = 32
    LEARNING_RATE: float = 0.001

    # GNN Configuration
    GNN_HIDDEN_DIM: int = 64
    GNN_NUM_LAYERS: int = 3
    GNN_TYPE: str = "gcn"  # 'gcn' or 'gat'
    GNN_K_NEIGHBORS: int = 5
    GNN_MAX_DISTANCE_KM: Optional[float] = None
    GNN_DROPOUT: float = 0.3
    GNN_LEARNING_RATE: float = 0.001
    GNN_WEIGHT_DECAY: float = 1e-5
    GNN_EPOCHS: int = 100

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://localhost:5175",
    ]

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"  # Ignore extra env vars


settings = Settings()


# Geographic Regions
REGIONS = {
    "delhi": {
        "name": "Delhi NCR",
        "bounds": (28.4, 76.8, 28.9, 77.4),  # (lat_min, lng_min, lat_max, lng_max)
        "center": (28.6139, 77.2090),
        "epsg": 4326,
    },
}


# AlphaEarth band names
ALPHAEARTH_BANDS = [f"A{i:02d}" for i in range(64)]  # A00 to A63
