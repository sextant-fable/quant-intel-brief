"""Timezone utilities for local display and UTC storage."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
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


def next_regular_market_open(
    value: datetime | None = None,
    timezone_name: str = "America/New_York",
) -> datetime:
    """Return the next weekday 09:30 regular-session open in UTC."""
    timezone = ZoneInfo(timezone_name)
    local_now = ensure_utc(value or utc_now()).astimezone(timezone)
    candidate = datetime.combine(local_now.date(), time(9, 30), tzinfo=timezone)
    if local_now >= candidate:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)
