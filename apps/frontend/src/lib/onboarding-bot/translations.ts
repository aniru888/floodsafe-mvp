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

    // ── LoginScreen ──────────────────────────────────────────────
    'login.brand.tagline': {
        en: 'Community flood monitoring',
        hi: 'सामुदायिक बाढ़ निगरानी',
        id: 'Pemantauan banjir komunitas',
    },
    'login.brand.cities': {
        en: 'Delhi \u00B7 Bangalore \u00B7 Yogyakarta \u00B7 Singapore \u00B7 Indore',
        hi: 'दिल्ली \u00B7 बेंगलुरु \u00B7 योग्यकर्ता \u00B7 सिंगापुर \u00B7 इंदौर',
        id: 'Delhi \u00B7 Bangalore \u00B7 Yogyakarta \u00B7 Singapura \u00B7 Indore',
    },
    'login.heading.create': {
        en: 'Create your account',
        hi: 'अपना खाता बनाएं',
        id: 'Buat akun Anda',
    },
    'login.heading.signin': {
        en: 'Welcome back',
        hi: 'वापसी पर स्वागत है',
        id: 'Selamat datang kembali',
    },
    'login.subheading.create': {
        en: 'Join the flood monitoring community',
        hi: 'बाढ़ निगरानी समुदाय से जुड़ें',
        id: 'Bergabung dengan komunitas pemantauan banjir',
    },
    'login.subheading.signin': {
        en: 'Sign in to access alerts, routes & reports',
        hi: 'अलर्ट, मार्ग और रिपोर्ट तक पहुंचने के लिए साइन इन करें',
        id: 'Masuk untuk mengakses peringatan, rute & laporan',
    },
    'login.label.email': {
        en: 'Email',
        hi: 'ईमेल',
        id: 'Email',
    },
    'login.label.password': {
        en: 'Password',
        hi: 'पासवर्ड',
        id: 'Kata sandi',
    },
    'login.placeholder.email': {
        en: 'you@example.com',
        hi: 'you@example.com',
        id: 'anda@contoh.com',
    },
    'login.placeholder.password.create': {
        en: 'Min 8 characters',
        hi: 'न्यूनतम 8 अक्षर',
        id: 'Minimal 8 karakter',
    },
    'login.placeholder.password.signin': {
        en: 'Your password',
        hi: 'आपका पासवर्ड',
        id: 'Kata sandi Anda',
    },
    'login.button.create': {
        en: 'Create Account',
        hi: 'खाता बनाएं',
        id: 'Buat Akun',
    },
    'login.button.signin': {
        en: 'Sign In',
        hi: 'साइन इन करें',
        id: 'Masuk',
    },
    'login.button.creating': {
        en: 'Creating...',
        hi: 'बना रहे हैं...',
        id: 'Membuat...',
    },
    'login.button.signingIn': {
        en: 'Signing in...',
        hi: 'साइन इन हो रहा है...',
        id: 'Masuk...',
    },
    'login.divider.or': {
        en: 'or',
        hi: 'या',
        id: 'atau',
    },
    'login.toggle.toSignin': {
        en: 'Already have an account?',
        hi: 'पहले से खाता है?',
        id: 'Sudah punya akun?',
    },
    'login.toggle.toSignup': {
        en: "Don't have an account?",
        hi: 'खाता नहीं है?',
        id: 'Belum punya akun?',
    },
    'login.toggle.signin': {
        en: 'Sign in',
        hi: 'साइन इन',
        id: 'Masuk',
    },
    'login.toggle.signup': {
        en: 'Sign up',
        hi: 'साइन अप',
        id: 'Daftar',
    },
    'login.toggle.toPhone': {
        en: 'Use phone number',
        hi: 'फ़ोन नंबर का उपयोग करें',
        id: 'Gunakan nomor telepon',
    },
    'login.phone.heading': {
        en: 'Phone sign in',
        hi: 'फ़ोन से साइन इन',
        id: 'Masuk dengan telepon',
    },
    'login.phone.subheading': {
        en: "We'll send you a verification code",
        hi: 'हम आपको एक सत्यापन कोड भेजेंगे',
        id: 'Kami akan mengirimkan kode verifikasi',
    },
    'login.phone.placeholder': {
        en: 'Phone number',
        hi: 'फ़ोन नंबर',
        id: 'Nomor telepon',
    },
    'login.phone.sendCode': {
        en: 'Send code',
        hi: 'कोड भेजें',
        id: 'Kirim kode',
    },
    'login.phone.changeNumber': {
        en: 'Change number',
        hi: 'नंबर बदलें',
        id: 'Ganti nomor',
    },
    'login.phone.codeSent': {
        en: 'Code sent to',
        hi: 'कोड भेजा गया',
        id: 'Kode dikirim ke',
    },
    'login.phone.resend': {
        en: 'Resend code',
        hi: 'कोड दोबारा भेजें',
        id: 'Kirim ulang kode',
    },
    'login.phone.verify': {
        en: 'Verify',
        hi: 'सत्यापित करें',
        id: 'Verifikasi',
    },
    'login.phone.backToEmail': {
        en: 'Back to email sign in',
        hi: 'ईमेल साइन इन पर वापस जाएं',
        id: 'Kembali ke masuk email',
    },
    'login.terms': {
        en: 'By continuing, you agree to our Terms & Privacy Policy',
        hi: 'जारी रखकर, आप हमारी शर्तों और गोपनीयता नीति से सहमत हैं',
        id: 'Dengan melanjutkan, Anda menyetujui Syarat & Kebijakan Privasi kami',
    },
    'login.error.email': {
        en: 'Please enter a valid email address',
        hi: 'कृपया एक मान्य ईमेल पता दर्ज करें',
        id: 'Silakan masukkan alamat email yang valid',
    },
    'login.error.password': {
        en: 'Password must be at least 8 characters',
        hi: 'पासवर्ड कम से कम 8 अक्षर का होना चाहिए',
        id: 'Kata sandi harus minimal 8 karakter',
    },

    // ── OnboardingScreen ─────────────────────────────────────────
    'onboarding.header.welcome': {
        en: 'Welcome to FloodSafe',
        hi: 'FloodSafe में आपका स्वागत है',
        id: 'Selamat datang di FloodSafe',
    },
    'onboarding.header.subtitle': {
        en: "Let's set up your account",
        hi: 'आइए आपका खाता सेट करें',
        id: 'Mari siapkan akun Anda',
    },
    'onboarding.language.title': {
        en: 'Choose your preferred language',
        hi: 'अपनी पसंदीदा भाषा चुनें',
        id: 'Pilih bahasa pilihan Anda',
    },
    'onboarding.language.continue': {
        en: 'Continue',
        hi: 'जारी रखें',
        id: 'Lanjutkan',
    },
    'onboarding.steps.city': {
        en: 'Select City',
        hi: 'शहर चुनें',
        id: 'Pilih Kota',
    },
    'onboarding.steps.profile': {
        en: 'Your Profile',
        hi: 'आपकी प्रोफ़ाइल',
        id: 'Profil Anda',
    },
    'onboarding.steps.watchAreas': {
        en: 'Watch Areas',
        hi: 'निगरानी क्षेत्र',
        id: 'Area Pantau',
    },
    'onboarding.steps.routes': {
        en: 'Daily Routes',
        hi: 'दैनिक मार्ग',
        id: 'Rute Harian',
    },
    'onboarding.steps.complete': {
        en: 'Complete',
        hi: 'पूर्ण',
        id: 'Selesai',
    },
    'onboarding.progress': {
        en: 'Step {n} of 5: {title}',
        hi: 'चरण {n} / 5: {title}',
        id: 'Langkah {n} dari 5: {title}',
    },
    'onboarding.city.heading': {
        en: 'Select Your City',
        hi: 'अपना शहर चुनें',
        id: 'Pilih Kota Anda',
    },
    'onboarding.city.subheading': {
        en: 'Choose the city where you want to receive flood alerts',
        hi: 'वह शहर चुनें जहां आप बाढ़ अलर्ट प्राप्त करना चाहते हैं',
        id: 'Pilih kota tempat Anda ingin menerima peringatan banjir',
    },
    'onboarding.city.region.delhi': {
        en: 'National Capital Territory, India',
        hi: 'राष्ट्रीय राजधानी क्षेत्र, भारत',
        id: 'Wilayah Ibu Kota Nasional, India',
    },
    'onboarding.city.region.bangalore': {
        en: 'Karnataka, India',
        hi: 'कर्नाटक, भारत',
        id: 'Karnataka, India',
    },
    'onboarding.city.region.yogyakarta': {
        en: 'Special Region of Yogyakarta, Indonesia',
        hi: 'योग्यकर्ता विशेष क्षेत्र, इंडोनेशिया',
        id: 'Daerah Istimewa Yogyakarta, Indonesia',
    },
    'onboarding.city.region.singapore': {
        en: 'Republic of Singapore',
        hi: 'सिंगापुर गणराज्य',
        id: 'Republik Singapura',
    },
    'onboarding.city.region.indore': {
        en: 'Madhya Pradesh, India',
        hi: 'मध्य प्रदेश, भारत',
        id: 'Madhya Pradesh, India',
    },
    'onboarding.profile.heading': {
        en: 'Your Profile',
        hi: 'आपकी प्रोफ़ाइल',
        id: 'Profil Anda',
    },
    'onboarding.profile.subheading': {
        en: 'Set up your profile information',
        hi: 'अपनी प्रोफ़ाइल जानकारी सेट करें',
        id: 'Atur informasi profil Anda',
    },
    'onboarding.profile.username': {
        en: 'Username *',
        hi: 'उपयोगकर्ता नाम *',
        id: 'Nama pengguna *',
    },
    'onboarding.profile.usernamePlaceholder': {
        en: 'Enter your username',
        hi: 'अपना उपयोगकर्ता नाम दर्ज करें',
        id: 'Masukkan nama pengguna Anda',
    },
    'onboarding.profile.phone': {
        en: 'Phone Number (optional)',
        hi: 'फ़ोन नंबर (वैकल्पिक)',
        id: 'Nomor Telepon (opsional)',
    },
    'onboarding.profile.phoneHelper': {
        en: 'Used for SMS alerts (optional)',
        hi: 'SMS अलर्ट के लिए उपयोग (वैकल्पिक)',
        id: 'Digunakan untuk peringatan SMS (opsional)',
    },
    'onboarding.watchAreas.heading': {
        en: 'Watch Areas',
        hi: 'निगरानी क्षेत्र',
        id: 'Area Pantau',
    },
    'onboarding.watchAreas.subheading': {
        en: 'Add locations you want to monitor for flood alerts (at least 1 required)',
        hi: 'बाढ़ अलर्ट के लिए निगरानी हेतु स्थान जोड़ें (कम से कम 1 आवश्यक)',
        id: 'Tambahkan lokasi yang ingin Anda pantau untuk peringatan banjir (minimal 1 diperlukan)',
    },
    'onboarding.watchAreas.areaName': {
        en: 'Area name (e.g., Home, Office)',
        hi: 'क्षेत्र का नाम (जैसे, घर, कार्यालय)',
        id: 'Nama area (mis., Rumah, Kantor)',
    },
    'onboarding.watchAreas.search': {
        en: 'Search for a location...',
        hi: 'स्थान खोजें...',
        id: 'Cari lokasi...',
    },
    'onboarding.watchAreas.useLocation': {
        en: 'Use My Current Location',
        hi: 'मेरा वर्तमान स्थान उपयोग करें',
        id: 'Gunakan Lokasi Saya Saat Ini',
    },
    'onboarding.watchAreas.gettingLocation': {
        en: 'Getting location...',
        hi: 'स्थान प्राप्त हो रहा है...',
        id: 'Mendapatkan lokasi...',
    },
    'onboarding.watchAreas.existing': {
        en: 'Previously added:',
        hi: 'पहले से जोड़ा गया:',
        id: 'Sebelumnya ditambahkan:',
    },
    'onboarding.watchAreas.pending': {
        en: 'To be added:',
        hi: 'जोड़ा जाएगा:',
        id: 'Akan ditambahkan:',
    },
    'onboarding.watchAreas.none': {
        en: 'No watch areas added yet',
        hi: 'अभी तक कोई निगरानी क्षेत्र नहीं जोड़ा गया',
        id: 'Belum ada area pantau yang ditambahkan',
    },
    'onboarding.routes.heading': {
        en: 'Daily Routes',
        hi: 'दैनिक मार्ग',
        id: 'Rute Harian',
    },
    'onboarding.routes.subheading': {
        en: 'Add your regular commute routes to get flood alerts along your path (optional)',
        hi: 'अपने नियमित आवागमन मार्ग जोड़ें ताकि आपके रास्ते में बाढ़ अलर्ट मिलें (वैकल्पिक)',
        id: 'Tambahkan rute perjalanan reguler Anda untuk mendapatkan peringatan banjir di sepanjang jalur Anda (opsional)',
    },
    'onboarding.routes.tip': {
        en: 'Tip: Add routes like "Home to Office" to receive alerts about flooding along your daily commute.',
        hi: 'सुझाव: "घर से कार्यालय" जैसे मार्ग जोड़ें ताकि आपके दैनिक आवागमन में बाढ़ अलर्ट मिलें।',
        id: 'Tips: Tambahkan rute seperti "Rumah ke Kantor" untuk menerima peringatan banjir di perjalanan harian Anda.',
    },
    'onboarding.routes.none': {
        en: 'No daily routes added',
        hi: 'कोई दैनिक मार्ग नहीं जोड़ा गया',
        id: 'Belum ada rute harian yang ditambahkan',
    },
    'onboarding.routes.addLater': {
        en: 'You can add routes later from your profile',
        hi: 'आप बाद में अपनी प्रोफ़ाइल से मार्ग जोड़ सकते हैं',
        id: 'Anda dapat menambahkan rute nanti dari profil Anda',
    },
    'onboarding.complete.heading': {
        en: "You're All Set!",
        hi: 'आप पूरी तरह तैयार हैं!',
        id: 'Anda Siap!',
    },
    'onboarding.complete.subheading': {
        en: "Here's a summary of your setup:",
        hi: 'यहां आपके सेटअप का सारांश है:',
        id: 'Berikut ringkasan pengaturan Anda:',
    },
    'onboarding.complete.instruction': {
        en: 'Click "Get Started" to begin using FloodSafe',
        hi: 'FloodSafe का उपयोग शुरू करने के लिए "शुरू करें" पर क्लिक करें',
        id: 'Klik "Mulai" untuk mulai menggunakan FloodSafe',
    },
    'onboarding.complete.summary.city': {
        en: 'City:',
        hi: 'शहर:',
        id: 'Kota:',
    },
    'onboarding.complete.summary.username': {
        en: 'Username:',
        hi: 'उपयोगकर्ता नाम:',
        id: 'Nama pengguna:',
    },
    'onboarding.complete.summary.watchAreas': {
        en: 'Watch Areas:',
        hi: 'निगरानी क्षेत्र:',
        id: 'Area Pantau:',
    },
    'onboarding.complete.summary.routes': {
        en: 'Daily Routes:',
        hi: 'दैनिक मार्ग:',
        id: 'Rute Harian:',
    },
    'onboarding.nav.back': {
        en: 'Back',
        hi: 'पीछे',
        id: 'Kembali',
    },
    'onboarding.nav.skip': {
        en: 'Skip',
        hi: 'छोड़ें',
        id: 'Lewati',
    },
    'onboarding.nav.next': {
        en: 'Next',
        hi: 'आगे',
        id: 'Selanjutnya',
    },
    'onboarding.nav.getStarted': {
        en: 'Get Started',
        hi: 'शुरू करें',
        id: 'Mulai',
    },
    'onboarding.toast.welcome': {
        en: 'Welcome to FloodSafe!',
        hi: 'FloodSafe में आपका स्वागत है!',
        id: 'Selamat datang di FloodSafe!',
    },
    'onboarding.toast.error': {
        en: 'Something went wrong. Please try again.',
        hi: 'कुछ गलत हो गया। कृपया दोबारा प्रयास करें।',
        id: 'Terjadi kesalahan. Silakan coba lagi.',
    },
    'onboarding.error.city': {
        en: 'Please select a city',
        hi: 'कृपया एक शहर चुनें',
        id: 'Silakan pilih kota',
    },
    'onboarding.error.username': {
        en: 'Username must be at least 3 characters',
        hi: 'उपयोगकर्ता नाम कम से कम 3 अक्षर का होना चाहिए',
        id: 'Nama pengguna harus minimal 3 karakter',
    },
    'onboarding.error.watchAreas': {
        en: 'Add at least one watch area',
        hi: 'कम से कम एक निगरानी क्षेत्र जोड़ें',
        id: 'Tambahkan minimal satu area pantau',
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
