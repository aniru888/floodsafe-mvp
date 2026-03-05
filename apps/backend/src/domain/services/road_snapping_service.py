"""
Road snapping service for ML pipeline report enrichment.

Finds nearest OSM road segment within 200m of a report location.
Non-blocking: returns None if city_roads not imported or no match.
"""
import logging
from typing import Optional, Dict, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RoadSnappingService:
    """Snaps report coordinates to nearest OSM road segment via PostGIS."""

    @staticmethod
    def snap_to_road(
        db: Session,
        lat: float,
        lng: float,
        city: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find nearest road segment within 200m.

        Returns dict with road_segment_id, road_name, road_type, distance_m.
        Returns None in two cases (Rule #14 — distinguish expected vs unexpected):
        - Expected: no roads imported for city, or no road within 200m (debug log)
        - Unexpected: database error (error log)
        """
        try:
            # Guard: check if any roads exist for this city (avoid slow spatial query on empty table)
            count_result = db.execute(
                text("SELECT COUNT(*) FROM city_roads WHERE city = :city LIMIT 1"),
                {"city": city}
            )
            road_count = count_result.scalar()

            if not road_count:
                logger.info(f"No road data imported for {city} yet, skipping road snap")
                return None

            # Spatial query: find nearest road within 200m
            result = db.execute(
                text("""
                    SELECT id, name, road_type, is_underpass,
                           ST_Distance(
                               geometry::geography,
                               ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                           ) as distance_m
                    FROM city_roads
                    WHERE city = :city
                      AND ST_DWithin(
                          geometry::geography,
                          ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                          200
                      )
                    ORDER BY distance_m
                    LIMIT 1
                """),
                {"lat": lat, "lng": lng, "city": city}
            )

            row = result.fetchone()
            if not row:
                logger.debug(f"No road within 200m for ({lat}, {lng}) in {city}")
                return None

            return {
                "road_segment_id": row[0],  # UUID
                "road_name": row[1],        # str or None
                "road_type": row[2],        # str
                "distance_m": float(row[4]),
            }

        except Exception as e:
            logger.error(f"Road snapping query failed for ({lat}, {lng}) in {city}: {e}")
            return None
