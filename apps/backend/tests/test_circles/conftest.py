"""
Pytest fixtures for Safety Circles tests.

Uses an in-memory SQLite database with ORM-based table creation.
Only creates the tables needed for circle tests (skips PostGIS-dependent models).
"""
import uuid
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine, event, text, Column, String, DateTime, Boolean, Integer, Float, Text
from sqlalchemy.orm import sessionmaker, declarative_base

from src.infrastructure.models import (
    Base, User, SafetyCircle, CircleMember, CircleAlert,
)

# Tables that DON'T have PostGIS columns — can create via ORM metadata
SAFE_TABLES = [
    User.__table__,
    SafetyCircle.__table__,
    CircleMember.__table__,
    CircleAlert.__table__,
]


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for testing.

    Creates only the circle-related tables + users via ORM metadata.
    Report and Alert tables are created manually (they have PostGIS columns).
    """
    engine = create_engine("sqlite:///:memory:")

    # Enable foreign keys in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create ORM-compatible tables (skip PostGIS-dependent ones)
    try:
        Base.metadata.create_all(engine, tables=SAFE_TABLES)
    except Exception as e:
        # If any table fails (e.g., UUID-related), log and continue
        print(f"Warning: Some tables failed to create via ORM: {e}")

    # Manually create Report and Alert tables (no PostGIS Geometry column)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reports (
                id CHAR(32) PRIMARY KEY,
                user_id CHAR(32) REFERENCES users(id),
                description TEXT,
                media_url VARCHAR(500),
                media_type VARCHAR(20),
                media_metadata TEXT,
                phone_number VARCHAR(20),
                phone_verified BOOLEAN DEFAULT 0,
                water_depth VARCHAR(20),
                vehicle_passability VARCHAR(20),
                location_verified BOOLEAN DEFAULT 0,
                verified BOOLEAN DEFAULT 0,
                verification_score INTEGER DEFAULT 0,
                upvotes INTEGER DEFAULT 0,
                downvotes INTEGER DEFAULT 0,
                quality_score FLOAT DEFAULT 0,
                verified_at TIMESTAMP,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                iot_validation_score FLOAT DEFAULT 0,
                nearby_sensor_ids TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alerts (
                id CHAR(32) PRIMARY KEY,
                user_id CHAR(32) REFERENCES users(id),
                report_id CHAR(32) REFERENCES reports(id),
                watch_area_id CHAR(32),
                message TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


def _create_user(db_session, username, email, display_name, phone=None):
    """Helper to create a test user via ORM (handles UUID properly)."""
    user = User(
        id=uuid.uuid4(),
        username=username,
        email=email,
        display_name=display_name,
        phone=phone,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    return _create_user(
        db_session,
        username="testuser",
        email="test@example.com",
        display_name="Test User",
        phone="+919876543210",
    )


@pytest.fixture
def test_user2(db_session):
    """Create a second test user."""
    return _create_user(
        db_session,
        username="testuser2",
        email="test2@example.com",
        display_name="Test User 2",
        phone="+919876543211",
    )


@pytest.fixture
def test_user3(db_session):
    """Create a third test user (no phone)."""
    return _create_user(
        db_session,
        username="testuser3",
        email="test3@example.com",
        display_name="Test User 3",
        phone=None,
    )


def create_test_report(db_session, user_id, description="Test flood"):
    """Helper to create a test report record (raw SQL, no PostGIS)."""
    report_id = uuid.uuid4()
    # Use hex representation for SQLite CHAR(32) column
    db_session.execute(text(
        "INSERT INTO reports (id, user_id, description) "
        "VALUES (:id, :uid, :d)"
    ), {"id": report_id.hex, "uid": user_id.hex, "d": description})
    db_session.commit()
    return report_id


def create_watch_area_alert(db_session, user_id, report_id, message="Watch area alert"):
    """Helper to create a watch area alert (simulates AlertService output)."""
    alert_id = uuid.uuid4()
    db_session.execute(text(
        "INSERT INTO alerts (id, user_id, report_id, message) "
        "VALUES (:id, :uid, :rid, :msg)"
    ), {"id": alert_id.hex, "uid": user_id.hex, "rid": report_id.hex, "msg": message})
    db_session.commit()
    return alert_id
