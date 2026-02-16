"""
Alerts API router for managing user alerts.

Includes unified endpoint that combines:
- External alerts (IMD, CWC, RSS, Twitter)
- Community reports from FloodSafe users
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_X, ST_Y
from uuid import UUID
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import logging

from ..infrastructure.database import get_db
from ..domain.services.alert_service import AlertService
from ..infrastructure.models import ExternalAlert, Report

router = APIRouter()
logger = logging.getLogger(__name__)


# Unified Alert Response Models
class UnifiedAlertResponse(BaseModel):
    """Unified alert response model."""
    id: str
    type: Literal["external", "community"]
    source: str
    source_name: Optional[str] = None
    title: str
    message: str
    severity: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SourceMeta(BaseModel):
    """Metadata about an alert source."""
    name: str
    count: int
    enabled: bool = True


class UnifiedAlertsListResponse(BaseModel):
    """Response for unified alerts list."""
    alerts: list[UnifiedAlertResponse]
    sources: dict[str, SourceMeta]
    total: int
    city: str


@router.get("/user/{user_id}")
def get_user_alerts(
    user_id: UUID,
    unread_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Get all alerts for a user."""
    try:
        alert_service = AlertService(db)
        alerts = alert_service.get_user_alerts(user_id, unread_only)
        return alerts
    except Exception as e:
        logger.error(f"Error fetching alerts for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alerts")


@router.get("/user/{user_id}/count")
def get_unread_alert_count(user_id: UUID, db: Session = Depends(get_db)):
    """Get count of unread alerts for a user."""
    try:
        alert_service = AlertService(db)
        count = alert_service.get_unread_count(user_id)
        return {"count": count}
    except Exception as e:
        logger.error(f"Error getting alert count for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get alert count")


@router.post("/{alert_id}/read")
def mark_alert_as_read(alert_id: UUID, user_id: UUID = Query(...), db: Session = Depends(get_db)):
    """Mark a single alert as read."""
    try:
        alert_service = AlertService(db)
        success = alert_service.mark_as_read(alert_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"message": "Alert marked as read"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking alert {alert_id} as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark alert as read")


@router.post("/user/{user_id}/read-all")
def mark_all_alerts_as_read(user_id: UUID, db: Session = Depends(get_db)):
    """Mark all alerts as read for a user."""
    try:
        alert_service = AlertService(db)
        count = alert_service.mark_all_as_read(user_id)
        return {"message": f"Marked {count} alerts as read"}
    except Exception as e:
        logger.error(f"Error marking all alerts as read for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark alerts as read")


# Unified Alerts Endpoint
@router.get("/unified", response_model=UnifiedAlertsListResponse)
def get_unified_alerts(
    city: str = Query(..., description="City identifier (delhi, bangalore)"),
    sources: str = Query("all", description="Filter: all, official, news, social, community"),
    limit: int = Query(50, le=100, description="Maximum alerts to return"),
    db: Session = Depends(get_db)
):
    """
    Get unified feed combining external alerts and community reports.

    Source filters:
    - all: All sources
    - official: IMD, CWC (government sources)
    - news: RSS news feeds
    - social: Twitter, Telegram
    - community: FloodSafe user reports

    Returns alerts sorted by created_at descending (most recent first).
    """
    try:
        alerts = []
        source_counts = {}

        # Map filter to sources
        source_mapping = {
            "official": ["imd", "cwc"],
            "news": ["rss"],
            "social": ["twitter", "telegram"],
            "community": ["floodsafe"],
        }

        # Determine which external sources to fetch
        external_sources = []
        include_community = False

        if sources == "all":
            external_sources = ["imd", "cwc", "rss", "twitter", "telegram"]
            include_community = True
        elif sources == "community":
            include_community = True
        else:
            external_sources = source_mapping.get(sources, [])
            include_community = sources == "community" or sources == "all"

        # Fetch external alerts
        if external_sources:
            external_query = db.query(ExternalAlert).filter(
                ExternalAlert.city == city.lower()
            )

            if sources != "all":
                external_query = external_query.filter(
                    ExternalAlert.source.in_(external_sources)
                )

            external_query = external_query.order_by(
                ExternalAlert.created_at.desc()
            ).limit(limit)

            for alert in external_query.all():
                alerts.append(UnifiedAlertResponse(
                    id=str(alert.id),
                    type="external",
                    source=alert.source,
                    source_name=alert.source_name,
                    title=alert.title,
                    message=alert.message,
                    severity=alert.severity,
                    latitude=alert.latitude,
                    longitude=alert.longitude,
                    url=alert.url,
                    created_at=alert.created_at,
                ))

                # Count by source
                source_counts[alert.source] = source_counts.get(alert.source, 0) + 1

        # Fetch community reports
        if include_community:
            # Get reports from last 7 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)

            # Community reports - query with PostGIS coordinate extraction
            # Report.location is a Geometry('POINT'), so we use ST_X/ST_Y to extract lng/lat
            reports_query = db.query(
                Report,
                ST_X(Report.location).label('longitude'),
                ST_Y(Report.location).label('latitude')
            ).filter(
                Report.timestamp >= cutoff,
                Report.verified == True
            ).order_by(
                Report.timestamp.desc()
            ).limit(limit)

            for row in reports_query.all():
                report = row[0]  # Report object
                longitude = row[1]  # ST_X result
                latitude = row[2]   # ST_Y result

                # Map water_depth to severity
                severity = _map_water_depth_to_severity(report.water_depth)

                # Build title from location description
                title = f"Flood Report"
                if report.water_depth:
                    title = f"{report.water_depth.title()}-deep flooding reported"

                alerts.append(UnifiedAlertResponse(
                    id=str(report.id),
                    type="community",
                    source="floodsafe",
                    source_name="FloodSafe Community",
                    title=title,
                    message=report.description or "Community flood report",
                    severity=severity,
                    latitude=latitude,
                    longitude=longitude,
                    url=None,
                    created_at=report.timestamp,
                ))

                source_counts["floodsafe"] = source_counts.get("floodsafe", 0) + 1

        # Sort all alerts by created_at
        alerts.sort(key=lambda x: x.created_at, reverse=True)

        # Limit total
        alerts = alerts[:limit]

        # Build source metadata
        source_meta = {
            "imd": SourceMeta(name="IMD Weather", count=source_counts.get("imd", 0)),
            "cwc": SourceMeta(name="CWC Flood Forecast", count=source_counts.get("cwc", 0)),
            "rss": SourceMeta(name="News Feeds", count=source_counts.get("rss", 0)),
            "twitter": SourceMeta(name="Twitter/X", count=source_counts.get("twitter", 0)),
            "telegram": SourceMeta(name="Telegram", count=source_counts.get("telegram", 0), enabled=True),
            "floodsafe": SourceMeta(name="Community Reports", count=source_counts.get("floodsafe", 0)),
        }

        return UnifiedAlertsListResponse(
            alerts=alerts,
            sources=source_meta,
            total=len(alerts),
            city=city.lower(),
        )

    except Exception as e:
        logger.error(f"Error fetching unified alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch unified alerts")


def _map_water_depth_to_severity(water_depth: Optional[str]) -> Optional[str]:
    """Map water depth to severity level."""
    if not water_depth:
        return "moderate"

    depth_lower = water_depth.lower()

    if depth_lower in ["impassable", "waist", "chest"]:
        return "severe"
    elif depth_lower in ["knee"]:
        return "high"
    elif depth_lower in ["ankle"]:
        return "moderate"

    return "low"
