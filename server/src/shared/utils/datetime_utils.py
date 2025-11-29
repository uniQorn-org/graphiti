"""DateTime conversion utilities for Neo4j compatibility."""

from datetime import datetime, timezone
from typing import Any


def convert_neo4j_datetime(dt: Any) -> datetime | None:
    """
    Convert Neo4j DateTime object to Python datetime.

    Neo4j returns custom DateTime objects that need to be converted
    to standard Python datetime objects for JSON serialization.

    Args:
        dt: Neo4j DateTime object or Python datetime or None

    Returns:
        Python datetime object or None if input is None
    """
    if dt is None:
        return None
    # Neo4j DateTime objects have a to_native() method
    if hasattr(dt, 'to_native'):
        return dt.to_native()
    # Already a Python datetime
    return dt


def format_datetime_iso(dt: datetime | None) -> str | None:
    """
    Format datetime to ISO 8601 string.

    Args:
        dt: Python datetime object or None

    Returns:
        ISO 8601 formatted string (e.g., "2024-01-15T10:30:00Z") or None
    """
    if dt is None:
        return None
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """
    Parse ISO 8601 datetime string to Python datetime.

    Handles both 'Z' suffix and timezone offsets.

    Args:
        dt_str: ISO 8601 formatted string (e.g., "2024-01-15T10:30:00Z")

    Returns:
        Python datetime object with UTC timezone, or None on error

    Examples:
        >>> parse_iso_datetime("2024-01-15T10:30:00Z")
        datetime.datetime(2024, 1, 15, 10, 30, tzinfo=datetime.timezone.utc)

        >>> parse_iso_datetime("2024-01-15T10:30:00+09:00")
        datetime.datetime(2024, 1, 15, 10, 30, tzinfo=datetime.timezone(datetime.timedelta(seconds=32400)))
    """
    if not dt_str:
        return None
    try:
        # Replace 'Z' with '+00:00' for proper ISO parsing
        normalized = dt_str.replace('Z', '+00:00')
        parsed = datetime.fromisoformat(normalized)
        # Ensure timezone is set (default to UTC if naive)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, AttributeError) as e:
        # Return None on parse error
        return None
