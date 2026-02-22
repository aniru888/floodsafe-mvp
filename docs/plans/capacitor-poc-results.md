# Capacitor Android PoC Results

> Date: 2026-02-22
> Phase: 1A (Tasks 5-7)

## Setup Status

| Step | Status | Notes |
|------|--------|-------|
| Install @capacitor/core + @capacitor/cli | PASS | v7.x installed |
| Install @capacitor/android | PASS | Android platform package |
| `npx cap init` | PASS | capacitor.config.ts created |
| `npx cap add android` | PASS | android/ directory generated |
| `npm run build` | PASS | Vite build (2.78MB bundle) |
| `npx cap sync` | PASS | Web assets copied to Android project |
| `npx tsc --noEmit` | PASS | No type errors |
| CORS origin added | PASS | `http://localhost` in config.py |
| Backend tests | PASS | 66/66 passed |

## Android Emulator Testing

**Status: BLOCKED** — Android Studio is not installed on this machine.

### Prerequisites Needed
1. Install Android Studio (https://developer.android.com/studio)
2. Install Android SDK (API 30+)
3. Create AVD (Android Virtual Device) with API 30+ (Android 11+)
4. Run: `cd apps/frontend && npx cap open android`

### Verification Checklist (pending)

- [ ] App loads without white screen
- [ ] MapLibre renders (WebGL works in WebView)
- [ ] Map is interactive (pan, zoom, tap markers)
- [ ] API calls succeed (check Chrome DevTools > WebView for CORS errors)
- [ ] Email login works (doesn't use popup)
- [ ] Google login — EXPECT FAILURE (document the error for later fix)
- [ ] Service worker registers (`chrome://inspect` > WebView)
- [ ] Airplane mode: offline indicator shows
- [ ] SOS queues to IndexedDB when offline

### Kill Criteria
- MapLibre doesn't render → STOP (native map SDK = project rewrite)
- Service worker doesn't register → STOP (core offline features break)
- Gradle build fails → likely fixable (path/asset config)

## Files Changed

| File | Change |
|------|--------|
| `apps/frontend/package.json` | Added @capacitor/core, @capacitor/cli, @capacitor/android |
| `apps/frontend/capacitor.config.ts` | NEW — Capacitor config (appId, webDir, androidScheme) |
| `apps/frontend/android/` | Generated (gitignored) |
| `.gitignore` | Added apps/frontend/android/ and ios/ exclusions |
| `apps/backend/src/core/config.py` | Added http://localhost to CORS origins |
