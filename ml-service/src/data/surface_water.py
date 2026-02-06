"""
Surface Water Data Fetcher.

Fetches historical surface water occurrence from JRC Global Surface Water dataset.
Provides water occurrence, recurrence, and seasonality features.
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


class SurfaceWaterFetcher(BaseDataFetcher):
    """
    Fetch surface water data from JRC Global Surface Water.

    Resolution: 30m
    Coverage: Global
    Time Period: 1984-2021

    Bands:
    - occurrence: % time water present (0-100)
    - recurrence: Inter-annual variability
    - seasonality: Intra-annual variability (months)
    - transition: Water transition classification
    - max_extent: Maximum water extent
    """

    @property
    def source_name(self) -> str:
        return "surface_water"

    @property
    def cache_ttl_days(self) -> int:
        return settings.CACHE_TTL_SURFACE_WATER  # 30 days

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Fetch surface water data for the given bounds.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Not used (dataset is pre-computed)
            end_date: Not used (dataset is pre-computed)
            **kwargs: Additional parameters (scale, etc.)

        Returns:
            Dictionary containing surface water data and metadata
        """
        try:
            gee_client.initialize()

            # Get surface water image
            water = ee.Image(settings.GEE_SURFACE_WATER)

            # Get geometry
            geometry = gee_client.bounds_to_geometry(bounds)

            # Extract scale from kwargs
            scale = kwargs.get("scale", 30)

            # Reduce region to get statistics for key bands
            bands = ["occurrence", "recurrence", "seasonality", "max_extent"]

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

            stats = water.select(bands).reduceRegion(
                reducer=reducer,
                geometry=geometry,
                scale=scale,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
            ).getInfo()

            # Sample region for array data
            lat_range = bounds[2] - bounds[0]
            lng_range = bounds[3] - bounds[1]
            area_deg2 = lat_range * lng_range
            num_samples = min(int(area_deg2 * 1000), 5000)  # Cap at 5000

            samples = water.select(bands).sample(
                region=geometry,
                scale=scale,
                numPixels=num_samples,
                geometries=True,
            ).getInfo()

            # Convert samples to numpy arrays
            occurrence_array = np.array([
                f['properties'].get('occurrence', np.nan)
                for f in samples.get('features', [])
            ])

            recurrence_array = np.array([
                f['properties'].get('recurrence', np.nan)
                for f in samples.get('features', [])
            ])

            seasonality_array = np.array([
                f['properties'].get('seasonality', np.nan)
                for f in samples.get('features', [])
            ])

            max_extent_array = np.array([
                f['properties'].get('max_extent', np.nan)
                for f in samples.get('features', [])
            ])

            return {
                "stats": stats,
                "occurrence": occurrence_array,
                "recurrence": recurrence_array,
                "seasonality": seasonality_array,
                "max_extent": max_extent_array,
                "bounds": bounds,
                "scale": scale,
                "num_samples": len(occurrence_array),
            }

        except Exception as e:
            logger.error(f"Failed to fetch surface water data: {e}")
            raise DataFetchError(f"Surface water fetch failed: {str(e)}") from e

    def get_water_features(
        self,
        bounds: Tuple[float, float, float, float],
        scale: int = 30,
    ) -> Dict[str, float]:
        """
        Get surface water features for a region.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            scale: Resolution in meters (default: 30m)

        Returns:
            Dictionary with water features:
            - water_occurrence: Mean % of time water was present (0-100)
            - water_recurrence: Mean inter-annual variability (0-100)
            - water_seasonality: Mean intra-annual variability (months, 0-12)
            - water_max_extent: % of area with maximum water extent
            - permanent_water_pct: % of pixels with occurrence > 90
            - seasonal_water_pct: % of pixels with 10 < occurrence < 90
        """
        data = self.fetch(bounds, scale=scale)

        stats = data.get("stats", {})
        occurrence_array = data.get("occurrence", np.array([]))
        recurrence_array = data.get("recurrence", np.array([]))
        seasonality_array = data.get("seasonality", np.array([]))
        max_extent_array = data.get("max_extent", np.array([]))

        # Calculate basic features
        features = {
            "water_occurrence": float(stats.get("occurrence_mean", np.nanmean(occurrence_array))),
            "water_occurrence_max": float(stats.get("occurrence_max", np.nanmax(occurrence_array))),
            "water_recurrence": float(stats.get("recurrence_mean", np.nanmean(recurrence_array))),
            "water_seasonality": float(stats.get("seasonality_mean", np.nanmean(seasonality_array))),
        }

        # Calculate water classification percentages
        valid_occurrence = occurrence_array[~np.isnan(occurrence_array)]
        total_pixels = len(valid_occurrence) if len(valid_occurrence) > 0 else 1

        # Permanent water: occurrence > 90%
        permanent_pixels = np.sum(valid_occurrence > 90)
        features["permanent_water_pct"] = float(100 * permanent_pixels / total_pixels)

        # Seasonal water: 10% < occurrence < 90%
        seasonal_pixels = np.sum((valid_occurrence > 10) & (valid_occurrence < 90))
        features["seasonal_water_pct"] = float(100 * seasonal_pixels / total_pixels)

        # Occasional water: 0% < occurrence < 10%
        occasional_pixels = np.sum((valid_occurrence > 0) & (valid_occurrence <= 10))
        features["occasional_water_pct"] = float(100 * occasional_pixels / total_pixels)

        # No water: occurrence = 0%
        no_water_pixels = np.sum(valid_occurrence == 0)
        features["no_water_pct"] = float(100 * no_water_pixels / total_pixels)

        # Maximum extent percentage
        valid_max_extent = max_extent_array[~np.isnan(max_extent_array)]
        if len(valid_max_extent) > 0:
            features["water_max_extent_pct"] = float(100 * np.mean(valid_max_extent > 0))
        else:
            features["water_max_extent_pct"] = 0.0

        return features

    def get_water_at_point(
        self,
        lat: float,
        lng: float,
        buffer_radius_km: float = 0.5,
    ) -> Dict[str, float]:
        """
        Get surface water information at a specific point.

        Args:
            lat: Latitude
            lng: Longitude
            buffer_radius_km: Buffer radius in km for averaging (default: 0.5km)

        Returns:
            Dictionary with water properties:
            - occurrence: % time water present
            - recurrence: Inter-annual variability
            - seasonality: Intra-annual variability (months)
            - max_extent: Maximum water extent (0 or 1)
        """
        try:
            gee_client.initialize()

            # Get surface water image
            water = ee.Image(settings.GEE_SURFACE_WATER)

            # Create buffer geometry around point
            geometry = gee_client.point_buffer(lat, lng, buffer_radius_km)

            # Select bands
            bands = ["occurrence", "recurrence", "seasonality", "max_extent"]

            # Reduce to mean
            result = water.select(bands).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=30,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
            ).getInfo()

            # Build response
            water_info = {
                "occurrence": float(result.get("occurrence", 0)),
                "recurrence": float(result.get("recurrence", 0)),
                "seasonality": float(result.get("seasonality", 0)),
                "max_extent": float(result.get("max_extent", 0)),
            }

            # Classify water type
            occurrence = water_info["occurrence"]
            if occurrence > 90:
                water_info["water_type"] = "permanent"
            elif occurrence > 10:
                water_info["water_type"] = "seasonal"
            elif occurrence > 0:
                water_info["water_type"] = "occasional"
            else:
                water_info["water_type"] = "no_water"

            return water_info

        except Exception as e:
            logger.error(f"Failed to get water at point: {e}")
            raise DataFetchError(f"Point water fetch failed: {str(e)}") from e


# Singleton instance
surface_water_fetcher = SurfaceWaterFetcher()
