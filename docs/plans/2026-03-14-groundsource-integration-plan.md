# Groundsource Historical Flood Data Integration Plan

> Date: 2026-03-14
> Status: PHASE 1 COMPLETE (data downloaded + inspected)
> Source: Google Research Groundsource dataset (Zenodo DOI: 10.5281/zenodo.18647054)
> Parent: `2026-03-14-google-flood-ai-integration-audit.md`

---

## Context

Google's Groundsource project (March 2026) used Gemini to extract 2.6M historical flood events from news articles across 150+ countries (2000-2026). The dataset is CC BY 4.0, available as a 667MB Parquet file on Zenodo.

FloodSafe currently has **zero historical flood data**. External alerts expire after 7 days. This integration gives users 26 years of flood history.

---

## Phase 1: Data Inspection — COMPLETE

### Dataset Verified
| Field | Value |
|-------|-------|
| **File** | `apps/ml-pipeline/data/groundsource/groundsource_2026.parquet` |
| **Size** | 667.1 MB |
| **Records** | 2,646,302 |
| **Date range** | 2000-01-01 to 2026-02-03 |
| **License** | CC BY 4.0 |
| **MD5** | `cd1b5de6508f7aad8e1d1d0dd4cecea6` |

### Schema (6 columns — very sparse)
```
uuid:                string   — Unique event identifier (e.g., "5acc1866dd6644dfa572f02ae3d54aa4")
area_km2:            double   — Flood extent area in km² (range: 0.000002 – 4,998.8, median: 2.0)
geometry:            binary   — WKB-encoded Polygon or MultiPolygon (actual flood boundaries!)
start_date:          string   — Event start date "YYYY-MM-DD"
end_date:            string   — Event end date "YYYY-MM-DD"
__index_level_0__:   int64    — Pandas index artifact (ignore)
```

**What's present**: Spatial polygons (not just points!), dates, area.
**What's missing**: No city, no country, no severity, no death toll, no description, no news URL, no confidence score.

### City Coverage (VERIFIED — all 2.6M WKB centroids parsed)
| City | Events | % of Dataset | Verdict |
|------|--------|-------------|---------|
| **Delhi** | 14,536 | 0.55% | Excellent — large enough for statistical analysis |
| **Bangalore** | 6,342 | 0.24% | Strong |
| **Yogyakarta** | 4,506 | 0.17% | Good — surprising for non-English media city |
| **Singapore** | 3,357 | 0.13% | Good — despite SG's rare severe flooding |
| **Indore** | 864 | 0.03% | Usable but thin |
| **Total (5 cities)** | **29,605** | **1.12%** | All cities viable |

Broader counts: India overall = 447,058 events, Indonesia = 370,156 events.

### Area Statistics
```
count    2,646,302
mean     142.3 km²     — skewed by large events
median   2.0 km²       — most events are localized
25th %   0.13 km²      — many very small (sub-neighborhood)
75th %   21.4 km²      — upper quartile is city-district scale
max      4,998.8 km²   — some events span entire basins
```

### Geometry Format
- WKB-encoded binary (Polygon or MultiPolygon)
- Parseable via `shapely.wkb.loads()`
- Can extract centroids for lat/lng point queries
- Can extract full polygons for map overlay layers
- Example: Row 0 is a MultiPolygon centered at (53.54°N, 8.58°E) — Germany

### Data Quality Observations
- No null values in any column
- Same-day start/end common (single-day events or imprecise dates)
- Area = 0.0 km² exists (point-like events, polygon too small to measure)
- No deduplication visible (same location+date may appear multiple times from different articles)
- Bounding box filtering used 0.5° buffer around city bounds

---

## Architecture Decision: Separate Table

**Decision: New `historical_floods` table, NOT extending `external_alerts`.**

| Consideration | Historical Floods | External Alerts |
|--------------|-------------------|-----------------|
| Lifecycle | Immutable (one-time import) | Expiring (7-14 day TTL) |
| Query pattern | "Floods here 2015-2025" | "Alerts today" |
| Retention | Forever | Auto-cleanup |
| Volume | 29,605 (filtered) | ~100 active |
| Update frequency | Rare (Zenodo version bumps) | Hourly/daily |
| Spatial data | Full polygons (WKB) | Points (lat/lng) |

---

## Phase 2: Database Schema & Import

**Goal**: Create table, build import script.

### Table Design (adapted from verified schema)
```sql
CREATE TABLE historical_floods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL DEFAULT 'groundsource',
    source_id VARCHAR(64) NOT NULL UNIQUE,  -- Groundsource uuid field
    city VARCHAR(50) NOT NULL,              -- Detected from centroid bounding box
    centroid_lat DOUBLE PRECISION NOT NULL,
    centroid_lng DOUBLE PRECISION NOT NULL,
    area_km2 DOUBLE PRECISION NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    -- Store WKB geometry as PostGIS geography for spatial queries
    geom GEOGRAPHY(GEOMETRY, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_hist_city_date ON historical_floods (city, start_date DESC);
CREATE INDEX idx_hist_geom ON historical_floods USING GIST (geom);
CREATE INDEX idx_hist_source_id ON historical_floods (source_id);
```

**Notes**:
- `source_id` = Groundsource `uuid` field (already unique)
- No `country`, `severity`, `description` — dataset doesn't have them
- PostGIS `GEOGRAPHY` type enables `ST_DWithin()` for radius queries
- `geom` stores full polygon — can render on map, not just centroid

### Import Script Design
- File: `apps/backend/scripts/import_groundsource.py`
- Read Parquet with pyarrow (memory-efficient row group iteration)
- Parse WKB geometry → extract centroid → match to city bounding box
- Filter: only import events within our 5 city bounding boxes (+ 0.5° buffer)
- Convert WKB to WKT for PostGIS insertion
- Batch insert: 500 rows per commit
- Dedup: ON CONFLICT (source_id) DO NOTHING
- Expected import: ~29,605 rows
- Estimated time: <5 minutes (Supabase remote)

### Migration Script
- File: `apps/backend/scripts/migrate_add_historical_floods.py`
- Creates table + indexes via Supabase Management API
- Follows existing pattern from `migrate_add_external_alerts.py`

---

## Phase 3: Backend API

**Goal**: Expose historical floods via REST API.

### Endpoints
```
GET /floods/historical
    ?city=delhi                     (required)
    &year_from=2020                 (optional, default: 2000)
    &year_to=2026                   (optional, default: current year)
    &limit=50                       (optional, max 100)
    &offset=0                       (optional)
    → Returns: GeoJSON FeatureCollection with centroids

GET /floods/historical/stats
    ?city=delhi                     (required)
    → Returns: { total, by_year: {2020: 45, 2021: 32, ...}, avg_area_km2 }

GET /floods/historical/nearby
    ?lat=28.6292&lng=77.2064        (required)
    &radius_km=2                    (optional, default 2, max 10)
    &limit=20                       (optional)
    → Returns: GeoJSON FeatureCollection sorted by distance
    → Uses PostGIS ST_DWithin() for spatial query

GET /floods/historical/{source_id}/geometry
    → Returns: Full GeoJSON polygon (for map overlay of single event)
```

### Implementation
- New file: `apps/backend/src/api/historical_floods.py`
- New SQLAlchemy model: `apps/backend/src/infrastructure/models.py` → `HistoricalFlood`
- Router registration: `apps/backend/src/main.py`
- Centroid endpoints use simple lat/lng columns (fast, indexed)
- Full geometry endpoint for individual event polygons (expensive, on-demand)
- TanStack Query caching: `staleTime: 24 * 60 * 60 * 1000` (24h — data is immutable)

---

## Phase 4: Frontend Display

**Goal**: Show historical floods in the app.

### Phase 4a: Hotspot Context (RECOMMENDED FIRST)
When viewing a hotspot detail popup/card:
- Call `GET /floods/historical/nearby?lat=X&lng=Y&radius_km=2`
- Show: "This area flooded **X times** since 2000"
- Expandable list: dates + area_km2
- Validates hotspot placement with real historical data

**Why first**: Lowest effort, highest user value. "This spot flooded 47 times in 26 years" is more compelling than abstract FHI scores.

### Phase 4b: Map Layer (SECOND)
- Toggle "Historical Floods" layer in map controls
- Render centroids as clustered markers
- Color by density (heatmap) or by year
- Click → popup with date, area, link to full polygon
- Full polygon rendering for selected events

### Phase 4c: History Tab (THIRD)
- New tab in AlertsScreen alongside All/Official/News/Social/Community
- Timeline view (year filter)
- City-level stats dashboard
- Chart: floods per year (bar chart)

---

## Phase 5: FHI Weight Optimization

**Goal**: Replace empirical FHI weights with data-driven per-city weights.

### Methodology
1. For each of 499 hotspots, count historical floods within 2km buffer
2. Run FHI calculator → get component values (P, I, S, A, R, E) for each hotspot
3. Build feature matrix: [P, I, S, A, R, E, historical_flood_count] × 499 rows
4. **Per-city PCA**: Identify which components explain most variance in flood frequency
5. **Regression**: historical_flood_count ~ w₁P + w₂I + w₃S + w₄A + w₅R + w₆E
6. Extract optimal weights per city
7. Compare: do data-driven weights produce better FHI scores (higher correlation with actual floods)?

### Validation
- Split: 70% train, 30% test (temporally — train on 2000-2020, test on 2021-2026)
- Metric: Spearman rank correlation between FHI score and flood frequency
- Baseline: current empirical weights (P=0.35, I=0.18, S=0.12, A=0.12, R=0.08, E=0.15)

### Expected Outcomes
- Per-city weight profiles (e.g., Singapore may weight E higher due to flat terrain + flash flood risk)
- Identification of irrelevant components (R = pressure-based runoff is likely weakest)
- Quantified improvement over empirical weights

### Dependencies
- Requires Phase 2 complete (historical data in DB)
- Requires FHI component values for all 499 hotspots
- Can run on static data (no live API needed)

---

## Phase 6: Cross-Validation

**Goal**: Validate Groundsource against our manually curated flood dates.

### Process
1. Load `docs/plans/flood-event-dates-research.md` curated events
2. For each curated event: search Groundsource within ±3 days and 5km radius
3. Calculate:
   - **Hit rate**: % of curated events found in Groundsource
   - **Miss rate**: % of curated events absent (potential Groundsource gaps)
   - **Extra events**: Groundsource events not in our curated list (potential additions)
4. Per-city breakdown
5. Temporal analysis: does Groundsource improve over time (better coverage 2015+ vs 2000-2010)?

### Expected Insights
- Groundsource likely captures major floods (monsoon events with media coverage)
- May miss localized flooding (neighborhood-level, no media coverage)
- Indore likely has worst coverage (smallest city, least English media)

---

## Risks & Mitigations (Updated with Verified Data)

| Risk | Likelihood | Status | Mitigation |
|------|-----------|--------|------------|
| Poor city coverage | ~~Medium~~ **RESOLVED** | All 5 cities have 864-14,536 events | N/A |
| No coordinates | ~~Medium~~ **RESOLVED** | WKB polygons with full boundaries | N/A |
| No severity data | **Confirmed** | Dataset has no severity/impact fields | Use area_km2 as proxy (larger area = more severe) |
| 60% accuracy = noisy data | **Confirmed** | Google's own eval | Show "approximate" label in UI; don't use for real-time alerts |
| 667MB too large for Supabase | Low | Only importing ~29,605 rows (1.12%) | Filtered subset is tiny |
| Duplicate events | **Likely** | Same flood from different articles | Dedup by spatial+temporal proximity during import |
| Single-day precision | **Confirmed** | Many events have start_date = end_date | Accept — day-level precision is sufficient for historical context |
| No news URL/description | **Confirmed** | Dataset has geometry+dates only | Less context for users; compensate with "X floods in this area" aggregate view |

---

## Files to Create/Modify

| File | Action | Phase |
|------|--------|-------|
| `apps/backend/scripts/migrate_add_historical_floods.py` | New: Create table via Supabase API | 2 |
| `apps/backend/scripts/import_groundsource.py` | New: Parquet → PostGIS import | 2 |
| `apps/backend/src/infrastructure/models.py` | Add `HistoricalFlood` SQLAlchemy model | 2 |
| `apps/backend/src/api/historical_floods.py` | New: REST endpoints (4 routes) | 3 |
| `apps/backend/src/main.py` | Register new router | 3 |
| `apps/frontend/src/types.ts` | Add `HistoricalFlood` TypeScript type | 4a |
| `apps/frontend/src/lib/api/hooks.ts` | Add `useHistoricalFloods()` + `useNearbyFloods()` hooks | 4a |
| Hotspot popup component | Add "Past floods in this area" section | 4a |
| Map layer component | Add toggle for historical flood layer | 4b |
| `AlertsScreen.tsx` | Add "History" tab | 4c |
| `apps/backend/scripts/analyze_fhi_weights.py` | New: PCA + regression for weight optimization | 5 |
| `apps/backend/scripts/cross_validate_groundsource.py` | New: Compare vs curated flood dates | 6 |

---

## Dependencies

```
Phase 1 ✅ (inspection) ─── blocks all ──→ Phase 2 (import)
                                              │
                                              ├──→ Phase 3 (API) ──→ Phase 4a (hotspot context)
                                              │                        ├──→ Phase 4b (map layer)
                                              │                        └──→ Phase 4c (history tab)
                                              │
                                              ├──→ Phase 5 (FHI weights) [independent]
                                              └──→ Phase 6 (cross-validation) [independent]
```

Phase 5 and 6 can run in parallel with Phase 3/4, as they only need DB access (not API).
