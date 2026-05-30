"""Tests for FR-2: Submit Availability feature.

Students should be able to:
- Submit availability blocks (date/time ranges when they're free)
- View their submitted availability
- Delete/edit availability (FR-2b)

Key constraints:
- Only authenticated users can submit availability
- Availability prevents out-of-window assignment (enforced via conflict detection)
"""
import pytest
from datetime import date, datetime, timedelta
from backend.app import create_app
from backend.app.database import db
from backend.app.models import User, Availability, Shift


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
        student = User(name='Student One', email='student@test.com', role='student')
        student.set_password('password')
        admin = User(name='Admin', email='admin@test.com', role='admin')
        admin.set_password('password')
        db.session.add_all([student, admin])
        db.session.commit()
    
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


class TestAvailabilityCreation:
    """Test FR-2: Submit Availability"""
    
    def test_create_availability_unauthenticated(self, client):
        """POST /api/availability without auth should return 401."""
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00',
            'end_time': '17:00'
        })
        assert resp.status_code == 401
        assert 'not authenticated' in resp.get_json()['error']
    
    def test_create_availability_as_student(self, client):
        """POST /api/availability as student should return 201."""
        # Login
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Submit availability
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00',
            'end_time': '17:00'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'id' in data
        assert isinstance(data['id'], int)
    
    def test_create_availability_with_admin(self, client):
        """POST /api/availability as admin should also work (self-submission)."""
        client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
        
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00',
            'end_time': '17:00'
        })
        assert resp.status_code == 201
    
    def test_create_availability_invalid_format(self, client):
        """POST /api/availability with invalid date/time format should return 400."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Invalid date format
        resp = client.post('/api/availability', json={
            'date': '20/12/2025',  # Wrong format
            'start_time': '09:00',
            'end_time': '17:00'
        })
        assert resp.status_code == 400
        assert 'invalid date/time format' in resp.get_json()['error']
    
    def test_create_availability_missing_fields(self, client):
        """POST /api/availability without required fields should return 400."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Missing end_time
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00'
        })
        assert resp.status_code == 400
        assert 'required' in resp.get_json()['error']
    
    def test_create_availability_invalid_time_range(self, client):
        """POST /api/availability with end_time <= start_time should return 400."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '17:00',
            'end_time': '09:00'  # End before start
        })
        assert resp.status_code == 400
        assert 'end_time must be after start_time' in resp.get_json()['error']


class TestAvailabilityRetrieval:
    """Test retrieving availability"""
    
    def test_list_own_availability(self, client):
        """GET /api/availability should return current user's availability."""
        # Login and create availability
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00',
            'end_time': '17:00'
        })
        client.post('/api/availability', json={
            'date': '2025-12-21',
            'start_time': '10:00',
            'end_time': '18:00'
        })
        
        # Retrieve availability
        resp = client.get('/api/availability')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]['date'] == '2025-12-20'
        assert data[0]['start_time'] == '09:00'
        assert data[0]['end_time'] == '17:00'
    
    def test_list_availability_unauthenticated(self, client):
        """GET /api/availability without auth when not specifying user_id should return 401."""
        resp = client.get('/api/availability')
        assert resp.status_code == 401
    
    def test_list_other_user_availability_as_admin(self, client):
        """GET /api/availability?user_id=X as admin should return 200."""
        # Create student with availability
        with client:
            client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
            resp = client.post('/api/availability', json={
                'date': '2025-12-20',
                'start_time': '09:00',
                'end_time': '17:00'
            })
            student_avail_id = resp.get_json()['id']
            client.post('/api/users/logout', json={})
            
            # Login as admin
            client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
            
            # Query student's availability
            resp = client.get('/api/availability?user_id=1')
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) == 1
            assert data[0]['id'] == student_avail_id
    
    def test_list_other_user_availability_as_student(self, client):
        """GET /api/availability?user_id=X as student should return 403."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Try to query another user's availability
        resp = client.get('/api/availability?user_id=2')
        assert resp.status_code == 403


class TestAvailabilityDelete:
    """Test FR-2b: Delete Availability"""
    
    def test_delete_own_availability(self, client):
        """DELETE /api/availability/<id> as owner should return 200."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Create availability
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00',
            'end_time': '17:00'
        })
        avail_id = resp.get_json()['id']
        
        # Delete it
        resp = client.delete(f'/api/availability/{avail_id}')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        
        # Verify it's gone
        resp = client.get('/api/availability')
        data = resp.get_json()
        assert len(data) == 0
    
    def test_delete_availability_unauthenticated(self, client):
        """DELETE /api/availability/<id> without auth should return 401."""
        resp = client.delete('/api/availability/1')
        assert resp.status_code == 401
    
    def test_delete_nonexistent_availability(self, client):
        """DELETE /api/availability/<id> with nonexistent id should return 404."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        resp = client.delete('/api/availability/9999')
        assert resp.status_code == 404
        assert 'not found' in resp.get_json()['error']
    
    def test_delete_other_user_availability_as_student(self, client):
        """DELETE /api/availability/<id> of another user as student should return 403."""
        # Create availability as admin
        with client:
            client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
            resp = client.post('/api/availability', json={
                'date': '2025-12-20',
                'start_time': '09:00',
                'end_time': '17:00'
            })
            admin_avail_id = resp.get_json()['id']
            client.post('/api/users/logout', json={})
            
            # Try to delete as student
            client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
            resp = client.delete(f'/api/availability/{admin_avail_id}')
            assert resp.status_code == 403
            assert 'can only delete your own' in resp.get_json()['error']
    
    def test_delete_other_user_availability_as_admin(self, client):
        """DELETE /api/availability/<id> of another user as admin should return 200."""
        # Create availability as student
        with client:
            client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
            resp = client.post('/api/availability', json={
                'date': '2025-12-20',
                'start_time': '09:00',
                'end_time': '17:00'
            })
            student_avail_id = resp.get_json()['id']
            client.post('/api/users/logout', json={})
            
            # Delete as admin
            client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
            resp = client.delete(f'/api/availability/{student_avail_id}')
            assert resp.status_code == 200


class TestAvailabilityUpdate:
    """Test FR-2b: Update/Edit Availability"""
    
    def test_update_own_availability(self, client):
        """PUT /api/availability/<id> as owner should return 200."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Create availability
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00',
            'end_time': '17:00'
        })
        avail_id = resp.get_json()['id']
        
        # Update it
        resp = client.put(f'/api/availability/{avail_id}', json={
            'date': '2025-12-21',
            'start_time': '10:00',
            'end_time': '18:00'
        })
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        
        # Verify changes
        resp = client.get('/api/availability')
        data = resp.get_json()
        assert data[0]['date'] == '2025-12-21'
        assert data[0]['start_time'] == '10:00'
        assert data[0]['end_time'] == '18:00'
    
    def test_update_availability_unauthenticated(self, client):
        """PUT /api/availability/<id> without auth should return 401."""
        resp = client.put('/api/availability/1', json={
            'date': '2025-12-21',
            'start_time': '10:00',
            'end_time': '18:00'
        })
        assert resp.status_code == 401
    
    def test_update_nonexistent_availability(self, client):
        """PUT /api/availability/<id> with nonexistent id should return 404."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        resp = client.put('/api/availability/9999', json={
            'date': '2025-12-21',
            'start_time': '10:00',
            'end_time': '18:00'
        })
        assert resp.status_code == 404
        assert 'not found' in resp.get_json()['error']
    
    def test_update_with_invalid_time_range(self, client):
        """PUT /api/availability/<id> with invalid time range should return 400."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        resp = client.post('/api/availability', json={
            'date': '2025-12-20',
            'start_time': '09:00',
            'end_time': '17:00'
        })
        avail_id = resp.get_json()['id']
        
        resp = client.put(f'/api/availability/{avail_id}', json={
            'date': '2025-12-21',
            'start_time': '18:00',
            'end_time': '10:00'  # Invalid: end before start
        })
        assert resp.status_code == 400
        assert 'end_time must be after start_time' in resp.get_json()['error']
    
    def test_update_other_user_availability_as_student(self, client):
        """PUT /api/availability/<id> of another user as student should return 403."""
        # Create availability as admin
        with client:
            client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
            resp = client.post('/api/availability', json={
                'date': '2025-12-20',
                'start_time': '09:00',
                'end_time': '17:00'
            })
            admin_avail_id = resp.get_json()['id']
            client.post('/api/users/logout', json={})
            
            # Try to update as student
            client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
            resp = client.put(f'/api/availability/{admin_avail_id}', json={
                'date': '2025-12-21',
                'start_time': '10:00',
                'end_time': '18:00'
            })
            assert resp.status_code == 403
            assert 'can only edit your own' in resp.get_json()['error']
    
    def test_update_other_user_availability_as_admin(self, client):
        """PUT /api/availability/<id> of another user as admin should return 200."""
        # Create availability as student
        with client:
            client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
            resp = client.post('/api/availability', json={
                'date': '2025-12-20',
                'start_time': '09:00',
                'end_time': '17:00'
            })
            student_avail_id = resp.get_json()['id']
            client.post('/api/users/logout', json={})
            
            # Update as admin
            client.post('/api/users/login', json={'email': 'admin@test.com', 'password': 'password'})
            resp = client.put(f'/api/availability/{student_avail_id}', json={
                'date': '2025-12-21',
                'start_time': '10:00',
                'end_time': '18:00'
            })
            assert resp.status_code == 200


class TestAvailabilityAcceptanceCriteria:
    """Test FR-2 acceptance criteria: saved blocks visible, prevents out-of-window assignment"""
    
    def test_availability_saved_and_visible(self, client):
        """Submitted availability should be saved to DB and visible in list."""
        with client:
            client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
            
            # Submit availability
            avail_data = {
                'date': '2025-12-20',
                'start_time': '09:00',
                'end_time': '17:00'
            }
            resp = client.post('/api/availability', json=avail_data)
            assert resp.status_code == 201
            avail_id = resp.get_json()['id']
            
            # Retrieve and verify
            resp = client.get('/api/availability')
            data = resp.get_json()
            assert len(data) == 1
            assert data[0]['id'] == avail_id
            assert data[0]['date'] == avail_data['date']
            assert data[0]['start_time'] == avail_data['start_time']
            assert data[0]['end_time'] == avail_data['end_time']
    
    def test_multiple_availability_blocks(self, client):
        """Student should be able to submit multiple availability blocks."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Submit multiple blocks
        blocks = [
            {'date': '2025-12-20', 'start_time': '09:00', 'end_time': '12:00'},
            {'date': '2025-12-20', 'start_time': '13:00', 'end_time': '17:00'},  # afternoon
            {'date': '2025-12-21', 'start_time': '10:00', 'end_time': '18:00'},
        ]
        
        for block in blocks:
            resp = client.post('/api/availability', json=block)
            assert resp.status_code == 201
        
        # Verify all saved
        resp = client.get('/api/availability')
        data = resp.get_json()
        assert len(data) == 3
        assert data[0]['date'] == '2025-12-20'
        assert data[2]['date'] == '2025-12-21'


class TestRecurringAvailability:
    """Test weekly recurring availability feature"""
    
    def test_create_recurring_availability(self, client):
        """POST /api/availability with is_recurring=true should create weekly recurring availability."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Create recurring availability for Mondays
        resp = client.post('/api/availability', json={
            'is_recurring': True,
            'day_of_week': 0,  # Monday
            'start_time': '09:00',
            'end_time': '17:00',
            'effective_until': '2026-05-15'
        })
        assert resp.status_code == 201
        avail_id = resp.get_json()['id']
        
        # Verify it's saved correctly
        resp = client.get('/api/availability')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['id'] == avail_id
        assert data[0]['is_recurring'] is True
        assert data[0]['day_of_week'] == 0
        assert data[0]['start_time'] == '09:00'
        assert data[0]['end_time'] == '17:00'
        assert data[0]['effective_until'] == '2026-05-15'
        assert 'date' not in data[0] or data[0]['date'] is None
    
    def test_create_recurring_without_day_of_week(self, client):
        """POST /api/availability with is_recurring=true but no day_of_week should return 400."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        resp = client.post('/api/availability', json={
            'is_recurring': True,
            'start_time': '09:00',
            'end_time': '17:00'
        })
        assert resp.status_code == 400
        assert 'day_of_week is required' in resp.get_json()['error']
    
    def test_create_recurring_invalid_day_of_week(self, client):
        """POST /api/availability with invalid day_of_week should return 400."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        resp = client.post('/api/availability', json={
            'is_recurring': True,
            'day_of_week': 7,  # Invalid: should be 0-6
            'start_time': '09:00',
            'end_time': '17:00'
        })
        assert resp.status_code == 400
        assert 'day_of_week must be' in resp.get_json()['error']
    
    def test_create_weekly_schedule_for_semester(self, client):
        """Student should be able to set up weekly recurring availability for entire semester."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Semester end date
        semester_end = '2026-05-15'
        
        # Set recurring availability for Monday, Wednesday, Friday
        days = [
            {'day': 0, 'day_name': 'Monday', 'start': '09:00', 'end': '12:00'},
            {'day': 2, 'day_name': 'Wednesday', 'start': '13:00', 'end': '17:00'},
            {'day': 4, 'day_name': 'Friday', 'start': '09:00', 'end': '17:00'},
        ]
        
        for day_info in days:
            resp = client.post('/api/availability', json={
                'is_recurring': True,
                'day_of_week': day_info['day'],
                'start_time': day_info['start'],
                'end_time': day_info['end'],
                'effective_until': semester_end
            })
            assert resp.status_code == 201
        
        # Verify all saved
        resp = client.get('/api/availability')
        data = resp.get_json()
        assert len(data) == 3
        assert all(a['is_recurring'] for a in data)
        assert all(a['effective_until'] == semester_end for a in data)
        day_of_weeks = [a['day_of_week'] for a in data]
        assert 0 in day_of_weeks  # Monday
        assert 2 in day_of_weeks  # Wednesday
        assert 4 in day_of_weeks  # Friday
    
    def test_recurring_without_effective_until(self, client):
        """Recurring availability without effective_until should work (ongoing)."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        resp = client.post('/api/availability', json={
            'is_recurring': True,
            'day_of_week': 1,  # Tuesday
            'start_time': '10:00',
            'end_time': '14:00'
        })
        assert resp.status_code == 201
        
        resp = client.get('/api/availability')
        data = resp.get_json()
        assert data[0]['effective_until'] is None
    
    def test_delete_recurring_availability(self, client):
        """Should be able to delete recurring availability."""
        client.post('/api/users/login', json={'email': 'student@test.com', 'password': 'password'})
        
        # Create recurring
        resp = client.post('/api/availability', json={
            'is_recurring': True,
            'day_of_week': 0,
            'start_time': '09:00',
            'end_time': '17:00'
        })
        avail_id = resp.get_json()['id']
        
        # Delete it
        resp = client.delete(f'/api/availability/{avail_id}')
        assert resp.status_code == 200
        
        # Verify gone
        resp = client.get('/api/availability')
        assert len(resp.get_json()) == 0

