import os
import json

import pytest


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    # Use an in-memory SQLite DB for tests
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('FLASK_ENV', 'testing')


def test_create_user_and_login():
    # import after env is set
    from backend.app import create_app
    from backend.app.database import db

    app = create_app()
    with app.app_context():
        db.create_all()
        # Seed admin for test
        from backend.app.models import User
        admin = User(name='Admin', email='admin@test.com', role='admin')
        admin.set_password('adminpass')
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()

    # Login as admin first
    login_r = client.post('/api/users/login', data=json.dumps({'email': 'admin@test.com', 'password': 'adminpass'}), content_type='application/json')
    assert login_r.status_code == 200

    # Create user as admin
    payload = {'first_name': 'T', 'last_name': 'User', 'email': 'tuser@example.com', 'password': 'securepw', 'role': 'student'}
    r = client.post('/api/users', data=json.dumps(payload), content_type='application/json')
    assert r.status_code == 201

    # Login
    r2 = client.post('/api/users/login', data=json.dumps({'email': 'tuser@example.com', 'password': 'securepw'}), content_type='application/json')
    assert r2.status_code == 200
    data = r2.get_json()
    assert data['email'] == 'tuser@example.com'


def test_shift_create_and_assign():
    from backend.app import create_app
    from backend.app.database import db
    from backend.app.models import User

    app = create_app()
    with app.app_context():
        db.create_all()
        # create admin user
        admin = User(name='Admin', email='admin@test.com', role='admin')
        admin.set_password('adminpw')
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()

    # login as admin
    r = client.post('/api/users/login', data=json.dumps({'email': 'admin@test.com', 'password': 'adminpw'}), content_type='application/json')
    assert r.status_code == 200

    # create shift
    import datetime
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    r2 = client.post('/api/shifts', data=json.dumps({'date': tomorrow, 'start_time': '09:00', 'end_time': '10:00'}), content_type='application/json')
    assert r2.status_code == 201
    sid = r2.get_json()['id']

    # create student
    r3 = client.post('/api/users', data=json.dumps({'first_name': 'S', 'last_name': 'Student', 'email': 's@test.com', 'password': 'studpass1', 'role': 'student'}), content_type='application/json')
    assert r3.status_code == 201
    uid = r3.get_json()['id']

    # assign shift
    r4 = client.post('/api/shifts/assign', data=json.dumps({'shift_id': sid, 'user_id': uid}), content_type='application/json')
    assert r4.status_code == 200


def test_swap_request_lifecycle():
    from backend.app import create_app
    from backend.app.database import db
    from backend.app.models import User

    app = create_app()
    with app.app_context():
        db.create_all()
        admin = User(name='Admin', email='admin@swap.test', role='admin')
        admin.set_password('adminpw')
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()

    login_admin = client.post('/api/users/login', data=json.dumps({'email': 'admin@swap.test', 'password': 'adminpw'}), content_type='application/json')
    assert login_admin.status_code == 200

    # create students
    s1 = client.post('/api/users', data=json.dumps({'first_name': 'Swap', 'last_name': 'One', 'email': 'swap1@swap.test', 'password': 'studpass1', 'role': 'student'}), content_type='application/json')
    s2 = client.post('/api/users', data=json.dumps({'first_name': 'Swap', 'last_name': 'Two', 'email': 'swap2@swap.test', 'password': 'studpass1', 'role': 'student'}), content_type='application/json')
    assert s1.status_code == 201
    assert s2.status_code == 201
    student_one_id = s1.get_json()['id']
    student_two_id = s2.get_json()['id']

    import datetime
    today = datetime.date.today()
    s1_shift = client.post('/api/shifts', data=json.dumps({'date': today.isoformat(), 'start_time': '08:00', 'end_time': '10:00'}), content_type='application/json')
    s2_shift = client.post('/api/shifts', data=json.dumps({'date': (today + datetime.timedelta(days=1)).isoformat(), 'start_time': '12:00', 'end_time': '14:00'}), content_type='application/json')
    assert s1_shift.status_code == 201
    assert s2_shift.status_code == 201
    s1_shift_id = s1_shift.get_json()['id']
    s2_shift_id = s2_shift.get_json()['id']

    assign_one = client.post('/api/shifts/assign', data=json.dumps({'shift_id': s1_shift_id, 'user_id': student_one_id}), content_type='application/json')
    assign_two = client.post('/api/shifts/assign', data=json.dumps({'shift_id': s2_shift_id, 'user_id': student_two_id}), content_type='application/json')
    assert assign_one.status_code == 200
    assert assign_two.status_code == 200

    client.post('/api/users/logout')

    student_login = client.post('/api/users/login', data=json.dumps({'email': 'swap1@swap.test', 'password': 'studpass1'}), content_type='application/json')
    assert student_login.status_code == 200
    swap_req = client.post('/api/swap_requests', data=json.dumps({'shift_id': s1_shift_id, 'target_shift_id': s2_shift_id}), content_type='application/json')
    assert swap_req.status_code == 201
    swap_id = swap_req.get_json()['id']
    client.post('/api/users/logout')

    student_login2 = client.post('/api/users/login', data=json.dumps({'email': 'swap2@swap.test', 'password': 'studpass1'}), content_type='application/json')
    assert student_login2.status_code == 200
    resp_accept = client.post(f'/api/swap_requests/{swap_id}/respond', data=json.dumps({'action': 'accept'}), content_type='application/json')
    assert resp_accept.status_code == 200
    client.post('/api/users/logout')

    supervisor_login = client.post('/api/users/login', data=json.dumps({'email': 'admin@swap.test', 'password': 'adminpw'}), content_type='application/json')
    assert supervisor_login.status_code == 200
    resp_approve = client.post(f'/api/swap_requests/{swap_id}/decide', data=json.dumps({'action': 'approve'}), content_type='application/json')
    assert resp_approve.status_code == 200

    all_shifts = client.get('/api/shifts?scope=all')
    assert all_shifts.status_code == 200
    shifts_by_id = {s['id']: s for s in all_shifts.get_json()}
    assert shifts_by_id[s1_shift_id]['assigned_user_id'] == student_two_id
    assert shifts_by_id[s2_shift_id]['assigned_user_id'] == student_one_id

    notifs = client.get('/api/notifications')
    assert notifs.status_code == 200
    assert len(notifs.get_json()) >= 1


def test_student_only_sees_assigned_shifts():
    from backend.app import create_app
    from backend.app.database import db
    from backend.app.models import User

    app = create_app()
    with app.app_context():
        db.create_all()
        admin = User(name='Admin', email='admin@filter.test', role='admin')
        admin.set_password('adminpw')
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()

    # Admin creates shifts and users
    login = client.post('/api/users/login', data=json.dumps({'email': 'admin@filter.test', 'password': 'adminpw'}), content_type='application/json')
    assert login.status_code == 200

    import datetime
    today = datetime.date.today()
    shift_one_date = (today + datetime.timedelta(days=1)).isoformat()
    shift_two_date = (today + datetime.timedelta(days=2)).isoformat()

    shift_one = client.post('/api/shifts', data=json.dumps({'date': shift_one_date, 'start_time': '08:00', 'end_time': '10:00'}), content_type='application/json')
    assert shift_one.status_code == 201
    shift_two = client.post('/api/shifts', data=json.dumps({'date': shift_two_date, 'start_time': '12:00', 'end_time': '14:00'}), content_type='application/json')
    assert shift_two.status_code == 201

    shift_one_id = shift_one.get_json()['id']
    shift_two_id = shift_two.get_json()['id']

    student_one = client.post('/api/users', data=json.dumps({'first_name': 'Student', 'last_name': 'One', 'email': 's1@filter.test', 'password': 'studpass1', 'role': 'student'}), content_type='application/json')
    assert student_one.status_code == 201
    student_two = client.post('/api/users', data=json.dumps({'first_name': 'Student', 'last_name': 'Two', 'email': 's2@filter.test', 'password': 'studpass1', 'role': 'student'}), content_type='application/json')
    assert student_two.status_code == 201

    student_one_id = student_one.get_json()['id']
    student_two_id = student_two.get_json()['id']

    assign_one = client.post('/api/shifts/assign', data=json.dumps({'shift_id': shift_one_id, 'user_id': student_one_id}), content_type='application/json')
    assert assign_one.status_code == 200
    assign_two = client.post('/api/shifts/assign', data=json.dumps({'shift_id': shift_two_id, 'user_id': student_two_id}), content_type='application/json')
    assert assign_two.status_code == 200

    client.post('/api/users/logout')

    student_login = client.post('/api/users/login', data=json.dumps({'email': 's1@filter.test', 'password': 'studpass1'}), content_type='application/json')
    assert student_login.status_code == 200

    resp = client.get('/api/shifts')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload) == 1
    assert payload[0]['assigned_user_id'] == student_one_id

    # Even a student should still be able to fetch the full schedule for display
    resp_all = client.get('/api/shifts?scope=all')
    assert resp_all.status_code == 200
    payload_all = resp_all.get_json()
    assert len(payload_all) == 2
