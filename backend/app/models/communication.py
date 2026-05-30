"""Communication-related models for CSUF Scheduler.

Includes models for notifications, announcements, swap requests, and call-offs.
"""

from datetime import datetime

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class SwapRequest(db.Model):
    """Represents a request by a user to swap or release a shift."""

    __tablename__ = "swap_requests"

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default="requested"
    )  # requested/target_accepted/supervisor_approved/denied
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    shift = db.relationship(
        "Shift", foreign_keys=[shift_id], backref=db.backref("swap_requests", lazy=True)
    )
    target_shift = db.relationship("Shift", foreign_keys=[target_shift_id])
    requester = db.relationship("User", foreign_keys=[requester_id])
    target_user = db.relationship("User", foreign_keys=[target_user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "shift_id": self.shift_id,
            "requester_id": self.requester_id,
            "target_shift_id": self.target_shift_id,
            "target_user_id": self.target_user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "requested_shift": (
                {
                    "id": self.shift.id,
                    "date": self.shift.date.isoformat(),
                    "start_time": self.shift.start_time.strftime("%H:%M"),
                    "end_time": self.shift.end_time.strftime("%H:%M"),
                }
                if self.shift
                else None
            ),
            "target_shift": (
                {
                    "id": self.target_shift.id,
                    "date": self.target_shift.date.isoformat(),
                    "start_time": self.target_shift.start_time.strftime("%H:%M"),
                    "end_time": self.target_shift.end_time.strftime("%H:%M"),
                }
                if self.target_shift
                else None
            ),
        }


class Notification(db.Model):
    """Notifications for users."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default="general")
    seen = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("notifications", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "message": self.message,
            "category": self.category,
            "seen": self.seen,
            "created_at": self.created_at.isoformat(),
        }


class Announcement(db.Model):
    """Supervisor announcements visible to users."""

    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    author = db.relationship("User", backref=db.backref("announcements", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "author_id": self.author_id,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


class CallOffRequest(db.Model):
    """Represents an employee calling off an assigned shift."""

    __tablename__ = "call_off_requests"

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="submitted")  # submitted/acknowledged
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    shift = db.relationship("Shift", backref=db.backref("call_off_requests", lazy=True))
    requester = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "shift_id": self.shift_id,
            "requester_id": self.requester_id,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }
