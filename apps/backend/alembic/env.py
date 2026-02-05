"""
Alembic migration environment configuration.

This file configures Alembic to:
1. Use the database URL from our application settings
2. Import all models for autogenerate support
3. Handle PostGIS geometry columns correctly
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add the backend directory to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our models and settings
from src.infrastructure.models import Base
from src.core.config import settings

# This is the Alembic Config object
config = context.config

# Override the sqlalchemy.url from the ini file with our settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter objects to include in migrations.

    This helps avoid issues with:
    - PostGIS internal tables (spatial_ref_sys, etc.)
    - TIGER geocoder tables (state, county, place, edges, etc.)
    - Topology tables
    - Other system tables we don't want to manage
    """
    # Skip PostGIS core system tables
    postgis_system_tables = {
        "spatial_ref_sys", "geography_columns", "geometry_columns"
    }

    # Skip TIGER geocoder tables (US Census data for geocoding)
    tiger_tables = {
        "addr", "addrfeat", "bg", "county", "county_lookup", "countysub_lookup",
        "cousub", "direction_lookup", "edges", "faces", "featnames",
        "geocode_settings", "geocode_settings_default", "loader_lookuptables",
        "loader_platform", "loader_variables", "pagc_gaz", "pagc_lex", "pagc_rules",
        "place", "place_lookup", "secondary_unit_lookup", "state", "state_lookup",
        "street_type_lookup", "tabblock", "tabblock20", "tract", "zcta5",
        "zip_lookup", "zip_lookup_all", "zip_lookup_base", "zip_state", "zip_state_loc"
    }

    # Skip topology tables
    topology_tables = {"topology", "layer"}

    # Combine all tables to skip
    skip_tables = postgis_system_tables | tiger_tables | topology_tables

    if type_ == "table" and name in skip_tables:
        return False

    # Skip indexes on skipped tables
    if type_ == "index" and hasattr(object, 'table') and object.table.name in skip_tables:
        return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,  # Detect column type changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,  # Detect column type changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
