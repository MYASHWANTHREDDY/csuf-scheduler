import datetime

from backend.app.database import db
from backend.app.models import User


def _seed_admin(app, email="admin.security@test.com", password="adminpass"):
    with app.app_context():
        db.create_all()
        existing = User.query.filter_by(email=email).first()
        if not existing:
            admin = User(name="Security Admin", email=email, role="admin")
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()


def test_security_headers_are_set(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers


def test_login_returns_csrf_token(app):
    _seed_admin(app)
    client = app.test_client()

    response = client.post(
        "/api/users/login",
        json={"email": "admin.security@test.com", "password": "adminpass"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload.get("csrf_token"), str)
    assert len(payload["csrf_token"]) >= 20


def test_csrf_endpoint_requires_auth(client):
    response = client.get("/api/users/csrf")
    assert response.status_code == 401


def test_csrf_enforced_on_mutating_routes(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("DEMO_CREATE_DB", "1")
    monkeypatch.setenv("CSRF_PROTECT_ENABLED", "1")
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "20 per minute")

    from backend.app import create_app

    app = create_app()
    _seed_admin(app)

    client = app.test_client()
    login = client.post(
        "/api/users/login",
        json={"email": "admin.security@test.com", "password": "adminpass"},
    )
    assert login.status_code == 200
    token = login.get_json()["csrf_token"]

    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    missing_token = client.post(
        "/api/shifts",
        json={"date": tomorrow, "start_time": "09:00", "end_time": "10:00"},
    )
    assert missing_token.status_code == 400
    assert "csrf" in missing_token.get_json()["error"].lower()

    valid_token = client.post(
        "/api/shifts",
        json={"date": tomorrow, "start_time": "10:00", "end_time": "11:00"},
        headers={"X-CSRF-Token": token},
    )
    assert valid_token.status_code == 201


def test_login_rate_limit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("DEMO_CREATE_DB", "1")
    monkeypatch.setenv("CSRF_PROTECT_ENABLED", "1")
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "2 per minute")

    from backend.app import create_app

    app = create_app()
    _seed_admin(app)

    client = app.test_client()

    first = client.post(
        "/api/users/login",
        json={"email": "admin.security@test.com", "password": "wrong-pass"},
    )
    second = client.post(
        "/api/users/login",
        json={"email": "admin.security@test.com", "password": "wrong-pass"},
    )
    third = client.post(
        "/api/users/login",
        json={"email": "admin.security@test.com", "password": "wrong-pass"},
    )

    assert first.status_code in {401, 429}
    assert second.status_code in {401, 429}
    assert third.status_code == 429
