# Language Selection at Registration — Design Document

> **Date:** 2026-03-01
> **Status:** Approved
> **Scope:** Add language selection to LoginScreen + OnboardingScreen, unify language state across app

---

## Problem

Users cannot pick their language until they reach the Profile screen — after completing registration AND the 5-step onboarding wizard. The entire auth + onboarding flow is hardcoded English. Non-English speakers (Hindi, Indonesian) must navigate a foreign-language interface before they can change it.

Additionally:
- The onboarding bot has its own internal language state, disconnected from the user's DB record
- ProfileScreen is missing Indonesian as a language option
- AiRiskInsightsCard has a completely independent language toggle
- Backend accepts any string for `user.language` with no validation
- Two different value formats coexist: `'english'`/`'hindi'` (DB) vs `'en'`/`'hi'`/`'id'` (bot)

## Solution

1. Language pills on LoginScreen (translate the entire login UI)
2. Language confirmation pre-step in OnboardingScreen (before the 5-step wizard)
3. New `LanguageContext` as single source of truth for language across the app
4. Unify all language consumers to read from one context

## Requirements (User-Confirmed)

- Language selector on BOTH LoginScreen and OnboardingScreen
- Fully manual — no auto-mapping from city selection
- LoginScreen UI translates immediately when language is changed
- 3 supported languages: English (`en`), Hindi (`hi`), Indonesian (`id`)

---

## Architecture

### LanguageContext (New)

**Canonical format:** Short codes `'en' | 'hi' | 'id'` (type: `AppLanguage`)

**Storage:**
- Pre-auth: `localStorage('floodsafe_language')`
- Post-auth: Synced to `user.language` in DB

**Sync rules:**
- On mount (no user): Read localStorage. If empty, default `'en'`
- On auth (user loaded): If DB has non-default language → DB wins (returning user). Else localStorage wins (fresh registration)
- On language change: Update context + localStorage immediately. If user exists, PATCH to DB

**Value conversion at DB boundary:**
```typescript
type AppLanguage = 'en' | 'hi' | 'id';

const toShortCode = (dbVal: string): AppLanguage => {
  const map: Record<string, AppLanguage> = {
    english: 'en', hindi: 'hi', indonesian: 'id',
    en: 'en', hi: 'hi', id: 'id'
  };
  return map[dbVal?.toLowerCase()] || 'en';
};

const toDbValue = (code: AppLanguage): string => {
  const map: Record<AppLanguage, string> = {
    en: 'english', hi: 'hindi', id: 'indonesian'
  };
  return map[code];
};
```

**Context interface:**
```typescript
interface LanguageContextValue {
  language: AppLanguage;
  setLanguage: (lang: AppLanguage) => void;
}
```

### Provider Tree (New Ordering)

```
LanguageProvider              <-- NEW, outermost (works pre-auth)
  QueryClientProvider
    AuthProvider
      UserProvider
        LanguageSyncBridge    <-- useEffect: syncs context <-> DB
        CityProvider
          InstallPromptProvider
            VoiceGuidanceProvider
              NavigationProvider
                OnboardingBotProvider  <-- reads from LanguageContext
                  LocationTrackingProvider
```

`LanguageSyncBridge` is a useEffect (inside UserProvider or as a thin component) that:
- On user load: converts `user.language` → short code → updates context if DB wins
- On context change + user exists: converts short code → DB value → PATCH to backend

### OnboardingBotContext Refactor

**Phase 2 approach: backward-compatible bridge**

Remove internal `language` state. Instead, compute `state.language` from LanguageContext:
```typescript
const { language } = useLanguage();
// state.language still exposed on the state object, but reads from context
const state = { ...internalState, language };
```

This means existing consumers (`BotInlineCard`, `BotTooltip`, `ProfileScreen`) that read `botState.language` continue working without changes until they're individually migrated in Phase 4.

Remove `setLanguage` from bot context. Language pills in `BotTooltip` call `useLanguage().setLanguage()` instead.

Remove `cityToLanguage()` calls from initialization and `startTour()`. Language is already set by the user.

---

## UI Changes

### LoginScreen Language Pills

Position: Top of screen, above brand header.

```
+---------------------------------------+
|  [EN]  [Hindi]  [Bahasa]              |  <- language pills (active = filled)
|                                        |
|     Welcome to FloodSafe               |  <- translated
|  Community flood monitoring            |  <- translated
|                                        |
|  Email: [______________]               |  <- label translated
|  Password: [___________]               |  <- label translated
|                                        |
|  [ Create Account ]                    |  <- button translated
|  ---- or ----                          |  <- translated
|  [ Sign In ]                           |  <- button translated
+---------------------------------------+
```

~25 translation keys for LoginScreen (labels, buttons, placeholders, errors, toggles).

**Cannot translate (known limitations):**
- Firebase error messages (SDK returns English) — mitigated by mapping common error codes to translated strings
- Google Sign-In button (Google SDK auto-localizes based on `navigator.language`)

### OnboardingScreen Language Pre-Step

**Pre-step, NOT Step 1.** Does not increment `currentStep`, does not save to `onboarding_step` in DB, does not affect progress bar.

```
+---------------------------------------+
|  Choose your preferred language        |  <- translated
|                                        |
|  (*) English                           |
|  ( ) Hindi (Hindi)                     |
|  ( ) Bahasa Indonesia                  |
|                                        |
|  Pre-selected from LoginScreen choice  |
|                                        |
|        [ Continue -> ]                 |  <- translated
+---------------------------------------+
        | (no DB save, no step increment)
        v
+---------------------------------------+
|  Step 1 of 5: Select City             |  <- original step 1, unchanged
|  ====____________________  20%        |
```

**Implementation:** Boolean state `languageConfirmed`:
- New users: `false` → show pre-step
- Resuming users (`onboarding_step > 1`): `true` → skip pre-step
- After clicking Continue: `true` → show wizard

~30 translation keys for OnboardingScreen (headings, labels, errors, buttons, toasts).

### ProfileScreen Fix

- Add Indonesian as third radio option
- Wire `handleLanguageChange` to LanguageContext (which syncs to DB via bridge)
- Read display value from LanguageContext

### AiRiskInsightsCard Fix

- Remove local `useState<'en' | 'hi'>('en')`
- Read from LanguageContext
- API only supports `en`/`hi`, so map `'id'` → `'en'` for the API call

---

## Backend Changes (Minimal)

**`domain/models.py` — UserUpdate validation:**
```python
language: Optional[str] = Field(None, pattern="^(english|hindi|indonesian|en|hi|id)$")
```

Accepts both formats during transition. No database migration needed.

**No changes to:** `get_user_language()` in message_templates.py (already normalizes both formats), infrastructure/models.py (column stays String type).

---

## Translation Scope

### New Keys (~55 total)

**LoginScreen (~25):**
`login.brand.tagline`, `login.brand.cities`, `login.heading.create`, `login.heading.signin`,
`login.subheading.create`, `login.subheading.signin`, `login.label.email`, `login.label.password`,
`login.placeholder.email`, `login.placeholder.password.create`, `login.placeholder.password.signin`,
`login.button.create`, `login.button.signin`, `login.button.creating`, `login.button.signingIn`,
`login.divider.or`, `login.toggle.toSignin`, `login.toggle.toSignup`, `login.toggle.toPhone`,
`login.phone.heading`, `login.phone.subheading`, `login.phone.placeholder`,
`login.phone.sendCode`, `login.phone.changeNumber`, `login.phone.codeSent`,
`login.phone.verify`, `login.phone.backToEmail`, `login.terms`,
`login.error.email`, `login.error.password`

**OnboardingScreen (~30):**
`onboarding.header.welcome`, `onboarding.header.subtitle`, `onboarding.language.title`,
`onboarding.language.continue`, `onboarding.steps.*` (5 step titles), `onboarding.progress`,
`onboarding.city.*`, `onboarding.profile.*`, `onboarding.watchAreas.*`, `onboarding.routes.*`,
`onboarding.complete.*`, `onboarding.nav.*`, `onboarding.toast.*`, `onboarding.error.*`

### What Stays English (Out of Scope)

- FloodAtlasScreen, map labels, alert cards (server data)
- HomeScreen, AlertsScreen, ReportScreen
- Complex components (search, routing, gamification)

Full app i18n is a separate, larger effort.

---

## Phased Parallel Workflow

### Phase 1: Foundation (3 parallel tracks)

| Track | File(s) | Work |
|-------|---------|------|
| A | `contexts/LanguageContext.tsx` (NEW) | Create context, hook, localStorage logic, conversion functions |
| B | `translations.ts` + `types.ts` + `onboarding-bot.ts` | Add ~55 translation keys, add `AppLanguage` type |
| C | `backend/domain/models.py` | Add language validation regex |

**Test Gate 1:** `npx tsc --noEmit` — types compile, no missing exports

### Phase 2: Core Wiring (2 parallel tracks)

| Track | File(s) | Work |
|-------|---------|------|
| D | `App.tsx` | Add LanguageProvider to tree, add LanguageSyncBridge |
| E | `OnboardingBotContext.tsx` | Remove internal language state, bridge from LanguageContext, remove cityToLanguage() calls |

**Test Gate 2:** `npx tsc --noEmit` + dev server boots without errors

### Phase 3: UI Screens (3 parallel tracks)

| Track | File(s) | Work |
|-------|---------|------|
| F | `LoginScreen.tsx` | Language pills, translate ~25 strings via `t()` |
| G | `OnboardingScreen.tsx` | Pre-step, `languageConfirmed` state, translate ~30 strings |
| H | `ProfileScreen.tsx` | Add Indonesian radio, wire to LanguageContext |

**Test Gate 3:** `npx tsc --noEmit` + `npm run build` — full bundle compiles

### Phase 4: Peripheral Consumers (3 parallel tracks)

| Track | File(s) | Work |
|-------|---------|------|
| I | `AiRiskInsightsCard.tsx` | Remove local state, read from LanguageContext |
| J | `BotInlineCard.tsx` | Import useLanguage, read from context |
| K | `BotTooltip.tsx` | Import useLanguage, wire language pills to context |

**Test Gate 4:** `npm run build` + dev server + smoke test UI

### Phase 5: E2E Verification (sequential)

1. Create new account with Hindi selected → verify every screen in Hindi
2. WebMCP `context_app_state` → confirm language in state
3. Chrome DevTools screenshots (LoginScreen in 3 languages, OnboardingScreen pre-step, ProfileScreen)
4. Returning user: log out → log in → verify DB language loads
5. Resume: start onboarding → close at step 2 → reopen → verify skips pre-step

### Parallel Safety

- Zero file conflicts in any phase (each track edits unique files)
- Phase 2 uses backward-compatible bridge (`state.language` reads from LanguageContext) so Phase 3/4 consumers don't break between phases
- Each test gate catches regressions before next phase starts

---

## Edge Cases

| Scenario | Behavior | Status |
|----------|----------|--------|
| New user never picks language | Default `'en'`, entire flow English | OK |
| User picks Hindi on login, closes before onboarding | localStorage `'hi'`, next visit pre-step pre-filled | OK |
| User picks Hindi, completes, logs in on new device | DB `'hindi'` → mapped to `'hi'` → context updated | OK |
| Indonesian user, WhatsApp alert | `get_user_language()` returns `'en'` (no Indonesian templates) | Documented limitation |
| Slow network, language sync fails | localStorage is truth, DB syncs next time | OK |
| Existing user resumes from step 3 | `languageConfirmed = true`, skips pre-step | OK |
| Profile language change months later | LanguageContext → DB update, next session loads new preference | OK |
| Google Sign-In button language | Google SDK uses `navigator.language`, may not match our picker | Known limitation |

---

## Files Changed

```
NEW:  apps/frontend/src/contexts/LanguageContext.tsx
EDIT: apps/frontend/src/App.tsx
EDIT: apps/frontend/src/components/screens/LoginScreen.tsx
EDIT: apps/frontend/src/components/screens/OnboardingScreen.tsx
EDIT: apps/frontend/src/components/screens/ProfileScreen.tsx
EDIT: apps/frontend/src/contexts/OnboardingBotContext.tsx
EDIT: apps/frontend/src/lib/onboarding-bot/translations.ts
EDIT: apps/frontend/src/types.ts
EDIT: apps/frontend/src/types/onboarding-bot.ts
EDIT: apps/frontend/src/components/AiRiskInsightsCard.tsx
EDIT: apps/frontend/src/components/onboarding-bot/BotInlineCard.tsx
EDIT: apps/frontend/src/components/onboarding-bot/BotTooltip.tsx
EDIT: apps/backend/src/domain/models.py
```

**Safe (no changes):** `infrastructure/models.py`, `auth_service.py`, `AuthContext.tsx`, `token-storage.ts`, `core/config.py`
