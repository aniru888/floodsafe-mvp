"""
Abstract Base Classes for Data Fetchers.

All data fetchers inherit from BaseDataFetcher which provides
caching and error handling.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
import hashlib
import json
import pickle
from pathlib import Path
import logging

from ..core.config import settings

logger = logging.getLogger(__name__)


class DataFetchError(Exception):
    """Custom exception for data fetching errors."""

    pass


class BaseDataFetcher(ABC):
    """
    Abstract base class for all data fetchers.

    Implements common caching and error handling logic.
    Subclasses must implement _fetch_data() method.
    """

    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self.cache_dir = Path(settings.DATA_CACHE_DIR) / self.source_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source (e.g., 'alphaearth', 'dem')."""
        pass

    @property
    @abstractmethod
    def cache_ttl_days(self) -> int:
        """Cache time-to-live in days."""
        pass

    @abstractmethod
    def _fetch_data(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> Any:
        """
        Fetch data from source. Must be implemented by subclasses.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            start_date: Start of time range (None for static data)
            end_date: End of time range (None for static data)
            **kwargs: Additional source-specific parameters

        Returns:
            Raw data from source (format varies by source)
        """
        pass

    def fetch(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        force_refresh: bool = False,
        **kwargs,
    ) -> Any:
        """
        Fetch data with caching support.

        Args:
            bounds: Geographic bounds (lat_min, lng_min, lat_max, lng_max)
            start_date: Start date for temporal data
            end_date: End date for temporal data
            force_refresh: Bypass cache and fetch fresh data
            **kwargs: Source-specific parameters

        Returns:
            Data from cache or fresh from source
        """
        # Generate cache key
        cache_key = self._generate_cache_key(bounds, start_date, end_date, kwargs)

        # Check cache
        if not force_refresh and self.cache_enabled:
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                logger.info(f"Cache hit for {self.source_name}: {cache_key[:8]}...")
                return cached_data

        # Fetch fresh data
        logger.info(f"Fetching fresh data from {self.source_name}")
        try:
            data = self._fetch_data(bounds, start_date, end_date, **kwargs)

            # Save to cache
            if self.cache_enabled:
                self._save_to_cache(cache_key, data)

            return data

        except Exception as e:
            logger.error(f"Failed to fetch {self.source_name}: {e}")
            raise DataFetchError(f"Failed to fetch {self.source_name}: {str(e)}") from e

    def _generate_cache_key(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        kwargs: Dict,
    ) -> str:
        """Generate unique cache key from parameters."""
        key_data = {
            "source": self.source_name,
            "bounds": bounds,
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
            "kwargs": {k: str(v) for k, v in kwargs.items()},
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[Any]:
        """Load data from cache if exists and valid."""
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if not cache_file.exists():
            return None

        # Check if cache is still valid (TTL)
        age_days = (
            datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        ).days

        if age_days > self.cache_ttl_days:
            cache_file.unlink()  # Delete expired cache
            logger.info(f"Cache expired for {self.source_name} (age: {age_days} days)")
            return None

        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def _save_to_cache(self, cache_key: str, data: Any) -> None:
        """Save data to cache."""
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)
            logger.info(f"Cached {self.source_name} data: {cache_key[:8]}...")
        except Exception as e:
            # Cache write failure shouldn't break the pipeline
            logger.warning(f"Failed to write cache: {e}")

    def clear_cache(self) -> int:
        """Clear all cached data for this source. Returns count of deleted files."""
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
            count += 1
        logger.info(f"Cleared {count} cache files for {self.source_name}")
        return count
