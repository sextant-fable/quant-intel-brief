"""Optional local scheduler wiring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

from app.core.config import Settings

DAILY_JOB_ID = "daily_quant_intel_brief"


@dataclass(frozen=True, slots=True)
class SchedulerStartResult:
    """Result of scheduler startup."""

    enabled: bool
    started: bool
    job_id: str | None = None
    message: str | None = None


def parse_daily_run_time(value: str) -> tuple[int, int]:
    """Parse HH:MM scheduler time."""
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise ValueError("Daily run time must use HH:MM format.") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Daily run time must be a valid 24-hour HH:MM time.")
    return hour, minute


def build_scheduler(
    settings: Settings,
    *,
    job_func: Callable[[], Any],
) -> Any | None:
    """Build a local scheduler when explicitly enabled."""
    if not settings.enable_scheduler:
        return None

    hour, minute = parse_daily_run_time(settings.daily_run_time)
    scheduler = BackgroundScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        job_func,
        "cron",
        hour=hour,
        minute=minute,
        id=DAILY_JOB_ID,
        replace_existing=True,
    )
    return scheduler


def start_scheduler(
    settings: Settings,
    *,
    job_func: Callable[[], Any],
) -> SchedulerStartResult:
    """Start the optional local scheduler only when explicitly enabled."""
    scheduler = build_scheduler(settings, job_func=job_func)
    if scheduler is None:
        return SchedulerStartResult(
            enabled=False,
            started=False,
            message="Scheduler disabled by ENABLE_SCHEDULER.",
        )

    scheduler.start()
    return SchedulerStartResult(enabled=True, started=True, job_id=DAILY_JOB_ID)


__all__ = [
    "DAILY_JOB_ID",
    "SchedulerStartResult",
    "build_scheduler",
    "parse_daily_run_time",
    "start_scheduler",
]
