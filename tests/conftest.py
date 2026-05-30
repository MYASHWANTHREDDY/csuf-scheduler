import os
import pytest


@pytest.fixture(scope='session')
def test_env():
    # Configure a fast in-memory SQLite DB for tests and a deterministic secret
    os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
    os.environ.setdefault('FLASK_ENV', 'testing')
    os.environ.setdefault('SECRET_KEY', 'test-secret')
    os.environ.setdefault('DEMO_CREATE_DB', '1')
    yield


@pytest.fixture()
def app(test_env):
    # Import here so env vars are applied before create_app reads them
    from backend.app import create_app
    from backend.app.database import db

    app = create_app()
    # ensure tables exist
    with app.app_context():
        db.create_all()
    yield app
    # teardown
    with app.app_context():
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()
