"""Extra routes: availability, swap requests, and announcements."""

from flask import Blueprint, jsonify, make_response, request
from sqlalchemy import or_

try:
    from ..database import db
    from ..models import (
        Announcement,
        Availability,
        AvailabilityRequest,
        CallOffRequest,
        Notification,
        Shift,
        SwapRequest,
        User,
    )
    from ..utils.audit import log_audit
    from ..utils.auth import require_auth as _require_auth
except (ImportError, ModuleNotFoundError):
    from database import db
    from models import (
        Availability,
        SwapRequest,
        Announcement,
        Shift,
        User,
        AvailabilityRequest,
        CallOffRequest,
        Notification,
    )
    from utils.auth import require_auth as _require_auth
    from utils.audit import log_audit

from datetime import datetime, timedelta

extras_bp = Blueprint("extras", __name__, url_prefix="/api")


def _notify_users(user_ids, message, category="swap"):
    user_ids = {uid for uid in (user_ids or []) if uid}
    for uid in user_ids:
        notif = Notification(user_id=uid, message=message, category=category)
        db.session.add(notif)


def _notify_supervisors(message, category="swap"):
    supervisors = User.query.filter(User.role.in_(["supervisor", "admin"])).all()
    _notify_users([u.id for u in supervisors], message, category)


def _shift_label(shift):
    if not shift:
        return "unknown shift"
    return f"{shift.date} {shift.start_time}-{shift.end_time}"


@extras_bp.route("/availability", methods=["GET"])
def list_availability():
    # optional query ?user_id= or current user
    user_id = request.args.get("user_id")
    if not user_id:
        # if not provided, return current user's availability
        user, err = _require_auth()
        if err:
            return err
        user_id = user.id
    else:
        # if requesting another user's availability, require supervisor/admin/FTO
        user, err = _require_auth({"supervisor", "admin", "FTO"})
        if err:
            return err
    avs = Availability.query.filter_by(user_id=user_id).order_by(Availability.date).all()
    return jsonify([a.to_dict() for a in avs])


@extras_bp.route("/availability", methods=["POST"])
def create_availability():
    user, err = _require_auth()
    if err:
        return err
    data = request.get_json() or {}

    is_recurring = data.get("is_recurring", False)
    st = data.get("start_time")
    et = data.get("end_time")

    if not st or not et:
        return make_response(jsonify({"error": "start_time and end_time are required"}), 400)

    try:
        start_time = datetime.strptime(st, "%H:%M").time()
        # Handle special "23:59" as end of day - convert to actual time(23, 59)
        if et == "23:59":
            end_time = datetime.strptime("23:59", "%H:%M").time()
        else:
            end_time = datetime.strptime(et, "%H:%M").time()
    except (ValueError, TypeError):
        return make_response(jsonify({"error": "invalid time format"}), 400)

    # Allow 23:59 as end time (represents end of day)
    if end_time < start_time and end_time.hour == 23 and end_time.minute == 59:
        # Special case: 23:59 is allowed as end time for all start times
        pass
    elif end_time <= start_time:
        return make_response(jsonify({"error": "end_time must be after start_time"}), 400)

    if is_recurring:
        # Recurring weekly availability
        day_of_week = data.get("day_of_week")
        effective_until_s = data.get("effective_until")
        shift_preference = data.get("shift_preference")

        if day_of_week is None:
            return make_response(
                jsonify(
                    {
                        "error": "day_of_week is required for recurring availability (0=Monday, 6=Sunday)"
                    }
                ),
                400,
            )

        if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
            return make_response(
                jsonify(
                    {"error": "day_of_week must be an integer between 0 (Monday) and 6 (Sunday)"}
                ),
                400,
            )

        effective_until = None
        if effective_until_s:
            try:
                effective_until = datetime.strptime(effective_until_s, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return make_response(jsonify({"error": "invalid effective_until date format"}), 400)

        try:
            a = Availability(
                user_id=user.id,
                start_time=start_time,
                end_time=end_time,
                is_recurring=True,
                day_of_week=day_of_week,
                effective_until=effective_until,
                shift_preference=shift_preference,
            )
        except Exception as e:
            return make_response(jsonify({"error": str(e)}), 500)
    else:
        # One-time availability
        date_s = data.get("date")
        shift_preference = data.get("shift_preference")
        if not date_s:
            return make_response(
                jsonify({"error": "date is required for one-time availability"}), 400
            )

        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return make_response(jsonify({"error": "invalid date/time format"}), 400)

        a = Availability(
            user_id=user.id,
            date=d,
            start_time=start_time,
            end_time=end_time,
            is_recurring=False,
            shift_preference=shift_preference,
        )

    try:
        db.session.add(a)
        db.session.flush()
        log_audit("create", "availability", a.id, after=a.to_dict())
        db.session.commit()
        return make_response(jsonify({"id": a.id}), 201)
    except Exception as e:
        db.session.rollback()
        return make_response(jsonify({"error": str(e)}), 500)


@extras_bp.route("/availability/<int:avail_id>", methods=["PUT"])
def update_availability(avail_id):
    """Update an existing availability block. User can only edit their own."""
    user, err = _require_auth()
    if err:
        return err
    a = db.session.get(Availability, avail_id)
    if not a:
        return make_response(jsonify({"error": "availability not found"}), 404)
    # Only owner or admin can edit
    if a.user_id != user.id and user.role not in ("admin", "supervisor"):
        return make_response(
            jsonify({"error": "forbidden: can only edit your own availability"}), 403
        )

    data = request.get_json() or {}
    is_recurring = data.get("is_recurring", a.is_recurring)
    st = data.get("start_time")
    et = data.get("end_time")

    if not st or not et:
        return make_response(jsonify({"error": "start_time and end_time are required"}), 400)

    try:
        start_time = datetime.strptime(st, "%H:%M").time()
        end_time = datetime.strptime(et, "%H:%M").time()
    except (ValueError, TypeError):
        return make_response(jsonify({"error": "invalid time format"}), 400)

    if datetime.combine(datetime.today(), end_time) <= datetime.combine(
        datetime.today(), start_time
    ):
        return make_response(jsonify({"error": "end_time must be after start_time"}), 400)

    a.start_time = start_time
    a.end_time = end_time
    a.is_recurring = is_recurring

    if is_recurring:
        day_of_week = data.get("day_of_week")
        if day_of_week is None:
            return make_response(
                jsonify({"error": "day_of_week is required for recurring availability"}), 400
            )
        if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
            return make_response(jsonify({"error": "day_of_week must be between 0-6"}), 400)

        a.day_of_week = day_of_week
        a.date = None  # Clear date for recurring

        effective_until_s = data.get("effective_until")
        if effective_until_s:
            try:
                a.effective_until = datetime.strptime(effective_until_s, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return make_response(jsonify({"error": "invalid effective_until format"}), 400)
    else:
        date_s = data.get("date")
        if not date_s:
            return make_response(
                jsonify({"error": "date is required for one-time availability"}), 400
            )
        try:
            a.date = datetime.strptime(date_s, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return make_response(jsonify({"error": "invalid date format"}), 400)

        a.day_of_week = None  # Clear day_of_week for one-time
        a.effective_until = None

    log_audit("update", "availability", a.id, before={"id": a.id}, after=a.to_dict())
    db.session.commit()
    return jsonify({"ok": True})


@extras_bp.route("/availability/<int:avail_id>", methods=["DELETE"])
def delete_availability(avail_id):
    """Delete an availability block. User can only delete their own."""
    user, err = _require_auth()
    if err:
        return err
    a = db.session.get(Availability, avail_id)
    if not a:
        return make_response(jsonify({"error": "availability not found"}), 404)
    # Only owner or admin can delete
    if a.user_id != user.id and user.role not in ("admin", "supervisor"):
        return make_response(
            jsonify({"error": "forbidden: can only delete your own availability"}), 403
        )

    before = a.to_dict()
    db.session.delete(a)
    log_audit("delete", "availability", avail_id, before=before)
    db.session.commit()
    return jsonify({"ok": True})


@extras_bp.route("/announcements", methods=["GET"])
def list_announcements():
    anns = Announcement.query.order_by(Announcement.created_at.desc()).limit(50).all()
    return jsonify([a.to_dict() for a in anns])


@extras_bp.route("/announcements", methods=["POST"])
def post_announcement():
    # only supervisors/admins can post
    user, err = _require_auth()
    if err:
        return err
    if user.role not in ("supervisor", "admin"):
        return make_response(jsonify({"error": "forbidden: insufficient role"}), 403)
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return make_response(jsonify({"error": "message is required"}), 400)
    ann = Announcement(author_id=user.id, message=message)
    db.session.add(ann)
    db.session.flush()
    log_audit("create", "announcement", ann.id, after=ann.to_dict())
    db.session.commit()
    return make_response(jsonify({"id": ann.id}), 201)


@extras_bp.route("/announcements/<int:aid>", methods=["DELETE"])
def delete_announcement(aid: int):
    """Delete an announcement. Only supervisors/admins can delete."""
    user, err = _require_auth()
    if err:
        return err
    if user.role not in ("supervisor", "admin"):
        return make_response(jsonify({"error": "forbidden: insufficient role"}), 403)
    ann = db.session.get(Announcement, aid)
    if not ann:
        return make_response(jsonify({"error": "announcement not found"}), 404)
    before = ann.to_dict()
    db.session.delete(ann)
    log_audit("delete", "announcement", aid, before=before)
    db.session.commit()
    return jsonify({"ok": True})


@extras_bp.route("/swap_requests", methods=["GET"])
def list_swap_requests():
    user, err = _require_auth()
    if err:
        return err
    if user.role in ("supervisor", "admin"):
        q = SwapRequest.query.order_by(SwapRequest.created_at.desc())
    else:
        q = SwapRequest.query.filter(
            or_(SwapRequest.requester_id == user.id, SwapRequest.target_user_id == user.id)
        ).order_by(SwapRequest.created_at.desc())
    items = q.all()
    return jsonify([s.to_dict() for s in items])


@extras_bp.route("/swap_requests", methods=["POST"])
def create_swap_request():
    user, err = _require_auth()
    if err:
        return err
    data = request.get_json() or {}
    shift_id = data.get("shift_id")
    target_shift_id = data.get("target_shift_id")

    if not shift_id:
        return make_response(jsonify({"error": "shift_id is required"}), 400)

    shift = db.session.get(Shift, shift_id)
    if not shift:
        return make_response(jsonify({"error": "shift not found"}), 404)

    # User must be assigned to the shift they want to swap
    if shift.assigned_user_id != user.id:
        return make_response(
            jsonify({"error": "only assigned user can request swap for this shift"}), 403
        )

    # Handle both simple and complex swap requests
    target_user_id = None
    if target_shift_id:
        # Complex swap: validate target shift
        target_shift = db.session.get(Shift, target_shift_id)
        if not target_shift:
            return make_response(jsonify({"error": "target shift not found"}), 404)
        if shift_id == target_shift_id:
            return make_response(jsonify({"error": "cannot swap a shift with itself"}), 400)
        if not target_shift.assigned_user_id or target_shift.assigned_user_id == user.id:
            return make_response(
                jsonify({"error": "target shift must be assigned to another user"}), 400
            )
        target_user_id = target_shift.assigned_user_id

    # Create swap request
    sr = SwapRequest(
        shift_id=shift.id,
        target_shift_id=target_shift_id,
        requester_id=user.id,
        target_user_id=target_user_id,
        status="requested",
    )
    db.session.add(sr)
    db.session.flush()
    log_audit("create", "swap_request", sr.id, after=sr.to_dict())

    if target_shift_id:
        # Complex swap: notify target user
        message = f"{user.name or user.email} requested to swap {_shift_label(shift)} with your shift {_shift_label(target_shift)}."
        _notify_users([target_user_id], message)
    else:
        # Simple swap: notify supervisors
        message = f"{user.name or user.email} requested to swap {_shift_label(shift)}."
        _notify_supervisors(message)

    db.session.commit()
    return make_response(jsonify({"id": sr.id}), 201)


@extras_bp.route("/swap_requests/<int:rid>/respond", methods=["POST"])
def respond_swap_request(rid):
    user, err = _require_auth()
    if err:
        return err
    sr = db.session.get(SwapRequest, rid)
    if not sr:
        return make_response(jsonify({"error": "swap request not found"}), 404)
    if sr.target_user_id != user.id:
        return make_response(
            jsonify({"error": "only the target user can respond to this request"}), 403
        )
    data = request.get_json() or {}
    action = (data.get("action") or "").lower()
    if action not in ("accept", "decline"):
        return make_response(jsonify({"error": "action must be accept or decline"}), 400)
    if action == "accept":
        if sr.status != "requested":
            return make_response(jsonify({"error": "swap request is not awaiting acceptance"}), 409)
        sr.status = "target_accepted"
        db.session.add(sr)
        _notify_supervisors(
            f"{user.name or user.email} accepted swap request #{sr.id} ({ _shift_label(sr.shift) } <-> { _shift_label(sr.target_shift) })."
        )
    else:
        reason = (data.get("reason") or "").strip()
        sr.status = "denied"
        msg = f"{user.name or user.email} declined swap request #{sr.id} ({ _shift_label(sr.shift) } <-> { _shift_label(sr.target_shift) })."
        if reason:
            msg += f" Reason: {reason}"
        _notify_users([sr.requester_id], msg)
    log_audit("update", "swap_request", sr.id, details={"action": action, "status": sr.status})
    db.session.commit()
    return jsonify({"ok": True})


@extras_bp.route("/swap_requests/<int:rid>/decide", methods=["POST"])
def decide_swap_request(rid):
    user, err = _require_auth()
    if err:
        return err
    if user.role not in ("supervisor", "admin"):
        return make_response(jsonify({"error": "forbidden: insufficient role"}), 403)
    sr = db.session.get(SwapRequest, rid)
    if not sr:
        return make_response(jsonify({"error": "swap request not found"}), 404)

    # Simple swap (no target specified): can approve from 'requested' status
    # Complex swap: requires 'target_accepted' status
    is_simple_swap = sr.target_shift_id is None or sr.target_user_id is None
    if not is_simple_swap and sr.status != "target_accepted":
        return make_response(
            jsonify({"error": "swap request is not ready for supervisor approval"}), 409
        )
    if is_simple_swap and sr.status != "requested":
        return make_response(
            jsonify({"error": "swap request is not awaiting supervisor decision"}), 409
        )

    data = request.get_json() or {}
    action = (data.get("action") or "").lower()
    if action not in ("approve", "deny"):
        return make_response(jsonify({"error": "action must be approve or deny"}), 400)
    reason = (data.get("reason") or "").strip()

    if action == "approve":
        # For simple swaps, just mark as approved without complex shift validation
        if is_simple_swap:
            sr.status = "approved"
            requester_name = sr.requester.name or sr.requester.email
            message = f"Supervisor approved swap request #{sr.id} for {requester_name} to swap {_shift_label(sr.shift)}."
            _notify_users([sr.requester_id], message)
        else:
            # Complex swap: validate and swap assignments
            requester_shift = sr.shift
            target_shift = sr.target_shift
            requester_name = (
                (sr.requester.name or sr.requester.email)
                if sr.requester
                else f"User {sr.requester_id}"
            )
            target_name = (
                (sr.target_user.name or sr.target_user.email)
                if sr.target_user
                else f"User {sr.target_user_id}"
            )

            if not requester_shift or not target_shift:
                return make_response(jsonify({"error": "shift data missing"}), 500)
            if target_shift.assigned_user_id != sr.target_user_id:
                return make_response(jsonify({"error": "target shift assignment changed"}), 409)

            # Check weekly hours constraint (students limited to 20 hours/week)
            def shift_duration_hours(s):
                if not s:
                    return 0
                start_dt = datetime.combine(s.date, s.start_time)
                end_dt = datetime.combine(s.date, s.end_time)
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                return (end_dt - start_dt).total_seconds() / 3600.0

            def week_bounds_for(d):
                # week starting Monday
                start = d - timedelta(days=d.weekday())
                end = start + timedelta(days=6)
                return start, end

            # compute week range based on the requester shift's date and target shift's date
            weeks = set()
            weeks.add(week_bounds_for(requester_shift.date))
            weeks.add(week_bounds_for(target_shift.date))

            def total_hours_for(user_id, week_start, week_end, exclude_shift_id=None):
                q = Shift.query.filter(
                    Shift.assigned_user_id == user_id,
                    Shift.date >= week_start,
                    Shift.date <= week_end,
                )
                if exclude_shift_id:
                    q = q.filter(Shift.id != exclude_shift_id)
                return sum(shift_duration_hours(s) for s in q.all())

            # For each affected week, check constraints
            for week_start, week_end in weeks:
                requester_base_hours = total_hours_for(
                    sr.requester_id, week_start, week_end, exclude_shift_id=requester_shift.id
                )
                target_base_hours = total_hours_for(
                    sr.target_user_id, week_start, week_end, exclude_shift_id=target_shift.id
                )

                requester_new_hours = requester_base_hours + shift_duration_hours(target_shift)
                target_new_hours = target_base_hours + shift_duration_hours(requester_shift)

                # Only check if either user is a student
                if sr.requester.role == "student" and requester_new_hours > 20:
                    return make_response(
                        jsonify(
                            {
                                "error": f"Swap would exceed 20-hour limit for {requester_name} in week of {week_start.date()}"
                            }
                        ),
                        400,
                    )
                if sr.target_user and sr.target_user.role == "student" and target_new_hours > 20:
                    return make_response(
                        jsonify(
                            {
                                "error": f"Swap would exceed 20-hour limit for {target_name} in week of {week_start.date()}"
                            }
                        ),
                        400,
                    )

            # Perform the swap
            requester_shift.assigned_user_id = sr.target_user_id
            target_shift.assigned_user_id = sr.requester_id
            sr.status = "approved"

            message = (
                f"Supervisor approved swap #{sr.id}. { _shift_label(requester_shift) } is now assigned to {target_name}, "
                f"{ _shift_label(target_shift) } is now assigned to {requester_name}."
            )
            _notify_users([sr.requester_id, sr.target_user_id], message)
    else:
        sr.status = "denied"
        requester_name = sr.requester.name or sr.requester.email
        if is_simple_swap:
            msg = f"Supervisor denied swap request #{sr.id} for {requester_name} to swap {_shift_label(sr.shift)}."
        else:
            target_shift = sr.target_shift
            requester_shift = sr.shift
            requester_name = (
                (sr.requester.name or sr.requester.email)
                if sr.requester
                else f"User {sr.requester_id}"
            )
            target_name = (
                (sr.target_user.name or sr.target_user.email)
                if sr.target_user
                else f"User {sr.target_user_id}"
            )
            msg = f"Supervisor denied swap #{sr.id} ({ _shift_label(requester_shift) } <-> { _shift_label(target_shift) }) requested by {requester_name} for {target_name}."
        if reason:
            msg += f" Reason: {reason}"
        _notify_users(
            (
                [sr.requester_id]
                if sr.target_user_id is None
                else [sr.requester_id, sr.target_user_id]
            ),
            msg,
        )

    log_audit(
        "update",
        "swap_request",
        sr.id,
        details={"action": action, "status": sr.status, "reason": reason},
    )
    db.session.commit()
    return jsonify({"ok": True})


@extras_bp.route("/notifications", methods=["GET"])
def list_notifications():
    user, err = _require_auth()
    if err:
        return err
    items = (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify([n.to_dict() for n in items])


@extras_bp.route("/notifications/<int:nid>/seen", methods=["POST"])
def mark_notification_seen(nid):
    user, err = _require_auth()
    if err:
        return err
    notif = db.session.get(Notification, nid)
    if not notif or notif.user_id != user.id:
        return make_response(jsonify({"error": "notification not found"}), 404)
    notif.seen = True
    db.session.commit()
    return jsonify({"ok": True})


# Call-off requests
@extras_bp.route("/call_off", methods=["POST"])
def create_call_off():
    """Employee or FTO calls off an assigned shift."""
    user, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    shift_id = data.get("shift_id")
    reason = (data.get("reason") or "").strip()

    if not shift_id:
        return make_response(jsonify({"error": "shift_id is required"}), 400)

    shift = db.session.get(Shift, shift_id)
    if not shift:
        return make_response(jsonify({"error": "shift not found"}), 404)

    # Only the assigned user, supervisor, admin, or FTO can call off
    if shift.assigned_user_id != user.id and user.role not in ("supervisor", "admin", "FTO"):
        return make_response(
            jsonify(
                {"error": "forbidden: only assigned user, supervisor, admin, or FTO can call off"}
            ),
            403,
        )

    calloff = CallOffRequest(
        shift_id=shift.id, requester_id=user.id, reason=reason, status="submitted"
    )
    db.session.add(calloff)
    db.session.commit()
    return make_response(jsonify({"id": calloff.id}), 201)


@extras_bp.route("/call_off", methods=["GET"])
def list_call_offs():
    """Managers and FTOs see all call-offs; employees see their own."""
    user, err = _require_auth()
    if err:
        return err

    if user.role in ("supervisor", "admin", "FTO"):
        reqs = CallOffRequest.query.order_by(CallOffRequest.created_at.desc()).all()
    else:
        reqs = (
            CallOffRequest.query.filter_by(requester_id=user.id)
            .order_by(CallOffRequest.created_at.desc())
            .all()
        )

    return jsonify([r.to_dict() for r in reqs])


@extras_bp.route("/availability_requests", methods=["GET"])
def list_availability_requests():
    """List availability requests. Employees see their own, supervisors see all."""
    user, err = _require_auth()
    if err:
        return err

    if user.role in ("supervisor", "admin", "FTO"):
        # Supervisors see all active requests
        reqs = (
            AvailabilityRequest.query.filter_by(status="active")
            .order_by(AvailabilityRequest.created_at.desc())
            .all()
        )
    else:
        # Employees see their own active requests
        reqs = AvailabilityRequest.query.filter_by(user_id=user.id, status="active").all()

    return jsonify([r.to_dict() for r in reqs])


@extras_bp.route("/availability_requests", methods=["POST"])
def create_availability_request():
    """Supervisor creates a request for an employee to submit availability."""
    user, err = _require_auth({"supervisor", "admin", "FTO"})
    if err:
        return err

    data = request.get_json() or {}
    employee_id = data.get("user_id")

    if not employee_id:
        return make_response(jsonify({"error": "user_id is required"}), 400)

    employee = db.session.get(User, employee_id)
    if not employee:
        return make_response(jsonify({"error": "user not found"}), 404)

    # Check if there's already an active request for this employee
    existing = AvailabilityRequest.query.filter_by(user_id=employee_id, status="active").first()
    if existing:
        return make_response(
            jsonify({"error": "active availability request already exists for this user"}), 400
        )

    req = AvailabilityRequest(user_id=employee_id, requested_by=user.id, status="active")
    db.session.add(req)
    db.session.flush()
    log_audit("create", "availability_request", req.id, after=req.to_dict())
    db.session.commit()

    return make_response(jsonify({"id": req.id}), 201)


@extras_bp.route("/availability_requests/<int:req_id>", methods=["DELETE"])
def cancel_availability_request(req_id):
    """Cancel/close an availability request."""
    user, err = _require_auth({"supervisor", "admin", "FTO"})
    if err:
        return err

    req = db.session.get(AvailabilityRequest, req_id)
    if not req:
        return make_response(jsonify({"error": "availability request not found"}), 404)

    before = req.to_dict()
    req.status = "cancelled"
    log_audit("update", "availability_request", req.id, before=before, after=req.to_dict())
    db.session.commit()

    return jsonify({"ok": True})


@extras_bp.route("/seed", methods=["POST"])
def seed_demo_users():
    """Seed test users (admin, students, FTO) with demo password 'password'.

    Only works if users table is empty. This endpoint exists to allow seeding
    without shell access on platforms like Render (free tier).

    For security, only allow this if DEMO_SEED_ENABLED environment variable is set.
    """
    import os

    if not os.getenv("DEMO_SEED_ENABLED"):
        return make_response(
            jsonify(
                {
                    "error": "seeding disabled (set DEMO_SEED_ENABLED=1 to enable)",
                }
            ),
            403,
        )

    # Check if users already exist
    existing_count = User.query.count()
    if existing_count > 0:
        return make_response(
            jsonify(
                {
                    "error": "users table not empty (seeding prevented)",
                    "existing_user_count": existing_count,
                }
            ),
            409,
        )

    try:
        now = datetime.utcnow()

        # Create demo users
        admin = User(name="Admin User", email="admin@csuf.edu", role="admin", created_at=now)
        s1 = User(name="Student One", email="s1@csuf.edu", role="student", created_at=now)
        s2 = User(name="Student Two", email="s2@csuf.edu", role="student", created_at=now)
        fto = User(name="FTO User", email="fto@csuf.edu", role="FTO", created_at=now)

        # Set demo password for all users
        for user in [admin, s1, s2, fto]:
            if hasattr(user, "set_password"):
                user.set_password("password")

        # Add to session
        db.session.add_all([admin, s1, s2, fto])
        db.session.flush()

        # Log audit trail
        for user in [admin, s1, s2, fto]:
            log_audit("create", "user", user.id, after=user.to_dict())

        db.session.commit()

        return make_response(
            jsonify(
                {
                    "message": "seed complete",
                    "users_created": [
                        {"id": admin.id, "email": admin.email, "role": admin.role},
                        {"id": s1.id, "email": s1.email, "role": s1.role},
                        {"id": s2.id, "email": s2.email, "role": s2.role},
                        {"id": fto.id, "email": fto.email, "role": fto.role},
                    ],
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return make_response(
            jsonify({"error": f"seeding failed: {str(e)}"}),
            500,
        )
