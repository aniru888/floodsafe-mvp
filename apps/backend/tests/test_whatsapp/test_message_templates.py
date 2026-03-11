"""
Tests for message_templates.py — template completeness, language detection, rendering.

Pure unit tests. Validates that ALL 35 templates have trilingual support (EN/HI/ID),
language detection fallback chain works correctly, and templates render with format variables.

Key tests: template count regression guard, 3-tier language fallback, button title length,
Indonesian flood terminology correctness.
"""
import pytest
from unittest.mock import MagicMock

from src.domain.services.whatsapp.message_templates import (
    TemplateKey,
    TEMPLATES,
    get_message,
    get_user_language,
)
from src.domain.services.whatsapp.meta_client import (
    BUTTON_SETS,
    BUTTON_SETS_HI,
    BUTTON_SETS_ID,
)


class TestTemplateCompleteness:
    """Verify every template has all 3 language variants."""

    def test_all_templates_have_three_languages(self):
        """Every template must have en, hi, and id keys."""
        required_languages = {"en", "hi", "id"}
        for key, template_set in TEMPLATES.items():
            missing = required_languages - set(template_set.keys())
            assert not missing, (
                f"Template {key} missing languages: {missing}"
            )

    def test_template_count_is_35(self):
        """Regression guard — exactly 35 templates (28 original + 7 circle)."""
        assert len(TEMPLATES) == 35, (
            f"Expected 35 templates, got {len(TEMPLATES)}. "
            f"Keys: {sorted(TEMPLATES.keys())}"
        )

    def test_all_template_keys_have_entries(self):
        """Every TemplateKey constant must have a matching TEMPLATES entry."""
        for attr in dir(TemplateKey):
            if attr.startswith("_"):
                continue
            key_value = getattr(TemplateKey, attr)
            assert key_value in TEMPLATES, (
                f"TemplateKey.{attr} = '{key_value}' has no TEMPLATES entry"
            )

    def test_no_orphan_templates(self):
        """Every TEMPLATES key must have a matching TemplateKey constant."""
        key_values = {
            getattr(TemplateKey, attr)
            for attr in dir(TemplateKey)
            if not attr.startswith("_")
        }
        for template_key in TEMPLATES:
            assert template_key in key_values, (
                f"TEMPLATES['{template_key}'] has no TemplateKey constant"
            )


class TestLanguageDetection:
    """Test get_user_language() 3-tier fallback: user → city → phone → en."""

    def _make_user(self, language=None, city_preference=None):
        user = MagicMock()
        user.language = language
        user.city_preference = city_preference
        return user

    def test_user_hindi_preference(self):
        user = self._make_user(language="hindi")
        assert get_user_language(user) == "hi"

    def test_user_hi_preference(self):
        user = self._make_user(language="hi")
        assert get_user_language(user) == "hi"

    def test_user_indonesian_preference(self):
        user = self._make_user(language="id")
        assert get_user_language(user) == "id"

    def test_user_bahasa_preference(self):
        """Real Indonesian users may set 'bahasa' instead of 'id'."""
        user = self._make_user(language="bahasa")
        assert get_user_language(user) == "id"

    def test_user_english_preference(self):
        """English users should get 'en' (not fall through to city)."""
        user = self._make_user(language="english")
        # "english" doesn't match hi or id, so falls through to city/phone/default
        assert get_user_language(user) == "en"

    def test_city_fallback_yogyakarta(self):
        """Anonymous Yogyakarta users should get Indonesian."""
        assert get_user_language(None, city="yogyakarta") == "id"

    def test_city_fallback_delhi_stays_english(self):
        """Delhi defaults to English, not Hindi (Hindi only via user.language)."""
        assert get_user_language(None, city="delhi") == "en"

    def test_city_fallback_bangalore_stays_english(self):
        assert get_user_language(None, city="bangalore") == "en"

    def test_phone_prefix_fallback_62(self):
        """Indonesian phone prefix → Indonesian language."""
        assert get_user_language(None, city=None, phone="+6281234567890") == "id"

    def test_phone_prefix_fallback_62_no_plus(self):
        """Should work even without + prefix."""
        assert get_user_language(None, city=None, phone="6281234567890") == "id"

    def test_phone_prefix_fallback_91_stays_english(self):
        """Indian phone does NOT imply Hindi (could be English speaker)."""
        assert get_user_language(None, city=None, phone="+919876543210") == "en"

    def test_user_preference_overrides_city(self):
        """User's explicit language beats city-based fallback."""
        user = self._make_user(language="hi")
        assert get_user_language(user, city="yogyakarta") == "hi"

    def test_none_user_none_city_none_phone_defaults_english(self):
        """All None → English."""
        assert get_user_language(None) == "en"
        assert get_user_language(None, None, None) == "en"

    def test_user_with_no_language_field(self):
        """User object without language attribute shouldn't crash."""
        user = MagicMock(spec=[])  # No attributes
        assert get_user_language(user) == "en"


class TestTemplateRendering:
    """Test that templates render correctly with format variables."""

    def test_circle_created_renders_all_languages(self):
        """CIRCLE_CREATED must render with name and code in all 3 languages."""
        for lang in ("en", "hi", "id"):
            result = get_message(
                TemplateKey.CIRCLE_CREATED, lang,
                name="Family", code="ABC123"
            )
            assert "Family" in result, f"Missing 'Family' in {lang}"
            assert "ABC123" in result, f"Missing 'ABC123' in {lang}"

    def test_circle_joined_renders_name(self):
        for lang in ("en", "hi", "id"):
            result = get_message(
                TemplateKey.CIRCLE_JOINED, lang, name="Neighbors"
            )
            assert "Neighbors" in result

    def test_template_with_missing_variable_returns_template(self):
        """Missing format variables should return raw template (not crash)."""
        result = get_message(TemplateKey.RISK_HIGH, "en")
        # Should contain the raw {location} placeholder
        assert "{location}" in result or "FLOOD RISK" in result

    def test_nonexistent_template_returns_error_string(self):
        """Unknown template key returns informative error string."""
        result = get_message("NONEXISTENT_KEY", "en")
        assert "not found" in result.lower()

    def test_circle_flood_alert_renders_emoji(self):
        """CIRCLE_FLOOD_ALERT must contain the alert emoji."""
        result = get_message(
            TemplateKey.CIRCLE_FLOOD_ALERT, "en",
            reporter_name="Alice",
            circle_name="Family",
            description="Heavy flooding"
        )
        assert "\U0001f6a8" in result  # 🚨

    def test_circle_invite_share_is_self_contained(self):
        """CIRCLE_INVITE_SHARE must contain phone number for forwarding."""
        result = get_message(
            TemplateKey.CIRCLE_INVITE_SHARE, "en",
            name="Family", code="XYZ789"
        )
        assert "JOIN XYZ789" in result
        assert "+91 9035398881" in result or "9035398881" in result

    def test_indonesian_template_uses_correct_terminology(self):
        """Indonesian templates must use correct flood terminology."""
        welcome_id = TEMPLATES[TemplateKey.WELCOME]["id"]
        assert "banjir" in welcome_id.lower()  # "flood"
        assert "genangan" in welcome_id.lower()  # "waterlogging"

        warnings_none_id = TEMPLATES[TemplateKey.WARNINGS_NONE]["id"]
        assert "musim hujan" in warnings_none_id.lower()  # "rainy season"

    def test_language_fallback_to_english(self):
        """Unknown language code should fall back to English."""
        result = get_message(TemplateKey.HELP, "xx")
        en_result = get_message(TemplateKey.HELP, "en")
        assert result == en_result


class TestButtonSets:
    """Test button set completeness and constraints."""

    def test_button_title_length_within_20_chars(self):
        """Meta rejects buttons with titles > 20 characters."""
        all_sets = {
            "EN": BUTTON_SETS,
            "HI": BUTTON_SETS_HI,
            "ID": BUTTON_SETS_ID,
        }
        for lang, sets in all_sets.items():
            for set_name, buttons in sets.items():
                for button_id, title in buttons:
                    assert len(title) <= 20, (
                        f"{lang}/{set_name}: button '{button_id}' title "
                        f"'{title}' is {len(title)} chars (max 20)"
                    )

    def test_all_button_sets_have_three_languages(self):
        """EN, HI, and ID must have the same set names."""
        en_sets = set(BUTTON_SETS.keys())
        hi_sets = set(BUTTON_SETS_HI.keys())
        id_sets = set(BUTTON_SETS_ID.keys())

        assert en_sets == hi_sets, (
            f"HI missing: {en_sets - hi_sets}, extra: {hi_sets - en_sets}"
        )
        assert en_sets == id_sets, (
            f"ID missing: {en_sets - id_sets}, extra: {id_sets - en_sets}"
        )

    def test_button_sets_max_3_buttons(self):
        """Meta allows max 3 buttons per message."""
        for set_name, buttons in BUTTON_SETS.items():
            assert len(buttons) <= 3, (
                f"Button set '{set_name}' has {len(buttons)} buttons (max 3)"
            )

    def test_button_ids_consistent_across_languages(self):
        """Button IDs must be the same across all languages."""
        for set_name in BUTTON_SETS:
            en_ids = [b[0] for b in BUTTON_SETS[set_name]]
            hi_ids = [b[0] for b in BUTTON_SETS_HI.get(set_name, [])]
            id_ids = [b[0] for b in BUTTON_SETS_ID.get(set_name, [])]
            assert en_ids == hi_ids, (
                f"Button IDs mismatch in '{set_name}': EN={en_ids}, HI={hi_ids}"
            )
            assert en_ids == id_ids, (
                f"Button IDs mismatch in '{set_name}': EN={en_ids}, ID={id_ids}"
            )
