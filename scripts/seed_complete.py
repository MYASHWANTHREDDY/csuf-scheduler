#!/usr/bin/env python
"""Comprehensive seed script for CSUF Scheduler demo.

This creates:
- Admin user
- Multiple student/FTO employees with realistic availability patterns
- Shift templates for scheduling
- Sample shifts and assignments

Run from repo root:
  python scripts/seed_complete.py
"""

from datetime import datetime, time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from backend.app.database import db
from backend.app.models import User, Availability, Shift, ShiftTemplate

def main():
    app = create_app()
    with app.app_context():
        # Option to reset database completely
        import sys
        if '--reset' in sys.argv:
            print("Dropping all tables...")
            db.drop_all()
        
        # Ensure tables exist
        db.create_all()

        existing = User.query.count()
        if existing:
            print(f"Database not empty (users count={existing}). Seed skipped.")
            print("  Use '--reset' flag to clear and rebuild: python scripts/seed_complete.py --reset")
            return

        now = datetime.utcnow()
        
        # Create users
        admin = User(name='Admin User', email='admin@csuf.edu', role='admin', created_at=now)
        admin.set_password('password')
        
        employees = [
            User(name='Yashwanth', email='yashwanth@csuf.edu', role='student', created_at=now),
            User(name='Alice Johnson', email='alice@csuf.edu', role='FTO', created_at=now),
            User(name='Bob Smith', email='bob@csuf.edu', role='student', created_at=now),
            User(name='Carol White', email='carol@csuf.edu', role='regular', created_at=now),
            User(name='David Brown', email='david@csuf.edu', role='trainee', created_at=now),
            User(name='Emma Davis', email='emma@csuf.edu', role='student', created_at=now),
        ]
        
        for emp in employees:
            emp.set_password('password')
        
        db.session.add(admin)
        db.session.add_all(employees)
        db.session.commit()
        
        print('Created users:')
        print(f' - admin: {admin.email} (id={admin.id})')
        
        # Create availability patterns
        # Pattern 1: Can work overnight shifts (PSL: 18:30-00:30)
        # Available: 00:00-08:30 and 12:30-23:59
        psl_availability = [
            (0, time(0, 0), time(8, 30)),     # Monday: 00:00-08:30
            (0, time(12, 30), time(23, 59)), # Monday: 12:30-23:59
            (1, time(0, 0), time(8, 30)),    # Tuesday: 00:00-08:30
            (1, time(12, 30), time(23, 59)), # Tuesday: 12:30-23:59
            (2, time(0, 0), time(8, 30)),    # Wednesday: 00:00-08:30
            (2, time(12, 30), time(23, 59)), # Wednesday: 12:30-23:59
            (3, time(0, 0), time(8, 30)),    # Thursday: 00:00-08:30
            (3, time(12, 30), time(23, 59)), # Thursday: 12:30-23:59
            (4, time(0, 0), time(8, 30)),    # Friday: 00:00-08:30
            (4, time(12, 30), time(23, 59)), # Friday: 12:30-23:59
            (5, time(0, 0), time(8, 30)),    # Saturday: 00:00-08:30
            (5, time(12, 30), time(23, 59)), # Saturday: 12:30-23:59
            (6, time(0, 0), time(8, 30)),    # Sunday: 00:00-08:30
            (6, time(12, 30), time(23, 59)), # Sunday: 12:30-23:59
        ]
        
        # Pattern 2: Standard daytime shifts (PS: 06:30-18:30)
        # Available: 06:30-23:59
        ps_availability = [
            (0, time(6, 30), time(23, 59)),  # Monday: 06:30-23:59
            (1, time(6, 30), time(23, 59)),  # Tuesday: 06:30-23:59
            (2, time(6, 30), time(23, 59)),  # Wednesday: 06:30-23:59
            (3, time(6, 30), time(23, 59)),  # Thursday: 06:30-23:59
            (4, time(6, 30), time(23, 59)),  # Friday: 06:30-23:59
            (5, time(6, 30), time(23, 59)),  # Saturday: 06:30-23:59
            (6, time(6, 30), time(23, 59)),  # Sunday: 06:30-23:59
        ]
        
        # Assign availability patterns to employees
        patterns = [(psl_availability, "PSL (overnight)"), (ps_availability, "PS (daytime)")]
        
        avail_count = 0
        for i, emp in enumerate(employees):
            pattern, pattern_name = patterns[i % len(patterns)]
            
            for day_of_week, start_time, end_time in pattern:
                avail = Availability(
                    user_id=emp.id,
                    start_time=start_time,
                    end_time=end_time,
                    is_recurring=True,
                    day_of_week=day_of_week
                )
                db.session.add(avail)
                avail_count += 1
            
            print(f' - {emp.name}: {pattern_name} pattern ({avail_count // len(pattern)} slots)')
        
        db.session.commit()
        
        # Create shift templates
        from datetime import timedelta
        ps_am_duration = 6   # 06:30-12:30 = 6 hours
        ps_pm_duration = 6   # 12:30-18:30 = 6 hours
        psl_duration = 6     # 18:30-00:30 = 6 hours (crosses midnight)
        
        templates = [
            ShiftTemplate(
                name='PS (Morning)', 
                start_time=time(6, 30), 
                end_time=time(12, 30),
                duration_hours=ps_am_duration,
                shift_type='PS',
                required_staff=2
            ),
            ShiftTemplate(
                name='PS (Afternoon)', 
                start_time=time(12, 30), 
                end_time=time(18, 30),
                duration_hours=ps_pm_duration,
                shift_type='PS',
                required_staff=2
            ),
            ShiftTemplate(
                name='PSL (Late)', 
                start_time=time(18, 30), 
                end_time=time(0, 30),
                duration_hours=psl_duration,
                shift_type='PSL',
                required_staff=2
            ),
        ]
        db.session.add_all(templates)
        db.session.commit()
        
        print('\nSeed complete. Summary:')
        print(f' - Created {len(employees)} employees')
        print(f' - Created {avail_count} availability records')
        print(f' - Created {len(templates)} shift templates')
        print('\nAvailability patterns:')
        print(' - 3 employees: PSL pattern (00:00-08:30 & 12:30-23:59) - can work overnight shifts')
        print(' - 3 employees: PS pattern (06:30-23:59) - daytime shifts only')

if __name__ == '__main__':
    main()
