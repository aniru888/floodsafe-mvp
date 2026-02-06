"""
FastAPI endpoints for flood predictions.

IMPORTANT: The ensemble models (ConvLSTM, GNN, LightGBM) are NOT TRAINED.
Only the XGBoost Hotspot model is trained and working.
The /forecast endpoint will return fallback 0.1 probability for all predictions.
See CLAUDE.md @ml-predictions for details.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import numpy as np
import logging

from ..data.gee_client import gee_client
from ..core.config import settings, REGIONS

router = APIRouter()
logger = logging.getLogger(__name__)

# Global instances (loaded on startup by main.py)
# NOTE: Ensemble models are NOT used in production (not trained).
# XGBoost hotspot model and MobileNet are the only trained models.
ensemble_model: Optional[Any] = None  # Shelved - not trained
feature_extractor: Optional[Any] = None  # Optional - needs GEE
grid_predictions_cache: Optional[Dict] = None  # Pre-computed grid predictions


def load_grid_predictions_cache():
    """Load pre-computed grid predictions from cache file."""
    global grid_predictions_cache

    cache_paths = [
        Path(__file__).parent.parent.parent / "data" / "grid_predictions_cache.json",
        Path("/app/data/grid_predictions_cache.json"),
    ]

    for cache_path in cache_paths:
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    grid_predictions_cache = json.load(f)
                logger.info(f"Loaded grid predictions cache: {len(grid_predictions_cache.get('features', []))} points from {cache_path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to load grid cache from {cache_path}: {e}")

    logger.warning("No grid predictions cache found - /forecast-grid will use real-time computation")
    return False


class PredictionRequest(BaseModel):
    """Request for flood forecast."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    horizon_days: int = Field(default=7, ge=1, le=30, description="Forecast horizon")
    include_uncertainty: bool = Field(default=True, description="Include model contributions")


class PredictionResponse(BaseModel):
    """Response with flood forecast."""

    latitude: float
    longitude: float
    predictions: List[Dict]
    model_contributions: Optional[Dict[str, List[float]]] = None
    metadata: Dict


class RiskAssessmentRequest(BaseModel):
    """Request for static risk assessment."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=5.0, ge=0.1, le=50)


class RiskAssessmentResponse(BaseModel):
    """Response with risk assessment."""

    risk_level: str  # low, moderate, high, extreme
    risk_score: float  # 0-1
    factors: Dict[str, float]
    recommendations: List[str]


class GridPredictionRequest(BaseModel):
    """Request for grid-based flood predictions."""

    min_lat: float = Field(..., ge=-90, le=90, description="Minimum latitude")
    max_lat: float = Field(..., ge=-90, le=90, description="Maximum latitude")
    min_lng: float = Field(..., ge=-180, le=180, description="Minimum longitude")
    max_lng: float = Field(..., ge=-180, le=180, description="Maximum longitude")
    resolution_km: float = Field(default=1.0, ge=0.5, le=5.0, description="Grid resolution in km")
    horizon_days: int = Field(default=0, ge=0, le=7, description="Days ahead (0=today)")


class GridPredictionResponse(BaseModel):
    """GeoJSON FeatureCollection response with flood predictions."""

    type: str = "FeatureCollection"
    features: List[Dict]
    metadata: Dict


@router.post("/forecast", response_model=PredictionResponse)
async def get_flood_forecast(request: PredictionRequest):
    """
    Get flood probability forecast for a location.

    Returns daily flood probabilities for the specified horizon.
    """
    global ensemble_model, feature_extractor

    if ensemble_model is None or not ensemble_model.is_trained:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service is initializing.",
        )

    if feature_extractor is None:
        raise HTTPException(
            status_code=503,
            detail="Feature extractor not available.",
        )

    try:
        # Extract features for current date
        reference_date = datetime.now()
        features = feature_extractor.extract_for_point(
            request.latitude,
            request.longitude,
            reference_date,
            radius_km=5.0,
        )

        # Prepare input (simplified - in production would use sequence data)
        # Ensure proper dtype for PyTorch compatibility
        combined = np.array(features["combined"], dtype=np.float32)
        combined = np.nan_to_num(combined, nan=0.0, posinf=0.0, neginf=0.0)

        # For LSTM: Create a 30-day sequence by tiling the current feature vector
        # In production, this would be actual historical data
        # NOTE: Ensemble models are NOT TRAINED - this will fall back to 0.1 probability
        seq_length = 30
        X_seq = np.tile(combined.reshape(1, 1, -1), (1, seq_length, 1))  # Shape: (1, 30, 37)

        # Get predictions directly from LSTM (most reliable trained model)
        # Note: This is a simplified example. Real implementation would use ensemble properly.
        probabilities = None
        for model in ensemble_model.models:
            if "LSTM" in model.model_name and model.is_trained:
                try:
                    probabilities = model.predict_proba(X_seq)
                    logger.info(f"LSTM prediction successful: {probabilities}")
                    break
                except Exception as e:
                    logger.warning(f"LSTM prediction failed: {e}")

        # Fallback to ensemble (may not work with current data format)
        if probabilities is None:
            X = combined.reshape(1, -1)
            try:
                probabilities = ensemble_model.predict_proba(X)
            except Exception as e:
                logger.warning(f"Ensemble fallback failed: {e}")
                # Return default low risk if all predictions fail
                probabilities = np.array([[0.1]])

        # Build response
        predictions = []
        base_date = datetime.now().date()

        # For now, return constant probability (would be time-series in production)
        for i in range(request.horizon_days):
            pred_date = base_date + timedelta(days=i + 1)
            prob = float(probabilities[0]) if len(probabilities) > 0 else 0.5

            predictions.append({
                "date": pred_date.isoformat(),
                "flood_probability": prob,
                "risk_level": _prob_to_risk_level(prob),
            })

        # Get model contributions if requested
        contributions = None
        if request.include_uncertainty:
            X = combined.reshape(1, -1)
            raw_contributions = ensemble_model.get_model_contributions(X)
            contributions = {
                name: preds.flatten().tolist()
                for name, preds in raw_contributions.items()
            }

        return PredictionResponse(
            latitude=request.latitude,
            longitude=request.longitude,
            predictions=predictions,
            model_contributions=contributions,
            metadata={
                "model": ensemble_model.model_name,
                "generated_at": datetime.now().isoformat(),
                "feature_dim": len(features["combined"]),
                "data_sources": ["AlphaEarth", "CHIRPS", "SRTM", "ERA5-Land/GloFAS"],
            },
        )

    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-assessment", response_model=RiskAssessmentResponse)
async def get_risk_assessment(request: RiskAssessmentRequest):
    """
    Get comprehensive flood risk assessment for a location.

    Combines static terrain factors with dynamic predictions.
    """
    try:
        from ..data.dem_fetcher import DEMFetcher
        from ..data.surface_water import SurfaceWaterFetcher
        from ..data.landcover import LandcoverFetcher

        dem_fetcher = DEMFetcher()
        water_fetcher = SurfaceWaterFetcher()
        land_fetcher = LandcoverFetcher()

        # Create bounds from point + radius
        lat_delta = request.radius_km / 111.0
        lng_delta = request.radius_km / (111.0 * np.cos(np.radians(request.latitude)))

        bounds = (
            request.latitude - lat_delta,
            request.longitude - lng_delta,
            request.latitude + lat_delta,
            request.longitude + lng_delta,
        )

        # Get terrain data
        dem_data = dem_fetcher.get_terrain_features(bounds)
        water_data = water_fetcher.get_water_features(bounds)
        land_data = land_fetcher.get_landcover_features(bounds)

        # Calculate risk factors
        factors = {
            "elevation_factor": _elevation_risk(dem_data["elevation_mean"]),
            "slope_factor": _slope_risk(dem_data["slope_mean"]),
            "water_history_factor": water_data["water_occurrence"] / 100.0,
            "built_area_factor": land_data["built_up_pct"] / 100.0,
            "drainage_factor": 1 - (land_data["permeable_pct"] / 100.0),
        }

        # Calculate overall risk score
        weights = {
            "elevation_factor": 0.25,
            "slope_factor": 0.15,
            "water_history_factor": 0.30,
            "built_area_factor": 0.15,
            "drainage_factor": 0.15,
        }

        risk_score = sum(factors[k] * weights[k] for k in factors)
        risk_level = _score_to_risk_level(risk_score)

        # Generate recommendations
        recommendations = _generate_recommendations(factors, risk_level)

        return RiskAssessmentResponse(
            risk_level=risk_level,
            risk_score=risk_score,
            factors=factors,
            recommendations=recommendations,
        )

    except Exception as e:
        logger.error(f"Risk assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Check ML service health."""
    global ensemble_model

    model_status = "not_loaded"
    if ensemble_model is not None:
        if ensemble_model.is_trained:
            model_status = "trained"
        else:
            model_status = "loaded_not_trained"

    return {
        "status": "healthy",
        "model_status": model_status,
        "gee_initialized": gee_client._initialized,
        "service": settings.PROJECT_NAME,
    }


@router.get("/models/info")
async def get_model_info():
    """Get information about loaded models."""
    global ensemble_model

    if ensemble_model is None:
        return {"error": "No model loaded"}

    return ensemble_model.get_model_info()


@router.post("/forecast-grid", response_model=GridPredictionResponse)
async def get_flood_forecast_grid(request: GridPredictionRequest):
    """
    Generate flood predictions for a geographic grid.

    Returns GeoJSON FeatureCollection with:
    - Point features at grid intersections
    - Properties: { flood_probability, risk_level }

    This endpoint is optimized for heatmap visualization.
    Uses pre-computed cache for fast response (< 100ms).
    """
    global grid_predictions_cache

    # Try to use pre-computed cache (FAST PATH)
    if grid_predictions_cache is not None:
        try:
            cached_features = grid_predictions_cache.get("features", [])
            cached_metadata = grid_predictions_cache.get("metadata", {})

            # Filter features within requested bounds
            filtered_features = []
            for feature in cached_features:
                coords = feature["geometry"]["coordinates"]
                lng, lat = coords[0], coords[1]

                if (request.min_lat <= lat <= request.max_lat and
                    request.min_lng <= lng <= request.max_lng):
                    filtered_features.append(feature)

            logger.info(f"Serving {len(filtered_features)} points from cache (total: {len(cached_features)})")

            return GridPredictionResponse(
                type="FeatureCollection",
                features=filtered_features,
                metadata={
                    "generated_at": cached_metadata.get("generated_at", datetime.now().isoformat()),
                    "model": cached_metadata.get("model", "xgboost_hotspot_v1"),
                    "grid_points": len(filtered_features),
                    "resolution_km": cached_metadata.get("resolution_km", request.resolution_km),
                    "horizon_days": request.horizon_days,
                    "bounds": {
                        "min_lat": request.min_lat,
                        "max_lat": request.max_lat,
                        "min_lng": request.min_lng,
                        "max_lng": request.max_lng,
                    },
                    "source": "pre_computed_cache",
                },
            )
        except Exception as e:
            logger.warning(f"Cache lookup failed, falling back to computation: {e}")

    # SLOW PATH: Real-time computation (fallback if no cache)
    global ensemble_model, feature_extractor

    if ensemble_model is None or not ensemble_model.is_trained:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded and no cache available. Service is initializing.",
        )

    if feature_extractor is None:
        raise HTTPException(
            status_code=503,
            detail="Feature extractor not available and no cache.",
        )

    try:
        # Generate grid points
        grid_points = _generate_grid_points(
            min_lat=request.min_lat,
            max_lat=request.max_lat,
            min_lng=request.min_lng,
            max_lng=request.max_lng,
            resolution_km=request.resolution_km,
        )

        logger.info(f"Processing {len(grid_points)} grid points (SLOW - no cache)...")

        # Get current date (or future date based on horizon)
        reference_date = datetime.now() + timedelta(days=request.horizon_days)

        # Process grid points in batches
        features = []
        batch_size = 10  # Process 10 points at a time to avoid memory issues

        for i in range(0, len(grid_points), batch_size):
            batch = grid_points[i : i + batch_size]

            for lat, lng in batch:
                try:
                    # Extract features for this point
                    point_features = feature_extractor.extract_for_point(
                        lat=lat,
                        lng=lng,
                        reference_date=reference_date,
                        radius_km=request.resolution_km,  # Use resolution as buffer
                    )

                    # Prepare input for LSTM
                    combined = np.array(point_features["combined"], dtype=np.float32)
                    combined = np.nan_to_num(combined, nan=0.0, posinf=0.0, neginf=0.0)

                    # Create sequence for LSTM
                    seq_length = 30
                    X_seq = np.tile(combined.reshape(1, 1, -1), (1, seq_length, 1))

                    # Get prediction from LSTM
                    prob = 0.1  # Default low probability
                    for model in ensemble_model.models:
                        if "LSTM" in model.model_name and model.is_trained:
                            try:
                                prob_array = model.predict_proba(X_seq)
                                prob = float(prob_array[0]) if len(prob_array) > 0 else 0.1
                                break
                            except Exception as e:
                                logger.warning(f"LSTM prediction failed for point ({lat}, {lng}): {e}")

                    # Clamp probability to valid range
                    prob = max(0.0, min(1.0, prob))

                    # Create GeoJSON feature
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lng, lat],  # GeoJSON uses [lng, lat]
                        },
                        "properties": {
                            "flood_probability": round(prob, 3),
                            "risk_level": _prob_to_risk_level(prob),
                        },
                    })

                except Exception as e:
                    logger.warning(f"Failed to process point ({lat}, {lng}): {e}")
                    # Add point with default low risk
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lng, lat],
                        },
                        "properties": {
                            "flood_probability": 0.1,
                            "risk_level": "low",
                        },
                    })

        logger.info(f"Grid prediction complete: {len(features)} points processed")

        return GridPredictionResponse(
            type="FeatureCollection",
            features=features,
            metadata={
                "generated_at": datetime.now().isoformat(),
                "model": ensemble_model.model_name,
                "grid_points": len(features),
                "resolution_km": request.resolution_km,
                "horizon_days": request.horizon_days,
                "bounds": {
                    "min_lat": request.min_lat,
                    "max_lat": request.max_lat,
                    "min_lng": request.min_lng,
                    "max_lng": request.max_lng,
                },
                "source": "real_time_computation",
            },
        )

    except Exception as e:
        logger.error(f"Grid prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _generate_grid_points(
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    resolution_km: float,
) -> List[tuple]:
    """
    Generate a grid of lat/lng points within the given bounds.

    Args:
        min_lat, max_lat: Latitude bounds
        min_lng, max_lng: Longitude bounds
        resolution_km: Distance between points in km

    Returns:
        List of (lat, lng) tuples
    """
    # Approximate conversion: 1 degree lat ≈ 111 km
    lat_step = resolution_km / 111.0
    # Longitude step varies by latitude - use center latitude
    center_lat = (min_lat + max_lat) / 2
    lng_step = resolution_km / (111.0 * np.cos(np.radians(center_lat)))

    points = []
    lat = min_lat
    while lat <= max_lat:
        lng = min_lng
        while lng <= max_lng:
            points.append((lat, lng))
            lng += lng_step
        lat += lat_step

    # Limit to reasonable number of points (max 200 for performance)
    if len(points) > 200:
        # Sample evenly to reduce to 200 points
        step = len(points) // 200
        points = points[::step][:200]

    return points


# Helper functions


def _prob_to_risk_level(prob: float) -> str:
    """Convert probability to risk level."""
    if prob < 0.25:
        return "low"
    elif prob < 0.50:
        return "moderate"
    elif prob < 0.75:
        return "high"
    else:
        return "extreme"


def _score_to_risk_level(score: float) -> str:
    """Convert risk score to level."""
    return _prob_to_risk_level(score)


def _elevation_risk(elevation: float) -> float:
    """Calculate risk from elevation. Lower elevation = higher risk."""
    # Delhi average ~216m
    if elevation < 200:
        return 0.8
    elif elevation < 220:
        return 0.5
    elif elevation < 250:
        return 0.3
    else:
        return 0.1


def _slope_risk(slope: float) -> float:
    """Calculate risk from slope. Flat areas = higher risk."""
    if slope < 1:
        return 0.9
    elif slope < 3:
        return 0.6
    elif slope < 5:
        return 0.3
    else:
        return 0.1


def _generate_recommendations(factors: Dict, risk_level: str) -> List[str]:
    """Generate safety recommendations based on risk factors."""
    recommendations = []

    if risk_level in ["high", "extreme"]:
        recommendations.append("Consider flood insurance for this area")
        recommendations.append("Keep emergency supplies ready during monsoon season")
        recommendations.append("Have an evacuation plan")

    if factors["water_history_factor"] > 0.3:
        recommendations.append(
            "Area has significant historical flooding - avoid basement storage"
        )
        recommendations.append("Install sump pumps and water sensors")

    if factors["drainage_factor"] > 0.7:
        recommendations.append(
            "Poor natural drainage - ensure proper storm water infrastructure"
        )

    if factors["built_area_factor"] > 0.7:
        recommendations.append(
            "High urbanization increases runoff - check local drain capacity"
        )

    if factors["elevation_factor"] > 0.6:
        recommendations.append(
            "Low-lying area - monitor river levels during heavy rainfall"
        )

    if not recommendations:
        recommendations.append("Standard monsoon precautions advised")
        recommendations.append("Stay informed about weather forecasts")

    return recommendations
