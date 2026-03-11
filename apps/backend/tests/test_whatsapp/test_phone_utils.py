"""
Tests for phone_utils.py — phone normalization, country detection, E.164 validation.

Pure unit tests with zero dependencies. Tests the single source of truth
for phone handling across 5 countries (IN, ID, SG).

Key gotcha tested: normalize_phone("081...", "IN") → Japan (not Indonesia).
This is WHY city_to_country() MUST be used for Yogyakarta users.
"""
import pytest

from src.core.phone_utils import (
    normalize_phone,
    detect_country_from_phone,
    city_to_country,
    is_valid_e164,
    CITY_TO_COUNTRY,
)


class TestNormalizePhone:
    """Test E.164 normalization for all supported countries."""

    def test_indian_10_digit(self):
        assert normalize_phone("9876543210", "IN") == "+919876543210"

    def test_indian_with_leading_zero(self):
        assert normalize_phone("09876543210", "IN") == "+919876543210"

    def test_already_e164_passthrough(self):
        """Already-formatted E.164 numbers should pass through unchanged."""
        assert normalize_phone("+919876543210") == "+919876543210"

    def test_already_e164_indonesian_passthrough(self):
        assert normalize_phone("+6281234567890") == "+6281234567890"

    def test_indonesian_10_digit(self):
        assert normalize_phone("8123456789", "ID") == "+628123456789"

    def test_indonesian_with_leading_zero(self):
        """Leading 0 stripped before prepending country code."""
        assert normalize_phone("08123456789", "ID") == "+628123456789"

    def test_indonesian_12_digit(self):
        """Indonesian mobile numbers can be 10-12 digits."""
        assert normalize_phone("812345678901", "ID") == "+62812345678901"

    def test_singapore_8_digit(self):
        assert normalize_phone("91234567", "SG") == "+6591234567"

    def test_bare_digits_with_country_code_fallback(self):
        """When digits don't match any country-specific pattern, prepend +."""
        result = normalize_phone("919876543210")
        assert result == "+919876543210"

    def test_strips_spaces_and_hyphens(self):
        """Spaces and hyphens should be stripped before normalization."""
        assert normalize_phone("  987-654-3210 ", "IN") == "+919876543210"

    # === THE GOTCHA TESTS (documented in MEMORY.md) ===

    def test_indonesian_081_with_wrong_country_GOTCHA(self):
        """KNOWN BUG: Indonesian 081... with default_country="IN" → Japan (+81).

        This proves WHY city_to_country() MUST be used for Yogyakarta users.
        Without correct country code, normalize_phone strips the leading 0,
        leaving 11 digits which doesn't match IN (10 digits), so it falls
        through to the bare-digits fallback: +81234567890 (Japan!).
        """
        result = normalize_phone("081234567890", "IN")
        # After stripping leading 0: "81234567890" (11 digits)
        # IN expects exactly 10 → no match → fallback: "+81234567890"
        assert result == "+81234567890"  # Japan, NOT Indonesia!
        assert not result.startswith("+62")  # Confirms the bug

    def test_indonesian_081_with_correct_country(self):
        """With correct country="ID", 081... normalizes to +62..."""
        result = normalize_phone("081234567890", "ID")
        assert result == "+6281234567890"
        assert result.startswith("+62")


class TestDetectCountryFromPhone:
    """Test country detection from phone number prefix."""

    def test_indian_prefix(self):
        assert detect_country_from_phone("+919876543210") == "IN"

    def test_indonesian_prefix(self):
        assert detect_country_from_phone("+6281234567890") == "ID"

    def test_singapore_prefix(self):
        assert detect_country_from_phone("+6591234567") == "SG"

    def test_bare_indonesian_no_plus(self):
        """Should detect country even without + prefix."""
        assert detect_country_from_phone("6281234567890") == "ID"

    def test_bare_indian_no_plus(self):
        assert detect_country_from_phone("919876543210") == "IN"

    def test_unknown_prefix_defaults_IN(self):
        """Unknown country prefixes default to India."""
        assert detect_country_from_phone("+4412345678") == "IN"

    def test_strips_whitespace_and_hyphens(self):
        assert detect_country_from_phone(" +62 812-345-6789 ") == "ID"


class TestCityToCountry:
    """Test city → country code mapping."""

    def test_all_cities_mapped(self):
        """All 5 supported cities must return correct country codes."""
        assert city_to_country("delhi") == "IN"
        assert city_to_country("bangalore") == "IN"
        assert city_to_country("indore") == "IN"
        assert city_to_country("yogyakarta") == "ID"
        assert city_to_country("singapore") == "SG"

    def test_case_insensitive(self):
        """City names should be case-insensitive."""
        assert city_to_country("YOGYAKARTA") == "ID"
        assert city_to_country("Delhi") == "IN"
        assert city_to_country("SINGAPORE") == "SG"

    def test_unknown_city_defaults_IN(self):
        """Unknown cities default to India."""
        assert city_to_country("mumbai") == "IN"
        assert city_to_country("tokyo") == "IN"

    def test_city_map_completeness(self):
        """CITY_TO_COUNTRY dict must have exactly 5 entries."""
        assert len(CITY_TO_COUNTRY) == 5
        assert set(CITY_TO_COUNTRY.keys()) == {
            "delhi", "bangalore", "indore", "yogyakarta", "singapore"
        }


class TestE164Validation:
    """Test E.164 format validation."""

    def test_valid_indian(self):
        assert is_valid_e164("+919876543210") is True

    def test_valid_indonesian(self):
        assert is_valid_e164("+6281234567890") is True

    def test_valid_singapore(self):
        assert is_valid_e164("+6591234567") is True

    def test_invalid_no_plus(self):
        """E.164 requires leading +."""
        assert is_valid_e164("919876543210") is False

    def test_invalid_starts_with_zero(self):
        """E.164 country codes never start with 0."""
        assert is_valid_e164("+0123456789") is False

    def test_too_short(self):
        """E.164 requires at least 7 digits after +."""
        assert is_valid_e164("+12345") is False

    def test_too_long(self):
        """E.164 allows max 15 digits total."""
        assert is_valid_e164("+1234567890123456") is False

    def test_valid_minimum_length(self):
        """Minimum valid: + followed by 7 digits."""
        assert is_valid_e164("+1234567") is True

    def test_valid_maximum_length(self):
        """Maximum valid: + followed by 15 digits."""
        assert is_valid_e164("+123456789012345") is True
