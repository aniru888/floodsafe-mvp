"""
Watch Area Service — personal pin CRUD with FHI compute, road snap, and historical context.

Design decisions:
- Max 25 pins per user
- FHI computed via calculate_fhi_for_location (async)
- Historical episode count via ST_DWithin on HistoricalFloodEpisode.centroid (2km radius)
- Nearest cluster from CandidateHotspot.centroid (closest within 5km)
- Road snapping via RoadSnappingService (optional — skipped gracefully if no road data)
- Alert radius label mapped to Float meters stored in WatchArea.alert_radius
- Columns not in the model (description, alert_radius_label, snap_distance_m) are NOT used
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from geoalchemy2 import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..ml.fhi_calculator import calculate_fhi_for_location
from ...infrastructure import models
from .road_snapping_service import RoadSnappingService

logger = logging.getLogger(__name__)

MAX_PINS_PER_USER = 25

# Maps frontend label → alert_radius float (meters) stored in WatchArea.alert_radius
ALERT_RADIUS_MAP: dict[str, float] = {
    "just_this_spot": 100.0,
    "my_street": 250.0,
    "my_neighborhood": 500.0,
    "wider_area": 1000.0,
}

HISTORICAL_SEARCH_RADIUS_M = 2_000   # 2 km radius for episode count
CLUSTER_SEARCH_RADIUS_M = 5_000      # 5 km radius for nearest cluster


class WatchAreaService:
    def __init__(self, db: Session):
        self.db = db

    async def create_personal_pin(
        self,
        user_id: UUID,
        latitude: float,
        longitude: float,
        name: str,
        city: Optional[str] = None,
        alert_radius_label: str = "my_neighborhood",
        visibility: str = "private",
    ) -> models.WatchArea:
        """
        Create a personal pin watch area for a user.

        Steps:
        1. Enforce 25-pin limit
        2. Map alert_radius_label → alert_radius float
        3. Compute FHI (async, best-effort)
        4. Count historical flood episodes within 2km
        5. Find nearest CandidateHotspot cluster within 5km
        6. Road snap (optional — skipped if no road data or city unknown)
        7. Persist and return
        """
        # 1. Enforce pin limit
        existing_count = (
            self.db.query(models.WatchArea)
            .filter(
                models.WatchArea.user_id == user_id,
                models.WatchArea.is_personal_hotspot == True,  # noqa: E712
            )
            .count()
        )
        if existing_count >= MAX_PINS_PER_USER:
            raise ValueError(
                f"Pin limit reached. You can have at most {MAX_PINS_PER_USER} personal pins."
            )

        # 2. Resolve alert radius
        alert_radius = ALERT_RADIUS_MAP.get(alert_radius_label, 500.0)

        # 3. Compute FHI (best-effort)
        fhi_score: Optional[float] = None
        fhi_level: Optional[str] = None
        fhi_components: Optional[dict] = None
        weather_snapshot: Optional[dict] = None

        try:
            fhi_dict = await calculate_fhi_for_location(latitude, longitude)
            fhi_score = fhi_dict.get("fhi_score")
            fhi_level = fhi_dict.get("fhi_level")
            fhi_components = {
                k: fhi_dict[k]
                for k in ("components", "monsoon_modifier", "rain_gated", "correction_factor",
                          "precip_prob_max", "data_source", "precip_24h_mm",
                          "precip_3d_mm", "hourly_max_mm")
                if k in fhi_dict
            }
            weather_snapshot = fhi_dict
        except Exception as exc:
            logger.warning(
                "FHI calculation failed for pin (%.4f, %.4f): %s — storing without FHI",
                latitude,
                longitude,
                exc,
            )

        # 4. Historical episode count within 2km
        historical_episode_count = self._count_historical_episodes(latitude, longitude)

        # 5. Nearest CandidateHotspot cluster within 5km
        nearest_cluster_id = self._find_nearest_cluster(latitude, longitude, city)

        # 6. Road snap (optional)
        road_segment_id: Optional[UUID] = None
        road_name: Optional[str] = None
        snapped_location_wkt: Optional[WKTElement] = None

        if city:
            try:
                snap = RoadSnappingService.snap_to_road(self.db, latitude, longitude, city)
                if snap:
                    raw_id = snap.get("road_segment_id")
                    road_segment_id = UUID(str(raw_id)) if raw_id else None
                    road_name = snap.get("road_name")
                    # road snapping returns the point itself; store as snapped_location
                    snapped_location_wkt = WKTElement(
                        f"POINT({longitude} {latitude})", srid=4326
                    )
            except Exception as exc:
                logger.debug("Road snap skipped for pin: %s", exc)

        # 7. Persist
        point_wkt = WKTElement(f"POINT({longitude} {latitude})", srid=4326)
        now = datetime.utcnow()

        pin = models.WatchArea(
            user_id=user_id,
            name=name,
            location=point_wkt,
            radius=alert_radius,           # repurpose radius for alert_radius as well
            city=city,
            is_personal_hotspot=True,
            source="personal_pin",
            visibility=visibility,
            alert_radius=alert_radius,
            fhi_score=fhi_score,
            fhi_level=fhi_level,
            fhi_components=fhi_components,
            fhi_updated_at=now if fhi_score is not None else None,
            weather_snapshot=weather_snapshot,
            historical_episode_count=historical_episode_count,
            nearest_cluster_id=nearest_cluster_id,
            road_segment_id=road_segment_id,
            road_name=road_name,
            snapped_location=snapped_location_wkt,
            created_at=now,
            updated_at=now,
        )

        self.db.add(pin)
        self.db.commit()
        self.db.refresh(pin)

        # Record initial FHI history entry if FHI was computed
        if fhi_score is not None and fhi_level is not None:
            self._record_fhi_history(pin, fhi_score, fhi_level, fhi_components)

        return pin

    async def refresh_pin_fhi(self, pin: models.WatchArea) -> models.WatchArea:
        """
        Re-compute FHI for an existing pin and update the model + history table.
        Raises ValueError if the pin has no location.
        """
        lat = pin.latitude
        lng = pin.longitude
        if lat is None or lng is None:
            raise ValueError(f"Pin {pin.id} has no extractable coordinates.")

        try:
            fhi_dict = await calculate_fhi_for_location(lat, lng)
        except Exception as exc:
            raise RuntimeError(f"FHI refresh failed for pin {pin.id}: {exc}") from exc

        fhi_score = fhi_dict.get("fhi_score")
        fhi_level = fhi_dict.get("fhi_level")
        fhi_components = {
            k: fhi_dict[k]
            for k in ("components", "monsoon_modifier", "rain_gated", "correction_factor",
                      "precip_prob_max", "data_source", "precip_24h_mm",
                      "precip_3d_mm", "hourly_max_mm")
            if k in fhi_dict
        }

        pin.fhi_score = fhi_score
        pin.fhi_level = fhi_level
        pin.fhi_components = fhi_components
        pin.fhi_updated_at = datetime.utcnow()
        pin.weather_snapshot = fhi_dict
        pin.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(pin)

        if fhi_score is not None and fhi_level is not None:
            self._record_fhi_history(pin, fhi_score, fhi_level, fhi_components)

        return pin

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _count_historical_episodes(self, lat: float, lng: float) -> int:
        """Count HistoricalFloodEpisode centroids within 2km of the given point."""
        try:
            result = self.db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM historical_flood_episodes
                    WHERE ST_DWithin(
                        centroid::geography,
                        ST_MakePoint(:lng, :lat)::geography,
                        :radius
                    )
                """),
                {"lat": lat, "lng": lng, "radius": HISTORICAL_SEARCH_RADIUS_M},
            )
            count = result.scalar()
            return int(count) if count else 0
        except Exception as exc:
            logger.warning("Historical episode count failed: %s", exc)
            return 0

    def _find_nearest_cluster(
        self, lat: float, lng: float, city: Optional[str]
    ) -> Optional[UUID]:
        """
        Find the nearest CandidateHotspot centroid within 5km.
        Filters by city when provided. Returns the cluster id or None.
        """
        try:
            city_filter = "AND city = :city" if city else ""
            result = self.db.execute(
                text(f"""
                    SELECT id
                    FROM candidate_hotspots
                    WHERE ST_DWithin(
                        centroid::geography,
                        ST_MakePoint(:lng, :lat)::geography,
                        :radius
                    )
                    {city_filter}
                    ORDER BY centroid::geography <-> ST_MakePoint(:lng, :lat)::geography
                    LIMIT 1
                """),
                {"lat": lat, "lng": lng, "radius": CLUSTER_SEARCH_RADIUS_M, "city": city},
            )
            row = result.fetchone()
            if row:
                return UUID(str(row[0]))
            return None
        except Exception as exc:
            logger.warning("Nearest cluster lookup failed: %s", exc)
            return None

    def _record_fhi_history(
        self,
        pin: models.WatchArea,
        fhi_score: float,
        fhi_level: str,
        fhi_components: Optional[dict],
    ) -> None:
        """Append a row to watch_area_fhi_history for this pin."""
        try:
            history_entry = models.WatchAreaFhiHistory(
                watch_area_id=pin.id,
                fhi_score=fhi_score,
                fhi_level=fhi_level,
                fhi_components=fhi_components,
                recorded_at=datetime.utcnow(),
            )
            self.db.add(history_entry)
            self.db.commit()
        except Exception as exc:
            logger.warning("FHI history record failed for pin %s: %s", pin.id, exc)
            self.db.rollback()
