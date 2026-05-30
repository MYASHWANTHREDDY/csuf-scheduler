import json
import datetime


def test_time_adjustment_review_and_resubmit_flow():
    from backend.app import create_app
    from backend.app.database import db
    from backend.app.models import User

    app = create_app()
    with app.app_context():
        db.create_all()
        admin = User(name='Admin', email='admin@time.test', role='admin')
        admin.set_password('adminpw')
        student = User(name='Student', email='student@time.test', role='student')
        student.set_password('studpw')
        db.session.add_all([admin, student])
        db.session.commit()

    client = app.test_client()

    login_admin = client.post('/api/users/login', data=json.dumps({'email': 'admin@time.test', 'password': 'adminpw'}), content_type='application/json')
    assert login_admin.status_code == 200

    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    shift_resp = client.post('/api/shifts', data=json.dumps({'date': tomorrow, 'start_time': '12:00', 'end_time': '14:00'}), content_type='application/json')
    assert shift_resp.status_code == 201
    shift_id = shift_resp.get_json()['id']

    users_resp = client.get('/api/users')
    student_id = next(u['id'] for u in users_resp.get_json() if u['email'] == 'student@time.test')
    assign_resp = client.post('/api/shifts/assign', data=json.dumps({'shift_id': shift_id, 'user_id': student_id}), content_type='application/json')
    assert assign_resp.status_code == 200

    client.post('/api/users/logout')

    login_student = client.post('/api/users/login', data=json.dumps({'email': 'student@time.test', 'password': 'studpw'}), content_type='application/json')
    assert login_student.status_code == 200

    submit_one = client.post('/api/time_adjustments', data=json.dumps({
        'shift_id': shift_id,
        'actual_start': '12:00',
        'actual_end': '16:30',
        'reason': 'Covered extended patrol after incident.'
    }), content_type='application/json')
    assert submit_one.status_code == 201
    request_one_id = submit_one.get_json()['id']

    my_requests_one = client.get('/api/time_adjustments/my-requests')
    assert my_requests_one.status_code == 200
    first_item = next(i for i in my_requests_one.get_json() if i['id'] == request_one_id)
    assert first_item['worked_minutes'] == 270

    client.post('/api/users/logout')
    client.post('/api/users/login', data=json.dumps({'email': 'admin@time.test', 'password': 'adminpw'}), content_type='application/json')

    pending_before = client.get('/api/time_adjustments?status=pending')
    assert pending_before.status_code == 200
    assert any(i['id'] == request_one_id for i in pending_before.get_json())

    approve_resp = client.post(f'/api/time_adjustments/{request_one_id}/review', data=json.dumps({
        'action': 'approve',
        'reviewer_notes': 'Approved - verified with log.'
    }), content_type='application/json')
    assert approve_resp.status_code == 200

    client.post('/api/users/logout')
    client.post('/api/users/login', data=json.dumps({'email': 'student@time.test', 'password': 'studpw'}), content_type='application/json')

    submit_two = client.post('/api/time_adjustments', data=json.dumps({
        'shift_id': shift_id,
        'actual_start': '12:15',
        'actual_end': '18:00',
        'reason': 'Stayed late for report handoff.'
    }), content_type='application/json')
    assert submit_two.status_code == 201
    request_two_id = submit_two.get_json()['id']

    client.post('/api/users/logout')
    client.post('/api/users/login', data=json.dumps({'email': 'admin@time.test', 'password': 'adminpw'}), content_type='application/json')

    reject_resp = client.post(f'/api/time_adjustments/{request_two_id}/review', data=json.dumps({
        'action': 'reject',
        'reviewer_notes': 'Please include exact end-of-shift duty details.'
    }), content_type='application/json')
    assert reject_resp.status_code == 200

    client.post('/api/users/logout')
    client.post('/api/users/login', data=json.dumps({'email': 'student@time.test', 'password': 'studpw'}), content_type='application/json')

    my_requests_two = client.get('/api/time_adjustments/my-requests')
    assert my_requests_two.status_code == 200
    request_items = my_requests_two.get_json()

    approved_item = next(i for i in request_items if i['id'] == request_one_id)
    rejected_item = next(i for i in request_items if i['id'] == request_two_id)
    assert approved_item['status'] == 'approved'
    assert approved_item['reviewer_notes'] == 'Approved - verified with log.'
    assert rejected_item['status'] == 'rejected'
    assert rejected_item['reviewer_notes'] == 'Please include exact end-of-shift duty details.'

    resubmit_resp = client.post('/api/time_adjustments', data=json.dumps({
        'shift_id': shift_id,
        'actual_start': rejected_item['actual_start'],
        'actual_end': rejected_item['actual_end'],
        'reason': 'Stayed late for report handoff and incident documentation.',
        'resubmit_of_id': request_two_id
    }), content_type='application/json')
    assert resubmit_resp.status_code == 201
    resubmitted_id = resubmit_resp.get_json()['id']

    final_list_resp = client.get('/api/time_adjustments/my-requests')
    final_items = final_list_resp.get_json()
    assert any(i['id'] == request_two_id and i['status'] == 'rejected' for i in final_items)
    assert any(i['id'] == resubmitted_id and i['status'] == 'pending' for i in final_items)


def test_supervisor_rejection_reason_is_optional():
    from backend.app import create_app
    from backend.app.database import db
    from backend.app.models import User

    app = create_app()
    with app.app_context():
        db.create_all()
        supervisor = User(name='Supervisor', email='supervisor@time.test', role='supervisor')
        supervisor.set_password('suppw')
        student = User(name='Student', email='student2@time.test', role='student')
        student.set_password('studpw')
        db.session.add_all([supervisor, student])
        db.session.commit()

    client = app.test_client()
    client.post('/api/users/login', data=json.dumps({'email': 'supervisor@time.test', 'password': 'suppw'}), content_type='application/json')

    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    shift_resp = client.post('/api/shifts', data=json.dumps({'date': tomorrow, 'start_time': '09:00', 'end_time': '10:00'}), content_type='application/json')
    shift_id = shift_resp.get_json()['id']
    users_resp = client.get('/api/users')
    student_id = next(u['id'] for u in users_resp.get_json() if u['email'] == 'student2@time.test')
    client.post('/api/shifts/assign', data=json.dumps({'shift_id': shift_id, 'user_id': student_id}), content_type='application/json')

    client.post('/api/users/logout')
    client.post('/api/users/login', data=json.dumps({'email': 'student2@time.test', 'password': 'studpw'}), content_type='application/json')
    submit_resp = client.post('/api/time_adjustments', data=json.dumps({
        'shift_id': shift_id,
        'actual_start': '09:00',
        'actual_end': '10:15',
        'reason': 'Late closeout.'
    }), content_type='application/json')
    request_id = submit_resp.get_json()['id']

    client.post('/api/users/logout')
    client.post('/api/users/login', data=json.dumps({'email': 'supervisor@time.test', 'password': 'suppw'}), content_type='application/json')
    reject_resp = client.post(f'/api/time_adjustments/{request_id}/review', data=json.dumps({
        'action': 'reject'
    }), content_type='application/json')
    assert reject_resp.status_code == 200

    client.post('/api/users/logout')
    client.post('/api/users/login', data=json.dumps({'email': 'student2@time.test', 'password': 'studpw'}), content_type='application/json')
    my_requests = client.get('/api/time_adjustments/my-requests').get_json()
    rejected_item = next(i for i in my_requests if i['id'] == request_id)
    assert rejected_item['status'] == 'rejected'
    assert rejected_item['reviewer_notes'] is None