# FloodSafe ML Pipeline

Offline analysis pipeline for city-specific flood hotspot profiling and community-driven hotspot discovery. These scripts run locally (not on Koyeb).

## Overview

Two independent analysis tracks:

**Part A — Static Feature Profiling** (all 5 cities): Extract GEE physical features (terrain, land cover) for 499 hotspots + 500 background points per city. Statistical comparison to understand what physical characteristics flood-prone locations share.

**Part B — SAR Temporal Contrast** (Bangalore + Yogyakarta): Compare Sentinel-1 SAR imagery at known hotspots during confirmed flood events vs dry periods. SAR captures physical surface water — the only temporal feature that isn't circular.

**Community Pipeline**: Per-city XGBoost training, report enrichment (weather + road snapping), and community report clustering for new hotspot discovery.

## Setup

```bash
cd apps/ml-pipeline
pip install -r requirements.txt
```

Requires:
- GEE service account: `apps/ml-service/credentials/gee-service-account.json`
- Database: `DATABASE_URL` in `.env` (for community pipeline scripts)

## Profiling Pipeline Scripts

| # | Script | Phase | Status |
|---|--------|-------|--------|
| 01 | `01_feature_trial.py` | GEE connectivity gate + feature availability trial | COMPLETE |
| 02 | `02_static_profiling.py` | Batched GEE extraction (reduceRegions) | COMPLETE (7.4 min, 5 cities) |
| 03a | `03_statistical_analysis.py` | Static feature analysis (Cliff's Delta, Moran's I) | COMPLETE (5 cities) |
| 03b | `03_create_event_dates.py` | Flood event date curation (Bangalore + Yogyakarta) | COMPLETE |
| 04 | `04_temporal_extraction.py` | SAR temporal feature extraction | COMPLETE (Bangalore + Yogyakarta) |
| 05 | `05_temporal_analysis.py` | Tiered analysis (descriptive/XGBoost) | COMPLETE (AUC 0.926 Bangalore) |

### Usage

```bash
# Phase 0+1: Feature trial (already run, results in config/)
python scripts/01_feature_trial.py

# Phase 2: Full static extraction — all cities (~22 min with batching)
python scripts/02_static_profiling.py

# Single city
python scripts/02_static_profiling.py --city bangalore

# Resume after interruption
python scripts/02_static_profiling.py --city bangalore --resume

# Background points only (no GEE calls)
python scripts/02_static_profiling.py --bg-only

# Phase 4: Generate event date JSONs
python scripts/03_create_event_dates.py
```

### Key Design Decisions

- **Batched `reduceRegions`**: ~650x fewer GEE API calls vs per-point extraction (~23x faster)
- **Recursive binary split fallback**: When a batch fails, split in half and retry down to single-point level
- **Cliff's Delta** over Cohen's d (no normality assumption for geospatial data)
- **p-values secondary** to effect sizes (n=500 makes everything statistically significant)
- **SAR-only temporal features** (weather features are tautological)
- **Per-city feature whitelists** (what works in hilly Yogyakarta fails in flat Delhi)

## Community Pipeline Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `import_city_roads.py` | Import OSM road network into `city_roads` table | `python scripts/import_city_roads.py --city delhi` |
| `extract_city_features.py` | GEE 18-feature extraction per city hotspots | `python scripts/extract_city_features.py --city delhi` |
| `train_city_xgboost.py` | Train per-city XGBoost with feature importance | `python scripts/train_city_xgboost.py --city delhi` |
| `cluster_reports.py` | Group verified reports by road segment for discovery | `python scripts/cluster_reports.py --city delhi` |
| `backfill_weather.py` | Backfill weather snapshots for old reports | `python scripts/backfill_weather.py` |

## Config Files

| File | Purpose |
|------|---------|
| `config/city_bounds.json` | Bounding boxes for all 5 cities |
| `config/feature_registry.json` | Feature metadata (source, resolution, known issues) |
| `config/{city}_feature_trial.json` | Per-city trial results with `passed_features` list |

## Output Structure

```
output/
  profiles/
    {city}_background_points.json   # 500 per city, quadrant-stratified
    {city}_hotspot_features.npz     # Hotspot GEE features (after extraction)
    {city}_background_features.npz  # Background GEE features (after extraction)
    checkpoints/                    # Resume checkpoints for GEE extraction
  temporal/
    bangalore_event_dates.json      # 15 flood + 7 dry dates
    yogyakarta_event_dates.json     # 12 flood + 7 dry dates
    {city}_temporal_features.npz    # SAR features (after extraction)
```

## Per-City Feature Availability

| Feature | Delhi | Bangalore | Yogyakarta | Singapore | Indore |
|---------|:-----:|:---------:|:----------:|:---------:|:------:|
| elevation | PASS | PASS | PASS | PASS | PASS |
| slope | PASS | PASS | PASS | PASS | PASS |
| aspect | PASS | PASS | PASS | PASS | PASS |
| tpi | PASS | PASS | PASS | PASS | PASS |
| twi | PASS | PASS | PASS | PASS | PASS |
| built_up_pct | PASS | PASS | PASS | PASS | PASS |
| vegetation_pct | PASS | PASS | PASS | PASS | PASS |
| cropland_pct | PASS | PASS | PASS | FAIL | PASS |
| water_pct | FAIL | PASS | FAIL | PASS | PASS |
| bare_pct | PASS | PASS | FAIL | PASS | PASS |
| grass_pct | PASS | PASS | PASS | PASS | PASS |
| wetland_pct | FAIL | FAIL | FAIL | FAIL | FAIL |

Whitelisted features per city: Delhi 10, Bangalore 11, Yogyakarta 9, Singapore 10, Indore 11.

## Design Documents

- [City XGBoost Profiling Design](../../docs/plans/2026-03-07-city-xgboost-profiling-design.md) — Part A+B methodology
- [Community ML Pipeline Design](../../docs/plans/2026-03-05-community-ml-pipeline-design.md) — Learning loop
- [Implementation Status](../../docs/plans/2026-03-07-profiling-implementation-status.md) — Progress tracker
- [Flood Event Dates Research](../../docs/plans/flood-event-dates-research.md) — Source compilation

## Prerequisites

- **GEE extraction**: Service account with Earth Engine API access
- **Road import**: Geofabrik PBF file or Overpass API access
- **Database**: PostgreSQL with PostGIS extension (for community pipeline)
