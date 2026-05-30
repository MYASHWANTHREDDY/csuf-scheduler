import json


def test_security_headers_present():
    from backend.app import create_app

    app = create_app()
    client = app.test_client()

    response = client.get('/')
    assert response.status_code == 200
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'DENY'
    assert response.headers.get('X-XSS-Protection') == '1; mode=block'


def test_password_policy_enforced(monkeypatch):
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
        admin = User(name='Admin', email='admin@backend.security.test', role='admin')
        admin.set_password('AdminPass123')
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()
    login = client.post(
        '/api/users/login',
        data=json.dumps({'email': 'admin@backend.security.test', 'password': 'AdminPass123'}),
        content_type='application/json',
    )
    assert login.status_code == 200

    weak = client.post(
        '/api/users',
        data=json.dumps({
            'name': 'Weak User',
            'email': 'weak@backend.security.test',
            'password': 'weakpass',
            'role': 'student',
        }),
        content_type='application/json',
    )
    assert weak.status_code == 400

    strong = client.post(
        '/api/users',
        data=json.dumps({
            'name': 'Strong User',
            'email': 'strong@backend.security.test',
            'password': 'StrongPass123',
            'role': 'student',
        }),
        headers={'X-CSRF-Token': login.get_json().get('csrf_token')},
        content_type='application/json',
    )
    assert strong.status_code == 201
