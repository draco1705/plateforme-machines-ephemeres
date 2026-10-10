"""add ssh_port to reservations

Revision ID: f1e2d3c4b5a6
Revises: 59f2d8fc8532
Create Date: 2026-10-10 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1e2d3c4b5a6'
down_revision = '59f2d8fc8532'      # ← head hiện tại (từ alembic current)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'reservations',
        sa.Column('ssh_port', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('reservations', 'ssh_port')