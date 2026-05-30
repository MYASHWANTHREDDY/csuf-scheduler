"""Authentication and authorization utilities.

Provides shared helper functions for role-based access control across all routes.
"""

from __future__ import annotations

from collections.abc import Iterable

from flask import jsonify, make_response, session
from flask.wrappers import Response

try:
    from ..database import db
    from ..models import User
except ImportError:
    from database import db
    from models import User


def require_role(allowed_roles: Iterable[str] | None) -> tuple[User | None, Response | None]:
    """Check if current user is authenticated and has an allowed role.

    Args:
        allowed_roles: Set of role strings that are permitted, or None to allow any authenticated user.

    Returns:
        Tuple of (user, None) if authenticated and authorized.
        Tuple of (None, response) with error response if not.
    """
    uid = session.get("user_id")
    if not uid:
        return None, make_response(jsonify({"error": "not authenticated"}), 401)
    user = db.session.get(User, uid)
    if not user:
        session.clear()
        return None, make_response(jsonify({"error": "not authenticated"}), 401)
    if allowed_roles and user.role not in allowed_roles:
        return None, make_response(jsonify({"error": "forbidden: insufficient role"}), 403)
    return user, None


def require_auth(allowed_roles: Iterable[str] | None = None) -> tuple[User | None, Response | None]:
    """Alias for require_role with optional role restriction.

    Args:
        allowed_roles: Optional set of role strings. If None, any authenticated user is allowed.

    Returns:
        Tuple of (user, None) if authenticated and authorized.
        Tuple of (None, response) with error response if not.
    """
    return require_role(allowed_roles)
