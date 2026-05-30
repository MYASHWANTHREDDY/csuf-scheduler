"""Shift-related models for CSUF Scheduler."""

from datetime import datetime

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class Shift(db.Model):
    """Represents a work shift. Can be assigned to a User."""

    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship to User; backref as assigned_shifts
    assigned_user = db.relationship("User", backref=db.backref("assigned_shifts", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "assigned_user_id": self.assigned_user_id,
        }


class ShiftTemplate(db.Model):
    """Predefined shift templates for scheduling.

    Defines standard shift times and types that can be used in schedule generation.
    """

    __tablename__ = "shift_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration_hours = db.Column(db.Float, nullable=False)  # Duration in hours
    shift_type = db.Column(db.String(20), nullable=False)  # PS, PSL, Custom
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    required_staff = db.Column(db.Integer, nullable=False, default=1)  # Minimum staff needed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "duration_hours": self.duration_hours,
            "shift_type": self.shift_type,
            "is_active": self.is_active,
            "required_staff": self.required_staff,
        }
