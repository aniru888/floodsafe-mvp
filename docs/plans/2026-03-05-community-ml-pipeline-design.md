# Community-Driven ML Pipeline — Design Document

> Date: 2026-03-05
> Status: Approved
> Author: Brainstorming session (Claude + Anirudh)

---

## Overview

Build a two-pillar ML pipeline that leverages FloodSafe's community flood reports and per-city XGBoost models to:

1. **Understand** why each city's hotspots flood (city-specific XGBoost feature importance)
2. **Discover** new flood-prone locations from verified community report clusters

These are independent pillars. XGBoost uses physical features only (GEE-derived). Community reports provide ground truth for spatial discovery. They do not feed into each other initially.

---

## Pillar 1: City-Specific XGBoost Models

### Goal

Train the same 18-feature XGBoost model (currently Delhi-only) for Bangalore, Yogyakarta, Singapore, and Indore. Surface per-city and per-hotspot feature importance in the frontend.

### Current State (Delhi)

- 62 MCD hotspots + 28 OSM underpasses = 90 total
- 18 GEE-extracted features (terrain, precipitation, land cover, SAR)
- AUC 0.987, top predictor: `built_up_pct` (15.6%)
- Pre-computed predictions in `hotspot_predictions_cache.json`

### Per-City Hotspot Data

| City | Current Hotspots | Source | Action Needed |
|------|-----------------|--------|---------------|
| Delhi | 90 | MCD + OSM | Already trained |
| Bangalore | 200 | BBMP official | GEE extraction + training. Verify coordinates are road-accurate |
| Yogyakarta | 19 | Manual research | **Too few.** Find BPBD flood data, BMKG records, academic studies. Target: 50+ |
| Singapore | 60 | PUB official | GEE extraction + training. Verify coordinates |
| Indore | 37 | Manual research | **Verify coordinates are on roads (not approximations).** Find IMC/NDMA data. Target: 50+ |

### Pre-requisites

1. **Yogyakarta**: Research BPBD (Badan Penanggulangan Bencana Daerah) flood-prone area data, academic flood mapping studies, recurring waterlogging news reports. Need 30+ more hotspots.
2. **Indore**: Verify all 37 hotspot coordinates are accurate and on actual roads. Research IMC flood data, NDMA reports, monsoon waterlogging archives. Add more if found.
3. **All cities**: Snap existing hotspot coordinates to nearest OSM road to verify accuracy. Flag any >50m from a road.

### Pipeline (offline scripts)

1. `extract_city_features.py` — One-time GEE feature extraction (18 features) per city's hotspots
2. `train_city_xgboost.py` — Train separate XGBoost model per city
3. Output: `{city}_xgboost/` model directory + `{city}_predictions_cache.json`
4. Output includes: per-city feature importance rankings, per-hotspot top contributing features

### Frontend Display

In the hotspot detail panel:

- **"Why this location floods"** section with top 3 contributing features
  - Example: "High urban density (23%) - Low elevation (18%) - Poor drainage terrain (15%)"
- **City-level summary**: "Top flood driver in Delhi: Urban built-up density"
- Data source: pre-computed in predictions cache JSON (no runtime computation)

### Concern: Small Sample Cities

Yogyakarta (19) and Indore (37) may have too few hotspots for robust XGBoost training. Options:
- Accept lower confidence and document the limitation
- Use simpler model (logistic regression) for cities with <30 hotspots
- Prioritize data collection to reach 50+ before training

---

## Pillar 2: Community Report Discovery Pipeline

### Goal

Use verified community flood reports to discover new flood-prone locations not in existing hotspot databases. Reports are enriched with weather and road data at creation time, then clustered offline to find candidates.

### Section A: Report Data Enrichment (Backend — at report creation)

**Weather Snapshot** — Single Open-Meteo API call (~100ms):
- Fields: `precipitation_mm`, `precipitation_probability`, `hourly_intensity_max`, `soil_moisture`, `surface_pressure_hpa`, `temperature_c`, `relative_humidity`, `rainfall_3d_mm`, `rainfall_7d_mm`
- Stored as `weather_snapshot` JSONB field on report

**Road Snapping** — PostGIS query (~50ms):
- Query `city_roads` table: nearest road within 200m
- Store: `road_segment_id` (FK), `road_name`, `road_type`
- If no road within 200m: store NULL (report still saved, just not road-linked)

**Archive Window Change**:
- `REPORT_ARCHIVE_DAYS` changes from 3 to 5
- Map shows last 5 days of reports
- All reports persist indefinitely in DB for ML pipeline
- Single constant change — all 8 query locations in `reports.py` use this constant
- No frontend changes needed (server-filtered)

**New DB fields on `reports`:**
```sql
ALTER TABLE reports ADD COLUMN weather_snapshot JSONB DEFAULT NULL;
ALTER TABLE reports ADD COLUMN road_segment_id UUID DEFAULT NULL;
ALTER TABLE reports ADD COLUMN road_name VARCHAR DEFAULT NULL;
ALTER TABLE reports ADD COLUMN road_type VARCHAR DEFAULT NULL;
```

### Section B: PostGIS Road Network (One-time per city)

**Purpose**: Enable road snapping for reports + validate existing hotspot coordinates.

**Data source**: OpenStreetMap via Geofabrik PBF extracts (more reliable than Overpass API for large cities).

**Road types imported**: motorway, trunk, primary, secondary, tertiary, residential, unclassified, service. Also tagged: `is_underpass` (tunnel=yes), `is_bridge` (bridge=yes).

**New `city_roads` table:**
```sql
CREATE TABLE city_roads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city VARCHAR NOT NULL,
    osm_id BIGINT,
    name VARCHAR,
    road_type VARCHAR NOT NULL,
    is_underpass BOOLEAN DEFAULT FALSE,
    is_bridge BOOLEAN DEFAULT FALSE,
    geometry tiger.geometry(GEOMETRY, 4326) NOT NULL,
    elevation_avg FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_city_roads_geometry ON city_roads USING GIST(geometry);
CREATE INDEX ix_city_roads_city ON city_roads(city);
```

Note: Uses `tiger.geometry` for Supabase schema compatibility (gotcha #12).

**Import all roads within city bounding box** — maximize coverage for snapping accuracy and negative example generation.

**Estimated storage**: ~15MB total across 5 cities (well within Supabase 500MB free tier).

**Road snapping query:**
```sql
SELECT id, name, road_type, is_underpass,
       ST_Distance(geometry::geography,
                   ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) as distance_m
FROM city_roads
WHERE city = :city
  AND ST_DWithin(geometry::geography,
                 ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, 200)
ORDER BY distance_m
LIMIT 1;
```

### Section C: Hotspot Discovery (Offline clustering script)

**Algorithm**: Group verified reports by `road_segment_id`, count per segment.

Why not DBSCAN: Since reports are already snapped to road segments, grouping by segment ID is simpler, more interpretable, and directly meaningful. No hyperparameter tuning needed.

**Candidate threshold**: Road segments with 3+ verified reports = candidate hotspot.

**Verified reports only**: IoT-verified (score >= 80) OR manually verified OR ML `is_flood=true`.

**Per candidate, compute**:
- Centroid (average lat/lng of reports in cluster)
- Report count, date range
- Average water depth across reports
- Average weather conditions (from weather_snapshot — honest summary, not a statistical score)
- Road name and type

**3-tier promotion:**
1. **Tier 1 — Threshold**: 3+ verified reports on same road segment = candidate
2. **Tier 2 — Context**: Show weather conditions at report times for human review (no fake correlation scores — with 3-5 data points, statistical tests are meaningless)
3. **Tier 3 — Manual review**: Admin reviews candidates. If approved, added to city hotspot data + gets GEE feature extraction

**New `candidate_hotspots` table:**
```sql
CREATE TABLE candidate_hotspots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city VARCHAR NOT NULL,
    road_segment_id UUID REFERENCES city_roads(id),
    centroid tiger.geometry(POINT, 4326) NOT NULL,
    road_name VARCHAR,
    report_count INTEGER NOT NULL,
    report_ids UUID[],
    avg_water_depth VARCHAR,
    avg_weather JSONB,
    date_first_report TIMESTAMP,
    date_last_report TIMESTAMP,
    status VARCHAR DEFAULT 'candidate',  -- candidate, approved, rejected
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    promoted_to_hotspot_name VARCHAR,    -- name of official hotspot if approved
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_candidate_hotspots_city ON candidate_hotspots(city);
CREATE INDEX ix_candidate_hotspots_status ON candidate_hotspots(status);
CREATE INDEX ix_candidate_hotspots_geometry ON candidate_hotspots USING GIST(centroid);
```

**Selection bias limitation (documented)**: Community reports are biased toward areas where people commute. Low-traffic residential areas, industrial zones, and outskirts are underrepresented. This is inherent to crowd-sourced data and cannot be fixed by the pipeline alone.

### Section D: Feedback Loop

Once a city accumulates enough approved candidates (bringing total hotspots to 50+), retrain that city's XGBoost model with the expanded dataset. This closes the loop: reports -> discovery -> more training data -> better predictions.

---

## Infrastructure

### Koyeb Backend (free tier: 0.1 vCPU, 256MB RAM)

Only lightweight operations at report creation:
- Weather snapshot: single Open-Meteo HTTP call (~100ms)
- Road snapping: single PostGIS query (~50ms)
- Total overhead per report: ~150-200ms — well within free tier for infrequent report submissions

### Offline Scripts (run locally)

All heavy computation is offline:
- GEE feature extraction
- XGBoost training
- Report clustering
- OSM road import
- Weather backfill for old reports

No new servers needed. Scripts connect directly to Supabase.

### Supabase (free tier: 500MB)

New tables: `city_roads` (~15MB), `candidate_hotspots` (~1MB), plus new columns on `reports`.
Current usage must be verified before migration but estimated to be well within limits.

---

## Project Structure

```
apps/ml-pipeline/                    # NEW directory
  scripts/
    import_city_roads.py             # OSM road import per city -> Supabase
    extract_city_features.py         # GEE feature extraction per city
    train_city_xgboost.py            # XGBoost training per city
    cluster_reports.py               # Group reports by road segment, flag candidates
    backfill_weather.py              # Backfill weather snapshots for old reports
  requirements.txt
  README.md

apps/backend/src/
  domain/services/
    weather_snapshot_service.py      # NEW: Open-Meteo snapshot for report enrichment
    road_snapping_service.py         # NEW: PostGIS nearest road query
  infrastructure/
    models.py                        # MODIFIED: new fields on Report, new CityRoad + CandidateHotspot models
  api/
    reports.py                       # MODIFIED: enrichment calls at creation, REPORT_ARCHIVE_DAYS=5
  scripts/
    migrate_ml_pipeline.py           # NEW: DB migration for new tables + columns

apps/backend/data/
  {city}_predictions_cache.json      # MODIFIED: add feature importance per hotspot

apps/frontend/src/
  components/
    HotspotDetailPanel.tsx           # MODIFIED: add "Why this location floods" section
```

---

## Data Flow

```
User submits flood report
        |
        v
Backend enriches:
  - Weather snapshot (Open-Meteo)
  - Road snapping (PostGIS)
        |
        v
Stored in DB (persists indefinitely)
        |
        +---> Map display (5-day window)
        |
        +---> Offline: cluster_reports.py
        |         |
        |         v
        |     candidate_hotspots table
        |         |
        |         v
        |     Human review -> approve/reject
        |         |
        |         v
        |     If approved: add to city hotspots
        |                   + GEE extraction
        |                   + retrain XGBoost
        |
        +---> Offline: train_city_xgboost.py
                  |
                  v
              Per-city feature importance
                  |
                  v
              Frontend: "Why this location floods"
```

---

## Known Limitations

1. **XGBoost doesn't generalize to unknown locations** (AUC drops to 0.71). It works for classifying known hotspots, not discovering new ones. Discovery relies on report clustering.
2. **Small-sample cities** (Yogyakarta 19, Indore 37) may produce overfit models. Need more data before training is meaningful.
3. **Report selection bias**: Crowd-sourced data overrepresents commuter routes and commercial areas.
4. **Weather enrichment adds ~150ms to report creation**. Acceptable for infrequent submissions but would need caching if report volume increases significantly.
5. **Road snapping depends on OSM completeness**. Some city roads (especially new developments or informal settlements) may not be in OSM.
6. **Supabase tiger schema**: All geometry columns must use `tiger.geometry()` for Management API compatibility.
7. **No real-time discovery**: Candidates are identified when offline clustering script runs, not in real-time.

---

## Future Work

1. **Migrate hotspots from JSON to DB table** — Enables proper FK from `candidate_hotspots.promoted_to_hotspot_id` to a `hotspots` table. Also enables dynamic hotspot management without code changes.
2. **Admin dashboard for candidate review** — Map-based UI for approving/rejecting candidate hotspots. Deferred to post-v1.
3. **Automated retraining trigger** — When approved candidates reach a threshold, auto-trigger XGBoost retraining.
4. **Report density normalization** — Adjust candidate scoring for population/traffic density to reduce selection bias.
5. **Road segment elevation profiles** — Compute min/max elevation along road segments for better underpass detection.
