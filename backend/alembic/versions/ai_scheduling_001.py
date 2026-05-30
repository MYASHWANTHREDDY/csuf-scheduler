"""Add AI scheduling models

Revision ID: ai_scheduling_001
Revises: 19f167bf8d2e
Create Date: 2025-12-23

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ai_scheduling_001"
down_revision = "19f167bf8d2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Employee Profiles table
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("employee_role", sa.String(length=20), nullable=False, server_default="Regular"),
        sa.Column("patrol_shift_certified", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("lockup_certified", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("east_lockup_trained", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("west_lockup_trained", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("probation_status", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("late_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_show_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("target_hours", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Shift Templates table
    op.create_table(
        "shift_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("duration_hours", sa.Float(), nullable=False),
        sa.Column("shift_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("required_staff", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Leave Requests table
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Schedule Configs table
    op.create_table(
        "schedule_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("academic_period", sa.String(length=20), nullable=False, server_default="term"),
        sa.Column("max_weekly_hours", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("target_hours_per_week", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("min_rest_hours", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("max_consecutive_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("shift_template_ids", sa.Text(), nullable=True),
        sa.Column("special_events", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Generated Schedules table
    op.create_table(
        "generated_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("config_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="generating"),
        sa.Column("schedule_data", sa.Text(), nullable=True),
        sa.Column("stats_data", sa.Text(), nullable=True),
        sa.Column("flags_data", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["config_id"],
            ["schedule_configs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Schedule Overrides table
    op.create_table(
        "schedule_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("shift_template_id", sa.Integer(), nullable=False),
        sa.Column("original_user_id", sa.Integer(), nullable=True),
        sa.Column("new_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("applied_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["applied_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["new_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["original_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["generated_schedules.id"],
        ),
        sa.ForeignKeyConstraint(
            ["shift_template_id"],
            ["shift_templates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("schedule_overrides")
    op.drop_table("generated_schedules")
    op.drop_table("schedule_configs")
    op.drop_table("leave_requests")
    op.drop_table("shift_templates")
    op.drop_table("employee_profiles")
