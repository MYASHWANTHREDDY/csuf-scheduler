"""Add recurring availability support

Revision ID: 19f167bf8d2e
Revises: 30e9b8a0a463
Create Date: 2025-12-13 18:28:50.905460

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19f167bf8d2e"
down_revision: Union[str, Sequence[str], None] = "30e9b8a0a463"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns for recurring availability
    op.add_column(
        "availability", sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="0")
    )
    op.add_column("availability", sa.Column("day_of_week", sa.Integer(), nullable=True))
    op.add_column("availability", sa.Column("effective_until", sa.Date(), nullable=True))

    # Make date nullable since recurring availability doesn't need a specific date
    op.alter_column("availability", "date", nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the new columns
    op.drop_column("availability", "effective_until")
    op.drop_column("availability", "day_of_week")
    op.drop_column("availability", "is_recurring")

    # Make date required again
    op.alter_column("availability", "date", nullable=False)
