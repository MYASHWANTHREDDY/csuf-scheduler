"""Global audit log model for tracking non-timesheet changes."""

import json
from datetime import date, datetime, time

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    return value


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100), nullable=True)
    before_json = db.Column(db.Text, nullable=True)
    after_json = db.Column(db.Text, nullable=True)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    actor = db.relationship("User", backref=db.backref("audit_logs", lazy=True))

    def to_dict(self):
        def _loads(text):
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                return text

        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "before": _loads(self.before_json),
            "after": _loads(self.after_json),
            "details": _loads(self.details_json),
            "created_at": _jsonable(self.created_at),
        }
