"""
Sentinel-1 SAR Data Fetcher for Flood Detection.

Fetches Synthetic Aperture Radar (SAR) data from Sentinel-1 GRD for
cloud-penetrating flood detection during monsoon season.

Dataset: COPERNICUS/S1_GRD
Resolution: 10m
Coverage: Global, 2014-present
Revisit: 6 days

Key advantages for India monsoon flood detection:
- Penetrates clouds (critical during monsoon)
- Day/night operation
- Free via Google Earth Engine
- 6-day revisit enables near-real-time monitoring

References:
- Malda study (2024): Sentinel-1 SAR-driven flood inventory
- Assam study (2024): Automated flood monitoring with SAR
- SAS_ML GitHub: Multi-temporal SAR flood detection
"""

import ee
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional, List
import logging

from ..core.config import settings
from .base import BaseDataFetcher, DataFetchError
from .gee_client import gee_client

logger = logging.getLogger(__name__)


class Sentinel1SARFetcher(BaseDataFetcher):
    """
    Fetches Sentinel-1 SAR data for flood detection via Google Earth Engine.

    Provides VV/VH backscatter measurements and change detection features
    for flood extent mapping and ML feature extraction.

    SAR Flood Detection Principle:
    - Water surfaces act as specular reflectors (smooth mirrors)
    - Backscatter decreases significantly over flooded areas
    - VV < -15 dB AND VH < -22 dB typically indicates water
    - Change detection: flood - baseline > 3 dB decrease = flooding
    """

    # SAR thresholds from research (SAS_ML, Malda study)
    VV_WATER_THRESHOLD = -15.0  # dB
    VH_WATER_THRESHOLD = -22.0  # dB
    CHANGE_THRESHOLD = -3.0     # dB decrease from baseline indicates flood

    # Speckle filter parameters
    SPECKLE_FILTER_KERNEL_SIZE = 7  # 7x7 window for Refined Lee

    @property
    def source_name(self) -> str:
        return "sentinel1_sar"

    @property
    def cache_ttl_days(self) -> int:
        return 7  # SAR data is relatively stable, cache for a week

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> Dict:
        """
        Fetch Sentinel-1 SAR data for flood detection.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Start date for flood event imagery
            end_date: End date for flood event imagery
            baseline_months: List of months (1-12) for dry season baseline (default: [1,2,3,4,5])

        Returns:
            Dict with SAR statistics and flood mask

        Raises:
            DataFetchError: If GEE query fails
        """
        if not start_date or not end_date:
            raise DataFetchError("start_date and end_date required for SAR data")

        baseline_months = kwargs.get("baseline_months", [1, 2, 3, 4, 5])  # Jan-May

        # Validate inputs to prevent injection
        baseline_year = start_date.year - 1 if start_date.month >= 6 else start_date.year
        if not (1900 <= baseline_year <= 2100):
            raise DataFetchError(f"Invalid baseline_year: {baseline_year}")
        if not all(1 <= m <= 12 for m in baseline_months):
            raise DataFetchError(f"Invalid baseline_months: {baseline_months}")

        try:
            gee_client.initialize()
            geometry = gee_client.bounds_to_geometry(bounds)

            # Get Sentinel-1 collection with IW mode and both polarizations
            s1_collection = self._get_s1_collection(geometry)

            # Check if any data exists
            total_count = s1_collection.size().getInfo()
            if total_count == 0:
                logger.warning(f"No Sentinel-1 data found for bounds {bounds}")
                return self._empty_result()

            # Create dry-season baseline (median of previous year's dry season)
            # baseline_year already validated above
            baseline = self._create_baseline(s1_collection, geometry, baseline_year, baseline_months)

            # Get flood event imagery
            flood_image = self._get_flood_image(s1_collection, geometry, start_date, end_date)

            # Compute change detection
            change_result = self._compute_change_detection(baseline, flood_image, geometry)

            # Extract statistics
            stats = self._extract_statistics(flood_image, geometry)

            # Create flood mask (skip if change detection failed)
            if change_result.get("change") is not None:
                flood_mask = self._create_flood_mask(flood_image, change_result["change"], geometry)
            else:
                flood_mask = {"flood_fraction": 0.0}

            return {
                "vv_mean": stats.get("VV_mean", None),
                "vv_min": stats.get("VV_min", None),
                "vv_stddev": stats.get("VV_stdDev", None),
                "vh_mean": stats.get("VH_mean", None),
                "vh_min": stats.get("VH_min", None),
                "vh_stddev": stats.get("VH_stdDev", None),
                "vv_vh_ratio": (stats.get("VV_mean") - stats.get("VH_mean")) if (stats.get("VV_mean") is not None and stats.get("VH_mean") is not None) else None,
                "change_vv_mean": change_result.get("change_vv_mean", None),
                "change_vh_mean": change_result.get("change_vh_mean", None),
                "flood_fraction": flood_mask.get("flood_fraction", 0.0),
                "baseline_vv_mean": change_result.get("baseline_vv_mean", None),
                "baseline_vh_mean": change_result.get("baseline_vh_mean", None),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "baseline_year": baseline_year,
                "image_count": change_result.get("flood_image_count", 0),
            }

        except Exception as e:
            logger.error(f"SAR fetch failed: {e}")
            raise DataFetchError(f"Sentinel-1 SAR fetch failed: {str(e)}") from e

    def _get_s1_collection(self, geometry: ee.Geometry, apply_speckle_filter: bool = True) -> ee.ImageCollection:
        """
        Get filtered Sentinel-1 GRD collection.

        Filters for:
        - IW (Interferometric Wide) mode
        - VV and VH polarization
        - Descending orbit (consistent geometry)
        - Optional speckle filtering (Refined Lee)
        """
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
            .filterBounds(geometry)
            .select(["VV", "VH"])
        )

        if apply_speckle_filter:
            collection = collection.map(self._apply_refined_lee_filter)

        return collection

    def _apply_refined_lee_filter(self, image: ee.Image) -> ee.Image:
        """
        Apply Refined Lee speckle filter to SAR image.

        The Refined Lee filter is an adaptive filter that:
        1. Preserves edges and linear features
        2. Reduces speckle noise in homogeneous areas
        3. Uses local statistics to adapt filtering strength

        Based on Lee, J.S., 1981: "Refined filtering of image noise using
        local statistics" and improvements from SNAP toolbox.

        Algorithm:
        - Compute local mean and variance in 7x7 window
        - Estimate noise variance from coefficient of variation
        - Apply adaptive weighting: filtered = mean + weight * (original - mean)
        - weight = variance_signal / (variance_signal + variance_noise)
        """
        # Convert from dB to linear power for filtering
        vv_linear = ee.Image(10).pow(image.select("VV").divide(10))
        vh_linear = ee.Image(10).pow(image.select("VH").divide(10))

        # Define kernel for local statistics
        kernel = ee.Kernel.square(
            radius=self.SPECKLE_FILTER_KERNEL_SIZE // 2,
            units="pixels"
        )

        # Apply Refined Lee to each band
        vv_filtered = self._refined_lee_band(vv_linear, kernel)
        vh_filtered = self._refined_lee_band(vh_linear, kernel)

        # Convert back to dB
        vv_db = ee.Image(10).multiply(vv_filtered.log10()).rename("VV")
        vh_db = ee.Image(10).multiply(vh_filtered.log10()).rename("VH")

        return vv_db.addBands(vh_db).copyProperties(image, image.propertyNames())

    def _refined_lee_band(self, band: ee.Image, kernel: ee.Kernel) -> ee.Image:
        """
        Apply Refined Lee filter to a single band.

        Uses the MMSE (Minimum Mean Square Error) estimator:
        filtered = local_mean + k * (original - local_mean)
        where k = (local_variance - noise_variance) / local_variance
        """
        # Compute local statistics
        local_mean = band.reduceNeighborhood(
            reducer=ee.Reducer.mean(),
            kernel=kernel
        )
        local_variance = band.reduceNeighborhood(
            reducer=ee.Reducer.variance(),
            kernel=kernel
        )

        # Estimate noise variance using coefficient of variation
        # For single-look SAR, theoretical CV ≈ 0.523 (fully developed speckle)
        # For multi-look GRD (typically 4-5 looks), CV ≈ 0.23-0.26
        equivalent_number_of_looks = 4.4  # Typical for Sentinel-1 GRD IW
        noise_variance = local_mean.pow(2).divide(equivalent_number_of_looks)

        # Calculate MMSE weight (bounded to [0, 1])
        signal_variance = local_variance.subtract(noise_variance).max(0)
        weight = signal_variance.divide(local_variance.add(1e-10))

        # Apply filter: filtered = mean + weight * (original - mean)
        filtered = local_mean.add(weight.multiply(band.subtract(local_mean)))

        return filtered

    def _create_baseline(
        self,
        collection: ee.ImageCollection,
        geometry: ee.Geometry,
        baseline_year: int,
        baseline_months: List[int],
    ) -> ee.Image:
        """
        Create dry-season baseline composite (median).

        Uses months from baseline_months (default: Jan-May) when
        flooding is typically minimal in India.
        """
        # Filter to baseline period
        baseline_collection = collection.filter(
            ee.Filter.calendarRange(baseline_year, baseline_year, "year")
        ).filter(
            ee.Filter.calendarRange(min(baseline_months), max(baseline_months), "month")
        )

        count = baseline_collection.size().getInfo()
        logger.info(f"Baseline images found: {count} for {baseline_year} months {baseline_months}")

        if count == 0:
            # Fall back to any available dry season data
            baseline_collection = collection.filter(
                ee.Filter.calendarRange(min(baseline_months), max(baseline_months), "month")
            ).limit(50)  # Use recent images

        # Create median composite (robust to outliers)
        return baseline_collection.median()

    def _get_flood_image(
        self,
        collection: ee.ImageCollection,
        geometry: ee.Geometry,
        start_date: datetime,
        end_date: datetime,
    ) -> ee.Image:
        """
        Get flood event imagery (median of date range).
        """
        flood_collection = collection.filterDate(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        count = flood_collection.size().getInfo()
        logger.info(f"Flood event images found: {count} for {start_date.date()} to {end_date.date()}")

        return flood_collection.median()

    def _compute_change_detection(
        self,
        baseline: ee.Image,
        flood: ee.Image,
        geometry: ee.Geometry,
    ) -> Dict:
        """
        Compute change detection between baseline and flood imagery.

        Negative change (flood - baseline < 0) indicates flooding.
        """
        # Check if images have bands before computing change
        baseline_bands = baseline.bandNames().size().getInfo()
        flood_bands = flood.bandNames().size().getInfo()

        if baseline_bands == 0 or flood_bands == 0:
            logger.warning(f"Empty image detected - baseline bands: {baseline_bands}, flood bands: {flood_bands}")
            return {
                "change": None,
                "change_vv_mean": None,
                "change_vh_mean": None,
                "baseline_vv_mean": None,
                "baseline_vh_mean": None,
                "flood_image_count": 0,
            }

        change = flood.subtract(baseline)

        # Get statistics for change image
        change_stats = change.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=100,  # 100m for efficiency
            maxPixels=1e8,
        ).getInfo()

        # Get baseline statistics
        baseline_stats = baseline.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=100,
            maxPixels=1e8,
        ).getInfo()

        return {
            "change": change,
            "change_vv_mean": change_stats.get("VV"),
            "change_vh_mean": change_stats.get("VH"),
            "baseline_vv_mean": baseline_stats.get("VV"),
            "baseline_vh_mean": baseline_stats.get("VH"),
            "flood_image_count": 1,  # Already composited
        }

    def _extract_statistics(self, image: ee.Image, geometry: ee.Geometry) -> Dict:
        """
        Extract VV/VH backscatter statistics for flood image.
        """
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.min(), sharedInputs=True
            ).combine(
                ee.Reducer.stdDev(), sharedInputs=True
            ),
            geometry=geometry,
            scale=100,  # 100m resolution for efficiency
            maxPixels=1e8,
        ).getInfo()

        return stats

    def _create_flood_mask(
        self,
        flood_image: ee.Image,
        change_image: ee.Image,
        geometry: ee.Geometry,
    ) -> Dict:
        """
        Create binary flood mask using thresholds.

        Flood detection criteria (from research):
        1. VV < -15 dB (water appears dark in VV)
        2. VH < -22 dB (water appears dark in VH)
        3. Change from baseline > 3 dB decrease

        Uses combination for robust detection.
        """
        # Threshold-based water detection
        vv_water = flood_image.select("VV").lt(self.VV_WATER_THRESHOLD)
        vh_water = flood_image.select("VH").lt(self.VH_WATER_THRESHOLD)

        # Change-based flood detection
        vv_change = change_image.select("VV").lt(self.CHANGE_THRESHOLD)

        # Combined flood mask (water AND significant change)
        flood_mask = vv_water.And(vh_water).And(vv_change)

        # Calculate flood fraction
        flood_area = flood_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=100,
            maxPixels=1e8,
        ).getInfo()

        return {
            "flood_fraction": flood_area.get("VV", 0.0) or 0.0,
        }

    def _empty_result(self) -> Dict:
        """Return empty result when no data available."""
        return {
            "vv_mean": None,
            "vv_min": None,
            "vv_stddev": None,
            "vh_mean": None,
            "vh_min": None,
            "vh_stddev": None,
            "vv_vh_ratio": None,
            "change_vv_mean": None,
            "change_vh_mean": None,
            "flood_fraction": 0.0,
            "baseline_vv_mean": None,
            "baseline_vh_mean": None,
            "start_date": None,
            "end_date": None,
            "baseline_year": None,
            "image_count": 0,
        }

    def get_sar_features(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
        lookback_days: int = 7,
    ) -> Dict[str, float]:
        """
        Get SAR features for ML model input.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            reference_date: Date for feature extraction
            lookback_days: Days to look back for imagery

        Returns:
            Dict with SAR feature values for ML model:
            - sar_vv_mean: Mean VV backscatter (dB)
            - sar_vh_mean: Mean VH backscatter (dB)
            - sar_vv_vh_ratio: VV/VH ratio (water indicator)
            - sar_change_magnitude: Change from baseline (negative = flooding)
        """
        try:
            start_date = reference_date - timedelta(days=lookback_days)
            end_date = reference_date

            data = self.fetch(bounds, start_date, end_date)

            return {
                "sar_vv_mean": data.get("vv_mean") or -10.0,  # Default dry value
                "sar_vh_mean": data.get("vh_mean") or -17.0,  # Default dry value
                "sar_vv_vh_ratio": data.get("vv_vh_ratio") or 7.0,  # Typical dry ratio
                "sar_change_magnitude": data.get("change_vv_mean") or 0.0,  # No change
            }

        except Exception as e:
            logger.warning(f"SAR feature extraction failed: {e}, using defaults")
            return {
                "sar_vv_mean": -10.0,
                "sar_vh_mean": -17.0,
                "sar_vv_vh_ratio": 7.0,
                "sar_change_magnitude": 0.0,
            }

    def get_flood_extent(
        self,
        bounds: Tuple[float, float, float, float],
        flood_date: datetime,
        lookback_days: int = 7,
    ) -> Dict:
        """
        Get flood extent analysis for a specific event.

        Returns detailed flood extent information including
        flood fraction, backscatter statistics, and change detection.
        """
        start_date = flood_date - timedelta(days=lookback_days)
        return self.fetch(bounds, start_date, flood_date)


# Convenience functions for hotspot feature extraction
def get_sar_features_at_point(
    lat: float,
    lng: float,
    reference_date: datetime,
    buffer_m: float = 500.0,
) -> Dict[str, float]:
    """
    Get SAR features for a single point location.

    Args:
        lat: Latitude
        lng: Longitude
        reference_date: Date for feature extraction
        buffer_m: Buffer around point in meters (default 500m)

    Returns:
        Dict with SAR features for ML input
    """
    # Convert buffer to approximate degrees
    buffer_deg = buffer_m / 111000  # ~111km per degree

    bounds = (
        lat - buffer_deg,
        lng - buffer_deg,
        lat + buffer_deg,
        lng + buffer_deg,
    )

    fetcher = Sentinel1SARFetcher()
    return fetcher.get_sar_features(bounds, reference_date)
