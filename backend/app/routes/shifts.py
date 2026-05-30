"""Shift API routes.
Prefix: /api/shifts

GET  /api/shifts          -> list shifts
POST /api/shifts          -> create shift
POST /api/shifts/assign   -> assign a user to a shift
"""

from flask import Blueprint, jsonify, make_response, request
from pydantic import ValidationError
from sqlalchemy import or_

try:
    from ..database import db
    from ..models import Shift, User
    from ..utils.audit import log_audit
    from ..utils.auth import require_role as _require_role
    from ..utils.availability import is_available_for_shift
    from ..utils.parsers import parse_date as _parse_date
    from ..utils.parsers import parse_time as _parse_time
    from ..utils.schemas import AssignShiftRequest, CreateShiftRequest
except Exception:
    from database import db
    from models import Shift, User
    from utils.audit import log_audit
    from utils.auth import require_role as _require_role
    from utils.availability import is_available_for_shift
    from utils.parsers import parse_date as _parse_date
    from utils.parsers import parse_time as _parse_time
    from utils.schemas import AssignShiftRequest, CreateShiftRequest

shifts_bp = Blueprint("shifts", __name__, url_prefix="/api/shifts")


@shifts_bp.route("", methods=["GET"])
def list_shifts():
    """Return list of shifts visible to the current user.

    Query params:
    - scope: ``all`` to bypass user scoping for managers.
    - date_from/date_to: date filters in ``YYYY-MM-DD``.
    - status: ``assigned`` or ``unassigned``.
    - assigned_user_id: exact assignee filter.
    - q: search assignee name/email.
    - page/per_page: optional pagination when either is provided.
    """
    user, err = _require_role(None)
    if err:
        return err

    manager_roles = {"admin", "supervisor", "FTO"}
    scope = request.args.get("scope", "").lower()
    query = Shift.query
    if scope != "all" and user.role not in manager_roles:
        query = query.filter(Shift.assigned_user_id == user.id)
    if user.role == "FTO" and scope != "all":
        query = query.filter(Shift.assigned_user_id == user.id)

    # For non-managers, show a rolling 6-week history window plus upcoming shifts
    if scope != "all" and user.role not in manager_roles:
        from datetime import date, timedelta

        today = date.today()
        history_start = today - timedelta(weeks=6)
        query = query.filter(Shift.date >= history_start)

    date_from = request.args.get("date_from", "").strip()
    if date_from:
        parsed_from = _parse_date(date_from)
        if not parsed_from:
            return make_response(jsonify({"error": "date_from must be YYYY-MM-DD"}), 400)
        query = query.filter(Shift.date >= parsed_from)

    date_to = request.args.get("date_to", "").strip()
    if date_to:
        parsed_to = _parse_date(date_to)
        if not parsed_to:
            return make_response(jsonify({"error": "date_to must be YYYY-MM-DD"}), 400)
        query = query.filter(Shift.date <= parsed_to)

    status = request.args.get("status", "").strip().lower()
    if status == "assigned":
        query = query.filter(Shift.assigned_user_id.isnot(None))
    elif status == "unassigned":
        query = query.filter(Shift.assigned_user_id.is_(None))
    elif status:
        return make_response(jsonify({"error": "status must be assigned or unassigned"}), 400)

    assigned_user_id = request.args.get("assigned_user_id", type=int)
    if assigned_user_id is not None:
        query = query.filter(Shift.assigned_user_id == assigned_user_id)

    search_text = request.args.get("q", "").strip()
    if search_text:
        like_pattern = f"%{search_text}%"
        query = query.outerjoin(User, Shift.assigned_user_id == User.id).filter(
            or_(
                User.email.ilike(like_pattern),
                User.first_name.ilike(like_pattern),
                User.last_name.ilike(like_pattern),
                User.name.ilike(like_pattern),
            )
        )

    ordered_query = query.order_by(Shift.date, Shift.start_time)

    def fmt(s):
        return {
            "id": s.id,
            "date": s.date.isoformat(),
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "assigned_user_id": s.assigned_user_id,
        }

    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)
    if page is not None or per_page is not None:
        page = max(page or 1, 1)
        per_page = min(max(per_page or 25, 1), 100)
        paginated = ordered_query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify(
            {
                "items": [fmt(s) for s in paginated.items],
                "page": page,
                "per_page": per_page,
                "total": paginated.total,
                "pages": paginated.pages,
            }
        )

    shifts = ordered_query.all()
    return jsonify([fmt(s) for s in shifts])


@shifts_bp.route("", methods=["POST"])
def create_shift():
    """Create a new shift from JSON { date, start_time, end_time }.

        ---
        tags:
            - Shifts
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        type: object
                        required: [date, start_time, end_time]
                        properties:
                            date: {type: string, format: date}
                            start_time: {type: string, example: "06:30"}
                            end_time: {type: string, example: "12:30"}
        responses:
            201:
                description: Shift created
            400:
                description: Validation error
            403:
                description: Forbidden

    Date must be YYYY-MM-DD; times HH:MM.
    """
    _, err = _require_role({"admin", "supervisor"})
    if err:
        return err
    data = request.get_json() or {}
    try:
        payload = CreateShiftRequest.model_validate(data)
    except ValidationError as exc:
        return make_response(jsonify({"error": exc.errors()}), 400)

    d = _parse_date(payload.date)
    st = _parse_time(payload.start_time)
    et = _parse_time(payload.end_time)

    if not d or not st or not et:
        return make_response(
            jsonify(
                {
                    "error": "date (YYYY-MM-DD), start_time and end_time (HH:MM) are required and must be correctly formatted"
                }
            ),
            400,
        )

    # Allow overnight shifts (e.g., 18:30 to 00:30 next day)
    # Validation: just ensure times are valid, don't enforce end > start
    # since end_time can be earlier if shift crosses midnight

    shift = Shift(date=d, start_time=st, end_time=et)
    db.session.add(shift)
    db.session.flush()
    log_audit("create", "shift", shift.id, after=shift.to_dict())
    db.session.commit()

    return make_response(jsonify({"id": shift.id}), 201)


@shifts_bp.route("/assign", methods=["POST"])
def assign_shift():
    """Assign a user to a shift.

    ---
    tags:
      - Shifts
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [shift_id, user_id]
            properties:
              shift_id: {type: integer}
              user_id: {type: integer}
    responses:
      200:
        description: Shift assigned
      400:
        description: Validation error
      404:
        description: Shift or user not found
      409:
        description: Availability or conflict issue
    """
    _, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json() or {}
    try:
        payload = AssignShiftRequest.model_validate(data)
    except ValidationError as exc:
        return make_response(jsonify({"error": exc.errors()}), 400)

    shift_id = payload.shift_id
    user_id = payload.user_id

    shift = db.session.get(Shift, shift_id)
    user = db.session.get(User, user_id)

    if not shift:
        return make_response(jsonify({"error": "shift not found"}), 404)
    if not user:
        return make_response(jsonify({"error": "user not found"}), 404)

    is_available, reason = is_available_for_shift(
        user.id, shift.date, shift.start_time, shift.end_time
    )
    if not is_available:
        return make_response(jsonify({"error": f"Cannot assign shift: {reason}"}), 409)

    conflicting_shifts = Shift.query.filter(
        Shift.assigned_user_id == user.id,
        Shift.date == shift.date,
        Shift.id != shift.id,
    ).all()

    for existing_shift in conflicting_shifts:
        if (
            shift.start_time < existing_shift.end_time
            and existing_shift.start_time < shift.end_time
        ):
            return make_response(
                jsonify(
                    {
                        "error": f'User {user.name or user.email} already has a conflicting shift on {shift.date} from {existing_shift.start_time.strftime("%H:%M")} to {existing_shift.end_time.strftime("%H:%M")}'
                    }
                ),
                409,
            )

    before = shift.to_dict()
    shift.assigned_user_id = user.id
    log_audit(
        "assign",
        "shift",
        shift.id,
        before=before,
        after=shift.to_dict(),
        details={"assigned_user_id": user.id},
    )
    db.session.commit()

    return jsonify({"ok": True})


@shifts_bp.route("/auto-assign", methods=["POST"])
def auto_assign_shifts():
    """Naively assign unassigned shifts round-robin across student users.

    Returns JSON { assigned: <count>, total_unassigned: <count> }.
    """
    # Require authenticated user with sufficient role
    _, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    # Find students (non-admin users)
    students = User.query.filter(User.role != "admin").order_by(User.id).all()
    if not students:
        return make_response(jsonify({"error": "no students available to assign"}), 400)

    unassigned = (
        Shift.query.filter(Shift.assigned_user_id.is_(None))
        .order_by(Shift.date, Shift.start_time)
        .all()
    )
    total = len(unassigned)
    if total == 0:
        return jsonify({"assigned": 0, "total_unassigned": 0})

    # Round-robin assignment with availability validation
    assigned = 0
    si = 0
    for shift in unassigned:
        # Try to find a student with availability
        attempts = 0
        while attempts < len(students):
            student = students[si % len(students)]
            is_available, _ = is_available_for_shift(
                student.id, shift.date, shift.start_time, shift.end_time
            )

            if is_available:
                # Also check for conflicting shifts
                conflicting = Shift.query.filter(
                    Shift.assigned_user_id == student.id,
                    Shift.date == shift.date,
                    Shift.id != shift.id,
                ).all()

                has_conflict = False
                for existing_shift in conflicting:
                    if (
                        shift.start_time < existing_shift.end_time
                        and existing_shift.start_time < shift.end_time
                    ):
                        has_conflict = True
                        break

                if not has_conflict:
                    shift.assigned_user_id = student.id
                    assigned += 1
                    si += 1
                    break

            si += 1
            attempts += 1

    db.session.commit()
    return jsonify({"assigned": assigned, "total_unassigned": total})


@shifts_bp.route("/by-user/<int:user_id>", methods=["GET"])
def get_shifts_by_user(user_id):
    """Get all shifts assigned to a specific user. Requires admin/supervisor role."""
    _, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    shifts = Shift.query.filter_by(assigned_user_id=user_id).all()
    data = [
        {
            "id": s.id,
            "date": s.date.isoformat(),
            "start_time": (
                s.start_time.isoformat() if isinstance(s.start_time, object) else str(s.start_time)
            ),
            "end_time": (
                s.end_time.isoformat() if isinstance(s.end_time, object) else str(s.end_time)
            ),
            "assigned_user_id": s.assigned_user_id,
        }
        for s in shifts
    ]
    return jsonify(data)


@shifts_bp.route("/swap", methods=["POST"])
def swap_shifts():
    """Swap assignments between two shifts. Requires admin/supervisor role."""
    _, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json()
    shift_id_1 = data.get("shift_id_1")
    shift_id_2 = data.get("shift_id_2")

    if not shift_id_1 or not shift_id_2:
        return make_response(jsonify({"error": "both shift IDs are required"}), 400)

    shift1 = db.session.get(Shift, shift_id_1)
    shift2 = db.session.get(Shift, shift_id_2)

    if not shift1 or not shift2:
        return make_response(jsonify({"error": "one or both shifts not found"}), 404)

    # Swap the assignments
    before_1 = shift1.to_dict()
    before_2 = shift2.to_dict()
    shift1.assigned_user_id, shift2.assigned_user_id = (
        shift2.assigned_user_id,
        shift1.assigned_user_id,
    )
    log_audit(
        "swap",
        "shift",
        shift1.id,
        before=before_1,
        after=shift1.to_dict(),
        details={"other_shift_id": shift2.id},
    )
    log_audit(
        "swap",
        "shift",
        shift2.id,
        before=before_2,
        after=shift2.to_dict(),
        details={"other_shift_id": shift1.id},
    )
    db.session.commit()

    return jsonify({"success": True, "message": "Shifts swapped successfully"})


@shifts_bp.route("/<int:shift_id>", methods=["DELETE"])
def delete_shift(shift_id):
    """Delete a shift. Only non-student roles may delete shifts."""
    _, err = _require_role({"admin", "supervisor"})
    if err:
        return err

    shift = db.session.get(Shift, shift_id)
    if not shift:
        return make_response(jsonify({"error": "shift not found"}), 404)

    # Remove any dependent records first
    try:
        from ..models import CallOffRequest, SwapRequest, TimeAdjustmentRequest, TimesheetLine
    except Exception:
        from models import CallOffRequest, SwapRequest, TimeAdjustmentRequest, TimesheetLine

    SwapRequest.query.filter_by(shift_id=shift.id).delete()
    CallOffRequest.query.filter_by(shift_id=shift.id).delete()
    TimeAdjustmentRequest.query.filter_by(shift_id=shift.id).delete()
    for line in TimesheetLine.query.filter_by(shift_id=shift.id).all():
        line.shift_id = None

    before = shift.to_dict()
    db.session.delete(shift)
    log_audit("delete", "shift", shift_id, before=before)
    db.session.commit()
    return jsonify({"ok": True})
