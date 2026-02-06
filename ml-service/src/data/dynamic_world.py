"""
Google Dynamic World Land Cover Fetcher.

Dataset: GOOGLE/DYNAMICWORLD/V1 (10m resolution, near-real-time)
Provides 9 land cover class probabilities including "flooded vegetation".
"""

import ee
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .base import BaseDataFetcher, DataFetchError
from .gee_client import gee_client
from ..core.config import settings

logger = logging.getLogger(__name__)


# Dynamic World class definitions
DYNAMIC_WORLD_CLASSES = {
    0: "water",
    1: "trees",
    2: "grass",
    3: "flooded_vegetation",  # CRITICAL for flood detection
    4: "crops",
    5: "shrub_and_scrub",
    6: "built",
    7: "bare",
    8: "snow_and_ice",
}


class DynamicWorldFetcher(BaseDataFetcher):
    """
    Fetch Dynamic World land cover probabilities.

    Dynamic World provides near-real-time land cover classification with
    probability distributions across 9 classes. The "flooded_vegetation"
    class (class 3) is particularly valuable for flood prediction.

    Unlike static land cover (ESA WorldCover), Dynamic World updates daily
    and provides probability distributions rather than hard classifications.
    """

    def __init__(self):
        super().__init__()

    @property
    def source_name(self) -> str:
        return "dynamic_world"

    @property
    def cache_ttl_days(self) -> int:
        return 1  # Dynamic World updates daily

    def _ensure_initialized(self) -> None:
        """Initialize GEE."""
        gee_client.initialize()

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        scale: int = 10,
        **kwargs,
    ) -> Dict[str, float]:
        """
        Fetch Dynamic World land cover probabilities for a region.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Start date for temporal composite
            end_date: End date for temporal composite
            scale: Resolution in meters (default 10m)

        Returns:
            Dict with probability for each of 9 land cover classes
        """
        self._ensure_initialized()
        geometry = gee_client.bounds_to_geometry(bounds)

        # Default to 7-day lookback if no dates provided
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        try:
            # Get Dynamic World collection
            dw = ee.ImageCollection(settings.GEE_DYNAMIC_WORLD).filterDate(
                start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            ).filterBounds(geometry)

            # Check if collection is empty
            count = dw.size().getInfo()
            if count == 0:
                logger.warning(
                    f"No Dynamic World data found for {start_date} to {end_date}"
                )
                return self._default_probabilities()

            # Use median composite to handle clouds and gaps
            # Dynamic World bands are named directly (not class_0, class_1, etc.)
            prob_bands = list(DYNAMIC_WORLD_CLASSES.values())  # ['water', 'trees', ...]
            composite = dw.select(prob_bands).median()

            # Reduce over region to get mean probabilities
            stats = composite.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=scale,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,
            ).getInfo()

            # Convert to result format
            result = {}
            for class_name in DYNAMIC_WORLD_CLASSES.values():
                # Dynamic World probabilities are 0-1
                prob = stats.get(class_name, 0) or 0
                result[class_name] = float(prob)

            # Normalize probabilities to sum to 1 (in case of slight variations)
            total = sum(result.values())
            if total > 0:
                result = {k: v / total for k, v in result.items()}

            logger.debug(
                f"Dynamic World probabilities: flooded_veg={result.get('flooded_vegetation', 0):.3f}, "
                f"water={result.get('water', 0):.3f}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to fetch Dynamic World: {e}")
            raise DataFetchError(f"Dynamic World fetch failed: {e}") from e

    def get_flood_features(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Get flood-relevant features from Dynamic World.

        Args:
            bounds: Geographic bounds
            reference_date: Date for temporal composite (default: today)

        Returns:
            Dict with 9 probability features:
                - water_prob: Direct flood indicator
                - trees_prob: High absorption capacity
                - grass_prob: Moderate absorption
                - flooded_vegetation_prob: CRITICAL - active flooding signal
                - crops_prob: Agricultural drainage
                - shrub_and_scrub_prob: Moderate absorption
                - built_prob: Impervious, high runoff
                - bare_prob: Low absorption
                - snow_and_ice_prob: N/A for Delhi
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Use 7-day window for robust composite
        start_date = reference_date - timedelta(days=7)
        end_date = reference_date

        probs = self.fetch(bounds, start_date=start_date, end_date=end_date)

        # Return with descriptive names
        return {
            "water_prob": probs.get("water", 0),
            "trees_prob": probs.get("trees", 0),
            "grass_prob": probs.get("grass", 0),
            "flooded_vegetation_prob": probs.get("flooded_vegetation", 0),
            "crops_prob": probs.get("crops", 0),
            "shrub_and_scrub_prob": probs.get("shrub_and_scrub", 0),
            "built_prob": probs.get("built", 0),
            "bare_prob": probs.get("bare", 0),
            "snow_and_ice_prob": probs.get("snow_and_ice", 0),
        }

    def get_flooded_vegetation_prob(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: Optional[datetime] = None,
    ) -> float:
        """
        Get flooded vegetation probability - the most direct flood signal.

        Args:
            bounds: Geographic bounds
            reference_date: Date to query

        Returns:
            Probability of flooded vegetation (0-1)
        """
        features = self.get_flood_features(bounds, reference_date)
        return features["flooded_vegetation_prob"]

    def _default_probabilities(self) -> Dict[str, float]:
        """Return default probabilities when data unavailable."""
        # Return uniform distribution
        return {class_name: 1.0 / 9 for class_name in DYNAMIC_WORLD_CLASSES.values()}


# Default instance
dynamic_world_fetcher = DynamicWorldFetcher()
