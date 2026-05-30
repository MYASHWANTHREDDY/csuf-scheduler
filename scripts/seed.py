"""Seed script for CSUF Scheduler (scripts wrapper).

This inserts an admin and two student users if the users table is empty.
Run from repo root:
  python scripts\seed.py
"""
from datetime import datetime
import sys
import os

from backend.app import create_app
from backend.app.database import db
from backend.app.models import User

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def main():
    app = create_app()
    with app.app_context():
        # Ensure tables exist
        db.create_all()

        existing = User.query.count()
        if existing:
            print(f"Users table not empty (count={existing}). Seed skipped.")
            return

        now = datetime.utcnow()
        admin = User(name='Admin User', email='admin@csuf.edu', role='admin', created_at=now)
        s1 = User(name='Student One', email='s1@csuf.edu', role='student', created_at=now)
        s2 = User(name='Student Two', email='s2@csuf.edu', role='student', created_at=now)
        fto = User(name='FTO User', email='fto@csuf.edu', role='FTO', created_at=now)

        # Set a demo password for seeded users (password)
        try:
            admin.set_password('password')
            s1.set_password('password')
            s2.set_password('password')
            fto.set_password('password')
        except AttributeError:
            pass

        db.session.add_all([admin, s1, s2])
        db.session.commit()

        print('Seed complete. Inserted:')
        print(f' - admin: {admin.email} (id={admin.id})')
        print(f' - student: {s1.email} (id={s1.id})')
        print(f' - student: {s2.email} (id={s2.id})')
        print(f' - fto: {fto.email} (id={fto.id})')


if __name__ == '__main__':
    main()
