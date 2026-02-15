"""
Backend API for waterlogging hotspot predictions.

Uses embedded ML models (XGBoost + FHI) for real-time risk calculation.
Falls back to static data when ML is disabled.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging
import json

from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_CITIES = {"delhi", "bangalore", "yogyakarta", "singapore"}

# Per-city service instances
_hotspots_services: Dict[str, Any] = {}


def _get_hotspots_service(city: str = "delhi"):
    """Get or create the hotspots service instance for a city."""
    if city not in _hotspots_services:
        from ..domain.ml.hotspots_service import HotspotsService
        service = HotspotsService(city=city)
        service.initialize()
        _hotspots_services[city] = service

    return _hotspots_services[city]


def _detect_city_from_coords(lat: float, lng: float) -> str:
    """Auto-detect city from coordinates using FHI calculator bounds."""
    from ..domain.ml.fhi_calculator import FHICalculator
    calc = FHICalculator()
    return calc._detect_city(lat, lng)


# Path to static hotspot data (for when ML is completely disabled)
def _get_static_hotspots_path(city: str = "delhi") -> Optional[Path]:
    """Get path to static hotspots data file for a city."""
    backend_data = Path(__file__).resolve().parent.parent.parent / "data" / f"{city}_waterlogging_hotspots.json"
    if backend_data.exists():
        return backend_data

    return None


def _load_static_hotspots(city: str = "delhi") -> Dict[str, Any]:
    """
    Load static hotspot data when ML is completely disabled.
    Returns GeoJSON FeatureCollection with baseline risk levels.
    """
    data_path = _get_static_hotspots_path(city)
    if not data_path:
        raise HTTPException(
            status_code=503,
            detail="Hotspot data file not found. Deploy with data files.",
        )

    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading static hotspots: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading hotspot data: {e}")

    # Handle both formats: raw array or {metadata, hotspots} object
    if isinstance(raw_data, dict) and "hotspots" in raw_data:
        hotspots_list = raw_data["hotspots"]
    elif isinstance(raw_data, list):
        hotspots_list = raw_data
    else:
        logger.error(f"Unexpected hotspots data format: {type(raw_data)}")
        raise HTTPException(status_code=500, detail="Invalid hotspot data format")

    # Convert to GeoJSON FeatureCollection format
    features = []
    for hotspot in hotspots_list:
        # Support both property name conventions
        severity = hotspot.get("severity_history") or hotspot.get("historical_severity", "moderate")
        severity = severity.lower() if severity else "moderate"

        # Map severity to risk levels
        if severity in ["high", "severe"]:
            risk_prob = 0.6
            risk_level = "high"
            risk_color = "#f97316"  # orange
        elif severity in ["critical", "extreme"]:
            risk_prob = 0.8
            risk_level = "extreme"
            risk_color = "#ef4444"  # red
        else:  # moderate, low
            risk_prob = 0.4
            risk_level = "moderate"
            risk_color = "#eab308"  # yellow

        # Support both coordinate conventions (lat/lng vs latitude/longitude)
        lng = hotspot.get("lng") or hotspot.get("longitude")
        lat = hotspot.get("lat") or hotspot.get("latitude")

        if lng is None or lat is None:
            logger.warning(f"Skipping hotspot without coordinates: {hotspot.get('id')}")
            continue

        # Determine source and verification status
        source = hotspot.get("source", "mcd_reports")
        verified = source == "mcd_reports"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "properties": {
                "id": hotspot.get("id", 0),
                "name": hotspot.get("name", "Unknown"),
                "zone": hotspot.get("zone", "Unknown"),
                "description": hotspot.get("description", ""),
                "risk_probability": risk_prob,
                "risk_level": risk_level,
                "risk_color": risk_color,
                "fhi": None,
                "fhi_color": None,
                "historical_severity": severity,
                "elevation_m": hotspot.get("elevation_m"),
                "static_data": True,
                "source": source,
                "verified": verified,
                "osm_id": hotspot.get("osm_id"),
            }
        }
        features.append(feature)

    logger.info(f"Loaded {len(features)} static hotspots from {data_path}")

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total_hotspots": len(features),
            "source": "static",
            "ml_enabled": False,
            "fhi_available": False,
            "generated_at": datetime.now().isoformat(),
            "note": "Live FHI calculations unavailable. Showing baseline risk from historical data."
        }
    }


@router.get("/all")
async def get_all_hotspots(
    city: str = Query("delhi", description="City: delhi, bangalore, yogyakarta"),
    include_rainfall: bool = Query(True, description="Include current rainfall factor (via FHI)"),
    test_fhi_override: str = Query(None, description="Override FHI for testing: 'high', 'extreme', or 'mixed'"),
):
    """
    Get all waterlogging hotspots for a city with current risk levels.

    Returns GeoJSON FeatureCollection with:
    - Point features for each hotspot
    - Properties: id, name, zone, risk_probability, risk_level, risk_color, fhi

    Risk is dynamically adjusted based on current weather when ML is enabled.
    Falls back to static baseline data when ML is disabled.
    """
    if city not in SUPPORTED_CITIES:
        raise HTTPException(status_code=400, detail=f"Unsupported city: {city}. Supported: {', '.join(SUPPORTED_CITIES)}")

    # If ML is completely disabled, return static data
    if not settings.ML_ENABLED:
        logger.info(f"ML disabled, serving static hotspot data for {city}")
        return _load_static_hotspots(city)

    try:
        # Use embedded ML service
        service = _get_hotspots_service(city)
        result = await service.get_all_hotspots(
            include_fhi=include_rainfall,  # FHI uses weather data including rainfall
            test_fhi_override=test_fhi_override,
        )

        feature_count = len(result.get("features", []))
        logger.info(f"Hotspots returned: {feature_count} {city} locations" +
                   (f" (TEST MODE: {test_fhi_override})" if test_fhi_override else ""))

        return result

    except RuntimeError as e:
        logger.error(f"Hotspots service error for {city}: {e}")
        # Fallback to static data on service error
        logger.info(f"Falling back to static hotspot data for {city}")
        return _load_static_hotspots(city)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hotspot/{hotspot_id}")
async def get_hotspot_risk(
    hotspot_id: int,
    city: str = Query("delhi", description="City: delhi, bangalore, yogyakarta"),
    include_fhi: bool = Query(True, description="Include FHI calculation"),
):
    """
    Get risk details for a specific hotspot by ID.

    Args:
        hotspot_id: Hotspot identifier
        city: City key (IDs overlap between cities)
        include_fhi: Include Flood Hazard Index calculation

    Returns:
        Hotspot details with current risk assessment
    """
    if not settings.ML_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="ML is not enabled",
        )

    try:
        service = _get_hotspots_service(city)
        result = await service.get_hotspot_by_id(hotspot_id, include_fhi=include_fhi)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Hotspot {hotspot_id} not found",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting hotspot {hotspot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-at-point")
async def get_risk_at_point(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
):
    """
    Get flood risk for any point in a supported city.

    Uses proximity to known hotspots and current weather.
    Auto-detects city from coordinates.

    Args:
        lat: Latitude (WGS84)
        lng: Longitude (WGS84)

    Returns:
        Risk assessment for the point
    """
    if not settings.ML_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="ML is not enabled",
        )

    try:
        detected_city = _detect_city_from_coords(lat, lng)
        service = _get_hotspots_service(detected_city)

        # Find nearest hotspot
        min_distance = float("inf")
        nearest_hotspot = None

        for h in service.hotspots_data:
            h_lat = h.get("lat") or h.get("latitude")
            h_lng = h.get("lng") or h.get("longitude")
            if h_lat is None or h_lng is None:
                continue

            dist = service.haversine_distance(lat, lng, h_lat, h_lng)
            if dist < min_distance:
                min_distance = dist
                nearest_hotspot = h

        # Calculate risk based on proximity
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

        # Determine risk level and color
        from ..domain.ml.xgboost_hotspot import get_risk_level
        risk_level, risk_color = get_risk_level(base_risk)

        return {
            "latitude": lat,
            "longitude": lng,
            "risk_probability": round(base_risk, 3),
            "risk_level": risk_level,
            "risk_color": risk_color,
            "nearest_hotspot": nearest_hotspot.get("name") if nearest_hotspot else None,
            "distance_to_hotspot_km": round(min_distance, 2) if nearest_hotspot else None,
        }

    except Exception as e:
        logger.error(f"Error calculating risk at point: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-summary")
async def get_risk_summary(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    language: str = Query("en", description="Language: 'en' or 'hi'"),
):
    """
    Get AI-generated flood risk summary for a location.

    Uses Meta Llama API to generate a natural language risk narrative
    from structured FHI data. Returns None if Llama is disabled.

    Args:
        lat: Latitude
        lng: Longitude
        language: Response language ('en' or 'hi')

    Returns:
        JSON with risk_summary string and metadata
    """
    from ..domain.services.llama_service import generate_risk_summary, is_llama_enabled

    if not is_llama_enabled():
        return {"risk_summary": None, "enabled": False}

    # Get risk data from the risk-at-point logic (auto-detect city from coords)
    risk_data = {"risk_level": "low", "fhi": 0.0, "is_hotspot": False}
    if settings.ML_ENABLED:
        try:
            detected_city = _detect_city_from_coords(lat, lng)
            service = _get_hotspots_service(detected_city)
            min_distance = float("inf")
            nearest = None
            for h in service.hotspots_data:
                h_lat = h.get("lat") or h.get("latitude")
                h_lng = h.get("lng") or h.get("longitude")
                if h_lat is None or h_lng is None:
                    continue
                dist = service.haversine_distance(lat, lng, h_lat, h_lng)
                if dist < min_distance:
                    min_distance = dist
                    nearest = h
            if min_distance < 0.5:
                risk_data["fhi"] = 0.7
            elif min_distance < 1.0:
                risk_data["fhi"] = 0.5
            elif min_distance < 2.0:
                risk_data["fhi"] = 0.35
            risk_data["is_hotspot"] = min_distance < 1.0
            if risk_data["fhi"] > 0.6:
                risk_data["risk_level"] = "high"
            elif risk_data["fhi"] > 0.3:
                risk_data["risk_level"] = "moderate"
        except Exception:
            pass

    location_name = f"({lat:.4f}, {lng:.4f})"
    summary = await generate_risk_summary(
        latitude=lat,
        longitude=lng,
        location_name=location_name,
        risk_level=risk_data["risk_level"],
        fhi_score=risk_data["fhi"],
        is_hotspot=risk_data["is_hotspot"],
        language=language,
    )

    return {
        "risk_summary": summary,
        "enabled": True,
        "risk_level": risk_data["risk_level"],
        "fhi_score": risk_data["fhi"],
        "language": language,
    }


@router.get("/health")
async def hotspots_health():
    """Check hotspots service health."""
    if not settings.ML_ENABLED:
        # Check if static data is available
        static_path = _get_static_hotspots_path()
        return {
            "status": "static_fallback",
            "ml_enabled": False,
            "static_data_available": static_path is not None,
            "static_data_path": str(static_path) if static_path else None,
            "note": "Serving baseline hotspot data. Live FHI disabled.",
        }

    try:
        service = _get_hotspots_service()
        health = service.get_health_status()

        return {
            "status": "healthy" if health["hotspots_loaded"] else "degraded",
            "ml_enabled": True,
            "hotspots_loaded": health["hotspots_loaded"],
            "total_hotspots": health["total_hotspots"],
            "model_trained": health["model_trained"],
            "predictions_cached": health["predictions_cached"],
        }

    except Exception as e:
        return {
            "status": "error",
            "ml_enabled": True,
            "error": str(e),
        }
