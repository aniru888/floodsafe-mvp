# FloodSafe Feature Registry

> Complete documentation of all implemented features, domain contexts, and project roadmap.
> For development rules, tools, and workflows, see [CLAUDE.md](./CLAUDE.md).

---

## Domain Contexts

### @reports (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/reports.py - CRUD, photo upload, EXIF extraction, voting
  Frontend:
  - apps/frontend/src/components/screens/ReportScreen.tsx - 4-step submission wizard
  - apps/frontend/src/components/ReportCard.tsx - Card with voting/comments

patterns: FormData upload, EXIF GPS extraction, PostGIS POINT, verification scoring
```

### @community (COMPLETE)
```yaml
files:
  - apps/backend/src/api/comments.py - Comments API (rate-limited: 5/min/user)
  - apps/backend/src/api/reports.py - Voting endpoints
  - apps/frontend/src/components/ReportCard.tsx - Card with voting/comments
  - apps/frontend/src/components/screens/AlertsScreen.tsx - Community filter tab
  - apps/frontend/src/components/screens/CommunityFeedScreen.tsx - Dedicated feed

key_points:
  - Community tab is a FILTER in AlertsScreen (also has dedicated CommunityFeedScreen)
  - Vote deduplication via ReportVote table (unique user_id + report_id)
  - Rate limiting: max 5 comments/minute/user

migration: python -m apps.backend.src.scripts.migrate_add_community_features
```

### @alerts (COMPLETE)
```yaml
files:
  - apps/backend/src/api/alerts.py - Alert CRUD
  - apps/backend/src/domain/services/alert_service.py - Watch area alerts
  - apps/backend/src/api/watch_areas.py - Watch area management

patterns: Watch areas, PostGIS ST_DWithin, notification badges
```

### @auth (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/auth.py - /register/email, /login/email, /verify-email
  - apps/backend/src/api/otp.py - OTP send/verify endpoints
  - apps/backend/src/domain/services/auth_service.py - register_email_user, authenticate_email_user
  - apps/backend/src/domain/services/otp_service.py - OTP generation and verification
  - apps/backend/src/domain/services/email_service.py - SendGrid email delivery
  - apps/backend/src/domain/services/security.py - hash_password, verify_password (bcrypt)
  - apps/backend/src/infrastructure/models.py - password_hash, EmailVerificationToken, RefreshToken

  Frontend:
  - apps/frontend/src/contexts/AuthContext.tsx - registerWithEmail, loginWithEmail
  - apps/frontend/src/components/screens/LoginScreen.tsx - Email/Google/Phone tabs
  - apps/frontend/src/components/screens/EmailVerifiedScreen.tsx - Verification confirmation

auth_methods:
  - Email/Password: bcrypt hashing, 8+ char minimum, email verification via SendGrid
  - Google OAuth: Firebase integration
  - Phone OTP: Firebase SMS

models: User (password_hash), RefreshToken (rotation), EmailVerificationToken
migration: python -m apps.backend.src.scripts.migrate_add_password_auth
```

### @onboarding (COMPLETE)
```yaml
files:
  - apps/backend/src/scripts/migrate_add_onboarding_fields.py
  - apps/backend/src/api/daily_routes.py
  - apps/frontend/src/components/screens/OnboardingScreen.tsx
patterns: 5-step wizard, resumable flow (onboarding_step field), city preference
flow: Login → profile_complete check → OnboardingScreen → HomeScreen
migration: python -m apps.backend.src.scripts.migrate_add_onboarding_fields
```

### @historical-floods (COMPLETE)
```yaml
files:
  - apps/frontend/src/components/HistoricalFloodsPanel.tsx
  - apps/frontend/src/lib/api/historical-floods.ts
  - apps/backend/src/api/historical_floods.py
  - apps/ml-service/data/delhi_historical_floods.json
data_source: IFI-Impacts (IIT-Delhi Hydrosense Lab, Zenodo)
coverage: Delhi NCR 1969-2023 (45 events)
features:
  - Decade-grouped timeline view
  - Severity color coding (minor/moderate/severe)
  - Stats: events, fatalities, severe count
  - City-specific: Delhi shows data, Bangalore shows "Coming Soon"
patterns:
  - GeoJSON FeatureCollection response
  - useHistoricalFloods hook (24hr cache)
  - Panel overlay with click-outside-to-close
```

### @hotspots (COMPLETE)
```yaml
files:
  - apps/ml-service/src/api/hotspots.py - 90 Delhi hotspots (62 MCD + 28 OSM)
  - apps/ml-service/src/data/fhi_calculator.py - FHI calculation
  - apps/ml-service/data/delhi_waterlogging_hotspots.json - Location data
  - apps/backend/src/api/hotspots.py - API proxy with caching

FHI_formula: |
  FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T
  CUSTOM HEURISTIC - weights empirically tuned, not from research
  Rain-gate: If <5mm/3d, FHI capped at 0.15 (prevents false alarms)

color_priority: FHI first (live weather), fallback to ML risk (static)
verification: python apps/backend/verify_hotspot_spatial.py
```

### @ml-predictions (PARTIAL)
```yaml
files:
  - apps/ml-service/src/models/xgboost_hotspot.py - XGBoost model (TRAINED)
  - apps/ml-service/src/features/hotspot_features.py - 18-dim features
  - apps/ml-service/src/features/extractor.py - 37-dim features
  - apps/ml-service/models/xgboost_hotspot/xgboost_model.json - Trained weights
  - apps/backend/src/api/predictions.py - ML service proxy (grid + point)
  - apps/backend/src/api/ml.py - Embedded TFLite MobileNet classifier

dual_mode_architecture:
  Embedded (always available):
    - ml.py uses TFLite MobileNet for photo flood classification
    - POST /api/ml/classify-flood (224x224, threshold 0.3)
  External (optional ML service):
    - predictions.py proxies to ML service when ML_SERVICE_ENABLED=true
    - GET /api/predictions/grid, /api/predictions/point
    - 1-hour cache TTL

model_status:
  XGBoost (90 hotspots):
    - Known Hotspots: WORKS (AUC 0.98, weather-sensitive)
    - New Locations: LIMITED (AUC 0.70-0.82, needs 0.85)
    - USE FOR: Dynamic risk at 90 known Delhi hotspots
    - DO NOT USE FOR: Discovering new locations
  Ensemble (LSTM/GNN/LightGBM): BROKEN - never trained, returns fallback 0.1

features:
  Hotspot (18-dim): elevation, slope, TPI, TRI, TWI, SPI, rainfall, land cover, SAR
  General (37-dim): Dynamic World, WorldCover, Sentinel-2, Terrain, Precip, Temporal, GloFAS

next: Collect 300+ diverse locations for better generalization
```

### @routing (COMPLETE)
```yaml
files:
  - apps/backend/src/domain/services/routing_service.py - Safe route calculation
  - apps/backend/src/domain/services/hotspot_routing.py - Hotspot avoidance
  - apps/backend/src/api/routes_api.py - Route comparison endpoints
  - apps/frontend/src/components/NavigationPanel.tsx - Route planning UI
  - apps/frontend/src/components/MapPicker.tsx - Pin-on-map location picker (reused)

location_input: |
  THREE WAYS to set origin/destination:
  1. SmartSearchBar text search (typo-tolerant via Photon + proximity sorting)
  2. "Pin on Map" button → MapPicker modal with draggable marker + reverse geocoding
  3. "Use GPS" button (origin only) → sets to current device location
  MapPicker is reused from ReportScreen — same component, zero duplication.

strategy: |
  HARD AVOID (300m threshold):
  - LOW/MODERATE FHI: Allow (warning only)
  - HIGH/EXTREME FHI: Must reroute around

flow: POST /routes/compare → analyze hotspots → normal vs FloodSafe comparison
```

### @gamification (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/gamification.py - Unified gamification endpoints
  - apps/backend/src/api/badges.py - Badge catalog and user badges
  - apps/backend/src/api/reputation.py - Reputation + privacy settings
  - apps/backend/src/api/leaderboards.py - Leaderboard with privacy controls
  - apps/backend/src/domain/services/reputation_service.py - Points, badges, streaks
  - apps/backend/src/domain/services/leaderboard_service.py - Leaderboard logic

models:
  - Badge: key, name, description, icon, category, requirement_type/value, points_reward
  - UserBadge: user_id, badge_id, earned_at
  - ReputationHistory: user_id, action, points_change, new_total, reason

points_system:
  report_submitted: 5
  report_verified_base: 10
  report_rejected: -5
  report_upvoted: 1
  streak_7: 25
  streak_30: 100

badge_categories: achievement, milestone, contribution, special
privacy_controls: leaderboard_visible, profile_public, display_name (anonymous option)

endpoints:
  - GET /api/gamification/me/badges - User's earned/in-progress badges
  - GET /api/gamification/me/reputation - Reputation summary
  - GET /api/gamification/me/reputation/history - Points history (paginated)
  - GET /api/badges/ - Badge catalog
  - GET /api/reputation/{user_id} - Public reputation
  - PATCH /api/reputation/{user_id}/privacy - Privacy settings
  - GET /api/leaderboards/ - Leaderboard (global/weekly/monthly)
  - GET /api/leaderboards/top - Top users widget
```

### @external-alerts (COMPLETE)
```yaml
files:
  - apps/backend/src/api/external_alerts.py - CRUD endpoints
  - apps/backend/src/domain/services/external_alerts/ - Fetcher subsystem
    - aggregator.py - Multi-source aggregation
    - base_fetcher.py - Base class for fetchers
    - imd_fetcher.py - India Meteorological Department
    - cwc_scraper.py - Central Water Commission
    - rss_fetcher.py - RSS news feeds
    - twitter_fetcher.py - Twitter/X monitoring
    - gdacs_fetcher.py - Global Disaster Alert System
    - gdelt_fetcher.py - GDELT event data
    - relevance_scorer.py - Alert relevance scoring
    - scheduler.py - Scheduled fetching

model: ExternalAlert (source, source_id, source_name, city, title, message, severity, url, lat/lng, raw_data, expires_at)
severity_levels: low, moderate, high, severe
cities: delhi, bangalore
deduplication: Unique constraint on source_id

endpoints:
  - GET /api/external-alerts - Alerts by city (filter: source, severity)
  - GET /api/external-alerts/sources - Available sources with counts
  - POST /api/external-alerts/refresh - Manual refresh for city
  - GET /api/external-alerts/stats - Stats by source/severity
  - DELETE /api/external-alerts/cleanup - Remove expired
```

### @rainfall (COMPLETE)
```yaml
files:
  - apps/backend/src/api/rainfall.py - All rainfall/FHI endpoints (~1600 lines)

data_source: Open-Meteo API (free, no auth required)

endpoints:
  - GET /api/rainfall/forecast - 3-day forecast for point
  - GET /api/rainfall/forecast/grid - Grid of forecasts (GeoJSON)
  - GET /api/rainfall/fhi - Flood Hazard Index (0-1)
  - GET /api/rainfall/health - Service health
  - GET /api/rainfall/validate/historical/{event_id} - Validate FHI against known events
  - GET /api/rainfall/validate/all - Validate all historical events
  - GET /api/rainfall/validate/summary - Accuracy summary

FHI_levels:
  low: 0.0-0.2 (Green)
  moderate: 0.2-0.4 (Yellow)
  high: 0.4-0.7 (Orange)
  extreme: 0.7-1.0 (Red)

calibration: Urban Delhi 1.5x-2.25x correction, 20 historical events tested
cache: 1-hour TTL, in-memory
```

### @floodhub (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/floodhub.py - FloodHub proxy endpoints
  - apps/backend/src/domain/services/floodhub_service.py - Google FloodHub integration

  Frontend:
  - apps/frontend/src/components/floodhub/FloodHubTab.tsx - Main tab
  - apps/frontend/src/components/floodhub/FloodHubHeader.tsx
  - apps/frontend/src/components/floodhub/FloodHubAlertsList.tsx
  - apps/frontend/src/components/floodhub/ForecastChart.tsx
  - apps/frontend/src/components/floodhub/FloodHubFooter.tsx

coverage: Delhi's Yamuna River (Old Railway Bridge, ITO Junction, Okhla Barrage)
severity_levels: normal, watch, warning, emergency
city_guard: Returns enabled=false for non-Delhi cities

endpoints:
  - GET /api/floodhub/status?city=DEL - Overall status with severity
  - GET /api/floodhub/gauges - All Delhi Yamuna gauges
  - GET /api/floodhub/forecast/{gauge_id} - 7-day forecast

no_silent_fallbacks: All API errors surfaced as HTTPException 502
```

### @saved-routes (COMPLETE)
```yaml
files:
  - apps/backend/src/api/saved_routes.py - Full CRUD

model: SavedRoute (user_id, name, origin_lat/lng/name, destination_lat/lng/name, transport_mode, use_count)
transport_modes: driving, walking, cycling

endpoints:
  - GET /api/saved-routes/user/{user_id} - All routes (sorted by use_count)
  - POST /api/saved-routes/ - Create
  - PUT /api/saved-routes/{route_id} - Update
  - DELETE /api/saved-routes/{route_id} - Delete
  - POST /api/saved-routes/{route_id}/increment - Increment use count
```

### @smart-search (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/search.py - Search endpoints (default limit: 30, max: 100)
  - apps/backend/src/domain/services/search_service.py - Dual-source geocoding + search logic
  - apps/backend/src/domain/services/location_aliases.py - Alias expansion (281+ aliases)

  Frontend:
  - apps/frontend/src/components/SmartSearchBar.tsx - Search UI with autocomplete, show-more sections

geocoding: |
  DUAL-SOURCE ARCHITECTURE (Photon primary, Nominatim fallback):
  - Photon (photon.komoot.io): Typo-tolerant, location-biased, typeahead-designed
  - Nominatim (openstreetmap.org): Authoritative fallback, alias-expanded queries
  - If Photon returns < 3 results → also queries Nominatim as supplement
  - Results merged, deduplicated by coordinates (0.0005° ~55m tolerance)
  - Sorted by haversine distance to user (proximity-first) when location available
  - Soft city bounds: retries without bounded if bounded returns < 5 results
  - Geo-bias default: when no user lat/lng provided, defaults to city center (Delhi: 28.6315, 77.2167)
    so cloud servers (e.g. Koyeb Frankfurt) return Indian results instead of European ones
  - 30-minute in-memory cache for both sources
  - User-Agent header: "FloodSafe-MVP/1.0" sent with Photon requests (good API citizenship)

typo_tolerance: |
  Photon uses OpenSearch fuzzy matching — handles misspellings automatically:
  - "conuaght plce" → Connaught Place
  - "banglaore" → Bangalore locations
  - "nehru palce" → Nehru Place
  - Limitation: extreme abbreviations (e.g. "karol bgh" for "Karol Bagh") may not match —
    Photon needs enough character overlap for fuzzy matching to work

intent_detection:
  - Location keywords (road, sector, colony) → prioritize locations
  - Flood keywords (water, flooding, impassable) → prioritize reports
  - @username pattern → search users
  - Prefixes: @location:, @report:, @user:

result_limits: |
  Per-category: locations (30), reports (30), users (15)
  Frontend shows 8 locations, 8 reports, 5 users initially
  "Show all X results" expandable button per section
  Result count badges in section headers

location_aliases: "cp" → Connaught Place, "hsr" → HSR Layout, "minto" → Minto Bridge, etc.
spatial_search: PostGIS ST_DWithin for radius filtering

endpoints:
  - GET /api/search/ - Unified search (all types, default limit=30, max=100)
  - GET /api/search/locations/ - Location search (default limit=30, max=50)
  - GET /api/search/reports/ - Report text search (default limit=30, max=100)
  - GET /api/search/users/ - User search (default limit=15, max=50)
  - GET /api/search/suggestions/ - Trending + popular areas
```

### @live-navigation (COMPLETE)
```yaml
files:
  - apps/frontend/src/components/LiveNavigationPanel.tsx - Live nav overlay
  - apps/frontend/src/contexts/NavigationContext.tsx - Route state management
  - apps/frontend/src/contexts/VoiceGuidanceContext.tsx - TTS voice instructions
  - apps/frontend/src/contexts/LocationTrackingContext.tsx - GPS tracking

features:
  - Turn-by-turn instructions with distance to next turn
  - Real-time hotspot warnings along route (FHI color dots)
  - Auto-reroute on deviation or new hotspot detection
  - Voice guidance via Web Speech API (TTS)
  - Live ETA and distance remaining
  - Offline location buffering

ui: Fixed bottom panel with instruction, street name, ETA, hotspot warnings
```

### @pwa (COMPLETE)
```yaml
files:
  - apps/frontend/vite.config.ts - Vite PWA plugin config
  - apps/frontend/src/components/InstallBanner.tsx - Install prompt UI
  - apps/frontend/src/components/OfflineIndicator.tsx - Offline status
  - apps/frontend/src/contexts/InstallPromptContext.tsx - Install prompt state

manifest:
  name: "FloodSafe - Real-time Flood Monitoring"
  display: standalone, portrait
  theme_color: "#3B82F6"

service_worker (Workbox):
  CacheFirst: Google Fonts, MapLibre CSS, PMTiles, images (30-365 days)
  NetworkFirst: API calls (10s timeout, 24h fallback) — excludes /api/ml/classify
  NetworkOnly: /api/ml/classify (can take 30s+ on mobile)
  StaleWhileRevalidate: GeoJSON files (24h)

icons: 192x192, 512x512 (regular + maskable)
auto_update: registerType 'autoUpdate'
max_file_size: 3MB (bundle ~2.2MB)
dev_mode: PWA disabled to avoid caching issues
```

### @esp32-firmware (COMPLETE)
```yaml
files:
  - apps/esp32-firmware/FloodSafe_IoT/FloodSafe_IoT.ino - Main firmware
  - apps/esp32-firmware/FloodSafe_IoT/config.h - User config
  - apps/esp32-firmware/README.md - Documentation

hardware:
  - Microcontroller: Seeed XIAO ESP32S3
  - Water Sensor: Grove Water Level (10cm, I2C 0x77/0x78)
  - Distance Sensor: VL53L0X ToF (I2C 0x29)
  - Display: Grove OLED 128x64 SSD1306 (I2C 0x3C)

dual_sensor_fusion:
  Grove strips: 0-20 segments (capacitive)
  VL53L0X: Distance to water surface (mm precision)

alert_logic:
  SAFE: 0 strips AND <10% distance
  WARNING: 1+ strips OR ≥10% distance
  FLOOD: 10+ strips OR ≥50% distance

features:
  - Offline buffering: 100-reading circular buffer (~50 min at 30s intervals)
  - OLED display: Real-time water level, status, WiFi, pending uploads
  - Auto-upload: FIFO upload when WiFi restored

config:
  READING_INTERVAL_MS: 5000
  UPLOAD_INTERVAL_MS: 30000
  BUFFER_SIZE: 100

backend_integration: POST /api/iot-ingestion/ingest
```

### @iot-ingestion (COMPLETE)
```yaml
files:
  Ingestion Service:
  - apps/iot-ingestion/src/main.py - High-throughput ingestion endpoint

  Sensor Management (Main Backend):
  - apps/backend/src/api/sensors.py - Sensor CRUD + API key auth
  - apps/backend/src/infrastructure/models.py - Sensor model with api_key_hash

endpoints:
  Ingestion (apps/iot-ingestion, port 8001):
    POST /ingest - Accept sensor readings (raw SQL, no ORM)

  Sensor Management (apps/backend):
    POST /api/sensors/ - Create sensor
    GET /api/sensors/ - List sensors
    POST /api/sensors/{id}/readings - Record reading (with API key auth)
    GET /api/sensors/{id}/readings - Get history
    POST /api/sensors/{id}/generate-key - Generate API key (SHA256, shown once)
    PATCH /api/sensors/{id}/name - Update name

sensor_model: user_id, name, hardware_type, firmware_version, api_key_hash, last_ping, location (PostGIS)
auth: X-API-Key header, SHA256 hash comparison
architecture: Ingestion service intentionally isolated for performance (raw SQL)
```

### @whatsapp (COMPLETE)
```yaml
files:
  - apps/backend/src/api/webhook.py - WhatsApp webhook handler + health check
  - apps/backend/src/domain/services/notification_service.py - TwilioNotificationService
  - apps/backend/src/domain/services/whatsapp/
    - button_sender.py - Quick Reply buttons (9 types)
    - command_handlers.py - RISK, WARNINGS, MY AREAS commands
    - message_templates.py - Message templating
    - photo_handler.py - Photo ingestion + ML classification

inbound: Location pin → SOS, photo → ML classify, text commands, Quick Reply buttons
outbound: Alerts to watch areas via Twilio
commands: Send location (SOS), LINK, STATUS, START/STOP, RISK, WARNINGS, MY AREAS

quick_reply_buttons:
  - report_flood, check_risk, view_alerts, add_photo
  - submit_anyway, cancel, menu, report_another, check_my_location

session: WhatsAppSession model, 30-min timeout
rate_limiting: 10 messages/minute per phone
multi_language: English + Hindi templates

setup: |
  1. Twilio sandbox creds → .env (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
  2. TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
  3. ngrok http 8000 → webhook URL in Twilio Console
  4. Migration: python -m apps.backend.src.scripts.migrate_add_whatsapp_sessions
```

### @profiles (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/infrastructure/models.py - User model with roles, gamification fields
  - apps/backend/src/api/deps.py - Admin/role checks
  - apps/backend/src/api/users.py - User management
  Frontend:
  - apps/frontend/src/components/screens/ProfileScreen.tsx - Profile settings
  - apps/frontend/src/contexts/UserContext.tsx - User state

roles:
  - user: Default, can submit reports
  - admin: Can access admin endpoints
  - verified_reporter: verified_reporter_since timestamp on User model
  - moderator: moderator_since timestamp on User model

audit: RoleHistory model (user_id, old_role, new_role, changed_by, reason)
gamification_link: User model has points, level, badges, reputation_score, streak_days
privacy: leaderboard_visible, profile_public, display_name
```

### @photo-verification (GPS + ML COMPLETE)
```yaml
files:
  - apps/backend/src/api/reports.py - EXIF GPS extraction
  - apps/backend/src/api/ml.py - Embedded TFLite MobileNet classifier
  - apps/ml-service/src/models/mobilenet_flood_classifier.py - MobileNet
  - apps/ml-service/models/sohail_flood_model.h5 - Trained weights

gps: Extract EXIF → compare to location → set location_verified if >100m
ml: MobileNet (224x224) → flood/no_flood, threshold 0.3 (safety-first)
storage: MOCKED - uses mock URLs, no real S3/Blob storage
missing: Depth estimation, fake detection, real storage
```

### @e2e-testing (COMPLETE)
```yaml
files:
  - apps/frontend/scripts/e2e-full-test.ts - Playwright E2E test suite

test_coverage:
  - Account creation via API + database verification
  - Login flow via UI (email/password)
  - Onboarding wizard (5 steps)
  - HomeScreen features (risk banner, cards, map)
  - Report submission (4-step wizard)
  - Profile and Watch Areas
  - Flood Atlas navigation

run: cd apps/frontend && npx tsx scripts/e2e-full-test.ts
output: 21 screenshots (e2e-1-*.png to e2e-21-*.png)
```

### @edge-ai (PLANNED)
```yaml
concept: ANN model running on IoT devices (ESP32/Raspberry Pi)
goal: Local flood prediction without cloud dependency
current: ESP32 firmware does threshold-based alerts (no ML yet)
next: Design lightweight neural network for edge inference
```

### @mobile (NOT STARTED)
```yaml
current: PWA covers install + offline. Web-responsive via Tailwind CSS.
missing: Capacitor config for native Android/iOS builds
next: Add Capacitor wrapper if native features needed beyond PWA
```

---

## Frontend Screens

| Screen | File | Status |
|--------|------|--------|
| Home | `HomeScreen.tsx` | ✅ |
| Login | `LoginScreen.tsx` | ✅ |
| Onboarding | `OnboardingScreen.tsx` | ✅ |
| Report | `ReportScreen.tsx` | ✅ |
| Alerts | `AlertsScreen.tsx` | ✅ |
| Community Feed | `CommunityFeedScreen.tsx` | ✅ |
| Flood Atlas | `FloodAtlasScreen.tsx` | ✅ |
| Profile | `ProfileScreen.tsx` | ✅ |
| Email Verified | `EmailVerifiedScreen.tsx` | ✅ |
| Privacy Policy | `PrivacyPolicyScreen.tsx` | ✅ |
| Terms | `TermsScreen.tsx` | ✅ |
| Placeholders | `Placeholders.tsx` | ✅ |

## Frontend Contexts (7)

| Context | File | Purpose |
|---------|------|---------|
| Auth | `AuthContext.tsx` | Email/Google/Phone auth state |
| City | `CityContext.tsx` | City preference/selection |
| User | `UserContext.tsx` | User profile/settings |
| Navigation | `NavigationContext.tsx` | Route + screen navigation state |
| Location Tracking | `LocationTrackingContext.tsx` | Real-time GPS |
| Voice Guidance | `VoiceGuidanceContext.tsx` | TTS for navigation |
| Install Prompt | `InstallPromptContext.tsx` | PWA install state |

## Backend API Files (25)

| File | Domain | Endpoints |
|------|--------|-----------|
| `auth.py` | @auth | register, login, verify-email |
| `otp.py` | @auth | send, verify OTP |
| `users.py` | @profiles | user CRUD |
| `reports.py` | @reports | report CRUD, voting, photo upload |
| `comments.py` | @community | comment CRUD |
| `alerts.py` | @alerts | alert CRUD |
| `watch_areas.py` | @alerts | watch area CRUD |
| `sensors.py` | @iot-ingestion | sensor CRUD, API keys |
| `hotspots.py` | @hotspots | hotspot proxy |
| `predictions.py` | @ml-predictions | ML service proxy |
| `ml.py` | @photo-verification | embedded TFLite classifier |
| `rainfall.py` | @rainfall | forecast + FHI |
| `historical_floods.py` | @historical-floods | flood history |
| `external_alerts.py` | @external-alerts | multi-source alerts |
| `floodhub.py` | @floodhub | FloodHub proxy |
| `search.py` | @smart-search | unified search |
| `routes_api.py` | @routing | route comparison |
| `saved_routes.py` | @saved-routes | route bookmarks |
| `daily_routes.py` | @onboarding | daily commute routes |
| `gamification.py` | @gamification | unified gamification |
| `badges.py` | @gamification | badge catalog |
| `reputation.py` | @gamification | reputation + privacy |
| `leaderboards.py` | @gamification | leaderboards |
| `webhook.py` | @whatsapp | WhatsApp webhook |
| `deps.py` | (shared) | auth dependencies, role checks |

## Database Models (16)

| Model | Table | Key Fields |
|-------|-------|------------|
| User | users | role, points, level, badges, reputation_score, streak_days, password_hash |
| Report | reports | location (PostGIS), severity, verification_score, upvotes/downvotes |
| ReportVote | report_votes | user_id + report_id (unique) |
| Comment | comments | report_id, user_id, content |
| Sensor | sensors | user_id, api_key_hash, hardware_type, location (PostGIS) |
| Reading | readings | sensor_id, water_level, water_segments, distance_mm |
| FloodZone | flood_zones | geometry (PostGIS Polygon) |
| WatchArea | watch_areas | user_id, center (PostGIS), radius_km |
| DailyRoute | daily_routes | user_id, origin/destination coordinates |
| Alert | alerts | watch_area_id, severity, message |
| SavedRoute | saved_routes | origin/destination with names, use_count |
| ExternalAlert | external_alerts | source, source_id (unique), severity, expires_at |
| Badge | badges | key, category, requirement_type, points_reward |
| UserBadge | user_badges | user_id, badge_id, earned_at |
| ReputationHistory | reputation_history | action, points_change, new_total |
| RoleHistory | role_history | old_role, new_role, changed_by |
| WhatsAppSession | whatsapp_sessions | phone, state, expires_at |
| RefreshToken | refresh_tokens | user_id, token_hash, expires_at |
| EmailVerificationToken | email_verification_tokens | user_id, token, expires_at |

---

## Roadmap

### Tier 1: Community Intelligence ✅ COMPLETE
Reports, map, alerts, onboarding, auth (Email/Google/Phone), E2E tests, community voting/comments

### Tier 2: ML/AI Foundation ✅ MOSTLY COMPLETE
- [x] XGBoost for 90 known hotspots (weather-sensitive, AUC 0.98)
- [x] FHI formula + rainfall forecasts (Open-Meteo)
- [x] Historical Floods Panel (45 Delhi events, 1969-2023)
- [x] Photo classification (embedded TFLite MobileNet)
- [x] External alert aggregation (IMD, CWC, RSS, Twitter, GDACS, GDELT)
- [x] FloodHub integration (Yamuna River gauges)
- [ ] Ensemble models (LSTM/GNN) - NOT TRAINED
- [ ] Better generalization (need 300+ diverse locations)

### Tier 3: Smart Sensors & Edge AI ✅ MOSTLY COMPLETE
- [x] IoT ingestion service (high-throughput, raw SQL)
- [x] Sensor registration + API key auth (SHA256)
- [x] ESP32 firmware (dual sensor, offline buffering, OLED)
- [ ] Edge ML (currently threshold-based, no neural network yet)

### Tier 4: Smart Features ✅ COMPLETE
- [x] Gamification (points, badges, reputation, leaderboards)
- [x] Safe routing with hotspot avoidance
- [x] Saved routes with use-count tracking
- [x] Smart search with intent detection + Nominatim geocoding
- [x] Live navigation with voice guidance + hotspot warnings

### Tier 5: Messaging ✅ COMPLETE
- [x] WhatsApp bot (SOS, commands, Quick Reply buttons, photo ML)
- [x] Multi-language (English + Hindi)
- [x] Twilio integration (inbound + outbound)

### Tier 6: Mobile & Offline ✅ COMPLETE (PWA)
- [x] PWA with Workbox service worker
- [x] Install banner + offline indicator
- [x] Cache strategies (CacheFirst, NetworkFirst, StaleWhileRevalidate)
- [ ] Capacitor native wrapper (if needed beyond PWA)

### Tier 7: Scale (PLANNED)
- [ ] Multi-language UI (Hindi, Kannada — WhatsApp Hindi done)
- [ ] GNN for flood propagation modeling
- [ ] City expansion beyond Delhi/Bangalore
- [ ] Real photo storage (S3/Blob, currently mocked)
- [ ] Water depth estimation from photos
