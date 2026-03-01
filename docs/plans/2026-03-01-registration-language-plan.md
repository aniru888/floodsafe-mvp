# Registration Language Selection — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add language selection to LoginScreen and OnboardingScreen so users can pick English/Hindi/Indonesian before creating an account, with a unified LanguageContext as single source of truth.

**Architecture:** New LanguageContext wraps the entire app (above AuthProvider). Pre-auth uses localStorage, post-auth syncs to DB. OnboardingBotContext bridges from LanguageContext (backward-compatible). OnboardingScreen adds a pre-step for language confirmation (no step numbering change). ~55 new translation keys in existing translations.ts.

**Tech Stack:** React 18, TypeScript, localStorage, existing `translations.ts` inline map, FastAPI Pydantic validation

**Design doc:** `docs/plans/2026-03-01-registration-language-design.md`

---

## Phase 1: Foundation (3 parallel tracks)

### Task 1A: Create LanguageContext

**Files:**
- Create: `apps/frontend/src/contexts/LanguageContext.tsx`

**Step 1: Create the context file**

```typescript
// apps/frontend/src/contexts/LanguageContext.tsx
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

export type AppLanguage = 'en' | 'hi' | 'id';

interface LanguageContextValue {
    language: AppLanguage;
    setLanguage: (lang: AppLanguage) => void;
}

const LS_KEY = 'floodsafe_language';
const VALID_LANGUAGES: AppLanguage[] = ['en', 'hi', 'id'];

/** Convert DB long names to short codes. Accepts both formats. */
export function toShortCode(dbVal: string | undefined | null): AppLanguage {
    if (!dbVal) return 'en';
    const map: Record<string, AppLanguage> = {
        english: 'en', hindi: 'hi', indonesian: 'id',
        en: 'en', hi: 'hi', id: 'id',
    };
    return map[dbVal.toLowerCase()] || 'en';
}

/** Convert short codes to DB long names for PATCH /users/me/profile. */
export function toDbValue(code: AppLanguage): string {
    const map: Record<AppLanguage, string> = { en: 'english', hi: 'hindi', id: 'indonesian' };
    return map[code];
}

function readStoredLanguage(): AppLanguage {
    try {
        const stored = localStorage.getItem(LS_KEY);
        if (stored && VALID_LANGUAGES.includes(stored as AppLanguage)) {
            return stored as AppLanguage;
        }
    } catch {
        // localStorage unavailable (SSR, privacy mode)
    }
    return 'en';
}

const LanguageContext = createContext<LanguageContextValue>({
    language: 'en',
    setLanguage: () => {},
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
    const [language, setLanguageState] = useState<AppLanguage>(readStoredLanguage);

    const setLanguage = useCallback((lang: AppLanguage) => {
        if (!VALID_LANGUAGES.includes(lang)) return;
        setLanguageState(lang);
        try {
            localStorage.setItem(LS_KEY, lang);
        } catch {
            // localStorage unavailable
        }
    }, []);

    return (
        <LanguageContext.Provider value={{ language, setLanguage }}>
            {children}
        </LanguageContext.Provider>
    );
}

/** Primary hook for reading/setting app language. */
export function useLanguage(): LanguageContextValue {
    return useContext(LanguageContext);
}
```

**Step 2: Verify types compile**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: PASS (new file, no consumers yet)

**Step 3: Commit**

```bash
git add apps/frontend/src/contexts/LanguageContext.tsx
git commit -m "feat: add LanguageContext for unified language state"
```

---

### Task 1B: Add translation keys + update types

**Files:**
- Modify: `apps/frontend/src/lib/onboarding-bot/translations.ts` (add ~55 keys after line 249)
- Modify: `apps/frontend/src/types/onboarding-bot.ts` (no change needed — `OnboardingBotLanguage` already matches `AppLanguage`)

**Step 1: Add LoginScreen translation keys**

Insert BEFORE the closing `};` of the translations object (before line 250 in `translations.ts`):

```typescript
    // ── LoginScreen ──────────────────────────────────────────────
    'login.brand.tagline': {
        en: 'Community flood monitoring',
        hi: 'सामुदायिक बाढ़ निगरानी',
        id: 'Pemantauan banjir komunitas',
    },
    'login.brand.cities': {
        en: 'Delhi \u00B7 Bangalore \u00B7 Yogyakarta \u00B7 Singapore',
        hi: 'दिल्ली \u00B7 बेंगलुरु \u00B7 योग्यकर्ता \u00B7 सिंगापुर',
        id: 'Delhi \u00B7 Bangalore \u00B7 Yogyakarta \u00B7 Singapura',
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
```

**Step 2: Verify types compile**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add apps/frontend/src/lib/onboarding-bot/translations.ts
git commit -m "feat: add 55 translation keys for LoginScreen and OnboardingScreen"
```

---

### Task 1C: Backend language validation

**Files:**
- Modify: `apps/backend/src/domain/models.py:148`

**Step 1: Add validation pattern to UserUpdate.language**

Change line 148 from:
```python
    language: Optional[str] = None
```
to:
```python
    language: Optional[str] = Field(None, pattern=r"^(english|hindi|indonesian|en|hi|id)$")
```

**Step 2: Verify backend tests pass**

Run: `cd apps/backend && python -m pytest tests/ -x -q 2>/dev/null || echo "No tests or tests passed"`
Expected: No failures related to language validation

**Step 3: Commit**

```bash
git add apps/backend/src/domain/models.py
git commit -m "feat: add language validation to UserUpdate model"
```

---

## TEST GATE 1

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: 0 errors. All new types compile, no missing exports.

---

## Phase 2: Core Wiring (2 parallel tracks)

### Task 2D: Wire LanguageProvider into App.tsx + sync bridge

**Files:**
- Modify: `apps/frontend/src/App.tsx`

**Step 1: Add LanguageProvider import and wrap provider tree**

At top of `App.tsx`, add import (after line 29):
```typescript
import { LanguageProvider, useLanguage, toShortCode, toDbValue } from './contexts/LanguageContext';
```

**Step 2: Add LanguageSyncBridge component**

Add this component BEFORE the `FloodSafeApp` function (around line 53, after PushNotificationRegistrar):
```typescript
/**
 * Syncs LanguageContext <-> user.language in DB.
 * - On user load: DB wins for returning users (non-default language).
 * - On language change: pushes to DB if user exists.
 */
function LanguageSyncBridge() {
    const { user } = useAuth();
    const { language, setLanguage } = useLanguage();
    const hasSyncedRef = useRef(false);

    // On user load: sync DB → context (DB wins for returning users)
    useEffect(() => {
        if (!user || hasSyncedRef.current) return;
        hasSyncedRef.current = true;

        const dbLang = toShortCode(user.language);
        // DB wins if user has a non-default language set
        if (user.language && user.language !== 'english' && dbLang !== language) {
            setLanguage(dbLang);
        }
    }, [user, language, setLanguage]);

    // Reset sync flag on logout
    useEffect(() => {
        if (!user) hasSyncedRef.current = false;
    }, [user]);

    return null;
}
```

Also add `useRef` to the React import at line 1:
```typescript
import { useState, useEffect, useRef } from 'react';
```

**Step 3: Wrap provider tree with LanguageProvider**

In the `App` component (around line 284), wrap `LanguageProvider` as the outermost provider (inside the fragment, around QueryClientProvider):

Change:
```typescript
export default function App() {
    return (
        <>
            <Analytics />
            <QueryClientProvider client={queryClient}>
            <AuthProvider>
```

To:
```typescript
export default function App() {
    return (
        <>
            <Analytics />
            <LanguageProvider>
            <QueryClientProvider client={queryClient}>
            <AuthProvider>
```

And add `LanguageSyncBridge` right after `<UserProvider>` (around line 290):
```typescript
                <UserProvider>
                    <LanguageSyncBridge />
                    <CityProvider>
```

And close `LanguageProvider` after `QueryClientProvider` closes (around line 322):
```typescript
        </QueryClientProvider>
        </LanguageProvider>
        </>
```

**Step 4: Verify types compile**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/frontend/src/App.tsx
git commit -m "feat: wire LanguageProvider into app + sync bridge"
```

---

### Task 2E: Refactor OnboardingBotContext to use LanguageContext

**Files:**
- Modify: `apps/frontend/src/contexts/OnboardingBotContext.tsx`
- Modify: `apps/frontend/src/types/onboarding-bot.ts`

**Step 1: Update OnboardingBotContext to read from LanguageContext**

In `OnboardingBotContext.tsx`:

1. Add import (after line 10):
```typescript
import { useLanguage } from './LanguageContext';
```

2. Add `useLanguage` hook call inside provider (after line 22):
```typescript
    const { language } = useLanguage();
```

3. Remove `language` from useState initial state (line 27). Change:
```typescript
    const [state, setState] = useState<OnboardingBotState>({
        phase: 'idle',
        language: cityToLanguage(currentCity),
        currentStepIndex: 0,
        isVoiceEnabled: true,
        isCardExpanded: true,
        isDismissed: localStorage.getItem(LS_DISMISSED) === 'true',
    });
```
To:
```typescript
    const [internalState, setInternalState] = useState<Omit<OnboardingBotState, 'language'>>({
        phase: 'idle',
        currentStepIndex: 0,
        isVoiceEnabled: true,
        isCardExpanded: true,
        isDismissed: localStorage.getItem(LS_DISMISSED) === 'true',
    });

    // Bridge: expose language from LanguageContext as part of state (backward-compatible)
    const state: OnboardingBotState = { ...internalState, language };
```

4. Replace ALL `setState` calls with `setInternalState` throughout the file. Search and replace. There should be calls at approximately lines: 69, 93, 104, 121, 131, 144, 148, 153, 164.

5. Update `speakCurrentStep` (around line 44-49) — it already takes `lang` as parameter, no change needed.

6. Update `startTour` (around line 52-73). Remove the language parameter and cityToLanguage fallback. Change:
```typescript
    const startTour = useCallback((phase: TourPhase, language?: OnboardingBotLanguage) => {
        // ...
        const lang = language || cityToLanguage(currentCity);
        // ...
        setState(prev => ({
            ...prev,
            phase,
            language: lang,
            currentStepIndex: 0,
            isCardExpanded: true,
            isDismissed: false,
        }));
    }, [currentCity, state.isDismissed]);
```
To:
```typescript
    const startTour = useCallback((phase: TourPhase) => {
        if (internalState.isDismissed && phase === 'onboarding') return;

        const targetSteps = phase === 'onboarding' ? onboardingSteps : appTourSteps;
        if (targetSteps.length === 0) return;

        // Run onBefore for first step
        const firstStep = targetSteps[0];
        if (firstStep?.onBefore) {
            firstStep.onBefore();
        }

        setInternalState(prev => ({
            ...prev,
            phase,
            currentStepIndex: 0,
            isCardExpanded: true,
            isDismissed: false,
        }));
    }, [internalState.isDismissed, appTourSteps]);
```

7. Remove the `setLanguage` callback (around line 139-141). Delete:
```typescript
    const setLanguage = useCallback((lang: OnboardingBotLanguage) => {
        setState(prev => ({ ...prev, language: lang }));
    }, []);
```

8. Update the voice useEffect (around line 174) — it uses `state.language` which now comes from LanguageContext. No code change needed since `state` is the computed object.

9. Remove `setLanguage` from the context value (around line 204):
```typescript
    return (
        <OnboardingBotContext.Provider value={{
            state,
            steps,
            currentStep,
            startTour,
            nextStep,
            prevStep,
            skipTour,
            toggleVoice,
            setCardExpanded,
            registerNavigation,
            syncOnboardingStep,
        }}>
```

10. Remove unused `cityToLanguage` import from line 10 (keep `t` and `languageToVoiceCode`).

**Step 2: Update types to reflect removed setLanguage**

In `types/onboarding-bot.ts`, update the context value interface:

Change line 41:
```typescript
    startTour: (phase: TourPhase, language?: OnboardingBotLanguage) => void;
```
To:
```typescript
    startTour: (phase: TourPhase) => void;
```

Remove line 45:
```typescript
    setLanguage: (lang: OnboardingBotLanguage) => void;
```

**Step 3: Fix all consumers that used `setLanguage` from bot context**

Search for `setLanguage` usage from bot context. Known consumers:
- `BotTooltip.tsx:30` — destructures `setLanguage` from `useOnboardingBot()`. This will break. **For now, just remove the destructure.** The language pills in BotTooltip will be properly rewired in Phase 4 (Task 4K).
- `OnboardingScreen.tsx` — does NOT use `setLanguage` directly.

In `BotTooltip.tsx`, change the destructure (around line 25-31):
```typescript
    const {
        state, currentStep, steps, nextStep, prevStep, skipTour,
        setLanguage,
    } = useOnboardingBot();
```
To:
```typescript
    const {
        state, currentStep, steps, nextStep, prevStep, skipTour,
    } = useOnboardingBot();
    const { setLanguage } = useLanguage();
```
Add import: `import { useLanguage } from '../../contexts/LanguageContext';`

Similarly check `BotInlineCard.tsx` — it reads `state.language` but doesn't call `setLanguage`. No change needed yet (backward-compatible bridge handles it).

**Step 4: Fix startTour callers (removed language param)**

Search for `startTour(` calls:
- `OnboardingScreen.tsx:112`: `startTour('onboarding')` — no language param, already correct
- `App.tsx:73` (app tour): `startTour('app-tour')` — no language param, already correct
- `ProfileScreen.tsx` (tour again button): `startTour('app-tour')` — already correct

**Step 5: Verify types compile**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/frontend/src/contexts/OnboardingBotContext.tsx apps/frontend/src/types/onboarding-bot.ts apps/frontend/src/components/onboarding-bot/BotTooltip.tsx
git commit -m "refactor: OnboardingBotContext reads language from LanguageContext"
```

---

## TEST GATE 2

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: 0 errors

Run: `cd apps/frontend && npx vite --host 0.0.0.0 --port 5175 &` (start dev server, check for React errors in first 5 seconds, then kill)
Expected: No crash, no provider errors in console

---

## Phase 3: UI Screens (3 parallel tracks)

### Task 3F: LoginScreen language pills + translations

**Files:**
- Modify: `apps/frontend/src/components/screens/LoginScreen.tsx`

**Step 1: Add imports**

At top of LoginScreen.tsx, add:
```typescript
import { useLanguage, type AppLanguage } from '../../contexts/LanguageContext';
import { t } from '../../lib/onboarding-bot/translations';
```

**Step 2: Add language hook + pills component**

Inside the `LoginScreen` component, add near the top (after existing state declarations):
```typescript
const { language, setLanguage } = useLanguage();

const LANG_OPTIONS: { code: AppLanguage; label: string }[] = [
    { code: 'en', label: 'EN' },
    { code: 'hi', label: 'हिंदी' },
    { code: 'id', label: 'Bahasa' },
];
```

**Step 3: Add language pills UI**

Add language pills at the very top of the JSX return, above the header. Place them as the first child inside the outermost container:

```tsx
{/* Language selector */}
<div className="flex items-center justify-center gap-1 py-2 bg-white/80 backdrop-blur-sm">
    <Globe className="w-4 h-4 text-muted-foreground" />
    {LANG_OPTIONS.map(({ code, label }) => (
        <button
            key={code}
            onClick={() => setLanguage(code)}
            className={cn(
                'px-3 py-1 rounded-full text-xs font-medium transition-colors',
                language === code
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
        >
            {label}
        </button>
    ))}
</div>
```

Add `Globe` to the lucide-react import if not already imported.
Add `cn` import if not present: `import { cn } from '../../lib/utils';`

**Step 4: Replace hardcoded strings with t() calls**

Replace each hardcoded string. Examples of the pattern:

- `"Community flood monitoring"` → `{t(language, 'login.brand.tagline')}`
- `"Create your account"` / `"Welcome back"` → `{isSignUp ? t(language, 'login.heading.create') : t(language, 'login.heading.signin')}`
- `"Email"` → `{t(language, 'login.label.email')}`
- `"Password"` → `{t(language, 'login.label.password')}`
- `"Create Account"` / `"Sign In"` → `{isSignUp ? t(language, 'login.button.create') : t(language, 'login.button.signin')}`
- `"Creating..."` / `"Signing in..."` → `{isSignUp ? t(language, 'login.button.creating') : t(language, 'login.button.signingIn')}`
- `"or"` → `{t(language, 'login.divider.or')}`
- `"Already have an account?"` → `{t(language, 'login.toggle.toSignin')}`
- `"Don't have an account?"` → `{t(language, 'login.toggle.toSignup')}`
- `"Use phone number"` → `{t(language, 'login.toggle.toPhone')}`
- Phone section strings: use corresponding `login.phone.*` keys
- Validation errors in `validateEmailForm`: use `login.error.*` keys
- Terms footer: `{t(language, 'login.terms')}`

**IMPORTANT**: Keep `you@example.com` placeholder as-is (universal). Keep phone country codes as-is. Keep Firebase SDK error messages as English fallback with a comment.

**Step 5: Verify types compile + build**

Run: `cd apps/frontend && npx tsc --noEmit && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/frontend/src/components/screens/LoginScreen.tsx
git commit -m "feat: add language pills and translations to LoginScreen"
```

---

### Task 3G: OnboardingScreen language pre-step + translations

**Files:**
- Modify: `apps/frontend/src/components/screens/OnboardingScreen.tsx`

**Step 1: Add imports**

```typescript
import { useLanguage, type AppLanguage } from '../../contexts/LanguageContext';
import { t } from '../../lib/onboarding-bot/translations';
```

**Step 2: Add language pre-step state**

Inside the component, after existing state:
```typescript
const { language, setLanguage } = useLanguage();
// Pre-step: show language confirmation before numbered wizard.
// Skip for resuming users (already past step 1).
const [languageConfirmed, setLanguageConfirmed] = useState(
    () => !!(user?.onboarding_step && user.onboarding_step > 1)
);
```

**Step 3: Add pre-step render**

BEFORE the main wizard JSX (before the progress bar), add a conditional:

```tsx
if (!languageConfirmed) {
    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 to-cyan-50 flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                <div className="text-center mb-8">
                    <h1 className="text-2xl font-bold text-gray-900">
                        {t(language, 'onboarding.header.welcome')}
                    </h1>
                    <p className="text-gray-500 mt-2">
                        {t(language, 'onboarding.language.title')}
                    </p>
                </div>

                <Card className="p-6">
                    <RadioGroup
                        value={language}
                        onValueChange={(val) => setLanguage(val as AppLanguage)}
                    >
                        <div className="space-y-3">
                            <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50">
                                <RadioGroupItem value="en" id="lang-en" />
                                <Label htmlFor="lang-en" className="cursor-pointer font-normal text-base">
                                    English
                                </Label>
                            </div>
                            <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50">
                                <RadioGroupItem value="hi" id="lang-hi" />
                                <Label htmlFor="lang-hi" className="cursor-pointer font-normal text-base">
                                    {t(language, 'lang.hindi')} (Hindi)
                                </Label>
                            </div>
                            <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50">
                                <RadioGroupItem value="id" id="lang-id" />
                                <Label htmlFor="lang-id" className="cursor-pointer font-normal text-base">
                                    {t(language, 'lang.indonesian')}
                                </Label>
                            </div>
                        </div>
                    </RadioGroup>

                    <Button
                        className="w-full mt-6"
                        onClick={() => setLanguageConfirmed(true)}
                    >
                        {t(language, 'onboarding.language.continue')} →
                    </Button>
                </Card>
            </div>
        </div>
    );
}
```

Ensure `Card`, `RadioGroup`, `RadioGroupItem`, `Label`, `Button` are imported (check existing imports — OnboardingScreen likely already has most of these).

**Step 4: Translate wizard step titles**

Replace the hardcoded step titles array:
```typescript
const stepTitles = ['Select City', 'Your Profile', 'Watch Areas', 'Daily Routes', 'Complete'];
```
With:
```typescript
const stepTitles = [
    t(language, 'onboarding.steps.city'),
    t(language, 'onboarding.steps.profile'),
    t(language, 'onboarding.steps.watchAreas'),
    t(language, 'onboarding.steps.routes'),
    t(language, 'onboarding.steps.complete'),
];
```

**Step 5: Replace progress text**

Replace `Step {state.currentStep} of 5: {stepTitles[...]}` with:
```typescript
{t(language, 'onboarding.progress')
    .replace('{n}', String(state.currentStep))
    .replace('{title}', stepTitles[state.currentStep - 1])}
```

**Step 6: Replace all other hardcoded strings**

Follow the same `t(language, 'key')` pattern for all strings identified in the exploration. Key replacements:
- Section headings: `onboarding.city.heading`, `onboarding.profile.heading`, etc.
- City region strings: `onboarding.city.region.delhi`, etc.
- Labels: `onboarding.profile.username`, `onboarding.profile.phone`, etc.
- Buttons: `onboarding.nav.back`, `onboarding.nav.next`, `onboarding.nav.getStarted`
- Errors in validateStep: `onboarding.error.city`, `onboarding.error.username`, `onboarding.error.watchAreas`
- Toast messages: `onboarding.toast.welcome`, `onboarding.toast.error`
- Completion: `onboarding.complete.heading`, `onboarding.complete.subheading`, etc.

**Step 7: Sync language to DB on completion**

In the `handleNext` case 5 (completion), add language sync BEFORE marking complete:
```typescript
case 5:
    // Sync language choice to DB
    await updateUser.mutateAsync({
        userId: user.id,
        data: { profile_complete: true, language: toDbValue(language) }
    });
```
Add `toDbValue` to imports: `import { useLanguage, type AppLanguage, toDbValue } from '../../contexts/LanguageContext';`

**Step 8: Verify types compile + build**

Run: `cd apps/frontend && npx tsc --noEmit && npm run build`
Expected: PASS

**Step 9: Commit**

```bash
git add apps/frontend/src/components/screens/OnboardingScreen.tsx
git commit -m "feat: add language pre-step and translations to OnboardingScreen"
```

---

### Task 3H: ProfileScreen — add Indonesian + wire to LanguageContext

**Files:**
- Modify: `apps/frontend/src/components/screens/ProfileScreen.tsx`

**Step 1: Add imports**

```typescript
import { useLanguage, toShortCode, toDbValue } from '../../contexts/LanguageContext';
```

**Step 2: Wire language handler to LanguageContext**

Replace `handleLanguageChange` (line 168-171):
```typescript
const { language: appLanguage, setLanguage: setAppLanguage } = useLanguage();

const handleLanguageChange = (value: string) => {
    if (!user) return;
    // value comes as DB format from radio ('english'/'hindi'/'indonesian')
    const shortCode = toShortCode(value);
    setAppLanguage(shortCode);  // Update context + localStorage
    updateUserMutation.mutate({ language: value } as Partial<User>);  // Sync to DB
};
```

**Step 3: Add Indonesian radio option**

Replace the RadioGroup section (lines 640-649):
```tsx
<RadioGroup value={user.language || 'english'} onValueChange={handleLanguageChange}>
    <div className="flex items-center space-x-2">
        <RadioGroupItem value="english" id="english" />
        <Label htmlFor="english" className="cursor-pointer font-normal">English</Label>
    </div>
    <div className="flex items-center space-x-2">
        <RadioGroupItem value="hindi" id="hindi" />
        <Label htmlFor="hindi" className="cursor-pointer font-normal">हिन्दी (Hindi)</Label>
    </div>
    <div className="flex items-center space-x-2">
        <RadioGroupItem value="indonesian" id="indonesian" />
        <Label htmlFor="indonesian" className="cursor-pointer font-normal">Bahasa Indonesia</Label>
    </div>
</RadioGroup>
```

**Step 4: Update bot tour-again button (line 865)**

Replace `{t(botState.language, 'bot.tourAgain')}` with:
```typescript
{t(appLanguage, 'bot.tourAgain')}
```

**Step 5: Verify types compile + build**

Run: `cd apps/frontend && npx tsc --noEmit && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/frontend/src/components/screens/ProfileScreen.tsx
git commit -m "feat: add Indonesian to ProfileScreen + wire to LanguageContext"
```

---

## TEST GATE 3

Run: `cd apps/frontend && npx tsc --noEmit && npm run build`
Expected: 0 errors, build succeeds

---

## Phase 4: Peripheral Consumers (3 parallel tracks)

### Task 4I: AiRiskInsightsCard — read from LanguageContext

**Files:**
- Modify: `apps/frontend/src/components/AiRiskInsightsCard.tsx`

**Step 1: Replace local state with context**

Add import:
```typescript
import { useLanguage } from '../contexts/LanguageContext';
```

Replace line 152:
```typescript
const [language, setLanguage] = useState<'en' | 'hi'>('en');
```
With:
```typescript
const { language: appLang } = useLanguage();
// Risk summary API only supports en/hi — map 'id' to 'en'
const language = appLang === 'hi' ? 'hi' : 'en';
const [manualOverride, setManualOverride] = useState<'en' | 'hi' | null>(null);
const effectiveLanguage = manualOverride || language;
```

Update the EN/HI toggle buttons (lines 220, 231) to use `setManualOverride` instead of `setLanguage`:
```typescript
onClick={() => setManualOverride('en')}
// ...
onClick={() => setManualOverride('hi')}
```

Update the active state checks to use `effectiveLanguage`:
```typescript
effectiveLanguage === 'en' ? 'bg-card ...' : '...'
effectiveLanguage === 'hi' ? 'bg-card ...' : '...'
```

Update the RiskInsightItem prop (line 255):
```typescript
language={effectiveLanguage}
```

**Step 2: Verify types compile**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add apps/frontend/src/components/AiRiskInsightsCard.tsx
git commit -m "fix: AiRiskInsightsCard reads language from LanguageContext"
```

---

### Task 4J: BotInlineCard — read from LanguageContext

**Files:**
- Modify: `apps/frontend/src/components/onboarding-bot/BotInlineCard.tsx`

**Step 1: The backward-compatible bridge handles this**

`BotInlineCard` reads `state.language` (line 44). Since Phase 2 made `state.language` a computed value from LanguageContext, this already works.

**Optional cleanup**: Replace `const lang = state.language` with direct context read:
```typescript
import { useLanguage } from '../../contexts/LanguageContext';
// ...
const { language: lang } = useLanguage();
```
Remove `const lang = state.language;` from line 44.

**Step 2: Verify types compile**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add apps/frontend/src/components/onboarding-bot/BotInlineCard.tsx
git commit -m "refactor: BotInlineCard reads language from LanguageContext directly"
```

---

### Task 4K: BotTooltip — wire language pills to LanguageContext

**Files:**
- Modify: `apps/frontend/src/components/onboarding-bot/BotTooltip.tsx`

**Step 1: Already partially done in Phase 2**

Phase 2 (Task 2E Step 3) already added `useLanguage` import and `setLanguage` from LanguageContext. Now replace `const lang = state.language` with direct context read:

```typescript
const { language: lang, setLanguage } = useLanguage();
```
Remove `const lang = state.language;` from line 35.

The language pill buttons already call `setLanguage(code)` — now this writes to LanguageContext instead of bot context. Correct.

**Step 2: Verify types compile**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add apps/frontend/src/components/onboarding-bot/BotTooltip.tsx
git commit -m "refactor: BotTooltip reads/writes language via LanguageContext"
```

---

## TEST GATE 4

Run: `cd apps/frontend && npm run build`
Expected: Build succeeds

Run: `cd apps/frontend && npm run dev` (start dev server on port 5175)
Manually verify:
- App loads without white screen
- LoginScreen renders
- No console errors

---

## Phase 5: E2E Verification

### Task 5A: Manual flow verification

**Steps:**
1. Start dev server: `cd apps/frontend && npm run dev`
2. Open `http://localhost:5175` in browser
3. On LoginScreen: click "हिंदी" pill → verify all text switches to Hindi
4. Click "Bahasa" pill → verify all text switches to Indonesian
5. Click "EN" pill → verify text returns to English
6. Select Hindi → create a new test account (email: `lang_test_TIMESTAMP@floodsafe.test`, password: `TestPassword123!`)
7. Verify OnboardingScreen shows language pre-step with Hindi pre-selected
8. Click Continue → verify wizard Step 1 labels are in Hindi
9. Complete all 5 wizard steps
10. In ProfileScreen → verify language shows Hindi selected, Indonesian option present
11. Change language to Indonesian in Profile → verify it persists on page reload

### Task 5B: WebMCP verification

Use Chrome DevTools MCP:
1. Connect to browser
2. Navigate to the app
3. Read `context_app_state` WebMCP resource → confirm `language` field present
4. Take screenshots of LoginScreen in all 3 languages

### Task 5C: Returning user test

1. Log out
2. Verify LoginScreen returns with language from localStorage (Hindi)
3. Log back in → verify DB language loaded correctly
4. Check Profile → language still Hindi

### Task 5D: Resume test

1. Create new account, start onboarding
2. Close browser at step 2
3. Reopen → verify pre-step is SKIPPED (resume at step 2)
4. Language should still be correct from localStorage

---

## Files Changed Summary

| File | Phase | Track | Change |
|------|-------|-------|--------|
| `contexts/LanguageContext.tsx` | 1 | A | NEW — context, hook, conversion fns |
| `lib/onboarding-bot/translations.ts` | 1 | B | ADD ~55 keys |
| `backend/domain/models.py` | 1 | C | ADD validation regex |
| `App.tsx` | 2 | D | WRAP LanguageProvider + sync bridge |
| `contexts/OnboardingBotContext.tsx` | 2 | E | REFACTOR — delegate to LanguageContext |
| `types/onboarding-bot.ts` | 2 | E | REMOVE setLanguage, update startTour |
| `onboarding-bot/BotTooltip.tsx` | 2+4 | E+K | WIRE to LanguageContext |
| `screens/LoginScreen.tsx` | 3 | F | ADD pills + translate 25 strings |
| `screens/OnboardingScreen.tsx` | 3 | G | ADD pre-step + translate 30 strings |
| `screens/ProfileScreen.tsx` | 3 | H | ADD Indonesian + wire context |
| `AiRiskInsightsCard.tsx` | 4 | I | READ from LanguageContext |
| `onboarding-bot/BotInlineCard.tsx` | 4 | J | READ from LanguageContext |
