#!/usr/bin/env python3
"""
Create Twilio Content Templates for WhatsApp Quick Reply Buttons

Run this script once to register all required templates in Twilio.
Templates are created with quick-reply buttons for interactive messaging.

Usage:
    python scripts/create_twilio_templates.py

Environment Variables:
    TWILIO_ACCOUNT_SID: Your Twilio Account SID
    TWILIO_AUTH_TOKEN: Your Twilio Auth Token

Note: Templates created here do NOT need WhatsApp approval for in-session use.
Just save them (don't submit for approval) and use the Content SID.
"""
import os
import sys
import json
import requests
from typing import List, Tuple, Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings


CONTENT_API_URL = "https://content.twilio.com/v1/Content"


def create_template(
    friendly_name: str,
    body: str,
    buttons: List[Tuple[str, str]],
    language: str = "en"
) -> Optional[str]:
    """
    Create a Content Template in Twilio.

    Returns Content SID (HX...) if successful.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        print("Error: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")
        return None

    # Build button actions
    actions = [{"id": btn_id, "title": btn_title} for btn_id, btn_title in buttons[:3]]

    payload = {
        "friendly_name": friendly_name,
        "language": language,
        "types": {
            "twilio/quick-reply": {
                "body": body,
                "actions": actions
            },
            "twilio/text": {
                "body": body  # Fallback for non-WhatsApp
            }
        }
    }

    try:
        response = requests.post(
            CONTENT_API_URL,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            json=payload,
            timeout=15
        )

        if response.status_code == 201:
            data = response.json()
            sid = data.get("sid")
            print(f"✅ Created: {friendly_name} -> {sid}")
            return sid
        elif response.status_code == 409:
            print(f"⚠️  Already exists: {friendly_name}")
            # Try to find the existing SID
            return get_template_sid(friendly_name)
        else:
            print(f"❌ Failed: {friendly_name} - {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error: {friendly_name} - {e}")
        return None


def get_template_sid(friendly_name: str) -> Optional[str]:
    """Get SID of existing template by name."""
    try:
        response = requests.get(
            CONTENT_API_URL,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            for content in data.get("contents", []):
                if content.get("friendly_name") == friendly_name:
                    return content.get("sid")

        return None

    except Exception as e:
        print(f"Error fetching templates: {e}")
        return None


def main():
    """Create all required Content Templates."""
    print("=" * 60)
    print("Creating Twilio Content Templates for FloodSafe")
    print("=" * 60)
    print()

    # Check credentials
    if not settings.TWILIO_ACCOUNT_SID:
        print("Error: TWILIO_ACCOUNT_SID not set in environment")
        print("Set it in .env or as environment variable")
        sys.exit(1)

    if not settings.TWILIO_AUTH_TOKEN:
        print("Error: TWILIO_AUTH_TOKEN not set in environment")
        print("Set it in .env or as environment variable")
        sys.exit(1)

    print(f"Account SID: {settings.TWILIO_ACCOUNT_SID[:8]}...")
    print()

    # Define all templates
    templates = [
        # English templates
        {
            "name": "floodsafe_welcome_en",
            "body": "🌊 Welcome to FloodSafe!\n\nReport floods happening around you.\nYour reports alert nearby residents.",
            "buttons": [
                ("report_flood", "📸 Report Flood"),
                ("check_risk", "🔍 Check Risk"),
                ("view_alerts", "⚠️ Alerts"),
            ],
            "language": "en"
        },
        {
            "name": "floodsafe_after_location_en",
            "body": "📍 Location received!\n\nAdd a photo for faster verification.\nPhotos help our AI confirm flooding.",
            "buttons": [
                ("add_photo", "📸 Add Photo"),
                ("submit_anyway", "✅ Submit Anyway"),
                ("cancel", "❌ Cancel"),
            ],
            "language": "en"
        },
        {
            "name": "floodsafe_after_report_en",
            "body": "✅ Report submitted!\n\nWhat would you like to do next?",
            "buttons": [
                ("check_risk", "🔍 Check Risk"),
                ("report_another", "📸 Report Another"),
                ("menu", "🏠 Menu"),
            ],
            "language": "en"
        },
        {
            "name": "floodsafe_risk_result_en",
            "body": "📊 Risk check complete.\n\nWhat would you like to do next?",
            "buttons": [
                ("check_my_location", "📍 My Location"),
                ("view_alerts", "⚠️ Alerts"),
                ("menu", "🏠 Menu"),
            ],
            "language": "en"
        },
        {
            "name": "floodsafe_alerts_result_en",
            "body": "⚠️ Alerts loaded.\n\nWhat would you like to do next?",
            "buttons": [
                ("check_risk", "🔍 Check Risk"),
                ("report_flood", "📸 Report"),
                ("menu", "🏠 Menu"),
            ],
            "language": "en"
        },
        {
            "name": "floodsafe_menu_en",
            "body": "What would you like to do?",
            "buttons": [
                ("report_flood", "📸 Report Flood"),
                ("check_risk", "🔍 Check Risk"),
                ("view_alerts", "⚠️ Alerts"),
            ],
            "language": "en"
        },

        # Hindi templates
        {
            "name": "floodsafe_welcome_hi",
            "body": "🌊 FloodSafe में आपका स्वागत है!\n\nअपने आसपास की बाढ़ की रिपोर्ट करें।\nआपकी रिपोर्ट पास के लोगों को अलर्ट करती है।",
            "buttons": [
                ("report_flood", "📸 बाढ़ रिपोर्ट"),
                ("check_risk", "🔍 जोखिम जांचें"),
                ("view_alerts", "⚠️ अलर्ट"),
            ],
            "language": "hi"
        },
        {
            "name": "floodsafe_after_location_hi",
            "body": "📍 स्थान प्राप्त हुआ!\n\nतेज़ verification के लिए फोटो जोड़ें।\nफोटो हमारे AI को बाढ़ confirm करने में मदद करती है।",
            "buttons": [
                ("add_photo", "📸 फोटो जोड़ें"),
                ("submit_anyway", "✅ बिना फोटो भेजें"),
                ("cancel", "❌ रद्द करें"),
            ],
            "language": "hi"
        },
        {
            "name": "floodsafe_menu_hi",
            "body": "आप क्या करना चाहेंगे?",
            "buttons": [
                ("report_flood", "📸 बाढ़ रिपोर्ट"),
                ("check_risk", "🔍 जोखिम जांचें"),
                ("view_alerts", "⚠️ अलर्ट"),
            ],
            "language": "hi"
        },
    ]

    # Create templates
    created = 0
    failed = 0
    sids = {}

    for template in templates:
        sid = create_template(
            friendly_name=template["name"],
            body=template["body"],
            buttons=template["buttons"],
            language=template["language"]
        )
        if sid:
            sids[template["name"]] = sid
            created += 1
        else:
            failed += 1

    print()
    print("=" * 60)
    print(f"Summary: {created} created, {failed} failed")
    print("=" * 60)

    if sids:
        print()
        print("Template SIDs (add to config if needed):")
        print("-" * 60)
        for name, sid in sids.items():
            print(f"  {name}: {sid}")

    print()
    print("Done! Templates are ready for in-session use.")
    print("No WhatsApp approval needed for messages within 24h session window.")


if __name__ == "__main__":
    main()
