"""
Import OSM road network into city_roads table.

Downloads road segments from Overpass API (or parses a PBF file) and inserts
them into the city_roads PostGIS table for report road-snapping.

Usage:
    python scripts/import_city_roads.py --city delhi
    python scripts/import_city_roads.py --city delhi --pbf-file india-latest.osm.pbf
    python scripts/import_city_roads.py --city delhi --dry-run

Requires: DATABASE_URL in .env or environment variable.
"""
import argparse
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# City bounding boxes (must match FHICalculator.CITY_BOUNDS and reports.py _CITY_BOUNDS)
CITY_BOUNDS = {
    "delhi": {"min_lat": 28.40, "max_lat": 28.88, "min_lng": 76.84, "max_lng": 77.35},
    "bangalore": {"min_lat": 12.75, "max_lat": 13.20, "min_lng": 77.35, "max_lng": 77.80},
    "yogyakarta": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
    "singapore": {"min_lat": 1.15, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    "indore": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
}

# Road types to import (OSM highway tags)
HIGHWAY_TYPES = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "unclassified", "service",
}

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 180  # seconds


def get_engine():
    """Create SQLAlchemy engine from DATABASE_URL."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Try parent .env files
        for parent in [Path(__file__).parent.parent.parent / "backend",
                       Path(__file__).parent.parent.parent.parent]:
            env_path = parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                database_url = os.getenv("DATABASE_URL")
                if database_url:
                    break

    if not database_url:
        logger.error("DATABASE_URL not found. Set it in .env or environment.")
        sys.exit(1)

    return create_engine(database_url)


def build_overpass_query(bounds: Dict[str, float]) -> str:
    """Build Overpass QL query for road segments within bounding box."""
    bbox = f"{bounds['min_lat']},{bounds['min_lng']},{bounds['max_lat']},{bounds['max_lng']}"
    highway_filter = "|".join(HIGHWAY_TYPES)

    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
(
  way["highway"~"^({highway_filter})$"]({bbox});
);
out body;
>;
out skel qt;
"""


def fetch_overpass_tiled(bounds: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Fetch road data from Overpass API, splitting into tiles if needed.

    Splits the bounding box into 4 quadrants to stay under response limits
    for large cities like Delhi and Bangalore.
    """
    mid_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
    mid_lng = (bounds["min_lng"] + bounds["max_lng"]) / 2

    tiles = [
        {"min_lat": bounds["min_lat"], "max_lat": mid_lat, "min_lng": bounds["min_lng"], "max_lng": mid_lng},
        {"min_lat": bounds["min_lat"], "max_lat": mid_lat, "min_lng": mid_lng, "max_lng": bounds["max_lng"]},
        {"min_lat": mid_lat, "max_lat": bounds["max_lat"], "min_lng": bounds["min_lng"], "max_lng": mid_lng},
        {"min_lat": mid_lat, "max_lat": bounds["max_lat"], "min_lng": mid_lng, "max_lng": bounds["max_lng"]},
    ]

    all_elements = []
    for i, tile in enumerate(tiles):
        logger.info(f"Fetching tile {i+1}/4: lat [{tile['min_lat']:.2f}, {tile['max_lat']:.2f}] "
                     f"lng [{tile['min_lng']:.2f}, {tile['max_lng']:.2f}]")

        query = build_overpass_query(tile)

        try:
            with httpx.Client(timeout=OVERPASS_TIMEOUT + 30) as client:
                response = client.post(OVERPASS_API_URL, data={"data": query})
                response.raise_for_status()
                data = response.json()

            elements = data.get("elements", [])
            all_elements.extend(elements)
            logger.info(f"  Tile {i+1}: {len(elements)} elements")

            # Rate limit: wait between tiles to be polite to Overpass
            if i < len(tiles) - 1:
                time.sleep(2)

        except httpx.TimeoutException:
            logger.error(f"  Tile {i+1} timed out after {OVERPASS_TIMEOUT}s")
            raise
        except Exception as e:
            logger.error(f"  Tile {i+1} failed: {e}")
            raise

    return all_elements


def parse_overpass_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse Overpass JSON elements into road segment dicts.

    Overpass returns nodes and ways separately. We need to:
    1. Build a node lookup (id -> lat/lng)
    2. For each way, resolve node references to coordinates
    3. Build a WKT LINESTRING geometry
    """
    # Build node lookup
    nodes = {}
    for el in elements:
        if el.get("type") == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])  # GeoJSON order: lng, lat

    # Parse ways into road segments
    roads = []
    seen_osm_ids = set()

    for el in elements:
        if el.get("type") != "way":
            continue

        osm_id = el["id"]
        if osm_id in seen_osm_ids:
            continue
        seen_osm_ids.add(osm_id)

        tags = el.get("tags", {})
        highway = tags.get("highway", "")
        if highway not in HIGHWAY_TYPES:
            continue

        # Resolve node references to coordinates
        node_refs = el.get("nodes", [])
        coords = []
        for nid in node_refs:
            if nid in nodes:
                coords.append(nodes[nid])

        if len(coords) < 2:
            continue  # Need at least 2 points for a line

        # Build WKT LINESTRING
        coord_str = ", ".join(f"{lng} {lat}" for lng, lat in coords)
        wkt = f"LINESTRING({coord_str})"

        roads.append({
            "osm_id": osm_id,
            "name": tags.get("name"),
            "road_type": highway,
            "is_underpass": tags.get("tunnel") == "yes",
            "is_bridge": tags.get("bridge") == "yes",
            "geometry_wkt": wkt,
        })

    return roads


def insert_roads(engine, city: str, roads: List[Dict[str, Any]], batch_size: int = 500):
    """Insert road segments into city_roads table in batches."""
    logger.info(f"Inserting {len(roads)} road segments for {city}...")

    inserted = 0
    with engine.connect() as conn:
        # Clear existing roads for this city (idempotent re-import)
        result = conn.execute(
            text("DELETE FROM city_roads WHERE city = :city"),
            {"city": city}
        )
        deleted = result.rowcount
        if deleted > 0:
            logger.info(f"Cleared {deleted} existing road segments for {city}")
        conn.commit()

        # Insert in batches
        for i in range(0, len(roads), batch_size):
            batch = roads[i:i + batch_size]

            for road in batch:
                try:
                    conn.execute(
                        text("""
                            INSERT INTO city_roads (id, city, osm_id, name, road_type, is_underpass, is_bridge, geometry)
                            VALUES (:id, :city, :osm_id, :name, :road_type, :is_underpass, :is_bridge,
                                    ST_GeomFromText(:geometry_wkt, 4326))
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "city": city,
                            "osm_id": road["osm_id"],
                            "name": road["name"],
                            "road_type": road["road_type"],
                            "is_underpass": road["is_underpass"],
                            "is_bridge": road["is_bridge"],
                            "geometry_wkt": road["geometry_wkt"],
                        }
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert road OSM ID {road['osm_id']}: {e}")

            conn.commit()
            logger.info(f"  Inserted batch {i//batch_size + 1}: {inserted}/{len(roads)} total")

    return inserted


def import_from_pbf(pbf_path: str, bounds: Dict[str, float]) -> List[Dict[str, Any]]:
    """Import roads from a PBF file using osmium library."""
    try:
        import osmium
        from shapely.geometry import LineString  # noqa: F401 — validates shapely install
    except ImportError:
        logger.error("osmium and/or shapely not installed. Install with: pip install osmium shapely")
        sys.exit(1)

    class RoadHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.roads = []

        def way(self, w):
            highway = w.tags.get("highway", "")
            if highway not in HIGHWAY_TYPES:
                return

            coords = []
            for node in w.nodes:
                try:
                    lat, lng = node.lat, node.lon
                    # Filter by bounding box
                    if (bounds["min_lat"] <= lat <= bounds["max_lat"] and
                            bounds["min_lng"] <= lng <= bounds["max_lng"]):
                        coords.append((lng, lat))
                except osmium.InvalidLocationError:
                    continue

            if len(coords) < 2:
                return

            coord_str = ", ".join(f"{lng} {lat}" for lng, lat in coords)
            wkt = f"LINESTRING({coord_str})"

            self.roads.append({
                "osm_id": w.id,
                "name": w.tags.get("name"),
                "road_type": highway,
                "is_underpass": w.tags.get("tunnel") == "yes",
                "is_bridge": w.tags.get("bridge") == "yes",
                "geometry_wkt": wkt,
            })

    handler = RoadHandler()
    handler.apply_file(pbf_path, locations=True)
    return handler.roads


def verify_import(engine, city: str):
    """Print import statistics."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM city_roads WHERE city = :city"),
            {"city": city}
        )
        total = result.scalar()

        result = conn.execute(
            text("""
                SELECT road_type, COUNT(*) as cnt
                FROM city_roads WHERE city = :city
                GROUP BY road_type
                ORDER BY cnt DESC
            """),
            {"city": city}
        )
        breakdown = result.fetchall()

        result = conn.execute(
            text("""
                SELECT COUNT(*) FROM city_roads
                WHERE city = :city AND is_underpass = true
            """),
            {"city": city}
        )
        underpasses = result.scalar()

        result = conn.execute(
            text("""
                SELECT COUNT(*) FROM city_roads
                WHERE city = :city AND is_bridge = true
            """),
            {"city": city}
        )
        bridges = result.scalar()

    print(f"\n{'='*50}")
    print(f"Import Summary: {city}")
    print(f"{'='*50}")
    print(f"Total road segments: {total}")
    print(f"Underpasses: {underpasses}")
    print(f"Bridges: {bridges}")
    print(f"\nBreakdown by type:")
    for row in breakdown:
        print(f"  {row[0]:20s} {row[1]:>6d}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Import OSM road network for a city")
    parser.add_argument("--city", required=True, choices=list(CITY_BOUNDS.keys()),
                        help="City to import roads for")
    parser.add_argument("--pbf-file", type=str, default=None,
                        help="Path to Geofabrik PBF file (uses Overpass API if not provided)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and parse roads but don't insert into DB")
    args = parser.parse_args()

    bounds = CITY_BOUNDS[args.city]
    logger.info(f"Importing roads for {args.city}: "
                f"lat [{bounds['min_lat']}, {bounds['max_lat']}] "
                f"lng [{bounds['min_lng']}, {bounds['max_lng']}]")

    # Fetch road data
    if args.pbf_file:
        logger.info(f"Using PBF file: {args.pbf_file}")
        roads = import_from_pbf(args.pbf_file, bounds)
    else:
        logger.info("Using Overpass API (tiled queries)...")
        elements = fetch_overpass_tiled(bounds)
        logger.info(f"Total elements from Overpass: {len(elements)}")
        roads = parse_overpass_elements(elements)

    logger.info(f"Parsed {len(roads)} road segments")

    if args.dry_run:
        print(f"\n[DRY RUN] Would insert {len(roads)} road segments for {args.city}")
        # Show sample
        for road in roads[:5]:
            print(f"  OSM {road['osm_id']}: {road['name'] or '(unnamed)'} [{road['road_type']}]"
                  f"{' (underpass)' if road['is_underpass'] else ''}"
                  f"{' (bridge)' if road['is_bridge'] else ''}")
        if len(roads) > 5:
            print(f"  ... and {len(roads) - 5} more")
        return

    # Insert into database
    engine = get_engine()
    inserted = insert_roads(engine, args.city, roads)
    logger.info(f"Successfully inserted {inserted}/{len(roads)} road segments")

    # Verify
    verify_import(engine, args.city)


if __name__ == "__main__":
    main()
