# WhatsApp Comprehensive Test Suite — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 111 pytest tests covering every WhatsApp feature path across both Twilio and Meta transports, including edge cases, security, bilingual support, and live endpoint smoke tests.

**Architecture:** Tests are organized by concern (one file per domain). All tests use mocked DB (SQLite in-memory via circles conftest pattern), mocked ML (patched TFLite), and mocked external APIs (httpx). Live tests use a separate `--run-live` marker.

**Tech Stack:** pytest, unittest.mock, FastAPI TestClient, httpx mocking, SQLite in-memory DB

**Design Doc:** `docs/plans/2026-03-04-whatsapp-testing-design.md`

---

## Task 1: Expand conftest.py with Meta + Shared Fixtures

**Files:**
- Modify: `apps/backend/tests/test_whatsapp/conftest.py`

**Step 1: Write new fixtures**

Add Meta webhook fixtures, HMAC signing helper, DB fixtures with sessions, and mock patches for external services. Append to the existing conftest:

```python
import hashlib
import hmac
import json

# ─── Meta Webhook Fixtures ───

def _sign_payload(body: bytes, secret: str = "test_app_secret") -> str:
    """Compute HMAC-SHA256 signature for Meta webhook validation."""
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _build_meta_text_payload(phone: str, text: str, message_id: str = "wamid.test123") -> dict:
    """Build a valid Meta webhook JSON payload with a text message."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001234", "phone_number_id": "PHONE_ID"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": phone.lstrip("+")}],
                    "messages": [{
                        "from": phone.lstrip("+"),
                        "id": message_id,
                        "timestamp": "1234567890",
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }


def _build_meta_location_payload(phone: str, lat: float, lng: float) -> dict:
    """Build Meta webhook JSON with a location message."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001234", "phone_number_id": "PHONE_ID"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": phone.lstrip("+")}],
                    "messages": [{
                        "from": phone.lstrip("+"),
                        "id": "wamid.loc123",
                        "timestamp": "1234567890",
                        "type": "location",
                        "location": {"latitude": lat, "longitude": lng},
                    }],
                },
            }],
        }],
    }


def _build_meta_button_payload(phone: str, button_id: str) -> dict:
    """Build Meta webhook JSON with an interactive button reply."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001234", "phone_number_id": "PHONE_ID"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": phone.lstrip("+")}],
                    "messages": [{
                        "from": phone.lstrip("+"),
                        "id": "wamid.btn123",
                        "timestamp": "1234567890",
                        "type": "interactive",
                        "interactive": {
                            "type": "button_reply",
                            "button_reply": {"id": button_id, "title": button_id.replace("_", " ").title()},
                        },
                    }],
                },
            }],
        }],
    }


def _build_meta_image_payload(phone: str, media_id: str = "media_123") -> dict:
    """Build Meta webhook JSON with an image message."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001234", "phone_number_id": "PHONE_ID"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": phone.lstrip("+")}],
                    "messages": [{
                        "from": phone.lstrip("+"),
                        "id": "wamid.img123",
                        "timestamp": "1234567890",
                        "type": "image",
                        "image": {"id": media_id, "mime_type": "image/jpeg"},
                    }],
                },
            }],
        }],
    }


@pytest.fixture
def meta_client():
    """TestClient configured for Meta webhook testing."""
    return TestClient(app)


@pytest.fixture
def mock_meta_enabled():
    """Enable Meta WhatsApp for tests."""
    with patch('src.api.whatsapp_meta.is_meta_whatsapp_enabled', return_value=True), \
         patch('src.core.config.settings.META_APP_SECRET', 'test_app_secret'), \
         patch('src.core.config.settings.META_VERIFY_TOKEN', 'test_verify_token'), \
         patch('src.core.config.settings.META_WHATSAPP_TOKEN', 'test_token'), \
         patch('src.core.config.settings.META_PHONE_NUMBER_ID', 'PHONE_ID'), \
         patch('src.core.config.settings.META_WHATSAPP_ENABLED', True):
        yield


@pytest.fixture
def mock_meta_send():
    """Capture all outbound Meta messages."""
    sent_messages = []

    async def _capture_text(to, text):
        sent_messages.append({"to": to, "type": "text", "text": text})
        return True

    async def _capture_buttons(to, body_text, buttons, **kwargs):
        sent_messages.append({"to": to, "type": "buttons", "body": body_text, "buttons": buttons})
        return True

    async def _capture_read(message_id):
        sent_messages.append({"type": "mark_read", "id": message_id})
        return True

    with patch('src.api.whatsapp_meta.meta_send_text', side_effect=_capture_text), \
         patch('src.api.whatsapp_meta.meta_send_buttons', side_effect=_capture_buttons), \
         patch('src.api.whatsapp_meta.mark_as_read', side_effect=_capture_read), \
         patch('src.api.whatsapp_meta.send_welcome_buttons', new_callable=AsyncMock, return_value=True), \
         patch('src.api.whatsapp_meta.send_after_location_buttons', new_callable=AsyncMock, return_value=True), \
         patch('src.api.whatsapp_meta.send_after_report_buttons', new_callable=AsyncMock, return_value=True), \
         patch('src.api.whatsapp_meta.send_risk_result_buttons', new_callable=AsyncMock, return_value=True), \
         patch('src.api.whatsapp_meta.send_account_choice_buttons', new_callable=AsyncMock, return_value=True), \
         patch('src.api.whatsapp_meta.send_menu_buttons', new_callable=AsyncMock, return_value=True):
        yield sent_messages


@pytest.fixture
def mock_wit_disabled():
    """Disable Wit.ai NLU."""
    with patch('src.api.whatsapp_meta.is_wit_enabled', return_value=False), \
         patch('src.api.webhook.is_wit_enabled', return_value=False):
        yield


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests that don't need real DB."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.add = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def clear_meta_rate_limit():
    """Clear the Meta webhook rate limit cache."""
    from src.api.whatsapp_meta import _rate_limit_cache
    _rate_limit_cache.clear()
    yield
    _rate_limit_cache.clear()
```

**Step 2: Run existing tests to verify fixtures don't break anything**

Run: `cd apps/backend && pytest tests/test_whatsapp/ -v`
Expected: All existing tests still pass.

**Step 3: Commit**

```bash
git add apps/backend/tests/test_whatsapp/conftest.py
git commit -m "test: expand WhatsApp conftest with Meta webhook fixtures"
```

---

## Task 2: test_message_templates.py (Pure Logic, No Mocking)

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_message_templates.py`

**Step 1: Write all template tests**

These are pure function tests — no mocking needed. Test that all templates exist in both languages, substitution works, and formatters produce correct output.

```python
"""
Tests for WhatsApp message templates — bilingual rendering and formatters.

Tests:
- All TemplateKeys have both en/hi translations
- Variable substitution works correctly
- Missing variables handled gracefully
- Risk factor formatting
- Alert list formatting with severity emojis
- Watch area formatting
"""
import pytest

from src.domain.services.whatsapp.message_templates import (
    TemplateKey, TEMPLATES, get_message, get_user_language,
    format_risk_factors, format_alerts_list, format_watch_areas,
)


class TestTemplateCompleteness:
    """Every template key must have both English and Hindi."""

    def test_all_templates_have_en(self):
        for key_name in dir(TemplateKey):
            if key_name.startswith("_"):
                continue
            key = getattr(TemplateKey, key_name)
            assert key in TEMPLATES, f"Missing template: {key}"
            assert "en" in TEMPLATES[key], f"Template {key} missing English"

    def test_all_templates_have_hi(self):
        for key_name in dir(TemplateKey):
            if key_name.startswith("_"):
                continue
            key = getattr(TemplateKey, key_name)
            if key in TEMPLATES:
                assert "hi" in TEMPLATES[key], f"Template {key} missing Hindi"


class TestGetMessage:
    """Test get_message() substitution and fallbacks."""

    def test_substitution_works(self):
        msg = get_message(TemplateKey.RISK_LOW, "en", location="Janpath")
        assert "Janpath" in msg

    def test_hindi_substitution(self):
        msg = get_message(TemplateKey.RISK_LOW, "hi", location="जनपथ")
        assert "जनपथ" in msg

    def test_missing_variable_returns_template(self):
        # Should not raise — returns template with {placeholder}
        msg = get_message(TemplateKey.RISK_HIGH, "en")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_unknown_key_returns_error(self):
        msg = get_message("NONEXISTENT_KEY", "en")
        assert "not found" in msg.lower()

    def test_unknown_language_falls_back_to_en(self):
        msg = get_message(TemplateKey.WELCOME, "fr")
        msg_en = get_message(TemplateKey.WELCOME, "en")
        assert msg == msg_en


class TestGetUserLanguage:
    """Test language detection from user object."""

    def test_none_user_returns_en(self):
        assert get_user_language(None) == "en"

    def test_hindi_user(self):
        from unittest.mock import MagicMock
        user = MagicMock()
        user.language = "hi"
        assert get_user_language(user) == "hi"

    def test_unknown_language_returns_en(self):
        from unittest.mock import MagicMock
        user = MagicMock()
        user.language = "fr"
        assert get_user_language(user) == "en"


class TestFormatRiskFactors:

    def test_low_elevation(self):
        result = format_risk_factors(elevation=200.0)
        assert "Low-lying" in result
        assert "200" in result

    def test_normal_elevation(self):
        result = format_risk_factors(elevation=250.0)
        assert "250" in result
        assert "Low-lying" not in result

    def test_rainfall(self):
        result = format_risk_factors(rainfall=45.0)
        assert "45" in result

    def test_hotspot_flag(self):
        result = format_risk_factors(is_hotspot=True)
        assert "waterlogging" in result.lower()

    def test_empty_returns_general(self):
        result = format_risk_factors()
        assert "General" in result

    def test_hindi_labels(self):
        result = format_risk_factors(elevation=200.0, language="hi")
        assert "ऊंचाई" in result


class TestFormatAlertsList:

    def test_empty_list(self):
        assert format_alerts_list([]) == ""

    def test_severity_emojis(self):
        alerts = [
            {"severity": "red", "source": "IMD", "title": "Heavy Rain", "description": "Danger"},
            {"severity": "orange", "source": "CWC", "title": "Moderate", "description": "Caution"},
            {"severity": "yellow", "source": "IMD", "title": "Light", "description": "Watch"},
        ]
        result = format_alerts_list(alerts)
        assert "\U0001F534" in result  # Red circle
        assert "\U0001F7E0" in result  # Orange circle
        assert "\U0001F7E1" in result  # Yellow circle

    def test_missing_fields_handled(self):
        alerts = [{"title": "Test"}]  # Missing severity, source, description
        result = format_alerts_list(alerts)
        assert "Test" in result


class TestFormatWatchAreas:

    def test_empty_returns_empty(self):
        assert format_watch_areas([]) == ""

    def test_numbered_list(self):
        areas = [
            {"name": "Home", "label": "Home", "risk_level": "low", "recent_reports": 0},
            {"name": "Office", "label": "Work", "risk_level": "high", "recent_reports": 3},
        ]
        result = format_watch_areas(areas)
        assert "1." in result
        assert "2." in result
        assert "Home" in result
        assert "Office" in result
        assert "\U0001F7E2" in result  # Green for low
        assert "\U0001F534" in result  # Red for high
```

**Step 2: Run tests**

Run: `cd apps/backend && pytest tests/test_whatsapp/test_message_templates.py -v`
Expected: All pass (these test existing functions)

**Step 3: Commit**

```bash
git add apps/backend/tests/test_whatsapp/test_message_templates.py
git commit -m "test: add message template tests (bilingual, formatters)"
```

---

## Task 3: test_photo_handler.py (ML Pipeline)

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_photo_handler.py`

**Step 1: Write photo handler tests**

Tests the ML classification pipeline and severity mapping. Mocks the TFLite classifier and httpx for Twilio media download.

```python
"""
Tests for WhatsApp photo handler — ML classification pipeline.

Tests:
- Flood image classification (flood/no-flood/ML-disabled)
- Twilio media download (success/failure/non-image)
- Severity mapping at confidence boundaries
- Edge cases: empty bytes, non-image content
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.domain.services.whatsapp.photo_handler import (
    FloodClassification,
    classify_flood_image,
    download_twilio_media,
    process_sos_with_photo,
    get_severity_from_classification,
    get_confidence_text,
)


class TestClassifyFloodImage:

    @pytest.mark.asyncio
    async def test_flood_detected(self):
        mock_classifier = MagicMock()
        mock_classifier.predict.return_value = {
            "is_flood": True, "confidence": 0.85,
            "classification": "flood", "needs_review": False,
        }
        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings, \
             patch('src.domain.services.whatsapp.photo_handler.get_classifier', return_value=mock_classifier):
            mock_settings.ML_ENABLED = True
            result = await classify_flood_image(b"fake_image_bytes")

        assert result is not None
        assert result.is_flood is True
        assert result.confidence == 0.85
        assert result.classification == "flood"

    @pytest.mark.asyncio
    async def test_no_flood(self):
        mock_classifier = MagicMock()
        mock_classifier.predict.return_value = {
            "is_flood": False, "confidence": 0.7,
            "classification": "no_flood", "needs_review": True,
        }
        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings, \
             patch('src.domain.services.whatsapp.photo_handler.get_classifier', return_value=mock_classifier):
            mock_settings.ML_ENABLED = True
            result = await classify_flood_image(b"fake_image_bytes")

        assert result is not None
        assert result.is_flood is False
        assert result.needs_review is True

    @pytest.mark.asyncio
    async def test_ml_disabled_returns_none(self):
        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings:
            mock_settings.ML_ENABLED = False
            result = await classify_flood_image(b"fake_image_bytes")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_bytes_returns_none(self):
        result = await classify_flood_image(b"")
        assert result is None

    @pytest.mark.asyncio
    async def test_none_bytes_returns_none(self):
        result = await classify_flood_image(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_classifier_exception_returns_none(self):
        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings, \
             patch('src.domain.services.whatsapp.photo_handler.get_classifier', side_effect=RuntimeError("Model not loaded")):
            mock_settings.ML_ENABLED = True
            result = await classify_flood_image(b"fake_image_bytes")
        assert result is None


class TestDownloadTwilioMedia:

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"jpeg_image_data"

        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings, \
             patch('httpx.AsyncClient') as mock_client:
            mock_settings.TWILIO_ACCOUNT_SID = "AC123"
            mock_settings.TWILIO_AUTH_TOKEN = "auth"
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await download_twilio_media("https://api.twilio.com/media/test")

        assert result == b"jpeg_image_data"

    @pytest.mark.asyncio
    async def test_404_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings, \
             patch('httpx.AsyncClient') as mock_client:
            mock_settings.TWILIO_ACCOUNT_SID = "AC123"
            mock_settings.TWILIO_AUTH_TOKEN = "auth"
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await download_twilio_media("https://api.twilio.com/media/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_non_image_content_type_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"pdf_data"

        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings, \
             patch('httpx.AsyncClient') as mock_client:
            mock_settings.TWILIO_ACCOUNT_SID = "AC123"
            mock_settings.TWILIO_AUTH_TOKEN = "auth"
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await download_twilio_media("https://api.twilio.com/media/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_url_returns_none(self):
        result = await download_twilio_media("")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        with patch('src.domain.services.whatsapp.photo_handler.settings') as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = ""
            mock_settings.TWILIO_AUTH_TOKEN = ""
            result = await download_twilio_media("https://api.twilio.com/media/test")
        assert result is None


class TestProcessSosWithPhoto:

    @pytest.mark.asyncio
    async def test_download_fails_returns_none_none(self):
        with patch('src.domain.services.whatsapp.photo_handler.download_twilio_media', new_callable=AsyncMock, return_value=None):
            img, cls = await process_sos_with_photo("https://api.twilio.com/media/test")
        assert img is None
        assert cls is None

    @pytest.mark.asyncio
    async def test_download_ok_classify_ok(self):
        mock_classification = FloodClassification(
            is_flood=True, confidence=0.9,
            classification="flood", needs_review=False, raw_response={},
        )
        with patch('src.domain.services.whatsapp.photo_handler.download_twilio_media',
                    new_callable=AsyncMock, return_value=b"img"), \
             patch('src.domain.services.whatsapp.photo_handler.classify_flood_image',
                    new_callable=AsyncMock, return_value=mock_classification):
            img, cls = await process_sos_with_photo("https://api.twilio.com/media/test")
        assert img == b"img"
        assert cls.is_flood is True


class TestSeverityMapping:

    def test_none_classification(self):
        assert "unavailable" in get_severity_from_classification(None).lower()

    def test_no_flood(self):
        cls = FloodClassification(is_flood=False, confidence=0.7, classification="no_flood", needs_review=True, raw_response={})
        assert "no flooding" in get_severity_from_classification(cls).lower()

    def test_high_confidence(self):
        cls = FloodClassification(is_flood=True, confidence=0.85, classification="flood", needs_review=False, raw_response={})
        assert "impassable" in get_severity_from_classification(cls).lower()

    def test_moderate_confidence(self):
        cls = FloodClassification(is_flood=True, confidence=0.65, classification="flood", needs_review=False, raw_response={})
        result = get_severity_from_classification(cls)
        assert "significant" in result.lower()

    def test_boundary_0_8(self):
        cls = FloodClassification(is_flood=True, confidence=0.8, classification="flood", needs_review=False, raw_response={})
        assert "impassable" in get_severity_from_classification(cls).lower()

    def test_boundary_0_6(self):
        cls = FloodClassification(is_flood=True, confidence=0.6, classification="flood", needs_review=False, raw_response={})
        assert "significant" in get_severity_from_classification(cls).lower()

    def test_boundary_0_4(self):
        cls = FloodClassification(is_flood=True, confidence=0.4, classification="flood", needs_review=False, raw_response={})
        assert "moderate" in get_severity_from_classification(cls).lower()

    def test_low_confidence(self):
        cls = FloodClassification(is_flood=True, confidence=0.35, classification="flood", needs_review=True, raw_response={})
        assert "possible" in get_severity_from_classification(cls).lower()


class TestConfidenceText:

    def test_flood_en(self):
        cls = FloodClassification(is_flood=True, confidence=0.85, classification="flood", needs_review=False, raw_response={})
        result = get_confidence_text(cls, "en")
        assert "FLOODING DETECTED" in result
        assert "85%" in result

    def test_no_flood_en(self):
        cls = FloodClassification(is_flood=False, confidence=0.7, classification="no_flood", needs_review=True, raw_response={})
        result = get_confidence_text(cls, "en")
        assert "No flooding" in result

    def test_none_en(self):
        result = get_confidence_text(None, "en")
        assert "unavailable" in result.lower()

    def test_flood_hi(self):
        cls = FloodClassification(is_flood=True, confidence=0.85, classification="flood", needs_review=False, raw_response={})
        result = get_confidence_text(cls, "hi")
        assert "बाढ़" in result
```

**Step 2: Run tests**

Run: `cd apps/backend && pytest tests/test_whatsapp/test_photo_handler.py -v`
Expected: All pass

**Step 3: Commit**

```bash
git add apps/backend/tests/test_whatsapp/test_photo_handler.py
git commit -m "test: add photo handler tests (ML classification, severity mapping)"
```

---

## Task 4: test_meta_client.py (Graph API Client)

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_meta_client.py`

Tests the Meta Graph API client's retry logic, button formatting, phone normalization, and sync/async variants. All httpx calls mocked.

**Key test patterns:**

```python
"""
Tests for Meta WhatsApp Cloud API client.

Tests: send_text (success/4xx/5xx-retry), send_interactive_buttons (truncation, max 3),
download_media (two-step, timeout-retry), mark_as_read, send_text_sync,
phone formatting, unknown exceptions.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from src.domain.services.whatsapp.meta_client import (
    send_text_message, send_interactive_buttons, download_media,
    mark_as_read, send_text_message_sync, is_meta_whatsapp_enabled,
    _send_request, BUTTON_SETS,
)
```

**12 tests covering:**
- `test_send_text_200_returns_true` — 200 → True
- `test_send_text_400_no_retry` — 400 → False, single attempt
- `test_send_text_500_retries_3_times` — 500 → 3 attempts with delays
- `test_send_text_timeout_retries` — TimeoutException → retry
- `test_send_text_unknown_error_no_retry` — ConnectionError → False immediately
- `test_send_buttons_max_3` — 5 buttons → only 3 in payload
- `test_send_buttons_title_truncated` — 25-char title → 20 chars
- `test_download_media_two_step` — URL fetch → content → bytes
- `test_download_media_4xx_no_retry` — 404 → None, no retry
- `test_download_media_timeout_retries` — timeout → retry
- `test_mark_as_read_payload` — correct message_id in payload
- `test_phone_plus_stripped` — "+919876543210" → "919876543210" in payload

**Step 1:** Write complete test file.
**Step 2:** Run: `cd apps/backend && pytest tests/test_whatsapp/test_meta_client.py -v`
**Step 3:** Commit: `git commit -m "test: add Meta Graph API client tests (retry, buttons, media)"`

---

## Task 5: test_command_handlers.py (RISK, WARNINGS, etc.)

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_command_handlers.py`

Tests the shared command handlers. Mocks internal httpx API calls (risk-at-point, unified alerts, geocode).

**15 tests covering:**
- `test_risk_with_place_name` — geocodes → calls risk API → formatted response with factors
- `test_risk_with_last_location` — uses coords directly, no geocode
- `test_risk_no_location` — returns RISK_NO_LOCATION template
- `test_risk_geocode_failure` — place not found → LOCATION_NOT_FOUND
- `test_risk_api_500_returns_low` — risk API failure → graceful LOW risk
- `test_risk_api_empty_json` — `{}` → LOW risk default
- `test_risk_fhi_0_3_moderate` — FHI exactly 0.3 → moderate template
- `test_risk_fhi_0_6_high` — FHI exactly 0.6 → high template
- `test_risk_geocode_timeout` — httpx.TimeoutException → fallback
- `test_risk_with_llama_summary` — llama enabled → AI summary appended
- `test_warnings_active_alerts` — alerts returned → WARNINGS_ACTIVE
- `test_warnings_no_alerts` — empty → WARNINGS_NONE
- `test_warnings_malformed_data` — missing fields → no crash
- `test_my_areas_unlinked` — no user → ACCOUNT_NOT_LINKED
- `test_my_areas_empty` — user with 0 watch areas → MY_AREAS_EMPTY

**Mock pattern for internal API calls:**
```python
mock_response = MagicMock()
mock_response.status_code = 200
mock_response.json.return_value = {"risk_level": "high", "fhi": 0.7, "is_hotspot": True}

with patch('httpx.AsyncClient') as mock_client:
    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
    result = await handle_risk_command(mock_db, None, None, (28.6, 77.2))

assert "HIGH" in result
```

**Step 1:** Write complete test file.
**Step 2:** Run: `cd apps/backend && pytest tests/test_whatsapp/test_command_handlers.py -v`
**Step 3:** Commit: `git commit -m "test: add command handler tests (RISK, WARNINGS, MY AREAS)"`

---

## Task 6: test_session_states.py (State Machine)

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_session_states.py`

Tests session state transitions. Uses mock DB with WhatsAppSession-like objects.

**14 tests covering the state machine:**
- `test_new_session_starts_idle` — `_get_or_create_session` for new phone → idle
- `test_location_sets_awaiting_photo` — location message → `awaiting_photo`
- `test_photo_after_location_resets_idle` — photo in `awaiting_photo` → `idle`
- `test_skip_resets_idle` — "SKIP" in `awaiting_photo` → `idle`
- `test_expired_session_resets` — `updated_at` > 30 min ago → reset to idle
- `test_link_sets_awaiting_choice` — "LINK" → `awaiting_choice`
- `test_choice_1_sets_awaiting_email` — in `awaiting_choice`, "1" → `awaiting_email`
- `test_email_resets_idle` — valid email → `idle`
- `test_corrupted_data_none` — `session.data = None` → no crash
- `test_missing_pending_lat` — `pending_lat` absent → graceful reset
- `test_random_text_in_awaiting_photo` — "hello" → reminder message
- `test_cancel_in_awaiting_email` — "cancel" → idle
- `test_last_location_preserved_on_cancel` — cancel keeps `last_lat`/`last_lng`
- `test_session_data_cleared_on_timeout` — expired → data = {}

**Step 1:** Write complete test file.
**Step 2:** Run: `cd apps/backend && pytest tests/test_whatsapp/test_session_states.py -v`
**Step 3:** Commit: `git commit -m "test: add session state machine tests (14 transitions)"`

---

## Task 7: test_meta_webhook.py (Full Integration)

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_meta_webhook.py`

Full integration tests using FastAPI TestClient against the Meta webhook endpoint. Uses fixtures from conftest.

**18 tests covering:**

Core:
- `test_verify_valid_token` — GET with correct params → returns challenge
- `test_verify_invalid_token` — GET with wrong token → 403
- `test_invalid_signature` — POST with wrong HMAC → 403
- `test_disabled_returns_disabled` — No token → `{"status":"disabled"}`
- `test_non_whatsapp_object` — `object: "page"` → 200 OK
- `test_text_message` — text → outbound message captured
- `test_location_message` — location → `awaiting_photo` state
- `test_image_with_pending_location` — image → report created
- `test_button_reply` — button_reply → correct handler
- `test_rate_limit` — 11th msg → rate limit response
- `test_mark_as_read` — message_id → mark_as_read called
- `test_health_endpoint` — GET health → JSON status

Edge cases:
- `test_malformed_json` — garbage body → 200 OK
- `test_missing_from` — no `from` field → skipped silently
- `test_empty_text_body` — empty text → welcome
- `test_long_text` — 10KB text → no crash
- `test_unknown_type_audio` — type "audio" → welcome
- `test_duplicate_message_id` — (verify no duplicate reports in DB)

**Key pattern for Meta webhook tests:**
```python
def test_text_message(self, meta_client, mock_meta_enabled, mock_meta_send, mock_wit_disabled, clear_meta_rate_limit):
    payload = _build_meta_text_payload("+919876543210", "HELP")
    body = json.dumps(payload).encode()
    sig = _sign_payload(body)

    response = meta_client.post(
        "/api/whatsapp-meta",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
        },
    )
    assert response.status_code == 200
    assert len(mock_meta_send) > 0  # Messages were sent
```

**Step 1:** Write complete test file.
**Step 2:** Run: `cd apps/backend && pytest tests/test_whatsapp/test_meta_webhook.py -v`
**Step 3:** Commit: `git commit -m "test: add Meta webhook integration tests (18 tests)"`

---

## Task 8: test_button_handling.py

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_button_handling.py`

**8 tests** covering button routing for Twilio (via `handle_button_tap`) and Meta (via `_handle_button`). Tests verify correct handler invocation and response text for each button ID.

**Step 1:** Write test file using mock DB + session with various button_ids.
**Step 2:** Run and verify.
**Step 3:** Commit: `git commit -m "test: add button handling tests (8 button routes)"`

---

## Task 9: test_account_linking.py

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_account_linking.py`

**11 tests** covering the LINK → choice → email → account creation/linking flow. Uses mock DB with pre-created users.

Key edge cases: invalid email, email-at-only, cancel, phone conflict, pending report linked after creation.

**Step 1:** Write test file.
**Step 2:** Run and verify.
**Step 3:** Commit: `git commit -m "test: add account linking tests (11 flows)"`

---

## Task 10: test_transport_parity.py

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_transport_parity.py`

**5 tests** that send identical messages through both Twilio and Meta endpoints and verify they produce equivalent behavior (same commands handled, same session states, same button IDs).

**Step 1:** Write test file.
**Step 2:** Run and verify.
**Step 3:** Commit: `git commit -m "test: add transport parity tests (Twilio vs Meta)"`

---

## Task 11: test_security_edge_cases.py + test_bilingual.py

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_security_edge_cases.py`
- Create: `apps/backend/tests/test_whatsapp/test_bilingual.py`

**Security (6 tests):** HMAC wrong secret, missing header, malformed prefix, Twilio dev mode, phone injection, XSS in body.

**Bilingual (4 tests):** Hindi risk response, Hinglish Wit.ai, unknown language default, Hindi button labels complete.

**Step 1:** Write both test files.
**Step 2:** Run and verify.
**Step 3:** Commit: `git commit -m "test: add security edge cases and bilingual tests"`

---

## Task 12: test_live_endpoints.py (Smoke Tests)

**Files:**
- Create: `apps/backend/tests/test_whatsapp/test_live_endpoints.py`

**5 tests** marked with `@pytest.mark.live` — skipped by default, run with `pytest --run-live`.

```python
"""
Live endpoint smoke tests — verifies real server responses.

Run with: pytest tests/test_whatsapp/test_live_endpoints.py --run-live -v
Requires: Backend running on localhost:8000
"""
import pytest
import httpx

# Custom marker: skip unless --run-live flag passed
def pytest_configure(config):
    config.addinivalue_line("markers", "live: live endpoint tests")

@pytest.fixture
def live_base_url():
    return "http://localhost:8000/api"

@pytest.mark.live
class TestLiveEndpoints:

    def test_twilio_health(self, live_base_url):
        r = httpx.get(f"{live_base_url}/whatsapp/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data

    def test_meta_health(self, live_base_url):
        r = httpx.get(f"{live_base_url}/whatsapp-meta/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data

    def test_meta_verify_endpoint(self, live_base_url):
        r = httpx.get(
            f"{live_base_url}/whatsapp-meta",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"},
            timeout=10,
        )
        assert r.status_code == 403  # Wrong token

    def test_meta_unsigned_rejected(self, live_base_url):
        r = httpx.post(
            f"{live_base_url}/whatsapp-meta",
            json={"object": "whatsapp_business_account"},
            timeout=10,
        )
        # Should be 403 (no signature) or 200 (disabled)
        assert r.status_code in (200, 403)

    def test_twilio_post_requires_form_data(self, live_base_url):
        # POST without form data should either 422 or 403
        r = httpx.post(f"{live_base_url}/whatsapp", timeout=10)
        assert r.status_code in (403, 422)
```

Also add the `--run-live` flag to conftest:

```python
# In conftest.py or a root conftest
def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False, help="Run live endpoint tests")

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        skip_live = pytest.mark.skip(reason="Need --run-live to run")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)
```

**Step 1:** Write test file + add `--run-live` support.
**Step 2:** Run: `cd apps/backend && pytest tests/test_whatsapp/test_live_endpoints.py -v` (all skipped)
**Step 3:** Commit: `git commit -m "test: add live endpoint smoke tests (5 tests, --run-live)"`

---

## Task 13: Final Verification

**Step 1: Run full test suite**

```bash
cd apps/backend && pytest tests/test_whatsapp/ -v --tb=short
```

Expected: All ~111 tests pass (live tests skipped).

**Step 2: Check coverage**

```bash
cd apps/backend && pytest tests/test_whatsapp/ --cov=src/api/webhook --cov=src/api/whatsapp_meta --cov=src/domain/services/whatsapp --cov-report=term-missing
```

Expected: >80% coverage across all WhatsApp files.

**Step 3: Final commit**

```bash
git add -A tests/test_whatsapp/
git commit -m "test: complete WhatsApp test suite — 111 tests across 12 files"
```
