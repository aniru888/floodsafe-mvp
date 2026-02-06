"""
ERA5 Land Data Fetcher.

Fetches weather and land surface data from ERA5-Land reanalysis.

Dataset: ECMWF/ERA5_LAND/DAILY_AGGR
Resolution: 0.1 degrees (~11km)
Coverage: Global, 1950-present (5-day lag)
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


class ERA5Fetcher(BaseDataFetcher):
    """
    Fetches ERA5-Land reanalysis data via Google Earth Engine.

    Provides daily weather and land surface variables for flood prediction.
    Includes temperature, precipitation, soil moisture, and runoff.
    """

    @property
    def source_name(self) -> str:
        return "era5"

    @property
    def cache_ttl_days(self) -> int:
        return 1  # Daily data, cache for 1 day

    # ERA5-Land bands we use
    BANDS = {
        "temperature_2m": "temperature_2m",  # Air temperature at 2m (K)
        "total_precipitation_sum": "total_precipitation_sum",  # Daily precip sum (m)
        "surface_runoff_sum": "surface_runoff_sum",  # Daily runoff sum (m)
        "volumetric_soil_water_layer_1": "volumetric_soil_water_layer_1",  # Soil moisture 0-7cm (m³/m³)
    }

    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Fetch daily ERA5-Land data.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Start date for data retrieval
            end_date: End date for data retrieval

        Returns:
            DataFrame with columns:
                - date
                - temperature_2m_k (Kelvin)
                - total_precipitation_m (meters)
                - surface_runoff_m (meters)
                - soil_moisture_m3m3 (volumetric fraction)

        Raises:
            DataFetchError: If GEE query fails
        """
        if not start_date or not end_date:
            raise DataFetchError("start_date and end_date are required for ERA5 data")

        try:
            gee_client.initialize()

            # Get ERA5-Land collection
            collection = gee_client.get_collection(
                settings.GEE_ERA5_LAND,
                bounds=bounds,
                start_date=start_date,
                end_date=end_date,
            )

            # Check if collection is empty
            count = collection.size().getInfo()
            if count == 0:
                logger.warning(
                    f"No ERA5-Land data found for {start_date.date()} to {end_date.date()}"
                )
                return pd.DataFrame(
                    columns=[
                        "date",
                        "temperature_2m_k",
                        "total_precipitation_m",
                        "surface_runoff_m",
                        "soil_moisture_m3m3",
                    ]
                )

            # Get geometry for spatial reduction
            geometry = gee_client.bounds_to_geometry(bounds)

            # Select bands we need
            band_list = list(self.BANDS.keys())
            collection = collection.select(band_list)

            # Extract daily values
            def extract_daily_values(image: ee.Image) -> ee.Feature:
                """Extract mean values for all bands for a single day."""
                # Compute mean over region
                mean_values = image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=11000,  # ~11km resolution
                    maxPixels=settings.MAX_PIXELS_PER_REQUEST,
                )

                # Get date from image
                date = ee.Date(image.get("system:time_start"))

                # Build properties dict
                props = {"date": date.format("YYYY-MM-dd")}
                for band_name in band_list:
                    props[band_name] = mean_values.get(band_name)

                return ee.Feature(None, props)

            # Map over collection
            features = collection.map(extract_daily_values)

            # Convert to Python list
            feature_list = features.getInfo()["features"]

            # Build DataFrame
            data = []
            for feature in feature_list:
                props = feature["properties"]

                # Extract and convert values
                row = {
                    "date": pd.to_datetime(props["date"]),
                    "temperature_2m_k": float(props.get("temperature_2m") or 273.15),  # Default ~0°C
                    "total_precipitation_m": float(props.get("total_precipitation_sum") or 0.0),
                    "surface_runoff_m": float(props.get("surface_runoff_sum") or 0.0),
                    "soil_moisture_m3m3": float(props.get("volumetric_soil_water_layer_1") or 0.0),
                }

                data.append(row)

            df = pd.DataFrame(data)
            df = df.sort_values("date").reset_index(drop=True)

            logger.info(
                f"Fetched {len(df)} days of ERA5-Land data "
                f"({start_date.date()} to {end_date.date()})"
            )

            return df

        except Exception as e:
            logger.error(f"Failed to fetch ERA5-Land data: {e}")
            raise DataFetchError(f"ERA5-Land fetch failed: {str(e)}") from e

    def get_weather_features(
        self,
        bounds: Tuple[float, float, float, float],
        reference_date: datetime,
        lookback_days: int = 7,
    ) -> Dict[str, float]:
        """
        Get aggregated weather features for model input.

        Args:
            bounds: Geographic bounds
            reference_date: Date to calculate features for
            lookback_days: Number of days to look back (default 7)

        Returns:
            Dictionary with:
                - temperature_mean: Mean temperature in last N days (°C)
                - temperature_min: Min temperature in last N days (°C)
                - temperature_max: Max temperature in last N days (°C)
                - precipitation_sum: Total precipitation in last N days (mm)
                - soil_moisture_mean: Mean soil moisture in last N days (m³/m³)
                - runoff_sum: Total surface runoff in last N days (mm)

        Example:
            >>> fetcher = ERA5Fetcher()
            >>> features = fetcher.get_weather_features(
            ...     bounds=(28.4, 76.8, 28.9, 77.4),
            ...     reference_date=datetime(2024, 7, 15),
            ...     lookback_days=7
            ... )
            >>> print(features['temperature_mean'])
            32.5
        """
        # Calculate date range
        end_date = reference_date
        start_date = reference_date - timedelta(days=lookback_days)

        # Fetch data
        df = self.fetch(bounds, start_date, end_date)

        if df.empty:
            logger.warning("No ERA5 data available, returning default features")
            return {
                "temperature_mean": 20.0,  # 20°C default
                "temperature_min": 15.0,
                "temperature_max": 25.0,
                "precipitation_sum": 0.0,
                "soil_moisture_mean": 0.2,
                "runoff_sum": 0.0,
            }

        # Convert temperature from Kelvin to Celsius
        df["temperature_2m_c"] = df["temperature_2m_k"] - 273.15

        # Convert meters to millimeters for precipitation and runoff
        df["total_precipitation_mm"] = df["total_precipitation_m"] * 1000
        df["surface_runoff_mm"] = df["surface_runoff_m"] * 1000

        # Calculate features
        features = {
            # Temperature (°C)
            "temperature_mean": float(df["temperature_2m_c"].mean()),
            "temperature_min": float(df["temperature_2m_c"].min()),
            "temperature_max": float(df["temperature_2m_c"].max()),

            # Precipitation (mm)
            "precipitation_sum": float(df["total_precipitation_mm"].sum()),

            # Soil moisture (volumetric fraction)
            "soil_moisture_mean": float(df["soil_moisture_m3m3"].mean()),

            # Runoff (mm)
            "runoff_sum": float(df["surface_runoff_mm"].sum()),
        }

        logger.info(
            f"ERA5 features for {reference_date.date()}: "
            f"temp={features['temperature_mean']:.1f}°C, "
            f"precip={features['precipitation_sum']:.1f}mm, "
            f"runoff={features['runoff_sum']:.1f}mm, "
            f"soil_moisture={features['soil_moisture_mean']:.3f}"
        )

        return features

    def get_latest_conditions(
        self,
        bounds: Tuple[float, float, float, float],
    ) -> Dict[str, float]:
        """
        Get current weather conditions (last available day).

        Args:
            bounds: Geographic bounds

        Returns:
            Dictionary with latest values for all variables

        Note:
            ERA5-Land has a 5-day lag, so "latest" is actually ~5 days ago
        """
        # ERA5 has ~5 day lag
        reference_date = datetime.now() - timedelta(days=6)

        # Get just the last day
        df = self.fetch(
            bounds,
            start_date=reference_date,
            end_date=reference_date,
        )

        if df.empty:
            logger.warning("No current ERA5 data available")
            return {
                "temperature_c": 20.0,
                "precipitation_mm": 0.0,
                "soil_moisture": 0.2,
                "runoff_mm": 0.0,
            }

        latest = df.iloc[0]

        return {
            "temperature_c": float(latest["temperature_2m_k"] - 273.15),
            "precipitation_mm": float(latest["total_precipitation_m"] * 1000),
            "soil_moisture": float(latest["soil_moisture_m3m3"]),
            "runoff_mm": float(latest["surface_runoff_m"] * 1000),
        }
