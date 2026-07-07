"""Timezone utilities for local display and UTC storage."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Return the current UTC time as an aware datetime."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_timezone(value: datetime, timezone_name: str) -> datetime:
    """Convert a datetime to the configured display timezone."""
    return ensure_utc(value).astimezone(ZoneInfo(timezone_name))
