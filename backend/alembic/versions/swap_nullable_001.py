"""Make swap request fields nullable for simple swap requests.

Revision ID: swap_nullable_001
Revises: avail_pref_001
Create Date: 2026-03-05

"""

import sqlalchemy as sa
from alembic import op

revision = "swap_nullable_001"
down_revision = "avail_pref_001"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # Create new table with nullable columns
    op.create_table(
        "swap_requests_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("target_shift_id", sa.Integer(), nullable=True),  # Now nullable
        sa.Column("target_user_id", sa.Integer(), nullable=True),  # Now nullable
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["shifts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_shift_id"],
            ["shifts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy data from old table
    op.execute("INSERT INTO swap_requests_new SELECT * FROM swap_requests")

    # Drop old table
    op.drop_table("swap_requests")

    # Rename new table
    op.rename_table("swap_requests_new", "swap_requests")


def downgrade():
    # Recreate old table structure with NOT NULL constraints
    op.create_table(
        "swap_requests_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("target_shift_id", sa.Integer(), nullable=False),  # Back to NOT NULL
        sa.Column("target_user_id", sa.Integer(), nullable=False),  # Back to NOT NULL
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["shifts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_shift_id"],
            ["shifts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy non-NULL records only
    op.execute(
        "INSERT INTO swap_requests_old SELECT * FROM swap_requests WHERE target_shift_id IS NOT NULL AND target_user_id IS NOT NULL"
    )

    # Drop new table
    op.drop_table("swap_requests")

    # Rename old table
    op.rename_table("swap_requests_old", "swap_requests")
