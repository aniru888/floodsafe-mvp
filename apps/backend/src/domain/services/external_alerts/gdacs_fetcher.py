"""
GDACS Fetcher - Fetches flood alerts from the Global Disaster Alert and Coordination System.

GDACS is a cooperation framework between the United Nations, the European Commission,
and disaster managers worldwide. It provides real-time alerts about natural disasters.

Feed URL: https://www.gdacs.org/xml/rss.xml
Reference: https://www.gdacs.org/

Categories: Drought, Earthquake, Flood, Tropical Cyclone, Tsunami, Volcano
Alert Levels: Red (severe), Orange (moderate), Green (low)

We filter by:
- eventtype = FL (Flood) or TC (Tropical Cyclone with flood potential)
- Geographic bounds for Delhi/Bangalore regions
- Alert level (Red/Orange prioritized)

No API keys required - public GeoRSS feed.
"""

import asyncio
import aiohttp
import feedparser
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import re
from xml.etree import ElementTree as ET

from .base_fetcher import BaseFetcher, ExternalAlertCreate
from src.core.config import settings

logger = logging.getLogger(__name__)


# GDACS GeoRSS feed URL
GDACS_FEED_URL = "https://www.gdacs.org/xml/rss.xml"

# Maximum age of alerts (days)
MAX_ALERT_AGE_DAYS = 7


class GDACSFetcher(BaseFetcher):
    """
    Fetches flood alerts from GDACS GeoRSS feed.

    GDACS provides global disaster alerts with geographic coordinates,
    making it possible to filter by region.
    """

    # City bounding boxes for filtering (approx rectangular regions)
    # Format: (lat_min, lat_max, lon_min, lon_max)
    CITY_BOUNDS = {
        "delhi": {
            "bounds": (28.0, 29.2, 76.5, 77.8),  # Expanded Delhi-NCR region
            "name": "Delhi NCR",
            "include_states": ["delhi", "haryana", "uttar pradesh"],  # Nearby states
        },
        "bangalore": {
            "bounds": (12.7, 13.3, 77.3, 77.9),  # Bangalore metro region
            "name": "Bangalore",
            "include_states": ["karnataka"],
        },
        "yogyakarta": {
            "bounds": (-7.95, -7.65, 110.30, 110.50),  # DIY province + Sleman/Bantul
            "name": "Yogyakarta",
            "include_states": ["yogyakarta", "jawa tengah"],  # DIY + Central Java
        },
        "singapore": {
            "bounds": (1.15, 1.47, 103.60, 104.05),  # Singapore island + surrounding
            "name": "Singapore",
            "include_states": ["singapore"],
        },
        "indore": {
            "bounds": (22.52, 22.85, 75.72, 75.97),
            "name": "Indore",
            "include_states": ["madhya pradesh"],
        },
    }

    # Event types to include
    FLOOD_EVENT_TYPES = ["FL", "TC"]  # Flood and Tropical Cyclone

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize GDACS fetcher.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries

    def get_source_name(self) -> str:
        return "gdacs"

    def is_enabled(self) -> bool:
        # GDACS is always enabled - public feed
        return getattr(settings, 'GDACS_ENABLED', True)

    async def fetch(self, city: str) -> list[ExternalAlertCreate]:
        """
        Fetch flood alerts from GDACS for a city.

        Args:
            city: City identifier ('delhi', 'bangalore')

        Returns:
            List of ExternalAlertCreate objects for the region
        """
        self.log_fetch_start(city)

        city_lower = city.lower()
        if city_lower not in self.CITY_BOUNDS:
            logger.warning(f"[GDACS] No bounds configured for city: {city}")
            return []

        # Fetch and parse the GDACS feed
        entries = await self._fetch_gdacs_feed()
        if not entries:
            self.log_fetch_complete(city, 0)
            return []

        logger.info(f"[GDACS] Raw feed entries: {len(entries)}")

        # Filter entries for this city/region
        alerts = self._filter_and_convert(entries, city_lower)

        self.log_fetch_complete(city, len(alerts))
        return alerts

    async def _fetch_gdacs_feed(self) -> list[dict]:
        """
        Fetch and parse the GDACS GeoRSS feed.

        Returns:
            List of parsed feed entries
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        GDACS_FEED_URL,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={"User-Agent": "FloodSafe/1.0 (+https://floodsafe.app)"}
                    ) as response:
                        if response.status != 200:
                            logger.warning(f"[GDACS] HTTP {response.status} (attempt {attempt}/{self.max_retries})")
                            if attempt < self.max_retries:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return []

                        content = await response.text()

                        # Parse with feedparser
                        feed = feedparser.parse(content)

                        if feed.bozo and feed.bozo_exception:
                            logger.warning(f"[GDACS] Parse warning: {feed.bozo_exception}")

                        return feed.entries

            except asyncio.TimeoutError:
                logger.warning(f"[GDACS] Timeout (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
            except aiohttp.ClientError as e:
                logger.warning(f"[GDACS] Client error: {e} (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"[GDACS] Unexpected error: {e}")
                break

        return []

    def _filter_and_convert(self, entries: list, city: str) -> list[ExternalAlertCreate]:
        """
        Filter entries by city/region and convert to alerts.

        Args:
            entries: Feed entries from GDACS
            city: City identifier

        Returns:
            List of ExternalAlertCreate for the region
        """
        alerts = []
        city_config = self.CITY_BOUNDS[city]
        bounds = city_config["bounds"]
        include_states = city_config.get("include_states", [])

        now = datetime.now(timezone.utc)
        max_age = timedelta(days=MAX_ALERT_AGE_DAYS)

        for entry in entries:
            try:
                # Check event type
                event_type = self._get_event_type(entry)
                if event_type not in self.FLOOD_EVENT_TYPES:
                    continue

                # Check if within geographic bounds or mentions relevant state
                lat, lon = self._extract_coordinates(entry)
                text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()

                is_in_bounds = lat is not None and lon is not None and self._is_in_bounds(lat, lon, bounds)
                mentions_region = any(state in text for state in include_states)

                # Also check for specific city mention
                mentions_city = city in text or city_config["name"].lower() in text

                if not (is_in_bounds or mentions_region or mentions_city):
                    continue

                # Check age
                pub_date = self._parse_date(entry)
                if pub_date and (now - pub_date) > max_age:
                    continue

                # Extract alert details
                title = entry.get("title", "GDACS Alert")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "https://www.gdacs.org/")
                alert_level = self._get_alert_level(entry)
                severity = self._map_alert_level_to_severity(alert_level)

                # Generate unique source_id
                gdacs_id = entry.get("id", entry.get("guid", ""))
                source_id = self.generate_source_id("gdacs", gdacs_id, city)

                # Clean HTML from summary
                clean_summary = self.clean_html(summary)

                # Build message
                message = clean_summary
                if alert_level:
                    message = f"[{alert_level} Alert] {message}"
                if lat is not None and lon is not None:
                    message += f"\n\nLocation: {lat:.4f}°N, {lon:.4f}°E"

                # Create alert
                alert = ExternalAlertCreate(
                    source="gdacs",
                    source_id=source_id,
                    source_name="UN GDACS",
                    city=city,
                    title=self.truncate_text(title, 500),
                    message=self.truncate_text(message, 2000),
                    severity=severity,
                    url=link,
                    latitude=lat,
                    longitude=lon,
                    raw_data={
                        "gdacs_id": gdacs_id,
                        "event_type": event_type,
                        "alert_level": alert_level,
                        "published": pub_date.isoformat() if pub_date else None,
                    }
                )
                alerts.append(alert)

            except Exception as e:
                logger.warning(f"[GDACS] Error parsing entry: {e}")
                continue

        return alerts

    def _get_event_type(self, entry: dict) -> str:
        """Extract event type from GDACS entry."""
        # GDACS uses gdacs:eventtype in the feed
        event_type = entry.get("gdacs_eventtype", "")
        if not event_type:
            # Try to infer from title
            title = entry.get("title", "").lower()
            if "flood" in title:
                return "FL"
            elif "cyclone" in title or "typhoon" in title or "hurricane" in title:
                return "TC"
            elif "earthquake" in title:
                return "EQ"
        return event_type

    def _extract_coordinates(self, entry: dict) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract latitude/longitude from GDACS entry.

        GDACS uses GeoRSS format.
        """
        # Try georss:point format (lat lon)
        if hasattr(entry, 'georss_point') or 'georss_point' in entry:
            point = entry.get('georss_point', '')
            if point:
                try:
                    parts = point.split()
                    if len(parts) == 2:
                        return float(parts[0]), float(parts[1])
                except (ValueError, IndexError):
                    pass

        # Try where.Point format
        if hasattr(entry, 'where') and entry.where:
            try:
                point = entry.where.get('point', entry.where.get('Point', {}))
                if point:
                    pos = point.get('pos', '')
                    if pos:
                        parts = pos.split()
                        if len(parts) == 2:
                            return float(parts[0]), float(parts[1])
            except (ValueError, AttributeError):
                pass

        # Try geo:lat and geo:long
        lat = entry.get('geo_lat') or entry.get('geo_latitude')
        lon = entry.get('geo_long') or entry.get('geo_longitude')
        if lat and lon:
            try:
                return float(lat), float(lon)
            except ValueError:
                pass

        return None, None

    def _is_in_bounds(self, lat: float, lon: float, bounds: Tuple[float, float, float, float]) -> bool:
        """Check if coordinates are within bounding box."""
        lat_min, lat_max, lon_min, lon_max = bounds
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

    def _get_alert_level(self, entry: dict) -> Optional[str]:
        """Extract alert level from GDACS entry."""
        # GDACS uses gdacs:alertlevel
        alert_level = entry.get("gdacs_alertlevel", "")
        if alert_level:
            return alert_level.upper()

        # Try to infer from title
        title = entry.get("title", "").lower()
        if "red" in title:
            return "RED"
        elif "orange" in title:
            return "ORANGE"
        elif "green" in title:
            return "GREEN"

        return None

    def _map_alert_level_to_severity(self, alert_level: Optional[str]) -> Optional[str]:
        """Map GDACS alert level to our severity scale."""
        if not alert_level:
            return "moderate"

        level = alert_level.upper()
        if level == "RED":
            return "severe"
        elif level == "ORANGE":
            return "high"
        elif level == "GREEN":
            return "moderate"

        return "moderate"

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parse publication date from entry."""
        # Try different date fields
        date_str = entry.get("published", entry.get("updated", entry.get("pubDate")))

        if not date_str:
            return None

        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            pass

        # Try feedparser's parsed time
        if "published_parsed" in entry and entry["published_parsed"]:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(entry["published_parsed"]), tz=timezone.utc)
            except (ValueError, TypeError, OverflowError):
                pass

        return None


async def test_gdacs_fetcher():
    """Test function to verify GDACS fetcher works."""
    fetcher = GDACSFetcher()

    print(f"GDACS Fetcher enabled: {fetcher.is_enabled()}")
    print(f"Source name: {fetcher.get_source_name()}")

    print("\nFetching Delhi GDACS alerts...")
    alerts = await fetcher.fetch("delhi")

    print(f"\nFound {len(alerts)} alerts for Delhi region:")
    for alert in alerts[:5]:  # Show first 5
        print(f"\n  [{alert.severity}] {alert.title[:80]}...")
        if alert.latitude and alert.longitude:
            print(f"  Location: {alert.latitude}, {alert.longitude}")
        print(f"  URL: {alert.url}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_gdacs_fetcher())
