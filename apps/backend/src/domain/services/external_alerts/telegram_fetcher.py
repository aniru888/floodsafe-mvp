"""
PUB Telegram Channel Fetcher - Scrapes real-time flood alerts from PUB's Telegram channel.

Singapore's PUB (Public Utilities Board) operates @pubfloodalerts on Telegram, broadcasting:
1. Heavy rain warnings (NEA-issued): "Heavy rain expected over {areas} from {time} to {time}."
2. Flash flood risk (PUB-issued): "[Risk of Flash Flood] Due to heavy rain, please avoid..."
3. Flash flood subsided (all-clear): "Flash flood subsided at {location}."

Source: https://t.me/s/pubfloodalerts (public web preview — no auth needed)
HTML parsing: BeautifulSoup (already in requirements.txt)
HTTP client: aiohttp (consistent with all existing fetchers)

This fetcher only activates for cities with configured Telegram channels.
"""

import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import re

from .base_fetcher import BaseFetcher, ExternalAlertCreate

logger = logging.getLogger(__name__)

# Public web preview base URL (SSR, no auth)
TELEGRAM_PREVIEW_URL = "https://t.me/s/{channel}"

# Skip messages older than this
MAX_MESSAGE_AGE_HOURS = 48

# Alert expiry (from alert time)
ALERT_EXPIRY_HOURS = 12

# Per-city channel configuration (extensible)
DEFAULT_CHANNELS: dict[str, list[str]] = {
    "singapore": ["pubfloodalerts"],
    # Future: "delhi": ["delhifloodalerts"], etc.
}


class TelegramFetcher(BaseFetcher):
    """
    Fetches flood alerts from PUB's public Telegram channel.

    Scrapes the SSR web preview at t.me/s/pubfloodalerts (returns ~40 messages).
    No API key or bot token required — the page is publicly accessible.
    """

    def get_source_name(self) -> str:
        return "telegram"

    def is_enabled(self) -> bool:
        # No API key needed — public web preview
        return True

    async def fetch(self, city: str) -> list[ExternalAlertCreate]:
        """
        Fetch alerts from configured Telegram channels for the given city.

        Args:
            city: City identifier — only processes cities with configured channels

        Returns:
            List of ExternalAlertCreate objects from recent messages
        """
        channels = DEFAULT_CHANNELS.get(city.lower(), [])
        if not channels:
            return []

        self.log_fetch_start(city)

        all_alerts: list[ExternalAlertCreate] = []
        for channel in channels:
            try:
                alerts = await self._fetch_channel(channel, city)
                all_alerts.extend(alerts)
            except Exception as e:
                self.log_fetch_error(city, e)

        self.log_fetch_complete(city, len(all_alerts))
        return all_alerts

    async def _fetch_channel(self, channel: str, city: str) -> list[ExternalAlertCreate]:
        """
        Fetch and parse messages from a single Telegram channel's web preview.

        Args:
            channel: Channel username (without @)
            city: City identifier

        Returns:
            List of parsed alerts
        """
        url = TELEGRAM_PREVIEW_URL.format(channel=channel)
        alerts: list[ExternalAlertCreate] = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; FloodSafe/1.0)",
                        "Accept": "text/html",
                    },
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"[Telegram] Channel {channel} returned status {resp.status}"
                        )
                        return []

                    html = await resp.text()
        except aiohttp.ClientError as e:
            logger.error(f"[Telegram] HTTP request failed for {channel}: {e}")
            return []

        # Parse HTML
        soup = BeautifulSoup(html, "html.parser")
        message_wraps = soup.select("div.tgme_widget_message_wrap")

        if not message_wraps:
            logger.warning(
                f"[Telegram] No message_wrap elements found for {channel} "
                f"(HTML length: {len(html)}). Page structure may have changed."
            )
            return []

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=MAX_MESSAGE_AGE_HOURS)

        for wrap in message_wraps:
            try:
                alert = self._parse_message(wrap, channel, city, cutoff)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                logger.debug(f"[Telegram] Failed to parse message in {channel}: {e}")
                continue

        logger.info(
            f"[Telegram] Parsed {len(alerts)} alerts from {len(message_wraps)} "
            f"messages in {channel}"
        )
        return alerts

    def _parse_message(
        self,
        wrap,
        channel: str,
        city: str,
        cutoff: datetime,
    ) -> Optional[ExternalAlertCreate]:
        """
        Parse a single Telegram message widget into an ExternalAlertCreate.

        Args:
            wrap: BeautifulSoup element for div.tgme_widget_message_wrap
            channel: Channel username
            city: City identifier
            cutoff: Oldest allowed message time

        Returns:
            ExternalAlertCreate or None if message should be skipped
        """
        # Find the message div with data-post attribute
        msg_div = wrap.select_one("div.tgme_widget_message[data-post]")
        if not msg_div:
            return None

        # Extract message ID (e.g. "pubfloodalerts/1391")
        data_post = msg_div.get("data-post", "")
        if not data_post:
            return None

        # Extract message text
        text_div = wrap.select_one("div.tgme_widget_message_text")
        if not text_div:
            return None

        raw_text = text_div.get_text(separator=" ", strip=True)
        if not raw_text:
            return None

        # Extract timestamp from <time datetime="ISO">
        time_tag = wrap.select_one("time[datetime]")
        alert_time = None
        if time_tag:
            try:
                dt_str = time_tag.get("datetime", "")
                alert_time = datetime.fromisoformat(dt_str)
                # Ensure timezone-aware
                if alert_time.tzinfo is None:
                    alert_time = alert_time.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                alert_time = None

        # Skip messages older than cutoff
        if alert_time and alert_time < cutoff:
            return None

        # Extract deep link URL
        link_tag = wrap.select_one("a.tgme_widget_message_date[href]")
        msg_url = link_tag.get("href", "") if link_tag else ""
        if not msg_url and data_post:
            msg_url = f"https://t.me/{data_post}"

        # Infer severity from message content
        severity = self._infer_severity(raw_text)

        # Build title: first sentence or first 120 chars
        title = self._extract_title(raw_text)

        # Set expiry
        expires_at = None
        if alert_time:
            expires_at = alert_time + timedelta(hours=ALERT_EXPIRY_HOURS)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ALERT_EXPIRY_HOURS)

        return ExternalAlertCreate(
            source="telegram",
            source_id=data_post,
            source_name="PUB Telegram",
            city=city,
            title=self.truncate_text(title, 500),
            message=self.truncate_text(raw_text, 2000),
            severity=severity,
            url=msg_url,
            latitude=None,
            longitude=None,
            raw_data={"channel": channel, "data_post": data_post, "text": raw_text[:500]},
            expires_at=expires_at,
        )

    def _infer_severity(self, text: str) -> str:
        """
        Infer alert severity from message text content.

        PUB Telegram messages follow predictable patterns:
        - "[Risk of Flash Flood]" = active flood warning → high
        - "ponding" / "water level" = flood observation → moderate
        - "Heavy rain expected" = weather advisory → low
        - "Flash flood subsided" = all-clear → low
        """
        text_lower = text.lower()

        # High: active flood risk (PUB uses exact bracket notation)
        if "[risk of flash flood]" in text_lower or "avoid this location" in text_lower:
            return "high"

        # Moderate: flood-related observations
        if any(kw in text_lower for kw in ["ponding", "water level", "waterlogging"]):
            return "moderate"

        # Low: weather advisory or all-clear
        if any(kw in text_lower for kw in [
            "heavy rain expected",
            "flash flood subsided",
            "issued by nea",
        ]):
            return "low"

        # Default for any other PUB message
        return "moderate"

    def _extract_title(self, text: str) -> str:
        """
        Extract a concise title from message text.

        Uses the first sentence (up to first period) or first 120 chars.
        """
        # Check for bracketed prefix like "[Risk of Flash Flood]"
        bracket_match = re.match(r"(\[.+?\])", text)
        if bracket_match:
            bracket_text = bracket_match.group(1)
            # Get the rest up to the first period
            rest = text[len(bracket_text):].strip()
            first_sentence = rest.split(".")[0].strip() if rest else ""
            if first_sentence:
                title = f"{bracket_text} {first_sentence}"
                return title[:200]
            return bracket_text

        # First sentence (up to first period)
        first_sentence = text.split(".")[0].strip()
        if first_sentence and len(first_sentence) <= 200:
            return first_sentence

        # Fallback: truncate
        return text[:120]
