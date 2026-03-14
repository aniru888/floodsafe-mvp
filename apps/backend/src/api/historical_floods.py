"""
Historical floods API endpoint.

Serves GeoJSON data from IFI-Impacts dataset for FloodAtlas visualization.
Also exposes Groundsource episode and cluster data from the database.
"""
import json
import os
import re
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, String
from geoalchemy2 import WKTElement
from geoalchemy2.types import Geography
from datetime import datetime
import logging

from ..infrastructure.database import get_db
from ..infrastructure import models

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
        "supported_cities": ["delhi", "delhi ncr", "new delhi", "singapore", "indore"],
        "data_path": str(floods_file)
    }


# ============================================================================
# Groundsource response models
# ============================================================================

class GroundsourceEpisodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    city: str
    latitude: float
    longitude: float
    area_km2: Optional[float] = None
    date_start: str
    date_end: Optional[str] = None
    article_count: int = 1


class GroundsourceClusterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    city: str
    latitude: float
    longitude: float
    episode_count: int
    overlap_status: str = "UNKNOWN"
    nearest_hotspot_name: Optional[str] = None
    nearest_hotspot_distance_m: Optional[float] = None
    confidence: str = "medium"
    infra_signal: Optional[str] = None


class HistoricalStatsResponse(BaseModel):
    city: str
    total_episodes: int
    total_clusters: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    confirmed_clusters: int = 0
    missed_clusters: int = 0


# ============================================================================
# Helper: extract lat/lng from a HistoricalFloodEpisode or GroundsourceCluster
# without triggering hybrid_property session lookups on detached objects.
# We use ST_X / ST_Y directly in the query instead.
# ============================================================================

def _episode_to_response(row) -> GroundsourceEpisodeResponse:
    """Convert a (HistoricalFloodEpisode, lat, lng) tuple to response model."""
    episode, lat, lng = row
    return GroundsourceEpisodeResponse(
        id=str(episode.id),
        city=episode.city,
        latitude=float(lat) if lat is not None else 0.0,
        longitude=float(lng) if lng is not None else 0.0,
        area_km2=episode.avg_area_km2,
        date_start=episode.start_date.isoformat(),
        date_end=episode.end_date.isoformat() if episode.end_date else None,
        article_count=episode.article_count or 1,
    )


def _cluster_to_response(row) -> GroundsourceClusterResponse:
    """Convert a (GroundsourceCluster, lat, lng) tuple to response model."""
    cluster, lat, lng = row
    return GroundsourceClusterResponse(
        id=str(cluster.id),
        city=cluster.city,
        latitude=float(lat) if lat is not None else 0.0,
        longitude=float(lng) if lng is not None else 0.0,
        episode_count=cluster.episode_count,
        overlap_status=cluster.overlap_status or "UNKNOWN",
        nearest_hotspot_name=cluster.nearest_hotspot_name,
        nearest_hotspot_distance_m=cluster.nearest_hotspot_distance_m,
        confidence=cluster.confidence or "medium",
        infra_signal=cluster.infra_signal,
    )


# ============================================================================
# Groundsource endpoints
# ============================================================================

@router.get("/groundsource/episodes", response_model=List[GroundsourceEpisodeResponse])
def list_groundsource_episodes(
    city: str = Query(..., description="City slug, e.g. 'delhi'"),
    year: Optional[int] = Query(None, description="Filter to episodes whose start_date falls in this year"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=500, description="Pagination limit"),
    db: Session = Depends(get_db),
):
    """
    List Groundsource flood episodes for a city with optional year filter and pagination.

    Returns episodes ordered by start_date descending.
    """
    city = city.lower().strip()

    # Pull coordinates in the same query to avoid hybrid_property session issues
    lat_col = func.ST_Y(models.HistoricalFloodEpisode.centroid).label("lat")
    lng_col = func.ST_X(models.HistoricalFloodEpisode.centroid).label("lng")

    q = db.query(models.HistoricalFloodEpisode, lat_col, lng_col).filter(
        models.HistoricalFloodEpisode.city == city
    )

    if year is not None:
        q = q.filter(
            func.extract("year", models.HistoricalFloodEpisode.start_date) == year
        )

    rows = (
        q.order_by(models.HistoricalFloodEpisode.start_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [_episode_to_response(row) for row in rows]


@router.get("/groundsource/stats", response_model=HistoricalStatsResponse)
def get_groundsource_stats(
    city: str = Query(..., description="City slug, e.g. 'delhi'"),
    db: Session = Depends(get_db),
):
    """
    Aggregated Groundsource statistics for a city.

    Returns total episode count, cluster count, date range, and cluster overlap breakdown.
    """
    city = city.lower().strip()

    total_episodes = (
        db.query(func.count(models.HistoricalFloodEpisode.id))
        .filter(models.HistoricalFloodEpisode.city == city)
        .scalar()
        or 0
    )

    date_range = (
        db.query(
            func.min(models.HistoricalFloodEpisode.start_date),
            func.max(models.HistoricalFloodEpisode.end_date),
        )
        .filter(models.HistoricalFloodEpisode.city == city)
        .one_or_none()
    )

    total_clusters = (
        db.query(func.count(models.GroundsourceCluster.id))
        .filter(models.GroundsourceCluster.city == city)
        .scalar()
        or 0
    )

    confirmed_clusters = (
        db.query(func.count(models.GroundsourceCluster.id))
        .filter(
            models.GroundsourceCluster.city == city,
            models.GroundsourceCluster.overlap_status == "CONFIRMED",
        )
        .scalar()
        or 0
    )

    missed_clusters = (
        db.query(func.count(models.GroundsourceCluster.id))
        .filter(
            models.GroundsourceCluster.city == city,
            models.GroundsourceCluster.overlap_status == "MISSED",
        )
        .scalar()
        or 0
    )

    date_range_start = date_range[0].isoformat() if date_range and date_range[0] else None
    date_range_end = date_range[1].isoformat() if date_range and date_range[1] else None

    return HistoricalStatsResponse(
        city=city,
        total_episodes=total_episodes,
        total_clusters=total_clusters,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        confirmed_clusters=confirmed_clusters,
        missed_clusters=missed_clusters,
    )


@router.get("/groundsource/nearby", response_model=List[GroundsourceEpisodeResponse])
def get_groundsource_nearby(
    lat: float = Query(..., description="Latitude of the query point"),
    lng: float = Query(..., description="Longitude of the query point"),
    radius_km: float = Query(5.0, gt=0, le=100, description="Search radius in kilometres"),
    limit: int = Query(20, ge=1, le=200, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """
    Return Groundsource episodes within radius_km of the given lat/lng.

    Uses ST_DWithin on geography type for accurate metre-based distance.
    """
    radius_m = radius_km * 1000.0
    point = WKTElement(f"POINT({lng} {lat})", srid=4326)

    lat_col = func.ST_Y(models.HistoricalFloodEpisode.centroid).label("lat")
    lng_col = func.ST_X(models.HistoricalFloodEpisode.centroid).label("lng")

    centroid_geo = cast(models.HistoricalFloodEpisode.centroid, Geography)
    point_geo = cast(point, Geography)

    rows = (
        db.query(models.HistoricalFloodEpisode, lat_col, lng_col)
        .filter(func.ST_DWithin(centroid_geo, point_geo, radius_m))
        .order_by(func.ST_Distance(centroid_geo, point_geo))
        .limit(limit)
        .all()
    )

    return [_episode_to_response(row) for row in rows]


@router.get("/groundsource/clusters", response_model=List[GroundsourceClusterResponse])
def list_groundsource_clusters(
    city: str = Query(..., description="City slug, e.g. 'delhi'"),
    min_confidence: Optional[str] = Query(
        None, description="Minimum confidence level: low, medium, high"
    ),
    db: Session = Depends(get_db),
):
    """
    List Groundsource clusters for a city with optional confidence filter.

    Results are ordered by episode_count descending.
    """
    city = city.lower().strip()

    _CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

    lat_col = func.ST_Y(models.GroundsourceCluster.centroid).label("lat")
    lng_col = func.ST_X(models.GroundsourceCluster.centroid).label("lng")

    q = db.query(models.GroundsourceCluster, lat_col, lng_col).filter(
        models.GroundsourceCluster.city == city
    )

    if min_confidence is not None:
        min_confidence = min_confidence.lower().strip()
        if min_confidence not in _CONFIDENCE_ORDER:
            raise HTTPException(
                status_code=400,
                detail="min_confidence must be one of: low, medium, high",
            )
        min_rank = _CONFIDENCE_ORDER[min_confidence]
        # Include rows whose confidence level is >= min_confidence rank
        allowed = [k for k, v in _CONFIDENCE_ORDER.items() if v >= min_rank]
        q = q.filter(models.GroundsourceCluster.confidence.in_(allowed))

    rows = (
        q.order_by(models.GroundsourceCluster.episode_count.desc())
        .all()
    )

    return [_cluster_to_response(row) for row in rows]


@router.get("/groundsource/episodes/{episode_id}", response_model=GroundsourceEpisodeResponse)
def get_groundsource_episode(
    episode_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve a single Groundsource episode by its UUID.

    Returns 404 if the episode does not exist.
    """
    lat_col = func.ST_Y(models.HistoricalFloodEpisode.centroid).label("lat")
    lng_col = func.ST_X(models.HistoricalFloodEpisode.centroid).label("lng")

    row = (
        db.query(models.HistoricalFloodEpisode, lat_col, lng_col)
        .filter(cast(models.HistoricalFloodEpisode.id, String) == episode_id)
        .one_or_none()
    )

    if row is None:
        raise HTTPException(status_code=404, detail=f"Episode {episode_id!r} not found")

    return _episode_to_response(row)
