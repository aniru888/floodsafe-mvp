"""
Hotspots Service - Unified service for waterlogging hotspot predictions.

Combines:
- Static hotspot data (from JSON)
- XGBoost model predictions (weather-sensitive)
- FHI calculations (real-time weather from Open-Meteo)

Provides GeoJSON FeatureCollection for map rendering with:
- Risk probability from ML model
- FHI (Flood Hazard Index) from weather data
- Color-coded risk levels
"""

import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from .xgboost_hotspot import XGBoostHotspotModel, get_risk_level, load_trained_model
from .fhi_calculator import calculate_fhi_for_location, get_fhi_calculator

logger = logging.getLogger(__name__)


class HotspotsService:
    """
    Service for managing and querying waterlogging hotspots.

    Provides:
    - All hotspots with current risk levels
    - Individual hotspot queries
    - Risk at arbitrary points
    """

    # Response cache (5 minute TTL)
    CACHE_TTL = timedelta(minutes=5)

    def __init__(self, data_dir: Optional[Path] = None, models_dir: Optional[Path] = None, city: str = "delhi"):
        """
        Initialize hotspots service.

        Args:
            data_dir: Path to data directory containing hotspots JSON
            models_dir: Path to models directory containing XGBoost model
            city: City key (delhi, bangalore, yogyakarta)
        """
        # Resolve directories relative to backend root
        if data_dir is None:
            data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
        if models_dir is None:
            models_dir = Path(__file__).resolve().parent.parent.parent.parent / "models"

        self.data_dir = data_dir
        self.models_dir = models_dir
        self.city = city

        # Data storage
        self.hotspots_data: List[Dict] = []
        self.predictions_cache: Dict[str, Dict] = {}  # Pre-computed ML predictions
        self.top_city_predictors: List[Dict] = []  # City-level XGBoost feature importance
        self.hotspot_model: Optional[XGBoostHotspotModel] = None

        # Response cache
        self._response_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_key: Optional[str] = None

        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize service by loading data and models.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        success = True

        # Load hotspots data (city-specific file)
        hotspots_file = self.data_dir / f"{self.city}_waterlogging_hotspots.json"
        if hotspots_file.exists():
            try:
                with open(hotspots_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Handle both formats: {hotspots: [...]} or just [...]
                    if isinstance(data, dict) and "hotspots" in data:
                        self.hotspots_data = data["hotspots"]
                    elif isinstance(data, list):
                        self.hotspots_data = data
                    else:
                        logger.error(f"Unexpected hotspots data format: {type(data)}")
                        self.hotspots_data = []
                        success = False
                logger.info(f"Loaded {len(self.hotspots_data)} waterlogging hotspots")
            except Exception as e:
                logger.error(f"Failed to load hotspots: {e}")
                self.hotspots_data = []
                success = False
        else:
            logger.warning(f"Hotspots file not found: {hotspots_file}")
            self.hotspots_data = []
            success = False

        # Load pre-computed predictions cache (per-city XGBoost models)
        # Try city-specific cache first, fall back to default (Delhi) cache
        cache_file = self.data_dir / f"{self.city}_predictions_cache.json"
        if not cache_file.exists():
            # Fall back to original Delhi cache for backward compatibility
            if self.city == "delhi":
                cache_file = self.data_dir / "hotspot_predictions_cache.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    self.predictions_cache = cache_data.get("predictions", {})
                    self.top_city_predictors = cache_data.get("top_city_predictors", [])
                logger.info(f"Loaded pre-computed predictions for {len(self.predictions_cache)} hotspots from {cache_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load predictions cache: {e}")
                self.predictions_cache = {}
        else:
            logger.info(f"No predictions cache found for {self.city} - will use severity-based fallback")
            self.predictions_cache = {}

        # Load trained XGBoost model (Delhi-only — model trained on Delhi data)
        if self.city == "delhi":
            model_path = self.models_dir / "xgboost_hotspot"
            if model_path.exists():
                try:
                    self.hotspot_model = load_trained_model(model_path)
                    logger.info("XGBoost hotspot model loaded")
                except Exception as e:
                    logger.warning(f"Failed to load hotspot model: {e}")
                    self.hotspot_model = None
            else:
                logger.info("No trained hotspot model found - using severity-based risk estimation")
                self.hotspot_model = None
        else:
            logger.info(f"Skipping XGBoost model for {self.city} (Delhi-only) — using severity-based FHI")
            self.hotspot_model = None

        self._initialized = success or len(self.hotspots_data) > 0
        return self._initialized

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized

    async def get_all_hotspots(
        self,
        include_fhi: bool = True,
        test_fhi_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get all hotspots with current risk levels.

        Args:
            include_fhi: Include FHI calculation (weather-based)
            test_fhi_override: Test mode - 'high', 'extreme', or 'mixed'

        Returns:
            GeoJSON FeatureCollection with all hotspots
        """
        if not self._initialized:
            self.initialize()

        if not self.hotspots_data:
            raise RuntimeError("Hotspots data not loaded")

        # Check cache (skip for test mode)
        cache_key = f"fhi={include_fhi}:test={test_fhi_override}"
        if (
            not test_fhi_override
            and self._response_cache
            and self._cache_key == cache_key
            and self._cache_timestamp
            and datetime.now() - self._cache_timestamp < self.CACHE_TTL
        ):
            cache_age = (datetime.now() - self._cache_timestamp).total_seconds()
            logger.info(f"Returning cached hotspots response (age: {cache_age:.1f}s)")
            return self._response_cache

        # Test FHI override values
        TEST_FHI_VALUES = {
            "high": {"fhi_score": 0.55, "fhi_level": "high", "fhi_color": "#f97316"},
            "extreme": {"fhi_score": 0.85, "fhi_level": "extreme", "fhi_color": "#ef4444"},
        }

        # Pre-calculate FHI for all hotspots in parallel
        fhi_results: Dict[int, Dict] = {}

        if include_fhi and not test_fhi_override:
            # Use semaphore to limit concurrent API calls (Open-Meteo rate limiting)
            semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

            logger.info(f"Starting parallel FHI calculation for {len(self.hotspots_data)} hotspots...")
            start_time = datetime.now()

            # Launch all FHI calculations in parallel
            tasks = [
                self._calculate_single_hotspot_fhi(hotspot, idx, semaphore)
                for idx, hotspot in enumerate(self.hotspots_data)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and track failures
            exception_count = 0
            unknown_count = 0
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"FHI calculation exception: {result}")
                    exception_count += 1
                    continue
                idx, fhi_data = result
                fhi_results[idx] = fhi_data
                # Track "unknown" results (API failures that returned defaults)
                if fhi_data.get("fhi_level") == "unknown":
                    unknown_count += 1

            elapsed = (datetime.now() - start_time).total_seconds()
            success_count = len(fhi_results) - unknown_count
            total_count = len(self.hotspots_data)

            # Log failure rate for monitoring
            failure_rate = 1 - (success_count / total_count) if total_count > 0 else 0
            if failure_rate > 0.1:  # >10% failures - warn
                logger.warning(
                    f"HIGH FHI failure rate: {failure_rate*100:.1f}% "
                    f"({total_count - success_count}/{total_count} failed/unknown) in {elapsed:.2f}s"
                )
            else:
                logger.info(
                    f"FHI calculation completed: {success_count}/{total_count} successful "
                    f"({unknown_count} unknown, {exception_count} exceptions) in {elapsed:.2f}s"
                )

        # Build GeoJSON features
        features = []
        for idx, hotspot in enumerate(self.hotspots_data):
            # Get base susceptibility from cache or severity fallback
            hotspot_id_str = str(hotspot.get("id", idx))

            if hotspot_id_str in self.predictions_cache:
                base_susceptibility = self.predictions_cache[hotspot_id_str].get("base_susceptibility", 0.5)
            else:
                # Fallback to historical severity
                severity_map = {
                    "extreme": 0.85, "critical": 0.85,
                    "high": 0.65, "severe": 0.65,
                    "moderate": 0.45,
                    "low": 0.25,
                }
                severity = hotspot.get("severity_history") or hotspot.get("historical_severity", "moderate")
                if severity:
                    severity = severity.lower()
                base_susceptibility = severity_map.get(severity, 0.5)

            risk_level, risk_color = get_risk_level(base_susceptibility)

            # Get FHI data
            fhi_data = {}
            if include_fhi:
                if test_fhi_override:
                    # Test override mode
                    if test_fhi_override.lower() == "mixed":
                        if idx % 5 == 0:  # 20% extreme
                            fhi_data = {**TEST_FHI_VALUES["extreme"], "elevation_m": 220.0}
                        elif idx % 3 == 0:  # ~30% high
                            fhi_data = {**TEST_FHI_VALUES["high"], "elevation_m": 220.0}
                        else:  # rest low
                            fhi_data = {"fhi_score": 0.15, "fhi_level": "low", "fhi_color": "#22c55e", "elevation_m": 220.0}
                    elif test_fhi_override.lower() in TEST_FHI_VALUES:
                        fhi_data = {**TEST_FHI_VALUES[test_fhi_override.lower()], "elevation_m": 220.0}
                else:
                    # Use pre-calculated FHI from parallel execution
                    fhi_data = fhi_results.get(idx, {
                        "fhi_score": 0.25,
                        "fhi_level": "unknown",
                        "fhi_color": "#9ca3af",
                        "elevation_m": 220.0,
                    })

            # Determine source and verification status
            source = hotspot.get("source", "mcd_reports")
            verified = source != "osm_underpass"

            # Get coordinates (support both naming conventions)
            lng = hotspot.get("lng") or hotspot.get("longitude")
            lat = hotspot.get("lat") or hotspot.get("latitude")

            if lng is None or lat is None:
                logger.warning(f"Skipping hotspot without coordinates: {hotspot.get('id')}")
                continue

            # Build properties
            properties = {
                "id": hotspot.get("id", idx),
                "name": hotspot.get("name", "Unknown"),
                "zone": hotspot.get("zone", "Unknown"),
                "description": hotspot.get("description", ""),
                "risk_probability": round(base_susceptibility, 3),
                "risk_level": risk_level,
                "risk_color": risk_color,
                "historical_severity": hotspot.get("severity_history") or hotspot.get("historical_severity", "unknown"),
                "source": source,
                "verified": verified,
                "osm_id": hotspot.get("osm_id"),
            }

            # Add per-hotspot XGBoost feature importance (if available in predictions cache)
            if hotspot_id_str in self.predictions_cache:
                cached = self.predictions_cache[hotspot_id_str]
                top_features = cached.get("top_features")
                if top_features:
                    properties["top_features"] = top_features

            # Add FHI data if calculated
            properties.update(fhi_data)

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat],  # GeoJSON uses [lng, lat]
                },
                "properties": properties,
            })

        # Count verified vs unverified and source composition
        verified_count = sum(1 for f in features if f["properties"].get("verified", True))
        unverified_count = len(features) - verified_count
        source_counts: Dict[str, int] = {}
        for f in features:
            src = f["properties"].get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1

        response = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_hotspots": len(features),
                "verified_count": verified_count,
                "unverified_count": unverified_count,
                "composition": source_counts,
                "predictions_source": "ml_cache" if self.predictions_cache else "severity_fallback",
                "cached_predictions_count": len(self.predictions_cache),
                "model_available": self.hotspot_model is not None and self.hotspot_model.is_trained,
                "fhi_enabled": include_fhi,
                "fhi_parallel": True,
                "test_mode": test_fhi_override.lower() if test_fhi_override else None,
                "risk_thresholds": {
                    "low": "0.0-0.25",
                    "moderate": "0.25-0.50",
                    "high": "0.50-0.75",
                    "extreme": "0.75-1.0",
                },
                "top_city_predictors": self.top_city_predictors,
            },
        }

        # Cache response (skip for test mode)
        if not test_fhi_override:
            self._response_cache = response
            self._cache_timestamp = datetime.now()
            self._cache_key = cache_key
            logger.info(f"Cached hotspots response (key: {cache_key})")

        return response

    async def get_hotspot_by_id(self, hotspot_id: int, include_fhi: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get risk details for a specific hotspot.

        Args:
            hotspot_id: Hotspot ID
            include_fhi: Include FHI calculation

        Returns:
            Hotspot details or None if not found
        """
        if not self._initialized:
            self.initialize()

        if not self.hotspots_data:
            return None

        # Find hotspot
        hotspot = None
        for h in self.hotspots_data:
            if h.get("id") == hotspot_id:
                hotspot = h
                break

        if hotspot is None:
            return None

        # Get base susceptibility
        hotspot_id_str = str(hotspot_id)
        if hotspot_id_str in self.predictions_cache:
            base_susceptibility = self.predictions_cache[hotspot_id_str].get("base_susceptibility", 0.5)
        else:
            severity_map = {"extreme": 0.85, "high": 0.65, "moderate": 0.45, "low": 0.25}
            severity = hotspot.get("severity_history", "moderate")
            base_susceptibility = severity_map.get(severity.lower() if severity else "moderate", 0.5)

        risk_level, risk_color = get_risk_level(base_susceptibility)

        lng = hotspot.get("lng") or hotspot.get("longitude")
        lat = hotspot.get("lat") or hotspot.get("latitude")

        response = {
            "id": hotspot["id"],
            "name": hotspot.get("name", "Unknown"),
            "lat": lat,
            "lng": lng,
            "zone": hotspot.get("zone", "Unknown"),
            "risk_probability": round(base_susceptibility, 3),
            "risk_level": risk_level,
            "risk_color": risk_color,
            "description": hotspot.get("description"),
        }

        # Calculate FHI if requested
        if include_fhi and lat is not None and lng is not None:
            try:
                fhi_result = await calculate_fhi_for_location(lat=lat, lng=lng)
                response["fhi"] = fhi_result
            except Exception as e:
                logger.warning(f"FHI calculation failed for hotspot {hotspot_id}: {e}")

        return response

    async def _calculate_single_hotspot_fhi(
        self,
        hotspot: Dict,
        idx: int,
        semaphore: asyncio.Semaphore,
        timeout_seconds: float = 30.0,  # Increased from 10s to allow for retries
    ) -> Tuple[int, Dict]:
        """
        Calculate FHI for a single hotspot with timeout and semaphore limiting.

        Returns (idx, fhi_data) tuple for later mapping.
        """
        async with semaphore:
            try:
                lat = hotspot.get("lat") or hotspot.get("latitude")
                lng = hotspot.get("lng") or hotspot.get("longitude")

                if lat is None or lng is None:
                    return (idx, {
                        "fhi_score": 0.25,
                        "fhi_level": "unknown",
                        "fhi_color": "#9ca3af",
                        "elevation_m": 220.0,
                    })

                fhi_result = await asyncio.wait_for(
                    calculate_fhi_for_location(lat=lat, lng=lng),
                    timeout=timeout_seconds
                )
                return (idx, {
                    "fhi_score": fhi_result["fhi_score"],
                    "fhi_level": fhi_result["fhi_level"],
                    "fhi_color": fhi_result["fhi_color"],
                    "elevation_m": fhi_result["elevation_m"],
                })
            except asyncio.TimeoutError:
                logger.warning(f"FHI calculation timed out for hotspot {hotspot.get('id')} ({hotspot.get('name')})")
                return (idx, {
                    "fhi_score": 0.15,
                    "fhi_level": "low",
                    "fhi_color": "#22c55e",
                    "elevation_m": 220.0,
                })
            except Exception as e:
                logger.warning(f"FHI calculation failed for hotspot {hotspot.get('id')}: {e}")
                return (idx, {
                    "fhi_score": 0.25,
                    "fhi_level": "unknown",
                    "fhi_color": "#9ca3af",
                    "elevation_m": 220.0,
                })

    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status."""
        return {
            "status": "healthy" if self._initialized else "initializing",
            "hotspots_loaded": len(self.hotspots_data) > 0,
            "total_hotspots": len(self.hotspots_data),
            "model_loaded": self.hotspot_model is not None,
            "model_trained": self.hotspot_model.is_trained if self.hotspot_model else False,
            "predictions_cached": len(self.predictions_cache) > 0,
            "cached_predictions_count": len(self.predictions_cache),
        }

    @staticmethod
    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate haversine distance between two points in km."""
        R = 6371  # Earth radius in km

        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        dlat = np.radians(lat2 - lat1)
        dlng = np.radians(lng2 - lng1)

        a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        return R * c


# Per-city service instances
_hotspots_services: Dict[str, HotspotsService] = {}


def get_hotspots_service(city: str = "delhi") -> HotspotsService:
    """Get hotspots service instance for a city (lazy-initialized)."""
    if city not in _hotspots_services:
        service = HotspotsService(city=city)
        service.initialize()
        _hotspots_services[city] = service
    return _hotspots_services[city]
