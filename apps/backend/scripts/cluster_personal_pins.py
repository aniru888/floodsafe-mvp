"""
Community Pin Clustering
========================
DBSCAN on personal pins (eps=300m, min_samples=3).
When cluster found:
  - Create CandidateHotspot with submission_type="pin_cluster"
  - Enrich with Groundsource episode count + avg FHI
  - Set for admin review

Run: DATABASE_URL=... python scripts/cluster_personal_pins.py
"""
import os
import uuid
import numpy as np
from sklearn.cluster import DBSCAN
import psycopg2
from psycopg2.extras import RealDictCursor

EPS_KM = 0.3  # 300 metres
MIN_SAMPLES = 3

CITIES = ["delhi", "bangalore", "yogyakarta", "singapore", "indore"]


def main():
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/floodsafe",
    )
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Load personal pins — WatchArea.location is a PostGIS POINT column
    cursor.execute("""
        SELECT id, user_id, name, city,
               ST_Y(location) AS lat, ST_X(location) AS lng,
               fhi_score, fhi_level, created_at
        FROM watch_areas
        WHERE is_personal_hotspot = TRUE
        ORDER BY city
    """)
    pins = cursor.fetchall()
    print(f"Loaded {len(pins)} personal pins")

    total_clusters = 0
    total_candidates = 0

    for city in CITIES:
        city_pins = [p for p in pins if p["city"] == city]
        if len(city_pins) < MIN_SAMPLES:
            print(f"  {city}: {len(city_pins)} pins (too few to cluster)")
            continue

        coords = np.array([[p["lat"], p["lng"]] for p in city_pins])
        coords_rad = np.radians(coords)

        # Haversine DBSCAN — eps in radians
        eps_rad = EPS_KM / 6371.0
        labels = DBSCAN(
            eps=eps_rad, min_samples=MIN_SAMPLES, metric="haversine"
        ).fit_predict(coords_rad)

        cluster_ids = set(labels)
        cluster_ids.discard(-1)  # -1 = noise points

        for cid in sorted(cluster_ids):
            mask = labels == cid
            cluster_pins = [p for p, m in zip(city_pins, mask) if m]
            cluster_coords = coords[mask]

            centroid_lat = float(cluster_coords[:, 0].mean())
            centroid_lng = float(cluster_coords[:, 1].mean())
            pin_count = len(cluster_pins)

            # pin_ids must be UUID strings for the PostgreSQL UUID[] column
            pin_ids = [str(p["id"]) for p in cluster_pins]

            # Average FHI from member pins
            fhi_scores = [
                p["fhi_score"]
                for p in cluster_pins
                if p["fhi_score"] is not None
            ]
            avg_fhi = float(np.mean(fhi_scores)) if fhi_scores else None

            # Historical episode count within 2 km of cluster centroid
            # HistoricalFloodEpisode also uses `centroid` for its geometry
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM historical_flood_episodes
                WHERE ST_DWithin(
                    centroid::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    2000
                )
                """,
                (centroid_lng, centroid_lat),
            )
            episode_count = cursor.fetchone()["cnt"]

            # Avoid duplicate candidates within 500 m
            # CandidateHotspot uses `centroid` (not `location`) for its geometry
            cursor.execute(
                """
                SELECT id FROM candidate_hotspots
                WHERE city = %s
                  AND ST_DWithin(
                    centroid::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    500
                  )
                  AND submission_type = 'pin_cluster'
                LIMIT 1
                """,
                (city, centroid_lng, centroid_lat),
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE candidate_hotspots
                    SET pin_count = %s,
                        pin_ids   = %s::uuid[],
                        avg_fhi   = %s,
                        historical_episode_count = %s
                    WHERE id = %s
                    """,
                    (
                        pin_count,
                        pin_ids,
                        avg_fhi,
                        episode_count,
                        existing["id"],
                    ),
                )
                print(f"    Updated existing candidate {existing['id']}")
            else:
                # INSERT into candidate_hotspots — geometry column is `centroid`
                fhi_display = f"{avg_fhi:.2f}" if avg_fhi is not None else "n/a"
                cursor.execute(
                    """
                    INSERT INTO candidate_hotspots
                        (id, city, centroid, name, report_count, status,
                         submission_type, pin_count, pin_ids, avg_fhi,
                         historical_episode_count, created_at)
                    VALUES (
                        %s,
                        %s,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                        %s,
                        %s,
                        'candidate',
                        'pin_cluster',
                        %s,
                        %s::uuid[],
                        %s,
                        %s,
                        NOW()
                    )
                    """,
                    (
                        str(uuid.uuid4()),
                        city,
                        centroid_lng,
                        centroid_lat,
                        f"Community Pin Cluster ({pin_count} pins)",
                        pin_count,
                        pin_count,
                        pin_ids,
                        avg_fhi,
                        episode_count,
                    ),
                )
                total_candidates += 1
                print(
                    f"    New candidate: {pin_count} pins, "
                    f"avg FHI={fhi_display}, "
                    f"{episode_count} episodes"
                )

        total_clusters += len(cluster_ids)
        print(
            f"  {city}: {len(city_pins)} pins -> {len(cluster_ids)} clusters"
        )

    conn.commit()
    cursor.close()
    conn.close()

    print(
        f"\nTotal: {total_clusters} clusters, {total_candidates} new candidates"
    )


if __name__ == "__main__":
    main()
