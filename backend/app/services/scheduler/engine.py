"""AI Scheduling Engine using Google OR-Tools CP-SAT Solver.

This module implements the constraint-based scheduling engine that generates
fair, policy-compliant work schedules for student employees.

Key Features:
- Hard constraints: availability, max hours, rest periods, certifications
- Soft constraints: fairness, rotation, workload distribution
- Training rules: Trainee-FTO pairing, certification requirements
- Labor policies: break requirements, consecutive day limits
"""

import json
import logging
import os
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Set, Tuple

try:
    from ortools.sat.python import cp_model
except ImportError:
    cp_model = None
    logging.warning("OR-Tools not installed. AI scheduling will not work.")

try:
    from ...database import db
    from ...models import (
        Availability,
        EmployeeProfile,
        GeneratedSchedule,
        LeaveRequest,
        ScheduleConfig,
        Shift,
        ShiftTemplate,
        User,
    )
except ImportError:
    from database import db
    from models import (
        Availability,
        EmployeeProfile,
        GeneratedSchedule,
        LeaveRequest,
        ScheduleConfig,
        Shift,
        ShiftTemplate,
        User,
    )


logger = logging.getLogger(__name__)


class SchedulingEngine:
    """OR-Tools CP-SAT based scheduling engine.

    Implements all hard and soft constraints from the scheduling requirements.
    """

    def __init__(self, config: ScheduleConfig):
        """Initialize the scheduling engine with a configuration.

        Args:
            config: ScheduleConfig instance with scheduling parameters
        """
        self.config = config
        self.model = cp_model.CpModel() if cp_model else None
        self.solver = cp_model.CpSolver() if cp_model else None

        # Data containers
        self.employees: List[User] = []
        self.employee_profiles: Dict[int, EmployeeProfile] = {}
        self.shift_templates: List[ShiftTemplate] = []
        self.dates: List[date] = []
        self.availability_map: Dict[int, Dict[date, List[Tuple[time, time]]]] = {}
        self.leave_dates: Dict[int, Set[date]] = {}

        # Decision variables: assignments[(employee_id, date, template_id)] = BoolVar
        self.assignments: Dict[Tuple[int, date, int], Any] = {}

        # Results
        self.schedule_result: List[Dict] = []
        self.stats: Dict = {}
        self.flags: List[Dict] = []

    def load_data(self):
        """Load all required data from the database."""
        logger.info(f"Loading data for schedule config {self.config.id}")

        # Load employees with role 'student' or employee roles
        self.employees = User.query.filter(
            User.role.in_(["employee", "student", "FTO", "trainee", "regular"])
        ).all()

        # Load employee profiles
        profiles = EmployeeProfile.query.filter(
            EmployeeProfile.user_id.in_([e.id for e in self.employees])
        ).all()
        self.employee_profiles = {p.user_id: p for p in profiles}

        # Create default profiles for employees without one
        for emp in self.employees:
            if emp.id not in self.employee_profiles:
                # Map user role to employee role
                emp_role = "Regular"
                if emp.role == "FTO":
                    emp_role = "FTO"
                elif emp.role == "trainee":
                    emp_role = "Trainee"

                default_profile = EmployeeProfile(
                    user_id=emp.id,
                    employee_role=emp_role,
                    patrol_shift_certified=True,  # Default to certified
                    lockup_certified=False,
                    priority_score=5,
                )
                self.employee_profiles[emp.id] = default_profile

        # Load shift templates
        template_ids = self.config.get_shift_template_ids()
        if template_ids:
            self.shift_templates = ShiftTemplate.query.filter(
                ShiftTemplate.id.in_(template_ids), ShiftTemplate.is_active.is_(True)
            ).all()
        else:
            # Use all active templates
            self.shift_templates = ShiftTemplate.query.filter_by(is_active=True).all()

        # If no templates exist, create default ones
        if not self.shift_templates:
            self._create_default_templates()

        # Generate date range
        self.dates = self._generate_date_range(self.config.start_date, self.config.end_date)

        # Load availability for each employee
        self._load_availability()

        # Load leave requests
        self._load_leave_dates()

        logger.info(
            f"Loaded {len(self.employees)} employees, {len(self.shift_templates)} templates, {len(self.dates)} days"
        )

    def _create_default_templates(self):
        """Create default shift templates based on requirements."""
        default_templates = [
            ("Morning 6hr", time(6, 30), time(12, 30), 6.0, "PS"),
            ("Morning 12hr", time(6, 30), time(18, 30), 12.0, "PS"),
            ("Afternoon 6hr", time(12, 30), time(18, 30), 6.0, "PS"),
            ("Afternoon 12hr", time(12, 30), time(0, 30), 12.0, "PSL"),
            ("Evening 6hr", time(18, 30), time(0, 30), 6.0, "PSL"),
        ]

        for name, start, end, duration, shift_type in default_templates:
            template = ShiftTemplate(
                name=name,
                start_time=start,
                end_time=end,
                duration_hours=duration,
                shift_type=shift_type,
                is_active=True,
                required_staff=1,
            )
            db.session.add(template)
            self.shift_templates.append(template)

        db.session.commit()
        logger.info("Created default shift templates")

    def _generate_date_range(self, start: date, end: date) -> List[date]:
        """Generate list of dates between start and end inclusive."""
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        return dates

    def _load_availability(self):
        """Load and process availability for all employees.

        Note: Loads availability for dates in the schedule PLUS one extra day
        to support overnight shifts on the last scheduled day.
        """
        from datetime import timedelta

        # Include one day after the schedule ends for overnight shift support
        extended_dates = self.dates + [self.dates[-1] + timedelta(days=1)] if self.dates else []

        for emp in self.employees:
            self.availability_map[emp.id] = {}

            # Get all availability records for this employee
            availabilities = Availability.query.filter_by(user_id=emp.id).all()

            for d in extended_dates:
                self.availability_map[emp.id][d] = []

                for avail in availabilities:
                    if avail.is_recurring:
                        # Check if day of week matches
                        if d.weekday() == avail.day_of_week:
                            if avail.effective_until is None or d <= avail.effective_until:
                                self.availability_map[emp.id][d].append(
                                    (avail.start_time, avail.end_time)
                                )
                    else:
                        # One-time availability
                        if avail.date == d:
                            self.availability_map[emp.id][d].append(
                                (avail.start_time, avail.end_time)
                            )

    def _load_leave_dates(self):
        """Load approved leave dates for all employees."""
        for emp in self.employees:
            self.leave_dates[emp.id] = set()

            leaves = LeaveRequest.query.filter(
                LeaveRequest.user_id == emp.id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= self.config.end_date,
                LeaveRequest.end_date >= self.config.start_date,
            ).all()

            for leave in leaves:
                current = max(leave.start_date, self.config.start_date)
                end = min(leave.end_date, self.config.end_date)
                while current <= end:
                    self.leave_dates[emp.id].add(current)
                    current += timedelta(days=1)

    def _is_available(self, employee_id: int, d: date, template: ShiftTemplate) -> bool:
        """Check if employee is available for a shift on a given date.

        For overnight shifts (e.g., PSL 18:30-00:30), checks:
        1. Employee available on day d from shift_start to 23:59
        2. Employee available on day d+1 from 00:00 to shift_end

        For regular shifts, checks availability covers full shift time.
        """
        from datetime import time, timedelta

        # Check leave dates
        if d in self.leave_dates.get(employee_id, set()):
            return False

        shift_start = template.start_time
        shift_end = template.end_time
        shift_spans_midnight = shift_end < shift_start

        if shift_spans_midnight:
            # Overnight shift: need availability on BOTH days
            # Day 1: from shift_start to 23:59
            # Day 2: from 00:00 to shift_end

            next_day = d + timedelta(days=1)

            # Check if on leave next day
            if next_day in self.leave_dates.get(employee_id, set()):
                return False

            # Check day 1: available from shift_start to end of day
            day1_windows = self.availability_map.get(employee_id, {}).get(d, [])
            if not day1_windows:
                return False

            day1_ok = False
            end_of_day = time(23, 59, 0)
            for window_start, window_end in day1_windows:
                window_spans = window_end < window_start
                if window_spans:
                    # Window like 18:00-06:00 - check start covers shift_start
                    if shift_start >= window_start:
                        day1_ok = True
                        break
                else:
                    # Normal window - must cover shift_start to end of day
                    # Use >= for end check to handle 23:59:00 properly
                    if window_start <= shift_start and window_end >= end_of_day:
                        day1_ok = True
                        break

            if not day1_ok:
                return False

            # Check day 2: available from 00:00 to shift_end
            day2_windows = self.availability_map.get(employee_id, {}).get(next_day, [])
            if not day2_windows:
                return False

            start_of_day = time(0, 0, 0)
            for window_start, window_end in day2_windows:
                window_spans = window_end < window_start
                if window_spans:
                    # Window spans midnight - end part covers 00:00 to window_end
                    if shift_end <= window_end:
                        return True
                else:
                    # Normal window - must start at 00:00 and cover shift_end
                    if window_start <= start_of_day and window_end >= shift_end:
                        return True

            return False
        else:
            # Regular shift (doesn't span midnight)
            avail_windows = self.availability_map.get(employee_id, {}).get(d, [])
            if not avail_windows:
                return False

            for window_start, window_end in avail_windows:
                window_spans = window_end < window_start
                if window_spans:
                    # Window spans midnight - shift fits in first part or second part
                    if shift_start >= window_start or shift_end <= window_end:
                        return True
                else:
                    # Neither spans midnight - simple containment check
                    if window_start <= shift_start and shift_end <= window_end:
                        return True

            return False

    def _can_work_shift_type(self, employee_id: int, shift_type: str) -> bool:
        """Check if employee has required certifications for shift type.

        Rules:
        - CSOs/FTOs: Can work any shift (PS and PSL)
        - Trainees: Start with PSL only. Can work PS only after completing BOTH lockup trainings.
        """
        profile = self.employee_profiles.get(employee_id)
        if not profile:
            return True  # No profile means assume qualified

        if shift_type == "PS":
            # CSOs and FTOs can always work PS
            if profile.employee_role in ("Regular", "FTO"):
                return True
            # Trainees can work PS only after completing BOTH lockup trainings
            if profile.employee_role == "Trainee":
                return profile.east_lockup_trained and profile.west_lockup_trained
            return False
        elif shift_type == "PSL":
            # Everyone can work PSL shifts
            return True
        else:
            return True  # Custom shifts - assume qualified

    def _is_trainee(self, employee_id: int) -> bool:
        """Check if employee is a trainee."""
        profile = self.employee_profiles.get(employee_id)
        return profile and profile.employee_role == "Trainee"

    def _is_fto(self, employee_id: int) -> bool:
        """Check if employee is an FTO (Field Training Officer)."""
        profile = self.employee_profiles.get(employee_id)
        return profile and profile.employee_role == "FTO"

    def _get_ftos(self) -> List[int]:
        """Get list of FTO employee IDs."""
        return [emp.id for emp in self.employees if self._is_fto(emp.id)]

    def _get_trainees(self) -> List[int]:
        """Get list of trainee employee IDs."""
        return [emp.id for emp in self.employees if self._is_trainee(emp.id)]

    def build_model(self):
        """Build the CP-SAT model with all constraints."""
        if not self.model:
            raise RuntimeError("OR-Tools not available")

        logger.info("Building scheduling model...")

        # Create decision variables
        self._create_variables()

        # Add hard constraints
        self._add_availability_constraints()
        self._add_certification_constraints()
        self._add_shift_preference_constraints()
        self._add_max_hours_constraints()
        self._add_rest_period_constraints()
        self._add_no_overlap_constraints()
        self._add_employee_inclusion_constraints()
        self._add_staffing_constraints()

        # Add training rules
        self._add_trainee_fto_constraints()

        # Add labor policy constraints
        self._add_consecutive_days_constraints()

        # Add soft constraints as objectives
        self._add_fairness_objective()

        logger.info("Model built successfully")

    def _create_variables(self):
        """Create boolean decision variables for each possible assignment."""
        for emp in self.employees:
            for d in self.dates:
                for template in self.shift_templates:
                    var_name = f"assign_e{emp.id}_d{d.isoformat()}_t{template.id}"
                    self.assignments[(emp.id, d, template.id)] = self.model.NewBoolVar(var_name)

    def _add_availability_constraints(self):
        """Add constraints to respect employee availability."""
        for emp in self.employees:
            for d in self.dates:
                for template in self.shift_templates:
                    if not self._is_available(emp.id, d, template):
                        # Employee not available - force variable to 0
                        self.model.Add(self.assignments[(emp.id, d, template.id)] == 0)

    def _add_certification_constraints(self):
        """Add constraints for certification requirements."""
        for emp in self.employees:
            for d in self.dates:
                for template in self.shift_templates:
                    if not self._can_work_shift_type(emp.id, template.shift_type):
                        # Employee not certified for this shift type
                        self.model.Add(self.assignments[(emp.id, d, template.id)] == 0)

    def _add_shift_preference_constraints(self):
        """Enforce employee shift_preference (only_6h or both).

        If an employee's profile says only_6h, block all 12hr templates.
        If 'both' (default), no restriction.
        """
        for emp in self.employees:
            profile = self.employee_profiles.get(emp.id)
            if not profile or profile.shift_preference != "only_6h":
                continue

            for d in self.dates:
                for template in self.shift_templates:
                    duration = template.duration_hours or 6
                    if duration > 6:
                        # Block all 12hr+ templates for only_6h employees
                        self.model.Add(self.assignments[(emp.id, d, template.id)] == 0)

        logger.info("Shift preference constraints added")

    def _add_max_hours_constraints(self):
        """Add weekly hour limits (20 during term, 40 during break)."""
        max_hours = self.config.max_weekly_hours

        if not self.dates:
            return

        # Group dates by 7-day windows aligned to schedule start date
        # (avoids ISO week boundary issues where a 7-day schedule spans 2 ISO weeks)
        weeks: Dict[int, List[date]] = {}
        start_date = self.dates[0]
        for d in self.dates:
            days_since_start = (d - start_date).days
            week_index = days_since_start // 7
            if week_index not in weeks:
                weeks[week_index] = []
            weeks[week_index].append(d)

        # Add constraint for each employee for each week
        for emp in self.employees:
            for week_index, week_dates in weeks.items():
                weekly_hours = []
                for d in week_dates:
                    for template in self.shift_templates:
                        var = self.assignments[(emp.id, d, template.id)]
                        # Multiply by duration in hours (scaled to avoid floats)
                        duration = template.duration_hours or 6  # Default to 6 hours if None
                        hours_scaled = int(duration * 10)
                        weekly_hours.append(var * hours_scaled)

                if weekly_hours:
                    self.model.Add(sum(weekly_hours) <= max_hours * 10)

    def _add_rest_period_constraints(self):
        """Add minimum 8-hour rest between consecutive shifts."""
        min_rest = self.config.min_rest_hours

        for emp in self.employees:
            for i, d in enumerate(self.dates[:-1]):
                next_date = self.dates[i + 1]

                for t1 in self.shift_templates:
                    for t2 in self.shift_templates:
                        # Calculate time between end of t1 and start of t2
                        # Simplified: if same day evening + next day morning, enforce rest
                        end_hour = t1.end_time.hour if t1.end_time.hour > 0 else 24
                        start_hour = t2.start_time.hour

                        # Hours from end of shift on day d to start of shift on day d+1
                        rest_hours = (24 - end_hour) + start_hour

                        if rest_hours < min_rest:
                            # Cannot have both shifts
                            self.model.Add(
                                self.assignments[(emp.id, d, t1.id)]
                                + self.assignments[(emp.id, next_date, t2.id)]
                                <= 1
                            )

    def _add_no_overlap_constraints(self):
        """Ensure no employee is assigned overlapping shifts on the same day."""
        for emp in self.employees:
            for d in self.dates:
                # At most one shift per employee per day
                day_assignments = [
                    self.assignments[(emp.id, d, t.id)] for t in self.shift_templates
                ]
                self.model.Add(sum(day_assignments) <= 1)

    def _add_employee_inclusion_constraints(self):
        """Track employee hours and target 18h/week for every employee.

        No hard minimum to avoid infeasibility with trainee-FTO pairing.
        The fairness objective uses extremely heavy weights to push every
        employee toward the 18h/week target.
        """
        TARGET_WEEKLY_HOURS = 18  # Target: 18 hours per week

        # Calculate number of weeks in schedule
        logger.info(
            f"Setting up hour tracking (target: {TARGET_WEEKLY_HOURS}h/week, soft enforcement via objective)"
        )

        # Group dates by week (used for tracking only)
        weeks: Dict[int, List[date]] = {}
        for d in self.dates:
            week_num = d.isocalendar()[1]
            year = d.isocalendar()[0]
            week_key = year * 100 + week_num
            if week_key not in weeks:
                weeks[week_key] = []
            weeks[week_key].append(d)

        for emp in self.employees:
            # Calculate total hours for this employee
            total_hours_terms = []
            all_assignments = []

            for d in self.dates:
                for template in self.shift_templates:
                    var = self.assignments[(emp.id, d, template.id)]
                    all_assignments.append(var)

                    duration = template.duration_hours or 6
                    # Scale by 10 to avoid float issues
                    hours_scaled = int(duration * 10)
                    total_hours_terms.append(var * hours_scaled)

            if total_hours_terms:
                # Create variable for total hours
                total_hours_var = self.model.NewIntVar(0, 10000, f"emp_hours_e{emp.id}")
                self.model.Add(total_hours_var == sum(total_hours_terms))

                # Store for fairness objective
                if not hasattr(self, "employee_hours_vars"):
                    self.employee_hours_vars = {}
                self.employee_hours_vars[emp.id] = total_hours_var

                # Track total shifts (no hard minimum - handled by objective)
                total_shifts = self.model.NewIntVar(
                    0, len(all_assignments), f"emp_shifts_e{emp.id}"
                )
                self.model.Add(total_shifts == sum(all_assignments))

                if not hasattr(self, "employee_shift_vars"):
                    self.employee_shift_vars = {}
                self.employee_shift_vars[emp.id] = total_shifts

    def _add_staffing_constraints(self):
        """Add constraints for required staffing levels per time slot.

        Requirements use labels PS_AM (06:30-12:30), PS_PM (12:30-18:30),
        PSL (18:30-00:30). The constraint enforces that the total number of
        employees ON-SITE during each time slot equals the requirement.

        A 12hr shift employee works across TWO time slots, so they count
        toward both slots' coverage. For example, a Morning 12hr (06:30-18:30)
        employee counts toward both PS_AM and PS_PM coverage.

        Supports two formats:
        1. Simple: {"PS_AM": {"0": 2, ...}} - exactly N employees
        2. Range: {"PS_AM": {"0": {"min": 1, "max": 4}, ...}} - between min and max
        """
        if not self.config.daily_staffing_requirements:
            logger.info("No staffing requirements configured, using defaults")
            requirements = {
                "PS_AM": {str(i): {"min": 1, "max": 4} for i in range(7)},
                "PS_PM": {str(i): {"min": 1, "max": 4} for i in range(7)},
                "PSL": {str(i): {"min": 2, "max": 5} for i in range(7)},
            }
        else:
            try:
                requirements = json.loads(self.config.daily_staffing_requirements)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Invalid staffing requirements JSON: {e}")
                return

        logger.info(f"Loading staffing requirements: {requirements}")

        # Define time slots (in decimal hours) that each label represents
        TIME_SLOTS = {
            "PS_AM": (6.5, 12.5),  # 06:30-12:30
            "PS_PM": (12.5, 18.5),  # 12:30-18:30
            "PSL": (18.5, 24.5),  # 18:30-00:30
        }

        def _template_covers_slot(template, slot_start, slot_end):
            """Check if a template's working hours overlap with a time slot."""
            t_start = template.start_time.hour + template.start_time.minute / 60
            t_end = template.end_time.hour + template.end_time.minute / 60
            if t_end <= t_start:  # overnight: crosses midnight
                t_end += 24
            return t_start < slot_end and t_end > slot_start

        # For each time slot, find ALL templates whose working hours overlap
        slot_to_templates = {}
        for slot_label, (slot_start, slot_end) in TIME_SLOTS.items():
            covering = [
                t for t in self.shift_templates if _template_covers_slot(t, slot_start, slot_end)
            ]
            slot_to_templates[slot_label] = covering

        logger.info(
            f"Time-slot coverage mapping: "
            f"{[(k, [t.name for t in v]) for k, v in slot_to_templates.items()]}"
        )

        # Track constraints for reporting
        self.staffing_constraints = []

        for d in self.dates:
            day_num = str(d.weekday())  # 0=Monday, 6=Sunday

            for slot_label, day_requirements in requirements.items():
                templates = slot_to_templates.get(slot_label, [])
                if not templates:
                    logger.warning(f"No template covers time slot: {slot_label}")
                    continue

                # Parse requirement (support both simple and range formats)
                req = day_requirements.get(day_num, 0)
                if isinstance(req, dict):
                    min_staff = int(req.get("min", 1))
                    max_staff = int(req.get("max", 4))
                elif isinstance(req, (int, str)):
                    min_staff = max_staff = int(req) if req is not None else 1
                else:
                    min_staff, max_staff = 1, 4

                # Sum assignments across ALL templates that cover this time slot
                assignment_vars = []
                for template in templates:
                    for emp in self.employees:
                        assignment_vars.append(self.assignments[(emp.id, d, template.id)])

                if not assignment_vars:
                    continue

                # CONSTRAINTS: on-site coverage must be within [min, max]
                self.model.Add(sum(assignment_vars) >= min_staff)
                self.model.Add(sum(assignment_vars) <= max_staff)

                logger.debug(
                    f"Staffing constraint: {d} {slot_label} [{min_staff}, {max_staff}] "
                    f"(templates: {[t.name for t in templates]})"
                )

                self.staffing_constraints.append(
                    {
                        "date": d,
                        "templates": templates,
                        "min_required": min_staff,
                        "max_allowed": max_staff,
                        "shift_label": slot_label,
                    }
                )

    def _add_trainee_fto_constraints(self):
        """Trainees must always be paired with an FTO."""
        trainees = self._get_trainees()
        ftos = self._get_ftos()

        if not trainees or not ftos:
            return  # No trainees or no FTOs

        for trainee_id in trainees:
            for d in self.dates:
                for template in self.shift_templates:
                    trainee_var = self.assignments[(trainee_id, d, template.id)]

                    # If trainee is assigned, at least one FTO must also be assigned
                    fto_vars = [self.assignments[(fto_id, d, template.id)] for fto_id in ftos]

                    # trainee_var <= sum(fto_vars)
                    # This means if trainee is assigned (=1), at least one FTO must be (>=1)
                    self.model.Add(trainee_var <= sum(fto_vars))

    def _add_consecutive_days_constraints(self):
        """Limit consecutive working days."""
        max_consecutive = self.config.max_consecutive_days

        for emp in self.employees:
            # Check each window of max_consecutive + 1 days
            for i in range(len(self.dates) - max_consecutive):
                window_dates = self.dates[i : i + max_consecutive + 1]

                # Sum of "working on this date" for the window
                working_vars = []
                for d in window_dates:
                    day_work = []
                    for template in self.shift_templates:
                        day_work.append(self.assignments[(emp.id, d, template.id)])
                    # Create a helper variable: employee works on this date
                    works_on_day = self.model.NewBoolVar(f"works_e{emp.id}_d{d.isoformat()}")
                    self.model.Add(sum(day_work) >= 1).OnlyEnforceIf(works_on_day)
                    self.model.Add(sum(day_work) == 0).OnlyEnforceIf(works_on_day.Not())
                    working_vars.append(works_on_day)

                # At most max_consecutive days in any window of max_consecutive+1 days
                self.model.Add(sum(working_vars) <= max_consecutive)

    def _add_fairness_objective(self):
        """Add objective function prioritizing EQUAL hour distribution.

        Priority order:
        1. HEAVILY penalize employees with 0 hours (exclusion penalty) - HIGHEST
        2. Penalize employees with < 12 hours/week (below target penalty)
        3. Equal hours for all employees (fairness)
        4. Maximize total hours assigned (fill shifts)
        5. Light randomization for variety

        Those with less availability may get less hours, but we still
        try to be as fair as possible within constraints.
        """
        logger.info("Building fairness objective function...")

        # Calculate number of weeks for target hours
        num_weeks = max(1, len(self.dates) // 7)
        TARGET_WEEKLY_HOURS = 18
        target_total_hours_scaled = int(TARGET_WEEKLY_HOURS * num_weeks * 10)  # Scaled by 10

        # Use pre-computed hour variables if available, otherwise create them
        if hasattr(self, "employee_hours_vars") and self.employee_hours_vars:
            hour_vars = self.employee_hours_vars
        else:
            # Calculate total hours for each employee
            hour_vars = {}
            for emp in self.employees:
                hours = []
                for d in self.dates:
                    for template in self.shift_templates:
                        var = self.assignments[(emp.id, d, template.id)]
                        duration = template.duration_hours or 6
                        hours_scaled = int(duration * 10)
                        hours.append(var * hours_scaled)

                total_var = self.model.NewIntVar(0, 10000, f"obj_hours_e{emp.id}")
                self.model.Add(total_var == sum(hours))
                hour_vars[emp.id] = total_var

        objective_terms = []

        # HIGHEST PRIORITY: Penalize employees with ZERO shifts
        # This uses a boolean indicator for "has any shifts"
        exclusion_penalties = []
        for emp_id, hour_var in hour_vars.items():
            # Create boolean: is this employee excluded (0 hours)?
            is_excluded = self.model.NewBoolVar(f"excluded_e{emp_id}")
            # is_excluded is true if hour_var == 0
            self.model.Add(hour_var == 0).OnlyEnforceIf(is_excluded)
            self.model.Add(hour_var > 0).OnlyEnforceIf(is_excluded.Not())
            exclusion_penalties.append(is_excluded)

        # Weight of 10000 makes this the absolute highest priority
        objective_terms.append(-sum(exclusion_penalties) * 10000)
        logger.info(f"Added exclusion penalty for {len(hour_vars)} employees")

        # PRIMARY OBJECTIVE: Penalize employees below 18 hours/week
        under_target_penalties = []
        for emp_id, hour_var in hour_vars.items():
            shortfall = self.model.NewIntVar(0, 10000, f"shortfall_e{emp_id}")
            diff = self.model.NewIntVar(-10000, 10000, f"target_diff_e{emp_id}")
            self.model.Add(diff == target_total_hours_scaled - hour_var)
            self.model.AddMaxEquality(shortfall, [diff, 0])
            under_target_penalties.append(shortfall)

        # Weight of 5000 makes this second priority
        objective_terms.append(-sum(under_target_penalties) * 5000)
        logger.info("Added target hours penalty (18h/week target)")

        # SECONDARY OBJECTIVE: Minimize variance in hours (equality)
        if len(hour_vars) > 1:
            total_all_hours = sum(hour_vars.values())
            num_employees = len(hour_vars)

            avg_hours = self.model.NewIntVar(0, 10000, "avg_hours")
            self.model.Add(avg_hours * num_employees <= total_all_hours)
            self.model.Add(avg_hours * num_employees >= total_all_hours - num_employees + 1)

            deviations = []
            for emp_id, hour_var in hour_vars.items():
                abs_dev = self.model.NewIntVar(0, 10000, f"abs_dev_e{emp_id}")
                self.model.AddAbsEquality(abs_dev, hour_var - avg_hours)
                deviations.append(abs_dev)

            # Weight of 1000 for fairness
            fairness_penalty = sum(deviations)
            objective_terms.append(-fairness_penalty * 1000)

            logger.info(f"Added fairness objective for {num_employees} employees")

        # TERTIARY OBJECTIVE: Maximize total hours assigned
        objective_terms.append(sum(hour_vars.values()))

        # QUATERNARY: Incentivize 12-hour shifts with moderate bonus
        # This ensures the solver doesn't exclusively pick 6-hour shifts when both satisfy coverage.
        twelve_hr_bonus_terms = []
        for emp in self.employees:
            for d in self.dates:
                for template in self.shift_templates:
                    duration = template.duration_hours or 6
                    if duration >= 12:
                        # Moderate bonus for 12hr usage (100 weight)
                        twelve_hr_bonus_terms.append(
                            self.assignments[(emp.id, d, template.id)] * 100
                        )
        if twelve_hr_bonus_terms:
            objective_terms.append(sum(twelve_hr_bonus_terms))
            logger.info(f"Added 12-hour shift incentive ({len(twelve_hr_bonus_terms)} terms)")

        # QUINARY OBJECTIVE: Light randomization for variety
        import random

        random.seed(42)  # Reproducible randomness for testing
        for emp in self.employees:
            for d in self.dates:
                for template in self.shift_templates:
                    weight = random.randint(1, 10)
                    objective_terms.append(self.assignments[(emp.id, d, template.id)] * weight)

        self.model.Maximize(sum(objective_terms))
        logger.info("Fairness objective function built")

    def _get_weeks(self) -> List[int]:
        """Get list of unique week numbers in the date range."""
        weeks = set()
        for d in self.dates:
            week_key = d.isocalendar()[0] * 100 + d.isocalendar()[1]
            weeks.add(week_key)
        return list(weeks)

    def solve(self) -> bool:
        """Solve the scheduling model.

        Dynamically adjusts timeout based on problem size:
        - Small (< 50 employees): 15 seconds
        - Medium (50-100 employees): 30 seconds
        - Large (100-200 employees): 60 seconds

        Returns:
            True if a valid solution was found, False if infeasible.
        """
        if not self.solver:
            raise RuntimeError("OR-Tools not available")

        # Calculate problem size and set appropriate timeout
        num_employees = len(self.employees)
        num_days = len(self.dates)
        num_templates = len(self.shift_templates)
        problem_size = num_employees * num_days * num_templates

        if num_employees < 50:
            timeout = 15.0
        elif num_employees < 100:
            timeout = 30.0
        else:
            timeout = 60.0

        timeout_override = os.getenv("ORTOOLS_MAX_TIME_SECONDS")
        if timeout_override:
            try:
                timeout = max(1.0, float(timeout_override))
            except ValueError:
                logger.warning(
                    f"Invalid ORTOOLS_MAX_TIME_SECONDS={timeout_override!r}; using computed timeout"
                )

        # Render free/starter instances often enforce short worker timeouts.
        # Keep solve time under 30s request deadlines unless explicitly overridden.
        is_render = bool(os.getenv("RENDER")) or bool(os.getenv("RENDER_EXTERNAL_HOSTNAME"))
        if is_render and not timeout_override:
            timeout = min(timeout, 18.0)

        logger.info(
            f"Problem size: {num_employees} employees × {num_days} days × {num_templates} shifts = {problem_size} variables"
        )
        logger.info(f"Solver timeout: {timeout}s")

        # Set solver parameters
        self.solver.parameters.max_time_in_seconds = timeout
        # Keep search workers conservative by default to avoid OOM/worker crashes
        # on constrained hosting environments (e.g. small Render instances).
        workers_raw = os.getenv("ORTOOLS_NUM_SEARCH_WORKERS", "1")
        try:
            workers = max(1, int(workers_raw))
        except ValueError:
            workers = 1
        self.solver.parameters.num_search_workers = workers
        logger.info(f"Solver search workers: {workers}")

        status = self.solver.Solve(self.model)

        self.solution_quality = "UNKNOWN"
        self.infeasibility_reason = None

        if status == cp_model.OPTIMAL:
            logger.info("Solution found (OPTIMAL)")
            self._extract_solution()
            self.solution_quality = "OPTIMAL"
            return True
        elif status == cp_model.FEASIBLE:
            logger.info("Solution found (FEASIBLE)")
            self._extract_solution()
            self.solution_quality = "FEASIBLE"
            return True
        else:
            logger.warning(f"No solution found (status: {status})")
            self._analyze_infeasibility()
            return False

    def _analyze_infeasibility(self):
        """Analyze why no solution was found and identify problematic shifts."""
        self.infeasibility_reason = "Not enough available staff to meet staffing requirements."
        self.problem_shifts = []

        if hasattr(self, "staffing_constraints"):
            for constraint in self.staffing_constraints:
                d = constraint["date"]
                templates = constraint["templates"]
                shift_label = constraint["shift_label"]

                # Handle both old format (required) and new format (min_required, max_required)
                if "min_required" in constraint:
                    min_required = constraint["min_required"]
                else:
                    min_required = constraint.get("required", 1)

                # Count how many employees are available for ANY template in this shift label
                available_count = 0
                for emp in self.employees:
                    for template in templates:
                        if self._is_employee_available(emp.id, d, template):
                            available_count += 1
                            break  # Count each employee only once

                if available_count < min_required:
                    self.problem_shifts.append(
                        {
                            "date": d.isoformat(),
                            "day_of_week": d.strftime("%A"),
                            "shift": shift_label,
                            "required": min_required,
                            "available": available_count,
                            "shortage": min_required - available_count,
                        }
                    )

        if self.problem_shifts:
            logger.warning(
                f"Infeasibility analysis: {len(self.problem_shifts)} shifts cannot be staffed"
            )

    def _is_employee_available(self, emp_id: int, d: date, template: ShiftTemplate) -> bool:
        """Check if an employee is available for a specific shift.

        For overnight shifts (e.g., PSL 18:30-00:30), checks:
        1. Employee available on day d from shift_start to 23:59
        2. Employee available on day d+1 from 00:00 to shift_end

        For regular shifts, checks availability covers full shift time.
        """
        from datetime import time, timedelta

        # Check leave dates
        if emp_id in self.leave_dates and d in self.leave_dates[emp_id]:
            return False

        # Check availability
        if emp_id not in self.availability_map:
            return False

        if d not in self.availability_map[emp_id]:
            return False

        # Check if any availability window covers the shift
        shift_start = template.start_time
        shift_end = template.end_time
        shift_spans_midnight = shift_end < shift_start

        if shift_spans_midnight:
            # Overnight shift: need availability on BOTH days
            next_day = d + timedelta(days=1)

            # Check if on leave next day
            if emp_id in self.leave_dates and next_day in self.leave_dates[emp_id]:
                return False

            # Check day 1: available from shift_start to end of day
            day1_windows = self.availability_map.get(emp_id, {}).get(d, [])
            if not day1_windows:
                return False

            day1_ok = False
            end_of_day = time(23, 59, 0)
            for window_start, window_end in day1_windows:
                window_spans = window_end < window_start
                if window_spans:
                    if shift_start >= window_start:
                        day1_ok = True
                        break
                else:
                    if window_start <= shift_start and window_end >= end_of_day:
                        day1_ok = True
                        break

            if not day1_ok:
                return False

            # Check day 2: available from 00:00 to shift_end
            day2_windows = self.availability_map.get(emp_id, {}).get(next_day, [])
            if not day2_windows:
                return False

            start_of_day = time(0, 0, 0)
            for window_start, window_end in day2_windows:
                window_spans = window_end < window_start
                if window_spans:
                    if shift_end <= window_end:
                        return True
                else:
                    if window_start <= start_of_day and window_end >= shift_end:
                        return True

            return False
        else:
            # Regular shift (doesn't span midnight)
            for avail_start, avail_end in self.availability_map[emp_id][d]:
                avail_spans = avail_end < avail_start
                if avail_spans:
                    if shift_start >= avail_start or shift_end <= avail_end:
                        return True
                else:
                    if avail_start <= shift_start and shift_end <= avail_end:
                        return True

            return False

    def _extract_solution(self):
        """Extract the solution into a structured format."""
        self.schedule_result = []
        employee_total_hours = {emp.id: 0.0 for emp in self.employees}
        shift_assignments_count = {emp.id: 0 for emp in self.employees}

        for d in self.dates:
            day_schedule = {
                "date": d.isoformat(),
                "day_of_week": d.strftime("%A"),
                "shifts": [],
                "unfilled": [],
            }

            for template in self.shift_templates:
                shift_data = {
                    "template_id": template.id,
                    "name": template.name,
                    "time": f"{template.start_time.strftime('%H:%M')}–{template.end_time.strftime('%H:%M')}",
                    "type": template.shift_type,
                    "duration_hours": template.duration_hours or 6,
                    "assigned": [],
                    "break_flags": [],
                    "notes": [],
                }

                # Add break flags
                duration = template.duration_hours or 6
                if duration >= 6:
                    shift_data["break_flags"].append("break_required")
                if duration >= 12:
                    shift_data["break_flags"].append("multiple_breaks")

                # Find assigned employees
                assigned_employees = []
                for emp in self.employees:
                    var = self.assignments[(emp.id, d, template.id)]
                    if self.solver.Value(var) == 1:
                        profile = self.employee_profiles.get(emp.id)
                        emp_data = {
                            "employee_id": emp.id,
                            "name": emp.name
                            or f"{emp.first_name or ''} {emp.last_name or ''}".strip()
                            or emp.email,
                            "role": profile.employee_role if profile else "Regular",
                            "paired_with": None,
                        }

                        # Track hours
                        employee_total_hours[emp.id] += template.duration_hours or 6
                        shift_assignments_count[emp.id] += 1

                        # Add notes for special cases
                        if profile:
                            if profile.probation_status:
                                shift_data["notes"].append(f"{emp_data['name']}: probation")
                            no_show = profile.no_show_count or 0
                            late = profile.late_count or 0
                            if no_show > 2 or late > 3:
                                shift_data["notes"].append(
                                    f"{emp_data['name']}: reliability concern"
                                )

                        assigned_employees.append(emp_data)

                # Handle trainee-FTO pairing display
                trainees = [e for e in assigned_employees if e["role"] == "Trainee"]
                ftos = [e for e in assigned_employees if e["role"] == "FTO"]

                if trainees and ftos:
                    for i, trainee in enumerate(trainees):
                        fto = ftos[i % len(ftos)]
                        trainee["paired_with"] = fto["employee_id"]

                shift_data["assigned"] = assigned_employees

                # NOTE: Understaffing is checked at the shift-label level below,
                # not per individual template, since staffing requirements are
                # defined per label (PS_AM, PS_PM, PSL) summing across all
                # templates in that label.

                # Include ALL shifts in the output, even if not assigned
                day_schedule["shifts"].append(shift_data)

            # Check understaffing at the SHIFT LABEL level (not per template)
            if hasattr(self, "staffing_constraints"):
                # Group assignments by shift label for this day
                checked_labels = set()
                for constraint in self.staffing_constraints:
                    if constraint["date"] != d:
                        continue
                    label = constraint["shift_label"]
                    if label in checked_labels:
                        continue
                    checked_labels.add(label)

                    min_required = constraint.get("min_required", constraint.get("required", 1))

                    # Count total assigned across ALL templates in this label
                    total_assigned = 0
                    template_names = []
                    for t in constraint["templates"]:
                        template_names.append(t.name)
                        for shift in day_schedule["shifts"]:
                            if shift["template_id"] == t.id:
                                total_assigned += len(shift["assigned"])

                    if total_assigned < min_required:
                        day_schedule["unfilled"].append(
                            {"shift": label, "needed": min_required - total_assigned}
                        )

            self.schedule_result.append(day_schedule)

        # Calculate statistics
        total_weeks = max(1, len(self.dates) // 7)
        avg_hours = (
            sum(employee_total_hours.values()) / len(self.employees) if self.employees else 0
        )

        self.stats = {
            "hours_per_employee": {str(k): round(v, 1) for k, v in employee_total_hours.items()},
            "shifts_per_employee": shift_assignments_count,
            "average_hours": round(avg_hours, 1),
            "average_weekly_hours": round(avg_hours / total_weeks, 1),
            "total_shifts_filled": sum(shift_assignments_count.values()),
            "fairness_score": self._calculate_fairness_score(employee_total_hours),
        }

        # Generate flags for issues
        self._generate_flags()

    def _calculate_fairness_score(self, hours: Dict[int, float]) -> float:
        """Calculate a fairness score based on hour distribution.

        Returns a value 0-100 where 100 is perfectly fair.
        """
        if not hours:
            return 100.0

        values = list(hours.values())
        avg = sum(values) / len(values)

        if avg == 0:
            return 100.0

        # Calculate coefficient of variation
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        std_dev = variance**0.5
        cv = std_dev / avg if avg > 0 else 0

        # Convert to 0-100 score (lower CV = higher score)
        score = max(0, 100 - (cv * 100))
        return round(score, 1)

    def _generate_flags(self):
        """Generate warning flags for scheduling issues."""
        self.flags = []

        # Check for unfilled shifts - group by date and provide summary
        understaffed_by_date = {}
        for day in self.schedule_result:
            if day.get("unfilled"):
                understaffed_by_date[day["date"]] = []
                for unfilled in day.get("unfilled", []):
                    understaffed_by_date[day["date"]].append(
                        {"shift": unfilled["shift"], "needed": unfilled["needed"]}
                    )

        # Add detailed flags for understaffed shifts
        for date_str, unfilled_shifts in understaffed_by_date.items():
            for unfilled in unfilled_shifts:
                self.flags.append(
                    {
                        "type": "understaffed_shift",
                        "date": date_str,
                        "shift": unfilled["shift"],
                        "issue": f"Understaffed by {unfilled['needed']} employee(s)",
                        "severity": "warning",
                    }
                )

        # Check for employees with too few/many hours
        # Use actual number of weeks based on date range, not ISO week count
        num_weeks = max(1, len(self.dates) // 7)
        target = self.config.target_hours_per_week * num_weeks
        for emp_id, hours in self.stats.get("hours_per_employee", {}).items():
            deviation = abs(float(hours) - target)
            if deviation > target * 0.3:  # More than 30% deviation
                emp = db.session.get(User, int(emp_id))
                name = emp.name or emp.email if emp else f"Employee {emp_id}"
                self.flags.append(
                    {
                        "type": "hour_imbalance",
                        "employee": name,
                        "issue": f"Hours: {hours}h vs target {target}h",
                        "severity": "info",
                    }
                )

    def get_results(self) -> Tuple[List[Dict], Dict, List[Dict]]:
        """Get the scheduling results.

        Returns:
            Tuple of (schedule_data, stats, flags)
        """
        return self.schedule_result, self.stats, self.flags


def generate_schedule(config_id: int) -> GeneratedSchedule:
    """Generate a schedule from a configuration.

    Args:
        config_id: ID of the ScheduleConfig to use

    Returns:
        GeneratedSchedule instance with results
    """
    config = db.session.get(ScheduleConfig, config_id)
    if not config:
        raise ValueError(f"Config {config_id} not found")

    # Create the generated schedule record
    generated = GeneratedSchedule(config_id=config_id, status="generating")
    db.session.add(generated)
    db.session.commit()

    try:
        # Create and run the scheduling engine
        engine = SchedulingEngine(config)
        engine.load_data()
        engine.build_model()

        if engine.solve():
            schedule_data, stats, flags = engine.get_results()

            generated.schedule_data = json.dumps(schedule_data)
            generated.stats_data = json.dumps(stats)
            generated.flags_data = json.dumps(flags)
            generated.status = "completed"
            generated.completed_at = datetime.utcnow()

            # Add solution quality info to error_message field
            solution_quality = getattr(engine, "solution_quality", "UNKNOWN")
            if solution_quality == "FEASIBLE":
                generated.error_message = f"Schedule generated. Solution quality: FEASIBLE. Check flags for understaffed shifts ({len([f for f in flags if 'Understaffed' in f.get('issue', '')])} found)."
            elif solution_quality == "OPTIMAL":
                generated.error_message = None  # Perfect solution
        else:
            generated.status = "failed"

            # Provide detailed diagnostics
            num_employees = len(engine.employees) if hasattr(engine, "employees") else 0
            num_dates = len(engine.dates) if hasattr(engine, "dates") else 0
            num_templates = len(engine.shift_templates) if hasattr(engine, "shift_templates") else 0

            error_details = [
                "Cannot generate schedule: Not enough available staff to meet requirements."
            ]
            error_details.append(
                f"Resources: {num_employees} employee(s), {num_dates} day(s), {num_templates} shift template(s)."
            )

            # Add specific problem shifts information
            if hasattr(engine, "problem_shifts") and engine.problem_shifts:
                error_details.append("PROBLEM SHIFTS:")
                for ps in engine.problem_shifts[:10]:  # Limit to first 10
                    error_details.append(
                        f"  - {ps['day_of_week']} {ps['date']} {ps['shift']}: Need {ps['required']}, only {ps['available']} available (short by {ps['shortage']})"
                    )
                if len(engine.problem_shifts) > 10:
                    error_details.append(f"  ... and {len(engine.problem_shifts) - 10} more shifts")

            error_details.append(
                "Solutions: Add more employees, adjust availability, or reduce staffing requirements."
            )

            generated.error_message = " ".join(error_details)

        db.session.commit()

    except Exception as e:
        logger.exception("Error generating schedule")
        generated.status = "failed"
        generated.error_message = str(e)
        db.session.commit()

    return generated


def apply_schedule(generated_id: int) -> int:
    """Apply a generated schedule to create actual Shift records.

    Args:
        generated_id: ID of the GeneratedSchedule to apply

    Returns:
        Number of shifts created
    """
    generated = db.session.get(GeneratedSchedule, generated_id)
    if not generated:
        raise ValueError("Invalid schedule")
    if generated.status not in ("completed", "applied"):
        raise ValueError("Schedule is not ready to apply")

    schedule_data = generated.get_schedule_data()
    if not schedule_data:
        raise ValueError("No schedule data to apply")

    # Collect all dates covered by this schedule
    schedule_dates = []
    for day_data in schedule_data:
        schedule_dates.append(datetime.strptime(day_data["date"], "%Y-%m-%d").date())

    # Delete existing shifts in the date range to prevent duplicates
    if schedule_dates:
        min_date = min(schedule_dates)
        max_date = max(schedule_dates)
        Shift.query.filter(Shift.date >= min_date, Shift.date <= max_date).delete()

    shifts_created = 0

    for day_data in schedule_data:
        shift_date = datetime.strptime(day_data["date"], "%Y-%m-%d").date()

        for shift_data in day_data.get("shifts", []):
            template = db.session.get(ShiftTemplate, shift_data["template_id"])
            if not template:
                continue

            for emp_data in shift_data.get("assigned", []):
                shift = Shift(
                    date=shift_date,
                    start_time=template.start_time,
                    end_time=template.end_time,
                    assigned_user_id=emp_data["employee_id"],
                )
                db.session.add(shift)
                shifts_created += 1

    generated.status = "applied"
    db.session.commit()

    return shifts_created
