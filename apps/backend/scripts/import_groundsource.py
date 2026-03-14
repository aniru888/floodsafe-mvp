"""
Groundsource Import Pipeline
==============================
1. Load 667MB Parquet file (2.6M events with WKB geometry polygons)
2. Extract centroids from WKB geometry via shapely
3. Filter to 5 cities by bounding box
4. Filter out events > 10 km² (basin-wide) and < 0.001 km² (artifacts)
5. Spatial-temporal deduplication (5km radius, 3-day window)
6. Insert deduped episodes into historical_flood_episodes table

Actual Parquet schema (verified 2026-03-14):
  - uuid: str (event ID)
  - area_km2: float64 (flood extent)
  - geometry: bytes (WKB Polygon/MultiPolygon — NOT lat/lng!)
  - start_date: str (YYYY-MM-DD)
  - end_date: str (YYYY-MM-DD)

Run locally: DATABASE_URL=... python scripts/import_groundsource.py [path/to/file.parquet]
Default path: apps/ml-pipeline/data/groundsource/groundsource_2026.parquet
"""
import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta
from shapely import wkb
from sklearn.cluster import DBSCAN
import psycopg2
from psycopg2.extras import execute_values

# Column names matching actual Parquet schema
LAT_COL = "centroid_lat"   # Derived from WKB geometry centroid
LNG_COL = "centroid_lng"   # Derived from WKB geometry centroid
DATE_COL = "start_date"
AREA_COL = "area_km2"
ID_COL = "uuid"

# Dedup parameters (from spec § 5.1)
DEDUP_RADIUS_KM = 5.0       # 5km radius
DEDUP_TIME_DAYS = 3          # ±3 days window
MAX_AREA_KM2 = 10.0          # Filter basin-wide events
MIN_AREA_KM2 = 0.001         # Filter geocoding artifacts

# Merapi exclusion zone for Yogyakarta
MERAPI_LAT = -7.54
MERAPI_LNG = 110.44
MERAPI_EXCLUSION_KM = 15.0

# City bounding boxes WITH +0.5° buffer (spec line 299)
CITY_BOUNDS = {
    "delhi": {"lat_min": 27.90, "lat_max": 29.38, "lng_min": 76.34, "lng_max": 77.85},
    "bangalore": {"lat_min": 12.35, "lat_max": 13.65, "lng_min": 76.95, "lng_max": 78.25},
    "yogyakarta": {"lat_min": -8.45, "lat_max": -7.20, "lng_min": 109.80, "lng_max": 111.00},
    "singapore": {"lat_min": 0.70, "lat_max": 1.97, "lng_min": 103.10, "lng_max": 104.50},
    "indore": {"lat_min": 22.12, "lat_max": 23.32, "lng_min": 75.28, "lng_max": 76.45},
}

# Default parquet path relative to project root
DEFAULT_PARQUET = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "ml-pipeline", "data", "groundsource", "groundsource_2026.parquet"
)


def extract_centroids(df):
    """Extract lat/lng centroids from WKB geometry column using shapely.

    The Parquet file stores flood extents as WKB Polygon/MultiPolygon bytes.
    We compute the centroid of each polygon for spatial operations.
    """
    print("  Extracting centroids from WKB geometry...")
    lats = []
    lngs = []
    errors = 0
    for i, geom_bytes in enumerate(df["geometry"]):
        try:
            geom = wkb.loads(geom_bytes)
            c = geom.centroid
            lats.append(c.y)
            lngs.append(c.x)
        except Exception:
            lats.append(np.nan)
            lngs.append(np.nan)
            errors += 1
        if (i + 1) % 500_000 == 0:
            print(f"    {i+1:,} / {len(df):,} geometries processed...")

    df[LAT_COL] = lats
    df[LNG_COL] = lngs
    if errors > 0:
        print(f"  WARNING: {errors:,} geometry parse errors (rows dropped)")
        df = df.dropna(subset=[LAT_COL, LNG_COL])
    return df


def filter_to_city(df, city, bounds):
    """Filter dataframe to city bounding box."""
    mask = (
        (df[LAT_COL] >= bounds["lat_min"]) & (df[LAT_COL] <= bounds["lat_max"]) &
        (df[LNG_COL] >= bounds["lng_min"]) & (df[LNG_COL] <= bounds["lng_max"])
    )
    result = df[mask].copy()
    result["city"] = city
    return result


def spatial_temporal_dedup(df, radius_km=DEDUP_RADIUS_KM, time_days=DEDUP_TIME_DAYS):
    """
    Merge events within radius_km AND time_days into single episodes.
    Returns deduped dataframe with article_count (merged event count).
    """
    if len(df) == 0:
        return pd.DataFrame()

    # Sort by date for temporal processing
    df = df.sort_values(DATE_COL).reset_index(drop=True)

    # Convert lat/lng to radians for haversine DBSCAN
    coords = np.radians(df[[LAT_COL, LNG_COL]].values)

    # DBSCAN spatial clustering (eps in radians: km / earth_radius_km)
    eps_rad = radius_km / 6371.0
    spatial_clusters = DBSCAN(eps=eps_rad, min_samples=1, metric='haversine').fit_predict(coords)
    df["spatial_cluster"] = spatial_clusters

    episodes = []
    for cluster_id in df["spatial_cluster"].unique():
        cluster_events = df[df["spatial_cluster"] == cluster_id].sort_values(DATE_COL)

        # Within each spatial cluster, merge temporally close events
        current_episode = None
        for _, event in cluster_events.iterrows():
            event_date = pd.to_datetime(event[DATE_COL])

            if current_episode is None:
                current_episode = {
                    "city": event["city"],
                    "lats": [event[LAT_COL]],
                    "lngs": [event[LNG_COL]],
                    "areas": [event[AREA_COL]] if pd.notna(event.get(AREA_COL)) else [],
                    "date_start": event_date,
                    "date_end": event_date,
                    "article_count": 1,
                    "source_event_ids": [str(event[ID_COL])] if ID_COL in event.index else [],
                }
            elif (event_date - current_episode["date_end"]) <= timedelta(days=time_days):
                # Merge into current episode
                current_episode["date_end"] = event_date
                current_episode["article_count"] += 1
                current_episode["lats"].append(event[LAT_COL])
                current_episode["lngs"].append(event[LNG_COL])
                if pd.notna(event.get(AREA_COL)):
                    current_episode["areas"].append(event[AREA_COL])
                if ID_COL in event.index:
                    current_episode["source_event_ids"].append(str(event[ID_COL]))
            else:
                # Finalize current episode with true mean centroid
                current_episode["lat"] = np.mean(current_episode["lats"])
                current_episode["lng"] = np.mean(current_episode["lngs"])
                current_episode["avg_area_km2"] = np.mean(current_episode["areas"]) if current_episode["areas"] else None
                episodes.append(current_episode)
                current_episode = {
                    "city": event["city"],
                    "lats": [event[LAT_COL]],
                    "lngs": [event[LNG_COL]],
                    "areas": [event[AREA_COL]] if pd.notna(event.get(AREA_COL)) else [],
                    "date_start": event_date,
                    "date_end": event_date,
                    "article_count": 1,
                    "source_event_ids": [str(event[ID_COL])] if ID_COL in event.index else [],
                }
        if current_episode:
            current_episode["lat"] = np.mean(current_episode["lats"])
            current_episode["lng"] = np.mean(current_episode["lngs"])
            current_episode["avg_area_km2"] = np.mean(current_episode["areas"]) if current_episode["areas"] else None
            episodes.append(current_episode)

    return pd.DataFrame(episodes)


def insert_episodes(episodes_df, db_url):
    """Insert deduped episodes into historical_flood_episodes table.
    Truncate + insert in single transaction (MVCC protects concurrent readers).
    Uses SET search_path for Supabase PostGIS (tiger schema).
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # Supabase has PostGIS in tiger schema
        cursor.execute("SET search_path TO public, tiger")
        cursor.execute("TRUNCATE TABLE historical_flood_episodes")

        values = []
        for _, ep in episodes_df.iterrows():
            source_ids = ep.get("source_event_ids", [])
            if not isinstance(source_ids, list):
                source_ids = []
            values.append((
                ep["city"],
                float(ep["lng"]), float(ep["lat"]),
                float(ep["avg_area_km2"]) if pd.notna(ep.get("avg_area_km2")) else None,
                str(ep["date_start"])[:10],
                str(ep.get("date_end", ep["date_start"]))[:10],
                int(ep["article_count"]),
                source_ids,
            ))

        execute_values(
            cursor,
            "INSERT INTO historical_flood_episodes (city, centroid, avg_area_km2, start_date, end_date, article_count, source_event_ids) VALUES %s",
            values,
            template="(%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s)"
        )

        conn.commit()
        count = len(values)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
    return count


def main():
    # Default to known parquet location
    if len(sys.argv) >= 2:
        parquet_path = sys.argv[1]
    else:
        parquet_path = os.path.normpath(DEFAULT_PARQUET)
        print(f"No path specified, using default: {parquet_path}")

    if not os.path.exists(parquet_path):
        print(f"ERROR: Parquet file not found at {parquet_path}")
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/floodsafe")

    print(f"Loading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    print(f"Loaded {len(df):,} total events")
    print(f"Columns: {list(df.columns)}")

    # Step 1: Extract centroids from WKB geometry
    df = extract_centroids(df)
    print(f"Centroids extracted: {len(df):,} events with valid geometry")

    # Step 2: Filter by area BEFORE city filtering (reduces centroid extraction waste)
    before = len(df)
    df = df[
        (df[AREA_COL] <= MAX_AREA_KM2) &
        (df[AREA_COL] >= MIN_AREA_KM2)
    ]
    print(f"Area filter ({MIN_AREA_KM2}-{MAX_AREA_KM2} km²): {before - len(df):,} removed, {len(df):,} remaining")

    # Step 3: Filter to 5 cities
    city_dfs = []
    for city, bounds in CITY_BOUNDS.items():
        city_df = filter_to_city(df, city, bounds)
        print(f"  {city}: {len(city_df):,} raw events")
        city_dfs.append(city_df)

    combined = pd.concat(city_dfs, ignore_index=True)
    print(f"\nTotal for 5 cities: {len(combined):,}")

    # Step 4: Yogyakarta Merapi lahar exclusion
    if "yogyakarta" in combined["city"].values:
        before = len(combined)
        merapi_mask = (
            (combined["city"] == "yogyakarta") &
            (np.sqrt(
                (combined[LAT_COL] - MERAPI_LAT)**2 +
                (combined[LNG_COL] - MERAPI_LNG)**2
            ) * 111 < MERAPI_EXCLUSION_KM)
        )
        combined = combined[~merapi_mask]
        print(f"Merapi lahar filter: {before - len(combined):,} removed from Yogyakarta")

    # Step 5: Dedup per city
    print(f"\nDeduplicating ({DEDUP_RADIUS_KM}km / {DEDUP_TIME_DAYS}d)...")
    all_episodes = []
    for city in CITY_BOUNDS:
        city_events = combined[combined["city"] == city]
        if len(city_events) == 0:
            print(f"  {city}: 0 events (skipped)")
            continue
        episodes = spatial_temporal_dedup(city_events)
        ratio = len(city_events) / max(len(episodes), 1)
        print(f"  {city}: {len(city_events):,} events → {len(episodes):,} episodes (dedup ratio: {ratio:.1f}x)")
        all_episodes.append(episodes)

    if not all_episodes:
        print("ERROR: No episodes after dedup. Check bounding boxes and area filters.")
        sys.exit(1)

    all_episodes_df = pd.concat(all_episodes, ignore_index=True)
    print(f"\nTotal deduped episodes: {len(all_episodes_df):,}")

    # Step 6: Insert into DB
    print(f"\nInserting into DB ({db_url[:50]}...)...")
    count = insert_episodes(all_episodes_df, db_url)
    print(f"Inserted {count:,} episodes")

    # Summary
    print(f"\n=== IMPORT SUMMARY ===")
    for city in CITY_BOUNDS:
        city_count = len(all_episodes_df[all_episodes_df["city"] == city])
        print(f"  {city}: {city_count:,} episodes")
    print(f"  TOTAL: {count:,} episodes")
    print(f"\nNext: Run cluster_groundsource.py to create spatial clusters")


if __name__ == "__main__":
    main()
