"""
Backend API wrapper for ML flood predictions.

Proxies requests to the ML service with caching and error handling.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from datetime import datetime
import httpx
import hashlib
import json
import logging

from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory LRU-bounded cache (max 100 entries)
_PREDICTION_CACHE_MAX = 100
_prediction_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def _get_cache_key(bbox: str, resolution_km: float, horizon_days: int) -> str:
    """Generate cache key from request parameters."""
    data = f"{bbox}:{resolution_km}:{horizon_days}"
    return hashlib.md5(data.encode()).hexdigest()


def _is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Check if cache entry is still valid."""
    if "timestamp" not in cache_entry:
        return False
    age = (datetime.now() - cache_entry["timestamp"]).total_seconds()
    return age < CACHE_TTL_SECONDS


@router.get("/grid")
async def get_prediction_grid(
    bbox: str = Query(..., description="minLng,minLat,maxLng,maxLat"),
    resolution_km: float = Query(1.0, ge=0.5, le=5.0, description="Grid resolution in km"),
    horizon_days: int = Query(0, ge=0, le=7, description="Days ahead (0=today)"),
):
    """
    Get flood prediction grid as GeoJSON FeatureCollection.

    This endpoint proxies to the ML service and caches results.

    Args:
        bbox: Bounding box as "minLng,minLat,maxLng,maxLat"
        resolution_km: Grid resolution in kilometers
        horizon_days: Days ahead to predict (0=today)

    Returns:
        GeoJSON FeatureCollection with flood probability at each grid point
    """
    # Check if ML service is enabled
    if not settings.ML_SERVICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="ML service is not enabled",
        )

    # Parse bbox
    try:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise ValueError("bbox must have 4 parts")
        min_lng, min_lat, max_lng, max_lat = map(float, parts)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid bbox format. Expected 'minLng,minLat,maxLng,maxLat'. Error: {e}",
        )

    # Check cache
    cache_key = _get_cache_key(bbox, resolution_km, horizon_days)
    if cache_key in _prediction_cache:
        cache_entry = _prediction_cache[cache_key]
        if _is_cache_valid(cache_entry):
            logger.info(f"Cache hit for predictions: {cache_key}")
            return cache_entry["data"]

    # Build ML service request
    ml_request = {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lng": min_lng,
        "max_lng": max_lng,
        "resolution_km": resolution_km,
        "horizon_days": horizon_days,
    }

    # Call ML service
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/api/v1/predictions/forecast-grid",
                json=ml_request,
            )

            if response.status_code != 200:
                logger.error(f"ML service error: {response.status_code} - {response.text}")
                # Return empty GeoJSON instead of 404 when ML models aren't available
                # This gracefully handles the case where ensemble models aren't trained
                if response.status_code == 404:
                    logger.warning("ML predictions endpoint not available (model not trained). Returning empty grid.")
                    return {
                        "type": "FeatureCollection",
                        "features": [],
                        "metadata": {
                            "model_status": "not_available",
                            "message": "Prediction models not yet trained for this region"
                        }
                    }
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"ML service error: {response.text}",
                )

            result = response.json()

            # Cache the result (with LRU eviction)
            _prediction_cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now(),
            }
            if len(_prediction_cache) > _PREDICTION_CACHE_MAX:
                excess = len(_prediction_cache) - _PREDICTION_CACHE_MAX
                for old_key in list(_prediction_cache.keys())[:excess]:
                    del _prediction_cache[old_key]

            # Clean old cache entries (simple cleanup)
            _cleanup_cache()

            logger.info(f"Prediction grid fetched: {len(result.get('features', []))} points")
            return result

    except httpx.TimeoutException:
        logger.error("ML service timeout")
        raise HTTPException(
            status_code=504,
            detail="ML service request timed out. The grid may be too large.",
        )
    except httpx.RequestError as e:
        logger.error(f"ML service request failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"ML service unavailable: {str(e)}",
        )


@router.get("/point")
async def get_prediction_point(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    horizon_days: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
):
    """
    Get flood prediction for a single point.

    Args:
        lat: Latitude
        lng: Longitude
        horizon_days: Number of days to forecast

    Returns:
        Flood probability forecast for the point
    """
    if not settings.ML_SERVICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="ML service is not enabled",
        )

    ml_request = {
        "latitude": lat,
        "longitude": lng,
        "horizon_days": horizon_days,
        "include_uncertainty": True,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/api/v1/predictions/forecast",
                json=ml_request,
            )

            if response.status_code != 200:
                logger.error(f"ML service error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"ML service error: {response.text}",
                )

            return response.json()

    except httpx.TimeoutException:
        logger.error("ML service timeout")
        raise HTTPException(
            status_code=504,
            detail="ML service request timed out",
        )
    except httpx.RequestError as e:
        logger.error(f"ML service request failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"ML service unavailable: {str(e)}",
        )


@router.get("/health")
async def predictions_health():
    """Check ML service health."""
    if not settings.ML_SERVICE_ENABLED:
        return {
            "status": "disabled",
            "ml_service_enabled": False,
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.ML_SERVICE_URL}/api/v1/predictions/health"
            )
            ml_health = response.json()

            return {
                "status": "healthy",
                "ml_service_enabled": True,
                "ml_service_status": ml_health.get("status"),
                "model_status": ml_health.get("model_status"),
            }

    except Exception as e:
        return {
            "status": "degraded",
            "ml_service_enabled": True,
            "ml_service_error": str(e),
        }


def _cleanup_cache():
    """Remove expired cache entries."""
    global _prediction_cache
    now = datetime.now()
    expired_keys = [
        key
        for key, entry in _prediction_cache.items()
        if (now - entry.get("timestamp", now)).total_seconds() > CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        del _prediction_cache[key]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
