"""
Groundsource Import Pipeline
==============================
1. Load 667MB Parquet file
2. Filter to 5 cities by bounding box
3. Filter out events > 10 km² (basin-wide, not neighborhood)
4. Spatial-temporal deduplication (5km radius, 3-day window)
5. Insert deduped episodes into historical_flood_episodes table

Run locally: DATABASE_URL=... python scripts/import_groundsource.py path/to/file.parquet
"""
import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta
from sklearn.cluster import DBSCAN
import psycopg2
from psycopg2.extras import execute_values

# UPDATE these after running exploration script
LAT_COL = "latitude"    # Verify from exploration
LNG_COL = "longitude"   # Verify from exploration
DATE_COL = "start_date" # Spec uses start_date (verify from exploration)
AREA_COL = "area_km2"   # Verify from exploration

# Dedup parameters (from spec § 5.1)
DEDUP_RADIUS_KM = 5.0       # 5km radius
DEDUP_TIME_DAYS = 3          # ±3 days window
MAX_AREA_KM2 = 10.0          # Filter basin-wide events
MIN_AREA_KM2 = 0.001         # Filter geocoding artifacts

# Merapi exclusion zone for Yogyakarta
MERAPI_LAT = -7.54
MERAPI_LNG = 110.44
MERAPI_EXCLUSION_KM = 15.0

# City bounding boxes WITH +0.5° buffer
CITY_BOUNDS = {
    "delhi": {"lat_min": 27.90, "lat_max": 29.38, "lng_min": 76.34, "lng_max": 77.85},
    "bangalore": {"lat_min": 12.35, "lat_max": 13.65, "lng_min": 76.95, "lng_max": 78.25},
    "yogyakarta": {"lat_min": -8.45, "lat_max": -7.20, "lng_min": 109.80, "lng_max": 111.00},
    "singapore": {"lat_min": 0.70, "lat_max": 1.97, "lng_min": 103.10, "lng_max": 104.50},
    "indore": {"lat_min": 22.12, "lat_max": 23.32, "lng_min": 75.28, "lng_max": 76.45},
}


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
    Merge events that are within radius_km AND time_days of each other
    into single episodes. Returns deduped dataframe with article_count.
    """
    if len(df) == 0:
        return df

    # Sort by date for temporal processing
    df = df.sort_values(DATE_COL).reset_index(drop=True)

    # Convert lat/lng to radians for haversine
    coords = np.radians(df[[LAT_COL, LNG_COL]].values)

    # DBSCAN for spatial clustering (eps in radians: km / earth_radius)
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
                    "areas": [event.get(AREA_COL)] if AREA_COL in event.index else [],
                    "date_start": event_date,
                    "date_end": event_date,
                    "article_count": 1,
                    "source_event_ids": [str(event.get("id", ""))] if "id" in event.index else [],
                }
            elif (event_date - current_episode["date_end"]) <= timedelta(days=time_days):
                # Merge into current episode
                current_episode["date_end"] = event_date
                current_episode["article_count"] += 1
                current_episode["lats"].append(event[LAT_COL])
                current_episode["lngs"].append(event[LNG_COL])
                if AREA_COL in event.index:
                    current_episode["areas"].append(event[AREA_COL])
                if "id" in event.index:
                    current_episode["source_event_ids"].append(str(event["id"]))
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
                    "areas": [event.get(AREA_COL)] if AREA_COL in event.index else [],
                    "date_start": event_date,
                    "date_end": event_date,
                    "article_count": 1,
                    "source_event_ids": [str(event.get("id", ""))] if "id" in event.index else [],
                }
        if current_episode:
            current_episode["lat"] = np.mean(current_episode["lats"])
            current_episode["lng"] = np.mean(current_episode["lngs"])
            current_episode["avg_area_km2"] = np.mean(current_episode["areas"]) if current_episode["areas"] else None
            episodes.append(current_episode)

    return pd.DataFrame(episodes)


def insert_episodes(episodes_df, db_url):
    """Insert deduped episodes into historical_flood_episodes table.
    IMPORTANT: Truncate + insert in single transaction.
    MVCC protects concurrent readers.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        cursor.execute("TRUNCATE TABLE historical_flood_episodes")

        values = []
        for _, ep in episodes_df.iterrows():
            values.append((
                ep["city"],
                ep["lng"], ep["lat"],
                ep.get("avg_area_km2"),
                ep["date_start"],
                ep.get("date_end", ep["date_start"]),
                ep["article_count"],
                ep.get("source_event_ids", []),
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
    if len(sys.argv) < 2:
        print("Usage: python import_groundsource.py <path/to/parquet>")
        sys.exit(1)

    parquet_path = sys.argv[1]
    db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/floodsafe")

    print(f"Loading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    print(f"Loaded {len(df):,} total events")

    # Filter to cities
    city_dfs = []
    for city, bounds in CITY_BOUNDS.items():
        city_df = filter_to_city(df, city, bounds)
        print(f"  {city}: {len(city_df):,} raw events")
        city_dfs.append(city_df)

    combined = pd.concat(city_dfs, ignore_index=True)
    print(f"\nTotal for 5 cities: {len(combined):,}")

    # Filter by area
    if AREA_COL in combined.columns:
        before = len(combined)
        combined = combined[
            (combined[AREA_COL] <= MAX_AREA_KM2) &
            (combined[AREA_COL] >= MIN_AREA_KM2)
        ]
        print(f"Area filter ({MIN_AREA_KM2}-{MAX_AREA_KM2} km²): {before - len(combined):,} removed")

    # Yogyakarta Merapi lahar exclusion
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

    # Dedup per city
    all_episodes = []
    for city in CITY_BOUNDS:
        city_events = combined[combined["city"] == city]
        if len(city_events) == 0:
            continue
        episodes = spatial_temporal_dedup(city_events)
        print(f"  {city}: {len(city_events):,} events → {len(episodes):,} episodes (dedup ratio: {len(city_events)/max(len(episodes),1):.1f}x)")
        all_episodes.append(episodes)

    all_episodes_df = pd.concat(all_episodes, ignore_index=True)
    print(f"\nTotal deduped episodes: {len(all_episodes_df):,}")

    # Insert
    print(f"\nInserting into DB...")
    count = insert_episodes(all_episodes_df, db_url)
    print(f"Inserted {count:,} episodes")

    # Summary
    print(f"\n=== IMPORT SUMMARY ===")
    for city in CITY_BOUNDS:
        city_count = len(all_episodes_df[all_episodes_df["city"] == city])
        print(f"  {city}: {city_count} episodes")


if __name__ == "__main__":
    main()
