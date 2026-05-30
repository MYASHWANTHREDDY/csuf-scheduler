"""Error handling helpers for API responses."""

from __future__ import annotations

from flask import jsonify, make_response
from werkzeug.wrappers import Response


def json_error_response(message: str, status_code: int = 500) -> Response:
    """Return a standardized JSON error response."""
    return make_response(jsonify({"error": message}), status_code)
