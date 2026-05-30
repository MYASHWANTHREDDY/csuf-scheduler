"""Users API blueprint.

Provides endpoints to list and create users.
"""

import logging
import secrets

from flask import Blueprint, current_app, jsonify, make_response, request, session
from pydantic import ValidationError

# Allow routes to be imported either as package (backend.app.routes) or run from the backend folder
try:
    from ..database import db
    from ..models import User
    from ..utils.audit import log_audit
    from ..utils.schemas import CreateUserRequest, LoginRequest
except (ImportError, ModuleNotFoundError):
    from database import db
    from models import User
    from utils.audit import log_audit
    from utils.schemas import CreateUserRequest, LoginRequest

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


def _validate_password_policy(password: str) -> str | None:
    min_length = int(current_app.config.get("PASSWORD_MIN_LENGTH", 8))
    require_complexity = bool(current_app.config.get("PASSWORD_REQUIRE_COMPLEXITY", False))

    if not password or len(password) < min_length:
        return f"password must be at least {min_length} characters"

    if require_complexity:
        has_letter = any(ch.isalpha() for ch in password)
        has_digit = any(ch.isdigit() for ch in password)
        if not (has_letter and has_digit):
            return "password must include at least one letter and one number"

    return None


def _csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@users_bp.route("", methods=["GET"])
def list_users():
    """Return list of users as JSON for any authenticated user."""
    uid = session.get("user_id")
    if not uid:
        return make_response(jsonify({"error": "not authenticated"}), 401)
    user = db.session.get(User, uid)
    if not user:
        session.clear()
        return make_response(jsonify({"error": "not authenticated"}), 401)

    # Return users ordered by ID (maintains consistent employee list ordering)
    users = User.query.order_by(User.id).all()
    result = [{"id": u.id, "name": u.name, "email": u.email, "role": u.role} for u in users]
    return jsonify(result)


@users_bp.route("", methods=["POST"])
def create_user():
    """Create a new user from JSON payload.

        ---
        tags:
            - Users
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            first_name: {type: string}
                            last_name: {type: string}
                            name: {type: string}
                            email: {type: string, format: email}
                            password: {type: string}
                            role: {type: string}
                        required: [email, password]
        responses:
            201:
                description: User created
            400:
                description: Validation error
            401:
                description: Not authenticated
            403:
                description: Insufficient role

    Expected JSON: { first_name?, last_name?, name?, email, password, role? }
    Returns: { id } and 201 on success, 400 on bad input.

    If user is authenticated as admin/supervisor, they can create any user.
    Otherwise, this is self-registration (unauthenticated signup) for students only.
    """
    data = request.get_json() or {}
    try:
        payload = CreateUserRequest.model_validate(data)
    except ValidationError as exc:
        return make_response(jsonify({"error": exc.errors()}), 400)

    first_name = payload.first_name
    last_name = payload.last_name
    name = payload.name
    email = str(payload.email)
    password = payload.password
    role = payload.role

    # Check if user is authenticated as admin/supervisor
    uid = session.get("user_id")
    if not uid:
        # Allow self-registration for students
        if role and role != "student":
            return make_response(
                jsonify({"error": "self-registration only allows student role"}),
                403,
            )
        role = "student"
    else:
        # Authenticated user - must be admin/supervisor to create users
        user = db.session.get(User, uid)
        if not user or user.role not in {"admin", "supervisor"}:
            return make_response(jsonify({"error": "insufficient role"}), 403)

    try:
        # Basic validation
        if not (first_name or last_name or name):
            return make_response(
                jsonify({"error": "first_name/last_name or name is required"}), 400
            )
        if not email:
            return make_response(jsonify({"error": "email is required"}), 400)
        # Build display name for length check
        display_name = (first_name + " " + last_name).strip() if (first_name or last_name) else name
        if len(display_name) > 120 or len(email) > 120:
            return make_response(
                jsonify({"error": "name and email must be 120 characters or fewer"}), 400
            )
        if "@" not in email or "." not in email.split("@")[-1]:
            return make_response(jsonify({"error": "email must be a valid address"}), 400)

        # Uniqueness
        if User.query.filter_by(email=email).first():
            return make_response(jsonify({"error": "email already exists"}), 400)

        # Password validation and hashing
        password_error = _validate_password_policy(password)
        if password_error:
            return make_response(jsonify({"error": password_error}), 400)

        # Build display name
        final_name = name or display_name
        user = User(
            name=final_name,
            first_name=first_name or None,
            last_name=last_name or None,
            email=email,
            role=role,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        log_audit(
            action="create",
            entity_type="user",
            entity_id=user.id,
            after={"id": user.id, "email": user.email, "role": user.role, "name": final_name},
        )
        db.session.commit()

        return make_response(jsonify({"id": user.id}), 201)
    except Exception:
        # Return JSON error for unexpected exceptions (avoid HTML tracebacks)
        logging.getLogger(__name__).exception("Unexpected error in create_user")
        return make_response(jsonify({"error": "internal server error"}), 500)


@users_bp.route("/login", methods=["POST"])
def login():
    """Simple demo login by email. Sets server-side session user_id.

        ---
        tags:
            - Auth
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        type: object
                        required: [email, password]
                        properties:
                            email: {type: string, format: email}
                            password: {type: string}
        responses:
            200:
                description: Successful login
            400:
                description: Missing or invalid payload
            401:
                description: Invalid credentials
            404:
                description: User not found

    Expected JSON: { email }
    Returns 200 with user info on success, 400/404 on failure.
    NOTE: This is a demo-only approach (no password). For production add proper auth.
    """
    data = request.get_json() or {}
    try:
        payload = LoginRequest.model_validate(data)
    except ValidationError as exc:
        return make_response(jsonify({"error": exc.errors()}), 400)

    email = str(payload.email)
    password = payload.password
    user = User.query.filter_by(email=email).first()
    if not user:
        return make_response(jsonify({"error": "user not found"}), 404)
    if not user.check_password(password):
        return make_response(jsonify({"error": "invalid credentials"}), 401)
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    return jsonify({**user.to_dict(), "csrf_token": _csrf_token()})


@users_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@users_bp.route("/csrf", methods=["GET"])
def csrf_token():
    uid = session.get("user_id")
    if not uid:
        return make_response(jsonify({"error": "not authenticated"}), 401)
    user = db.session.get(User, uid)
    if not user:
        session.clear()
        return make_response(jsonify({"error": "not authenticated"}), 401)
    return jsonify({"csrf_token": _csrf_token()})


@users_bp.route("/me", methods=["GET"])
def me():
    uid = session.get("user_id")
    if not uid:
        return make_response(jsonify({"error": "not authenticated"}), 401)
    user = db.session.get(User, uid)
    if not user:
        session.clear()
        return make_response(jsonify({"error": "not authenticated"}), 401)
    return jsonify({**user.to_dict(), "csrf_token": _csrf_token()})
