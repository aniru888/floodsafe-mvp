# City-Specific Flood Hotspot Profiling & Temporal Analysis -- Design Document

> Date: 2026-03-07
> Status: Approved
> Author: Brainstorming session (Claude + Anirudh)
> Supersedes: Pillar 1 of `2026-03-05-community-ml-pipeline-design.md`

---

## Overview

Build a two-part analysis pipeline for FloodSafe's 499 hotspots across 5 cities:

1. **Part A -- Static Feature Profiling** (all 5 cities): Extract GEE physical features, statistically compare hotspots against city background to understand what physical characteristics flood-prone locations share. This is the **core deliverable**.
2. **Part B -- SAR Temporal Contrast Analysis** (Bangalore + Yogyakarta only): Compare Sentinel-1 SAR imagery at known hotspot locations during confirmed flood events vs dry periods. SAR captures physical surface water extent -- the only temporal feature that isn't circular. Method scales with data: descriptive analysis for few dates, mixed-effects model for moderate dates, constrained XGBoost for 15+ dates.

Surface results in the frontend ("Why this location floods") and a public methodology page.

### Why Part B Requires SAR (Not Just Weather Features)

Without SAR, the only temporal features are precipitation and soil moisture from ERA5. Comparing weather during floods vs dry spells proves "it floods when it rains" -- a tautology that produces no insight. SAR captures actual surface water presence/absence, which is independent of the weather input and genuinely informative.

### Why Part B Is Limited to Bangalore + Yogyakarta

| City | Post-2014 flood dates | SAR viability | Part B status |
|------|----------------------|---------------|---------------|
| Delhi | 6 | Too few dates for meaningful analysis | Part A only |
| **Bangalore** | **16** | **Strong -- multi-source verified** | **Part B candidate** |
| **Yogyakarta** | **34** (~15-18 effective) | **Strong -- dense event history** | **Part B candidate** |
| Singapore | 8 | Floods subside in 20-60 min; Sentinel-1's 6-12 day revisit will miss them | Part A only (future: PUB sensor study) |
| Indore | 15 (~13 effective) | Borderline -- proceed if Bangalore/Yogyakarta succeed | Part A first, Part B stretch goal |

### Singapore: Independent Study (Future)

Singapore has uniquely rich government data not available in other cities:
- 208 PUB water level sensors (real-time + historical archives)
- PUB flood-prone area reduction records (3,200ha in 1970s -> 28ha today)
- Chow et al. 2016: 30 years of station rainfall + flood correlation analysis
- Insurance claims data (868 claims, S$23M for 2010-2011 Orchard Road events)

This enables a fundamentally different study: using actual ground-truth water level readings instead of satellite imagery. Deferred to a separate design document as it requires different methodology, data pipeline, and PUB data access.

### Design Principles (from CLAUDE.md)

- **No shortcuts**: Every feature verified before use. Every statistical test justified.
- **No assumptions**: Flood dates must be source-verified. No hand-assigned severity as ML targets.
- **No silent fallbacks**: Every exclusion documented with reason. If a city fails, we say so.
- **Fact-checked**: All claims backed by statistical tests with proper corrections.
- **Transparent methodology**: Public page explaining exactly what we did and didn't do.

---

## Context: Why Not Traditional Binary XGBoost?

The existing Delhi XGBoost model (AUC 0.987) has fundamental limitations:

1. **Negative samples are fake** -- Random points 500m+ from hotspots. Could be unobserved flood locations.
2. **Severity labels are hand-assigned** -- From news reports, not measurements. Can't regress on them.
3. **All training samples are monsoon** -- `is_monsoon` has 0 importance because it never varies.
4. **High AUC is misleading** -- Model separates "urban infrastructure" from "random land", not flood risk from non-risk.
5. **SAR features silently fall back to dry defaults** -- When extraction fails, returns -10.0/-17.0/7.0/0.0 without flagging.

### Academic Support for This Approach

- **Temporal contrast** used by SEN12-FLOOD dataset (337 locations, per-date flood/non-flood labels)
- **Presence-only models** (MaxEnt) used for flood susceptibility in Kigali, Rwanda (Angelique et al. 2026, AUC=0.84)
- **SHAP at both training and prediction stages** recommended by Waleed & Sajjad 2024 (J. Flood Risk Management)
- **Negative sampling is a known open problem** -- "Contrast or Diversity" (J. Hydrology, 2025) found neither random nor stratified sampling is optimal
- **No dominant open-source solution exists** for this problem

---

## Hotspot Data (Current State)

| City | Hotspots | Source | Ready for Analysis? |
|------|----------|--------|-------------------|
| Delhi | 90 | MCD Reports + OSM underpasses | Yes |
| Bangalore | 200 | BBMP official flood vulnerable locations | Yes |
| Yogyakarta | 76 | BPBD, DPUPKP, PetaBencana, news | Yes |
| Singapore | 60 | PUB official + flood-prone areas | Yes |
| Indore | 73 | IMC, Free Press Journal, Smart City | Yes |
| **Total** | **499** | | |

All cities now exceed the 50+ hotspot threshold identified in the 2026-03-05 design.

---

## Part A: Static Feature Profiling

### Goal

For each city, extract reliable GEE features for hotspots and background points. Statistically compare distributions. Output: per-hotspot feature profile + per-city summary.

### Phase 0: GEE Connectivity Gate

Before ANY extraction:
1. Authenticate GEE service account
2. Query SRTM elevation at known Delhi point (28.6139N, 77.2090E)
3. Verify result is ~215m +/- 5m
4. If this fails, STOP. Do not proceed with extraction.

### Phase 1: Feature Availability Trial

For each city, extract ALL candidate features for **5 sample hotspots**. Report:
- Actual values returned (not zeros, not NaN)
- Whether values vary between nearby hotspots (or if they share one coarse pixel)
- Data date/staleness

**Candidate features (to be verified, not assumed):**

| Feature | Source | Resolution | Expected Reliability |
|---------|--------|-----------|---------------------|
| elevation | SRTM | 30m | High -- static, global |
| slope | Derived SRTM | 30m | High |
| built_up_pct | ESA WorldCover 2021 | 10m | High |
| impervious_pct | ESA WorldCover 2021 | 10m | High |
| vegetation_pct | ESA WorldCover 2021 | 10m | High |
| water_pct | ESA WorldCover 2021 | 10m | Medium |
| TWI | Derived SRTM | 30m | Low for flat urban |
| TPI, TRI, SPI | Derived SRTM | 30m | Low for flat urban |
| SAR VV/VH | Sentinel-1 | 10m | Unreliable -- 1B dead, gaps |
| Precipitation | CHIRPS 0.05 deg | 5.5km | Coarse -- many hotspots share one pixel |
| NDVI, NDWI | Sentinel-2 | 10m | Cloud contamination in monsoon |

**Pass criteria**: Feature returns real, varying values for 4+ out of 5 sample hotspots.
**Fail criteria**: >20% nulls/zeros, or same value for all 5 hotspots (coarse pixel).

Features are whitelisted **per city**, not globally. A feature that works in hilly Yogyakarta may fail in flat Singapore.

### Phase 2: Full Extraction

For cities/features that passed Phase 1:

1. **Hotspot extraction**: All hotspots in the city
2. **Background extraction**: 500 stratified random points within city bounding box (quadrant-stratified for geographic spread)
3. Same GEE pipeline for both

### Phase 3: Statistical Analysis

**Layer 1 -- Data Quality Checks:**

| Check | Method | Fail Condition |
|-------|--------|---------------|
| Completeness | Count nulls/zeros per feature | >20% missing -> drop feature |
| Spatial autocorrelation | Moran's I (PySAL) | If significant -> use spatial block bootstrap |
| Multicollinearity | VIF | VIF > 5 -> remove or combine features |
| Distribution shape | Shapiro-Wilk | Determines parametric vs non-parametric |

**Layer 2 -- Association Testing:**

| Test | Purpose | Notes |
|------|---------|-------|
| Mann-Whitney U | Central tendency difference | Non-parametric |
| Kolmogorov-Smirnov | Full distribution shape difference | More sensitive than MW |
| Cliff's Delta | Non-parametric effect size | PRIMARY metric -- leads over p-values |
| Spatial block bootstrap (10,000 resamples) | Honest confidence intervals | 1km x 1km blocks preserve spatial correlation |
| Benjamini-Hochberg correction | Multiple comparison correction | Testing 6+ features simultaneously |

**Why Cliff's Delta over Cohen's d**: Cohen's d assumes normality. Geospatial features are bounded, skewed, multimodal. Cliff's Delta makes no distributional assumptions, ranges -1 to +1.

**Why spatial block bootstrap**: Standard bootstrap assumes independence. Spatially clustered hotspots share features due to proximity, not causation. Block bootstrap preserves correlation structure and gives honest CIs.

**Why p-values are SECONDARY**: With n=500 background points, even trivial differences achieve p < 0.001. Effect size (Cliff's Delta) measures magnitude. Methodology page reports effect sizes prominently, p-values as supporting.

**Layer 3 -- If Moran's I is significant (expected):**

Adjust effective degrees of freedom (Clifford et al., 1989). A sample of 90 spatially clustered hotspots may have effective n of ~15-30. Report both "apparent n" and "effective n".

**NOTE: Geodetector REMOVED from design.** It's zone-based, not point-based. Would require discretizing features into arbitrary classes and creating Voronoi polygons. Adds complexity without clear benefit. YAGNI.

### Phase 4: Per-Hotspot Z-Scores

For each hotspot, compute z-score relative to city background for each significant feature:
- z = (hotspot_value - background_mean) / background_std
- Only for features with BH-corrected p < 0.05 AND |Cliff's Delta| > 0.3

### Phase 5: Cross-City Consistency (Bradford Hill #2)

Run the SAME analysis pipeline independently per city. Then compare:
- Do the same features show up as significant across multiple cities?
- Are effect directions consistent (e.g., lower elevation -> flooding in ALL cities)?
- Forest plot of effect sizes across cities

If the same feature is significant in 4-5 cities independently, that's strong evidence toward causation.

### What Part A DOESN'T Claim

- Does NOT predict flood risk at new locations
- Does NOT say "low elevation causes flooding" -- only that hotspots tend to be lower
- Background points are NOT "safe" -- they're "the city average"
- Cannot capture drainage infrastructure, culvert capacity, or maintenance quality
- Correlation, not causation -- documented explicitly

---

## Part B: SAR Temporal Contrast Analysis (Bangalore + Yogyakarta)

### Goal

Compare Sentinel-1 SAR imagery at known hotspot locations during confirmed flood events vs confirmed dry periods. SAR captures physical surface water extent -- the only temporal feature that isn't simply restating "it rained."

### Key Framing

This is NOT "does this place flood?" (spatial prediction).
This IS "can we detect actual surface water at this known flood-prone place during flood events?" (temporal classification using physical remote sensing).

The "negative" isn't a different location -- it's the SAME location on a dry day. This is the cleanest possible contrast.

**Why SAR is required**: Without SAR, temporal features reduce to precipitation and soil moisture from ERA5. Comparing weather during floods vs dry spells is circular -- it proves "flooding correlates with rain," which is a tautology. SAR measures actual water on the ground surface, independent of the weather input.

**Scope**: Part B runs for Bangalore (16 post-2014 dates) and Yogyakarta (34 dates, ~15-18 effective). Indore is a stretch goal if the first two cities succeed. Delhi (only 6 post-2014 dates) and Singapore (floods too brief for SAR capture) are excluded.

### Phase 0: Flood Event Date Collection

**This is the hardest and most critical step. No shortcuts.**

For each city, collect verified flood event dates with source attribution.

**Data sources (ordered by reliability):**

| Tier | Source | Quality |
|------|--------|---------|
| 1 | Government databases (NDMA, BPBD, PUB) | Dated, geolocated, official |
| 2 | Dartmouth Flood Observatory / EM-DAT / GDACS | Dated, approximate location |
| 3 | News archives with specific dates | Dated, named locations |
| 4 | FloodSafe community reports | Dated, geolocated, sparse |

**Flood date sources (research completed -- see `docs/plans/flood-event-dates-research.md`):**

| City | Source Files | Post-2014 Dates | HIGH Confidence | Part B Scope |
|------|------------|-----------------|-----------------|-------------|
| Delhi | `delhi_historical_floods.json` + web search | 6 | 6 | Excluded (too few) |
| Bangalore | Web research (FloodList, Deccan Herald, The Watchers, ORF) | 16 | 12 | **Primary** |
| Yogyakarta | `34 latest floods in Yogyakarta.md` + news archives | 34 (~15-18 effective) | ~15 | **Primary** |
| Singapore | `Singapore-Flood-Data-Sources 2.docx.md` + Mothership/PUB | 8 | 5 | Excluded (too brief for SAR) |
| Indore | Web research (Free Press Journal, Knocksense, Skymet, ANI) | 15 (~13 effective) | 10 | Stretch goal |

**Format per city** (`{city}_event_dates.json`):
```json
{
  "city": "yogyakarta",
  "flood_dates": [
    {
      "date": "2025-03-29",
      "source": "Kompas",
      "url": "https://yogyakarta.kompas.com/read/...",
      "affected_areas": ["Kulon Progo", "Bantul", "Gunungkidul"],
      "severity": "19 locations simultaneously",
      "tier": 3
    }
  ],
  "dry_dates": [
    {
      "date": "2024-07-15",
      "source": "BMKG monthly summary",
      "verification": "< 5mm rainfall recorded in Yogyakarta"
    }
  ],
  "excluded": false,
  "exclusion_reason": null
}
```

**Every date must have a source URL or document reference. No assumed dates.**

**Dry period dates per region:**
- India (Delhi, Bangalore, Indore): January-February (winter, minimal rainfall)
- Yogyakarta: June-August (dry season)
- Singapore: No reliable dry season (rain year-round). Must identify specific low-rainfall weeks from historical weather station data.

**Minimum requirement**: 3 distinct flood event dates spanning 2+ years. Cities below this are excluded from Part B (documented, not silently skipped).

### Phase 1: Feature Availability Trial (Temporal)

For 5 sample hotspots per city, extract temporal features at ONE flood date and ONE dry date.

**Candidate temporal features:**

| Feature | Source | Known Issues |
|---------|--------|-------------|
| SAR VV backscatter | Sentinel-1 GRD | 12-day revisit, may not have image near flood date |
| SAR VH backscatter | Sentinel-1 GRD | Same |
| SAR VV/VH ratio | Derived | Amplifies noise when both low |
| SAR change magnitude | Derived (vs 30-60 day baseline) | Needs baseline image |
| Precipitation 24h | CHIRPS / Open-Meteo historical | CHIRPS daily at 5.5km. Open-Meteo hourly at ~11km |
| Precipitation 3d | Same | Same resolution |
| Precipitation 7d | Same | |
| Max daily 7d | Same | |
| Soil moisture | ERA5-Land (GEE) | 9km resolution -- very coarse |
| NDWI | Sentinel-2 | Fails during monsoon (clouds) |

**Critical validations per feature:**
1. Does the value DIFFER between flood date and dry date?
2. For SAR: is the image within reference_date to reference_date + 7 days? (forward-looking for flood dates, backward-looking for dry dates). Pre-flood SAR won't show water.
3. For precipitation: do different hotspots get different values, or do they share one CHIRPS pixel?
4. For NDWI: is it cloud-free on the flood date?

**SAR default detection (CRITICAL)**: The existing code returns exact defaults (-10.0, -17.0, 7.0, 0.0) when SAR fails. Phase 1 trial MUST check how many samples return these exact values. If >30% hit defaults, SAR is excluded for that city.

**SAR date window fix**: Current code uses 7-day backward lookback. For flood dates, extraction must use reference_date - 2 to reference_date + 7 (forward-looking to catch during + aftermath). For dry dates, standard backward lookback is fine.

### Phase 2: Full Extraction

For all hotspots in cities that passed Phase 0 + Phase 1:
- Extract verified features at each flood date AND each dry date
- Label: 1 (flood date), 0 (dry date)
- Log which actual satellite acquisition dates were used per sample

**Estimated sample sizes (Part B scope: Bangalore + Yogyakarta, Indore stretch):**

| City | Hotspots | Flood dates | Dry dates | Apparent n | Effective n (dates) |
|------|----------|-------------|-----------|------------|-------------------|
| Bangalore | 200 | 13-16 | 5-7 | 3600 | 18-23 |
| Yogyakarta | 76 | 15-18 | 5-8 | 1520-1976 | 20-26 |
| Indore (stretch) | 73 | 10-13 | 5 | 1095-1314 | 15-18 |

**Excluded from Part B:**
- Delhi: Only 6 post-2014 flood dates (insufficient for SAR temporal analysis)
- Singapore: Flash floods subside in 20-60 minutes; Sentinel-1's 6-12 day revisit will miss the flood window entirely. Future independent study using PUB water level sensor data instead.

**IMPORTANT: Effective n = number of independent temporal observations (dates), NOT hotspot-date pairs.** All hotspots on the same date share weather conditions and often the same satellite image. The design reports both "apparent n" and "effective n" in all documentation.

**Label noise acknowledgment**: A city-wide flood date doesn't mean ALL hotspots flooded. Options:
- **A) Accept noise**: If 70%+ of hotspots flood during a major event, signal survives. Document limitation.
- **B) Per-hotspot dates**: Only label positive if that specific location was reported. Cleaner but more data collection.
- **C) Weighted labels**: Hotspots in `affected_areas` get 1.0, others get 0.5. XGBoost supports sample weights.

Decision deferred to implementation based on what the date collection reveals.

### Phase 3: Tiered Analysis Method

**The method scales with available data. Do not force complex models onto insufficient data.**

```
Available dates per city:
  |
  |-- < 8 dates --> TIER 1: Descriptive Analysis Only
  |                   - Box plots per feature, flood vs dry
  |                   - Median + IQR comparisons
  |                   - Per-hotspot: "At Rajwada, median VV was -18.3 dB
  |                     during floods vs -10.1 dB dry"
  |                   - No model. Descriptive statistics valid with small n.
  |
  |-- 8-14 dates --> TIER 2: Mixed-Effects Model
  |                   - Linear mixed model:
  |                     feature ~ condition(flood/dry) + (1|hotspot) + (1|date)
  |                   - Properly handles nested structure
  |                   - Reports: beta coefficients + 95% CI + p-values
  |                   - Per-hotspot random effects = location-level sensitivity
  |                   - Libraries: statsmodels or pymer4
  |
  |-- 15+ dates --> TIER 3: Constrained XGBoost
                     - max_depth=2, n_estimators=30 (shallow, regularized)
                     - Leave-One-Date-Out CV (NOT random split)
                     - If mean AUC < 0.65: fall back to Tier 2
                     - SHAP global (per city) + local (per hotspot)
                     - Permutation importance as cross-check (must agree with SHAP)
```

**Why not XGBoost for all cities**: With depth-5, 100-tree XGBoost (existing Delhi config), you have hundreds of parameters. With 5-10 effective temporal observations, that's fitting hundreds of parameters to 5-10 data points. The model memorizes dates, not conditions. Constrained XGBoost (depth-2, 30 trees) is defensible at 15+ dates. Below that, mixed-effects models are statistically honest.

**Removed from design (statistically invalid with our data):**
- Ljung-Box test (requires time series, we have 5-20 irregular dates)
- Brier score + reliability diagram (too few predictions per bin)
- Unconstrained XGBoost for < 15 dates

### Phase 4: Interpretation

**Tier 1 (Descriptive)**:
- Per-city: feature comparison table (flood median vs dry median)
- Per-hotspot: deviation from city-average contrast
- Visualizations: box plots, violin plots

**Tier 2 (Mixed-Effects)**:
- Fixed effects: which features change significantly flood vs dry
- Random effects per hotspot: which locations show strongest contrast
- "Flooding at Rajwada is most associated with VV backscatter drop (beta = -6.8, 95% CI: [-9.2, -4.4])"

**Tier 3 (XGBoost)**:
- Global SHAP: feature importance ranking per city
- Local SHAP: per-hotspot top 3 triggers
- SHAP dependence plots: non-linear thresholds ("flooding triggers when 3-day rainfall exceeds 48mm")
- Permutation importance must agree with SHAP direction

### Phase 5: Honest Failure Documentation

Every city gets a `failure_report.json` documenting:

| Outcome | What we say |
|---------|-------------|
| Tier 3 AUC >= 0.75 | "Model reliably distinguishes flood from dry conditions" |
| Tier 3 AUC 0.65-0.75 | "Weak signal. Features may be too coarse. Reporting as associations, not predictions." |
| Tier 3 AUC < 0.65 | "Available data cannot distinguish flood from dry at this resolution. Falling back to Tier 2." |
| Tier 2 no significant effects | "Mixed model found no features significantly different flood vs dry. Data resolution limitation." |
| City excluded (< 3 flood dates) | "Insufficient verified flood dates. Requires more historical documentation." |
| Feature excluded (Phase 1) | "[Feature] showed no flood-vs-dry contrast. Excluded. Reason: [SAR gap / CHIRPS pixel / cloud]" |

**No silent fallbacks. Every exclusion logged.**

### Causation Assessment (Bradford Hill Criteria)

| Criterion | Part A | Part B | Combined |
|-----------|--------|--------|----------|
| 1. Strength | Cliff's Delta > 0.5 | Beta coefficient magnitude | Strong if both show large effects |
| 2. Consistency | Same feature significant across 5 cities? | Same triggers across cities? | Strongest criterion we have |
| 3. Specificity | Weak (features correlate with many things) | Moderate (weather -> flooding is specific) | Moderate |
| 4. Temporality | Static features pre-date floods | Weather precedes flooding by hours/days | Strong |
| 5. Dose-response | Need real severity data (biggest gap) | SHAP dependence plots show thresholds | Partial via Part B |
| 6. Plausibility | Water flows downhill, impervious = no infiltration | Heavy rain causes flooding | Strong (established hydrology) |
| 7. Coherence | Consistent with flood literature | Consistent with meteorological science | Strong |
| 8. Experiment | Need before/after infrastructure data | Natural experiment: heavy rain but no flood | Partial |
| 9. Analogy | Well-established globally | Well-established globally | Strong |

**Score: 5-6/9 criteria assessable. Main gaps: dose-response (need real severity data) and experimental (need interventional data).**

---

## Frontend Display

### Hotspot Detail Panel: "Flood Risk Profile"

New section below existing hotspot info:

**Physical Profile (Part A):**
```
Physical Characteristics:
- Elevation: 435m (1.8 std below city average)
- Built-up density: 89% (1.2 std above city average)
- Imperviousness: 82% (0.9 std above city average)

This location sits lower than surrounding areas with high
surface sealing, reducing natural water absorption.
```
- Only features with BH-corrected p < 0.05 AND |Cliff's Delta| > 0.3
- Plain language summary auto-generated from top 2-3 features

**Flood Triggers (Part B, only if analysis passed):**
```
What triggers flooding here:
- 3-day rainfall > 48mm (strongest trigger)
- SAR water detection spike
- Sustained rainfall over 5+ days
```
- Tier 1: "Based on comparison of X flood events and Y dry periods"
- Tier 2: "Based on mixed-effects model of X events"
- Tier 3: "Based on XGBoost analysis of X events (AUC: Y.YY)"
- If Part B failed for this city: section not shown (absent, not degraded)

**City-Level Summary:**
```
Indore Flood Analysis Summary
Top physical factor: Low elevation (Cliff's Delta = -0.72)
Top flood trigger: 3-day cumulative rainfall
Hotspots analyzed: 73 | Flood events studied: 12

Full methodology ->
```

### Methodology Page (`/methodology`)

**Route**: `/methodology` -- new screen
**Rendering**: `react-markdown` with `remark-gfm` plugin
**Content**: `apps/frontend/public/methodology/methodology.md`
**Charts**: Static PNGs from analysis notebooks in `public/methodology/`

**Page sections:**
1. Overview (no jargon, 2-3 paragraphs)
2. Data Sources (table with GEE datasets, resolution, links)
3. Part A methodology + per-city results
4. Part B methodology + per-city results (tier used, model performance)
5. Causation Assessment (Bradford Hill table, honestly scored)
6. "What This Doesn't Tell You" -- explicit limitations
7. References (all papers + data sources cited)

---

## Integration with Existing Pipeline

### No Runtime Changes

All analysis is offline. Backend serves pre-computed JSON files. No new real-time computation.

### Backend Changes

**`apps/backend/src/domain/ml/hotspots_service.py`** -- Modified:
- Load `{city}_hotspot_zscores.json` (Part A)
- Load `{city}_shap_per_hotspot.json` (Part B) if exists
- Add fields: `physical_profile`, `flood_triggers` (null if no analysis)

**`apps/backend/src/api/hotspots.py`** -- Modified:
- New query param: `?include_analysis=true` (default false, backwards compatible)
- New endpoint: `GET /hotspots/methodology/{city}` -- city analysis summary

### Frontend Changes

**New**: `FloodRiskProfile` component in hotspot detail panel
**New**: `MethodologyScreen.tsx` at `/methodology` route
**New**: `public/methodology/` directory (markdown + chart PNGs)

### Delhi Legacy Transition

New analysis coexists with existing Delhi XGBoost predictions cache:
- API response includes `analysis_version: "v1_legacy"` or `"v2_profiling"`
- If Part B Delhi model outperforms legacy, migrate predictions
- Legacy deprecated only after verification

### New ML Pipeline Directory

```
apps/ml-pipeline/
  notebooks/
    01_feature_trial.ipynb               # Phase 0+1: GEE connectivity + feature availability
    02_static_profiling.ipynb            # Part A: extraction + statistical analysis
    03_event_date_collection.ipynb       # Flood date research + verification
    04_temporal_extraction.ipynb         # Part B: temporal feature extraction
    05_temporal_analysis.ipynb           # Part B: tiered analysis (descriptive/mixed/XGBoost)
    06_generate_outputs.ipynb            # Compile JSON + PNG outputs
  scripts/
    extract_city_features.py            # GEE extraction (called from notebooks)
    validate_features.py                # Phase 1 trial validation + SAR default detection
    statistical_tests.py                # Mann-Whitney, KS, Cliff's Delta, Moran's I, VIF, BH
    generate_methodology.py             # Compile per-city results into methodology.md
  config/
    city_bounds.json                    # Bounding boxes per city
    feature_registry.json               # Master feature list with source, resolution, known issues
  requirements.txt                      # scipy, scikit-learn, xgboost, shap, pysal, statsmodels, earthengine-api
  README.md
```

### Execution Order

```
01 -> GEE check + feature trial per city
      GATE: Which features pass? Which cities proceed?

02 -> Part A extraction + statistics
      GATE: Which features are significant?

03 -> Manual research: collect flood dates with sources
      GATE: Does each city have 3+ verified flood dates?

04 -> Part B temporal feature extraction
      GATE: Do temporal features show flood-vs-dry contrast?

05 -> Tiered analysis per city
      GATE: Which tier? AUC threshold for Tier 3?

06 -> Generate all output files for backend/frontend
```

**Each notebook has an explicit GO/NO-GO decision gate.**

---

## Output Files

```
apps/ml-service/data/profiles/
  {city}_feature_trial.json             # Phase 0+1 results
  {city}_background_features.npz        # Background point features
  {city}_hotspot_features.npz           # Hotspot features
  {city}_profile_analysis.json          # Statistical results (Part A)
  {city}_hotspot_zscores.json           # Per-hotspot z-scores

apps/ml-service/data/temporal/
  {city}_event_dates.json               # Verified flood/dry dates with sources
  {city}_temporal_trial.json            # Phase 1 temporal trial
  {city}_temporal_features.npz          # All temporal features
  {city}_temporal_model/
    model.json OR excluded.json         # Tier 3 model or exclusion doc
    metadata.json                       # CV results, tier, performance
    shap_global.json                    # City-level importance (Tier 2-3)
    shap_per_hotspot.json               # Per-hotspot top features
    failure_report.json                 # What failed and why (always present)
  {city}_temporal_analysis.md           # Human-readable narrative

apps/frontend/public/methodology/
  methodology.md                        # Full methodology document
  {city}_feature_comparison.png         # Part A charts
  {city}_temporal_analysis.png          # Part B charts
```

---

## Known Limitations

1. **GEE can't see drainage infrastructure** -- The top predictor (built_up_pct) may just mean "urban areas flood more", which is a tautology since all hotspots are urban.
2. **CHIRPS precipitation is 5.5km resolution** -- Many hotspots share one pixel. Urban flooding is street-scale.
3. **Sentinel-1B failed Dec 2021** -- SAR revisit doubled from 6 to 12 days. Many flood dates won't have same-day SAR.
4. **Effective sample size << apparent** -- All hotspots on same date share weather. Methodology reports both.
5. **Severity labels are hand-assigned** -- Cannot be used as ML targets.
6. **Selection bias** -- Government hotspot lists overrepresent reported/commercial areas.
7. **No confirmed "non-flood" locations** -- Background points are "city average", not "safe".
8. **Singapore excluded from Part B** -- Flash floods subside in 20-60 minutes, far too brief for Sentinel-1's 6-12 day revisit to capture. Future independent study using PUB's 208 water level sensors could provide ground-truth temporal data instead.
9. **Part B without SAR is circular** -- ERA5 precipitation/soil moisture during floods vs dry periods just confirms "it floods when it rains." Only SAR captures physical surface water presence, making it the only non-tautological temporal feature.
10. **Delhi excluded from Part B** -- Only 6 post-2014 flood dates in Sentinel-1 era. Rich pre-2014 history (45 events from IFI-Impacts) is unusable for SAR analysis.

---

## References

### Academic Papers

| # | Citation | DOI |
|---|---------|-----|
| 1 | Angelique et al. (2026). Flood Susceptibility Mapping Using MaxEnt -- Kigali, Rwanda. *J. Flood Risk Mgmt*, 19(1). | [10.1111/jfr3.70191](https://doi.org/10.1111/jfr3.70191) |
| 2 | Waleed & Sajjad (2024). Advancing flood susceptibility prediction -- ML algorithms -- Pakistan. *J. Flood Risk Mgmt*, 18(1). | [10.1111/jfr3.13047](https://doi.org/10.1111/jfr3.13047) |
| 3 | Sun et al. (2022). Urban road waterlogging risk -- source-pathway-receptor -- Shenzhen. *J. Flood Risk Mgmt*, 16(1). | [10.1111/jfr3.12873](https://doi.org/10.1111/jfr3.12873) |
| 4 | Pirone et al. (2026). Urban Flood Modelling According to Available Data -- review. *J. Flood Risk Mgmt*, 19(1). | [10.1111/jfr3.70184](https://doi.org/10.1111/jfr3.70184) |
| 5 | Kurugama et al. (2024). Flood susceptibility -- boosting algorithms -- Sri Lanka. *J. Flood Risk Mgmt*, 17(2). | [10.1111/jfr3.12980](https://doi.org/10.1111/jfr3.12980) |
| 6 | Satapathy & Mishra (2024). Flood susceptibility -- tree-based regression with BWO. *Transactions in GIS*, 28(5). | [10.1111/tgis.13171](https://doi.org/10.1111/tgis.13171) |
| 7 | Hayashi et al. (2026). Critical Review for One-Class Classification. *WIREs Data Mining*, 16(1). | [10.1002/widm.70058](https://doi.org/10.1002/widm.70058) |
| 8 | Negri et al. (2025). ML Models on Temporal and Multi-Sensor Data for Flood Mapping. *Transactions in GIS*, 29(2). | [10.1111/tgis.70028](https://doi.org/10.1111/tgis.70028) |
| 9 | Huang et al. (2025). High-resolution flood probability mapping -- generative ML. *Computer-Aided Civil Eng*, 40(19). | [10.1111/mice.13490](https://doi.org/10.1111/mice.13490) |
| 10 | Contrast or Diversity: Non-Flood Sampling (2025). *Journal of Hydrology*. | [S0022169425003919](https://www.sciencedirect.com/science/article/abs/pii/S0022169425003919) |
| 11 | Inverse-Occurrence Sampling for flood susceptibility (2023). *Remote Sensing*, 15(22). | [mdpi.com/2072-4292/15/22/5384](https://www.mdpi.com/2072-4292/15/22/5384) |
| 12 | K-Means negative sampling for waterlogging susceptibility (2025). *Int. J. Disaster Risk Reduction*. | [S2212420925008027](https://www.sciencedirect.com/science/article/pii/S2212420925008027) |
| 13 | Voronoi-Entropy absence data (2024). *Journal of Hydrology*. | [S0022169424017335](https://www.sciencedirect.com/science/article/abs/pii/S0022169424017335) |
| 14 | PBLC PU Learning -- Urban Flood Susceptibility -- Guangzhou (2022). *Land*, 11(11). | [mdpi.com/2073-445X/11/11/1971](https://www.mdpi.com/2073-445X/11/11/1971) |
| 15 | BSVM for satellite flood mask extrapolation (2021). *Remote Sensing*, 13(11). | [mdpi.com/2072-4292/13/11/2042](https://www.mdpi.com/2072-4292/13/11/2042) |
| 16 | OSSA Sample Enhancement for waterlogging (2024). *J. Environmental Management*. | [S0301479723014706](https://www.sciencedirect.com/science/article/abs/pii/S0301479723014706) |

### Statistical Methods

| Method | Reference |
|--------|-----------|
| Moran's I | Moran (1950). *Biometrika*, 37(1-2). |
| Cliff's Delta | Cliff (1993). *Organizational Research Methods*. |
| Bradford Hill Criteria | Hill (1965). *Proc. Royal Society of Medicine*, 58. |
| Benjamini-Hochberg | Benjamini & Hochberg (1995). *JRSS-B*, 57(1). |
| Spatial block bootstrap | Clifford et al. (1989). *Mathematical Geology*. |

### GitHub Repositories

| Repo | Relevance |
|------|-----------|
| [omarseleem92/Machine_learning_for_flood_susceptibility](https://github.com/omarseleem92/Machine_learning_for_flood_susceptibility) | Berlin urban floods, published Zenodo dataset |
| [ClmRmb/SEN12-FLOOD](https://github.com/ClmRmb/SEN12-FLOOD) | Temporal contrast dataset (337 locations, per-date labels) |
| [ianpdavies/cloudy_flood_prediction](https://github.com/ianpdavies/cloudy_flood_prediction) | Temporal contrast for flood prediction under clouds |
| [WRHGroup/PyLandslide](https://github.com/WRHGroup/PyLandslide) | Susceptibility toolkit with buffer-controlled sampling |
| [cloudtostreet/MODIS_GlobalFloodDatabase](https://github.com/cloudtostreet/MODIS_GlobalFloodDatabase) | Global flood extent polygons from MODIS |

### Project Flood Date Sources

Full research compilation: `docs/plans/flood-event-dates-research.md`

| City | File | Events | Key Sources |
|------|------|--------|-------------|
| Delhi | `apps/backend/data/delhi_historical_floods.json` + web | 45 total (6 post-2014) | IFI-Impacts, CNN, SANDRP, ReliefWeb |
| Bangalore | `docs/plans/flood-event-dates-research.md` | 16 post-2014 | FloodList, Deccan Herald, The Watchers, ORF |
| Yogyakarta | `34 latest floods in Yogyakarta.md` | 34 (2017-2026) | detikJogja, Kompas, ANTARA, CNN Indonesia |
| Singapore | `Singapore-Flood-Data-Sources 2.docx.md` + web | 8 post-2014 | Lin et al. 2021, Mothership.sg, PUB, FloodList |
| Indore | `docs/plans/flood-event-dates-research.md` | 15 post-2014 | Free Press Journal, Knocksense, Skymet, ANI |

---

## Future Work

1. **Accumulate flood dates** -- As more events occur and are documented, cities can upgrade tiers (descriptive -> mixed -> XGBoost).
2. **IoT sensor integration** -- ESP32 water depth sensors provide real flood severity data, solving the dose-response gap (Bradford Hill #5).
3. **Community reports as flood dates** -- Verified reports with timestamps become additional positive labels.
4. **Natural experiment tracking** -- Before/after drainage improvements at specific hotspots.
5. **Migrate hotspots from JSON to DB** -- Enables dynamic hotspot management and proper FK relationships.
6. **Pillar 2 (Community Discovery)** -- Unchanged from 2026-03-05 design. Deferred to post-v1.
7. **Singapore PUB sensor study** -- Independent study using 208 water level sensors, drainage capacity records, and insurance claims data. Different methodology from SAR-based Part B. Requires PUB data access and separate design doc.
