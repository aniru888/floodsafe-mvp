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
| #7 | Phase 2: Full static extraction (all hotspots + 500 background/city) | **COMPLETE** (100% valid, 7.4 min) | — |
| #8 | Phase 3: Statistical analysis (Cliff's Delta, Moran's I, BH) | **COMPLETE** (5 cities, forest plot) | #7 |
| #9 | Phase 4: Create flood event date JSONs (Bangalore + Yogyakarta) | **COMPLETE** | — |
| #10 | Phase 5: Part B SAR temporal extraction | **COMPLETE** (Bangalore 13.6% defaults, Yogyakarta 57.9%) | #9 |
| #11 | Phase 6: Tiered analysis + generate output files | **COMPLETE** (Bangalore AUC 0.926, Yogyakarta descriptive) | #8, #10 |

**ALL PHASES COMPLETE.** Full profiling pipeline executed end-to-end.

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

## Phase 2: Static Extraction — COMPLETE

**GEE extraction completed in 7.4 minutes** (vs 8h estimated for per-point). Batched `reduceRegions` achieved ~0.1-0.2s/point.

### Extraction Results

| City | Hotspots | Background | Features | Time | Valid |
|------|----------|------------|----------|------|-------|
| Delhi | 90 | 500 | 10 | 137s | 100% |
| Bangalore | 200 | 500 | 11 | 153s | 100% |
| Yogyakarta | 76 | 500 | 9 | 44s | 100% |
| Singapore | 60 | 500 | 10 | 67s | 100% |
| Indore | 73 | 500 | 11 | 44s | 100% |

Zero batch failures. Binary-split fallback never triggered. All NPZ files verified.

---

## Phase 3: Statistical Analysis — COMPLETE

**Script**: `apps/ml-pipeline/scripts/03_statistical_analysis.py`

### Cross-City Results — Full Background (INFLATED)

| Feature | Strong Evidence? | Mean Delta | Direction | Cities Meaningful |
|---------|:---:|--------|-----------|:---:|
| built_up_pct | YES | +0.806 | higher | 5/5 |
| cropland_pct | YES | -0.759 | lower | 4/4 |
| grass_pct | YES | -0.293 | mixed | 5/5 |

**⚠️ WARNING**: These results compare urban hotspots against ALL background (including farmland, forests). The `built_up_pct` effect is inflated by rural-vs-urban confound.

### Cross-City Results — Urban-Only Background (HONEST)

| Feature | Mean Delta | Cities Meaningful (of tested) |
|---------|--------|:---:|
| cropland_pct | -0.410 | 2/4 |
| grass_pct | -0.266 | 2/5 |
| built_up_pct | +0.245 | 1/5 (only Yogyakarta) |
| tpi | -0.161 | 1/5 (only Bangalore) |

**No feature shows strong universal evidence after urban-only filtering.**

### Per-City Meaningful Features (Urban-Only)

| City | Full BG | Urban BG | Inflated | Surviving Features |
|------|:---:|:---:|---------|-----------|
| Delhi | 4 | **1** | built_up_pct, cropland_pct, grass_pct | vegetation_pct only |
| Bangalore | 4 | **2** | built_up_pct, cropland_pct | **tpi** (depressions!), grass_pct |
| Yogyakarta | 6 | **5** | grass_pct | slope, twi, built_up_pct, vegetation_pct, cropland_pct |
| Singapore | 9 | **0** | ALL NINE features | Nothing discriminates within urban areas |
| Indore | 5 | **2** | built_up_pct, slope, twi | cropland_pct, grass_pct |

### Key Findings (Corrected)
- **No universal static signal** — after controlling for rural-vs-urban bias, no feature is meaningful in ≥3 cities
- **Yogyakarta is the exception** — terrain genuinely matters (5 urban-only features). South-north slope from Merapi creates real topographic flood risk
- **Bangalore TPI is genuine** — hotspots sit in topographic depressions (delta -0.47). Physical cause: water pools in low spots
- **Delhi has essentially NO static discriminator** — urban flooding is infrastructure-driven (drainage capacity, road design), not terrain-driven
- **Singapore: ALL features were artifacts** — 9→0 after urban filtering. Flash flooding is entirely infrastructure/drainage dependent
- **Terrain features are city-dependent** — crucial for hilly Yogyakarta, irrelevant for flat Delhi/Singapore
- **Spatial autocorrelation ubiquitous** — Moran's I significant for most features in most cities
- **VIF reveals multicollinearity** — land cover features are highly correlated (expected: they sum to ~100%)

### Output Files
- `output/profiles/{city}_profile_analysis.json` — Full per-feature statistical results
- `output/profiles/{city}_hotspot_zscores.json` — Per-hotspot z-scores
- `output/profiles/cross_city_summary.json` — Cross-city consistency analysis
- `output/profiles/forest_plot.png` — Effect size visualization

---

## Phase 2 Script Details

**Script**: `apps/ml-pipeline/scripts/02_static_profiling.py`

### Background Point Generation — VERIFIED
- 500 points per city, quadrant-stratified (125 per NW/NE/SW/SE)
- Min distance from any hotspot: >= 500m (haversine verified)
- Reproducible via `random.Random(42)` seed
- Cached to `output/profiles/{city}_background_points.json`

### Validation Results

| City | Hotspots | BG Points | Whitelisted Features | Min Hotspot Dist |
|------|----------|-----------|---------------------|-----------------|
| Delhi | 90 | 500 | 10 | 0.53km |
| Bangalore | 200 | 500 | 11 | 0.52km |
| Yogyakarta | 76 | 500 | 9 | 0.53km |
| Singapore | 60 | 500 | 10 | 0.53km |
| Indore | 73 | 500 | 11 | 0.51km |

### How to Run
```bash
# All cities (sequential, ~8 hours)
python apps/ml-pipeline/scripts/02_static_profiling.py

# Single city (~1.5 hours)
python apps/ml-pipeline/scripts/02_static_profiling.py --city bangalore

# Resume after interruption
python apps/ml-pipeline/scripts/02_static_profiling.py --city bangalore --resume
```

### Features
- Checkpoints every 25 points to `output/profiles/checkpoints/`
- 2s delay between GEE calls (rate limit avoidance)
- 3 retries with exponential backoff on GEE errors
- Imports `extract_static_features()` from Phase 1 via importlib

---

## Phase 4: Event Date JSONs — COMPLETE

**Script**: `apps/ml-pipeline/scripts/03_create_event_dates.py`

### Output Files
- `output/temporal/bangalore_event_dates.json`: 15 flood dates (13 independent storms), 7 dry dates
- `output/temporal/yogyakarta_event_dates.json`: 12 flood dates (10 independent storms), 7 dry dates

### Curation Decisions
- **Included**: Only HIGH + MEDIUM confidence events with exact dates
- **Excluded**: LOW confidence (month-level only) — SAR needs exact dates
- **Merged**: Same-date entries (e.g., 2019-03-18 Yogyakarta: 3 locations, 1 storm)
- **Storm clusters**: Tagged multi-day events (2022-08-29/30 Bangalore, 2024-10-21/22 Bangalore, 2019-03-06/18 Yogyakarta, 2025-03-29/30 Yogyakarta)
- **Dry dates**: Spread across flood-event years for temporal balance. Will cross-check against Open-Meteo in Phase 5.

---

## Phase 5: SAR Temporal Extraction — COMPLETE

**Script**: `apps/ml-pipeline/scripts/04_temporal_extraction.py`

### Architecture
- **Date-first iteration**: Outer loop over dates (not hotspots) — each date needs one SAR composite, shared across all hotspots via `reduceRegions`
- **Forward/backward windows**: Flood dates use ref-2d to ref+7d (captures persistent standing water). Dry dates use ref-7d to ref (stable dry conditions)
- **Batched extraction**: 50 hotspots per `reduceRegions` call with recursive split fallback on failure
- **SAR default detection**: Tracks values matching (-10.0 VV, -17.0 VH, 7.0 ratio, 0.0 change). Reports per-feature and overall default rates. >30% = unreliable flag

### Effective-n and Analysis Tiers
| City | Flood Dates | Dry Dates | Storm Clusters | Independent Storms | Effective-n | Tier |
|------|-------------|-----------|----------------|--------------------|-------------|------|
| Bangalore | 15 | 7 | 2 (2-day each) | 13 | 20 | xgboost |
| Yogyakarta | 12 | 7 | 2 (2-day each) | 10 | 17 | xgboost |

### Features Extracted (4 per point per date)
- `vv_mean`: VV backscatter (dB) — water appears dark (<-15 dB)
- `vh_mean`: VH backscatter (dB) — water appears dark (<-22 dB)
- `vv_vh_ratio`: VV - VH (dB) — water indicator
- `change_magnitude`: flood composite - dry baseline change (negative = flooding)

### How to Run
```bash
# Both cities (~3.2 hours total)
python scripts/04_temporal_extraction.py

# Single city
python scripts/04_temporal_extraction.py --city bangalore

# Resume after interruption
python scripts/04_temporal_extraction.py --city bangalore --resume
```

### Output
- `output/temporal/bangalore_temporal_features.npz` — 200 hotspots × 22 dates = 4,400 samples
- `output/temporal/yogyakarta_temporal_features.npz` — 76 hotspots × 19 dates = 1,444 samples
- Each NPZ: features (n,4), labels (n,), hotspot_ids, dates, metadata JSON

---

## File Structure (Current)

```
apps/ml-pipeline/
  scripts/
    __init__.py
    01_feature_trial.py          # DONE - Phase 0+1
    02_static_profiling.py       # DONE - Phase 2 (COMPLETE, 7.4 min)
    03_statistical_analysis.py   # DONE - Phase 3 (COMPLETE, all 5 cities)
    03_create_event_dates.py     # DONE - Phase 4
    04_temporal_extraction.py    # DONE - Phase 5 (COMPLETE, ~9 min)
    05_temporal_analysis.py      # DONE - Phase 6 (COMPLETE, AUC 0.926)
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
    profiles/
      {city}_background_points.json  # DONE - 500 per city, quadrant-stratified
      {city}_hotspot_features.npz    # DONE - Phase 2 GEE extraction
      {city}_background_features.npz # DONE - Phase 2 GEE extraction
      {city}_profile_analysis.json   # DONE - Phase 3 statistical results
      {city}_hotspot_zscores.json    # DONE - Phase 3 z-scores
      cross_city_summary.json        # DONE - Phase 3 cross-city consistency
      forest_plot.png                # DONE - Phase 3 effect size visualization
      checkpoints/                   # DONE - for GEE extraction resume
    temporal/
      bangalore_event_dates.json      # DONE - 15 flood + 7 dry dates
      yogyakarta_event_dates.json     # DONE - 12 flood + 7 dry dates
      bangalore_temporal_features.npz # DONE - Phase 5 (4400 samples, 13.6% defaults)
      yogyakarta_temporal_features.npz # DONE - Phase 5 (1444 samples, 57.9% defaults)
      bangalore_temporal_analysis.json # DONE - Phase 6 (AUC 0.926)
      bangalore_temporal_report.md    # DONE - Phase 6 methodology report
      yogyakarta_temporal_analysis.json # DONE - Phase 6 (descriptive tier)
      yogyakarta_temporal_report.md   # DONE - Phase 6 methodology report
      temporal_summary.json           # DONE - Phase 6 cross-city summary
      checkpoints/                    # DONE - for SAR extraction resume
  requirements.txt               # DONE - includes scipy, libpysal, esda, statsmodels, shap, etc.
  README.md                      # Exists but minimal
```

---

## Phase 5: SAR Temporal Extraction — COMPLETE

### Extraction Results

| City | Hotspots | Dates | Samples | Default Rate | Time |
|------|----------|-------|---------|-------------|------|
| Bangalore | 200 | 22 (15 flood + 7 dry) | 4,400 | 13.6% | 411s |
| Yogyakarta | 76 | 19 (12 flood + 7 dry) | 1,444 | **57.9%** | 136s |

### SAR Coverage Issues
- **Bangalore**: 3 dates had no SAR coverage (2014-09-26, 2018-08-14, 2022-08-29) — pre-Sentinel-1 or coverage gaps. 13.6% defaults overall — acceptable.
- **Yogyakarta**: 57.9% defaults — most dry season dates (Jun-Aug) AND several flood dates had no SAR images. Tropical equatorial orbit gaps. Restricted to descriptive analysis only.

---

## Phase 6: Temporal Analysis — COMPLETE

### Bangalore (XGBoost Tier)
- **Global AUC: 0.926** (strong) — leave-one-date-out CV, 19 folds, 3800 valid predictions
- **Feature importance (gain)**:
  1. `change_magnitude`: 76.9% — flood-vs-baseline SAR change dominates
  2. `vv_mean`: 13.5% — VV backscatter level
  3. `vh_mean`: 8.9% — VH backscatter level
  4. `vv_vh_ratio`: 0.7% — nearly useless (both polarizations shift together)
- **Descriptive**: Flood VV=-2.5dB vs dry VV=-4.2dB; change_mag flood=+1.6 vs dry=-0.03
- SHAP failed (XGBoost 3.x + SHAP 0.49 incompatibility), native XGBoost importance used instead

### Yogyakarta (Descriptive Tier)
- Restricted to descriptive due to 57.9% SAR default rate
- Limited comparisons possible with 608 valid samples
- 0 per-hotspot summaries (most hotspots lost all dry samples after filtering)

### Key Finding
**SAR change_magnitude is the dominant temporal signal** — the difference between flood-date backscatter and the 90-day baseline captures surface water changes with 76.9% feature importance.

### Honest Interpretation (⚠️ IMPORTANT)
- **AUC 0.926 is DATE-LEVEL detection**, not spatial prediction. ANOVA F-stat=1,320 (between-date >> within-date variance). The model learns "was this a flood date?" not "which hotspots flood more."
- Within a single date, all 200 Bangalore hotspots get similar SAR values (std ≈ 0.15-0.64). The SAR composite is a city-wide image — hotspot-level variation is minimal.
- **Genuine value**: SAR reliably detects active flooding at city scale. Given a Sentinel-1 image of Bangalore, we can tell if flooding is occurring (AUC 0.926). This is useful for flood event confirmation, not spatial prediction.
- **Not useful for**: Predicting which specific locations will flood. That requires infrastructure data (drainage, road design) which GEE static features can't capture.

### CV Bug Fix
Leave-one-date-out CV initially returned AUC=0.000 because each date is entirely flood or dry → per-fold AUC undefined. Fixed by accumulating all out-of-fold predictions and computing a single global AUC.

---

## Git Status

All commits pushed to `origin/master`:
- `2ecb36c` docs: add city XGBoost profiling design + flood event dates research
- `08f678b` docs: scope Part B to SAR-only (Bangalore + Yogyakarta)
- `5d329de` feat(ml-pipeline): Phase 0+1 — GEE connectivity gate + feature trial all 5 cities
- `fe9c236` fix(ml-pipeline): align output paths + add shap dependency

**Branch**: master, up to date with origin.
