"""
Historical floods API endpoint.

Serves GeoJSON data from IFI-Impacts dataset for FloodAtlas visualization.
"""
import json
import os
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Path to processed historical floods data
# Priority: 1) ML_SERVICE_DATA_DIR env var, 2) backend/data/, 3) ml-service/data/
def _get_data_dir() -> Path:
    """Get data directory with fallback options for different deployment environments."""
    # Check environment variable first
    env_dir = os.environ.get("ML_SERVICE_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    # Check backend's own data directory (for Railway/production)
    backend_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    if backend_data_dir.exists() and (backend_data_dir / "delhi_historical_floods.json").exists():
        return backend_data_dir

    # Fallback to ml-service data directory (for local development)
    ml_service_data_dir = Path(__file__).resolve().parent.parent.parent.parent / "ml-service" / "data"
    return ml_service_data_dir


DATA_DIR = _get_data_dir()

# Security: Validate city parameter pattern (alphanumeric + spaces only, max 50 chars)
CITY_PATTERN = re.compile(r'^[a-zA-Z\s]{1,50}$')


class HistoricalFloodProperties(BaseModel):
    """Properties of a historical flood event."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    date: str
    districts: str
    severity: str  # minor, moderate, severe
    source: str  # IFI-Impacts or user_report
    year: int
    fatalities: int
    injured: int
    displaced: int
    duration_days: Optional[int] = None
    main_cause: Optional[str] = None
    area_affected: Optional[str] = None


class HistoricalFloodFeature(BaseModel):
    """GeoJSON Feature for a flood event."""
    model_config = ConfigDict(from_attributes=True)

    type: str = "Feature"
    geometry: dict
    properties: dict


class HistoricalFloodsResponse(BaseModel):
    """GeoJSON FeatureCollection response."""
    model_config = ConfigDict(from_attributes=True)

    type: str = "FeatureCollection"
    features: list
    metadata: dict


@router.get("", response_model=HistoricalFloodsResponse)
async def get_historical_floods(
    city: str = Query("delhi", description="City to get historical floods for"),
    min_year: Optional[int] = Query(None, description="Minimum year filter"),
    max_year: Optional[int] = Query(None, description="Maximum year filter"),
    severity: Optional[str] = Query(None, description="Filter by severity: minor, moderate, severe")
):
    """
    Get historical flood events for a city.

    Returns GeoJSON FeatureCollection with flood events from IFI-Impacts dataset.
    Currently only Delhi NCR is supported.

    Args:
        city: City name (currently only 'delhi' supported)
        min_year: Filter events from this year onwards
        max_year: Filter events up to this year
        severity: Filter by severity level (minor, moderate, severe)

    Returns:
        GeoJSON FeatureCollection with flood events and metadata
    """
    # Validate and normalize city name
    city = city.lower().strip()

    # Security: Validate city parameter format
    if not CITY_PATTERN.match(city):
        raise HTTPException(
            status_code=400,
            detail="Invalid city parameter. Use only letters and spaces (max 50 characters)."
        )

    # Currently Delhi has historical data; other cities return empty gracefully
    if city not in ["delhi", "delhi ncr", "new delhi"]:
        logger.info(f"Historical floods requested for unsupported city: {city}")
        return HistoricalFloodsResponse(
            type="FeatureCollection",
            features=[],
            metadata={
                "source": "India Flood Inventory (IFI-Impacts)",
                "coverage": "1967-2023",
                "region": city,
                "total_events": 0,
                "message": f"Historical flood data not yet available for {city}. Coming soon!",
                "generated_at": datetime.now().isoformat()
            }
        )

    # Load Delhi historical floods
    floods_file = DATA_DIR / "delhi_historical_floods.json"

    if not floods_file.exists():
        logger.error(f"Historical floods data file not found: {floods_file}")
        raise HTTPException(
            status_code=503,
            detail="Historical floods data not yet generated. Run ml-service preprocessing scripts first."
        )

    try:
        with open(floods_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing historical floods JSON: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing historical floods data: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error reading historical floods file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reading historical floods data: {str(e)}"
        )

    features = data.get("features", [])

    # Apply filters
    if min_year is not None:
        features = [
            f for f in features
            if f.get("properties", {}).get("year") and f["properties"]["year"] >= min_year
        ]
        logger.info(f"Filtered by min_year={min_year}: {len(features)} events")

    if max_year is not None:
        features = [
            f for f in features
            if f.get("properties", {}).get("year") and f["properties"]["year"] <= max_year
        ]
        logger.info(f"Filtered by max_year={max_year}: {len(features)} events")

    if severity is not None:
        severity = severity.lower()
        features = [
            f for f in features
            if f.get("properties", {}).get("severity", "").lower() == severity
        ]
        logger.info(f"Filtered by severity={severity}: {len(features)} events")

    # Update metadata
    metadata = data.get("metadata", {})
    metadata["total_events"] = len(features)
    metadata["generated_at"] = datetime.now().isoformat()

    if min_year or max_year or severity:
        metadata["filters"] = {}
        if min_year:
            metadata["filters"]["min_year"] = min_year
        if max_year:
            metadata["filters"]["max_year"] = max_year
        if severity:
            metadata["filters"]["severity"] = severity

    logger.info(f"Returning {len(features)} historical flood events for Delhi")

    return HistoricalFloodsResponse(
        type="FeatureCollection",
        features=features,
        metadata=metadata
    )


@router.get("/stats")
async def get_historical_floods_stats(
    city: str = Query("delhi", description="City to get stats for")
):
    """
    Get statistics about historical floods for a city.

    Provides aggregated statistics including year range, severity breakdown,
    casualties, and affected districts.

    Args:
        city: City name (currently only 'delhi' supported)

    Returns:
        Dictionary with statistics about historical floods
    """
    city = city.lower().strip()

    # Security: Validate city parameter format
    if not CITY_PATTERN.match(city):
        raise HTTPException(
            status_code=400,
            detail="Invalid city parameter. Use only letters and spaces (max 50 characters)."
        )

    if city not in ["delhi", "delhi ncr", "new delhi"]:
        logger.info(f"Historical floods stats requested for unsupported city: {city}")
        return {
            "city": city,
            "available": False,
            "message": f"Historical flood data not yet available for {city}"
        }

    floods_file = DATA_DIR / "delhi_historical_floods.json"

    if not floods_file.exists():
        logger.error(f"Historical floods data file not found: {floods_file}")
        raise HTTPException(
            status_code=503,
            detail="Historical floods data not yet generated"
        )

    try:
        with open(floods_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading historical floods file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reading historical floods data: {str(e)}"
        )

    features = data.get("features", [])

    # Calculate statistics
    years = [f["properties"].get("year") for f in features if f["properties"].get("year")]
    severities = [f["properties"].get("severity", "unknown") for f in features]

    total_fatalities = sum(
        f["properties"].get("fatalities", 0) or 0
        for f in features
    )
    total_injured = sum(
        f["properties"].get("injured", 0) or 0
        for f in features
    )
    total_displaced = sum(
        f["properties"].get("displaced", 0) or 0
        for f in features
    )

    # Extract unique districts (handling the comma-separated string)
    all_districts = set()
    for f in features:
        districts_str = f["properties"].get("districts", "")
        if districts_str and districts_str != "nan":
            # Split by comma and clean up
            districts = [d.strip() for d in districts_str.split(",") if d.strip()]
            all_districts.update(districts)

    logger.info(f"Calculated stats for {len(features)} historical flood events")

    return {
        "city": "Delhi NCR",
        "available": True,
        "total_events": len(features),
        "year_range": {
            "min": min(years) if years else None,
            "max": max(years) if years else None
        },
        "severity_breakdown": {
            "minor": severities.count("minor"),
            "moderate": severities.count("moderate"),
            "severe": severities.count("severe"),
            "unknown": severities.count("unknown")
        },
        "casualties": {
            "total_fatalities": total_fatalities,
            "total_injured": total_injured,
            "total_displaced": total_displaced
        },
        "districts_affected_count": len(all_districts),
        "source": "India Flood Inventory (IFI-Impacts)",
        "metadata": data.get("metadata", {})
    }


@router.get("/health")
async def historical_floods_health():
    """Health check endpoint for historical floods service."""
    floods_file = DATA_DIR / "delhi_historical_floods.json"

    return {
        "status": "ok",
        "service": "historical-floods",
        "data_available": floods_file.exists(),
        "supported_cities": ["delhi", "delhi ncr", "new delhi"],
        "data_path": str(floods_file)
    }
