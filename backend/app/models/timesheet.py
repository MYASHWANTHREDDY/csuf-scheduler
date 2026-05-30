"""Timesheet-related models for pay period submission and review workflow."""

from datetime import datetime

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class PayPeriod(db.Model):
    __tablename__ = "pay_periods"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    submission_deadline = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="open")  # open/finalized
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    finalized_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    finalized_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    finalized_by = db.relationship("User", foreign_keys=[finalized_by_id])

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "submission_deadline": (
                self.submission_deadline.isoformat() if self.submission_deadline else None
            ),
            "status": self.status,
            "created_by_id": self.created_by_id,
            "finalized_by_id": self.finalized_by_id,
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None,
            "created_at": self.created_at.isoformat(),
        }


class Timesheet(db.Model):
    __tablename__ = "timesheets"

    id = db.Column(db.Integer, primary_key=True)
    pay_period_id = db.Column(db.Integer, db.ForeignKey("pay_periods.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.String(30), nullable=False, default="draft"
    )  # draft/submitted/needs_response/approved/rejected
    submitted_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    pay_period = db.relationship("PayPeriod", backref=db.backref("timesheets", lazy=True))
    user = db.relationship("User", foreign_keys=[user_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])

    def total_minutes(self):
        return sum(line.worked_minutes() for line in self.lines)

    def has_open_clarification(self):
        return any(c.requires_response and c.resolved_at is None for c in self.comments)

    def to_dict(self, include_lines=False, include_comments=False):
        data = {
            "id": self.id,
            "pay_period_id": self.pay_period_id,
            "user_id": self.user_id,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by_id": self.approved_by_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_minutes": self.total_minutes(),
            "has_open_clarification": self.has_open_clarification(),
            "pay_period": self.pay_period.to_dict() if self.pay_period else None,
        }
        if include_lines:
            data["lines"] = [
                line.to_dict()
                for line in sorted(self.lines, key=lambda x: (x.work_date, x.start_time))
            ]
        if include_comments:
            data["comments"] = [
                c.to_dict() for c in sorted(self.comments, key=lambda x: x.created_at)
            ]
        return data


class TimesheetLine(db.Model):
    __tablename__ = "timesheet_lines"

    id = db.Column(db.Integer, primary_key=True)
    timesheet_id = db.Column(db.Integer, db.ForeignKey("timesheets.id"), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=True)
    work_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    original_start_time = db.Column(db.Time, nullable=True)
    original_end_time = db.Column(db.Time, nullable=True)
    source_type = db.Column(
        db.String(30), nullable=False, default="scheduled"
    )  # scheduled/time_adjustment/manual
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    timesheet = db.relationship(
        "Timesheet", backref=db.backref("lines", lazy=True, cascade="all, delete-orphan")
    )
    shift = db.relationship("Shift")

    @staticmethod
    def _minutes(start_time, end_time):
        start = start_time.hour * 60 + start_time.minute
        end = end_time.hour * 60 + end_time.minute
        minutes = end - start
        if minutes <= 0:
            minutes += 24 * 60
        return minutes

    def worked_minutes(self):
        return self._minutes(self.start_time, self.end_time)

    def is_modified(self):
        if self.source_type == "manual":
            return True
        if not self.original_start_time or not self.original_end_time:
            return False
        return (
            self.start_time != self.original_start_time or self.end_time != self.original_end_time
        )

    def to_dict(self):
        return {
            "id": self.id,
            "timesheet_id": self.timesheet_id,
            "shift_id": self.shift_id,
            "work_date": self.work_date.isoformat(),
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "original_start_time": (
                self.original_start_time.strftime("%H:%M") if self.original_start_time else None
            ),
            "original_end_time": (
                self.original_end_time.strftime("%H:%M") if self.original_end_time else None
            ),
            "source_type": self.source_type,
            "note": self.note,
            "is_modified": self.is_modified(),
            "worked_minutes": self.worked_minutes(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TimesheetComment(db.Model):
    __tablename__ = "timesheet_comments"

    id = db.Column(db.Integer, primary_key=True)
    timesheet_id = db.Column(db.Integer, db.ForeignKey("timesheets.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    requires_response = db.Column(db.Boolean, nullable=False, default=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    timesheet = db.relationship(
        "Timesheet", backref=db.backref("comments", lazy=True, cascade="all, delete-orphan")
    )
    author = db.relationship("User", foreign_keys=[author_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])

    def to_dict(self):
        return {
            "id": self.id,
            "timesheet_id": self.timesheet_id,
            "author_id": self.author_id,
            "message": self.message,
            "requires_response": self.requires_response,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by_id": self.resolved_by_id,
            "created_at": self.created_at.isoformat(),
        }


class TimesheetAuditLog(db.Model):
    __tablename__ = "timesheet_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    timesheet_id = db.Column(db.Integer, db.ForeignKey("timesheets.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    timesheet = db.relationship(
        "Timesheet", backref=db.backref("audit_logs", lazy=True, cascade="all, delete-orphan")
    )
    actor = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "timesheet_id": self.timesheet_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }
