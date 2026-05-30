"""Availability checking utilities.

Provides helper functions for validating whether an employee is available
for a given shift, considering their availability windows and leave dates.
"""

from datetime import date, time, timedelta

try:
    from ..models import Availability, LeaveRequest
except (ImportError, ModuleNotFoundError):
    from models import Availability, LeaveRequest


def _time_in_range(
    check_time: time, range_start: time, range_end: time, range_spans_midnight: bool = False
) -> bool:
    """Check if a time falls within a range, accounting for midnight-spanning ranges.

    Args:
        check_time: The time to check
        range_start: Start of the range
        range_end: End of the range
        range_spans_midnight: Whether the range spans midnight (end < start)

    Returns:
        True if check_time is within the range
    """
    if range_spans_midnight:
        # Range spans midnight (e.g., 22:00 - 06:00)
        return check_time >= range_start or check_time <= range_end
    else:
        # Normal range
        return range_start <= check_time <= range_end


def _shift_within_window(
    shift_start: time, shift_end: time, window_start: time, window_end: time
) -> bool:
    """Check if a shift time falls completely within an availability window.

    Handles both normal and midnight-spanning windows and shifts.

    Args:
        shift_start: Start time of the shift
        shift_end: End time of the shift
        window_start: Start of the availability window
        window_end: End of the availability window

    Returns:
        True if the entire shift fits within the window
    """
    shift_spans_midnight = shift_end < shift_start
    window_spans_midnight = window_end < window_start

    if shift_spans_midnight and window_spans_midnight:
        # Both span midnight - check if shift is within window
        # Window: start to 00:00, then 00:00 to end
        # Shift: start to 00:00, then 00:00 to end
        # Shift fits if: shift_start >= window_start AND shift_end <= window_end
        return shift_start >= window_start and shift_end <= window_end

    elif shift_spans_midnight and not window_spans_midnight:
        # Shift spans midnight but window doesn't - shift doesn't fit
        return False

    elif not shift_spans_midnight and window_spans_midnight:
        # Window spans midnight but shift doesn't
        # Window: start to 00:00, then 00:00 to end
        # Shift must fit in one of these parts
        # Part 1: >= window_start (before midnight)
        # Part 2: <= window_end (after midnight)
        return shift_start >= window_start or shift_end <= window_end

    else:
        # Neither spans midnight - simple check
        return window_start <= shift_start and shift_end <= window_end


def _availability_windows_for_date(user_id: int, shift_date: date):
    """Return all availability windows for a user on a specific date."""
    one_time_avail = Availability.query.filter(
        Availability.user_id == user_id,
        Availability.is_recurring.is_(False),
        Availability.date == shift_date,
    ).all()

    day_of_week = shift_date.weekday()  # 0=Monday, 6=Sunday
    recurring_avail = Availability.query.filter(
        Availability.user_id == user_id,
        Availability.is_recurring.is_(True),
        Availability.day_of_week == day_of_week,
        (Availability.effective_until.is_(None)) | (Availability.effective_until >= shift_date),
    ).all()

    return one_time_avail + recurring_avail


def _availability_windows_from_records(availabilities, shift_date: date):
    """Return availability windows from a preloaded availability record list."""
    windows = []
    day_of_week = shift_date.weekday()  # 0=Monday, 6=Sunday
    for avail in availabilities:
        if avail.is_recurring:
            if avail.day_of_week == day_of_week and (
                avail.effective_until is None or avail.effective_until >= shift_date
            ):
                windows.append(avail)
        elif avail.date == shift_date:
            windows.append(avail)
    return windows


def _format_windows(windows):
    """Format availability windows for error messages."""
    window_strs = []
    for window in windows:
        if window.is_recurring:
            day_name = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ][window.day_of_week]
            window_strs.append(
                f"Every {day_name}: {window.start_time.strftime('%H:%M')} - {window.end_time.strftime('%H:%M')}"
            )
        else:
            window_strs.append(
                f"{window.date}: {window.start_time.strftime('%H:%M')} - {window.end_time.strftime('%H:%M')}"
            )
    return window_strs


def is_available_from_windows(
    shift_date: date,
    shift_start: time,
    shift_end: time,
    all_windows,
    next_day_windows=None,
    has_leave: bool = False,
    has_next_day_leave: bool = False,
) -> tuple[bool, str]:
    """Check availability using preloaded availability windows.

    This mirrors :func:`is_available_for_shift` but avoids database queries.
    """
    if has_leave:
        return False, f"User has approved leave on {shift_date}"

    if not all_windows:
        return True, ""

    shift_spans_midnight = shift_end < shift_start

    if shift_spans_midnight:
        next_day_windows = next_day_windows or []

        if has_next_day_leave:
            return False, (
                f"User is not available during overnight shift time. Available: "
                f"{', '.join(_format_windows(all_windows))}"
            )

        if not next_day_windows:
            return False, (
                f"User is not available during overnight shift time. Available: "
                f"{', '.join(_format_windows(all_windows))}"
            )

        end_of_day = time(23, 59, 0)
        start_of_day = time(0, 0, 0)

        day1_ok = False
        for window in all_windows:
            window_spans_midnight = window.end_time < window.start_time
            if window_spans_midnight:
                if shift_start >= window.start_time:
                    day1_ok = True
                    break
            elif window.start_time <= shift_start and window.end_time >= end_of_day:
                day1_ok = True
                break

        if not day1_ok:
            return False, (
                f"User is not available during overnight shift time. Available: "
                f"{', '.join(_format_windows(all_windows))}"
            )

        for window in next_day_windows:
            window_spans_midnight = window.end_time < window.start_time
            if window_spans_midnight:
                if shift_end <= window.end_time:
                    return True, ""
            elif window.start_time <= start_of_day and window.end_time >= shift_end:
                return True, ""

        return False, (
            f"User is not available during overnight shift time. Available: "
            f"{', '.join(_format_windows(all_windows + next_day_windows))}"
        )

    for window in all_windows:
        if _shift_within_window(shift_start, shift_end, window.start_time, window.end_time):
            return True, ""

    return (
        False,
        f"User is not available during shift time. Available: {', '.join(_format_windows(all_windows))}",
    )


def is_available_for_shift(
    user_id: int, shift_date: date, shift_start: time, shift_end: time
) -> tuple[bool, str]:
    """Check if a user is available for a shift.

    Args:
        user_id: ID of the user
        shift_date: Date of the shift
        shift_start: Start time of the shift (time object)
        shift_end: End time of the shift (time object)

    Returns:
        Tuple of (is_available: bool, reason: str)
        - (True, '') if available
        - (False, reason) if not available with explanation
    """

    # Check if user has any leave on this date
    leave_request = LeaveRequest.query.filter(
        LeaveRequest.user_id == user_id,
        LeaveRequest.start_date <= shift_date,
        LeaveRequest.end_date >= shift_date,
        LeaveRequest.status == "approved",
    ).first()

    if leave_request:
        return False, f"User has approved leave on {shift_date}"

    all_windows = _availability_windows_for_date(user_id, shift_date)

    # If no availability windows defined, consider user available (no restrictions)
    if not all_windows:
        return True, ""

    shift_spans_midnight = shift_end < shift_start

    if shift_spans_midnight:
        next_day = shift_date + timedelta(days=1)
        next_day_windows = _availability_windows_for_date(user_id, next_day)

        if not next_day_windows:
            return False, (
                f"User is not available during overnight shift time. Available: "
                f"{', '.join(_format_windows(all_windows))}"
            )

        end_of_day = time(23, 59, 0)
        start_of_day = time(0, 0, 0)

        day1_ok = False
        for window in all_windows:
            window_spans_midnight = window.end_time < window.start_time
            if window_spans_midnight:
                if shift_start >= window.start_time:
                    day1_ok = True
                    break
            elif window.start_time <= shift_start and window.end_time >= end_of_day:
                day1_ok = True
                break

        if not day1_ok:
            return False, (
                f"User is not available during overnight shift time. Available: "
                f"{', '.join(_format_windows(all_windows))}"
            )

        for window in next_day_windows:
            window_spans_midnight = window.end_time < window.start_time
            if window_spans_midnight:
                if shift_end <= window.end_time:
                    return True, ""
            elif window.start_time <= start_of_day and window.end_time >= shift_end:
                return True, ""

        return False, (
            f"User is not available during overnight shift time. Available: "
            f"{', '.join(_format_windows(all_windows + next_day_windows))}"
        )

    # Check if shift fits within any availability window
    for window in all_windows:
        if _shift_within_window(shift_start, shift_end, window.start_time, window.end_time):
            return True, ""

    # Format availability windows for error message
    return (
        False,
        f"User is not available during shift time. Available: {', '.join(_format_windows(all_windows))}",
    )
