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
  - apps/frontend/src/contexts/OnboardingBotContext.tsx - Bot state for onboarding phase
  - apps/frontend/src/components/onboarding-bot/ - Inline card, companion, spotlight, tooltip
patterns: 5-step wizard, resumable flow (onboarding_step field), city preference
flow: Login → profile_complete check → OnboardingScreen (with bot companion) → HomeScreen
bot_integration: |
  OnboardingBot inline card accompanies each wizard step (see @onboarding-bot).
  tour_completed_at tracked on User model for replay from ProfileScreen.
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
  ML Service:
  - apps/ml-service/src/api/hotspots.py - HotspotsService (singleton per city)
  - apps/ml-service/src/data/fhi_calculator.py - FHI calculation (Delhi-tuned)
  - apps/ml-service/data/delhi_waterlogging_hotspots.json - 90 Delhi hotspots (62 MCD + 28 OSM)
  - apps/ml-service/data/yogyakarta_waterlogging_hotspots.json - 19 Yogyakarta hotspots
  Backend:
  - apps/backend/data/bangalore_waterlogging_hotspots.json - 200 Bangalore BBMP hotspots
  - apps/backend/data/singapore_waterlogging_hotspots.json - 60 Singapore PUB hotspots
  - apps/backend/src/api/hotspots.py - API proxy with caching + risk-summary endpoint
  - apps/backend/src/api/rainfall.py - Per-city FHI calibration (lines 36-38)
  - apps/backend/src/domain/ml/hotspots_service.py - City-aware HotspotsService loader

hotspot_counts:
  delhi: 90 (62 MCD + 28 OSM underpasses)
  bangalore: 200 (BBMP official flood-vulnerable locations, 8 zones via OpenCity.in KML)
  yogyakarta: 19 (river confluences, low-elevation areas)
  singapore: 60 (24 PUB hotspots + 36 flood-prone areas, geocoded from PUB Nov 2025 PDFs)
  total: 369

FHI_formula: |
  FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T
  CUSTOM HEURISTIC - weights empirically tuned, not from research
  Rain-gate: City-specific threshold — below = FHI capped at 0.15
  S component: 14-day exponential API decay (k: Delhi=0.92, Bangalore=0.88, Yogyakarta=0.85, Singapore=0.80)
  P component: Ceiling-only monthly P95 percentiles from 10yr ERA5 data
  S vs A distinction: S=14-day API decay (long-term wetness), A=3-day burst (short-term)

city_calibration:
  delhi:      { elev: 190-320m, wet_months: Jun-Sep,  urban: 75%, rain_gate: 5mm  }
  bangalore:  { elev: 800-1000m, wet_months: Jun-Oct, urban: 65%, rain_gate: 5mm  }
  yogyakarta: { elev: 75-200m, wet_months: Oct-Mar,  urban: 55%, rain_gate: 15mm }
  singapore:  { elev: 0-50m,   wet_months: Nov-Feb,  urban: 95%, rain_gate: 10mm }

pipeline: |
  Load hotspots (city-specific JSON) → XGBoost scoring (Delhi only) or severity fallback
  → FHI calculation (per-city calibration) → parallel scoring → cached response

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

metro_integration:
  delhi: Delhi Metro stations suggested when routes cross flood zones
  singapore: MRT 6 lines (NSL, EWL, NEL, CCL, DTL, TEL) rendered on map with official colors
  mrt_generator: apps/frontend/scripts/generate-sg-metro.py (OSM data → validated GeoJSON)
  mrt_validation: Station proximity (550m), terminal endpoint (1km), backtrack removal, zigzag smoothing
  route_casing: Google Maps-style darker outline behind route lines for contrast

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
cities: delhi, bangalore, yogyakarta, singapore
deduplication: Unique constraint on source_id

yogyakarta_support:
  GDACS bounding box: (-7.95, -7.65, 110.30, 110.50) — DIY province + Sleman/Bantul
  include_states: yogyakarta, jawa tengah (Central Java)
  Bilingual relevance scoring: Indonesian flood keywords (banjir, genangan, longsor, lahar, sungai)

singapore_support:
  GDACS bounding box: (1.15, 1.47, 103.60, 104.05) — island-wide
  include_states: singapore
  Relevance scoring: Singapore flood keywords (ponding, PUB, NEA, expressway underpasses)
  Expressways monitored: PIE, AYE, CTE, ECP, BKE, KPE, TPE

telegram_integration:
  status: LIVE (Singapore only)
  source: PUB (Public Utilities Board) Telegram channel
  display: Branded alert card in AlertsScreen Social tab
  features:
    - Recent alert history with original message dates
    - Branded container (not iframe — Telegram X-Frame-Options blocks it)
    - 5-second timeout with graceful fallback
  files:
    - apps/frontend/src/components/screens/AlertsScreen.tsx (Telegram section)
    - apps/backend/src/domain/services/external_alerts/telegram_fetcher.py

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

data_source: Multi-source: Open-Meteo (Delhi/Bangalore), NEA (Singapore), OpenWeatherMap (Yogyakarta)

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

calibration: Urban 1.5x-2.25x correction, 20 historical events tested (Delhi)

city_specific_calibration:
  delhi:      { elev: 190-320m, wet_months: Jun-Sep,  urban_fraction: 0.75, rain_gate: 5mm  }
  bangalore:  { elev: 800-1000m, wet_months: Jun-Oct, urban_fraction: 0.65, rain_gate: 5mm  }
  yogyakarta: { elev: 75-200m, wet_months: Oct-Mar,  urban_fraction: 0.55, rain_gate: 15mm }
  singapore:  { elev: 0-50m,   wet_months: Nov-Feb,  urban_fraction: 0.95, rain_gate: 10mm }

rain_gate: Per-city threshold. Below threshold = FHI capped at 0.15 (prevents false alarms in dry conditions)
cache: 1-hour TTL, in-memory

weather_sources:
  delhi: Open-Meteo (1hr cache TTL)
  bangalore: Open-Meteo (1hr cache TTL)
  yogyakarta: OpenWeatherMap One Call 3.0 when OPENWEATHERMAP_API_KEY set, else Open-Meteo (30min cache TTL)
  singapore: NEA (5min realtime, ×6 extrapolation for 3-day component) + OpenWeatherMap fallback (5min cache TTL)

nea_integration: |
  Singapore uses NEA (National Environment Agency) as primary weather source:
  - Current conditions: temperature, humidity, wind
  - 2-hour flash flood nowcast
  - 5-minute update frequency
  - ×6 extrapolation: NEA provides 2hr cumulative → multiply by 6 for FHI's 12hr component
  - Falls back to Open-Meteo if NEA unavailable
```

### @floodhub (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/floodhub.py - FloodHub proxy endpoints (5 endpoints)
  - apps/backend/src/domain/services/floodhub_service.py - Google FloodHub integration (785 lines)

  Frontend:
  - apps/frontend/src/components/floodhub/FloodHubTab.tsx - Main tab
  - apps/frontend/src/components/floodhub/FloodHubHeader.tsx
  - apps/frontend/src/components/floodhub/FloodHubAlertsList.tsx
  - apps/frontend/src/components/floodhub/ForecastChart.tsx - Dynamic units (m vs m³/s), extreme danger reference line
  - apps/frontend/src/components/floodhub/SignificantEventsCard.tsx - Active flood events display
  - apps/frontend/src/components/floodhub/FloodHubFooter.tsx
  - apps/frontend/src/components/MapComponent.tsx - Inundation GeoJSON fill layer (severity coloring)

status: LIVE IN PRODUCTION (API key active, E2E verified Feb 2026)
coverage: Delhi's Yamuna River (CWC_015-UYDDEL — Delhi Railway Bridge)
severity_levels: no_flooding, warning, danger, extreme
city_support:
  delhi: 1 active CWC gauge (Yamuna) — full forecasts + inundation
  bangalore: No gauges (Google monitors rivers, not urban drains)
  yogyakarta: No gauges (Google monitors rivers, not urban drains)
  singapore: No gauges (Google monitors rivers, not urban ponding)

hooks: useFloodHubStatus, useFloodHubGauges, useFloodHubForecast, useFloodHubEvents, useFloodHubInundation

endpoints:
  - GET /api/floodhub/status?city=DEL - Overall status with severity
  - GET /api/floodhub/gauges?city=DEL - City gauges with flood status
  - GET /api/floodhub/forecast/{gauge_id} - Forecast with water level predictions
  - GET /api/floodhub/inundation/{polygon_id} - Inundation map as GeoJSON (KML→GeoJSON conversion)
  - GET /api/floodhub/events?city=DEL - Significant flood events

cache_ttls: gauges 10min, forecasts 15min, models 60min, inundation 30min, events 15min

api_bugs_fixed:
  - Double-nested forecasts response: {"forecasts": {"gaugeId": {"forecasts": [...]}}} — unwrap twice
  - NaN water levels: Not JSON-serializable — convert to None, Optional[float]
  - Inundation 404: Upstream 404 returned as None, not wrapped as FloodHubAPIError

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
  - Geo-bias default: when no user lat/lng provided, defaults to city center
    so cloud servers (e.g. Koyeb Frankfurt) return local results instead of European ones
  - Country code: Nominatim countrycodes param uses city_bounds.country_code ("in" for Delhi/Bangalore, "id" for Yogyakarta)
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
  Frontend shows initial results, expandable per section
  Photon fetches 20 results, Nominatim fetches 30 as supplement
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
  - apps/frontend/src/contexts/NavigationContext.tsx - Route state management (lifted to App root)
  - apps/frontend/src/contexts/VoiceGuidanceContext.tsx - TTS voice instructions (lifted to App root)
  - apps/frontend/src/contexts/LocationTrackingContext.tsx - GPS tracking

features:
  - Turn-by-turn instructions with distance to next turn
  - Real-time hotspot warnings along route (FHI color dots)
  - Auto-reroute on deviation or new hotspot detection
  - Voice guidance via Web Speech API (TTS)
  - Live ETA and distance remaining
  - Offline location buffering
  - Direction arrow: chevron replaces pulsing dot during live navigation, rotates to bearing
  - Route line casing: Google Maps-style darker outline (12px casing + 8px fill for selected, 5px + 3px unselected)
  - calculateBearing() geo utility in lib/geo/distance.ts

voice_languages: |
  VoiceGuidanceContext supports 3 languages via Web Speech API:
  - en-IN (English India)
  - hi-IN (Hindi)
  - id-ID (Indonesian)
  Language-aware: tries exact match, then prefix, then English fallback.
  Lifted to App root so onboarding bot can use voice narration across all screens.

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

### @esp32-firmware (PAUSED)
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
status: Hardware design and firmware complete. Deployment paused.
```

### @iot-ingestion (PAUSED)
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
status: Service code complete. Deployment and integration paused.
```

### @whatsapp (COMPLETE)
```yaml
files:
  Twilio Transport:
  - apps/backend/src/api/webhook.py - Twilio webhook handler (form-encoded, TwiML response)
  - apps/backend/src/domain/services/notification_service.py - TwilioNotificationService

  Meta Cloud API Transport:
  - apps/backend/src/api/whatsapp_meta.py - Meta Graph API webhook (715 lines, JSON, HMAC-SHA256 signature)
  - apps/backend/src/domain/services/whatsapp/meta_client.py - Meta Graph API client (text, buttons, media)

  Shared Services:
  - apps/backend/src/domain/services/whatsapp/
    - button_sender.py - Quick Reply buttons (9 types)
    - command_handlers.py - RISK, WARNINGS, MY AREAS commands
    - message_templates.py - Message templating (bilingual EN/HI)
    - photo_handler.py - Photo ingestion + ML classification

dual_transport: |
  Two parallel webhook endpoints, shared session model + message templates:
  - Twilio: POST /api/whatsapp (form-encoded, TwiML response, Basic Auth media download)
  - Meta:   POST /api/whatsapp-meta (JSON, Graph API outbound, HMAC-SHA256 signature validation)
  Both use same WhatsAppSession, Wit.ai NLU, and ML classification pipeline.

inbound: Location pin → SOS, photo → ML classify, text commands, Quick Reply buttons
outbound: Alerts to watch areas via Twilio
commands: Send location (SOS), LINK, STATUS, START/STOP, RISK, WARNINGS, MY AREAS

quick_reply_buttons:
  - report_flood, check_risk, view_alerts, add_photo
  - submit_anyway, cancel, menu, report_another, check_my_location

session: WhatsAppSession model, 30-min timeout (shared by both transports)
rate_limiting: 10 messages/minute per phone
multi_language: English + Hindi templates

meta_config:
  env_vars: META_WHATSAPP_TOKEN, META_PHONE_NUMBER_ID, META_VERIFY_TOKEN, META_APP_SECRET
  auto_disable: Meta transport disabled if META_WHATSAPP_TOKEN not set
  verification: GET /api/whatsapp-meta with hub.mode=subscribe, hub.verify_token, returns hub.challenge
  signature: X-Hub-Signature-256 HMAC-SHA256 validation on every POST

setup: |
  Twilio:
  1. Twilio sandbox creds → .env (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
  2. TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
  3. ngrok http 8000 → webhook URL in Twilio Console
  4. Migration: python -m apps.backend.src.scripts.migrate_add_whatsapp_sessions

  Meta Cloud API:
  1. Meta Business Account + WhatsApp app → .env (META_WHATSAPP_TOKEN, META_PHONE_NUMBER_ID)
  2. META_VERIFY_TOKEN (custom string) + META_APP_SECRET (from Meta dashboard)
  3. Webhook URL: https://<domain>/api/whatsapp-meta (POST + GET verification)
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

### @safety-circles (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/circles.py - 16 endpoints (CRUD, members, alerts, invite codes)
  - apps/backend/src/domain/services/circle_service.py - CircleService (20+ methods)
  - apps/backend/src/domain/services/circle_notification_service.py - WhatsApp/SMS/email dispatch
  Frontend:
  - apps/frontend/src/components/circles/SafetyCirclesTab.tsx - Main tab (in AlertsScreen)
  - apps/frontend/src/components/circles/CreateCircleModal.tsx - Circle creation form
  - apps/frontend/src/components/circles/JoinCircleModal.tsx - Join via invite code
  - apps/frontend/src/components/circles/CircleDetailModal.tsx - Members, settings
  - apps/frontend/src/components/circles/CircleMemberList.tsx - Member list with roles
  - apps/frontend/src/components/circles/AddMemberModal.tsx - Single + bulk add
  - apps/frontend/src/components/circles/CircleSettingsSheet.tsx - Edit name/description
  - apps/frontend/src/components/circles/InviteLinkShare.tsx - Share invite code
  - apps/frontend/src/components/circles/CircleAlertCard.tsx - Alert with read status
  - apps/frontend/src/components/circles/index.ts - Barrel export

circle_types:
  family: max 20 members
  school: max 500 members
  apartment: max 200 members
  neighborhood: max 1000 members
  custom: max 50 members

roles: creator (full delete) > admin (manage members/settings) > member (receive, leave)

models:
  SafetyCircle: id, name, description, circle_type, created_by, invite_code (8-char unique), max_members, is_active
  CircleMember: id, circle_id, user_id (nullable for non-registered), phone (E.164), email, display_name, role, is_muted, notify_whatsapp/sms/email, joined_at, invited_by
  CircleAlert: id, circle_id, report_id, reporter_user_id, member_id, message, is_read, notification_sent, notification_channel

key_points:
  - Non-registered contacts supported (phone/email only), auto-upgrade when they register
  - Invite code: 8-char alphanumeric with collision retry (5 attempts)
  - Notification tracking per alert: notification_sent + notification_channel (Rule #14: no silent fallbacks)
  - Phone normalization delegates to core/phone_utils.py (E.164 format)
  - Partial unique constraint: registered users one-per-circle, unregistered contacts unconstrained
  - Shown as tab in AlertsScreen with unread count badge
  - SOS emergency: One-tap SOS sends to all circle members via Twilio (see @sos)
  - Offline SOS: Queued in IndexedDB, delivered via Background Sync when online

hooks (TanStack Query):
  Queries: useMyCircles (60s stale), useCircleDetail (30s), useCircleAlerts (30s, 60s refetch), useUnreadCircleAlertCount (30s, 60s refetch)
  Mutations: useCreateCircle, useJoinCircle, useAddCircleMember, useBulkAddCircleMembers, useRemoveCircleMember, useUpdateCircleMember, useLeaveCircle, useDeleteCircle, useMarkCircleAlertRead, useMarkAllCircleAlertsRead, useUpdateCircle

endpoints:
  - POST /api/circles/ - Create circle
  - GET /api/circles/ - List user's circles
  - GET /api/circles/{id} - Circle detail with members
  - PUT /api/circles/{id} - Update circle (admin+)
  - DELETE /api/circles/{id} - Delete (creator only)
  - POST /api/circles/{id}/members - Add member
  - POST /api/circles/{id}/members/bulk - Bulk add
  - DELETE /api/circles/{id}/members/{member_id} - Remove
  - PATCH /api/circles/{id}/members/{member_id} - Update role/notifications
  - POST /api/circles/join - Join via invite code
  - POST /api/circles/{id}/leave - Leave circle
  - GET /api/circles/alerts - Get circle alerts (paginated)
  - PATCH /api/circles/alerts/{id}/read - Mark alert read
  - PATCH /api/circles/alerts/read-all - Mark all read
  - GET /api/circles/alerts/unread-count - Unread badge count

migration: python -m apps.backend.src.scripts.migrate_add_safety_circles
```

### @onboarding-bot (COMPLETE)
```yaml
files:
  Frontend:
  - apps/frontend/src/components/onboarding-bot/OnboardingBot.tsx - Root component (phase router)
  - apps/frontend/src/components/onboarding-bot/BotCompanion.tsx - Floating companion (app tour phase)
  - apps/frontend/src/components/onboarding-bot/BotInlineCard.tsx - Inline card (onboarding phase)
  - apps/frontend/src/components/onboarding-bot/BotSpotlight.tsx - Element spotlight overlay
  - apps/frontend/src/components/onboarding-bot/BotTooltip.tsx - Tooltip for spotlighted elements
  - apps/frontend/src/contexts/OnboardingBotContext.tsx - Tour state, language, phase management
  - apps/frontend/src/lib/onboarding-bot/tourSteps.ts - 6 onboarding + 11 app tour step definitions
  - apps/frontend/src/lib/onboarding-bot/translations.ts - EN/HI/ID translations
  - apps/frontend/src/types/onboarding-bot.ts - TourStep, BotPhase, BotLanguage types

  Backend:
  - apps/backend/src/infrastructure/models.py - User.tour_completed_at column
  - apps/backend/src/api/users.py - POST /api/users/me/tour-completed endpoint
  - apps/backend/scripts/migrate_add_tour_completed.py - Migration script

two_phase_system: |
  1. ONBOARDING PHASE: BotInlineCard embedded in OnboardingScreen.
     - 6 steps matching wizard flow (welcome → city → profile → watch areas → routes → complete)
     - Card auto-collapses to 32px pill after 5 seconds idle
     - No spotlight — purely informational companion
  2. APP TOUR PHASE: BotCompanion floats across all screens.
     - 11 steps across Home, Map, Report, Alerts, Profile screens
     - BotSpotlight highlights specific UI elements (data-tour-id attributes)
     - Screen navigation via onBefore hooks (navigateTo callback)
     - Triggered after onboarding completion via localStorage bridge

multilingual:
  languages: English (en), Hindi (hi), Indonesian (id)
  selector: Language pill buttons in bot UI
  voice: Language-aware narration via VoiceGuidanceContext (en-IN, hi-IN, id-ID)

user_control:
  - Skip/dismiss button on companion and inline card
  - Escape key dismisses bot
  - Replay tour from ProfileScreen (resets tour_completed_at)

bridge_pattern: |
  Onboarding → App tour bridge uses localStorage flag (floodsafe_start_app_tour).
  OnboardingScreen sets flag + reloads page on completion.
  App.tsx useEffect reads + clears flag, then starts app tour phase.
  Required because page reload destroys React state.

key_gotchas:
  - setState({currentStepIndex: 0}) does NOT run onBefore hooks — must manually call steps[0].onBefore()
  - NavigationProvider must be at App root (above OnboardingBotProvider) for screen navigation
  - FloodAtlasScreen's inner NavigationProvider shadows root one for isolated nav sessions
  - driver.js: overlayClickBehavior (NOT onOverlayClick), must destroy() before re-creating

migration: python scripts/migrate_add_tour_completed.py (from apps/backend/)
```

### @ai-risk-insights (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/domain/services/llama_service.py - Groq/Llama risk summary generation
  - apps/backend/src/domain/services/wit_service.py - Wit.ai NLU (7 intents, EN/HI)
  - apps/backend/src/domain/services/meta_client.py - Meta API client
  - apps/backend/src/api/hotspots.py - /risk-summary endpoint (lines 321-394)
  Frontend:
  - apps/frontend/src/components/AiRiskInsightsCard.tsx - Risk card with language toggle
  - apps/frontend/src/lib/api/hooks.ts - useRiskSummary hook

architecture:
  Primary API: Meta Llama (llama-3.3-8b, api.llama.com)
  Fallback API: Groq (llama-3.1-8b-instant, api.groq.com) — ACTIVE
  NLU: Wit.ai (floodsafe app, 7 intents, 51 utterances)

languages: English (default), Hindi (toggle in UI)
caching: 1-hour backend TTL per (lat, lng, language), max 500 entries. 10-min frontend staleTime.

rate_limiting_groq:
  hard: 120 req/min, 2000 req/day
  soft: 100 req/min, 1800 req/day (warns at 80% daily)
  exceeded: returns null (graceful degradation, UI shows "service busy")

endpoint: GET /api/hotspots/risk-summary?lat=X&lng=Y&language=en|hi
response: { risk_summary: string|null, enabled: bool, risk_level: string, fhi_score: float, language: string }

frontend_ui_states:
  1. Loading - Gray skeleton lines
  2. Error - "Could not load insight" + Retry
  3. Disabled - "AI insights being set up" (enabled=false)
  4. Rate-limited - "AI service is busy" + Refresh (enabled=true, summary=null)
  5. Success - Colored border (emerald/amber/orange/red) + risk badge + narrative

integration: HomeScreen shows top 3 locations (watch areas + daily routes) with independent parallel fetching

wit_ai_intents: check_risk, report_flood, get_warnings, check_status, get_help, get_my_areas, greet
wit_confidence_threshold: 0.5

graceful_disable: All failures return risk_summary=null without throwing. UI handles independently.
```

### @webmcp-bridge (COMPLETE)
```yaml
files:
  - apps/frontend/src/components/WebMCPProvider.tsx - Bridge component (renders null, pure side-effect)
  - apps/frontend/package.json - @mcp-b/react-webmcp@1.1.1, @mcp-b/global@1.5.0

mount: App.tsx root level (inside LocationTrackingProvider)
protocol: postMessage API (browser window events)
status: Production-enabled

entities (13 total):
  Contexts (2):
    context_app_state: City, auth status, user profile, gamification points
    context_location: GPS position, nearby hotspots with FHI, tracking state

  Tools (3):
    search_locations: { query, city?, limit? } - Read-only
    get_query_cache: { query_key } - Read-only (TanStack Query cache)
    switch_city: { city: delhi|bangalore|yogyakarta|singapore } - Destructive

  Resources (5):
    floodsafe://config - API URL, city list, bounds, feature flags
    floodsafe://alerts/{city} - Unified flood alerts (IMD, GDACS, community, FloodHub)
    floodsafe://hotspots/{city} - Waterlogging hotspots with FHI risk levels
    floodsafe://reports - Recent community flood reports
    floodsafe://floodhub/{city} - Google Flood Forecasting status + gauges

  Prompts (3):
    analyze-flood-risk: Full risk analysis for a city
    debug-ui-state: Gather all app state for debugging
    verify-yogyakarta: E2E Yogyakarta integration check

contexts_consumed: AuthContext, CityContext, LocationTrackingContext, TanStack Query
zod_constraint: Must use zod@^3.25.0 (v4 breaks @mcp-b/react-webmcp peer dependency)
```

### @push-notifications (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/push.py - FCM token registration (2 endpoints)
  - apps/backend/src/domain/services/push_notification_service.py - Firebase Cloud Messaging sender
  - apps/backend/src/scripts/migrate_add_fcm_token.py - Migration for User FCM fields
  - apps/backend/src/infrastructure/models.py - User.fcm_token, fcm_token_updated_at, notification_push

  Frontend:
  - apps/frontend/src/hooks/usePushNotifications.ts - Permission request, token registration, foreground handler
  - apps/frontend/public/firebase-messaging-sw.js - Background notification handler + click routing

endpoints:
  - POST /api/push/register-token - Store/update FCM token (auth required, 50-500 char token)
  - DELETE /api/push/register-token - Remove FCM token (logout cleanup)

notification_triggers:
  - Watch area alert: When a flood report is created near a user's watch area
  - Circle alert: When a safety circle member reports flooding nearby

architecture: |
  Registration: Frontend requestPermission() → Firebase getToken(vapidKey) → POST /api/push/register-token → User.fcm_token
  Sending: Report created → identify affected users (watch areas + circles) → send_push_to_user() → Firebase Admin SDK → FCM
  Foreground: React onMessage listener → native Notification()
  Background: Service Worker onBackgroundMessage → self.registration.showNotification()
  Click: Service Worker notificationclick → focus existing window or openWindow()

firebase_admin: |
  Initialized via FIREBASE_SERVICE_ACCOUNT_B64 env var (base64-encoded service account JSON).
  Double-checked locking for thread-safe lazy initialization.
  Stale token cleanup: UnregisteredError → auto-clear fcm_token from User record.

preference_check: user.notification_push boolean checked before every send
platform_detection: Capacitor.isNativePlatform() placeholder for future native push (not yet wired)

migration: python -m apps.backend.src.scripts.migrate_add_fcm_token
```

### @sos (COMPLETE)
```yaml
files:
  Backend:
  - apps/backend/src/api/sos.py - SOS emergency endpoint (POST /api/sos/send)
  - apps/backend/src/domain/services/sos_service.py - SOSService with Twilio SMS/WhatsApp fanout
  - apps/backend/src/infrastructure/models.py - SOSMessage model with per-recipient JSON tracking

  Frontend:
  - apps/frontend/src/hooks/useSOSQueue.ts - Offline-first hook (IndexedDB + Background Sync)
  - apps/frontend/src/components/SOSButton.tsx - SOS button (full + compact variants)
  - apps/frontend/src/components/EmergencyContactsModal.tsx - Emergency contacts with integrated SOS
  - apps/frontend/public/sw-sos-sync.js - Service Worker Background Sync handler

offline_architecture: |
  Online: SOSButton → useSOSQueue.queueSOS() → IndexedDB → flushQueue() → POST /api/sos/send
  Offline: SOSButton → useSOSQueue.queueSOS() → IndexedDB → registerBackgroundSync('flush-sos-queue')
  Recovery: SW sync event → sw-sos-sync.js flushSosQueue() → reads IndexedDB → POST /api/sos/send
  Notification: SW postMessage 'SOS_SYNC_COMPLETE' → useSOSQueue listener updates UI

indexeddb:
  database: floodsafe-sos
  store: sos-queue
  max_queue: 50 messages
  max_retries: 3 per message

per_recipient_tracking: |
  SOSMessage.recipients_json stores individual delivery results:
  Each recipient: { phone, name, status ('sent'|'failed'), channel, error }
  Overall status: 'sent' (all), 'partial' (some), 'failed' (none)

channels: SMS or WhatsApp via Twilio (Meta Graph API not yet supported for SOS)
phone_normalization: core/phone_utils.py (E.164 format)

ui_states:
  sending: Button disabled, spinner
  sent: Green checkmark (5 seconds), shows contact count
  offline: Yellow "Offline" pill with WifiOff icon
  queued: Yellow pill showing pending count

endpoints:
  - POST /api/sos/send - Send emergency SOS to safety circle members (auth required)
    request: { circle_ids: [uuid], message?: string, location?: {lat, lng}, channel: 'sms'|'whatsapp' }
    response: { id, status, total, sent, failed, results: [...] }
```

### @edge-ai (PLANNED)
```yaml
concept: ANN model running on IoT devices (ESP32/Raspberry Pi)
goal: Local flood prediction without cloud dependency
current: ESP32 firmware does threshold-based alerts (no ML yet)
next: Design lightweight neural network for edge inference
```

### @mobile (IN PROGRESS)
```yaml
files:
  - apps/frontend/capacitor.config.ts - Capacitor configuration (appId: com.floodsafe.app)
  - apps/frontend/android/ - Android project (BridgeActivity, AndroidManifest.xml)
  - apps/frontend/android/variables.gradle - minSdk 24, compileSdk 36, targetSdk 36

status: |
  Capacitor 8.1.0 initialized with Android wrapper.
  BridgeActivity is minimal (extends com.getcapacitor.BridgeActivity, zero custom logic).
  WebView loads Vite build output from assets. CORS permissive (access origin="*").
  No native Capacitor plugins installed yet — all features run through web path.

working:
  - Capacitor Core installed ✅
  - BridgeActivity configured ✅
  - WebView asset loading ✅
  - Platform detection (Capacitor.isNativePlatform()) in push notifications hook ✅

not_yet_implemented:
  - Native push notifications (@capacitor/push-notifications not installed)
  - Native geolocation (@capacitor/geolocation not installed)
  - Camera access (@capacitor/camera not installed)
  - App signing for Play Store release

android_config:
  minSdk: 24 (Android 7.0)
  targetSdk: 36
  compileSdk: 36
  javaVersion: 21
  androidScheme: http (for local asset loading)

next: Install native Capacitor plugins for push, geolocation, camera
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

## Frontend Contexts (8)

| Context | File | Purpose |
|---------|------|---------|
| Auth | `AuthContext.tsx` | Email/Google/Phone auth state |
| City | `CityContext.tsx` | City preference/selection |
| User | `UserContext.tsx` | User profile/settings |
| Navigation | `NavigationContext.tsx` | Route + screen navigation state |
| Location Tracking | `LocationTrackingContext.tsx` | Real-time GPS |
| Voice Guidance | `VoiceGuidanceContext.tsx` | TTS for navigation + onboarding bot |
| Install Prompt | `InstallPromptContext.tsx` | PWA install state |
| Onboarding Bot | `OnboardingBotContext.tsx` | Tour state, language, phase management |

## Backend API Files (29)

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
| `hotspots.py` | @hotspots | hotspot proxy, risk-summary |
| `predictions.py` | @ml-predictions | ML service proxy |
| `ml.py` | @photo-verification | embedded TFLite classifier |
| `rainfall.py` | @rainfall | forecast + FHI (per-city calibration) |
| `historical_floods.py` | @historical-floods | flood history |
| `external_alerts.py` | @external-alerts | multi-source alerts |
| `floodhub.py` | @floodhub | FloodHub proxy (5 endpoints) |
| `circles.py` | @safety-circles | circle CRUD, members, alerts (16 endpoints) |
| `search.py` | @smart-search | unified search |
| `routes_api.py` | @routing | route comparison |
| `saved_routes.py` | @saved-routes | route bookmarks |
| `daily_routes.py` | @onboarding | daily commute routes |
| `gamification.py` | @gamification | unified gamification |
| `badges.py` | @gamification | badge catalog |
| `reputation.py` | @gamification | reputation + privacy |
| `leaderboards.py` | @gamification | leaderboards |
| `webhook.py` | @whatsapp | WhatsApp webhook (Twilio) |
| `whatsapp_meta.py` | @whatsapp | WhatsApp webhook (Meta Cloud API) |
| `push.py` | @push-notifications | FCM token registration |
| `sos.py` | @sos | Emergency SOS fanout |
| `deps.py` | (shared) | auth dependencies, role checks |

## Database Models (23)

| Model | Table | Key Fields |
|-------|-------|------------|
| User | users | role, points, level, badges, reputation_score, streak_days, password_hash, fcm_token, notification_push |
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
| SafetyCircle | safety_circles | name, circle_type, invite_code (8-char unique), max_members, created_by |
| CircleMember | circle_members | circle_id, user_id (nullable), phone, role, notify_whatsapp/sms/email |
| CircleAlert | circle_alerts | circle_id, report_id, member_id, is_read, notification_sent/channel |
| WhatsAppSession | whatsapp_sessions | phone, state, expires_at |
| SOSMessage | sos_messages | user_id, circle_ids, message, location, recipients_json, status (sent/partial/failed) |
| RefreshToken | refresh_tokens | user_id, token_hash, expires_at |
| EmailVerificationToken | email_verification_tokens | user_id, token, expires_at |

---

## Roadmap

### Tier 1: Community Intelligence ✅ COMPLETE
Reports, map, alerts, onboarding, auth (Email/Google/Phone), E2E tests, community voting/comments

### Tier 2: ML/AI Foundation ✅ MOSTLY COMPLETE
- [x] XGBoost for 369 known hotspots (90 Delhi + 200 Bangalore + 19 Yogyakarta + 60 Singapore, AUC 0.98)
- [x] FHI formula + rainfall forecasts (Open-Meteo, per-city calibration)
- [x] Historical Floods Panel (45 Delhi events, 1969-2023)
- [x] Photo classification (embedded TFLite MobileNet)
- [x] External alert aggregation (IMD, CWC, RSS, Twitter, GDACS, GDELT)
- [x] FloodHub integration (Yamuna gauges + inundation layer + significant events)
- [x] AI Risk Insights (Groq Llama 3.1 summaries, EN/HI, per-location narratives)
- [ ] Ensemble models (LSTM/GNN) - NOT TRAINED
- [ ] Better generalization (need 300+ diverse locations)

### Tier 3: Smart Sensors & Edge AI ⏸️ PAUSED
- [x] IoT ingestion service (high-throughput, raw SQL) — code complete, deployment paused
- [x] Sensor registration + API key auth (SHA256) — code complete, deployment paused
- [x] ESP32 firmware (dual sensor, offline buffering, OLED) — hardware complete, deployment paused
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
- [x] Meta WhatsApp Cloud API (parallel transport, Graph API, HMAC-SHA256 signature validation)
- [x] FCM push notifications (watch area + circle alerts, foreground + background, service worker)
- [x] SOS emergency fanout (offline-first IndexedDB queue, Background Sync, per-recipient tracking)

### Tier 6: Mobile & Offline ✅ MOSTLY COMPLETE
- [x] PWA with Workbox service worker
- [x] Install banner + offline indicator
- [x] Cache strategies (CacheFirst, NetworkFirst, StaleWhileRevalidate)
- [x] Capacitor Android wrapper initialized (BridgeActivity, WebView, minSdk 24)
- [ ] Capacitor native plugins (push, geolocation, camera — currently web-only paths)
- [ ] Play Store release (app signing, listing)

### Tier 7: Scale ✅ PARTIALLY COMPLETE
- [x] City expansion: Yogyakarta added as 3rd city (19 hotspots, GDACS, FHI, search)
- [x] Singapore added as 4th city (60 PUB hotspots, MRT, NEA weather, Telegram alerts)
- [x] Bangalore BBMP hotspots (200 official flood-vulnerable locations, 8 zones)
- [x] Per-city FHI weather sources (NEA for Singapore, OWM for Yogyakarta)
- [x] FHI 14-day API decay (S component) + ceiling-only P percentiles + per-city k differentiation
- [x] Telegram channel integration for Singapore flood alerts
- [x] Navigation direction arrow + route line casing
- [x] MRT line validation with station-proximity checks
- [x] WebMCP browser automation bridge (13 entities, production-enabled)
- [x] Safety Circles (emergency contacts, 5 circle types, notification tracking)
- [x] Multilingual onboarding bot with guided app tour (EN/HI/ID)
- [x] FCM push notifications (watch area + circle alert triggers)
- [x] SOS emergency with offline queue (IndexedDB + Background Sync + Twilio fanout)
- [x] Meta WhatsApp Cloud API (parallel transport alongside Twilio)
- [x] Capacitor Android wrapper (BridgeActivity, WebView, platform detection)
- [ ] Multi-language UI (Hindi, Kannada, Indonesian — onboarding bot covers 3 languages, WhatsApp Hindi done)
- [ ] GNN for flood propagation modeling
- [ ] Real photo storage (S3/Blob, currently mocked)
- [ ] Water depth estimation from photos
- [ ] Native Capacitor plugins (push, geolocation, camera)
- [ ] Play Store release
