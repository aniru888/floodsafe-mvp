"""
Cluster verified community reports by road segment to discover candidate hotspots.

Groups reports by road_segment_id (from road snapping enrichment), identifies
road segments with 3+ verified reports as candidate hotspots.

Usage:
    python scripts/cluster_reports.py --city delhi
    python scripts/cluster_reports.py --city delhi --min-reports 5

Prerequisites:
    - city_roads imported (import_city_roads.py)
    - Reports enriched with road_segment_id (backend enrichment services)
    - DATABASE_URL in .env
"""
import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_engine():
    """Create SQLAlchemy engine from DATABASE_URL."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
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


def find_candidate_hotspots(engine, city: str, min_reports: int = 3):
    """
    Find road segments with min_reports+ verified reports.

    Only counts verified reports: manually verified OR IoT score >= 80.
    """
    query = text("""
        SELECT
            r.road_segment_id,
            r.road_name,
            r.road_type,
            COUNT(*) as report_count,
            array_agg(r.id) as report_ids,
            AVG(ST_Y(r.location::geometry)) as avg_lat,
            AVG(ST_X(r.location::geometry)) as avg_lng,
            MIN(r.timestamp) as first_report,
            MAX(r.timestamp) as last_report
        FROM reports r
        WHERE r.road_segment_id IS NOT NULL
          AND (r.verified = true OR r.iot_validation_score >= 80)
        GROUP BY r.road_segment_id, r.road_name, r.road_type
        HAVING COUNT(*) >= :min_reports
        ORDER BY report_count DESC
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"min_reports": min_reports})
        candidates = result.fetchall()

    logger.info(f"Found {len(candidates)} road segments with {min_reports}+ verified reports")
    return candidates


def compute_cluster_weather(engine, report_ids):
    """Compute average weather conditions from report weather_snapshots."""
    if not report_ids:
        return None

    # Convert UUID list to strings for SQL
    id_strs = [str(rid) for rid in report_ids]
    placeholders = ", ".join(f"'{rid}'" for rid in id_strs)

    query = text(f"""
        SELECT weather_snapshot
        FROM reports
        WHERE id IN ({placeholders})
          AND weather_snapshot IS NOT NULL
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        snapshots = [row[0] for row in result.fetchall()]

    if not snapshots:
        return None

    # Average numeric fields
    avg_weather = {}
    numeric_fields = [
        "precipitation_mm", "precipitation_probability", "hourly_intensity_max",
        "surface_pressure_hpa", "temperature_c", "relative_humidity",
        "rainfall_3d_mm", "rainfall_7d_mm",
    ]

    for field in numeric_fields:
        values = [s.get(field) for s in snapshots if s.get(field) is not None]
        if values:
            avg_weather[field] = round(sum(values) / len(values), 2)

    avg_weather["n_snapshots"] = len(snapshots)
    return avg_weather


def compute_water_depth_mode(engine, report_ids):
    """Get most common water depth from reports."""
    if not report_ids:
        return None

    id_strs = [str(rid) for rid in report_ids]
    placeholders = ", ".join(f"'{rid}'" for rid in id_strs)

    query = text(f"""
        SELECT water_depth, COUNT(*) as cnt
        FROM reports
        WHERE id IN ({placeholders})
          AND water_depth IS NOT NULL
        GROUP BY water_depth
        ORDER BY cnt DESC
        LIMIT 1
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        row = result.fetchone()

    return row[0] if row else None


def upsert_candidate_hotspots(engine, city: str, candidates):
    """Insert or update candidate hotspots in the database."""
    inserted = 0
    updated = 0

    with engine.connect() as conn:
        for candidate in candidates:
            road_segment_id = candidate[0]
            road_name = candidate[1]
            report_count = candidate[3]
            report_ids = candidate[4]
            avg_lat = candidate[5]
            avg_lng = candidate[6]
            first_report = candidate[7]
            last_report = candidate[8]

            # Compute enrichment
            avg_weather = compute_cluster_weather(engine, report_ids)
            avg_water_depth = compute_water_depth_mode(engine, report_ids)

            # Check if candidate already exists for this road segment
            existing = conn.execute(
                text("SELECT id FROM candidate_hotspots WHERE road_segment_id = :rsid"),
                {"rsid": str(road_segment_id)}
            ).fetchone()

            if existing:
                # Update existing candidate
                conn.execute(
                    text("""
                        UPDATE candidate_hotspots
                        SET report_count = :count,
                            report_ids = :rids,
                            avg_water_depth = :depth,
                            avg_weather = :weather,
                            date_first_report = :first,
                            date_last_report = :last
                        WHERE id = :id
                    """),
                    {
                        "id": str(existing[0]),
                        "count": report_count,
                        "rids": [str(r) for r in report_ids],
                        "depth": avg_water_depth,
                        "weather": json.dumps(avg_weather) if avg_weather else None,
                        "first": first_report,
                        "last": last_report,
                    }
                )
                updated += 1
            else:
                # Insert new candidate
                conn.execute(
                    text("""
                        INSERT INTO candidate_hotspots
                            (id, city, road_segment_id, centroid, road_name,
                             report_count, report_ids, avg_water_depth, avg_weather,
                             date_first_report, date_last_report)
                        VALUES
                            (:id, :city, :rsid,
                             ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                             :name, :count, :rids, :depth,
                             :weather::jsonb, :first, :last)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "city": city,
                        "rsid": str(road_segment_id),
                        "lng": avg_lng,
                        "lat": avg_lat,
                        "name": road_name,
                        "count": report_count,
                        "rids": [str(r) for r in report_ids],
                        "depth": avg_water_depth,
                        "weather": json.dumps(avg_weather) if avg_weather else None,
                        "first": first_report,
                        "last": last_report,
                    }
                )
                inserted += 1

        conn.commit()

    return inserted, updated


def main():
    parser = argparse.ArgumentParser(description="Cluster verified reports by road segment")
    parser.add_argument("--city", required=True,
                        choices=["delhi", "bangalore", "yogyakarta", "singapore", "indore"])
    parser.add_argument("--min-reports", type=int, default=3,
                        help="Minimum verified reports per road segment (default 3)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Find candidates but don't write to DB")
    args = parser.parse_args()

    engine = get_engine()

    # Find candidates
    candidates = find_candidate_hotspots(engine, args.city, args.min_reports)

    if not candidates:
        print(f"\nNo candidate hotspots found in {args.city} "
              f"(need {args.min_reports}+ verified reports on same road segment)")
        return

    # Display results
    print(f"\n{'='*60}")
    print(f"Candidate Hotspots: {args.city.upper()}")
    print(f"{'='*60}")
    print(f"Threshold: {args.min_reports}+ verified reports per road segment\n")

    for c in candidates:
        road_name = c[1] or "(unnamed road)"
        road_type = c[2]
        report_count = c[3]
        print(f"  [{report_count} reports] {road_name} ({road_type})")

    if args.dry_run:
        print(f"\n[DRY RUN] Would create/update {len(candidates)} candidate hotspots")
        return

    # Write to database
    inserted, updated = upsert_candidate_hotspots(engine, args.city, candidates)
    print(f"\nResults: {inserted} new, {updated} updated candidate hotspots")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
