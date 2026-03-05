"""
Migration: ML pipeline enrichment columns and discovery tables

Creates:
- 4 new columns on reports (weather_snapshot, road_segment_id, road_name, road_type)
- city_roads table for OSM road network segments
- candidate_hotspots table for community-discovered flood-prone locations

Run:      python -m apps.backend.src.scripts.migrate_ml_pipeline
Rollback: python -m apps.backend.src.scripts.migrate_ml_pipeline --rollback
Verify:   python -m apps.backend.src.scripts.migrate_ml_pipeline --verify
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from apps.backend.src.infrastructure.database import engine


def migrate():
    """Run migration to add ML pipeline columns and create discovery tables."""
    print("Starting migration: ML pipeline enrichment...")

    with engine.connect() as conn:
        # 1. New columns on reports
        try:
            print("\n1. Adding ML enrichment columns to reports table...")
            conn.execute(text("""
                ALTER TABLE reports ADD COLUMN IF NOT EXISTS weather_snapshot JSONB DEFAULT NULL;
            """))
            conn.execute(text("""
                ALTER TABLE reports ADD COLUMN IF NOT EXISTS road_segment_id UUID DEFAULT NULL;
            """))
            conn.execute(text("""
                ALTER TABLE reports ADD COLUMN IF NOT EXISTS road_name VARCHAR DEFAULT NULL;
            """))
            conn.execute(text("""
                ALTER TABLE reports ADD COLUMN IF NOT EXISTS road_type VARCHAR DEFAULT NULL;
            """))
            conn.commit()
            print("[OK] Added weather_snapshot, road_segment_id, road_name, road_type to reports")
        except Exception as e:
            print(f"[ERROR] Error adding columns to reports: {e}")
            conn.rollback()
            raise

        # 2. city_roads table
        try:
            print("\n2. Creating city_roads table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS city_roads (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    city VARCHAR NOT NULL,
                    osm_id BIGINT,
                    name VARCHAR,
                    road_type VARCHAR NOT NULL,
                    is_underpass BOOLEAN DEFAULT FALSE,
                    is_bridge BOOLEAN DEFAULT FALSE,
                    geometry geometry(GEOMETRY, 4326) NOT NULL,
                    elevation_avg FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))
            conn.commit()
            print("[OK] Created city_roads table")
        except Exception as e:
            print(f"[ERROR] Error creating city_roads table: {e}")
            conn.rollback()
            raise

        try:
            print("   Creating spatial index on city_roads.geometry...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_city_roads_geometry ON city_roads USING GIST(geometry);
            """))
            conn.commit()
            print("[OK] Created ix_city_roads_geometry")
        except Exception as e:
            print(f"[ERROR] Error creating spatial index: {e}")
            conn.rollback()
            raise

        try:
            print("   Creating city index on city_roads...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_city_roads_city ON city_roads(city);
            """))
            conn.commit()
            print("[OK] Created ix_city_roads_city")
        except Exception as e:
            print(f"[ERROR] Error creating city index: {e}")
            conn.rollback()
            raise

        # 3. candidate_hotspots table
        try:
            print("\n3. Creating candidate_hotspots table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS candidate_hotspots (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    city VARCHAR NOT NULL,
                    road_segment_id UUID REFERENCES city_roads(id),
                    centroid geometry(POINT, 4326) NOT NULL,
                    road_name VARCHAR,
                    report_count INTEGER NOT NULL,
                    report_ids UUID[],
                    avg_water_depth VARCHAR,
                    avg_weather JSONB,
                    date_first_report TIMESTAMP,
                    date_last_report TIMESTAMP,
                    status VARCHAR DEFAULT 'candidate',
                    reviewed_by UUID REFERENCES users(id),
                    reviewed_at TIMESTAMP,
                    promoted_to_hotspot_name VARCHAR,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))
            conn.commit()
            print("[OK] Created candidate_hotspots table")
        except Exception as e:
            print(f"[ERROR] Error creating candidate_hotspots table: {e}")
            conn.rollback()
            raise

        try:
            print("   Creating city index on candidate_hotspots...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_candidate_hotspots_city ON candidate_hotspots(city);
            """))
            conn.commit()
            print("[OK] Created ix_candidate_hotspots_city")
        except Exception as e:
            print(f"[ERROR] Error creating city index: {e}")
            conn.rollback()
            raise

        try:
            print("   Creating status index on candidate_hotspots...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_candidate_hotspots_status ON candidate_hotspots(status);
            """))
            conn.commit()
            print("[OK] Created ix_candidate_hotspots_status")
        except Exception as e:
            print(f"[ERROR] Error creating status index: {e}")
            conn.rollback()
            raise

        try:
            print("   Creating spatial index on candidate_hotspots.centroid...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_candidate_hotspots_geometry ON candidate_hotspots USING GIST(centroid);
            """))
            conn.commit()
            print("[OK] Created ix_candidate_hotspots_geometry")
        except Exception as e:
            print(f"[ERROR] Error creating spatial index: {e}")
            conn.rollback()
            raise

        # 4. FK constraint on reports.road_segment_id -> city_roads.id
        try:
            print("\n4. Adding FK constraint reports.road_segment_id -> city_roads.id...")
            conn.execute(text("""
                ALTER TABLE reports ADD CONSTRAINT fk_reports_road_segment
                    FOREIGN KEY (road_segment_id) REFERENCES city_roads(id) ON DELETE SET NULL;
            """))
            conn.commit()
            print("[OK] Added fk_reports_road_segment constraint")
        except Exception as e:
            print(f"[ERROR] Error adding FK constraint: {e}")
            conn.rollback()
            raise

    print("\n" + "=" * 60)
    print("[SUCCESS] Migration completed successfully!")
    print("=" * 60)
    print("\nChanges applied:")
    print("\n1. reports (new columns)")
    print("   - weather_snapshot (JSONB)        — at-report-time weather data")
    print("   - road_segment_id (UUID, FK)      — nearest OSM road segment")
    print("   - road_name (VARCHAR)             — human-readable road name")
    print("   - road_type (VARCHAR)             — OSM highway tag (primary, residential, etc.)")
    print("\n2. city_roads")
    print("   Columns: id, city, osm_id, name, road_type, is_underpass, is_bridge,")
    print("            geometry, elevation_avg, created_at")
    print("   Indexes: ix_city_roads_geometry (GIST), ix_city_roads_city")
    print("\n3. candidate_hotspots")
    print("   Columns: id, city, road_segment_id, centroid, road_name, report_count,")
    print("            report_ids, avg_water_depth, avg_weather, date_first_report,")
    print("            date_last_report, status, reviewed_by, reviewed_at,")
    print("            promoted_to_hotspot_name, notes, created_at")
    print("   Indexes: ix_candidate_hotspots_city, ix_candidate_hotspots_status,")
    print("            ix_candidate_hotspots_geometry (GIST)")
    print("\n4. FK constraint: reports.road_segment_id -> city_roads.id ON DELETE SET NULL")


def rollback():
    """Rollback migration — drop new tables and columns."""
    print("Starting rollback: ML pipeline enrichment...")

    with engine.connect() as conn:
        try:
            print("Dropping FK constraint fk_reports_road_segment...")
            conn.execute(text("""
                ALTER TABLE reports DROP CONSTRAINT IF EXISTS fk_reports_road_segment;
            """))
            conn.commit()
            print("[OK] Dropped fk_reports_road_segment")
        except Exception as e:
            print(f"[ERROR] Error dropping FK constraint: {e}")
            conn.rollback()
            raise

        try:
            print("Dropping ML columns from reports...")
            conn.execute(text("""
                ALTER TABLE reports DROP COLUMN IF EXISTS weather_snapshot;
            """))
            conn.execute(text("""
                ALTER TABLE reports DROP COLUMN IF EXISTS road_segment_id;
            """))
            conn.execute(text("""
                ALTER TABLE reports DROP COLUMN IF EXISTS road_name;
            """))
            conn.execute(text("""
                ALTER TABLE reports DROP COLUMN IF EXISTS road_type;
            """))
            conn.commit()
            print("[OK] Dropped weather_snapshot, road_segment_id, road_name, road_type from reports")
        except Exception as e:
            print(f"[ERROR] Error dropping columns from reports: {e}")
            conn.rollback()
            raise

        try:
            print("Dropping candidate_hotspots table...")
            conn.execute(text("DROP TABLE IF EXISTS candidate_hotspots;"))
            conn.commit()
            print("[OK] Dropped candidate_hotspots")
        except Exception as e:
            print(f"[ERROR] Error dropping candidate_hotspots: {e}")
            conn.rollback()
            raise

        try:
            print("Dropping city_roads table...")
            conn.execute(text("DROP TABLE IF EXISTS city_roads;"))
            conn.commit()
            print("[OK] Dropped city_roads")
        except Exception as e:
            print(f"[ERROR] Error dropping city_roads: {e}")
            conn.rollback()
            raise

    print("\n[SUCCESS] Rollback completed successfully!")


def verify():
    """Verify migration — check columns, tables, and indexes exist."""
    print("Verifying migration: ML pipeline enrichment...")
    all_ok = True

    with engine.connect() as conn:
        # Check new columns on reports
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'reports'
              AND column_name IN ('weather_snapshot', 'road_segment_id', 'road_name', 'road_type');
        """))
        found_cols = {row[0] for row in result.fetchall()}
        expected_cols = {'weather_snapshot', 'road_segment_id', 'road_name', 'road_type'}
        missing_cols = expected_cols - found_cols
        if missing_cols:
            print(f"\n[FAIL] Missing columns on reports: {missing_cols}")
            all_ok = False
        else:
            print(f"\n[OK] All 4 ML columns present on reports: {sorted(found_cols)}")

        # Check city_roads table
        result = conn.execute(text("""
            SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'city_roads');
        """))
        city_roads_exists = result.scalar()
        print(f"[{'OK' if city_roads_exists else 'FAIL'}] Table 'city_roads' exists: {city_roads_exists}")
        if not city_roads_exists:
            all_ok = False

        # Check candidate_hotspots table
        result = conn.execute(text("""
            SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'candidate_hotspots');
        """))
        candidates_exists = result.scalar()
        print(f"[{'OK' if candidates_exists else 'FAIL'}] Table 'candidate_hotspots' exists: {candidates_exists}")
        if not candidates_exists:
            all_ok = False

        if city_roads_exists:
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'city_roads'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            print(f"\n[OK] city_roads has {len(columns)} columns:")
            for col in columns:
                print(f"    - {col[0]} ({col[1]})")

        if candidates_exists:
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'candidate_hotspots'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            print(f"\n[OK] candidate_hotspots has {len(columns)} columns:")
            for col in columns:
                print(f"    - {col[0]} ({col[1]})")

        # Check indexes
        result = conn.execute(text("""
            SELECT tablename, indexname FROM pg_indexes
            WHERE tablename IN ('city_roads', 'candidate_hotspots')
            ORDER BY tablename, indexname;
        """))
        indexes = result.fetchall()
        print(f"\n[OK] Found {len(indexes)} indexes on new tables:")
        for idx in indexes:
            print(f"    - {idx[0]}.{idx[1]}")

        # Check FK constraint
        result = conn.execute(text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'reports'
              AND constraint_name = 'fk_reports_road_segment'
              AND constraint_type = 'FOREIGN KEY';
        """))
        fk_exists = result.scalar() is not None
        print(f"\n[{'OK' if fk_exists else 'FAIL'}] FK constraint fk_reports_road_segment exists: {fk_exists}")
        if not fk_exists:
            all_ok = False

    if all_ok:
        print("\n[SUCCESS] Verification completed successfully!")
    else:
        print("\n[FAIL] Verification failed. Run migration first.")
    return all_ok


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate ML pipeline enrichment tables")
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    parser.add_argument('--verify', action='store_true', help='Verify migration')
    args = parser.parse_args()

    if args.rollback:
        confirm = input(
            "[WARNING] This will DROP city_roads and candidate_hotspots tables "
            "and remove ML columns from reports. Continue? (yes/no): "
        )
        if confirm.lower() == 'yes':
            rollback()
        else:
            print("Rollback cancelled")
    elif args.verify:
        verify()
    else:
        migrate()
