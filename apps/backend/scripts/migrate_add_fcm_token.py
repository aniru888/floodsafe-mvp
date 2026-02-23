"""Add fcm_token column to users table."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from src.core.config import settings

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token_updated_at TIMESTAMP;
    """))
    conn.commit()
    print("Migration complete: added fcm_token columns to users")
