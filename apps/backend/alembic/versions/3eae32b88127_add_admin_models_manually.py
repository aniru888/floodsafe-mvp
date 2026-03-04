"""Add admin models manually

Revision ID: 3eae32b88127
Revises: 654d12e73e2f
Create Date: 2026-03-05 01:50:58.089029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3eae32b88127'
down_revision: Union[str, Sequence[str], None] = '654d12e73e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('admin_audit_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.String(length=255), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_log_action'), 'admin_audit_log', ['action'], unique=False)
    op.create_index(op.f('ix_admin_audit_log_admin_id'), 'admin_audit_log', ['admin_id'], unique=False)
    op.create_index(op.f('ix_admin_audit_log_created_at'), 'admin_audit_log', ['created_at'], unique=False)

    op.add_column('users', sa.Column('tour_completed_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('verified_reporter_since', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('moderator_since', sa.DateTime(), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'moderator_since')
    op.drop_column('users', 'verified_reporter_since')
    op.drop_column('users', 'tour_completed_at')

    op.drop_index(op.f('ix_admin_audit_log_created_at'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_admin_id'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_action'), table_name='admin_audit_log')
    op.drop_table('admin_audit_log')
