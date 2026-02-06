"""
GloFAS (Global Flood Awareness System) Data Fetcher.

Fetches river discharge data from ECMWF's GloFAS via Google Earth Engine.
This provides hydrological context for flood predictions.
"""

import ee
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging
import numpy as np

from ..core.config import settings
from .gee_client import gee_client

logger = logging.getLogger(__name__)


class GloFASFetcher:
    """
    Fetch GloFAS river discharge data from Google Earth Engine.

    GloFAS provides global river discharge forecasts and historical data.
    Dataset: ECMWF/ERA5_LAND/DAILY_AGGR (ERA5-Land daily aggregates)

    Note: The actual GloFAS reanalysis (ECMWF/CEMS_GLOFAS_*) may have limited
    availability, so we use ERA5-Land runoff as a proxy for discharge.
    """

    # ERA5-Land runoff bands
    RUNOFF_BAND = "runoff_sum"  # Total runoff (surface + subsurface)
    SURFACE_RUNOFF_BAND = "surface_runoff_sum"

    def __init__(self):
        """Initialize GloFAS fetcher."""
        self._initialized = False
        self._init_gee()

    def _init_gee(self) -> None:
        """Initialize Google Earth Engine."""
        if self._initialized:
            return

        try:
            gee_client.initialize()
            self._initialized = True
            logger.info("GloFAS fetcher: GEE initialized")
        except Exception as e:
            logger.warning(f"GEE initialization failed: {e}")
            self._initialized = False

    def _bounds_to_geometry(
        self, bounds: Tuple[float, float, float, float]
    ) -> ee.Geometry:
        """Convert bounds tuple to GEE geometry."""
        lat_min, lng_min, lat_max, lng_max = bounds
        return ee.Geometry.Rectangle([lng_min, lat_min, lng_max, lat_max])

    def get_discharge_features(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
        lookback_days: int = 7,
    ) -> Dict[str, float]:
        """
        Get river discharge/runoff features for a region.

        Uses ERA5-Land runoff data as proxy for river discharge.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            reference_date: Date to get discharge for
            lookback_days: Days of data to aggregate

        Returns:
            Dict with discharge features:
                - discharge_mean: Average runoff (mm)
                - discharge_max: Peak runoff (mm)
        """
        if not self._initialized:
            self._init_gee()
            if not self._initialized:
                return self._default_discharge()

        try:
            geometry = self._bounds_to_geometry(bounds)
            end_date = reference_date
            start_date = reference_date - timedelta(days=lookback_days)

            # Use ERA5-Land daily aggregates
            era5 = (
                ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
                .filterBounds(geometry)
            )

            # Check if collection is empty
            count = era5.size().getInfo()
            if count == 0:
                logger.warning(f"No ERA5-Land data found for {start_date} to {end_date}")
                return self._default_discharge()

            # Get mean runoff over the period
            mean_runoff = era5.select(self.RUNOFF_BAND).mean()
            max_runoff = era5.select(self.RUNOFF_BAND).max()

            # Reduce over region
            mean_stats = mean_runoff.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=10000,  # ERA5-Land is ~9km resolution
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,
            ).getInfo()

            max_stats = max_runoff.reduceRegion(
                reducer=ee.Reducer.max(),
                geometry=geometry,
                scale=10000,
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,
            ).getInfo()

            # Convert from m to mm and handle None values
            discharge_mean = mean_stats.get(self.RUNOFF_BAND, 0) or 0
            discharge_max = max_stats.get(self.RUNOFF_BAND, 0) or 0

            # ERA5-Land runoff is in meters, convert to mm
            discharge_mean = float(discharge_mean) * 1000
            discharge_max = float(discharge_max) * 1000

            logger.debug(
                f"GloFAS discharge: mean={discharge_mean:.2f}mm, max={discharge_max:.2f}mm"
            )

            return {
                "discharge_mean": discharge_mean,
                "discharge_max": discharge_max,
            }

        except Exception as e:
            logger.warning(f"GloFAS fetch failed: {e}")
            return self._default_discharge()

    def get_surface_runoff(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
    ) -> float:
        """
        Get surface runoff for the reference date.

        Surface runoff is the immediate response to precipitation
        and is a key indicator of flash flood potential.

        Args:
            bounds: Geographic bounds
            reference_date: Date to query

        Returns:
            Surface runoff in mm
        """
        if not self._initialized:
            self._init_gee()
            if not self._initialized:
                return 0.0

        try:
            geometry = self._bounds_to_geometry(bounds)
            date_str = reference_date.strftime("%Y-%m-%d")
            next_day = (reference_date + timedelta(days=1)).strftime("%Y-%m-%d")

            era5 = (
                ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                .filterDate(date_str, next_day)
                .filterBounds(geometry)
                .first()
            )

            if era5 is None:
                return 0.0

            stats = (
                era5.select(self.SURFACE_RUNOFF_BAND)
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=10000,
                    maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                    bestEffort=True,
                )
                .getInfo()
            )

            runoff = stats.get(self.SURFACE_RUNOFF_BAND, 0) or 0
            return float(runoff) * 1000  # Convert m to mm

        except Exception as e:
            logger.warning(f"Surface runoff fetch failed: {e}")
            return 0.0

    def _default_discharge(self) -> Dict[str, float]:
        """Return default discharge values when data unavailable."""
        return {
            "discharge_mean": 0.0,
            "discharge_max": 0.0,
        }


# Default instance
glofas_fetcher = GloFASFetcher()
