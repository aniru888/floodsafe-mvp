"""
Cross-Validation Gate (BLOCKING)
================================
Validates Groundsource dedup + clustering pipeline against curated flood dates.

GATES:
  - Hit rate (recall) >= 60% for Delhi, Bangalore, Singapore
  - Hit rate (recall) >= 40% for Yogyakarta, Indore
  - Precision >= 50% (clusters correspond to real floods)

IF ANY GATE FAILS -> DO NOT SHIP user-facing Groundsource features.

Run: DATABASE_URL=... python scripts/cross_validate_groundsource.py
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import timedelta

def haversine_km(lat1, lng1, lat2, lng2):
    """Haversine distance between two points in km."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# Known flood events for validation (manually curated)
KNOWN_FLOODS = [
    # Delhi (7 events)
    ("delhi", "2023-07-09", 28.6139, 77.2090, "ITO flooding"),
    ("delhi", "2023-07-12", 28.6448, 77.2167, "Civil Lines waterlogging"),
    ("delhi", "2021-08-21", 28.5672, 77.2100, "Minto Bridge submerged"),
    ("delhi", "2020-08-19", 28.6353, 77.2250, "Pul Prahladpur underpass"),
    ("delhi", "2024-06-28", 28.6280, 77.2190, "Rajghat area flooding"),
    ("delhi", "2019-08-17", 28.6500, 77.2300, "Pragati Maidan flooding"),
    ("delhi", "2018-07-26", 28.6270, 77.2200, "Delhi Airport waterlogging"),
    # Bangalore (5 events)
    ("bangalore", "2022-09-05", 12.9716, 77.5946, "Outer Ring Road flooding"),
    ("bangalore", "2023-10-15", 12.9352, 77.6245, "Koramangala flooding"),
    ("bangalore", "2022-09-12", 12.9500, 77.6100, "Silk Board flooding"),
    ("bangalore", "2024-10-22", 13.0358, 77.5970, "Hebbal flooding"),
    ("bangalore", "2022-09-04", 12.9250, 77.6010, "Bellandur flooding"),
    # Yogyakarta (5 events)
    ("yogyakarta", "2024-02-06", -7.7956, 110.3695, "Code River overflow"),
    ("yogyakarta", "2023-11-21", -7.8014, 110.3641, "Kota Gede flooding"),
    ("yogyakarta", "2022-02-15", -7.8200, 110.3900, "Bantul flooding"),
    ("yogyakarta", "2021-01-17", -7.7800, 110.3600, "Umbulharjo flooding"),
    ("yogyakarta", "2020-03-10", -7.7950, 110.3700, "Mergangsan flooding"),
    # Singapore (5 events)
    ("singapore", "2024-01-21", 1.3521, 103.8198, "Orchard Road flash flood"),
    ("singapore", "2023-04-17", 1.3000, 103.8400, "Bukit Timah flood"),
    ("singapore", "2022-08-20", 1.3100, 103.8600, "Upper Thomson flooding"),
    ("singapore", "2021-04-17", 1.3050, 103.8350, "Bukit Timah Canal overflow"),
    ("singapore", "2020-01-02", 1.2900, 103.8200, "Pasir Panjang flooding"),
    # Indore (5 events)
    ("indore", "2023-07-15", 22.7196, 75.8577, "Rajwada area waterlogging"),
    ("indore", "2024-08-12", 22.7240, 75.8650, "MG Road flooding"),
    ("indore", "2022-07-22", 22.7180, 75.8500, "Nala road waterlogging"),
    ("indore", "2021-09-14", 22.7300, 75.8700, "Palasia underpass flooding"),
    ("indore", "2020-08-25", 22.7150, 75.8550, "Khandwa Road flooding"),
]

HIT_RATE_THRESHOLDS = {
    "delhi": 0.60,
    "bangalore": 0.60,
    "singapore": 0.60,
    "yogyakarta": 0.40,
    "indore": 0.40,
}

MATCH_RADIUS_KM = 10.0
MATCH_TIME_DAYS = 5
SENSITIVITY_RADIUS_KM = 5.0
SENSITIVITY_TIME_DAYS = 3


def main():
    db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/floodsafe")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Supabase has PostGIS in tiger schema
    cursor.execute("SET search_path TO public, tiger")

    print("=== CROSS-VALIDATION GATE ===\n")

    all_pass = True
    city_results = {}

    for city, threshold in HIT_RATE_THRESHOLDS.items():
        city_floods = [f for f in KNOWN_FLOODS if f[0] == city]
        if not city_floods:
            print(f"  {city}: No validation data -- SKIP")
            continue

        hits = 0
        for _, date_str, lat, lng, desc in city_floods:
            cursor.execute("""
                SELECT id, start_date, article_count,
                       ST_Distance(centroid::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) / 1000 as dist_km
                FROM historical_flood_episodes
                WHERE city = %s
                  AND ST_DWithin(centroid::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
                  AND start_date BETWEEN %s::date - interval '%s days' AND %s::date + interval '%s days'
                ORDER BY dist_km
                LIMIT 1
            """, (lng, lat, city, lng, lat, MATCH_RADIUS_KM * 1000, date_str, MATCH_TIME_DAYS, date_str, MATCH_TIME_DAYS))

            match = cursor.fetchone()
            if match:
                hits += 1
                print(f"  + {city}/{desc} -- matched at {match['dist_km']:.1f}km, {match['article_count']} articles")
            else:
                print(f"  - {city}/{desc} -- no match within {MATCH_RADIUS_KM}km / {MATCH_TIME_DAYS}d")

        hit_rate = hits / len(city_floods) if city_floods else 0
        passed = hit_rate >= threshold
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False

        city_results[city] = {"hits": hits, "total": len(city_floods), "rate": hit_rate, "threshold": threshold}
        print(f"\n  {city}: {hits}/{len(city_floods)} = {hit_rate:.0%} (threshold: {threshold:.0%}) -> {status}\n")

    # Precision check
    cursor.execute("""
        SELECT id, city, ST_Y(centroid) as lat, ST_X(centroid) as lng,
               first_episode, last_episode, episode_count
        FROM groundsource_clusters
    """)
    clusters = cursor.fetchall()
    validated = 0
    for cluster in clusters:
        matching = [f for f in KNOWN_FLOODS if f[0] == cluster["city"]]
        for _, date_str, flat, flng, _ in matching:
            dist = haversine_km(cluster["lat"], cluster["lng"], flat, flng)
            if dist <= MATCH_RADIUS_KM:
                validated += 1
                break

    precision = validated / len(clusters) if clusters else 0
    precision_passed = precision >= 0.50

    print(f"\n=== PRECISION CHECK ===")
    print(f"Clusters matching curated events: {validated}/{len(clusters)} = {precision:.0%} (threshold: 50%)")
    print(f"Precision: {'PASS' if precision_passed else 'FAIL'}")

    # Sensitivity check
    print(f"\n=== SENSITIVITY CHECK (+/-{SENSITIVITY_TIME_DAYS}d / {SENSITIVITY_RADIUS_KM}km) ===")
    for city, threshold in HIT_RATE_THRESHOLDS.items():
        city_floods = [f for f in KNOWN_FLOODS if f[0] == city]
        if not city_floods:
            continue
        hits_tight = 0
        for _, date_str, lat, lng, desc in city_floods:
            cursor.execute("""
                SELECT 1 FROM historical_flood_episodes
                WHERE city = %s
                  AND ST_DWithin(centroid::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
                  AND start_date BETWEEN %s::date - interval '%s days' AND %s::date + interval '%s days'
                LIMIT 1
            """, (city, lng, lat, SENSITIVITY_RADIUS_KM * 1000, date_str, SENSITIVITY_TIME_DAYS, date_str, SENSITIVITY_TIME_DAYS))
            if cursor.fetchone():
                hits_tight += 1
        rate_tight = hits_tight / len(city_floods) if city_floods else 0
        primary_rate = city_results.get(city, {}).get("rate", 0)
        drop = primary_rate - rate_tight
        print(f"  {city}: {rate_tight:.0%} (drop: {drop:.0%} from primary)")
        if drop > 0.20:
            print(f"    WARNING: >20% drop -- spatial precision may be too low for neighborhood use")

    if not precision_passed:
        all_pass = False

    # Final verdict
    print(f"\n{'='*50}")
    if all_pass:
        print(f"GATE: PASSED -- Safe to proceed with user-facing features")
    else:
        print(f"GATE: FAILED -- DO NOT ship Groundsource user-facing features")
        print(f"Action: Review dedup parameters, supplement validation data, or adjust thresholds")
        sys.exit(1)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
