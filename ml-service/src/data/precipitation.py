"""
Precipitation Data Fetcher.

Fetches daily rainfall data from CHIRPS (Climate Hazards Group InfraRed
Precipitation with Station data).

Dataset: UCSB-CHG/CHIRPS/DAILY
Resolution: 0.05 degrees (~5.5km)
Coverage: Global, 1981-present
"""

import ee
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional
import logging

from ..core.config import settings
from .base import BaseDataFetcher, DataFetchError
from .gee_client import gee_client

logger = logging.getLogger(__name__)


class PrecipitationFetcher(BaseDataFetcher):
    """
    Fetches precipitation data from CHIRPS via Google Earth Engine.

    Provides daily rainfall measurements and aggregated features
    for flood prediction models.
    """

    @property
    def source_name(self) -> str:
        return "precipitation"

    @property
    def cache_ttl_days(self) -> int:
        return 1  # Daily data, cache for 1 day

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Fetch daily precipitation data from CHIRPS.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Start date for data retrieval
            end_date: End date for data retrieval

        Returns:
            DataFrame with columns [date, precipitation_mm]

        Raises:
            DataFetchError: If GEE query fails
        """
        if not start_date or not end_date:
            raise DataFetchError("start_date and end_date are required for precipitation data")

        try:
            gee_client.initialize()

            # Get CHIRPS collection
            collection = gee_client.get_collection(
                settings.GEE_PRECIPITATION,
                bounds=bounds,
                start_date=start_date,
                end_date=end_date,
            )

            # Check if collection is empty
            count = collection.size().getInfo()
            if count == 0:
                logger.warning(
                    f"No CHIRPS data found for {start_date.date()} to {end_date.date()}"
                )
                return pd.DataFrame(columns=["date", "precipitation_mm"])

            # Get geometry for spatial reduction
            geometry = gee_client.bounds_to_geometry(bounds)

            # Extract daily precipitation values
            def extract_daily_precip(image: ee.Image) -> ee.Feature:
                """Extract mean precipitation for a single day."""
                # CHIRPS band is 'precipitation'
                mean_precip = image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=5500,  # ~5.5km resolution
                    maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                )

                # Get date from image
                date = ee.Date(image.get("system:time_start"))

                return ee.Feature(
                    None,
                    {
                        "date": date.format("YYYY-MM-dd"),
                        "precipitation": mean_precip.get("precipitation"),
                    },
                )

            # Map over collection
            features = collection.map(extract_daily_precip)

            # Convert to Python list
            feature_list = features.getInfo()["features"]

            # Build DataFrame
            data = []
            for feature in feature_list:
                props = feature["properties"]
                precip = props.get("precipitation")

                # Handle None values (cloud cover, missing data)
                if precip is None:
                    precip = 0.0

                data.append(
                    {
                        "date": pd.to_datetime(props["date"]),
                        "precipitation_mm": float(precip),
                    }
                )

            df = pd.DataFrame(data)
            df = df.sort_values("date").reset_index(drop=True)

            logger.info(
                f"Fetched {len(df)} days of precipitation data "
                f"({start_date.date()} to {end_date.date()})"
            )

            return df

        except Exception as e:
            logger.error(f"Failed to fetch CHIRPS data: {e}")
            raise DataFetchError(f"CHIRPS fetch failed: {str(e)}") from e

    def get_rainfall_features(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
        lookback_days: int = 7,
    ) -> Dict[str, float]:
        """
        Get aggregated rainfall features for model input.

        Args:
            bounds: Geographic bounds
            reference_date: Date to calculate features for
            lookback_days: Number of days to look back (default 7)

        Returns:
            Dictionary with:
                - rainfall_24h: Rainfall in last 24 hours (mm)
                - rainfall_3d: Cumulative rainfall in last 3 days (mm)
                - rainfall_7d: Cumulative rainfall in last 7 days (mm)
                - max_daily_7d: Maximum daily rainfall in last 7 days (mm)
                - wet_days_7d: Number of days with >1mm rain in last 7 days

        Example:
            >>> fetcher = PrecipitationFetcher()
            >>> features = fetcher.get_rainfall_features(
            ...     bounds=(28.4, 76.8, 28.9, 77.4),
            ...     reference_date=datetime(2024, 7, 15),
            ...     lookback_days=7
            ... )
            >>> print(features['rainfall_24h'])
            45.3
        """
        # Calculate date range
        end_date = reference_date
        start_date = reference_date - timedelta(days=lookback_days)

        # Fetch data
        df = self.fetch(bounds, start_date, end_date)

        if df.empty:
            logger.warning("No precipitation data available, returning zero features")
            return {
                "rainfall_24h": 0.0,
                "rainfall_3d": 0.0,
                "rainfall_7d": 0.0,
                "max_daily_7d": 0.0,
                "wet_days_7d": 0,
            }

        # Ensure we have the reference date
        df_sorted = df.sort_values("date", ascending=False)

        # Calculate features
        features = {}

        # Last 24h (most recent day)
        features["rainfall_24h"] = float(df_sorted.iloc[0]["precipitation_mm"]) if not df_sorted.empty else 0.0

        # Last 3 days
        last_3d = df_sorted.head(3)
        features["rainfall_3d"] = float(last_3d["precipitation_mm"].sum())

        # Last 7 days
        last_7d = df_sorted.head(lookback_days)
        features["rainfall_7d"] = float(last_7d["precipitation_mm"].sum())

        # Max daily in last 7 days
        features["max_daily_7d"] = float(last_7d["precipitation_mm"].max()) if not last_7d.empty else 0.0

        # Wet days (>1mm threshold)
        features["wet_days_7d"] = int((last_7d["precipitation_mm"] > 1.0).sum())

        logger.info(
            f"Precipitation features for {reference_date.date()}: "
            f"24h={features['rainfall_24h']:.1f}mm, "
            f"7d={features['rainfall_7d']:.1f}mm, "
            f"wet_days={features['wet_days_7d']}"
        )

        return features
