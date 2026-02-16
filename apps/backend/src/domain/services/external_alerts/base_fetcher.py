"""
Base Fetcher - Abstract base class for all external alert fetchers.

All fetchers must implement:
- fetch(city: str) -> list[ExternalAlertCreate]
- get_source_name() -> str
- is_enabled() -> bool
"""

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)


class ExternalAlertCreate(BaseModel):
    """Schema for creating an external alert."""

    source: str = Field(..., description="Source identifier: 'imd', 'cwc', 'twitter', 'rss', 'telegram'")
    source_id: Optional[str] = Field(None, description="Unique ID from source for deduplication")
    source_name: Optional[str] = Field(None, description="Display name: 'Hindustan Times', 'IMD Delhi'")
    city: str = Field(..., description="City: 'delhi', 'bangalore'")
    title: str = Field(..., max_length=500, description="Alert title/headline")
    message: str = Field(..., description="Full alert message/description")
    severity: Optional[str] = Field(None, description="Severity: 'low', 'moderate', 'high', 'severe'")
    url: Optional[str] = Field(None, max_length=2048, description="Link to original source")
    latitude: Optional[float] = Field(None, description="Location latitude if available")
    longitude: Optional[float] = Field(None, description="Location longitude if available")
    raw_data: Optional[dict] = Field(None, description="Original API/RSS response data")
    expires_at: Optional[datetime] = Field(None, description="When alert becomes stale")
    alert_time: Optional[datetime] = Field(None, description="Original message timestamp (tz-naive UTC)")

    class Config:
        from_attributes = True


class BaseFetcher(ABC):
    """Abstract base class for all external alert fetchers."""

    # Flood-related keywords for filtering
    FLOOD_KEYWORDS = [
        'flood', 'floods', 'flooding', 'flooded',
        'waterlog', 'waterlogged', 'waterlogging',
        'inundation', 'inundated',
        'submerge', 'submerged',
        'yamuna', 'river level', 'water level',
        'heavy rain', 'heavy rainfall', 'torrential',
        'overflow', 'overflowing',
        'deluge',
        'drain', 'drainage',
        'monsoon',
        'rescue', 'evacuate', 'evacuation',
        'alert', 'warning',
    ]

    # Hindi keywords (transliterated)
    FLOOD_KEYWORDS_HINDI = [
        'baadh', 'baarish', 'paani', 'jal',
    ]

    @abstractmethod
    async def fetch(self, city: str) -> list[ExternalAlertCreate]:
        """
        Fetch alerts for a specific city.

        Args:
            city: City identifier ('delhi', 'bangalore')

        Returns:
            List of ExternalAlertCreate objects
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Return the source identifier (e.g., 'rss', 'imd', 'twitter').

        Returns:
            Source identifier string
        """
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """
        Check if this fetcher is enabled (has required config/API keys).

        Returns:
            True if fetcher is enabled and can be used
        """
        pass

    def filter_by_keywords(self, text: str) -> bool:
        """
        Check if text contains flood-related keywords.

        Args:
            text: Text to check (title, description, etc.)

        Returns:
            True if text contains flood-related keywords
        """
        if not text:
            return False

        text_lower = text.lower()

        # Check English keywords
        for keyword in self.FLOOD_KEYWORDS:
            if keyword in text_lower:
                return True

        # Check Hindi keywords
        for keyword in self.FLOOD_KEYWORDS_HINDI:
            if keyword in text_lower:
                return True

        return False

    def generate_source_id(self, *args) -> str:
        """
        Generate a unique source_id from input arguments.

        Used for deduplication - same inputs will generate same ID.

        Args:
            *args: Values to hash (e.g., url, title, timestamp)

        Returns:
            SHA256 hash of concatenated inputs
        """
        combined = '|'.join(str(arg) for arg in args if arg)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def map_severity(self, value: str) -> Optional[str]:
        """
        Map various severity indicators to standard levels.

        Args:
            value: Raw severity value from source

        Returns:
            Standardized severity: 'low', 'moderate', 'high', 'severe', or None
        """
        if not value:
            return None

        value_lower = value.lower()

        # Standard mappings
        if value_lower in ['severe', 'extreme', 'critical', 'red', '4', 'emergency']:
            return 'severe'
        elif value_lower in ['high', 'danger', 'orange', '3', 'warning']:
            return 'high'
        elif value_lower in ['moderate', 'medium', 'yellow', '2', 'advisory']:
            return 'moderate'
        elif value_lower in ['low', 'minor', 'green', '1', 'watch']:
            return 'low'

        return None

    def truncate_text(self, text: str, max_length: int = 500) -> str:
        """
        Truncate text to max length, adding ellipsis if needed.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text
        """
        if not text:
            return ""

        if len(text) <= max_length:
            return text

        return text[:max_length - 3] + "..."

    def clean_html(self, text: str) -> str:
        """
        Remove HTML tags from text.

        Args:
            text: Text that may contain HTML

        Returns:
            Clean text without HTML tags
        """
        if not text:
            return ""

        import re
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        clean = clean.replace('&nbsp;', ' ')
        clean = clean.replace('&amp;', '&')
        clean = clean.replace('&lt;', '<')
        clean = clean.replace('&gt;', '>')
        clean = clean.replace('&quot;', '"')
        clean = clean.replace('&#39;', "'")
        # Normalize whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def log_fetch_start(self, city: str):
        """Log fetch operation start."""
        logger.info(f"[{self.get_source_name()}] Starting fetch for city: {city}")

    def log_fetch_complete(self, city: str, count: int):
        """Log fetch operation completion."""
        logger.info(f"[{self.get_source_name()}] Fetch complete for {city}: {count} alerts found")

    def log_fetch_error(self, city: str, error: Exception):
        """Log fetch operation error."""
        logger.error(f"[{self.get_source_name()}] Fetch failed for {city}: {error}")
