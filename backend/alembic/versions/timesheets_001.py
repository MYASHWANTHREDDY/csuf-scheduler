"""Add pay periods and timesheet workflow tables.

Revision ID: timesheets_001
Revises: time_adjustments_001
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "timesheets_001"
down_revision = "time_adjustments_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pay_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("submission_deadline", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("finalized_by_id", sa.Integer(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["finalized_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pay_period_dates", "pay_periods", ["start_date", "end_date"])

    op.create_table(
        "timesheets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pay_period_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pay_period_id"], ["pay_periods.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pay_period_id", "user_id", name="uq_timesheet_period_user"),
    )
    op.create_index("ix_timesheets_status", "timesheets", ["status"])
    op.create_index("ix_timesheets_period_user", "timesheets", ["pay_period_id", "user_id"])

    op.create_table(
        "timesheet_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timesheet_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("original_start_time", sa.Time(), nullable=True),
        sa.Column("original_end_time", sa.Time(), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="scheduled"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["timesheet_id"], ["timesheets.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timesheet_lines_date", "timesheet_lines", ["timesheet_id", "work_date"])

    op.create_table(
        "timesheet_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timesheet_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("requires_response", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["timesheet_id"], ["timesheets.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "timesheet_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timesheet_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["timesheet_id"], ["timesheets.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_timesheet_audit_sheet", "timesheet_audit_logs", ["timesheet_id", "created_at"]
    )


def downgrade():
    op.drop_index("ix_timesheet_audit_sheet", table_name="timesheet_audit_logs")
    op.drop_table("timesheet_audit_logs")

    op.drop_table("timesheet_comments")

    op.drop_index("ix_timesheet_lines_date", table_name="timesheet_lines")
    op.drop_table("timesheet_lines")

    op.drop_index("ix_timesheets_period_user", table_name="timesheets")
    op.drop_index("ix_timesheets_status", table_name="timesheets")
    op.drop_table("timesheets")

    op.drop_index("ix_pay_period_dates", table_name="pay_periods")
    op.drop_table("pay_periods")
