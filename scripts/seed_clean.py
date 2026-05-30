#!/usr/bin/env python
"""Seed database with clean employee structure - 33 CSOs, 12 Trainees, 5 FTOs, 1 Admin."""

from backend.app import create_app
from backend.app.models import User, EmployeeProfile
from backend.app.database import db

app = create_app()

with app.app_context():
    print("Clearing all database tables...")
    # Delete all tables
    db.drop_all()
    db.create_all()
    
    print("Creating new users and profiles...\n")
    
    # Create admin
    admin = User(
        name="Admin",
        email="admin@csuf.edu",
        role="admin"
    )
    admin.set_password("password")
    db.session.add(admin)
    db.session.commit()
    print(f"✓ Admin: admin@csuf.edu (id={admin.id})")
    
    # Create 33 CSO Officers
    print("\nCreating 33 CSO Officers:")
    for i in range(1, 34):
        user = User(
            name=f"CSO Officer {i}",
            email=f"cso{i}@csuf.edu",
            role="employee"
        )
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        
        profile = EmployeeProfile(
            user_id=user.id,
            employee_role="Regular",
            patrol_shift_certified=True,
            lockup_certified=False,
            priority_score=5
        )
        db.session.add(profile)
        if i % 10 == 0:
            print(f"  ✓ Created {i} CSO Officers...")
    
    print(f"  ✓ Created 33 CSO Officers")
    
    # Create 12 CSO Trainees
    print("\nCreating 12 CSO Trainees:")
    for i in range(1, 13):
        user = User(
            name=f"CSO Trainee {i}",
            email=f"trainee{i}@csuf.edu",
            role="trainee"
        )
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        
        profile = EmployeeProfile(
            user_id=user.id,
            employee_role="Trainee",
            patrol_shift_certified=False,
            lockup_certified=False,
            priority_score=3
        )
        db.session.add(profile)
        if i % 5 == 0:
            print(f"  ✓ Created {i} CSO Trainees...")
    
    print(f"  ✓ Created 12 CSO Trainees")
    
    # Create 5 FTO Officers
    print("\nCreating 5 FTO Officers:")
    for i in range(1, 6):
        user = User(
            name=f"FTO Officer {i}",
            email=f"fto{i}@csuf.edu",
            role="FTO"
        )
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        
        profile = EmployeeProfile(
            user_id=user.id,
            employee_role="FTO",
            patrol_shift_certified=True,
            lockup_certified=True,
            priority_score=8
        )
        db.session.add(profile)
    
    print(f"  ✓ Created 5 FTO Officers")
    
    db.session.commit()
    
    print("\n" + "=" * 80)
    print("SEED COMPLETE".center(80))
    print("=" * 80)
    
    # Summary
    users = User.query.all()
    profiles = EmployeeProfile.query.all()
    
    print(f"\nTotal Users Created: {len(users)}")
    print(f"Total Profiles Created: {len(profiles)}")
    print(f"Total Availability Records: 0 (for you to add manually)")
    print(f"Shift Preferences: Not set (for you to add manually)")
    
    print("\n" + "-" * 80)
    print("USERS SUMMARY".center(80))
    print("-" * 80)
    
    print(f"\n{'ID':<4} {'Name':<25} {'Email':<25} {'Role':<12}")
    print("-" * 80)
    for user in users[:5]:
        print(f"{user.id:<4} {user.name:<25} {user.email:<25} {user.role:<12}")
    
    if len(users) > 5:
        print(f"... and {len(users) - 5} more users")
    
    print("\n✅ All set! Availability and shift preferences are ready for you to add.")
    print("\nYou can now:")
    print("  1. Log in as admin@csuf.edu with password 'password'")
    print("  2. Add availability for each employee through the UI")
    print("  3. Set shift preferences for employees (6-hour only, 12-hour only, or both)")

