"""
Migration: Create Safety Circles tables for family/community group notifications

Creates:
- safety_circles table: Circle groups (family, school, apartment, etc.)
- circle_members table: Members (registered users + non-registered phone/email contacts)
- circle_alerts table: Notifications generated when a circle member creates a flood report

Run (from project root): python -m apps.backend.src.scripts.migrate_add_safety_circles
Run (in Docker): docker-compose exec backend python -m src.scripts.migrate_add_safety_circles
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
    """Run migration to create Safety Circles tables."""
    print("Starting migration: Safety Circles tables...")

    with engine.connect() as conn:
        # 1. Create safety_circles table
        try:
            print("\n1. Creating safety_circles table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS safety_circles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(500),
                    circle_type VARCHAR(30) NOT NULL DEFAULT 'custom',
                    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    invite_code VARCHAR(12) UNIQUE NOT NULL,
                    max_members INTEGER NOT NULL DEFAULT 50,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """))
            conn.commit()
            print("[OK] Created safety_circles table")
        except Exception as e:
            print(f"[ERROR] Error creating safety_circles table: {e}")
            conn.rollback()
            raise

        # 2. Create circle_members table
        try:
            print("\n2. Creating circle_members table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS circle_members (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    circle_id UUID NOT NULL REFERENCES safety_circles(id) ON DELETE CASCADE,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    phone VARCHAR(20),
                    email VARCHAR(255),
                    display_name VARCHAR(100),
                    role VARCHAR(10) NOT NULL DEFAULT 'member',
                    is_muted BOOLEAN DEFAULT FALSE,
                    notify_whatsapp BOOLEAN DEFAULT TRUE,
                    notify_sms BOOLEAN DEFAULT TRUE,
                    notify_email BOOLEAN DEFAULT FALSE,
                    joined_at TIMESTAMP DEFAULT NOW(),
                    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,

                    CONSTRAINT chk_member_identity
                        CHECK (user_id IS NOT NULL OR phone IS NOT NULL OR email IS NOT NULL)
                );
            """))
            conn.commit()
            print("[OK] Created circle_members table")
        except Exception as e:
            print(f"[ERROR] Error creating circle_members table: {e}")
            conn.rollback()
            raise

        # 3. Create unique partial index (registered users can only be in a circle once)
        try:
            print("   Creating unique index for registered members...")
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_circle_registered_user
                ON circle_members(circle_id, user_id)
                WHERE user_id IS NOT NULL;
            """))
            conn.commit()
            print("[OK] Created partial unique index uq_circle_registered_user")
        except Exception as e:
            print(f"[ERROR] Error creating unique index: {e}")
            conn.rollback()
            raise

        # 4. Create circle_alerts table
        try:
            print("\n3. Creating circle_alerts table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS circle_alerts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    circle_id UUID NOT NULL REFERENCES safety_circles(id) ON DELETE CASCADE,
                    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                    reporter_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    member_id UUID NOT NULL REFERENCES circle_members(id) ON DELETE CASCADE,
                    message VARCHAR(500) NOT NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    notification_sent BOOLEAN DEFAULT FALSE,
                    notification_channel VARCHAR(20),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))
            conn.commit()
            print("[OK] Created circle_alerts table")
        except Exception as e:
            print(f"[ERROR] Error creating circle_alerts table: {e}")
            conn.rollback()
            raise

        # 5. Create indexes for safety_circles
        try:
            print("\n4. Creating indexes for safety_circles...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_safety_circles_created_by
                ON safety_circles(created_by);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_safety_circles_invite_code
                ON safety_circles(invite_code);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_safety_circles_is_active
                ON safety_circles(is_active) WHERE is_active = TRUE;
            """))
            conn.commit()
            print("[OK] Created safety_circles indexes")
        except Exception as e:
            print(f"[ERROR] Error creating safety_circles indexes: {e}")
            conn.rollback()
            raise

        # 6. Create indexes for circle_members
        try:
            print("   Creating indexes for circle_members...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_members_circle_id
                ON circle_members(circle_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_members_user_id
                ON circle_members(user_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_members_phone
                ON circle_members(phone);
            """))
            conn.commit()
            print("[OK] Created circle_members indexes")
        except Exception as e:
            print(f"[ERROR] Error creating circle_members indexes: {e}")
            conn.rollback()
            raise

        # 7. Create indexes for circle_alerts
        try:
            print("   Creating indexes for circle_alerts...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_alerts_member_id
                ON circle_alerts(member_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_alerts_circle_id
                ON circle_alerts(circle_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_alerts_report_id
                ON circle_alerts(report_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_alerts_unread
                ON circle_alerts(is_read) WHERE is_read = FALSE;
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_circle_alerts_created_at
                ON circle_alerts(created_at DESC);
            """))
            conn.commit()
            print("[OK] Created circle_alerts indexes")
        except Exception as e:
            print(f"[ERROR] Error creating circle_alerts indexes: {e}")
            conn.rollback()
            raise

    print("\n" + "=" * 60)
    print("[SUCCESS] Migration completed successfully!")
    print("=" * 60)
    print("\nCreated tables:")
    print("  1. safety_circles - Circle groups (family, school, apartment, etc.)")
    print("     Columns: id, name, description, circle_type, created_by, invite_code,")
    print("              max_members, is_active, created_at, updated_at")
    print("  2. circle_members - Members (registered + non-registered contacts)")
    print("     Columns: id, circle_id, user_id, phone, email, display_name, role,")
    print("              is_muted, notify_whatsapp, notify_sms, notify_email,")
    print("              joined_at, invited_by")
    print("  3. circle_alerts - Notifications for circle members on flood reports")
    print("     Columns: id, circle_id, report_id, reporter_user_id, member_id,")
    print("              message, is_read, notification_sent, notification_channel,")
    print("              created_at")
    print("\nCircle types: family (20), school (500), apartment (200),")
    print("              neighborhood (1000), custom (50)")


def rollback():
    """Rollback migration - drop Safety Circles tables."""
    print("Starting rollback: Safety Circles tables...")

    with engine.connect() as conn:
        # Drop in reverse order (circle_alerts → circle_members → safety_circles)
        for table in ['circle_alerts', 'circle_members', 'safety_circles']:
            try:
                print(f"Dropping {table} table...")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                conn.commit()
                print(f"[OK] Dropped {table} table")
            except Exception as e:
                print(f"[ERROR] Error dropping {table} table: {e}")
                conn.rollback()
                raise

    print("\n[SUCCESS] Rollback completed successfully!")


def verify():
    """Verify migration - check all tables and indexes exist."""
    print("Verifying migration: Safety Circles tables...")
    all_ok = True

    with engine.connect() as conn:
        for table_name in ['safety_circles', 'circle_members', 'circle_alerts']:
            # Check table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = :table_name
                );
            """), {"table_name": table_name})
            table_exists = result.scalar()
            status = 'OK' if table_exists else 'FAIL'
            print(f"\n[{status}] Table '{table_name}' exists: {table_exists}")

            if not table_exists:
                all_ok = False
                continue

            # Check columns
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = :table_name
                ORDER BY ordinal_position;
            """), {"table_name": table_name})
            columns = result.fetchall()
            print(f"  [{len(columns)} columns]:")
            for col in columns:
                print(f"    - {col[0]} ({col[1]})")

            # Check indexes
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = :table_name;
            """), {"table_name": table_name})
            indexes = result.fetchall()
            print(f"  [{len(indexes)} indexes]:")
            for idx in indexes:
                print(f"    - {idx[0]}")

    if all_ok:
        print("\n[SUCCESS] Verification completed — all tables present!")
    else:
        print("\n[FAIL] Some tables are missing. Run migration first.")
    return all_ok


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate Safety Circles tables")
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    parser.add_argument('--verify', action='store_true', help='Verify migration')
    args = parser.parse_args()

    if args.rollback:
        confirm = input(
            "[WARNING] This will DROP safety_circles, circle_members, and circle_alerts "
            "tables and ALL their data. Continue? (yes/no): "
        )
        if confirm.lower() == 'yes':
            rollback()
        else:
            print("Rollback cancelled")
    elif args.verify:
        verify()
    else:
        migrate()
