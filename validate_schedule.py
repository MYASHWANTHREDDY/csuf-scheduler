"""Validate a generated schedule against staffing requirements and availability."""
import sys, json
from datetime import datetime, time, timedelta
from collections import defaultdict

sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.database import db
from backend.app.models import GeneratedSchedule, User, ShiftTemplate, Availability

app = create_app()


def _get_label_for_template(template_name, start_time):
    """Map template to label the same way the engine does: by start_hour."""
    hour = start_time.hour
    if hour < 10:
        return "PS_AM"
    elif hour < 15:
        return "PS_PM"
    else:
        return "PSL"


def _is_available_for_shift(emp_avails_by_dow, shift_start, shift_end, day_of_week):
    """Check availability, correctly handling overnight shifts."""
    is_overnight = shift_end < shift_start

    if is_overnight:
        # Day 1: need availability covering shift_start to ~23:59
        day1_avails = emp_avails_by_dow.get(day_of_week, [])
        day1_ok = False
        for avail in day1_avails:
            a_start, a_end = avail.start_time, avail.end_time
            a_spans = a_end < a_start
            if a_spans:
                # Avail like 18:00-06:00 — covers shift_start onward
                if shift_start >= a_start:
                    day1_ok = True
                    break
            else:
                # Normal window — must cover shift_start to end of day
                if a_start <= shift_start and a_end >= time(23, 59):
                    day1_ok = True
                    break
        if not day1_ok:
            return False

        # Day 2: need availability covering 00:00 to shift_end
        next_dow = (day_of_week + 1) % 7
        day2_avails = emp_avails_by_dow.get(next_dow, [])
        for avail in day2_avails:
            a_start, a_end = avail.start_time, avail.end_time
            a_spans = a_end < a_start
            if a_spans:
                if shift_end <= a_end:
                    return True
            else:
                if a_start <= time(0, 0) and a_end >= shift_end:
                    return True
        return False
    else:
        # Regular (non-overnight) shift
        avails = emp_avails_by_dow.get(day_of_week, [])
        for avail in avails:
            a_start, a_end = avail.start_time, avail.end_time
            a_spans = a_end < a_start
            if a_spans:
                if shift_start >= a_start or shift_end <= a_end:
                    return True
            else:
                if a_start <= shift_start and shift_end <= a_end:
                    return True
        return False


def validate_schedule(schedule_obj=None, verbose=True):
    """Validate a schedule. Returns (is_valid, violations_list)."""
    with app.app_context():
        schedule = schedule_obj or GeneratedSchedule.query.order_by(
            GeneratedSchedule.created_at.desc()
        ).first()

        if not schedule:
            if verbose:
                print("ERROR: No schedule found")
            return True, []

        if verbose:
            print(f"Validating Schedule: {schedule.config.name}")
            print(f"Period: {schedule.config.start_date} to {schedule.config.end_date}")
            print("=" * 80)

        schedule_data = json.loads(schedule.schedule_data) if schedule.schedule_data else []
        staffing_req = json.loads(schedule.config.daily_staffing_requirements)

        violations = []
        templates = {t.id: t for t in ShiftTemplate.query.all()}

        # ==================================================================
        # 1. Staffing Requirements (on-site coverage per time slot)
        # ==================================================================
        if verbose:
            print("\n[STAFFING REQUIREMENTS]")

        # Time slots that each label represents
        TIME_SLOTS = {
            'PS_AM': (6.5, 12.5),   # 06:30-12:30
            'PS_PM': (12.5, 18.5),  # 12:30-18:30
            'PSL':   (18.5, 24.5),  # 18:30-00:30
        }

        def _template_covers_slot(template, slot_start, slot_end):
            t_start = template.start_time.hour + template.start_time.minute / 60
            t_end = template.end_time.hour + template.end_time.minute / 60
            if t_end <= t_start:  # overnight
                t_end += 24
            return t_start < slot_end and t_end > slot_start

        for day_data in schedule_data:
            date_str = day_data["date"]
            day_name = day_data["day_of_week"]
            day_idx = datetime.strptime(date_str, "%Y-%m-%d").weekday()

            for label in ["PS_AM", "PS_PM", "PSL"]:
                slot_start, slot_end = TIME_SLOTS[label]

                # Count all employees on-site during this time slot
                count = 0
                for shift in day_data["shifts"]:
                    t = templates.get(shift["template_id"])
                    if t and _template_covers_slot(t, slot_start, slot_end):
                        count += len(shift["assigned"])

                req = staffing_req.get(label, {}).get(str(day_idx), 0)
                if isinstance(req, dict):
                    rmin = req.get("min", 0)
                    rmax = req.get("max", 999)
                else:
                    rmin = rmax = int(req) if req else 0

                ok = rmin <= count <= rmax
                if verbose:
                    print(f"  {date_str} {day_name:9} {label:6}: {count} on-site (need {rmin}-{rmax}) [{'OK' if ok else 'VIOLATION'}]")
                if not ok:
                    if count < rmin:
                        violations.append(f"UNDERSTAFFED: {date_str} {label}: {count} on-site (need min {rmin})")
                    else:
                        violations.append(f"OVERSTAFFED: {date_str} {label}: {count} on-site (max {rmax})")

        # ==================================================================
        # 2. Employee Availability (overnight-aware)
        # ==================================================================
        if verbose:
            print("\n[EMPLOYEE AVAILABILITY]")

        # Build avail map: {user_id: {day_of_week: [avail_records]}}
        avail_map = defaultdict(lambda: defaultdict(list))
        for avail in Availability.query.all():
            if avail.day_of_week is not None:
                avail_map[avail.user_id][avail.day_of_week].append(avail)

        for day_data in schedule_data:
            date_str = day_data["date"]
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            dow = shift_date.weekday()

            for shift in day_data["shifts"]:
                t = templates.get(shift["template_id"])
                if not t:
                    continue

                for assigned in shift["assigned"]:
                    emp_id = assigned["employee_id"]
                    emp_name = assigned["name"]
                    emp_avails_by_dow = avail_map.get(emp_id, {})

                    ok = _is_available_for_shift(
                        emp_avails_by_dow, t.start_time, t.end_time, dow
                    )
                    if verbose:
                        print(f"  {emp_name:25} {date_str} {t.name:15} [{'OK' if ok else 'VIOLATION'}]")
                    if not ok:
                        violations.append(
                            f"NOT AVAILABLE: {emp_name} on {date_str} {t.name}"
                        )

        # ==================================================================
        # 3. Max Weekly Hours
        # ==================================================================
        if verbose:
            print("\n[MAX WEEKLY HOURS]")

        max_weekly = schedule.config.max_weekly_hours or 20
        emp_hours = defaultdict(float)
        emp_names = {}
        for day_data in schedule_data:
            for shift in day_data["shifts"]:
                dur = shift.get("duration_hours", 6)
                for assigned in shift["assigned"]:
                    emp_hours[assigned["employee_id"]] += dur
                    emp_names[assigned["employee_id"]] = assigned["name"]

        # Group by week (7-day windows from schedule start)
        dates_in_schedule = [
            datetime.strptime(d["date"], "%Y-%m-%d").date() for d in schedule_data
        ]
        if dates_in_schedule:
            start_date = min(dates_in_schedule)
            num_weeks = max(1, len(dates_in_schedule) // 7)
            target_max = max_weekly * num_weeks

            for eid, hours in emp_hours.items():
                ok = hours <= target_max
                if verbose:
                    print(f"  {emp_names[eid]:25} {hours:5.1f}h / {target_max}h [{'OK' if ok else 'VIOLATION'}]")
                if not ok:
                    violations.append(
                        f"OVER HOURS: {emp_names[eid]} worked {hours}h (max {target_max}h for {num_weeks} week(s))"
                    )

        # ==================================================================
        # 4. Trainee-FTO Pairings
        # ==================================================================
        if verbose:
            print("\n[TRAINEE-FTO PAIRINGS]")

        for day_data in schedule_data:
            date_str = day_data["date"]
            for shift in day_data["shifts"]:
                fto_ids = {a["employee_id"] for a in shift["assigned"] if a["role"] == "FTO"}
                for assigned in shift["assigned"]:
                    if assigned["role"] != "Trainee":
                        continue
                    paired = assigned.get("paired_with")
                    ok = paired and paired in fto_ids
                    if verbose:
                        print(f"  {assigned['name']:25} {date_str} {shift['name']:15} paired={paired} [{'OK' if ok else 'VIOLATION'}]")
                    if not ok:
                        violations.append(
                            f"PAIRING: {assigned['name']} on {date_str} {shift['name']} - {'no FTO paired' if not paired else f'FTO {paired} not in shift'}"
                        )

        # ==================================================================
        # 5. Rest Period (8h between shifts)
        # ==================================================================
        if verbose:
            print("\n[REST PERIODS]")

        min_rest = schedule.config.min_rest_hours or 8
        # Build per-employee shift list ordered by date+time
        emp_shifts = defaultdict(list)
        for day_data in schedule_data:
            date_str = day_data["date"]
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            for shift in day_data["shifts"]:
                t = templates.get(shift["template_id"])
                if not t:
                    continue
                end_dt = datetime.combine(shift_date, t.end_time)
                if t.end_time < t.start_time:
                    end_dt += timedelta(days=1)
                start_dt = datetime.combine(shift_date, t.start_time)
                for assigned in shift["assigned"]:
                    emp_shifts[assigned["employee_id"]].append(
                        (start_dt, end_dt, assigned["name"], t.name, date_str)
                    )

        for eid, shifts in emp_shifts.items():
            shifts.sort()
            for i in range(len(shifts) - 1):
                _, end1, name, sname1, d1 = shifts[i]
                start2, _, _, sname2, d2 = shifts[i + 1]
                gap = (start2 - end1).total_seconds() / 3600
                if gap < min_rest:
                    if verbose:
                        print(f"  {name:25} {d1} {sname1} -> {d2} {sname2}: {gap:.1f}h gap [VIOLATION]")
                    violations.append(
                        f"REST: {name} only {gap:.1f}h rest between {d1} {sname1} and {d2} {sname2} (need {min_rest}h)"
                    )

        # ==================================================================
        # 6. Consecutive Days
        # ==================================================================
        if verbose:
            print("\n[CONSECUTIVE DAYS]")

        max_consec = schedule.config.max_consecutive_days or 5
        emp_dates = defaultdict(set)
        for day_data in schedule_data:
            shift_date = datetime.strptime(day_data["date"], "%Y-%m-%d").date()
            for shift in day_data["shifts"]:
                for assigned in shift["assigned"]:
                    emp_dates[assigned["employee_id"]].add(shift_date)
                    emp_names[assigned["employee_id"]] = assigned["name"]

        for eid, dates_set in emp_dates.items():
            sorted_dates = sorted(dates_set)
            streak = 1
            for i in range(1, len(sorted_dates)):
                if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                    streak += 1
                    if streak > max_consec:
                        name = emp_names.get(eid, f"Emp {eid}")
                        if verbose:
                            print(f"  {name:25} {streak} consecutive days [VIOLATION]")
                        violations.append(
                            f"CONSECUTIVE: {name} worked {streak} consecutive days (max {max_consec})"
                        )
                        break
                else:
                    streak = 1

        # ==================================================================
        # Summary
        # ==================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("VALIDATION RESULTS")
            print("=" * 80)
            if violations:
                print(f"\nVIOLATIONS FOUND: {len(violations)}")
                for i, v in enumerate(violations, 1):
                    print(f"  {i}. {v}")
            else:
                print("\nSUCCESS: No violations found!")

        return len(violations) == 0, violations


if __name__ == "__main__":
    ok, _ = validate_schedule()
    sys.exit(0 if ok else 1)
