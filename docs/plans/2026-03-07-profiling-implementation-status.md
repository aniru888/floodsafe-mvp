# City XGBoost Profiling — Implementation Status

> Date: 2026-03-07
> Design doc: `docs/plans/2026-03-07-city-xgboost-profiling-design.md`
> Flood dates research: `docs/plans/flood-event-dates-research.md`

---

## Phase 0+1: GEE Connectivity Gate + Feature Trial — COMPLETE

**Commit**: `5d329de` (pushed to GitHub)
**Script**: `apps/ml-pipeline/scripts/01_feature_trial.py`
**Config files created**: `apps/ml-pipeline/config/`

### Phase 0 Result
- GEE service account authenticated (`apps/ml-service/credentials/gee-service-account.json`)
- SRTM elevation at Delhi (28.6139N, 77.2090E) = **214m** (expected ~215m) — PASS

### Phase 1 Results — Feature Availability Per City

| Feature | Delhi | Bangalore | Yogyakarta | Singapore | Indore |
|---------|-------|-----------|------------|-----------|--------|
| elevation | PASS | PASS | PASS | PASS | PASS |
| slope | PASS | PASS | PASS | PASS | PASS |
| aspect | PASS | PASS | PASS | PASS | PASS |
| tpi | PASS | PASS | PASS | PASS | PASS |
| twi | PASS | PASS | PASS | PASS | PASS |
| built_up_pct | PASS | PASS | PASS | PASS | PASS |
| vegetation_pct | PASS | PASS | PASS | PASS | PASS |
| cropland_pct | PASS | PASS | PASS | FAIL (0%) | PASS |
| water_pct | FAIL (0%) | PASS | FAIL (0%) | PASS | PASS |
| bare_pct | PASS | PASS | FAIL (0%) | PASS | PASS |
| grass_pct | PASS | PASS | PASS | PASS | PASS |
| wetland_pct | FAIL | FAIL | FAIL | FAIL | FAIL |

**7 universally passed**: elevation, slope, aspect, tpi, twi, built_up_pct, vegetation_pct
**1 universally failed**: wetland_pct (0% everywhere, dropped)

### Key Observations From Trial Data

- **Delhi**: Very flat (214-225m, 11m range). TPI near zero. Terrain indices likely weak discriminators.
- **Bangalore**: Best variation. Elevation 849-895m. Built-up 34-100% (peri-urban to dense core). TPI -3.3 to +0.1 captures depressions.
- **Yogyakarta**: Clear south-north elevation gradient (84-133m over ~5km, Merapi slope toward coast). Dense built-up (75-98%).
- **Singapore**: Surprising slope variation (3-12deg). No cropland (expected). Low elevation (9-30m).
- **Indore**: Good elevation range (548-570m). Mix of urban (49-98% built-up) + cropland (0-38%).

### GEE Gotcha Discovered
ESA WorldCover (`ESA/WorldCover/v200`) is an **ImageCollection**, not a single Image. Must use `ee.ImageCollection().mosaic()`. SRTM is a single Image. Always check asset type before querying.

---

## Cross-Verification Fixes — COMPLETE

**Commit**: `fe9c236` (pushed to GitHub)

### Issues Found and Fixed
1. **Output path mismatch** — Design said `apps/ml-service/data/profiles/` but pipeline lives in `apps/ml-pipeline/`. Fixed: outputs go to `apps/ml-pipeline/output/{profiles,temporal}/`, final JSONs copied to `apps/backend/data/` by Phase 6.
2. **Missing `shap` dependency** — Added to `apps/ml-pipeline/requirements.txt`. Needed for Part B SHAP analysis.
3. **Directory structure in design doc** — Updated to reflect actual implementation (scripts not notebooks, correct file names).

---

## Current Task List

| ID | Task | Status | Blocked By |
|----|------|--------|------------|
| #7 | Phase 2: Full static extraction (all hotspots + 500 background/city) | pending | — |
| #8 | Phase 3: Statistical analysis (Cliff's Delta, Moran's I, BH) | pending | #7 |
| #9 | Phase 4: Create flood event date JSONs (Bangalore + Yogyakarta) | pending | — |
| #10 | Phase 5: Part B SAR temporal extraction | pending | #9 |
| #11 | Phase 6: Tiered analysis + generate output files | pending | #8, #10 |

**#7 and #9 can run in parallel** (independent).

---

## What Each Pending Phase Needs

### Phase 2 (Task #7): Full Static Extraction
- **Script to create**: `apps/ml-pipeline/scripts/02_static_profiling.py`
- **Input**: Hotspot JSONs from `apps/backend/data/{city}_waterlogging_hotspots.json`
- **Per city**: Extract whitelisted features for ALL hotspots + 500 stratified random background points
- **Background point strategy**: Quadrant-stratified within city bounding box, min 500m from any hotspot
- **Output**: `apps/ml-pipeline/output/profiles/{city}_hotspot_features.npz` + `{city}_background_features.npz`
- **GEE call pattern**: Same `extract_static_features()` from `01_feature_trial.py`, batched
- **Estimated time**: ~10s/point x (499 hotspots + 2500 background) = ~8 hours total. Can parallelize by city.
- **Feature whitelist per city**: Use `config/{city}_feature_trial.json` → `passed_features` list

### Phase 3 (Task #8): Statistical Analysis
- **Script to create**: `apps/ml-pipeline/scripts/02_static_profiling.py` (second half, or separate `statistical_tests.py`)
- **Input**: .npz files from Phase 2
- **Per city, per whitelisted feature**:
  1. Data quality: null counts, Shapiro-Wilk normality
  2. Spatial autocorrelation: Moran's I (libpysal/esda)
  3. Association: Mann-Whitney U, KS test, Cliff's Delta (PRIMARY effect size)
  4. Multiple correction: Benjamini-Hochberg
  5. Per-hotspot z-scores (only for features with BH p<0.05 AND |Delta|>0.3)
  6. VIF multicollinearity check
- **Cross-city**: Forest plot of effect sizes, Bradford Hill consistency check
- **Output**: `{city}_profile_analysis.json`, `{city}_hotspot_zscores.json`

### Phase 4 (Task #9): Flood Event Date JSONs
- **Script to create**: `apps/ml-pipeline/scripts/03_create_event_dates.py`
- **Input**: Research from `docs/plans/flood-event-dates-research.md`
- **Output**: `apps/ml-pipeline/output/temporal/{city}_event_dates.json` for Bangalore + Yogyakarta
- **Format**: `{"city": "...", "flood_dates": [{date, source, url, affected_areas, severity, tier}], "dry_dates": [{date, source, verification}]}`
- **Dry dates**: India Jan-Feb, Yogyakarta Jun-Aug (from BMKG records)

### Phase 5 (Task #10): SAR Temporal Extraction
- **Script to create**: `apps/ml-pipeline/scripts/04_temporal_extraction.py`
- **Scope**: Bangalore (16 dates) + Yogyakarta (34 dates, ~15-18 effective)
- **Per hotspot x date**: Extract Sentinel-1 VV, VH, VV/VH ratio, change magnitude
- **SAR date window**: Flood dates use forward-looking (ref-2d to ref+7d), dry dates use backward lookback
- **CRITICAL**: Check for SAR defaults (-10.0, -17.0, 7.0, 0.0). If >30% hit defaults, SAR excluded for that city.
- **Output**: `{city}_temporal_features.npz` with labels (1=flood, 0=dry)

### Phase 6 (Task #11): Analysis + Outputs
- **Tiered analysis** based on effective date count: <8 descriptive, 8-14 mixed-effects, 15+ constrained XGBoost
- **Generate**: methodology.md, chart PNGs, frontend-ready JSONs
- **Copy final files** to `apps/backend/data/` and `apps/frontend/public/methodology/`

---

## File Structure (Current)

```
apps/ml-pipeline/
  scripts/
    __init__.py
    01_feature_trial.py          # DONE - Phase 0+1
    extract_city_features.py     # Legacy (from community pipeline design)
    train_city_xgboost.py        # Legacy
    cluster_reports.py           # Legacy (community pipeline)
    import_city_roads.py         # Legacy (community pipeline)
    backfill_weather.py          # Legacy (community pipeline)
  config/
    city_bounds.json             # DONE - 5 cities
    feature_registry.json        # DONE - feature metadata
    bangalore_feature_trial.json # DONE - trial results
    delhi_feature_trial.json     # DONE
    yogyakarta_feature_trial.json # DONE
    singapore_feature_trial.json # DONE
    indore_feature_trial.json    # DONE
  output/
    profiles/.gitkeep            # DONE - empty, awaiting Phase 2
    temporal/.gitkeep            # DONE - empty, awaiting Phase 4-5
  requirements.txt               # DONE - includes scipy, libpysal, esda, statsmodels, shap, etc.
  README.md                      # Exists but minimal
```

---

## Git Status

All commits pushed to `origin/master`:
- `2ecb36c` docs: add city XGBoost profiling design + flood event dates research
- `08f678b` docs: scope Part B to SAR-only (Bangalore + Yogyakarta)
- `5d329de` feat(ml-pipeline): Phase 0+1 — GEE connectivity gate + feature trial all 5 cities
- `fe9c236` fix(ml-pipeline): align output paths + add shap dependency

**Branch**: master, up to date with origin.
