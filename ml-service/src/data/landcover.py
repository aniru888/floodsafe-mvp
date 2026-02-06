"""
ESA WorldCover Land Cover Fetcher.

Dataset: ESA/WorldCover/v200 (10m resolution)
"""

import ee
import numpy as np
from typing import Dict, Optional, Tuple
import logging

from .base import BaseDataFetcher, DataFetchError
from .gee_client import gee_client
from ..core.config import settings

logger = logging.getLogger(__name__)


# ESA WorldCover class definitions
LANDCOVER_CLASSES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse",
    70: "snow_ice",
    80: "water",
    90: "wetland",
    95: "mangroves",
    100: "moss_lichen",
}


class LandcoverFetcher(BaseDataFetcher):
    """
    Fetch ESA WorldCover land cover classification.

    Land cover is important for flood prediction:
    - Built-up areas have poor drainage
    - Vegetation improves infiltration
    - Water bodies indicate flood-prone areas
    """

    def __init__(self):
        super().__init__()
        self._landcover = None

    @property
    def source_name(self) -> str:
        return "landcover"

    @property
    def cache_ttl_days(self) -> int:
        return settings.CACHE_TTL_LANDCOVER

    def _ensure_initialized(self) -> None:
        """Initialize GEE and load landcover image."""
        gee_client.initialize()
        if self._landcover is None:
            # ESA WorldCover is an ImageCollection - get 2021 version
            self._landcover = ee.ImageCollection(settings.GEE_LANDCOVER).first().select("Map")

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date=None,
        end_date=None,
        scale: int = 10,
        **kwargs,
    ) -> Dict[str, float]:
        """
        Fetch land cover distribution for a region.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Ignored (static dataset)
            end_date: Ignored (static dataset)
            scale: Resolution in meters (default 10m)

        Returns:
            Dict with percentage of each land cover class
        """
        self._ensure_initialized()
        geometry = gee_client.bounds_to_geometry(bounds)

        try:
            # Get frequency histogram of land cover classes
            histogram = self._landcover.reduceRegion(
                reducer=ee.Reducer.frequencyHistogram(),
                geometry=geometry,
                scale=scale,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,  # Allow GEE to use coarser scale if needed
            ).getInfo()

            hist = histogram.get("Map", {})
            total = sum(hist.values()) if hist else 1

            # Convert to percentages with readable names
            result = {}
            for class_id, class_name in LANDCOVER_CLASSES.items():
                count = hist.get(str(class_id), 0)
                result[class_name] = (count / total) * 100 if total > 0 else 0

            return result

        except Exception as e:
            logger.error(f"Failed to fetch landcover: {e}")
            raise DataFetchError(f"Landcover fetch failed: {e}") from e

    def get_landcover_features(
        self,
        bounds: Tuple[float, float, float, float],
        scale: int = 10,
    ) -> Dict[str, float]:
        """
        Get land cover features useful for flood prediction.

        Args:
            bounds: Geographic bounds
            scale: Resolution in meters

        Returns:
            Dict with:
                - built_up_pct: Percentage of built-up area
                - vegetation_pct: Combined tree + shrub + grass
                - water_pct: Permanent water bodies
                - cropland_pct: Agricultural land
                - impervious_pct: Built-up + bare (poor drainage)
                - permeable_pct: Vegetation + cropland (good drainage)
        """
        raw = self.fetch(bounds, scale=scale)

        built = raw.get("built_up", 0)
        tree = raw.get("tree_cover", 0)
        shrub = raw.get("shrubland", 0)
        grass = raw.get("grassland", 0)
        crop = raw.get("cropland", 0)
        bare = raw.get("bare_sparse", 0)
        water = raw.get("water", 0)
        wetland = raw.get("wetland", 0)

        return {
            "built_up_pct": built,
            "vegetation_pct": tree + shrub + grass,
            "water_pct": water + wetland,
            "cropland_pct": crop,
            "impervious_pct": built + bare,  # Poor drainage
            "permeable_pct": tree + shrub + grass + crop,  # Good drainage
        }

    def get_landcover_at_point(
        self,
        lat: float,
        lng: float,
        buffer_m: int = 500,
    ) -> Dict[str, float]:
        """
        Get land cover distribution around a point.

        Args:
            lat: Latitude
            lng: Longitude
            buffer_m: Buffer radius in meters

        Returns:
            Dict with land cover percentages
        """
        self._ensure_initialized()

        try:
            buffer = gee_client.point_buffer(lat, lng, buffer_m / 1000)

            histogram = self._landcover.reduceRegion(
                reducer=ee.Reducer.frequencyHistogram(),
                geometry=buffer,
                scale=10,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,
            ).getInfo()

            hist = histogram.get("Map", {})
            total = sum(hist.values()) if hist else 1

            result = {}
            for class_id, class_name in LANDCOVER_CLASSES.items():
                count = hist.get(str(class_id), 0)
                result[class_name] = (count / total) * 100 if total > 0 else 0

            return result

        except Exception as e:
            logger.error(f"Failed to get landcover at point: {e}")
            raise DataFetchError(f"Landcover point query failed: {e}") from e

    def get_dominant_class(
        self,
        bounds: Tuple[float, float, float, float],
    ) -> str:
        """Get the dominant land cover class in a region."""
        distribution = self.fetch(bounds)
        return max(distribution.items(), key=lambda x: x[1])[0]
