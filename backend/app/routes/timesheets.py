"""Timesheet and pay period API routes.

Prefix: /api/timesheets
"""

from datetime import datetime

from flask import Blueprint, jsonify, make_response, request

try:
    from ..database import db
    from ..models import (
        PayPeriod,
        Shift,
        TimeAdjustmentRequest,
        Timesheet,
        TimesheetAuditLog,
        TimesheetComment,
        TimesheetLine,
        User,
    )
    from ..utils.auth import require_auth as _require_auth
    from ..utils.parsers import parse_date as _parse_date
    from ..utils.parsers import parse_time as _parse_time
except (ImportError, ModuleNotFoundError):
    from database import db
    from models import (
        PayPeriod,
        Shift,
        TimeAdjustmentRequest,
        Timesheet,
        TimesheetAuditLog,
        TimesheetComment,
        TimesheetLine,
        User,
    )
    from utils.auth import require_auth as _require_auth
    from utils.parsers import parse_date as _parse_date
    from utils.parsers import parse_time as _parse_time


timesheets_bp = Blueprint("timesheets", __name__, url_prefix="/api/timesheets")


TIMESHEET_STATUSES = {"draft", "submitted", "needs_response", "approved", "rejected"}
TIMESHEET_REVIEW_ROLES = {"admin", "supervisor"}


def _log(timesheet_id, actor_id, action, details=None):
    db.session.add(
        TimesheetAuditLog(
            timesheet_id=timesheet_id, actor_id=actor_id, action=action, details=details
        )
    )


def _in_period(work_date, pay_period):
    return pay_period.start_date <= work_date <= pay_period.end_date


def _latest_approved_adjustment(shift_id, user_id):
    return (
        TimeAdjustmentRequest.query.filter_by(
            shift_id=shift_id,
            user_id=user_id,
            status="approved",
        )
        .order_by(TimeAdjustmentRequest.reviewed_at.desc(), TimeAdjustmentRequest.created_at.desc())
        .first()
    )


def _load_or_create_timesheet(pay_period_id, user_id):
    timesheet = Timesheet.query.filter_by(pay_period_id=pay_period_id, user_id=user_id).first()
    if timesheet:
        return timesheet, False

    timesheet = Timesheet(pay_period_id=pay_period_id, user_id=user_id, status="draft")
    db.session.add(timesheet)
    db.session.flush()
    return timesheet, True


def _seed_lines_from_shifts(timesheet, actor_id):
    pay_period = timesheet.pay_period
    shifts = (
        Shift.query.filter(
            Shift.assigned_user_id == timesheet.user_id,
            Shift.date >= pay_period.start_date,
            Shift.date <= pay_period.end_date,
        )
        .order_by(Shift.date.asc(), Shift.start_time.asc())
        .all()
    )

    existing_shift_ids = {line.shift_id for line in timesheet.lines if line.shift_id}
    created_count = 0

    for shift in shifts:
        if shift.id in existing_shift_ids:
            continue

        approved_adj = _latest_approved_adjustment(shift.id, timesheet.user_id)
        line = TimesheetLine(
            timesheet_id=timesheet.id,
            shift_id=shift.id,
            work_date=shift.date,
            start_time=approved_adj.actual_start if approved_adj else shift.start_time,
            end_time=approved_adj.actual_end if approved_adj else shift.end_time,
            original_start_time=shift.start_time,
            original_end_time=shift.end_time,
            source_type="time_adjustment" if approved_adj else "scheduled",
            note=(approved_adj.reason if approved_adj and approved_adj.reason else None),
        )
        db.session.add(line)
        created_count += 1

    if created_count:
        _log(timesheet.id, actor_id, "seed_lines", f"Created {created_count} lines")


def _timesheet_for_user_or_manager(timesheet_id, user):
    timesheet = db.session.get(Timesheet, timesheet_id)
    if not timesheet:
        return None, make_response(jsonify({"error": "timesheet not found"}), 404)
    if user.role in TIMESHEET_REVIEW_ROLES:
        return timesheet, None
    if timesheet.user_id != user.id:
        return None, make_response(jsonify({"error": "forbidden"}), 403)
    return timesheet, None


@timesheets_bp.route("/pay-periods", methods=["POST"])
def create_pay_period():
    actor, err = _require_auth({"admin", "supervisor"})
    if err:
        return err

    data = request.get_json() or {}
    label = (data.get("label") or "").strip()
    start_date = _parse_date(data.get("start_date"))
    end_date = _parse_date(data.get("end_date"))
    deadline_raw = data.get("submission_deadline")

    if not label or not start_date or not end_date:
        return make_response(
            jsonify({"error": "label, start_date, and end_date are required"}), 400
        )
    if end_date < start_date:
        return make_response(jsonify({"error": "end_date must be on/after start_date"}), 400)

    submission_deadline = None
    if deadline_raw:
        try:
            submission_deadline = datetime.fromisoformat(deadline_raw)
        except ValueError:
            return make_response(
                jsonify({"error": "submission_deadline must be ISO datetime"}), 400
            )

    overlap = PayPeriod.query.filter(
        PayPeriod.start_date <= end_date,
        PayPeriod.end_date >= start_date,
    ).first()
    if overlap:
        return make_response(jsonify({"error": "pay period overlaps an existing pay period"}), 409)

    period = PayPeriod(
        label=label,
        start_date=start_date,
        end_date=end_date,
        submission_deadline=submission_deadline,
        status="open",
        created_by_id=actor.id,
    )
    db.session.add(period)
    db.session.commit()
    return make_response(jsonify(period.to_dict()), 201)


@timesheets_bp.route("/pay-periods", methods=["GET"])
def list_pay_periods():
    _, err = _require_auth()
    if err:
        return err

    items = PayPeriod.query.order_by(PayPeriod.start_date.desc()).all()
    return jsonify([i.to_dict() for i in items])


@timesheets_bp.route("/pay-periods/<int:pay_period_id>/finalize", methods=["POST"])
def finalize_pay_period(pay_period_id):
    actor, err = _require_auth({"admin"})
    if err:
        return err

    period = db.session.get(PayPeriod, pay_period_id)
    if not period:
        return make_response(jsonify({"error": "pay period not found"}), 404)
    if period.status == "finalized":
        return make_response(jsonify({"error": "pay period already finalized"}), 409)

    not_approved = Timesheet.query.filter(
        Timesheet.pay_period_id == pay_period_id,
        Timesheet.status != "approved",
    ).count()
    if not_approved > 0:
        return make_response(
            jsonify({"error": "all timesheets must be approved before finalization"}), 409
        )

    period.status = "finalized"
    period.finalized_by_id = actor.id
    period.finalized_at = datetime.utcnow()
    db.session.commit()
    return jsonify(period.to_dict())


@timesheets_bp.route("/my", methods=["GET"])
def get_my_timesheet_for_period():
    user, err = _require_auth()
    if err:
        return err

    pay_period_id = request.args.get("pay_period_id", type=int)
    if not pay_period_id:
        return make_response(jsonify({"error": "pay_period_id is required"}), 400)

    period = db.session.get(PayPeriod, pay_period_id)
    if not period:
        return make_response(jsonify({"error": "pay period not found"}), 404)

    timesheet, created = _load_or_create_timesheet(pay_period_id, user.id)
    _seed_lines_from_shifts(timesheet, user.id)
    if created:
        _log(timesheet.id, user.id, "create_timesheet", "Auto-created timesheet")
    db.session.commit()

    return jsonify(timesheet.to_dict(include_lines=True, include_comments=True))


@timesheets_bp.route("/<int:timesheet_id>/lines", methods=["POST"])
def add_manual_line(timesheet_id):
    user, err = _require_auth()
    if err:
        return err

    timesheet, err_resp = _timesheet_for_user_or_manager(timesheet_id, user)
    if err_resp:
        return err_resp

    if timesheet.status == "approved" or timesheet.pay_period.status == "finalized":
        return make_response(jsonify({"error": "timesheet is locked"}), 409)

    data = request.get_json() or {}
    work_date = _parse_date(data.get("work_date"))
    start_time = _parse_time(data.get("start_time"))
    end_time = _parse_time(data.get("end_time"))
    note = (data.get("note") or "").strip()

    if not work_date or not start_time or not end_time:
        return make_response(
            jsonify({"error": "work_date, start_time, and end_time are required"}), 400
        )
    if not _in_period(work_date, timesheet.pay_period):
        return make_response(jsonify({"error": "manual entry date must be inside pay period"}), 400)
    if not note:
        return make_response(jsonify({"error": "note is required for manual entries"}), 400)

    line = TimesheetLine(
        timesheet_id=timesheet.id,
        shift_id=None,
        work_date=work_date,
        start_time=start_time,
        end_time=end_time,
        source_type="manual",
        note=note,
    )
    db.session.add(line)
    timesheet.status = "draft"
    _log(
        timesheet.id,
        user.id,
        "add_manual_line",
        f"{work_date.isoformat()} {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}",
    )
    db.session.commit()

    return make_response(jsonify(line.to_dict()), 201)


@timesheets_bp.route("/<int:timesheet_id>/lines/<int:line_id>", methods=["PUT"])
def edit_line(timesheet_id, line_id):
    user, err = _require_auth()
    if err:
        return err

    timesheet, err_resp = _timesheet_for_user_or_manager(timesheet_id, user)
    if err_resp:
        return err_resp

    line = db.session.get(TimesheetLine, line_id)
    if not line or line.timesheet_id != timesheet.id:
        return make_response(jsonify({"error": "timesheet line not found"}), 404)

    if timesheet.status == "approved" or timesheet.pay_period.status == "finalized":
        return make_response(jsonify({"error": "timesheet is locked"}), 409)

    data = request.get_json() or {}
    start_time = _parse_time(data.get("start_time"))
    end_time = _parse_time(data.get("end_time"))
    note = (data.get("note") or "").strip()

    if not start_time or not end_time:
        return make_response(jsonify({"error": "start_time and end_time are required"}), 400)
    if not note:
        return make_response(jsonify({"error": "note is required when editing a line"}), 400)

    old_text = f"{line.start_time.strftime('%H:%M')}-{line.end_time.strftime('%H:%M')}"
    new_text = f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}"
    line.start_time = start_time
    line.end_time = end_time
    line.note = note
    timesheet.status = "draft"
    _log(timesheet.id, user.id, "edit_line", f"line {line.id}: {old_text} -> {new_text}; {note}")

    if user.id == timesheet.user_id:
        open_comments = [
            c for c in timesheet.comments if c.requires_response and c.resolved_at is None
        ]
        for comment in open_comments:
            comment.resolved_at = datetime.utcnow()
            comment.resolved_by_id = user.id
        if open_comments and timesheet.status == "needs_response":
            timesheet.status = "submitted"
            _log(
                timesheet.id, user.id, "respond_clarification", "Employee responded with line edits"
            )

    db.session.commit()
    return jsonify(line.to_dict())


@timesheets_bp.route("/<int:timesheet_id>/submit", methods=["POST"])
def submit_timesheet(timesheet_id):
    user, err = _require_auth()
    if err:
        return err

    timesheet, err_resp = _timesheet_for_user_or_manager(timesheet_id, user)
    if err_resp:
        return err_resp

    if timesheet.user_id != user.id:
        return make_response(jsonify({"error": "only employee can submit own timesheet"}), 403)
    if timesheet.pay_period.status == "finalized":
        return make_response(jsonify({"error": "pay period finalized"}), 409)
    if not timesheet.lines:
        return make_response(jsonify({"error": "timesheet has no lines"}), 400)

    timesheet.status = "submitted"
    timesheet.submitted_at = datetime.utcnow()
    _log(timesheet.id, user.id, "submit", "Timesheet submitted")
    db.session.commit()
    return jsonify(timesheet.to_dict(include_lines=True, include_comments=True))


@timesheets_bp.route("/<int:timesheet_id>/withdraw", methods=["POST"])
def withdraw_timesheet(timesheet_id):
    user, err = _require_auth()
    if err:
        return err

    timesheet, err_resp = _timesheet_for_user_or_manager(timesheet_id, user)
    if err_resp:
        return err_resp

    if timesheet.user_id != user.id:
        return make_response(jsonify({"error": "only employee can withdraw own timesheet"}), 403)
    if timesheet.status == "approved" or timesheet.pay_period.status == "finalized":
        return make_response(jsonify({"error": "cannot withdraw locked timesheet"}), 409)

    timesheet.status = "draft"
    _log(timesheet.id, user.id, "withdraw", "Timesheet withdrawn back to draft")
    db.session.commit()
    return jsonify(timesheet.to_dict(include_lines=True, include_comments=True))


@timesheets_bp.route("/<int:timesheet_id>/comments", methods=["GET"])
def list_comments(timesheet_id):
    user, err = _require_auth()
    if err:
        return err

    timesheet, err_resp = _timesheet_for_user_or_manager(timesheet_id, user)
    if err_resp:
        return err_resp

    return jsonify([c.to_dict() for c in sorted(timesheet.comments, key=lambda x: x.created_at)])


@timesheets_bp.route("/<int:timesheet_id>/comments", methods=["POST"])
def add_comment(timesheet_id):
    user, err = _require_auth()
    if err:
        return err

    timesheet, err_resp = _timesheet_for_user_or_manager(timesheet_id, user)
    if err_resp:
        return err_resp

    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    requires_response = bool(data.get("requires_response"))

    if not message:
        return make_response(jsonify({"error": "message is required"}), 400)

    if requires_response and user.role not in {"admin", "supervisor"}:
        return make_response(jsonify({"error": "only supervisor/admin can require response"}), 403)

    comment = TimesheetComment(
        timesheet_id=timesheet.id,
        author_id=user.id,
        message=message,
        requires_response=requires_response,
    )
    db.session.add(comment)

    if requires_response:
        timesheet.status = "needs_response"
        _log(timesheet.id, user.id, "request_clarification", message)
    else:
        _log(timesheet.id, user.id, "comment", message)

    if user.id == timesheet.user_id and timesheet.status == "needs_response":
        open_comments = [
            c for c in timesheet.comments if c.requires_response and c.resolved_at is None
        ]
        for c in open_comments:
            c.resolved_at = datetime.utcnow()
            c.resolved_by_id = user.id
        timesheet.status = "submitted"
        _log(timesheet.id, user.id, "clarification_response", "Employee responded to clarification")

    db.session.commit()
    return make_response(jsonify(comment.to_dict()), 201)


@timesheets_bp.route("/<int:timesheet_id>/approve", methods=["POST"])
def approve_timesheet(timesheet_id):
    reviewer, err = _require_auth({"admin", "supervisor"})
    if err:
        return err

    timesheet = db.session.get(Timesheet, timesheet_id)
    if not timesheet:
        return make_response(jsonify({"error": "timesheet not found"}), 404)

    if timesheet.status not in {"submitted"}:
        return make_response(jsonify({"error": "only submitted timesheets can be approved"}), 409)
    if timesheet.has_open_clarification():
        return make_response(
            jsonify({"error": "cannot approve while clarification is pending"}), 409
        )

    timesheet.status = "approved"
    timesheet.approved_at = datetime.utcnow()
    timesheet.approved_by_id = reviewer.id
    _log(timesheet.id, reviewer.id, "approve", "Timesheet approved")
    db.session.commit()
    return jsonify(timesheet.to_dict(include_lines=True, include_comments=True))


@timesheets_bp.route("/<int:timesheet_id>/reject", methods=["POST"])
def reject_timesheet(timesheet_id):
    reviewer, err = _require_auth(TIMESHEET_REVIEW_ROLES)
    if err:
        return err

    timesheet = db.session.get(Timesheet, timesheet_id)
    if not timesheet:
        return make_response(jsonify({"error": "timesheet not found"}), 404)

    data = request.get_json() or {}
    reason = (data.get("reason") or "").strip()

    timesheet.status = "rejected"
    _log(timesheet.id, reviewer.id, "reject", reason or "Rejected")
    if reason:
        db.session.add(
            TimesheetComment(
                timesheet_id=timesheet.id,
                author_id=reviewer.id,
                message=reason,
                requires_response=False,
            )
        )
    db.session.commit()
    return jsonify(timesheet.to_dict(include_lines=True, include_comments=True))


@timesheets_bp.route("/review", methods=["GET"])
def list_review_items():
    reviewer, err = _require_auth(TIMESHEET_REVIEW_ROLES)
    if err:
        return err

    pay_period_id = request.args.get("pay_period_id", type=int)
    status = (request.args.get("status") or "").strip().lower()

    query = Timesheet.query
    if pay_period_id:
        query = query.filter(Timesheet.pay_period_id == pay_period_id)
    if status:
        if status not in TIMESHEET_STATUSES:
            return make_response(jsonify({"error": "invalid status filter"}), 400)
        query = query.filter(Timesheet.status == status)

    items = query.order_by(Timesheet.user_id.asc(), Timesheet.updated_at.desc()).all()

    grouped = {}
    for item in items:
        grouped.setdefault(
            str(item.user_id),
            {
                "user": item.user.to_dict() if item.user else {"id": item.user_id},
                "timesheets": [],
            },
        )
        grouped[str(item.user_id)]["timesheets"].append(
            item.to_dict(include_lines=True, include_comments=True)
        )

    return jsonify(list(grouped.values()))


@timesheets_bp.route("/review/bulk-approve", methods=["POST"])
def bulk_approve():
    reviewer, err = _require_auth(TIMESHEET_REVIEW_ROLES)
    if err:
        return err

    data = request.get_json() or {}
    ids = data.get("timesheet_ids") or []
    if not isinstance(ids, list) or not ids:
        return make_response(jsonify({"error": "timesheet_ids list is required"}), 400)

    approved = []
    skipped = []
    for tid in ids:
        timesheet = db.session.get(Timesheet, tid)
        if not timesheet:
            skipped.append({"id": tid, "reason": "not found"})
            continue
        if timesheet.status != "submitted":
            skipped.append({"id": tid, "reason": f"status is {timesheet.status}"})
            continue
        if timesheet.has_open_clarification():
            skipped.append({"id": tid, "reason": "open clarification"})
            continue

        timesheet.status = "approved"
        timesheet.approved_at = datetime.utcnow()
        timesheet.approved_by_id = reviewer.id
        _log(timesheet.id, reviewer.id, "approve", "Bulk approved")
        approved.append(tid)

    db.session.commit()
    return jsonify({"approved_ids": approved, "skipped": skipped})


@timesheets_bp.route("/admin/overview", methods=["GET"])
def admin_overview():
    _, err = _require_auth(TIMESHEET_REVIEW_ROLES)
    if err:
        return err

    pay_period_id = request.args.get("pay_period_id", type=int)
    if not pay_period_id:
        return make_response(jsonify({"error": "pay_period_id is required"}), 400)

    period = db.session.get(PayPeriod, pay_period_id)
    if not period:
        return make_response(jsonify({"error": "pay period not found"}), 404)

    rows = []
    users = User.query.order_by(User.id.asc()).all()
    for user in users:
        if user.role in {"admin", "supervisor"}:
            continue
        ts = Timesheet.query.filter_by(pay_period_id=pay_period_id, user_id=user.id).first()
        rows.append(
            {
                "user": user.to_dict(),
                "timesheet": (
                    ts.to_dict(include_lines=False, include_comments=False) if ts else None
                ),
            }
        )

    return jsonify({"pay_period": period.to_dict(), "rows": rows})
