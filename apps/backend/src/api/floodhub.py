"""
FloodHub API endpoints - Google Flood Forecasting proxy.

Provides flood forecasting data for Delhi's Yamuna River.
NO SILENT FALLBACKS - all errors are surfaced to frontend.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..domain.services.floodhub_service import (
    get_floodhub_service,
    FloodHubAPIError,
    GaugeStatus,
    GaugeForecast,
    FloodHubStatus,
    SignificantEvent,
)

router = APIRouter(prefix="/floodhub", tags=["floodhub"])


class FloodHubStatusResponse(BaseModel):
    """Response for FloodHub status endpoint."""
    enabled: bool
    message: Optional[str] = None
    overall_severity: Optional[str] = None
    gauge_count: Optional[int] = None
    alerts_by_severity: Optional[dict] = None
    last_updated: Optional[str] = None


@router.get("/status", response_model=FloodHubStatusResponse)
async def get_floodhub_status(city: str = Query("DEL", description="City code (DEL or BLR)")):
    """
    Get overall FloodHub status for a city.

    Returns:
    - enabled=False with message for unsupported cities or unconfigured service
    - enabled=True with severity data when operational

    Raises HTTPException on API failures - NO SILENT FALLBACKS.
    """
    # City guard - FloodHub only covers Delhi for now
    if city.upper() not in ("DEL", "DELHI"):
        return FloodHubStatusResponse(
            enabled=False,
            message="FloodHub coverage coming soon for this city"
        )

    try:
        service = get_floodhub_service()
        status = await service.get_overall_status()

        return FloodHubStatusResponse(
            enabled=status.enabled,
            message=status.message,
            overall_severity=status.overall_severity,
            gauge_count=status.gauge_count,
            alerts_by_severity=status.alerts_by_severity,
            last_updated=status.last_updated,
        )
    except FloodHubAPIError as e:
        # Surface API errors to frontend - NO SILENT FALLBACK
        raise HTTPException(status_code=502, detail=str(e))
    except RuntimeError as e:
        # Service not initialized
        return FloodHubStatusResponse(
            enabled=False,
            message="FloodHub service not initialized"
        )


@router.get("/gauges", response_model=List[GaugeStatus])
async def get_floodhub_gauges():
    """
    Get all Delhi Yamuna River gauges with current flood status.

    Returns empty list if service is disabled (frontend shows "Not Configured").
    Raises HTTPException on API failures - NO SILENT FALLBACKS.
    """
    try:
        service = get_floodhub_service()
        return await service.get_delhi_gauges()
    except FloodHubAPIError as e:
        # Surface API errors - NO SILENT FALLBACK
        raise HTTPException(status_code=502, detail=str(e))
    except RuntimeError:
        # Service not initialized - return empty (shows "Not Configured" in UI)
        return []


@router.get("/forecast/{gauge_id}", response_model=Optional[GaugeForecast])
async def get_gauge_forecast(gauge_id: str):
    """
    Get forecast for a specific gauge.

    Returns forecast with water level predictions and threshold levels.
    Raises HTTPException on API failures - NO SILENT FALLBACKS.
    """
    try:
        service = get_floodhub_service()
        forecast = await service.get_gauge_forecast(gauge_id)

        if forecast is None:
            raise HTTPException(
                status_code=404,
                detail=f"No forecast available for gauge {gauge_id}"
            )

        return forecast
    except FloodHubAPIError as e:
        # Surface API errors - NO SILENT FALLBACK
        raise HTTPException(status_code=502, detail=str(e))
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="FloodHub service not configured"
        )


@router.get("/inundation/{polygon_id}")
async def get_inundation_map(polygon_id: str):
    """
    Get inundation map polygon as GeoJSON.

    Fetches KML from Google API and converts to GeoJSON FeatureCollection
    for rendering on MapLibre.
    """
    try:
        service = get_floodhub_service()
        geojson = await service.get_inundation_polygon(polygon_id)

        if geojson is None:
            raise HTTPException(
                status_code=404,
                detail=f"No inundation polygon found for ID {polygon_id}"
            )

        return geojson
    except FloodHubAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="FloodHub service not configured"
        )


@router.get("/events", response_model=List[SignificantEvent])
async def get_significant_events():
    """
    Get current significant flood events affecting India.

    Returns events with affected population, area, and linked gauges.
    Empty list during non-flood periods is normal.
    """
    try:
        service = get_floodhub_service()
        return await service.get_significant_events()
    except FloodHubAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except RuntimeError:
        return []
