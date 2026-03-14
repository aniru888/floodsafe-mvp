"""
Community Intelligence Database Migration
==========================================
Creates 3 new tables and adds columns to 3 existing tables.
All new columns are DEFAULT NULL for backward compatibility.

Tables created:
  - historical_flood_episodes (Groundsource deduped events)
  - groundsource_clusters (DBSCAN clustering results)
  - watch_area_fhi_history (FHI time series per watch area)

Tables modified:
  - watch_areas (+15 columns)
  - reports (+6 columns)
  - candidate_hotspots (+6 columns)

Usage:
  # Local DB
  DATABASE_URL=postgresql://user:password@localhost:5432/floodsafe python scripts/migrate_community_intelligence.py

  # Supabase (via Management API)
  SUPABASE_PROJECT_ID=udblirsscaghsepuxxqv SUPABASE_ACCESS_TOKEN=sbp_... python scripts/migrate_community_intelligence.py
"""

import os
import sys
import json
import urllib.request

# ─── SQL Definitions ─────────────────────────────────────────────

CREATE_TABLES_SQL = """
-- 1. Historical flood episodes (Groundsource deduped)
CREATE TABLE IF NOT EXISTS historical_flood_episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city VARCHAR(50) NOT NULL CHECK (city IN ('delhi','bangalore','yogyakarta','singapore','indore')),
    avg_area_km2 DOUBLE PRECISION,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    article_count INTEGER DEFAULT 1,
    source_event_ids TEXT[],
    centroid GEOMETRY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hfe_city_date ON historical_flood_episodes(city, start_date DESC);
CREATE INDEX IF NOT EXISTS idx_hfe_centroid ON historical_flood_episodes USING GIST(centroid);

-- 2. Groundsource clusters (DBSCAN output)
CREATE TABLE IF NOT EXISTS groundsource_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city VARCHAR(50) NOT NULL CHECK (city IN ('delhi','bangalore','yogyakarta','singapore','indore')),
    episode_count INTEGER NOT NULL,
    total_article_count INTEGER NOT NULL,
    first_episode DATE NOT NULL,
    last_episode DATE NOT NULL,
    recency_score FLOAT,
    avg_area_km2 FLOAT,
    nearest_hotspot_name VARCHAR,
    nearest_hotspot_distance_m FLOAT,
    overlap_status VARCHAR(20) NOT NULL CHECK (overlap_status IN ('CONFIRMED', 'PERIPHERAL', 'MISSED')),
    confidence VARCHAR(10),
    infra_signal VARCHAR(20),
    admin_status VARCHAR(20) DEFAULT 'pending',
    admin_notes TEXT,
    centroid GEOMETRY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gc_centroid ON groundsource_clusters USING GIST(centroid);

-- 3. Watch area FHI history (time series)
CREATE TABLE IF NOT EXISTS watch_area_fhi_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_area_id UUID NOT NULL REFERENCES watch_areas(id) ON DELETE CASCADE,
    fhi_score FLOAT NOT NULL,
    fhi_level VARCHAR NOT NULL,
    fhi_components JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_wafh_wa_time ON watch_area_fhi_history(watch_area_id, recorded_at DESC);
"""

ALTER_WATCH_AREAS_SQL = """
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS road_segment_id UUID DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS road_name VARCHAR DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS snapped_location GEOMETRY(POINT, 4326) DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS fhi_score FLOAT DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS fhi_level VARCHAR DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS fhi_components JSONB DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS fhi_updated_at TIMESTAMP DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS weather_snapshot JSONB DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS is_personal_hotspot BOOLEAN DEFAULT FALSE;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS hotspot_ref UUID DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS city VARCHAR DEFAULT NULL;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS visibility VARCHAR DEFAULT 'circles';
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'map';
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS alert_radius FLOAT DEFAULT 300.0;
DO $$ BEGIN
    ALTER TABLE watch_areas ADD CONSTRAINT chk_wa_alert_radius CHECK (alert_radius >= 50 AND alert_radius <= 10000);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS historical_episode_count INTEGER DEFAULT 0;
ALTER TABLE watch_areas ADD COLUMN IF NOT EXISTS nearest_cluster_id UUID DEFAULT NULL;

CREATE INDEX IF NOT EXISTS ix_wa_snapped ON watch_areas USING GIST(snapped_location);
CREATE INDEX IF NOT EXISTS ix_wa_personal ON watch_areas(is_personal_hotspot) WHERE is_personal_hotspot = TRUE;
CREATE INDEX IF NOT EXISTS ix_wa_user_id ON watch_areas(user_id);
CREATE INDEX IF NOT EXISTS ix_wa_city ON watch_areas(city);
"""

ALTER_REPORTS_SQL = """
ALTER TABLE reports ADD COLUMN IF NOT EXISTS fhi_score FLOAT;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS fhi_level VARCHAR;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS fhi_components JSONB;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS nearest_hotspot_id VARCHAR;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS nearest_hotspot_distance FLOAT;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS historical_episode_count INTEGER DEFAULT 0;
"""

ALTER_CANDIDATE_HOTSPOTS_SQL = """
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS submitted_by UUID;
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS submission_type VARCHAR DEFAULT 'automated';
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS pin_ids UUID[];
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS pin_count INTEGER DEFAULT 0;
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS avg_fhi FLOAT;
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS fhi_history_summary JSONB;
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS groundsource_cluster_id UUID;
ALTER TABLE candidate_hotspots ADD COLUMN IF NOT EXISTS historical_episode_count INTEGER DEFAULT 0;
"""

VERIFY_SQL = """
SELECT 'historical_flood_episodes' as tbl, count(*) FROM historical_flood_episodes
UNION ALL
SELECT 'groundsource_clusters', count(*) FROM groundsource_clusters
UNION ALL
SELECT 'watch_area_fhi_history', count(*) FROM watch_area_fhi_history;
"""

ROLLBACK_SQL = """
DROP TABLE IF EXISTS watch_area_fhi_history CASCADE;
DROP TABLE IF EXISTS groundsource_clusters CASCADE;
DROP TABLE IF EXISTS historical_flood_episodes CASCADE;

ALTER TABLE watch_areas DROP COLUMN IF EXISTS city;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS is_personal_hotspot;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS source;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS visibility;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS road_segment_id;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS road_name;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS snapped_location;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS fhi_score;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS fhi_level;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS fhi_components;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS fhi_updated_at;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS weather_snapshot;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS hotspot_ref;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS updated_at;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS alert_radius;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS historical_episode_count;
ALTER TABLE watch_areas DROP COLUMN IF EXISTS nearest_cluster_id;

ALTER TABLE reports DROP COLUMN IF EXISTS fhi_score;
ALTER TABLE reports DROP COLUMN IF EXISTS fhi_level;
ALTER TABLE reports DROP COLUMN IF EXISTS fhi_components;
ALTER TABLE reports DROP COLUMN IF EXISTS nearest_hotspot_id;
ALTER TABLE reports DROP COLUMN IF EXISTS nearest_hotspot_distance;
ALTER TABLE reports DROP COLUMN IF EXISTS historical_episode_count;

ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS submitted_by;
ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS submission_type;
ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS pin_ids;
ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS pin_count;
ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS avg_fhi;
ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS fhi_history_summary;
ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS groundsource_cluster_id;
ALTER TABLE candidate_hotspots DROP COLUMN IF EXISTS historical_episode_count;
"""


def run_local(sql: str):
    """Execute SQL against local PostgreSQL."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/floodsafe")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cursor = conn.cursor()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt and not stmt.startswith("--"):
            try:
                cursor.execute(stmt)
                print(f"  OK: {stmt[:80]}...")
            except Exception as e:
                print(f"  WARN: {e} — {stmt[:80]}...")
    cursor.close()
    conn.close()


def run_supabase(sql: str):
    """Execute SQL via Supabase Management API."""
    project_id = os.environ["SUPABASE_PROJECT_ID"]
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    url = f"https://api.supabase.com/v1/projects/{project_id}/database/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"  OK: {len(result)} result(s)")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ERROR ({e.code}): {body[:200]}")
        sys.exit(1)


def main():
    rollback = "--rollback" in sys.argv
    verify_only = "--verify" in sys.argv
    use_supabase = "SUPABASE_PROJECT_ID" in os.environ

    runner = run_supabase if use_supabase else run_local
    target = "Supabase" if use_supabase else "local DB"

    if rollback:
        print(f"ROLLING BACK community intelligence tables on {target}...")
        runner(ROLLBACK_SQL)
        print("Rollback complete.")
        return

    if verify_only:
        print(f"VERIFYING community intelligence tables on {target}...")
        runner(VERIFY_SQL)
        return

    print(f"MIGRATING community intelligence tables on {target}...")

    print("\n[1/4] Creating new tables...")
    runner(CREATE_TABLES_SQL)

    print("\n[2/4] Altering watch_areas...")
    runner(ALTER_WATCH_AREAS_SQL)

    print("\n[3/4] Altering reports...")
    runner(ALTER_REPORTS_SQL)

    print("\n[4/4] Altering candidate_hotspots...")
    runner(ALTER_CANDIDATE_HOTSPOTS_SQL)

    print("\nVERIFYING...")
    runner(VERIFY_SQL)

    print("\nMigration complete. Run with --verify to re-check, --rollback to undo.")


if __name__ == "__main__":
    main()
