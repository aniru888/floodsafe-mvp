"""
External Alerts Module

Aggregates flood alerts from multiple external sources:
- RSS news feeds (Hindustan Times, Times of India, etc.)
- IMD (India Meteorological Department) - weather warnings
- CWC (Central Water Commission) - flood forecasts
- Twitter/X - social media alerts
- Telegram - public channels

Usage:
    from src.domain.services.external_alerts import AlertAggregator

    aggregator = AlertAggregator(db_session)
    results = await aggregator.fetch_all_alerts(city="delhi")

Scheduler:
    from src.domain.services.external_alerts import start_scheduler, stop_scheduler

    # In FastAPI startup:
    start_scheduler()

    # In FastAPI shutdown:
    stop_scheduler()
"""

from .base_fetcher import BaseFetcher, ExternalAlertCreate
from .rss_fetcher import RSSFetcher
from .imd_fetcher import IMDFetcher
from .twitter_fetcher import TwitterFetcher
from .cwc_scraper import CWCScraper
from .pub_fetcher import PUBFetcher
from .aggregator import AlertAggregator
from .scheduler import AlertScheduler, start_scheduler, stop_scheduler, get_scheduler

__all__ = [
    "BaseFetcher",
    "ExternalAlertCreate",
    "RSSFetcher",
    "IMDFetcher",
    "TwitterFetcher",
    "CWCScraper",
    "PUBFetcher",
    "AlertAggregator",
    "AlertScheduler",
    "start_scheduler",
    "stop_scheduler",
    "get_scheduler",
]
