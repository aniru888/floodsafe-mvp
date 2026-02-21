# Viability Assessment: Offline App, Push Notifications, WhatsApp Sync, BLE Mesh

> Date: 2026-02-22
> Status: Design (feasibility analysis + PoC test plans)
> Constraint: Solo developer, minimal budget (free tiers only)
> Context: FloodSafe is a 4-city flood monitoring PWA (Delhi, Bangalore, Yogyakarta, Singapore)

---

## Table of Contents

1. [Capability 1: Capacitor Native Wrapper](#capability-1-capacitor-native-wrapper)
2. [Capability 2: Push Notifications for Route-Based Alerts](#capability-2-push-notifications-for-route-based-alerts)
3. [Capability 3: WhatsApp Bidirectional Sync](#capability-3-whatsapp-bidirectional-sync)
4. [Capability 4: BLE Mesh + SMS Fallback](#capability-4-ble-mesh--sms-fallback)
5. [Cross-Cutting Concerns](#cross-cutting-concerns)
6. [Final Verdict & Build Order](#final-verdict--build-order)
7. [Appendix: Existing Infrastructure Audit](#appendix-existing-infrastructure-audit)

---

## Capability 1: Capacitor Native Wrapper

### What Exists Today

FloodSafe is a PWA with Workbox service worker:
- **CacheFirst**: Google Fonts, MapLibre CSS, PMTiles, images (30-365 day TTL)
- **NetworkFirst**: API calls (10s timeout, 24h cache fallback) — excludes `/api/ml/classify`
- **StaleWhileRevalidate**: GeoJSON files (24h)
- **IndexedDB**: SOS queue (`floodsafe-sos`) + auth token cache (`floodsafe-auth`)
- **Background Sync**: `flush-sos-queue` tag triggers SOS delivery when connectivity returns
- **Install banner**: `InstallPromptContext.tsx` + `InstallBanner.tsx`
- **Offline indicator**: `OfflineIndicator.tsx`

No Capacitor config, no `android/` or `ios/` directories, no native wrapper of any kind.

### What Capacitor Adds

| Capability | PWA Today | Capacitor Adds |
|-----------|-----------|----------------|
| Distribution | "Add to Home Screen" | Play Store listing |
| Push (iOS) | Safari 16.4+ only | Native push via APNs |
| BLE access | Web Bluetooth (foreground only) | Native BLE (background capable) |
| Background tasks | Background Sync only | True background services |
| File system | Cache API (~50MB soft limit) | Full native filesystem |
| Geofencing | None | Native geofence triggers |
| SMS sending | None | Native SMS intent |

### Critical Scrutiny

#### CORS Will Break Immediately

**Finding**: Backend CORS config (`apps/backend/src/core/config.py`, line 18-22) only allows:
```
http://localhost:5175
http://localhost:8000
https://frontend-lime-psi-83.vercel.app
```

Capacitor WebView uses origin `http://localhost` (Android) or `capacitor://localhost` (iOS). **All API calls will fail with CORS errors** until these origins are added to the allow list.

**Fix**: Add `http://localhost` (Android) and `capacitor://localhost` (iOS) to `BACKEND_CORS_ORIGINS` in both config.py defaults and Koyeb env var. Note: `http://localhost` without a port is different from the existing `http://localhost:5175` — both are needed.

#### Firebase Auth Popup Will Not Work

Firebase `signInWithPopup` (used for Google Auth) **does not work in Capacitor WebView**. The popup is blocked or opens in an external browser that can't redirect back.

**Fix options**:
1. Use `signInWithRedirect` instead (works in WebView, but requires careful state management)
2. Use `@capacitor-firebase/authentication` plugin (native Google Sign-In dialog)
3. Both are non-trivial changes to `AuthContext.tsx`

**Severity**: HIGH — Google login would be completely broken without this fix.

#### Google OAuth Domain Restrictions

**Finding**: Google OAuth is configured to only allow login from the Koyeb backend URL and the Vercel production URL. Capacitor's `http://localhost` origin is NOT an authorized domain in Firebase/Google OAuth console.

**Implication**: Even after fixing the popup→redirect flow, Google Auth will **reject the request** because `http://localhost` (Capacitor Android) is not in the authorized domains list. You must add it in:
1. Firebase Console → Authentication → Settings → Authorized domains
2. Google Cloud Console → OAuth consent screen → Authorized redirect URIs

**Testing constraint**: All auth PoC testing must be done through the **production Koyeb backend** and **production Vercel frontend URLs**, not local dev. The Capacitor WebView must point its API calls to the production backend (which it will, since the env var `VITE_API_URL` points to Koyeb in the build).

#### MapLibre WebGL Performance

MapLibre GL JS requires WebGL. Android WebView supports WebGL, but:
- Low-end devices (1-2GB RAM) may stutter with complex layers (hotspots + metro + inundation + routes)
- Some budget Android phones have poor GPU drivers for WebView specifically
- PMTiles protocol (already used) helps since tiles are local/cached, not fetched per-pan

**Mitigation**: Reduce max visible layers on mobile. Test on $100 Android phone, not flagship.

#### Service Worker Behavior Differs

Capacitor Android WebView supports service workers (since Android 7.0+ / API 24 via `ServiceWorkerController`; older devices may work if WebView is updated via Play Store), but:
- iOS WKWebView **effectively does not support service workers in Capacitor** due to the `capacitor://` custom scheme conflicting with SW's HTTP/HTTPS requirement (open Capacitor issues #4122, #7069)
- SW `push` event handler may not fire in background on iOS
- Background Sync API: supported on Android WebView, NOT on iOS WebView

**Consequence**: iOS Capacitor would need `@capacitor/push-notifications` plugin (bypasses SW entirely for push). The existing `sw-sos-sync.js` Background Sync would only work on Android.

#### True Time Estimate

I initially said "2-3 hours" for the PoC. That was **unrealistically optimistic**.

Realistic breakdown:
- Android Studio + SDK download (first time): **1-2 hours**
- Capacitor init + build + sync: **30 min**
- First emulator run: **30 min** (Gradle build is slow)
- Debugging CORS + Firebase issues: **2-4 hours**
- **Total: 4-7 hours** for a functioning PoC, not 2-3

### Verdict

**VIABLE for Android** — requires CORS fix, Firebase auth redirect, and testing on low-end devices.
**CONDITIONAL for iOS** — requires $99/year Apple Developer account + significant SW workarounds.
**Recommendation**: Android-only for now. $25 one-time Google Play fee is budget-compatible.

### PoC Test Plan

```
Experiment: "Can FloodSafe run in Capacitor on Android?"
Time estimate: 5-7 hours (honest)
Prerequisites: Android Studio + SDK installed

Steps:
1. cd apps/frontend
2. npm install @capacitor/core @capacitor/cli
3. npx cap init FloodSafe com.floodsafe.app --web-dir dist
4. npx cap add android
5. Add "http://localhost" (Android) to backend CORS (config.py + Koyeb env)
6. npm run build && npx cap sync
7. npx cap open android → run on emulator (API 30+)

Verify:
- [ ] App loads without white screen
- [ ] MapLibre renders and is interactive (pan, zoom, tap markers)
- [ ] API calls succeed (no CORS errors in WebView console)
- [ ] Email login works (doesn't use popup)
- [ ] Google login — EXPECT FAILURE (popup blocked + unauthorized domain) → document the error
- [ ] Verify API calls go to production Koyeb backend (not localhost)
- [ ] Service worker registers (check chrome://inspect > WebView)
- [ ] Airplane mode: offline indicator shows, SOS queues to IndexedDB
- [ ] Reconnect: SOS queue flushes

Kill criteria:
- MapLibre doesn't render (no WebGL) → STOP, native map SDK = project rewrite
- Service worker doesn't register in WebView → STOP, core offline features break
- Gradle build fails on Vite output → likely fixable (path/asset config)

Known issues to defer (not kill criteria):
- Google Auth popup blocked → will fix with redirect flow later
- Firebase phone auth recaptcha may not render → defer to plugin solution

WebMCP Testing (use native WebMCP bridge for verification):
- Use `context_app_state` to verify auth state, city selection, user profile load correctly in WebView
- Use `floodsafe://hotspots/{city}` resource to confirm hotspot data loads (proves API + cache working)
- Use `floodsafe://alerts/{city}` resource to confirm alert pipeline functions
- Use `switch_city` tool to test city switching works in WebView context
- Use `search_locations` tool to verify geocoding API calls succeed through WebView CORS
- If WebMCP entities respond correctly → core app functionality confirmed without manual UI testing
```

---

## Capability 2: Push Notifications for Route-Based Alerts

### What Exists Today

- **Firebase SDK** (`firebase ^10.7.0`) installed, but ONLY Phone Auth initialized
- **`getMessaging` is never imported or called anywhere in the codebase**
- `messagingSenderId` is in `firebaseConfig` (line 28 of `firebase.ts`) but unused
- No `firebase-messaging-sw.js` service worker for background push
- Watch areas use PostGIS `ST_DWithin` but only check on-demand (user opens app)
- Saved routes have origin/destination coordinates + transport mode
- FHI scoring runs per-request, no scheduled background monitoring
- Twilio sends SMS/WhatsApp outbound, but not FCM push

### Architecture Required

```
Backend (New):
  ┌──────────────────┐     ┌─────────────────┐
  │ Cron Trigger      │────>│ Route Monitor    │
  │ (external, 15min) │     │ Service          │
  └──────────────────┘     └────────┬────────┘
                                    │
                           Fetch cached FHI
                           per city (NOT per route)
                                    │
                           ┌────────▼────────┐
                           │ For each user's  │
                           │ saved routes:    │
                           │ any hotspot      │
                           │ within 300m at   │
                           │ HIGH+ FHI?       │
                           └────────┬────────┘
                                    │ yes
                           ┌────────▼────────┐
                           │ FCM Push Service │
                           │ (firebase-admin) │
                           └─────────────────┘

Frontend (New):
  1. getMessaging() → getToken() → store FCM device token
  2. POST /api/users/me/fcm-token
  3. firebase-messaging-sw.js handles background push
  4. Notification click → deep link to route in app
```

### Critical Scrutiny

#### Koyeb Sleep Kills Background Cron

Koyeb free tier sleeps after 5 minutes of inactivity. A cron job inside the backend process **will never fire** because the process isn't running.

**Workaround**: Use external cron service (e.g., cron-job.org) to ping `GET /api/cron/check-routes` every 15 minutes. But:
- cron-job.org free tier: unlimited jobs, minimum interval = 1 minute (fine for 15min)
- Koyeb cold start: **10-30 seconds**. The cron HTTP request may timeout at the caller's end.
- **Fix**: cron-job.org allows 30s timeout. Koyeb typically wakes in 15s. Should work, but add retry logic.
- **Alternative**: Vercel Cron is available on free tier but limited to 2 jobs at once-per-day frequency — insufficient for 15-minute route checks. Not viable.

#### FHI Rate Limits — The Batching Trick

Open-Meteo allows ~10,000 requests/day (free, no key). Naive approach:

```
100 users × 3 saved routes × 96 checks/day (every 15 min) = 28,800 FHI calls/day
```

This **exceeds the rate limit by 3x**.

**Smart batching**: Don't compute FHI per-route. The ML service already caches FHI per-city (1hr TTL). The cron job should:
1. Fetch city hotspot scores (already cached, ~1 API call per city)
2. For each user's saved routes, check if any route segment passes within 300m of a HIGH+ hotspot
3. This is a **spatial query** (PostGIS), not an API call

**Result**: 4 FHI fetches/day (one per city per cache miss), not 28,800. The per-route check is pure geometry.

#### Notification Fatigue

If a route stays HIGH risk for 6 hours, a naive 15-min cron sends **24 push notifications**. This will make users disable notifications entirely.

**Required**: Cooldown logic — 1 notification per route per severity *transition* (LOW→HIGH triggers push, HIGH→HIGH does not). Store `last_notified_at` and `last_notified_severity` per saved route.

#### FCM Token Lifecycle

FCM tokens expire and rotate. `onTokenRefresh` callback must update the backend. If the token stored in the backend is stale, push silently fails (no error to the user).

**Fix**: Re-register token on every app open (cheap, idempotent `POST /api/users/me/fcm-token`). Firebase recommends this.

#### Firebase Admin SDK on Koyeb

Requires a service account JSON file. Koyeb env vars are strings, not files.

**Standard workaround**: Base64-encode the JSON, store as `FIREBASE_SERVICE_ACCOUNT_B64` env var, decode at startup:
```python
import base64, json
creds = json.loads(base64.b64decode(os.environ["FIREBASE_SERVICE_ACCOUNT_B64"]))
```

This is well-documented and works. Not a blocker.

### Verdict

**HIGHLY VIABLE**. FCM is free and unlimited. The main work is:
1. Frontend: initialize messaging, request permission, store token (half a day)
2. Backend: FCM push service + cron endpoint (1 day)
3. Cooldown + spatial route check logic (half a day)

Total: **2-3 days of focused work**, honestly estimated.

### PoC Test Plan

```
Experiment: "Can we send a push notification from backend to browser?"
Time estimate: 3-4 hours
Prerequisites: Firebase project (exists), service account JSON

Steps:
1. Generate Firebase service account key (Firebase Console > Project Settings > Service Accounts)
2. Base64-encode it, add to Koyeb env as FIREBASE_SERVICE_ACCOUNT_B64

Frontend:
3. In firebase.ts: import { getMessaging, getToken } from 'firebase/messaging'
4. Create initMessaging() function:
   - Call getMessaging(app)
   - Request Notification.requestPermission()
   - Call getToken(messaging, { vapidKey: VITE_FIREBASE_VAPID_KEY })
   - POST token to /api/users/me/fcm-token
5. Create public/firebase-messaging-sw.js:
   - importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js')
   - messaging.onBackgroundMessage → self.registration.showNotification()

Backend:
6. pip install firebase-admin
7. Create push_notification_service.py:
   - Initialize firebase_admin with decoded service account
   - send_push(token, title, body) → messaging.send(Message(...))
8. Create /api/users/me/fcm-token endpoint (POST, stores token on User model)
9. Send test push manually via Python shell

Verify:
- [ ] Browser shows notification permission dialog
- [ ] FCM token generated and stored in DB
- [ ] Backend sends push → notification appears (browser tab closed!)
- [ ] Notification click opens FloodSafe
- [ ] Token refresh updates DB record (close/reopen app)

Kill criteria:
- Firebase service account can't load on Koyeb → workaround: try env var decode
- FCM getToken fails (VAPID key wrong) → regenerate in Firebase Console
- Push doesn't show when tab is closed → firebase-messaging-sw.js not registering

WebMCP Testing (verify push plumbing via bridge):
- After FCM token stored, use `get_query_cache` with key `["user-profile"]` to verify
  the fcm_token field is persisted on the user object
- Use `context_app_state` to confirm notification permission state
- After sending test push, use `floodsafe://alerts/{city}` to verify the alert
  pipeline didn't break during firebase-messaging-sw.js registration

Do NOT test yet:
- Route-based monitoring (needs cron + spatial logic — build after push works)
- Capacitor native push (needs PoC 1 first)
```

---

## Capability 3: WhatsApp Bidirectional Sync

### What Exists Today

**Inbound (WhatsApp → FloodSafe):**
- Meta WhatsApp Cloud API webhook: `apps/backend/src/api/whatsapp_meta.py` (HMAC-SHA256 signature validation, rate limiting 10 msgs/60s)
- Command handlers: RISK, WARNINGS, MY AREAS, STATUS, LINK, START/STOP
- Photo handler: receives images → ML flood classification via embedded TFLite
- Quick Reply buttons: 9 types (report_flood, check_risk, view_alerts, etc.)
- Session management: `WhatsAppSession` model, 30-min timeout

**Outbound (FloodSafe → WhatsApp):**
- `TwilioNotificationService`: sends alerts to watch area phone numbers
- `sos_service.py`: SOS broadcast to safety circle phones via Twilio
- `circle_notification_service.py`: dispatches via WhatsApp/SMS/email

**The gap**: These are disconnected systems:
- A flood report sent via WhatsApp does NOT create a `Report` record in the database
- A report submitted in the app does NOT notify WhatsApp contacts (unless it triggers a safety circle alert)
- `WhatsAppSession.phone` (line 430 in models.py) has no foreign key to `User.phone` (line 47). **There is no reliable way to link a WhatsApp sender to a FloodSafe user account.**

### Three Approaches

**Approach A: Inbound-Only Sync (Recommended)**

WhatsApp reports create proper `Report` records visible in-app. No proactive outbound.

- Effort: 2-3 days
- Cost: $0
- Meta approval: NOT required (webhook already works)

**Approach B: Inbound + Templated Outbound**

Everything in A + submit Message Templates to Meta for proactive flood alerts.

- Effort: 1-2 weeks (including Meta approval wait)
- Cost: Service replies within 24hr window are FREE (unlimited). Proactive template messages: ~INR 0.13/msg (utility) or ~INR 0.88/msg (marketing)
- Meta approval: REQUIRED (business verification + template review)

**Approach C: Full Bidirectional Mirror**

WhatsApp becomes a complete alternative interface to the app.

- Effort: 3-4 weeks
- Cost: Likely exceeds free tier at any user count
- Meta approval: REQUIRED + 10+ templates

### Critical Scrutiny

#### The Phone → User Mapping Gap Is Worse Than It Looks

Current state in `models.py`:
- `User.phone` (line 47): nullable String, populated for phone-auth users
- `WhatsAppSession.phone` (line 430): String PK in E.164 format
- `CircleMember.phone` (line 494): nullable String
- **No FK or index linking WhatsAppSession to User**

When a WhatsApp message arrives, the webhook knows the sender's phone number. To create a `Report` linked to a user:
1. Look up `User` by `phone` field → may be NULL (email/Google auth users don't have phone set)
2. The user may have registered with a different phone (Firebase Phone Auth number != WhatsApp number)
3. **70-80% of users may not be matchable** if they signed up via email/Google

**Fix**: Create a `user_phone_links` table or add a `whatsapp_phone` field on User. Require explicit linking (user sends "LINK" command in WhatsApp → enters email → verified).

This linking flow already partially exists (`LINK` command in command_handlers.py) but I haven't verified it creates the DB association. This needs investigation before building sync.

#### Meta Business Verification — The Organizational Blocker

This is NOT a technical problem. It's a bureaucratic one:
- Requires: registered business entity (NPO/NGO qualifies)
- Requires: business website with matching domain
- Requires: Meta Business Portfolio
- Timeline: 2-4 weeks for review, can be rejected
- **Without this, you're limited to Twilio Sandbox** (only pre-registered test numbers, max ~5)

For solo dev: Unless FloodSafe is registered as an entity (even an informal NPO), Meta verification will fail. This is the hardest blocker and it's not about code.

#### The 24-Hour Window Rule

Meta's policy: you can send freeform replies for 24 hours after the user's last message. After that, you MUST use pre-approved Message Templates.

**Implication for sync**: If a user submits a report in-app and you want to send them a WhatsApp confirmation — you can only do this if they messaged the bot within the last 24 hours. Otherwise, you need a template.

Templates require:
- Submission to Meta (1-3 day review per template)
- Specific format (header, body, footer, buttons)
- No dynamic URLs in body (only in buttons)
- Rejection if too promotional or unclear

For a flood alert template, something like:
```
Header: FloodSafe Alert
Body: {{1}} flood risk detected on your route {{2}}.
      Current risk level: {{3}}.
Footer: Reply STOP to unsubscribe
Button: [Open FloodSafe]
```

This is doable but requires Meta approval. Cannot be tested on sandbox.

#### Cost Reality Check

```
Meta WhatsApp Business API (India pricing, updated July 2025):
  NOTE: Meta switched from conversation-based to per-message pricing in July 2025.
  Service replies (within 24hr window):  FREE, unlimited
  Utility template messages:             INR 0.13/msg
  Marketing template messages:           INR 0.88/msg
  Authentication template messages:      INR 0.13/msg

  500 users, 5 alerts/month each (sent as utility templates):
    2,500 msgs × INR 0.13 = INR 325/month (~$3.90/month)

  If alerts sent within 24hr reply window (user messaged bot recently):
    FREE — $0/month

  Verdict: Significantly cheaper than old model. Reply-window strategy
           could make outbound nearly free if users interact regularly.

Twilio WhatsApp (current, sandbox only):
  Per-message: ~$0.005 + carrier fees
  Cannot go production without Meta Business verification anyway
```

#### Twilio → Meta Direct Migration

Currently using Twilio as intermediary for outbound. Going Meta direct means:
- Rewriting `TwilioNotificationService` to use Meta Graph API
- Different API contract (Twilio REST vs Meta Graph API v21.0)
- Different webhook format (already have Meta webhook, would retire Twilio webhook)
- **Can't run both simultaneously** without careful routing

This migration is non-trivial. Estimate: 1-2 days just for the API swap, before any sync logic.

### Verdict

**Approach A (inbound sync) is VIABLE** — mostly exists, main work is Report creation from WA messages + phone→user linking.

**Approach B requires Meta Business Verification** — organizational blocker, not technical. Apply early, build if approved.

**Approach C is NOT REALISTIC** for solo dev on free tier.

### PoC Test Plan

```
Experiment A: "Can a WhatsApp flood report create a Report in the database?"
Time estimate: 3-4 hours
Prerequisites: Twilio sandbox connected

Steps:
1. Investigate LINK command: does it actually persist phone→user mapping? (Read command_handlers.py)
2. If not: add whatsapp_phone column to User model (migration)
3. Modify photo_handler.py:
   - After ML classification, create Report record:
     reporter_id = User lookup by whatsapp_phone (or create anonymous "wa_reporter")
     location = from WhatsApp location pin (already parsed in webhook)
     severity = from ML confidence score
     source = "whatsapp" (add to Report model if needed)
4. Send WhatsApp message: photo + location pin to Twilio sandbox number
5. Check database: Report record created?
6. Open FloodSafe app: Report visible on map + community feed?

Verify:
- [ ] WhatsApp photo → Report record in DB
- [ ] Location pin → correct lat/lng on Report
- [ ] Report visible in app immediately (query invalidation working)
- [ ] ML classification score attached
- [ ] Duplicate detection: same user, same location, <10 min → no duplicate
- [ ] Anonymous reporter: if phone not linked to User, report still created

Kill criteria:
- WhatsApp media download fails (Meta CDN URL expired) → increase download timeout
- Photo storage is mocked → reports will have mock URLs (acceptable for PoC)
- Location pin not sent → report created without coordinates (allow, flag for review)

WebMCP Testing (verify WA→Report sync via bridge):
- After WhatsApp report created, use `floodsafe://reports` resource to check if
  the new report appears in the reports list without page refresh
- Use `search_locations` with the report's address to verify location data is correct
- Use `floodsafe://hotspots/{city}` to confirm hotspot data wasn't corrupted by
  the new Report creation path
- Use `context_app_state` to verify user session if LINK command was used

Blocker validation (start ASAP, do not wait for code):
- [ ] Can FloodSafe register as nonprofit/entity for Meta Business Verification?
- [ ] Submit Meta Business Portfolio application → track timeline
- [ ] Submit 1 test message template → track approval timeline
- [ ] If either takes >4 weeks or is rejected → Approach B is not viable at this time
```

---

## Capability 4: BLE Mesh + SMS Fallback (BitChat-like SOS)

### What BitChat Actually Is (and Isn't)

BitChat uses BLE advertising as a broadcast channel:
- Messages encoded in BLE advertisement packets (31 bytes max, ~20 usable after overhead)
- No pairing required — passive scanning discovers nearby devices
- **Single-hop only** — you see messages from devices within ~30-100m
- NOT a true mesh — no multi-hop relay, no routing protocol
- Works at events/conferences (high density, everyone has the app)

True mesh networking (Meshtastic, Bridgefy, Briar) is fundamentally different — multi-hop relay, store-and-forward, routing tables. This is a research-grade problem.

### The Critical Mass Problem (The Real Killer)

This is not a technical problem — it's a **physics + adoption problem**:

```
BLE range: ~30-100m (walls, rain, and flooding reduce this to ~15-50m)

Scenario: Flood in Delhi, user's internet is down.
Question: How many FloodSafe users are within 50m?

Urban density calculation:
  Delhi population density: ~11,000/km²
  Area within 50m radius: ~7,850 m² = 0.00785 km²
  People within 50m: ~86
  Smartphone penetration: ~70% → 60 smartphone users
  FloodSafe adoption: 0.01% (optimistic for early stage) → 0.006 users

  Result: < 1 FloodSafe user within BLE range.

  For BLE to reliably find 1 peer, you need:
  - 1% adoption in the area = ~600 nearby users with FloodSafe
  - This requires ~60,000 total users in Delhi
  - Current user count: << 1,000
```

**BLE mesh is only useful at scale you don't have.** This isn't a criticism — it's math.

### Three Approaches

**Approach A: Store-and-Forward SOS (Recommended)**

No BLE. Focus on guaranteed delivery via any available channel:

```
User taps SOS → IndexedDB queue (already exists) → retry loop:
  1. WiFi? → POST to FloodSafe API (already exists)
  2. Cell data? → POST to FloodSafe API (already exists)
  3. SMS available? → Native SMS to safety circle (NEW, via Capacitor)
  4. Nothing? → Keep retrying. Survives app restart.
```

**Approach B: BLE Beacon (Broadcast-Only, No Chat)**

Not messaging — just a distress signal:

```
SOS activated → BLE advertise: [magic_byte][severity][lat_4bytes][lng_4bytes]
Any nearby FloodSafe app scanning → "SOS detected ~50m away" on map
That device relays to server when it gets connectivity
```

**Approach C: Full BLE Mesh Chat**

Multi-hop text messaging between phones.

### Critical Scrutiny

#### Approach A: Native SMS Is Not Truly "Free" or "Automatic"

I originally said "native SMS is FREE — user's phone sends it." This needs correction:

1. **Android Play Store Policy**: Apps that send SMS without user interaction may be **rejected from Play Store** (anti-spam policy). Google requires explicit user confirmation for SMS sends.
2. **User confirmation required**: `@byteowls/capacitor-sms` opens the SMS compose screen with pre-filled text. The user must tap "Send." It is NOT automatic.
3. **Data-only SIMs**: Some users (especially with secondary phones) have data-only plans. SMS won't work.
4. **Cost varies by country**: India SMS is essentially free (bundled). Singapore SMS costs SGD 0.03/msg. Indonesia varies.

**Revised assessment**: "Free" is misleading. It's "user pays their carrier rate" and requires manual tap. Still better than nothing, but not the seamless background send I implied.

**Better framing**: This is a "pre-composed emergency SMS" feature, not an "automatic SMS fallback."

#### Approach B: BLE Beacon Scrutiny

1. **BLE advertising in background (Android)**: Requires `BLUETOOTH_ADVERTISE` permission (Android 12+). User must grant. App must have a foreground service running to maintain advertising. Battery drain: ~2-5%/hour for continuous advertising.
2. **BLE scanning in background (Android)**: Requires `BLUETOOTH_SCAN` permission. Can use `PendingIntent`-based scanning, but Android limits scan frequency in background (to save battery). May take 5-15 minutes to discover a nearby beacon. In an emergency, that's too slow.
3. **iOS**: Background BLE advertising possible as peripheral, but **scanning as central in background is severely throttled** (iOS may not deliver results for 10+ minutes). Effectively useless.
4. **Spoofing**: BLE advertisements are unencrypted. Anyone can broadcast a fake FloodSafe SOS beacon. Would need a signing scheme (HMAC with device-specific key), which complicates the protocol and expands the 20-byte payload.
5. **Range in flood conditions**: Water absorbs 2.4GHz signals. Standing water, rain, and humidity all reduce BLE range. The ~100m clear-air range could drop to ~15-30m in heavy rain. Combined with the critical mass problem, this makes real-world utility extremely low.

#### Approach C: Disqualified

Building a multi-hop mesh routing protocol is:
- 2-3 months minimum development
- Requires solving message deduplication, loop prevention, TTL management
- No off-the-shelf Capacitor plugin exists
- The critical mass problem is even worse (need relay nodes)
- **This is PhD-level research, not a solo dev feature**

#### What ACTUALLY Saves Lives Without Internet

```
Things that work when internet is down:        Things that DON'T:
──────────────────────────────────────────      ──────────────────
Pre-cached map + hotspot data   ← EXISTS        BLE mesh (no users nearby)
Pre-cached route data           ← EXISTS        Push notifications (no internet)
SOS queue with retry            ← EXISTS        Cloud API calls
SMS to emergency contacts       ← ADD (easy)    WhatsApp (needs internet)
Offline voice guidance          ← EXISTS        Real-time FHI updates
Last-known FHI displayed        ← EXISTS        Community reports
```

The table above shows that FloodSafe already covers most offline scenarios. The highest-impact addition is the SMS compose feature (~1 day of work), not BLE mesh (~3 months).

### Verdict

**Approach A (Store-and-Forward + SMS compose) is HIGHLY VIABLE** — 1-2 days, $0, genuinely useful.
**Approach B (BLE Beacon) is a DEMO FEATURE** — cool for presentations, near-zero real-world utility at current scale.
**Approach C (BLE Mesh Chat) is NOT VIABLE** for solo dev.

### PoC Test Plan

```
Experiment A: "Can FloodSafe compose an emergency SMS when offline?"
Time estimate: 2-3 hours
Prerequisites: Capacitor set up (from Capability 1 PoC)

Steps:
1. npm install @byteowls/capacitor-sms (or use Capacitor App plugin with SMS intent)
2. In useSOSQueue.ts: add SMS compose fallback when navigator.onLine === false
3. Format message:
   "SOS FLOOD EMERGENCY from [name] at [address].
    Location: [lat],[lng]
    Time: [timestamp]
    Open: https://floodsafe.app/sos?lat=X&lng=Y"
4. Get safety circle phone numbers from cached query data
5. Open native SMS compose with pre-filled recipients + message
6. Test: Airplane mode → tap SOS → verify SMS compose opens

Verify:
- [ ] SMS compose screen opens with correct recipients
- [ ] Message body includes GPS coordinates
- [ ] Message body includes deep link URL
- [ ] User can manually tap Send (we cannot auto-send)
- [ ] SOS ALSO queued in IndexedDB for API delivery when online
- [ ] If no safety circle contacts, show "Add emergency contacts first" prompt
- [ ] Works on Android 10, 12, 14 (test permission variations)

Kill criteria:
- @byteowls/capacitor-sms plugin crashes on target Android version → try Intent approach
- SMS compose doesn't accept multiple recipients → send one-by-one (slower but works)

NOT testing:
- BLE beacon (only test after Approaches A passes AND user base >10,000)
- Auto-send SMS (Play Store will reject, don't even try)
```

---

## Cross-Cutting Concerns

### Maintenance Burden

Each capability adds a dependency chain:

| Capability | New Dependencies | Update Risk |
|-----------|-----------------|-------------|
| Capacitor | @capacitor/core, Android SDK, Gradle | Android SDK updates break builds ~2x/year |
| FCM Push | firebase-admin (Python), firebase/messaging (JS) | Firebase SDK major versions ~1x/year |
| WhatsApp Sync | Meta Graph API v21+ | Meta deprecates API versions every 2 years |
| BLE | @capacitor-community/bluetooth-le | Niche plugin, slow updates, breaking changes |

For a solo dev, adding ALL four simultaneously means 4 new surfaces to maintain. **Recommendation: add one at a time, stabilize, then add the next.**

### Offline Data Strategy

If the app works offline, how much data should be cached locally?

```
Data type              Size estimate    Cache strategy
─────────────────────  ──────────────   ──────────────────────
Hotspots (per city)    ~50-200 KB       StaleWhileRevalidate (already done)
Saved routes           ~5-10 KB         NetworkFirst (already done)
Safety circle contacts ~2-5 KB          NetworkFirst (need to add)
Last FHI scores        ~10-20 KB        NetworkFirst (already cached 24h)
Map tiles (PMTiles)    ~2-50 MB         CacheFirst (already done)
Reports (nearby)       ~50-100 KB       NOT cached, would need new strategy
User profile           ~1 KB            NetworkFirst (already done)

Total offline footprint: ~3-55 MB (mostly map tiles)
IndexedDB soft limit:   ~50 MB (browser), unlimited (Capacitor filesystem)
```

Current caching is adequate for offline viewing. The main gap is **safety circle contacts** — the SMS compose feature needs phone numbers when offline. These should be cached in IndexedDB on every sync.

### Security Considerations

1. **FCM token storage**: Storing device tokens in the DB is standard. Tokens are not secrets (they can only receive push, not send). But should be cleaned up when user logs out.
2. **BLE spoofing**: If BLE beacon is implemented, anyone within range can forge an SOS. Would need HMAC signing in the payload, which requires pre-shared keys between devices. Complex.
3. **SMS content**: SOS messages include GPS coordinates. This is intentional for emergencies but is PII. Users should be informed during onboarding that SOS shares their location via SMS.
4. **WhatsApp webhook validation**: Already uses HMAC-SHA256 (good). But the webhook URL is public. Rate limiting (10 msg/60s) exists but could be tighter for production.

### WebMCP as Testing Infrastructure

FloodSafe already has a **13-entity WebMCP bridge** in production (`WebMCPProvider.tsx`). This is a powerful testing tool for all capabilities because it provides programmatic access to app state without manual UI interaction.

**Testing strategy across all phases:**

| Phase | WebMCP Usage |
|-------|-------------|
| Capacitor PoC | `context_app_state` → verify auth, city, profile load in WebView. `search_locations` → verify CORS. `floodsafe://hotspots/{city}` → verify API pipeline. |
| FCM Push | `get_query_cache(["user-profile"])` → verify FCM token stored. `context_app_state` → check notification permission state. |
| Route Monitor | `floodsafe://hotspots/{city}` → verify FHI data available for route checks. `get_query_cache(["saved-routes"])` → verify saved routes accessible. |
| WhatsApp Sync | `floodsafe://reports` → verify WA-created reports appear. `context_app_state` → check user linking state. |
| Offline SOS | `context_location` → verify GPS available for SMS message. `get_query_cache(["my-circles"])` → verify safety circle contacts cached for offline SMS compose. |

**Key advantage**: WebMCP entities respond with JSON, making assertions programmatic. No need to visually inspect the UI for most data-flow validations. Use Chrome DevTools MCP (`take_snapshot`, `evaluate_script`) for UI-level verification.

**Limitation**: WebMCP only works when the app is loaded in a browser with the WebMCP client connected. Won't work for pure background/service-worker testing.

### Offline Conflict Resolution

If user creates reports or SOSes offline and they sync when back online:

- **Duplicate SOS**: User taps SOS 5 times while offline → 5 queued. The existing `useSOSQueue` has `MAX_RETRIES` but no dedup. Could send 5 identical SOS alerts to safety circles.
- **Fix**: Deduplicate by (user_id, lat/lng within 100m, timestamp within 10 min) before sending.
- **Stale reports**: User creates report offline about flooding. Comes online 6 hours later. The report has a stale timestamp. Should it post with original timestamp or current time?
- **Recommendation**: Post with original timestamp but flag as `submitted_offline: true` with `offline_duration_minutes` metadata. Let the UI show "submitted 6h ago (was offline)."

---

## Final Verdict & Build Order

### Viability Summary

| Capability | Viability | Cost | Honest Effort | Impact |
|-----------|-----------|------|---------------|--------|
| **FCM Push Notifications** | **HIGH** | $0 | 2-3 days | **HIGHEST** |
| **Capacitor Android Wrapper** | **HIGH** | $25 one-time | 5-7 days (with auth fixes) | **HIGH** |
| **Store-and-Forward SMS** | **HIGH** | $0 | 1-2 days | **HIGH** |
| **WhatsApp Inbound Sync** | **MODERATE** | $0 | 2-3 days | **MODERATE** |
| **WhatsApp Outbound Sync** | **LOW** | INR 0-325/mo | 1-2 weeks + Meta approval | **MODERATE** |
| **BLE Beacon** | **LOW** | $0 | 1-2 weeks | **LOW** (needs 60K users) |
| **BLE Mesh Chat** | **NOT VIABLE** | $0 | 2-3 months | **THEORETICAL** |

### Recommended Build Order

```
Phase 1 — Foundation (Week 1):
  1. Capacitor Android PoC (5-7 hrs)
     → Validates the native wrapper before building on it
  2. FCM Push PoC (3-4 hrs)
     → Validates push delivery end-to-end
  If both pass: commit to native path

Phase 2 — Core Value (Week 2):
  3. Route-based push monitoring (2 days)
     → Cron endpoint + spatial route check + cooldown logic
  4. SMS compose for offline SOS (1 day)
     → Capacitor SMS plugin + safety circle contact caching

Phase 3 — WhatsApp Inbound (Week 3):
  5. Phone → User linking (1 day)
     → whatsapp_phone column or linking table
  6. WA report → DB Report creation (1-2 days)
     → Modify photo_handler + webhook to create Report records

Phase 4 — Deferred (only if Meta approves):
  7. Submit Meta Business Verification (start during Phase 1)
  8. Submit message templates (start during Phase 2)
  9. Build outbound sync IF approved

Phase NEVER (unless user base > 50,000):
  10. BLE Beacon
  11. BLE Mesh
```

### Decision Gates

```
After Phase 1:
  Q: Did Capacitor + FCM PoCs pass?
  → YES: Continue to Phase 2
  → NO (Capacitor failed): Pivot to PWA-only push (Web Push API, skip native)
  → NO (FCM failed): Debug Firebase config, likely fixable

After Phase 3:
  Q: Has Meta Business Verification been approved?
  → YES: Proceed to Phase 4
  → NO (pending): Wait. Do not build outbound sync on hope.
  → NO (rejected): Accept inbound-only sync as final state

After 50,000 active users:
  Q: Is BLE beacon worth the development cost now?
  → Probably still no. But at least the critical mass math works.
```

---

## Appendix: Existing Infrastructure Audit

### Files That Need Changes (by capability)

**Capacitor Wrapper:**
- NEW: `capacitor.config.ts`
- NEW: `android/` directory (auto-generated)
- MODIFY: `apps/backend/src/core/config.py` (add Capacitor CORS origin)
- MODIFY: `apps/frontend/src/lib/firebase.ts` (redirect auth flow for WebView)
- MODIFY: `apps/frontend/src/contexts/AuthContext.tsx` (handle redirect result)

**FCM Push:**
- MODIFY: `apps/frontend/src/lib/firebase.ts` (add getMessaging, getToken)
- NEW: `apps/frontend/public/firebase-messaging-sw.js`
- MODIFY: `apps/frontend/vite.config.ts` (exclude firebase-messaging-sw from Workbox)
- NEW: `apps/backend/src/domain/services/push_notification_service.py`
- NEW: `apps/backend/src/api/cron.py` (route monitoring endpoint)
- MODIFY: `apps/backend/src/infrastructure/models.py` (fcm_token on User, last_notified per route)
- MODIFY: `apps/backend/requirements.txt` (firebase-admin)

**SMS Compose:**
- MODIFY: `apps/frontend/src/hooks/useSOSQueue.ts` (add SMS compose fallback)
- NEW: Capacitor SMS plugin integration
- MODIFY: SOS UI to show "SMS will open" when offline

**WhatsApp Inbound Sync:**
- MODIFY: `apps/backend/src/domain/services/whatsapp/photo_handler.py` (create Report)
- MODIFY: `apps/backend/src/infrastructure/models.py` (whatsapp_phone on User, source on Report)
- MODIFY: `apps/backend/src/domain/services/whatsapp/command_handlers.py` (LINK persists mapping)
- NEW: Migration script for new columns

### Current Phone Number State in DB

```
User.phone (line 47):             Nullable, may or may not match WhatsApp
WhatsAppSession.phone (line 430): PK, E.164 format, NO FK to User
CircleMember.phone (line 494):    Nullable, E.164 format, NO FK to User
SOSMessage.recipients_json:       Raw JSON array of {phone, name, ...}

Gap: No reliable phone → user_id mapping for WhatsApp senders.
Fix: Add User.whatsapp_phone column OR create phone_links table.
```

---

## Appendix: Dependency Review Corrections

The following errors were caught during critical dependency review and corrected in this document:

| # | Severity | Original Claim | Correction |
|---|----------|---------------|------------|
| 1 | **HIGH** | `@capacitor-community/sms` plugin | **Does not exist.** Correct package: `@byteowls/capacitor-sms` |
| 2 | **HIGH** | Capacitor origin: `capacitor://localhost` (Android), `ionic://localhost` (iOS) | **Reversed.** Android = `http://localhost`, iOS = `capacitor://localhost`. `ionic://` is legacy Cordova. |
| 3 | **HIGH** | WhatsApp: "first 1,000 service conversations free/month, INR 0.35/conv" | **Outdated (pre-Nov 2024).** Since July 2025: per-message pricing. Service replies within 24hr = FREE unlimited. Utility templates = INR 0.13/msg. |
| 4 | **MEDIUM** | "Vercel free tier does not support cron" | **Wrong.** Vercel Hobby supports cron (2 jobs, once/day). Still insufficient for 15-min checks, but the stated reason was incorrect. |
| 5 | **MEDIUM** | "Service workers since Android 6.0+" | **Incorrect.** `ServiceWorkerController` added in Android 7.0 (API 24). Older devices may work with updated WebView from Play Store. |
| 6 | **MEDIUM** | iOS WKWebView has "partial/unstable" SW support | **Understated.** Service workers effectively DO NOT work in Capacitor iOS due to `capacitor://` scheme conflict. Open issues #4122, #7069. |
| 7 | **HIGH** | Google Auth not mentioned as domain-restricted | **Missing.** Google OAuth only allows login from Koyeb + Vercel production URLs. Capacitor `http://localhost` must be added to authorized domains. All PoC testing must use production backend. |
| 8 | **LOW** | Android 12 BLE permissions: only SCAN + ADVERTISE mentioned | **Incomplete.** BLUETOOTH_CONNECT also exists (but not needed for beacon use case). Positive: ACCESS_FINE_LOCATION no longer required for BLE on Android 12+. |
