"""
Alert Aggregator - Combines all external alert fetchers and stores results.

Features:
- Runs all enabled fetchers concurrently
- Handles deduplication by source_id
- Stores new alerts and updates existing ones
- Returns statistics on fetch results
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .base_fetcher import BaseFetcher, ExternalAlertCreate
from .pub_fetcher import PUBFetcher
from .rss_fetcher import RSSFetcher
from .imd_fetcher import IMDFetcher
from .twitter_fetcher import TwitterFetcher
from .cwc_scraper import CWCScraper
from .gdelt_fetcher import GDELTFetcher
from .gdacs_fetcher import GDACSFetcher
from src.infrastructure.models import ExternalAlert

logger = logging.getLogger(__name__)


class FetchResult:
    """Result of a fetcher run."""

    def __init__(self, source: str):
        self.source = source
        self.success = False
        self.alerts_found = 0
        self.alerts_new = 0
        self.alerts_updated = 0
        self.error: Optional[str] = None
        self.duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "success": self.success,
            "alerts_found": self.alerts_found,
            "alerts_new": self.alerts_new,
            "alerts_updated": self.alerts_updated,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class AggregatorResult:
    """Result of aggregator run."""

    def __init__(self):
        self.fetcher_results: list[FetchResult] = []
        self.total_alerts_found = 0
        self.total_alerts_new = 0
        self.total_alerts_updated = 0
        self.duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "total_alerts_found": self.total_alerts_found,
            "total_alerts_new": self.total_alerts_new,
            "total_alerts_updated": self.total_alerts_updated,
            "duration_ms": self.duration_ms,
            "fetchers": [r.to_dict() for r in self.fetcher_results],
        }


class AlertAggregator:
    """
    Aggregates flood alerts from multiple external sources.

    Usage:
        aggregator = AlertAggregator(db_session)
        result = await aggregator.fetch_all_alerts(city="delhi")
        print(f"Found {result.total_alerts_found} alerts")
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize aggregator with database session.

        Args:
            db: SQLAlchemy async session
        """
        self.db = db

        # Initialize all fetchers
        self.fetchers: list[BaseFetcher] = [
            RSSFetcher(),
            IMDFetcher(),
            TwitterFetcher(),
            CWCScraper(),
            GDELTFetcher(),    # News intelligence from GDELT
            GDACSFetcher(),    # UN disaster alerts
            PUBFetcher(),      # Singapore PUB flood alerts
        ]

    def get_enabled_fetchers(self) -> list[BaseFetcher]:
        """Get list of enabled fetchers."""
        return [f for f in self.fetchers if f.is_enabled()]

    def get_source_status(self) -> dict:
        """
        Get status of all sources.

        Returns:
            Dict with source names and their enabled status
        """
        return {
            f.get_source_name(): {
                "enabled": f.is_enabled(),
                "name": self._get_source_display_name(f.get_source_name()),
            }
            for f in self.fetchers
        }

    def _get_source_display_name(self, source: str) -> str:
        """Get display name for a source."""
        names = {
            "rss": "News Feeds",
            "imd": "IMD Weather",
            "twitter": "Twitter/X",
            "cwc": "CWC Flood Forecast",
            "gdelt": "GDELT News",
            "gdacs": "UN GDACS",
            "pub": "PUB Singapore",
        }
        return names.get(source, source.upper())

    async def fetch_all_alerts(
        self,
        city: str,
        sources: Optional[list[str]] = None
    ) -> AggregatorResult:
        """
        Fetch alerts from all enabled sources for a city.

        Args:
            city: City identifier ('delhi', 'bangalore')
            sources: Optional list of specific sources to fetch

        Returns:
            AggregatorResult with fetch statistics
        """
        start_time = datetime.now(timezone.utc)
        result = AggregatorResult()

        # Filter fetchers
        fetchers = self.get_enabled_fetchers()
        if sources:
            fetchers = [f for f in fetchers if f.get_source_name() in sources]

        if not fetchers:
            logger.warning("[Aggregator] No enabled fetchers available")
            return result

        logger.info(f"[Aggregator] Starting fetch for {city} with {len(fetchers)} fetchers")

        # Run all fetchers concurrently
        tasks = [
            self._run_fetcher(fetcher, city)
            for fetcher in fetchers
        ]
        fetcher_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for fetch_result in fetcher_results:
            if isinstance(fetch_result, Exception):
                logger.error(f"[Aggregator] Fetcher error: {fetch_result}")
                continue

            result.fetcher_results.append(fetch_result)
            result.total_alerts_found += fetch_result.alerts_found
            result.total_alerts_new += fetch_result.alerts_new
            result.total_alerts_updated += fetch_result.alerts_updated

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        result.duration_ms = (end_time - start_time).total_seconds() * 1000

        logger.info(
            f"[Aggregator] Fetch complete: {result.total_alerts_found} found, "
            f"{result.total_alerts_new} new, {result.total_alerts_updated} updated "
            f"in {result.duration_ms:.0f}ms"
        )

        return result

    async def _run_fetcher(self, fetcher: BaseFetcher, city: str) -> FetchResult:
        """
        Run a single fetcher and store results.

        Args:
            fetcher: Fetcher instance
            city: City identifier

        Returns:
            FetchResult with statistics
        """
        source = fetcher.get_source_name()
        result = FetchResult(source)
        start_time = datetime.now(timezone.utc)

        try:
            # Fetch alerts
            alerts = await fetcher.fetch(city)
            result.alerts_found = len(alerts)

            # Store alerts in database
            if alerts:
                new_count, updated_count = await self._store_alerts(alerts)
                result.alerts_new = new_count
                result.alerts_updated = updated_count

            result.success = True

        except Exception as e:
            logger.error(f"[Aggregator] {source} fetcher failed: {e}")
            result.error = str(e)

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        result.duration_ms = (end_time - start_time).total_seconds() * 1000

        return result

    async def _store_alerts(self, alerts: list[ExternalAlertCreate]) -> tuple[int, int]:
        """
        Store alerts in database with upsert logic.

        Args:
            alerts: List of alerts to store

        Returns:
            Tuple of (new_count, updated_count)
        """
        new_count = 0
        updated_count = 0

        for alert in alerts:
            try:
                # Check if alert already exists by source_id
                if alert.source_id:
                    existing = await self.db.execute(
                        select(ExternalAlert).where(
                            ExternalAlert.source_id == alert.source_id
                        )
                    )
                    existing_alert = existing.scalar_one_or_none()

                    if existing_alert:
                        # Update existing alert if message changed
                        if existing_alert.message != alert.message:
                            await self.db.execute(
                                update(ExternalAlert)
                                .where(ExternalAlert.id == existing_alert.id)
                                .values(
                                    title=alert.title,
                                    message=alert.message,
                                    severity=alert.severity,
                                    raw_data=alert.raw_data,
                                )
                            )
                            updated_count += 1
                        continue

                # Insert new alert
                new_alert = ExternalAlert(
                    source=alert.source,
                    source_id=alert.source_id,
                    source_name=alert.source_name,
                    city=alert.city,
                    title=alert.title,
                    message=alert.message,
                    severity=alert.severity,
                    url=alert.url,
                    latitude=alert.latitude,
                    longitude=alert.longitude,
                    raw_data=alert.raw_data,
                    expires_at=alert.expires_at,
                )
                self.db.add(new_alert)
                new_count += 1

            except Exception as e:
                logger.error(f"[Aggregator] Error storing alert: {e}")
                continue

        # Commit all changes
        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"[Aggregator] Commit failed: {e}")
            await self.db.rollback()
            return 0, 0

        return new_count, updated_count

    async def cleanup_expired_alerts(self, city: Optional[str] = None) -> int:
        """
        Remove expired alerts from database.

        Args:
            city: Optional city filter

        Returns:
            Number of alerts deleted
        """
        now = datetime.now(timezone.utc)

        query = delete(ExternalAlert).where(
            ExternalAlert.expires_at < now
        )

        if city:
            query = query.where(ExternalAlert.city == city)

        try:
            result = await self.db.execute(query)
            await self.db.commit()
            deleted = result.rowcount
            logger.info(f"[Aggregator] Cleaned up {deleted} expired alerts")
            return deleted
        except Exception as e:
            logger.error(f"[Aggregator] Cleanup failed: {e}")
            await self.db.rollback()
            return 0

    async def get_alerts(
        self,
        city: str,
        source: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[ExternalAlert]:
        """
        Get alerts from database.

        Args:
            city: City identifier
            source: Optional source filter
            severity: Optional severity filter
            limit: Maximum number of alerts
            offset: Offset for pagination

        Returns:
            List of ExternalAlert objects
        """
        query = select(ExternalAlert).where(
            ExternalAlert.city == city
        ).order_by(
            ExternalAlert.created_at.desc()
        )

        if source:
            query = query.where(ExternalAlert.source == source)

        if severity:
            query = query.where(ExternalAlert.severity == severity)

        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_alert_count_by_source(self, city: str) -> dict:
        """
        Get alert counts grouped by source.

        Args:
            city: City identifier

        Returns:
            Dict with source -> count mapping
        """
        from sqlalchemy import func

        query = select(
            ExternalAlert.source,
            func.count(ExternalAlert.id).label('count')
        ).where(
            ExternalAlert.city == city
        ).group_by(
            ExternalAlert.source
        )

        result = await self.db.execute(query)
        return {row.source: row.count for row in result.all()}
