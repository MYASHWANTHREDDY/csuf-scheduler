"""Time adjustment request model for shift attendance corrections."""

from datetime import datetime

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class TimeAdjustmentRequest(db.Model):
    """Represents an employee-requested adjustment to worked shift times."""

    __tablename__ = "time_adjustment_requests"

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    actual_start = db.Column(db.Time, nullable=False)
    actual_end = db.Column(db.Time, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default="pending"
    )  # pending/approved/rejected
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    shift = db.relationship("Shift", backref=db.backref("time_adjustment_requests", lazy=True))
    user = db.relationship("User", foreign_keys=[user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    @staticmethod
    def _format_minutes(start_time, end_time):
        start = start_time.hour * 60 + start_time.minute
        end = end_time.hour * 60 + end_time.minute
        minutes = end - start
        if minutes <= 0:
            minutes += 24 * 60
        return minutes

    def to_dict(self):
        shift_dict = None
        if self.shift:
            shift_dict = {
                "id": self.shift.id,
                "date": self.shift.date.isoformat(),
                "start_time": self.shift.start_time.strftime("%H:%M"),
                "end_time": self.shift.end_time.strftime("%H:%M"),
            }

        return {
            "id": self.id,
            "shift_id": self.shift_id,
            "user_id": self.user_id,
            "actual_start": self.actual_start.strftime("%H:%M"),
            "actual_end": self.actual_end.strftime("%H:%M"),
            "reason": self.reason,
            "status": self.status,
            "reviewed_by_id": self.reviewed_by_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_notes": self.reviewer_notes,
            "created_at": self.created_at.isoformat(),
            "worked_minutes": self._format_minutes(self.actual_start, self.actual_end),
            "scheduled_shift": shift_dict,
        }
