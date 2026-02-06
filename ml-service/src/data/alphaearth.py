"""
AlphaEarth Data Fetcher.

Fetches 64-dimensional embeddings from Google's AlphaEarth dataset:
GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL

AlphaEarth provides pre-computed embeddings at 10m resolution,
useful for terrain classification and flood risk analysis.
"""

import ee
import numpy as np
from typing import Optional, Tuple, Literal
from datetime import datetime
import logging

from .base import BaseDataFetcher, DataFetchError
from .gee_client import gee_client
from ..core.config import settings, ALPHAEARTH_BANDS

logger = logging.getLogger(__name__)


class AlphaEarthFetcher(BaseDataFetcher):
    """
    Fetches AlphaEarth embeddings from Google Earth Engine.

    AlphaEarth provides 64-dimensional embeddings (bands A00-A63) at 10m resolution,
    derived from satellite imagery. These embeddings capture terrain characteristics
    useful for flood risk modeling.

    Example:
        fetcher = AlphaEarthFetcher()

        # Get embedding at a single point
        embedding = fetcher.get_embedding_at_point(28.6139, 77.2090, year=2023)
        # Returns: np.ndarray of shape (64,)

        # Get aggregated embedding for a region
        bounds = (28.4, 76.8, 28.9, 77.4)
        avg_embedding = fetcher.get_aggregated_embedding(bounds, method='mean')
        # Returns: np.ndarray of shape (64,)

        # Get spatial embeddings as a grid
        embeddings = fetcher.get_region_embeddings(bounds, scale=100)
        # Returns: np.ndarray of shape (H, W, 64)
    """

    @property
    def source_name(self) -> str:
        """Source identifier."""
        return "alphaearth"

    @property
    def cache_ttl_days(self) -> int:
        """Cache TTL: 7 days (embeddings are annual, updated yearly)."""
        return settings.CACHE_TTL_ALPHAEARTH

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> ee.Image:
        """
        Fetch AlphaEarth image for the given bounds and year.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Not used (annual data)
            end_date: Not used (annual data)
            **kwargs: Additional parameters
                - year (int): Year to fetch (default: 2023)

        Returns:
            ee.Image with 64 bands (A00-A63)

        Raises:
            DataFetchError: If image cannot be fetched
        """
        year = kwargs.get("year", 2023)

        try:
            gee_client.initialize()

            # Get the image collection
            collection = ee.ImageCollection(settings.GEE_ALPHAEARTH)

            # Filter by date (annual data, so just need one image from the year)
            image = collection.filterDate(f"{year}-01-01", f"{year}-12-31").first()

            # Verify image exists
            if image is None:
                raise DataFetchError(
                    f"No AlphaEarth data found for year {year} in bounds {bounds}"
                )

            # Select only the 64 embedding bands (A00-A63)
            image = image.select(ALPHAEARTH_BANDS)

            logger.info(f"Fetched AlphaEarth image for year {year}")
            return image

        except Exception as e:
            logger.error(f"Failed to fetch AlphaEarth data: {e}")
            raise DataFetchError(f"Failed to fetch AlphaEarth data: {str(e)}") from e

    def get_embedding_at_point(
        self,
        lat: float,
        lng: float,
        year: int = 2023,
        buffer_radius_m: float = 10.0,
    ) -> np.ndarray:
        """
        Get 64-dimensional embedding at a specific point.

        Args:
            lat: Latitude
            lng: Longitude
            year: Year to fetch (default: 2023)
            buffer_radius_m: Buffer radius in meters for sampling (default: 10m)

        Returns:
            np.ndarray of shape (64,) with embedding values

        Raises:
            DataFetchError: If embedding cannot be retrieved
        """
        try:
            gee_client.initialize()

            # Create a small buffer around the point for sampling
            point = gee_client.point_to_geometry(lat, lng)
            region = point.buffer(buffer_radius_m)

            # Convert bounds for caching
            # Create approximate bounds from point (for cache key)
            approx_bounds = (
                lat - 0.001,
                lng - 0.001,
                lat + 0.001,
                lng + 0.001,
            )

            # Fetch the image (uses caching)
            image = self.fetch(bounds=approx_bounds, year=year)

            # Sample the image at the point
            result = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=region,
                scale=10,  # 10m resolution
                maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                bestEffort=True,
            )

            # Extract values
            embedding_dict = result.getInfo()

            # Convert to numpy array (ensure order A00, A01, ..., A63)
            embedding = np.array([embedding_dict.get(band, 0.0) for band in ALPHAEARTH_BANDS])

            logger.info(f"Extracted embedding at ({lat}, {lng}) for year {year}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to get embedding at point ({lat}, {lng}): {e}")
            raise DataFetchError(
                f"Failed to get embedding at point ({lat}, {lng}): {str(e)}"
            ) from e

    def get_aggregated_embedding(
        self,
        bounds: Tuple[float, float, float, float],
        year: int = 2023,
        method: Literal["mean", "median", "stdDev"] = "mean",
        scale: int = 100,
    ) -> np.ndarray:
        """
        Get aggregated embedding for a region.

        Useful for summarizing terrain characteristics over an entire area.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            year: Year to fetch (default: 2023)
            method: Aggregation method - 'mean', 'median', or 'stdDev' (default: 'mean')
            scale: Resolution in meters for aggregation (default: 100m)

        Returns:
            np.ndarray of shape (64,) with aggregated embedding values

        Raises:
            DataFetchError: If aggregation fails
        """
        try:
            gee_client.initialize()

            # Fetch the image (uses caching)
            image = self.fetch(bounds=bounds, year=year)

            # Select reducer based on method
            if method == "mean":
                reducer = ee.Reducer.mean()
            elif method == "median":
                reducer = ee.Reducer.median()
            elif method == "stdDev":
                reducer = ee.Reducer.stdDev()
            else:
                raise ValueError(f"Invalid aggregation method: {method}")

            # Reduce over region
            result = gee_client.reduce_region(
                image=image,
                bounds=bounds,
                reducer=reducer,
                scale=scale,
            )

            # Convert to numpy array (ensure order A00, A01, ..., A63)
            embedding = np.array([result.get(band, 0.0) for band in ALPHAEARTH_BANDS])

            logger.info(
                f"Aggregated embedding for bounds {bounds} using method '{method}'"
            )
            return embedding

        except Exception as e:
            logger.error(f"Failed to aggregate embedding for region: {e}")
            raise DataFetchError(
                f"Failed to aggregate embedding for region: {str(e)}"
            ) from e

    def get_region_embeddings(
        self,
        bounds: Tuple[float, float, float, float],
        year: int = 2023,
        scale: int = 100,
    ) -> np.ndarray:
        """
        Get spatial embeddings as a grid for the entire region.

        Returns embeddings at every pixel within the bounds, useful for
        creating spatial feature maps for ML models.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            year: Year to fetch (default: 2023)
            scale: Resolution in meters (default: 100m)
                   Note: Lower values (e.g., 10m) give higher resolution but require more memory

        Returns:
            np.ndarray of shape (H, W, 64) where:
                H = height in pixels
                W = width in pixels
                64 = embedding dimensions

        Raises:
            DataFetchError: If download fails

        Warning:
            Large regions at fine resolution can exceed GEE's pixel limit.
            Use coarser scale (e.g., 100m) for larger regions.
        """
        try:
            gee_client.initialize()

            # Fetch the image (uses caching)
            image = self.fetch(bounds=bounds, year=year)

            # Convert bounds to geometry
            geometry = gee_client.bounds_to_geometry(bounds)

            # Sample the image at every pixel
            # Note: This can be memory-intensive for large regions
            lat_min, lng_min, lat_max, lng_max = bounds

            # Calculate approximate dimensions
            lat_span = lat_max - lat_min
            lng_span = lng_max - lng_min
            approx_height = int((lat_span * 111_000) / scale)  # 111km per degree latitude
            approx_width = int((lng_span * 111_000 * np.cos(np.radians((lat_min + lat_max) / 2))) / scale)
            approx_pixels = approx_height * approx_width

            if approx_pixels > settings.MAX_PIXELS_PER_REQUEST:
                logger.warning(
                    f"Region contains approximately {approx_pixels:,} pixels at {scale}m resolution. "
                    f"This may exceed GEE limits. Consider using larger scale or smaller bounds."
                )

            # Download as numpy array
            # GEE's sampleRectangle is best for regular grids
            try:
                # Get the array
                array = image.sampleRectangle(region=geometry, defaultValue=0)
                array_info = array.getInfo()

                # Extract arrays for each band and stack them
                band_arrays = []
                for band in ALPHAEARTH_BANDS:
                    band_data = np.array(array_info['properties'][band])
                    band_arrays.append(band_data)

                # Stack into shape (H, W, 64)
                embeddings = np.stack(band_arrays, axis=-1)

                logger.info(
                    f"Downloaded region embeddings: shape {embeddings.shape} at {scale}m resolution"
                )
                return embeddings

            except Exception as e:
                # Fallback: use sampling if sampleRectangle fails
                logger.warning(
                    f"sampleRectangle failed ({e}), falling back to point sampling"
                )

                # Sample points instead (less precise but more robust)
                num_samples = min(1000, settings.MAX_PIXELS_PER_REQUEST // 64)
                samples = gee_client.sample_region(
                    image=image,
                    bounds=bounds,
                    scale=scale,
                    num_pixels=num_samples,
                )

                # Extract features
                features = samples.get("features", [])
                if not features:
                    raise DataFetchError("No samples returned from region")

                # Convert to array (N, 64)
                sample_embeddings = []
                for feature in features:
                    props = feature.get("properties", {})
                    embedding = [props.get(band, 0.0) for band in ALPHAEARTH_BANDS]
                    sample_embeddings.append(embedding)

                embeddings_array = np.array(sample_embeddings)

                logger.info(
                    f"Sampled {len(features)} points with embeddings of shape {embeddings_array.shape}"
                )
                logger.warning(
                    "Returning sampled points (N, 64) instead of regular grid. "
                    "Use get_aggregated_embedding() for summary statistics."
                )

                return embeddings_array

        except Exception as e:
            logger.error(f"Failed to get region embeddings: {e}")
            raise DataFetchError(
                f"Failed to get region embeddings: {str(e)}"
            ) from e


# Convenience instance
alphaearth_fetcher = AlphaEarthFetcher()
