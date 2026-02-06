"""
Google Earth Engine Client.

Handles authentication and provides common GEE utilities.
"""

import ee
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import logging

from ..core.config import settings
from .base import DataFetchError

logger = logging.getLogger(__name__)


class GEEClient:
    """
    Google Earth Engine Client Singleton.

    Handles authentication and provides common utilities for GEE queries.
    """

    _instance: Optional["GEEClient"] = None
    _initialized: bool = False
    _gee_available: bool = False  # True only if GEE is actually usable

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        pass

    @property
    def is_available(self) -> bool:
        """Check if GEE is actually available and usable."""
        return self._gee_available

    def initialize(self) -> None:
        """Initialize GEE with authentication."""
        if self._initialized:
            return

        # Check if GEE is disabled (e.g., for HuggingFace Spaces deployment)
        if not settings.GEE_ENABLED:
            logger.info("GEE disabled via GEE_ENABLED=false - skipping initialization")
            self.__class__._initialized = True  # Mark as initialized but inactive
            self.__class__._gee_available = False
            return

        try:
            # Try service account first
            if settings.GEE_SERVICE_ACCOUNT_KEY:
                credentials = ee.ServiceAccountCredentials(
                    email=None,  # Will be read from key file
                    key_file=settings.GEE_SERVICE_ACCOUNT_KEY,
                )
                ee.Initialize(credentials=credentials, project=settings.GCP_PROJECT_ID)
                logger.info(f"GEE initialized with service account")
            else:
                # Fall back to OAuth flow (one-time browser auth)
                try:
                    ee.Initialize(project=settings.GCP_PROJECT_ID)
                except Exception:
                    logger.info("Running ee.Authenticate()...")
                    ee.Authenticate()
                    ee.Initialize(project=settings.GCP_PROJECT_ID)

            self.__class__._initialized = True
            self.__class__._gee_available = True
            logger.info(f"GEE initialized with project: {settings.GCP_PROJECT_ID}")

        except Exception as e:
            logger.error(f"GEE initialization failed: {e}")
            raise DataFetchError(f"GEE initialization failed: {str(e)}") from e

    @staticmethod
    def bounds_to_geometry(
        bounds: Tuple[float, float, float, float]
    ) -> ee.Geometry.Rectangle:
        """
        Convert bounds tuple to ee.Geometry.Rectangle.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)

        Returns:
            ee.Geometry.Rectangle in EPSG:4326
        """
        lat_min, lng_min, lat_max, lng_max = bounds
        return ee.Geometry.Rectangle([lng_min, lat_min, lng_max, lat_max])

    @staticmethod
    def point_to_geometry(lat: float, lng: float) -> ee.Geometry.Point:
        """
        Convert lat/lng to ee.Geometry.Point.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            ee.Geometry.Point
        """
        return ee.Geometry.Point([lng, lat])

    @staticmethod
    def point_buffer(
        lat: float, lng: float, radius_km: float
    ) -> ee.Geometry.Polygon:
        """
        Create circular buffer around a point.

        Args:
            lat: Latitude
            lng: Longitude
            radius_km: Radius in kilometers

        Returns:
            ee.Geometry (circular polygon)
        """
        point = ee.Geometry.Point([lng, lat])
        return point.buffer(radius_km * 1000)  # Convert to meters

    def get_image(self, dataset_id: str) -> ee.Image:
        """
        Get a single image from dataset.

        Args:
            dataset_id: GEE dataset ID (e.g., 'USGS/SRTMGL1_003')

        Returns:
            ee.Image
        """
        self.initialize()
        return ee.Image(dataset_id)

    def get_collection(
        self,
        collection_id: str,
        bounds: Optional[Tuple[float, float, float, float]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ee.ImageCollection:
        """
        Get filtered ImageCollection.

        Args:
            collection_id: GEE collection ID (e.g., 'UCSB-CHG/CHIRPS/DAILY')
            bounds: Geographic bounds (optional)
            start_date: Start date filter (optional)
            end_date: End date filter (optional)

        Returns:
            Filtered ee.ImageCollection
        """
        self.initialize()
        collection = ee.ImageCollection(collection_id)

        # Filter by bounds
        if bounds:
            geometry = self.bounds_to_geometry(bounds)
            collection = collection.filterBounds(geometry)

        # Filter by date if provided
        if start_date and end_date:
            collection = collection.filterDate(
                start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            )

        return collection

    def reduce_region(
        self,
        image: ee.Image,
        bounds: Tuple[float, float, float, float],
        reducer: ee.Reducer,
        scale: int = 100,
    ) -> Dict[str, Any]:
        """
        Reduce image over a region.

        Args:
            image: ee.Image to reduce
            bounds: Geographic bounds
            reducer: ee.Reducer to apply
            scale: Resolution in meters

        Returns:
            Dictionary with reduced values
        """
        self.initialize()
        geometry = self.bounds_to_geometry(bounds)

        result = image.reduceRegion(
            reducer=reducer,
            geometry=geometry,
            scale=scale,
            maxPixels=settings.MAX_PIXELS_PER_REQUEST,
            bestEffort=True,
        )

        return result.getInfo()

    def sample_region(
        self,
        image: ee.Image,
        bounds: Tuple[float, float, float, float],
        scale: int = 100,
        num_pixels: int = 1000,
    ) -> Dict[str, Any]:
        """
        Sample random pixels from a region.

        Args:
            image: ee.Image to sample
            bounds: Geographic bounds
            scale: Resolution in meters
            num_pixels: Number of pixels to sample

        Returns:
            Dictionary with sampled features
        """
        self.initialize()
        geometry = self.bounds_to_geometry(bounds)

        samples = image.sample(
            region=geometry,
            scale=scale,
            numPixels=num_pixels,
            geometries=True,
        )

        return samples.getInfo()


# Singleton instance
gee_client = GEEClient()
