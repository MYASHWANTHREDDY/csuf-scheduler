"""AI Scheduler API routes.
Prefix: /api/scheduler

Endpoints for AI-powered schedule generation and management.
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, make_response, request

try:
    from ..database import db
    from ..models import (
        EmployeeProfile,
        GeneratedSchedule,
        LeaveRequest,
        ScheduleConfig,
        ScheduleOverride,
        Shift,
        ShiftTemplate,
        User,
    )
    from ..services.scheduler import apply_schedule, generate_schedule
    from ..utils.audit import log_audit
    from ..utils.auth import require_role as _require_role
    from ..utils.parsers import parse_date as _parse_date
    from ..utils.parsers import parse_time as _parse_time
except ImportError:
    from database import db
    from models import (
        EmployeeProfile,
        GeneratedSchedule,
        LeaveRequest,
        ScheduleConfig,
        ScheduleOverride,
        ShiftTemplate,
        User,
    )
    from services.scheduler import apply_schedule, generate_schedule
    from utils.audit import log_audit
    from utils.auth import require_role as _require_role
    from utils.parsers import parse_date as _parse_date
    from utils.parsers import parse_time as _parse_time


scheduler_bp = Blueprint("scheduler", __name__, url_prefix="/api/scheduler")
logger = logging.getLogger(__name__)


# =============================================================================
# EMPLOYEE PROFILES
# =============================================================================


@scheduler_bp.route("/profiles", methods=["GET"])
def list_profiles():
    """List all employee profiles with training/certification data."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    profiles = EmployeeProfile.query.all()

    user_ids = [profile.user_id for profile in profiles]
    users_by_id = (
        {item.id: item for item in User.query.filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    # Join with user data for display
    result = []
    for profile in profiles:
        user_obj = users_by_id.get(profile.user_id)
        if user_obj:
            data = profile.to_dict()
            data["user_name"] = (
                user_obj.name
                or f"{user_obj.first_name or ''} {user_obj.last_name or ''}".strip()
                or user_obj.email
            )
            data["user_email"] = user_obj.email
            result.append(data)

    return jsonify(result)


@scheduler_bp.route("/profiles/<int:user_id>", methods=["GET"])
def get_profile(user_id):
    """Get a specific employee profile."""
    current_user, err = _require_role(None)
    if err:
        return err

    # Users can view their own profile, supervisors can view all
    if current_user.id != user_id and current_user.role not in {"admin", "supervisor"}:
        return make_response(jsonify({"error": "forbidden"}), 403)

    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        # Auto-create default profile if it doesn't exist
        user = db.session.get(User, user_id)
        if not user:
            return make_response(jsonify({"error": "user not found"}), 404)

        profile = EmployeeProfile(
            user_id=user_id, employee_role="Regular", patrol_shift_certified=True, priority_score=5
        )
        db.session.add(profile)
        db.session.commit()

    return jsonify(profile.to_dict())


@scheduler_bp.route("/profiles/<int:user_id>", methods=["PUT"])
def update_profile(user_id):
    """Update an employee profile."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        # Create new profile if it doesn't exist
        profile = EmployeeProfile(user_id=user_id)
        db.session.add(profile)

    data = request.get_json() or {}

    # Update fields
    if "employee_role" in data:
        profile.employee_role = data["employee_role"]
    if "patrol_shift_certified" in data:
        profile.patrol_shift_certified = data["patrol_shift_certified"]
    if "lockup_certified" in data:
        profile.lockup_certified = data["lockup_certified"]
    if "east_lockup_trained" in data:
        profile.east_lockup_trained = data["east_lockup_trained"]
    if "west_lockup_trained" in data:
        profile.west_lockup_trained = data["west_lockup_trained"]
    if "probation_status" in data:
        profile.probation_status = data["probation_status"]
    if "late_count" in data:
        profile.late_count = data["late_count"]
    if "no_show_count" in data:
        profile.no_show_count = data["no_show_count"]
    if "priority_score" in data:
        profile.priority_score = max(1, min(10, data["priority_score"]))
    if "target_hours" in data:
        profile.target_hours = data["target_hours"]
    if "shift_preference" in data:
        if data["shift_preference"] in ["only_6h", "both"]:
            profile.shift_preference = data["shift_preference"]

    db.session.flush()
    log_audit("update", "employee_profile", profile.user_id, after=profile.to_dict())
    db.session.commit()
    return jsonify(profile.to_dict())


@scheduler_bp.route("/profiles/bulk", methods=["POST"])
def bulk_create_profiles():
    """Create default profiles for all employees without one."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    # Find employees without profiles
    employees = User.query.filter(User.role.in_(["student", "FTO", "trainee", "regular"])).all()
    existing_ids = {p.user_id for p in EmployeeProfile.query.all()}

    created = 0
    for emp in employees:
        if emp.id not in existing_ids:
            emp_role = "Regular"
            if emp.role == "FTO":
                emp_role = "FTO"
            elif emp.role == "trainee":
                emp_role = "Trainee"

            profile = EmployeeProfile(
                user_id=emp.id,
                employee_role=emp_role,
                patrol_shift_certified=True,
                priority_score=5,
            )
            db.session.add(profile)
            created += 1

    db.session.commit()
    return jsonify({"created": created})


# =============================================================================
# SHIFT TEMPLATES
# =============================================================================


@scheduler_bp.route("/templates", methods=["GET"])
def list_templates():
    """List all shift templates."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    templates = ShiftTemplate.query.order_by(ShiftTemplate.start_time).all()
    return jsonify([t.to_dict() for t in templates])


@scheduler_bp.route("/templates", methods=["POST"])
def create_template():
    """Create a new shift template."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json() or {}

    name = data.get("name")
    start = _parse_time(data.get("start_time"))
    end = _parse_time(data.get("end_time"))
    duration = data.get("duration_hours")
    shift_type = data.get("shift_type", "PS")
    required_staff = data.get("required_staff", 1)

    if not all([name, start, end, duration]):
        return make_response(
            jsonify({"error": "name, start_time, end_time, and duration_hours are required"}), 400
        )

    template = ShiftTemplate(
        name=name,
        start_time=start,
        end_time=end,
        duration_hours=duration,
        shift_type=shift_type,
        required_staff=required_staff,
    )
    db.session.add(template)
    db.session.flush()
    log_audit("create", "shift_template", template.id, after=template.to_dict())
    db.session.commit()

    return make_response(jsonify(template.to_dict()), 201)


@scheduler_bp.route("/templates/<int:template_id>", methods=["PUT"])
def update_template(template_id):
    """Update a shift template."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    template = ShiftTemplate.query.get(template_id)
    if not template:
        return make_response(jsonify({"error": "template not found"}), 404)

    data = request.get_json() or {}

    if "name" in data:
        template.name = data["name"]
    if "start_time" in data:
        template.start_time = _parse_time(data["start_time"])
    if "end_time" in data:
        template.end_time = _parse_time(data["end_time"])
    if "duration_hours" in data:
        template.duration_hours = data["duration_hours"]
    if "shift_type" in data:
        template.shift_type = data["shift_type"]
    if "is_active" in data:
        template.is_active = data["is_active"]
    if "required_staff" in data:
        template.required_staff = data["required_staff"]

    log_audit("update", "shift_template", template.id, after=template.to_dict())
    db.session.commit()
    return jsonify(template.to_dict())


@scheduler_bp.route("/templates/<int:template_id>", methods=["DELETE"])
def delete_template(template_id):
    """Delete (deactivate) a shift template."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    template = ShiftTemplate.query.get(template_id)
    if not template:
        return make_response(jsonify({"error": "template not found"}), 404)

    # Soft delete - just deactivate
    before = template.to_dict()
    template.is_active = False
    log_audit("deactivate", "shift_template", template.id, before=before, after=template.to_dict())
    db.session.commit()

    return jsonify({"ok": True})


@scheduler_bp.route("/templates/seed", methods=["POST"])
def seed_templates():
    """Seed default shift templates."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    default_templates = [
        ("Morning 6hr (PS)", "06:30", "12:30", 6.0, "PS", 2),
        ("Full Day 12hr (PS)", "06:30", "18:30", 12.0, "PS", 2),
        ("Afternoon 6hr (PS)", "12:30", "18:30", 6.0, "PS", 2),
        ("Afternoon 12hr (PSL)", "12:30", "00:30", 12.0, "PSL", 2),
        ("Evening 6hr (PSL)", "18:30", "00:30", 6.0, "PSL", 2),
    ]

    created = 0
    for name, start, end, duration, shift_type, staff in default_templates:
        # Check if already exists
        existing = ShiftTemplate.query.filter_by(name=name).first()
        if not existing:
            template = ShiftTemplate(
                name=name,
                start_time=_parse_time(start),
                end_time=_parse_time(end),
                duration_hours=duration,
                shift_type=shift_type,
                required_staff=staff,
            )
            db.session.add(template)
            created += 1

    db.session.commit()
    return jsonify({"created": created})


# =============================================================================
# LEAVE REQUESTS
# =============================================================================


@scheduler_bp.route("/leave", methods=["GET"])
def list_leave_requests():
    """List leave requests."""
    current_user, err = _require_role(None)
    if err:
        return err

    if current_user.role in {"admin", "supervisor"}:
        # Supervisors see all
        leaves = LeaveRequest.query.order_by(LeaveRequest.start_date.desc()).all()
    else:
        # Users see their own
        leaves = (
            LeaveRequest.query.filter_by(user_id=current_user.id)
            .order_by(LeaveRequest.start_date.desc())
            .all()
        )

    return jsonify([leave.to_dict() for leave in leaves])


@scheduler_bp.route("/leave", methods=["POST"])
def create_leave_request():
    """Create a leave request."""
    current_user, err = _require_role(None)
    if err:
        return err

    data = request.get_json() or {}

    start = _parse_date(data.get("start_date"))
    end = _parse_date(data.get("end_date"))
    reason = data.get("reason", "")

    if not start or not end:
        return make_response(jsonify({"error": "start_date and end_date are required"}), 400)

    if end < start:
        return make_response(jsonify({"error": "end_date must be after start_date"}), 400)

    leave = LeaveRequest(user_id=current_user.id, start_date=start, end_date=end, reason=reason)
    db.session.add(leave)
    db.session.commit()

    return make_response(jsonify(leave.to_dict()), 201)


@scheduler_bp.route("/leave/<int:leave_id>/approve", methods=["POST"])
def approve_leave(leave_id):
    """Approve a leave request."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    leave = LeaveRequest.query.get(leave_id)
    if not leave:
        return make_response(jsonify({"error": "leave request not found"}), 404)

    leave.status = "approved"
    db.session.commit()

    return jsonify(leave.to_dict())


@scheduler_bp.route("/leave/<int:leave_id>/deny", methods=["POST"])
def deny_leave(leave_id):
    """Deny a leave request."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    leave = LeaveRequest.query.get(leave_id)
    if not leave:
        return make_response(jsonify({"error": "leave request not found"}), 404)

    leave.status = "denied"
    db.session.commit()

    return jsonify(leave.to_dict())


# =============================================================================
# SCHEDULE CONFIGURATION
# =============================================================================


@scheduler_bp.route("/configs", methods=["GET"])
def list_configs():
    """List all schedule configurations."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    configs = ScheduleConfig.query.order_by(ScheduleConfig.created_at.desc()).all()
    return jsonify([c.to_dict() for c in configs])


@scheduler_bp.route("/configs", methods=["POST"])
def create_config():
    """Create a new schedule configuration."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json() or {}

    name = data.get("name", "Schedule Configuration")
    start = _parse_date(data.get("start_date"))
    end = _parse_date(data.get("end_date"))

    if not start or not end:
        return make_response(jsonify({"error": "start_date and end_date are required"}), 400)

    if end < start:
        return make_response(jsonify({"error": "end_date must be after start_date"}), 400)

    academic_period = data.get("academic_period", "term")
    max_hours = 20 if academic_period == "term" else 40

    config = ScheduleConfig(
        name=name,
        start_date=start,
        end_date=end,
        academic_period=academic_period,
        max_weekly_hours=data.get("max_weekly_hours", max_hours),
        target_hours_per_week=data.get("target_hours_per_week", 18),
        min_rest_hours=data.get("min_rest_hours", 8),
        max_consecutive_days=data.get("max_consecutive_days", 5),
        shift_template_ids=json.dumps(data.get("shift_template_ids", [])),
        special_events=json.dumps(data.get("special_events", [])),
        created_by=user.id,
    )
    db.session.add(config)
    db.session.flush()
    log_audit("create", "schedule_config", config.id, after=config.to_dict())
    db.session.commit()

    return make_response(jsonify(config.to_dict()), 201)


@scheduler_bp.route("/configs/<int:config_id>", methods=["GET"])
def get_config(config_id):
    """Get a specific schedule configuration."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    config = db.session.get(ScheduleConfig, config_id)
    if not config:
        return make_response(jsonify({"error": "config not found"}), 404)

    return jsonify(config.to_dict())


@scheduler_bp.route("/configs/<int:config_id>", methods=["PUT"])
def update_config(config_id):
    """Update a schedule configuration."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    config = db.session.get(ScheduleConfig, config_id)
    if not config:
        return make_response(jsonify({"error": "config not found"}), 404)

    data = request.get_json() or {}

    # Update date fields if provided
    if "start_date" in data:
        start = _parse_date(data.get("start_date"))
        if start:
            config.start_date = start
        else:
            return make_response(jsonify({"error": "invalid start_date format"}), 400)

    if "end_date" in data:
        end = _parse_date(data.get("end_date"))
        if end:
            config.end_date = end
        else:
            return make_response(jsonify({"error": "invalid end_date format"}), 400)

    # Validate dates
    if config.end_date < config.start_date:
        return make_response(jsonify({"error": "end_date must be after start_date"}), 400)

    # Update other optional fields
    if "name" in data:
        config.name = data["name"]
    if "max_weekly_hours" in data:
        config.max_weekly_hours = data["max_weekly_hours"]
    if "target_hours_per_week" in data:
        config.target_hours_per_week = data["target_hours_per_week"]
    if "min_rest_hours" in data:
        config.min_rest_hours = data["min_rest_hours"]
    if "max_consecutive_days" in data:
        config.max_consecutive_days = data["max_consecutive_days"]

    db.session.commit()
    log_audit("update", "schedule_config", config.id, after=config.to_dict())

    return jsonify(config.to_dict())


@scheduler_bp.route("/configs/<int:config_id>", methods=["DELETE"])
def delete_config(config_id):
    """Delete a schedule configuration."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    config = db.session.get(ScheduleConfig, config_id)
    if not config:
        return make_response(jsonify({"error": "config not found"}), 404)

    before = config.to_dict()
    db.session.delete(config)
    log_audit("delete", "schedule_config", config_id, before=before)
    db.session.commit()

    return jsonify({"ok": True})


# =============================================================================
# STAFFING REQUIREMENTS TABLE
# =============================================================================


@scheduler_bp.route("/staffing-requirements", methods=["GET"])
def get_staffing_requirements():
    """Get the staffing requirements table data."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    # Get the most recent config or create default
    config = ScheduleConfig.query.order_by(ScheduleConfig.id.desc()).first()

    if config and config.daily_staffing_requirements:
        try:
            return jsonify(json.loads(config.daily_staffing_requirements))
        except (json.JSONDecodeError, TypeError):
            pass

    # Return default staffing requirements
    default = {
        "PS_AM": {"0": 2, "1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2},
        "PS_PM": {"0": 2, "1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2},
        "PSL": {"0": 2, "1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2},
    }
    return jsonify(default)


@scheduler_bp.route("/staffing-requirements", methods=["POST"])
def save_staffing_requirements():
    """Save the staffing requirements table data."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json() or {}

    # Get or create a config to store the staffing requirements
    config = ScheduleConfig.query.order_by(ScheduleConfig.id.desc()).first()

    if not config:
        # Create a default config if none exists
        from datetime import date, timedelta

        today = date.today()
        config = ScheduleConfig(
            name="Default Config",
            start_date=today,
            end_date=today + timedelta(days=30),
            academic_period="term",
            created_by=user.id,
        )
        db.session.add(config)

    before = config.daily_staffing_requirements
    config.daily_staffing_requirements = json.dumps(data)
    log_audit(
        "update",
        "staffing_requirements",
        config.id,
        before={"daily_staffing_requirements": before},
        after={"daily_staffing_requirements": config.daily_staffing_requirements},
    )
    db.session.commit()

    return jsonify({"ok": True})


# =============================================================================
# SCHEDULE GENERATION
# =============================================================================


@scheduler_bp.route("/generate", methods=["POST"])
def generate_new_schedule():
    """Generate a new schedule from a configuration."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json() or {}
    config_id = data.get("config_id")

    if not config_id:
        return make_response(jsonify({"error": "config_id is required"}), 400)

    config = db.session.get(ScheduleConfig, config_id)
    if not config:
        return make_response(jsonify({"error": "config not found"}), 404)

    try:
        generated = generate_schedule(config_id)
        log_audit("generate", "generated_schedule", generated.id, after=generated.to_dict())
        return jsonify(generated.to_dict(include_data=True))
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)


@scheduler_bp.route("/schedules", methods=["GET"])
def list_generated_schedules():
    """List all generated schedules.

    ---
    tags:
        - Scheduler
    responses:
        200:
            description: Generated schedule list
        403:
            description: Forbidden
    """
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    schedules = GeneratedSchedule.query.order_by(GeneratedSchedule.created_at.desc()).all()
    return jsonify([item.to_dict() for item in schedules])


@scheduler_bp.route("/schedules/<int:schedule_id>", methods=["GET"])
def get_generated_schedule(schedule_id):
    """Get a specific generated schedule with full data."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    schedule = db.session.get(GeneratedSchedule, schedule_id)
    if not schedule:
        return make_response(jsonify({"error": "schedule not found"}), 404)

    return jsonify(schedule.to_dict(include_data=True))


@scheduler_bp.route("/schedules/<int:schedule_id>", methods=["DELETE"])
def delete_generated_schedule(schedule_id):
    """Delete a generated schedule and its associated shifts if applied."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    schedule = db.session.get(GeneratedSchedule, schedule_id)
    if not schedule:
        return make_response(jsonify({"error": "schedule not found"}), 404)

    # If schedule was applied, delete the shifts that were created from it
    if schedule.status == "applied":
        # Extract shift dates and employee IDs from schedule_data to identify which shifts to delete
        try:
            schedule_data = schedule.get_schedule_data()
            if schedule_data:
                for day_data in schedule_data:
                    shift_date = datetime.strptime(day_data["date"], "%Y-%m-%d").date()
                    for shift_data in day_data.get("shifts", []):
                        for emp_data in shift_data.get("assigned", []):
                            # Find and delete matching shifts by date and employee
                            Shift.query.filter_by(
                                date=shift_date, assigned_user_id=emp_data["employee_id"]
                            ).delete(synchronize_session=False)
        except Exception as e:
            logger.warning(f"Error deleting shifts from schedule {schedule_id}: {e}")
            # Continue with schedule deletion anyway
        db.session.flush()  # Ensure shifts are deleted before deleting schedule

    before = schedule.to_dict()
    db.session.delete(schedule)
    log_audit("delete", "generated_schedule", schedule_id, before=before)
    db.session.commit()
    return jsonify({"success": True, "message": "Schedule and its shifts deleted"})


@scheduler_bp.route("/schedules/<int:schedule_id>/cancel", methods=["POST"])
def cancel_schedule_generation(schedule_id):
    """Cancel an in-progress schedule generation by marking it as failed."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    schedule = db.session.get(GeneratedSchedule, schedule_id)
    if not schedule:
        return make_response(jsonify({"error": "schedule not found"}), 404)

    # Idempotent behavior: if schedule is no longer generating, return a helpful
    # success response so stale UI actions do not hard-fail.
    if schedule.status != "generating":
        return jsonify(
            {
                "success": False,
                "message": f'Schedule is already in "{schedule.status}" status; nothing to cancel',
                "status": schedule.status,
            }
        )

    # Mark the schedule as failed so it can be deleted
    schedule.status = "failed"
    schedule.error_message = "Schedule generation was cancelled by user"
    log_audit("cancel", "generated_schedule", schedule.id, after=schedule.to_dict())
    db.session.commit()

    return jsonify(
        {"success": True, "message": "Schedule generation cancelled and marked as failed"}
    )


@scheduler_bp.route("/schedules/<int:schedule_id>/apply", methods=["POST"])
def apply_generated_schedule(schedule_id):
    """Apply a generated schedule, creating actual shift records."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    try:
        shifts_created = apply_schedule(schedule_id)
        log_audit(
            "apply", "generated_schedule", schedule_id, details={"shifts_created": shifts_created}
        )
        return jsonify({"ok": True, "shifts_created": shifts_created})
    except ValueError as e:
        return make_response(jsonify({"error": str(e)}), 400)
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)


# =============================================================================
# SCHEDULE OVERRIDES
# =============================================================================


@scheduler_bp.route("/schedules/<int:schedule_id>/override", methods=["POST"])
def create_override(schedule_id):
    """Create a manual override for a generated schedule."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    schedule = db.session.get(GeneratedSchedule, schedule_id)
    if not schedule:
        return make_response(jsonify({"error": "schedule not found"}), 404)

    data = request.get_json() or {}

    shift_date = _parse_date(data.get("shift_date"))
    template_id = data.get("shift_template_id")

    if not shift_date or not template_id:
        return make_response(
            jsonify({"error": "shift_date and shift_template_id are required"}), 400
        )

    override = ScheduleOverride(
        schedule_id=schedule_id,
        shift_date=shift_date,
        shift_template_id=template_id,
        original_user_id=data.get("original_user_id"),
        new_user_id=data.get("new_user_id"),
        reason=data.get("reason", ""),
        applied_by=user.id,
    )
    db.session.add(override)
    db.session.flush()
    log_audit("create", "schedule_override", override.id, after=override.to_dict())
    db.session.commit()

    return make_response(jsonify(override.to_dict()), 201)


@scheduler_bp.route("/schedules/<int:schedule_id>/overrides", methods=["GET"])
def list_overrides(schedule_id):
    """List all overrides for a generated schedule."""
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    overrides = ScheduleOverride.query.filter_by(schedule_id=schedule_id).all()
    return jsonify([o.to_dict() for o in overrides])


# =============================================================================
# QUICK ACTIONS
# =============================================================================


@scheduler_bp.route("/quick-generate", methods=["POST"])
def quick_generate():
    """Create config and generate schedule in one call.

    ---
    tags:
        - Scheduler
    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    required: [start_date, end_date]
                    properties:
                        start_date: {type: string, format: date}
                        end_date: {type: string, format: date}
                        academic_period: {type: string, enum: [term, break]}
                        max_weekly_hours: {type: integer}
                        target_hours_per_week: {type: integer}
                        min_rest_hours: {type: integer}
                        max_consecutive_days: {type: integer}
    responses:
        200:
            description: Generated schedule payload
        400:
            description: Validation error
        403:
            description: Forbidden
        500:
            description: Generation failure
    """
    user, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json() or {}
    start = _parse_date(data.get("start_date"))
    end = _parse_date(data.get("end_date"))

    if not start or not end:
        return make_response(jsonify({"error": "start_date and end_date are required"}), 400)

    academic_period = data.get("academic_period", "term")
    max_hours = 20 if academic_period == "term" else 40

    existing_config = (
        ScheduleConfig.query.filter(ScheduleConfig.daily_staffing_requirements.isnot(None))
        .order_by(ScheduleConfig.id.desc())
        .first()
    )

    staffing_requirements = None
    if existing_config and existing_config.daily_staffing_requirements:
        staffing_requirements = existing_config.daily_staffing_requirements
        logger.info(
            f"Using staffing requirements from config {existing_config.id}: {staffing_requirements}"
        )

    config = ScheduleConfig(
        name=data.get("name", f"Schedule {start.isoformat()} to {end.isoformat()}"),
        start_date=start,
        end_date=end,
        academic_period=academic_period,
        max_weekly_hours=data.get("max_weekly_hours", max_hours),
        target_hours_per_week=data.get("target_hours_per_week", 18),
        min_rest_hours=data.get("min_rest_hours", 8),
        max_consecutive_days=data.get("max_consecutive_days", 5),
        shift_template_ids=json.dumps(data.get("shift_template_ids", [])),
        special_events=json.dumps(data.get("special_events", [])),
        daily_staffing_requirements=staffing_requirements,
        created_by=user.id,
    )
    db.session.add(config)
    db.session.commit()

    try:
        generated = generate_schedule(config.id)
        return jsonify(
            {"config": config.to_dict(), "schedule": generated.to_dict(include_data=True)}
        )
    except Exception as error:
        logger.error(f"QUICK_GENERATE ERROR: {type(error).__name__}: {error}", exc_info=True)
        return make_response(jsonify({"error": str(error), "type": type(error).__name__}), 500)


@scheduler_bp.route("/status", methods=["GET"])
def scheduler_status():
    """Check scheduler service status.

    ---
    tags:
      - Scheduler
    responses:
      200:
        description: Scheduler status and counts
    """
    try:
        import ortools.sat.python.cp_model as cp_model

        ortools_available = cp_model is not None
    except ImportError:
        ortools_available = False

    return jsonify(
        {
            "ortools_available": ortools_available,
            "templates_count": ShiftTemplate.query.filter_by(is_active=True).count(),
            "profiles_count": EmployeeProfile.query.count(),
            "pending_leave_requests": LeaveRequest.query.filter_by(status="pending").count(),
        }
    )
