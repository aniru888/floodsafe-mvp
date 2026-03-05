# FloodSafe ML Pipeline

Offline scripts for the community-driven ML pipeline. These run locally (not on Koyeb).

## Setup

```bash
cd apps/ml-pipeline
pip install -r requirements.txt
```

Requires a `.env` file with `DATABASE_URL` pointing to Supabase (or local DB).

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `import_city_roads.py` | Import OSM road network into `city_roads` table | `python scripts/import_city_roads.py --city delhi` |
| `extract_city_features.py` | GEE 18-feature extraction per city hotspots | `python scripts/extract_city_features.py --city delhi` |
| `train_city_xgboost.py` | Train per-city XGBoost with feature importance | `python scripts/train_city_xgboost.py --city delhi` |
| `cluster_reports.py` | Group verified reports by road segment | `python scripts/cluster_reports.py --city delhi` |
| `backfill_weather.py` | Backfill weather snapshots for old reports | `python scripts/backfill_weather.py` |

## Prerequisites

- **Road import**: Geofabrik PBF file or Overpass API access
- **GEE extraction**: `earthengine authenticate` (Google Earth Engine)
- **Database**: PostgreSQL with PostGIS extension
