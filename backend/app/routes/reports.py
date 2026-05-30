"""Reporting API routes.

Prefix: /api/reports
"""

import csv
from datetime import datetime, timedelta
from io import StringIO

from flask import Blueprint, jsonify, make_response, request

try:
    from ..models import Shift, User
    from ..utils.auth import require_auth as _require_auth
except (ImportError, ModuleNotFoundError):
    from models import Shift, User
    from utils.auth import require_auth as _require_auth


reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


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


def _shift_duration_hours(shift):
    start_dt = datetime.combine(shift.date, shift.start_time)
    end_dt = datetime.combine(shift.date, shift.end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return (end_dt - start_dt).total_seconds() / 3600.0


def _hours_rows_for_week(week_param):
    week_start, week_end = _parse_week_param(week_param)
    if not week_start:
        return None, None, None

    shifts = Shift.query.filter(
        Shift.assigned_user_id.isnot(None), Shift.date >= week_start, Shift.date <= week_end
    ).all()

    totals = {}
    for shift in shifts:
        uid = shift.assigned_user_id
        totals[uid] = totals.get(uid, 0.0) + _shift_duration_hours(shift)

    users = User.query.filter(User.id.in_(totals.keys())).all() if totals else []
    users_by_id = {user.id: user for user in users}

    rows = []
    for uid, hours in sorted(totals.items(), key=lambda item: item[0]):
        user = users_by_id.get(uid)
        rows.append(
            {
                "user_id": uid,
                "name": (
                    user.name if user and user.name else (user.email if user else f"User {uid}")
                ),
                "email": user.email if user else None,
                "role": user.role if user else None,
                "hours": round(hours, 2),
            }
        )

    return week_start, week_end, rows


@reports_bp.route("/hours", methods=["GET"])
def report_hours_json():
    """Weekly hours summary as JSON.

    ---
    tags:
      - Reports
    parameters:
      - in: query
        name: week
        required: true
        schema:
          type: string
        description: ISO week format `YYYY-Www`.
    responses:
      200:
        description: Weekly hours report
      400:
        description: Invalid or missing week parameter
      403:
        description: Forbidden
    """
    _, err = _require_auth({"admin", "supervisor"})
    if err:
        return err

    week = (request.args.get("week") or "").strip()
    if not week:
        return make_response(
            jsonify({"error": "week query param is required (format YYYY-Www)"}), 400
        )

    week_start, week_end, rows = _hours_rows_for_week(week)
    if week_start is None:
        return make_response(jsonify({"error": "invalid week format; use YYYY-Www"}), 400)

    return jsonify(
        {
            "week": week,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "rows": rows,
        }
    )


@reports_bp.route("/hours.csv", methods=["GET"])
def report_hours_csv():
    """Weekly hours summary as CSV.

    ---
    tags:
      - Reports
    parameters:
      - in: query
        name: week
        required: true
        schema:
          type: string
        description: ISO week format `YYYY-Www`.
    responses:
      200:
        description: CSV payload
      400:
        description: Invalid or missing week parameter
      403:
        description: Forbidden
    """
    _, err = _require_auth({"admin", "supervisor"})
    if err:
        return err

    week = (request.args.get("week") or "").strip()
    if not week:
        return make_response(
            jsonify({"error": "week query param is required (format YYYY-Www)"}), 400
        )

    week_start, week_end, rows = _hours_rows_for_week(week)
    if week_start is None:
        return make_response(jsonify({"error": "invalid week format; use YYYY-Www"}), 400)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["week", "week_start", "week_end", "user_id", "name", "email", "role", "hours"])
    for row in rows:
        writer.writerow(
            [
                week,
                week_start.isoformat(),
                week_end.isoformat(),
                row["user_id"],
                row["name"],
                row["email"] or "",
                row["role"] or "",
                row["hours"],
            ]
        )

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=hours_{week}.csv"
    return response
