"""
Tests for Meta WhatsApp Cloud API webhook endpoint (/api/whatsapp-meta).

Tests HTTP layer: HMAC-SHA256 signature validation, webhook verification,
message deduplication, and malformed payload handling.

The entire Meta handler — the PRODUCTION code path — had zero automated
test coverage before these tests. These validate security boundaries.
"""
import hashlib
import hmac
import json
import time

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from src.main import app
from src.api.whatsapp_meta import _dedup_cache, _rate_limit_cache


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear dedup and rate limit caches before each test."""
    _dedup_cache.clear()
    _rate_limit_cache.clear()
    yield
    _dedup_cache.clear()
    _rate_limit_cache.clear()


@pytest.fixture
def meta_app_secret():
    """A fixed app secret for testing signature validation."""
    return "test_app_secret_12345"


def _compute_signature(body: bytes, secret: str) -> str:
    """Compute valid HMAC-SHA256 signature like Meta does."""
    sig = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


def _sample_meta_payload(phone: str = "919876543210", text: str = "HELP",
                          message_id: str = "wamid.test123") -> dict:
    """Factory for a valid Meta webhook JSON payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "919035398881",
                        "phone_number_id": "PHONE_ID"
                    },
                    "contacts": [{
                        "profile": {"name": "Test User"},
                        "wa_id": phone
                    }],
                    "messages": [{
                        "from": phone,
                        "id": message_id,
                        "timestamp": str(int(time.time())),
                        "type": "text",
                        "text": {"body": text}
                    }]
                }
            }]
        }]
    }


# =============================================================================
# Mocks for all tests — disable external calls
# =============================================================================

@pytest.fixture(autouse=True)
def mock_meta_send():
    """Mock all Meta send functions to prevent real API calls."""
    with patch("src.api.whatsapp_meta.meta_send_text", new_callable=AsyncMock, return_value=True) as mock_text, \
         patch("src.api.whatsapp_meta.meta_send_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.mark_as_read", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_welcome_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_menu_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_extended_menu", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_onboarding_city_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_onboarding_city_2_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_after_location_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_after_report_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_risk_result_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_account_choice_buttons", new_callable=AsyncMock, return_value=True), \
         patch("src.api.whatsapp_meta.send_circles_menu_buttons", new_callable=AsyncMock, return_value=True):
        yield mock_text


def _post_webhook(client, payload: dict, secret: str, headers: dict = None):
    """Helper to POST to Meta webhook with correct signature."""
    body = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(body, secret)
    default_headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }
    if headers:
        default_headers.update(headers)
    return client.post(
        "/api/whatsapp-meta",
        content=body,
        headers=default_headers,
    )


# =============================================================================
# Tests
# =============================================================================

class TestMetaSignature:
    """Test HMAC-SHA256 signature validation (security boundary)."""

    def test_valid_signature_returns_200(self, client, meta_app_secret):
        """Valid HMAC-SHA256 signature should be accepted."""
        payload = _sample_meta_payload()

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True
            mock_settings.META_VERIFY_TOKEN = "test_verify"
            mock_settings.ML_ENABLED = False

            response = _post_webhook(client, payload, meta_app_secret)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_invalid_signature_returns_403(self, client, meta_app_secret):
        """Wrong signature must be rejected with 403."""
        payload = _sample_meta_payload()
        body = json.dumps(payload).encode("utf-8")

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = client.post(
                "/api/whatsapp-meta",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
                },
            )

        assert response.status_code == 403

    def test_missing_signature_header_returns_403(self, client, meta_app_secret):
        """Missing X-Hub-Signature-256 header → 403."""
        payload = _sample_meta_payload()
        body = json.dumps(payload).encode("utf-8")

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = client.post(
                "/api/whatsapp-meta",
                content=body,
                headers={"Content-Type": "application/json"},
                # No X-Hub-Signature-256 header
            )

        assert response.status_code == 403

    def test_missing_app_secret_returns_403(self, client):
        """Misconfigured server (empty META_APP_SECRET) must reject all webhooks."""
        payload = _sample_meta_payload()
        body = json.dumps(payload).encode("utf-8")

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = ""  # Not configured
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = client.post(
                "/api/whatsapp-meta",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": "sha256=anything",
                },
            )

        assert response.status_code == 403


class TestMetaVerification:
    """Test webhook verification (GET endpoint for Meta registration)."""

    def test_get_verify_returns_challenge(self, client):
        """Valid verify token should echo the challenge as integer."""
        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_VERIFY_TOKEN = "my_verify_token"
            mock_settings.META_WHATSAPP_TOKEN = "test"
            mock_settings.META_PHONE_NUMBER_ID = "123"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = client.get(
                "/api/whatsapp-meta",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "my_verify_token",
                    "hub.challenge": "12345",
                },
            )

        assert response.status_code == 200
        assert response.json() == 12345

    def test_get_verify_wrong_token_returns_403(self, client):
        """Wrong verify token → 403."""
        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_VERIFY_TOKEN = "my_verify_token"
            mock_settings.META_WHATSAPP_TOKEN = "test"
            mock_settings.META_PHONE_NUMBER_ID = "123"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = client.get(
                "/api/whatsapp-meta",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong_token",
                    "hub.challenge": "12345",
                },
            )

        assert response.status_code == 403


class TestMetaDedup:
    """Test message deduplication (Phase A2)."""

    def test_duplicate_wamid_skipped(self, client, meta_app_secret, mock_meta_send):
        """Same wamid sent twice should only be processed once."""
        payload = _sample_meta_payload(message_id="wamid.DUPLICATE_TEST")

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True
            mock_settings.META_VERIFY_TOKEN = "test"
            mock_settings.ML_ENABLED = False

            # First send — should be processed
            _post_webhook(client, payload, meta_app_secret)
            first_call_count = mock_meta_send.call_count

            # Second send (same wamid) — should be skipped
            _post_webhook(client, payload, meta_app_secret)
            second_call_count = mock_meta_send.call_count

        # Second message should NOT trigger additional send calls
        assert second_call_count == first_call_count

    def test_dedup_expires_after_ttl(self, client, meta_app_secret):
        """Dedup entries older than TTL should be evicted."""
        # Manually insert an expired entry
        _dedup_cache["wamid.EXPIRED"] = time.time() - 400  # 6+ minutes ago

        # Now process a new message — expired entry should be evicted
        payload = _sample_meta_payload(message_id="wamid.NEW_MSG")

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True
            mock_settings.META_VERIFY_TOKEN = "test"
            mock_settings.ML_ENABLED = False

            _post_webhook(client, payload, meta_app_secret)

        # Expired entry should have been evicted
        assert "wamid.EXPIRED" not in _dedup_cache
        # New entry should be in cache
        assert "wamid.NEW_MSG" in _dedup_cache


class TestMetaPayloadEdgeCases:
    """Test handling of non-standard and malformed payloads."""

    def test_non_whatsapp_object_ignored(self, client, meta_app_secret):
        """Non-WhatsApp objects (e.g. page events) should return 200 silently."""
        payload = {"object": "page", "entry": []}

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = _post_webhook(client, payload, meta_app_secret)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_empty_messages_array_handled(self, client, meta_app_secret):
        """Status updates (read receipts, delivered) have empty messages array."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "BIZ_ID",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "919035398881"},
                        "statuses": [{
                            "id": "wamid.xxx",
                            "status": "delivered",
                            "timestamp": "1710000000"
                        }]
                        # No "messages" key at all
                    }
                }]
            }]
        }

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = _post_webhook(client, payload, meta_app_secret)

        assert response.status_code == 200

    def test_missing_entry_field_returns_200(self, client, meta_app_secret):
        """Missing 'entry' field should not crash."""
        payload = {"object": "whatsapp_business_account"}

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = _post_webhook(client, payload, meta_app_secret)

        assert response.status_code == 200

    def test_non_json_body_returns_200(self, client, meta_app_secret):
        """Non-JSON body should return 200 (not crash)."""
        body = b"not json at all"
        sig = _compute_signature(body, meta_app_secret)

        with patch("src.api.whatsapp_meta.settings") as mock_settings:
            mock_settings.META_APP_SECRET = meta_app_secret
            mock_settings.META_WHATSAPP_TOKEN = "test_token"
            mock_settings.META_PHONE_NUMBER_ID = "12345"
            mock_settings.META_WHATSAPP_ENABLED = True

            response = client.post(
                "/api/whatsapp-meta",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                },
            )

        assert response.status_code == 200
