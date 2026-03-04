"""
WhatsApp Message Templates - Bilingual (English/Hindi)

User-centric templates emphasizing photo-based flood reporting.
Every template ends with a clear call-to-action.
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ....infrastructure.models import User


# Template key constants
class TemplateKey:
    WELCOME = "WELCOME"
    HELP = "HELP"
    REPORT_FLOOD_DETECTED = "REPORT_FLOOD_DETECTED"
    REPORT_NO_FLOOD = "REPORT_NO_FLOOD"
    REPORT_NO_PHOTO = "REPORT_NO_PHOTO"
    REPORT_NO_PHOTO_SKIP = "REPORT_NO_PHOTO_SKIP"
    REPORT_PHOTO_ADDED = "REPORT_PHOTO_ADDED"
    RISK_HIGH = "RISK_HIGH"
    RISK_MODERATE = "RISK_MODERATE"
    RISK_LOW = "RISK_LOW"
    RISK_NO_LOCATION = "RISK_NO_LOCATION"
    LOCATION_NOT_FOUND = "LOCATION_NOT_FOUND"
    WARNINGS_ACTIVE = "WARNINGS_ACTIVE"
    WARNINGS_NONE = "WARNINGS_NONE"
    MY_AREAS = "MY_AREAS"
    MY_AREAS_EMPTY = "MY_AREAS_EMPTY"
    ACCOUNT_NOT_LINKED = "ACCOUNT_NOT_LINKED"
    LINK_PROMPT = "LINK_PROMPT"
    LINK_SUCCESS = "LINK_SUCCESS"
    LINK_ALREADY = "LINK_ALREADY"
    STATUS = "STATUS"
    ML_UNAVAILABLE = "ML_UNAVAILABLE"
    ERROR = "ERROR"
    CIRCLE_FLOOD_ALERT = "CIRCLE_FLOOD_ALERT"


TEMPLATES = {
    TemplateKey.WELCOME: {
        "en": """Welcome to FloodSafe!

Report floods happening around you. Your reports alert nearby residents and help authorities respond faster.

HOW TO REPORT A FLOOD:
1. Take a photo of the flooding
2. Tap + -> Location -> Send current location
3. Send both in one message!

That's it! We'll verify your photo and alert people nearby.

Other commands:
- RISK - Check flood risk at your location
- WARNINGS - Official IMD/CWC alerts
- HELP - All commands""",

        "hi": """FloodSafe में आपका स्वागत है!

अपने आसपास की बाढ़ की रिपोर्ट करें। आपकी रिपोर्ट पास के लोगों को अलर्ट करती है।

बाढ़ की रिपोर्ट कैसे करें:
1. बाढ़ की फोटो लें
2. + -> Location -> अपना स्थान भेजें
3. दोनों एक साथ भेजें!

हम आपकी फोटो verify करेंगे और पास के लोगों को alert करेंगे।

अन्य commands:
- RISK - अपने स्थान पर बाढ़ का जोखिम जांचें
- WARNINGS - आधिकारिक IMD/CWC अलर्ट
- HELP - सभी commands"""
    },

    TemplateKey.HELP: {
        "en": """FLOODSAFE COMMANDS

REPORT FLOODING (PRIMARY)
Send a photo + your location together!

CHECK CONDITIONS
- RISK - Flood risk at your location
- RISK [place] - Risk at a specific place
- WARNINGS - Official IMD/CWC alerts

YOUR ACCOUNT
- MY AREAS - Your watch areas
- LINK - Connect your FloodSafe account
- STATUS - Check account status

Need help? Visit floodsafe.app/help""",

        "hi": """FLOODSAFE COMMANDS

बाढ़ की रिपोर्ट (मुख्य)
फोटो + अपना स्थान एक साथ भेजें!

स्थिति जांचें
- RISK - अपने स्थान पर बाढ़ का जोखिम
- RISK [जगह] - किसी विशेष स्थान पर जोखिम
- WARNINGS - आधिकारिक IMD/CWC अलर्ट

आपका खाता
- MY AREAS - आपके watch areas
- LINK - FloodSafe खाता जोड़ें
- STATUS - खाता स्थिति जांचें"""
    },

    TemplateKey.REPORT_FLOOD_DETECTED: {
        "en": """FLOOD REPORT SUBMITTED

Location: {location}
AI Verification: FLOODING DETECTED ({confidence}% confidence)
Severity: {severity}

{alerts_count} people in nearby watch areas have been alerted.

Your report helps others avoid this area. Stay safe!

Reply RISK to check flood risk at other locations.""",

        "hi": """बाढ़ रिपोर्ट सबमिट हो गई

स्थान: {location}
AI सत्यापन: बाढ़ का पता चला ({confidence}% confidence)
गंभीरता: {severity}

{alerts_count} पास के लोगों को अलर्ट भेजा गया।

आपकी रिपोर्ट दूसरों को इस क्षेत्र से बचने में मदद करती है। सुरक्षित रहें!"""
    },

    TemplateKey.REPORT_NO_FLOOD: {
        "en": """REPORT RECEIVED

Location: {location}
AI Verification: No flooding detected in image

We've logged your report for review. If you believe this is flooding, our team will verify manually.

Thank you for helping keep your community informed!""",

        "hi": """रिपोर्ट प्राप्त हुई

स्थान: {location}
AI सत्यापन: छवि में बाढ़ नहीं मिली

हमने आपकी रिपोर्ट समीक्षा के लिए दर्ज कर ली है। अगर आपको लगता है कि यह बाढ़ है, तो हमारी टीम manually verify करेगी।

समुदाय को जानकारी देने के लिए धन्यवाद!"""
    },

    TemplateKey.REPORT_NO_PHOTO: {
        "en": """Location received!

TIP: Add a photo for faster verification!

Take a photo of the flooding and send it now. Photos help our AI verify the report and alert more people.

Or reply SKIP to submit without photo.""",

        "hi": """स्थान प्राप्त हुआ!

सुझाव: तेज़ सत्यापन के लिए फोटो जोड़ें!

बाढ़ की फोटो लें और अभी भेजें। फोटो हमारे AI को रिपोर्ट verify करने और अधिक लोगों को alert करने में मदद करती है।

या बिना फोटो के सबमिट करने के लिए SKIP भेजें।"""
    },

    TemplateKey.REPORT_NO_PHOTO_SKIP: {
        "en": """SOS REPORT SUBMITTED

Location: {location}
Status: Unverified (no photo)

{alerts_count} people nearby have been alerted.

Next time, add a photo for faster verification!""",

        "hi": """SOS रिपोर्ट सबमिट हो गई

स्थान: {location}
स्थिति: असत्यापित (कोई फोटो नहीं)

{alerts_count} पास के लोगों को अलर्ट भेजा गया।

अगली बार, तेज़ सत्यापन के लिए फोटो जोड़ें!"""
    },

    TemplateKey.REPORT_PHOTO_ADDED: {
        "en": """PHOTO ADDED TO REPORT

Location: {location}
AI Verification: {classification}
{confidence_text}

{alerts_count} people in nearby watch areas have been notified.

Stay safe!""",

        "hi": """फोटो रिपोर्ट में जोड़ी गई

स्थान: {location}
AI सत्यापन: {classification}
{confidence_text}

{alerts_count} पास के लोगों को सूचित किया गया।

सुरक्षित रहें!"""
    },

    TemplateKey.RISK_HIGH: {
        "en": """FLOOD RISK ANALYSIS

Location: {location}

Current Risk Level: HIGH

Factors:
{factors}

Waterlogging likely in this area. Consider alternate routes if commuting.

Send your location + photo to report flooding.""",

        "hi": """बाढ़ जोखिम विश्लेषण

स्थान: {location}

वर्तमान जोखिम स्तर: उच्च

कारक:
{factors}

इस इलाके में जलभराव की संभावना है। यात्रा करते समय वैकल्पिक मार्ग अपनाएं।

बाढ़ की रिपोर्ट करने के लिए अपना स्थान + फोटो भेजें।"""
    },

    TemplateKey.RISK_MODERATE: {
        "en": """FLOOD RISK ANALYSIS

Location: {location}

Current Risk Level: MODERATE

Factors:
{factors}

Some waterlogging possible. Take care near underpasses and low-lying roads.

Reply with a place name for risk elsewhere:
Example: "RISK Lajpat Nagar\"""",

        "hi": """बाढ़ जोखिम विश्लेषण

स्थान: {location}

वर्तमान जोखिम स्तर: मध्यम

कारक:
{factors}

कुछ जलभराव संभव है। अंडरपास और निचली सड़कों पर ध्यान रखें।

अन्य जगह के लिए: "RISK [जगह का नाम]\""""
    },

    TemplateKey.RISK_LOW: {
        "en": """FLOOD RISK: {location}

Current Risk Level: LOW

No waterlogging reported. Area drains well.

Send your location to check risk where you are.""",

        "hi": """बाढ़ जोखिम: {location}

वर्तमान जोखिम स्तर: कम

कोई जलभराव रिपोर्ट नहीं। क्षेत्र में अच्छी drainage है।

जहां आप हैं वहां जोखिम जांचने के लिए अपना स्थान भेजें।"""
    },

    TemplateKey.RISK_NO_LOCATION: {
        "en": """To check flood risk, please:

1. Share your location, OR
2. Type a place name: "RISK Connaught Place\"""",

        "hi": """बाढ़ जोखिम जांचने के लिए:

1. अपना स्थान भेजें, या
2. जगह का नाम लिखें: "RISK Connaught Place\""""
    },

    TemplateKey.LOCATION_NOT_FOUND: {
        "en": """Location not found: "{query}"

Try a more specific place name or landmark.
Example: "RISK India Gate" or "RISK Sector 12 Noida\"""",

        "hi": """स्थान नहीं मिला: "{query}"

अधिक विशिष्ट जगह का नाम या landmark आज़माएं।
उदाहरण: "RISK India Gate" या "RISK Sector 12 Noida\""""
    },

    TemplateKey.WARNINGS_ACTIVE: {
        "en": """OFFICIAL FLOOD ALERTS

{city} - Active Alerts:

{alerts}

Last updated: {updated}

Send your location to report flooding in your area.""",

        "hi": """आधिकारिक बाढ़ अलर्ट

{city} - सक्रिय अलर्ट:

{alerts}

अंतिम अपडेट: {updated}

अपने क्षेत्र में बाढ़ की रिपोर्ट करने के लिए अपना स्थान भेजें।"""
    },

    TemplateKey.WARNINGS_NONE: {
        "en": """NO ACTIVE ALERTS

No official flood warnings for {city} right now.

Stay prepared during monsoon season!

Send your location + photo to report flooding.""",

        "hi": """कोई सक्रिय अलर्ट नहीं

{city} के लिए अभी कोई आधिकारिक बाढ़ चेतावनी नहीं है।

मानसून के मौसम में तैयार रहें!

बाढ़ की रिपोर्ट करने के लिए अपना स्थान + फोटो भेजें।"""
    },

    TemplateKey.MY_AREAS: {
        "en": """YOUR WATCH AREAS

{areas_list}

You'll get alerts when flooding is reported near these areas.

Manage areas in the FloodSafe app.""",

        "hi": """आपके WATCH AREAS

{areas_list}

जब इन क्षेत्रों के पास बाढ़ की रिपोर्ट होगी तो आपको अलर्ट मिलेगा।

FloodSafe app में areas manage करें।"""
    },

    TemplateKey.MY_AREAS_EMPTY: {
        "en": """You haven't set up any watch areas yet.

Open the FloodSafe app to add areas you want to monitor for flood reports.""",

        "hi": """आपने अभी तक कोई watch area सेट नहीं किया है।

बाढ़ रिपोर्ट के लिए निगरानी करने वाले क्षेत्र जोड़ने के लिए FloodSafe app खोलें।"""
    },

    TemplateKey.ACCOUNT_NOT_LINKED: {
        "en": """LINK YOUR ACCOUNT

To view your watch areas, connect your FloodSafe account.

Reply LINK to get started, or download the app to create an account.""",

        "hi": """खाता लिंक करें

अपने watch areas देखने के लिए, अपना FloodSafe खाता कनेक्ट करें।

शुरू करने के लिए LINK भेजें, या खाता बनाने के लिए app download करें।"""
    },

    TemplateKey.LINK_PROMPT: {
        "en": """LINK YOUR ACCOUNT

Benefits of linking:
- Your reports appear in your profile
- Get alerts for your watch areas via WhatsApp
- Build reputation as verified reporter

Reply with your FloodSafe account email:""",

        "hi": """खाता लिंक करें

लिंक करने के फायदे:
- आपकी रिपोर्ट आपकी profile में दिखेंगी
- WhatsApp पर watch areas के लिए अलर्ट मिलेंगे
- सत्यापित reporter के रूप में प्रतिष्ठा बनाएं

अपना FloodSafe खाता email भेजें:"""
    },

    TemplateKey.LINK_SUCCESS: {
        "en": """ACCOUNT LINKED!

Email: {email}
Phone: {phone}

Your future reports will be linked to your profile.

Send a photo + location to report flooding!""",

        "hi": """खाता लिंक हो गया!

Email: {email}
Phone: {phone}

आपकी भविष्य की रिपोर्ट आपकी profile से जुड़ी होंगी।

बाढ़ की रिपोर्ट करने के लिए फोटो + स्थान भेजें!"""
    },

    TemplateKey.LINK_ALREADY: {
        "en": """Your WhatsApp is already linked to {email}.

No action needed!""",

        "hi": """आपका WhatsApp पहले से {email} से लिंक है।

कोई कार्रवाई आवश्यक नहीं!"""
    },

    TemplateKey.STATUS: {
        "en": """YOUR STATUS

{status_info}

Send your location + photo to report flooding.""",

        "hi": """आपकी स्थिति

{status_info}

बाढ़ की रिपोर्ट करने के लिए अपना स्थान + फोटो भेजें।"""
    },

    TemplateKey.ML_UNAVAILABLE: {
        "en": """REPORT SUBMITTED

Location: {location}

Note: AI verification is temporarily unavailable. Your report will be reviewed manually.

{alerts_count} people nearby have been alerted.""",

        "hi": """रिपोर्ट सबमिट हो गई

स्थान: {location}

नोट: AI सत्यापन अस्थायी रूप से उपलब्ध नहीं है। आपकी रिपोर्ट manually review होगी।

{alerts_count} पास के लोगों को अलर्ट भेजा गया।"""
    },

    TemplateKey.ERROR: {
        "en": """Something went wrong. Please try again.

If the problem persists, visit floodsafe.app for help.""",

        "hi": """कुछ गलत हो गया। कृपया पुनः प्रयास करें।

यदि समस्या बनी रहती है, तो मदद के लिए floodsafe.app पर जाएं।"""
    },

    TemplateKey.CIRCLE_FLOOD_ALERT: {
        "en": """\U0001f6a8 {reporter_name} reported flooding near your area.
Circle: {circle_name}
{description}

Open FloodSafe for details.""",

        "hi": """\U0001f6a8 {reporter_name} ने आपके क्षेत्र में बाढ़ की रिपोर्ट की।
सर्कल: {circle_name}
{description}

विवरण के लिए FloodSafe खोलें।"""
    },
}


def get_user_language(user) -> str:
    """
    Get user's preferred language.
    Falls back to English if not set or user not linked.
    """
    if user and hasattr(user, 'language') and user.language:
        lang = user.language.lower()
        if lang in ['hi', 'hindi']:
            return 'hi'
    return 'en'


def get_message(
    key: str,
    language: str = 'en',
    **kwargs
) -> str:
    """
    Get a message template in the specified language.

    Args:
        key: Template key (from TemplateKey class)
        language: 'en' or 'hi' (default: 'en')
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted message string

    Example:
        get_message(TemplateKey.RISK_LOW, 'en', location="Janpath, New Delhi")
    """
    template_set = TEMPLATES.get(key)
    if not template_set:
        return f"[Template not found: {key}]"

    # Fall back to English if language not available
    template = template_set.get(language, template_set.get('en', ''))

    try:
        return template.format(**kwargs)
    except KeyError as e:
        # Missing variable - return template with placeholder shown
        return template


def format_risk_factors(
    elevation: float = None,
    rainfall: float = None,
    drainage: str = None,
    is_hotspot: bool = False,
    language: str = 'en'
) -> str:
    """Format risk factors for RISK command response."""
    factors = []

    if elevation is not None:
        label = "Elevation" if language == 'en' else "ऊंचाई"
        if elevation < 210:
            factors.append(f"- {label}: Low-lying area ({elevation:.0f}m)")
        else:
            factors.append(f"- {label}: {elevation:.0f}m")

    if rainfall is not None:
        label = "Recent rainfall" if language == 'en' else "हाल की बारिश"
        factors.append(f"- {label}: {rainfall:.0f}mm in last 6 hours")

    if drainage:
        label = "Drainage" if language == 'en' else "Drainage"
        factors.append(f"- {label}: {drainage}")

    if is_hotspot:
        if language == 'en':
            factors.append("- Known waterlogging spot")
        else:
            factors.append("- ज्ञात जलभराव स्थान")

    return "\n".join(factors) if factors else "- General area assessment"


def format_alerts_list(alerts: list, language: str = 'en') -> str:
    """Format official alerts for WARNINGS command response."""
    if not alerts:
        return ""

    formatted = []
    for alert in alerts:
        severity = alert.get('severity', 'yellow').upper()
        source = alert.get('source', 'Unknown')
        title = alert.get('title', 'Alert')
        description = alert.get('description', '')

        emoji = {
            'RED': '\U0001F534',      # Red circle
            'ORANGE': '\U0001F7E0',   # Orange circle
            'YELLOW': '\U0001F7E1',   # Yellow circle
        }.get(severity, '\u26A0\uFE0F')  # Warning sign

        formatted.append(f"{emoji} {severity} ALERT ({source})\n{title}\n{description}")

    return "\n\n".join(formatted)


def format_watch_areas(areas: list, language: str = 'en') -> str:
    """Format watch areas for MY AREAS command response."""
    if not areas:
        return ""

    formatted = []
    for i, area in enumerate(areas, 1):
        name = area.get('name', 'Unknown')
        label = area.get('label', '')
        risk = area.get('risk_level', 'low').upper()
        reports = area.get('recent_reports', 0)

        risk_emoji = {
            'HIGH': '\U0001F534',      # Red
            'MODERATE': '\U0001F7E1',  # Yellow
            'LOW': '\U0001F7E2',       # Green
        }.get(risk, '\U0001F7E2')

        label_text = f" ({label})" if label else ""
        reports_text = f"{reports} reports nearby" if reports else "No reports in last 24h"
        if language == 'hi':
            reports_text = f"{reports} रिपोर्ट पास में" if reports else "पिछले 24 घंटों में कोई रिपोर्ट नहीं"

        formatted.append(f"{i}. {name}{label_text}\n   Risk: {risk_emoji} {risk}\n   {reports_text}")

    return "\n\n".join(formatted)
