"""Helpers for writing global audit log entries."""

import json
from datetime import date, datetime, time
from typing import Any

from flask import has_request_context, session

try:
    from ..database import db
    from ..models import AuditLog
except (ImportError, ModuleNotFoundError):
    from database import db
    from models import AuditLog


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def log_audit(
    action: str,
    entity_type: str,
    entity_id: Any = None,
    before: Any = None,
    after: Any = None,
    details: Any = None,
    actor_user_id: int | None = None,
) -> None:
    actor_id = actor_user_id
    if actor_id is None and has_request_context():
        actor_id = session.get("user_id")

    entry = AuditLog(
        actor_user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_json=json.dumps(_serialize(before)) if before is not None else None,
        after_json=json.dumps(_serialize(after)) if after is not None else None,
        details_json=json.dumps(_serialize(details)) if details is not None else None,
    )
    db.session.add(entry)
