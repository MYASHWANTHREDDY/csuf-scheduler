"""Add shift_preference column to availability table.

Revision ID: avail_pref_001
Revises: shift_pref_001
Create Date: 2025-12-23

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "avail_pref_001"
down_revision = "shift_pref_001"
branch_labels = None
depends_on = None


def upgrade():
    # Add shift_preference to availability table
    op.add_column("availability", sa.Column("shift_preference", sa.String(10), nullable=True))


def downgrade():
    # Remove column
    op.drop_column("availability", "shift_preference")
