"""RBAC (Role-Based Access Control) tests for scheduler endpoints."""
import pytest
from backend.app import create_app
from backend.app.database import db
from backend.app.models import User, Shift
from datetime import date, datetime, time


@pytest.fixture
def app():
    """Create test app with in-memory SQLite."""
    import os
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_app()
    app.config['TESTING'] = True
    
    with app.app_context():
        db.create_all()
        # Create test users
        admin = User(name='Admin', email='admin@test.com', role='admin')
        admin.set_password('password')
        supervisor = User(name='Supervisor', email='sup@test.com', role='supervisor')
        supervisor.set_password('password')
        student = User(name='Student', email='student@test.com', role='student')
        student.set_password('password')
        db.session.add_all([admin, supervisor, student])
        db.session.commit()
    
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


class TestUserEndpointsRBAC:
    """Test user list/create endpoints require auth and role."""
    
    def test_list_users_unauthenticated(self, client):
        """GET /api/users without auth should return 401."""
        resp = client.get('/api/users')
        assert resp.status_code == 401
        assert 'not authenticated' in resp.get_json()['error']
    
    def test_list_users_as_student(self, client):
        """GET /api/users as student should return 200."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        resp = client.get('/api/users')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert isinstance(payload, list)
        assert len(payload) >= 3
    
    def test_list_users_as_admin(self, client):
        """GET /api/users as admin should return 200."""
        client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
        resp = client.get('/api/users')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)
        assert len(resp.get_json()) >= 3
    
    def test_create_user_unauthenticated(self, client):
        """POST /api/users without auth should return 401."""
        resp = client.post('/api/users', json={'name': 'New', 'email': 'new@test.com', 'password': 'pass12345'})
        assert resp.status_code == 401
    
    def test_create_user_as_student(self, client):
        """POST /api/users as student should return 403."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        resp = client.post('/api/users', json={'name': 'New', 'email': 'new@test.com', 'password': 'pass12345'})
        assert resp.status_code == 403
    
    def test_create_user_as_supervisor(self, client):
        """POST /api/users as supervisor should return 201."""
        client.post('/api/users/login', json={'email': 'sup@test.com', 'password': 'password'})
        resp = client.post('/api/users', json={'name': 'New', 'email': 'new2@test.com', 'password': 'pass12345'})
        assert resp.status_code == 201
        assert 'id' in resp.get_json()


class TestShiftEndpointsRBAC:
    """Test shift create/assign/delete endpoints require supervisor/admin."""
    
    def test_create_shift_unauthenticated(self, client):
        """POST /api/shifts without auth should return 401."""
        resp = client.post('/api/shifts', json={'date': '2025-12-20', 'start_time': '09:00', 'end_time': '11:00'})
        assert resp.status_code == 401
    
    def test_create_shift_as_student(self, client):
        """POST /api/shifts as student should return 403."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        resp = client.post('/api/shifts', json={'date': '2025-12-20', 'start_time': '09:00', 'end_time': '11:00'})
        assert resp.status_code == 403
    
    def test_create_shift_as_admin(self, client):
        """POST /api/shifts as admin should return 201."""
        client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
        resp = client.post('/api/shifts', json={'date': '2025-12-20', 'start_time': '09:00', 'end_time': '11:00'})
        assert resp.status_code == 201
    
    def test_assign_shift_as_student(self, client):
        """POST /api/shifts/assign as student should return 403."""
        # Create a shift as admin first
        client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
        shift_resp = client.post('/api/shifts', json={'date': '2025-12-20', 'start_time': '09:00', 'end_time': '11:00'})
        shift_id = shift_resp.get_json()['id']
        client.post('/api/users/logout', json={})
        
        # Try to assign as student
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        resp = client.post('/api/shifts/assign', json={'shift_id': shift_id, 'user_id': 2})
        assert resp.status_code == 403
    
    def test_delete_shift_as_student(self, client):
        """DELETE /api/shifts/<id> as student should return 403."""
        # Create shift as admin
        client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
        shift_resp = client.post('/api/shifts', json={'date': '2025-12-20', 'start_time': '09:00', 'end_time': '11:00'})
        shift_id = shift_resp.get_json()['id']
        client.post('/api/users/logout', json={})
        
        # Try to delete as student
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        resp = client.delete(f'/api/shifts/{shift_id}')
        assert resp.status_code == 403
    
    def test_auto_assign_as_student(self, client):
        """POST /api/shifts/auto-assign as student should return 403."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        resp = client.post('/api/shifts/auto-assign', json={})
        assert resp.status_code == 403
