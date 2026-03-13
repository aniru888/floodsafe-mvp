# Google Flood AI Integration Audit (March 2026)

> Date: 2026-03-14
> Status: COMPLETE (research + fixes deployed)
> Trigger: Google Research blog posts on flash flood forecasting + Groundsource
> Commit: e311da0 (fixes deployed to Koyeb)

---

## Articles Analyzed

| # | Title | URL | Published |
|---|-------|-----|-----------|
| 1 | Protecting Cities with AI-Driven Flash Flood Forecasting | `research.google/blog/protecting-cities-with-ai-driven-flash-flood-forecasting/` | Mar 9, 2026 |
| 2 | Introducing Groundsource: Turning News Reports into Data with Gemini | `research.google/blog/introducing-groundsource-turning-news-reports-into-data-with-gemini/` | Mar 12, 2026 |
| 3 | Gemini: Help Communities Predict Crisis | `blog.google/innovation-and-ai/technology/research/gemini-help-communities-predict-crisis/` | Mar 12, 2026 |

Articles 1+2 are technical; article 3 is a high-level blog tying them together (same content, different audience).

---

## Article 1: Flash Flood Forecasting — Technical Details

### Model Architecture
- **Type**: Recurrent Neural Network (RNN) with LSTM unit
- **Resolution**: 20×20km spatial grid
- **Prediction horizon**: 24 hours advance notice
- **Focus**: Rapid-onset urban flash floods (population density >100/km²)

### Data Sources Used by Google
| Source | Type | Available to FloodSafe? |
|--------|------|------------------------|
| NASA IMERG | 30-min satellite precipitation | YES — on GEE (`NASA/GPM_L3/IMERG_V07`) |
| NOAA CPC | Global gauge-based precipitation | NO — not on GEE, requires NOAA FTP |
| ECMWF IFS HRES | 9km deterministic forecast | NO — not on GEE, needs ECMWF CDS account |
| DeepMind AI weather model | Medium-range forecast | NO — completely closed, no hosted API |
| Urbanization density | Static geographic attribute | YES — via ESA WorldCover on GEE |
| Topography | Static geographic attribute | YES — via USGS SRTM on GEE |
| Soil absorption | Static geographic attribute | YES — via ERA5-Land soil moisture on GEE |

### Performance Metrics
- Manual audit noted precision metrics are "likely underestimates"
- Compared to NWS: NWS recall 22%, NWS precision 44%
- Model achieves "similar results" in most-affected countries
- Countries with <10 ground truth events excluded

### Public Access
- **Model weights**: NOT released
- **API endpoint**: NONE — flash flood predictions served exclusively on Flood Hub website
- **Paper**: EarthArXiv preprint (not peer reviewed), DOI available, 8 downloads as of audit date
- **GitHub**: No repository found at `google-research/groundsource` or similar
- **API discovery**: `floodforecasting.googleapis.com/$discovery/rest` returns 403 (auth-gated)
- **Developer docs**: `developers.google.com/flood-hub/reference` and `/guides` both return 404

### Key Insight
The flash flood LSTM model likely feeds INTO the existing `floodStatus:searchLatestFloodStatusByArea` and `significantEvents:search` API responses — not as a separate endpoint. The API is opaque; the underlying model can change without the endpoint changing. **FloodSafe already consumes these endpoints.**

---

## Article 2: Groundsource — Technical Details

### Pipeline Architecture
```
News article identification (flooding as primary subject)
    → Text extraction via Google Read Aloud user-agent (80 languages)
    → Translation to English (Cloud Translation API)
    → Gemini LLM processing:
        1. Classification (actual floods vs warnings/policy)
        2. Temporal reasoning (relative date anchoring)
        3. Spatial precision (location → Google Maps standardized polygons)
    → Location mapping (Google Maps Platform)
    → Structured dataset compilation
```

### Dataset (VERIFIED — downloaded and inspected)
| Field | Value |
|-------|-------|
| **Zenodo DOI** | 10.5281/zenodo.18647054 (v1), concept DOI: 10.5281/zenodo.18647053 |
| **File** | `groundsource_2026.parquet` (667.1 MB) |
| **Records** | 2,646,302 |
| **Date range** | 2000-01-01 to 2026-02-03 |
| **License** | CC BY 4.0 (free for nonprofit with attribution) |
| **Authors** | 15 researchers (Google, UC Davis, University of Alabama) |
| **Published** | February 15, 2026 |
| **Last modified** | March 12, 2026 |

### Schema (6 columns only — very sparse)
```
uuid:       string    — Unique event identifier
area_km2:   double    — Flood extent area in km²
geometry:   binary    — WKB-encoded polygon/multipolygon (actual flood boundaries!)
start_date: string    — Event start date (YYYY-MM-DD)
end_date:   string    — Event end date (YYYY-MM-DD)
__index_level_0__: int64  — Pandas index artifact
```

**What's MISSING**: No city name, no country, no severity, no death toll, no description, no news URL. Just geometry + dates + area.

### City Coverage (VERIFIED by parsing all 2.6M WKB centroids)
| City | Events | Sample Dates |
|------|--------|-------------|
| **Delhi** | 14,536 | 2001-01-30, 2005-07-26, 2010-07-18... |
| **Bangalore** | 6,342 | 2005-10-22, 2009-10-02, 2013-10-06... |
| **Yogyakarta** | 4,506 | 2006-01-01, 2010-02-02, 2016-11-29... |
| **Singapore** | 3,357 | 2001-12-27, 2004-03-08, 2010-06-16... |
| **Indore** | 864 | 2005-07-26, 2011-07-16, 2017-08-05... |
| **India (all)** | 447,058 | — |
| **Indonesia (all)** | 370,156 | — |

### Area Statistics
```
count    2,646,302
mean     142.3 km²
median   2.0 km²
min      0.000002 km²
max      4,998.8 km²
```

### Accuracy (Google's own evaluation)
- **60%** of extracted events accurate in both location and timing
- **82%** "accurate enough to be practically useful"
- **85-100%** capture rate of severe GDACS events (2020-2026)
- **Limitation**: Urban bias from English-language media; may underrepresent non-English areas

### What's NOT Available
- **Pipeline code**: Not open-sourced, no GitHub repo
- **Real-time API**: No endpoint to query live flood events
- **Companion paper**: Not found on arXiv or Google Scholar (may be under review)

---

## FloodSafe's Current Architecture (Relevant to Integration)

### FloodHub Integration (6 endpoints, all implemented)
| Google API Endpoint | FloodSafe Method | Status |
|---------------------|-----------------|--------|
| `POST /v1/gauges:searchGaugesByArea` | `get_region_gauges()` | Working |
| `POST /v1/floodStatus:searchLatestFloodStatusByArea` | `get_region_flood_statuses()` | Working |
| `GET /v1/gauges:queryGaugeForecasts` | `get_gauge_forecast()` | **Fixed** (was hardcoded "IN") |
| `GET /v1/gaugeModels:batchGet` | `get_gauge_models()` | Working |
| `GET /v1/serializedPolygons/{id}` | `get_inundation_polygon()` | Working |
| `POST /v1/significantEvents:search` | `get_significant_events()` | Working |

**API Key**: Configured in `.env` (`AIzaSyD...`), auth via `?key=` query parameter.

**City Region Codes**: Delhi/Bangalore/Indore → `IN`, Yogyakarta → `ID`, Singapore → `SG`. Country-level fetch, then local bounding box filter.

### FHI Calculator — Two Copies
| Copy | Location | Status | Features |
|------|----------|--------|----------|
| **Backend (canonical)** | `apps/backend/src/domain/ml/fhi_calculator.py` | **Advanced** | Per-city calibration, 14-day API decay, NEA/OWM sources, climate percentiles, circuit breaker, retry |
| **ML-service (simple)** | `apps/ml-service/src/data/fhi_calculator.py` | **Basic** | Open-Meteo only, no per-city calibration (updated with past_days + elevation in this session) |

### FHI Data Sources (Current)
```
REAL-TIME (per request):
├── Open-Meteo Elevation API → elevation in meters
├── Open-Meteo Forecast API → hourly precip, soil moisture, pressure (past 14d + forecast 3d)
├── NEA (Singapore only) → 5-min real-time rainfall from nearest station
└── OWM (Yogyakarta only) → minutely/hourly precip + severe weather alerts

STATIC (loaded once):
├── Per-city climate percentiles JSON → ceiling-only P95 thresholds
└── Per-city calibration dict → elevation bounds, decay constants, wet months, thresholds
```

### External Alerts System (8 fetchers)
| Source | Type | Coverage | Key Detail |
|--------|------|----------|-----------|
| **GDACS** | Official | All cities | UN GeoRSS feed, RED/ORANGE/GREEN severity |
| **GDELT** | News | Country-level | DOC 2.0 API, relevance scoring (0.7 threshold) |
| **RSS** | News | Delhi (7), Bangalore (4) | HT, TOI, IE, NDTV, TheHindu + relevance scoring (0.4) |
| **Twitter** | Social | Delhi, Bangalore | API v2, 1,500 tweets/month free tier |
| **IMD** | Official | Delhi, Bangalore | Weather API, requires IP whitelist |
| **CWC** | Official | Delhi, Bangalore | HTML scraper, polite 2s delays |
| **PUB** | Official | Singapore | REST API, no key needed |
| **Telegram** | Social | Singapore | PUB channel monitoring |

**Key gap**: Forward-looking only. Max 7-day retention. Zero historical data.

### GEE Datasets Currently Used
| Dataset | GEE ID | Used In |
|---------|--------|---------|
| USGS SRTM DEM | `USGS/SRTMGL1_003` | dem_fetcher, static profiling |
| JRC Global Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` | surface_water analysis |
| CHIRPS Daily Precip | `UCSB-CHG/CHIRPS/DAILY` | precipitation analysis |
| ERA5-Land Daily | `ECMWF/ERA5_LAND/DAILY_AGGR` | era5_fetcher, glofas proxy |
| ESA WorldCover v200 | `ESA/WorldCover/v200` | landcover analysis |
| Google Dynamic World | `GOOGLE/DYNAMICWORLD/V1` | near-real-time land cover |
| Sentinel-1 GRD (SAR) | `COPERNICUS/S1_GRD` | flood extent detection |
| Sentinel-2 SR | `COPERNICUS/S2_SR_HARMONIZED` | optical imagery |
| AlphaEarth Embeddings | `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | spatial embeddings |

### GEE Datasets Available But NOT Used
| Dataset | GEE ID | Resolution | Why It Matters |
|---------|--------|-----------|---------------|
| **NASA IMERG V07** | `NASA/GPM_L3/IMERG_V07` | 30-min, 0.1° (~11km) | Same data Google's LSTM uses. 60x better temporal resolution than CHIRPS daily. Early Run has 4-hour latency. |
| **NOAA GFS** | `NOAA/GFS0P25` | 6-hourly, 0.25° (~28km) | 16-day NWP forecast. FloodSafe has NO forecast precipitation from satellite/NWP. Only uses Open-Meteo (statistical model). |
| **ERA5-Land Hourly** | `ECMWF/ERA5_LAND/HOURLY` | Hourly, 0.1° | Sub-daily soil moisture. Currently only use DAILY_AGGR. |
| **GloFAS Reanalysis** | `ECMWF/CEMS_GLOFAS_CONSOLIDATED/V22` | Daily | River discharge data. FloodSafe's glofas.py punted on this — uses ERA5 runoff as proxy. |
| **NOAA PERSIANN-CDR** | `NOAA/PERSIANN-CDR` | Daily, 0.25° | Alternative precipitation, 1983–present. Lower resolution than IMERG. |

### IMERG Technical Notes
- **Versions**: Early Run (~4h lag), Late Run (~12h lag), Final Run (~3.5 month lag)
- **GEE lag**: V07 catalog on GEE may trail NASA release by weeks. Need to verify with `ee.ImageCollection('NASA/GPM_L3/IMERG_V07').sort('system:time_start', false).first()`
- **For FHI real-time**: Would need city-wide grid pre-fetch + cache (can't make 499 GEE calls per request)
- **For ML pipeline offline**: Direct GEE query is fine for training data extraction

### Data Sources NOT Available on GEE
| Source | Access Path | Effort |
|--------|------------|--------|
| NOAA CPC Precipitation | NOAA FTP download or Climate Data Online API | Medium |
| ECMWF IFS HRES Forecast | ECMWF CDS API (free account, rate-limited) or Open Data (0.4°, 10-day) | Medium |
| DeepMind GraphCast | Open-source weights on GitHub, needs ERA5 inputs + GPU | High |
| Google internal flood model | No public access | Impossible |

---

## Fixes Applied (2026-03-14) — Deployed

### FHI Calculator Fixes

**1. Antecedent (A) now uses PAST observed data**
- **Before**: A component computed from `precip_hourly` which was the forecast-only portion. "Antecedent" literally means "what came before" — but was using future predictions.
- **After**: A uses `historical_daily_precip[-3:]` (last 3 days of observed rainfall from `past_days=14` in Open-Meteo call).
- **Impact**: A will now correctly reflect ground saturation from actual rain, not forecasted rain that may not materialize.
- **File**: `apps/backend/src/domain/ml/fhi_calculator.py` line ~701

**2. Correction factor removed from I (Intensity)**
- **Before**: `hourly_max_corrected = hourly_max * correction_factor` — a 20mm/h forecast could become 45mm/h with a 2.25x correction.
- **After**: `I = min(1.0, hourly_max / intensity_threshold)` — raw forecast intensity, no artificial inflation.
- **Rationale**: Correction factor compensates for systematic underestimation in cumulative precipitation forecasts (P component). Point-in-time hourly maximum doesn't have the same systematic bias. Applying it to I artificially inflated flash flood signals.
- **File**: `apps/backend/src/domain/ml/fhi_calculator.py` line ~670

**3. ML-service copy modernized**
- Added `past_days=3` to Open-Meteo call (was forecast-only)
- Split past/forecast arrays (past 72h vs forecast 72h)
- Added per-city elevation bounds dict (was hardcoded to Delhi 190-320m)
- Correction factor only on P (not I or A)
- Added `city` parameter to `calculate_fhi()` and `calculate_fhi_for_location()`
- **File**: `apps/ml-service/src/data/fhi_calculator.py`

### FloodHub Service Fixes

**4. Region bug fixed**
- **Before**: `get_gauge_forecast()` line 520 hardcoded `await self.get_region_gauges("IN")` — Yogyakarta and Singapore gauge site names always showed "Unknown Station".
- **After**: Searches all 3 regions (`IN`, `ID`, `SG`) sequentially until gauge found.
- **File**: `apps/backend/src/domain/services/floodhub_service.py` line ~520

**5. Notification polygon added**
- Added `notification_polygon_id: Optional[str]` field to `GaugeStatus` model.
- Extracts `serializedNotificationPolygonId` from flood status response (the evacuation/notification zone, distinct from inundation probability maps).
- **File**: `apps/backend/src/domain/services/floodhub_service.py` lines 48, 384, 406

**6. `.env.example` updated**
- Added `GOOGLE_FLOODHUB_API_KEY=` with documentation about where to get the key.
- **File**: `apps/backend/.env.example`

---

## Remaining Integration Opportunities (Prioritized)

### Tier 1: Immediately Actionable
| Integration | Effort | Impact | Dependencies |
|-------------|--------|--------|-------------|
| **Groundsource dataset import** | Medium (2-3 days) | High — 26 years of historical floods for all 5 cities | Downloaded, schema inspected. See `2026-03-14-groundsource-integration-plan.md` |
| **FHI weight optimization with PCA** | Medium (1-2 days) | High — replace empirical weights with data-driven per-city weights | Needs Groundsource import + FHI scoring correlation analysis |

### Tier 2: Medium Effort, High Value
| Integration | Effort | Impact | Dependencies |
|-------------|--------|--------|-------------|
| **NASA IMERG for ML pipeline** | Medium (1-2 days) | Medium — better training data for temporal profiling | GEE access (already have), pipeline phases 5-6 |
| **NOAA GFS for FHI enhancement** | Medium (2-3 days) | Medium — NWP forecast supplement | Need city-grid pre-fetch architecture + cache |
| **Groundsource cross-validation** | Low (1 day) | Medium — validate our curated flood dates | Needs Groundsource import |
| **FloodHub notification polygons on map** | Medium (1-2 days) | Medium — show evacuation zones | Backend done, needs frontend InundationLayer |
| **Consolidate FHI calculator copies** | Low (half day) | Medium — eliminate drift between backend/ml-service | Both copies now work but will diverge again |

### Tier 3: Significant Effort
| Integration | Effort | Impact | Dependencies |
|-------------|--------|--------|-------------|
| **Build our own Groundsource** | High (1-2 weeks) | High — real-time LLM-powered flood extraction | Gemini API costs, prompt engineering, GDELT/RSS refactor |
| **GCS inundation history** | Medium (2-3 days) | Medium — 1999-2020 flood maps | Bulk download from `gs://flood-forecasting/inundation_history`, format unknown |
| **ERA5-Land Hourly for FHI** | Medium (1-2 days) | Low — sub-daily soil moisture (5-day lag limits value) | GEE access, FHI architecture change |
| **GloFAS river discharge** | Medium (1-2 days) | Low — relevant only for river-gauge cities | GEE dataset untested, may not cover our specific rivers |

### Not Feasible (Hard Limits)
| Integration | Why Blocked |
|-------------|------------|
| Google's flash flood LSTM model | No API endpoint, no model weights, website-only |
| DeepMind weather model (GraphCast/GenCast) | No hosted API; running locally needs ERA5 pipeline + GPU |
| ECMWF IFS operational forecast via GEE | Not in GEE catalog; separate ECMWF CDS account needed |
| Groundsource real-time pipeline | Internal Google tool, code not released |

---

## FHI Architecture: Known Issues for Future Work

### Dual Calculator Problem
Two independent FHI calculators exist with different feature sets:

| Feature | Backend Copy | ML-Service Copy |
|---------|-------------|----------------|
| Per-city calibration dict | YES (5 cities) | Partial (elevation only) |
| 14-day API decay | YES | NO (3-day only) |
| NEA Singapore real-time | YES | NO |
| OWM Yogyakarta | YES | NO |
| Climate percentiles | YES | NO |
| Circuit breaker | YES | NO |
| Retry with backoff | YES | NO |
| Past/forecast split | YES (fixed) | YES (fixed) |
| Correction factor fix | YES (fixed) | YES (fixed) |

**Recommendation**: Consolidate to single copy. Backend is canonical.

### Correction Factor Analysis
Current correction factor: `base_correction × (1 + prob/100 × boost_multiplier)`

| City | Base | Boost Mult | Range |
|------|------|-----------|-------|
| Delhi | 1.5 | 0.5 | 1.5x – 2.25x |
| Bangalore | 1.5 | 0.5 | 1.5x – 2.25x |
| Yogyakarta | 1.1 | 0.3 | 1.1x – 1.43x |
| Singapore | 1.0 | 0.25 | 1.0x – 1.25x |
| Indore | 1.3 | 0.5 | 1.3x – 1.95x |

**Now only applied to P component** (was previously triple-counted on P, I, A).

### Weight Optimization Path
Current weights are empirically tuned for Delhi with no formal validation:
```
P=0.35, I=0.18, S=0.12, A=0.12, R=0.08, E=0.15
```

**Proposed approach**: Use Groundsource historical flood polygons as ground truth:
1. For each hotspot, count historical floods within 2km buffer
2. Run FHI with current weights, get component values
3. PCA on components × historical frequency → identify which components correlate with actual floods
4. Derive optimal weights per city via regression
5. Compare: do data-driven weights outperform empirical ones?

---

## Key Findings

1. **Google's March 2026 announcements are research publications, not product launches.** No new API endpoints, no model weights, no pipeline code.

2. **The biggest improvement was discovering FHI's antecedent bug** — A component was using forecast data instead of past observed data. A 1-line fix (`past_days` parameter) with more impact than any new data source.

3. **Groundsource dataset is genuinely valuable** — 29,605 events across our 5 cities with actual flood boundary polygons (not just points). 26 years of history FloodSafe completely lacks.

4. **Two GEE datasets (IMERG, GFS) are available but unused** — same data Google's model trains on. Can enhance ML pipeline and potentially FHI, but GEE latency prevents real-time per-point queries.

5. **FloodHub API is complete** — all 6 endpoints implemented, no new ones added by Google. Flash flood predictions feed into existing responses transparently.

6. **The FHI calculator has diverged into two copies** — backend is canonical (advanced), ml-service is basic. Both now have the core fixes but feature sets differ significantly.
