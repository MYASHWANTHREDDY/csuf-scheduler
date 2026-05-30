"""Add shift_preference and daily_staffing_requirements fields.

Revision ID: shift_pref_001
Revises: ai_scheduling_001
Create Date: 2025-12-23

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "shift_pref_001"
down_revision = "ai_scheduling_001"
branch_labels = None
depends_on = None


def upgrade():
    # Add shift_preference to employee_profiles
    op.add_column(
        "employee_profiles",
        sa.Column("shift_preference", sa.String(10), nullable=False, server_default="both"),
    )

    # Add daily_staffing_requirements to schedule_configs
    op.add_column(
        "schedule_configs", sa.Column("daily_staffing_requirements", sa.Text, nullable=True)
    )


def downgrade():
    # Remove columns
    op.drop_column("employee_profiles", "shift_preference")
    op.drop_column("schedule_configs", "daily_staffing_requirements")
