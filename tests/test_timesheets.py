import datetime
import json


def _login(client, email, password):
    return client.post('/api/users/login', data=json.dumps({'email': email, 'password': password}), content_type='application/json')


def test_timesheet_clarification_pauses_approval_and_requires_response(app, client):
    from backend.app.database import db
    from backend.app.models import User

    with app.app_context():
        admin = User(name='Admin TS', email='admin.timesheet@test.com', role='admin')
        admin.set_password('adminpw')
        supervisor = User(name='Supervisor TS', email='sup.timesheet@test.com', role='supervisor')
        supervisor.set_password('suppw')
        student = User(name='Student TS', email='student.timesheet@test.com', role='student')
        student.set_password('studpw')
        db.session.add_all([admin, supervisor, student])
        db.session.commit()

    assert _login(client, 'admin.timesheet@test.com', 'adminpw').status_code == 200

    today = datetime.date.today()
    shift_date = (today - datetime.timedelta(days=1)).isoformat()
    create_shift = client.post('/api/shifts', data=json.dumps({'date': shift_date, 'start_time': '08:00', 'end_time': '12:00'}), content_type='application/json')
    assert create_shift.status_code == 201
    shift_id = create_shift.get_json()['id']

    users = client.get('/api/users').get_json()
    student_id = next(u['id'] for u in users if u['email'] == 'student.timesheet@test.com')
    assert client.post('/api/shifts/assign', data=json.dumps({'shift_id': shift_id, 'user_id': student_id}), content_type='application/json').status_code == 200

    pay_period_resp = client.post('/api/timesheets/pay-periods', data=json.dumps({
        'label': 'Pay Period 1 (Mar 1-31, 2026)',
        'start_date': (today - datetime.timedelta(days=10)).isoformat(),
        'end_date': (today + datetime.timedelta(days=10)).isoformat(),
        'submission_deadline': datetime.datetime.utcnow().isoformat(),
    }), content_type='application/json')
    assert pay_period_resp.status_code == 201
    pay_period_id = pay_period_resp.get_json()['id']

    client.post('/api/users/logout')
    assert _login(client, 'student.timesheet@test.com', 'studpw').status_code == 200

    my_ts = client.get(f'/api/timesheets/my?pay_period_id={pay_period_id}')
    assert my_ts.status_code == 200
    ts_data = my_ts.get_json()
    assert ts_data['status'] == 'draft'
    assert len(ts_data['lines']) >= 1

    manual_add = client.post(f"/api/timesheets/{ts_data['id']}/lines", data=json.dumps({
        'work_date': shift_date,
        'start_time': '13:00',
        'end_time': '14:00',
        'note': 'Manual patrol extension',
    }), content_type='application/json')
    assert manual_add.status_code == 201

    submit_resp = client.post(f"/api/timesheets/{ts_data['id']}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.get_json()['status'] == 'submitted'

    client.post('/api/users/logout')
    assert _login(client, 'sup.timesheet@test.com', 'suppw').status_code == 200

    review = client.get(f'/api/timesheets/review?pay_period_id={pay_period_id}')
    assert review.status_code == 200
    groups = review.get_json()
    assert groups and groups[0]['timesheets']
    ts_id = groups[0]['timesheets'][0]['id']

    ask_clarification = client.post(f'/api/timesheets/{ts_id}/comments', data=json.dumps({
        'message': 'Please explain your manual line and confirm end time.',
        'requires_response': True,
    }), content_type='application/json')
    assert ask_clarification.status_code == 201

    approve_while_pending = client.post(f'/api/timesheets/{ts_id}/approve')
    assert approve_while_pending.status_code == 409

    client.post('/api/users/logout')
    assert _login(client, 'student.timesheet@test.com', 'studpw').status_code == 200

    response_comment = client.post(f'/api/timesheets/{ts_id}/comments', data=json.dumps({
        'message': 'Manual line was required due to extra post check.',
        'requires_response': False,
    }), content_type='application/json')
    assert response_comment.status_code == 201

    client.post('/api/users/logout')
    assert _login(client, 'sup.timesheet@test.com', 'suppw').status_code == 200

    approve_after_response = client.post(f'/api/timesheets/{ts_id}/approve')
    assert approve_after_response.status_code == 200
    assert approve_after_response.get_json()['status'] == 'approved'

    client.post('/api/users/logout')
    assert _login(client, 'admin.timesheet@test.com', 'adminpw').status_code == 200

    finalize = client.post(f'/api/timesheets/pay-periods/{pay_period_id}/finalize')
    assert finalize.status_code == 200
    assert finalize.get_json()['status'] == 'finalized'


def test_bulk_approve_submitted_timesheets_skips_non_submitted(app, client):
    from backend.app.database import db
    from backend.app.models import User

    with app.app_context():
        supervisor = User(name='Supervisor Bulk', email='sup.bulk@test.com', role='supervisor')
        supervisor.set_password('suppw')
        s1 = User(name='Student One', email='student.one@test.com', role='student')
        s1.set_password('studpw')
        s2 = User(name='Student Two', email='student.two@test.com', role='student')
        s2.set_password('studpw')
        db.session.add_all([supervisor, s1, s2])
        db.session.commit()

    assert _login(client, 'sup.bulk@test.com', 'suppw').status_code == 200

    today = datetime.date.today()
    pp = client.post('/api/timesheets/pay-periods', data=json.dumps({
        'label': 'Pay Period 2 (Apr 1-30, 2026)',
        'start_date': (today - datetime.timedelta(days=2)).isoformat(),
        'end_date': (today + datetime.timedelta(days=2)).isoformat(),
    }), content_type='application/json')
    assert pp.status_code == 201
    pay_period_id = pp.get_json()['id']

    users = client.get('/api/users').get_json()
    ids = {u['email']: u['id'] for u in users}

    for idx, email in enumerate(['student.one@test.com', 'student.two@test.com']):
        shift = client.post('/api/shifts', data=json.dumps({
            'date': today.isoformat(),
            'start_time': f'0{8 + idx}:00',
            'end_time': f'1{2 + idx}:00',
        }), content_type='application/json')
        assert shift.status_code == 201
        sid = shift.get_json()['id']
        assert client.post('/api/shifts/assign', data=json.dumps({'shift_id': sid, 'user_id': ids[email]}), content_type='application/json').status_code == 200

    client.post('/api/users/logout')

    assert _login(client, 'student.one@test.com', 'studpw').status_code == 200
    ts1 = client.get(f'/api/timesheets/my?pay_period_id={pay_period_id}').get_json()
    assert client.post(f"/api/timesheets/{ts1['id']}/submit").status_code == 200
    client.post('/api/users/logout')

    assert _login(client, 'student.two@test.com', 'studpw').status_code == 200
    ts2 = client.get(f'/api/timesheets/my?pay_period_id={pay_period_id}').get_json()
    assert ts2['status'] == 'draft'
    client.post('/api/users/logout')

    assert _login(client, 'sup.bulk@test.com', 'suppw').status_code == 200
    bulk = client.post('/api/timesheets/review/bulk-approve', data=json.dumps({'timesheet_ids': [ts1['id'], ts2['id']]}), content_type='application/json')
    assert bulk.status_code == 200
    payload = bulk.get_json()
    assert ts1['id'] in payload['approved_ids']
    assert any(s['id'] == ts2['id'] for s in payload['skipped'])
