"""Time adjustment API routes.

Prefix: /api/time_adjustments
"""

from datetime import datetime

from flask import Blueprint, jsonify, make_response, request

try:
    from ..database import db
    from ..models import Shift, TimeAdjustmentRequest
    from ..utils.audit import log_audit
    from ..utils.auth import require_auth as _require_auth
    from ..utils.parsers import parse_time as _parse_time
except (ImportError, ModuleNotFoundError):
    from database import db
    from models import Shift, TimeAdjustmentRequest
    from utils.audit import log_audit
    from utils.auth import require_auth as _require_auth
    from utils.parsers import parse_time as _parse_time


time_adjustments_bp = Blueprint("time_adjustments", __name__, url_prefix="/api/time_adjustments")


@time_adjustments_bp.route("", methods=["POST"])
def create_time_adjustment():
    """Create a new time adjustment request for the current user's assigned shift."""
    user, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    shift_id = data.get("shift_id")
    actual_start_raw = data.get("actual_start")
    actual_end_raw = data.get("actual_end")
    reason = (data.get("reason") or "").strip()
    resubmit_of_id = data.get("resubmit_of_id")

    if not shift_id:
        return make_response(jsonify({"error": "shift_id is required"}), 400)
    if not actual_start_raw or not actual_end_raw:
        return make_response(jsonify({"error": "actual_start and actual_end are required"}), 400)

    actual_start = _parse_time(actual_start_raw)
    actual_end = _parse_time(actual_end_raw)
    if not actual_start or not actual_end:
        return make_response(jsonify({"error": "actual_start and actual_end must be HH:MM"}), 400)

    shift = db.session.get(Shift, shift_id)
    if not shift:
        return make_response(jsonify({"error": "shift not found"}), 404)

    if shift.assigned_user_id != user.id:
        return make_response(
            jsonify({"error": "you can only submit adjustments for your own assigned shifts"}), 403
        )

    start_minutes = actual_start.hour * 60 + actual_start.minute
    end_minutes = actual_end.hour * 60 + actual_end.minute
    if end_minutes <= start_minutes:
        return make_response(jsonify({"error": "actual_end must be after actual_start"}), 400)

    existing_pending = TimeAdjustmentRequest.query.filter_by(
        shift_id=shift.id, user_id=user.id, status="pending"
    ).first()
    if existing_pending:
        return make_response(
            jsonify({"error": "a pending time adjustment already exists for this shift"}), 409
        )

    if resubmit_of_id is not None:
        prior_request = db.session.get(TimeAdjustmentRequest, resubmit_of_id)
        if not prior_request:
            return make_response(
                jsonify({"error": "original request for resubmission not found"}), 404
            )
        if prior_request.user_id != user.id:
            return make_response(jsonify({"error": "cannot resubmit another user's request"}), 403)
        if prior_request.status != "rejected":
            return make_response(
                jsonify({"error": "only rejected requests can be resubmitted"}), 400
            )

    req = TimeAdjustmentRequest(
        shift_id=shift.id,
        user_id=user.id,
        actual_start=actual_start,
        actual_end=actual_end,
        reason=reason,
        status="pending",
    )
    db.session.add(req)
    db.session.flush()
    log_audit("create", "time_adjustment_request", req.id, after=req.to_dict())
    db.session.commit()

    return make_response(jsonify({"id": req.id}), 201)


@time_adjustments_bp.route("/my-requests", methods=["GET"])
def list_my_time_adjustments():
    """List time adjustment requests for the current authenticated user."""
    user, err = _require_auth()
    if err:
        return err

    items = (
        TimeAdjustmentRequest.query.filter_by(user_id=user.id)
        .order_by(TimeAdjustmentRequest.created_at.desc())
        .all()
    )
    return jsonify([item.to_dict() for item in items])


@time_adjustments_bp.route("", methods=["GET"])
def list_time_adjustments():
    """List time adjustment requests for managers with optional status filter."""
    _, err = _require_auth({"supervisor", "admin"})
    if err:
        return err

    status = (request.args.get("status") or "").strip().lower()
    query = TimeAdjustmentRequest.query
    if status:
        query = query.filter(TimeAdjustmentRequest.status == status)

    items = query.order_by(TimeAdjustmentRequest.created_at.desc()).all()
    return jsonify([item.to_dict() for item in items])


@time_adjustments_bp.route("/<int:request_id>/review", methods=["POST"])
def review_time_adjustment(request_id):
    """Review a pending time adjustment request (approve/reject)."""
    reviewer, err = _require_auth({"supervisor", "admin"})
    if err:
        return err

    item = db.session.get(TimeAdjustmentRequest, request_id)
    if not item:
        return make_response(jsonify({"error": "time adjustment request not found"}), 404)
    if item.status != "pending":
        return make_response(jsonify({"error": "only pending requests can be reviewed"}), 409)

    data = request.get_json() or {}
    action = (data.get("action") or "").strip().lower()
    reviewer_notes = (data.get("reviewer_notes") or "").strip()

    if action not in ("approve", "reject"):
        return make_response(jsonify({"error": "action must be approve or reject"}), 400)

    before = item.to_dict()
    item.status = "approved" if action == "approve" else "rejected"
    item.reviewed_by_id = reviewer.id
    item.reviewed_at = datetime.utcnow()
    item.reviewer_notes = reviewer_notes or None

    # If approving, update the associated shift's times
    if action == "approve" and item.shift:
        item.shift.start_time = item.actual_start
        item.shift.end_time = item.actual_end

    log_audit(
        "review",
        "time_adjustment_request",
        item.id,
        before=before,
        after=item.to_dict(),
        details={"action": action},
    )

    db.session.commit()
    return jsonify({"ok": True, "status": item.status})
