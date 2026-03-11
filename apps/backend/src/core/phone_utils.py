"""Shared phone number normalization — single source of truth.

All phone handling (normalization + validation) consolidated here.
Used by: notification_service, sos_service, circle_service, auth_service,
         whatsapp_meta, webhook.
"""
import re

# Country codes for supported regions
COUNTRY_CODES = {
    "IN": "+91",  # India (10-digit mobile)
    "ID": "+62",  # Indonesia (10-12 digit mobile)
    "SG": "+65",  # Singapore (8-digit mobile)
}

E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")

# City → country code mapping for WhatsApp (determines phone normalization)
CITY_TO_COUNTRY = {
    "delhi": "IN",
    "bangalore": "IN",
    "indore": "IN",
    "yogyakarta": "ID",
    "singapore": "SG",
}


def detect_country_from_phone(phone: str) -> str:
    """Detect country from phone prefix. Returns ISO alpha-2 code."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+62") or phone.startswith("62"):
        return "ID"
    if phone.startswith("+65") or phone.startswith("65"):
        return "SG"
    if phone.startswith("+91") or phone.startswith("91"):
        return "IN"
    return "IN"  # Default fallback


def city_to_country(city: str) -> str:
    """Get country code from city name. Returns ISO alpha-2 code."""
    return CITY_TO_COUNTRY.get(city.lower(), "IN")


def normalize_phone(phone: str, default_country: str = "IN") -> str:
    """Normalize phone number to E.164 format.

    Handles: spaces, hyphens, leading 0, bare 10-digit Indian numbers,
    bare 10-12 digit Indonesian numbers, already-formatted E.164.

    Args:
        phone: Raw phone string from user input or database.
        default_country: ISO 3166-1 alpha-2 code ("IN", "ID") used when
            the number has no country prefix.

    Returns:
        E.164 formatted phone string (e.g. "+919876543210").
    """
    phone = phone.strip().replace(" ", "").replace("-", "")

    # Already has country code
    if phone.startswith("+"):
        return phone

    # Strip leading 0 (common in local dialing)
    if phone.startswith("0"):
        phone = phone[1:]

    prefix = COUNTRY_CODES.get(default_country, "+91")

    # India: exactly 10 digits
    if default_country == "IN" and len(phone) == 10:
        return f"{prefix}{phone}"

    # Indonesia: 10-12 digits
    if default_country == "ID" and 10 <= len(phone) <= 12:
        return f"{prefix}{phone}"

    # Singapore: exactly 8 digits (mobile starts with 8 or 9)
    if default_country == "SG" and len(phone) == 8:
        return f"{prefix}{phone}"

    # Fallback: assume digits are a full number without +
    return f"+{phone}"


def is_valid_e164(phone: str) -> bool:
    """Check if phone is valid E.164 format."""
    return bool(E164_PATTERN.match(phone))
