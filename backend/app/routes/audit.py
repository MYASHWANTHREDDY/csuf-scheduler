"""Global audit API routes.

Prefix: /api/audit
"""

from flask import Blueprint, jsonify, request

try:
    from ..models import AuditLog
    from ..utils.auth import require_auth as _require_auth
except (ImportError, ModuleNotFoundError):
    from models import AuditLog
    from utils.auth import require_auth as _require_auth


audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@audit_bp.route("", methods=["GET"])
def list_audit_logs():
    """List audit log records with filters.

    ---
    tags:
      - Audit
    parameters:
      - in: query
        name: action
        schema:
          type: string
      - in: query
        name: entity_type
        schema:
          type: string
      - in: query
        name: entity_id
        schema:
          type: string
      - in: query
        name: limit
        schema:
          type: integer
          minimum: 1
          maximum: 1000
    responses:
      200:
        description: Audit log list
      403:
        description: Forbidden
    """
    _, err = _require_auth({"admin", "supervisor"})
    if err:
        return err

    entity_type = (request.args.get("entity_type") or "").strip()
    entity_id = (request.args.get("entity_id") or "").strip()
    action = (request.args.get("action") or "").strip()
    limit = request.args.get("limit", default=200, type=int)
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    query = AuditLog.query
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if action:
        query = query.filter(AuditLog.action == action)

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify([log.to_dict() for log in logs])
