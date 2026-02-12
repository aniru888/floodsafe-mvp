"""
External Alerts API - Endpoints for external flood alert sources.

Endpoints:
- GET  /external-alerts             - Get external alerts for a city
- GET  /external-alerts/sources     - Get available alert sources
- POST /external-alerts/refresh     - Trigger manual refresh
- GET  /external-alerts/stats       - Get alert statistics
"""

from enum import Enum

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel
import logging

from src.infrastructure.database import get_async_db
from src.domain.services.external_alerts import AlertAggregator
from src.infrastructure.models import ExternalAlert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/external-alerts", tags=["external-alerts"])


# Valid cities enum (for input validation)
class CityEnum(str, Enum):
    """Valid city identifiers for external alerts."""
    delhi = "delhi"
    bangalore = "bangalore"
    yogyakarta = "yogyakarta"


# Response Models
class ExternalAlertResponse(BaseModel):
    """Response model for external alert."""
    id: str
    source: str
    source_name: Optional[str]
    city: str
    title: str
    message: str
    severity: Optional[str]
    url: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class ExternalAlertsListResponse(BaseModel):
    """Response model for list of external alerts."""
    alerts: list[ExternalAlertResponse]
    total: int
    city: str
    source_filter: Optional[str]


class SourceStatus(BaseModel):
    """Status of an alert source."""
    name: str
    enabled: bool
    count: int = 0
    last_updated: Optional[datetime] = None


class SourcesResponse(BaseModel):
    """Response model for sources list."""
    sources: dict[str, SourceStatus]


class RefreshResponse(BaseModel):
    """Response model for refresh operation."""
    success: bool
    total_alerts_found: int
    total_alerts_new: int
    total_alerts_updated: int
    duration_ms: float
    fetcher_results: list[dict]


class StatsResponse(BaseModel):
    """Response model for alert statistics."""
    city: str
    by_source: dict[str, int]
    by_severity: dict[str, int]
    total: int


@router.get("", response_model=ExternalAlertsListResponse)
async def get_external_alerts(
    city: CityEnum = Query(..., description="City name (delhi, bangalore)"),
    source: Optional[str] = Query(None, description="Filter by source (rss, imd, twitter, cwc)"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, moderate, high, severe)"),
    limit: int = Query(50, le=100, description="Maximum number of alerts"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get external alerts for a city.

    Args:
        city: City identifier (delhi, bangalore)
        source: Optional filter by source
        severity: Optional filter by severity
        limit: Maximum alerts to return (max 100)
        offset: Pagination offset

    Returns:
        List of external alerts
    """
    aggregator = AlertAggregator(db)

    alerts = await aggregator.get_alerts(
        city=city.value,
        source=source,
        severity=severity,
        limit=limit,
        offset=offset
    )

    return ExternalAlertsListResponse(
        alerts=[
            ExternalAlertResponse(
                id=str(alert.id),
                source=alert.source,
                source_name=alert.source_name,
                city=alert.city,
                title=alert.title,
                message=alert.message,
                severity=alert.severity,
                url=alert.url,
                latitude=alert.latitude,
                longitude=alert.longitude,
                created_at=alert.created_at,
            )
            for alert in alerts
        ],
        total=len(alerts),
        city=city.value,
        source_filter=source,
    )


@router.get("/sources", response_model=SourcesResponse)
async def get_available_sources(
    city: Optional[str] = Query(None, description="Optional city for counts"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get list of available alert sources with their status.

    Returns:
        Dict with source names and their enabled/count status
    """
    aggregator = AlertAggregator(db)

    # Get base source status
    source_status = aggregator.get_source_status()

    # Get counts if city provided
    counts = {}
    if city:
        counts = await aggregator.get_alert_count_by_source(city.lower())

    # Build response
    sources = {}
    for source_id, status in source_status.items():
        sources[source_id] = SourceStatus(
            name=status["name"],
            enabled=status["enabled"],
            count=counts.get(source_id, 0),
        )

    return SourcesResponse(sources=sources)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_external_alerts(
    city: CityEnum = Query(..., description="City to refresh alerts for"),
    sources: Optional[str] = Query(None, description="Comma-separated sources to refresh"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Trigger manual refresh of external alerts.

    Args:
        city: City to refresh
        sources: Optional comma-separated list of sources (e.g., "rss,imd")

    Returns:
        Refresh statistics
    """
    logger.info(f"Manual refresh triggered for {city.value}")

    aggregator = AlertAggregator(db)

    # Parse sources if provided
    source_list = None
    if sources:
        source_list = [s.strip().lower() for s in sources.split(",")]

    # Run fetch
    result = await aggregator.fetch_all_alerts(city=city.value, sources=source_list)

    return RefreshResponse(
        success=True,
        total_alerts_found=result.total_alerts_found,
        total_alerts_new=result.total_alerts_new,
        total_alerts_updated=result.total_alerts_updated,
        duration_ms=result.duration_ms,
        fetcher_results=[r.to_dict() for r in result.fetcher_results],
    )


@router.get("/stats", response_model=StatsResponse)
async def get_alert_stats(
    city: CityEnum = Query(..., description="City for statistics"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get alert statistics by source and severity.

    Args:
        city: City identifier

    Returns:
        Statistics breakdown
    """
    from sqlalchemy import select, func
    from src.infrastructure.models import ExternalAlert

    # Count by source
    source_query = select(
        ExternalAlert.source,
        func.count(ExternalAlert.id).label('count')
    ).where(
        ExternalAlert.city == city.value
    ).group_by(ExternalAlert.source)

    source_result = await db.execute(source_query)
    by_source = {row.source: row.count for row in source_result.all()}

    # Count by severity
    severity_query = select(
        ExternalAlert.severity,
        func.count(ExternalAlert.id).label('count')
    ).where(
        ExternalAlert.city == city.value
    ).group_by(ExternalAlert.severity)

    severity_result = await db.execute(severity_query)
    by_severity = {(row.severity or 'unknown'): row.count for row in severity_result.all()}

    # Total count
    total = sum(by_source.values())

    return StatsResponse(
        city=city.value,
        by_source=by_source,
        by_severity=by_severity,
        total=total,
    )


@router.delete("/cleanup")
async def cleanup_expired_alerts(
    city: Optional[str] = Query(None, description="Optional city filter"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Remove expired alerts from database.

    Args:
        city: Optional city to limit cleanup

    Returns:
        Number of alerts deleted
    """
    aggregator = AlertAggregator(db)
    deleted = await aggregator.cleanup_expired_alerts(city=city)

    return {"deleted": deleted, "city": city}
