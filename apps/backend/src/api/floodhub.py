"""
FloodHub API endpoints - Google Flood Forecasting proxy.

Provides flood forecasting data for supported cities (Delhi, Bangalore, Yogyakarta, Singapore).
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


SUPPORTED_CITIES = {
    "DEL": "delhi", "DELHI": "delhi",
    "BLR": "bangalore", "BANGALORE": "bangalore",
    "YGY": "yogyakarta", "YOGYAKARTA": "yogyakarta",
    "SIN": "singapore", "SINGAPORE": "singapore",
}


@router.get("/status", response_model=FloodHubStatusResponse)
async def get_floodhub_status(city: str = Query("DEL", description="City code (DEL, BLR, YGY, or SIN)")):
    """
    Get overall FloodHub status for a city.

    Returns:
    - enabled=False with message for unsupported cities or unconfigured service
    - enabled=True with severity data when operational

    Raises HTTPException on API failures - NO SILENT FALLBACKS.
    """
    city_key = SUPPORTED_CITIES.get(city.upper())
    if not city_key:
        return FloodHubStatusResponse(
            enabled=False,
            message=f"FloodHub not available for city code '{city}'"
        )

    try:
        service = get_floodhub_service()
        # For Delhi, use existing optimized overall_status (uses cached Delhi gauges)
        # For other cities, fetch city-specific gauges and derive status
        if city_key == "delhi":
            status = await service.get_overall_status()
        else:
            gauges = await service.get_city_gauges(city_key)
            if not gauges:
                return FloodHubStatusResponse(
                    enabled=True,
                    message=f"No FloodHub gauges found for {city_key.title()}. Coverage may be limited.",
                    gauge_count=0,
                )
            # Derive status from gauges
            severity_counts: dict = {}
            for g in gauges:
                sev = g.severity or "no_flooding"
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            overall = "no_flooding"
            for sev in ["extreme", "danger", "warning"]:
                if severity_counts.get(sev, 0) > 0:
                    overall = sev
                    break
            status = FloodHubStatus(
                enabled=True,
                overall_severity=overall,
                gauge_count=len(gauges),
                alerts_by_severity=severity_counts,
            )

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
async def get_floodhub_gauges(city: str = Query("DEL", description="City code (DEL, BLR, YGY, or SIN)")):
    """
    Get gauges with current flood status for a city.

    Returns empty list if service is disabled (frontend shows "Not Configured").
    Raises HTTPException on API failures - NO SILENT FALLBACKS.
    """
    city_key = SUPPORTED_CITIES.get(city.upper())
    if not city_key:
        raise HTTPException(status_code=400, detail=f"Unsupported city code: {city}")

    try:
        service = get_floodhub_service()
        return await service.get_city_gauges(city_key)
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
async def get_significant_events(city: str = Query("DEL", description="City code (DEL, BLR, YGY, or SIN)")):
    """
    Get current significant flood events for a city's country.

    Returns events with affected population, area, and linked gauges.
    Empty list during non-flood periods is normal.
    """
    city_key = SUPPORTED_CITIES.get(city.upper())
    if not city_key:
        raise HTTPException(status_code=400, detail=f"Unsupported city code: {city}")

    try:
        service = get_floodhub_service()
        return await service.get_city_events(city_key)
    except FloodHubAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except RuntimeError:
        return []
