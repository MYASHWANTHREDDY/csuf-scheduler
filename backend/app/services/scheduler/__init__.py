"""AI Scheduling Engine Package.

This package provides the constraint-based scheduling engine for generating
fair, policy-compliant work schedules for student employees.

Main exports:
- SchedulingEngine: The core scheduling engine class
- generate_schedule: Generate a schedule from a configuration
- apply_schedule: Apply a generated schedule to create shift records
"""

from .engine import SchedulingEngine, apply_schedule, generate_schedule

__all__ = ["SchedulingEngine", "generate_schedule", "apply_schedule"]
