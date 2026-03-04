from sqlalchemy import create_engine, URL
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as async_sessionmaker
from ..core.config import settings
import logging
import re
import os

logger = logging.getLogger(__name__)


def create_database_url() -> URL:
    """
    Create SQLAlchemy URL object, handling special characters in password.
    Supports Supabase pooler format: postgresql://postgres.ref:password@host:port/db
    """
    database_url_string = settings.DATABASE_URL

    if not database_url_string:
        raise ValueError("DATABASE_URL is empty or not set")

    try:
        # First, try SQLAlchemy's make_url (handles most cases)
        try:
            url_obj = make_url(database_url_string)
            sanitized = f"{url_obj.drivername}://{url_obj.username}:****@{url_obj.host}:{url_obj.port}/{url_obj.database}"
            logger.info(f"Connecting to database: {sanitized}")
            return url_obj
        except Exception as parse_error:
            logger.warning(f"Standard URL parsing failed: {parse_error}, trying regex parser")

        # Fallback: Manual regex parsing for complex URLs (Supabase with special chars)
        # Format: postgresql://user:password@host:port/database
        pattern = r'^(postgresql(?:\+\w+)?):\/\/([^:]+):(.+)@([^:\/]+):(\d+)\/(.+)$'
        match = re.match(pattern, database_url_string)

        if not match:
            raise ValueError("URL doesn't match expected format: scheme://user:pass@host:port/db")

        scheme, username, password, host, port, database = match.groups()

        # Create URL object (handles special characters properly)
        url_obj = URL.create(
            drivername=scheme,
            username=username,
            password=password,
            host=host,
            port=int(port),
            database=database,
        )

        sanitized = f"{scheme}://{username}:****@{host}:{port}/{database}"
        logger.info(f"Connecting to database (regex parsed): {sanitized}")

        return url_obj

    except Exception as e:
        logger.error(f"Failed to parse DATABASE_URL: {e}")
        logger.error(f"DATABASE_URL format should be: postgresql://user:password@host:port/database")
        # Only log first 50 chars to avoid exposing password
        safe_preview = database_url_string[:50] if len(database_url_string) > 50 else database_url_string[:20] + "..."
        logger.error(f"DATABASE_URL preview: {safe_preview}")
        raise ValueError(f"Invalid DATABASE_URL format: {e}")


# Determine if we need SSL (required for cloud databases like Supabase)
def get_connect_args(url: URL) -> dict:
    """Get connection arguments based on host (SSL for cloud, none for localhost)."""
    host = url.host or ""
    if "localhost" in host or "127.0.0.1" in host or "db" == host:
        # Local development - no SSL needed
        return {}
    else:
        # Cloud database (Supabase, etc.) - require SSL
        # Also set search_path to include 'tiger' schema where PostGIS is installed
        return {
            "sslmode": "require",
            "options": "-c search_path=public,tiger,extensions"
        }


# Sync engine (for existing endpoints)
try:
    database_url = create_database_url()
    connect_args = get_connect_args(database_url)
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f"Database sync engine initialized (SSL: {'sslmode' in connect_args})")
except Exception as e:
    logger.error(f"CRITICAL: Failed to initialize database engine: {e}")
    logger.error(f"DATABASE_URL env var exists: {bool(os.getenv('DATABASE_URL'))}")
    raise

# Async engine (for external alerts)
try:
    # Create async version of the URL
    async_url = database_url.set(drivername="postgresql+asyncpg")
    # For asyncpg, SSL is passed differently
    host = database_url.host or ""
    is_cloud = "localhost" not in host and "127.0.0.1" not in host and host != "db"
    # asyncpg uses server_settings for search_path
    async_connect_args = {
        "ssl": "require",
        "server_settings": {"search_path": "public,tiger,extensions"}
    } if is_cloud else {}
    async_engine = create_async_engine(
        async_url,
        echo=False,
        connect_args=async_connect_args,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    AsyncSessionLocal = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info(f"Database async engine initialized (SSL: {is_cloud})")
except Exception as e:
    logger.error(f"CRITICAL: Failed to initialize async database engine: {e}")
    raise

Base = declarative_base()


def get_db():
    """Get sync database session (for existing endpoints)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """Get async database session (for external alerts)."""
    async with AsyncSessionLocal() as session:
        yield session
