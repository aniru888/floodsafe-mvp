"""add admin report and comment type fields

Revision ID: a1b2c3d4e5f6
Revises: 3eae32b88127
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '3eae32b88127'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reports', sa.Column('admin_created', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('reports', sa.Column('source', sa.String(length=50), nullable=True))
    op.add_column('comments', sa.Column('comment_type', sa.String(length=20), server_default='community', nullable=True))


def downgrade() -> None:
    op.drop_column('comments', 'comment_type')
    op.drop_column('reports', 'source')
    op.drop_column('reports', 'admin_created')
