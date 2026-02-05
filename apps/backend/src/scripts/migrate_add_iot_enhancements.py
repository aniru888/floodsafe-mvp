"""
Migration: Add IoT sensor enhancements for ESP32 integration

Extends:
- sensors table: user_id, name, api_key_hash, hardware_type, firmware_version
- readings table: water_segments, distance_mm, water_height_mm, is_warning, is_flood

Adds indexes for:
- sensors(user_id) - filter by owner
- sensors(api_key_hash) - fast API key lookup
- readings(sensor_id, timestamp DESC) - time-series queries

Run: python -m apps.backend.src.scripts.migrate_add_iot_enhancements
Rollback: python -m apps.backend.src.scripts.migrate_add_iot_enhancements --rollback
Verify: python -m apps.backend.src.scripts.migrate_add_iot_enhancements --verify
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from apps.backend.src.infrastructure.database import engine


def migrate():
    """Run migration to add IoT sensor enhancements."""
    print("Starting migration: IoT sensor enhancements...")
    print("=" * 60)

    with engine.connect() as conn:
        # ================================================================
        # SENSOR TABLE ENHANCEMENTS
        # ================================================================
        print("\n1. Adding columns to sensors table...")

        # user_id - FK to users table for sensor ownership
        try:
            print("   Adding user_id column...")
            conn.execute(text("""
                ALTER TABLE sensors
                ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;
            """))
            conn.commit()
            print("   [OK] user_id column added")
        except Exception as e:
            print(f"   [WARN] user_id: {e}")
            conn.rollback()

        # name - human-readable sensor name
        try:
            print("   Adding name column...")
            conn.execute(text("""
                ALTER TABLE sensors
                ADD COLUMN IF NOT EXISTS name VARCHAR(100);
            """))
            conn.commit()
            print("   [OK] name column added")
        except Exception as e:
            print(f"   [WARN] name: {e}")
            conn.rollback()

        # api_key_hash - SHA256 hash for authentication
        try:
            print("   Adding api_key_hash column...")
            conn.execute(text("""
                ALTER TABLE sensors
                ADD COLUMN IF NOT EXISTS api_key_hash VARCHAR(128) UNIQUE;
            """))
            conn.commit()
            print("   [OK] api_key_hash column added")
        except Exception as e:
            print(f"   [WARN] api_key_hash: {e}")
            conn.rollback()

        # hardware_type - sensor hardware model
        try:
            print("   Adding hardware_type column...")
            conn.execute(text("""
                ALTER TABLE sensors
                ADD COLUMN IF NOT EXISTS hardware_type VARCHAR(64) DEFAULT 'ESP32S3_GROVE_VL53L0X';
            """))
            conn.commit()
            print("   [OK] hardware_type column added")
        except Exception as e:
            print(f"   [WARN] hardware_type: {e}")
            conn.rollback()

        # firmware_version - installed firmware version
        try:
            print("   Adding firmware_version column...")
            conn.execute(text("""
                ALTER TABLE sensors
                ADD COLUMN IF NOT EXISTS firmware_version VARCHAR(16);
            """))
            conn.commit()
            print("   [OK] firmware_version column added")
        except Exception as e:
            print(f"   [WARN] firmware_version: {e}")
            conn.rollback()

        # ================================================================
        # READING TABLE ENHANCEMENTS
        # ================================================================
        print("\n2. Adding columns to readings table...")

        # water_segments - 0-20 from Grove sensor
        try:
            print("   Adding water_segments column...")
            conn.execute(text("""
                ALTER TABLE readings
                ADD COLUMN IF NOT EXISTS water_segments INTEGER;
            """))
            conn.commit()
            print("   [OK] water_segments column added")
        except Exception as e:
            print(f"   [WARN] water_segments: {e}")
            conn.rollback()

        # distance_mm - VL53L0X raw reading
        try:
            print("   Adding distance_mm column...")
            conn.execute(text("""
                ALTER TABLE readings
                ADD COLUMN IF NOT EXISTS distance_mm FLOAT;
            """))
            conn.commit()
            print("   [OK] distance_mm column added")
        except Exception as e:
            print(f"   [WARN] distance_mm: {e}")
            conn.rollback()

        # water_height_mm - calculated water height
        try:
            print("   Adding water_height_mm column...")
            conn.execute(text("""
                ALTER TABLE readings
                ADD COLUMN IF NOT EXISTS water_height_mm FLOAT;
            """))
            conn.commit()
            print("   [OK] water_height_mm column added")
        except Exception as e:
            print(f"   [WARN] water_height_mm: {e}")
            conn.rollback()

        # water_percent_strips - % from strip sensor
        try:
            print("   Adding water_percent_strips column...")
            conn.execute(text("""
                ALTER TABLE readings
                ADD COLUMN IF NOT EXISTS water_percent_strips FLOAT;
            """))
            conn.commit()
            print("   [OK] water_percent_strips column added")
        except Exception as e:
            print(f"   [WARN] water_percent_strips: {e}")
            conn.rollback()

        # water_percent_distance - % from distance sensor
        try:
            print("   Adding water_percent_distance column...")
            conn.execute(text("""
                ALTER TABLE readings
                ADD COLUMN IF NOT EXISTS water_percent_distance FLOAT;
            """))
            conn.commit()
            print("   [OK] water_percent_distance column added")
        except Exception as e:
            print(f"   [WARN] water_percent_distance: {e}")
            conn.rollback()

        # is_warning - WARNING status flag
        try:
            print("   Adding is_warning column...")
            conn.execute(text("""
                ALTER TABLE readings
                ADD COLUMN IF NOT EXISTS is_warning BOOLEAN DEFAULT FALSE;
            """))
            conn.commit()
            print("   [OK] is_warning column added")
        except Exception as e:
            print(f"   [WARN] is_warning: {e}")
            conn.rollback()

        # is_flood - FLOOD status flag
        try:
            print("   Adding is_flood column...")
            conn.execute(text("""
                ALTER TABLE readings
                ADD COLUMN IF NOT EXISTS is_flood BOOLEAN DEFAULT FALSE;
            """))
            conn.commit()
            print("   [OK] is_flood column added")
        except Exception as e:
            print(f"   [WARN] is_flood: {e}")
            conn.rollback()

        # ================================================================
        # INDEXES
        # ================================================================
        print("\n3. Creating indexes...")

        # idx_sensors_user_id - filter sensors by owner
        try:
            print("   Creating idx_sensors_user_id...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sensors_user_id
                ON sensors(user_id);
            """))
            conn.commit()
            print("   [OK] idx_sensors_user_id created")
        except Exception as e:
            print(f"   [WARN] idx_sensors_user_id: {e}")
            conn.rollback()

        # idx_sensors_api_key_hash - fast API key lookup
        try:
            print("   Creating idx_sensors_api_key_hash...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sensors_api_key_hash
                ON sensors(api_key_hash);
            """))
            conn.commit()
            print("   [OK] idx_sensors_api_key_hash created")
        except Exception as e:
            print(f"   [WARN] idx_sensors_api_key_hash: {e}")
            conn.rollback()

        # idx_readings_sensor_timestamp - time-series queries
        try:
            print("   Creating idx_readings_sensor_timestamp...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_readings_sensor_timestamp
                ON readings(sensor_id, timestamp DESC);
            """))
            conn.commit()
            print("   [OK] idx_readings_sensor_timestamp created")
        except Exception as e:
            print(f"   [WARN] idx_readings_sensor_timestamp: {e}")
            conn.rollback()

    print("\n" + "=" * 60)
    print("[SUCCESS] Migration completed!")
    print("=" * 60)
    print("\nEnhanced tables:")
    print("\n1. sensors (new columns):")
    print("   - user_id (UUID, FK -> users) - sensor ownership")
    print("   - name (VARCHAR(100)) - human-readable name")
    print("   - api_key_hash (VARCHAR(128), UNIQUE) - API auth")
    print("   - hardware_type (VARCHAR(64)) - sensor model")
    print("   - firmware_version (VARCHAR(16)) - firmware version")
    print("\n2. readings (new columns):")
    print("   - water_segments (INTEGER) - Grove sensor 0-20")
    print("   - distance_mm (FLOAT) - VL53L0X raw reading")
    print("   - water_height_mm (FLOAT) - calculated height")
    print("   - water_percent_strips (FLOAT) - % from strips")
    print("   - water_percent_distance (FLOAT) - % from distance")
    print("   - is_warning (BOOLEAN) - WARNING flag")
    print("   - is_flood (BOOLEAN) - FLOOD flag")
    print("\n3. Indexes:")
    print("   - idx_sensors_user_id")
    print("   - idx_sensors_api_key_hash")
    print("   - idx_readings_sensor_timestamp")


def rollback():
    """Rollback migration - drop added columns and indexes."""
    print("Starting rollback: IoT sensor enhancements...")
    print("[WARNING] This will remove IoT-specific columns but preserve existing data.")

    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Rollback cancelled")
        return

    with engine.connect() as conn:
        # Drop indexes
        print("\n1. Dropping indexes...")
        for idx in ['idx_sensors_user_id', 'idx_sensors_api_key_hash', 'idx_readings_sensor_timestamp']:
            try:
                conn.execute(text(f"DROP INDEX IF EXISTS {idx};"))
                conn.commit()
                print(f"   [OK] Dropped {idx}")
            except Exception as e:
                print(f"   [WARN] {idx}: {e}")
                conn.rollback()

        # Drop readings columns
        print("\n2. Dropping readings columns...")
        for col in ['water_segments', 'distance_mm', 'water_height_mm',
                    'water_percent_strips', 'water_percent_distance',
                    'is_warning', 'is_flood']:
            try:
                conn.execute(text(f"ALTER TABLE readings DROP COLUMN IF EXISTS {col};"))
                conn.commit()
                print(f"   [OK] Dropped readings.{col}")
            except Exception as e:
                print(f"   [WARN] readings.{col}: {e}")
                conn.rollback()

        # Drop sensors columns
        print("\n3. Dropping sensors columns...")
        for col in ['user_id', 'name', 'api_key_hash', 'hardware_type', 'firmware_version']:
            try:
                conn.execute(text(f"ALTER TABLE sensors DROP COLUMN IF EXISTS {col};"))
                conn.commit()
                print(f"   [OK] Dropped sensors.{col}")
            except Exception as e:
                print(f"   [WARN] sensors.{col}: {e}")
                conn.rollback()

    print("\n[SUCCESS] Rollback completed!")


def verify():
    """Verify migration - check columns and indexes exist."""
    print("Verifying migration: IoT sensor enhancements...")

    all_pass = True

    with engine.connect() as conn:
        # Check sensors columns
        print("\n1. Checking sensors table columns...")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sensors'
            ORDER BY ordinal_position;
        """))
        columns = {row[0]: row[1] for row in result.fetchall()}

        expected_sensor_cols = ['user_id', 'name', 'api_key_hash', 'hardware_type', 'firmware_version']
        for col in expected_sensor_cols:
            exists = col in columns
            status = "OK" if exists else "MISSING"
            print(f"   [{status}] sensors.{col}")
            if not exists:
                all_pass = False

        # Check readings columns
        print("\n2. Checking readings table columns...")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'readings'
            ORDER BY ordinal_position;
        """))
        columns = {row[0]: row[1] for row in result.fetchall()}

        expected_reading_cols = ['water_segments', 'distance_mm', 'water_height_mm',
                                 'water_percent_strips', 'water_percent_distance',
                                 'is_warning', 'is_flood']
        for col in expected_reading_cols:
            exists = col in columns
            status = "OK" if exists else "MISSING"
            print(f"   [{status}] readings.{col}")
            if not exists:
                all_pass = False

        # Check indexes
        print("\n3. Checking indexes...")
        result = conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename IN ('sensors', 'readings')
            AND indexname LIKE 'idx_%';
        """))
        indexes = [row[0] for row in result.fetchall()]

        expected_indexes = ['idx_sensors_user_id', 'idx_sensors_api_key_hash', 'idx_readings_sensor_timestamp']
        for idx in expected_indexes:
            exists = idx in indexes
            status = "OK" if exists else "MISSING"
            print(f"   [{status}] {idx}")
            if not exists:
                all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("[SUCCESS] All migration components verified!")
    else:
        print("[FAIL] Some components missing - run migration first")
    print("=" * 60)

    return all_pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate IoT sensor enhancements")
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    parser.add_argument('--verify', action='store_true', help='Verify migration')
    args = parser.parse_args()

    if args.rollback:
        rollback()
    elif args.verify:
        verify()
    else:
        migrate()
