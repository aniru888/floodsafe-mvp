import type { OnboardingBotLanguage } from '../../types/onboarding-bot';

/**
 * Translation map: ~50 keys × 3 languages (English, Hindi, Indonesian)
 * Simple inline object — no i18n framework overhead for 3 languages.
 */
const translations: Record<string, Record<OnboardingBotLanguage, string>> = {
    // ── Language picker ────────────────────────────────────────
    'lang.picker.title': {
        en: 'Choose your language',
        hi: 'अपनी भाषा चुनें',
        id: 'Pilih bahasa Anda',
    },
    'lang.english': {
        en: 'English',
        hi: 'English',
        id: 'English',
    },
    'lang.hindi': {
        en: 'हिंदी',
        hi: 'हिंदी',
        id: 'हिंदी',
    },
    'lang.indonesian': {
        en: 'Bahasa Indonesia',
        hi: 'Bahasa Indonesia',
        id: 'Bahasa Indonesia',
    },

    // ── Onboarding phase ───────────────────────────────────────
    'onboarding.welcome.title': {
        en: 'Hi! I\'m your FloodSafe guide',
        hi: 'नमस्ते! मैं आपका FloodSafe गाइड हूँ',
        id: 'Halo! Saya pemandu FloodSafe Anda',
    },
    'onboarding.welcome.message': {
        en: 'I\'ll help you set up your account. Pick your language and let\'s get started!',
        hi: 'मैं आपका अकाउंट सेट करने में मदद करूँगा। अपनी भाषा चुनें और शुरू करें!',
        id: 'Saya akan membantu Anda mengatur akun. Pilih bahasa dan mari mulai!',
    },
    'onboarding.city.title': {
        en: 'Select your city',
        hi: 'अपना शहर चुनें',
        id: 'Pilih kota Anda',
    },
    'onboarding.city.message': {
        en: 'Your city determines which flood alerts, weather data, and hotspots you see. Choose where you live.',
        hi: 'आपका शहर तय करता है कि आपको कौन से बाढ़ अलर्ट, मौसम डेटा और हॉटस्पॉट दिखेंगे।',
        id: 'Kota Anda menentukan peringatan banjir, data cuaca, dan titik rawan yang akan Anda lihat.',
    },
    'onboarding.profile.title': {
        en: 'Set up your profile',
        hi: 'अपनी प्रोफ़ाइल बनाएं',
        id: 'Siapkan profil Anda',
    },
    'onboarding.profile.message': {
        en: 'Your username identifies you in community reports. Phone is optional — for SMS flood alerts.',
        hi: 'आपका यूज़रनेम सामुदायिक रिपोर्ट में दिखता है। फ़ोन वैकल्पिक है — SMS अलर्ट के लिए।',
        id: 'Nama pengguna Anda terlihat di laporan komunitas. Telepon opsional — untuk peringatan SMS.',
    },
    'onboarding.watchAreas.title': {
        en: 'Add watch areas',
        hi: 'निगरानी क्षेत्र जोड़ें',
        id: 'Tambahkan area pantauan',
    },
    'onboarding.watchAreas.message': {
        en: 'Watch areas are locations you care about — home, office, school. You\'ll get alerts when flooding is detected nearby.',
        hi: 'निगरानी क्षेत्र वे जगहें हैं जो आपके लिए ज़रूरी हैं — घर, ऑफ़िस, स्कूल। पास में बाढ़ होने पर आपको अलर्ट मिलेगा।',
        id: 'Area pantauan adalah lokasi penting Anda — rumah, kantor, sekolah. Anda akan diberi peringatan saat banjir terdeteksi.',
    },
    'onboarding.routes.title': {
        en: 'Daily routes (optional)',
        hi: 'दैनिक मार्ग (वैकल्पिक)',
        id: 'Rute harian (opsional)',
    },
    'onboarding.routes.message': {
        en: 'Add your daily commute to get alerts about flooding along your path. You can skip this for now.',
        hi: 'अपना दैनिक रास्ता जोड़ें ताकि आपके मार्ग पर बाढ़ के अलर्ट मिलें। आप इसे अभी छोड़ सकते हैं।',
        id: 'Tambahkan rute perjalanan harian untuk mendapat peringatan banjir di sepanjang jalan Anda. Bisa dilewati.',
    },
    'onboarding.complete.title': {
        en: 'All set!',
        hi: 'सब तैयार!',
        id: 'Semuanya siap!',
    },
    'onboarding.complete.message': {
        en: 'Great job! Want a quick tour of the app features? It takes about 30 seconds.',
        hi: 'बहुत अच्छा! ऐप की विशेषताओं का एक छोटा दौरा चाहेंगे? इसमें लगभग 30 सेकंड लगेंगे।',
        id: 'Bagus! Mau tur singkat fitur aplikasi? Hanya sekitar 30 detik.',
    },

    // ── App tour phase ─────────────────────────────────────────
    'tour.home.title': {
        en: 'Welcome to FloodSafe!',
        hi: 'FloodSafe में आपका स्वागत है!',
        id: 'Selamat datang di FloodSafe!',
    },
    'tour.home.message': {
        en: 'This is your home dashboard. It shows your flood risk, recent reports, and quick actions.',
        hi: 'यह आपका होम डैशबोर्ड है। यहाँ बाढ़ जोखिम, हालिया रिपोर्ट और त्वरित कार्य दिखते हैं।',
        id: 'Ini adalah dasbor utama Anda. Menampilkan risiko banjir, laporan terbaru, dan aksi cepat.',
    },
    'tour.mapPreview.title': {
        en: 'Map preview',
        hi: 'मानचित्र पूर्वावलोकन',
        id: 'Pratinjau peta',
    },
    'tour.mapPreview.message': {
        en: 'A quick glance at flood conditions near you. Tap to open the full interactive map.',
        hi: 'आपके पास की बाढ़ स्थिति की एक झलक। पूरा मानचित्र खोलने के लिए टैप करें।',
        id: 'Sekilas kondisi banjir di sekitar Anda. Ketuk untuk membuka peta interaktif.',
    },
    'tour.recentReports.title': {
        en: 'Community reports',
        hi: 'सामुदायिक रिपोर्ट',
        id: 'Laporan komunitas',
    },
    'tour.recentReports.message': {
        en: 'Real-time flood reports from people in your city. This is where you\'ll see updates as they happen.',
        hi: 'आपके शहर के लोगों से वास्तविक समय की बाढ़ रिपोर्ट। यहाँ आप अपडेट देखेंगे।',
        id: 'Laporan banjir real-time dari warga di kota Anda. Di sinilah Anda akan melihat pembaruan.',
    },
    'tour.aiInsights.title': {
        en: 'AI risk insights',
        hi: 'AI जोखिम जानकारी',
        id: 'Wawasan risiko AI',
    },
    'tour.aiInsights.message': {
        en: 'Our AI analyzes weather, terrain, and reports to predict flood risk in your area.',
        hi: 'हमारा AI मौसम, भूभाग और रिपोर्ट का विश्लेषण करके आपके क्षेत्र में बाढ़ जोखिम की भविष्यवाणी करता है।',
        id: 'AI kami menganalisis cuaca, medan, dan laporan untuk memprediksi risiko banjir di area Anda.',
    },
    'tour.emergencyContacts.title': {
        en: 'Emergency contacts',
        hi: 'आपातकालीन संपर्क',
        id: 'Kontak darurat',
    },
    'tour.emergencyContacts.message': {
        en: 'Quick dial for emergency services in your city. Always accessible from the home screen.',
        hi: 'आपके शहर की आपातकालीन सेवाओं के लिए त्वरित डायल। होम स्क्रीन से हमेशा उपलब्ध।',
        id: 'Panggilan cepat untuk layanan darurat di kota Anda. Selalu dapat diakses dari layar utama.',
    },
    'tour.map.title': {
        en: 'Interactive flood map',
        hi: 'इंटरैक्टिव बाढ़ मानचित्र',
        id: 'Peta banjir interaktif',
    },
    'tour.map.message': {
        en: 'Your main map with flood hotspots, water levels, and safe routes. Let me show you the key features.',
        hi: 'बाढ़ हॉटस्पॉट, जल स्तर और सुरक्षित मार्गों वाला आपका मुख्य मानचित्र।',
        id: 'Peta utama Anda dengan titik rawan banjir, ketinggian air, dan rute aman.',
    },
    'tour.mapLayers.title': {
        en: 'Map layers',
        hi: 'मानचित्र की परतें',
        id: 'Lapisan peta',
    },
    'tour.mapLayers.message': {
        en: 'Toggle different layers — hotspots, flood zones, metro stations, and satellite imagery.',
        hi: 'विभिन्न परतें टॉगल करें — हॉटस्पॉट, बाढ़ क्षेत्र, मेट्रो स्टेशन और उपग्रह छवियाँ।',
        id: 'Aktifkan lapisan berbeda — titik rawan, zona banjir, stasiun metro, dan citra satelit.',
    },
    'tour.routing.title': {
        en: 'Safe routing',
        hi: 'सुरक्षित मार्ग',
        id: 'Rute aman',
    },
    'tour.routing.message': {
        en: 'Plan routes that avoid flooded areas. Enter your destination to see the safest path.',
        hi: 'बाढ़ वाले क्षेत्रों से बचने वाले मार्ग बनाएं। सबसे सुरक्षित रास्ता देखने के लिए गंतव्य दर्ज करें।',
        id: 'Rencanakan rute yang menghindari area banjir. Masukkan tujuan untuk melihat jalur teraman.',
    },
    'tour.report.title': {
        en: 'Report flooding',
        hi: 'बाढ़ की रिपोर्ट करें',
        id: 'Laporkan banjir',
    },
    'tour.report.message': {
        en: 'See flooding? Report it here with a photo to help your community. You\'ll earn points too!',
        hi: 'बाढ़ दिख रही है? यहाँ फोटो के साथ रिपोर्ट करें और अपने समुदाय की मदद करें। आपको अंक भी मिलेंगे!',
        id: 'Melihat banjir? Laporkan di sini dengan foto untuk membantu komunitas Anda. Anda juga akan mendapat poin!',
    },
    'tour.alerts.title': {
        en: 'Unified alerts',
        hi: 'एकीकृत अलर्ट',
        id: 'Peringatan terpadu',
    },
    'tour.alerts.message': {
        en: 'All flood alerts in one place — weather warnings, community reports, government advisories, and Google FloodHub.',
        hi: 'सभी बाढ़ अलर्ट एक जगह — मौसम चेतावनी, सामुदायिक रिपोर्ट, सरकारी सलाह और Google FloodHub।',
        id: 'Semua peringatan banjir di satu tempat — peringatan cuaca, laporan komunitas, imbauan pemerintah, dan Google FloodHub.',
    },
    'tour.profile.title': {
        en: 'Your profile',
        hi: 'आपकी प्रोफ़ाइल',
        id: 'Profil Anda',
    },
    'tour.profile.message': {
        en: 'View your badges, reputation, and settings. You can replay this tour anytime from here!',
        hi: 'अपने बैज, प्रतिष्ठा और सेटिंग्स देखें। आप यहाँ से कभी भी यह दौरा दोबारा चला सकते हैं!',
        id: 'Lihat lencana, reputasi, dan pengaturan Anda. Anda bisa memutar ulang tur ini kapan saja dari sini!',
    },

    // ── UI controls ────────────────────────────────────────────
    'bot.skip': {
        en: 'Skip guide',
        hi: 'गाइड छोड़ें',
        id: 'Lewati panduan',
    },
    'bot.next': {
        en: 'Next',
        hi: 'अगला',
        id: 'Berikutnya',
    },
    'bot.back': {
        en: 'Back',
        hi: 'पिछला',
        id: 'Kembali',
    },
    'bot.done': {
        en: 'Done!',
        hi: 'हो गया!',
        id: 'Selesai!',
    },
    'bot.tapForTip': {
        en: 'Tap for tip',
        hi: 'टिप के लिए टैप करें',
        id: 'Ketuk untuk tip',
    },
    'bot.startTour': {
        en: 'Tour the app',
        hi: 'ऐप का दौरा करें',
        id: 'Tur aplikasi',
    },
    'bot.skipTour': {
        en: 'Maybe later',
        hi: 'बाद में',
        id: 'Nanti saja',
    },
    'bot.tourAgain': {
        en: 'Tour the App Again',
        hi: 'ऐप का दौरा दोबारा करें',
        id: 'Tur Aplikasi Lagi',
    },
    'bot.stepOf': {
        en: 'of',
        hi: 'का',
        id: 'dari',
    },
};

/**
 * Get a translated string by key and language.
 * Falls back to English if the key/language combination is missing.
 */
export function t(language: OnboardingBotLanguage, key: string): string {
    const entry = translations[key];
    if (!entry) return key;
    return entry[language] || entry.en || key;
}

/**
 * Map city to default bot language.
 * Users can override this on the welcome step.
 */
export function cityToLanguage(city: string | null): OnboardingBotLanguage {
    switch (city) {
        case 'delhi':
        case 'bangalore':
            return 'hi';
        case 'yogyakarta':
            return 'id';
        default:
            return 'en';
    }
}

/**
 * Map bot language to BCP-47 voice synthesis language tag.
 */
export function languageToVoiceCode(lang: OnboardingBotLanguage): string {
    switch (lang) {
        case 'hi': return 'hi-IN';
        case 'id': return 'id-ID';
        default: return 'en-US';
    }
}
