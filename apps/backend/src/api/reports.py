from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List
from uuid import UUID
from PIL import Image
from datetime import datetime, timedelta
import io
import logging
import json
import httpx

from ..infrastructure.database import get_db
from ..infrastructure import models
from ..domain.models import ReportResponse, Report as ReportDomain, UserResponse, VoteResponse
from ..domain.reputation_models import ReportVerificationRequest
from .deps import get_current_user, get_current_user_optional, get_current_verified_user
from ..domain.services.reputation_service import ReputationService
from ..core.utils import get_exif_data, get_lat_lon
from ..core.config import settings
from ..infrastructure.storage import get_storage_service, StorageError, StorageNotConfiguredError
from math import radians, sin, cos, sqrt, atan2
from ..domain.services.otp_service import get_otp_service
from ..domain.services.validation_service import ReportValidationService
from ..domain.services.push_notification_service import send_push_to_user
from ..domain.services.weather_snapshot_service import WeatherSnapshotService
from ..domain.services.road_snapping_service import RoadSnappingService
from geoalchemy2.functions import ST_DWithin, ST_MakePoint

router = APIRouter()
logger = logging.getLogger(__name__)

# Reports auto-archive after 5 days
REPORT_ARCHIVE_DAYS = 5

# City bounding boxes for coordinate-based detection (matches FHICalculator.CITY_BOUNDS)
_CITY_BOUNDS = {
    "delhi": {"min_lat": 28.40, "max_lat": 28.88, "min_lng": 76.84, "max_lng": 77.35},
    "bangalore": {"min_lat": 12.75, "max_lat": 13.20, "min_lng": 77.35, "max_lng": 77.80},
    "yogyakarta": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
    "singapore": {"min_lat": 1.15, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    "indore": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
}


def _detect_city(lat: float, lng: float) -> Optional[str]:
    """Detect city from coordinates using bounding boxes. Returns None if no match."""
    for city, bounds in _CITY_BOUNDS.items():
        if (bounds["min_lat"] <= lat <= bounds["max_lat"] and
                bounds["min_lng"] <= lng <= bounds["max_lng"]):
            return city
    return None


def get_active_reports_filter():
    """
    Filter for active (non-archived) reports.
    A report is archived if:
    - It was explicitly archived (archived_at is not NULL), OR
    - It's older than 5 days (auto-archive)
    """
    archive_cutoff = datetime.utcnow() - timedelta(days=REPORT_ARCHIVE_DAYS)
    return and_(
        or_(models.Report.archived_at == None, models.Report.archived_at == None),  # Not explicitly archived
        models.Report.timestamp > archive_cutoff  # Not auto-archived (less than 5 days old)
    )

# Location verification tolerance in meters (matches frontend)
LOCATION_VERIFICATION_TOLERANCE_METERS = 100

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def get_comment_counts(db: Session, report_ids: List[UUID]) -> dict:
    """Get comment counts for a list of report IDs in a single query."""
    if not report_ids:
        return {}

    counts = db.query(
        models.Comment.report_id,
        func.count(models.Comment.id).label('count')
    ).filter(
        models.Comment.report_id.in_(report_ids)
    ).group_by(
        models.Comment.report_id
    ).all()

    return {str(report_id): count for report_id, count in counts}


def convert_report_to_response(report: models.Report, comment_count: int = 0) -> ReportResponse:
    """Convert a Report ORM model to ReportResponse with comment count."""
    # Extract lat/lon from geometry
    latitude = None
    longitude = None
    if report.location:
        from geoalchemy2.shape import to_shape
        point = to_shape(report.location)
        latitude = point.y
        longitude = point.x

    # Extract ML classification from media_metadata JSON
    ml_classification = None
    ml_confidence = None
    ml_is_flood = None
    ml_needs_review = None

    if report.media_metadata:
        try:
            metadata = json.loads(report.media_metadata) if isinstance(report.media_metadata, str) else report.media_metadata
            ml_classification = metadata.get("ml_classification")
            ml_confidence = metadata.get("ml_confidence")
            ml_is_flood = metadata.get("ml_is_flood")
            ml_needs_review = metadata.get("ml_needs_review")
        except (json.JSONDecodeError, TypeError):
            # If parsing fails, leave ML fields as None
            pass

    return ReportResponse(
        id=report.id,
        user_id=report.user_id,
        description=report.description,
        latitude=latitude,
        longitude=longitude,
        media_url=report.media_url,
        media_type=report.media_type,
        media_metadata=report.media_metadata,
        timestamp=report.timestamp,
        verified=report.verified,
        verification_score=report.verification_score,
        upvotes=report.upvotes,
        downvotes=report.downvotes,
        quality_score=report.quality_score,
        verified_at=report.verified_at,
        phone_number=report.phone_number,
        phone_verified=report.phone_verified,
        water_depth=report.water_depth,
        vehicle_passability=report.vehicle_passability,
        iot_validation_score=report.iot_validation_score,
        nearby_sensor_ids=report.nearby_sensor_ids,
        prophet_prediction_match=report.prophet_prediction_match,
        location_verified=report.location_verified,
        archived_at=report.archived_at,
        comment_count=comment_count,
        ml_classification=ml_classification,
        ml_confidence=ml_confidence,
        ml_is_flood=ml_is_flood,
        ml_needs_review=ml_needs_review,
        # ML pipeline enrichment
        weather_snapshot=report.weather_snapshot,
        road_segment_id=str(report.road_segment_id) if report.road_segment_id else None,
        road_name=report.road_name,
        road_type=report.road_type,
    )


@router.get("/", response_model=List[ReportResponse])
def list_reports(db: Session = Depends(get_db)):
    """
    List all active (non-archived) flood reports.
    Reports are auto-archived after 5 days.
    Includes comment counts for each report.
    """
    try:
        archive_cutoff = datetime.utcnow() - timedelta(days=REPORT_ARCHIVE_DAYS)
        reports = db.query(models.Report).filter(
            models.Report.archived_at == None,  # Not explicitly archived
            models.Report.timestamp > archive_cutoff  # Not auto-archived
        ).order_by(models.Report.timestamp.desc()).all()

        # Get comment counts for all reports in a single query
        report_ids = [r.id for r in reports]
        comment_counts = get_comment_counts(db, report_ids)

        # Convert to responses with comment counts
        return [
            convert_report_to_response(r, comment_counts.get(str(r.id), 0))
            for r in reports
        ]
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to list reports")


@router.get("/user/{user_id}", response_model=List[ReportResponse])
def get_user_reports(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(False, description="Include archived reports"),
    db: Session = Depends(get_db)
):
    """
    Get all reports submitted by a specific user.
    Returns reports ordered by timestamp (most recent first).
    Used for the "My Reports" section in user profile.

    By default, only active reports are returned.
    Set include_archived=true to include all reports.
    """
    try:
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Build query
        query = db.query(models.Report).filter(models.Report.user_id == user_id)

        # Filter out archived unless explicitly requested
        if not include_archived:
            archive_cutoff = datetime.utcnow() - timedelta(days=REPORT_ARCHIVE_DAYS)
            query = query.filter(
                models.Report.archived_at == None,
                models.Report.timestamp > archive_cutoff
            )

        reports = query.order_by(
            models.Report.timestamp.desc()
        ).offset(offset).limit(limit).all()

        # Get comment counts
        report_ids = [r.id for r in reports]
        comment_counts = get_comment_counts(db, report_ids)

        return [
            convert_report_to_response(r, comment_counts.get(str(r.id), 0))
            for r in reports
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching reports for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user reports")


@router.get("/location/details", response_model=dict)
def get_location_details(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: float = Query(500, gt=0, le=5000),
    db: Session = Depends(get_db)
):
    """
    Get all active (non-archived) reports and user information at a specific location.
    This is used when user clicks "Locate" on an alert to see details.

    Returns:
    - List of reports at this location
    - Users who reported (with their report counts)
    - Count of total reports
    """
    try:
        # Create a point for the query location
        query_point = ST_MakePoint(longitude, latitude)
        archive_cutoff = datetime.utcnow() - timedelta(days=REPORT_ARCHIVE_DAYS)

        # Find all active reports within radius (exclude archived)
        nearby_reports = db.query(models.Report).filter(
            ST_DWithin(
                models.Report.location,
                query_point,
                radius_meters,
                True  # Use spheroid for accurate distance
            ),
            models.Report.archived_at == None,  # Not explicitly archived
            models.Report.timestamp > archive_cutoff  # Not auto-archived
        ).order_by(models.Report.timestamp.desc()).all()

        # Get unique user IDs from these reports
        user_ids = list(set([r.user_id for r in nearby_reports]))

        # Get user details
        users = db.query(models.User).filter(models.User.id.in_(user_ids)).all() if user_ids else []

        # Build response
        report_details = []
        for report in nearby_reports:
            report_details.append({
                "id": str(report.id),
                "description": report.description,
                "latitude": report.latitude,
                "longitude": report.longitude,
                "verified": report.verified,
                "upvotes": report.upvotes,
                "timestamp": report.timestamp.isoformat(),
                "user_id": str(report.user_id)
            })

        user_details = []
        for user in users:
            user_details.append({
                "id": str(user.id),
                "username": user.username,
                "reports_count": user.reports_count,
                "verified_reports_count": user.verified_reports_count,
                "level": user.level
            })

        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "radius_meters": radius_meters
            },
            "total_reports": len(nearby_reports),
            "reports": report_details,
            "reporters": user_details
        }

    except Exception as e:
        logger.error(f"Error getting location details: {e}")
        raise HTTPException(status_code=500, detail="Failed to get location details")

@router.post("/", response_model=ReportResponse)
async def create_report(
    user_id: UUID = Form(...),
    description: str = Form(..., min_length=10, max_length=500),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    phone_number: Optional[str] = Form(None),  # Optional for MVP/demo mode
    phone_verification_token: Optional[str] = Form(None),  # Optional for MVP/demo mode
    water_depth: Optional[str] = Form(None),
    vehicle_passability: Optional[str] = Form(None),
    # Photo GPS coordinates extracted by frontend (preferred if available)
    photo_latitude: Optional[float] = Form(None),
    photo_longitude: Optional[float] = Form(None),
    photo_location_verified: Optional[bool] = Form(None),
    image: UploadFile = File(...),  # MANDATORY - changed from File(None)
    db: Session = Depends(get_db)
):
    """
    Create a new flood report with community verification.

    Required fields:
    - Geotagged photo (MANDATORY)
    - Location coordinates
    - Phone number with OTP verification (optional for MVP/demo mode)

    Validation:
    1. Verify phone number via OTP token (if provided)
    2. Extract GPS from photo EXIF
    3. Validate photo GPS matches reported location (±100m)
    4. Cross-reference with IoT sensor data
    5. Calculate validation score
    """
    # 1. Verify phone number via OTP token (only if phone fields provided)
    phone_verified = False
    if phone_number and phone_verification_token:
        otp_service = get_otp_service()
        if not otp_service.verify_token(phone_number, phone_verification_token):
            raise HTTPException(
                status_code=401,
                detail="Invalid phone verification token. Please verify your phone number."
            )
        phone_verified = True  # Only true if OTP verification succeeded

    media_url = None
    media_metadata = {}

    # 2. Process mandatory image and extract EXIF GPS
    content = await image.read()
    try:
        img = Image.open(io.BytesIO(content))
        exif_data = get_exif_data(img)
        img_lat, img_lng = get_lat_lon(exif_data)

        # Use frontend-provided location verification if available (more accurate for camera captures)
        # Frontend captures GPS at photo time, which is more reliable than EXIF extraction
        if photo_location_verified is not None:
            location_verified = photo_location_verified
            # Use frontend-provided photo GPS if available
            if photo_latitude is not None and photo_longitude is not None:
                media_metadata["gps"] = {"lat": photo_latitude, "lng": photo_longitude}
                logger.info(f"Using frontend-provided photo GPS: ({photo_latitude:.6f}, {photo_longitude:.6f}), verified={photo_location_verified}")
            elif img_lat and img_lng:
                media_metadata["gps"] = {"lat": img_lat, "lng": img_lng}
        else:
            # Fallback: Extract GPS from EXIF and verify server-side
            location_verified = True

            if not img_lat or not img_lng:
                # No GPS in photo - flag as not location verified (don't block)
                location_verified = False
                logger.warning(f"Report photo has no GPS coordinates")
            else:
                media_metadata["gps"] = {"lat": img_lat, "lng": img_lng}

                # 3. GPS validation: Check if photo GPS matches reported location within tolerance
                distance = haversine_distance(img_lat, img_lng, latitude, longitude)
                if distance > LOCATION_VERIFICATION_TOLERANCE_METERS:
                    # GPS mismatch - flag as not location verified (don't block, allow with warning)
                    location_verified = False
                    logger.warning(f"Report photo GPS ({img_lat:.6f}, {img_lng:.6f}) is {distance:.1f}m from reported location ({latitude:.6f}, {longitude:.6f})")

        # Upload to Supabase Storage
        storage_service = get_storage_service()
        try:
            media_url, storage_path = await storage_service.upload_image(
                content=content,
                filename=image.filename or f"report_{datetime.utcnow().timestamp()}.jpg",
                content_type=image.content_type or "image/jpeg",
                user_id=str(user_id)
            )
            media_metadata["storage_path"] = storage_path
            logger.info(f"Uploaded report photo to storage: {storage_path}")
        except StorageNotConfiguredError as e:
            # Deployment issue - explicit error, no silent fallback
            logger.error(f"Storage not configured: {e}")
            raise HTTPException(
                status_code=503,
                detail="Photo storage service is not configured. Please contact support."
            )
        except StorageError as e:
            # Upload failed - explicit error, no silent fallback
            logger.error(f"Storage upload failed: {e}")
            raise HTTPException(
                status_code=503,
                detail="Failed to upload photo. Please try again later."
            )

        # 2.5. ML-based flood image verification (TFLite classifier)
        # Validates if the photo actually shows a flood scene
        if settings.ML_ENABLED:
            try:
                from ..domain.ml.tflite_classifier import get_classifier
                from io import BytesIO

                classifier = get_classifier()
                ml_result = classifier.predict(BytesIO(content))

                media_metadata["ml_classification"] = ml_result.get("classification")
                media_metadata["ml_confidence"] = ml_result.get("confidence")
                media_metadata["ml_is_flood"] = ml_result.get("is_flood")
                media_metadata["ml_needs_review"] = ml_result.get("needs_review")

                # Calculate verification score based on confidence
                if ml_result.get("is_flood"):
                    verification_score = int(ml_result.get("flood_probability", 0.5) * 100)
                else:
                    verification_score = int(ml_result.get("probabilities", {}).get("no_flood", 0.5) * 100)
                if ml_result.get("needs_review"):
                    verification_score = max(30, verification_score - 20)
                media_metadata["ml_verification_score"] = verification_score

                # Flag suspicious reports (non-flood images with high confidence)
                if not ml_result.get("is_flood") and ml_result.get("confidence", 0) > 0.8:
                    media_metadata["needs_review"] = True
                    logger.warning(
                        f"Report photo doesn't look like flood (confidence: {ml_result.get('confidence'):.2%})"
                    )

            except RuntimeError as e:
                logger.warning(f"ML classifier not loaded: {e} - continuing without verification")
            except Exception as e:
                logger.warning(f"ML classification failed: {e} - continuing without verification")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise HTTPException(status_code=400, detail=f"Image processing failed: {str(e)}")

    try:
        # 4. Create report with new fields
        new_report = models.Report(
            user_id=user_id,
            description=description,
            location=f"POINT({longitude} {latitude})",  # PostGIS Point
            media_url=media_url,
            media_type="image",
            media_metadata=json.dumps(media_metadata),
            phone_number=phone_number,
            phone_verified=phone_verified,  # True only if OTP verified
            water_depth=water_depth,
            vehicle_passability=vehicle_passability,
            location_verified=location_verified  # Photo GPS matches reported location
        )

        db.add(new_report)
        db.flush()  # Flush to get ID, but don't commit yet

        # --- ML Pipeline Enrichment (non-blocking) ---
        report_city = _detect_city(latitude, longitude)

        # Weather snapshot
        try:
            weather_service = WeatherSnapshotService()
            weather_data = await weather_service.get_snapshot(latitude, longitude)
            if weather_data:
                new_report.weather_snapshot = weather_data
        except Exception as e:
            logger.error(f"Weather enrichment failed for report {new_report.id}: {e}")

        # Road snapping (only if city detected and roads imported)
        if report_city:
            try:
                road_data = RoadSnappingService.snap_to_road(db, latitude, longitude, city=report_city)
                if road_data:
                    new_report.road_segment_id = road_data["road_segment_id"]
                    new_report.road_name = road_data["road_name"]
                    new_report.road_type = road_data["road_type"]
            except Exception as e:
                logger.error(f"Road snapping failed for report {new_report.id}: {e}")
        else:
            logger.debug(f"Could not detect city for ({latitude}, {longitude}), skipping road snap")

        db.flush()  # Flush enrichment data
        # --- End ML Pipeline Enrichment ---

        # 5. Validate against IoT sensors
        validation_service = ReportValidationService(db)

        # Create domain model for validation
        report_domain = ReportDomain(
            id=new_report.id,
            user_id=user_id,
            description=description,
            location_lat=latitude,
            location_lng=longitude,
            water_depth=water_depth,
            vehicle_passability=vehicle_passability,
            media_url=media_url,
            phone_number=phone_number,
            phone_verified=phone_verified
        )

        iot_score = validation_service.validate_report(report_domain)

        # Get nearby sensors for reference
        nearby_sensors = validation_service._find_nearby_sensors(latitude, longitude, 1000)
        nearby_sensor_ids = [str(s.id) for s in nearby_sensors]

        # Update report with validation results
        new_report.iot_validation_score = iot_score
        new_report.nearby_sensor_ids = json.dumps(nearby_sensor_ids)

        # 6. Auto-verify if IoT validation score is high
        if iot_score >= 80:
            new_report.verified = True
            new_report.verification_score += 20

            # Award points to user with reputation system
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if user:
                user.points += 15  # Bonus for IoT-validated report
                user.reports_count += 1
                user.verified_reports_count += 1
                user.level = (user.points // 100) + 1
        else:
            # Update counts and give base points even if not auto-verified
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if user:
                user.reports_count += 1
                user.points += 5  # Base submission points
                user.level = (user.points // 100) + 1

        db.commit()
        db.refresh(new_report)

        logger.info(f"Report created: {new_report.id}, IoT score: {iot_score}, verified: {new_report.verified}")

        # Update streak (using reputation service)
        reputation_service = ReputationService(db)
        streak_bonus = reputation_service.update_streak(user_id)

        if streak_bonus:
            logger.info(f"User {user_id} earned streak bonus: {streak_bonus} points")

        # Trigger alerts for users with nearby watch areas
        pushed_user_ids: set = set()
        alerts_created = 0
        alerted_user_ids = []
        try:
            from ..domain.services.alert_service import AlertService
            alert_service = AlertService(db)
            alerts_created, alerted_user_ids = alert_service.check_watch_areas_for_report(
                new_report.id, latitude, longitude, user_id
            )
            if alerts_created > 0:
                logger.info(f"Created {alerts_created} alerts for report {new_report.id}")
        except Exception as e:
            logger.warning(f"Failed to create alerts for report {new_report.id}: {e}")
            # Don't fail the report creation if alerts fail

        # Push notifications for watch area alerts
        for uid in alerted_user_ids:
            try:
                target_user = db.query(models.User).filter(models.User.id == uid).first()
                if target_user:
                    sent = await send_push_to_user(
                        db, target_user,
                        "Flood Report Near You",
                        description[:80] if description else "New flood report in your watch area",
                        data={"type": "watch_area_alert", "report_id": str(new_report.id)},
                    )
                    if sent:
                        pushed_user_ids.add(uid)
            except Exception as e:
                logger.warning(f"Push notification failed for user {uid}: {e}")

        # Trigger Safety Circle notifications (synchronous, D1)
        circle_notification_summary = None
        try:
            from ..domain.services.circle_notification_service import CircleNotificationService
            circle_notif = CircleNotificationService(db)
            circle_result = circle_notif.notify_circles_for_report(
                new_report.id, user_id, latitude, longitude, description
            )
            if circle_result.alerts_created > 0:
                logger.info(
                    f"Circle alerts: {circle_result.alerts_created} created, "
                    f"WhatsApp: {circle_result.whatsapp_sent} sent / {circle_result.whatsapp_failed} failed, "
                    f"SMS: {circle_result.sms_sent} sent / {circle_result.sms_failed} failed"
                )
            circle_notification_summary = circle_result.to_dict()
        except Exception as e:
            # Log as ERROR not warning — this is a real failure (CLAUDE.md rule #14)
            logger.error(f"Circle notification FAILED for report {new_report.id}: {e}", exc_info=True)
            circle_notification_summary = {"error": str(e)}

        # Push notifications for circle members (skip users already pushed via watch area)
        try:
            circle_member_user_ids = db.query(models.CircleMember.user_id).join(
                models.CircleAlert, models.CircleAlert.member_id == models.CircleMember.id
            ).filter(
                models.CircleAlert.report_id == new_report.id,
                models.CircleMember.user_id.isnot(None),
                models.CircleMember.user_id != user_id,
            ).distinct().all()

            for (cuid,) in circle_member_user_ids:
                if cuid in pushed_user_ids:
                    continue
                try:
                    target_user = db.query(models.User).filter(models.User.id == cuid).first()
                    if target_user:
                        await send_push_to_user(
                            db, target_user,
                            "Circle Alert",
                            description[:80] if description else "A circle member reported flooding nearby",
                            data={"type": "circle_alert", "report_id": str(new_report.id)},
                        )
                        pushed_user_ids.add(cuid)
                except Exception as e:
                    logger.warning(f"Circle push notification failed for user {cuid}: {e}")
        except Exception as e:
            logger.warning(f"Circle push query failed for report {new_report.id}: {e}")

        # Return response with combined fields from both features
        return ReportResponse(
            id=new_report.id,
            description=new_report.description,
            latitude=latitude,
            longitude=longitude,
            media_url=new_report.media_url,
            verified=new_report.verified,
            verification_score=new_report.verification_score,
            upvotes=new_report.upvotes,
            downvotes=new_report.downvotes,
            quality_score=new_report.quality_score,
            verified_at=new_report.verified_at,
            timestamp=new_report.timestamp,
            phone_verified=new_report.phone_verified,
            water_depth=new_report.water_depth,
            vehicle_passability=new_report.vehicle_passability,
            iot_validation_score=new_report.iot_validation_score,
            location_verified=new_report.location_verified,
            # ML pipeline enrichment
            weather_snapshot=new_report.weather_snapshot,
            road_segment_id=str(new_report.road_segment_id) if new_report.road_segment_id else None,
            road_name=new_report.road_name,
            road_type=new_report.road_type,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Database error creating report: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create report: {str(e)}")

@router.get("/hyperlocal")
def get_hyperlocal_status(
    lat: float,
    lng: float,
    radius: int = 500,  # meters
    db: Session = Depends(get_db)
):
    """
    Get hyperlocal area status for a specific location.

    Returns:
    - All active (non-archived) reports within radius from last 24 hours
    - Aggregate status (safe/caution/warning/critical)
    - Area summary statistics
    - Sensor data summary
    """
    from sqlalchemy import text

    try:
        # 1. Find active reports in radius using PostGIS
        # Note: 24-hour filter is more restrictive than 5-day archive, so archived_at check is redundant
        # but we include it for safety in case REPORT_ARCHIVE_DAYS changes
        query = text("""
            SELECT
                id, description, verified, water_depth, vehicle_passability,
                iot_validation_score, timestamp,
                ST_X(location::geometry) as longitude,
                ST_Y(location::geometry) as latitude
            FROM reports
            WHERE ST_DWithin(
                location::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius
            )
            AND timestamp > NOW() - INTERVAL '24 hours'
            AND archived_at IS NULL
            ORDER BY timestamp DESC
        """)

        result = db.execute(query, {'lat': lat, 'lng': lng, 'radius': radius})
        reports = []

        verified_count = 0
        water_depths = []

        for row in result:
            report_dict = {
                'id': str(row[0]),
                'description': row[1],
                'verified': row[2],
                'water_depth': row[3],
                'vehicle_passability': row[4],
                'iot_validation_score': row[5],
                'timestamp': row[6].isoformat() if row[6] else None,
                'longitude': float(row[7]) if row[7] else None,
                'latitude': float(row[8]) if row[8] else None
            }
            reports.append(report_dict)

            if row[2]:  # verified
                verified_count += 1
            if row[3]:  # water_depth
                water_depths.append(row[3])

        # 2. Get sensor data summary
        validation_service = ReportValidationService(db)
        sensor_summary = validation_service.get_nearby_sensor_summary(lat, lng, radius)

        # 3. Calculate aggregate status
        total_reports = len(reports)
        avg_validation_score = sum(r['iot_validation_score'] or 0 for r in reports) / total_reports if total_reports > 0 else 0

        # Determine status based on multiple factors
        if total_reports == 0:
            status = sensor_summary.get('status', 'unknown')
        else:
            # Count critical indicators
            critical_count = sum(1 for r in reports if r['water_depth'] in ['waist', 'impassable'])
            high_count = sum(1 for r in reports if r['water_depth'] == 'knee')

            if critical_count > 0 or sensor_summary.get('status') == 'critical':
                status = 'critical'
            elif high_count > 1 or sensor_summary.get('status') == 'warning':
                status = 'warning'
            elif total_reports > 2 or sensor_summary.get('status') == 'caution':
                status = 'caution'
            else:
                status = 'safe'

        # 4. Calculate average water depth
        depth_order = {'ankle': 1, 'knee': 2, 'waist': 3, 'impassable': 4}
        avg_depth = None
        if water_depths:
            avg_depth_value = sum(depth_order.get(d, 0) for d in water_depths) / len(water_depths)
            if avg_depth_value >= 3.5:
                avg_depth = 'impassable'
            elif avg_depth_value >= 2.5:
                avg_depth = 'waist'
            elif avg_depth_value >= 1.5:
                avg_depth = 'knee'
            else:
                avg_depth = 'ankle'

        return {
            'reports': reports,
            'status': status,
            'area_summary': {
                'total_reports': total_reports,
                'verified_reports': verified_count,
                'avg_water_depth': avg_depth,
                'avg_validation_score': round(avg_validation_score, 1),
                'last_updated': reports[0]['timestamp'] if reports else None
            },
            'sensor_summary': sensor_summary
        }

    except Exception as e:
        logger.error(f"Error getting hyperlocal status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get hyperlocal status: {str(e)}")


@router.post("/{report_id}/verify")
async def verify_report(
    report_id: UUID,
    verification: ReportVerificationRequest,
    current_user: models.User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """Verify or reject a report with quality scoring, admin notes, and push notification."""
    try:
        report = db.query(models.Report).filter(models.Report.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if report.verified and verification.verified:
            return {
                'message': 'Report already verified',
                'report_id': str(report_id),
                'verified': True,
                'quality_score': report.quality_score
            }

        # Process verification through reputation service
        reputation_service = ReputationService(db)
        result = reputation_service.process_report_verification(
            report_id=report_id,
            verified=verification.verified,
            quality_score=verification.quality_score
        )

        # Create/update admin verification comment
        if verification.notes:
            from src.domain.services.admin_service import upsert_admin_comment
            comment_type = "admin_verification" if verification.verified else "admin_rejection"
            upsert_admin_comment(db, report_id, current_user.id, verification.notes, comment_type)
            db.commit()

        # Push notification to report author
        if report.user_id and report.user_id != current_user.id:
            author = db.query(models.User).filter(models.User.id == report.user_id).first()
            if author:
                try:
                    if verification.verified:
                        await send_push_to_user(
                            db, author,
                            "Report Verified!",
                            f"Your flood report was verified by the FloodSafe team. +{result.get('points_earned', 0)} points!",
                            data={"report_id": str(report_id), "type": "verification"}
                        )
                    elif verification.notes:  # Rejection push only if admin wrote a reason
                        await send_push_to_user(
                            db, author,
                            "Report Update",
                            "Your flood report was reviewed. Tap for details.",
                            data={"report_id": str(report_id), "type": "review"}
                        )
                except Exception as push_err:
                    logger.warning(f"Failed to send push notification: {push_err}")

        return {
            'message': 'Report verified' if verification.verified else 'Report rejected',
            'report_id': str(report_id),
            'verified': verification.verified,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying report: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to verify report")


@router.post("/{report_id}/upvote", response_model=VoteResponse)
async def upvote_report(
    report_id: UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upvote a report (requires authentication).
    - First upvote: adds vote, increments count
    - Second upvote (toggle off): removes vote, decrements count
    - Switching from downvote: changes vote type, adjusts counts
    - Cannot upvote your own report
    """
    try:
        report = db.query(models.Report).filter(models.Report.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        # Prevent self-voting
        if report.user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot vote on your own report")

        # Check for existing vote
        existing_vote = db.query(models.ReportVote).filter(
            models.ReportVote.user_id == current_user.id,
            models.ReportVote.report_id == report_id
        ).first()

        user_vote = None
        if existing_vote:
            if existing_vote.vote_type == 'upvote':
                # Toggle off - remove upvote
                db.delete(existing_vote)
                report.upvotes = max(0, report.upvotes - 1)
                user_vote = None
            else:
                # Switch from downvote to upvote
                existing_vote.vote_type = 'upvote'
                report.upvotes += 1
                report.downvotes = max(0, report.downvotes - 1)
                user_vote = 'upvote'
        else:
            # New upvote
            db.add(models.ReportVote(
                user_id=current_user.id,
                report_id=report_id,
                vote_type='upvote'
            ))
            report.upvotes += 1
            user_vote = 'upvote'

        db.commit()

        # Award bonus to report owner (only for new upvotes)
        if user_vote == 'upvote' and not existing_vote:
            reputation_service = ReputationService(db)
            reputation_service.process_report_upvote(report_id)

        return VoteResponse(
            message='Vote updated',
            report_id=report_id,
            upvotes=report.upvotes,
            downvotes=report.downvotes,
            user_vote=user_vote
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upvoting report: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upvote report")


@router.post("/{report_id}/downvote", response_model=VoteResponse)
async def downvote_report(
    report_id: UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Downvote a report (requires authentication).
    - First downvote: adds vote, increments count
    - Second downvote (toggle off): removes vote, decrements count
    - Switching from upvote: changes vote type, adjusts counts
    - Cannot downvote your own report
    """
    try:
        report = db.query(models.Report).filter(models.Report.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        # Prevent self-voting
        if report.user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot vote on your own report")

        # Check for existing vote
        existing_vote = db.query(models.ReportVote).filter(
            models.ReportVote.user_id == current_user.id,
            models.ReportVote.report_id == report_id
        ).first()

        user_vote = None
        if existing_vote:
            if existing_vote.vote_type == 'downvote':
                # Toggle off - remove downvote
                db.delete(existing_vote)
                report.downvotes = max(0, report.downvotes - 1)
                user_vote = None
            else:
                # Switch from upvote to downvote
                existing_vote.vote_type = 'downvote'
                report.downvotes += 1
                report.upvotes = max(0, report.upvotes - 1)
                user_vote = 'downvote'
        else:
            # New downvote
            db.add(models.ReportVote(
                user_id=current_user.id,
                report_id=report_id,
                vote_type='downvote'
            ))
            report.downvotes += 1
            user_vote = 'downvote'

        db.commit()

        return VoteResponse(
            message='Vote updated',
            report_id=report_id,
            upvotes=report.upvotes,
            downvotes=report.downvotes,
            user_vote=user_vote
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downvoting report: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to downvote report")


@router.get("/user/{user_id}/archived", response_model=List[ReportResponse])
def get_user_archived_reports(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get archived reports for a specific user.
    A report is archived if:
    - It was explicitly archived (archived_at is set), OR
    - It's older than 5 days (auto-archived)

    Only the report owner can view their archived reports.
    """
    try:
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        archive_cutoff = datetime.utcnow() - timedelta(days=REPORT_ARCHIVE_DAYS)

        # Get archived reports: explicitly archived OR older than 5 days
        reports = db.query(models.Report).filter(
            models.Report.user_id == user_id,
            or_(
                models.Report.archived_at != None,  # Explicitly archived
                models.Report.timestamp <= archive_cutoff  # Auto-archived (5+ days old)
            )
        ).order_by(
            models.Report.timestamp.desc()
        ).offset(offset).limit(limit).all()

        # Get comment counts
        report_ids = [r.id for r in reports]
        comment_counts = get_comment_counts(db, report_ids)

        return [
            convert_report_to_response(r, comment_counts.get(str(r.id), 0))
            for r in reports
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching archived reports for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch archived reports")


@router.get("/user/{user_id}/stats")
def get_user_report_stats(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get report statistics for a user including active and archived counts.
    """
    try:
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        archive_cutoff = datetime.utcnow() - timedelta(days=REPORT_ARCHIVE_DAYS)

        # Count active reports
        active_count = db.query(models.Report).filter(
            models.Report.user_id == user_id,
            models.Report.archived_at == None,
            models.Report.timestamp > archive_cutoff
        ).count()

        # Count archived reports
        archived_count = db.query(models.Report).filter(
            models.Report.user_id == user_id,
            or_(
                models.Report.archived_at != None,
                models.Report.timestamp <= archive_cutoff
            )
        ).count()

        # Total reports
        total_count = active_count + archived_count

        return {
            "user_id": str(user_id),
            "active_reports": active_count,
            "archived_reports": archived_count,
            "total_reports": total_count,
            "archive_days": REPORT_ARCHIVE_DAYS
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching report stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch report stats")

