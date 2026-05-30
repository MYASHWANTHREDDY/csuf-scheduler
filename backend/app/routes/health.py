"""Health check endpoints.

Prefix: /api/health
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint
from sqlalchemy import text

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


health_bp = Blueprint("health", __name__, url_prefix="/api/health")


@health_bp.route("", methods=["GET"])
def health() -> tuple[dict, int]:
    """Return service and database health.

    ---
    tags:
      - Health
    responses:
      200:
        description: Service healthy
      503:
        description: Service unhealthy
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.session.execute(text("SELECT 1"))
        return (
            {
                "status": "healthy",
                "database": "ok",
                "timestamp": now,
            },
            200,
        )
    except Exception as exc:
        return (
            {
                "status": "unhealthy",
                "database": "error",
                "error": str(exc),
                "timestamp": now,
            },
            503,
        )
