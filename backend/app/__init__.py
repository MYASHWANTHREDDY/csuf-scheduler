"""Flask application factory and entrypoint for CSUF Scheduler.

Creates and configures the Flask app, initializes extensions, registers
blueprints and creates database tables on first run.
"""

import logging
import os
from datetime import timedelta
from typing import Any

from dotenv import load_dotenv
from flasgger import Swagger
from flask import (
    Flask,
    Response,
    jsonify,
    make_response,
    render_template,
    request,
    send_from_directory,
    session,
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import the db instance and models so SQLAlchemy knows about them
try:
    from . import models  # noqa: F401 (import for model registration)
    from .database import db
    from .middleware import register_request_logging
except Exception:
    # Fallback when running scripts directly from the backend folder
    import models  # noqa: F401
    from database import db
    from middleware import register_request_logging


def create_app() -> Flask:
    """Create and configure the Flask application."""
    # Load .env values into environment.
    # Prefer backend/.env to avoid relying on current working directory.
    backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv(backend_env)
    load_dotenv()

    app = Flask(__name__, template_folder="templates")
    frontend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

    app.config["SWAGGER"] = {
        "title": "CSUF Scheduler API",
        "uiversion": 3,
        "openapi": "3.0.2",
    }
    Swagger(
        app,
        template={
            "info": {
                "title": "CSUF Scheduler API",
                "version": "1.0.0",
                "description": "API documentation for CSUF Scheduler endpoints.",
            }
        },
    )

    # Configuration: require DATABASE_URL (Postgres recommended for local/dev via docker-compose)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Please copy backend/.env.example to backend/.env and set DATABASE_URL to a Postgres URI."
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["LOG_LEVEL"] = os.getenv("LOG_LEVEL", os.getenv("LOGS_LEVEL", "INFO"))
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
    )
    flask_env = os.getenv("FLASK_ENV", "development")
    csrf_default = "1" if flask_env == "production" else "0"
    csrf_enabled = os.getenv("CSRF_PROTECT_ENABLED", csrf_default) == "1"
    app.config["CSRF_PROTECT_ENABLED"] = csrf_enabled and flask_env != "testing"
    login_rate_limit_default = "5 per minute" if flask_env == "production" else ""
    app.config["LOGIN_RATE_LIMIT"] = os.getenv("LOGIN_RATE_LIMIT", login_rate_limit_default)
    password_complexity_default = "1" if flask_env == "production" else "0"
    app.config["PASSWORD_MIN_LENGTH"] = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    app.config["PASSWORD_REQUIRE_COMPLEXITY"] = (
        os.getenv("PASSWORD_REQUIRE_COMPLEXITY", password_complexity_default) == "1"
    )

    # Safety check: in production require a non-default SECRET_KEY
    if os.getenv("FLASK_ENV") == "production":
        bad_secrets = (None, "", "dev", "change-me-to-a-secure-value")
        if app.config.get("SECRET_KEY") in bad_secrets:
            raise RuntimeError("SECRET_KEY must be set to a secure value in production")

    # Secure cookie settings in production
    if os.getenv("FLASK_ENV") == "production":
        app.config.update(
            SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax"
        )

    limiter = Limiter(
        key_func=lambda: session.get("user_id") or get_remote_address(),
        default_limits=[],
        storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    )
    limiter.init_app(app)

    # Initialize extensions
    db.init_app(app)
    # Restrict CORS to a specific origin for dev (adjust via CORS_ORIGIN env var).
    # Default is the React dev server origin commonly used: http://localhost:5173
    cors_origin = os.getenv("CORS_ORIGIN", "http://localhost:5173")
    CORS(app, origins=[cors_origin])
    register_request_logging(app)

    sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
    if sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=sentry_dsn,
                environment=flask_env,
                traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            )
            app.logger.info("Sentry error tracking enabled")
        except Exception:
            app.logger.exception("Failed to initialize Sentry")

    # Register blueprints (support package and script execution)
    try:
        from .routes import health_bp, shifts_bp, time_adjustments_bp, timesheets_bp, users_bp
    except Exception:
        from routes import health_bp, shifts_bp, time_adjustments_bp, timesheets_bp, users_bp

    app.register_blueprint(users_bp)
    app.register_blueprint(shifts_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(time_adjustments_bp)
    app.register_blueprint(timesheets_bp)

    try:
        from .routes import audit_bp, conflicts_bp, reports_bp
    except Exception:
        from routes import audit_bp, conflicts_bp, reports_bp
    app.register_blueprint(reports_bp)
    app.register_blueprint(conflicts_bp)
    app.register_blueprint(audit_bp)
    # register extra demo blueprints (availability, swap requests, announcements)
    try:
        from .routes import extras as extras_mod
    except Exception:
        import routes.extras as extras_mod
    app.register_blueprint(extras_mod.extras_bp)

    # Register AI scheduler blueprint
    try:
        from .routes.scheduler import scheduler_bp
    except Exception:
        from routes.scheduler import scheduler_bp
    app.register_blueprint(scheduler_bp)

    login_endpoint = app.view_functions.get("users.login")
    if login_endpoint and app.config.get("LOGIN_RATE_LIMIT"):
        app.view_functions["users.login"] = limiter.limit(app.config["LOGIN_RATE_LIMIT"])(
            login_endpoint
        )

    @app.before_request
    def enforce_csrf() -> Response | None:
        if not app.config.get("CSRF_PROTECT_ENABLED"):
            return None
        if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            return None
        if request.path == "/api/users/login":
            return None
        if not session.get("user_id"):
            return None

        session_token = session.get("csrf_token")
        header_token = request.headers.get("X-CSRF-Token")
        if not session_token or not header_token or session_token != header_token:
            return make_response(jsonify({"error": "csrf token missing or invalid"}), 400)
        return None

    @app.after_request
    def set_security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self'"
        )
        if os.getenv("FLASK_ENV") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Startup information and migration policy
    # NOTE: We intentionally do NOT call `db.create_all()` here. Alembic is the
    # canonical schema manager. Ensure you run `alembic upgrade head` after
    # configuring `DATABASE_URL` (see backend/.env.example).
    with app.app_context():
        # Use logging instead of print for startup messages so container logs are consistent
        logger = logging.getLogger(__name__)
        try:
            dialect = db.engine.dialect.name
            url = db.engine.url
            host = getattr(url, "host", None)
            database = getattr(url, "database", None)
            logger.info("DB startup: dialect=%s host=%s database=%s", dialect, host, database)
        except Exception:
            logger.exception(
                "DB startup: could not inspect engine URL. Ensure DATABASE_URL is correct."
            )

        # Auto-run Alembic migrations on startup to ensure schema is up-to-date
        # This is safe to run multiple times (Alembic tracks already-applied migrations)
        try:
            logger.info("Running Alembic migrations (alembic upgrade head)...")
            from alembic.command import upgrade
            from alembic.config import Config

            # Find alembic.ini by checking common relative paths
            # In Render with root directory set to 'backend', we run from /app/backend
            # so alembic.ini is at ../alembic.ini relative to cwd
            candidate_paths = [
                os.path.join(os.getcwd(), "..", "alembic.ini"),  # ../alembic.ini
                os.path.join(os.getcwd(), "alembic.ini"),  # ./alembic.ini
                "/app/alembic.ini",  # /app/alembic.ini
            ]

            alembic_cfg_path = None
            for candidate in candidate_paths:
                normalized = os.path.normpath(candidate)
                logger.info("Checking for alembic.ini at: %s", normalized)
                if os.path.exists(normalized):
                    alembic_cfg_path = normalized
                    logger.info("✅ Found alembic.ini at: %s", alembic_cfg_path)
                    break

            if not alembic_cfg_path:
                raise RuntimeError(f"alembic.ini not found. Checked: {candidate_paths}")

            alembic_cfg = Config(alembic_cfg_path)
            # Only set database URL; script_location is already configured in alembic.ini
            alembic_cfg.set_main_option("sqlalchemy.url", database_url)

            logger.info("Starting Alembic upgrade to head...")
            upgrade(alembic_cfg, "head")
            logger.info("✅ Alembic migrations completed successfully")
        except Exception as e:
            logger.error("Failed to run Alembic migrations: %s", e, exc_info=True)
            logger.warning("Continuing startup despite migration failure (check database state)")

        # For quick demos only: if DEMO_CREATE_DB=1, create missing tables from models.
        # This is intentionally guarded so production continues to use Alembic migrations.
        # Only create tables automatically for development/demo environments
        if os.getenv("DEMO_CREATE_DB") == "1":
            if os.getenv("FLASK_ENV") == "production":
                logger.warning("DEMO_CREATE_DB=1 is ignored in production (unsafe)")
            else:
                try:
                    logger.info("DEMO_CREATE_DB=1 -> creating database tables (dev/demo only)")
                    db.create_all()
                except Exception as e:
                    logger.exception("Failed to create tables in demo mode: %s", e)

        # In production on Render, if migrations failed, still try to create any missing tables
        # This is a safety fallback to ensure the app doesn't completely fail
        if os.getenv("FLASK_ENV") == "production":
            try:
                # Check if users table exists; if not, create all tables
                from sqlalchemy import inspect as sa_inspect

                inspector = sa_inspect(db.engine)
                existing_tables = inspector.get_table_names()
                logger.info("Existing database tables: %s", existing_tables)
                if "users" not in existing_tables:
                    logger.warning(
                        "users table missing; attempting to create all tables as fallback"
                    )
                    db.create_all()
                    logger.info("✅ Database tables created successfully (fallback)")
                else:
                    logger.info("✅ Database schema exists (users table found)")
            except Exception as e:
                logger.error("Tables check/creation fallback failed: %s", e, exc_info=True)

    @app.route("/frontend/<path:filename>")
    def frontend_assets(filename: str) -> Response:
        return send_from_directory(frontend_root, filename)

    @app.route("/frontend")
    def frontend_index_file() -> Response:
        return send_from_directory(frontend_root, "index.html")

    # Main app route (template-based modernized UI)
    @app.route("/")
    def index() -> Response:
        from flask import make_response

        response = make_response(render_template("index.html"))
        # Disable caching for development to ensure browser gets latest changes
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # Vue component-library preview route kept for incremental migration
    @app.route("/app-vue")
    def vue_index() -> Response:
        from flask import make_response

        response = make_response(render_template("vue_app.html"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.errorhandler(404)
    def not_found(error: Any) -> Response:
        return make_response(render_template("404.html"), 404)

    @app.errorhandler(500)
    def internal_error(error: Any) -> Response:
        return make_response(render_template("500.html"), 500)

    return app


if __name__ == "__main__":
    # When running directly, create app and run debug server
    app = create_app()
    app.run(debug=True)
