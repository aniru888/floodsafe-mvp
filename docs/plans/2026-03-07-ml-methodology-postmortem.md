# ML Methodology Post-Mortem: What Works, What Failed, and Why

> FloodSafe ML Transparency Report
> Date: 2026-03-08
> Status: Complete — XGBoost retired, FHI is sole differentiating signal

---

## Executive Summary

FloodSafe attempted 11 distinct ML approaches for flood risk prediction. Through rigorous statistical analysis (GEE profiling pipeline across 5 cities), we discovered that the flagship Delhi XGBoost model (AUC 0.98) was a **rural-vs-urban artifact** — it learned to distinguish urban areas from farmland, not flood-prone locations from safe ones. All terrain-based heuristics similarly failed when restricted to urban-only comparisons.

**What actually works:** FHI (real-time weather formula), MobileNet photo verification, and community reporting. These avoid the fundamental negative sampling problem that plagues all supervised flood ML.

---

## The Fundamental Problem: Negative Sampling Bias

Every supervised flood ML model needs:
- **Positive samples**: Known flood-prone locations (we have these — government hotspot databases)
- **Negative samples**: Known safe locations (we DON'T have these)

The standard workaround — random points within city bounds as negatives — introduces fatal bias. Random points across Delhi include farmland, forest, and water bodies. Any model trivially separates "urban" from "rural" and achieves inflated AUC.

**This is not a FloodSafe-specific problem.** It affects all urban flood ML that uses random negative sampling without land-use filtering.

---

## Catalog of All ML Approaches

### 1. XGBoost Hotspot Classifier (Delhi) — RETIRED

| Metric | Value |
|--------|-------|
| Architecture | XGBoost binary classifier, 18 GEE features |
| Training data | 270 hotspots (positive) + 300 random points (negative) |
| AUC | 0.98 |
| Status | **RETIRED** — urban-vs-rural artifact |

**Evidence of artifact:**
- 89/90 Delhi hotspots scored 0.75-1.0 (mean: 0.952)
- Near-zero differentiation between hotspots
- Top feature: `built_up_pct` (urbanization percentage) — an urban proxy, not a flood predictor
- Cliff's Delta for `built_up_pct`: +0.53 (all background) → -0.15 (urban-only background)

**What it actually learned:** "Is this location in a city?" not "Will this location flood?"

**Code paths:** `apps/backend/src/domain/ml/xgboost_hotspot.py` (kept for training scripts), `apps/backend/data/hotspot_predictions_cache.json` (no longer loaded)

### 2. MobileNet Flood Image Classifier — ACTIVE

| Metric | Value |
|--------|-------|
| Architecture | MobileNetV1 transfer learning + TFLite |
| Model file | `sohail_flood_model.h5` |
| Threshold | 0.3 (safety-first — minimize false negatives) |
| FNR | <2% target |
| Status | **ACTIVE** — validates community report photos |

This works because it's a vision task (does this photo show flooding?) not a geospatial prediction task. Pre-trained on flood imagery, safety-first threshold catches 98%+ of real floods at the cost of some false positives.

### 3. FHI (Flood Hazard Index) Calculator — ACTIVE

| Metric | Value |
|--------|-------|
| Architecture | Weighted heuristic formula |
| Formula | P(35%) + I(18%) + S(12%) + A(12%) + R(8%) + E(15%) |
| Data source | Open-Meteo (Delhi, Bangalore, Indore), NEA (Singapore), OWM (Yogyakarta) |
| Status | **ACTIVE** — sole differentiating risk signal |

Components:
- **P**: Precipitation vs city-specific P95 threshold (35%)
- **I**: Rainfall intensity — current hourly rate (18%)
- **S**: Soil saturation — 14-day exponential decay, per-city k factor (12%)
- **A**: Antecedent rainfall — 3-day burst accumulation (12%)
- **R**: River proximity factor (8%)
- **E**: Elevation-based drainage (15%)

**Why it works:** It measures real-time weather conditions, not static features. It's the only signal that actually varies between hotspots in real-time.

### 4. Historical Severity Scores — STATIC (limited value)

| City | Severity Distribution | Differentiation |
|------|----------------------|-----------------|
| Delhi | Mixed (extreme/high/moderate) | Some variation |
| Bangalore | ALL "high" | Zero |
| Yogyakarta | Mostly "moderate", some "high" | Minimal |
| Singapore | ALL "high" | Zero |
| Indore | ALL "high" | Zero |

3 of 5 cities have uniform severity — this provides zero differentiation. Kept as a baseline `risk_level` display but not a meaningful signal.

### 5. Ensemble v3 (LSTM + LightGBM) — SHELVED

Designed but never trained. Required daily flood occurrence labels at point-level resolution — no public dataset provides this for any of our cities.

### 6. Ensemble v4 (ConvLSTM + GNN + LightGBM) — SHELVED

More sophisticated architecture (spatial graph convolutions + temporal sequences). Same data problem as v3. The architecture was sound but the training data doesn't exist.

### 7. Stacking Ensemble — NOT TRAINED

Meta-learner combining multiple base models. Without trained base models, nothing to stack.

### 8. AlphaEarth Integration — DEPRECATED

Early exploration of Google's AlphaEarth for feature extraction. Superseded by direct GEE access.

### 9. Terrain Heuristics (5 cities) — FAILED

| City | Features (all BG) | Features (urban-only) | Signal Lost |
|------|-------------------|----------------------|-------------|
| Delhi | 4 significant | 1 significant | 75% |
| Bangalore | 5 significant | 2 significant | 60% |
| Singapore | 9 significant | 0 significant | 100% |
| Yogyakarta | 6 significant | 5 significant | 17% |
| Indore | 7 significant | 3 significant | 57% |

Rigorous GEE extraction (elevation, slope, TWI, aspect, land cover) across 5 cities with Cliff's Delta effect sizes and Moran's I spatial autocorrelation. When background points were restricted to urban areas only, most "significant" features collapsed.

**Exception:** Yogyakarta retained 5/6 features — terrain matters for hilly cities with topographic flood corridors. But for flat, densely-built cities (Delhi, Singapore), urban flooding is an infrastructure problem, not a terrain one.

### 10. XGBoost Generalization Attempt — FAILED (AUC 0.71)

Attempted to extend Delhi XGBoost to other cities. AUC dropped from 0.98 to 0.71, confirming the model overfit to Delhi's specific urban-vs-rural boundary, not generalizable flood patterns.

### 11. Community Report Clustering — DESIGNED (not yet trained)

**This is the path forward.** Reports with photos, GPS, and weather → road snapping (OSM) → spatial clustering → candidate hotspot discovery → human review.

No negative sampling needed. Density-based discovery avoids the fundamental problem.

---

## The Profiling Pipeline (Evidence)

**What:** GEE feature extraction for 499 hotspots + 500 background points per city, across 5 cities. Statistical analysis with Cliff's Delta effect sizes (not p-values — at n=500, everything is "significant").

**Key finding — The Smoking Gun:**

Delhi `built_up_pct` (the XGBoost model's #1 feature):
- All background comparison: Cliff's Delta = **+0.53** (large effect — hotspots are more urban)
- Urban-only comparison: Cliff's Delta = **-0.15** (negligible/reversed — hotspots are NOT more urban than other urban areas)

This proves the XGBoost model learned "is this urban?" not "will this flood?"

**Pipeline scripts:** `apps/ml-pipeline/scripts/02_static_profiling.py`, `03_statistical_analysis.py`, `05_temporal_analysis.py`

---

## What Actually Differentiates Flood Risk

Given that terrain features and ML scores don't differentiate between urban hotspots, what does?

1. **Real-time weather** (FHI) — varies hour-by-hour, hotspot-specific via local elevation and drainage
2. **Infrastructure** — storm drain capacity, road grading, construction quality (not measurable from satellite)
3. **Community reports** — actual observed flooding, timestamped with weather conditions
4. **Temporal patterns** — SAR satellite imagery during known flood events (Bangalore AUC 0.926 in profiling pipeline, but requires known event dates)

---

## Recommendations

1. **Keep FHI as primary signal** — it's real-time, weather-responsive, and actually differentiates risk
2. **Invest in community reporting pipeline** — each verified report is one ground-truth data point
3. **After 2-3 monsoon seasons** — enough community data to train genuine event-based models
4. **Consider Yogyakarta terrain model** — the one city where terrain features survived urban-only filtering
5. **SAR temporal analysis** — promising (Bangalore AUC 0.926) but requires known flood event dates as input

---

## Files Changed (2026-03-08)

| File | Change |
|------|--------|
| `apps/backend/src/domain/ml/hotspots_service.py` | Removed XGBoost loading, cache, top_features. Severity-only fallback |
| `apps/frontend/src/components/MethodologyModal.tsx` | New — transparency modal matching landing page aesthetic |
| `apps/frontend/src/components/MapComponent.tsx` | "Base Risk (ML)" → "Known Flood Hotspot" badge + methodology link |
| `apps/frontend/src/lib/api/hooks.ts` | Removed `top_features` from HotspotFeature type |
| `apps/backend/src/domain/ml/xgboost_hotspot.py` | Unchanged — kept for training scripts |
