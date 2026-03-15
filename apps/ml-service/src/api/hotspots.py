"""
FastAPI endpoints for waterlogging hotspot risk prediction.

This module provides endpoints for:
- Getting all 62 Delhi waterlogging hotspots with current risk levels
- Getting risk for a specific location
- Dynamic risk calculation based on rainfall
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import numpy as np

from ..core.config import settings
from ..data.fhi_calculator import calculate_fhi_for_location

router = APIRouter()
logger = logging.getLogger(__name__)

# Global instances (loaded on startup)
hotspot_model = None
feature_extractor = None
hotspots_data: List[Dict] = []
predictions_cache: Dict[str, Dict] = {}  # Pre-computed ML predictions

# Response-level cache for /all endpoint (5 minute TTL)
_hotspots_response_cache: Dict[str, any] = {
    "data": None,
    "timestamp": None,
    "ttl": timedelta(minutes=5),
    "cache_key": None,
}


class HotspotRiskResponse(BaseModel):
    """Response for single hotspot risk query."""

    id: int
    name: str
    lat: float
    lng: float
    zone: str
    risk_probability: float = Field(..., ge=0, le=1)
    risk_level: str  # low, moderate, high, extreme
    risk_color: str  # hex color
    rainfall_factor: Optional[float] = None
    description: Optional[str] = None
    fhi: Optional[Dict] = Field(None, description="Flood Hazard Index data")

    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility


class AllHotspotsResponse(BaseModel):
    """GeoJSON FeatureCollection response with all hotspots."""

    type: str = "FeatureCollection"
    features: List[Dict]
    metadata: Dict


class RiskAtPointRequest(BaseModel):
    """Request for risk at a specific point."""

    latitude: float = Field(..., ge=28.3, le=29.0, description="Latitude (Delhi bounds)")
    longitude: float = Field(..., ge=76.7, le=77.5, description="Longitude (Delhi bounds)")


class RiskAtPointResponse(BaseModel):
    """Response for point risk query."""

    latitude: float
    longitude: float
    risk_probability: float
    risk_level: str
    risk_color: str
    nearest_hotspot: Optional[str] = None
    distance_to_hotspot_km: Optional[float] = None


def _get_risk_level_and_color(probability: float) -> tuple:
    """
    Convert probability to risk level and color.

    Risk levels based on research thresholds:
    - Low: 0.0 - 0.25
    - Moderate: 0.25 - 0.50
    - High: 0.50 - 0.75
    - Extreme: 0.75 - 1.0
    """
    if probability < 0.25:
        return "low", "#22c55e"  # green-500
    elif probability < 0.50:
        return "moderate", "#eab308"  # yellow-500
    elif probability < 0.75:
        return "high", "#f97316"  # orange-500
    else:
        return "extreme", "#ef4444"  # red-500


def _calculate_dynamic_risk(
    base_susceptibility: float,
    current_rainfall_mm: float,
    threshold_mm: float = 20.0,
) -> float:
    """
    Calculate dynamic risk based on static susceptibility and current rainfall.

    Formula from research:
    - Dry conditions: risk = susceptibility * 1.0
    - Light rain (10mm): risk = susceptibility * 1.5
    - Moderate rain (20mm): risk = susceptibility * 2.0
    - Heavy rain (40mm+): risk = susceptibility * 3.0 (capped)
    """
    if current_rainfall_mm <= 0:
        return base_susceptibility

    rainfall_factor = min(current_rainfall_mm / threshold_mm, 2.0)
    dynamic_risk = base_susceptibility * (1 + rainfall_factor)

    return min(dynamic_risk, 1.0)


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate haversine distance between two points in km."""
    R = 6371  # Earth radius in km

    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlng = np.radians(lng2 - lng1)

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c


async def _calculate_single_hotspot_fhi(
    hotspot: Dict,
    idx: int,
    semaphore: asyncio.Semaphore,
    timeout_seconds: float = 10.0,
) -> Tuple[int, Dict]:
    """
    Calculate FHI for a single hotspot with timeout and semaphore limiting.

    Returns (idx, fhi_data) tuple for later mapping.
    """
    async with semaphore:
        try:
            fhi_result = await asyncio.wait_for(
                calculate_fhi_for_location(
                    lat=hotspot["lat"],
                    lng=hotspot["lng"]
                ),
                timeout=timeout_seconds
            )
            return (idx, {
                "fhi_score": fhi_result["fhi_score"],
                "fhi_level": fhi_result["fhi_level"],
                "fhi_color": fhi_result["fhi_color"],
                "elevation_m": fhi_result["elevation_m"],
            })
        except asyncio.TimeoutError:
            logger.warning(f"FHI calculation timed out for hotspot {hotspot['id']} ({hotspot['name']})")
            return (idx, {
                "fhi_score": 0.15,
                "fhi_level": "low",
                "fhi_color": "#22c55e",
                "elevation_m": 220.0,
            })
        except Exception as e:
            logger.warning(f"FHI calculation failed for hotspot {hotspot['id']}: {e}")
            return (idx, {
                "fhi_score": 0.25,
                "fhi_level": "unknown",
                "fhi_color": "#9ca3af",
                "elevation_m": 220.0,
            })


@router.get("/all", response_model=AllHotspotsResponse)
async def get_all_hotspots(
    include_rainfall: bool = Query(False, description="Include current rainfall factor (slow, uses GEE)"),
    include_fhi: bool = Query(True, description="Include Flood Hazard Index (FHI) calculation"),
    test_fhi_override: str = Query(None, description="Override FHI for testing: 'high', 'extreme', or 'mixed'"),
):
    """
    Get all 62 Delhi waterlogging hotspots with current risk levels.

    Returns GeoJSON FeatureCollection for easy map rendering.
    Risk is calculated as:
    - Base susceptibility from XGBoost model (or historical severity)
    - Dynamic adjustment based on current rainfall (if available)

    Performance optimizations:
    - Response-level caching (5 minute TTL)
    - Parallel FHI calculations with asyncio.gather()
    - Semaphore limiting (max 10 concurrent API calls)
    """
    global hotspots_data, hotspot_model, _hotspots_response_cache

    if not hotspots_data:
        raise HTTPException(
            status_code=503,
            detail="Hotspots data not loaded. Service is initializing.",
        )

    # Check response cache (only for non-test, FHI-enabled requests)
    cache_key = f"fhi={include_fhi}:rain={include_rainfall}:test={test_fhi_override}"
    if (
        not test_fhi_override
        and _hotspots_response_cache["data"]
        and _hotspots_response_cache["cache_key"] == cache_key
        and _hotspots_response_cache["timestamp"]
        and datetime.now() - _hotspots_response_cache["timestamp"] < _hotspots_response_cache["ttl"]
    ):
        cache_age = (datetime.now() - _hotspots_response_cache["timestamp"]).total_seconds()
        logger.info(f"Returning cached hotspots response (age: {cache_age:.1f}s)")
        return _hotspots_response_cache["data"]

    features = []
    current_rainfall = 0.0

    # Try to get current rainfall from CHIRPS
    if include_rainfall:
        try:
            from ..data.precipitation import PrecipitationFetcher
            precip = PrecipitationFetcher()

            # Delhi regional bounds
            delhi_bounds = (28.4, 76.8, 28.9, 77.4)
            rainfall_features = precip.get_rainfall_features(
                bounds=delhi_bounds,
                reference_date=datetime.now(),
                lookback_days=1,
            )
            current_rainfall = rainfall_features.get("rainfall_24h", 0.0)
            logger.info(f"Current Delhi rainfall (24h): {current_rainfall:.1f}mm")
        except Exception as e:
            logger.warning(f"Failed to get current rainfall: {e}")
            current_rainfall = 0.0

    # Test FHI override values
    TEST_FHI_VALUES = {
        "high": {"fhi_score": 0.55, "fhi_level": "high", "fhi_color": "#f97316"},
        "extreme": {"fhi_score": 0.85, "fhi_level": "extreme", "fhi_color": "#ef4444"},
    }

    # Pre-calculate FHI for all hotspots in PARALLEL if needed
    fhi_results: Dict[int, Dict] = {}

    if include_fhi and not test_fhi_override:
        # Use semaphore to limit concurrent API calls (Open-Meteo rate limiting)
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        logger.info(f"Starting parallel FHI calculation for {len(hotspots_data)} hotspots...")
        start_time = datetime.now()

        # Launch all FHI calculations in parallel
        tasks = [
            _calculate_single_hotspot_fhi(hotspot, idx, semaphore)
            for idx, hotspot in enumerate(hotspots_data)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"FHI calculation exception: {result}")
                continue
            idx, fhi_data = result
            fhi_results[idx] = fhi_data

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Parallel FHI calculation completed: {len(fhi_results)}/{len(hotspots_data)} in {elapsed:.2f}s")

    # Build features with pre-calculated FHI data
    for idx, hotspot in enumerate(hotspots_data):
        # Base susceptibility from pre-computed ML predictions
        # Priority: 1) Pre-computed cache, 2) Historical severity fallback
        hotspot_id_str = str(hotspot["id"])

        if hotspot_id_str in predictions_cache:
            # Use pre-computed ML prediction (fast!)
            base_susceptibility = predictions_cache[hotspot_id_str]["base_susceptibility"]
        else:
            # Fallback to historical severity
            severity_map = {
                "extreme": 0.85,
                "high": 0.65,
                "moderate": 0.45,
                "low": 0.25,
            }
            base_susceptibility = severity_map.get(hotspot.get("severity_history", "moderate"), 0.5)

        # Apply rainfall factor
        risk_probability = _calculate_dynamic_risk(
            base_susceptibility=base_susceptibility,
            current_rainfall_mm=current_rainfall,
        )

        risk_level, risk_color = _get_risk_level_and_color(risk_probability)

        # Get FHI data (pre-calculated or from test override)
        fhi_data = {}
        if include_fhi:
            if test_fhi_override:
                # Test override mode
                if test_fhi_override.lower() == "mixed":
                    # Mixed mode: ~30% high, ~20% extreme, rest low
                    if idx % 5 == 0:  # 20% extreme
                        fhi_data = {**TEST_FHI_VALUES["extreme"], "elevation_m": 220.0}
                    elif idx % 3 == 0:  # ~30% high (minus the extreme ones)
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
        source = hotspot.get("source", "mcd_reports")  # Default to MCD for legacy data
        verified = source == "mcd_reports"  # MCD reports are verified, OSM underpasses are not

        # Create GeoJSON feature
        properties = {
            "id": hotspot["id"],
            "name": hotspot["name"],
            "zone": hotspot.get("zone", "unknown"),
            "description": hotspot.get("description", ""),
            "risk_probability": round(risk_probability, 3),
            "risk_level": risk_level,
            "risk_color": risk_color,
            "severity_history": hotspot.get("severity_history", "unknown"),
            "rainfall_24h_mm": round(current_rainfall, 1),
            "source": source,  # 'mcd_reports' or 'osm_underpass'
            "verified": verified,  # True for MCD-validated, False for ML-predicted
            "osm_id": hotspot.get("osm_id"),  # OSM way/node ID for underpasses
        }

        # Add FHI data if calculated
        properties.update(fhi_data)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [hotspot["lng"], hotspot["lat"]],  # GeoJSON uses [lng, lat]
            },
            "properties": properties,
        })

    # Count verified vs unverified hotspots
    verified_count = sum(1 for f in features if f["properties"].get("verified", True))
    unverified_count = len(features) - verified_count

    response = AllHotspotsResponse(
        type="FeatureCollection",
        features=features,
        metadata={
            "generated_at": datetime.now().isoformat(),
            "total_hotspots": len(features),
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "composition": {
                "mcd_reports": verified_count,
                "osm_underpass": unverified_count,
            },
            "current_rainfall_mm": round(current_rainfall, 1),
            "predictions_source": "ml_cache" if predictions_cache else "severity_fallback",
            "cached_predictions_count": len(predictions_cache),
            "model_available": hotspot_model is not None and hotspot_model.is_trained,
            "fhi_enabled": include_fhi,
            "fhi_parallel": True,  # New: indicates parallel calculation
            "test_mode": test_fhi_override.lower() if test_fhi_override else None,
            "test_mode_note": "FHI values are simulated for testing HARD AVOID routing" if test_fhi_override else None,
            "risk_thresholds": {
                "low": "0.0-0.25",
                "moderate": "0.25-0.50",
                "high": "0.50-0.75",
                "extreme": "0.75-1.0",
            },
            "fhi_formula": "FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T_modifier" if include_fhi else None,
            "fhi_components": {
                "P": "Precipitation forecast (35%)",
                "I": "Intensity (hourly max, 18%)",
                "S": "Soil saturation (12%)",
                "A": "Antecedent conditions (12%)",
                "R": "Runoff potential (8%)",
                "E": "Elevation risk (15%)",
            } if include_fhi else None,
        },
    )

    # Cache the response (only for non-test mode)
    if not test_fhi_override:
        _hotspots_response_cache["data"] = response
        _hotspots_response_cache["timestamp"] = datetime.now()
        _hotspots_response_cache["cache_key"] = cache_key
        logger.info(f"Cached hotspots response (key: {cache_key})")

    return response


@router.get("/hotspot/{hotspot_id}", response_model=HotspotRiskResponse)
async def get_hotspot_risk(
    hotspot_id: int,
    include_fhi: bool = Query(True, description="Include Flood Hazard Index (FHI) calculation"),
):
    """Get risk details for a specific hotspot by ID."""
    global hotspots_data

    if not hotspots_data:
        raise HTTPException(status_code=503, detail="Hotspots data not loaded")

    # Find hotspot
    hotspot = None
    for h in hotspots_data:
        if h["id"] == hotspot_id:
            hotspot = h
            break

    if hotspot is None:
        raise HTTPException(status_code=404, detail=f"Hotspot {hotspot_id} not found")

    # Get rainfall
    try:
        from ..data.precipitation import PrecipitationFetcher
        precip = PrecipitationFetcher()
        bounds = (
            hotspot["lat"] - 0.01,
            hotspot["lng"] - 0.01,
            hotspot["lat"] + 0.01,
            hotspot["lng"] + 0.01,
        )
        rainfall_features = precip.get_rainfall_features(
            bounds=bounds,
            reference_date=datetime.now(),
        )
        current_rainfall = rainfall_features.get("rainfall_24h", 0.0)
    except Exception:
        current_rainfall = 0.0

    # Get base susceptibility from cache or fallback to severity
    global predictions_cache
    hotspot_id_str = str(hotspot_id)

    if hotspot_id_str in predictions_cache:
        # Use pre-computed ML prediction (fast!)
        base_susceptibility = predictions_cache[hotspot_id_str]["base_susceptibility"]
        logger.info(f"Cached prediction for {hotspot['name']}: {base_susceptibility:.4f}")
    else:
        # Fallback to historical severity
        severity_map = {"extreme": 0.85, "high": 0.65, "moderate": 0.45, "low": 0.25}
        base_susceptibility = severity_map.get(hotspot.get("severity_history", "moderate"), 0.5)
        logger.info(f"Fallback to severity for {hotspot['name']}: {base_susceptibility:.4f}")

    risk_probability = _calculate_dynamic_risk(base_susceptibility, current_rainfall)
    risk_level, risk_color = _get_risk_level_and_color(risk_probability)

    # Calculate FHI if requested
    fhi_data = None
    if include_fhi:
        try:
            fhi_result = await calculate_fhi_for_location(
                lat=hotspot["lat"],
                lng=hotspot["lng"]
            )
            fhi_data = fhi_result
            logger.info(
                f"FHI for {hotspot['name']}: "
                f"score={fhi_result['fhi_score']:.3f}, "
                f"level={fhi_result['fhi_level']}"
            )
        except Exception as e:
            logger.warning(f"FHI calculation failed for hotspot {hotspot_id}: {e}")

    response_data = {
        "id": hotspot["id"],
        "name": hotspot["name"],
        "lat": hotspot["lat"],
        "lng": hotspot["lng"],
        "zone": hotspot.get("zone", "unknown"),
        "risk_probability": round(risk_probability, 3),
        "risk_level": risk_level,
        "risk_color": risk_color,
        "rainfall_factor": round(current_rainfall, 1),
        "description": hotspot.get("description"),
    }

    # Add FHI data if available
    if fhi_data:
        response_data["fhi"] = fhi_data

    return response_data


@router.post("/risk-at-point", response_model=RiskAtPointResponse)
async def get_risk_at_point(request: RiskAtPointRequest):
    """
    Get flood risk for any point in Delhi.

    Uses proximity to known hotspots and current rainfall to estimate risk.
    """
    global hotspots_data, hotspot_model

    if not hotspots_data:
        raise HTTPException(status_code=503, detail="Hotspots data not loaded")

    # Find nearest hotspot
    min_distance = float("inf")
    nearest_hotspot = None

    for h in hotspots_data:
        dist = _haversine_distance(
            request.latitude, request.longitude,
            h["lat"], h["lng"]
        )
        if dist < min_distance:
            min_distance = dist
            nearest_hotspot = h

    # Calculate risk based on proximity
    # If very close to hotspot (<0.5km), use hotspot's risk
    # If far (>5km), use low base risk
    if min_distance < 0.5:
        base_risk = 0.7  # Close to known hotspot
    elif min_distance < 1.0:
        base_risk = 0.5
    elif min_distance < 2.0:
        base_risk = 0.35
    elif min_distance < 5.0:
        base_risk = 0.2
    else:
        base_risk = 0.1

    # Get current rainfall
    try:
        from ..data.precipitation import PrecipitationFetcher
        precip = PrecipitationFetcher()
        bounds = (
            request.latitude - 0.01,
            request.longitude - 0.01,
            request.latitude + 0.01,
            request.longitude + 0.01,
        )
        rainfall_features = precip.get_rainfall_features(
            bounds=bounds,
            reference_date=datetime.now(),
        )
        current_rainfall = rainfall_features.get("rainfall_24h", 0.0)
    except Exception:
        current_rainfall = 0.0

    risk_probability = _calculate_dynamic_risk(base_risk, current_rainfall)
    risk_level, risk_color = _get_risk_level_and_color(risk_probability)

    return RiskAtPointResponse(
        latitude=request.latitude,
        longitude=request.longitude,
        risk_probability=round(risk_probability, 3),
        risk_level=risk_level,
        risk_color=risk_color,
        nearest_hotspot=nearest_hotspot["name"] if nearest_hotspot else None,
        distance_to_hotspot_km=round(min_distance, 2) if nearest_hotspot else None,
    )


@router.get("/simulate-fhi")
async def simulate_fhi(
    lat: float, lng: float, city: str = "delhi", precip_mm: float = 50.0,
):
    """
    Calculate FHI with overridden precipitation for scenario simulation.

    Returns the same FHI result structure but with forecast precipitation
    replaced by the specified precip_mm value.
    """
    result = await calculate_fhi_for_location(
        lat, lng, city=city, override_precip_mm=precip_mm,
    )
    return result


@router.get("/health")
async def health_check():
    """Check hotspots service health."""
    global hotspots_data, hotspot_model, predictions_cache

    return {
        "status": "healthy",
        "hotspots_loaded": len(hotspots_data) > 0,
        "total_hotspots": len(hotspots_data),
        "model_loaded": hotspot_model is not None,
        "model_trained": hotspot_model.is_trained if hotspot_model else False,
        "predictions_cached": len(predictions_cache) > 0,
        "cached_predictions_count": len(predictions_cache),
    }


class SARFloodExtentRequest(BaseModel):
    """Request for SAR-based flood extent analysis."""

    lat_min: float = Field(..., description="Minimum latitude")
    lng_min: float = Field(..., description="Minimum longitude")
    lat_max: float = Field(..., description="Maximum latitude")
    lng_max: float = Field(..., description="Maximum longitude")
    lookback_days: int = Field(default=7, ge=1, le=30, description="Days to look back for SAR imagery")


class SARFloodExtentResponse(BaseModel):
    """Response for SAR flood extent analysis."""

    bounds: Dict[str, float]
    flood_fraction: float = Field(..., ge=0, le=1, description="Fraction of area detected as flooded")
    vv_mean: Optional[float] = Field(None, description="Mean VV backscatter (dB)")
    vh_mean: Optional[float] = Field(None, description="Mean VH backscatter (dB)")
    change_vv_mean: Optional[float] = Field(None, description="VV change from baseline (dB)")
    change_vh_mean: Optional[float] = Field(None, description="VH change from baseline (dB)")
    baseline_year: Optional[int] = Field(None, description="Year used for dry-season baseline")
    image_count: int = Field(default=0, description="Number of SAR images used")
    status: str = Field(default="success", description="Status of the analysis")
    message: Optional[str] = None


@router.post("/sar-flood-extent", response_model=SARFloodExtentResponse)
async def get_sar_flood_extent(request: SARFloodExtentRequest):
    """
    Get SAR-based flood extent analysis for a region.

    Uses Sentinel-1 SAR data to detect flooded areas.
    SAR can penetrate clouds, making it ideal for monsoon flood detection.

    Detection is based on:
    - VV backscatter < -15 dB (water appears dark)
    - VH backscatter < -22 dB
    - Change from dry-season baseline > 3 dB decrease
    """
    # Validate bounds
    if not (-90 <= request.lat_min < request.lat_max <= 90):
        raise HTTPException(status_code=400, detail="Invalid latitude bounds")
    if not (-180 <= request.lng_min < request.lng_max <= 180):
        raise HTTPException(status_code=400, detail="Invalid longitude bounds")

    # Limit area to prevent abuse (max ~100km x 100km)
    lat_range = request.lat_max - request.lat_min
    lng_range = request.lng_max - request.lng_min
    if lat_range > 1.0 or lng_range > 1.0:
        raise HTTPException(status_code=400, detail="Region too large. Max 1 degree (~100km) per dimension.")

    try:
        from ..data.sentinel1_sar import Sentinel1SARFetcher

        fetcher = Sentinel1SARFetcher()

        bounds = (
            request.lat_min,
            request.lng_min,
            request.lat_max,
            request.lng_max,
        )

        result = fetcher.get_flood_extent(
            bounds=bounds,
            flood_date=datetime.now(),
            lookback_days=request.lookback_days,
        )

        return SARFloodExtentResponse(
            bounds={
                "lat_min": request.lat_min,
                "lng_min": request.lng_min,
                "lat_max": request.lat_max,
                "lng_max": request.lng_max,
            },
            flood_fraction=result.get("flood_fraction", 0.0),
            vv_mean=result.get("vv_mean"),
            vh_mean=result.get("vh_mean"),
            change_vv_mean=result.get("change_vv_mean"),
            change_vh_mean=result.get("change_vh_mean"),
            baseline_year=result.get("baseline_year"),
            image_count=result.get("image_count", 0),
            status="success",
        )

    except Exception as e:
        logger.error(f"SAR flood extent analysis failed: {e}")
        return SARFloodExtentResponse(
            bounds={
                "lat_min": request.lat_min,
                "lng_min": request.lng_min,
                "lat_max": request.lat_max,
                "lng_max": request.lng_max,
            },
            flood_fraction=0.0,
            image_count=0,
            status="error",
            message=str(e),
        )


@router.get("/sar-features/{hotspot_id}")
async def get_sar_features_for_hotspot(hotspot_id: int):
    """
    Get current SAR features for a specific hotspot.

    Returns SAR backscatter values useful for flood detection:
    - sar_vv_mean: VV polarization backscatter (dB)
    - sar_vh_mean: VH polarization backscatter (dB)
    - sar_vv_vh_ratio: VV/VH ratio (water indicator)
    - sar_change_magnitude: Change from dry baseline
    """
    global hotspots_data

    if not hotspots_data:
        raise HTTPException(status_code=503, detail="Hotspots data not loaded")

    # Find hotspot
    hotspot = None
    for h in hotspots_data:
        if h["id"] == hotspot_id:
            hotspot = h
            break

    if hotspot is None:
        raise HTTPException(status_code=404, detail=f"Hotspot {hotspot_id} not found")

    try:
        from ..data.sentinel1_sar import get_sar_features_at_point

        features = get_sar_features_at_point(
            lat=hotspot["lat"],
            lng=hotspot["lng"],
            reference_date=datetime.now(),
        )

        return {
            "hotspot_id": hotspot_id,
            "name": hotspot["name"],
            "lat": hotspot["lat"],
            "lng": hotspot["lng"],
            "sar_features": features,
            "interpretation": {
                "vv_threshold": -15.0,
                "vh_threshold": -22.0,
                "flood_likely": features.get("sar_vv_mean", 0) < -15 or features.get("sar_change_magnitude", 0) < -3,
            },
        }

    except Exception as e:
        logger.warning(f"SAR feature extraction failed for hotspot {hotspot_id}: {e}")
        return {
            "hotspot_id": hotspot_id,
            "name": hotspot["name"],
            "lat": hotspot["lat"],
            "lng": hotspot["lng"],
            "sar_features": {
                "sar_vv_mean": -10.0,
                "sar_vh_mean": -17.0,
                "sar_vv_vh_ratio": 7.0,
                "sar_change_magnitude": 0.0,
            },
            "status": "default_values",
            "error": str(e),
        }


def initialize_hotspots_router():
    """
    Initialize hotspots data and model.

    Called on startup to load:
    - Hotspots JSON data
    - Pre-computed ML predictions cache (fast lookup)
    - Trained XGBoost model (if available, for single-point queries)
    """
    global hotspots_data, hotspot_model, predictions_cache

    # Load hotspots data
    hotspots_file = Path(__file__).parent.parent.parent / "data" / "delhi_waterlogging_hotspots.json"

    if hotspots_file.exists():
        try:
            with open(hotspots_file) as f:
                data = json.load(f)
                hotspots_data = data["hotspots"]
            logger.info(f"Loaded {len(hotspots_data)} waterlogging hotspots")
        except Exception as e:
            logger.error(f"Failed to load hotspots: {e}")
            hotspots_data = []
    else:
        logger.warning(f"Hotspots file not found: {hotspots_file}")
        hotspots_data = []

    # Load pre-computed predictions cache (priority for fast API responses)
    cache_file = Path(__file__).parent.parent.parent / "data" / "hotspot_predictions_cache.json"

    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cache_data = json.load(f)
                predictions_cache = cache_data.get("predictions", {})
            logger.info(f"Loaded pre-computed predictions for {len(predictions_cache)} hotspots")
        except Exception as e:
            logger.warning(f"Failed to load predictions cache: {e}")
            predictions_cache = {}
    else:
        logger.info("No predictions cache found - will use severity-based fallback")
        predictions_cache = {}

    # Load trained model (if available, for single-point queries)
    model_path = Path(__file__).parent.parent.parent / "models" / "xgboost_hotspot"

    if model_path.exists():
        try:
            from ..models.xgboost_hotspot import load_trained_model
            hotspot_model = load_trained_model(model_path)
            logger.info("XGBoost hotspot model loaded")
        except Exception as e:
            logger.warning(f"Failed to load hotspot model: {e}")
            hotspot_model = None
    else:
        logger.info("No trained hotspot model found - using severity-based risk estimation")
        hotspot_model = None
