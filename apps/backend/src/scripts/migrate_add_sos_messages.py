"""
Migration: Create SOS Messages table for offline emergency alerts

Creates:
- sos_messages table: Emergency SOS messages sent to safety contacts
  Tracks per-recipient delivery status, supports offline queueing on frontend

Run (from project root): python -m apps.backend.src.scripts.migrate_add_sos_messages
Run (in Docker): docker-compose exec backend python -m src.scripts.migrate_add_sos_messages
Rollback: Add --rollback flag
Verify: Add --verify flag
"""
import sys
from pathlib import Path

# Add project root to path for local development
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

# Try importing from Docker path first, then local path
try:
    from src.infrastructure.database import engine
except ImportError:
    from apps.backend.src.infrastructure.database import engine


def migrate():
    """Run migration to create sos_messages table."""
    print("Starting migration: SOS Messages table...")

    with engine.connect() as conn:
        # 1. Create sos_messages table
        try:
            print("\n1. Creating sos_messages table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sos_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    message VARCHAR(500) NOT NULL,
                    location GEOGRAPHY(POINT, 4326),
                    recipients_json JSONB NOT NULL,
                    channel VARCHAR(20) NOT NULL DEFAULT 'sms',
                    status VARCHAR(20) NOT NULL DEFAULT 'queued',
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    error_log TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    sent_at TIMESTAMP
                );
            """))
            conn.commit()
            print("[OK] Created sos_messages table")
        except Exception as e:
            print(f"[ERROR] Error creating sos_messages table: {e}")
            conn.rollback()
            raise

        # 2. Create indexes
        try:
            print("\n2. Creating indexes for sos_messages...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_sos_messages_user_id
                ON sos_messages(user_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_sos_messages_created_at
                ON sos_messages(created_at DESC);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_sos_messages_status
                ON sos_messages(status);
            """))
            conn.commit()
            print("[OK] Created indexes for sos_messages")
        except Exception as e:
            print(f"[ERROR] Error creating indexes: {e}")
            conn.rollback()
            raise

    print("\n" + "=" * 60)
    print("[SUCCESS] Migration completed successfully!")
    print("=" * 60)
    print("\nCreated table:")
    print("  sos_messages - Emergency SOS messages with delivery tracking")
    print("    Columns:")
    print("      - id (UUID, PK)")
    print("      - user_id (UUID, FK -> users)")
    print("      - message (VARCHAR 500, emergency message)")
    print("      - location (GEOGRAPHY POINT, optional GPS coords)")
    print("      - recipients_json (JSONB, per-recipient delivery results)")
    print("      - channel (VARCHAR 20, 'sms' or 'whatsapp')")
    print("      - status (VARCHAR 20, 'queued'/'sending'/'sent'/'partial'/'failed')")
    print("      - sent_count (INT, successfully sent count)")
    print("      - failed_count (INT, failed delivery count)")
    print("      - error_log (TEXT, newline-separated error messages)")
    print("      - created_at (TIMESTAMP, when queued)")
    print("      - sent_at (TIMESTAMP, when sending completed)")
    print("\nIndexes:")
    print("  - ix_sos_messages_user_id")
    print("  - ix_sos_messages_created_at (DESC)")
    print("  - ix_sos_messages_status")


def rollback():
    """Rollback migration - drop sos_messages table."""
    print("Starting rollback: SOS Messages table...")

    with engine.connect() as conn:
        try:
            print("Dropping sos_messages table...")
            conn.execute(text("DROP TABLE IF EXISTS sos_messages CASCADE;"))
            conn.commit()
            print("[OK] Dropped sos_messages table")
        except Exception as e:
            print(f"[ERROR] Error dropping sos_messages table: {e}")
            conn.rollback()
            raise

    print("\n[SUCCESS] Rollback completed successfully!")


def verify():
    """Verify migration - check table and indexes exist."""
    print("Verifying migration: SOS Messages table...")
    all_ok = True

    with engine.connect() as conn:
        # Check table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'sos_messages'
            );
        """))
        table_exists = result.scalar()
        status = 'OK' if table_exists else 'FAIL'
        print(f"\n[{status}] Table 'sos_messages' exists: {table_exists}")

        if not table_exists:
            all_ok = False
        else:
            # Check columns
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'sos_messages'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            print(f"  [{len(columns)} columns]:")
            for col in columns:
                print(f"    - {col[0]} ({col[1]})")

            # Check indexes
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'sos_messages';
            """))
            indexes = result.fetchall()
            print(f"  [{len(indexes)} indexes]:")
            for idx in indexes:
                print(f"    - {idx[0]}")

    if all_ok:
        print("\n[SUCCESS] Verification completed — sos_messages table present!")
    else:
        print("\n[FAIL] Table is missing. Run migration first.")
    return all_ok


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate SOS Messages table")
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    parser.add_argument('--verify', action='store_true', help='Verify migration')
    args = parser.parse_args()

    if args.rollback:
        confirm = input(
            "[WARNING] This will DROP sos_messages table and ALL its data. "
            "Continue? (yes/no): "
        )
        if confirm.lower() == 'yes':
            rollback()
        else:
            print("Rollback cancelled")
    elif args.verify:
        verify()
    else:
        migrate()
