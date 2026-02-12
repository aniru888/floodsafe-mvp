"""
External Alerts Scheduler - Background job scheduler for fetching alerts.

Uses APScheduler to run fetchers at configured intervals:
- RSS: Every 15 minutes
- IMD: Every 60 minutes
- Twitter: Every 30 minutes
- CWC: Every 120 minutes

Usage:
    from src.domain.services.external_alerts.scheduler import AlertScheduler

    # In FastAPI startup:
    scheduler = AlertScheduler()
    scheduler.start()

    # In FastAPI shutdown:
    scheduler.stop()
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .aggregator import AlertAggregator
from src.core.config import settings

logger = logging.getLogger(__name__)


# Default cities to refresh
DEFAULT_CITIES = ["delhi", "bangalore", "yogyakarta"]


class AlertScheduler:
    """
    Scheduler for background alert fetching jobs.

    Runs fetchers at configured intervals to keep alerts fresh.
    """

    def __init__(self):
        """Initialize scheduler."""
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._running = False

        # Create shared async engine and session factory (reused across jobs)
        database_url = settings.DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        self._engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,  # Verify connections before use
            pool_size=5,
            max_overflow=10,
        )
        self._async_session = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("[Scheduler] Already running")
            return

        logger.info("[Scheduler] Starting external alerts scheduler...")

        self.scheduler = AsyncIOScheduler()

        # Schedule RSS fetcher (most frequent - free, no rate limits)
        self.scheduler.add_job(
            self._run_rss_fetch,
            IntervalTrigger(minutes=settings.ALERT_REFRESH_RSS_MINUTES),
            id="rss_fetch",
            name="RSS News Fetch",
            replace_existing=True,
        )

        # Schedule IMD fetcher
        self.scheduler.add_job(
            self._run_imd_fetch,
            IntervalTrigger(minutes=settings.ALERT_REFRESH_IMD_MINUTES),
            id="imd_fetch",
            name="IMD Weather Fetch",
            replace_existing=True,
        )

        # Schedule Twitter fetcher (less frequent due to rate limits)
        self.scheduler.add_job(
            self._run_twitter_fetch,
            IntervalTrigger(minutes=settings.ALERT_REFRESH_TWITTER_MINUTES),
            id="twitter_fetch",
            name="Twitter Fetch",
            replace_existing=True,
        )

        # Schedule CWC scraper (least frequent - scraping should be polite)
        self.scheduler.add_job(
            self._run_cwc_fetch,
            IntervalTrigger(minutes=settings.ALERT_REFRESH_CWC_MINUTES),
            id="cwc_fetch",
            name="CWC Flood Forecast Fetch",
            replace_existing=True,
        )

        # Schedule cleanup (once per day)
        self.scheduler.add_job(
            self._run_cleanup,
            IntervalTrigger(hours=24),
            id="cleanup",
            name="Expired Alert Cleanup",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True

        logger.info("[Scheduler] External alerts scheduler started")
        logger.info(f"  RSS: every {settings.ALERT_REFRESH_RSS_MINUTES} minutes")
        logger.info(f"  IMD: every {settings.ALERT_REFRESH_IMD_MINUTES} minutes")
        logger.info(f"  Twitter: every {settings.ALERT_REFRESH_TWITTER_MINUTES} minutes")
        logger.info(f"  CWC: every {settings.ALERT_REFRESH_CWC_MINUTES} minutes")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler and self._running:
            logger.info("[Scheduler] Stopping external alerts scheduler...")
            self.scheduler.shutdown(wait=True)  # Wait for running jobs to complete
            self._running = False
            logger.info("[Scheduler] Scheduler stopped")

    async def _get_db_session(self) -> AsyncSession:
        """Get a database session from the shared pool."""
        return self._async_session()

    async def _run_fetch(self, sources: list[str], job_name: str):
        """
        Run fetch for specific sources.

        Args:
            sources: List of source names to fetch
            job_name: Name for logging
        """
        logger.info(f"[Scheduler] Starting {job_name}...")
        start_time = datetime.now(timezone.utc)

        try:
            async with await self._get_db_session() as db:
                aggregator = AlertAggregator(db)

                for city in DEFAULT_CITIES:
                    try:
                        result = await aggregator.fetch_all_alerts(
                            city=city,
                            sources=sources
                        )
                        logger.info(
                            f"[Scheduler] {job_name} for {city}: "
                            f"{result.total_alerts_found} found, "
                            f"{result.total_alerts_new} new"
                        )
                    except Exception as e:
                        logger.error(f"[Scheduler] {job_name} failed for {city}: {e}")

        except Exception as e:
            logger.error(f"[Scheduler] {job_name} failed: {e}")

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"[Scheduler] {job_name} completed in {duration:.1f}s")

    async def _run_rss_fetch(self):
        """Run RSS feed fetch job."""
        if settings.RSS_FEEDS_ENABLED:
            await self._run_fetch(["rss"], "RSS Fetch")
        else:
            logger.debug("[Scheduler] RSS fetch skipped (disabled)")

    async def _run_imd_fetch(self):
        """Run IMD fetch job."""
        if settings.IMD_API_ENABLED:
            await self._run_fetch(["imd"], "IMD Fetch")
        else:
            logger.debug("[Scheduler] IMD fetch skipped (disabled)")

    async def _run_twitter_fetch(self):
        """Run Twitter fetch job."""
        if settings.TWITTER_BEARER_TOKEN:
            await self._run_fetch(["twitter"], "Twitter Fetch")
        else:
            logger.debug("[Scheduler] Twitter fetch skipped (no bearer token)")

    async def _run_cwc_fetch(self):
        """Run CWC scraper job."""
        if settings.CWC_SCRAPER_ENABLED:
            await self._run_fetch(["cwc"], "CWC Fetch")
        else:
            logger.debug("[Scheduler] CWC fetch skipped (disabled)")

    async def _run_cleanup(self):
        """Run cleanup of expired alerts."""
        logger.info("[Scheduler] Running expired alert cleanup...")

        try:
            async with await self._get_db_session() as db:
                aggregator = AlertAggregator(db)
                deleted = await aggregator.cleanup_expired_alerts()
                logger.info(f"[Scheduler] Cleanup complete: {deleted} alerts removed")
        except Exception as e:
            logger.error(f"[Scheduler] Cleanup failed: {e}")


# Global scheduler instance
_scheduler: Optional[AlertScheduler] = None


def get_scheduler() -> AlertScheduler:
    """Get or create global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AlertScheduler()
    return _scheduler


def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
