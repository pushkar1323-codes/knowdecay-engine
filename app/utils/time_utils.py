"""
app/utils/time_utils.py
────────────────────────
Shared time/date helpers used across engine modules and services.
All timestamps are UTC and timezone-aware throughout the system.
"""

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    """Return the current UTC datetime (always timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime is UTC timezone-aware.
    Treats naive datetimes as UTC (PostgreSQL stores UTC by convention).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def hours_since(dt: datetime | None) -> float:
    """
    Hours elapsed since `dt`.
    Returns 0.0 if dt is None (treat as 'just now').
    """
    if dt is None:
        return 0.0
    return max(0.0, (utcnow() - as_utc(dt)).total_seconds() / 3_600.0)


def days_since(dt: datetime | None) -> float:
    """
    Days elapsed since `dt`.
    Returns 0.0 if dt is None.
    """
    return hours_since(dt) / 24.0


def days_until(dt: datetime | None) -> float:
    """
    Days remaining until `dt`.
    Returns negative value if `dt` is in the past.
    Returns 0.0 if dt is None.
    """
    if dt is None:
        return 0.0
    return (as_utc(dt) - utcnow()).total_seconds() / 86_400.0


def add_days(dt: datetime, days: float) -> datetime:
    """Add a floating-point number of days to a timezone-aware datetime."""
    return as_utc(dt) + timedelta(days=days)


def is_overdue(next_revision_at: datetime | None) -> bool:
    """
    Return True if the scheduled revision time has passed.
    Items that have never been scheduled are always considered overdue.
    """
    if next_revision_at is None:
        return True
    return utcnow() > as_utc(next_revision_at)


def overdue_ratio(next_revision_at: datetime | None, interval_days: float) -> float:
    """
    How much past due is this item, expressed as a ratio of its interval?
    Used by the priority engine to weight overdue severity.

    Returns 0.0 if item is not yet due.
    Returns 1.0 if item is exactly one interval overdue.
    Returns >1.0 if item is multiple intervals overdue.
    """
    if next_revision_at is None or interval_days <= 0:
        return 1.0
    overdue_days = days_since(next_revision_at)
    if overdue_days <= 0:
        return 0.0
    return overdue_days / interval_days
