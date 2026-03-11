"""
Tests for outbound rate limiting in meta_client.py:_send_request().

Tests the daily 1,500-message limit, warning threshold at 1,400,
daily counter reset, and read receipt exemption behavior.

The counter is a module-level singleton dict — tests must manipulate it directly.
"""
import pytest
from datetime import date
from unittest.mock import patch, AsyncMock, MagicMock

from src.domain.services.whatsapp.meta_client import (
    _outbound_counter,
    OUTBOUND_DAILY_LIMIT,
    OUTBOUND_WARNING_THRESHOLD,
    send_text_message,
    mark_as_read,
    _send_request,
)


@pytest.fixture(autouse=True)
def reset_outbound_counter():
    """Reset the outbound counter before and after each test."""
    _outbound_counter["date"] = str(date.today())
    _outbound_counter["count"] = 0
    yield
    _outbound_counter["date"] = str(date.today())
    _outbound_counter["count"] = 0


def _mock_successful_response():
    """Create a mock httpx response with status 200."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"messages": [{"id": "wamid.xxx"}]}
    return response


class TestOutboundRateLimit:
    """Test daily outbound message rate limiting."""

    @pytest.mark.asyncio
    async def test_counter_increments_on_send(self):
        """Successful sends should increment the counter."""
        mock_response = _mock_successful_response()

        with patch("src.domain.services.whatsapp.meta_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_text_message("+919876543210", "Hello")

        assert result is True
        assert _outbound_counter["count"] == 1

    @pytest.mark.asyncio
    async def test_blocks_at_daily_limit(self):
        """Messages should be blocked when daily limit is reached."""
        _outbound_counter["count"] = OUTBOUND_DAILY_LIMIT  # 1500

        # Should NOT make any HTTP request
        result = await send_text_message("+919876543210", "Hello")

        assert result is False
        assert _outbound_counter["count"] == OUTBOUND_DAILY_LIMIT  # Unchanged

    @pytest.mark.asyncio
    async def test_read_receipts_exempt_at_limit(self):
        """Read receipts should return True even when limit is reached."""
        _outbound_counter["count"] = OUTBOUND_DAILY_LIMIT

        result = await mark_as_read("wamid.test123")

        assert result is True  # Read receipts never blocked

    @pytest.mark.asyncio
    async def test_warning_logged_at_threshold(self):
        """Warning should be logged when approaching the limit."""
        _outbound_counter["count"] = OUTBOUND_WARNING_THRESHOLD  # 1400

        mock_response = _mock_successful_response()

        with patch("src.domain.services.whatsapp.meta_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("src.domain.services.whatsapp.meta_client.logger") as mock_logger:
                result = await send_text_message("+919876543210", "Hello")

        assert result is True
        # Verify warning was logged
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "rate limit" in warning_msg.lower() or str(OUTBOUND_WARNING_THRESHOLD) in warning_msg

    @pytest.mark.asyncio
    async def test_counter_resets_on_new_day(self):
        """Counter should reset to 0 when the date changes."""
        _outbound_counter["date"] = "2026-03-11"  # Yesterday
        _outbound_counter["count"] = OUTBOUND_DAILY_LIMIT  # Was at limit

        mock_response = _mock_successful_response()

        with patch("src.domain.services.whatsapp.meta_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_text_message("+919876543210", "Hello")

        assert result is True
        assert _outbound_counter["date"] == str(date.today())
        assert _outbound_counter["count"] == 1  # Reset and incremented

    @pytest.mark.asyncio
    async def test_read_receipts_skipped_near_limit(self):
        """Near limit, read receipts should return True without incrementing."""
        _outbound_counter["count"] = OUTBOUND_WARNING_THRESHOLD

        result = await mark_as_read("wamid.test456")

        assert result is True
        # Read receipts near limit should NOT increment counter
        assert _outbound_counter["count"] == OUTBOUND_WARNING_THRESHOLD

    @pytest.mark.asyncio
    async def test_counter_persists_across_calls(self):
        """Counter should persist across multiple send calls."""
        mock_response = _mock_successful_response()

        with patch("src.domain.services.whatsapp.meta_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await send_text_message("+919876543210", "Message 1")
            await send_text_message("+919876543210", "Message 2")
            await send_text_message("+919876543210", "Message 3")

        assert _outbound_counter["count"] == 3
