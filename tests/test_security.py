import json


def test_security_headers_present(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'DENY'
    assert response.headers.get('X-XSS-Protection') == '1; mode=block'
    assert 'default-src' in (response.headers.get('Content-Security-Policy') or '')


def test_password_policy_min_length_and_complexity(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.setenv('PASSWORD_MIN_LENGTH', '8')
    monkeypatch.setenv('PASSWORD_REQUIRE_COMPLEXITY', '1')

    from backend.app import create_app
    from backend.app.database import db
    from backend.app.models import User

    app = create_app()
    with app.app_context():
        db.create_all()
        admin = User(name='Admin', email='admin@security.test', role='admin')
        admin.set_password('AdminPass123')
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()

    login_resp = client.post(
        '/api/users/login',
        data=json.dumps({'email': 'admin@security.test', 'password': 'AdminPass123'}),
        content_type='application/json',
    )
    assert login_resp.status_code == 200

    weak_resp = client.post(
        '/api/users',
        data=json.dumps({
            'name': 'Weak User',
            'email': 'weak@security.test',
            'password': 'password',
            'role': 'student',
        }),
        content_type='application/json',
    )
    assert weak_resp.status_code == 400
    assert 'password' in (weak_resp.get_json() or {}).get('error', '').lower()

    strong_resp = client.post(
        '/api/users',
        data=json.dumps({
            'name': 'Strong User',
            'email': 'strong@security.test',
            'password': 'StrongPass123',
            'role': 'student',
        }),
        content_type='application/json',
    )
    assert strong_resp.status_code == 201


def test_csrf_required_for_authenticated_mutation(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.setenv('CSRF_PROTECT_ENABLED', '1')

    from backend.app import create_app
    from backend.app.database import db
    from backend.app.models import User

    app = create_app()
    with app.app_context():
        db.create_all()
        admin = User(name='Admin', email='admin@csrf.test', role='admin')
        admin.set_password('AdminPass123')
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()

    login_resp = client.post(
        '/api/users/login',
        data=json.dumps({'email': 'admin@csrf.test', 'password': 'AdminPass123'}),
        content_type='application/json',
    )
    assert login_resp.status_code == 200

    no_csrf_resp = client.post(
        '/api/users',
        data=json.dumps({
            'name': 'No Csrf',
            'email': 'nocsrf@security.test',
            'password': 'StrongPass123',
            'role': 'student',
        }),
        content_type='application/json',
    )
    assert no_csrf_resp.status_code == 400

    csrf_token = (login_resp.get_json() or {}).get('csrf_token')
    ok_resp = client.post(
        '/api/users',
        data=json.dumps({
            'name': 'With Csrf',
            'email': 'withcsrf@security.test',
            'password': 'StrongPass123',
            'role': 'student',
        }),
        headers={'X-CSRF-Token': csrf_token},
        content_type='application/json',
    )
    assert ok_resp.status_code == 201
