"""Availability-related models for CSUF Scheduler."""

from datetime import datetime

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class Availability(db.Model):
    """Represents a user's availability for a particular date/time range.

    Can be either:
    - One-time availability (specific date)
    - Recurring weekly availability (repeats every week for a day_of_week)
    """

    __tablename__ = "availability"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=True)  # For one-time availability
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    day_of_week = db.Column(db.Integer, nullable=True)  # 0=Monday, 6=Sunday (for recurring)
    effective_until = db.Column(db.Date, nullable=True)  # End date for recurring availability
    shift_preference = db.Column(
        db.String(10), nullable=True
    )  # 'only_6h' or 'both' - employee's preferred shift types
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("availability", lazy=True))

    def to_dict(self):
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "is_recurring": self.is_recurring,
            "shift_preference": self.shift_preference,
        }
        if self.is_recurring:
            result["day_of_week"] = self.day_of_week
            result["effective_until"] = (
                self.effective_until.isoformat() if self.effective_until else None
            )
        else:
            result["date"] = self.date.isoformat() if self.date else None
        return result


class LeaveRequest(db.Model):
    """Employee leave/unavailability dates."""

    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/approved/denied
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("leave_requests", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class AvailabilityRequest(db.Model):
    """Represents a supervisor's request for an employee to submit availability."""

    __tablename__ = "availability_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default="active"
    )  # active/completed/cancelled
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("availability_requests_received", lazy=True),
    )
    supervisor = db.relationship("User", foreign_keys=[requested_by])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "requested_by": self.requested_by,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "user": (
                {
                    "id": self.user.id,
                    "name": self.user.name,
                    "first_name": self.user.first_name,
                    "last_name": self.user.last_name,
                }
                if self.user
                else None
            ),
        }
