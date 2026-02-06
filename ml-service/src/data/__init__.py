"""Data fetching layer for GEE and external sources."""

from .base import BaseDataFetcher, DataFetchError
from .gee_client import gee_client, GEEClient
from .alphaearth import AlphaEarthFetcher, alphaearth_fetcher
from .precipitation import PrecipitationFetcher
from .era5_fetcher import ERA5Fetcher
from .dem_fetcher import DEMFetcher, dem_fetcher
from .surface_water import SurfaceWaterFetcher, surface_water_fetcher
from .landcover import LandcoverFetcher

__all__ = [
    "BaseDataFetcher",
    "DataFetchError",
    "GEEClient",
    "gee_client",
    "AlphaEarthFetcher",
    "alphaearth_fetcher",
    "PrecipitationFetcher",
    "ERA5Fetcher",
    "DEMFetcher",
    "dem_fetcher",
    "SurfaceWaterFetcher",
    "surface_water_fetcher",
    "LandcoverFetcher",
]
