from datetime import date, timedelta


def test_shift_create_assign_swap_delete(client, app):
    # Import models inside the test to avoid import-time side effects during collection
    from backend.app.database import db
    from backend.app.models import User

    def create_user(email, role='student', password='password'):
        u = User(name=email.split('@')[0], email=email, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    # Create users directly in DB
    with app.app_context():
        admin = create_user('admin@example.com', role='admin')
        student = create_user('student@example.com', role='student')
        # capture simple fields while still attached to session
        admin_email = admin.email
        student_email = student.email
        student_id = student.id

    # Login as admin
    rv = client.post('/api/users/login', json={'email': admin_email, 'password': 'password'})
    assert rv.status_code == 200

    # Create a shift
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rv = client.post('/api/shifts', json={'date': tomorrow, 'start_time': '09:00', 'end_time': '11:00'})
    assert rv.status_code == 201
    sid = rv.get_json().get('id')

    # Assign to student
    rv = client.post('/api/shifts/assign', json={'shift_id': sid, 'user_id': student_id})
    assert rv.status_code == 200

    # Login as student and request swap
    rv = client.post('/api/users/login', json={'email': student_email, 'password': 'password'})
    assert rv.status_code == 200
    rv = client.post('/api/swap_requests', json={'shift_id': sid})
    assert rv.status_code == 201
    srid = rv.get_json().get('id')

    # Approve as admin
    rv = client.post('/api/users/login', json={'email': admin.email, 'password': 'password'})
    assert rv.status_code == 200
    rv = client.post(f'/api/swap_requests/{srid}/decide', json={'action': 'approve'})
    assert rv.status_code == 200

    # Delete shift
    rv = client.delete(f'/api/shifts/{sid}')
    assert rv.status_code == 200
