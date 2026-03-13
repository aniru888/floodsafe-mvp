# Groundsource Historical Flood Data Integration Plan

> Date: 2026-03-14
> Status: PLANNING
> Source: Google Research Groundsource dataset (Zenodo DOI: 10.5281/zenodo.18647054)

---

## Context

Google's Groundsource project (March 2026) used Gemini to extract 2.6M historical flood events from news articles across 150+ countries (2000-present). The dataset is CC BY 4.0, available as a 667MB Parquet file on Zenodo.

FloodSafe currently has **zero historical flood data**. External alerts expire after 7 days. This integration would give users 25+ years of flood history for context.

### What We Verified
- Dataset is real and downloadable (single Parquet file, 667MB)
- License: CC BY 4.0 (fully compatible with nonprofit use)
- No schema documentation — must inspect Parquet to determine fields
- No public API — dataset only, no real-time pipeline
- Google's own eval: 60% precise accuracy, 82% practically useful
- 85-100% capture of severe GDACS events

### What We Don't Know Yet
- Exact schema/columns (pending download + inspection)
- City coverage for Delhi, Bangalore, Yogyakarta, Singapore, Indore
- Whether coordinates (lat/lng) are included or just place names
- Severity/impact fields availability

---

## Architecture Decision: Separate Table

**Decision: New `historical_floods` table, NOT extending `external_alerts`.**

Rationale:
- Different lifecycle: historical data is immutable, alerts expire
- Different query patterns: "floods in this area 2015-2025" vs "alerts today"
- Different retention: historical = forever, alerts = 7-14 days
- Different volume: 2.6M historical vs ~100 active alerts

---

## Phase 1: Data Inspection & Filtering (1-2 hours)

**Goal**: Download, inspect schema, filter for our 5 cities.

1. Download Parquet from Zenodo (667MB)
2. Inspect schema with `pyarrow.parquet.read_schema()`
3. Identify coordinate columns (lat/lng) and location text columns
4. Filter for our 5 cities:
   - By coordinates (bounding boxes from `cityConfigs.ts`)
   - By text matching (city names in location fields)
5. Count events per city, per year
6. Assess data quality: duplicates, missing coords, date precision

**Output**: Schema documentation, city coverage report, filtered subset

---

## Phase 2: Database Schema & Import (2-3 hours)

**Goal**: Create table, build import script.

### Table Design (preliminary — adapt after schema inspection)
```sql
CREATE TABLE historical_floods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL DEFAULT 'groundsource',
    source_id VARCHAR(255) UNIQUE,  -- Groundsource internal ID or hash
    city VARCHAR(50),               -- Our city name (delhi, bangalore, etc.)
    country VARCHAR(100),
    location_name VARCHAR(500),
    latitude FLOAT,
    longitude FLOAT,
    event_date DATE,                -- Start date of flood event
    end_date DATE,                  -- End date (if available)
    severity VARCHAR(50),           -- If available from dataset
    description TEXT,
    news_url VARCHAR(2048),         -- Source article URL
    raw_data JSONB,                 -- Full Groundsource record
    created_at TIMESTAMP DEFAULT NOW(),

    -- Indexes for common queries
    INDEX idx_hist_city_date (city, event_date DESC),
    INDEX idx_hist_country (country),
    INDEX idx_hist_location (latitude, longitude)  -- For spatial queries
);
```

### Import Script
- `scripts/import_groundsource.py`
- Read Parquet with pandas
- Filter by bounding boxes for our 5 cities (+ 0.5° buffer)
- Generate `source_id` as SHA256 of (location + date + description)
- Batch insert (1000 rows per commit)
- Report: total imported, per-city counts, date range

---

## Phase 3: Backend API (2-3 hours)

**Goal**: Expose historical floods via REST API.

### Endpoints
```
GET /floods/historical?city=delhi&year_from=2020&year_to=2025
GET /floods/historical/{id}
GET /floods/historical/stats?city=delhi  (count by year, severity breakdown)
GET /floods/historical/nearby?lat=28.6&lng=77.2&radius_km=5
```

### Implementation
- New file: `apps/backend/src/api/historical_floods.py`
- New model: `apps/backend/src/infrastructure/models.py` (add `HistoricalFlood`)
- Pagination: offset/limit with max 100 per page
- Response: GeoJSON FeatureCollection for map display

---

## Phase 4: Frontend Display (3-4 hours)

**Goal**: Show historical floods in the app.

### Option A: New tab in AlertsScreen
- Add "History" tab alongside All/Official/News/Social/Community
- List view with year/severity filters
- Clicking an event centers map on that location

### Option B: Map layer
- Toggle "Historical Floods" layer on map
- Clustered markers (by year or density)
- Popup shows event details

### Option C: Hotspot context (recommended first)
- When viewing a hotspot, show "Past floods in this area"
- Count + list of events within 2km radius
- Validates hotspot placement with real data

**Recommended**: Start with Option C (lowest effort, highest signal), then add A/B later.

---

## Phase 5: FHI Validation (future)

**Goal**: Use historical flood frequency to inform FHI weights.

- Count historical floods per hotspot (2km buffer)
- Correlate with current FHI scores
- Identify hotspots that flooded historically but score low (false negatives)
- Identify hotspots that never flooded but score high (false positives)
- Use PCA or correlation analysis on Groundsource + FHI components to derive data-driven weights per city

**This is a separate workstream** — depends on having sufficient city coverage in Groundsource.

---

## Phase 6: Cross-Validation (future)

**Goal**: Validate Groundsource against our manually curated flood dates.

- Compare `docs/plans/flood-event-dates-research.md` entries against Groundsource
- Calculate overlap: how many of our curated events appear in Groundsource?
- Assess Groundsource quality for our specific cities
- Identify events Groundsource missed (gaps in non-English media coverage)

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Poor city coverage (esp. Indore, Yogyakarta) | Medium | Inspect before building; if <10 events, skip that city |
| No coordinates in dataset | Medium | Geocode location names via Google Maps API; fall back to city centroid |
| 60% accuracy = noisy data | High | Show "approximate" label; don't use for alerts, only for context |
| 667MB too large for Supabase free tier | Low | Filter to our 5 cities only (~1-5% of 2.6M) before import |
| Dataset updates (Zenodo versioning) | Low | One-time import; re-import on major version bumps |

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `apps/ml-pipeline/data/groundsource/` | Download location |
| `scripts/import_groundsource.py` | New: Parquet → PostgreSQL import |
| `apps/backend/src/infrastructure/models.py` | Add `HistoricalFlood` model |
| `apps/backend/src/api/historical_floods.py` | New: REST endpoints |
| `apps/backend/src/main.py` | Register new router |
| `apps/frontend/src/types.ts` | Add `HistoricalFlood` type |
| `apps/frontend/src/lib/api/hooks.ts` | Add `useHistoricalFloods()` hook |
| Frontend component(s) | TBD based on display approach |

---

## Dependencies

- Phase 1 (inspection) blocks all other phases
- Phase 2 requires Phase 1 schema knowledge
- Phase 3 requires Phase 2 table
- Phase 4 requires Phase 3 API
- Phase 5-6 can run in parallel after Phase 1
