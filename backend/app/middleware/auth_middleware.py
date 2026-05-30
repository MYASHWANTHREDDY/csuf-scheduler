"""Authentication middleware helpers."""

from __future__ import annotations

from flask import session


def current_user_id() -> int | None:
    """Return the current session user id if authenticated."""
    user_id = session.get("user_id")
    return int(user_id) if user_id is not None else None


def is_authenticated() -> bool:
    """Return whether a user is authenticated in the current session."""
    return current_user_id() is not None
