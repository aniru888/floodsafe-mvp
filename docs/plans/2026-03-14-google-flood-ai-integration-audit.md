# Google Flood AI Integration Audit (March 2026)

> Date: 2026-03-14
> Status: COMPLETE (research), IN PROGRESS (implementation)
> Trigger: Google Research blog posts on flash flood forecasting + Groundsource

---

## Articles Analyzed

1. **Flash Flood Forecasting** — LSTM model, 20x20km, 24h horizon, NASA IMERG + ECMWF + DeepMind weather
2. **Groundsource** — Gemini converts news articles to structured flood events (2.6M records, 150+ countries)
3. **Gemini Crisis Prediction** — High-level blog tying both together

## Reality vs. Hype

| Announced | Actually Available | Usable by FloodSafe? |
|-----------|-------------------|---------------------|
| LSTM flash flood model | No API, website-only | NO |
| Groundsource pipeline | Internal Google tool, no code/API | NO |
| Groundsource dataset | YES — 667MB Parquet on Zenodo, CC BY 4.0 | YES |
| DeepMind weather model | Closed, no hosted API | NO |
| NASA IMERG on GEE | YES — `NASA/GPM_L3/IMERG_V07`, 30-min resolution | YES (not yet used) |
| NOAA GFS on GEE | YES — `NOAA/GFS0P25`, 16-day forecast | YES (not yet used) |
| FloodHub API | Same 6 endpoints, no new ones | Already integrated |
| GCS inundation history | Bulk download (1999-2020) | Possibly |

## Fixes Applied (2026-03-14)

### FHI Calculator
1. **Antecedent (A) now uses PAST data** — was using forecast (conceptual error)
2. **Correction factor de-duplicated** — removed from I component, only applies to P
3. **ML-service copy modernized** — past_days, split arrays, per-city elevation

### FloodHub Service
4. **Region bug fixed** — hardcoded "IN" replaced with multi-region search
5. **Notification polygon added** — `serializedNotificationPolygonId` extracted
6. **`.env.example` updated** — added `GOOGLE_FLOODHUB_API_KEY`

## Future Integration Opportunities

### Tier 1: Immediately Actionable
- **Groundsource dataset import** — See `2026-03-14-groundsource-integration-plan.md`
- **Open-Meteo `past_days` parameter** — Already applied (1-line fix)

### Tier 2: Medium Effort, High Value
- **NASA IMERG via GEE** — Pre-compute city-wide precipitation grids nightly, use for FHI validation
- **NOAA GFS via GEE** — Supplement Open-Meteo forecast with NWP model data
- **FHI weight optimization** — Use Groundsource historical data + PCA to derive per-city weights

### Tier 3: Significant Effort
- **Build our own Groundsource** — Use Gemini API to extract flood events from GDELT/RSS (expensive)
- **GCS inundation history** — Download and integrate 1999-2020 flood maps (format unknown)

### Not Feasible
- Flash flood LSTM model (no API access)
- DeepMind weather model (no hosted API)
- ECMWF IFS operational forecast (not on GEE, needs separate account)

## GEE Datasets Available But Not Used

| Dataset | GEE ID | Resolution | Use Case |
|---------|--------|-----------|----------|
| NASA IMERG V07 | `NASA/GPM_L3/IMERG_V07` | 30-min, 0.1deg | Observed precipitation (replaces CHIRPS for flash flood) |
| NOAA GFS | `NOAA/GFS0P25` | 6-hourly, 0.25deg | 16-day precipitation forecast |
| ERA5-Land Hourly | `ECMWF/ERA5_LAND/HOURLY` | Hourly, 0.1deg | Sub-daily soil moisture (upgrade from DAILY_AGGR) |
| GloFAS Reanalysis | `ECMWF/CEMS_GLOFAS_CONSOLIDATED/V22` | Daily | River discharge (untested in FloodSafe) |

## Key Finding

The biggest improvement from this audit was not any Google technology — it was discovering that the FHI's antecedent conditions component was using forecast data instead of past observed data. The `past_days` parameter fix is a 1-line change with more impact than adding any new data source.
