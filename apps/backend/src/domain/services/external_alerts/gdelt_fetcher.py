"""
GDELT Fetcher - Fetches flood-related news from GDELT DOC 2.0 API.

GDELT (Global Database of Events, Language, and Tone) monitors news media
from around the world in 100+ languages, updating every 15 minutes.

CRITICAL LIMITATION: GDELT only supports country-level filtering (India),
NOT city-level (Delhi). We solve this by:
1. Forcing "delhi" in the query string
2. Post-filtering results with DelhiFloodRelevanceScorer

Reference: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
API Documentation: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

No API keys required - completely free.
"""

import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import json

from .base_fetcher import BaseFetcher, ExternalAlertCreate
from .relevance_scorer import get_scorer_for_city
from src.core.config import settings

logger = logging.getLogger(__name__)


# GDELT DOC 2.0 API endpoint
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Maximum articles to fetch per request
MAX_ARTICLES = 50

# Maximum age of articles (hours)
MAX_ARTICLE_AGE_HOURS = 72


class GDELTFetcher(BaseFetcher):
    """
    Fetches flood news from GDELT DOC 2.0 API.

    IMPORTANT: GDELT only supports country filtering, not city.
    We force Delhi keywords in the query AND post-filter results
    through the relevance scorer.
    """

    # City-specific query configurations
    # The query FORCES city mention alongside flood keywords
    CITY_QUERIES = {
        "delhi": {
            # Query forces "delhi" OR NCR to appear WITH flood keywords
            # Using GDELT's query syntax with boolean operators
            "query": '("delhi" OR "new delhi" OR "ncr" OR "national capital") AND (flood OR waterlog OR waterlogging OR inundation OR "heavy rain" OR deluge OR submerged)',
            "sourcecountry": "IN",  # India
            "sourcelang": "english",
        },
        "bangalore": {
            "query": '("bangalore" OR "bengaluru") AND (flood OR waterlog OR waterlogging OR rain OR inundation)',
            "sourcecountry": "IN",
            "sourcelang": "english",
        },
        "yogyakarta": {
            "query": '("yogyakarta" OR "jogjakarta" OR "jogja") AND (banjir OR flood OR genangan OR "heavy rain" OR waterlog)',
            "sourcecountry": "ID",
            "sourcelang": "english",
        },
        "singapore": {
            "query": '("singapore") AND (flood OR "flash flood" OR ponding OR "heavy rain" OR waterlog)',
            "sourcecountry": "SG",
            "sourcelang": "english",
        },
    }

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize GDELT fetcher.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries

    def get_source_name(self) -> str:
        return "gdelt"

    def is_enabled(self) -> bool:
        # GDELT is always enabled - no API keys required
        return getattr(settings, 'GDELT_ENABLED', True)

    async def fetch(self, city: str) -> list[ExternalAlertCreate]:
        """
        Fetch and filter flood news from GDELT for a city.

        Args:
            city: City identifier ('delhi', 'bangalore')

        Returns:
            List of high-quality, city-relevant ExternalAlertCreate objects
        """
        self.log_fetch_start(city)

        city_lower = city.lower()
        if city_lower not in self.CITY_QUERIES:
            logger.warning(f"[GDELT] No query configured for city: {city}")
            return []

        # Step 1: Fetch from GDELT API
        raw_articles = await self._fetch_gdelt_api(city_lower)
        logger.info(f"[GDELT] Raw articles from API: {len(raw_articles)}")

        # Step 2: Convert to alerts
        alerts = self._convert_to_alerts(raw_articles, city_lower)
        logger.info(f"[GDELT] Converted to alerts: {len(alerts)}")

        # Step 3: Post-filter with relevance scorer (CRITICAL for quality)
        scorer = get_scorer_for_city(city_lower)
        filtered_alerts = []

        for alert in alerts:
            score, reason = scorer.score(alert.title, alert.message)

            if score >= 0.7:  # HIGH QUALITY ONLY
                # Add relevance metadata
                if alert.raw_data is None:
                    alert.raw_data = {}
                alert.raw_data["relevance_score"] = score
                alert.raw_data["relevance_reason"] = reason
                filtered_alerts.append(alert)
                logger.debug(f"[GDELT] Accepted (score={score:.2f}): {alert.title[:60]}...")
            else:
                logger.debug(f"[GDELT] Rejected (score={score:.2f}): {alert.title[:60]}... ({reason})")

        self.log_fetch_complete(city, len(filtered_alerts))
        return filtered_alerts

    async def _fetch_gdelt_api(self, city: str) -> list[dict]:
        """
        Make request to GDELT DOC 2.0 API.

        Args:
            city: City identifier

        Returns:
            List of article dictionaries from GDELT
        """
        config = self.CITY_QUERIES[city]

        # Calculate time range (last MAX_ARTICLE_AGE_HOURS hours)
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

        # Build API parameters
        params = {
            "query": config["query"],
            "mode": "artlist",  # Get article list with metadata
            "format": "json",
            "maxrecords": str(MAX_ARTICLES),
            "sort": "datedesc",  # Most recent first
            "timespan": f"{MAX_ARTICLE_AGE_HOURS}h",
        }

        # Add optional filters
        if "sourcecountry" in config:
            params["sourcecountry"] = config["sourcecountry"]
        if "sourcelang" in config:
            params["sourcelang"] = config["sourcelang"]

        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        GDELT_DOC_API,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={"User-Agent": "FloodSafe/1.0 (+https://floodsafe.app)"}
                    ) as response:
                        if response.status != 200:
                            logger.warning(f"[GDELT] HTTP {response.status} (attempt {attempt}/{self.max_retries})")
                            if attempt < self.max_retries:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return []

                        text = await response.text()

                        # GDELT sometimes returns HTML error pages
                        if text.startswith("<!DOCTYPE") or text.startswith("<html"):
                            logger.warning(f"[GDELT] Received HTML instead of JSON")
                            return []

                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError as e:
                            logger.warning(f"[GDELT] JSON decode error: {e}")
                            return []

                        # Extract articles from response
                        articles = data.get("articles", [])
                        return articles

            except asyncio.TimeoutError:
                logger.warning(f"[GDELT] Timeout (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
            except aiohttp.ClientError as e:
                logger.warning(f"[GDELT] Client error: {e} (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"[GDELT] Unexpected error: {e}")
                break

        return []

    def _convert_to_alerts(self, articles: list[dict], city: str) -> list[ExternalAlertCreate]:
        """
        Convert GDELT article objects to ExternalAlertCreate.

        Args:
            articles: List of article dicts from GDELT API
            city: City identifier

        Returns:
            List of ExternalAlertCreate objects
        """
        alerts = []

        for article in articles:
            try:
                # Extract fields from GDELT article format
                title = article.get("title", "").strip()
                url = article.get("url", "")
                source_name = article.get("domain", article.get("source", "GDELT"))
                seendate = article.get("seendate", "")

                # Skip articles without title
                if not title:
                    continue

                # Build message from title (GDELT doesn't provide full article text)
                # In DOC API, 'title' is the headline
                message = title

                # If socialimage exists, note it in the message
                if article.get("socialimage"):
                    message += f"\n\n[Image available: {article.get('socialimage')}]"

                # Parse date (GDELT uses format: YYYYMMDDTHHMMSSZ)
                pub_date = self._parse_gdelt_date(seendate)

                # Generate unique source_id
                source_id = self.generate_source_id("gdelt", url, seendate)

                # Infer severity from content
                severity = self._infer_severity(title)

                # Extract language
                language = article.get("language", "English")

                # Create alert
                alert = ExternalAlertCreate(
                    source="gdelt",
                    source_id=source_id,
                    source_name=source_name,
                    city=city,
                    title=self.truncate_text(title, 500),
                    message=self.truncate_text(message, 2000),
                    severity=severity,
                    url=url,
                    raw_data={
                        "gdelt_url": url,
                        "seendate": seendate,
                        "domain": article.get("domain"),
                        "language": language,
                        "socialimage": article.get("socialimage"),
                        "sourcecountry": article.get("sourcecountry"),
                    }
                )
                alerts.append(alert)

            except Exception as e:
                logger.warning(f"[GDELT] Error parsing article: {e}")
                continue

        return alerts

    def _parse_gdelt_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse GDELT date format (YYYYMMDDTHHMMSSZ).

        Args:
            date_str: Date string from GDELT

        Returns:
            datetime object or None
        """
        if not date_str:
            return None

        try:
            # GDELT format: 20231225T143000Z
            return datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        try:
            # Alternative format without 'T'
            return datetime.strptime(date_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        return None

    def _infer_severity(self, text: str) -> Optional[str]:
        """
        Infer severity from text content.

        Args:
            text: Article title or content

        Returns:
            Severity level string
        """
        text_lower = text.lower()

        # Severe indicators
        severe_keywords = [
            'death', 'dead', 'dies', 'killed', 'casualt', 'fatalit',
            'rescue', 'evacuate', 'evacuation',
            'emergency', 'disaster', 'crisis', 'severe', 'extreme',
            'swept away', 'missing persons', 'bodies'
        ]
        if any(kw in text_lower for kw in severe_keywords):
            return 'severe'

        # High indicators
        high_keywords = [
            'warning', 'alert', 'red alert', 'danger', 'dangerous',
            'rising', 'overflow', 'submerge', 'submerged',
            'stranded', 'trapped', 'marooned'
        ]
        if any(kw in text_lower for kw in high_keywords):
            return 'high'

        # Moderate indicators
        moderate_keywords = [
            'waterlog', 'waterlogging', 'flood', 'flooded',
            'inundat', 'heavy rain', 'disruption',
            'traffic jam', 'traffic chaos'
        ]
        if any(kw in text_lower for kw in moderate_keywords):
            return 'moderate'

        # Default to low for general flood news
        return 'low'


async def test_gdelt_fetcher():
    """Test function to verify GDELT fetcher works."""
    fetcher = GDELTFetcher()

    print(f"GDELT Fetcher enabled: {fetcher.is_enabled()}")
    print(f"Source name: {fetcher.get_source_name()}")

    print("\nFetching Delhi GDELT news...")
    alerts = await fetcher.fetch("delhi")

    print(f"\nFound {len(alerts)} high-quality flood alerts:")
    for alert in alerts[:10]:  # Show first 10
        print(f"\n  [{alert.source_name}] Severity: {alert.severity or 'N/A'}")
        print(f"  Title: {alert.title[:100]}...")
        print(f"  Score: {alert.raw_data.get('relevance_score', 'N/A')}")
        print(f"  URL: {alert.url}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_gdelt_fetcher())
