"""Add performance indexes for high-traffic filters and audit lookups.

Revision ID: obs_perf_indexes_001
Revises: audit_logs_001
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

revision = "obs_perf_indexes_001"
down_revision = "audit_logs_001"
branch_labels = None
depends_on = None


def _existing_index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if name in _existing_index_names(table):
        return
    op.create_index(name, table, columns)


def _drop_index_if_exists(name: str, table: str) -> None:
    if name not in _existing_index_names(table):
        return
    op.drop_index(name, table_name=table)


def upgrade() -> None:
    _create_index_if_missing("ix_shifts_date", "shifts", ["date"])
    _create_index_if_missing("ix_shifts_assigned_user_id", "shifts", ["assigned_user_id"])
    _create_index_if_missing("ix_shifts_date_assigned", "shifts", ["date", "assigned_user_id"])

    _create_index_if_missing("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    _create_index_if_missing("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    _create_index_if_missing("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])


def downgrade() -> None:
    _drop_index_if_exists("ix_audit_logs_actor_user_id", "audit_logs")
    _drop_index_if_exists("ix_audit_logs_entity_type", "audit_logs")
    _drop_index_if_exists("ix_audit_logs_created_at", "audit_logs")

    _drop_index_if_exists("ix_shifts_date_assigned", "shifts")
    _drop_index_if_exists("ix_shifts_assigned_user_id", "shifts")
    _drop_index_if_exists("ix_shifts_date", "shifts")
