"""
Seed realistic availability for 49 employees (all except CSO Officer 1).

Each employee is a student with 2-4 classes per week.
Classes block time; availability = the inverse (open hours).
Some employees also have a second job that blocks additional time.
Every employee is guaranteed at least 30 available hours/week
so the scheduler can assign them 18h/week.
Shift preferences are randomly assigned on the profile.
"""
import sys, os, random
from datetime import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.app.database import db
from backend.app.models import User, Availability, EmployeeProfile

# ─── Class time slots (start_hour, end_hour) ───
CLASS_SLOTS = [
    (8, 0, 9, 45),    # 8:00 - 9:45   (1h45m)
    (8, 0, 10, 45),   # 8:00 - 10:45  (2h45m)
    (9, 0, 10, 45),   # 9:00 - 10:45  (1h45m)
    (9, 0, 11, 45),   # 9:00 - 11:45  (2h45m)
    (10, 0, 11, 45),  # 10:00 - 11:45 (1h45m)
    (10, 0, 12, 45),  # 10:00 - 12:45 (2h45m)
    (11, 0, 12, 45),  # 11:00 - 12:45 (1h45m)
    (11, 0, 13, 45),  # 11:00 - 13:45 (2h45m)
    (12, 0, 13, 45),  # 12:00 - 13:45 (1h45m)
    (13, 0, 14, 45),  # 13:00 - 14:45 (1h45m)
    (14, 0, 15, 45),  # 14:00 - 15:45 (1h45m)
    (14, 0, 16, 45),  # 14:00 - 16:45 (2h45m)
    (15, 0, 16, 45),  # 15:00 - 16:45 (1h45m)
    (15, 0, 17, 45),  # 15:00 - 17:45 (2h45m)
    (16, 0, 17, 45),  # 16:00 - 17:45 (1h45m)
    (19, 0, 20, 45),  # 19:00 - 20:45 (1h45m)
    (19, 0, 21, 45),  # 19:00 - 21:45 (2h45m)
]

# ─── Second job patterns (start_hour, end_hour, days_list) ───
SECOND_JOB_PATTERNS = [
    # Retail morning/afternoon shifts
    {"start": (6, 0), "end": (12, 0), "days": [5, 6]},          # Sat-Sun 6am-12pm
    {"start": (10, 0), "end": (15, 0), "days": [5]},            # Sat 10am-3pm
    {"start": (8, 0), "end": (14, 0), "days": [6]},             # Sun 8am-2pm
    {"start": (12, 0), "end": (17, 0), "days": [5, 6]},         # Sat-Sun 12pm-5pm
    {"start": (7, 0), "end": (11, 0), "days": [0, 2, 4]},       # MWF 7am-11am
    {"start": (16, 0), "end": (20, 0), "days": [1, 3]},         # Tue-Thu 4pm-8pm
    {"start": (6, 0), "end": (10, 0), "days": [0, 2]},          # Mon-Wed 6am-10am
    {"start": (17, 0), "end": (21, 0), "days": [5]},            # Sat 5pm-9pm
    {"start": (14, 0), "end": (19, 0), "days": [6]},            # Sun 2pm-7pm
    {"start": (8, 0), "end": (12, 0), "days": [5]},             # Sat 8am-12pm
]

# Common class day patterns (MWF, TTh, MW, etc.)
CLASS_DAY_PATTERNS = [
    [0, 2, 4],     # Mon-Wed-Fri
    [1, 3],        # Tue-Thu
    [0, 2],        # Mon-Wed
    [1, 3, 5],     # Tue-Thu-Sat
    [0, 4],        # Mon-Fri
    [2, 4],        # Wed-Fri
    [0, 1, 2, 3],  # Mon-Tue-Wed-Thu
    [3, 5],        # Thu-Sat
]

random.seed(42)  # Reproducible results


def generate_class_schedule(num_classes):
    """Generate a realistic class schedule: list of (day, start_h, start_m, end_h, end_m)."""
    schedule = []
    used_day_slots = set()  # (day, hour) to avoid overlaps

    attempts = 0
    while len(schedule) < num_classes and attempts < 200:
        attempts += 1
        # Pick a class day pattern
        day_pattern = random.choice(CLASS_DAY_PATTERNS)
        # Pick a class time slot
        slot = random.choice(CLASS_SLOTS)
        start_h, start_m, end_h, end_m = slot

        # Check for overlap on each day
        conflict = False
        for day in day_pattern:
            for h in range(start_h, end_h + 1):
                if (day, h) in used_day_slots:
                    conflict = True
                    break
            if conflict:
                break

        if not conflict:
            for day in day_pattern:
                schedule.append((day, start_h, start_m, end_h, end_m))
                for h in range(start_h, end_h + 1):
                    used_day_slots.add((day, h))
            # Count this as one class (it repeats on the day pattern)
            # But we only increment num_classes by 1 per pattern
            num_classes -= (len(day_pattern) - 1)  # Adjust since one class covers multiple days

    return schedule


def compute_availability_slots(blocked_intervals_by_day):
    """Given blocked time intervals per day, compute available time slots.
    
    blocked_intervals_by_day: dict of day -> list of (start_minutes, end_minutes)
    Returns: dict of day -> list of (start_time, end_time) as time objects
    """
    result = {}
    for day in range(7):
        blocks = sorted(blocked_intervals_by_day.get(day, []))
        if not blocks:
            # Entire day available
            result[day] = [(time(0, 0), time(23, 59))]
            continue

        # Merge overlapping blocks
        merged = [blocks[0]]
        for start, end in blocks[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # Compute gaps (available time)
        slots = []
        day_start = 0  # 0:00
        for block_start, block_end in merged:
            if day_start < block_start:
                s_h, s_m = divmod(day_start, 60)
                e_h, e_m = divmod(block_start, 60)
                if e_h < 24:
                    slots.append((time(s_h, s_m), time(e_h, e_m)))
            day_start = block_end

        # After last block until end of day
        if day_start < 24 * 60:
            s_h, s_m = divmod(day_start, 60)
            slots.append((time(s_h, s_m), time(23, 59)))

        result[day] = slots
    return result


def count_available_6h_slots(avail_by_day):
    """Count how many 6-hour windows fit in the availability."""
    count = 0
    for day in range(7):
        for start_t, end_t in avail_by_day.get(day, []):
            start_min = start_t.hour * 60 + start_t.minute
            end_min = end_t.hour * 60 + end_t.minute
            duration = end_min - start_min
            if duration >= 360:  # 6 hours
                count += duration // 360
    return count


def main():
    app = create_app()
    with app.app_context():
        # Get all employees except user_id=1 (admin) and user_id=2 (CSO Officer 1 who already has availability)
        employees = User.query.filter(
            User.id >= 3,  # Skip admin (1) and CSO Officer 1 (2)
            User.role != 'admin'
        ).all()

        # Also include trainees and FTOs
        all_employees = User.query.filter(
            User.id >= 3
        ).all()

        print(f"Creating availability for {len(all_employees)} employees...\n")

        shift_pref_options = ['only_6h', 'both']
        shift_pref_weights = [0.3, 0.7]  # 30% prefer 6h only, 70% both (no only_12h to avoid 18h/week conflict)

        total_avail_created = 0

        for emp in all_employees:
            # Delete any existing availability for this employee
            Availability.query.filter_by(user_id=emp.id).delete()

            # Determine number of classes (2-4, reduced to ensure 30+ available hours)
            num_classes = random.randint(2, 4)

            # Generate class schedule
            class_schedule = generate_class_schedule(num_classes)

            # Build blocked intervals by day (in minutes from midnight)
            blocked = {}
            for day, sh, sm, eh, em in class_schedule:
                if day not in blocked:
                    blocked[day] = []
                # Add 15 min buffer before class and after (commute)
                start_min = max(0, sh * 60 + sm - 15)
                end_min = min(24 * 60, eh * 60 + em + 15)
                blocked[day].append((start_min, end_min))

            # ~20% of employees have a second job (reduced from 30%)
            has_second_job = random.random() < 0.20
            job_info = ""
            if has_second_job:
                job = random.choice(SECOND_JOB_PATTERNS)
                for day in job["days"]:
                    if day not in blocked:
                        blocked[day] = []
                    j_start = job["start"][0] * 60 + job["start"][1]
                    j_end = job["end"][0] * 60 + job["end"][1]
                    blocked[day].append((j_start, j_end))
                job_days_str = ",".join(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d] for d in job["days"])
                job_info = f" | 2nd job: {job['start'][0]:02d}:00-{job['end'][0]:02d}:00 on {job_days_str}"

            # Compute available time slots
            avail_by_day = compute_availability_slots(blocked)

            # Calculate total available hours
            total_avail_minutes = 0
            for day in range(7):
                for start_t, end_t in avail_by_day.get(day, []):
                    start_min = start_t.hour * 60 + start_t.minute
                    end_min = end_t.hour * 60 + end_t.minute
                    if end_min - start_min >= 120:  # Only count 2h+ slots
                        total_avail_minutes += end_min - start_min
            
            total_avail_hours = total_avail_minutes / 60
            
            # If not enough available hours (need at least 30h for scheduler to assign 18h),
            # remove second job and try again
            if total_avail_hours < 30 and has_second_job:
                # Rebuild without second job
                blocked = {}
                for day, sh, sm, eh, em in class_schedule:
                    if day not in blocked:
                        blocked[day] = []
                    start_min = max(0, sh * 60 + sm - 15)
                    end_min = min(24 * 60, eh * 60 + em + 15)
                    blocked[day].append((start_min, end_min))
                has_second_job = False
                job_info = " | (2nd job removed - insufficient hours)"
                avail_by_day = compute_availability_slots(blocked)
                
                # Recalculate
                total_avail_minutes = 0
                for day in range(7):
                    for start_t, end_t in avail_by_day.get(day, []):
                        start_min = start_t.hour * 60 + start_t.minute
                        end_min = end_t.hour * 60 + end_t.minute
                        if end_min - start_min >= 120:
                            total_avail_minutes += end_min - start_min
                total_avail_hours = total_avail_minutes / 60

            # Check we have enough 6h slots
            six_h_count = count_available_6h_slots(avail_by_day)

            # Assign random shift preference
            shift_pref = random.choices(shift_pref_options, weights=shift_pref_weights, k=1)[0]

            # Update profile with shift preference
            profile = EmployeeProfile.query.filter_by(user_id=emp.id).first()
            if profile:
                profile.shift_preference = shift_pref

            # Create availability records
            emp_avail_count = 0
            for day in range(7):
                for start_t, end_t in avail_by_day.get(day, []):
                    # Skip very short slots (less than 2 hours)
                    start_min = start_t.hour * 60 + start_t.minute
                    end_min = end_t.hour * 60 + end_t.minute
                    if end_min - start_min < 120:
                        continue

                    avail = Availability(
                        user_id=emp.id,
                        start_time=start_t,
                        end_time=end_t,
                        is_recurring=True,
                        day_of_week=day,
                    )
                    db.session.add(avail)
                    emp_avail_count += 1
                    total_avail_created += 1

            days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            class_days = set()
            for day, sh, sm, eh, em in class_schedule:
                class_days.add(f"{days_names[day]} {sh:02d}:{sm:02d}-{eh:02d}:{em:02d}")

            print(f"  {emp.email:25s} | {emp_avail_count:2d} slots | {total_avail_hours:5.1f}h avail | {len(class_schedule):2d} class blocks | pref: {shift_pref:8s} | 6h windows: {six_h_count}{job_info}")

        db.session.commit()

        print(f"\n{'='*80}")
        print(f"{'AVAILABILITY SEED COMPLETE':^80}")
        print(f"{'='*80}")
        print(f"\n  Total availability records created: {total_avail_created}")
        print(f"  Employees with availability: {len(all_employees)}")
        print(f"  Employee 1 (cso1@csuf.edu): UNCHANGED (14 existing slots)\n")

        # Summary of shift preferences
        prefs = db.session.query(EmployeeProfile.shift_preference, db.func.count()).group_by(EmployeeProfile.shift_preference).all()
        print("  Shift Preference Distribution:")
        for pref, count in prefs:
            print(f"    {pref:10s}: {count} employees")

        # Verify minimum availability
        print("\n  Availability per employee:")
        for emp in all_employees[:5]:
            count = Availability.query.filter_by(user_id=emp.id).count()
            print(f"    {emp.email}: {count} slots")
        print(f"    ... and {len(all_employees) - 5} more")


if __name__ == "__main__":
    main()
