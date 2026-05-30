"""Add time adjustment requests table.

Revision ID: time_adjustments_001
Revises: swap_nullable_001
Create Date: 2026-03-14

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "time_adjustments_001"
down_revision = "swap_nullable_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "time_adjustment_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actual_start", sa.Time(), nullable=False),
        sa.Column("actual_end", sa.Time(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_time_adjustment_status", "time_adjustment_requests", ["status"])
    op.create_index(
        "ix_time_adjustment_user_shift_status",
        "time_adjustment_requests",
        ["user_id", "shift_id", "status"],
    )


def downgrade():
    op.drop_index("ix_time_adjustment_user_shift_status", table_name="time_adjustment_requests")
    op.drop_index("ix_time_adjustment_status", table_name="time_adjustment_requests")
    op.drop_table("time_adjustment_requests")
