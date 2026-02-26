"""
Alert service for managing flood alerts based on watch areas.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from typing import List, Tuple
import logging

from ...infrastructure import models

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, db: Session):
        self.db = db

    def check_watch_areas_for_report(self, report_id: UUID, latitude: float, longitude: float, reporter_user_id: UUID = None) -> Tuple[int, List[UUID]]:
        """
        Check all watch areas to see if the new report falls within any.
        Creates alerts for users whose watch areas are affected.
        Returns (count of alerts created, list of alerted user IDs).
        """
        # Use PostGIS ST_DWithin to find watch areas that contain the report location
        query = text("""
            SELECT wa.id, wa.user_id, wa.name, wa.radius
            FROM watch_areas wa
            WHERE ST_DWithin(
                wa.location::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                wa.radius
            )
        """)

        result = self.db.execute(query, {'lat': latitude, 'lng': longitude})
        alerts_created = 0
        alerted_user_ids: List[UUID] = []

        for row in result:
            watch_area_id, user_id, watch_area_name, radius = row

            # Don't alert the user who created the report
            if reporter_user_id and str(user_id) == str(reporter_user_id):
                continue

            # Check if alert already exists for this report + watch area combo
            existing = self.db.query(models.Alert).filter(
                models.Alert.report_id == report_id,
                models.Alert.watch_area_id == watch_area_id
            ).first()
            if existing:
                continue

            # Create alert
            alert = models.Alert(
                user_id=user_id,
                report_id=report_id,
                watch_area_id=watch_area_id,
                message=f"New flood report near {watch_area_name}"
            )
            self.db.add(alert)
            alerts_created += 1
            alerted_user_ids.append(user_id)
            logger.info(f"Created alert for user {user_id} in watch area {watch_area_name}")

        if alerts_created > 0:
            self.db.commit()

        return alerts_created, alerted_user_ids

    def get_user_alerts(self, user_id: UUID, unread_only: bool = False) -> List[dict]:
        """Get alerts for a user with report and watch area details."""
        query = self.db.query(models.Alert).filter(
            models.Alert.user_id == user_id
        )

        if unread_only:
            query = query.filter(models.Alert.is_read == False)

        alerts = query.order_by(models.Alert.created_at.desc()).limit(50).all()

        result = []
        for alert in alerts:
            report = self.db.query(models.Report).filter(models.Report.id == alert.report_id).first()
            watch_area = self.db.query(models.WatchArea).filter(models.WatchArea.id == alert.watch_area_id).first()

            result.append({
                'id': str(alert.id),
                'user_id': str(alert.user_id),
                'report_id': str(alert.report_id),
                'watch_area_id': str(alert.watch_area_id),
                'message': alert.message,
                'is_read': alert.is_read,
                'created_at': alert.created_at.isoformat(),
                'report_latitude': report.latitude if report else None,
                'report_longitude': report.longitude if report else None,
                'watch_area_name': watch_area.name if watch_area else None
            })

        return result

    def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread alerts for a user."""
        return self.db.query(models.Alert).filter(
            models.Alert.user_id == user_id,
            models.Alert.is_read == False
        ).count()

    def mark_as_read(self, alert_id: UUID, user_id: UUID) -> bool:
        """Mark a single alert as read."""
        alert = self.db.query(models.Alert).filter(
            models.Alert.id == alert_id,
            models.Alert.user_id == user_id
        ).first()

        if alert:
            alert.is_read = True
            self.db.commit()
            return True
        return False

    def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all alerts as read for a user. Returns count updated."""
        count = self.db.query(models.Alert).filter(
            models.Alert.user_id == user_id,
            models.Alert.is_read == False
        ).update({'is_read': True})
        self.db.commit()
        return count
