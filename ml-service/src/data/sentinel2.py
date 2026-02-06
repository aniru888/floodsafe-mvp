"""
Sentinel-2 Spectral Indices Fetcher.

Dataset: COPERNICUS/S2_SR_HARMONIZED (10-60m resolution, 5-day revisit)
Computes spectral indices for flood detection: NDWI, NDVI, NDBI, MNDWI, BSI.
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


class Sentinel2Fetcher(BaseDataFetcher):
    """
    Fetch Sentinel-2 spectral indices for flood prediction.

    Sentinel-2 provides high-resolution optical imagery. We compute:
    - NDWI: Normalized Difference Water Index (water detection)
    - NDVI: Normalized Difference Vegetation Index (vegetation health)
    - NDBI: Normalized Difference Built-up Index (urbanization)
    - MNDWI: Modified NDWI (better water discrimination)
    - BSI: Bare Soil Index (exposed ground)

    These indices are computed from surface reflectance bands:
    - B2: Blue (490nm)
    - B3: Green (560nm)
    - B4: Red (665nm)
    - B8: NIR (842nm)
    - B11: SWIR1 (1610nm)
    - B12: SWIR2 (2190nm)
    """

    def __init__(self):
        super().__init__()

    @property
    def source_name(self) -> str:
        return "sentinel2"

    @property
    def cache_ttl_days(self) -> int:
        return 1  # Sentinel-2 updates every 5 days

    def _ensure_initialized(self) -> None:
        """Initialize GEE."""
        gee_client.initialize()

    def _mask_clouds(self, image: ee.Image) -> ee.Image:
        """
        Mask clouds using Scene Classification Layer (SCL).

        SCL values:
        - 3: Cloud shadows
        - 8: Cloud medium probability
        - 9: Cloud high probability
        - 10: Thin cirrus
        """
        scl = image.select("SCL")
        mask = (
            scl.neq(3)
            .And(scl.neq(8))
            .And(scl.neq(9))
            .And(scl.neq(10))
        )
        return image.updateMask(mask)

    def _compute_indices(self, image: ee.Image) -> ee.Image:
        """
        Compute spectral indices from Sentinel-2 bands.

        Args:
            image: Sentinel-2 surface reflectance image

        Returns:
            Image with computed index bands
        """
        # Extract bands
        blue = image.select("B2").float()
        green = image.select("B3").float()
        red = image.select("B4").float()
        nir = image.select("B8").float()
        swir1 = image.select("B11").float()
        swir2 = image.select("B12").float()

        # NDWI: Normalized Difference Water Index
        # (Green - NIR) / (Green + NIR)
        # Range: -1 to 1, higher values indicate water
        ndwi = green.subtract(nir).divide(green.add(nir)).rename("NDWI")

        # NDVI: Normalized Difference Vegetation Index
        # (NIR - Red) / (NIR + Red)
        # Range: -1 to 1, higher values indicate healthy vegetation
        ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")

        # NDBI: Normalized Difference Built-up Index
        # (SWIR - NIR) / (SWIR + NIR)
        # Range: -1 to 1, higher values indicate built-up areas
        ndbi = swir1.subtract(nir).divide(swir1.add(nir)).rename("NDBI")

        # MNDWI: Modified Normalized Difference Water Index
        # (Green - SWIR) / (Green + SWIR)
        # Range: -1 to 1, better at discriminating water from built-up
        mndwi = green.subtract(swir1).divide(green.add(swir1)).rename("MNDWI")

        # BSI: Bare Soil Index
        # ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
        # Range: -1 to 1, higher values indicate bare soil
        bsi = (
            swir1.add(red)
            .subtract(nir.add(blue))
            .divide(swir1.add(red).add(nir.add(blue)))
            .rename("BSI")
        )

        return image.addBands([ndwi, ndvi, ndbi, mndwi, bsi])

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        scale: int = 10,
        **kwargs,
    ) -> Dict[str, float]:
        """
        Fetch Sentinel-2 spectral indices for a region.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Start date for temporal composite
            end_date: End date for temporal composite
            scale: Resolution in meters (default 10m)

        Returns:
            Dict with mean values for each spectral index
        """
        self._ensure_initialized()
        geometry = gee_client.bounds_to_geometry(bounds)

        # Default to 30-day lookback if no dates provided
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        try:
            # Get Sentinel-2 collection
            s2 = (
                ee.ImageCollection(settings.GEE_SENTINEL2)
                .filterDate(
                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
                )
                .filterBounds(geometry)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 50))  # Filter cloudy images
            )

            # Check if collection is empty
            count = s2.size().getInfo()
            if count == 0:
                logger.warning(
                    f"No Sentinel-2 data found for {start_date} to {end_date}"
                )
                return self._default_indices()

            # Apply cloud masking and compute indices
            s2_masked = s2.map(self._mask_clouds)
            s2_indices = s2_masked.map(self._compute_indices)

            # Use median composite to handle clouds and gaps
            composite = s2_indices.select(["NDWI", "NDVI", "NDBI", "MNDWI", "BSI"]).median()

            # Reduce over region
            stats = composite.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=scale,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,
            ).getInfo()

            # Extract indices (default to 0 if None)
            result = {
                "NDWI": float(stats.get("NDWI", 0) or 0),
                "NDVI": float(stats.get("NDVI", 0) or 0),
                "NDBI": float(stats.get("NDBI", 0) or 0),
                "MNDWI": float(stats.get("MNDWI", 0) or 0),
                "BSI": float(stats.get("BSI", 0) or 0),
            }

            logger.debug(
                f"Sentinel-2 indices: NDWI={result['NDWI']:.3f}, "
                f"MNDWI={result['MNDWI']:.3f}, NDVI={result['NDVI']:.3f}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to fetch Sentinel-2: {e}")
            raise DataFetchError(f"Sentinel-2 fetch failed: {e}") from e

    def get_water_indices(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Get water detection indices.

        Args:
            bounds: Geographic bounds
            reference_date: Date for temporal composite (default: today)

        Returns:
            Dict with:
                - ndwi: Normalized Difference Water Index
                - mndwi: Modified NDWI (better for urban areas)
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Use 30-day window for robust composite
        start_date = reference_date - timedelta(days=30)
        end_date = reference_date

        indices = self.fetch(bounds, start_date=start_date, end_date=end_date)

        return {
            "ndwi": indices["NDWI"],
            "mndwi": indices["MNDWI"],
        }

    def get_flood_features(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Get all spectral indices for flood prediction.

        Args:
            bounds: Geographic bounds
            reference_date: Date for temporal composite

        Returns:
            Dict with 5 spectral indices (values in -1 to 1 range)
        """
        if reference_date is None:
            reference_date = datetime.now()

        start_date = reference_date - timedelta(days=30)
        end_date = reference_date

        return self.fetch(bounds, start_date=start_date, end_date=end_date)

    def _default_indices(self) -> Dict[str, float]:
        """Return default index values when data unavailable."""
        return {
            "NDWI": 0.0,
            "NDVI": 0.0,
            "NDBI": 0.0,
            "MNDWI": 0.0,
            "BSI": 0.0,
        }


# Default instance
sentinel2_fetcher = Sentinel2Fetcher()
