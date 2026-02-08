<div align="center">
  <img src="apps/frontend/public/pwa-512x512.png" alt="FloodSafe" width="120" />
  <h1>FloodSafe</h1>
  <p><strong>Open-source flood monitoring platform for Indian cities</strong></p>
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

Every monsoon season, Delhi and other Indian cities face devastating urban flooding. The 2023 Yamuna floods displaced over 25,000 people in Delhi alone. Waterlogging paralyzes transportation, endangers lives, and disproportionately impacts low-income communities who rely on public transit and live in flood-prone areas.

**FloodSafe addresses this with four pillars:**

- **Community Intelligence** — Citizens report flooding in real-time with GPS-verified photos, building a crowd-sourced flood map that helps everyone navigate safely.

- **AI-Powered Prediction** — Machine learning models (XGBoost, AUC 0.98) predict waterlogging risk at 90 known hotspots using live weather data, giving people advance warning before they step outside.

- **Safe Routing** — A route planner that avoids high-risk flood zones with 300-meter safety buffers, with live turn-by-turn voice navigation to guide you through safer paths.

- **Multi-Channel Alerts** — Watch area notifications, 7 government and institutional alert sources (IMD, CWC, GDACS), and a WhatsApp bot with Hindi support — meeting people where they already communicate.

FloodSafe is a nonprofit project built for social good.

---

## Features

### Flood Intelligence

| Feature | Description |
|---------|-------------|
| **Flood Hazard Index (FHI)** | Live risk score (0–1) from 6 weather components: `0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E`. Monsoon 1.2x modifier. Sources: Open-Meteo + CHIRPS |
| **Waterlogging Hotspots** | 90 Delhi locations (62 MCD-identified + 28 OSM underpasses) with live FHI-based color coding |
| **XGBoost Risk Model** | 18-feature binary classifier (AUC 0.98) for weather-responsive risk prediction at known hotspots |
| **Flood Photo Classifier** | MobileNet v1 via TFLite, threshold 0.3 (safety-first to minimize false negatives) |
| **Historical Floods** | 45 Delhi NCR events (1969–2023) from the IFI-Impacts dataset, grouped by decade |
| **Google FloodHub** | Yamuna River gauge proxy — Old Railway Bridge, ITO Junction, Okhla Barrage — with 7-day forecasts |
| **External Alerts** | 7 sources: IMD, CWC, RSS feeds, Twitter/X, GDACS, GDELT, news. Severity-scored and deduplicated |

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
| **Metro Integration** | Suggests nearby Delhi Metro stations when routes cross active flood zones |
| **Live Navigation** | Turn-by-turn with voice guidance (Web Speech API), real-time hotspot proximity warnings |
| **Saved Routes** | Bookmark routes with use-count tracking across 3 transport modes (driving, walking, cycling) |

### Alerts & Monitoring

| Feature | Description |
|---------|-------------|
| **Watch Areas** | User-defined monitoring zones with PostGIS spatial queries and custom radius |
| **Push Notifications** | Real-time alert delivery when flood events occur within watch areas |
| **WhatsApp Bot** | Twilio-powered with 9 Quick Reply button types, location-based SOS, photo classification, Hindi support |

### Safety Circles

| Feature | Description |
|---------|-------------|
| **Group Safety** | Create circles with 6-character invite codes, add family and friends |
| **Member Tracking** | Real-time location sharing within circles during flood events |
| **SOS Emergency** | One-tap SOS with offline queue (IndexedDB + Background Sync) and SMS fanout via Twilio |

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
| **Offline SOS** | Emergency SOS queued via IndexedDB when offline, delivered via Background Sync when connectivity returns |

### IoT Sensors (Experimental — Paused)

ESP32-based water level monitoring with dual sensor fusion (capacitive strips + VL53L0X ToF), OLED display, and 100-reading offline buffer. High-throughput ingestion service on port 8001. Currently paused — contributions welcome.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, TypeScript 5, Vite, Tailwind CSS v4, Radix UI, MapLibre GL JS, TanStack Query, Workbox |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, PostGIS |
| **ML / AI** | XGBoost, TensorFlow / MobileNet (TFLite), Google Earth Engine, CHIRPS, Open-Meteo |
| **Database** | PostgreSQL 15 + PostGIS (SRID 4326) |
| **Auth** | Email/Password (bcrypt), Google OAuth, Phone OTP (Firebase) |
| **Maps** | MapLibre GL JS, PMTiles (offline tiles), OpenStreetMap, Photon + Nominatim geocoding |
| **Messaging** | Twilio (WhatsApp + SMS), SendGrid (email) |
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
                         │  27 routers, 80+ endpoints  │
                         │     Clean Architecture      │
                         └───┬──────────┬──────────┬──┘
                             │          │          │
                  ┌──────────▼───┐ ┌────▼─────┐ ┌─▼────────────┐
                  │ PostgreSQL   │ │    ML    │ │     IoT      │
                  │ + PostGIS    │ │  Service │ │  Ingestion   │
                  │  19 tables   │ │ XGBoost  │ │  (Paused)    │
                  │ (Supabase)   │ │ MobileNet│ │  Port 8001   │
                  └──────────────┘ │ FHI Calc │ └──────────────┘
                                   └──────────┘
```

- **Frontend** — 12 screens, 7 React contexts, full PWA with offline support. Hosted on Vercel.
- **Backend API** — 27 router modules following Clean Architecture (`api/` → `domain/services/` → `infrastructure/`). Hosted on Koyeb.
- **ML Service** — XGBoost hotspot risk model, FHI calculator, MobileNet flood classifier. Hosted on Koyeb.
- **Database** — PostgreSQL 15 with PostGIS extensions, 19 tables, UUID primary keys. Hosted on Supabase.

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
git clone https://github.com/your-org/FloodSafe.git
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
| `GCP_PROJECT_ID` | ML | Google Earth Engine access |

---

## API Overview

The backend exposes 27 router modules with 80+ endpoints. Full Swagger docs available at `/docs`.

| Group | Routers | Endpoints | Description |
|-------|---------|:---------:|-------------|
| **Auth** | `auth`, `otp` | 6 | Email register/login, Google OAuth, phone OTP (Firebase) |
| **Users** | `users` | 4 | Profile CRUD, account management |
| **Reports** | `reports`, `comments`, `ml` | 10 | Flood reports with photo upload, voting, comments, ML classification |
| **Flood Data** | `hotspots`, `rainfall`, `predictions`, `historical_floods`, `floodhub`, `external_alerts` | 19 | Hotspots with FHI, weather data, ML predictions, FloodHub proxy, multi-source alerts |
| **Routing** | `routes_api`, `saved_routes`, `daily_routes` | 8 | Route comparison, bookmarks, daily commute tracking |
| **Alerts** | `alerts`, `watch_areas` | 6 | Alert CRUD, watch area management with PostGIS |
| **Social** | `gamification`, `badges`, `reputation`, `leaderboards` | 9 | Points, badges, streaks, leaderboards, privacy controls |
| **Safety** | `circles`, `sos` | 17 | Safety circles CRUD, members, invites, SOS emergency fanout |
| **Search** | `search` | 5 | Unified search: locations, reports, users, suggestions |
| **Messaging** | `webhook` | 2 | WhatsApp webhook (Twilio) |
| **IoT** | `sensors` | 6 | Sensor CRUD, readings, API key auth (paused) |

---

## Project Structure

```
FloodSafe/
├── apps/
│   ├── backend/                 # FastAPI backend
│   │   └── src/
│   │       ├── api/             # 27 router modules
│   │       ├── domain/services/ # Business logic (auth, routing, alerts, circles...)
│   │       ├── infrastructure/  # SQLAlchemy models, database
│   │       └── core/            # Config, dependencies
│   ├── frontend/                # React 18 + TypeScript PWA
│   │   └── src/
│   │       ├── components/
│   │       │   ├── screens/     # 12 screen components
│   │       │   ├── ui/          # Radix UI primitives
│   │       │   ├── floodhub/    # FloodHub tab
│   │       │   └── circles/     # Safety Circles
│   │       ├── contexts/        # 7 React contexts
│   │       ├── lib/api/         # API client (fetchJson, uploadFile)
│   │       └── hooks/           # Custom React hooks
│   ├── ml-service/              # ML prediction service
│   │   └── src/
│   │       ├── models/          # XGBoost, MobileNet, FHI
│   │       ├── features/        # Feature engineering
│   │       └── data/            # Data loading & processing
│   ├── iot-ingestion/           # Sensor ingestion (paused)
│   └── esp32-firmware/          # Arduino firmware (paused)
├── docker-compose.yml
├── CLAUDE.md                    # AI development guide
└── FEATURES.md                  # Feature registry (700+ lines)
```

---

## City Coverage

| City | Status | Hotspots | Historical Events | FloodHub | Alert Sources |
|------|--------|:--------:|:-----------------:|:--------:|:-------------:|
| **Delhi** | Full | 90 (62 MCD + 28 OSM) | 45 (1969–2023) | Yamuna gauges | All 7 |
| **Bangalore** | Basic | — | — | — | Limited |

Expansion to other Indian metros is planned for Tier 7.

---

## Roadmap

| Tier | Name | Status |
|:----:|------|--------|
| 1 | **Community Intelligence** | Complete — Reports, auth, alerts, onboarding, voting, comments, E2E tests |
| 2 | **ML/AI Foundation** | Complete — XGBoost (AUC 0.98), FHI calculator, MobileNet, external alerts, FloodHub, historical floods |
| 3 | **Smart Sensors** | Mostly complete — ESP32 firmware and ingestion built; edge ML not yet implemented. IoT paused |
| 4 | **Smart Features** | Complete — Gamification, safe routing, saved routes, smart search, live navigation |
| 5 | **Messaging** | Complete — WhatsApp bot with Hindi support, Twilio integration |
| 6 | **Mobile & Offline** | Complete — PWA (Workbox), install banner, offline caching, Safety Circles with offline SOS |

### What's Next (Tier 7: Scale)

- [ ] Multi-language UI (Hindi, Kannada)
- [ ] GNN for flood propagation modeling
- [ ] City expansion beyond Delhi and Bangalore
- [ ] Cloud photo storage (S3)
- [ ] Water depth estimation from photos
- [ ] Edge ML on IoT devices

---

## Contributing

FloodSafe is a nonprofit project — contributions are welcome.

1. Read [`CLAUDE.md`](./CLAUDE.md) for development patterns and architecture rules
2. Read [`FEATURES.md`](./FEATURES.md) for the full feature registry (700+ lines of domain context)
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
