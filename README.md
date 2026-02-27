<div align="center">
  <img src="apps/frontend/public/pwa-512x512.png" alt="FloodSafe" width="120" />
  <h1>FloodSafe</h1>
  <p><strong>Open-source flood monitoring platform for flood-prone cities</strong></p>
  <p>Community reporting · AI predictions · Safe routing · Real-time alerts</p>

  ![License: Nonprofit](https://img.shields.io/badge/License-Nonprofit-blue)
  ![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?logo=typescript&logoColor=white)
  ![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
  ![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
  ![PostGIS](https://img.shields.io/badge/PostGIS-15-336791?logo=postgresql&logoColor=white)
  ![PWA](https://img.shields.io/badge/PWA-Installable-5A0FC8)
</div>

---

## Why FloodSafe

Every monsoon and wet season, cities across Asia face devastating urban flooding. The 2023 Yamuna floods displaced over 25,000 people in Delhi alone; Singapore sees flash floods from intense tropical rainfall; Yogyakarta contends with river overflows during the rainy season. Waterlogging paralyzes transportation, endangers lives, and disproportionately impacts low-income communities who rely on public transit and live in flood-prone areas.

**FloodSafe addresses this with four pillars:**

- **Community Intelligence** — Citizens report flooding in real-time with GPS-verified photos, building a crowd-sourced flood map that helps everyone navigate safely.

- **AI-Powered Prediction** — Machine learning models (XGBoost, AUC 0.98) predict waterlogging risk at 369 known hotspots across 4 cities using live weather data, giving people advance warning before they step outside.

- **Safe Routing** — A route planner that avoids high-risk flood zones with 300-meter safety buffers, with live turn-by-turn voice navigation to guide you through safer paths.

- **Multi-Channel Alerts** — Watch area notifications, 7 government and institutional alert sources (IMD, CWC, GDACS), and a WhatsApp bot with Hindi support — meeting people where they already communicate.

FloodSafe is a nonprofit project built for social good.

---

## Features

### Flood Intelligence

| Feature | Description |
|---------|-------------|
| **Flood Hazard Index (FHI)** | Live risk score (0–1) from 6 weather components: `0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E`. 14-day exponential API decay for soil saturation, ceiling-only P95 percentiles from ERA5, per-city calibration (k: 0.80–0.92). Sources: Open-Meteo, NEA, OpenWeatherMap |
| **Waterlogging Hotspots** | 369 locations across 4 cities (90 Delhi, 200 Bangalore, 19 Yogyakarta, 60 Singapore) with live FHI-based color coding. Per-city weather sources: NEA (Singapore), OpenWeatherMap (Yogyakarta), Open-Meteo (Delhi/Bangalore) |
| **XGBoost Risk Model** | 18-feature binary classifier (AUC 0.98) for weather-responsive risk prediction at 369 known hotspots |
| **Flood Photo Classifier** | MobileNet v1 via TFLite, threshold 0.3 (safety-first to minimize false negatives) |
| **Historical Floods** | 45 Delhi NCR events (1969–2023) from the IFI-Impacts dataset, grouped by decade |
| **Google Flood Forecasting** | Live Google Flood Forecasting API — 1 Delhi gauge (CWC_015-UYDDEL, Yamuna), 28-hour forecasts, 3-tier thresholds (warning/danger/extreme), significant events with population impact, KML→GeoJSON inundation maps |
| **External Alerts** | 8 sources: IMD, CWC, RSS feeds, Twitter/X, GDACS, GDELT, news, PUB Telegram channel (Singapore). Severity-scored and deduplicated |

### Community & Reporting

| Feature | Description |
|---------|-------------|
| **Flood Reports** | Photo upload with GPS/EXIF verification, severity tagging, and location cross-validation |
| **Voting & Comments** | Upvote/downvote with deduplication (one vote per user per report), comments with rate limiting (5/min) |
| **Gamification** | Points for verified reports, 4 badge categories, daily streaks, leaderboards with privacy controls |
| **Photo Verification** | EXIF GPS extraction, ML flood classification, automatic location validation |

### Safe Routing & Navigation

| Feature | Description |
|---------|-------------|
| **Route Comparison** | Side-by-side normal vs flood-safe routes with distance, time, and risk comparison |
| **Hotspot Avoidance** | HARD AVOID for HIGH/EXTREME FHI zones (300m buffer). LOW/MODERATE: warning overlay only |
| **Metro Integration** | Delhi Metro + Singapore MRT (6 lines, official colors) station suggestions when routes cross flood zones. Route line casing for map contrast |
| **Live Navigation** | Turn-by-turn with voice guidance (Web Speech API), direction arrow (chevron bearing indicator), real-time hotspot proximity warnings |
| **Saved Routes** | Bookmark routes with use-count tracking across 3 transport modes (driving, walking, cycling) |

### Alerts & Monitoring

| Feature | Description |
|---------|-------------|
| **Watch Areas** | User-defined monitoring zones with PostGIS spatial queries and custom radius |
| **Push Notifications (FCM)** | Firebase Cloud Messaging for real-time alerts. Watch area + safety circle triggers. Foreground (in-app) and background (service worker) notification paths. Auto token cleanup on unregister |
| **WhatsApp Bot** | Dual transport: Twilio (TwiML, form-encoded) + Meta Cloud API (Graph API, HMAC-SHA256 signature). Wit.ai NLU (6 intents), 9 Quick Reply buttons, location SOS, photo ML classification, Hindi/Hinglish support, AI risk summaries (Meta Llama with Groq fallback, 1hr cache). Shared session model + message templates |
| **Emergency Contacts** | City-aware emergency numbers: Delhi (112, NDMA 1070, DDMA 1077), Bangalore (BBMP), Yogyakarta (112, BPBD), Singapore (999 SPF, 995 SCDF, PUB 1800-284-6600). 88px tap targets. Integrated in Alerts, Home (SOS), and Profile screens |

### Safety Circles

| Feature | Description |
|---------|-------------|
| **Group Safety** | Create circles (family/school/apartment/neighborhood/custom) with 8-char invite codes, up to 1000 members. 16 API endpoints |
| **SOS Emergency** | One-tap SOS with offline queue (IndexedDB + Background Sync). Service worker delivers when online. Per-recipient delivery tracking (sent/partial/failed) |
| **SOS Fanout** | Twilio SMS or WhatsApp delivery to all circle members. Phone normalization (E.164), 3 retry limit, max 50 queued messages |

### Smart Search

| Feature | Description |
|---------|-------------|
| **Dual Geocoding** | Photon (typo-tolerant) + Nominatim (authoritative), proximity-sorted, deduplicated |
| **Delhi Aliases** | 281+ local aliases — "CP" resolves to Connaught Place, "Minto" to Minto Bridge |
| **Intent Detection** | Distinguishes location, report, and user searches with @-prefix patterns |

### Progressive Web App

| Feature | Description |
|---------|-------------|
| **Offline Support** | Workbox service worker with CacheFirst, NetworkFirst, and StaleWhileRevalidate strategies |
| **Installable** | Install banner for Android/desktop, dedicated iOS install prompt, standalone display mode |
| **Offline SOS** | Emergency SOS queued via IndexedDB when offline, delivered via Background Sync when connectivity returns. Service worker handles token auth + delivery |

### IoT Sensors (Experimental — Paused)

ESP32-based water level monitoring with dual sensor fusion (capacitive strips + VL53L0X ToF), OLED display, and 100-reading offline buffer. High-throughput ingestion service on port 8001. Currently paused — contributions welcome.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, TypeScript 5, Vite, Tailwind CSS v4, Radix UI, MapLibre GL JS, TanStack Query, Workbox, Capacitor 8 (Android) |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, PostGIS |
| **ML / AI** | XGBoost, TensorFlow / MobileNet (TFLite), Google Flood Forecasting API, Google Earth Engine, CHIRPS, Open-Meteo, NEA (Singapore weather), OpenWeatherMap |
| **Database** | PostgreSQL 15 + PostGIS (SRID 4326) |
| **Auth** | Email/Password (bcrypt), Google OAuth, Phone OTP (Firebase) |
| **Maps** | MapLibre GL JS, PMTiles (offline tiles), OpenStreetMap, Photon + Nominatim geocoding |
| **Messaging** | Twilio (WhatsApp + SMS), Meta WhatsApp Cloud API, Firebase Cloud Messaging (FCM push), SendGrid (email) |
| **Meta AI** | Wit.ai (NLU), Meta Llama API (risk summaries), MobileSAM (flood segmentation demo) |
| **Deploy** | Vercel (frontend), Koyeb (backend + ML), Supabase (database) |
| **Testing** | Playwright (E2E + visual regression), Vitest, pytest, TypeScript strict mode |

---

## Architecture

```
                              ┌──────────────────┐
                              │   Vercel (CDN)    │
                              └────────┬─────────┘
                                       │
                            ┌──────────▼──────────┐
                            │      Frontend        │
                            │  React 18 + MapLibre │
                            │  PWA + Workbox       │
                            │  12 screens          │
                            └──────────┬──────────┘
                                       │
                         ┌─────────────▼──────────────┐
                         │        Backend API          │
                         │   FastAPI + SQLAlchemy      │
                         │  32 routers, 100+ endpoints │
                         │     Clean Architecture      │
                         └─┬───────┬──────────┬────┬──┘
                           │       │          │    │
              ┌────────────▼──┐ ┌──▼─────┐ ┌──▼──┐ ┌▼─────────────┐
              │ PostgreSQL    │ │   ML   │ │ IoT │ │ External APIs │
              │ + PostGIS     │ │ Service│ │Ingest│ │───────────────│
              │  23 tables    │ │ XGBoost│ │(8001)│ │ Google Flood  │
              │ (Supabase)    │ │MbilNet │ │Paused│ │ Forecasting   │
              └───────────────┘ │FHI Calc│ └─────┘ │ Meta/Wit.ai   │
                                └────────┘         │ Twilio + FCM  │
                                                   └───────────────┘
```

- **Frontend** — 12 screens, 8 React contexts, full PWA with offline support. Hosted on Vercel.
- **Backend API** — 32 router modules following Clean Architecture (`api/` → `domain/services/` → `infrastructure/`). Hosted on Koyeb.
- **ML Service** — XGBoost hotspot risk model, FHI calculator, MobileNet flood classifier. Hosted on Koyeb.
- **External APIs** — Google Flood Forecasting (gauge forecasts, inundation maps), NEA (Singapore weather), Wit.ai (NLU for WhatsApp), Meta Llama (AI risk summaries with Groq fallback), Twilio + Meta WhatsApp Cloud API (dual transport), Firebase Cloud Messaging (push notifications).
- **Database** — PostgreSQL 15 with PostGIS extensions, 23 tables, UUID primary keys. Hosted on Supabase.

---

## Screenshots

> Screenshots coming soon. Try the live app at **[frontend-lime-psi-83.vercel.app](https://frontend-lime-psi-83.vercel.app)**.

<!--
| Home | Flood Atlas | Safe Routing |
|:----:|:-----------:|:------------:|
| ![Home](docs/screenshots/home.png) | ![Atlas](docs/screenshots/atlas.png) | ![Routing](docs/screenshots/routing.png) |
-->

---

## Getting Started

### Prerequisites

- Docker Desktop
- Node.js 18+
- Python 3.11+

### Docker (Full Stack)

```bash
git clone https://github.com/FloodSafe-Delhi/floodsafe-mvp.git
cd FloodSafe
docker-compose up -d
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5175 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| ML Service | http://localhost:8002 |

### Local Development

```bash
# Start database and ML service
docker-compose up -d db ml-service

# Backend
cd apps/backend
cp .env.example .env          # Set DATABASE_URL to localhost:5432
python -m uvicorn src.main:app --reload

# Frontend (in a separate terminal)
cd apps/frontend
npm install
npm run dev                   # Runs on port 5175
```

### Environment Variables

Each service has a `.env.example` file. Key variables:

| Variable | Service | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | Backend | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Backend | Authentication token signing |
| `ML_SERVICE_URL` | Backend | ML service endpoint |
| `VITE_API_URL` | Frontend | Backend API URL |
| `VITE_FIREBASE_*` | Frontend | Firebase config (6 vars) |
| `TWILIO_*` | Backend | WhatsApp/SMS (account SID, auth token, number) |
| `GOOGLE_FLOODHUB_API_KEY` | Backend | Google Flood Forecasting API access |
| `WIT_AI_TOKEN` | Backend | Wit.ai NLU for WhatsApp command classification |
| `META_LLAMA_API_KEY` | Backend | Meta Llama API for AI risk summaries |
| `LLAMA_FALLBACK_API_KEY` | Backend | Groq fallback for Llama (optional, `gsk_...` prefix) |
| `META_WHATSAPP_TOKEN` | Backend | Meta WhatsApp Cloud API token |
| `META_PHONE_NUMBER_ID` | Backend | Meta WhatsApp phone number ID |
| `META_VERIFY_TOKEN` | Backend | Meta webhook verification token |
| `META_APP_SECRET` | Backend | Meta app HMAC signature validation |
| `NEA_API_KEY` | Backend | Singapore NEA weather data (optional, has free tier) |
| `OPENWEATHERMAP_API_KEY` | Backend | Yogyakarta OWM One Call 3.0 (optional) |
| `FIREBASE_SERVICE_ACCOUNT_B64` | Backend | Base64-encoded Firebase service account JSON (FCM push notifications) |
| `GCP_PROJECT_ID` | ML | Google Earth Engine access |

---

## API Overview

The backend exposes 32 router modules with 100+ endpoints. Full Swagger docs available at `/docs`.

| Group | Routers | Endpoints | Description |
|-------|---------|:---------:|-------------|
| **Auth** | `auth`, `otp` | 6 | Email register/login, Google OAuth, phone OTP (Firebase) |
| **Users** | `users` | 4 | Profile CRUD, account management |
| **Reports** | `reports`, `comments`, `ml` | 10 | Flood reports with photo upload, voting, comments, ML classification |
| **Flood Data** | `hotspots`, `rainfall`, `predictions`, `historical_floods`, `floodhub`, `external_alerts` | 22 | Hotspots with FHI, weather data, ML predictions, FloodHub proxy (5 endpoints: status, gauges, forecast, inundation, events), multi-source alerts |
| **Routing** | `routes_api`, `saved_routes`, `daily_routes` | 8 | Route comparison, bookmarks, daily commute tracking |
| **Alerts** | `alerts`, `watch_areas` | 6 | Alert CRUD, watch area management with PostGIS |
| **Social** | `gamification`, `badges`, `reputation`, `leaderboards` | 9 | Points, badges, streaks, leaderboards, privacy controls |
| **Safety** | `circles`, `sos` | 18 | Safety circles CRUD (16 endpoints), members, invites, SOS emergency fanout via Twilio |
| **Search** | `search` | 5 | Unified search: locations, reports, users, suggestions |
| **Messaging** | `webhook`, `whatsapp_meta` | 4 | WhatsApp webhooks — Twilio (TwiML) + Meta Cloud API (Graph API, HMAC-SHA256) |
| **Push** | `push` | 2 | FCM token registration + deletion |
| **IoT** | `sensors` | 6 | Sensor CRUD, readings, API key auth (paused) |

---

## Project Structure

```
FloodSafe/
├── apps/
│   ├── backend/                 # FastAPI backend
│   │   └── src/
│   │       ├── api/             # 32 router modules
│   │       ├── domain/services/ # Business logic (auth, routing, alerts, circles...)
│   │       ├── infrastructure/  # SQLAlchemy models, database
│   │       └── core/            # Config, dependencies
│   ├── frontend/                # React 18 + TypeScript PWA
│   │   ├── android/             # Capacitor Android wrapper (BridgeActivity)
│   │   └── src/
│   │       ├── components/
│   │       │   ├── screens/     # 12 screen components
│   │       │   ├── ui/          # Radix UI primitives
│   │       │   ├── floodhub/    # FloodHub tab
│   │       │   ├── circles/     # Safety Circles
│   │       │   └── onboarding-bot/ # Multilingual guided tour
│   │       ├── contexts/        # 8 React contexts
│   │       ├── hooks/           # Custom hooks (push, SOS queue, etc.)
│   │       └── lib/api/         # API client (fetchJson, uploadFile)
│   ├── ml-service/              # ML prediction service
│   │   └── src/
│   │       ├── models/          # XGBoost, MobileNet, FHI
│   │       ├── features/        # Feature engineering
│   │       └── data/            # Data loading & processing
│   ├── iot-ingestion/           # Sensor ingestion (paused)
│   └── esp32-firmware/          # Arduino firmware (paused)
├── docker-compose.yml
├── CLAUDE.md                    # AI development guide
└── FEATURES.md                  # Feature registry (1100+ lines)
```

---

## City Coverage

| City | Status | Hotspots | Historical Events | FloodHub | Weather Source | Alert Sources |
|------|--------|:--------:|:-----------------:|:--------:|:-------------:|:-------------:|
| **Delhi NCR** | Full | 90 (62 MCD + 28 OSM) | 45 (1969–2023) | 1 CWC gauge | Open-Meteo | All 8 + IMD |
| **Bangalore** | Active | 200 (BBMP official) | — | — | Open-Meteo | GDACS + IMD |
| **Yogyakarta** | Active | 19 | — | — | OWM / Open-Meteo | GDACS + bilingual ID |
| **Singapore** | Active | 60 (PUB official) | — | — | NEA (5min) | PUB + GDACS + Telegram |

FloodSafe supports 4 cities across 3 countries with 369 total hotspots. Delhi has the deepest integration (FloodHub gauge forecasts, 45 historical events, 90 hotspots). Bangalore has 200 official BBMP flood-vulnerable locations across 8 zones. Singapore uses NEA for real-time weather with 5-minute updates. Yogyakarta uses OpenWeatherMap when an API key is configured. Each city has per-city FHI calibration tuned to local elevation, wet season, and urban density — including 14-day exponential decay for soil saturation.

---

## Roadmap

| Tier | Name | Status |
|:----:|------|--------|
| 1 | **Community Intelligence** | Complete — Reports, auth, alerts, onboarding, voting, comments, E2E tests |
| 2 | **ML/AI Foundation** | Complete — XGBoost (AUC 0.98), FHI calculator, MobileNet, external alerts, Google Flood Forecasting API (live), historical floods |
| 3 | **Smart Sensors** | Mostly complete — ESP32 firmware and ingestion built; edge ML not yet implemented. IoT paused |
| 4 | **Smart Features** | Complete — Gamification, safe routing, saved routes, smart search, live navigation |
| 5 | **Messaging** | Complete — WhatsApp dual transport (Twilio + Meta Cloud API), Wit.ai NLU, Meta Llama risk summaries, FCM push notifications, SOS emergency fanout |
| 6 | **Mobile & Offline** | Mostly complete — PWA (Workbox), install banner, offline caching, Capacitor Android wrapper initialized, offline SOS via IndexedDB + Background Sync |

### What's Next (Tier 7: Scale)

- [x] City expansion: Yogyakarta (3rd) + Singapore (4th)
- [x] Bangalore BBMP hotspots (200 official flood-vulnerable locations)
- [x] Per-city weather calibration (NEA, OWM, Open-Meteo)
- [x] FHI 14-day API decay + ceiling-only P95 percentiles
- [x] Telegram channel integration (Singapore)
- [x] Navigation direction arrow + route casing
- [x] FCM push notifications (watch area + circle alert triggers)
- [x] SOS emergency with offline queue (IndexedDB + Background Sync)
- [x] Meta WhatsApp Cloud API (parallel transport alongside Twilio)
- [x] Capacitor Android wrapper (BridgeActivity, WebView)
- [ ] Native Capacitor plugins (push, geolocation, camera)
- [ ] Play Store release
- [ ] Multi-language UI (Hindi, Kannada, Indonesian)
- [ ] GNN for flood propagation modeling
- [ ] Cloud photo storage (S3)
- [ ] Water depth estimation from photos
- [ ] Edge ML on IoT devices

---

## Contributing

FloodSafe is a nonprofit project — contributions are welcome.

1. Read [`CLAUDE.md`](./CLAUDE.md) for development patterns and architecture rules
2. Read [`FEATURES.md`](./FEATURES.md) for the full feature registry (1100+ lines of domain context)
3. Open an issue before starting large changes

**Quality gates** (all must pass before merge):
```bash
cd apps/frontend && npx tsc --noEmit   # Type safety
cd apps/frontend && npm run build       # Production build
cd apps/backend && pytest               # Backend tests
```

---

## License

FloodSafe is a nonprofit project built for social good. Contact for licensing inquiries.

---

<div align="center">
  <sub>Built with purpose. Saving lives through technology.</sub>
</div>
