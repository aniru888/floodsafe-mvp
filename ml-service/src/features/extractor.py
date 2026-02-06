"""
Feature Extractor for Flood Prediction.

Combines data from all sources into a unified feature vector.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from ..core.config import settings, REGIONS

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Extract and combine features from all data sources.

    Feature Vector Structure (37 dimensions by default):
    - [0:9]    Dynamic World: 9 land cover probabilities (includes flooded_vegetation)
    - [9:15]   ESA WorldCover: 6 static land cover percentages
    - [15:20]  Sentinel-2: 5 spectral indices (NDWI, NDVI, NDBI, MNDWI, BSI)
    - [20:26]  Terrain: elev_mean, elev_min, elev_max, elev_range, slope, aspect
    - [26:31]  Precipitation (historical): rain_24h, rain_3d, rain_7d, max_daily, wet_days
    - [31:35]  Temporal: day_of_year, month, is_monsoon, days_since_monsoon
    - [35:37]  GloFAS: discharge_mean, discharge_max (river discharge/runoff)

    Optional (enable_forecast=True for 40 dimensions):
    - [31:34]  Precipitation (forecast): forecast_24h, forecast_48h, forecast_72h
    - [34:38]  Temporal: shifted by 3
    - [38:40]  GloFAS: shifted by 3

    Note: Forecast features disabled by default to match existing training data (37-dim).
    """

    FEATURE_DIM = 37  # Default without forecast (use 40 with enable_forecast=True)
    DYNAMIC_WORLD_DIM = 9  # Dynamic World land cover probabilities
    LANDCOVER_DIM = 6  # ESA WorldCover
    SENTINEL2_DIM = 5  # Sentinel-2 spectral indices
    TERRAIN_DIM = 6
    PRECIP_DIM = 5
    PRECIP_FORECAST_DIM = 3  # Optional: 24h, 48h, 72h forecast (only if enable_forecast=True)
    TEMPORAL_DIM = 4
    GLOFAS_DIM = 2

    def __init__(self, lazy_load: bool = True, use_wavelet: bool = False, enable_forecast: bool = False):
        """
        Initialize feature extractor.

        Args:
            lazy_load: If True, defer loading data fetchers until first use
            use_wavelet: If True, apply wavelet preprocessing to precipitation features
            enable_forecast: If True, include rainfall forecast features (default: True)
        """
        self.lazy_load = lazy_load
        self.use_wavelet = use_wavelet
        self._enable_forecast = enable_forecast
        self._fetchers_loaded = False
        self._dynamic_world = None  # NEW: replaces AlphaEarth
        self._landcover = None  # NEW: ESA WorldCover
        self._sentinel2 = None  # NEW: spectral indices
        self._dem = None
        self._precipitation = None
        self._surface_water = None
        self._glofas = None
        self._rainfall_forecast = None  # NEW: rainfall forecast fetcher

        # Initialize wavelet preprocessor if enabled
        self._wavelet = None
        if use_wavelet:
            from .wavelet import WaveletPreprocessor
            self._wavelet = WaveletPreprocessor(wavelet='db4', level=3)
            logger.info("Wavelet preprocessing enabled (db4, level=3)")

    def _load_fetchers(self) -> None:
        """Load data fetchers on first use."""
        if self._fetchers_loaded:
            return

        try:
            from ..data.dynamic_world import DynamicWorldFetcher
            from ..data.landcover import LandcoverFetcher
            from ..data.sentinel2 import Sentinel2Fetcher
            from ..data.dem_fetcher import DEMFetcher
            from ..data.precipitation import PrecipitationFetcher
            from ..data.surface_water import SurfaceWaterFetcher
            from ..data.glofas import GloFASFetcher

            self._dynamic_world = DynamicWorldFetcher()
            self._landcover = LandcoverFetcher()
            self._sentinel2 = Sentinel2Fetcher()
            self._dem = DEMFetcher()
            self._precipitation = PrecipitationFetcher()
            self._surface_water = SurfaceWaterFetcher()
            self._glofas = GloFASFetcher()

            # Load rainfall forecast fetcher if enabled
            if self._enable_forecast:
                try:
                    from ..data.rainfall_forecast import RainfallForecastFetcher
                    self._rainfall_forecast = RainfallForecastFetcher()
                    logger.info("Rainfall forecast fetcher loaded")
                except ImportError as e:
                    logger.warning(f"Rainfall forecast fetcher not available: {e}")

            self._fetchers_loaded = True
            logger.info(f"Feature extractor: all data fetchers loaded ({self.FEATURE_DIM}-dim vector)")

        except ImportError as e:
            logger.warning(f"Some fetchers not available: {e}")
            self._fetchers_loaded = True

    def extract_features(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
        include_dynamic_world: bool = True,
        include_landcover: bool = True,
        include_sentinel2: bool = True,
        include_terrain: bool = True,
        include_precipitation: bool = True,
        include_forecast: bool = True,
        include_temporal: bool = True,
        include_glofas: bool = True,
    ) -> Dict[str, np.ndarray]:
        """
        Extract all features for a region and time.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            reference_date: Date to compute features for
            include_dynamic_world: Include Dynamic World land cover probabilities
            include_landcover: Include ESA WorldCover features
            include_sentinel2: Include Sentinel-2 spectral indices
            include_terrain: Include DEM features
            include_precipitation: Include rainfall features (historical)
            include_forecast: Include rainfall forecast features
            include_temporal: Include time-based features
            include_glofas: Include GloFAS discharge features

        Returns:
            Dict with feature groups and combined vector:
                - dynamic_world: (9,) land cover probabilities
                - landcover: (6,) ESA WorldCover features
                - sentinel2: (5,) spectral indices
                - terrain: (6,) DEM features
                - precipitation: (5,) historical rainfall features
                - forecast: (3,) rainfall forecast features
                - temporal: (4,) time features
                - glofas: (2,) GloFAS discharge features
                - combined: (40,) all features concatenated
        """
        if not self.lazy_load:
            self._load_fetchers()

        features = {}

        # 1. Dynamic World Land Cover Probabilities (9 dims)
        if include_dynamic_world:
            features["dynamic_world"] = self._extract_dynamic_world(bounds, reference_date)
        else:
            features["dynamic_world"] = np.zeros(self.DYNAMIC_WORLD_DIM)

        # 2. ESA WorldCover Static Land Cover (6 dims)
        if include_landcover:
            features["landcover"] = self._extract_landcover(bounds)
        else:
            features["landcover"] = np.zeros(self.LANDCOVER_DIM)

        # 3. Sentinel-2 Spectral Indices (5 dims)
        if include_sentinel2:
            features["sentinel2"] = self._extract_sentinel2(bounds, reference_date)
        else:
            features["sentinel2"] = np.zeros(self.SENTINEL2_DIM)

        # 4. Terrain Features (6 dims)
        if include_terrain:
            features["terrain"] = self._extract_terrain(bounds)
        else:
            features["terrain"] = np.zeros(self.TERRAIN_DIM)

        # 5. Precipitation Features (5 dims)
        if include_precipitation:
            features["precipitation"] = self._extract_precipitation(bounds, reference_date)
        else:
            features["precipitation"] = np.zeros(self.PRECIP_DIM)

        # 6. Precipitation Forecast Features (3 dims) - NEW
        if include_forecast and self._enable_forecast:
            # Calculate center point from bounds
            lat = (bounds[0] + bounds[2]) / 2
            lng = (bounds[1] + bounds[3]) / 2
            try:
                features["forecast"] = self._extract_precipitation_forecast(lat, lng)
            except Exception as e:
                # If forecast fails, log warning and use zeros (graceful degradation)
                logger.warning(f"Forecast extraction failed, using zeros: {e}")
                features["forecast"] = np.zeros(self.PRECIP_FORECAST_DIM)
        else:
            features["forecast"] = np.zeros(self.PRECIP_FORECAST_DIM)

        # 7. Temporal Features (4 dims)
        if include_temporal:
            features["temporal"] = self._extract_temporal(reference_date)
        else:
            features["temporal"] = np.zeros(self.TEMPORAL_DIM)

        # 8. GloFAS Discharge Features (2 dims)
        if include_glofas:
            features["glofas"] = self._extract_glofas(bounds, reference_date)
        else:
            features["glofas"] = np.zeros(self.GLOFAS_DIM)

        # Combine all features (37 default, 40 with forecast)
        if self._enable_forecast:
            # 40-dim with forecast
            features["combined"] = np.concatenate([
                features["dynamic_world"],
                features["landcover"],
                features["sentinel2"],
                features["terrain"],
                features["precipitation"],
                features["forecast"],
                features["temporal"],
                features["glofas"],
            ])
        else:
            # 37-dim without forecast (matches training data)
            features["combined"] = np.concatenate([
                features["dynamic_world"],
                features["landcover"],
                features["sentinel2"],
                features["terrain"],
                features["precipitation"],
                features["temporal"],
                features["glofas"],
            ])

        return features

    def _extract_dynamic_world(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
    ) -> np.ndarray:
        """Extract Dynamic World land cover probabilities (9 dims)."""
        self._load_fetchers()

        if self._dynamic_world is None:
            logger.warning("Dynamic World fetcher not available, using zeros")
            return np.zeros(self.DYNAMIC_WORLD_DIM)

        try:
            result = self._dynamic_world.get_flood_features(bounds, reference_date)
            return np.array([
                result.get("water_prob", 0),
                result.get("trees_prob", 0),
                result.get("grass_prob", 0),
                result.get("flooded_vegetation_prob", 0),  # CRITICAL
                result.get("crops_prob", 0),
                result.get("shrub_and_scrub_prob", 0),
                result.get("built_prob", 0),
                result.get("bare_prob", 0),
                result.get("snow_and_ice_prob", 0),
            ])
        except Exception as e:
            logger.warning(f"Failed to get Dynamic World features: {e}")
            return np.zeros(self.DYNAMIC_WORLD_DIM)

    def _extract_landcover(
        self,
        bounds: Tuple[float, float, float, float],
    ) -> np.ndarray:
        """Extract ESA WorldCover static land cover features (6 dims)."""
        self._load_fetchers()

        if self._landcover is None:
            logger.warning("Landcover fetcher not available, using zeros")
            return np.zeros(self.LANDCOVER_DIM)

        try:
            result = self._landcover.get_landcover_features(bounds)
            return np.array([
                result.get("built_up_pct", 0),
                result.get("vegetation_pct", 0),
                result.get("water_pct", 0),
                result.get("cropland_pct", 0),
                result.get("impervious_pct", 0),
                result.get("permeable_pct", 0),
            ])
        except Exception as e:
            logger.warning(f"Failed to get landcover features: {e}")
            return np.zeros(self.LANDCOVER_DIM)

    def _extract_sentinel2(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
    ) -> np.ndarray:
        """Extract Sentinel-2 spectral indices (5 dims)."""
        self._load_fetchers()

        if self._sentinel2 is None:
            logger.warning("Sentinel-2 fetcher not available, using zeros")
            return np.zeros(self.SENTINEL2_DIM)

        try:
            result = self._sentinel2.get_flood_features(bounds, reference_date)
            return np.array([
                result.get("NDWI", 0),
                result.get("NDVI", 0),
                result.get("NDBI", 0),
                result.get("MNDWI", 0),
                result.get("BSI", 0),
            ])
        except Exception as e:
            logger.warning(f"Failed to get Sentinel-2 indices: {e}")
            return np.zeros(self.SENTINEL2_DIM)

    def _extract_terrain(
        self,
        bounds: Tuple[float, float, float, float],
    ) -> np.ndarray:
        """Extract terrain features (6 dims)."""
        self._load_fetchers()

        if self._dem is None:
            logger.warning("DEM fetcher not available, using zeros")
            return np.zeros(self.TERRAIN_DIM)

        try:
            terrain = self._dem.get_terrain_features(bounds)
            return np.array([
                terrain.get("elevation_mean", 0),
                terrain.get("elevation_min", 0),
                terrain.get("elevation_max", 0),
                terrain.get("elevation_range", 0),
                terrain.get("slope_mean", 0),
                terrain.get("aspect_mean", 0),
            ])
        except Exception as e:
            logger.warning(f"Failed to get terrain features: {e}")
            return np.zeros(self.TERRAIN_DIM)

    def _extract_precipitation(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
        lookback_days: int = 7,
    ) -> np.ndarray:
        """Extract precipitation features (5 dims)."""
        self._load_fetchers()

        if self._precipitation is None:
            logger.warning("Precipitation fetcher not available, using zeros")
            return np.zeros(self.PRECIP_DIM)

        try:
            precip = self._precipitation.get_rainfall_features(
                bounds, reference_date, lookback_days=lookback_days
            )
            return np.array([
                precip.get("rainfall_24h", 0),
                precip.get("rainfall_3d", 0),
                precip.get("rainfall_7d", 0),
                precip.get("max_daily_7d", 0),
                precip.get("wet_days_7d", 0),
            ])
        except Exception as e:
            logger.warning(f"Failed to get precipitation features: {e}")
            return np.zeros(self.PRECIP_DIM)

    def _extract_precipitation_forecast(
        self,
        lat: float,
        lng: float,
    ) -> np.ndarray:
        """
        Extract precipitation forecast features (3 dims).

        IMPORTANT: This method does NOT return zeros for missing data.
        If forecast is unavailable, it raises RainfallForecastError.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Array of [rain_forecast_24h, rain_forecast_48h, rain_forecast_72h]

        Raises:
            RainfallForecastError: If forecast data is unavailable
        """
        self._load_fetchers()

        if self._rainfall_forecast is None:
            if self._enable_forecast:
                raise RuntimeError("Rainfall forecast fetcher not initialized but forecast enabled")
            logger.info("Forecast disabled, using zeros")
            return np.zeros(self.PRECIP_FORECAST_DIM)

        try:
            from ..data.rainfall_forecast import RainfallForecastError

            forecast = self._rainfall_forecast.get_forecast(lat, lng)

            return np.array([
                forecast.rain_forecast_24h,
                forecast.rain_forecast_48h,
                forecast.rain_forecast_72h,
            ])

        except RainfallForecastError as e:
            logger.error(f"Failed to get rainfall forecast for ({lat}, {lng}): {e}")
            raise  # NO silent fallback to zeros

    def _extract_temporal(self, reference_date: datetime) -> np.ndarray:
        """Extract temporal features (4 dims)."""
        day_of_year = reference_date.timetuple().tm_yday / 365.0
        month = reference_date.month

        # Monsoon season in India: June-September (months 6-9)
        is_monsoon = 1.0 if 6 <= month <= 9 else 0.0

        # Days since monsoon start (June 1)
        year = reference_date.year
        monsoon_start = datetime(year, 6, 1)

        if reference_date < monsoon_start:
            # Before monsoon this year, count from last year
            monsoon_start = datetime(year - 1, 6, 1)

        days_since_monsoon = (reference_date - monsoon_start).days

        return np.array([
            day_of_year,
            float(month),
            is_monsoon,
            float(days_since_monsoon),
        ])

    def _extract_glofas(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
    ) -> np.ndarray:
        """Extract GloFAS discharge features (2 dims)."""
        self._load_fetchers()

        if self._glofas is None:
            logger.warning("GloFAS fetcher not available, using zeros")
            return np.zeros(self.GLOFAS_DIM)

        try:
            discharge = self._glofas.get_discharge_features(bounds, reference_date)
            return np.array([
                discharge.get("discharge_mean", 0),
                discharge.get("discharge_max", 0),
            ])
        except Exception as e:
            logger.warning(f"Failed to get GloFAS features: {e}")
            return np.zeros(self.GLOFAS_DIM)

    def extract_for_point(
        self,
        lat: float,
        lng: float,
        reference_date: datetime,
        radius_km: float = 5.0,
    ) -> Dict[str, np.ndarray]:
        """
        Extract features for a single point with buffer.

        Args:
            lat: Latitude
            lng: Longitude
            reference_date: Date for temporal features
            radius_km: Buffer radius in km

        Returns:
            Feature dict
        """
        # Convert point + radius to bounds
        # Approximate: 1 degree lat ≈ 111km
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * np.cos(np.radians(lat)))

        bounds = (
            lat - lat_delta,
            lng - lng_delta,
            lat + lat_delta,
            lng + lng_delta,
        )

        return self.extract_features(bounds, reference_date)

    def get_feature_names(self) -> List[str]:
        """Get ordered list of feature names."""
        names = []

        # Dynamic World land cover probabilities
        names.extend([
            "dw_water",
            "dw_trees",
            "dw_grass",
            "dw_flooded_veg",
            "dw_crops",
            "dw_shrub",
            "dw_built",
            "dw_bare",
            "dw_snow",
        ])

        # ESA WorldCover static features
        names.extend([
            "lc_built_up",
            "lc_vegetation",
            "lc_water",
            "lc_cropland",
            "lc_impervious",
            "lc_permeable",
        ])

        # Sentinel-2 spectral indices
        names.extend([
            "s2_ndwi",
            "s2_ndvi",
            "s2_ndbi",
            "s2_mndwi",
            "s2_bsi",
        ])

        # Terrain features
        names.extend([
            "elev_mean",
            "elev_min",
            "elev_max",
            "elev_range",
            "slope_mean",
            "aspect_mean",
        ])

        # Precipitation features (historical)
        names.extend([
            "rain_24h",
            "rain_3d",
            "rain_7d",
            "rain_max_7d",
            "wet_days_7d",
        ])

        # Precipitation forecast features (only if enabled)
        if self._enable_forecast:
            names.extend([
                "forecast_24h",
                "forecast_48h",
                "forecast_72h",
            ])

        # Temporal features
        names.extend([
            "day_of_year",
            "month",
            "is_monsoon",
            "days_since_monsoon",
        ])

        # GloFAS discharge features
        names.extend([
            "discharge_mean",
            "discharge_max",
        ])

        return names

    def get_feature_indices(self) -> Dict[str, Tuple[int, int]]:
        """Get start and end indices for each feature group."""
        if self._enable_forecast:
            # 40-dim with forecast
            return {
                "dynamic_world": (0, 9),
                "landcover": (9, 15),
                "sentinel2": (15, 20),
                "terrain": (20, 26),
                "precipitation": (26, 31),
                "forecast": (31, 34),
                "temporal": (34, 38),
                "glofas": (38, 40),
            }
        else:
            # 37-dim without forecast (default)
            return {
                "dynamic_world": (0, 9),
                "landcover": (9, 15),
                "sentinel2": (15, 20),
                "terrain": (20, 26),
                "precipitation": (26, 31),
                "temporal": (31, 35),
                "glofas": (35, 37),
            }

    def apply_wavelet_preprocessing(
        self,
        feature_sequence: np.ndarray,
        denoise: bool = True
    ) -> np.ndarray:
        """
        Apply wavelet preprocessing to a sequence of features.

        This should be called on training data sequences, not single timesteps.
        Wavelet transform requires multiple timesteps to decompose signals.

        Args:
            feature_sequence: Feature array of shape (n_timesteps, n_features)
                             where n_features = 37
            denoise: Whether to apply wavelet denoising

        Returns:
            Preprocessed feature sequence with same shape

        Example:
            >>> # During training data generation
            >>> features_seq = np.array([extractor.extract_for_point(...)
            ...                          for date in date_range])  # (30, 37)
            >>> features_preprocessed = extractor.apply_wavelet_preprocessing(features_seq)
        """
        if not self.use_wavelet or self._wavelet is None:
            logger.warning("Wavelet preprocessing not enabled. Returning original features.")
            return feature_sequence

        if feature_sequence.ndim != 2:
            raise ValueError(
                f"Expected 2D feature sequence (n_timesteps, n_features), "
                f"got shape {feature_sequence.shape}"
            )

        # Apply wavelet preprocessing to precipitation features
        precip_indices = list(range(26, 31))  # rain_24h, rain_3d, rain_7d, max, wet_days

        return self._wavelet.preprocess_features(
            feature_sequence,
            precip_indices=precip_indices,
            denoise=denoise
        )


# Default instance
feature_extractor = FeatureExtractor()
