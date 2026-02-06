"""
Hotspot Feature Extractor for Urban Waterlogging Prediction.

Extracts an 18-dimensional research-backed feature vector for each hotspot location.
Uses validated data sources (CHIRPS, WorldCover, DEM, Sentinel-1 SAR).

Feature Vector (18 dimensions):
    TERRAIN (6):
    [0]  elevation      - meters above sea level (DEM)
    [1]  slope          - terrain slope in degrees
    [2]  tpi            - Topographic Position Index (flood-prone if negative)
    [3]  tri            - Terrain Ruggedness Index
    [4]  twi            - Topographic Wetness Index (higher = more water accumulation)
    [5]  spi            - Stream Power Index (flash flood indicator)

    PRECIPITATION (5):
    [6]  rainfall_24h   - mm in last 24 hours (CHIRPS)
    [7]  rainfall_3d    - mm in last 3 days (CHIRPS)
    [8]  rainfall_7d    - mm in last 7 days (CHIRPS)
    [9]  max_daily_7d   - max daily rainfall in 7 days (CHIRPS)
    [10] wet_days_7d    - days with >1mm rain (CHIRPS)

    LAND COVER (2):
    [11] impervious_pct - % impervious surface (WorldCover)
    [12] built_up_pct   - % built-up area (WorldCover)

    SAR (4) - CRITICAL FOR MONSOON:
    [13] sar_vv_mean    - Mean VV backscatter (dB)
    [14] sar_vh_mean    - Mean VH backscatter (dB)
    [15] sar_vv_vh_ratio - VV/VH ratio (water indicator)
    [16] sar_change_mag  - Change from baseline (negative = flooding)

    TEMPORAL (1):
    [17] is_monsoon     - 1 if June-September, else 0

Research References:
- Malda Study (2024): Stacking ensemble with terrain indices (0.965 AUC)
- Mumbai FSM (2025): XGBoost with SHAP validation (0.93 AUC)
- Sentinel-1 SAR: Cloud-penetrating flood detection for monsoon
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Feature names in order (18 dimensions)
FEATURE_NAMES = [
    # Terrain (6)
    "elevation",
    "slope",
    "tpi",
    "tri",
    "twi",
    "spi",
    # Precipitation (5)
    "rainfall_24h",
    "rainfall_3d",
    "rainfall_7d",
    "max_daily_7d",
    "wet_days_7d",
    # Land Cover (2)
    "impervious_pct",
    "built_up_pct",
    # SAR (4)
    "sar_vv_mean",
    "sar_vh_mean",
    "sar_vv_vh_ratio",
    "sar_change_mag",
    # Temporal (1)
    "is_monsoon",
]

FEATURE_DIM = 18

# Legacy 10-dim feature names (for backward compatibility)
FEATURE_NAMES_10DIM = [
    "elevation", "slope",
    "rainfall_24h", "rainfall_3d", "rainfall_7d", "max_daily_7d", "wet_days_7d",
    "impervious_pct", "built_up_pct",
    "is_monsoon",
]


class HotspotFeatureExtractor:
    """
    Extract 18-dimensional features for waterlogging hotspots.

    Uses validated data sources:
    - DEM (SRTM): elevation, slope
    - Terrain Indices: TPI, TRI, TWI, SPI
    - CHIRPS: precipitation features
    - ESA WorldCover: land cover percentages
    - Sentinel-1 SAR: cloud-penetrating flood detection
    - Temporal: monsoon indicator

    Research-backed feature selection from:
    - Malda Study (2024): Terrain indices improve accuracy
    - Mumbai FSM (2025): XGBoost with SHAP validation
    - SAR studies: Essential for monsoon cloud penetration
    """

    def __init__(self, lazy_load: bool = True, use_sar: bool = True, use_terrain_indices: bool = True):
        """
        Initialize feature extractor.

        Args:
            lazy_load: If True, defer loading data fetchers until first use
            use_sar: If True, include SAR features (requires GEE)
            use_terrain_indices: If True, include terrain indices (TPI, TRI, TWI, SPI)
        """
        self.lazy_load = lazy_load
        self.use_sar = use_sar
        self.use_terrain_indices = use_terrain_indices
        self._fetchers_loaded = False
        self._dem = None
        self._precipitation = None
        self._landcover = None
        self._sar = None
        self._terrain_indices = None

    def _load_fetchers(self) -> None:
        """Load data fetchers on first use."""
        if self._fetchers_loaded:
            return

        try:
            from ..data.dem_fetcher import DEMFetcher
            from ..data.precipitation import PrecipitationFetcher
            from ..data.landcover import LandcoverFetcher

            self._dem = DEMFetcher()
            self._precipitation = PrecipitationFetcher()
            self._landcover = LandcoverFetcher()

            # Load terrain indices calculator
            if self.use_terrain_indices:
                from .terrain_indices import TerrainIndicesCalculator
                self._terrain_indices = TerrainIndicesCalculator()
                logger.info("HotspotFeatureExtractor: terrain indices calculator loaded")

            # Load SAR fetcher
            if self.use_sar:
                from ..data.sentinel1_sar import Sentinel1SARFetcher
                self._sar = Sentinel1SARFetcher()
                logger.info("HotspotFeatureExtractor: SAR fetcher loaded")

            self._fetchers_loaded = True
            logger.info("HotspotFeatureExtractor: all data fetchers loaded")

        except ImportError as e:
            logger.error(f"Failed to load fetchers: {e}")
            raise

    def extract_features_for_hotspot(
        self,
        lat: float,
        lng: float,
        reference_date: datetime,
        buffer_km: float = 0.5,
    ) -> np.ndarray:
        """
        Extract 18-dimensional feature vector for a single hotspot.

        Args:
            lat: Latitude of hotspot
            lng: Longitude of hotspot
            reference_date: Date to compute features for
            buffer_km: Buffer radius in km for area-based features

        Returns:
            numpy array of shape (18,) with features
        """
        self._load_fetchers()

        features = np.zeros(FEATURE_DIM)

        # TERRAIN FEATURES (0-5)
        # 0. Elevation (DEM point query)
        features[0] = self._get_elevation(lat, lng, buffer_km)

        # 1. Slope (estimated from elevation gradient)
        features[1] = self._estimate_slope(lat, lng, buffer_km)

        # 2-5. Terrain indices (TPI, TRI, TWI, SPI)
        if self.use_terrain_indices and self._terrain_indices:
            terrain = self._get_terrain_indices(lat, lng, buffer_km)
            features[2] = terrain.get("tpi", 0.0)
            features[3] = terrain.get("tri", 0.0)
            features[4] = terrain.get("twi", 5.0)  # Default TWI
            features[5] = terrain.get("spi", 0.1)  # Default SPI
        else:
            features[2:6] = [0.0, 0.0, 5.0, 0.1]  # Defaults

        # PRECIPITATION FEATURES (6-10)
        precip = self._get_precipitation_features(lat, lng, reference_date, buffer_km)
        features[6] = precip.get("rainfall_24h", 0)
        features[7] = precip.get("rainfall_3d", 0)
        features[8] = precip.get("rainfall_7d", 0)
        features[9] = precip.get("max_daily_7d", 0)
        features[10] = precip.get("wet_days_7d", 0)

        # LAND COVER FEATURES (11-12)
        landcover = self._get_landcover_features(lat, lng, buffer_km)
        features[11] = landcover.get("impervious_pct", 0)
        features[12] = landcover.get("built_up_pct", 0)

        # SAR FEATURES (13-16) - Critical for monsoon flood detection
        if self.use_sar and self._sar:
            sar = self._get_sar_features(lat, lng, reference_date, buffer_km)
            features[13] = sar.get("sar_vv_mean", -10.0)
            features[14] = sar.get("sar_vh_mean", -17.0)
            features[15] = sar.get("sar_vv_vh_ratio", 7.0)
            features[16] = sar.get("sar_change_magnitude", 0.0)
        else:
            # Default dry-condition SAR values
            features[13:17] = [-10.0, -17.0, 7.0, 0.0]

        # TEMPORAL FEATURE (17)
        features[17] = self._is_monsoon(reference_date)

        return features

    def _get_elevation(self, lat: float, lng: float, buffer_km: float) -> float:
        """Get elevation using point-based query (validated)."""
        if self._dem is None:
            return 0.0

        try:
            elevation = self._dem.get_elevation_at_point(lat, lng, buffer_km)
            return float(elevation) if elevation is not None and not np.isnan(elevation) else 0.0
        except Exception as e:
            logger.warning(f"Failed to get elevation at ({lat}, {lng}): {e}")
            return 0.0

    def _estimate_slope(self, lat: float, lng: float, buffer_km: float) -> float:
        """
        Estimate slope from elevation differences.

        Since the regional terrain sampling had issues, we estimate slope
        by querying elevation at 4 cardinal directions and computing gradient.
        """
        if self._dem is None:
            return 0.0

        try:
            # Sample elevation at center and 4 directions
            delta_deg = buffer_km / 111.0  # Convert km to degrees

            center_elev = self._get_elevation(lat, lng, 0.1)
            north_elev = self._get_elevation(lat + delta_deg, lng, 0.1)
            south_elev = self._get_elevation(lat - delta_deg, lng, 0.1)
            east_elev = self._get_elevation(lat, lng + delta_deg, 0.1)
            west_elev = self._get_elevation(lat, lng - delta_deg, 0.1)

            # Calculate gradients (rise/run)
            distance_m = buffer_km * 1000  # Convert to meters

            ns_gradient = abs(north_elev - south_elev) / (2 * distance_m)
            ew_gradient = abs(east_elev - west_elev) / (2 * distance_m)

            # Combined gradient magnitude
            gradient = np.sqrt(ns_gradient**2 + ew_gradient**2)

            # Convert to slope in degrees
            slope_deg = np.degrees(np.arctan(gradient))

            return float(slope_deg) if not np.isnan(slope_deg) else 0.0

        except Exception as e:
            logger.warning(f"Failed to estimate slope at ({lat}, {lng}): {e}")
            return 0.0

    def _get_precipitation_features(
        self,
        lat: float,
        lng: float,
        reference_date: datetime,
        buffer_km: float,
    ) -> Dict[str, float]:
        """Get precipitation features using CHIRPS (validated)."""
        if self._precipitation is None:
            return {}

        try:
            # Convert point to bounds
            lat_delta = buffer_km / 111.0
            lng_delta = buffer_km / (111.0 * np.cos(np.radians(lat)))

            bounds = (
                lat - lat_delta,
                lng - lng_delta,
                lat + lat_delta,
                lng + lng_delta,
            )

            return self._precipitation.get_rainfall_features(bounds, reference_date)

        except Exception as e:
            logger.warning(f"Failed to get precipitation at ({lat}, {lng}): {e}")
            return {}

    def _get_landcover_features(
        self,
        lat: float,
        lng: float,
        buffer_km: float,
    ) -> Dict[str, float]:
        """Get land cover features using WorldCover (validated)."""
        if self._landcover is None:
            return {}

        try:
            # Convert point to bounds
            lat_delta = buffer_km / 111.0
            lng_delta = buffer_km / (111.0 * np.cos(np.radians(lat)))

            bounds = (
                lat - lat_delta,
                lng - lng_delta,
                lat + lat_delta,
                lng + lng_delta,
            )

            return self._landcover.get_landcover_features(bounds)

        except Exception as e:
            logger.warning(f"Failed to get landcover at ({lat}, {lng}): {e}")
            return {}

    def _is_monsoon(self, date: datetime) -> float:
        """Check if date is during monsoon season (June-September)."""
        return 1.0 if 6 <= date.month <= 9 else 0.0

    def _get_terrain_indices(
        self,
        lat: float,
        lng: float,
        buffer_km: float,
    ) -> Dict[str, float]:
        """
        Get terrain indices (TPI, TRI, TWI, SPI) at a location.

        These indices are research-validated predictors for flood susceptibility:
        - TPI: Negative values indicate depressions/valleys (flood-prone)
        - TRI: Low values indicate flat areas (may pool water)
        - TWI: High values indicate water accumulation zones
        - SPI: High values indicate flash flood potential
        """
        if self._terrain_indices is None:
            return {}

        try:
            return self._terrain_indices.get_terrain_indices_at_point(lat, lng, buffer_km)

        except Exception as e:
            logger.warning(f"Failed to get terrain indices at ({lat}, {lng}): {e}")
            return {}

    def _get_sar_features(
        self,
        lat: float,
        lng: float,
        reference_date: datetime,
        buffer_km: float,
    ) -> Dict[str, float]:
        """
        Get Sentinel-1 SAR features at a location.

        SAR features are critical for monsoon flood detection:
        - Penetrates clouds (essential during monsoon)
        - VV/VH backscatter drops over water surfaces
        - Change from baseline indicates new flooding

        Returns:
            - sar_vv_mean: Mean VV backscatter (dB)
            - sar_vh_mean: Mean VH backscatter (dB)
            - sar_vv_vh_ratio: VV - VH (higher = drier)
            - sar_change_magnitude: Change from baseline (negative = flooding)
        """
        if self._sar is None:
            return {}

        try:
            # Convert point to bounds
            buffer_deg = buffer_km / 111.0
            bounds = (
                lat - buffer_deg,
                lng - buffer_deg,
                lat + buffer_deg,
                lng + buffer_deg,
            )

            return self._sar.get_sar_features(bounds, reference_date)

        except Exception as e:
            logger.warning(f"Failed to get SAR features at ({lat}, {lng}): {e}")
            return {}

    def extract_batch(
        self,
        locations: List[Dict],
        reference_date: datetime,
        buffer_km: float = 0.5,
        progress_callback=None,
    ) -> np.ndarray:
        """
        Extract features for multiple hotspots.

        Args:
            locations: List of dicts with 'lat' and 'lng' keys
            reference_date: Date to compute features for
            buffer_km: Buffer radius in km
            progress_callback: Optional callback(i, total) for progress

        Returns:
            numpy array of shape (n_locations, 18)
        """
        n_locs = len(locations)
        features = np.zeros((n_locs, FEATURE_DIM))

        for i, loc in enumerate(locations):
            if progress_callback:
                progress_callback(i, n_locs)

            features[i] = self.extract_features_for_hotspot(
                lat=loc["lat"],
                lng=loc["lng"],
                reference_date=reference_date,
                buffer_km=buffer_km,
            )

        return features

    @staticmethod
    def get_feature_names() -> List[str]:
        """Get ordered list of feature names."""
        return FEATURE_NAMES.copy()

    @staticmethod
    def get_feature_dim() -> int:
        """Get feature vector dimension."""
        return FEATURE_DIM


# Default instance
hotspot_feature_extractor = HotspotFeatureExtractor()
