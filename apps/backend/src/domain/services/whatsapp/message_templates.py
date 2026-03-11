"""
WhatsApp Message Templates - Trilingual (English/Hindi/Indonesian)

User-centric templates emphasizing photo-based flood reporting.
Every template ends with a clear call-to-action.

Languages: en (English), hi (Hindi), id (Indonesian/Bahasa Indonesia)
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
    RISK_UNAVAILABLE = "RISK_UNAVAILABLE"
    WARNINGS_UNAVAILABLE = "WARNINGS_UNAVAILABLE"
    SEND_FAILED = "SEND_FAILED"
    SESSION_ERROR = "SESSION_ERROR"
    CIRCLE_FLOOD_ALERT = "CIRCLE_FLOOD_ALERT"
    CIRCLES_LIST = "CIRCLES_LIST"
    CIRCLE_CREATED = "CIRCLE_CREATED"
    CIRCLE_JOINED = "CIRCLE_JOINED"
    CIRCLE_ALREADY_MEMBER = "CIRCLE_ALREADY_MEMBER"
    CIRCLE_INVALID_CODE = "CIRCLE_INVALID_CODE"
    CIRCLE_INVITE_SHARE = "CIRCLE_INVITE_SHARE"
    CIRCLE_NOT_LINKED = "CIRCLE_NOT_LINKED"


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
- HELP - सभी commands""",

        "id": """Selamat datang di FloodSafe!

Laporkan banjir di sekitar Anda. Laporan Anda membantu warga sekitar dan pihak berwenang merespons lebih cepat.

CARA MELAPORKAN BANJIR:
1. Ambil foto genangan/banjir
2. Ketuk + -> Lokasi -> Kirim lokasi saat ini
3. Kirim keduanya dalam satu pesan!

Selesai! Kami akan verifikasi foto Anda dan memberi tahu warga sekitar.

Perintah lain:
- RISK - Cek risiko banjir di lokasi Anda
- WARNINGS - Peringatan resmi BMKG
- HELP - Semua perintah"""
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
- STATUS - खाता स्थिति जांचें""",

        "id": """PERINTAH FLOODSAFE

LAPORKAN BANJIR (UTAMA)
Kirim foto + lokasi Anda bersamaan!

CEK KONDISI
- RISK - Risiko banjir di lokasi Anda
- RISK [tempat] - Risiko di tempat tertentu
- WARNINGS - Peringatan resmi BMKG

AKUN ANDA
- MY AREAS - Area pantauan Anda
- LINK - Hubungkan akun FloodSafe
- STATUS - Cek status akun

Butuh bantuan? Kunjungi floodsafe.app/help"""
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

आपकी रिपोर्ट दूसरों को इस क्षेत्र से बचने में मदद करती है। सुरक्षित रहें!""",

        "id": """LAPORAN BANJIR TERKIRIM

Lokasi: {location}
Verifikasi AI: BANJIR TERDETEKSI ({confidence}% keyakinan)
Tingkat keparahan: {severity}

{alerts_count} orang di area pantauan terdekat telah diberitahu.

Laporan Anda membantu orang lain menghindari area ini. Tetap aman!"""
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

समुदाय को जानकारी देने के लिए धन्यवाद!""",

        "id": """LAPORAN DITERIMA

Lokasi: {location}
Verifikasi AI: Tidak ada banjir terdeteksi di gambar

Laporan Anda telah dicatat untuk ditinjau. Jika Anda yakin ini banjir, tim kami akan memverifikasi secara manual.

Terima kasih telah membantu komunitas Anda!"""
    },

    TemplateKey.REPORT_NO_PHOTO: {
        "en": """Location received!

TIP: Add a photo for faster verification!

Take a photo of the flooding and send it now. Photos help our AI verify the report and alert more people.

Or reply SKIP to submit without photo.""",

        "hi": """स्थान प्राप्त हुआ!

सुझाव: तेज़ सत्यापन के लिए फोटो जोड़ें!

बाढ़ की फोटो लें और अभी भेजें। फोटो हमारे AI को रिपोर्ट verify करने और अधिक लोगों को alert करने में मदद करती है।

या बिना फोटो के सबमिट करने के लिए SKIP भेजें।""",

        "id": """Lokasi diterima!

TIPS: Tambahkan foto untuk verifikasi lebih cepat!

Ambil foto banjir dan kirim sekarang. Foto membantu AI kami memverifikasi laporan dan memberi tahu lebih banyak orang.

Atau balas SKIP untuk mengirim tanpa foto."""
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

अगली बार, तेज़ सत्यापन के लिए फोटो जोड़ें!""",

        "id": """LAPORAN SOS TERKIRIM

Lokasi: {location}
Status: Belum diverifikasi (tanpa foto)

{alerts_count} orang terdekat telah diberitahu.

Lain kali, tambahkan foto untuk verifikasi lebih cepat!"""
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

सुरक्षित रहें!""",

        "id": """FOTO DITAMBAHKAN KE LAPORAN

Lokasi: {location}
Verifikasi AI: {classification}
{confidence_text}

{alerts_count} orang di area pantauan terdekat telah diberitahu.

Tetap aman!"""
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

बाढ़ की रिपोर्ट करने के लिए अपना स्थान + फोटो भेजें।""",

        "id": """ANALISIS RISIKO BANJIR

Lokasi: {location}

Tingkat Risiko Saat Ini: TINGGI

Faktor:
{factors}

Genangan air kemungkinan terjadi di area ini. Pertimbangkan rute alternatif saat bepergian.

Kirim lokasi + foto untuk melaporkan banjir."""
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

अन्य जगह के लिए: "RISK [जगह का नाम]\"""",

        "id": """ANALISIS RISIKO BANJIR

Lokasi: {location}

Tingkat Risiko Saat Ini: SEDANG

Faktor:
{factors}

Genangan air mungkin terjadi. Berhati-hatilah di underpass dan jalan rendah.

Cek tempat lain: "RISK [nama tempat]\""""
    },

    TemplateKey.RISK_LOW: {
        "en": """FLOOD RISK: {location}

Current Risk Level: LOW

No waterlogging reported. Area drains well.

Send your location to check risk where you are.""",

        "hi": """बाढ़ जोखिम: {location}

वर्तमान जोखिम स्तर: कम

कोई जलभराव रिपोर्ट नहीं। क्षेत्र में अच्छी drainage है।

जहां आप हैं वहां जोखिम जांचने के लिए अपना स्थान भेजें।""",

        "id": """RISIKO BANJIR: {location}

Tingkat Risiko Saat Ini: RENDAH

Tidak ada genangan dilaporkan. Area ini memiliki drainase yang baik.

Kirim lokasi Anda untuk cek risiko di tempat Anda."""
    },

    TemplateKey.RISK_NO_LOCATION: {
        "en": """To check flood risk, please:

1. Share your location, OR
2. Type a place name: "RISK Connaught Place\"""",

        "hi": """बाढ़ जोखिम जांचने के लिए:

1. अपना स्थान भेजें, या
2. जगह का नाम लिखें: "RISK Connaught Place\"""",

        "id": """Untuk cek risiko banjir:

1. Kirim lokasi Anda, ATAU
2. Ketik nama tempat: "RISK Malioboro\""""
    },

    TemplateKey.LOCATION_NOT_FOUND: {
        "en": """Location not found: "{query}"

Try a more specific place name or landmark.
Example: "RISK India Gate" or "RISK Sector 12 Noida\"""",

        "hi": """स्थान नहीं मिला: "{query}"

अधिक विशिष्ट जगह का नाम या landmark आज़माएं।
उदाहरण: "RISK India Gate" या "RISK Sector 12 Noida\"""",

        "id": """Lokasi tidak ditemukan: "{query}"

Coba nama tempat atau landmark yang lebih spesifik.
Contoh: "RISK Malioboro" atau "RISK Tugu Yogyakarta\""""
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

अपने क्षेत्र में बाढ़ की रिपोर्ट करने के लिए अपना स्थान भेजें।""",

        "id": """PERINGATAN BANJIR RESMI

{city} - Peringatan Aktif:

{alerts}

Terakhir diperbarui: {updated}

Kirim lokasi Anda untuk melaporkan banjir di area Anda."""
    },

    TemplateKey.WARNINGS_NONE: {
        "en": """NO ACTIVE ALERTS

No official flood warnings for {city} right now.

Stay prepared during monsoon season!

Send your location + photo to report flooding.""",

        "hi": """कोई सक्रिय अलर्ट नहीं

{city} के लिए अभी कोई आधिकारिक बाढ़ चेतावनी नहीं है।

मानसून के मौसम में तैयार रहें!

बाढ़ की रिपोर्ट करने के लिए अपना स्थान + फोटो भेजें।""",

        "id": """TIDAK ADA PERINGATAN AKTIF

Tidak ada peringatan banjir resmi untuk {city} saat ini.

Tetap waspada di musim hujan!

Kirim lokasi + foto untuk melaporkan banjir."""
    },

    TemplateKey.MY_AREAS: {
        "en": """YOUR WATCH AREAS

{areas_list}

You'll get alerts when flooding is reported near these areas.

Manage areas in the FloodSafe app.""",

        "hi": """आपके WATCH AREAS

{areas_list}

जब इन क्षेत्रों के पास बाढ़ की रिपोर्ट होगी तो आपको अलर्ट मिलेगा।

FloodSafe app में areas manage करें।""",

        "id": """AREA PANTAUAN ANDA

{areas_list}

Anda akan mendapat notifikasi saat banjir dilaporkan di dekat area ini.

Kelola area di aplikasi FloodSafe."""
    },

    TemplateKey.MY_AREAS_EMPTY: {
        "en": """You haven't set up any watch areas yet.

Open the FloodSafe app to add areas you want to monitor for flood reports.""",

        "hi": """आपने अभी तक कोई watch area सेट नहीं किया है।

बाढ़ रिपोर्ट के लिए निगरानी करने वाले क्षेत्र जोड़ने के लिए FloodSafe app खोलें।""",

        "id": """Anda belum mengatur area pantauan.

Buka aplikasi FloodSafe untuk menambahkan area yang ingin Anda pantau."""
    },

    TemplateKey.ACCOUNT_NOT_LINKED: {
        "en": """LINK YOUR ACCOUNT

To view your watch areas, connect your FloodSafe account.

Reply LINK to get started, or download the app to create an account.""",

        "hi": """खाता लिंक करें

अपने watch areas देखने के लिए, अपना FloodSafe खाता कनेक्ट करें।

शुरू करने के लिए LINK भेजें, या खाता बनाने के लिए app download करें।""",

        "id": """HUBUNGKAN AKUN ANDA

Untuk melihat area pantauan, hubungkan akun FloodSafe Anda.

Balas LINK untuk memulai, atau unduh aplikasi untuk membuat akun."""
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

अपना FloodSafe खाता email भेजें:""",

        "id": """HUBUNGKAN AKUN ANDA

Keuntungan menghubungkan:
- Laporan Anda muncul di profil Anda
- Dapatkan notifikasi area pantauan via WhatsApp
- Bangun reputasi sebagai pelapor terverifikasi

Balas dengan email akun FloodSafe Anda:"""
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

बाढ़ की रिपोर्ट करने के लिए फोटो + स्थान भेजें!""",

        "id": """AKUN TERHUBUNG!

Email: {email}
Telepon: {phone}

Laporan Anda selanjutnya akan terhubung ke profil Anda.

Kirim foto + lokasi untuk melaporkan banjir!"""
    },

    TemplateKey.LINK_ALREADY: {
        "en": """Your WhatsApp is already linked to {email}.

No action needed!""",

        "hi": """आपका WhatsApp पहले से {email} से लिंक है।

कोई कार्रवाई आवश्यक नहीं!""",

        "id": """WhatsApp Anda sudah terhubung ke {email}.

Tidak perlu tindakan lagi!"""
    },

    TemplateKey.STATUS: {
        "en": """YOUR STATUS

{status_info}

Send your location + photo to report flooding.""",

        "hi": """आपकी स्थिति

{status_info}

बाढ़ की रिपोर्ट करने के लिए अपना स्थान + फोटो भेजें।""",

        "id": """STATUS ANDA

{status_info}

Kirim lokasi + foto untuk melaporkan banjir."""
    },

    TemplateKey.ML_UNAVAILABLE: {
        "en": """REPORT SUBMITTED

Location: {location}

Note: AI verification is temporarily unavailable. Your report will be reviewed manually.

{alerts_count} people nearby have been alerted.""",

        "hi": """रिपोर्ट सबमिट हो गई

स्थान: {location}

नोट: AI सत्यापन अस्थायी रूप से उपलब्ध नहीं है। आपकी रिपोर्ट manually review होगी।

{alerts_count} पास के लोगों को अलर्ट भेजा गया।""",

        "id": """LAPORAN TERKIRIM

Lokasi: {location}

Catatan: Verifikasi AI tidak tersedia sementara. Laporan Anda akan ditinjau secara manual.

{alerts_count} orang terdekat telah diberitahu."""
    },

    TemplateKey.ERROR: {
        "en": """Something went wrong. Please try again.

If the problem persists, visit floodsafe.app for help.""",

        "hi": """कुछ गलत हो गया। कृपया पुनः प्रयास करें।

यदि समस्या बनी रहती है, तो मदद के लिए floodsafe.app पर जाएं।""",

        "id": """Terjadi kesalahan. Silakan coba lagi.

Jika masalah berlanjut, kunjungi floodsafe.app untuk bantuan."""
    },

    TemplateKey.RISK_UNAVAILABLE: {
        "en": """Unable to check flood risk right now.

Please try again in a few minutes. If the problem persists, check the FloodSafe app for live risk data.

Send your location + photo to report flooding.""",

        "hi": """अभी बाढ़ जोखिम जांचने में असमर्थ।

कुछ मिनटों बाद पुनः प्रयास करें। समस्या बनी रहे तो FloodSafe app पर live risk data देखें।

बाढ़ की रिपोर्ट करने के लिए स्थान + फोटो भेजें।""",

        "id": """Tidak dapat memeriksa risiko banjir saat ini.

Coba lagi dalam beberapa menit. Jika masalah berlanjut, cek aplikasi FloodSafe untuk data risiko terkini.

Kirim lokasi + foto untuk melaporkan banjir."""
    },

    TemplateKey.WARNINGS_UNAVAILABLE: {
        "en": """Unable to fetch flood alerts right now.

Please check the FloodSafe app for the latest official warnings, or try again shortly.

Send your location + photo to report flooding.""",

        "hi": """अभी बाढ़ अलर्ट प्राप्त करने में असमर्थ।

नवीनतम आधिकारिक चेतावनियों के लिए FloodSafe app देखें, या कुछ देर बाद पुनः प्रयास करें।

बाढ़ की रिपोर्ट करने के लिए स्थान + फोटो भेजें।""",

        "id": """Tidak dapat mengambil peringatan banjir saat ini.

Cek aplikasi FloodSafe untuk peringatan resmi terbaru, atau coba lagi nanti.

Kirim lokasi + foto untuk melaporkan banjir."""
    },

    TemplateKey.SEND_FAILED: {
        "en": """Message failed to send. Please try again.

If the problem persists, visit floodsafe.app for help.""",

        "hi": """संदेश भेजने में विफल। कृपया पुनः प्रयास करें।

समस्या बनी रहे तो floodsafe.app पर जाएं।""",

        "id": """Pesan gagal dikirim. Silakan coba lagi.

Jika masalah berlanjut, kunjungi floodsafe.app."""
    },

    TemplateKey.SESSION_ERROR: {
        "en": """Something went wrong. Please start over by sending 'hi'.

If the problem persists, visit floodsafe.app for help.""",

        "hi": """कुछ गलत हो गया। 'hi' भेजकर दोबारा शुरू करें।

समस्या बनी रहे तो floodsafe.app पर जाएं।""",

        "id": """Terjadi kesalahan. Mulai ulang dengan mengirim 'hi'.

Jika masalah berlanjut, kunjungi floodsafe.app."""
    },

    TemplateKey.CIRCLE_FLOOD_ALERT: {
        "en": """\U0001f6a8 {reporter_name} reported flooding near your area.
Circle: {circle_name}
{description}

Open FloodSafe for details.""",

        "hi": """\U0001f6a8 {reporter_name} ने आपके क्षेत्र में बाढ़ की रिपोर्ट की।
सर्कल: {circle_name}
{description}

विवरण के लिए FloodSafe खोलें।""",

        "id": """\U0001f6a8 {reporter_name} melaporkan banjir di dekat area Anda.
Lingkaran: {circle_name}
{description}

Buka FloodSafe untuk detail."""
    },

    TemplateKey.CIRCLES_LIST: {
        "en": """YOUR SAFETY CIRCLES ({count})

{circles_list}

Reply "INVITE [number]" to share an invite code.
Reply "CREATE [name]" to create a new circle.
Reply "JOIN [code]" to join a circle.""",

        "hi": """आपकी सुरक्षा सर्कल ({count})

{circles_list}

"INVITE [नंबर]" — आमंत्रण कोड शेयर करें
"CREATE [नाम]" — नई सर्कल बनाएं
"JOIN [कोड]" — सर्कल में शामिल हों""",

        "id": """LINGKARAN KESELAMATAN ANDA ({count})

{circles_list}

Balas "INVITE [nomor]" untuk bagikan kode undangan.
Balas "CREATE [nama]" untuk buat lingkaran baru.
Balas "JOIN [kode]" untuk bergabung."""
    },

    TemplateKey.CIRCLE_CREATED: {
        "en": """Circle "{name}" created!

Invite code: {code}

Share this code with family and friends.
They can join by sending: JOIN {code}""",

        "hi": """सर्कल "{name}" बनाई गई!

आमंत्रण कोड: {code}

इस कोड को परिवार और दोस्तों से शेयर करें।
वे JOIN {code} भेजकर शामिल हो सकते हैं।""",

        "id": """Lingkaran "{name}" dibuat!

Kode undangan: {code}

Bagikan kode ini ke keluarga dan teman.
Mereka bisa bergabung dengan mengirim: JOIN {code}"""
    },

    TemplateKey.CIRCLE_JOINED: {
        "en": """You joined "{name}"!

You'll get alerts when members report flooding nearby. Stay safe together!""",

        "hi": """आप "{name}" में शामिल हो गए!

जब सदस्य पास में बाढ़ की रिपोर्ट करेंगे तो आपको अलर्ट मिलेगा। एक साथ सुरक्षित रहें!""",

        "id": """Anda bergabung di "{name}"!

Anda akan mendapat notifikasi saat anggota melaporkan banjir di sekitar. Tetap aman bersama!"""
    },

    TemplateKey.CIRCLE_ALREADY_MEMBER: {
        "en": """You're already a member of this circle.""",

        "hi": """आप पहले से इस सर्कल के सदस्य हैं।""",

        "id": """Anda sudah menjadi anggota lingkaran ini."""
    },

    TemplateKey.CIRCLE_INVALID_CODE: {
        "en": """Invalid invite code. Please check and try again.

To join a circle, send: JOIN [invite code]""",

        "hi": """अमान्य आमंत्रण कोड। कृपया जांचें और पुनः प्रयास करें।

सर्कल में शामिल होने के लिए भेजें: JOIN [आमंत्रण कोड]""",

        "id": """Kode undangan tidak valid. Silakan periksa dan coba lagi.

Untuk bergabung, kirim: JOIN [kode undangan]"""
    },

    TemplateKey.CIRCLE_INVITE_SHARE: {
        "en": """Join my FloodSafe safety circle "{name}"!

Send "JOIN {code}" to +91 9035398881 on WhatsApp to join.

FloodSafe alerts you when circle members report flooding nearby. Stay safe together!""",

        "hi": """मेरी FloodSafe सुरक्षा सर्कल "{name}" में शामिल हों!

WhatsApp पर +91 9035398881 को "JOIN {code}" भेजें।

FloodSafe आपको सतर्क करता है जब सर्कल सदस्य पास में बाढ़ की रिपोर्ट करते हैं। एक साथ सुरक्षित रहें!""",

        "id": """Bergabunglah di lingkaran keselamatan FloodSafe saya "{name}"!

Kirim "JOIN {code}" ke +91 9035398881 di WhatsApp untuk bergabung.

FloodSafe memberi tahu Anda saat anggota melaporkan banjir di sekitar. Tetap aman bersama!"""
    },

    TemplateKey.CIRCLE_NOT_LINKED: {
        "en": """Link your account first to manage circles.

Reply LINK to connect your FloodSafe account.""",

        "hi": """सर्कल प्रबंधित करने के लिए पहले अपना खाता लिंक करें।

अपना FloodSafe खाता जोड़ने के लिए LINK भेजें।""",

        "id": """Hubungkan akun Anda terlebih dahulu untuk mengelola lingkaran.

Balas LINK untuk menghubungkan akun FloodSafe Anda."""
    },
}


def get_user_language(user, city: str = None, phone: str = None) -> str:
    """
    Get user's preferred language.

    Priority: user.language > city fallback > phone prefix fallback > English.

    Args:
        user: User object (may be None for anonymous)
        city: City name for fallback (e.g. "yogyakarta" → "id")
        phone: Phone number for fallback (e.g. "+62..." → "id")
    """
    if user and hasattr(user, 'language') and user.language:
        lang = user.language.lower()
        if lang in ('hi', 'hindi'):
            return 'hi'
        if lang in ('id', 'indonesian', 'bahasa'):
            return 'id'

    # City-based fallback
    if city:
        city_lang = _CITY_TO_LANGUAGE.get(city.lower())
        if city_lang:
            return city_lang

    # Phone prefix fallback (for anonymous users)
    if phone:
        clean = phone.strip().replace(" ", "").replace("-", "")
        if clean.startswith("+62") or clean.startswith("62"):
            return 'id'

    return 'en'


_CITY_TO_LANGUAGE = {
    "yogyakarta": "id",
    # Indian cities default to English (Hindi via user.language)
    # Singapore defaults to English
}


def get_message(
    key: str,
    language: str = 'en',
    **kwargs
) -> str:
    """
    Get a message template in the specified language.

    Args:
        key: Template key (from TemplateKey class)
        language: 'en', 'hi', or 'id' (default: 'en')
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
