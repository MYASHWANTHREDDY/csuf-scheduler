"""Employee profile model for CSUF Scheduler."""

from datetime import datetime

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class EmployeeProfile(db.Model):
    """Extended employee profile for AI scheduling.

    Stores training certifications, reliability metrics, and scheduling preferences.
    """

    __tablename__ = "employee_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    # Role: Trainee, FTO (Field Training Officer), Regular
    employee_role = db.Column(db.String(20), nullable=False, default="Regular")

    # Training & Certifications
    patrol_shift_certified = db.Column(db.Boolean, nullable=False, default=False)  # PS certified
    lockup_certified = db.Column(db.Boolean, nullable=False, default=False)  # PSL certified
    east_lockup_trained = db.Column(db.Boolean, nullable=False, default=False)
    west_lockup_trained = db.Column(db.Boolean, nullable=False, default=False)

    # Status
    probation_status = db.Column(db.Boolean, nullable=False, default=False)

    # Reliability metrics (updated from attendance history)
    late_count = db.Column(db.Integer, nullable=False, default=0)
    no_show_count = db.Column(db.Integer, nullable=False, default=0)

    # Scheduling priority (1=highest, 10=lowest) - calculated from reliability
    priority_score = db.Column(db.Integer, nullable=False, default=5)

    # Preferred weekly hours target
    target_hours = db.Column(db.Integer, nullable=False, default=18)

    # Shift preference: only_6h, only_12h, both
    shift_preference = db.Column(db.String(10), nullable=False, default="both")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref=db.backref("employee_profile", uselist=False, lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "employee_role": self.employee_role,
            "patrol_shift_certified": self.patrol_shift_certified,
            "lockup_certified": self.lockup_certified,
            "east_lockup_trained": self.east_lockup_trained,
            "west_lockup_trained": self.west_lockup_trained,
            "probation_status": self.probation_status,
            "late_count": self.late_count,
            "no_show_count": self.no_show_count,
            "priority_score": self.priority_score,
            "target_hours": self.target_hours,
            "shift_preference": self.shift_preference,
        }

    @property
    def lockup_training_complete(self):
        """Returns True if both East and West lockup training completed."""
        return self.east_lockup_trained and self.west_lockup_trained
