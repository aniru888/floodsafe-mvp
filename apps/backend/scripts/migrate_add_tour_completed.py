"""
Migration: Add tour_completed_at column to users table.

Run this against Supabase or local database:
    python scripts/migrate_add_tour_completed.py

Uses Supabase Management API if DATABASE_URL is not available (IPv6-only workaround).
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SQL = """
ALTER TABLE users
ADD COLUMN IF NOT EXISTS tour_completed_at TIMESTAMPTZ;
"""

def migrate_local():
    """Migrate via direct database connection."""
    from sqlalchemy import create_engine, text
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(database_url)
    with engine.connect() as conn:
        conn.execute(text(SQL))
        conn.commit()
    print("Migration complete: tour_completed_at column added to users table")


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

    resp = requests.post(url, json={"query": SQL}, headers=headers)
    if resp.status_code == 200:
        print("Migration complete via Supabase Management API")
        print(resp.json())
    else:
        print(f"ERROR: {resp.status_code} - {resp.text}")
        sys.exit(1)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'auto'

    if mode == 'supabase':
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
