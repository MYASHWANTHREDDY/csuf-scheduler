"""Conflict inspection API routes.

Prefix: /api/conflicts
"""

from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, make_response, request

try:
    from ..models import Availability, LeaveRequest, Shift, SwapRequest, User
    from ..utils.auth import require_auth as _require_auth
    from ..utils.availability import _availability_windows_from_records, is_available_from_windows
except (ImportError, ModuleNotFoundError):
    from models import Availability, LeaveRequest, Shift, SwapRequest, User
    from utils.auth import require_auth as _require_auth
    from utils.availability import _availability_windows_from_records, is_available_from_windows


conflicts_bp = Blueprint("conflicts", __name__, url_prefix="/api/conflicts")


def _parse_week_param(week_param: str):
    try:
        year_str, week_str = week_param.split("-W")
        year = int(year_str)
        week = int(week_str)
        # Interpret UI week values as Sunday-Saturday windows.
        # HTML week input is ISO-based; convert ISO Monday to prior Sunday.
        iso_monday = datetime.fromisocalendar(year, week, 1).date()
        start = iso_monday - timedelta(days=1)
        end = start + timedelta(days=6)
        return start, end
    except Exception:
        return None, None


def _duration_hours(shift):
    start_dt = datetime.combine(shift.date, shift.start_time)
    end_dt = datetime.combine(shift.date, shift.end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return (end_dt - start_dt).total_seconds() / 3600.0


def _shift_label(shift):
    return (
        f"Shift #{shift.id} {shift.date.isoformat()} "
        f"{shift.start_time.strftime('%H:%M')} - {shift.end_time.strftime('%H:%M')}"
    )


@conflicts_bp.route("", methods=["GET"])
def list_conflicts():
    """List scheduling conflicts for a week.

    ---
    tags:
      - Conflicts
    parameters:
      - in: query
        name: week
        required: true
        schema:
          type: string
        description: ISO week format `YYYY-Www`.
      - in: query
        name: max_weekly_hours
        schema:
          type: number
          format: float
        description: Optional weekly cap override.
    responses:
      200:
        description: Conflict analysis result
      400:
        description: Invalid or missing week parameter
      403:
        description: Forbidden
    """
    _, err = _require_auth({"admin", "supervisor"})
    if err:
        return err

    week = (request.args.get("week") or "").strip()
    max_weekly_hours = request.args.get("max_weekly_hours", type=float)
    if max_weekly_hours is None:
        max_weekly_hours = 20.0
    if not week:
        return make_response(
            jsonify({"error": "week query param is required (format YYYY-Www)"}), 400
        )

    week_start, week_end = _parse_week_param(week)
    if not week_start:
        return make_response(jsonify({"error": "invalid week format; use YYYY-Www"}), 400)

    shifts = (
        Shift.query.filter(
            Shift.assigned_user_id.isnot(None),
            Shift.date >= week_start,
            Shift.date <= week_end,
        )
        .order_by(Shift.assigned_user_id.asc(), Shift.date.asc(), Shift.start_time.asc())
        .all()
    )

    user_ids = sorted({shift.assigned_user_id for shift in shifts if shift.assigned_user_id})
    week_end_plus_one = week_end + timedelta(days=1)

    shift_ids = [shift.id for shift in shifts]
    swap_requests = (
        SwapRequest.query.filter(
            (SwapRequest.shift_id.in_(shift_ids)) | (SwapRequest.target_shift_id.in_(shift_ids))
        ).all()
        if shift_ids
        else []
    )
    swap_context = defaultdict(list)
    for swap in swap_requests:
        swap_context[swap.shift_id].append(swap)
        if swap.target_shift_id:
            swap_context[swap.target_shift_id].append(swap)

    availability_by_user = defaultdict(list)
    if user_ids:
        for availability in Availability.query.filter(Availability.user_id.in_(user_ids)).all():
            availability_by_user[availability.user_id].append(availability)

    leave_dates_by_user = defaultdict(set)
    if user_ids:
        leaves = LeaveRequest.query.filter(
            LeaveRequest.user_id.in_(user_ids),
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= week_end_plus_one,
            LeaveRequest.end_date >= week_start,
        ).all()
        for leave in leaves:
            current = max(leave.start_date, week_start)
            end = min(leave.end_date, week_end_plus_one)
            while current <= end:
                leave_dates_by_user[leave.user_id].add(current)
                current += timedelta(days=1)

    users_by_id = (
        {item.id: item for item in User.query.filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    availability_windows_cache = {}

    def windows_for(user_id, shift_date):
        key = (user_id, shift_date)
        if key not in availability_windows_cache:
            availability_windows_cache[key] = _availability_windows_from_records(
                availability_by_user.get(user_id, []), shift_date
            )
        return availability_windows_cache[key]

    conflicts = []

    for shift in shifts:
        next_day = shift.date + timedelta(days=1)
        user = users_by_id.get(shift.assigned_user_id)
        user_name = (
            user.name
            if user and user.name
            else (user.email if user else f"User {shift.assigned_user_id}")
        )
        shift_label = _shift_label(shift)
        ok, reason = is_available_from_windows(
            shift.date,
            shift.start_time,
            shift.end_time,
            windows_for(shift.assigned_user_id, shift.date),
            windows_for(shift.assigned_user_id, next_day),
            has_leave=shift.date in leave_dates_by_user.get(shift.assigned_user_id, set()),
            has_next_day_leave=next_day in leave_dates_by_user.get(shift.assigned_user_id, set()),
        )
        if not ok:
            related_swaps = swap_context.get(shift.id, [])
            related_swap_ids = [swap.id for swap in related_swaps]
            related_swap_statuses = sorted({swap.status for swap in related_swaps})
            conflicts.append(
                {
                    "type": "out_of_availability",
                    "user_id": shift.assigned_user_id,
                    "employee_name": user_name,
                    "shift_id": shift.id,
                    "shift_label": shift_label,
                    "date": shift.date.isoformat(),
                    "message": f"{user_name} on {shift_label} is not available. {reason}",
                    "related_swap_request_ids": related_swap_ids,
                    "related_swap_statuses": related_swap_statuses,
                }
            )

    by_user = {}
    for shift in shifts:
        by_user.setdefault(shift.assigned_user_id, []).append(shift)

    for uid, user_shifts in by_user.items():
        daily = {}
        for shift in user_shifts:
            daily.setdefault(shift.date, []).append(shift)
        for shift_date, day_shifts in daily.items():
            day_shifts.sort(key=lambda item: item.start_time)
            for index, first_shift in enumerate(day_shifts):
                for second_shift in day_shifts[index + 1 :]:
                    if (
                        first_shift.start_time < second_shift.end_time
                        and second_shift.start_time < first_shift.end_time
                    ):
                        conflicts.append(
                            {
                                "type": "overlap",
                                "user_id": uid,
                                "date": shift_date.isoformat(),
                                "shift_ids": [first_shift.id, second_shift.id],
                                "message": f"Overlapping shifts {first_shift.id} and {second_shift.id} for user {uid}",
                            }
                        )

    users_by_id = (
        {item.id: item for item in User.query.filter(User.id.in_(by_user.keys())).all()}
        if by_user
        else {}
    )
    for uid, user_shifts in by_user.items():
        total = sum(_duration_hours(shift) for shift in user_shifts)
        user = users_by_id.get(uid)
        effective_cap = max_weekly_hours if (not user or user.role != "admin") else float("inf")
        if total > effective_cap:
            conflicts.append(
                {
                    "type": "hour_cap",
                    "user_id": uid,
                    "week": week,
                    "hours": round(total, 2),
                    "cap": effective_cap,
                    "message": f"User {uid} assigned {total:.2f}h > cap {effective_cap:.2f}h",
                }
            )

    return jsonify(
        {
            "week": week,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "count": len(conflicts),
            "items": conflicts,
        }
    )
