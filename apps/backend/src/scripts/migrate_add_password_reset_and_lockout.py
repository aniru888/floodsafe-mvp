"""
Migration: Add password_reset_tokens table and account lockout fields

Creates:
- password_reset_tokens table for forgot-password flow
- failed_login_attempts column on users table (for account lockout)
- locked_until column on users table (for account lockout)

Run: python -m apps.backend.src.scripts.migrate_add_password_reset_and_lockout
Rollback: python -m apps.backend.src.scripts.migrate_add_password_reset_and_lockout --rollback
Verify: python -m apps.backend.src.scripts.migrate_add_password_reset_and_lockout --verify
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from apps.backend.src.infrastructure.database import engine


def migrate():
    """Run migration."""
    print("Starting migration: password_reset_tokens + account lockout...")

    with engine.connect() as conn:
        # 1. Create password_reset_tokens table
        try:
            print("\n1. Creating password_reset_tokens table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    used_at TIMESTAMP DEFAULT NULL
                );
            """))
            conn.commit()
            print("   password_reset_tokens table created")
        except Exception as e:
            print(f"   Error: {e}")
            conn.rollback()

        # 2. Add index on token_hash
        try:
            print("2. Creating index on token_hash...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_token_hash
                ON password_reset_tokens(token_hash);
            """))
            conn.commit()
            print("   Index created")
        except Exception as e:
            print(f"   Error: {e}")
            conn.rollback()

        # 3. Add account lockout columns to users table
        try:
            print("3. Adding failed_login_attempts column...")
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0;
            """))
            conn.commit()
            print("   failed_login_attempts column added")
        except Exception as e:
            print(f"   Error: {e}")
            conn.rollback()

        try:
            print("4. Adding locked_until column...")
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP DEFAULT NULL;
            """))
            conn.commit()
            print("   locked_until column added")
        except Exception as e:
            print(f"   Error: {e}")
            conn.rollback()

    print("\nMigration complete!")


def rollback():
    """Rollback migration."""
    print("Rolling back migration...")

    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS locked_until;"))
            conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS failed_login_attempts;"))
            conn.execute(text("DROP TABLE IF EXISTS password_reset_tokens;"))
            conn.commit()
            print("Rollback complete")
        except Exception as e:
            print(f"Rollback error: {e}")
            conn.rollback()


def verify():
    """Verify migration was applied."""
    print("Verifying migration...")

    with engine.connect() as conn:
        # Check table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'password_reset_tokens'
            );
        """))
        table_exists = result.scalar()
        print(f"  password_reset_tokens table: {'EXISTS' if table_exists else 'MISSING'}")

        # Check lockout columns
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users'
            AND column_name IN ('failed_login_attempts', 'locked_until');
        """))
        columns = [row[0] for row in result]
        print(f"  Lockout columns: {columns}")

        if table_exists and len(columns) == 2:
            print("\nVerification PASSED")
        else:
            print("\nVerification FAILED")


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        rollback()
    elif "--verify" in sys.argv:
        verify()
    else:
        migrate()
