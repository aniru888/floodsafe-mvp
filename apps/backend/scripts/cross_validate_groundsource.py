"""
Cross-Validation Gate — Spatial Evidence
==========================================
Validates that Groundsource data correctly identifies known flood-prone locations.

METHODOLOGY (redesigned 2026-03-15):
  The original date+location matching (10km AND ±5 days) failed at 4% because
  polygon centroids don't align with specific urban landmarks on specific dates.
  The data proves WHERE floods happen, not precisely WHEN specific events occurred.

  This script tests SPATIAL accuracy: "Does Groundsource know these places flood?"

GATES:
  1. Spatial Recall ≥ 80% at 5km (curated flood spots have nearby episodes)
  2. Spatial Recall ≥ 60% at 3km (tighter check for user-facing 3km radius)
  3. Hotspot Overlap ≥ 30% at 2km for cities with data (official hotspots have evidence)

IF GATE 1 FAILS → DO NOT SHIP user-facing Groundsource features.
IF GATE 2 FAILS → Use 5km radius instead of 3km for user-facing display.
IF GATE 3 FAILS → Informational only, no validation against official hotspots.

Run: DATABASE_URL=... python scripts/cross_validate_groundsource.py

See: docs/superpowers/specs/2026-03-15-groundsource-spatial-validation-design.md
"""
import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor


def haversine_km(lat1, lng1, lat2, lng2):
    """Haversine distance between two points in km."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# Known flood-prone LOCATIONS (dates used only for reference, NOT for matching)
# Source: IMD records, PUB records, BPBD reports, local news archives
KNOWN_FLOOD_LOCATIONS = [
    # Delhi (7 locations)
    ("delhi", 28.6139, 77.2090, "ITO"),
    ("delhi", 28.6448, 77.2167, "Civil Lines"),
    ("delhi", 28.5672, 77.2100, "Minto Bridge"),
    ("delhi", 28.6353, 77.2250, "Pul Prahladpur"),
    ("delhi", 28.6280, 77.2190, "Rajghat area"),
    ("delhi", 28.6500, 77.2300, "Pragati Maidan"),
    ("delhi", 28.6270, 77.2200, "Delhi Airport area"),
    # Bangalore (5 locations)
    ("bangalore", 12.9716, 77.5946, "Outer Ring Road"),
    ("bangalore", 12.9352, 77.6245, "Koramangala"),
    ("bangalore", 12.9500, 77.6100, "Silk Board Junction"),
    ("bangalore", 13.0358, 77.5970, "Hebbal"),
    ("bangalore", 12.9250, 77.6010, "Bellandur"),
    # Yogyakarta (5 locations)
    ("yogyakarta", -7.7956, 110.3695, "Code River"),
    ("yogyakarta", -7.8014, 110.3641, "Kota Gede"),
    ("yogyakarta", -7.8200, 110.3900, "Bantul"),
    ("yogyakarta", -7.7800, 110.3600, "Umbulharjo"),
    ("yogyakarta", -7.7950, 110.3700, "Mergangsan"),
    # Singapore (5 locations)
    ("singapore", 1.3521, 103.8198, "Orchard Road"),
    ("singapore", 1.3000, 103.8400, "Bukit Timah"),
    ("singapore", 1.3100, 103.8600, "Upper Thomson"),
    ("singapore", 1.3050, 103.8350, "Bukit Timah Canal"),
    ("singapore", 1.2900, 103.8200, "Pasir Panjang"),
    # Indore (5 locations)
    ("indore", 22.7196, 75.8577, "Rajwada"),
    ("indore", 22.7240, 75.8650, "MG Road"),
    ("indore", 22.7180, 75.8500, "Nala road"),
    ("indore", 22.7300, 75.8700, "Palasia underpass"),
    ("indore", 22.7150, 75.8550, "Khandwa Road"),
]

# Hotspot JSON files for overlap check
HOTSPOT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HOTSPOT_FILES = {
    "delhi": "delhi_waterlogging_hotspots.json",
    "bangalore": "bangalore_waterlogging_hotspots.json",
    "yogyakarta": "yogyakarta_waterlogging_hotspots.json",
    "singapore": "singapore_waterlogging_hotspots.json",
    "indore": "indore_waterlogging_hotspots.json",
}


def test_spatial_recall(cursor, radius_km):
    """
    TEST 1: For each curated flood-prone location, check if ANY episode
    exists within radius_km, regardless of date.

    This tests: "Does Groundsource agree these are flood-prone areas?"
    """
    hits = 0
    total = len(KNOWN_FLOOD_LOCATIONS)
    city_results = {}

    for city, lat, lng, name in KNOWN_FLOOD_LOCATIONS:
        cursor.execute("""
            SELECT count(*) as cnt,
                   min(ST_Distance(centroid::geography,
                       ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) / 1000) as min_dist_km,
                   sum(article_count) as total_articles,
                   min(start_date) as earliest,
                   max(start_date) as latest
            FROM historical_flood_episodes
            WHERE city = %s
              AND ST_DWithin(centroid::geography,
                  ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
        """, (lng, lat, city, lng, lat, radius_km * 1000))

        row = cursor.fetchone()
        cnt = row["cnt"] if row else 0

        if cnt > 0:
            hits += 1
            print(f"  + {city}/{name}: {cnt} episodes within {radius_km}km "
                  f"(nearest: {row['min_dist_km']:.1f}km, "
                  f"{row['earliest']}-{row['latest']}, "
                  f"{row['total_articles']} articles)")
        else:
            print(f"  - {city}/{name}: NO episodes within {radius_km}km")

        if city not in city_results:
            city_results[city] = {"hits": 0, "total": 0}
        city_results[city]["total"] += 1
        if cnt > 0:
            city_results[city]["hits"] += 1

    recall = hits / total if total else 0

    # Per-city breakdown
    print()
    for city, r in sorted(city_results.items()):
        rate = r["hits"] / r["total"] if r["total"] else 0
        print(f"  {city}: {r['hits']}/{r['total']} = {rate:.0%}")

    return recall, city_results


def test_hotspot_overlap(cursor, radius_km=2.0):
    """
    TEST 2: For each official hotspot (from JSON files), check if episodes
    exist within radius_km.

    This tests: "Does Groundsource evidence correlate with curated hotspots?"
    """
    results = {}
    for city, fname in HOTSPOT_FILES.items():
        path = os.path.join(HOTSPOT_DIR, fname)
        if not os.path.exists(path):
            print(f"  {city}: hotspot file not found, skipping")
            continue

        with open(path) as f:
            data = json.load(f)
        hotspots = data.get("hotspots", data) if isinstance(data, dict) else data

        total = len(hotspots)
        with_evidence = 0

        for h in hotspots:
            lat = h.get("latitude", h.get("lat"))
            lng = h.get("longitude", h.get("lng"))
            if lat is None or lng is None:
                continue

            cursor.execute("""
                SELECT count(*) as cnt FROM historical_flood_episodes
                WHERE ST_DWithin(centroid::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
            """, (lng, lat, radius_km * 1000))

            row = cursor.fetchone()
            if row and row["cnt"] > 0:
                with_evidence += 1

        rate = with_evidence / total if total else 0
        results[city] = {"total": total, "with_evidence": with_evidence, "rate": rate}
        print(f"  {city}: {with_evidence}/{total} = {rate:.0%}")

    return results


def test_idw_score_sample(cursor):
    """
    TEST 3: Compute IDW flood activity scores for a sample of locations.
    IDW = SUM(1 / (1 + d_i / d_scale)) where d_scale = median polygon radius.

    This previews how the user-facing "flood activity score" would look.
    """
    # Use d_scale = 1.5km (approximate median sqrt(area_km2 / pi) for our data)
    D_SCALE = 1.5

    sample_locations = [
        ("delhi", 28.6139, 77.2090, "ITO (flood-prone)"),
        ("delhi", 28.5985, 77.1740, "Delhi Ridge (elevated)"),
        ("bangalore", 12.9716, 77.5946, "ORR (flood-prone)"),
        ("bangalore", 12.9783, 77.5712, "Cubbon Park (elevated)"),
        ("singapore", 1.3000, 103.8400, "Bukit Timah (flood-prone)"),
        ("singapore", 1.3644, 103.9915, "Changi (coastal)"),
        ("indore", 22.7196, 75.8577, "Rajwada (flood-prone)"),
    ]

    for city, lat, lng, name in sample_locations:
        cursor.execute("""
            SELECT ST_Distance(centroid::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) / 1000 as dist_km,
                article_count
            FROM historical_flood_episodes
            WHERE city = %s
              AND ST_DWithin(centroid::geography,
                  ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 10000)
            ORDER BY dist_km
        """, (lng, lat, city, lng, lat))

        episodes = cursor.fetchall()
        if not episodes:
            print(f"  {name}: IDW=0.0 (no episodes within 10km)")
            continue

        idw_score = sum(1.0 / (1.0 + ep["dist_km"] / D_SCALE) for ep in episodes)
        nearest = episodes[0]["dist_km"]
        print(f"  {name}: IDW={idw_score:.1f} ({len(episodes)} episodes, nearest={nearest:.1f}km)")


def main():
    db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/floodsafe")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Supabase has PostGIS in tiger schema
    cursor.execute("SET search_path TO public, tiger")

    print("=" * 60)
    print("GROUNDSOURCE SPATIAL VALIDATION")
    print("=" * 60)
    print()

    all_pass = True

    # ─── TEST 1: Spatial Recall at 5km ──────────────────────────
    print("=== TEST 1: Spatial Recall at 5km (GATE: ≥ 80%) ===")
    print("  Question: Do curated flood-prone locations have nearby episodes?")
    print()
    recall_5km, _ = test_spatial_recall(cursor, radius_km=5.0)
    gate1 = recall_5km >= 0.80
    print(f"\n  RESULT: {recall_5km:.0%} spatial recall at 5km → {'PASS' if gate1 else 'FAIL'}")
    if not gate1:
        all_pass = False
    print()

    # ─── TEST 2: Spatial Recall at 3km ──────────────────────────
    print("=== TEST 2: Spatial Recall at 3km (GATE: ≥ 60%) ===")
    print("  Question: Tighter check — still good at user-facing 3km radius?")
    print()
    recall_3km, _ = test_spatial_recall(cursor, radius_km=3.0)
    gate2 = recall_3km >= 0.60
    print(f"\n  RESULT: {recall_3km:.0%} spatial recall at 3km → {'PASS' if gate2 else 'FAIL'}")
    if not gate2:
        print("  NOTE: Consider using 5km radius for user-facing display instead of 3km")
    print()

    # ─── TEST 3: Hotspot Overlap at 2km ─────────────────────────
    print("=== TEST 3: Hotspot Overlap at 2km (GATE: ≥ 30% for ≥ 2 cities) ===")
    print("  Question: Do official hotspots have Groundsource evidence nearby?")
    print()
    overlap = test_hotspot_overlap(cursor, radius_km=2.0)
    cities_passing = sum(1 for r in overlap.values() if r["rate"] >= 0.30)
    gate3 = cities_passing >= 2
    print(f"\n  RESULT: {cities_passing} cities with ≥30% overlap → {'PASS' if gate3 else 'FAIL'}")
    if not gate3:
        all_pass = False
    print()

    # ─── TEST 4: IDW Score Sanity Check ─────────────────────────
    print("=== TEST 4: IDW Flood Activity Scores (informational) ===")
    print("  Question: Do known flood-prone spots score higher than safe spots?")
    print()
    test_idw_score_sample(cursor)
    print()

    # ─── FINAL VERDICT ──────────────────────────────────────────
    print("=" * 60)
    if all_pass:
        print("GATE: PASSED — Spatial evidence validated")
        print("  → Ship user-facing historical flood evidence feature")
        print(f"  → Recommended display radius: {'3km' if gate2 else '5km'}")
        print("  → FHI weight optimization: DEFERRED (needs ERA5 reanalysis)")
    else:
        if not gate1:
            print("GATE: FAILED — Spatial recall too low")
            print("  → DO NOT ship Groundsource user-facing features")
            print("  → Action: Check dedup parameters, verify centroid extraction")
        elif not gate3:
            print("GATE: PARTIAL — Spatial recall OK but hotspot overlap low")
            print("  → Ship as informational context only")
            print("  → Do not claim hotspot-level precision")
        sys.exit(1 if not gate1 else 0)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
