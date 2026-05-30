"""Scheduling configuration and result models for CSUF Scheduler."""

import json
from datetime import datetime

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class ScheduleConfig(db.Model):
    """Configuration for AI schedule generation.

    Stores supervisor settings for a scheduling run.
    """

    __tablename__ = "schedule_configs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # Scheduling range
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    # Academic period: "term" or "break"
    academic_period = db.Column(db.String(20), nullable=False, default="term")

    # Max hours based on period (auto-set based on academic_period)
    max_weekly_hours = db.Column(db.Integer, nullable=False, default=20)

    # Target hours per employee per week
    target_hours_per_week = db.Column(db.Integer, nullable=False, default=18)

    # Minimum rest between shifts (hours)
    min_rest_hours = db.Column(db.Integer, nullable=False, default=8)

    # Max consecutive working days
    max_consecutive_days = db.Column(db.Integer, nullable=False, default=5)

    # Shift templates to use (JSON array of template IDs)
    shift_template_ids = db.Column(db.Text, nullable=True)  # JSON array

    # Per-day staffing requirements (JSON: {date: {template_id: count}})
    daily_staffing_requirements = db.Column(db.Text, nullable=True)  # JSON

    # Special events (JSON array of {date, additional_staff, employee_ids})
    special_events = db.Column(db.Text, nullable=True)  # JSON

    # Created by supervisor
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    creator = db.relationship("User", backref=db.backref("schedule_configs", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "academic_period": self.academic_period,
            "max_weekly_hours": self.max_weekly_hours,
            "target_hours_per_week": self.target_hours_per_week,
            "min_rest_hours": self.min_rest_hours,
            "max_consecutive_days": self.max_consecutive_days,
            "shift_template_ids": (
                json.loads(self.shift_template_ids) if self.shift_template_ids else []
            ),
            "daily_staffing_requirements": (
                json.loads(self.daily_staffing_requirements)
                if self.daily_staffing_requirements
                else {}
            ),
            "special_events": json.loads(self.special_events) if self.special_events else [],
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }

    def get_shift_template_ids(self):
        return json.loads(self.shift_template_ids) if self.shift_template_ids else []

    def set_shift_template_ids(self, ids):
        self.shift_template_ids = json.dumps(ids)


class GeneratedSchedule(db.Model):
    """Stores AI-generated schedules.

    Contains the full schedule output with assignments and metadata.
    """

    __tablename__ = "generated_schedules"

    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey("schedule_configs.id"), nullable=False)

    # Status: generating, completed, failed, applied
    status = db.Column(db.String(20), nullable=False, default="generating")

    # Full schedule data (JSON)
    schedule_data = db.Column(db.Text, nullable=True)

    # Statistics
    stats_data = db.Column(db.Text, nullable=True)  # JSON: hours_per_employee, fairness_score, etc.

    # Flags/warnings from generation
    flags_data = db.Column(db.Text, nullable=True)  # JSON array of issues

    # Error message if failed
    error_message = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    config = db.relationship("ScheduleConfig", backref=db.backref("generated_schedules", lazy=True))

    def to_dict(self, include_data=False):
        result = {
            "id": self.id,
            "config_id": self.config_id,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        # Include config date range
        if self.config:
            result["start_date"] = self.config.start_date.isoformat()
            result["end_date"] = self.config.end_date.isoformat()
        if include_data:
            result["schedule_data"] = json.loads(self.schedule_data) if self.schedule_data else None
            result["stats_data"] = json.loads(self.stats_data) if self.stats_data else None
            result["flags_data"] = json.loads(self.flags_data) if self.flags_data else None
        return result

    def set_schedule_data(self, data):
        self.schedule_data = json.dumps(data)

    def get_schedule_data(self):
        return json.loads(self.schedule_data) if self.schedule_data else None


class ScheduleOverride(db.Model):
    """Manual overrides applied to generated schedules."""

    __tablename__ = "schedule_overrides"

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("generated_schedules.id"), nullable=False)

    # Original assignment
    shift_date = db.Column(db.Date, nullable=False)
    shift_template_id = db.Column(db.Integer, db.ForeignKey("shift_templates.id"), nullable=False)
    original_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # New assignment
    new_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Reason for override
    reason = db.Column(db.Text, nullable=True)

    # Applied by supervisor
    applied_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    schedule = db.relationship("GeneratedSchedule", backref=db.backref("overrides", lazy=True))
    shift_template = db.relationship("ShiftTemplate")
    original_user = db.relationship("User", foreign_keys=[original_user_id])
    new_user = db.relationship("User", foreign_keys=[new_user_id])
    supervisor = db.relationship("User", foreign_keys=[applied_by])

    def to_dict(self):
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "shift_date": self.shift_date.isoformat(),
            "shift_template_id": self.shift_template_id,
            "original_user_id": self.original_user_id,
            "new_user_id": self.new_user_id,
            "reason": self.reason,
            "applied_by": self.applied_by,
            "created_at": self.created_at.isoformat(),
        }
