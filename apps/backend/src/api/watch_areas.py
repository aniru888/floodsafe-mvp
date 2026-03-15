from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from uuid import UUID
import logging
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from geoalchemy2 import WKTElement

from ..infrastructure.database import get_db
from ..infrastructure import models
from ..domain.models import WatchAreaCreate, WatchAreaResponse
from ..domain.services.watch_area_risk_service import WatchAreaRiskService
from ..domain.services.watch_area_service import WatchAreaService, ALERT_RADIUS_MAP
from .deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic models for personal pin endpoints
# =============================================================================

class PinCreateRequest(BaseModel):
    """Request body for creating a personal pin."""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    name: str = Field(..., min_length=1, max_length=100)
    city: Optional[str] = None
    alert_radius_label: str = Field(
        default="my_neighborhood",
        description="One of: just_this_spot, my_street, my_neighborhood, wider_area",
    )
    visibility: str = Field(
        default="private",
        description="'private' or 'circles'",
    )


class PinResponse(BaseModel):
    """Response shape for a personal pin."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    latitude: Optional[float]
    longitude: Optional[float]
    city: Optional[str]
    alert_radius: Optional[float]
    radius: float
    fhi_score: Optional[float]
    fhi_level: Optional[str]
    fhi_components: Optional[dict]
    fhi_updated_at: Optional[datetime]
    historical_episode_count: int
    nearest_cluster_id: Optional[UUID]
    road_name: Optional[str]
    is_personal_hotspot: bool
    visibility: str
    source: str
    created_at: datetime
    updated_at: Optional[datetime]


class FhiHistoryEntry(BaseModel):
    """A single FHI history record for a pin."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    watch_area_id: UUID
    fhi_score: float
    fhi_level: str
    fhi_components: Optional[dict]
    recorded_at: datetime


@router.post("/", response_model=WatchAreaResponse)
def create_watch_area(watch_area: WatchAreaCreate, db: Session = Depends(get_db)):
    """
    Create a new watch area for a user.
    Watch areas allow users to monitor specific locations for flood alerts.
    """
    try:
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == watch_area.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Create PostGIS point from lat/lng using WKTElement for proper geometry conversion
        point_wkt = f"POINT({watch_area.longitude} {watch_area.latitude})"

        new_watch_area = models.WatchArea(
            user_id=watch_area.user_id,
            name=watch_area.name,
            location=WKTElement(point_wkt, srid=4326),
            radius=watch_area.radius
        )

        db.add(new_watch_area)
        db.commit()
        db.refresh(new_watch_area)

        # Return response with extracted lat/lng
        return WatchAreaResponse(
            id=new_watch_area.id,
            user_id=new_watch_area.user_id,
            name=new_watch_area.name,
            latitude=new_watch_area.latitude,
            longitude=new_watch_area.longitude,
            radius=new_watch_area.radius,
            created_at=new_watch_area.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating watch area: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create watch area")


@router.get("/user/{user_id}", response_model=list[WatchAreaResponse])
def get_user_watch_areas(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get all watch areas for a specific user.
    """
    try:
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        watch_areas = db.query(models.WatchArea).filter(
            models.WatchArea.user_id == user_id
        ).all()

        # Convert to response format with lat/lng
        response = []
        for wa in watch_areas:
            response.append(WatchAreaResponse(
                id=wa.id,
                user_id=wa.user_id,
                name=wa.name,
                latitude=wa.latitude,
                longitude=wa.longitude,
                radius=wa.radius,
                created_at=wa.created_at
            ))

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching watch areas for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch watch areas")


@router.get("/my-pins", response_model=List[PinResponse])
def list_my_pins(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return all personal pins for the authenticated user, newest first.
    """
    pins = (
        db.query(models.WatchArea)
        .filter(
            models.WatchArea.user_id == current_user.id,
            models.WatchArea.is_personal_hotspot == True,  # noqa: E712
        )
        .order_by(models.WatchArea.created_at.desc())
        .all()
    )
    return [_pin_to_response(p) for p in pins]


@router.get("/{watch_area_id}", response_model=WatchAreaResponse)
def get_watch_area(watch_area_id: UUID, db: Session = Depends(get_db)):
    """
    Get a specific watch area by ID.
    """
    try:
        watch_area = db.query(models.WatchArea).filter(
            models.WatchArea.id == watch_area_id
        ).first()

        if not watch_area:
            raise HTTPException(status_code=404, detail="Watch area not found")

        return WatchAreaResponse(
            id=watch_area.id,
            user_id=watch_area.user_id,
            name=watch_area.name,
            latitude=watch_area.latitude,
            longitude=watch_area.longitude,
            radius=watch_area.radius,
            created_at=watch_area.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching watch area {watch_area_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch watch area")


@router.delete("/{watch_area_id}")
def delete_watch_area(watch_area_id: UUID, db: Session = Depends(get_db)):
    """
    Delete a watch area.
    """
    try:
        watch_area = db.query(models.WatchArea).filter(
            models.WatchArea.id == watch_area_id
        ).first()

        if not watch_area:
            raise HTTPException(status_code=404, detail="Watch area not found")

        db.delete(watch_area)
        db.commit()

        return {"message": "Watch area deleted successfully", "id": str(watch_area_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting watch area {watch_area_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete watch area")


# Pydantic models for risk assessment response
class HotspotInWatchAreaResponse(BaseModel):
    """Hotspot within a watch area."""
    id: int
    name: str
    fhi_score: float
    fhi_level: str
    fhi_color: str
    distance_meters: float


class WatchAreaRiskAssessmentResponse(BaseModel):
    """Risk assessment for a watch area."""
    watch_area_id: UUID
    watch_area_name: str
    latitude: float
    longitude: float
    radius: float
    nearby_hotspots: List[HotspotInWatchAreaResponse]
    nearby_hotspots_count: int
    critical_hotspots_count: int
    average_fhi: float
    max_fhi: float
    max_fhi_level: str
    is_at_risk: bool
    risk_flag_reason: Optional[str]
    last_calculated: datetime


@router.get("/user/{user_id}/risk-assessment", response_model=List[WatchAreaRiskAssessmentResponse])
async def get_user_watch_area_risks(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get risk assessment for all user's watch areas based on nearby hotspots.

    Analyzes each watch area for:
    - Nearby hotspots within radius
    - Average and maximum FHI scores
    - Critical hotspots (HIGH/EXTREME)
    - Risk flag if average FHI > 0.5 OR any HIGH/EXTREME hotspot present

    Returns:
        List of risk assessments, one per watch area
    """
    try:
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Calculate risk assessments
        service = WatchAreaRiskService(db)
        assessments = await service.calculate_risk_for_user_watch_areas(user_id)

        # Convert dataclasses to Pydantic models
        response = []
        for assessment in assessments:
            response.append(WatchAreaRiskAssessmentResponse(
                watch_area_id=assessment.watch_area_id,
                watch_area_name=assessment.watch_area_name,
                latitude=assessment.latitude,
                longitude=assessment.longitude,
                radius=assessment.radius,
                nearby_hotspots=[
                    HotspotInWatchAreaResponse(
                        id=h.id,
                        name=h.name,
                        fhi_score=h.fhi_score,
                        fhi_level=h.fhi_level,
                        fhi_color=h.fhi_color,
                        distance_meters=h.distance_meters
                    )
                    for h in assessment.nearby_hotspots
                ],
                nearby_hotspots_count=assessment.nearby_hotspots_count,
                critical_hotspots_count=assessment.critical_hotspots_count,
                average_fhi=assessment.average_fhi,
                max_fhi=assessment.max_fhi,
                max_fhi_level=assessment.max_fhi_level,
                is_at_risk=assessment.is_at_risk,
                risk_flag_reason=assessment.risk_flag_reason,
                last_calculated=assessment.last_calculated
            ))

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating watch area risks for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate watch area risks")


# =============================================================================
# Personal pin endpoints
# =============================================================================

def _pin_to_response(wa: models.WatchArea) -> PinResponse:
    """Convert a WatchArea ORM object to a PinResponse."""
    return PinResponse(
        id=wa.id,
        user_id=wa.user_id,
        name=wa.name,
        latitude=wa.latitude,
        longitude=wa.longitude,
        city=wa.city,
        alert_radius=wa.alert_radius,
        radius=wa.radius,
        fhi_score=wa.fhi_score,
        fhi_level=wa.fhi_level,
        fhi_components=wa.fhi_components,
        fhi_updated_at=wa.fhi_updated_at,
        historical_episode_count=wa.historical_episode_count or 0,
        nearest_cluster_id=wa.nearest_cluster_id,
        road_name=wa.road_name,
        is_personal_hotspot=wa.is_personal_hotspot or False,
        visibility=wa.visibility or "private",
        source=wa.source or "personal_pin",
        created_at=wa.created_at,
        updated_at=wa.updated_at,
    )


@router.post("/pin", response_model=PinResponse, status_code=status.HTTP_201_CREATED)
async def create_personal_pin(
    data: PinCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create a personal pin watch area for the authenticated user.

    Computes FHI, counts historical flood episodes within 2km, finds the
    nearest candidate hotspot cluster, and attempts road snapping.
    Returns HTTP 201 on success, 409 if the 25-pin limit is reached.
    """
    if data.alert_radius_label not in ALERT_RADIUS_MAP:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid alert_radius_label '{data.alert_radius_label}'. "
                f"Valid values: {list(ALERT_RADIUS_MAP.keys())}"
            ),
        )

    service = WatchAreaService(db)
    try:
        pin = await service.create_personal_pin(
            user_id=current_user.id,
            latitude=data.latitude,
            longitude=data.longitude,
            name=data.name,
            city=data.city,
            alert_radius_label=data.alert_radius_label,
            visibility=data.visibility,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except Exception as exc:
        logger.error("Error creating personal pin for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create personal pin",
        )

    return _pin_to_response(pin)


class WatchHotspotRequest(BaseModel):
    """Request body for watching an official hotspot."""
    hotspot_name: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    city: Optional[str] = None


@router.post("/watch-hotspot", response_model=PinResponse, status_code=status.HTTP_201_CREATED)
async def watch_hotspot(
    data: WatchHotspotRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Save an official hotspot to the user's personal watch list.

    Reuses the personal pin creation flow (FHI compute, historical lookup,
    road snap, 25-pin limit) but marks it as watching an official hotspot.
    """
    service = WatchAreaService(db)
    try:
        pin = await service.create_personal_pin(
            user_id=current_user.id,
            latitude=data.latitude,
            longitude=data.longitude,
            name=data.hotspot_name,
            city=data.city,
            alert_radius_label="my_neighborhood",
            visibility="private",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except Exception as exc:
        logger.error("Error watching hotspot for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save hotspot to watch list",
        )

    return _pin_to_response(pin)


@router.post("/{watch_area_id}/refresh-fhi", response_model=PinResponse)
async def refresh_pin_fhi(
    watch_area_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Re-compute FHI for a personal pin owned by the authenticated user.

    Returns the updated pin. Raises 404 if the pin does not exist or belongs
    to another user. Raises 400 if the pin has no stored coordinates.
    """
    pin = db.query(models.WatchArea).filter(
        models.WatchArea.id == watch_area_id,
        models.WatchArea.user_id == current_user.id,
    ).first()

    if not pin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pin not found or does not belong to you",
        )

    service = WatchAreaService(db)
    try:
        pin = await service.refresh_pin_fhi(pin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        logger.error("FHI refresh failed for pin %s: %s", watch_area_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="FHI calculation service is currently unavailable",
        )
    except Exception as exc:
        logger.error("Unexpected error refreshing FHI for pin %s: %s", watch_area_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh FHI",
        )

    return _pin_to_response(pin)


@router.get("/{watch_area_id}/fhi-history", response_model=List[FhiHistoryEntry])
def get_pin_fhi_history(
    watch_area_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return the FHI history for a personal pin owned by the authenticated user,
    most recent first.

    Raises 404 if the pin does not exist or belongs to another user.
    """
    pin = db.query(models.WatchArea).filter(
        models.WatchArea.id == watch_area_id,
        models.WatchArea.user_id == current_user.id,
    ).first()

    if not pin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pin not found or does not belong to you",
        )

    history = (
        db.query(models.WatchAreaFhiHistory)
        .filter(models.WatchAreaFhiHistory.watch_area_id == watch_area_id)
        .order_by(models.WatchAreaFhiHistory.recorded_at.desc())
        .all()
    )

    return [
        FhiHistoryEntry(
            id=h.id,
            watch_area_id=h.watch_area_id,
            fhi_score=h.fhi_score,
            fhi_level=h.fhi_level,
            fhi_components=h.fhi_components,
            recorded_at=h.recorded_at,
        )
        for h in history
    ]
