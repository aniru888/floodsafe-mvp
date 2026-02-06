"""
Digital Elevation Model (DEM) Data Fetcher.

Fetches elevation data from USGS SRTMGL1_003 via Google Earth Engine.
Provides terrain features including slope, aspect, and elevation statistics.
"""

import ee
import numpy as np
from typing import Dict, Optional, Tuple, Any
from datetime import datetime
import logging

from .base import BaseDataFetcher, DataFetchError
from .gee_client import gee_client
from ..core.config import settings

logger = logging.getLogger(__name__)


class DEMFetcher(BaseDataFetcher):
    """
    Fetch Digital Elevation Model data from USGS SRTMGL1_003.

    Resolution: 30m (1 arc-second)
    Coverage: Global (between 60N-60S)
    Data: Elevation in meters above sea level
    """

    @property
    def source_name(self) -> str:
        return "dem"

    @property
    def cache_ttl_days(self) -> int:
        return settings.CACHE_TTL_DEM  # 365 days - DEM rarely changes

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Fetch elevation data for the given bounds.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Not used (DEM is static)
            end_date: Not used (DEM is static)
            **kwargs: Additional parameters (scale, etc.)

        Returns:
            Dictionary containing elevation data and metadata
        """
        try:
            gee_client.initialize()

            # Get DEM image
            dem = ee.Image(settings.GEE_DEM)

            # Get terrain products (adds slope, aspect bands)
            terrain = ee.Terrain.products(dem)

            # Get geometry
            geometry = gee_client.bounds_to_geometry(bounds)

            # Extract scale from kwargs
            scale = kwargs.get("scale", 30)

            # Reduce region to get statistics
            reducer = ee.Reducer.mean().combine(
                reducer2=ee.Reducer.min(),
                sharedInputs=True
            ).combine(
                reducer2=ee.Reducer.max(),
                sharedInputs=True
            ).combine(
                reducer2=ee.Reducer.stdDev(),
                sharedInputs=True
            )

            stats = terrain.reduceRegion(
                reducer=reducer,
                geometry=geometry,
                scale=scale,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,
            ).getInfo()

            # Sample region for array data (for ML models)
            # Get a reasonable number of samples based on area
            lat_range = bounds[2] - bounds[0]
            lng_range = bounds[3] - bounds[1]
            area_deg2 = lat_range * lng_range
            num_samples = min(int(area_deg2 * 1000), 5000)  # Cap at 5000 samples

            samples = terrain.sample(
                region=geometry,
                scale=scale,
                numPixels=num_samples,
                geometries=True,
            ).getInfo()

            # Convert samples to numpy arrays
            elevation_array = np.array([
                f['properties'].get('elevation', np.nan)
                for f in samples.get('features', [])
            ])

            slope_array = np.array([
                f['properties'].get('slope', np.nan)
                for f in samples.get('features', [])
            ])

            aspect_array = np.array([
                f['properties'].get('aspect', np.nan)
                for f in samples.get('features', [])
            ])

            return {
                "stats": stats,
                "elevation": elevation_array,
                "slope": slope_array,
                "aspect": aspect_array,
                "bounds": bounds,
                "scale": scale,
                "num_samples": len(elevation_array),
            }

        except Exception as e:
            logger.error(f"Failed to fetch DEM data: {e}")
            raise DataFetchError(f"DEM fetch failed: {str(e)}") from e

    def get_terrain_features(
        self,
        bounds: Tuple[float, float, float, float],
        scale: int = 30,
    ) -> Dict[str, float]:
        """
        Get terrain features for a region.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            scale: Resolution in meters (default: 30m)

        Returns:
            Dictionary with terrain features:
            - elevation_mean: Mean elevation in meters
            - elevation_min: Minimum elevation
            - elevation_max: Maximum elevation
            - elevation_range: Elevation range
            - slope_mean: Mean slope in degrees
            - aspect_mean: Mean aspect in degrees (0-360)
        """
        data = self.fetch(bounds, scale=scale)

        stats = data.get("stats", {})
        elevation_array = data.get("elevation", np.array([]))
        slope_array = data.get("slope", np.array([]))
        aspect_array = data.get("aspect", np.array([]))

        # Calculate features
        features = {
            "elevation_mean": float(stats.get("elevation_mean", np.nanmean(elevation_array))),
            "elevation_min": float(stats.get("elevation_min", np.nanmin(elevation_array))),
            "elevation_max": float(stats.get("elevation_max", np.nanmax(elevation_array))),
            "elevation_std": float(stats.get("elevation_stdDev", np.nanstd(elevation_array))),
            "slope_mean": float(stats.get("slope_mean", np.nanmean(slope_array))),
            "aspect_mean": float(stats.get("aspect_mean", np.nanmean(aspect_array))),
        }

        # Calculate range
        if not np.isnan(features["elevation_min"]) and not np.isnan(features["elevation_max"]):
            features["elevation_range"] = features["elevation_max"] - features["elevation_min"]
        else:
            features["elevation_range"] = 0.0

        return features

    def get_elevation_at_point(
        self,
        lat: float,
        lng: float,
        buffer_radius_km: float = 0.5,
    ) -> float:
        """
        Get elevation at a specific point.

        Args:
            lat: Latitude
            lng: Longitude
            buffer_radius_km: Buffer radius in km for averaging (default: 0.5km)

        Returns:
            Elevation in meters above sea level
        """
        try:
            gee_client.initialize()

            # Get DEM
            dem = ee.Image(settings.GEE_DEM)

            # Create buffer geometry around point
            geometry = gee_client.point_buffer(lat, lng, buffer_radius_km)

            # Reduce to mean elevation
            result = dem.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=30,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
            ).getInfo()

            elevation = result.get("elevation", None)

            if elevation is None:
                logger.warning(f"No elevation data at ({lat}, {lng})")
                return np.nan

            return float(elevation)

        except Exception as e:
            logger.error(f"Failed to get elevation at point: {e}")
            raise DataFetchError(f"Point elevation fetch failed: {str(e)}") from e


# Singleton instance
dem_fetcher = DEMFetcher()
