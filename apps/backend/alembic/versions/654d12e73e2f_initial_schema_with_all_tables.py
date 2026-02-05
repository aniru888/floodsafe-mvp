"""Initial schema baseline - establishes Alembic starting point

Revision ID: 654d12e73e2f
Revises:
Create Date: 2025-12-30 03:36:21.213351

This is a BASELINE migration for an existing database.
It does not modify the schema - it simply marks the current
database state as the starting point for future migrations.

The FloodSafe database schema is defined in:
- apps/backend/src/infrastructure/models.py

Tables managed by this application:
- users, reports, sensors, readings, alerts
- watch_areas, daily_routes, saved_routes
- badges, user_badges, role_history
- report_votes, comments
- email_verification_tokens, whatsapp_sessions

Tables NOT managed (PostGIS extensions):
- spatial_ref_sys, geography_columns, geometry_columns
- tiger.* (TIGER geocoder tables) - managed by PostGIS extension
- topology.* (topology tables) - managed by PostGIS extension
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '654d12e73e2f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration - no changes.

    This migration establishes Alembic version tracking for an existing database.
    All FloodSafe tables are already created via models.Base.metadata.create_all()
    or previous ad-hoc migration scripts.

    After running this migration, future schema changes should be made via
    `alembic revision --autogenerate -m "description"` and then `alembic upgrade head`
    """
    pass


def downgrade() -> None:
    """
    Baseline migration - no changes.

    WARNING: Downgrading past this point would require dropping all FloodSafe tables,
    which would result in data loss. This is intentionally left empty.
    """
    pass
