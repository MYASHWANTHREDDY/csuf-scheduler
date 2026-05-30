"""Date and time parsing utilities.

Provides shared helper functions for parsing date and time strings from API requests.
"""

from datetime import date, datetime, time


def parse_date(date_string: str | None) -> date | None:
    """Parse a date string in YYYY-MM-DD format.

    Args:
        date_string: String in YYYY-MM-DD format.

    Returns:
        date object if valid, None if invalid or empty.
    """
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_time(time_string: str | None) -> time | None:
    """Parse a time string in HH:MM format.

    Args:
        time_string: String in HH:MM format.

    Returns:
        time object if valid, None if invalid or empty.
    """
    try:
        return datetime.strptime(time_string, "%H:%M").time()
    except (ValueError, TypeError):
        return None
