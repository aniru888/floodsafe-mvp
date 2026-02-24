"""
Migration: Add fcm_token and fcm_token_updated_at columns to users table.

Run this against Supabase or local database:
    python scripts/migrate_add_fcm_token.py           # Auto-detect
    python scripts/migrate_add_fcm_token.py supabase   # Force Supabase Management API
    python scripts/migrate_add_fcm_token.py local      # Force direct connection
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SQL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR;
ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token_updated_at TIMESTAMPTZ;
"""

VERIFY_SQL = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'users' AND column_name LIKE 'fcm%'
ORDER BY column_name;
"""

ROLLBACK_SQL = """
ALTER TABLE users DROP COLUMN IF EXISTS fcm_token;
ALTER TABLE users DROP COLUMN IF EXISTS fcm_token_updated_at;
"""


def migrate_local():
    """Migrate via direct database connection (requires IPv6 for Supabase)."""
    from sqlalchemy import create_engine, text
    from src.infrastructure.database import create_database_url

    database_url = create_database_url()
    # Determine connect_args based on host
    url_str = str(database_url)
    host = url_str.split('@')[1].split(':')[0] if '@' in url_str else ''
    connect_args = {}
    if 'localhost' not in host and '127.0.0.1' not in host and host != 'db':
        connect_args = {
            "sslmode": "require",
            "options": "-c search_path=public,tiger,extensions",
        }

    engine = create_engine(database_url, connect_args=connect_args)
    try:
        with engine.connect() as conn:
            conn.execute(text(SQL))
            conn.commit()

            # Verify
            result = conn.execute(text(VERIFY_SQL))
            rows = result.fetchall()
            if len(rows) >= 2:
                print(f"Migration verified: {len(rows)} fcm columns found")
                for row in rows:
                    print(f"  - {row[0]}: {row[1]}")
            else:
                print(f"WARNING: Expected 2 columns, found {len(rows)}")
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        sys.exit(1)

    print("Migration complete: added fcm_token columns to users")


def migrate_supabase():
    """Migrate via Supabase Management API (for IPv6-only hosts)."""
    import requests

    token = os.getenv('SUPABASE_ACCESS_TOKEN')
    project_ref = os.getenv('SUPABASE_PROJECT_REF', 'udblirsscaghsepuxxqv')

    if not token:
        print("ERROR: Set SUPABASE_ACCESS_TOKEN (sbp_ personal access token)")
        sys.exit(1)

    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Run migration
    resp = requests.post(url, json={"query": SQL}, headers=headers)
    if resp.status_code != 200:
        print(f"ERROR: Migration failed: {resp.status_code} - {resp.text}")
        sys.exit(1)

    # Verify
    resp = requests.post(url, json={"query": VERIFY_SQL}, headers=headers)
    if resp.status_code == 200:
        print("Migration complete via Supabase Management API")
        print(resp.json())
    else:
        print(f"WARNING: Migration ran but verification failed: {resp.status_code}")


def rollback_supabase():
    """Rollback via Supabase Management API."""
    import requests

    token = os.getenv('SUPABASE_ACCESS_TOKEN')
    project_ref = os.getenv('SUPABASE_PROJECT_REF', 'udblirsscaghsepuxxqv')

    if not token:
        print("ERROR: Set SUPABASE_ACCESS_TOKEN")
        sys.exit(1)

    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(url, json={"query": ROLLBACK_SQL}, headers=headers)
    if resp.status_code == 200:
        print("Rollback complete: dropped fcm_token columns")
    else:
        print(f"ERROR: Rollback failed: {resp.status_code} - {resp.text}")
        sys.exit(1)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'auto'

    if mode == 'rollback':
        rollback_supabase()
    elif mode == 'supabase':
        migrate_supabase()
    elif mode == 'local':
        migrate_local()
    else:
        # Auto-detect: try local first, fall back to Supabase
        if os.getenv('DATABASE_URL'):
            migrate_local()
        elif os.getenv('SUPABASE_ACCESS_TOKEN'):
            migrate_supabase()
        else:
            print("Set DATABASE_URL or SUPABASE_ACCESS_TOKEN")
            sys.exit(1)
