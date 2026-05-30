"""SQLAlchemy models for CSUF Scheduler.

This package contains all database models organized by domain.
All models are re-exported here for backward compatibility.
"""

from .audit import AuditLog
from .availability import Availability, AvailabilityRequest, LeaveRequest
from .communication import Announcement, CallOffRequest, Notification, SwapRequest
from .employee import EmployeeProfile
from .scheduling import GeneratedSchedule, ScheduleConfig, ScheduleOverride
from .shift import Shift, ShiftTemplate
from .time_adjustment import TimeAdjustmentRequest
from .timesheet import PayPeriod, Timesheet, TimesheetAuditLog, TimesheetComment, TimesheetLine
from .user import User

__all__ = [
    # User
    "User",
    # Shift
    "Shift",
    "ShiftTemplate",
    # Availability
    "Availability",
    "LeaveRequest",
    "AvailabilityRequest",
    # Employee
    "EmployeeProfile",
    # Scheduling
    "ScheduleConfig",
    "GeneratedSchedule",
    "ScheduleOverride",
    # Communication
    "SwapRequest",
    "Notification",
    "Announcement",
    "CallOffRequest",
    # Time adjustments
    "TimeAdjustmentRequest",
    # Timesheets
    "PayPeriod",
    "Timesheet",
    "TimesheetLine",
    "TimesheetComment",
    "TimesheetAuditLog",
    # Global audit
    "AuditLog",
]
