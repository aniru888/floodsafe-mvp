"""
Groundsource Cluster Analysis
==============================
1. Load deduped episodes from DB
2. Run DBSCAN per city (eps=500m, min_samples=3)
3. For each cluster: compute centroid, episode count, date range, article stats
4. Overlap analysis against existing 499 hotspots
5. Insert clusters into groundsource_clusters table

Run: DATABASE_URL=... python scripts/cluster_groundsource.py
"""
import os
import sys
import json
import numpy as np
from datetime import datetime
from sklearn.cluster import DBSCAN
import psycopg2
from psycopg2.extras import RealDictCursor

# Clustering parameters
EPS_KM = 0.5          # 500m radius

# Per-city min_samples
MIN_SAMPLES_PER_CITY = {
    "delhi": 5,
    "bangalore": 5,
    "yogyakarta": 4,
    "singapore": 4,
    "indore": 3,
}

# Overlap thresholds
CONFIRMED_RADIUS_KM = 0.5   # < 500m = CONFIRMED
PERIPHERAL_RADIUS_KM = 2.0  # 500-2000m = PERIPHERAL

# Hotspot data paths (relative to apps/backend/)
HOTSPOT_FILES = {
    "delhi": "data/delhi_waterlogging_hotspots.json",
    "bangalore": "data/bangalore_waterlogging_hotspots.json",
    "yogyakarta": "data/yogyakarta_waterlogging_hotspots.json",
    "singapore": "data/singapore_waterlogging_hotspots.json",
    "indore": "data/indore_waterlogging_hotspots.json",
}


def load_hotspots(city):
    """Load official hotspot coordinates for overlap analysis."""
    path = os.path.join(os.path.dirname(__file__), "..", HOTSPOT_FILES.get(city, ""))
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    hotspots = data.get("hotspots", data) if isinstance(data, dict) else data
    return [(h.get("latitude", h.get("lat")), h.get("longitude", h.get("lng")), h.get("name", "")) for h in hotspots]


def haversine_km(lat1, lng1, lat2, lng2):
    """Haversine distance between two points in km."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlng = np.radians(lng2 - lng1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlng/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))


def main():
    db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/floodsafe")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Supabase has PostGIS in tiger schema
    cursor.execute("SET search_path TO public, tiger")

    # Load episodes
    cursor.execute("""
        SELECT id, city, ST_Y(centroid) as lat, ST_X(centroid) as lng,
               start_date, end_date, article_count, avg_area_km2
        FROM historical_flood_episodes
        ORDER BY city, start_date
    """)
    episodes = cursor.fetchall()
    print(f"Loaded {len(episodes)} episodes")

    # Truncate clusters (idempotent)
    cursor.execute("TRUNCATE TABLE groundsource_clusters")

    cities = set(ep["city"] for ep in episodes)
    total_clusters = 0

    for city in sorted(cities):
        city_episodes = [ep for ep in episodes if ep["city"] == city]
        min_samples = MIN_SAMPLES_PER_CITY.get(city, 4)
        if len(city_episodes) < min_samples:
            print(f"  {city}: {len(city_episodes)} episodes (too few for clustering)")
            continue

        coords = np.array([[ep["lat"], ep["lng"]] for ep in city_episodes])
        coords_rad = np.radians(coords)

        eps_rad = EPS_KM / 6371.0
        labels = DBSCAN(eps=eps_rad, min_samples=min_samples, metric='haversine').fit_predict(coords_rad)

        cluster_ids = set(labels)
        cluster_ids.discard(-1)

        hotspots = load_hotspots(city)
        confirmed = 0
        peripheral = 0
        missed = 0

        for cid in sorted(cluster_ids):
            mask = labels == cid
            cluster_eps = [ep for ep, m in zip(city_episodes, mask) if m]
            cluster_coords = coords[mask]

            centroid_lat = cluster_coords[:, 0].mean()
            centroid_lng = cluster_coords[:, 1].mean()
            episode_count = len(cluster_eps)
            dates = [ep["start_date"] for ep in cluster_eps]
            articles = [ep["article_count"] for ep in cluster_eps]

            date_range_years = (max(dates) - min(dates)).days / 365.25

            # Overlap analysis
            min_dist = float('inf')
            nearest_name = None
            for hlat, hlng, hname in hotspots:
                dist = haversine_km(centroid_lat, centroid_lng, hlat, hlng)
                if dist < min_dist:
                    min_dist = dist
                    nearest_name = hname

            if min_dist <= CONFIRMED_RADIUS_KM:
                overlap = "CONFIRMED"
                confirmed += 1
            elif min_dist <= PERIPHERAL_RADIUS_KM:
                overlap = "PERIPHERAL"
                peripheral += 1
            else:
                overlap = "MISSED"
                missed += 1

            # Confidence scoring
            total_articles = sum(articles)
            if total_articles >= 10 and episode_count >= 5 and max(dates).year >= 2018:
                confidence = "HIGH"
            elif total_articles >= 5 and episode_count >= 3:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            # Infrastructure signal
            if overlap == "MISSED":
                if min(dates).year >= 2015 and max(dates).year >= 2020 and episode_count >= 3:
                    infra_signal = "NEW_FAILURE"
                elif min(dates).year <= 2010 and max(dates).year >= 2020 and episode_count >= 5:
                    infra_signal = "CHRONIC"
                else:
                    infra_signal = "NONE"
            else:
                infra_signal = "NONE"

            # Recency score
            current_year = datetime.now().year
            recency_score = sum(
                ep["article_count"] * np.exp(-0.1 * (current_year - ep["start_date"].year))
                for ep in cluster_eps
            )

            avg_area = np.mean([ep.get("avg_area_km2") or 0 for ep in cluster_eps])

            cursor.execute("""
                INSERT INTO groundsource_clusters
                (city, centroid, episode_count, total_article_count,
                 first_episode, last_episode, recency_score, avg_area_km2,
                 nearest_hotspot_name, nearest_hotspot_distance_m,
                 overlap_status, confidence, infra_signal)
                VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                city, centroid_lng, centroid_lat, episode_count, total_articles,
                min(dates), max(dates), recency_score, avg_area,
                nearest_name, min_dist * 1000,
                overlap, confidence, infra_signal
            ))

        total_clusters += len(cluster_ids)
        print(f"  {city}: {len(city_episodes)} episodes → {len(cluster_ids)} clusters "
              f"(CONFIRMED={confirmed}, PERIPHERAL={peripheral}, MISSED={missed})")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"\nTotal clusters: {total_clusters}")


if __name__ == "__main__":
    main()
